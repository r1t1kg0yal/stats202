#!/usr/bin/env python3
"""
NY Fed Markets Data -- Complete Markets API Client

Single-script client for the New York Fed Markets API (markets.newyorkfed.org).
Covers all 10 public databases:
  1. Reference rates (SOFR, EFFR, OBFR, TGCR, BGCR)
  2. SOMA holdings (summary + CUSIP-level Treasury & Agency/MBS + WAM)
  3. Repo/reverse-repo operations
  4. Primary dealer statistics
  5. Treasury securities operations (outright purchases/sales)
  6. Agency MBS operations (purchases, sales, rolls, swaps)
  7. Securities lending operations
  8. Central bank liquidity swaps (FX swap lines)
  9. SOMA detailed holdings (monthly, by type, by CUSIP)
  10. Operations dashboard (combined OMO view)

No auth required. No rate limit documented but polite 0.2s between calls.

Usage:
    python nyfed.py                                  # interactive CLI
    python nyfed.py rates                            # all reference rates latest
    python nyfed.py sofr --obs 60                    # SOFR last 60 observations
    python nyfed.py soma                             # SOMA holdings latest + trend
    python nyfed.py soma-holdings                    # CUSIP-level Treasury holdings
    python nyfed.py soma-agency                      # CUSIP-level Agency/MBS holdings
    python nyfed.py soma-cusip 912810QA9             # single CUSIP history
    python nyfed.py soma-wam                         # weighted average maturity
    python nyfed.py soma-monthly --last 24           # monthly SOMA data
    python nyfed.py tsy-ops                          # treasury securities operations
    python nyfed.py ambs-ops                         # agency MBS operations
    python nyfed.py seclending                       # securities lending operations
    python nyfed.py fxswaps                          # central bank liquidity swaps
    python nyfed.py repo                             # latest repo operations
    python nyfed.py rrp                              # latest ON RRP results
    python nyfed.py pd-positions                     # primary dealer positioning
    python nyfed.py pd-snapshot                      # latest PD survey all series
    python nyfed.py funding-snapshot                 # combined rates + liquidity view
    python nyfed.py qt-monitor                       # QT runoff tracker
    python nyfed.py operations-summary               # all open market operations
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

BASE_URL = "https://markets.newyorkfed.org"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

RATE_TYPES = {
    "sofr":  {"path": "secured/sofr",   "label": "SOFR",  "desc": "Secured Overnight Financing Rate"},
    "effr":  {"path": "unsecured/effr", "label": "EFFR",  "desc": "Effective Federal Funds Rate"},
    "obfr":  {"path": "unsecured/obfr", "label": "OBFR",  "desc": "Overnight Bank Funding Rate"},
    "tgcr":  {"path": "secured/tgcr",   "label": "TGCR",  "desc": "Tri-Party General Collateral Rate"},
    "bgcr":  {"path": "secured/bgcr",   "label": "BGCR",  "desc": "Broad General Collateral Rate"},
}

PD_KEY_SERIES = {
    "PDPOSGST-TOT":  "Treasury Positions (ex-TIPS)",
    "PDPOSCS-TOT":   "Corporate Securities Positions",
    "PDPOSMBS-TOT":  "MBS Positions",
    "PDPOSFGS-TOT":  "Agency/GSE Positions (ex-MBS)",
}

QT_CAPS = {"treasury": 25.0, "mbs": 35.0}

TSY_OPERATIONS = ["all", "purchases", "sales"]
TSY_INCLUDE = ["summary", "details"]

AMBS_OPERATIONS = ["all", "purchases", "sales", "roll", "swap"]
AMBS_INCLUDE = ["summary", "details"]

SECLENDING_OPERATIONS = ["all", "seclending", "extensions"]
SECLENDING_INCLUDE = ["summary", "details"]

FXS_TYPES = ["all", "usdollar", "nonusdollar"]

SOMA_TSY_TYPES = ["all", "bills", "notesbonds", "frn", "tips"]
SOMA_AGENCY_TYPES = ["all", "agency debts", "mbs", "cmbs"]

REQUEST_DELAY = 0.2


# --- HTTP + Parsing ----------------------------------------------------------

def _request(endpoint, params=None, max_retries=3):
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
            if not r.text.strip():
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


def _safe_float(val, default=0.0):
    if val is None:
        return default
    try:
        return float(str(val).strip().replace(",", ""))
    except (ValueError, TypeError):
        return default


def _parse_date(val):
    if not val:
        return ""
    return str(val)[:10]


def _fmt_num(n, sign=True, decimals=0):
    if decimals > 0:
        if sign:
            return f"{n:+,.{decimals}f}"
        return f"{n:,.{decimals}f}"
    n = int(round(n))
    if sign:
        return f"{n:+,}"
    return f"{n:,}"


def _fmt_pct(p, sign=True):
    if sign:
        return f"{p:+.2f}%"
    return f"{p:.2f}%"


def _fmt_bps(p, sign=True):
    if sign:
        return f"{p:+.1f}bp"
    return f"{p:.1f}bp"


def _fmt_billions(val, decimals=1):
    return f"${val:,.{decimals}f}B"


def _str_to_billions(val):
    f = _safe_float(val)
    return f / 1e9


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


# --- Data Fetchers: Reference Rates ------------------------------------------

def _fetch_all_rates_latest():
    data = _request("api/rates/all/latest.json")
    if not data:
        return []
    return data.get("refRates", [])


def _fetch_rate_last(rate_key, n=30):
    info = RATE_TYPES.get(rate_key)
    if not info:
        print(f"  Unknown rate type: {rate_key}")
        return []
    data = _request(f"api/rates/{info['path']}/last/{n}.json")
    if not data:
        return []
    return data.get("refRates", [])


def _fetch_rate_search(rate_key, start_date, end_date):
    info = RATE_TYPES.get(rate_key)
    if not info:
        print(f"  Unknown rate type: {rate_key}")
        return []
    data = _request(
        f"api/rates/{info['path']}/search.json",
        params={"startDate": start_date, "endDate": end_date},
    )
    if not data:
        return []
    return data.get("refRates", [])


# --- Data Fetchers: SOMA Summary ---------------------------------------------

def _fetch_soma_summary():
    data = _request("api/soma/summary.json")
    if not data:
        return []
    soma = data.get("soma", {})
    return soma.get("summary", [])


def _fetch_soma_latest_date():
    data = _request("api/soma/asofdates/latest.json")
    if not data:
        return None
    dates = data.get("soma", {}).get("asOfDates", [])
    return dates[0] if dates else None


# --- Data Fetchers: SOMA Detailed Holdings ------------------------------------

def _fetch_soma_tsy_holdings(date):
    data = _request(f"api/soma/tsy/get/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_tsy_holdingtype(holding_type, date):
    data = _request(f"api/soma/tsy/get/{holding_type}/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_tsy_cusip(cusip):
    data = _request(f"api/soma/tsy/get/cusip/{cusip}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_tsy_wam(holding_type, date):
    data = _request(f"api/soma/tsy/wam/{holding_type}/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_tsy_monthly():
    data = _request("api/soma/tsy/get/monthly.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_tsy_release_log():
    data = _request("api/soma/tsy/get/release_log.json")
    if not data:
        return []
    return data.get("soma", {}).get("dates", [])


def _fetch_soma_agency_holdings(date):
    data = _request(f"api/soma/agency/get/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_agency_holdingtype(holding_type, date):
    ht = holding_type.replace(" ", "%20")
    data = _request(f"api/soma/agency/get/{ht}/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_agency_cusip(cusip):
    data = _request(f"api/soma/agency/get/cusip/{cusip}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_agency_wam(date):
    data = _request(f"api/soma/agency/wam/agency%20debts/asof/{date}.json")
    if not data:
        return []
    return data.get("soma", {}).get("holdings", [])


def _fetch_soma_agency_release_log():
    data = _request("api/soma/agency/get/release_log.json")
    if not data:
        return []
    return data.get("soma", {}).get("dates", [])


# --- Data Fetchers: Repo/Reverse Repo ----------------------------------------

def _fetch_repo_results(n=5):
    data = _request(f"api/rp/repo/all/results/last/{n}.json")
    if not data:
        return []
    return data.get("repo", {}).get("operations", [])


def _fetch_rrp_results(n=5):
    data = _request(f"api/rp/reverserepo/all/results/last/{n}.json")
    if not data:
        return []
    return data.get("repo", {}).get("operations", [])


def _fetch_repo_search(start_date, end_date, op_type="all", method="all"):
    data = _request(
        "api/rp/results/search.json",
        params={
            "startDate": start_date, "endDate": end_date,
            "operationTypes": op_type if op_type != "all" else None,
            "method": method if method != "all" else None,
        },
    )
    if not data:
        return []
    return data.get("repo", {}).get("operations", [])


# --- Data Fetchers: Primary Dealer -------------------------------------------

def _fetch_pd_series_list():
    data = _request("api/pd/list/timeseries.json")
    if not data:
        return []
    return data.get("pd", {}).get("timeseries", [])


def _fetch_pd_series(keyid):
    data = _request(f"api/pd/get/{keyid}.json")
    if not data:
        return []
    return data.get("pd", {}).get("timeseries", [])


def _fetch_pd_latest():
    data = _request("api/pd/latest.json")
    if not data:
        return []
    return data.get("pd", {}).get("timeseries", [])


def _fetch_pd_asof(date):
    data = _request(f"api/pd/get/asof/{date}.json")
    if not data:
        return []
    return data.get("pd", {}).get("timeseries", [])


# --- Data Fetchers: Treasury Securities Operations ----------------------------

def _fetch_tsy_ops(operation="all", include="summary", n=10):
    data = _request(f"api/tsy/{operation}/results/{include}/last/{n}.json")
    if not data:
        return []
    return data.get("treasury", {}).get("auctions", [])


def _fetch_tsy_ops_search(operation="all", include="summary",
                           start_date=None, end_date=None):
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _request(
        f"api/tsy/{operation}/results/{include}/search.json",
        params=params,
    )
    if not data:
        return []
    return data.get("treasury", {}).get("auctions", [])


# --- Data Fetchers: Agency MBS Operations -------------------------------------

def _fetch_ambs_ops(operation="all", include="summary", n=10):
    data = _request(f"api/ambs/{operation}/results/{include}/last/{n}.json")
    if not data:
        return []
    return data.get("ambs", {}).get("auctions", [])


def _fetch_ambs_ops_search(operation="all", include="summary",
                            start_date=None, end_date=None):
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _request(
        f"api/ambs/{operation}/results/{include}/search.json",
        params=params,
    )
    if not data:
        return []
    return data.get("ambs", {}).get("auctions", [])


# --- Data Fetchers: Securities Lending ----------------------------------------

def _fetch_seclending_ops(operation="all", include="summary", n=10):
    data = _request(
        f"api/seclending/{operation}/results/{include}/last/{n}.json"
    )
    if not data:
        return []
    return data.get("seclending", {}).get("operations", [])


def _fetch_seclending_search(operation="all", include="summary",
                              start_date=None, end_date=None):
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _request(
        f"api/seclending/{operation}/results/{include}/search.json",
        params=params,
    )
    if not data:
        return []
    return data.get("seclending", {}).get("operations", [])


# --- Data Fetchers: Central Bank Liquidity Swaps (FX Swaps) -------------------

def _fetch_fxswaps(n=10, operation_type="all"):
    data = _request(f"api/fxs/{operation_type}/last/{n}.json")
    if not data:
        return []
    return data.get("fxSwaps", {}).get("operations", [])


def _fetch_fxswaps_search(operation_type="all", start_date=None, end_date=None):
    params = {}
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    data = _request(
        f"api/fxs/{operation_type}/search.json",
        params=params,
    )
    if not data:
        return []
    return data.get("fxSwaps", {}).get("operations", [])


# ==============================================================================
# COMMAND FUNCTIONS
# ==============================================================================

# --- Commands: Reference Rates ------------------------------------------------

def cmd_rates(as_json=False, export_fmt=None):
    print("\n  Fetching all reference rates (latest)...")
    rates = _fetch_all_rates_latest()

    if not rates:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(rates, indent=2, default=str))
        return rates

    sofrai = None
    rate_rows = []
    for r in rates:
        rtype = r.get("type", "")
        if rtype == "SOFRAI":
            sofrai = r
            continue
        rate_rows.append(r)

    print(f"\n  NY Fed Reference Rates (latest)")
    print("  " + "=" * 85)
    print(f"  {'Rate':<8} {'Date':<12} {'Rate%':>8} {'P1':>8} {'P25':>8} {'P75':>8} "
          f"{'P99':>8} {'Vol($B)':>10}")
    print(f"  {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

    for r in rate_rows:
        rtype = r.get("type", "")
        date = _parse_date(r.get("effectiveDate", ""))
        rate = _safe_float(r.get("percentRate"))
        p1 = r.get("percentPercentile1", "")
        p25 = r.get("percentPercentile25", "")
        p75 = r.get("percentPercentile75", "")
        p99 = r.get("percentPercentile99", "")
        vol = _safe_float(r.get("volumeInBillions"))

        p1_s = f"{_safe_float(p1):.2f}" if p1 not in (None, "") else "--"
        p25_s = f"{_safe_float(p25):.2f}" if p25 not in (None, "") else "--"
        p75_s = f"{_safe_float(p75):.2f}" if p75 not in (None, "") else "--"
        p99_s = f"{_safe_float(p99):.2f}" if p99 not in (None, "") else "--"
        vol_s = f"{vol:,.0f}" if vol > 0 else "--"

        target_from = r.get("targetRateFrom")
        target_to = r.get("targetRateTo")
        extra = ""
        if target_from is not None and target_to is not None:
            extra = f"  [target: {_safe_float(target_from):.2f}-{_safe_float(target_to):.2f}]"

        print(f"  {rtype:<8} {date:<12} {rate:>8.2f} {p1_s:>8} {p25_s:>8} {p75_s:>8} "
              f"{p99_s:>8} {vol_s:>10}{extra}")

    if sofrai:
        print(f"\n  SOFR Averages & Index")
        print(f"  {'-'*50}")
        a30 = _safe_float(sofrai.get("average30day"))
        a90 = _safe_float(sofrai.get("average90day"))
        a180 = _safe_float(sofrai.get("average180day"))
        idx = _safe_float(sofrai.get("index"))
        print(f"  30-Day Avg:   {a30:.4f}%")
        print(f"  90-Day Avg:   {a90:.4f}%")
        print(f"  180-Day Avg:  {a180:.4f}%")
        print(f"  SOFR Index:   {idx:.6f}")

    print()

    if export_fmt:
        _do_export(rates, "nyfed_rates", export_fmt)
    return rates


def cmd_sofr(obs=30, as_json=False, export_fmt=None):
    print(f"\n  Fetching SOFR (last {obs} observations)...")
    rows = _fetch_rate_last("sofr", obs)

    if not rows:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    _display_rate_history(rows, "SOFR")

    if export_fmt:
        _do_export(rows, "nyfed_sofr", export_fmt)
    return rows


def cmd_effr(obs=30, as_json=False, export_fmt=None):
    print(f"\n  Fetching EFFR (last {obs} observations)...")
    rows = _fetch_rate_last("effr", obs)

    if not rows:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    _display_rate_history(rows, "EFFR")

    if export_fmt:
        _do_export(rows, "nyfed_effr", export_fmt)
    return rows


def cmd_rate_history(rate_key, start_date=None, end_date=None,
                     as_json=False, export_fmt=None):
    if not start_date:
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    info = RATE_TYPES.get(rate_key)
    if not info:
        print(f"  Unknown rate type: {rate_key}. Options: {', '.join(RATE_TYPES.keys())}")
        return

    print(f"\n  Fetching {info['label']} history ({start_date} to {end_date})...")
    rows = _fetch_rate_search(rate_key, start_date, end_date)

    if not rows:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    _display_rate_history(rows, info["label"])

    if export_fmt:
        _do_export(rows, f"nyfed_{rate_key}_history", export_fmt)
    return rows


# --- Commands: SOMA Summary ---------------------------------------------------

def cmd_soma(as_json=False, export_fmt=None):
    print("\n  Fetching SOMA holdings summary...")
    summaries = _fetch_soma_summary()

    if not summaries:
        print("  No data returned.")
        return

    recent = sorted(summaries, key=lambda x: x.get("asOfDate", ""), reverse=True)[:4]

    if as_json:
        print(json.dumps(recent, indent=2, default=str))
        return recent

    latest = recent[0]
    print(f"\n  SOMA Holdings (as of {_parse_date(latest.get('asOfDate', ''))})")
    print("  " + "=" * 60)

    fields = [
        ("Total",                "total"),
        ("Notes & Bonds",       "notesbonds"),
        ("Bills",               "bills"),
        ("TIPS",                "tips"),
        ("FRN",                 "frn"),
        ("MBS",                 "mbs"),
        ("CMBS",                "cmbs"),
        ("Agencies",            "agencies"),
        ("TIPS Infl Comp",      "tipsInflationCompensation"),
    ]

    print(f"  {'Category':<22} {'Current ($B)':>14}")
    print(f"  {'-'*22} {'-'*14}")

    for label, key in fields:
        val = _str_to_billions(latest.get(key, "0"))
        print(f"  {label:<22} {_fmt_billions(val):>14}")

    if len(recent) >= 2:
        print(f"\n  Weekly Changes (last {len(recent) - 1} weeks)")
        print(f"  {'Date':<12} {'Total ($B)':>14} {'Chg ($B)':>12} {'Notes+Bonds':>14} {'MBS':>14}")
        print(f"  {'-'*12} {'-'*14} {'-'*12} {'-'*14} {'-'*14}")

        for i in range(len(recent) - 1):
            curr = recent[i]
            prev = recent[i + 1]
            date = _parse_date(curr.get("asOfDate", ""))
            tot = _str_to_billions(curr.get("total", "0"))
            tot_prev = _str_to_billions(prev.get("total", "0"))
            chg = tot - tot_prev
            nb = _str_to_billions(curr.get("notesbonds", "0"))
            mbs = _str_to_billions(curr.get("mbs", "0"))
            print(f"  {date:<12} {_fmt_billions(tot):>14} {_fmt_billions(chg):>12} "
                  f"{_fmt_billions(nb):>14} {_fmt_billions(mbs):>14}")

    print()

    if export_fmt:
        out = []
        for s in recent:
            out.append({
                "date": _parse_date(s.get("asOfDate", "")),
                "total_bn": round(_str_to_billions(s.get("total", "0")), 2),
                "notesbonds_bn": round(_str_to_billions(s.get("notesbonds", "0")), 2),
                "bills_bn": round(_str_to_billions(s.get("bills", "0")), 2),
                "tips_bn": round(_str_to_billions(s.get("tips", "0")), 2),
                "mbs_bn": round(_str_to_billions(s.get("mbs", "0")), 2),
                "agencies_bn": round(_str_to_billions(s.get("agencies", "0")), 2),
            })
        _do_export(out, "nyfed_soma", export_fmt)
    return recent


def cmd_soma_history(weeks=26, as_json=False, export_fmt=None):
    print(f"\n  Fetching SOMA holdings history (last {weeks} weeks)...")
    summaries = _fetch_soma_summary()

    if not summaries:
        print("  No data returned.")
        return

    recent = sorted(summaries, key=lambda x: x.get("asOfDate", ""), reverse=True)[:weeks]

    if as_json:
        print(json.dumps(recent, indent=2, default=str))
        return recent

    print(f"\n  SOMA Holdings History ({len(recent)} weeks)")
    print("  " + "=" * 85)
    print(f"  {'Date':<12} {'Total ($B)':>14} {'Notes+Bonds':>14} {'Bills':>10} "
          f"{'MBS':>12} {'TIPS':>10} {'Agencies':>10}")
    print(f"  {'-'*12} {'-'*14} {'-'*14} {'-'*10} {'-'*12} {'-'*10} {'-'*10}")

    for s in recent:
        date = _parse_date(s.get("asOfDate", ""))
        total = _str_to_billions(s.get("total", "0"))
        nb = _str_to_billions(s.get("notesbonds", "0"))
        bills = _str_to_billions(s.get("bills", "0"))
        mbs = _str_to_billions(s.get("mbs", "0"))
        tips = _str_to_billions(s.get("tips", "0"))
        agencies = _str_to_billions(s.get("agencies", "0"))
        print(f"  {date:<12} {_fmt_billions(total):>14} {_fmt_billions(nb):>14} "
              f"{_fmt_billions(bills):>10} {_fmt_billions(mbs):>12} "
              f"{_fmt_billions(tips):>10} {_fmt_billions(agencies):>10}")

    if len(recent) >= 2:
        first = _str_to_billions(recent[0].get("total", "0"))
        last = _str_to_billions(recent[-1].get("total", "0"))
        chg = first - last
        print(f"\n  Period change: {_fmt_billions(chg)} over {len(recent)} weeks")

    print()

    if export_fmt:
        out = []
        for s in recent:
            out.append({
                "date": _parse_date(s.get("asOfDate", "")),
                "total_bn": round(_str_to_billions(s.get("total", "0")), 2),
                "notesbonds_bn": round(_str_to_billions(s.get("notesbonds", "0")), 2),
                "bills_bn": round(_str_to_billions(s.get("bills", "0")), 2),
                "mbs_bn": round(_str_to_billions(s.get("mbs", "0")), 2),
                "tips_bn": round(_str_to_billions(s.get("tips", "0")), 2),
            })
        _do_export(out, "nyfed_soma_history", export_fmt)
    return recent


# --- Commands: SOMA Detailed Holdings -----------------------------------------

def cmd_soma_holdings(date=None, holding_type="all", as_json=False, export_fmt=None):
    if not date:
        date = _fetch_soma_latest_date()
        if not date:
            print("  Could not determine latest SOMA date.")
            return

    if holding_type == "all":
        print(f"\n  Fetching SOMA Treasury holdings as of {date}...")
        holdings = _fetch_soma_tsy_holdings(date)
    else:
        print(f"\n  Fetching SOMA Treasury {holding_type} as of {date}...")
        holdings = _fetch_soma_tsy_holdingtype(holding_type, date)

    if not holdings:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(holdings, indent=2, default=str))
        return holdings

    by_type = {}
    for h in holdings:
        st = h.get("securityType", "Other")
        by_type.setdefault(st, []).append(h)

    print(f"\n  SOMA Treasury Holdings ({len(holdings)} securities, as of {date})")
    print("  " + "=" * 90)

    total_par = sum(_safe_float(h.get("parValue")) for h in holdings)
    print(f"  Total Par Value: {_fmt_billions(total_par / 1e9)}")
    print()

    for stype in ["Bills", "NotesBonds", "FRN", "TIPS"]:
        group = by_type.get(stype, [])
        if not group:
            continue
        group_par = sum(_safe_float(h.get("parValue")) for h in group)
        print(f"  {stype} ({len(group)} securities, {_fmt_billions(group_par / 1e9)})")
        print(f"  {'CUSIP':<12} {'Maturity':<12} {'Coupon':>8} {'Par ($B)':>12} "
              f"{'% Outstdg':>10} {'Wk Chg':>12}")
        print(f"  {'-'*12} {'-'*12} {'-'*8} {'-'*12} {'-'*10} {'-'*12}")

        sorted_group = sorted(group, key=lambda x: x.get("maturityDate", ""))
        for h in sorted_group[:25]:
            cusip = h.get("cusip", "")
            mat = _parse_date(h.get("maturityDate", ""))
            coupon = h.get("coupon", "")
            coupon_s = f"{_safe_float(coupon):.3f}" if coupon else "--"
            par = _safe_float(h.get("parValue")) / 1e9
            pct = _safe_float(h.get("percentOutstanding")) * 100
            wk_chg = _safe_float(h.get("changeFromPriorWeek"))
            wk_s = _fmt_billions(wk_chg / 1e9) if wk_chg != 0 else "--"
            print(f"  {cusip:<12} {mat:<12} {coupon_s:>8} {_fmt_billions(par):>12} "
                  f"{pct:>9.1f}% {wk_s:>12}")

        if len(sorted_group) > 25:
            print(f"  ... and {len(sorted_group) - 25} more {stype}")
        print()

    if export_fmt:
        out = []
        for h in holdings:
            out.append({
                "date": _parse_date(h.get("asOfDate", "")),
                "cusip": h.get("cusip", ""),
                "security_type": h.get("securityType", ""),
                "maturity": _parse_date(h.get("maturityDate", "")),
                "coupon": h.get("coupon", ""),
                "par_value": _safe_float(h.get("parValue")),
                "pct_outstanding": _safe_float(h.get("percentOutstanding")),
                "chg_prior_week": _safe_float(h.get("changeFromPriorWeek")),
            })
        _do_export(out, "nyfed_soma_tsy_holdings", export_fmt)
    return holdings


def cmd_soma_agency(date=None, holding_type="all", as_json=False, export_fmt=None):
    if not date:
        date = _fetch_soma_latest_date()
        if not date:
            print("  Could not determine latest SOMA date.")
            return

    if holding_type == "all":
        print(f"\n  Fetching SOMA Agency holdings as of {date}...")
        holdings = _fetch_soma_agency_holdings(date)
    else:
        print(f"\n  Fetching SOMA Agency {holding_type} as of {date}...")
        holdings = _fetch_soma_agency_holdingtype(holding_type, date)

    if not holdings:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(holdings, indent=2, default=str))
        return holdings

    by_type = {}
    for h in holdings:
        st = h.get("securityType", "Other")
        by_type.setdefault(st, []).append(h)

    print(f"\n  SOMA Agency Holdings ({len(holdings)} securities, as of {date})")
    print("  " + "=" * 90)

    total_par = sum(_safe_float(h.get("parValue")) for h in holdings)
    print(f"  Total Par Value: {_fmt_billions(total_par / 1e9)}")
    print()

    for stype, group in sorted(by_type.items()):
        group_par = sum(_safe_float(h.get("parValue")) for h in group)
        print(f"  {stype} ({len(group)} securities, {_fmt_billions(group_par / 1e9)})")
        print(f"  {'CUSIP':<12} {'Issuer':<8} {'Maturity':<12} {'Coupon':>8} "
              f"{'Par ($B)':>12} {'Wk Chg':>12}")
        print(f"  {'-'*12} {'-'*8} {'-'*12} {'-'*8} {'-'*12} {'-'*12}")

        sorted_group = sorted(group, key=lambda x: _safe_float(x.get("parValue")),
                              reverse=True)
        for h in sorted_group[:20]:
            cusip = h.get("cusip", "")
            issuer = h.get("issuer", "")[:8]
            mat = _parse_date(h.get("maturityDate", ""))
            coupon = h.get("coupon", "")
            coupon_s = f"{_safe_float(coupon):.3f}" if coupon else "--"
            par = _safe_float(h.get("parValue")) / 1e9
            wk_chg = _safe_float(h.get("changeFromPriorWeek"))
            wk_s = _fmt_billions(wk_chg / 1e9) if wk_chg != 0 else "--"
            print(f"  {cusip:<12} {issuer:<8} {mat:<12} {coupon_s:>8} "
                  f"{_fmt_billions(par):>12} {wk_s:>12}")

        if len(sorted_group) > 20:
            print(f"  ... and {len(sorted_group) - 20} more {stype}")
        print()

    if export_fmt:
        out = []
        for h in holdings:
            out.append({
                "date": _parse_date(h.get("asOfDate", "")),
                "cusip": h.get("cusip", ""),
                "security_type": h.get("securityType", ""),
                "issuer": h.get("issuer", ""),
                "maturity": _parse_date(h.get("maturityDate", "")),
                "coupon": h.get("coupon", ""),
                "par_value": _safe_float(h.get("parValue")),
                "chg_prior_week": _safe_float(h.get("changeFromPriorWeek")),
            })
        _do_export(out, "nyfed_soma_agency_holdings", export_fmt)
    return holdings


def cmd_soma_cusip(cusip, asset_class="tsy", as_json=False, export_fmt=None):
    print(f"\n  Fetching SOMA history for CUSIP {cusip} ({asset_class})...")
    if asset_class == "tsy":
        holdings = _fetch_soma_tsy_cusip(cusip)
    else:
        holdings = _fetch_soma_agency_cusip(cusip)

    if not holdings:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(holdings, indent=2, default=str))
        return holdings

    recent = sorted(holdings, key=lambda x: x.get("asOfDate", ""), reverse=True)

    h0 = recent[0]
    print(f"\n  SOMA Holdings: CUSIP {cusip}")
    print("  " + "=" * 70)
    print(f"  Security Type: {h0.get('securityType', '')}")
    print(f"  Maturity:      {_parse_date(h0.get('maturityDate', ''))}")
    if h0.get("coupon"):
        print(f"  Coupon:        {h0.get('coupon')}%")
    if h0.get("issuer"):
        print(f"  Issuer:        {h0.get('issuer')}")
    print()

    print(f"  {'Date':<12} {'Par ($B)':>14} {'% Outstanding':>14} {'Wk Chg ($B)':>14}")
    print(f"  {'-'*12} {'-'*14} {'-'*14} {'-'*14}")

    for h in recent[:52]:
        date = _parse_date(h.get("asOfDate", ""))
        par = _safe_float(h.get("parValue")) / 1e9
        pct = _safe_float(h.get("percentOutstanding")) * 100
        wk_chg = _safe_float(h.get("changeFromPriorWeek")) / 1e9
        pct_s = f"{pct:.2f}%" if pct > 0 else "--"
        print(f"  {date:<12} {_fmt_billions(par):>14} {pct_s:>14} "
              f"{_fmt_billions(wk_chg):>14}")

    if len(recent) > 52:
        print(f"  ... {len(recent) - 52} more observations")
    print()

    if export_fmt:
        out = [{"date": _parse_date(h.get("asOfDate", "")),
                "par_bn": round(_safe_float(h.get("parValue")) / 1e9, 4),
                "pct_outstanding": _safe_float(h.get("percentOutstanding"))}
               for h in recent]
        _do_export(out, f"nyfed_soma_cusip_{cusip}", export_fmt)
    return holdings


def cmd_soma_wam(holding_type="all", date=None, asset_class="tsy",
                 as_json=False, export_fmt=None):
    if not date:
        date = _fetch_soma_latest_date()
        if not date:
            print("  Could not determine latest SOMA date.")
            return

    if asset_class == "tsy":
        print(f"\n  Fetching SOMA Treasury WAM ({holding_type}) as of {date}...")
        data = _fetch_soma_tsy_wam(holding_type, date)
    else:
        print(f"\n  Fetching SOMA Agency WAM as of {date}...")
        data = _fetch_soma_agency_wam(date)

    if not data:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    print(f"\n  SOMA Weighted Average Maturity ({asset_class.upper()}, as of {date})")
    print("  " + "=" * 50)

    for entry in data:
        sec_type = entry.get("securityType", entry.get("holdingType", ""))
        wam = entry.get("wam", entry.get("weightedAverageMaturity", ""))
        print(f"  {sec_type:<25} WAM: {wam}")

    print()

    if export_fmt:
        _do_export(data, f"nyfed_soma_wam_{asset_class}", export_fmt)
    return data


def cmd_soma_monthly(last_n=24, as_json=False, export_fmt=None):
    print(f"\n  Fetching SOMA monthly Treasury data (last {last_n} months)...")
    all_holdings = _fetch_soma_tsy_monthly()

    if not all_holdings:
        print("  No data returned.")
        return

    dates = sorted(set(h.get("asOfDate", "") for h in all_holdings), reverse=True)
    target_dates = dates[:last_n]

    monthly_summaries = []
    for d in target_dates:
        month_holdings = [h for h in all_holdings if h.get("asOfDate") == d]
        total = sum(_safe_float(h.get("parValue")) for h in month_holdings)
        bills = sum(_safe_float(h.get("parValue")) for h in month_holdings
                    if h.get("securityType") == "Bills")
        nb = sum(_safe_float(h.get("parValue")) for h in month_holdings
                 if h.get("securityType") == "NotesBonds")
        tips = sum(_safe_float(h.get("parValue")) for h in month_holdings
                   if h.get("securityType") == "TIPS")
        frn = sum(_safe_float(h.get("parValue")) for h in month_holdings
                  if h.get("securityType") == "FRN")
        monthly_summaries.append({
            "date": d, "total_bn": total / 1e9, "bills_bn": bills / 1e9,
            "notesbonds_bn": nb / 1e9, "tips_bn": tips / 1e9, "frn_bn": frn / 1e9,
            "count": len(month_holdings),
        })

    if as_json:
        print(json.dumps(monthly_summaries, indent=2, default=str))
        return monthly_summaries

    print(f"\n  SOMA Monthly Treasury Holdings ({len(monthly_summaries)} months)")
    print("  " + "=" * 85)
    print(f"  {'Date':<12} {'Total ($B)':>14} {'N&B ($B)':>14} {'Bills ($B)':>12} "
          f"{'TIPS ($B)':>12} {'FRN ($B)':>12} {'#Sec':>6}")
    print(f"  {'-'*12} {'-'*14} {'-'*14} {'-'*12} {'-'*12} {'-'*12} {'-'*6}")

    for m in monthly_summaries:
        print(f"  {m['date']:<12} {_fmt_billions(m['total_bn']):>14} "
              f"{_fmt_billions(m['notesbonds_bn']):>14} "
              f"{_fmt_billions(m['bills_bn']):>12} "
              f"{_fmt_billions(m['tips_bn']):>12} "
              f"{_fmt_billions(m['frn_bn']):>12} {m['count']:>6}")

    print()

    if export_fmt:
        _do_export(monthly_summaries, "nyfed_soma_monthly", export_fmt)
    return monthly_summaries


# --- Commands: Repo & RRP ----------------------------------------------------

def cmd_repo(n=5, as_json=False, export_fmt=None):
    print(f"\n  Fetching latest repo operations (last {n})...")
    ops = _fetch_repo_results(n)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  Repo Operations (last {len(ops)})")
    print("  " + "=" * 90)
    print(f"  {'Date':<12} {'Type':<12} {'Method':<18} {'Term':<12} "
          f"{'Submitted':>14} {'Accepted':>14}")
    print(f"  {'-'*12} {'-'*12} {'-'*18} {'-'*12} {'-'*14} {'-'*14}")

    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        otype = op.get("operationType", "")
        method = op.get("operationMethod", "")[:18]
        term = op.get("term", "")[:12]
        submitted = _safe_float(op.get("totalAmtSubmitted"))
        accepted = _safe_float(op.get("totalAmtAccepted"))

        sub_s = _fmt_billions(submitted / 1e9) if submitted > 0 else "$0"
        acc_s = _fmt_billions(accepted / 1e9) if accepted > 0 else "$0"

        print(f"  {date:<12} {otype:<12} {method:<18} {term:<12} {sub_s:>14} {acc_s:>14}")

        details = op.get("details", [])
        for d in details:
            sec = d.get("securityType", "")
            d_sub = _safe_float(d.get("amtSubmitted"))
            d_acc = _safe_float(d.get("amtAccepted"))
            min_rate = d.get("minimumBidRate")
            rate_s = f"  min rate: {_safe_float(min_rate):.2f}%" if min_rate is not None else ""
            if d_sub > 0 or d_acc > 0 or rate_s:
                print(f"  {'':12} {sec:<12} {'':18} {'':12} "
                      f"{_fmt_billions(d_sub / 1e9) if d_sub > 0 else '--':>14} "
                      f"{_fmt_billions(d_acc / 1e9) if d_acc > 0 else '--':>14}{rate_s}")

    print()

    if export_fmt:
        _do_export(ops, "nyfed_repo", export_fmt)
    return ops


def cmd_rrp(n=5, as_json=False, export_fmt=None):
    print(f"\n  Fetching latest ON RRP operations (last {n})...")
    ops = _fetch_rrp_results(n)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  ON RRP (Reverse Repo) Operations (last {len(ops)})")
    print("  " + "=" * 95)
    print(f"  {'Date':<12} {'Term':<12} {'Accepted ($B)':>14} {'Counterparties':>16} "
          f"{'Offer Rate':>12} {'Award Rate':>12}")
    print(f"  {'-'*12} {'-'*12} {'-'*14} {'-'*16} {'-'*12} {'-'*12}")

    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        term = op.get("term", "")[:12]
        accepted = _safe_float(op.get("totalAmtAccepted"))
        cpty = op.get("participatingCpty", op.get("acceptedCpty", ""))
        offer_rate = op.get("percentOfferingRate")
        award_rate = op.get("percentAwardRate")

        acc_s = _fmt_billions(accepted / 1e9)
        offer_s = f"{_safe_float(offer_rate):.2f}%" if offer_rate is not None else "--"
        award_s = f"{_safe_float(award_rate):.2f}%" if award_rate is not None else "--"

        print(f"  {date:<12} {term:<12} {acc_s:>14} {str(cpty):>16} "
              f"{offer_s:>12} {award_s:>12}")

    if len(ops) >= 2:
        latest = _safe_float(ops[0].get("totalAmtAccepted")) / 1e9
        prev = _safe_float(ops[1].get("totalAmtAccepted")) / 1e9
        chg = latest - prev
        print(f"\n  Day-over-day change: {_fmt_billions(chg)}")

    print()

    if export_fmt:
        out = []
        for op in ops:
            out.append({
                "date": _parse_date(op.get("operationDate", "")),
                "accepted_bn": round(_safe_float(op.get("totalAmtAccepted")) / 1e9, 2),
                "counterparties": op.get("participatingCpty", op.get("acceptedCpty", "")),
                "offer_rate": op.get("percentOfferingRate"),
                "award_rate": op.get("percentAwardRate"),
            })
        _do_export(out, "nyfed_rrp", export_fmt)
    return ops


# --- Commands: Treasury Securities Operations ---------------------------------

def cmd_tsy_ops(operation="all", n=10, include="summary",
                as_json=False, export_fmt=None):
    print(f"\n  Fetching Treasury operations ({operation}, last {n})...")
    ops = _fetch_tsy_ops(operation, include, n)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  Treasury Securities Operations ({len(ops)} results)")
    print("  " + "=" * 100)
    print(f"  {'Date':<12} {'Type':<30} {'Direction':>10} {'Method':<16} "
          f"{'Submitted':>14} {'Accepted':>14}")
    print(f"  {'-'*12} {'-'*30} {'-'*10} {'-'*16} {'-'*14} {'-'*14}")

    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        otype = op.get("operationType", "")[:30]
        direction = "Purchase" if op.get("operationDirection") == "P" else "Sale"
        method = op.get("auctionMethod", "")[:16]
        submitted = _safe_float(op.get("totalParAmtSubmitted"))
        accepted = _safe_float(op.get("totalParAmtAccepted"))
        settle = _parse_date(op.get("settlementDate", ""))

        sub_s = _fmt_billions(submitted / 1e9) if submitted > 0 else "--"
        acc_s = _fmt_billions(accepted / 1e9) if accepted > 0 else "--"

        print(f"  {date:<12} {otype:<30} {direction:>10} {method:<16} "
              f"{sub_s:>14} {acc_s:>14}")

        mat_start = _parse_date(op.get("maturityRangeStart", ""))
        mat_end = _parse_date(op.get("maturityRangeEnd", ""))
        if mat_start and mat_end:
            print(f"  {'':12} Maturity range: {mat_start} to {mat_end}  |  "
                  f"Settlement: {settle}")

    print()

    if export_fmt:
        out = []
        for op in ops:
            out.append({
                "operation_id": op.get("operationId", ""),
                "date": _parse_date(op.get("operationDate", "")),
                "type": op.get("operationType", ""),
                "direction": op.get("operationDirection", ""),
                "method": op.get("auctionMethod", ""),
                "submitted_bn": round(_safe_float(op.get("totalParAmtSubmitted")) / 1e9, 3),
                "accepted_bn": round(_safe_float(op.get("totalParAmtAccepted")) / 1e9, 3),
                "settlement": _parse_date(op.get("settlementDate", "")),
                "maturity_start": _parse_date(op.get("maturityRangeStart", "")),
                "maturity_end": _parse_date(op.get("maturityRangeEnd", "")),
            })
        _do_export(out, "nyfed_tsy_ops", export_fmt)
    return ops


def cmd_tsy_ops_search(operation="all", include="summary",
                        start_date=None, end_date=None,
                        as_json=False, export_fmt=None):
    if not start_date:
        start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    print(f"\n  Searching Treasury operations ({start_date} to {end_date})...")
    ops = _fetch_tsy_ops_search(operation, include, start_date, end_date)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    cmd_tsy_ops.__wrapped_display = True
    print(f"\n  Treasury Operations Search ({len(ops)} results, {start_date} to {end_date})")
    print("  " + "=" * 100)
    print(f"  {'Date':<12} {'Type':<30} {'Dir':>5} {'Submitted':>14} {'Accepted':>14}")
    print(f"  {'-'*12} {'-'*30} {'-'*5} {'-'*14} {'-'*14}")

    total_accepted = 0
    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        otype = op.get("operationType", "")[:30]
        direction = "P" if op.get("operationDirection") == "P" else "S"
        submitted = _safe_float(op.get("totalParAmtSubmitted"))
        accepted = _safe_float(op.get("totalParAmtAccepted"))
        total_accepted += accepted

        sub_s = _fmt_billions(submitted / 1e9) if submitted > 0 else "--"
        acc_s = _fmt_billions(accepted / 1e9) if accepted > 0 else "--"

        print(f"  {date:<12} {otype:<30} {direction:>5} {sub_s:>14} {acc_s:>14}")

    print(f"\n  Total accepted: {_fmt_billions(total_accepted / 1e9)} across {len(ops)} operations")
    print()

    if export_fmt:
        out = [{"date": _parse_date(o.get("operationDate", "")),
                "type": o.get("operationType", ""),
                "accepted_bn": round(_safe_float(o.get("totalParAmtAccepted")) / 1e9, 3)}
               for o in ops]
        _do_export(out, "nyfed_tsy_ops_search", export_fmt)
    return ops


# --- Commands: Agency MBS Operations ------------------------------------------

def cmd_ambs_ops(operation="all", n=10, include="summary",
                 as_json=False, export_fmt=None):
    print(f"\n  Fetching Agency MBS operations ({operation}, last {n})...")
    ops = _fetch_ambs_ops(operation, include, n)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  Agency MBS Operations ({len(ops)} results)")
    print("  " + "=" * 100)
    print(f"  {'Date':<12} {'Type':<30} {'Dir':>5} {'Method':<16} "
          f"{'Submitted':>14} {'Accepted':>14}")
    print(f"  {'-'*12} {'-'*30} {'-'*5} {'-'*16} {'-'*14} {'-'*14}")

    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        otype = op.get("operationType", "")[:30]
        direction = op.get("operationDirection", "")
        method = op.get("method", "")[:16]
        settle = _parse_date(op.get("settlementDate", ""))

        sub_orig = _safe_float(op.get("totalSubmittedOrigFace"))
        acc_orig = _safe_float(op.get("totalAcceptedOrigFace"))
        sub_par = _safe_float(op.get("totalAmtSubmittedPar"))
        acc_par = _safe_float(op.get("totalAmtAcceptedPar"))

        submitted = sub_orig if sub_orig > 0 else sub_par
        accepted = acc_orig if acc_orig > 0 else acc_par

        sub_s = _fmt_billions(submitted / 1e9) if submitted > 0 else "--"
        acc_s = _fmt_billions(accepted / 1e9) if accepted > 0 else "--"

        print(f"  {date:<12} {otype:<30} {direction:>5} {method:<16} "
              f"{sub_s:>14} {acc_s:>14}")
        if settle:
            print(f"  {'':12} Settlement: {settle}")

    print()

    if export_fmt:
        out = []
        for op in ops:
            sub_orig = _safe_float(op.get("totalSubmittedOrigFace"))
            acc_orig = _safe_float(op.get("totalAcceptedOrigFace"))
            out.append({
                "operation_id": op.get("operationId", ""),
                "date": _parse_date(op.get("operationDate", "")),
                "type": op.get("operationType", ""),
                "direction": op.get("operationDirection", ""),
                "submitted_orig_face_bn": round(sub_orig / 1e9, 3) if sub_orig else None,
                "accepted_orig_face_bn": round(acc_orig / 1e9, 3) if acc_orig else None,
                "settlement": _parse_date(op.get("settlementDate", "")),
            })
        _do_export(out, "nyfed_ambs_ops", export_fmt)
    return ops


# --- Commands: Securities Lending ---------------------------------------------

def cmd_seclending_ops(operation="all", n=10, include="summary",
                       as_json=False, export_fmt=None):
    print(f"\n  Fetching Securities Lending operations ({operation}, last {n})...")
    ops = _fetch_seclending_ops(operation, include, n)

    if not ops:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  Securities Lending Operations ({len(ops)} results)")
    print("  " + "=" * 95)
    print(f"  {'Date':<12} {'Type':<22} {'Settlement':<12} {'Maturity':<12} "
          f"{'Submitted':>14} {'Accepted':>14}")
    print(f"  {'-'*12} {'-'*22} {'-'*12} {'-'*12} {'-'*14} {'-'*14}")

    for op in ops:
        date = _parse_date(op.get("operationDate", ""))
        otype = op.get("operationType", "")[:22]
        settle = _parse_date(op.get("settlementDate", ""))
        maturity = _parse_date(op.get("maturityDate", ""))

        submitted = _safe_float(op.get("totalParAmtSubmitted"))
        accepted = _safe_float(op.get("totalParAmtAccepted"))
        extended = _safe_float(op.get("totalParAmtExtended"))

        if submitted > 0:
            sub_s = _fmt_billions(submitted / 1e9)
            acc_s = _fmt_billions(accepted / 1e9) if accepted > 0 else "--"
        elif extended > 0:
            sub_s = "--"
            acc_s = f"{_fmt_billions(extended / 1e9)} ext"
        else:
            sub_s = "--"
            acc_s = "--"

        print(f"  {date:<12} {otype:<22} {settle:<12} {maturity:<12} "
              f"{sub_s:>14} {acc_s:>14}")

    total_sub = sum(_safe_float(o.get("totalParAmtSubmitted")) for o in ops) / 1e9
    total_acc = sum(_safe_float(o.get("totalParAmtAccepted")) for o in ops) / 1e9
    if total_sub > 0:
        fill_rate = total_acc / total_sub * 100
        print(f"\n  Totals: {_fmt_billions(total_sub)} submitted, "
              f"{_fmt_billions(total_acc)} accepted ({fill_rate:.1f}% fill)")

    print()

    if export_fmt:
        out = [{"date": _parse_date(o.get("operationDate", "")),
                "type": o.get("operationType", ""),
                "submitted_bn": round(_safe_float(o.get("totalParAmtSubmitted")) / 1e9, 3),
                "accepted_bn": round(_safe_float(o.get("totalParAmtAccepted")) / 1e9, 3)}
               for o in ops]
        _do_export(out, "nyfed_seclending", export_fmt)
    return ops


# --- Commands: FX Swaps (Central Bank Liquidity Swaps) ------------------------

def cmd_fxswaps(n=10, operation_type="all", as_json=False, export_fmt=None):
    print(f"\n  Fetching Central Bank Liquidity Swaps ({operation_type}, last {n})...")
    ops = _fetch_fxswaps(n, operation_type)

    if not ops:
        print("  No active FX swap operations found.")
        print("  (CB swap lines are typically dormant outside stress periods)")
        return []

    if as_json:
        print(json.dumps(ops, indent=2, default=str))
        return ops

    print(f"\n  Central Bank Liquidity Swaps ({len(ops)} results)")
    print("  " + "=" * 80)

    for op in ops:
        print(json.dumps(op, indent=2, default=str))

    print()

    if export_fmt:
        _do_export(ops, "nyfed_fxswaps", export_fmt)
    return ops


# --- Commands: Primary Dealers ------------------------------------------------

def cmd_pd_positions(n_recent=12, as_json=False, export_fmt=None):
    print("\n  Fetching primary dealer positions...")
    all_data = {}
    total = len(PD_KEY_SERIES)

    for idx, (keyid, label) in enumerate(PD_KEY_SERIES.items()):
        print(f"  [{idx + 1}/{total}] {label}...")
        rows = _fetch_pd_series(keyid)
        if rows:
            rows = sorted(rows, key=lambda x: x.get("asofdate", ""), reverse=True)
            all_data[keyid] = rows[:n_recent]
        if idx < total - 1:
            time.sleep(REQUEST_DELAY)

    if not all_data:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(all_data, indent=2, default=str))
        return all_data

    print(f"\n  Primary Dealer Net Positions (last {n_recent} observations)")
    print("  " + "=" * 85)

    for keyid, label in PD_KEY_SERIES.items():
        rows = all_data.get(keyid, [])
        if not rows:
            continue

        print(f"\n  {label} ({keyid})")
        print(f"  {'Date':<12} {'Value ($M)':>14} {'Chg':>14}")
        print(f"  {'-'*12} {'-'*14} {'-'*14}")

        for i, row in enumerate(rows):
            date = _parse_date(row.get("asofdate", ""))
            val = _safe_float(row.get("value"))
            chg = ""
            if i < len(rows) - 1:
                prev = _safe_float(rows[i + 1].get("value"))
                diff = val - prev
                chg = _fmt_num(diff, sign=True)
            print(f"  {date:<12} {_fmt_num(val, sign=False):>14} {chg:>14}")

    print()

    if export_fmt:
        out = []
        for keyid, rows in all_data.items():
            for row in rows:
                out.append({
                    "keyid": keyid,
                    "series": PD_KEY_SERIES.get(keyid, keyid),
                    "date": _parse_date(row.get("asofdate", "")),
                    "value_millions": _safe_float(row.get("value")),
                })
        _do_export(out, "nyfed_pd_positions", export_fmt)
    return all_data


def cmd_pd_snapshot(as_json=False, export_fmt=None):
    print("\n  Fetching latest PD survey data (all series)...")
    rows = _fetch_pd_latest()

    if not rows:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    print(f"\n  Primary Dealer Survey -- Latest ({len(rows)} series)")
    print("  " + "=" * 80)
    print(f"  {'Key ID':<25} {'As Of':<12} {'Value':>14}")
    print(f"  {'-'*25} {'-'*12} {'-'*14}")

    for row in rows[:50]:
        keyid = row.get("keyid", "")[:25]
        date = _parse_date(row.get("asofdate", ""))
        val = _safe_float(row.get("value"))
        print(f"  {keyid:<25} {date:<12} {_fmt_num(val, sign=False):>14}")

    if len(rows) > 50:
        print(f"  ... and {len(rows) - 50} more series")
    print()

    if export_fmt:
        out = [{"keyid": r.get("keyid", ""),
                "date": _parse_date(r.get("asofdate", "")),
                "value": _safe_float(r.get("value"))}
               for r in rows]
        _do_export(out, "nyfed_pd_snapshot", export_fmt)
    return rows


def cmd_series(query=None, as_json=False, export_fmt=None):
    print("\n  Fetching primary dealer timeseries list...")
    rows = _fetch_pd_series_list()

    if not rows:
        print("  No data returned.")
        return

    if query:
        query_lower = query.lower()
        rows = [r for r in rows if query_lower in r.get("keyid", "").lower()
                or query_lower in r.get("description", "").lower()]

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    curated_ids = set(PD_KEY_SERIES.keys())

    match_note = ' matching "%s"' % query if query else ""
    print(f"\n  Primary Dealer Timeseries ({len(rows)} series{match_note})")
    print("  " + "=" * 75)
    print(f"  {'Key ID':<25} {'Description':<48} {'Curated'}")
    print(f"  {'-'*25} {'-'*48} {'-'*7}")

    for r in rows[:60]:
        keyid = r.get("keyid", "")[:25]
        desc = r.get("description", "")[:48]
        curated = " *" if keyid.strip() in curated_ids else ""
        print(f"  {keyid:<25} {desc:<48}{curated}")

    if len(rows) > 60:
        print(f"  ... and {len(rows) - 60} more (use search to filter)")

    print(f"\n  Curated key series for macro monitoring:")
    for keyid, label in PD_KEY_SERIES.items():
        print(f"    {keyid:<25} {label}")
    print()

    if export_fmt:
        _do_export(rows, "nyfed_pd_series", export_fmt)
    return rows


# --- Commands: Dashboards -----------------------------------------------------

def cmd_funding_snapshot(as_json=False, export_fmt=None):
    print("\n  Building funding snapshot...")

    print("  [1/3] Reference rates...")
    rates = _fetch_all_rates_latest()
    time.sleep(REQUEST_DELAY)

    print("  [2/3] ON RRP operations...")
    rrp_ops = _fetch_rrp_results(3)
    time.sleep(REQUEST_DELAY)

    print("  [3/3] Repo operations...")
    repo_ops = _fetch_repo_results(1)

    if not rates:
        print("  No rate data returned.")
        return

    rate_map = {}
    sofrai = None
    for r in rates:
        rtype = r.get("type", "")
        if rtype == "SOFRAI":
            sofrai = r
        else:
            rate_map[rtype] = r

    out = {
        "rates": rate_map,
        "sofr_averages": sofrai,
        "rrp": rrp_ops,
        "repo": repo_ops,
    }

    if as_json:
        print(json.dumps(out, indent=2, default=str))
        return out

    sofr = rate_map.get("SOFR", {})
    effr = rate_map.get("EFFR", {})
    obfr = rate_map.get("OBFR", {})
    tgcr = rate_map.get("TGCR", {})
    bgcr = rate_map.get("BGCR", {})

    sofr_rate = _safe_float(sofr.get("percentRate"))
    effr_rate = _safe_float(effr.get("percentRate"))
    spread_bps = (sofr_rate - effr_rate) * 100

    target_from = _safe_float(effr.get("targetRateFrom"))
    target_to = _safe_float(effr.get("targetRateTo"))

    date = _parse_date(sofr.get("effectiveDate", effr.get("effectiveDate", "")))

    print(f"\n  FUNDING SNAPSHOT (as of {date})")
    print("  " + "=" * 65)

    print(f"\n  TARGET RATE BAND")
    print(f"  {'-'*40}")
    print(f"  Fed Funds Target:   {target_from:.2f}% - {target_to:.2f}%")
    mid = (target_from + target_to) / 2
    print(f"  Midpoint:           {mid:.2f}%")

    print(f"\n  REFERENCE RATES")
    print(f"  {'-'*40}")
    print(f"  {'Rate':<8} {'Level':>8} {'Vol ($B)':>10}  {'Notes'}")
    print(f"  {'-'*8} {'-'*8} {'-'*10}  {'-'*25}")

    for label, data in [("SOFR", sofr), ("EFFR", effr), ("OBFR", obfr),
                         ("TGCR", tgcr), ("BGCR", bgcr)]:
        rate = _safe_float(data.get("percentRate"))
        vol = _safe_float(data.get("volumeInBillions"))
        vol_s = f"{vol:,.0f}" if vol > 0 else "--"
        diff = (rate - mid) * 100
        note = f"{diff:+.1f}bp vs mid" if target_to > 0 else ""
        print(f"  {label:<8} {rate:>7.2f}% {vol_s:>10}  {note}")

    print(f"\n  FUNDING STRESS INDICATOR")
    print(f"  {'-'*40}")
    print(f"  SOFR - EFFR spread:  {_fmt_bps(spread_bps)}")
    if abs(spread_bps) < 3:
        assessment = "Normal -- no funding stress signal"
    elif spread_bps > 10:
        assessment = "Elevated -- secured rates trading rich to unsecured"
    elif spread_bps < -10:
        assessment = "Inverted -- potential reserve scarcity signal"
    else:
        assessment = "Mild divergence -- monitor"
    print(f"  Assessment:          {assessment}")

    if sofrai:
        print(f"\n  SOFR AVERAGES")
        print(f"  {'-'*40}")
        print(f"  30-Day:   {_safe_float(sofrai.get('average30day')):.4f}%")
        print(f"  90-Day:   {_safe_float(sofrai.get('average90day')):.4f}%")
        print(f"  180-Day:  {_safe_float(sofrai.get('average180day')):.4f}%")

    if rrp_ops:
        latest_rrp = rrp_ops[0]
        rrp_accepted = _safe_float(latest_rrp.get("totalAmtAccepted")) / 1e9
        rrp_cpty = latest_rrp.get("participatingCpty",
                                   latest_rrp.get("acceptedCpty", "N/A"))
        rrp_date = _parse_date(latest_rrp.get("operationDate", ""))

        print(f"\n  ON RRP FACILITY (as of {rrp_date})")
        print(f"  {'-'*40}")
        print(f"  Total Accepted:     {_fmt_billions(rrp_accepted)}")
        print(f"  Counterparties:     {rrp_cpty}")
        offer = latest_rrp.get("percentOfferingRate")
        if offer is not None:
            print(f"  Offering Rate:      {_safe_float(offer):.2f}%")

        if rrp_accepted > 500:
            liq_note = "Substantial excess liquidity in system"
        elif rrp_accepted > 100:
            liq_note = "Moderate RRP usage -- adequate reserves"
        elif rrp_accepted > 20:
            liq_note = "Low RRP usage -- reserves declining"
        else:
            liq_note = "Minimal RRP -- watch for reserve scarcity"
        print(f"  Liquidity Signal:   {liq_note}")

    print()

    if export_fmt:
        rrp_accepted_val = _safe_float(rrp_ops[0].get("totalAmtAccepted")) / 1e9 if rrp_ops else None
        rrp_cpty_val = rrp_ops[0].get("participatingCpty", rrp_ops[0].get("acceptedCpty", "")) if rrp_ops else None
        flat = {
            "date": date,
            "sofr": sofr_rate, "effr": effr_rate,
            "obfr": _safe_float(obfr.get("percentRate")),
            "tgcr": _safe_float(tgcr.get("percentRate")),
            "bgcr": _safe_float(bgcr.get("percentRate")),
            "sofr_effr_spread_bps": round(spread_bps, 1),
            "target_from": target_from, "target_to": target_to,
            "rrp_accepted_bn": round(rrp_accepted_val, 2) if rrp_accepted_val else None,
            "rrp_counterparties": rrp_cpty_val,
        }
        _do_export([flat], "nyfed_funding_snapshot", export_fmt)
    return out


def cmd_qt_monitor(weeks=26, as_json=False, export_fmt=None):
    print(f"\n  Building QT monitor (last {weeks} weeks)...")
    summaries = _fetch_soma_summary()

    if not summaries:
        print("  No data returned.")
        return

    recent = sorted(summaries, key=lambda x: x.get("asOfDate", ""), reverse=True)[:weeks]

    if len(recent) < 2:
        print("  Not enough data for QT analysis.")
        return

    if as_json:
        print(json.dumps(recent, indent=2, default=str))
        return recent

    print(f"\n  QT MONITOR -- SOMA Runoff Tracker")
    print("  " + "=" * 90)

    print(f"\n  Weekly SOMA Changes")
    print(f"  {'Date':<12} {'Total ($B)':>14} {'Chg Total':>12} {'Chg Tsy':>12} "
          f"{'Chg MBS':>12} {'Chg Bills':>12}")
    print(f"  {'-'*12} {'-'*14} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

    changes_total = []
    changes_tsy = []
    changes_mbs = []

    for i in range(len(recent) - 1):
        curr = recent[i]
        prev = recent[i + 1]
        date = _parse_date(curr.get("asOfDate", ""))

        tot_c = _str_to_billions(curr.get("total", "0"))
        tot_p = _str_to_billions(prev.get("total", "0"))
        chg_tot = tot_c - tot_p

        nb_c = _str_to_billions(curr.get("notesbonds", "0"))
        nb_p = _str_to_billions(prev.get("notesbonds", "0"))
        bills_c = _str_to_billions(curr.get("bills", "0"))
        bills_p = _str_to_billions(prev.get("bills", "0"))
        tips_c = _str_to_billions(curr.get("tips", "0"))
        tips_p = _str_to_billions(prev.get("tips", "0"))
        chg_tsy = (nb_c - nb_p) + (bills_c - bills_p) + (tips_c - tips_p)

        mbs_c = _str_to_billions(curr.get("mbs", "0"))
        mbs_p = _str_to_billions(prev.get("mbs", "0"))
        chg_mbs = mbs_c - mbs_p

        chg_bills = bills_c - bills_p

        changes_total.append(chg_tot)
        changes_tsy.append(chg_tsy)
        changes_mbs.append(chg_mbs)

        print(f"  {date:<12} {_fmt_billions(tot_c):>14} {_fmt_billions(chg_tot):>12} "
              f"{_fmt_billions(chg_tsy):>12} {_fmt_billions(chg_mbs):>12} "
              f"{_fmt_billions(chg_bills):>12}")

    n_weeks = len(changes_total)
    if n_weeks > 0:
        avg_total = sum(changes_total) / n_weeks
        avg_tsy = sum(changes_tsy) / n_weeks
        avg_mbs = sum(changes_mbs) / n_weeks

        ann_total = avg_total * 52
        ann_tsy = avg_tsy * 52
        ann_mbs = avg_mbs * 52

        monthly_tsy = avg_tsy * (52 / 12)
        monthly_mbs = avg_mbs * (52 / 12)

        print(f"\n  RUNOFF PACE ANALYSIS ({n_weeks}-week average)")
        print(f"  {'-'*55}")
        print(f"  {'':22} {'Weekly':>12} {'Monthly':>12} {'Annualized':>14}")
        print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*14}")
        print(f"  {'Total':22} {_fmt_billions(avg_total):>12} "
              f"{_fmt_billions(avg_total * 52/12):>12} {_fmt_billions(ann_total):>14}")
        print(f"  {'Treasuries':22} {_fmt_billions(avg_tsy):>12} "
              f"{_fmt_billions(monthly_tsy):>12} {_fmt_billions(ann_tsy):>14}")
        print(f"  {'MBS':22} {_fmt_billions(avg_mbs):>12} "
              f"{_fmt_billions(monthly_mbs):>12} {_fmt_billions(ann_mbs):>14}")

        print(f"\n  REINVESTMENT CAP COMPARISON")
        print(f"  {'-'*55}")
        print(f"  Treasury cap: ${QT_CAPS['treasury']:.0f}B/month | "
              f"Actual runoff: {_fmt_billions(abs(monthly_tsy))}/month | "
              f"{'At cap' if abs(monthly_tsy) >= QT_CAPS['treasury'] * 0.9 else 'Below cap'}")
        print(f"  MBS cap:      ${QT_CAPS['mbs']:.0f}B/month | "
              f"Actual runoff: {_fmt_billions(abs(monthly_mbs))}/month | "
              f"{'At cap' if abs(monthly_mbs) >= QT_CAPS['mbs'] * 0.9 else 'Below cap'}")

        total_start = _str_to_billions(recent[-1].get("total", "0"))
        total_end = _str_to_billions(recent[0].get("total", "0"))
        cum_runoff = total_end - total_start

        print(f"\n  CUMULATIVE")
        print(f"  {'-'*55}")
        print(f"  Period start:  {_fmt_billions(total_start)} ({_parse_date(recent[-1].get('asOfDate', ''))})")
        print(f"  Current:       {_fmt_billions(total_end)} ({_parse_date(recent[0].get('asOfDate', ''))})")
        print(f"  Cumulative:    {_fmt_billions(cum_runoff)} over {n_weeks} weeks")

    print()

    if export_fmt:
        out = []
        for i in range(len(recent) - 1):
            curr = recent[i]
            out.append({
                "date": _parse_date(curr.get("asOfDate", "")),
                "total_bn": round(_str_to_billions(curr.get("total", "0")), 2),
                "chg_total_bn": round(changes_total[i], 2),
                "chg_tsy_bn": round(changes_tsy[i], 2),
                "chg_mbs_bn": round(changes_mbs[i], 2),
            })
        _do_export(out, "nyfed_qt_monitor", export_fmt)
    return recent


def cmd_operations_summary(as_json=False, export_fmt=None):
    print("\n  Building operations summary (all OMO types)...")
    t0 = time.time()

    print("  [1/5] Treasury operations...")
    tsy = _fetch_tsy_ops("all", "summary", 5)
    time.sleep(REQUEST_DELAY)

    print("  [2/5] Agency MBS operations...")
    ambs = _fetch_ambs_ops("all", "summary", 5)
    time.sleep(REQUEST_DELAY)

    print("  [3/5] Securities lending...")
    seclend = _fetch_seclending_ops("all", "summary", 5)
    time.sleep(REQUEST_DELAY)

    print("  [4/5] Repo operations...")
    repo = _fetch_repo_results(3)
    time.sleep(REQUEST_DELAY)

    print("  [5/5] Reverse repo...")
    rrp = _fetch_rrp_results(3)

    result = {
        "timestamp": datetime.now().isoformat(),
        "treasury_operations": tsy,
        "agency_mbs_operations": ambs,
        "securities_lending": seclend,
        "repo": repo,
        "reverse_repo": rrp,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    print(f"\n  OPEN MARKET OPERATIONS SUMMARY")
    print("  " + "=" * 95)

    if tsy:
        print(f"\n  TREASURY SECURITIES ({len(tsy)} recent)")
        for op in tsy[:3]:
            date = _parse_date(op.get("operationDate", ""))
            otype = op.get("operationType", "")
            accepted = _safe_float(op.get("totalParAmtAccepted"))
            print(f"    {date}  {otype:<35} Accepted: {_fmt_billions(accepted / 1e9)}")

    if ambs:
        print(f"\n  AGENCY MBS ({len(ambs)} recent)")
        for op in ambs[:3]:
            date = _parse_date(op.get("operationDate", ""))
            otype = op.get("operationType", "")
            acc_orig = _safe_float(op.get("totalAcceptedOrigFace"))
            acc_par = _safe_float(op.get("totalAmtAcceptedPar"))
            accepted = acc_orig if acc_orig > 0 else acc_par
            print(f"    {date}  {otype:<35} Accepted: {_fmt_billions(accepted / 1e9)}")

    if seclend:
        print(f"\n  SECURITIES LENDING ({len(seclend)} recent)")
        for op in seclend[:3]:
            date = _parse_date(op.get("operationDate", ""))
            otype = op.get("operationType", "")
            accepted = _safe_float(op.get("totalParAmtAccepted"))
            print(f"    {date}  {otype:<35} Accepted: {_fmt_billions(accepted / 1e9)}")

    if repo:
        print(f"\n  REPO ({len(repo)} recent)")
        for op in repo[:3]:
            date = _parse_date(op.get("operationDate", ""))
            accepted = _safe_float(op.get("totalAmtAccepted"))
            print(f"    {date}  Repo                                "
                  f"Accepted: {_fmt_billions(accepted / 1e9)}")

    if rrp:
        print(f"\n  REVERSE REPO ({len(rrp)} recent)")
        for op in rrp[:3]:
            date = _parse_date(op.get("operationDate", ""))
            accepted = _safe_float(op.get("totalAmtAccepted"))
            cpty = op.get("participatingCpty", op.get("acceptedCpty", ""))
            print(f"    {date}  ON RRP                              "
                  f"Accepted: {_fmt_billions(accepted / 1e9)}  ({cpty} cptys)")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _do_export(result, "nyfed_operations_summary", export_fmt)
    return result


# --- Display Helpers ----------------------------------------------------------

def _display_rate_history(rows, label):
    if not rows:
        print("  No data to display.")
        return

    print(f"\n  {label} History ({len(rows)} observations)")
    print("  " + "=" * 80)
    print(f"  {'Date':<12} {'Rate%':>8} {'P1':>8} {'P25':>8} {'P75':>8} "
          f"{'P99':>8} {'Vol($B)':>10}")
    print(f"  {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*10}")

    for r in rows:
        date = _parse_date(r.get("effectiveDate", ""))
        rate = _safe_float(r.get("percentRate"))
        p1 = r.get("percentPercentile1", "")
        p25 = r.get("percentPercentile25", "")
        p75 = r.get("percentPercentile75", "")
        p99 = r.get("percentPercentile99", "")
        vol = _safe_float(r.get("volumeInBillions"))

        p1_s = f"{_safe_float(p1):.2f}" if p1 not in (None, "") else "--"
        p25_s = f"{_safe_float(p25):.2f}" if p25 not in (None, "") else "--"
        p75_s = f"{_safe_float(p75):.2f}" if p75 not in (None, "") else "--"
        p99_s = f"{_safe_float(p99):.2f}" if p99 not in (None, "") else "--"
        vol_s = f"{vol:,.0f}" if vol > 0 else "--"

        print(f"  {date:<12} {rate:>8.2f} {p1_s:>8} {p25_s:>8} {p75_s:>8} "
              f"{p99_s:>8} {vol_s:>10}")

    rates_list = [_safe_float(r.get("percentRate")) for r in rows]
    if rates_list:
        latest = rates_list[0]
        lo = min(rates_list)
        hi = max(rates_list)
        avg = sum(rates_list) / len(rates_list)
        print(f"\n  Range: {lo:.2f}% - {hi:.2f}%  |  Mean: {avg:.2f}%  |  "
              f"Latest: {latest:.2f}%")
    print()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   NY Fed Markets Data -- Complete API Client
  =====================================================

   REFERENCE RATES
     1) rates           All reference rates (latest snapshot)
     2) sofr            SOFR history (last N observations)
     3) effr            EFFR history (last N observations)
     4) rate-history    Any rate type history (date range)

   SOMA SUMMARY
     5) soma            SOMA holdings latest + trend
     6) soma-history    SOMA holdings over time

   SOMA DETAILED
     7) soma-holdings   CUSIP-level Treasury holdings
     8) soma-agency     CUSIP-level Agency/MBS holdings
     9) soma-cusip      Track single CUSIP over time
    10) soma-wam        Weighted average maturity
    11) soma-monthly    Monthly Treasury summary

   TREASURY OPERATIONS
    12) tsy-ops         Treasury securities operations
    13) tsy-search      Search Treasury ops by date range

   AGENCY MBS OPERATIONS
    14) ambs-ops        Agency MBS operations

   SECURITIES LENDING
    15) seclending      Securities lending operations

   FX SWAPS
    16) fxswaps         Central bank liquidity swaps

   REPO OPERATIONS
    17) repo            Latest repo operation results
    18) rrp             Latest ON RRP (reverse repo) results

   PRIMARY DEALERS
    19) pd-positions    Primary dealer net positioning
    20) pd-snapshot     Latest PD survey (all series)
    21) series          List PD timeseries

   DASHBOARDS
    22) funding-snapshot  Combined rates + liquidity view
    23) qt-monitor        QT runoff tracker
    24) operations-summary  All open market operations

   q) quit
"""


