#!/usr/bin/env python3
"""
OpenFIGI -- Financial Instrument Global Identifier Mapping Client

Single-script client for the OpenFIGI API v3 (api.openfigi.com).
Maps between identifier systems: ticker, CUSIP, ISIN, SEDOL, FIGI, composite FIGI,
share class FIGI, and 20+ other ID types. Covers equities, fixed income, derivatives,
indices globally.

Usage:
    python openfigi.py                                    # interactive CLI (33 commands)
    python openfigi.py map TICKER IBM                     # map ticker to FIGI
    python openfigi.py map ID_CUSIP 459200101             # map CUSIP to FIGI
    python openfigi.py search "apple" --sector Equity     # keyword search
    python openfigi.py equity AAPL                        # quick equity lookup
    python openfigi.py bond 912810SZ9                     # Treasury CUSIP lookup
    python openfigi.py cross-ref TICKER AAPL              # all identifiers for AAPL
    python openfigi.py options AAPL --strike-min 150      # options chain
    python openfigi.py futures ES                         # futures term structure
    python openfigi.py figi-lookup BBG000B9XRY4           # reverse FIGI hierarchy
    python openfigi.py portfolio "AAPL,US4592001014"      # auto-detect mixed IDs
    python openfigi.py mbs FNMA --maturity 2025-2030      # mortgage-backed securities
    python openfigi.py fx EUR --json                      # FX instruments
    python openfigi.py exchange-scan US --sector Equity    # exchange universe
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime

import requests


# ─── API Configuration ────────────────────────────────────────────────────────

BASE_URL = "https://api.openfigi.com/v3"
SESSION = requests.Session()
SESSION.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
})

API_KEY = os.environ.get("OPENFIGI_API_KEY", "27555b60-a631-4142-94c1-320133283cc1")
if API_KEY:
    SESSION.headers["X-OPENFIGI-APIKEY"] = API_KEY

HAS_KEY = bool(API_KEY)
MAX_JOBS = 100 if HAS_KEY else 10
RATE_LIMIT_WINDOW = 6 if HAS_KEY else 60
MAX_REQUESTS_PER_WINDOW = 25


# ─── ID Type Registry ─────────────────────────────────────────────────────────
# Organized by usage frequency for PRISM workflows.

ID_TYPES = {
    "TICKER":                      "Ticker symbol (e.g. IBM, AAPL)",
    "ID_CUSIP":                    "CUSIP (9-char, e.g. 459200101)",
    "ID_ISIN":                     "ISIN (e.g. US4592001014)",
    "ID_SEDOL":                    "SEDOL (7-char, e.g. 2005973)",
    "ID_BB_GLOBAL":                "Bloomberg FIGI (BBG...)",
    "COMPOSITE_ID_BB_GLOBAL":      "Composite FIGI (country-level aggregate)",
    "ID_BB_GLOBAL_SHARE_CLASS_LEVEL": "Share Class FIGI (global aggregate)",
    "BASE_TICKER":                 "Base ticker (for options, bonds, pools)",
    "ID_CUSIP_8_CHR":              "CUSIP first 8 chars (issuer-level)",
    "ID_BB_UNIQUE":                "Legacy Bloomberg unique ID",
    "ID_BB":                       "Legacy Bloomberg ID",
    "ID_BB_8_CHR":                 "Legacy Bloomberg 8-char",
    "ID_TRACE":                    "FINRA TRACE identifier",
    "ID_COMMON":                   "Common Code (9-digit)",
    "ID_WERTPAPIER":               "WKN / Wertpapierkennnummer",
    "ID_CINS":                     "CINS (international CUSIP)",
    "ID_ITALY":                    "Italian identifier",
    "ID_EXCH_SYMBOL":              "Exchange-specific symbol",
    "ID_FULL_EXCHANGE_SYMBOL":     "Full exchange symbol (futures/options)",
    "ID_BB_SEC_NUM_DES":           "Bloomberg security description",
    "OCC_SYMBOL":                  "OCC option symbol",
    "UNIQUE_ID_FUT_OPT":           "Bloomberg future/option unique ID",
    "OPRA_SYMBOL":                 "OPRA option symbol",
    "TRADING_SYSTEM_IDENTIFIER":   "Trading system ID",
    "ID_SHORT_CODE":               "Short code (Asian FI)",
    "VENDOR_INDEX_CODE":           "Index provider code",
}

MARKET_SECTORS = ["Equity", "Corp", "Govt", "Comdty", "Curncy", "Index", "M-Mkt", "Mtge", "Muni", "Pfd"]

ENUM_KEYS = ["idType", "exchCode", "micCode", "currency", "marketSecDes",
             "securityType", "securityType2", "stateCode"]

RESPONSE_FIELDS = ["figi", "name", "ticker", "exchCode", "compositeFIGI",
                   "shareClassFIGI", "securityType", "securityType2",
                   "marketSector", "securityDescription"]


# ─── Curated Issuer Lists ─────────────────────────────────────────────────────

ISSUER_LISTS = {
    "banks":   ["JPM", "BAC", "C", "GS", "MS", "WFC"],
    "tech":    ["AAPL", "MSFT", "GOOG", "AMZN", "META", "INTC"],
    "energy":  ["XOM", "CVX", "COP", "SLB", "EOG"],
    "pharma":  ["JNJ", "PFE", "MRK", "ABBV", "LLY"],
    "telco":   ["T", "VZ", "TMUS"],
    "auto":    ["F", "GM", "TSLA"],
}


# ─── Identifier Auto-Detection ────────────────────────────────────────────────

def _detect_id_type(value):
    """Auto-detect identifier type from value format."""
    value = value.strip()
    if not value:
        return "TICKER"
    if value.startswith("BBG") and len(value) == 12:
        return "ID_BB_GLOBAL"
    if len(value) == 12 and value[:2].isalpha() and value[2:].isalnum():
        return "ID_ISIN"
    if len(value) == 9 and value.isalnum():
        return "ID_CUSIP"
    if len(value) == 7 and value.isalnum():
        return "ID_SEDOL"
    if len(value) == 8 and value.isalnum():
        return "ID_CUSIP_8_CHR"
    return "TICKER"


import re

_DATE_RE = re.compile(r'(\d{2}/\d{2}/\d{2,4})')


def _parse_bond_ticker(ticker_str):
    """Parse a Bloomberg bond ticker description into structured fields.
    Examples:
        "INTC 3.7 07/29/25"      -> coupon=3.7, maturity=2025-07-29, rate_type=fixed
        "INTC F 05/11/27"        -> coupon=None, maturity=2027-05-11, rate_type=floating
        "INTC V3.22 03/01/25"    -> coupon=3.22, maturity=2025-03-01, rate_type=variable
        "JPM 4.25 11/30/25 GMTN" -> coupon=4.25, maturity=2025-11-30, suffix=GMTN
        "INTC 0 02/01/04 144A"   -> coupon=0, maturity=2004-02-01, suffix=144A
    """
    result = {"issuer": None, "coupon": None, "rate_type": "fixed",
              "maturity": None, "maturity_str": None, "suffix": None, "raw": ticker_str}

    if not ticker_str:
        return result

    m = _DATE_RE.search(ticker_str)
    if not m:
        parts = ticker_str.split()
        result["issuer"] = parts[0] if parts else ticker_str
        return result

    date_str = m.group(1)
    before = ticker_str[:m.start()].strip()
    after = ticker_str[m.end():].strip()

    # Parse maturity date (MM/DD/YY or MM/DD/YYYY)
    try:
        d_parts = date_str.split("/")
        month, day = int(d_parts[0]), int(d_parts[1])
        year = int(d_parts[2])
        if year < 100:
            year += 2000 if year < 70 else 1900
        result["maturity"] = f"{year:04d}-{month:02d}-{day:02d}"
        result["maturity_str"] = date_str
    except (ValueError, IndexError):
        result["maturity_str"] = date_str

    # Parse before-date: issuer + coupon
    before_parts = before.split()
    if before_parts:
        result["issuer"] = before_parts[0]
        if len(before_parts) >= 2:
            cpn = before_parts[1]
            if cpn.startswith("F") and (len(cpn) == 1 or not cpn[1:].replace(".", "").isdigit()):
                result["rate_type"] = "floating"
            elif cpn.startswith("V"):
                result["rate_type"] = "variable"
                try:
                    result["coupon"] = float(cpn[1:])
                except ValueError:
                    pass
            elif cpn.startswith("L") and (len(cpn) == 1 or not cpn[1:].replace(".", "").isdigit()):
                result["rate_type"] = "floating"
            else:
                try:
                    result["coupon"] = float(cpn)
                    if result["coupon"] == 0:
                        result["rate_type"] = "zero"
                except ValueError:
                    pass

    # Parse suffix (144A, REGS, GMTN, AI, etc.)
    if after:
        result["suffix"] = after

    return result


def _parse_maturity_year(parsed):
    """Extract year from parsed bond ticker, returns int or None."""
    if parsed.get("maturity"):
        try:
            return int(parsed["maturity"][:4])
        except (ValueError, TypeError):
            pass
    return None


def _fmt_coupon(parsed):
    """Format coupon for display."""
    if parsed["rate_type"] == "floating":
        return "Float"
    if parsed["rate_type"] == "variable":
        return f"V{parsed['coupon']:.2f}" if parsed["coupon"] is not None else "Var"
    if parsed["rate_type"] == "zero":
        return "Zero"
    if parsed["coupon"] is not None:
        return f"{parsed['coupon']:.3f}"
    return "N/A"


# ─── HTTP Layer ───────────────────────────────────────────────────────────────

_last_request_time = 0.0


def _rate_wait():
    global _last_request_time
    min_interval = RATE_LIMIT_WINDOW / MAX_REQUESTS_PER_WINDOW
    elapsed = time.time() - _last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    _last_request_time = time.time()


def _post(endpoint, payload, max_retries=3):
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        _rate_wait()
        try:
            r = SESSION.post(url, json=payload, timeout=30)
            if r.status_code == 429:
                reset = int(r.headers.get("ratelimit-reset", 10))
                wait = max(reset, 3 * (attempt + 1))
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code == 413:
                print(f"  [payload too large -- reduce batch size]")
                return None
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


def _get(endpoint, max_retries=3):
    url = f"{BASE_URL}{endpoint}"
    for attempt in range(max_retries):
        _rate_wait()
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 429:
                reset = int(r.headers.get("ratelimit-reset", 10))
                wait = max(reset, 3 * (attempt + 1))
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


# ─── Core API Functions ───────────────────────────────────────────────────────

def api_map(jobs):
    """POST /v3/mapping -- batch map identifiers to FIGIs.
    jobs: list of dicts, each with at minimum idType + idValue.
    Returns list of result dicts (one per job), each with 'data', 'error', or 'warning'.
    """
    if not jobs:
        return []

    all_results = []
    for i in range(0, len(jobs), MAX_JOBS):
        chunk = jobs[i:i + MAX_JOBS]
        if i > 0:
            print(f"  Mapping batch {i // MAX_JOBS + 1} ({len(chunk)} jobs)...")
        resp = _post("/mapping", chunk)
        if resp is None:
            all_results.extend([{"error": "Request failed"}] * len(chunk))
        else:
            all_results.extend(resp)
    return all_results


def api_map_single(id_type, id_value, **filters):
    """Map a single identifier. Convenience wrapper around api_map."""
    job = {"idType": id_type, "idValue": id_value}
    job.update({k: v for k, v in filters.items() if v is not None})
    results = api_map([job])
    return results[0] if results else {"error": "No response"}


def api_search(query, start=None, max_pages=5, **filters):
    """POST /v3/search -- keyword search for FIGIs.
    Returns consolidated list of instrument dicts.
    """
    payload = {"query": query}
    payload.update({k: v for k, v in filters.items() if v is not None})

    all_data = []
    for page in range(max_pages):
        if start:
            payload["start"] = start
        resp = _post("/search", payload)
        if resp is None:
            break
        if "data" in resp:
            all_data.extend(resp["data"])
        if "next" not in resp:
            break
        start = resp["next"]
        if page < max_pages - 1:
            print(f"  Page {page + 2}...")

    return all_data


def api_filter(query=None, start=None, max_pages=5, **filters):
    """POST /v3/filter -- filtered search, alphabetical by FIGI.
    Returns consolidated list of instrument dicts + total count.
    """
    payload = {}
    if query:
        payload["query"] = query
    payload.update({k: v for k, v in filters.items() if v is not None})

    all_data = []
    total = 0
    for page in range(max_pages):
        if start:
            payload["start"] = start
        resp = _post("/filter", payload)
        if resp is None:
            break
        if "data" in resp:
            all_data.extend(resp["data"])
        if "total" in resp:
            total = resp["total"]
        if "next" not in resp:
            break
        start = resp["next"]
        if page < max_pages - 1:
            print(f"  Page {page + 2} (total: {total:,})...")

    return all_data, total


def api_enum_values(key):
    """GET /v3/mapping/values/:key -- list valid enum values."""
    resp = _get(f"/mapping/values/{key}")
    if resp and "values" in resp:
        return resp["values"]
    return []


# ─── Display Helpers ──────────────────────────────────────────────────────────

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


def _display_instruments(instruments, title=None, compact=False):
    if not instruments:
        print("  No results found.")
        return

    if title:
        print(f"\n  {title}")
        print("  " + "=" * 80)

    if compact:
        hdr = f"  {'Ticker':<12} {'Name':<35} {'Sector':<8} {'Type':<18} {'Exch':<6} {'FIGI'}"
        sep = f"  {'-'*12} {'-'*35} {'-'*8} {'-'*18} {'-'*6} {'-'*12}"
        print(hdr)
        print(sep)
        for inst in instruments:
            ticker = (inst.get("ticker") or "")[:12]
            name = (inst.get("name") or "")[:35]
            sector = (inst.get("marketSector") or "")[:8]
            stype = (inst.get("securityType") or inst.get("securityType2") or "")[:18]
            exch = (inst.get("exchCode") or "")[:6]
            figi = inst.get("figi") or ""
            print(f"  {ticker:<12} {name:<35} {sector:<8} {stype:<18} {exch:<6} {figi}")
    else:
        for i, inst in enumerate(instruments):
            if i > 0:
                print("  " + "-" * 60)
            print(f"  FIGI:           {inst.get('figi', 'N/A')}")
            print(f"  Composite FIGI: {inst.get('compositeFIGI') or 'N/A'}")
            print(f"  Share Class:    {inst.get('shareClassFIGI') or 'N/A'}")
            print(f"  Ticker:         {inst.get('ticker') or 'N/A'}")
            print(f"  Name:           {inst.get('name') or 'N/A'}")
            print(f"  Exchange:       {inst.get('exchCode') or 'N/A'}")
            print(f"  Sector:         {inst.get('marketSector') or 'N/A'}")
            print(f"  Security Type:  {inst.get('securityType') or 'N/A'}")
            print(f"  Type 2:         {inst.get('securityType2') or 'N/A'}")
            print(f"  Description:    {inst.get('securityDescription') or 'N/A'}")

    print(f"\n  [{len(instruments)} instrument(s)]")


def _display_mapping_result(result, id_type, id_value):
    if "error" in result:
        print(f"  {id_type} {id_value} -> ERROR: {result['error']}")
    elif "warning" in result:
        print(f"  {id_type} {id_value} -> {result['warning']}")
    elif "data" in result:
        data = result["data"]
        print(f"\n  {id_type} {id_value} -> {len(data)} match(es)")
        _display_instruments(data)
    else:
        print(f"  {id_type} {id_value} -> unexpected response")


def _display_batch_summary(jobs, results, compact=True):
    successes = 0
    failures = 0
    warnings = 0
    all_instruments = []

    for job, result in zip(jobs, results):
        id_val = job.get("idValue", "?")
        if "data" in result:
            successes += 1
            for inst in result["data"]:
                inst["_query_id"] = id_val
                inst["_query_type"] = job.get("idType", "?")
                all_instruments.append(inst)
        elif "warning" in result:
            warnings += 1
        else:
            failures += 1

    print(f"\n  Batch Results: {successes} resolved, {warnings} not found, {failures} errors")
    print(f"  Total instruments returned: {len(all_instruments)}")

    if all_instruments and compact:
        print()
        _display_instruments(all_instruments, compact=True)

    return all_instruments


# ─── Export ───────────────────────────────────────────────────────────────────

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
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Exported: {path}")


def _do_export(data, prefix, fmt):
    path = os.path.join(SCRIPT_DIR, f"{prefix}_{_ts()}.{fmt}")
    if fmt == "json":
        _export_json(data, path)
    elif fmt == "csv":
        _export_csv(data, path)


def _prompt_export(data, prefix):
    choice = _prompt("Export? (json/csv/no)", "no")
    if choice in ("json", "csv"):
        _do_export(data, prefix, choice)


# ─── Command Functions ────────────────────────────────────────────────────────

def cmd_map(id_type, id_value, exch_code=None, currency=None, sector=None,
            sec_type=None, as_json=False, export_fmt=None):
    """Map a single identifier to FIGI(s)."""
    id_type = id_type.upper()
    if id_type not in ID_TYPES and id_type not in [v.upper() for v in ID_TYPES]:
        print(f"  Unknown idType: {id_type}")
        print(f"  Run 'enums idType' to see valid types.")
        return

    filters = {}
    if exch_code:
        filters["exchCode"] = exch_code
    if currency:
        filters["currency"] = currency
    if sector:
        filters["marketSecDes"] = sector
    if sec_type:
        filters["securityType2"] = sec_type

    print(f"\n  Mapping {id_type} = {id_value}...")
    result = api_map_single(id_type, id_value, **filters)

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    _display_mapping_result(result, id_type, id_value)

    if export_fmt and "data" in result:
        _do_export(result["data"], f"openfigi_map_{id_type}", export_fmt)

    return result


def cmd_batch(id_values, id_type="TICKER", exch_code=None, currency=None,
              sector=None, as_json=False, export_fmt=None):
    """Batch map multiple identifiers of the same type."""
    id_type = id_type.upper()

    jobs = []
    for val in id_values:
        val = val.strip()
        if not val:
            continue
        job = {"idType": id_type, "idValue": val}
        if exch_code:
            job["exchCode"] = exch_code
        if currency:
            job["currency"] = currency
        if sector:
            job["marketSecDes"] = sector
        jobs.append(job)

    if not jobs:
        print("  No identifiers to map.")
        return

    print(f"\n  Batch mapping {len(jobs)} {id_type}(s)...")
    t0 = time.time()
    results = api_map(jobs)
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s")

    if as_json:
        out = []
        for job, res in zip(jobs, results):
            out.append({"query": job, "result": res})
        print(json.dumps(out, indent=2, default=str))
        return out

    instruments = _display_batch_summary(jobs, results)

    if export_fmt and instruments:
        _do_export(instruments, f"openfigi_batch_{id_type}", export_fmt)

    return instruments


def cmd_batch_file(filepath, id_type="TICKER", exch_code=None, currency=None,
                   sector=None, as_json=False, export_fmt=None):
    """Batch map from a file (one identifier per line, or CSV first column)."""
    if not os.path.exists(filepath):
        print(f"  File not found: {filepath}")
        return

    values = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            val = line.split(",")[0].strip().strip('"').strip("'")
            if val:
                values.append(val)

    if not values:
        print(f"  No identifiers found in {filepath}")
        return

    print(f"  Read {len(values)} identifiers from {filepath}")
    return cmd_batch(values, id_type=id_type, exch_code=exch_code, currency=currency,
                     sector=sector, as_json=as_json, export_fmt=export_fmt)


def cmd_search(query, sector=None, exch_code=None, sec_type=None,
               max_pages=3, as_json=False, export_fmt=None):
    """Search for instruments by keyword."""
    filters = {}
    if sector:
        filters["marketSecDes"] = sector
    if exch_code:
        filters["exchCode"] = exch_code
    if sec_type:
        filters["securityType2"] = sec_type

    print(f"\n  Searching: \"{query}\"...")
    data = api_search(query, max_pages=max_pages, **filters)

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    _display_instruments(data, title=f"Search: \"{query}\"", compact=True)

    if export_fmt and data:
        _do_export(data, f"openfigi_search", export_fmt)

    return data


def cmd_filter(query=None, sector=None, exch_code=None, sec_type=None,
               max_pages=3, as_json=False, export_fmt=None):
    """Filter instruments (alphabetical by FIGI, with total count)."""
    filters = {}
    if sector:
        filters["marketSecDes"] = sector
    if exch_code:
        filters["exchCode"] = exch_code
    if sec_type:
        filters["securityType2"] = sec_type

    print(f"\n  Filtering...")
    data, total = api_filter(query=query, max_pages=max_pages, **filters)

    if as_json:
        print(json.dumps({"data": data, "total": total}, indent=2, default=str))
        return data, total

    if total:
        print(f"  Total matching instruments: {total:,}")
    _display_instruments(data, title="Filter Results", compact=True)

    if export_fmt and data:
        _do_export(data, f"openfigi_filter", export_fmt)

    return data, total


def cmd_enums(key=None, as_json=False):
    """List valid enum values for a mapping property."""
    if key and key not in ENUM_KEYS:
        print(f"  Unknown enum key: {key}")
        print(f"  Valid keys: {', '.join(ENUM_KEYS)}")
        return

    if key:
        print(f"\n  Fetching valid values for '{key}'...")
        values = api_enum_values(key)
        if as_json:
            print(json.dumps(values, indent=2))
            return values
        print(f"\n  {key} ({len(values)} values):")
        for v in sorted(values):
            print(f"    {v}")
        return values
    else:
        print(f"\n  Available enum keys: {', '.join(ENUM_KEYS)}")
        print(f"  Use: openfigi.py enums <KEY>")
        return ENUM_KEYS


def cmd_equity(ticker, exch_code=None, as_json=False, export_fmt=None):
    """Quick equity lookup: ticker -> all exchange listings."""
    filters = {"marketSecDes": "Equity"}
    if exch_code:
        filters["exchCode"] = exch_code

    print(f"\n  Looking up equity: {ticker}...")
    result = api_map_single("TICKER", ticker, **filters)

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    if "data" in result:
        _display_instruments(result["data"],
                             title=f"Equity: {ticker}",
                             compact=len(result["data"]) > 3)
    else:
        _display_mapping_result(result, "TICKER", ticker)

    if export_fmt and "data" in result:
        _do_export(result["data"], f"openfigi_equity_{ticker}", export_fmt)

    return result


def cmd_bond(cusip, as_json=False, export_fmt=None):
    """Bond lookup by CUSIP (or ISIN). Returns all matching instruments."""
    cusip = cusip.strip()

    if len(cusip) == 12 and cusip[:2].isalpha():
        id_type = "ID_ISIN"
    elif len(cusip) == 9:
        id_type = "ID_CUSIP"
    elif len(cusip) == 8:
        id_type = "ID_CUSIP_8_CHR"
    else:
        id_type = "ID_CUSIP"

    print(f"\n  Looking up bond: {id_type} = {cusip}...")
    result = api_map_single(id_type, cusip)

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    if "data" in result:
        _display_instruments(result["data"],
                             title=f"Bond: {cusip}",
                             compact=len(result["data"]) > 3)
    else:
        _display_mapping_result(result, id_type, cusip)

    if export_fmt and "data" in result:
        _do_export(result["data"], f"openfigi_bond_{cusip}", export_fmt)

    return result


def cmd_cross_ref(id_type, id_value, as_json=False, export_fmt=None):
    """Cross-reference: get all identifiers for an instrument.
    Maps the given identifier, then displays the full identifier set
    including FIGI, composite FIGI, share class FIGI, ticker, etc.
    """
    id_type = id_type.upper()
    print(f"\n  Cross-referencing {id_type} = {id_value}...")
    result = api_map_single(id_type, id_value)

    if "data" not in result or not result["data"]:
        if as_json:
            print(json.dumps(result, indent=2, default=str))
        else:
            _display_mapping_result(result, id_type, id_value)
        return result

    instruments = result["data"]

    if as_json:
        print(json.dumps(instruments, indent=2, default=str))
        return instruments

    print(f"\n  Cross-Reference: {id_type} = {id_value}")
    print("  " + "=" * 70)

    for i, inst in enumerate(instruments):
        if i > 0:
            print()
            print("  " + "-" * 70)

        exch = inst.get("exchCode") or "N/A"
        print(f"\n  Listing [{exch}]:")

        ids = [
            ("FIGI",             inst.get("figi")),
            ("Composite FIGI",   inst.get("compositeFIGI")),
            ("Share Class FIGI", inst.get("shareClassFIGI")),
            ("Ticker",           inst.get("ticker")),
            ("Name",             inst.get("name")),
            ("Exchange",         inst.get("exchCode")),
            ("Market Sector",    inst.get("marketSector")),
            ("Security Type",    inst.get("securityType")),
            ("Security Type 2",  inst.get("securityType2")),
            ("Description",      inst.get("securityDescription")),
        ]

        for label, val in ids:
            if val:
                print(f"    {label:<20} {val}")

    print(f"\n  [{len(instruments)} listing(s)]")

    if export_fmt:
        _do_export(instruments, f"openfigi_xref_{id_type}", export_fmt)

    return instruments


def cmd_treasury_cusips(cusips, as_json=False, export_fmt=None):
    """Batch resolve Treasury CUSIPs to FIGIs.
    Useful for linking TreasuryDirect auction data to Bloomberg identifiers.
    """
    jobs = [{"idType": "ID_CUSIP", "idValue": c.strip(), "marketSecDes": "Govt"}
            for c in cusips if c.strip()]

    if not jobs:
        print("  No CUSIPs provided.")
        return

    print(f"\n  Resolving {len(jobs)} Treasury CUSIP(s)...")
    t0 = time.time()
    results = api_map(jobs)
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s")

    if as_json:
        out = []
        for job, res in zip(jobs, results):
            out.append({"cusip": job["idValue"], "result": res})
        print(json.dumps(out, indent=2, default=str))
        return out

    instruments = _display_batch_summary(jobs, results)

    if export_fmt and instruments:
        _do_export(instruments, "openfigi_treasury", export_fmt)

    return instruments


def cmd_id_types(as_json=False):
    """List all supported identifier types with descriptions."""
    if as_json:
        print(json.dumps(ID_TYPES, indent=2))
        return ID_TYPES

    print("\n  Supported Identifier Types")
    print("  " + "=" * 70)
    print(f"  {'ID Type':<35} {'Description'}")
    print(f"  {'-'*35} {'-'*35}")
    for k, v in ID_TYPES.items():
        print(f"  {k:<35} {v}")
    print(f"\n  [{len(ID_TYPES)} types]")
    return ID_TYPES


# ─── Analytical Command Functions ─────────────────────────────────────────────

def _fetch_issuer_bonds(ticker, maturity_start=None, maturity_end=None,
                        sec_type_filter=None, coupon_min=None, coupon_max=None):
    """Fetch an issuer's corporate bond stack via BASE_TICKER.
    For mega-issuers (banks), chunks by 1-year maturity windows to avoid timeouts.
    Returns list of instrument dicts with parsed bond fields attached.
    """
    base_job = {"idType": "BASE_TICKER", "idValue": ticker, "securityType2": "Corp"}
    if sec_type_filter:
        base_job["securityType"] = sec_type_filter
    if coupon_min is not None or coupon_max is not None:
        base_job["coupon"] = [coupon_min, coupon_max]

    if maturity_start and maturity_end:
        start_y = int(maturity_start[:4])
        end_y = int(maturity_end[:4])
        span = end_y - start_y

        if span <= 1:
            base_job["maturity"] = [maturity_start, maturity_end]
            result = api_map([base_job])
            bonds = result[0].get("data", []) if result else []
        else:
            bonds = []
            for y in range(start_y, end_y + 1):
                chunk_start = f"{y}-01-01"
                chunk_end = f"{y}-12-31"
                job = dict(base_job)
                job["maturity"] = [chunk_start, chunk_end]
                print(f"  Fetching {y}...")
                result = api_map([job])
                if result and "data" in result[0]:
                    bonds.extend(result[0]["data"])
                elif result and "error" in result[0]:
                    if "15,000" in result[0].get("error", ""):
                        print(f"  [{y}: too many results, try narrower range]")
    else:
        result = api_map([base_job])
        if result and "error" in result[0] and "15,000" in result[0].get("error", ""):
            print("  [too many bonds, chunking by year 2020-2065...]")
            bonds = []
            for y in range(2020, 2066):
                job = dict(base_job)
                job["maturity"] = [f"{y}-01-01", f"{y}-12-31"]
                print(f"  Fetching {y}...")
                result = api_map([job])
                if result and "data" in result[0]:
                    bonds.extend(result[0]["data"])
        else:
            bonds = result[0].get("data", []) if result else []

    for b in bonds:
        b["_parsed"] = _parse_bond_ticker(b.get("ticker"))

    seen = set()
    deduped = []
    for b in bonds:
        figi = b.get("figi")
        if figi and figi not in seen:
            seen.add(figi)
            deduped.append(b)

    deduped.sort(key=lambda b: b["_parsed"].get("maturity") or "9999")
    return deduped


def _display_bond_table(bonds, title=None):
    """Display bonds in a structured table with parsed coupon/maturity."""
    if not bonds:
        print("  No bonds found.")
        return

    if title:
        print(f"\n  {title}")
        print("  " + "=" * 95)

    hdr = f"  {'Ticker':<30} {'Coupon':>7} {'Maturity':>12} {'Type':<18} {'Exch':<8} {'Suffix'}"
    sep = f"  {'-'*30} {'-'*7} {'-'*12} {'-'*18} {'-'*8} {'-'*10}"
    print(hdr)
    print(sep)

    current_type = None
    for b in bonds:
        p = b.get("_parsed") or _parse_bond_ticker(b.get("ticker"))
        stype = (b.get("securityType") or "")[:18]

        if stype != current_type:
            current_type = stype
            if bonds.index(b) > 0:
                print()

        ticker = (b.get("ticker") or "")[:30]
        cpn = _fmt_coupon(p)
        mat = p.get("maturity") or ""
        exch = (b.get("exchCode") or "")[:8]
        suffix = (p.get("suffix") or "")[:10]
        print(f"  {ticker:<30} {cpn:>7} {mat:>12} {stype:<18} {exch:<8} {suffix}")

    print(f"\n  [{len(bonds)} bond(s)]")


def cmd_issuer_bonds(ticker, maturity_start=None, maturity_end=None,
                     sec_type_filter=None, as_json=False, export_fmt=None):
    """Full bond stack for an issuer."""
    ticker = ticker.upper()
    mat_desc = ""
    if maturity_start and maturity_end:
        mat_desc = f" maturing {maturity_start[:4]}-{maturity_end[:4]}"
    elif maturity_start:
        mat_desc = f" maturing from {maturity_start[:4]}"

    print(f"\n  Fetching {ticker} corporate bonds{mat_desc}...")
    t0 = time.time()
    bonds = _fetch_issuer_bonds(ticker, maturity_start, maturity_end, sec_type_filter)
    elapsed = time.time() - t0
    print(f"  Got {len(bonds)} bonds in {elapsed:.1f}s")

    if not bonds:
        return []

    if as_json:
        out = []
        for b in bonds:
            p = b.get("_parsed", {})
            out.append({**{k: v for k, v in b.items() if k != "_parsed"},
                        "parsed_coupon": p.get("coupon"),
                        "parsed_rate_type": p.get("rate_type"),
                        "parsed_maturity": p.get("maturity"),
                        "parsed_suffix": p.get("suffix")})
        print(json.dumps(out, indent=2, default=str))
        return out

    # Summary stats
    coupons = [b["_parsed"]["coupon"] for b in bonds if b["_parsed"]["coupon"] is not None and b["_parsed"]["coupon"] > 0]
    types = {}
    for b in bonds:
        t = b.get("securityType") or "Unknown"
        types[t] = types.get(t, 0) + 1

    print(f"\n  {ticker} Bond Stack Summary")
    print("  " + "-" * 50)
    print(f"  Total bonds:    {len(bonds)}")
    if coupons:
        print(f"  Coupon range:   {min(coupons):.3f} - {max(coupons):.3f}")
        print(f"  Avg coupon:     {sum(coupons)/len(coupons):.3f}")
    print(f"  By type:")
    for t, cnt in sorted(types.items(), key=lambda x: -x[1]):
        print(f"    {t:<20} {cnt}")

    _display_bond_table(bonds, title=f"{ticker} Corporate Bonds")

    if export_fmt:
        rows = []
        for b in bonds:
            p = b.get("_parsed", {})
            rows.append({
                "ticker": b.get("ticker"), "figi": b.get("figi"),
                "name": b.get("name"), "securityType": b.get("securityType"),
                "exchCode": b.get("exchCode"), "coupon": p.get("coupon"),
                "rate_type": p.get("rate_type"), "maturity": p.get("maturity"),
                "suffix": p.get("suffix"),
            })
        _do_export(rows, f"openfigi_bonds_{ticker}", export_fmt)

    return bonds


def cmd_capital_structure(ticker, as_json=False, export_fmt=None):
    """One-shot capital structure map: equity + bonds + pfds + loans."""
    ticker = ticker.upper()
    print(f"\n  Mapping capital structure for {ticker}...")

    structure = {"ticker": ticker, "equity": [], "bonds": [], "preferred": [], "loans": []}

    # Equity
    print("  [1/4] Equity listings...")
    eq_result = api_map_single("TICKER", ticker, marketSecDes="Equity")
    if "data" in eq_result:
        structure["equity"] = eq_result["data"]

    # Corp bonds (with maturity chunking for safety)
    print("  [2/4] Corporate bonds...")
    bonds = _fetch_issuer_bonds(ticker)
    structure["bonds"] = bonds

    # Preferred
    issuer_name = None
    if structure["equity"]:
        issuer_name = structure["equity"][0].get("name")
    if issuer_name:
        print(f"  [3/4] Preferred stock (searching '{issuer_name}')...")
        pfds = api_search(issuer_name, max_pages=2, marketSecDes="Pfd")
        structure["preferred"] = pfds
    else:
        print(f"  [3/4] Preferred stock (searching '{ticker}')...")
        pfds = api_search(ticker, max_pages=2, marketSecDes="Pfd")
        structure["preferred"] = pfds

    # Loans
    search_name = issuer_name or ticker
    print(f"  [4/4] Loan facilities (searching '{search_name}')...")
    terms = api_search(search_name, max_pages=1, securityType="TERM")
    revs = api_search(search_name, max_pages=1, securityType="REV")
    structure["loans"] = terms + revs

    if as_json:
        out = {
            "ticker": ticker,
            "equity_count": len(structure["equity"]),
            "bond_count": len(structure["bonds"]),
            "preferred_count": len(structure["preferred"]),
            "loan_count": len(structure["loans"]),
            "equity": structure["equity"][:3],
            "bonds_sample": [b.get("ticker") for b in structure["bonds"][:20]],
            "preferred_sample": [p.get("ticker") for p in structure["preferred"][:10]],
            "loans_sample": [l.get("ticker") for l in structure["loans"][:10]],
        }
        print(json.dumps(out, indent=2, default=str))
        return out

    # Display
    eq = structure["equity"]
    bonds = structure["bonds"]
    pfds = structure["preferred"]
    loans = structure["loans"]

    name = eq[0].get("name") if eq else ticker
    print(f"\n  Capital Structure: {name} ({ticker})")
    print("  " + "=" * 70)

    # Equity summary
    us_listings = [e for e in eq if e.get("exchCode") in ("US", "UN", "UA", "UB")]
    print(f"\n  EQUITY")
    print(f"    Listings: {len(eq)} total ({len(us_listings)} US)")
    if eq:
        print(f"    Share Class FIGI: {eq[0].get('shareClassFIGI', 'N/A')}")
        print(f"    Composite FIGI:   {eq[0].get('compositeFIGI', 'N/A')}")

    # Bond summary
    print(f"\n  CORPORATE DEBT")
    print(f"    Bonds: {len(bonds)}")
    if bonds:
        coupons = [b["_parsed"]["coupon"] for b in bonds
                   if b.get("_parsed", {}).get("coupon") is not None and b["_parsed"]["coupon"] > 0]
        types = {}
        for b in bonds:
            t = b.get("securityType") or "?"
            types[t] = types.get(t, 0) + 1
        if coupons:
            print(f"    Coupon range: {min(coupons):.3f} - {max(coupons):.3f}")
        for t, cnt in sorted(types.items(), key=lambda x: -x[1]):
            print(f"      {t:<20} {cnt}")

    # Preferred
    print(f"\n  PREFERRED / HYBRID")
    print(f"    Instruments: {len(pfds)}")
    for p in pfds[:5]:
        print(f"      {(p.get('ticker') or '?'):<30} {(p.get('securityType') or '?')}")

    # Loans
    print(f"\n  LOAN FACILITIES")
    print(f"    Facilities: {len(loans)}")
    for l in loans[:5]:
        print(f"      {(l.get('ticker') or '?'):<30} {(l.get('securityType') or '?')}")

    print()

    if export_fmt:
        rows = [{"layer": "equity", "ticker": e.get("ticker"), "figi": e.get("figi"),
                 "type": e.get("securityType"), "exchange": e.get("exchCode")} for e in eq[:10]]
        for b in bonds:
            p = b.get("_parsed", {})
            rows.append({"layer": "bond", "ticker": b.get("ticker"), "figi": b.get("figi"),
                         "type": b.get("securityType"), "coupon": p.get("coupon"),
                         "maturity": p.get("maturity"), "exchange": b.get("exchCode")})
        for p in pfds:
            rows.append({"layer": "preferred", "ticker": p.get("ticker"), "figi": p.get("figi"),
                         "type": p.get("securityType")})
        for l in loans:
            rows.append({"layer": "loan", "ticker": l.get("ticker"), "figi": l.get("figi"),
                         "type": l.get("securityType")})
        _do_export(rows, f"openfigi_capstruct_{ticker}", export_fmt)

    return structure


def cmd_maturity_profile(ticker, start_year=None, end_year=None,
                         as_json=False, export_fmt=None):
    """Bond maturity wall: bucketed by year with coupon stats."""
    ticker = ticker.upper()
    start_year = start_year or datetime.now().year
    end_year = end_year or start_year + 15

    mat_start = f"{start_year}-01-01"
    mat_end = f"{end_year}-12-31"
    print(f"\n  Building maturity profile for {ticker} ({start_year}-{end_year})...")

    bonds = _fetch_issuer_bonds(ticker, mat_start, mat_end)
    if not bonds:
        print("  No bonds found in range.")
        return {}

    # Bucket by year
    buckets = {}
    for b in bonds:
        year = _parse_maturity_year(b.get("_parsed", {}))
        if year:
            buckets.setdefault(year, []).append(b)

    if as_json:
        out = {}
        for y in sorted(buckets):
            bs = buckets[y]
            coupons = [b["_parsed"]["coupon"] for b in bs
                       if b.get("_parsed", {}).get("coupon") is not None and b["_parsed"]["coupon"] > 0]
            out[y] = {
                "count": len(bs),
                "avg_coupon": round(sum(coupons) / len(coupons), 3) if coupons else None,
                "min_coupon": round(min(coupons), 3) if coupons else None,
                "max_coupon": round(max(coupons), 3) if coupons else None,
                "bonds": [b.get("ticker") for b in bs],
            }
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  {ticker} Maturity Profile ({start_year}-{end_year})")
    print("  " + "=" * 70)
    print(f"  {'Year':<6} {'Count':>5} {'Avg Cpn':>8} {'Range':>14} {'Bar'}")
    print(f"  {'-'*6} {'-'*5} {'-'*8} {'-'*14} {'-'*25}")

    max_count = max(len(v) for v in buckets.values()) if buckets else 1

    for y in range(start_year, end_year + 1):
        bs = buckets.get(y, [])
        cnt = len(bs)
        coupons = [b["_parsed"]["coupon"] for b in bs
                   if b.get("_parsed", {}).get("coupon") is not None and b["_parsed"]["coupon"] > 0]
        avg = f"{sum(coupons)/len(coupons):.3f}" if coupons else "  --  "
        rng = f"{min(coupons):.1f}-{max(coupons):.1f}" if coupons else "  --  "
        bar_len = int(cnt / max_count * 25) if max_count > 0 else 0
        bar = "\u2588" * bar_len
        print(f"  {y:<6} {cnt:>5} {avg:>8} {rng:>14} {bar}")

    total = sum(len(v) for v in buckets.values())
    all_coupons = []
    for bs in buckets.values():
        for b in bs:
            c = b.get("_parsed", {}).get("coupon")
            if c is not None and c > 0:
                all_coupons.append(c)

    print(f"\n  Total: {total} bonds")
    if all_coupons:
        print(f"  Portfolio avg coupon: {sum(all_coupons)/len(all_coupons):.3f}")

    if export_fmt:
        rows = []
        for y in sorted(buckets):
            for b in buckets[y]:
                p = b.get("_parsed", {})
                rows.append({"year": y, "ticker": b.get("ticker"), "coupon": p.get("coupon"),
                             "maturity": p.get("maturity"), "type": b.get("securityType"),
                             "figi": b.get("figi")})
        _do_export(rows, f"openfigi_maturity_{ticker}", export_fmt)

    return buckets


def cmd_compare_issuers(tickers, as_json=False, export_fmt=None):
    """Side-by-side bond stack comparison across issuers."""
    tickers = [t.upper() for t in tickers]
    print(f"\n  Comparing {len(tickers)} issuers: {', '.join(tickers)}...")

    jobs = [{"idType": "BASE_TICKER", "idValue": t, "securityType2": "Corp"} for t in tickers]
    results = api_map(jobs)

    summaries = []
    for ticker, result in zip(tickers, results):
        if "data" in result:
            bonds = result["data"]
            for b in bonds:
                b["_parsed"] = _parse_bond_ticker(b.get("ticker"))
            coupons = [b["_parsed"]["coupon"] for b in bonds
                       if b["_parsed"].get("coupon") is not None and b["_parsed"]["coupon"] > 0]
            maturities = [b["_parsed"]["maturity"] for b in bonds if b["_parsed"].get("maturity")]
            types = {}
            for b in bonds:
                t = b.get("securityType") or "?"
                types[t] = types.get(t, 0) + 1

            summaries.append({
                "ticker": ticker,
                "name": bonds[0].get("name", "") if bonds else "",
                "count": len(bonds),
                "avg_coupon": round(sum(coupons) / len(coupons), 3) if coupons else None,
                "min_coupon": round(min(coupons), 3) if coupons else None,
                "max_coupon": round(max(coupons), 3) if coupons else None,
                "earliest": min(maturities) if maturities else None,
                "latest": max(maturities) if maturities else None,
                "types": types,
            })
        elif "error" in result and "15,000" in result.get("error", ""):
            summaries.append({"ticker": ticker, "count": -1, "note": "too many (>15k), use --maturity"})
        else:
            summaries.append({"ticker": ticker, "count": 0})

    if as_json:
        print(json.dumps(summaries, indent=2, default=str))
        return summaries

    print(f"\n  Issuer Bond Stack Comparison")
    print("  " + "=" * 90)
    print(f"  {'Ticker':<8} {'Name':<25} {'Bonds':>6} {'Avg Cpn':>8} {'Cpn Range':>12} {'Mat Range':>22}")
    print(f"  {'-'*8} {'-'*25} {'-'*6} {'-'*8} {'-'*12} {'-'*22}")

    for s in sorted(summaries, key=lambda x: -(x.get("count") or 0)):
        ticker = s["ticker"]
        name = s.get("name", "")[:25]
        cnt = s.get("count", 0)
        if cnt == -1:
            print(f"  {ticker:<8} {name:<25} {'>15k':>6} {'--':>8} {'--':>12} {'use --maturity':>22}")
            continue
        avg = f"{s['avg_coupon']:.3f}" if s.get("avg_coupon") else "--"
        rng = f"{s['min_coupon']:.1f}-{s['max_coupon']:.1f}" if s.get("min_coupon") else "--"
        mat = ""
        if s.get("earliest") and s.get("latest"):
            mat = f"{s['earliest'][:4]}-{s['latest'][:4]}"
        print(f"  {ticker:<8} {name:<25} {cnt:>6} {avg:>8} {rng:>12} {mat:>22}")

    print()

    if export_fmt:
        _do_export(summaries, "openfigi_compare", export_fmt)

    return summaries


def cmd_treasury_universe(maturity_start=None, maturity_end=None,
                          instrument_type="all", as_json=False, export_fmt=None):
    """Enumerate outstanding Treasury securities by maturity range."""
    start_y = int(maturity_start[:4]) if maturity_start else datetime.now().year
    end_y = int(maturity_end[:4]) if maturity_end else start_y + 10
    mat_start = maturity_start or f"{start_y}-01-01"
    mat_end = maturity_end or f"{end_y}-12-31"

    type_map = {
        "notes": [("T", "Note")],
        "bonds": [("T", "Bond")],
        "bills": [("T", "Bill")],
        "all": [("T", "Note"), ("T", "Bond")],
    }
    queries = type_map.get(instrument_type, type_map["all"])

    print(f"\n  Fetching Treasury securities ({mat_start[:4]}-{mat_end[:4]}, type={instrument_type})...")

    all_bonds = []
    for base_ticker, sec_type2 in queries:
        for y in range(start_y, end_y + 1):
            cs = f"{y}-01-01"
            ce = f"{y}-12-31"
            job = {"idType": "BASE_TICKER", "idValue": base_ticker,
                   "securityType2": sec_type2, "marketSecDes": "Govt",
                   "maturity": [cs, ce]}
            result = api_map([job])
            if result and "data" in result[0]:
                for b in result[0]["data"]:
                    b["_parsed"] = _parse_bond_ticker(b.get("ticker"))
                    b["_ust_type"] = sec_type2
                all_bonds.extend(result[0]["data"])
            print(f"  {sec_type2}s {y}: {len(result[0].get('data', [])) if result else 0}")

    seen = set()
    deduped = []
    for b in all_bonds:
        figi = b.get("figi")
        if figi and figi not in seen:
            seen.add(figi)
            deduped.append(b)
    deduped.sort(key=lambda b: b.get("_parsed", {}).get("maturity") or "9999")

    if as_json:
        out = []
        for b in deduped:
            p = b.get("_parsed", {})
            out.append({"ticker": b.get("ticker"), "figi": b.get("figi"),
                        "name": b.get("name"), "type": b.get("_ust_type"),
                        "coupon": p.get("coupon"), "maturity": p.get("maturity")})
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  Treasury Universe ({mat_start[:4]}-{mat_end[:4]})")
    print("  " + "=" * 80)
    print(f"  {'Ticker':<25} {'Coupon':>7} {'Maturity':>12} {'Type':<6} {'Name':<30}")
    print(f"  {'-'*25} {'-'*7} {'-'*12} {'-'*6} {'-'*30}")

    for b in deduped:
        p = b.get("_parsed", {})
        ticker = (b.get("ticker") or "")[:25]
        cpn = _fmt_coupon(p)
        mat = p.get("maturity") or ""
        ust_type = b.get("_ust_type", "")[:6]
        name = (b.get("name") or "")[:30]
        print(f"  {ticker:<25} {cpn:>7} {mat:>12} {ust_type:<6} {name}")

    print(f"\n  [{len(deduped)} security(ies)]")

    if export_fmt:
        rows = []
        for b in deduped:
            p = b.get("_parsed", {})
            rows.append({"ticker": b.get("ticker"), "figi": b.get("figi"),
                         "coupon": p.get("coupon"), "maturity": p.get("maturity"),
                         "type": b.get("_ust_type"), "name": b.get("name")})
        _do_export(rows, "openfigi_ust_universe", export_fmt)

    return deduped


def cmd_sector_scan(list_name=None, tickers=None, as_json=False, export_fmt=None):
    """Scan a list of tickers for bond universe size."""
    if list_name:
        list_name = list_name.lower()
        if list_name not in ISSUER_LISTS:
            print(f"  Unknown list: {list_name}")
            print(f"  Available: {', '.join(ISSUER_LISTS.keys())}")
            return
        tickers = ISSUER_LISTS[list_name]
    elif not tickers:
        print("  Provide --list or ticker(s).")
        return

    label = list_name.upper() if list_name else "Custom"
    return cmd_compare_issuers(tickers, as_json=as_json, export_fmt=export_fmt)


def cmd_preferred(ticker, as_json=False, export_fmt=None):
    """Preferred stock / hybrid capital universe for an issuer."""
    ticker = ticker.upper()

    # Try to get issuer name from equity lookup first
    eq = api_map_single("TICKER", ticker, marketSecDes="Equity", exchCode="US")
    issuer_name = None
    if "data" in eq and eq["data"]:
        issuer_name = eq["data"][0].get("name")

    search_term = issuer_name or ticker
    print(f"\n  Searching preferred stock for '{search_term}'...")
    pfds = api_search(search_term, max_pages=3, marketSecDes="Pfd")

    if as_json:
        print(json.dumps(pfds, indent=2, default=str))
        return pfds

    if not pfds:
        print("  No preferred instruments found.")
        return []

    print(f"\n  Preferred / Hybrid Capital: {ticker}")
    print("  " + "=" * 80)
    print(f"  {'Ticker':<30} {'Type':<20} {'Name':<30}")
    print(f"  {'-'*30} {'-'*20} {'-'*30}")

    for p in pfds:
        ticker_str = (p.get("ticker") or "")[:30]
        stype = (p.get("securityType") or "")[:20]
        name = (p.get("name") or "")[:30]
        print(f"  {ticker_str:<30} {stype:<20} {name}")

    print(f"\n  [{len(pfds)} instrument(s)]")

    if export_fmt:
        _do_export(pfds, f"openfigi_pfd_{ticker}", export_fmt)

    return pfds


def cmd_loans(ticker, as_json=False, export_fmt=None):
    """Loan facility search for an issuer (term loans, revolvers)."""
    ticker = ticker.upper()

    eq = api_map_single("TICKER", ticker, marketSecDes="Equity", exchCode="US")
    issuer_name = None
    if "data" in eq and eq["data"]:
        issuer_name = eq["data"][0].get("name")

    search_term = issuer_name or ticker
    print(f"\n  Searching loan facilities for '{search_term}'...")

    terms = api_search(search_term, max_pages=2, securityType="TERM")
    revs = api_search(search_term, max_pages=2, securityType="REV")
    ddts = api_search(search_term, max_pages=1, securityType="DELAY-DRAW TERM")

    all_loans = terms + revs + ddts

    if as_json:
        print(json.dumps(all_loans, indent=2, default=str))
        return all_loans

    if not all_loans:
        print("  No loan facilities found.")
        return []

    print(f"\n  Loan Facilities: {ticker}")
    print("  " + "=" * 80)

    for label, group in [("TERM LOANS", terms), ("REVOLVERS", revs), ("DELAY-DRAW", ddts)]:
        if group:
            print(f"\n  {label}")
            print(f"  {'Ticker':<35} {'Type':<25} {'Name':<25}")
            print(f"  {'-'*35} {'-'*25} {'-'*25}")
            for l in group:
                t = (l.get("ticker") or "")[:35]
                stype = (l.get("securityType") or "")[:25]
                name = (l.get("name") or "")[:25]
                print(f"  {t:<35} {stype:<25} {name}")

    print(f"\n  [{len(all_loans)} facility(ies)]")

    if export_fmt:
        _do_export(all_loans, f"openfigi_loans_{ticker}", export_fmt)

    return all_loans


# ─── Portfolio Auto-Detection ──────────────────────────────────────────────────

def cmd_portfolio(filepath=None, identifiers=None, as_json=False, export_fmt=None):
    """Auto-detect and batch resolve mixed identifiers (tickers, CUSIPs, ISINs, SEDOLs, FIGIs)."""
    values = []
    if filepath:
        if not os.path.exists(filepath):
            print(f"  File not found: {filepath}")
            return
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                val = line.split(",")[0].strip().strip('"').strip("'")
                if val:
                    values.append(val)
        print(f"  Read {len(values)} identifiers from {filepath}")
    elif identifiers:
        values = [v.strip() for v in identifiers if v.strip()]

    if not values:
        print("  No identifiers provided.")
        return

    by_type = {}
    for val in values:
        id_type = _detect_id_type(val)
        by_type.setdefault(id_type, []).append(val)

    print(f"\n  Auto-detected identifier types:")
    for t, vs in sorted(by_type.items()):
        print(f"    {t:<25} {len(vs)} identifier(s)")

    jobs = []
    for val in values:
        id_type = _detect_id_type(val)
        jobs.append({"idType": id_type, "idValue": val})

    print(f"\n  Resolving {len(jobs)} identifier(s)...")
    t0 = time.time()
    results = api_map(jobs)
    elapsed = time.time() - t0
    print(f"  Completed in {elapsed:.1f}s")

    if as_json:
        out = []
        for job, res in zip(jobs, results):
            out.append({"query_id": job["idValue"], "query_type": job["idType"],
                        "result": res})
        print(json.dumps(out, indent=2, default=str))
        return out

    instruments = _display_batch_summary(jobs, results)

    if export_fmt and instruments:
        _do_export(instruments, "openfigi_portfolio", export_fmt)

    return instruments


# ─── FIGI Hierarchy ────────────────────────────────────────────────────────────

def cmd_figi_lookup(figi, as_json=False, export_fmt=None):
    """Reverse FIGI lookup + hierarchy walk.
    Given any FIGI (listing, composite, or share class), resolves the full hierarchy.
    """
    figi = figi.strip()
    print(f"\n  Looking up FIGI: {figi}...")

    hierarchy = {"query_figi": figi, "listing": None, "composite": None,
                 "share_class": None, "all_listings": []}

    result = api_map_single("ID_BB_GLOBAL", figi)
    if "data" in result and result["data"]:
        inst = result["data"][0]
        hierarchy["listing"] = inst
        comp_figi = inst.get("compositeFIGI")
        sc_figi = inst.get("shareClassFIGI")

        if comp_figi:
            hierarchy["composite"] = comp_figi
            print(f"  Walking composite FIGI: {comp_figi}...")
            comp_result = api_map_single("COMPOSITE_ID_BB_GLOBAL", comp_figi)
            if "data" in comp_result:
                hierarchy["all_listings"] = comp_result["data"]

        if sc_figi:
            hierarchy["share_class"] = sc_figi
    else:
        result = api_map_single("COMPOSITE_ID_BB_GLOBAL", figi)
        if "data" in result and result["data"]:
            hierarchy["composite"] = figi
            hierarchy["all_listings"] = result["data"]
            if result["data"]:
                hierarchy["share_class"] = result["data"][0].get("shareClassFIGI")
        else:
            result = api_map_single("ID_BB_GLOBAL_SHARE_CLASS_LEVEL", figi)
            if "data" in result and result["data"]:
                hierarchy["share_class"] = figi
                hierarchy["all_listings"] = result["data"]
                if result["data"]:
                    hierarchy["composite"] = result["data"][0].get("compositeFIGI")

    listings = hierarchy["all_listings"]

    if as_json:
        out = {"query": figi, "share_class_figi": hierarchy["share_class"],
               "composite_figi": hierarchy["composite"],
               "listing_count": len(listings), "listings": listings}
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  FIGI Hierarchy: {figi}")
    print("  " + "=" * 70)

    if hierarchy["share_class"]:
        print(f"\n  Share Class FIGI: {hierarchy['share_class']}")
    if hierarchy["composite"]:
        print(f"  Composite FIGI:   {hierarchy['composite']}")

    if hierarchy["listing"]:
        inst = hierarchy["listing"]
        print(f"\n  Primary Instrument:")
        print(f"    Name:     {inst.get('name', 'N/A')}")
        print(f"    Ticker:   {inst.get('ticker', 'N/A')}")
        print(f"    Sector:   {inst.get('marketSector', 'N/A')}")
        print(f"    Type:     {inst.get('securityType', 'N/A')}")

    if listings:
        by_exch = {}
        for l in listings:
            exch = l.get("exchCode") or "N/A"
            by_exch.setdefault(exch, []).append(l)

        print(f"\n  Exchange Listings ({len(listings)} total, {len(by_exch)} exchanges):")
        print(f"  {'Exchange':<8} {'Ticker':<12} {'FIGI':<15} {'Type':<20} {'Name'}")
        print(f"  {'-'*8} {'-'*12} {'-'*15} {'-'*20} {'-'*25}")

        for exch in sorted(by_exch):
            for l in by_exch[exch]:
                ticker = (l.get("ticker") or "")[:12]
                lfigi = l.get("figi") or ""
                stype = (l.get("securityType") or "")[:20]
                name = (l.get("name") or "")[:25]
                print(f"  {exch:<8} {ticker:<12} {lfigi:<15} {stype:<20} {name}")

    print()

    if export_fmt and listings:
        _do_export(listings, f"openfigi_hierarchy_{figi}", export_fmt)

    return hierarchy


# ─── Global Listings ───────────────────────────────────────────────────────────

def cmd_global_listings(ticker, as_json=False, export_fmt=None):
    """All worldwide exchange listings for a ticker, grouped by composite FIGI."""
    ticker = ticker.upper()
    print(f"\n  Fetching all global listings for {ticker}...")

    result = api_map_single("TICKER", ticker)

    if "data" not in result or not result["data"]:
        print(f"  No results for {ticker}.")
        return

    listings = result["data"]

    by_composite = {}
    for l in listings:
        comp = l.get("compositeFIGI") or "Unknown"
        by_composite.setdefault(comp, []).append(l)

    if as_json:
        out = {"ticker": ticker, "total_listings": len(listings),
               "composites": len(by_composite),
               "share_class_figi": listings[0].get("shareClassFIGI") if listings else None,
               "listings": listings}
        print(json.dumps(out, indent=2, default=str))
        return out

    name = listings[0].get("name") or ticker
    sc_figi = listings[0].get("shareClassFIGI") or "N/A"

    print(f"\n  Global Listings: {name} ({ticker})")
    print("  " + "=" * 80)
    print(f"  Share Class FIGI: {sc_figi}")
    print(f"  Total listings: {len(listings)} across {len(by_composite)} composite(s)")

    for comp_figi in sorted(by_composite):
        group = by_composite[comp_figi]
        print(f"\n  Composite: {comp_figi}")
        print(f"  {'Exchange':<8} {'Ticker':<12} {'FIGI':<15} {'Type':<20} {'Sector':<8}")
        print(f"  {'-'*8} {'-'*12} {'-'*15} {'-'*20} {'-'*8}")
        for l in group:
            exch = (l.get("exchCode") or "")[:8]
            t = (l.get("ticker") or "")[:12]
            f = l.get("figi") or ""
            stype = (l.get("securityType") or "")[:20]
            sector = (l.get("marketSector") or "")[:8]
            print(f"  {exch:<8} {t:<12} {f:<15} {stype:<20} {sector:<8}")

    print()

    if export_fmt:
        _do_export(listings, f"openfigi_listings_{ticker}", export_fmt)

    return listings


# ─── Options Chain ─────────────────────────────────────────────────────────────

def cmd_options_chain(ticker, expiry_start=None, expiry_end=None,
                      strike_min=None, strike_max=None,
                      exch_code=None, as_json=False, export_fmt=None):
    """Options chain for a ticker via search/filter API.
    Uses keyword search with securityType='Equity Option'.
    Strike/expiry filters applied as post-processing on ticker string parsing.
    """
    ticker = ticker.upper()

    filters = {"securityType": "Equity Option"}
    if exch_code:
        filters["exchCode"] = exch_code

    print(f"\n  Fetching options for {ticker}...")
    data, total = api_filter(query=ticker, max_pages=10, **filters)

    if not data:
        data = api_search(ticker, max_pages=10, **filters)

    if not data:
        print("  No options found.")
        return []

    # Post-filter by expiry/strike parsed from ticker description
    if expiry_start or expiry_end or strike_min is not None or strike_max is not None:
        filtered = []
        for o in data:
            desc = o.get("securityDescription") or o.get("ticker") or ""
            m = _DATE_RE.search(desc)
            if m and (expiry_start or expiry_end):
                try:
                    dp = m.group(1).split("/")
                    month, day = int(dp[0]), int(dp[1])
                    year = int(dp[2])
                    if year < 100:
                        year += 2000 if year < 70 else 1900
                    opt_date = f"{year:04d}-{month:02d}-{day:02d}"
                    if expiry_start and opt_date < expiry_start:
                        continue
                    if expiry_end and opt_date > expiry_end:
                        continue
                except (ValueError, IndexError):
                    pass
            # Strike parsing from description (e.g. "C150" or "P200")
            if strike_min is not None or strike_max is not None:
                import re as _re
                sm = _re.search(r'[CP](\d+\.?\d*)', desc)
                if sm:
                    try:
                        strike = float(sm.group(1))
                        if strike_min is not None and strike < strike_min:
                            continue
                        if strike_max is not None and strike > strike_max:
                            continue
                    except ValueError:
                        pass
            filtered.append(o)
        data = filtered

    seen = set()
    deduped = []
    for o in data:
        figi = o.get("figi")
        if figi and figi not in seen:
            seen.add(figi)
            deduped.append(o)

    deduped.sort(key=lambda o: (o.get("securityType") or "", o.get("ticker") or ""))

    if not deduped:
        print("  No options found matching filters.")
        return []

    if as_json:
        print(json.dumps(deduped, indent=2, default=str))
        return deduped

    calls = [o for o in deduped if "Call" in (o.get("name") or o.get("securityType") or "")]
    puts = [o for o in deduped if "Put" in (o.get("name") or o.get("securityType") or "")]
    other = [o for o in deduped if o not in calls and o not in puts]

    total_label = f" (of {total:,} total)" if total else ""
    print(f"\n  Options Chain: {ticker}")
    print("  " + "=" * 85)
    print(f"  Retrieved: {len(deduped)}{total_label}")
    print(f"  Calls: {len(calls)}, Puts: {len(puts)}, Other: {len(other)}")

    _display_instruments(deduped[:100], compact=True)
    if len(deduped) > 100:
        print(f"\n  [showing 100 of {len(deduped)} -- use --export for full set]")

    if export_fmt:
        _do_export(deduped, f"openfigi_options_{ticker}", export_fmt)

    return deduped


# ─── Futures ───────────────────────────────────────────────────────────────────

def cmd_futures(ticker, expiry_start=None, expiry_end=None,
                as_json=False, export_fmt=None):
    """Futures term structure via search API.
    Common tickers: ES (E-mini S&P), CL (Crude), GC (Gold), ZN (10Y Note), TY (Treasury).
    """
    ticker = ticker.upper()

    print(f"\n  Fetching futures for {ticker}...")
    data = api_search(ticker, max_pages=10, securityType2="Future")

    if not data:
        data, _ = api_filter(query=ticker, max_pages=10, securityType2="Future")

    if not data:
        print("  No futures found.")
        return []

    seen = set()
    deduped = []
    for f in data:
        figi = f.get("figi")
        if figi and figi not in seen:
            seen.add(figi)
            deduped.append(f)

    deduped.sort(key=lambda f: f.get("ticker") or "")

    if not deduped:
        print("  No futures found.")
        return []

    if as_json:
        print(json.dumps(deduped, indent=2, default=str))
        return deduped

    print(f"\n  Futures: {ticker}")
    print("  " + "=" * 80)
    _display_instruments(deduped, compact=True)

    if export_fmt:
        _do_export(deduped, f"openfigi_futures_{ticker}", export_fmt)

    return deduped


# ─── Derivatives ───────────────────────────────────────────────────────────────

def cmd_derivatives(ticker, expiry_start=None, expiry_end=None,
                    as_json=False, export_fmt=None):
    """All derivatives (options + futures) for a ticker via search API."""
    ticker = ticker.upper()

    print(f"\n  Fetching all derivatives for {ticker}...")

    print("  [1/2] Options...")
    options, opt_total = api_filter(query=ticker, max_pages=3, securityType="Equity Option")
    if not options:
        options = api_search(ticker, max_pages=3, securityType="Equity Option")
        opt_total = len(options)

    print("  [2/2] Futures...")
    futures_list = api_search(ticker, max_pages=5, securityType2="Future")

    calls = [o for o in options if "Call" in (o.get("name") or o.get("securityType") or "")]
    puts = [o for o in options if "Put" in (o.get("name") or o.get("securityType") or "")]

    if as_json:
        out = {"ticker": ticker,
               "options_retrieved": len(options),
               "options_total": opt_total,
               "calls": len(calls), "puts": len(puts),
               "futures_count": len(futures_list),
               "options_sample": options[:20], "futures": futures_list}
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  Derivatives: {ticker}")
    print("  " + "=" * 70)
    opt_label = f"{len(options)} retrieved" + (f" (of {opt_total:,} total)" if opt_total > len(options) else "")
    print(f"\n  OPTIONS: {opt_label}")
    print(f"    Calls: {len(calls)}")
    print(f"    Puts:  {len(puts)}")

    print(f"\n  FUTURES: {len(futures_list)} contract(s)")
    if futures_list:
        _display_instruments(futures_list, compact=True)

    if options:
        print(f"\n  Options sample (first 20):")
        _display_instruments(options[:20], compact=True)

    print()

    if export_fmt:
        all_instruments = []
        for o in options:
            o["_derivative_type"] = "option"
            all_instruments.append(o)
        for f in futures_list:
            f["_derivative_type"] = "future"
            all_instruments.append(f)
        _do_export(all_instruments, f"openfigi_derivatives_{ticker}", export_fmt)

    return {"options": options, "futures": futures_list}


# ─── Asset-Class Sector Search Helper ──────────────────────────────────────────

def _search_sector(query, sector, max_pages=5, as_json=False, export_fmt=None,
                   label=None, prefix=None, **extra_filters):
    """Generic sector search with display."""
    label = label or sector
    print(f"\n  Searching {label}: \"{query}\"...")

    filters = {"marketSecDes": sector}
    filters.update({k: v for k, v in extra_filters.items() if v is not None})

    data = api_search(query, max_pages=max_pages, **filters)

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    _display_instruments(data, title=f"{label}: \"{query}\"", compact=True)

    if export_fmt and data:
        _do_export(data, prefix or f"openfigi_{sector.lower()}", export_fmt)

    return data


# ─── MBS / Agency Securities ──────────────────────────────────────────────────

def cmd_mbs(query, maturity_start=None, maturity_end=None,
            as_json=False, export_fmt=None):
    """Mortgage-backed / agency securities universe.
    Common queries: FNMA, GNMA, FHLMC, or issuer name.
    With maturity range: uses BASE_TICKER mapping for precise enumeration.
    Without: uses keyword search in Mtge sector.
    """
    if maturity_start and maturity_end:
        job = {"idType": "BASE_TICKER", "idValue": query.upper(),
               "marketSecDes": "Mtge", "maturity": [maturity_start, maturity_end]}
        print(f"\n  Fetching MBS: {query} ({maturity_start[:4]}-{maturity_end[:4]})...")

        result = api_map([job])
        data = []
        if result and "data" in result[0]:
            data = result[0]["data"]
        elif result and "error" in result[0] and "15,000" in result[0].get("error", ""):
            print("  [too many results, chunking by year...]")
            start_y = int(maturity_start[:4])
            end_y = int(maturity_end[:4])
            for y in range(start_y, end_y + 1):
                chunk = dict(job)
                chunk["maturity"] = [f"{y}-01-01", f"{y}-12-31"]
                print(f"  {y}...")
                r = api_map([chunk])
                if r and "data" in r[0]:
                    data.extend(r[0]["data"])

        seen = set()
        deduped = []
        for d in data:
            figi = d.get("figi")
            if figi and figi not in seen:
                seen.add(figi)
                deduped.append(d)

        if as_json:
            print(json.dumps(deduped, indent=2, default=str))
            return deduped

        _display_instruments(deduped, title=f"MBS: {query}", compact=True)

        if export_fmt and deduped:
            _do_export(deduped, f"openfigi_mbs_{query}", export_fmt)

        return deduped

    return _search_sector(query, "Mtge", as_json=as_json, export_fmt=export_fmt,
                          label="MBS/Agency", prefix="openfigi_mbs")


# ─── Municipal Bonds ───────────────────────────────────────────────────────────

def cmd_munis(query, state_code=None, as_json=False, export_fmt=None):
    """Municipal bond universe. Filter by state code (e.g. CA, NY, TX)."""
    extra = {}
    if state_code:
        extra["stateCode"] = state_code.upper()
    return _search_sector(query, "Muni", as_json=as_json, export_fmt=export_fmt,
                          label="Municipal Bonds", prefix="openfigi_munis", **extra)


# ─── FX / Currency ─────────────────────────────────────────────────────────────

def cmd_fx(query, as_json=False, export_fmt=None):
    """FX / Currency instrument lookup."""
    return _search_sector(query, "Curncy", as_json=as_json, export_fmt=export_fmt,
                          label="FX / Currency", prefix="openfigi_fx")


# ─── Commodity ─────────────────────────────────────────────────────────────────

def cmd_commodity(query, as_json=False, export_fmt=None):
    """Commodity instrument lookup."""
    return _search_sector(query, "Comdty", as_json=as_json, export_fmt=export_fmt,
                          label="Commodity", prefix="openfigi_commodity")


# ─── Index Instruments ─────────────────────────────────────────────────────────

def cmd_index_instruments(query, as_json=False, export_fmt=None):
    """Index instrument lookup."""
    return _search_sector(query, "Index", as_json=as_json, export_fmt=export_fmt,
                          label="Index", prefix="openfigi_index")


# ─── Money Market ──────────────────────────────────────────────────────────────

def cmd_money_market(query, as_json=False, export_fmt=None):
    """Money market instrument lookup."""
    return _search_sector(query, "M-Mkt", as_json=as_json, export_fmt=export_fmt,
                          label="Money Market", prefix="openfigi_mmkt")


# ─── Exchange Universe ─────────────────────────────────────────────────────────

def cmd_exchange_scan(exch_code, sector=None, sec_type=None,
                      max_pages=3, as_json=False, export_fmt=None):
    """Enumerate instruments on a specific exchange with optional sector/type filters."""
    exch_code = exch_code.upper()
    filters = {"exchCode": exch_code}
    if sector:
        filters["marketSecDes"] = sector
    if sec_type:
        filters["securityType2"] = sec_type

    print(f"\n  Scanning exchange: {exch_code}...")
    data, total = api_filter(max_pages=max_pages, **filters)

    if as_json:
        print(json.dumps({"exchange": exch_code, "total": total,
                          "sample_size": len(data), "data": data}, indent=2, default=str))
        return data, total

    print(f"\n  Exchange: {exch_code}")
    print("  " + "=" * 70)
    print(f"  Total instruments: {total:,}")
    print(f"  Retrieved: {len(data)}")

    types = {}
    sectors = {}
    for d in data:
        t = d.get("securityType2") or d.get("securityType") or "Unknown"
        s = d.get("marketSector") or "Unknown"
        types[t] = types.get(t, 0) + 1
        sectors[s] = sectors.get(s, 0) + 1

    if sectors:
        print(f"\n  By sector (sample):")
        for s, cnt in sorted(sectors.items(), key=lambda x: -x[1]):
            print(f"    {s:<15} {cnt}")

    if types:
        print(f"\n  By type (sample):")
        for t, cnt in sorted(types.items(), key=lambda x: -x[1])[:15]:
            print(f"    {t:<25} {cnt}")

    _display_instruments(data[:50], compact=True)
    if len(data) > 50:
        print(f"\n  [showing 50 of {len(data)} retrieved, {total:,} total on exchange]")

    print()

    if export_fmt and data:
        _do_export(data, f"openfigi_exchange_{exch_code}", export_fmt)

    return data, total


# ─── Issuer Universe ───────────────────────────────────────────────────────────

def cmd_issuer_universe(ticker, as_json=False, export_fmt=None):
    """Complete issuer universe: equity + bonds + preferred + loans + options + futures."""
    ticker = ticker.upper()
    now = datetime.now()
    print(f"\n  Building full issuer universe for {ticker}...")

    universe = {"ticker": ticker, "equity": [], "bonds": [], "preferred": [],
                "loans": [], "options_count": 0, "futures_count": 0}

    print("  [1/6] Equity listings...")
    eq = api_map_single("TICKER", ticker, marketSecDes="Equity")
    if "data" in eq:
        universe["equity"] = eq["data"]

    issuer_name = None
    if universe["equity"]:
        issuer_name = universe["equity"][0].get("name")

    print("  [2/6] Corporate bonds...")
    bonds = _fetch_issuer_bonds(ticker)
    universe["bonds"] = bonds

    search_term = issuer_name or ticker
    print("  [3/6] Preferred stock...")
    pfds = api_search(search_term, max_pages=2, marketSecDes="Pfd")
    universe["preferred"] = pfds

    print("  [4/6] Loan facilities...")
    terms = api_search(search_term, max_pages=1, securityType="TERM")
    revs = api_search(search_term, max_pages=1, securityType="REV")
    universe["loans"] = terms + revs

    print("  [5/6] Options (counting)...")
    opt_overflow = False
    _, opt_total = api_filter(query=ticker, max_pages=1, securityType="Equity Option")
    universe["options_count"] = opt_total
    if opt_total > 15000:
        opt_overflow = True

    print("  [6/6] Futures...")
    fut_data = api_search(ticker, max_pages=2, securityType2="Future")
    universe["futures_count"] = len(fut_data)

    if as_json:
        out = {"ticker": ticker, "name": issuer_name,
               "equity_listings": len(universe["equity"]),
               "bonds_outstanding": len(universe["bonds"]),
               "preferred_instruments": len(universe["preferred"]),
               "loan_facilities": len(universe["loans"]),
               "options_near_term": universe["options_count"],
               "options_overflow": opt_overflow,
               "futures_active": universe["futures_count"],
               "equity": universe["equity"][:5],
               "bonds_sample": [b.get("ticker") for b in universe["bonds"][:20]],
               "preferred_sample": [p.get("ticker") for p in universe["preferred"][:10]],
               "loans_sample": [l.get("ticker") for l in universe["loans"][:10]]}
        print(json.dumps(out, indent=2, default=str))
        return out

    name = issuer_name or ticker
    print(f"\n  Issuer Universe: {name} ({ticker})")
    print("  " + "=" * 70)

    eq_list = universe["equity"]
    us_listings = [e for e in eq_list if e.get("exchCode") in ("US", "UN", "UA", "UB")]
    print(f"\n  EQUITY")
    print(f"    Listings: {len(eq_list)} total ({len(us_listings)} US)")
    if eq_list:
        print(f"    Share Class FIGI: {eq_list[0].get('shareClassFIGI', 'N/A')}")

    bond_list = universe["bonds"]
    print(f"\n  CORPORATE DEBT")
    print(f"    Bonds: {len(bond_list)}")
    if bond_list:
        coupons = [b["_parsed"]["coupon"] for b in bond_list
                   if b.get("_parsed", {}).get("coupon") is not None and b["_parsed"]["coupon"] > 0]
        if coupons:
            print(f"    Coupon range: {min(coupons):.3f} - {max(coupons):.3f}")
            print(f"    Avg coupon:   {sum(coupons)/len(coupons):.3f}")

    print(f"\n  PREFERRED / HYBRID")
    print(f"    Instruments: {len(universe['preferred'])}")

    print(f"\n  LOAN FACILITIES")
    print(f"    Facilities: {len(universe['loans'])}")

    opt_cnt = universe["options_count"]
    opt_label = f"{opt_cnt:,}" if not opt_overflow else ">15,000"
    print(f"\n  OPTIONS (near-term)")
    print(f"    Contracts: {opt_label}")

    print(f"\n  FUTURES")
    print(f"    Contracts: {universe['futures_count']}")

    total = (len(eq_list) + len(bond_list) + len(universe["preferred"]) +
             len(universe["loans"]) + opt_cnt + universe["futures_count"])
    print(f"\n  TOTAL INSTRUMENTS: ~{total:,}")
    print()

    if export_fmt:
        rows = []
        for e in eq_list[:10]:
            rows.append({"layer": "equity", "ticker": e.get("ticker"), "figi": e.get("figi"),
                         "type": e.get("securityType"), "exchange": e.get("exchCode")})
        for b in bond_list:
            p = b.get("_parsed", {})
            rows.append({"layer": "bond", "ticker": b.get("ticker"), "figi": b.get("figi"),
                         "type": b.get("securityType"), "coupon": p.get("coupon"),
                         "maturity": p.get("maturity")})
        for p in universe["preferred"]:
            rows.append({"layer": "preferred", "ticker": p.get("ticker"), "figi": p.get("figi"),
                         "type": p.get("securityType")})
        for l in universe["loans"]:
            rows.append({"layer": "loan", "ticker": l.get("ticker"), "figi": l.get("figi"),
                         "type": l.get("securityType")})
        _do_export(rows, f"openfigi_universe_{ticker}", export_fmt)

    return universe


# ─── Interactive CLI ──────────────────────────────────────────────────────────

MENU = """
  =====================================================
   OpenFIGI -- Instrument Identifier Mapping Client
  =====================================================

   MAPPING
     1) map             Map a single identifier to FIGI(s)
     2) batch           Batch map multiple identifiers
     3) batch-file      Batch map from a file
     4) portfolio       Auto-detect and resolve mixed identifiers

   SEARCH
     5) search          Keyword search for instruments
     6) filter          Filtered search (alphabetical, with count)

   QUICK LOOKUPS
     7) equity          Quick equity lookup (ticker -> FIGI)
     8) bond            Bond lookup (CUSIP/ISIN -> FIGI)
     9) treasury-cusips Batch resolve Treasury CUSIPs
    10) cross-ref       All identifiers for an instrument
    11) figi-lookup     Reverse FIGI lookup + hierarchy walk
    12) global-listings All worldwide exchange listings

   CREDIT / ANALYTICAL
    13) issuer-bonds    Full bond stack for an issuer
    14) capital-struct  Capital structure map (equity+bonds+pfds+loans)
    15) maturity-prof   Maturity wall / profile by year
    16) compare         Compare bond stacks across issuers
    17) ust-universe    Treasury securities by maturity range
    18) sector-scan     Scan curated issuer list for bond counts
    19) preferred       Preferred stock / hybrid capital
    20) loans           Loan facilities (term, revolver, delay-draw)
    21) issuer-universe Full universe across all asset classes

   DERIVATIVES
    22) options         Options chain (strike/expiry filters)
    23) futures         Futures term structure
    24) derivatives     All derivatives for a ticker

   ASSET CLASSES
    25) mbs             Mortgage-backed securities
    26) munis           Municipal bonds
    27) fx              FX / Currency instruments
    28) commodity       Commodity instruments
    29) index           Index instruments
    30) money-market    Money market instruments

   EXCHANGE
    31) exchange-scan   Instruments on an exchange

   REFERENCE
    32) enums           List valid enum values (idType, exchCode, etc.)
    33) id-types        List all supported identifier types

   q) quit
