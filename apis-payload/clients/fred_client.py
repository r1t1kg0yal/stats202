#!/usr/bin/env python3
"""
FRED (Federal Reserve Economic Data) -- Macro Data Client

Single-script client for the FRED API (api.stlouisfed.org/fred).
Curated catalog of macro-relevant series organized by theme, plus full
access to FRED's search, category browsing, and release tracking.

Requires FRED_API_KEY env var (free at https://fred.stlouisfed.org/docs/api/api_key.html).

Usage:
    python fred.py                                      # interactive CLI
    python fred.py search "unemployment rate"            # search for series
    python fred.py get UNRATE                            # latest observations
    python fred.py get UNRATE --start 2020-01-01         # observations from date
    python fred.py get GDPC1,UNRATE,CPIAUCSL --combine   # multi-series wide CSV
    python fred.py compare GDPC1 PAYEMS CPIAUCSL         # side-by-side latest
    python fred.py catalog                               # show curated catalog
    python fred.py catalog --theme rates                 # filter by theme
    python fred.py releases                              # recent release calendar
    python fred.py release 53                            # GDP release detail
    python fred.py categories 0                          # browse category tree
    python fred.py macro-snapshot                        # curated dashboard pull
    python fred.py metadata GDPC1                        # series metadata
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from time import monotonic
from urllib.parse import urlencode
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError


# --- Configuration ------------------------------------------------------------

BASE_URL = "https://api.stlouisfed.org/fred"
API_KEY = os.environ.get("FRED_API_KEY", "").strip()
REQUEST_DELAY = 1.0
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Curated Series Catalog ---------------------------------------------------
# Organized by macro theme. Each entry: (series_id, name, freq, units)
# Extend this over time -- adding a series here is all that's needed to include
# it in catalog listings, macro-snapshot, and theme-filtered pulls.

CATALOG = {
    "output_growth": {
        "label": "Output & Growth",
        "series": [
            ("GDPC1",              "Real GDP",                              "Q",  "Bil. 2017$, SAAR"),
            ("A191RL1Q225SBEA",    "Real GDP Growth Rate",                  "Q",  "%, annualized"),
            ("GDPPOT",             "Real Potential GDP",                    "Q",  "Bil. 2017$"),
            ("GDPNOW",             "Atlanta Fed GDPNow",                   "D",  "%"),
            ("INDPRO",             "Industrial Production Index",           "M",  "Index 2017=100"),
            ("CPIAI",              "Capacity Utilization",                  "M",  "%"),
            ("RSAFS",              "Retail Sales (ex food svc)",            "M",  "Mil.$"),
        ],
    },
    "labor": {
        "label": "Labor Market",
        "series": [
            ("PAYEMS",             "Total Nonfarm Payrolls",                "M",  "Thousands"),
            ("UNRATE",             "Unemployment Rate",                     "M",  "%"),
            ("U6RATE",             "U-6 Unemployment Rate",                "M",  "%"),
            ("ICSA",               "Initial Jobless Claims",                "W",  "Number"),
            ("CCSA",               "Continued Claims",                      "W",  "Number"),
            ("CES0500000003",      "Avg Hourly Earnings (Private)",         "M",  "$/hr"),
            ("JTSJOL",             "JOLTS Job Openings",                    "M",  "Thousands"),
            ("JTSQUR",             "JOLTS Quits Rate",                      "M",  "%"),
            ("CIVPART",            "Labor Force Participation Rate",        "M",  "%"),
            ("EMRATIO",            "Employment-Population Ratio",           "M",  "%"),
            ("AWHNONAG",           "Avg Weekly Hours (Nonfarm)",            "M",  "Hours"),
        ],
    },
    "inflation": {
        "label": "Prices & Inflation",
        "series": [
            ("CPIAUCSL",           "CPI All Items",                         "M",  "Index 1982-84=100"),
            ("CPILFESL",           "Core CPI (ex Food & Energy)",           "M",  "Index 1982-84=100"),
            ("PCEPILFE",           "Core PCE Price Index",                  "M",  "Index 2017=100"),
            ("PCEPI",              "PCE Price Index",                       "M",  "Index 2017=100"),
            ("MEDCPIM158SFRBCLE",  "Median CPI (Cleveland Fed)",           "M",  "% chg"),
            ("PPIFIS",             "PPI Final Demand",                      "M",  "Index 2009=100"),
            ("T5YIE",              "5Y Breakeven Inflation",                "D",  "%"),
            ("T10YIE",             "10Y Breakeven Inflation",               "D",  "%"),
            ("T5YIFR",             "5Y5Y Forward Inflation Exp.",           "D",  "%"),
            ("MICH",               "UMich Inflation Expectations (1Y)",     "M",  "%"),
        ],
    },
    "rates": {
        "label": "Interest Rates & Yields",
        "series": [
            ("FEDFUNDS",           "Effective Federal Funds Rate",          "M",  "%"),
            ("DFEDTARU",           "Fed Funds Target Upper",                "D",  "%"),
            ("DFEDTARL",           "Fed Funds Target Lower",                "D",  "%"),
            ("DGS1MO",             "1-Month Treasury Yield",                "D",  "%"),
            ("DGS3MO",             "3-Month Treasury Yield",                "D",  "%"),
            ("DGS6MO",             "6-Month Treasury Yield",                "D",  "%"),
            ("DGS1",               "1-Year Treasury Yield",                 "D",  "%"),
            ("DGS2",               "2-Year Treasury Yield",                 "D",  "%"),
            ("DGS5",               "5-Year Treasury Yield",                 "D",  "%"),
            ("DGS7",               "7-Year Treasury Yield",                 "D",  "%"),
            ("DGS10",              "10-Year Treasury Yield",                "D",  "%"),
            ("DGS20",              "20-Year Treasury Yield",                "D",  "%"),
            ("DGS30",              "30-Year Treasury Yield",                "D",  "%"),
            ("T10Y2Y",             "10Y-2Y Treasury Spread",                "D",  "%"),
            ("T10Y3M",             "10Y-3M Treasury Spread",                "D",  "%"),
            ("BAMLH0A0HYM2",      "ICE BofA HY OAS",                       "D",  "%"),
            ("BAMLC0A0CM",         "ICE BofA IG OAS",                       "D",  "%"),
            ("MORTGAGE30US",       "30-Year Mortgage Rate",                 "W",  "%"),
            ("TEDRATE",            "TED Spread",                            "D",  "%"),
        ],
    },
    "monetary": {
        "label": "Monetary Policy & Money Supply",
        "series": [
            ("WALCL",              "Fed Total Assets",                      "W",  "Mil.$"),
            ("RRPONTSYD",          "ON RRP Outstanding",                    "D",  "Bil.$"),
            ("WTREGEN",            "Treasury General Account (TGA)",        "W",  "Mil.$"),
            ("TOTRESNS",           "Total Reserves",                        "M",  "Bil.$"),
            ("BOGMBASE",           "Monetary Base",                         "M",  "Bil.$"),
            ("M2SL",               "M2 Money Stock",                        "M",  "Bil.$"),
            ("M1SL",               "M1 Money Stock",                        "M",  "Bil.$"),
            ("MULT",               "M1 Money Multiplier",                   "M",  "Ratio"),
        ],
    },
    "financial_conditions": {
        "label": "Financial Conditions & Stress",
        "series": [
            ("NFCI",               "Chicago Fed NFCI",                      "W",  "Index"),
            ("ANFCI",              "Adjusted NFCI",                         "W",  "Index"),
            ("STLFSI4",            "St. Louis Fed Financial Stress",        "W",  "Index"),
            ("VIXCLS",             "CBOE VIX",                              "D",  "Index"),
            ("DTWEXBGS",           "Trade-Weighted USD (Broad)",            "D",  "Index"),
            ("DCOILWTICO",         "WTI Crude Oil",                         "D",  "$/barrel"),
            ("GOLDAMGBD228NLBM",   "Gold Price (London Fix)",               "D",  "$/oz"),
            ("SP500",              "S&P 500",                               "D",  "Index"),
            ("WILL5000INDFC",      "Wilshire 5000 Total Market",            "D",  "Index"),
        ],
    },
    "housing": {
        "label": "Housing",
        "series": [
            ("HOUST",              "Housing Starts",                        "M",  "Thousands, SAAR"),
            ("PERMIT",             "Building Permits",                      "M",  "Thousands, SAAR"),
            ("CSUSHPINSA",         "Case-Shiller National HPI",             "M",  "Index Jan2000=100"),
            ("MSPUS",              "Median Home Sale Price",                "Q",  "$"),
            ("EXHOSLUSM495S",      "Existing Home Sales",                   "M",  "Mil., SAAR"),
            ("NHSLTOT",            "New Home Sales",                        "M",  "Thousands, SAAR"),
            ("RHORUSQ156N",        "Homeownership Rate",                   "Q",  "%"),
        ],
    },
    "credit": {
        "label": "Consumer & Bank Credit",
        "series": [
            ("TOTALSL",            "Total Consumer Credit",                 "M",  "Bil.$"),
            ("REVOLSL",            "Revolving Consumer Credit",             "M",  "Bil.$"),
            ("DRALACBS",           "Delinquency Rate (All Loans)",          "Q",  "%"),
            ("DRSFRMACBS",         "Delinquency Rate (Residential RE)",     "Q",  "%"),
            ("BUSLOANS",           "C&I Loans (All Banks)",                 "M",  "Bil.$"),
            ("DRTSCILM",           "Sr. Loan Officer Survey: Tightening",   "Q",  "% net"),
        ],
    },
    "trade": {
        "label": "Trade & External",
        "series": [
            ("BOPGSTB",            "Trade Balance (Goods & Services)",      "M",  "Mil.$"),
            ("BOPGTB",             "Trade Balance (Goods Only)",            "M",  "Mil.$"),
            ("DEXUSEU",            "USD/EUR Exchange Rate",                 "D",  "$/EUR"),
            ("DEXJPUS",            "JPY/USD Exchange Rate",                 "D",  "JPY/$"),
            ("DEXUSUK",            "USD/GBP Exchange Rate",                 "D",  "$/GBP"),
            ("DEXCHUS",            "CNY/USD Exchange Rate",                 "D",  "CNY/$"),
        ],
    },
    "fiscal": {
        "label": "Government & Fiscal",
        "series": [
            ("GFDEBTN",            "Federal Debt Total Public",             "Q",  "Mil.$"),
            ("GFDEGDQ188S",        "Federal Debt as % of GDP",             "Q",  "%"),
            ("MTSDS133FMS",        "Federal Surplus/Deficit",               "M",  "Mil.$"),
            ("FYFSD",              "Federal Surplus/Deficit (FY)",          "A",  "Mil.$"),
            ("A091RC1Q027SBEA",    "Federal Gov Current Expenditures",     "Q",  "Bil.$, SAAR"),
        ],
    },
    "recession_indicators": {
        "label": "Recession Indicators",
        "series": [
            ("SAHMREALTIME",       "Sahm Rule Recession Indicator",         "M",  "pp"),
            ("RECPROUSM156N",      "Smoothed US Recession Probs",           "M",  "%"),
            ("T10Y3M",             "10Y-3M Spread (yield curve)",           "D",  "%"),
            ("USSLIND",            "Leading Index",                         "M",  "Index 2016=100"),
            ("UMCSENT",            "UMich Consumer Sentiment",              "M",  "Index"),
        ],
    },
}

MACRO_SNAPSHOT_SERIES = [
    "GDPC1", "A191RL1Q225SBEA", "PAYEMS", "UNRATE", "ICSA",
    "CPIAUCSL", "PCEPILFE", "FEDFUNDS", "DGS2", "DGS10",
    "T10Y2Y", "BAMLH0A0HYM2", "VIXCLS", "SP500", "NFCI",
    "WALCL", "RRPONTSYD", "M2SL", "HOUST", "SAHMREALTIME",
]

ALL_CATALOG_CODES = {}
for _theme, _info in CATALOG.items():
    for _code, _name, _freq, _units in _info["series"]:
        ALL_CATALOG_CODES[_code] = {
            "name": _name, "freq": _freq, "units": _units, "theme": _theme,
        }


# --- HTTP Layer ---------------------------------------------------------------

_LAST_REQUEST_TS = 0.0


def _rate_limit():
    global _LAST_REQUEST_TS
    now = monotonic()
    elapsed = now - _LAST_REQUEST_TS
    if elapsed < REQUEST_DELAY:
        time.sleep(REQUEST_DELAY - elapsed)
    _LAST_REQUEST_TS = monotonic()


def _fetch_json(endpoint, params, max_retries=4):
    params["api_key"] = API_KEY
    params["file_type"] = "json"
    url = f"{BASE_URL}/{endpoint}?{urlencode(params)}"
    for attempt in range(max_retries):
        try:
            _rate_limit()
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 429:
                wait = 5 * (2 ** attempt)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
            elif e.code == 400:
                print(f"  [bad request: {e.reason}]")
                return None
            else:
                print(f"  [HTTP {e.code}: {e.reason}]")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        except (URLError, TimeoutError) as e:
            print(f"  [connection error: {e}]")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    return None


# --- Helpers ------------------------------------------------------------------

def _safe_float(val, default=None):
    if val in (None, "", "."):
        return default
    try:
        return float(str(val).strip())
    except (ValueError, TypeError):
        return default


def _fmt_num(n, decimals=2, sign=False):
    if n is None:
        return "N/A"
    if sign:
        return f"{n:+,.{decimals}f}"
    return f"{n:,.{decimals}f}"


def _fmt_date(d):
    return str(d)[:10] if d else ""


def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")


def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _export_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Exported: {path}")


def _export_csv(rows, path):
    if not rows:
        return
    if isinstance(rows[0], dict):
        keys = list(rows[0].keys())
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    else:
        with open(path, "w", newline="") as f:
            csv.writer(f).writerows(rows)
    print(f"  Exported: {path}")


def _do_export(data, prefix, fmt):
    os.makedirs(os.path.join(SCRIPT_DIR, "data"), exist_ok=True)
    path = os.path.join(SCRIPT_DIR, "data", f"{prefix}_{_ts()}.{fmt}")
    if fmt == "json":
        _export_json(data, path)
    elif fmt == "csv":
        if isinstance(data, dict):
            data = [data] if not isinstance(list(data.values())[0] if data else None, list) else []
        _export_csv(data if isinstance(data, list) else [data], path)


# --- Data Fetchers ------------------------------------------------------------

def _fetch_observations(series_id, start=None, end=None, limit=100000):
    params = {"series_id": series_id, "limit": limit}
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end
    result = _fetch_json("series/observations", params)
    if not result:
        return []
    return result.get("observations", [])


def _fetch_series_meta(series_id):
    result = _fetch_json("series", {"series_id": series_id})
    if not result:
        return None
    series_list = result.get("seriess", [])
    return series_list[0] if series_list else None


def _fetch_search(text, limit=50):
    result = _fetch_json("series/search", {"search_text": text, "limit": limit})
    if not result:
        return []
    return result.get("seriess", [])


def _fetch_releases(limit=50, offset=0):
    result = _fetch_json("releases", {"limit": limit, "offset": offset})
    if not result:
        return []
    return result.get("releases", [])


def _fetch_release(release_id):
    result = _fetch_json("release", {"release_id": release_id})
    if not result:
        return None
    releases = result.get("releases", [])
    return releases[0] if releases else None


def _fetch_release_series(release_id, limit=1000):
    result = _fetch_json("release/series", {
        "release_id": release_id, "limit": limit,
    })
    if not result:
        return []
    return result.get("seriess", [])


def _fetch_release_dates(limit=50, include_empty=False):
    params = {"limit": limit, "sort_order": "desc"}
    if include_empty:
        params["include_release_dates_with_no_data"] = "true"
    result = _fetch_json("releases/dates", params)
    if not result:
        return []
    return result.get("release_dates", [])


def _fetch_category(category_id):
    result = _fetch_json("category", {"category_id": category_id})
    if not result:
        return None
    cats = result.get("categories", [])
    return cats[0] if cats else None


def _fetch_category_children(category_id):
    result = _fetch_json("category/children", {"category_id": category_id})
    if not result:
        return []
    return result.get("categories", [])


def _fetch_category_series(category_id, limit=1000):
    result = _fetch_json("category/series", {
        "category_id": category_id, "limit": limit,
    })
    if not result:
        return []
    return result.get("seriess", [])


# --- Command Functions --------------------------------------------------------

def cmd_search(text, limit=50, as_json=False, export_fmt=None):
    print(f"\n  Searching FRED for \"{text}\"...")
    results = _fetch_search(text, limit=limit)

    if not results:
        print("  No results found.")
        return

    if as_json:
        print(json.dumps(results, indent=2, default=str))
        return results

    print(f"\n  Search Results ({len(results)} series)")
    print("  " + "=" * 95)
    print(f"  {'Series ID':<20} {'Title':<48} {'Freq':<6} {'Units'}")
    print(f"  {'-'*20} {'-'*48} {'-'*6} {'-'*20}")

    for s in results:
        sid = s.get("id", "")[:20]
        title = s.get("title", "")[:48]
        freq = s.get("frequency_short", "")[:6]
        units = s.get("units_short", s.get("units", ""))[:20]
        in_catalog = " *" if sid.strip() in ALL_CATALOG_CODES else ""
        print(f"  {sid:<20} {title:<48} {freq:<6} {units}{in_catalog}")

    print(f"\n  * = in curated catalog")
    print()

    if export_fmt:
        _do_export(results, f"fred_search_{text.replace(' ', '_')[:20]}", export_fmt)
    return results


def cmd_get(series_ids, start=None, end=None, last_n=None, combine=False,
            as_json=False, export_fmt=None):
    ids = [s.strip().upper() for s in series_ids.split(",") if s.strip()]
    if not ids:
        print("  No series IDs provided.")
        return

    all_data = {}
    total = len(ids)
    for idx, sid in enumerate(ids):
        label = ALL_CATALOG_CODES.get(sid, {}).get("name", sid)
        print(f"  [{idx+1}/{total}] Fetching {sid} ({label})...")
        obs = _fetch_observations(sid, start=start, end=end)
        if obs:
            if last_n:
                obs = obs[-last_n:]
            all_data[sid] = obs
        else:
            print(f"    No data returned for {sid}")

    if not all_data:
        print("  No data returned.")
        return

    if as_json:
        out = {}
        for sid, obs_list in all_data.items():
            out[sid] = [{"date": o.get("date", ""), "value": o.get("value", "")}
                        for o in obs_list]
        print(json.dumps(out, indent=2, default=str))
        return out

    if combine and len(ids) > 1:
        _display_combined(all_data, ids)
    else:
        for sid, obs_list in all_data.items():
            _display_series(sid, obs_list)

    if export_fmt:
        if combine and len(ids) > 1:
            flat = _build_wide_rows(all_data, ids)
            _do_export(flat, f"fred_{'_'.join(ids[:3])}", export_fmt)
        else:
            for sid, obs_list in all_data.items():
                rows = [{"date": o.get("date", ""), "value": o.get("value", "")}
                        for o in obs_list]
                _do_export(rows, f"fred_{sid}", export_fmt)
    return all_data


def cmd_compare(series_ids, as_json=False, export_fmt=None):
    ids = [s.strip().upper() for s in series_ids if s.strip()]
    if not ids:
        print("  No series IDs provided.")
        return

    records = []
    total = len(ids)
    for idx, sid in enumerate(ids):
        print(f"  [{idx+1}/{total}] Fetching {sid}...")
        obs = _fetch_observations(sid)
        if not obs:
            continue
        recent = [o for o in obs if o.get("value", ".") != "."]
        if not recent:
            continue
        last_obs = recent[-1]
        prev_obs = recent[-2] if len(recent) >= 2 else None
        val = _safe_float(last_obs.get("value"))
        prev_val = _safe_float(prev_obs.get("value")) if prev_obs else None
        chg = (val - prev_val) if val is not None and prev_val is not None else None
        info = ALL_CATALOG_CODES.get(sid, {})
        records.append({
            "series_id": sid,
            "name": info.get("name", sid),
            "date": _fmt_date(last_obs.get("date")),
            "value": val,
            "prev_value": prev_val,
            "change": chg,
            "freq": info.get("freq", ""),
            "units": info.get("units", ""),
        })

    if not records:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    print(f"\n  Series Comparison ({len(records)} series)")
    print("  " + "=" * 100)
    print(f"  {'Series':<16} {'Name':<34} {'Date':<12} {'Value':>14} {'Change':>12} {'Units'}")
    print(f"  {'-'*16} {'-'*34} {'-'*12} {'-'*14} {'-'*12} {'-'*18}")
    for r in records:
        val_str = _fmt_num(r["value"], decimals=2) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=2, sign=True) if r["change"] is not None else ""
        print(f"  {r['series_id']:<16} {r['name']:<34} {r['date']:<12} "
              f"{val_str:>14} {chg_str:>12} {r['units']}")
    print()

    if export_fmt:
        _do_export(records, "fred_compare", export_fmt)
    return records


def cmd_catalog(theme=None, as_json=False, export_fmt=None):
    if theme:
        theme = theme.lower().replace("-", "_").replace(" ", "_")
        if theme not in CATALOG:
            matches = [k for k in CATALOG if theme in k]
            if matches:
                theme = matches[0]
            else:
                print(f"  Unknown theme '{theme}'. Available: {', '.join(CATALOG.keys())}")
                return

    themes = {theme: CATALOG[theme]} if theme else CATALOG

    if as_json:
        out = {}
        for t, info in themes.items():
            out[t] = {
                "label": info["label"],
                "series": [{"id": s[0], "name": s[1], "freq": s[2], "units": s[3]}
                           for s in info["series"]],
            }
        print(json.dumps(out, indent=2))
        return out

    total = sum(len(info["series"]) for info in themes.values())
    print(f"\n  FRED Curated Catalog ({total} series across {len(themes)} themes)")
    print("  " + "=" * 90)

    for t, info in themes.items():
        print(f"\n  {info['label'].upper()} [{t}]")
        print(f"  {'Series ID':<22} {'Name':<40} {'Freq':<6} {'Units'}")
        print(f"  {'-'*22} {'-'*40} {'-'*6} {'-'*20}")
        for code, name, freq, units in info["series"]:
            print(f"  {code:<22} {name:<40} {freq:<6} {units}")

    print()

    if export_fmt:
        flat = []
        for t, info in themes.items():
            for code, name, freq, units in info["series"]:
                flat.append({"theme": t, "series_id": code, "name": name,
                             "freq": freq, "units": units})
        _do_export(flat, "fred_catalog", export_fmt)
    return themes


def cmd_releases(limit=30, as_json=False, export_fmt=None):
    print(f"\n  Fetching recent release dates...")
    dates = _fetch_release_dates(limit=limit)

    if not dates:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(dates, indent=2, default=str))
        return dates

    print(f"\n  Recent FRED Releases ({len(dates)} entries)")
    print("  " + "=" * 80)
    print(f"  {'Date':<12} {'Release ID':>12} {'Name'}")
    print(f"  {'-'*12} {'-'*12} {'-'*52}")

    for d in dates:
        date = _fmt_date(d.get("date", d.get("release_date", "")))
        rid = d.get("release_id", "")
        name = d.get("release_name", d.get("name", ""))[:52]
        print(f"  {date:<12} {str(rid):>12} {name}")

    print()

    if export_fmt:
        _do_export(dates, "fred_releases", export_fmt)
    return dates


def cmd_release(release_id, as_json=False, export_fmt=None):
    print(f"\n  Fetching release {release_id}...")
    meta = _fetch_release(release_id)
    if not meta:
        print(f"  Release {release_id} not found.")
        return

    print(f"  Fetching series in release {release_id}...")
    series = _fetch_release_series(release_id)

    result = {"release": meta, "series": series}

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    print(f"\n  Release: {meta.get('name', '')} (ID: {release_id})")
    print("  " + "=" * 80)
    print(f"  Link:      {meta.get('link', 'N/A')}")
    print(f"  Press:     {meta.get('press_release', 'N/A')}")

    if series:
        print(f"\n  Series in release ({len(series)} total):")
        print(f"  {'Series ID':<20} {'Title':<48} {'Freq':<6}")
        print(f"  {'-'*20} {'-'*48} {'-'*6}")
        for s in series[:50]:
            sid = s.get("id", "")[:20]
            title = s.get("title", "")[:48]
            freq = s.get("frequency_short", "")
            in_cat = " *" if sid.strip() in ALL_CATALOG_CODES else ""
            print(f"  {sid:<20} {title:<48} {freq:<6}{in_cat}")
        if len(series) > 50:
            print(f"  ... and {len(series) - 50} more")
    print()

    if export_fmt:
        _do_export(series, f"fred_release_{release_id}", export_fmt)
    return result


def cmd_categories(category_id=0, as_json=False, export_fmt=None):
    print(f"\n  Browsing category {category_id}...")
    cat = _fetch_category(category_id)
    children = _fetch_category_children(category_id)

    result = {"category": cat, "children": children}

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    if cat:
        name = cat.get("name", f"Category {category_id}")
        parent = cat.get("parent_id", "")
        print(f"\n  Category: {name} (ID: {category_id}, parent: {parent})")
    else:
        print(f"\n  Category {category_id}")
    print("  " + "=" * 60)

    if children:
        print(f"\n  Child Categories ({len(children)}):")
        print(f"  {'ID':>8} {'Name':<50}")
        print(f"  {'-'*8} {'-'*50}")
        for c in children:
            cid = c.get("id", "")
            cname = c.get("name", "")[:50]
            print(f"  {str(cid):>8} {cname}")
    else:
        print("  No child categories. Fetching series...")
        series = _fetch_category_series(category_id)
        if series:
            print(f"\n  Series in category ({len(series)}):")
            print(f"  {'Series ID':<20} {'Title':<48} {'Freq':<6}")
            print(f"  {'-'*20} {'-'*48} {'-'*6}")
            for s in series[:40]:
                print(f"  {s.get('id', ''):<20} {s.get('title', '')[:48]:<48} "
                      f"{s.get('frequency_short', ''):<6}")
            if len(series) > 40:
                print(f"  ... and {len(series) - 40} more")

    print()

    if export_fmt:
        _do_export(children if children else [], f"fred_category_{category_id}", export_fmt)
    return result


def cmd_metadata(series_id, as_json=False, export_fmt=None):
    series_id = series_id.strip().upper()
    print(f"\n  Fetching metadata for {series_id}...")
    meta = _fetch_series_meta(series_id)

    if not meta:
        print(f"  Series {series_id} not found.")
        return

    if as_json:
        print(json.dumps(meta, indent=2, default=str))
        return meta

    print(f"\n  Series: {meta.get('id', '')} -- {meta.get('title', '')}")
    print("  " + "=" * 70)
    fields = [
        ("Frequency", "frequency"),
        ("Units", "units"),
        ("Seasonal Adj", "seasonal_adjustment"),
        ("First Obs", "observation_start"),
        ("Last Obs", "observation_end"),
        ("Last Updated", "last_updated"),
        ("Popularity", "popularity"),
        ("Notes", "notes"),
    ]
    for label, key in fields:
        val = meta.get(key, "N/A")
        if key == "notes" and val and len(str(val)) > 200:
            val = str(val)[:200] + "..."
        print(f"  {label:<16} {val}")

    catalog_info = ALL_CATALOG_CODES.get(series_id)
    if catalog_info:
        print(f"  {'Catalog Theme':<16} {catalog_info['theme']}")

    print()

    if export_fmt:
        _do_export(meta, f"fred_meta_{series_id}", export_fmt)
    return meta


def cmd_macro_snapshot(as_json=False, export_fmt=None):
    print(f"\n  Building macro snapshot ({len(MACRO_SNAPSHOT_SERIES)} series)...")
    records = []
    total = len(MACRO_SNAPSHOT_SERIES)
    t0 = time.time()

    for idx, sid in enumerate(MACRO_SNAPSHOT_SERIES):
        info = ALL_CATALOG_CODES.get(sid, {})
        label = info.get("name", sid)
        elapsed = int(time.time() - t0)
        print(f"  [{idx+1}/{total}] {sid} ({label})... ({elapsed}s)")

        obs = _fetch_observations(sid)
        if not obs:
            continue

        recent = [o for o in obs if o.get("value", ".") != "."]
        if not recent:
            continue

        last_obs = recent[-1]
        prev_obs = recent[-2] if len(recent) >= 2 else None
        val = _safe_float(last_obs.get("value"))
        prev_val = _safe_float(prev_obs.get("value")) if prev_obs else None
        chg = (val - prev_val) if val is not None and prev_val is not None else None

        records.append({
            "series_id": sid,
            "name": label,
            "date": _fmt_date(last_obs.get("date")),
            "value": val,
            "change": chg,
            "freq": info.get("freq", ""),
            "units": info.get("units", ""),
            "theme": info.get("theme", ""),
        })

    if not records:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(records, indent=2, default=str))
        return records

    current_theme = None
    print(f"\n  MACRO SNAPSHOT ({len(records)} indicators)")
    print("  " + "=" * 105)

    for r in records:
        theme = r.get("theme", "")
        if theme != current_theme:
            current_theme = theme
            theme_label = CATALOG.get(theme, {}).get("label", theme.upper())
            print(f"\n  {theme_label}")
            print(f"  {'Series':<16} {'Name':<30} {'Date':<12} {'Value':>14} "
                  f"{'Change':>12} {'Units'}")
            print(f"  {'-'*16} {'-'*30} {'-'*12} {'-'*14} {'-'*12} {'-'*18}")

        val_str = _fmt_num(r["value"], decimals=2) if r["value"] is not None else "N/A"
        chg_str = _fmt_num(r["change"], decimals=2, sign=True) if r["change"] is not None else ""
        print(f"  {r['series_id']:<16} {r['name']:<30} {r['date']:<12} "
              f"{val_str:>14} {chg_str:>12} {r['units']}")

    elapsed = int(time.time() - t0)
    print(f"\n  Completed in {elapsed}s")
    print()

    if export_fmt:
        _do_export(records, "fred_macro_snapshot", export_fmt)
    return records


# --- Display Helpers ----------------------------------------------------------

def _display_series(series_id, observations):
    if not observations:
        return
    info = ALL_CATALOG_CODES.get(series_id, {})
    name = info.get("name", series_id)
    units = info.get("units", "")

    recent = observations[-60:] if len(observations) > 60 else observations

    print(f"\n  {series_id} -- {name}")
    if units:
        print(f"  Units: {units}")
    print("  " + "=" * 40)
    print(f"  {'Date':<12} {'Value':>14}")
    print(f"  {'-'*12} {'-'*14}")

    for obs in recent:
        date = _fmt_date(obs.get("date"))
        val = obs.get("value", ".")
        if val == ".":
            val_str = "N/A"
        else:
            v = _safe_float(val)
            val_str = _fmt_num(v, decimals=2) if v is not None else str(val)
        print(f"  {date:<12} {val_str:>14}")

    if len(observations) > 60:
        print(f"  ... showing last 60 of {len(observations)} observations")
    print()


def _display_combined(all_data, ids):
    wide = _build_wide_rows(all_data, ids)
    if not wide:
        return

    header_ids = [sid[:14] for sid in ids if sid in all_data]
    print(f"\n  Combined Series ({len(header_ids)} series)")
    print("  " + "=" * (14 + 16 * len(header_ids)))
    hdr = f"  {'Date':<12}"
    for h in header_ids:
        hdr += f" {h:>14}"
    print(hdr)
    sep = f"  {'-'*12}"
    for _ in header_ids:
        sep += f" {'-'*14}"
    print(sep)

    display_rows = wide[-60:] if len(wide) > 60 else wide
    for row in display_rows:
        line = f"  {row['date']:<12}"
        for sid in ids:
            if sid in all_data:
                v = row.get(sid, "")
                if v == "" or v is None:
                    line += f" {'':>14}"
                else:
                    line += f" {_fmt_num(_safe_float(v), decimals=2):>14}"
        print(line)

    if len(wide) > 60:
        print(f"  ... showing last 60 of {len(wide)} rows")
    print()


def _build_wide_rows(all_data, ids):
    date_map = {}
    for sid in ids:
        for obs in all_data.get(sid, []):
            d = obs.get("date", "")
            if d not in date_map:
                date_map[d] = {"date": d}
            date_map[d][sid] = obs.get("value", "")
    return sorted(date_map.values(), key=lambda x: x["date"])


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   FRED -- Federal Reserve Economic Data Client
  =====================================================

   DISCOVERY
     1) search          Search for series by keyword
     2) catalog         Browse curated series catalog
     3) metadata        Series metadata detail

   DATA RETRIEVAL
     4) get             Pull observations for series
     5) compare         Side-by-side latest values

   NAVIGATION
     6) releases        Recent release calendar
     7) release         Release detail + series list
     8) categories      Browse category tree

   DASHBOARDS
     9) macro-snapshot  Curated macro dashboard pull

   q) quit
"""