def _i_rates():
    cmd_rates()

def _i_sofr():
    obs = _prompt("Number of observations", "30")
    cmd_sofr(obs=int(obs))

def _i_effr():
    obs = _prompt("Number of observations", "30")
    cmd_effr(obs=int(obs))

def _i_rate_history():
    print(f"  Available rate types: {', '.join(RATE_TYPES.keys())}")
    rate_key = _prompt("Rate type", "sofr")
    start = _prompt("Start date (YYYY-MM-DD)", (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))
    end = _prompt("End date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
    cmd_rate_history(rate_key=rate_key, start_date=start, end_date=end)

def _i_soma():
    cmd_soma()

def _i_soma_history():
    weeks = _prompt("Number of weeks", "26")
    cmd_soma_history(weeks=int(weeks))

def _i_soma_holdings():
    ht = _prompt("Holding type (all/bills/notesbonds/frn/tips)", "all")
    cmd_soma_holdings(holding_type=ht)

def _i_soma_agency():
    cmd_soma_agency()

def _i_soma_cusip():
    cusip = _prompt("CUSIP")
    if not cusip:
        print("  CUSIP required.")
        return
    ac = _prompt("Asset class (tsy/agency)", "tsy")
    cmd_soma_cusip(cusip=cusip, asset_class=ac)

def _i_soma_wam():
    ht = _prompt("Holding type (all/bills/notesbonds/frn/tips)", "all")
    ac = _prompt("Asset class (tsy/agency)", "tsy")
    cmd_soma_wam(holding_type=ht, asset_class=ac)

def _i_soma_monthly():
    n = _prompt("Last N months", "24")
    cmd_soma_monthly(last_n=int(n))

def _i_tsy_ops():
    op = _prompt("Operation type (all/purchases/sales)", "all")
    n = _prompt("Number of results", "10")
    cmd_tsy_ops(operation=op, n=int(n))

def _i_tsy_search():
    op = _prompt("Operation type (all/purchases/sales)", "all")
    start = _prompt("Start date (YYYY-MM-DD)", (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d"))
    end = _prompt("End date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
    cmd_tsy_ops_search(operation=op, start_date=start, end_date=end)

def _i_ambs_ops():
    op = _prompt("Operation type (all/purchases/sales/roll/swap)", "all")
    n = _prompt("Number of results", "10")
    cmd_ambs_ops(operation=op, n=int(n))

def _i_seclending():
    op = _prompt("Type (all/seclending/extensions)", "all")
    n = _prompt("Number of results", "10")
    cmd_seclending_ops(operation=op, n=int(n))

def _i_fxswaps():
    n = _prompt("Number of results", "10")
    cmd_fxswaps(n=int(n))

def _i_repo():
    n = _prompt("Number of recent operations", "5")
    cmd_repo(n=int(n))

def _i_rrp():
    n = _prompt("Number of recent operations", "5")
    cmd_rrp(n=int(n))

def _i_pd_positions():
    n = _prompt("Recent observations per series", "12")
    cmd_pd_positions(n_recent=int(n))

def _i_pd_snapshot():
    cmd_pd_snapshot()

def _i_series():
    query = _prompt("Search filter (or enter for all)", "")
    query = query if query else None
    cmd_series(query=query)

def _i_funding_snapshot():
    cmd_funding_snapshot()

def _i_qt_monitor():
    weeks = _prompt("Number of weeks", "26")
    cmd_qt_monitor(weeks=int(weeks))

def _i_operations_summary():
    cmd_operations_summary()


COMMAND_MAP = {
    "1":  _i_rates,
    "2":  _i_sofr,
    "3":  _i_effr,
    "4":  _i_rate_history,
    "5":  _i_soma,
    "6":  _i_soma_history,
    "7":  _i_soma_holdings,
    "8":  _i_soma_agency,
    "9":  _i_soma_cusip,
    "10": _i_soma_wam,
    "11": _i_soma_monthly,
    "12": _i_tsy_ops,
    "13": _i_tsy_search,
    "14": _i_ambs_ops,
    "15": _i_seclending,
    "16": _i_fxswaps,
    "17": _i_repo,
    "18": _i_rrp,
    "19": _i_pd_positions,
    "20": _i_pd_snapshot,
    "21": _i_series,
    "22": _i_funding_snapshot,
    "23": _i_qt_monitor,
    "24": _i_operations_summary,
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
            print("  Enter 1-24 or q to quit")


# --- Argparse -----------------------------------------------------------------

VALID_RATE_TYPES = list(RATE_TYPES.keys())


def build_argparse():
    p = argparse.ArgumentParser(
        prog="nyfed.py",
        description="NY Fed Markets Data -- Complete API Client",
    )
    sub = p.add_subparsers(dest="command")

    # Reference rates
    s = sub.add_parser("rates", help="All reference rates latest snapshot")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("sofr", help="SOFR history (last N observations)")
    s.add_argument("--obs", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("effr", help="EFFR history (last N observations)")
    s.add_argument("--obs", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("rate-history", help="Any rate type history with date range")
    s.add_argument("rate_type", choices=VALID_RATE_TYPES, help="Rate type")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # SOMA summary
    s = sub.add_parser("soma", help="SOMA holdings latest + recent trend")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("soma-history", help="SOMA holdings over time")
    s.add_argument("--weeks", type=int, default=26)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # SOMA detailed
    s = sub.add_parser("soma-holdings", help="CUSIP-level Treasury holdings")
    s.add_argument("--date", help="As-of date YYYY-MM-DD (default: latest)")
    s.add_argument("--type", choices=SOMA_TSY_TYPES, default="all",
                   help="Holding type filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("soma-agency", help="CUSIP-level Agency/MBS holdings")
    s.add_argument("--date", help="As-of date YYYY-MM-DD (default: latest)")
    s.add_argument("--type", choices=["all", "agency debts", "mbs", "cmbs"],
                   default="all", help="Holding type filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("soma-cusip", help="Track single CUSIP over time")
    s.add_argument("cusip", help="CUSIP identifier")
    s.add_argument("--asset-class", choices=["tsy", "agency"], default="tsy")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("soma-wam", help="Weighted average maturity")
    s.add_argument("--type", choices=SOMA_TSY_TYPES, default="all")
    s.add_argument("--date", help="As-of date YYYY-MM-DD (default: latest)")
    s.add_argument("--asset-class", choices=["tsy", "agency"], default="tsy")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("soma-monthly", help="Monthly Treasury SOMA data")
    s.add_argument("--last", type=int, default=24, help="Last N months")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Treasury operations
    s = sub.add_parser("tsy-ops", help="Treasury securities operations")
    s.add_argument("--operation", choices=TSY_OPERATIONS, default="all")
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--include", choices=TSY_INCLUDE, default="summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("tsy-search", help="Search Treasury ops by date range")
    s.add_argument("--operation", choices=TSY_OPERATIONS, default="all")
    s.add_argument("--include", choices=TSY_INCLUDE, default="summary")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Agency MBS
    s = sub.add_parser("ambs-ops", help="Agency MBS operations")
    s.add_argument("--operation", choices=AMBS_OPERATIONS, default="all")
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--include", choices=AMBS_INCLUDE, default="summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Securities lending
    s = sub.add_parser("seclending", help="Securities lending operations")
    s.add_argument("--operation", choices=SECLENDING_OPERATIONS, default="all")
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--include", choices=SECLENDING_INCLUDE, default="summary")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # FX swaps
    s = sub.add_parser("fxswaps", help="Central bank liquidity swaps")
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--type", choices=FXS_TYPES, default="all")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Repo
    s = sub.add_parser("repo", help="Latest repo operation results")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("rrp", help="Latest ON RRP (reverse repo) results")
    s.add_argument("--count", type=int, default=5)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Primary dealers
    s = sub.add_parser("pd-positions", help="Primary dealer net positioning")
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("pd-snapshot", help="Latest PD survey all series")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("series", help="List available primary dealer series")
    s.add_argument("--query", help="Filter by keyword")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Dashboards
    s = sub.add_parser("funding-snapshot", help="Combined rates + liquidity view")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("qt-monitor", help="QT runoff tracker")
    s.add_argument("--weeks", type=int, default=26)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("operations-summary", help="All open market operations")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "rates":
        cmd_rates(as_json=j, export_fmt=exp)
    elif args.command == "sofr":
        cmd_sofr(obs=args.obs, as_json=j, export_fmt=exp)
    elif args.command == "effr":
        cmd_effr(obs=args.obs, as_json=j, export_fmt=exp)
    elif args.command == "rate-history":
        cmd_rate_history(rate_key=args.rate_type, start_date=args.start,
                         end_date=args.end, as_json=j, export_fmt=exp)
    elif args.command == "soma":
        cmd_soma(as_json=j, export_fmt=exp)
    elif args.command == "soma-history":
        cmd_soma_history(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "soma-holdings":
        cmd_soma_holdings(date=args.date, holding_type=args.type,
                          as_json=j, export_fmt=exp)
    elif args.command == "soma-agency":
        cmd_soma_agency(date=args.date, holding_type=args.type,
                        as_json=j, export_fmt=exp)
    elif args.command == "soma-cusip":
        cmd_soma_cusip(cusip=args.cusip,
                       asset_class=getattr(args, "asset_class", "tsy"),
                       as_json=j, export_fmt=exp)
    elif args.command == "soma-wam":
        cmd_soma_wam(holding_type=args.type, date=args.date,
                     asset_class=getattr(args, "asset_class", "tsy"),
                     as_json=j, export_fmt=exp)
    elif args.command == "soma-monthly":
        cmd_soma_monthly(last_n=getattr(args, "last", 24),
                         as_json=j, export_fmt=exp)
    elif args.command == "tsy-ops":
        cmd_tsy_ops(operation=args.operation, n=args.count,
                    include=args.include, as_json=j, export_fmt=exp)
    elif args.command == "tsy-search":
        cmd_tsy_ops_search(operation=args.operation, include=args.include,
                            start_date=args.start, end_date=args.end,
                            as_json=j, export_fmt=exp)
    elif args.command == "ambs-ops":
        cmd_ambs_ops(operation=args.operation, n=args.count,
                     include=args.include, as_json=j, export_fmt=exp)
    elif args.command == "seclending":
        cmd_seclending_ops(operation=args.operation, n=args.count,
                           include=args.include, as_json=j, export_fmt=exp)
    elif args.command == "fxswaps":
        cmd_fxswaps(n=args.count, operation_type=args.type,
                    as_json=j, export_fmt=exp)
    elif args.command == "repo":
        cmd_repo(n=args.count, as_json=j, export_fmt=exp)
    elif args.command == "rrp":
        cmd_rrp(n=args.count, as_json=j, export_fmt=exp)
    elif args.command == "pd-positions":
        cmd_pd_positions(n_recent=args.count, as_json=j, export_fmt=exp)
    elif args.command == "pd-snapshot":
        cmd_pd_snapshot(as_json=j, export_fmt=exp)
    elif args.command == "funding-snapshot":
        cmd_funding_snapshot(as_json=j, export_fmt=exp)
    elif args.command == "qt-monitor":
        cmd_qt_monitor(weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "series":
        cmd_series(query=getattr(args, "query", None), as_json=j, export_fmt=exp)
    elif args.command == "operations-summary":
        cmd_operations_summary(as_json=j, export_fmt=exp)


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