"""


def _i_map():
    print(f"\n  Common ID types: TICKER, ID_CUSIP, ID_ISIN, ID_SEDOL, ID_BB_GLOBAL")
    id_type = _prompt("ID type", "TICKER")
    id_value = _prompt("ID value")
    if not id_value:
        return
    exch = _prompt("Exchange code (optional, e.g. US)", "")
    currency = _prompt("Currency (optional, e.g. USD)", "")
    sector = _prompt("Market sector (optional, e.g. Equity/Govt/Corp)", "")
    result = cmd_map(id_type, id_value,
                     exch_code=exch or None,
                     currency=currency or None,
                     sector=sector or None)
    if result and "data" in result:
        _prompt_export(result["data"], f"openfigi_map_{id_type}")


def _i_batch():
    id_type = _prompt("ID type for all identifiers", "TICKER")
    print("  Enter identifiers (comma-separated or one per line, blank line to finish):")
    values = []
    while True:
        line = _prompt("  ")
        if not line:
            break
        values.extend([v.strip() for v in line.split(",") if v.strip()])
    if not values:
        return
    exch = _prompt("Exchange code (optional)", "")
    result = cmd_batch(values, id_type=id_type, exch_code=exch or None)
    if result:
        _prompt_export(result, f"openfigi_batch_{id_type}")


def _i_batch_file():
    filepath = _prompt("File path (one ID per line or CSV)")
    if not filepath:
        return
    id_type = _prompt("ID type", "TICKER")
    exch = _prompt("Exchange code (optional)", "")
    result = cmd_batch_file(filepath, id_type=id_type, exch_code=exch or None)
    if result:
        _prompt_export(result, f"openfigi_batch_{id_type}")


def _i_portfolio():
    print("  Enter identifiers (mixed types OK -- auto-detected):")
    print("  Comma-separated or one per line, blank line to finish.")
    values = []
    while True:
        line = _prompt("  ")
        if not line:
            break
        values.extend([v.strip() for v in line.split(",") if v.strip()])
    if not values:
        filepath = _prompt("Or enter file path (one ID per line)")
        if filepath:
            cmd_portfolio(filepath=filepath)
        return
    result = cmd_portfolio(identifiers=values)
    if result:
        _prompt_export(result, "openfigi_portfolio")


def _i_search():
    query = _prompt("Search query")
    if not query:
        return
    sector = _prompt("Market sector filter (optional, e.g. Equity/Govt/Corp)", "")
    exch = _prompt("Exchange code filter (optional)", "")
    result = cmd_search(query, sector=sector or None, exch_code=exch or None)
    if result:
        _prompt_export(result, "openfigi_search")


def _i_filter():
    query = _prompt("Filter query (optional)")
    sector = _prompt("Market sector (optional)", "")
    exch = _prompt("Exchange code (optional)", "")
    result, total = cmd_filter(query=query or None, sector=sector or None,
                               exch_code=exch or None)
    if result:
        _prompt_export(result, "openfigi_filter")


def _i_equity():
    ticker = _prompt("Ticker symbol")
    if not ticker:
        return
    exch = _prompt("Exchange code (optional, e.g. US)", "")
    result = cmd_equity(ticker, exch_code=exch or None)
    if result and "data" in result:
        _prompt_export(result["data"], f"openfigi_equity_{ticker}")


def _i_bond():
    cusip = _prompt("CUSIP or ISIN")
    if not cusip:
        return
    result = cmd_bond(cusip)
    if result and "data" in result:
        _prompt_export(result["data"], f"openfigi_bond_{cusip}")


def _i_treasury():
    print("  Enter Treasury CUSIPs (comma-separated or one per line, blank line to finish):")
    cusips = []
    while True:
        line = _prompt("  ")
        if not line:
            break
        cusips.extend([v.strip() for v in line.split(",") if v.strip()])
    if not cusips:
        return
    result = cmd_treasury_cusips(cusips)
    if result:
        _prompt_export(result, "openfigi_treasury")


def _i_cross_ref():
    print(f"\n  Common ID types: TICKER, ID_CUSIP, ID_ISIN, ID_SEDOL, ID_BB_GLOBAL")
    id_type = _prompt("ID type", "TICKER")
    id_value = _prompt("ID value")
    if not id_value:
        return
    result = cmd_cross_ref(id_type, id_value)
    if result and isinstance(result, list):
        _prompt_export(result, f"openfigi_xref")


def _i_figi_lookup():
    figi = _prompt("FIGI (e.g. BBG000B9XRY4)")
    if not figi:
        return
    cmd_figi_lookup(figi)


def _i_global_listings():
    ticker = _prompt("Ticker symbol")
    if not ticker:
        return
    result = cmd_global_listings(ticker)
    if result and isinstance(result, list):
        _prompt_export(result, f"openfigi_listings_{ticker}")


def _i_issuer_bonds():
    ticker = _prompt("Issuer ticker (e.g. INTC, AAPL, JPM)")
    if not ticker:
        return
    mat = _prompt("Maturity range? (e.g. 2025-2035, or blank for all)", "")
    mat_start, mat_end = None, None
    if mat and "-" in mat:
        parts = mat.split("-")
        mat_start = f"{parts[0].strip()}-01-01"
        mat_end = f"{parts[1].strip()}-12-31"
    result = cmd_issuer_bonds(ticker, maturity_start=mat_start, maturity_end=mat_end)
    if result:
        _prompt_export([{"ticker": b.get("ticker"), "figi": b.get("figi"),
                         "coupon": b.get("_parsed", {}).get("coupon"),
                         "maturity": b.get("_parsed", {}).get("maturity"),
                         "type": b.get("securityType")} for b in result],
                       f"openfigi_bonds_{ticker}")


def _i_capital_structure():
    ticker = _prompt("Issuer ticker")
    if not ticker:
        return
    cmd_capital_structure(ticker)


def _i_maturity_profile():
    ticker = _prompt("Issuer ticker")
    if not ticker:
        return
    start = _prompt("Start year", str(datetime.now().year))
    end = _prompt("End year", str(int(start) + 15))
    cmd_maturity_profile(ticker, start_year=int(start), end_year=int(end))


def _i_compare():
    print("  Enter tickers (comma-separated):")
    line = _prompt("Tickers", "AAPL,MSFT,GOOG,AMZN,META")
    tickers = [t.strip() for t in line.split(",") if t.strip()]
    if not tickers:
        return
    cmd_compare_issuers(tickers)


def _i_ust_universe():
    start = _prompt("Start year", str(datetime.now().year))
    end = _prompt("End year", str(int(start) + 10))
    itype = _prompt_choice("Instrument type", ["all", "notes", "bonds", "bills"], "all")
    cmd_treasury_universe(
        maturity_start=f"{start}-01-01", maturity_end=f"{end}-12-31",
        instrument_type=itype)


def _i_sector_scan():
    print(f"  Available lists: {', '.join(ISSUER_LISTS.keys())}")
    list_name = _prompt("List name (or 'custom')", "tech")
    if list_name.lower() == "custom":
        line = _prompt("Tickers (comma-separated)")
        tickers = [t.strip() for t in line.split(",") if t.strip()]
        cmd_sector_scan(tickers=tickers)
    else:
        cmd_sector_scan(list_name=list_name)


def _i_preferred():
    ticker = _prompt("Issuer ticker")
    if not ticker:
        return
    result = cmd_preferred(ticker)
    if result:
        _prompt_export(result, f"openfigi_pfd_{ticker}")


def _i_loans():
    ticker = _prompt("Issuer ticker")
    if not ticker:
        return
    result = cmd_loans(ticker)
    if result:
        _prompt_export(result, f"openfigi_loans_{ticker}")


def _i_issuer_universe():
    ticker = _prompt("Issuer ticker")
    if not ticker:
        return
    cmd_issuer_universe(ticker)


def _i_options():
    ticker = _prompt("Underlying ticker (e.g. AAPL, SPY)")
    if not ticker:
        return
    expiry = _prompt("Expiry range (e.g. 2025-01-01 to 2025-12-31, or blank for next 2yr)", "")
    strike = _prompt("Strike range MIN-MAX (e.g. 150-200, or blank for all)", "")

    expiry_start, expiry_end = None, None
    if expiry and " to " in expiry:
        parts = expiry.split(" to ")
        expiry_start, expiry_end = parts[0].strip(), parts[1].strip()

    strike_min, strike_max = None, None
    if strike and "-" in strike:
        parts = strike.split("-")
        try:
            strike_min = float(parts[0].strip())
            strike_max = float(parts[1].strip())
        except ValueError:
            pass

    result = cmd_options_chain(ticker, expiry_start=expiry_start, expiry_end=expiry_end,
                               strike_min=strike_min, strike_max=strike_max)
    if result:
        _prompt_export(result, f"openfigi_options_{ticker}")


def _i_futures():
    ticker = _prompt("Base ticker (e.g. ES, CL, GC, ZN, TY)")
    if not ticker:
        return
    expiry = _prompt("Expiry range YYYY-YYYY (or blank for next 3yr)", "")
    expiry_start, expiry_end = None, None
    if expiry and "-" in expiry:
        parts = expiry.split("-")
        expiry_start = f"{parts[0].strip()}-01-01"
        expiry_end = f"{parts[1].strip()}-12-31"
    result = cmd_futures(ticker, expiry_start=expiry_start, expiry_end=expiry_end)
    if result:
        _prompt_export(result, f"openfigi_futures_{ticker}")


def _i_derivatives():
    ticker = _prompt("Underlying ticker")
    if not ticker:
        return
    cmd_derivatives(ticker)


def _i_mbs():
    query = _prompt("Search query (e.g. FNMA, GNMA, FHLMC)")
    if not query:
        return
    mat = _prompt("Maturity range YYYY-YYYY (or blank for search)", "")
    mat_start, mat_end = None, None
    if mat and "-" in mat:
        parts = mat.split("-")
        mat_start = f"{parts[0].strip()}-01-01"
        mat_end = f"{parts[1].strip()}-12-31"
    result = cmd_mbs(query, maturity_start=mat_start, maturity_end=mat_end)
    if result:
        _prompt_export(result, "openfigi_mbs")


def _i_munis():
    query = _prompt("Search query (e.g. 'California', 'NY GO')")
    if not query:
        return
    state = _prompt("State code filter (e.g. CA, NY, TX -- optional)", "")
    result = cmd_munis(query, state_code=state or None)
    if result:
        _prompt_export(result, "openfigi_munis")


def _i_fx():
    query = _prompt("Search query (e.g. EUR, JPY, EURUSD)")
    if not query:
        return
    result = cmd_fx(query)
    if result:
        _prompt_export(result, "openfigi_fx")


def _i_commodity():
    query = _prompt("Search query (e.g. crude, gold, corn, natural gas)")
    if not query:
        return
    result = cmd_commodity(query)
    if result:
        _prompt_export(result, "openfigi_commodity")


def _i_index():
    query = _prompt("Search query (e.g. S&P, NASDAQ, MSCI)")
    if not query:
        return
    result = cmd_index_instruments(query)
    if result:
        _prompt_export(result, "openfigi_index")


def _i_money_market():
    query = _prompt("Search query (e.g. SOFR, LIBOR, commercial paper)")
    if not query:
        return
    result = cmd_money_market(query)
    if result:
        _prompt_export(result, "openfigi_mmkt")


def _i_exchange_scan():
    exch = _prompt("Exchange code (e.g. US, LN, JP, HK)")
    if not exch:
        return
    sector = _prompt("Sector filter (optional, e.g. Equity)", "")
    cmd_exchange_scan(exch, sector=sector or None)


def _i_enums():
    print(f"\n  Available keys: {', '.join(ENUM_KEYS)}")
    key = _prompt("Enum key", "idType")
    cmd_enums(key)


def _i_id_types():
    cmd_id_types()


COMMAND_MAP = {
    "1":  _i_map,
    "2":  _i_batch,
    "3":  _i_batch_file,
    "4":  _i_portfolio,
    "5":  _i_search,
    "6":  _i_filter,
    "7":  _i_equity,
    "8":  _i_bond,
    "9":  _i_treasury,
    "10": _i_cross_ref,
    "11": _i_figi_lookup,
    "12": _i_global_listings,
    "13": _i_issuer_bonds,
    "14": _i_capital_structure,
    "15": _i_maturity_profile,
    "16": _i_compare,
    "17": _i_ust_universe,
    "18": _i_sector_scan,
    "19": _i_preferred,
    "20": _i_loans,
    "21": _i_issuer_universe,
    "22": _i_options,
    "23": _i_futures,
    "24": _i_derivatives,
    "25": _i_mbs,
    "26": _i_munis,
    "27": _i_fx,
    "28": _i_commodity,
    "29": _i_index,
    "30": _i_money_market,
    "31": _i_exchange_scan,
    "32": _i_enums,
    "33": _i_id_types,
}


def interactive_loop():
    auth_status = "authenticated" if HAS_KEY else "unauthenticated (set OPENFIGI_API_KEY for higher limits)"
    print(MENU)
    print(f"  Status: {auth_status}")
    print(f"  Rate limit: {MAX_JOBS} jobs/request, {MAX_REQUESTS_PER_WINDOW} requests/{RATE_LIMIT_WINDOW}s")
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
            print("  Enter 1-33 or q to quit")


# ─── Argparse ─────────────────────────────────────────────────────────────────

def build_argparse():
    p = argparse.ArgumentParser(
        prog="openfigi.py",
        description="OpenFIGI -- Financial Instrument Global Identifier Mapping Client",
    )
    sub = p.add_subparsers(dest="command")

    # map
    s = sub.add_parser("map", help="Map a single identifier to FIGI(s)")
    s.add_argument("id_type", help="Identifier type (e.g. TICKER, ID_CUSIP, ID_ISIN)")
    s.add_argument("id_value", help="Identifier value")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--currency", help="Currency filter")
    s.add_argument("--sector", help="Market sector filter (e.g. Equity, Govt, Corp)")
    s.add_argument("--sec-type", help="Security type filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # batch
    s = sub.add_parser("batch", help="Batch map identifiers from a file")
    s.add_argument("filepath", help="File with one identifier per line")
    s.add_argument("--id-type", default="TICKER", help="ID type for all identifiers")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--currency", help="Currency filter")
    s.add_argument("--sector", help="Market sector filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # search
    s = sub.add_parser("search", help="Keyword search for instruments")
    s.add_argument("query", help="Search keywords")
    s.add_argument("--sector", help="Market sector filter")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--sec-type", help="Security type filter")
    s.add_argument("--pages", type=int, default=3, help="Max pages to fetch")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # filter
    s = sub.add_parser("filter", help="Filtered search (alphabetical by FIGI)")
    s.add_argument("--query", help="Filter keywords")
    s.add_argument("--sector", help="Market sector filter")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--sec-type", help="Security type filter")
    s.add_argument("--pages", type=int, default=3, help="Max pages to fetch")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # enums
    s = sub.add_parser("enums", help="List valid enum values")
    s.add_argument("key", nargs="?", help="Enum key (idType, exchCode, currency, etc.)")
    s.add_argument("--json", action="store_true")

    # equity
    s = sub.add_parser("equity", help="Quick equity lookup by ticker")
    s.add_argument("ticker", help="Equity ticker symbol")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # bond
    s = sub.add_parser("bond", help="Bond lookup by CUSIP or ISIN")
    s.add_argument("cusip", help="CUSIP (9-char) or ISIN (12-char)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # cross-ref
    s = sub.add_parser("cross-ref", help="All identifiers for an instrument")
    s.add_argument("id_type", help="Identifier type")
    s.add_argument("id_value", help="Identifier value")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # treasury
    s = sub.add_parser("treasury", help="Batch resolve Treasury CUSIPs")
    s.add_argument("cusips", nargs="+", help="Treasury CUSIP(s)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # id-types
    s = sub.add_parser("id-types", help="List all supported identifier types")
    s.add_argument("--json", action="store_true")

    # issuer-bonds
    s = sub.add_parser("issuer-bonds", help="Full bond stack for an issuer")
    s.add_argument("ticker", help="Issuer ticker (e.g. INTC, AAPL)")
    s.add_argument("--maturity", help="Maturity range YYYY-YYYY (e.g. 2025-2035)")
    s.add_argument("--sec-type", help="Security type filter (e.g. GLOBAL)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # capital-structure
    s = sub.add_parser("capital-structure", help="Capital structure map")
    s.add_argument("ticker", help="Issuer ticker")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # maturity-profile
    s = sub.add_parser("maturity-profile", help="Bond maturity wall by year")
    s.add_argument("ticker", help="Issuer ticker")
    s.add_argument("--start", type=int, default=None, help="Start year")
    s.add_argument("--end", type=int, default=None, help="End year")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # compare-issuers
    s = sub.add_parser("compare-issuers", help="Compare bond stacks across issuers")
    s.add_argument("tickers", nargs="+", help="Issuer tickers")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # treasury-universe
    s = sub.add_parser("treasury-universe", help="Enumerate Treasury securities")
    s.add_argument("--maturity", help="Maturity range YYYY-YYYY (e.g. 2025-2035)")
    s.add_argument("--type", choices=["all", "notes", "bonds", "bills"], default="all",
                   help="Instrument type")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # sector-scan
    s = sub.add_parser("sector-scan", help="Scan issuer list for bond counts")
    s.add_argument("--list", dest="list_name",
                   help=f"Curated list ({', '.join(ISSUER_LISTS.keys())})")
    s.add_argument("--tickers", nargs="+", help="Custom ticker list")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # preferred
    s = sub.add_parser("preferred", help="Preferred stock / hybrid capital")
    s.add_argument("ticker", help="Issuer ticker")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # loans
    s = sub.add_parser("loans", help="Loan facilities for an issuer")
    s.add_argument("ticker", help="Issuer ticker")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # portfolio
    s = sub.add_parser("portfolio", help="Auto-detect and resolve mixed identifiers")
    s.add_argument("source", help="File path or comma-separated identifiers")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # figi-lookup
    s = sub.add_parser("figi-lookup", help="Reverse FIGI lookup + hierarchy walk")
    s.add_argument("figi", help="FIGI to look up (listing, composite, or share class)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # global-listings
    s = sub.add_parser("global-listings", help="All worldwide exchange listings")
    s.add_argument("ticker", help="Ticker symbol")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # issuer-universe
    s = sub.add_parser("issuer-universe", help="Full universe across all asset classes")
    s.add_argument("ticker", help="Issuer ticker")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # options
    s = sub.add_parser("options", help="Options chain with strike/expiry filters")
    s.add_argument("ticker", help="Underlying ticker (e.g. AAPL, SPY)")
    s.add_argument("--expiry-start", help="Expiry start date YYYY-MM-DD")
    s.add_argument("--expiry-end", help="Expiry end date YYYY-MM-DD")
    s.add_argument("--strike-min", type=float, help="Min strike price")
    s.add_argument("--strike-max", type=float, help="Max strike price")
    s.add_argument("--exch", help="Exchange code filter")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # futures
    s = sub.add_parser("futures", help="Futures term structure")
    s.add_argument("ticker", help="Base ticker (e.g. ES, CL, GC, ZN, TY)")
    s.add_argument("--expiry-start", help="Expiry start date YYYY-MM-DD")
    s.add_argument("--expiry-end", help="Expiry end date YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # derivatives
    s = sub.add_parser("derivatives", help="All derivatives for a ticker")
    s.add_argument("ticker", help="Underlying ticker")
    s.add_argument("--expiry-start", help="Expiry start date YYYY-MM-DD")
    s.add_argument("--expiry-end", help="Expiry end date YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # mbs
    s = sub.add_parser("mbs", help="Mortgage-backed / agency securities")
    s.add_argument("query", help="Search query (e.g. FNMA, GNMA, FHLMC)")
    s.add_argument("--maturity", help="Maturity range YYYY-YYYY")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # munis
    s = sub.add_parser("munis", help="Municipal bonds")
    s.add_argument("query", help="Search query (e.g. California, NY GO)")
    s.add_argument("--state", help="State code filter (e.g. CA, NY, TX)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # fx
    s = sub.add_parser("fx", help="FX / Currency instruments")
    s.add_argument("query", help="Search query (e.g. EUR, JPY, EURUSD)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # commodity
    s = sub.add_parser("commodity", help="Commodity instruments")
    s.add_argument("query", help="Search query (e.g. crude, gold, corn)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # index
    s = sub.add_parser("index", help="Index instruments")
    s.add_argument("query", help="Search query (e.g. S&P, NASDAQ, MSCI)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # money-market
    s = sub.add_parser("money-market", help="Money market instruments")
    s.add_argument("query", help="Search query (e.g. SOFR, LIBOR)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # exchange-scan
    s = sub.add_parser("exchange-scan", help="Instruments on a specific exchange")
    s.add_argument("exch_code", help="Exchange code (e.g. US, LN, JP, HK)")
    s.add_argument("--sector", help="Market sector filter")
    s.add_argument("--sec-type", help="Security type filter")
    s.add_argument("--pages", type=int, default=3, help="Max pages to fetch")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "map":
        cmd_map(args.id_type, args.id_value,
                exch_code=args.exch, currency=args.currency,
                sector=args.sector, sec_type=getattr(args, "sec_type", None),
                as_json=j, export_fmt=exp)
    elif args.command == "batch":
        cmd_batch_file(args.filepath, id_type=args.id_type,
                       exch_code=args.exch, currency=args.currency,
                       sector=args.sector, as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(args.query, sector=args.sector, exch_code=args.exch,
                   sec_type=getattr(args, "sec_type", None),
                   max_pages=args.pages, as_json=j, export_fmt=exp)
    elif args.command == "filter":
        cmd_filter(query=args.query, sector=args.sector, exch_code=args.exch,
                   sec_type=getattr(args, "sec_type", None),
                   max_pages=args.pages, as_json=j, export_fmt=exp)
    elif args.command == "enums":
        cmd_enums(key=args.key, as_json=j)
    elif args.command == "equity":
        cmd_equity(args.ticker, exch_code=args.exch, as_json=j, export_fmt=exp)
    elif args.command == "bond":
        cmd_bond(args.cusip, as_json=j, export_fmt=exp)
    elif args.command == "cross-ref":
        cmd_cross_ref(args.id_type, args.id_value, as_json=j, export_fmt=exp)
    elif args.command == "treasury":
        cmd_treasury_cusips(args.cusips, as_json=j, export_fmt=exp)
    elif args.command == "id-types":
        cmd_id_types(as_json=j)
    elif args.command == "issuer-bonds":
        mat_start, mat_end = None, None
        if args.maturity and "-" in args.maturity:
            parts = args.maturity.split("-")
            mat_start = f"{parts[0].strip()}-01-01"
            mat_end = f"{parts[1].strip()}-12-31"
        cmd_issuer_bonds(args.ticker, maturity_start=mat_start, maturity_end=mat_end,
                         sec_type_filter=getattr(args, "sec_type", None),
                         as_json=j, export_fmt=exp)
    elif args.command == "capital-structure":
        cmd_capital_structure(args.ticker, as_json=j, export_fmt=exp)
    elif args.command == "maturity-profile":
        cmd_maturity_profile(args.ticker, start_year=args.start, end_year=args.end,
                             as_json=j, export_fmt=exp)
    elif args.command == "compare-issuers":
        cmd_compare_issuers(args.tickers, as_json=j, export_fmt=exp)
    elif args.command == "treasury-universe":
        mat_start, mat_end = None, None
        if args.maturity and "-" in args.maturity:
            parts = args.maturity.split("-")
            mat_start = f"{parts[0].strip()}-01-01"
            mat_end = f"{parts[1].strip()}-12-31"
        cmd_treasury_universe(maturity_start=mat_start, maturity_end=mat_end,
                              instrument_type=args.type, as_json=j, export_fmt=exp)
    elif args.command == "sector-scan":
        cmd_sector_scan(list_name=args.list_name, tickers=args.tickers,
                        as_json=j, export_fmt=exp)
    elif args.command == "preferred":
        cmd_preferred(args.ticker, as_json=j, export_fmt=exp)
    elif args.command == "loans":
        cmd_loans(args.ticker, as_json=j, export_fmt=exp)
    elif args.command == "portfolio":
        src = args.source
        if os.path.exists(src):
            cmd_portfolio(filepath=src, as_json=j, export_fmt=exp)
        else:
            ids = [v.strip() for v in src.split(",") if v.strip()]
            cmd_portfolio(identifiers=ids, as_json=j, export_fmt=exp)
    elif args.command == "figi-lookup":
        cmd_figi_lookup(args.figi, as_json=j, export_fmt=exp)
    elif args.command == "global-listings":
        cmd_global_listings(args.ticker, as_json=j, export_fmt=exp)
    elif args.command == "issuer-universe":
        cmd_issuer_universe(args.ticker, as_json=j, export_fmt=exp)
    elif args.command == "options":
        cmd_options_chain(args.ticker, expiry_start=args.expiry_start,
                          expiry_end=args.expiry_end,
                          strike_min=args.strike_min, strike_max=args.strike_max,
                          exch_code=args.exch, as_json=j, export_fmt=exp)
    elif args.command == "futures":
        cmd_futures(args.ticker, expiry_start=args.expiry_start,
                    expiry_end=args.expiry_end, as_json=j, export_fmt=exp)
    elif args.command == "derivatives":
        cmd_derivatives(args.ticker, expiry_start=args.expiry_start,
                        expiry_end=args.expiry_end, as_json=j, export_fmt=exp)
    elif args.command == "mbs":
        mat_start, mat_end = None, None
        if args.maturity and "-" in args.maturity:
            parts = args.maturity.split("-")
            mat_start = f"{parts[0].strip()}-01-01"
            mat_end = f"{parts[1].strip()}-12-31"
        cmd_mbs(args.query, maturity_start=mat_start, maturity_end=mat_end,
                as_json=j, export_fmt=exp)
    elif args.command == "munis":
        cmd_munis(args.query, state_code=getattr(args, "state", None),
                  as_json=j, export_fmt=exp)
    elif args.command == "fx":
        cmd_fx(args.query, as_json=j, export_fmt=exp)
    elif args.command == "commodity":
        cmd_commodity(args.query, as_json=j, export_fmt=exp)
    elif args.command == "index":
        cmd_index_instruments(args.query, as_json=j, export_fmt=exp)
    elif args.command == "money-market":
        cmd_money_market(args.query, as_json=j, export_fmt=exp)
    elif args.command == "exchange-scan":
        cmd_exchange_scan(args.exch_code, sector=args.sector,
                          sec_type=getattr(args, "sec_type", None),
                          max_pages=args.pages, as_json=j, export_fmt=exp)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()

    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