def _i_search():
    text = _prompt("Search text")
    if text:
        limit = _prompt("Max results", "50")
        cmd_search(text, limit=int(limit))

def _i_catalog():
    print(f"  Themes: {', '.join(CATALOG.keys())}")
    theme = _prompt("Theme filter (or enter for all)", "")
    cmd_catalog(theme=theme if theme else None)

def _i_metadata():
    sid = _prompt("Series ID (e.g. GDPC1)")
    if sid:
        cmd_metadata(sid)

def _i_get():
    sid = _prompt("Series ID(s), comma-separated (e.g. GDPC1,UNRATE)")
    if not sid:
        return
    start = _prompt("Start date YYYY-MM-DD (or enter for all)", "")
    last_n = _prompt("Last N observations (or enter for all)", "")
    combine = False
    if "," in sid:
        combine_str = _prompt("Combine into wide format? (y/n)", "n")
        combine = combine_str.lower() == "y"
    cmd_get(sid, start=start if start else None,
            last_n=int(last_n) if last_n else None, combine=combine)

def _i_compare():
    sid = _prompt("Series IDs, space-separated (e.g. GDPC1 UNRATE CPIAUCSL)")
    if sid:
        ids = sid.split()
        cmd_compare(ids)

def _i_releases():
    limit = _prompt("Number of recent releases", "30")
    cmd_releases(limit=int(limit))

def _i_release():
    rid = _prompt("Release ID (e.g. 53 for GDP)")
    if rid:
        cmd_release(int(rid))

def _i_categories():
    cid = _prompt("Category ID (0 for root)", "0")
    cmd_categories(category_id=int(cid))

def _i_macro_snapshot():
    cmd_macro_snapshot()


COMMAND_MAP = {
    "1": _i_search,
    "2": _i_catalog,
    "3": _i_metadata,
    "4": _i_get,
    "5": _i_compare,
    "6": _i_releases,
    "7": _i_release,
    "8": _i_categories,
    "9": _i_macro_snapshot,
}


def interactive_loop():
    if not API_KEY:
        print("\n  WARNING: FRED_API_KEY not set.")
        print("  Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        print("  Then: export FRED_API_KEY=your_key_here\n")
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
            print("  Enter 1-9 or q to quit")


# --- Argparse -----------------------------------------------------------------

def build_argparse():
    p = argparse.ArgumentParser(
        prog="fred.py",
        description="FRED (Federal Reserve Economic Data) -- Macro Data Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("search", help="Search for series by keyword")
    s.add_argument("text", help="Search keywords")
    s.add_argument("--limit", type=int, default=50)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("get", help="Pull observations for one or more series")
    s.add_argument("series", help="Series ID(s), comma-separated")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--last", type=int, help="Last N observations only")
    s.add_argument("--combine", action="store_true", help="Combine multi-series into wide CSV")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("compare", help="Side-by-side latest values for multiple series")
    s.add_argument("series", nargs="+", help="Series IDs")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("catalog", help="Show curated series catalog")
    s.add_argument("--theme", help="Filter by theme")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("releases", help="Recent release calendar")
    s.add_argument("--limit", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("release", help="Release detail + series list")
    s.add_argument("release_id", type=int, help="Release ID")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("categories", help="Browse FRED category tree")
    s.add_argument("category_id", nargs="?", type=int, default=0, help="Category ID (0=root)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("metadata", help="Series metadata detail")
    s.add_argument("series", help="Series ID")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("macro-snapshot", help="Curated macro dashboard pull")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "search":
        cmd_search(args.text, limit=args.limit, as_json=j, export_fmt=exp)
    elif args.command == "get":
        cmd_get(args.series, start=args.start, end=getattr(args, "end", None),
                last_n=getattr(args, "last", None), combine=args.combine,
                as_json=j, export_fmt=exp)
    elif args.command == "compare":
        cmd_compare(args.series, as_json=j, export_fmt=exp)
    elif args.command == "catalog":
        cmd_catalog(theme=getattr(args, "theme", None), as_json=j, export_fmt=exp)
    elif args.command == "releases":
        cmd_releases(limit=args.limit, as_json=j, export_fmt=exp)
    elif args.command == "release":
        cmd_release(args.release_id, as_json=j, export_fmt=exp)
    elif args.command == "categories":
        cmd_categories(category_id=args.category_id, as_json=j, export_fmt=exp)
    elif args.command == "metadata":
        cmd_metadata(args.series, as_json=j, export_fmt=exp)
    elif args.command == "macro-snapshot":
        cmd_macro_snapshot(as_json=j, export_fmt=exp)


# --- Main ---------------------------------------------------------------------

def main():
    if not API_KEY:
        print("  WARNING: FRED_API_KEY not set. Set via: export FRED_API_KEY=your_key",
              file=sys.stderr)

    parser = build_argparse()
    args = parser.parse_args()

    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
