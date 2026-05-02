#!/usr/bin/env python3
"""
USITC Harmonized Tariff Schedule -- HTS Reststop Client

Single-script client for the USITC HTS Reststop API. Queries the official
Harmonized Tariff Schedule of the United States for duty rates, tariff codes,
and chapter-level data. Curated registry of macro-relevant sectors (steel,
autos, semis, energy, agriculture) and reference mapping of major tariff
actions (Section 232, 301, reciprocal). No auth required.

Usage:
    python tariffs.py                                          # interactive CLI
    python tariffs.py lookup 8703.23                           # lookup HTS code
    python tariffs.py search "crude petroleum"                 # keyword search
    python tariffs.py chapter 72                               # all codes in chapter 72
    python tariffs.py releases                                 # available HTS releases
    python tariffs.py duty 8703.23.01                          # duty detail for code
    python tariffs.py macro-sectors                            # curated macro sectors
    python tariffs.py sector steel_aluminum                    # pull sector codes+rates
    python tariffs.py tariff-actions                           # major tariff actions ref
    python tariffs.py rate-check 7206.10 7601.10 2709.00       # batch rate check
    python tariffs.py chapter-summary 72                       # chapter rate stats
    python tariffs.py high-duty 72 --threshold 25              # codes above 25% duty
    python tariffs.py export chapter --chapter 72 --format csv # export to CSV
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime

import requests


# --- Configuration ------------------------------------------------------------

BASE_URL = "https://hts.usitc.gov/reststop"
SESSION = requests.Session()

MACRO_CHAPTERS = {
    "steel_aluminum": {
        "label": "Steel & Aluminum",
        "chapters": [72, 73, 76],
        "codes": ["7206.10", "7207.11", "7601.10"],
    },
    "autos": {
        "label": "Automobiles & Parts",
        "chapters": [87],
        "codes": ["8703.23", "8703.24", "8708.10"],
    },
    "semiconductors": {
        "label": "Semiconductors & Electronics",
        "chapters": [84, 85],
        "codes": ["8541.10", "8542.31", "8471.30"],
    },
    "energy": {
        "label": "Energy & Petroleum",
        "chapters": [27],
        "codes": ["2709.00", "2710.12", "2711.11"],
    },
    "agriculture": {
        "label": "Agriculture & Food",
        "chapters": [2, 4, 10, 12, 17, 22],
        "codes": ["1001.19", "1005.90", "1201.90"],
    },
    "pharma": {
        "label": "Pharmaceuticals",
        "chapters": [29, 30],
        "codes": ["3004.90"],
    },
    "rare_earths": {
        "label": "Rare Earths & Critical Minerals",
        "chapters": [26, 28],
        "codes": ["2612.10", "2846.90"],
    },
    "textiles": {
        "label": "Textiles & Apparel",
        "chapters": [50, 51, 52, 61, 62],
        "codes": [],
    },
    "chemicals": {
        "label": "Chemicals & Feedstocks",
        "chapters": [28, 29, 38, 39, 40],
        "codes": ["2804.10", "2901.10", "2902.30", "3901.10", "3902.10"],
    },
    "batteries_ev": {
        "label": "Batteries & EV Components",
        "chapters": [85],
        "codes": ["8507.60", "8507.30", "8544.60"],
    },
    "solar": {
        "label": "Solar & Renewables",
        "chapters": [85],
        "codes": ["8541.42", "8541.43"],
    },
    "capital_equipment": {
        "label": "Capital Equipment & Machine Tools",
        "chapters": [84],
        "codes": ["8456.11", "8457.10", "8458.11", "8462.10", "8466.93"],
    },
    "aerospace": {
        "label": "Aerospace",
        "chapters": [88],
        "codes": ["8802.40", "8803.30"],
    },
    "copper_metals": {
        "label": "Copper & Industrial Metals",
        "chapters": [74, 78, 79, 80],
        "codes": ["7403.11", "7408.11"],
    },
    "medical_devices": {
        "label": "Medical Devices",
        "chapters": [90],
        "codes": ["9018.19", "9018.31", "9022.12"],
    },
    "consumer_goods": {
        "label": "Consumer Goods (Apparel, Footwear, Retail)",
        "chapters": [42, 61, 62, 63, 64, 71],
        "codes": ["6404.11", "4202.12", "7113.19"],
    },
}

# Statutory tariff actions (metadata + base-layer scope)
TARIFF_ACTIONS = {
    "section_232_steel": {
        "desc": "Section 232 Steel (25%)",
        "year": 2018,
        "codes_prefix": ["72", "73"],
        "overlay_prefix": "9903.81",
    },
    "section_232_aluminum": {
        "desc": "Section 232 Aluminum (10%)",
        "year": 2018,
        "codes_prefix": ["76"],
        "overlay_prefix": "9903.85",
    },
    "section_232_aluminum_russia_200": {
        "desc": "Section 232 Aluminum Russia 200%",
        "year": 2023,
        "overlay_prefix": "9903.85.67",
    },
    "section_232_semiconductors": {
        "desc": "Section 232 Semiconductors",
        "year": 2025,
        "overlay_prefix": "9903.79",
    },
    "section_232_derivative": {
        "desc": "Section 232 Aluminum/Steel/Copper Derivatives",
        "year": 2025,
        "overlay_prefix": "9903.82",
    },
    "section_301_list1": {
        "desc": "Section 301 China List 1 ($34B)",
        "year": 2018,
        "chapters": [84, 85],
        "overlay_prefix": "9903.88",
    },
    "section_301_list2": {
        "desc": "Section 301 China List 2 ($16B)",
        "year": 2018,
        "chapters": [27, 28, 39, 72, 73, 76, 84, 85, 86, 87, 88, 89, 90],
        "overlay_prefix": "9903.88",
    },
    "section_301_list3": {
        "desc": "Section 301 China List 3 ($200B)",
        "year": 2018,
        "overlay_prefix": "9903.88",
    },
    "section_301_list4a": {
        "desc": "Section 301 China List 4A ($112B)",
        "year": 2019,
        "overlay_prefix": "9903.88",
    },
    "section_301_china_usmca_2024": {
        "desc": "Section 301 China USMCA-adjacent (Sep 2024)",
        "year": 2024,
        "overlay_prefix": "9903.91",
    },
    "section_301_china_cranes_2024": {
        "desc": "Section 301 China Ship-to-Shore Cranes",
        "year": 2024,
        "overlay_prefix": "9903.92",
    },
    "section_201_solar": {
        "desc": "Section 201 Solar Safeguard",
        "year": 2018,
        "overlay_prefix": "9903.45",
    },
    "ieepa_russia": {
        "desc": "IEEPA Russia Sanctions",
        "year": 2022,
        "overlay_prefix": "9903.90",
    },
    "ieepa_oil_russia": {
        "desc": "IEEPA Oil/Fuel Russia",
        "year": 2024,
        "overlay_prefix": "9903.27",
    },
    "reciprocal_mexico": {
        "desc": "Reciprocal Tariffs - Mexico (Feb 2025)",
        "year": 2025,
        "overlay_prefix": "9903.01",
    },
    "reciprocal_broad_2025": {
        "desc": "Reciprocal Tariffs Broad (Apr 2025)",
        "year": 2025,
        "overlay_prefix": "9903.02",
    },
    "reciprocal_country_2025": {
        "desc": "Reciprocal Tariffs Country-Specific (2025)",
        "year": 2025,
        "overlay_prefix": "9903.03",
    },
    "usmca_carveouts_2025": {
        "desc": "USMCA Carveouts / Exclusions (2025)",
        "year": 2025,
        "overlay_prefix": "9903.94",
    },
    "aircraft_civil_2025": {
        "desc": "Civil Aircraft Tariffs (2025)",
        "year": 2025,
        "overlay_prefix": "9903.96",
    },
    "hdv_2025": {
        "desc": "Medium/Heavy-Duty Vehicle Safeguard",
        "year": 2025,
        "overlay_prefix": "9903.74",
    },
    "softwood_lumber_2025": {
        "desc": "Softwood Lumber Safeguard",
        "year": 2025,
        "overlay_prefix": "9903.76",
    },
}

# Chapter 99 subchapter registry: maps 4-digit prefix -> descriptive label.
# Used to auto-resolve footnote references like "See 9903.88.01" to the
# policy regime producing the additional duty.
CHAPTER99_SUBCHAPTERS = {
    "9903.01": {
        "label": "Reciprocal Tariffs - Mexico (Feb 2025+)",
        "regime": "IEEPA - Mexico",
        "typical_overlay": "+25% (base rate + 25)",
    },
    "9903.02": {
        "label": "Reciprocal Tariffs - Broad & Transshipment (Apr 2025)",
        "regime": "IEEPA - Global Reciprocal",
        "typical_overlay": "+15% to +40%",
    },
    "9903.03": {
        "label": "Reciprocal Tariffs - Country-Specific (2025)",
        "regime": "IEEPA - Country Reciprocal",
        "typical_overlay": "varies by country",
    },
    "9903.04": {
        "label": "Dairy Quotas",
        "regime": "USMCA TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.08": {
        "label": "Bath Preparations Safeguard",
        "regime": "Section 201",
        "typical_overlay": "ad valorem",
    },
    "9903.17": {
        "label": "USMCA Quota - Sugar/Dairy",
        "regime": "USMCA TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.18": {
        "label": "USMCA Quota - Beef/Poultry",
        "regime": "USMCA TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.19": {
        "label": "Food Product Quotas",
        "regime": "TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.27": {
        "label": "Fuel / Oil - Russia Sanctions",
        "regime": "IEEPA - Russia Oil",
        "typical_overlay": "varies",
    },
    "9903.40": {
        "label": "Section 201 Tire Safeguard",
        "regime": "Section 201",
        "typical_overlay": "ad valorem phase-down",
    },
    "9903.41": {
        "label": "Leather IEEPA",
        "regime": "IEEPA",
        "typical_overlay": "+duty",
    },
    "9903.45": {
        "label": "Section 201 Solar Safeguard",
        "regime": "Section 201 - Solar",
        "typical_overlay": "ad valorem phase-down",
    },
    "9903.52": {
        "label": "Special Limited Global Import Quota",
        "regime": "Agriculture Quota",
        "typical_overlay": "quota-gated",
    },
    "9903.53": {
        "label": "Softwood Lumber - Canada by Region",
        "regime": "AD/CVD-related",
        "typical_overlay": "varies",
    },
    "9903.54": {
        "label": "Argentina Beef Additional Quota",
        "regime": "Agriculture TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.55": {
        "label": "Temporary Importation Bond Quotas",
        "regime": "TIB / TRQ",
        "typical_overlay": "quota-gated",
    },
    "9903.74": {
        "label": "Medium/Heavy-Duty Vehicle Safeguard",
        "regime": "Section 232 HDV",
        "typical_overlay": "ad valorem",
    },
    "9903.76": {
        "label": "Softwood Timber & Lumber Safeguard",
        "regime": "Section 232 Timber",
        "typical_overlay": "ad valorem",
    },
    "9903.79": {
        "label": "Semiconductor Articles - Section 232",
        "regime": "Section 232 Semiconductors",
        "typical_overlay": "varies",
    },
    "9903.82": {
        "label": "Aluminum/Steel/Copper Derivatives",
        "regime": "Section 232 Derivatives",
        "typical_overlay": "+25% derivatives",
    },
    "9903.85": {
        "label": "Aluminum - Russia (high overlay)",
        "regime": "Section 232 Russia",
        "typical_overlay": "+200%",
    },
    "9903.88": {
        "label": "Section 301 China (Lists 1-4A, $450B+)",
        "regime": "Section 301 China",
        "typical_overlay": "+7.5% / +15% / +25%",
    },
    "9903.89": {
        "label": "Nicaragua",
        "regime": "IEEPA",
        "typical_overlay": "ad valorem",
    },
    "9903.90": {
        "label": "Russian Federation (IEEPA)",
        "regime": "IEEPA Russia",
        "typical_overlay": "ad valorem",
    },
    "9903.91": {
        "label": "China USMCA-Adjacent (Sep 2024)",
        "regime": "Section 301 China",
        "typical_overlay": "+25% / higher",
    },
    "9903.92": {
        "label": "China Ship-to-Shore Cranes / Industrial Equipment",
        "regime": "Section 301 China",
        "typical_overlay": "+25% to +100%",
    },
    "9903.94": {
        "label": "USMCA Reciprocal Carveouts/Exclusions",
        "regime": "Reciprocal - USMCA",
        "typical_overlay": "excluded (pass-through)",
    },
    "9903.96": {
        "label": "Civil Aircraft Tariffs (2025)",
        "regime": "IEEPA - Aircraft",
        "typical_overlay": "ad valorem",
    },
}

SECTOR_KEYS = list(MACRO_CHAPTERS.keys())

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# --- HTTP Layer ---------------------------------------------------------------

def _request(url, params=None, max_retries=3):
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


# --- Data Fetchers ------------------------------------------------------------
# The USITC Reststop has two data endpoints:
#   /search?keyword=...       -- keyword OR HTS number search (up to 100 results)
#   /exportList?from=...&to=...&format=JSON  -- range export (all codes in range)
# Plus /releaseList for available schedule versions.

def _fetch_search(keyword):
    """Search by keyword or HTS number. Returns list of code dicts."""
    data = _request(f"{BASE_URL}/search", params={"keyword": keyword})
    if not data:
        return []
    return data if isinstance(data, list) else data.get("results", [data])


def _fetch_export_range(hts_from, hts_to):
    """Export a range of HTS codes. Returns list of code dicts."""
    params = {"from": hts_from, "to": hts_to, "format": "JSON", "styles": "false"}
    data = _request(f"{BASE_URL}/exportList", params=params)
    if not data:
        return []
    return data if isinstance(data, list) else data.get("results", [data])


def _fetch_chapter(chapter):
    """Get all codes in a chapter via exportList with XXYY..XXYY range."""
    ch = int(chapter)
    hts_from = f"{ch:02d}00"
    hts_to = f"{ch:02d}99"
    return _fetch_export_range(hts_from, hts_to)


def _fetch_releases():
    data = _request(f"{BASE_URL}/releaseList")
    if not data:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("releases", "ReleaseList", "releaseList", "results"):
            if key in data:
                return data[key]
    return [data] if data else []


# --- Parsing Helpers ----------------------------------------------------------

def _parse_rate(rate_str):
    """Extract numeric duty percentage from rate strings like '25%', 'Free',
    '2.5 cents/kg', '3.4%'. Returns float or None for non-percentage rates."""
    if not rate_str:
        return None
    s = str(rate_str).strip()
    if not s:
        return None
    if s.lower() in ("free", "free."):
        return 0.0
    pct_match = re.search(r"(\d+\.?\d*)\s*%", s)
    if pct_match:
        return float(pct_match.group(1))
    return None


def _truncate(text, length=80):
    if not text:
        return ""
    text = str(text).replace("\n", " ").strip()
    return text[:length - 3] + "..." if len(text) > length else text


def _safe_str(code, field, default=""):
    val = code.get(field, default)
    if val is None:
        return default
    if isinstance(val, list):
        return ", ".join(str(v) for v in val) if val else default
    return str(val).strip() if val else default


def _flatten_code(code):
    units = code.get("units")
    if isinstance(units, list):
        unit1 = units[0] if len(units) > 0 else ""
        unit2 = units[1] if len(units) > 1 else ""
    else:
        unit1 = _safe_str(code, "units")
        unit2 = ""

    return {
        "htsno": _safe_str(code, "htsno"),
        "description": _safe_str(code, "description"),
        "superior": _safe_str(code, "superior"),
        "indent": _safe_str(code, "indent"),
        "statistical_suffix": _safe_str(code, "statisticalSuffix"),
        "general": _safe_str(code, "general"),
        "special": _safe_str(code, "special"),
        "other": _safe_str(code, "other"),
        "unit1": unit1,
        "unit2": unit2,
        "units": _safe_str(code, "units"),
        "footnotes": _format_footnotes(code.get("footnotes")),
        "footnote_refs": ";".join(_extract_overlay_refs(code.get("footnotes"))),
        "quota_quantity": _safe_str(code, "quotaQuantity"),
        "additional_duties": _safe_str(code, "additionalDuties"),
    }


def _format_footnotes(footnotes):
    if not footnotes:
        return ""
    if isinstance(footnotes, list):
        parts = []
        for fn in footnotes:
            if isinstance(fn, dict):
                val = fn.get("value", "").strip()
                cols = fn.get("columns", [])
                if cols and isinstance(cols, list):
                    val = f"[{','.join(cols)}] {val}"
                parts.append(val)
            else:
                parts.append(str(fn))
        return "; ".join(p for p in parts if p)
    return str(footnotes)


# --- Chapter 99 Overlay Resolver ---------------------------------------------

_OVERLAY_REGEX = re.compile(r"9903\.\d{2}(?:\.\d{2,4})?")


def _extract_overlay_refs(footnotes):
    """Return list of 9903.xx references found in footnote text."""
    if not footnotes:
        return []
    if isinstance(footnotes, list):
        text = " ".join(
            (fn.get("value", "") if isinstance(fn, dict) else str(fn))
            for fn in footnotes
        )
    else:
        text = str(footnotes)
    refs = _OVERLAY_REGEX.findall(text)
    seen = set()
    ordered = []
    for r in refs:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    return ordered


def _classify_overlay(hts_ref):
    """Given 9903.xx[.yy], return subchapter registry entry."""
    if not hts_ref:
        return None
    prefix = ".".join(hts_ref.split(".")[:2])
    return CHAPTER99_SUBCHAPTERS.get(prefix)


# --- Display Functions --------------------------------------------------------

def _display_codes_table(codes, title="HTS Codes"):
    if not codes:
        print("  [no codes found]")
        return
    print(f"\n  {title} ({len(codes)} results)")
    print("  " + "=" * 95)
    print(f"  {'HTS No':<16} {'Description':<40} {'General':>12} {'Special':>12} {'Other':>12}")
    print(f"  {'-'*16} {'-'*40} {'-'*12} {'-'*12} {'-'*12}")
    for c in codes:
        hts = _safe_str(c, "htsno")[:15]
        desc = _truncate(_safe_str(c, "description"), 39)
        gen = _truncate(_safe_str(c, "general"), 11)
        spc = _truncate(_safe_str(c, "special"), 11)
        oth = _truncate(_safe_str(c, "other"), 11)
        print(f"  {hts:<16} {desc:<40} {gen:>12} {spc:>12} {oth:>12}")
    print()


def _display_duty_detail(code_data):
    if not code_data:
        print("  [no duty data]")
        return
    c = code_data if isinstance(code_data, dict) else code_data[0]
    hts = _safe_str(c, "htsno")
    desc = _safe_str(c, "description")
    print(f"\n  DUTY DETAIL: {hts}")
    print("  " + "=" * 65)
    print(f"  {'HTS Number:':<25} {hts}")
    print(f"  {'Description:':<25} {_truncate(desc, 60)}")
    print(f"  {'General Rate:':<25} {_safe_str(c, 'general')}")
    print(f"  {'Special Rate:':<25} {_safe_str(c, 'special')}")
    print(f"  {'Other Rate:':<25} {_safe_str(c, 'other')}")
    units = _safe_str(c, "units")
    if units:
        print(f"  {'Units:':<25} {units}")
    fn = _format_footnotes(c.get("footnotes"))
    if fn:
        print(f"  {'Footnotes:':<25} {_truncate(fn, 60)}")
    qq = _safe_str(c, "quotaQuantity")
    if qq:
        print(f"  {'Quota Quantity:':<25} {qq}")
    ad = _safe_str(c, "additionalDuties")
    if ad:
        print(f"  {'Additional Duties:':<25} {_truncate(ad, 60)}")
    gen_pct = _parse_rate(_safe_str(c, "general"))
    if gen_pct is not None:
        print(f"  {'Parsed General %:':<25} {gen_pct:.1f}%")
    print()


def _display_releases(releases):
    if not releases:
        print("  [no releases found]")
        return
    print(f"\n  HTS SCHEDULE RELEASES ({len(releases)} available)")
    print("  " + "=" * 50)
    for i, r in enumerate(releases, 1):
        if isinstance(r, dict):
            label = r.get("name", r.get("release", r.get("id", str(r))))
        else:
            label = str(r)
        print(f"  {i:>4}) {label}")
    print()


def _display_rate_summary(codes, title="Rate Summary"):
    if not codes:
        print("  [no codes to summarize]")
        return
    print(f"\n  {title}")
    print("  " + "=" * 95)
    print(f"  {'HTS No':<16} {'Description':<40} {'General':>12} {'Parsed %':>10}")
    print(f"  {'-'*16} {'-'*40} {'-'*12} {'-'*10}")
    for c in codes:
        hts = _safe_str(c, "htsno")[:15]
        desc = _truncate(_safe_str(c, "description"), 39)
        gen = _truncate(_safe_str(c, "general"), 11)
        pct = _parse_rate(_safe_str(c, "general"))
        pct_str = f"{pct:.1f}%" if pct is not None else "---"
        print(f"  {hts:<16} {desc:<40} {gen:>12} {pct_str:>10}")
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

def cmd_lookup(query, as_json=False, export_fmt=None):
    print(f"\n  Looking up HTS number '{query}'...")
    codes = _fetch_search(query)
    if not codes:
        print("  [no results]")
        return None
    if as_json:
        print(json.dumps(codes, indent=2, default=str))
    else:
        _display_codes_table(codes, f"HTS LOOKUP: {query}")
    if export_fmt:
        flat = [_flatten_code(c) for c in codes]
        _do_export(flat, f"hts_lookup_{query.replace('.', '')}", export_fmt)
    return codes


def cmd_search(query, as_json=False, export_fmt=None):
    print(f"\n  Searching HTS for '{query}'...")
    codes = _fetch_search(query)
    if not codes:
        print("  [no results]")
        return None
    if as_json:
        print(json.dumps(codes, indent=2, default=str))
    else:
        _display_codes_table(codes, f"HTS SEARCH: {query}")
    if export_fmt:
        flat = [_flatten_code(c) for c in codes]
        _do_export(flat, f"hts_search_{query.replace(' ', '_')[:30]}", export_fmt)
    return codes


def cmd_chapter(chapter, as_json=False, export_fmt=None):
    ch_str = str(chapter).zfill(2)
    print(f"\n  Fetching chapter {ch_str}...")
    codes = _fetch_chapter(chapter)
    if not codes:
        print("  [no data for chapter]")
        return None
    if as_json:
        print(json.dumps(codes, indent=2, default=str))
    else:
        _display_codes_table(codes, f"CHAPTER {ch_str}")
    if export_fmt:
        flat = [_flatten_code(c) for c in codes]
        _do_export(flat, f"hts_chapter_{ch_str}", export_fmt)
    return codes


def cmd_releases(as_json=False):
    print("\n  Fetching HTS release list...")
    releases = _fetch_releases()
    if as_json:
        print(json.dumps(releases, indent=2, default=str))
    else:
        _display_releases(releases)
    return releases


def cmd_duty(hts_code, as_json=False, export_fmt=None):
    print(f"\n  Fetching duty detail for '{hts_code}'...")
    codes = _fetch_search(hts_code)
    if not codes:
        print("  [no results]")
        return None
    exact = [c for c in codes
             if _safe_str(c, "htsno").replace(" ", "").startswith(hts_code.replace(" ", ""))]
    target = exact if exact else codes[:1]
    if as_json:
        print(json.dumps(target, indent=2, default=str))
    else:
        for c in target:
            _display_duty_detail(c)
    if export_fmt:
        flat = [_flatten_code(c) for c in target]
        _do_export(flat, f"hts_duty_{hts_code.replace('.', '')}", export_fmt)
    return target


def cmd_macro_sectors(as_json=False):
    if as_json:
        print(json.dumps(MACRO_CHAPTERS, indent=2, default=str))
        return MACRO_CHAPTERS
    print(f"\n  MACRO-RELEVANT TARIFF SECTORS ({len(MACRO_CHAPTERS)} categories)")
    print("  " + "=" * 70)
    for key, info in MACRO_CHAPTERS.items():
        chapters_str = ", ".join(str(ch) for ch in info["chapters"])
        codes_str = ", ".join(info["codes"]) if info["codes"] else "(none)"
        print(f"\n  {info['label']} [{key}]")
        print(f"  {'-' * len(info['label'])}")
        print(f"    Chapters: {chapters_str}")
        print(f"    Key codes: {codes_str}")
    print()
    return MACRO_CHAPTERS


def cmd_sector(sector, as_json=False, export_fmt=None):
    if sector not in MACRO_CHAPTERS:
        print(f"  [unknown sector: {sector}]")
        print(f"  Available: {', '.join(SECTOR_KEYS)}")
        return None
    info = MACRO_CHAPTERS[sector]
    all_codes = []
    total_chapters = len(info["chapters"])

    print(f"\n  Fetching {info['label']} ({total_chapters} chapters)...")
    for i, ch in enumerate(info["chapters"], 1):
        ch_str = str(ch).zfill(2)
        print(f"  [{i}/{total_chapters}] Chapter {ch_str}...", flush=True)
        codes = _fetch_chapter(ch)
        if codes:
            all_codes.extend(codes)

    if info["codes"]:
        print(f"  Fetching {len(info['codes'])} specific codes...")
        for code in info["codes"]:
            results = _fetch_search(code)
            if results:
                existing_hts = {_safe_str(c, "htsno") for c in all_codes}
                for r in results:
                    if _safe_str(r, "htsno") not in existing_hts:
                        all_codes.append(r)

    if not all_codes:
        print("  [no data]")
        return None
    if as_json:
        print(json.dumps(all_codes, indent=2, default=str))
    else:
        _display_rate_summary(all_codes, f"{info['label'].upper()} -- DUTY RATES")
    if export_fmt:
        flat = [_flatten_code(c) for c in all_codes]
        _do_export(flat, f"hts_sector_{sector}", export_fmt)
    return all_codes


def cmd_tariff_actions(as_json=False):
    if as_json:
        print(json.dumps(TARIFF_ACTIONS, indent=2, default=str))
        return TARIFF_ACTIONS
    print(f"\n  MAJOR TARIFF ACTIONS REFERENCE ({len(TARIFF_ACTIONS)} actions)")
    print("  " + "=" * 75)
    print(f"  {'Action':<28} {'Year':>6}  {'Description':<35}")
    print(f"  {'-'*28} {'-'*6}  {'-'*35}")
    for key, info in TARIFF_ACTIONS.items():
        desc = info["desc"]
        year = info["year"]
        print(f"  {key:<28} {year:>6}  {desc:<35}", end="")
        extras = []
        if "codes_prefix" in info:
            extras.append(f"prefixes: {', '.join(info['codes_prefix'])}")
        if "chapters" in info:
            ch_list = ", ".join(str(c) for c in info["chapters"][:8])
            if len(info["chapters"]) > 8:
                ch_list += "..."
            extras.append(f"ch: {ch_list}")
        if extras:
            print(f"  ({'; '.join(extras)})", end="")
        print()
    print()
    return TARIFF_ACTIONS


def cmd_rate_check(codes_list, as_json=False, export_fmt=None):
    if not codes_list:
        print("  [provide at least one HTS code]")
        return None
    all_results = []
    total = len(codes_list)
    print(f"\n  Checking rates for {total} codes...")
    for i, code in enumerate(codes_list, 1):
        print(f"  [{i}/{total}] {code}...", flush=True)
        results = _fetch_search(code)
        if results:
            all_results.extend(results)
    if not all_results:
        print("  [no results]")
        return None
    if as_json:
        print(json.dumps(all_results, indent=2, default=str))
    else:
        _display_rate_summary(all_results, f"RATE CHECK ({total} queries)")
    if export_fmt:
        flat = [_flatten_code(c) for c in all_results]
        _do_export(flat, "hts_rate_check", export_fmt)
    return all_results


def cmd_chapter_summary(chapter, as_json=False, export_fmt=None):
    ch_str = str(chapter).zfill(2)
    print(f"\n  Fetching chapter {ch_str} for summary...")
    codes = _fetch_chapter(chapter)
    if not codes:
        print("  [no data]")
        return None

    total = len(codes)
    free_count = 0
    dutiable_count = 0
    unparsed_count = 0
    rates = []

    for c in codes:
        gen = _safe_str(c, "general")
        pct = _parse_rate(gen)
        if pct is not None:
            rates.append(pct)
            if pct == 0.0:
                free_count += 1
            else:
                dutiable_count += 1
        else:
            if gen and gen.lower() not in ("", "free", "free."):
                unparsed_count += 1

    summary = {
        "chapter": ch_str,
        "total_codes": total,
        "free_count": free_count,
        "dutiable_count": dutiable_count,
        "unparsed_count": unparsed_count,
    }

    if rates:
        rates_sorted = sorted(rates)
        n = len(rates_sorted)
        summary["rate_min"] = rates_sorted[0]
        summary["rate_max"] = rates_sorted[-1]
        summary["rate_median"] = rates_sorted[n // 2]
        summary["rate_mean"] = sum(rates_sorted) / n
        summary["rate_count"] = n

    if as_json:
        print(json.dumps(summary, indent=2, default=str))
    else:
        print(f"\n  CHAPTER {ch_str} SUMMARY")
        print("  " + "=" * 50)
        print(f"  {'Total codes:':<25} {total}")
        print(f"  {'Free (0%):':<25} {free_count}")
        print(f"  {'Dutiable (>0%):':<25} {dutiable_count}")
        print(f"  {'Unparsed rates:':<25} {unparsed_count}")
        if "rate_count" in summary:
            print(f"\n  RATE DISTRIBUTION ({summary['rate_count']} parseable rates)")
            print(f"  {'Min:':<25} {summary['rate_min']:.1f}%")
            print(f"  {'Max:':<25} {summary['rate_max']:.1f}%")
            print(f"  {'Median:':<25} {summary['rate_median']:.1f}%")
            print(f"  {'Mean:':<25} {summary['rate_mean']:.1f}%")
        pct_free = (free_count / total * 100) if total > 0 else 0
        pct_dut = (dutiable_count / total * 100) if total > 0 else 0
        print(f"\n  Free: {pct_free:.1f}%  |  Dutiable: {pct_dut:.1f}%")
        print()

    if export_fmt:
        _do_export(summary, f"hts_chapter_summary_{ch_str}", export_fmt)
    return summary


def cmd_high_duty(chapter, threshold=25.0, as_json=False, export_fmt=None):
    ch_str = str(chapter).zfill(2)
    print(f"\n  Fetching chapter {ch_str}, filtering >{threshold:.0f}% duty...")
    codes = _fetch_chapter(chapter)
    if not codes:
        print("  [no data]")
        return None

    high = []
    for c in codes:
        pct = _parse_rate(_safe_str(c, "general"))
        if pct is not None and pct > threshold:
            high.append(c)

    if not high:
        print(f"  [no codes above {threshold:.0f}% in chapter {ch_str}]")
        return None

    if as_json:
        print(json.dumps(high, indent=2, default=str))
    else:
        _display_rate_summary(high,
                              f"CHAPTER {ch_str} -- CODES ABOVE {threshold:.0f}% DUTY")
    if export_fmt:
        flat = [_flatten_code(c) for c in high]
        _do_export(flat, f"hts_high_duty_ch{ch_str}", export_fmt)
    return high


# --- Extended Commands: Chapter 99 Overlay Layer ----------------------------

def cmd_chapter99(as_json=False, export_fmt=None):
    """Curated Chapter 99 subchapter registry. Shows each policy regime
    (Section 232, 301, reciprocal, IEEPA, safeguards) and its HTS prefix.
    Use cmd_chapter99_subchapter for the actual line-level data."""
    if as_json:
        print(json.dumps(CHAPTER99_SUBCHAPTERS, indent=2, default=str))
        return CHAPTER99_SUBCHAPTERS

    print(f"\n  CHAPTER 99 OVERLAY REGISTRY ({len(CHAPTER99_SUBCHAPTERS)} subchapters)")
    print("  " + "=" * 95)
    print(f"  {'Prefix':<10} {'Regime':<28} {'Typical Overlay':<22} {'Label'}")
    print(f"  {'-'*10} {'-'*28} {'-'*22} {'-'*30}")
    for prefix, info in CHAPTER99_SUBCHAPTERS.items():
        regime = _truncate(info.get("regime", ""), 28)
        overlay = _truncate(info.get("typical_overlay", ""), 22)
        label = _truncate(info.get("label", ""), 30)
        print(f"  {prefix:<10} {regime:<28} {overlay:<22} {label}")
    print()

    if export_fmt:
        rows = [{
            "prefix": p,
            "regime": info.get("regime", ""),
            "typical_overlay": info.get("typical_overlay", ""),
            "label": info.get("label", ""),
        } for p, info in CHAPTER99_SUBCHAPTERS.items()]
        _do_export(rows, "hts_chapter99_registry", export_fmt)
    return CHAPTER99_SUBCHAPTERS


def cmd_chapter99_subchapter(prefix, as_json=False, export_fmt=None):
    """Pull all lines under a specific Chapter 99 subchapter (e.g. 9903.88)."""
    p = prefix if prefix.startswith("9903.") else f"9903.{prefix.lstrip('0')}"
    parts = p.split(".")
    if len(parts) < 2:
        print(f"  [invalid prefix: {prefix}. Use e.g. 9903.88]")
        return None
    sub = parts[1]
    print(f"\n  Fetching Chapter 99 subchapter 9903.{sub}...")
    codes = _fetch_export_range(f"9903.{sub}", f"9903.{sub}.99")
    if not codes:
        print(f"  [no data for 9903.{sub}]")
        return None

    info = CHAPTER99_SUBCHAPTERS.get(f"9903.{sub}", {})

    if as_json:
        print(json.dumps({"info": info, "codes": codes}, indent=2, default=str))
        return codes

    if info:
        print(f"\n  REGIME: {info.get('label','')}")
        print(f"  Overlay type: {info.get('regime','')}")
        print(f"  Typical: {info.get('typical_overlay','')}")

    print(f"\n  CHAPTER 99 SUBCHAPTER 9903.{sub} ({len(codes)} lines)")
    print("  " + "=" * 95)
    print(f"  {'HTS':<14} {'Overlay Rate':<40} {'Description'}")
    print(f"  {'-'*14} {'-'*40} {'-'*35}")
    for c in codes:
        hts = _safe_str(c, "htsno")[:14]
        overlay = _truncate(_safe_str(c, "general"), 40)
        desc = _truncate(_safe_str(c, "description"), 35)
        print(f"  {hts:<14} {overlay:<40} {desc}")
    print()

    if export_fmt:
        flat = [_flatten_code(c) for c in codes]
        _do_export(flat, f"hts_chapter99_{sub}", export_fmt)
    return codes


def cmd_overlay(hts_code, as_json=False, export_fmt=None):
    """Given a base HTS code, look up its base rate AND auto-resolve any
    Chapter 99 overlays referenced in footnotes. This gives the effective
    stacked duty (base + Section 232/301/reciprocal)."""
    print(f"\n  Resolving effective tariff for {hts_code}...")
    base = _fetch_search(hts_code)
    if not base:
        print(f"  [no base code matching {hts_code}]")
        return None

    base_exact = [c for c in base
                  if _safe_str(c, "htsno").replace(" ", "").startswith(
                      hts_code.replace(" ", ""))]
    target = base_exact[0] if base_exact else base[0]

    overlay_refs = _extract_overlay_refs(target.get("footnotes"))
    overlays = []
    for ref in overlay_refs[:10]:
        print(f"  Fetching overlay {ref}...")
        overlay_codes = _fetch_search(ref)
        time.sleep(0.3)
        match = None
        for oc in overlay_codes:
            if _safe_str(oc, "htsno") == ref:
                match = oc
                break
        if match is None and overlay_codes:
            match = overlay_codes[0]
        if match:
            classification = _classify_overlay(ref) or {}
            overlays.append({
                "ref": ref,
                "overlay_htsno": _safe_str(match, "htsno"),
                "overlay_description": _safe_str(match, "description"),
                "overlay_general": _safe_str(match, "general"),
                "regime": classification.get("regime", "Unknown"),
                "label": classification.get("label", ""),
            })

    result = {
        "base": _flatten_code(target),
        "base_general": _safe_str(target, "general"),
        "base_parsed_pct": _parse_rate(_safe_str(target, "general")),
        "overlay_references": overlay_refs,
        "overlays": overlays,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    print(f"\n  EFFECTIVE TARIFF: {hts_code}")
    print("  " + "=" * 90)
    print(f"  Base HTS:      {result['base']['htsno']}")
    print(f"  Description:   {_truncate(result['base']['description'], 75)}")
    print(f"  Base rate:     {result['base_general']}")
    if result["base_parsed_pct"] is not None:
        print(f"  Parsed %:      {result['base_parsed_pct']:.2f}%")

    if overlays:
        print(f"\n  OVERLAYS ({len(overlays)} Chapter 99 references)")
        print(f"  {'Ref':<14} {'Regime':<32} {'Overlay Rate'}")
        print(f"  {'-'*14} {'-'*32} {'-'*40}")
        for ov in overlays:
            ref = ov["ref"]
            regime = _truncate(ov.get("regime", ""), 32)
            rate = _truncate(ov.get("overlay_general", ""), 40)
            print(f"  {ref:<14} {regime:<32} {rate}")
        print()
        print("  NOTE: Effective stacked duty = base rate applied first, then")
        print("        each 9903.xx overlay added as per its general column.")
    else:
        print(f"\n  No Chapter 99 overlays referenced in footnotes.")
    print()

    if export_fmt:
        export_rows = [result["base"]]
        for ov in overlays:
            export_rows.append({
                "htsno": ov.get("overlay_htsno", ""),
                "description": ov.get("overlay_description", ""),
                "general": ov.get("overlay_general", ""),
                "superior": "",
                "indent": "",
                "statistical_suffix": "",
                "special": "",
                "other": "",
                "unit1": "",
                "unit2": "",
                "units": "",
                "footnotes": f"overlay for {result['base']['htsno']}",
                "footnote_refs": ov.get("ref", ""),
                "quota_quantity": "",
                "additional_duties": "",
            })
        _do_export(export_rows,
                   f"hts_overlay_{hts_code.replace('.', '')}", export_fmt)
    return result


def cmd_release_diff(release_a=None, release_b=None, chapter=None,
                     as_json=False, export_fmt=None):
    """Compare two HTS releases for a chapter. Returns changes in general rate.
    Usage: cmd_release_diff('2025HTSRev5', '2026HTSRev1', chapter=72)"""
    releases = _fetch_releases()
    release_names = []
    for r in releases:
        if isinstance(r, dict):
            release_names.append(r.get("name", r.get("release", "")))
        else:
            release_names.append(str(r))

    if release_a is None or release_b is None:
        if len(release_names) < 2:
            print("  [need at least 2 releases to diff]")
            return None
        release_b = release_names[0]
        release_a = release_names[1]
        print(f"  Defaulting to latest two: {release_a} vs {release_b}")

    if chapter is None:
        print("  [chapter required]")
        return None

    ch = int(chapter)
    hts_from = f"{ch:02d}00"
    hts_to = f"{ch:02d}99"

    print(f"\n  Fetching chapter {ch:02d} in release '{release_a}'...")
    data_a = _request(f"{BASE_URL}/exportList",
                      params={"from": hts_from, "to": hts_to,
                              "format": "JSON", "styles": "false",
                              "release": release_a})
    time.sleep(0.5)
    print(f"  Fetching chapter {ch:02d} in release '{release_b}'...")
    data_b = _request(f"{BASE_URL}/exportList",
                      params={"from": hts_from, "to": hts_to,
                              "format": "JSON", "styles": "false",
                              "release": release_b})

    if not data_a or not data_b:
        print("  [could not fetch one or both releases]")
        return None

    codes_a = data_a if isinstance(data_a, list) else data_a.get("results", [])
    codes_b = data_b if isinstance(data_b, list) else data_b.get("results", [])

    index_a = {_safe_str(c, "htsno"): c for c in codes_a}
    index_b = {_safe_str(c, "htsno"): c for c in codes_b}

    added = []
    removed = []
    rate_changes = []

    for hts, c in index_b.items():
        if hts not in index_a:
            added.append(c)
        else:
            gen_a = _safe_str(index_a[hts], "general")
            gen_b = _safe_str(c, "general")
            if gen_a != gen_b:
                rate_changes.append({
                    "htsno": hts,
                    "description": _safe_str(c, "description"),
                    "general_before": gen_a,
                    "general_after": gen_b,
                })

    for hts, c in index_a.items():
        if hts not in index_b:
            removed.append(c)

    result = {
        "release_a": release_a,
        "release_b": release_b,
        "chapter": ch,
        "total_a": len(codes_a),
        "total_b": len(codes_b),
        "added": len(added),
        "removed": len(removed),
        "rate_changes": len(rate_changes),
        "added_codes": [_flatten_code(c) for c in added[:50]],
        "removed_codes": [_flatten_code(c) for c in removed[:50]],
        "rate_change_list": rate_changes[:100],
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return result

    print(f"\n  RELEASE DIFF: chapter {ch:02d}")
    print("  " + "=" * 80)
    print(f"  Release A:    {release_a}   ({len(codes_a)} codes)")
    print(f"  Release B:    {release_b}   ({len(codes_b)} codes)")
    print(f"  Added lines:  {len(added)}")
    print(f"  Removed:      {len(removed)}")
    print(f"  Rate changes: {len(rate_changes)}")

    if rate_changes:
        print(f"\n  RATE CHANGES (first 20)")
        print(f"  {'HTS':<14} {'Before':<20} {'After':<20} {'Description'}")
        print(f"  {'-'*14} {'-'*20} {'-'*20} {'-'*35}")
        for rc in rate_changes[:20]:
            print(f"  {rc['htsno']:<14} {_truncate(rc['general_before'],20):<20} "
                  f"{_truncate(rc['general_after'],20):<20} "
                  f"{_truncate(rc['description'],35)}")
        if len(rate_changes) > 20:
            print(f"    ... and {len(rate_changes) - 20} more")

    if added:
        print(f"\n  ADDED LINES (first 10)")
        for c in added[:10]:
            print(f"    + {_safe_str(c,'htsno'):<14} "
                  f"{_truncate(_safe_str(c,'description'),70)}")
    if removed:
        print(f"\n  REMOVED LINES (first 10)")
        for c in removed[:10]:
            print(f"    - {_safe_str(c,'htsno'):<14} "
                  f"{_truncate(_safe_str(c,'description'),70)}")
    print()

    if export_fmt:
        _do_export(rate_changes,
                   f"hts_diff_{ch:02d}_{release_a}_{release_b}", export_fmt)
    return result


def cmd_export(target, chapter=None, query=None,
               codes_list=None, sector=None, threshold=25.0, fmt="csv"):
    dispatch = {
        "lookup":          lambda: cmd_lookup(query or "", export_fmt=fmt),
        "search":          lambda: cmd_search(query or "", export_fmt=fmt),
        "chapter":         lambda: cmd_chapter(chapter or 72, export_fmt=fmt),
        "duty":            lambda: cmd_duty(query or "", export_fmt=fmt),
        "sector":          lambda: cmd_sector(sector or "steel_aluminum", export_fmt=fmt),
        "rate-check":      lambda: cmd_rate_check(codes_list or [], export_fmt=fmt),
        "chapter-summary": lambda: cmd_chapter_summary(chapter or 72, export_fmt=fmt),
        "high-duty":       lambda: cmd_high_duty(chapter or 72, threshold=threshold, export_fmt=fmt),
    }
    if target not in dispatch:
        print(f"  [unknown export target: {target}]")
        print(f"  Available: {', '.join(dispatch.keys())}")
        return
    dispatch[target]()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   USITC Harmonized Tariff Schedule -- HTS Client
  =====================================================

   LOOKUP
     1) lookup           Search HTS by number
     2) search           Search by description keywords
     3) chapter          All codes in a chapter
     4) releases         Available HTS schedule releases

   DUTY ANALYSIS
     5) duty             Duty detail for specific code
     6) rate-check       Batch rate check for multiple codes
     7) chapter-summary  Summary stats for a chapter
     8) high-duty        Codes above a duty threshold

   MACRO
     9) macro-sectors    Curated macro sector categories
    10) sector           Pull all codes for a macro sector
    11) tariff-actions   Major tariff actions reference

   CHAPTER 99 OVERLAYS
    12) chapter99        Chapter 99 subchapter registry (policy regimes)
    13) chapter99-sub    All lines in a Chapter 99 subchapter (e.g. 9903.88)
    14) overlay          Auto-resolve effective rate (base + overlays)

   VERSIONING
    15) release-diff     Compare two HTS releases for a chapter

   DATA
    16) export           Export data to CSV/JSON

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


def _i_lookup():
    query = _prompt("HTS number (prefix match)")
    if not query:
        return
    cmd_lookup(query)


def _i_search():
    query = _prompt("Description keywords")
    if not query:
        return
    cmd_search(query)


def _i_chapter():
    ch = _prompt("Chapter number (1-99)", "72")
    cmd_chapter(int(ch))


def _i_releases():
    cmd_releases()


def _i_duty():
    code = _prompt("HTS code")
    if not code:
        return
    cmd_duty(code)


def _i_rate_check():
    raw = _prompt("HTS codes (comma or space separated)")
    if not raw:
        return
    codes_list = [c.strip() for c in re.split(r"[,\s]+", raw) if c.strip()]
    cmd_rate_check(codes_list)


def _i_chapter_summary():
    ch = _prompt("Chapter number", "72")
    cmd_chapter_summary(int(ch))


def _i_high_duty():
    ch = _prompt("Chapter number", "72")
    threshold = _prompt("Duty threshold %", "25")
    cmd_high_duty(int(ch), threshold=float(threshold))


def _i_macro_sectors():
    cmd_macro_sectors()


def _i_sector():
    print(f"  Sectors: {', '.join(SECTOR_KEYS)}")
    sector = _prompt("Sector key", "steel_aluminum")
    cmd_sector(sector)


def _i_tariff_actions():
    cmd_tariff_actions()


def _i_chapter99():
    cmd_chapter99()


def _i_chapter99_sub():
    print(f"  Known prefixes: {', '.join(CHAPTER99_SUBCHAPTERS.keys())}")
    prefix = _prompt("Chapter 99 prefix (e.g. 9903.88)", "9903.88")
    cmd_chapter99_subchapter(prefix)


def _i_overlay():
    code = _prompt("Base HTS code (e.g. 7206.10.00)")
    if not code:
        return
    cmd_overlay(code)


def _i_release_diff():
    releases = _fetch_releases()
    names = [r.get("name", "") if isinstance(r, dict) else str(r)
             for r in releases][:6]
    print(f"  Recent releases: {', '.join(names)}")
    rel_a = _prompt("Release A (older)", names[1] if len(names) > 1 else "")
    rel_b = _prompt("Release B (newer)", names[0] if names else "")
    ch = _prompt("Chapter number", "72")
    cmd_release_diff(release_a=rel_a, release_b=rel_b, chapter=int(ch))


def _i_export():
    targets = ["lookup", "search", "chapter", "duty", "sector",
               "rate-check", "chapter-summary", "high-duty"]
    print(f"  Targets: {', '.join(targets)}")
    target = _prompt("Export target", "chapter")
    fmt = _prompt_choice("Format", ["csv", "json"], "csv")

    chapter = None
    query = None
    codes_list = None
    sector = None
    threshold = 25.0

    if target in ("chapter", "chapter-summary", "high-duty"):
        chapter = int(_prompt("Chapter number", "72"))
    if target in ("lookup", "search", "duty"):
        query = _prompt("Query / HTS code")
    if target == "rate-check":
        raw = _prompt("HTS codes (comma separated)")
        codes_list = [c.strip() for c in re.split(r"[,\s]+", raw) if c.strip()]
    if target == "sector":
        print(f"  Sectors: {', '.join(SECTOR_KEYS)}")
        sector = _prompt("Sector key", "steel_aluminum")
    if target == "high-duty":
        threshold = float(_prompt("Duty threshold %", "25"))

    cmd_export(target, chapter=chapter, query=query, codes_list=codes_list,
               sector=sector, threshold=threshold, fmt=fmt)


COMMAND_MAP = {
    "1":  _i_lookup,
    "2":  _i_search,
    "3":  _i_chapter,
    "4":  _i_releases,
    "5":  _i_duty,
    "6":  _i_rate_check,
    "7":  _i_chapter_summary,
    "8":  _i_high_duty,
    "9":  _i_macro_sectors,
    "10": _i_sector,
    "11": _i_tariff_actions,
    "12": _i_chapter99,
    "13": _i_chapter99_sub,
    "14": _i_overlay,
    "15": _i_release_diff,
    "16": _i_export,
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
            print("  Enter 1-16 or q to quit")


# --- Argparse -----------------------------------------------------------------

EXPORT_TARGETS = ["lookup", "search", "chapter", "duty", "sector",
                  "rate-check", "chapter-summary", "high-duty"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="tariffs.py",
        description="USITC Harmonized Tariff Schedule -- HTS Reststop Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("lookup", help="Search HTS by number")
    s.add_argument("query", help="HTS number (prefix match)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search by description keywords")
    s.add_argument("query", help="Description keywords")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("chapter", help="All codes in a chapter")
    s.add_argument("chapter", type=int, help="Chapter number (1-99)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("releases", help="Available HTS schedule releases")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("duty", help="Duty detail for a specific HTS code")
    s.add_argument("code", help="Full HTS code")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("macro-sectors", help="Curated macro sector categories")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("sector", help="Pull all codes for a macro sector")
    s.add_argument("sector", choices=SECTOR_KEYS, help="Sector key")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("tariff-actions", help="Major tariff actions reference")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("rate-check", help="Batch rate check for HTS codes")
    s.add_argument("codes", nargs="+", help="One or more HTS codes")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("chapter-summary", help="Summary stats for a chapter")
    s.add_argument("chapter", type=int, help="Chapter number")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("high-duty", help="Codes above a duty threshold")
    s.add_argument("chapter", type=int, help="Chapter number")
    s.add_argument("--threshold", type=float, default=25.0,
                   help="Duty %% threshold (default 25)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("export", help="Export data to CSV/JSON")
    s.add_argument("target", choices=EXPORT_TARGETS)
    s.add_argument("--chapter", type=int, help="Chapter number")
    s.add_argument("--query", help="Query string or HTS code")
    s.add_argument("--codes", nargs="+", help="HTS codes for rate-check")
    s.add_argument("--sector", choices=SECTOR_KEYS)
    s.add_argument("--threshold", type=float, default=25.0)
    s.add_argument("--format", choices=["csv", "json"], default="csv")

    # --- Extended: Chapter 99 Overlay Layer ---------------------------------
    s = sub.add_parser("chapter99",
                       help="Chapter 99 subchapter registry (Section 232/301/IEEPA regimes)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("chapter99-sub",
                       help="All lines in a Chapter 99 subchapter (e.g. 9903.88)")
    s.add_argument("prefix", help="Subchapter prefix (e.g. 9903.88)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("overlay",
                       help="Resolve effective tariff (base rate + Chapter 99 overlays)")
    s.add_argument("code", help="Base HTS code to resolve")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # --- Extended: Release Diff ---------------------------------------------
    s = sub.add_parser("release-diff",
                       help="Compare two HTS releases for a chapter")
    s.add_argument("--release-a", default=None,
                   help="Older release name (e.g. 2025HTSRev5)")
    s.add_argument("--release-b", default=None,
                   help="Newer release name (e.g. 2026HTSRev1)")
    s.add_argument("--chapter", type=int, required=True)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "lookup":
        cmd_lookup(args.query, as_json=j, export_fmt=exp)

    elif args.command == "search":
        cmd_search(args.query, as_json=j, export_fmt=exp)

    elif args.command == "chapter":
        cmd_chapter(args.chapter, as_json=j, export_fmt=exp)

    elif args.command == "releases":
        cmd_releases(as_json=j)

    elif args.command == "duty":
        cmd_duty(args.code, as_json=j, export_fmt=exp)

    elif args.command == "macro-sectors":
        cmd_macro_sectors(as_json=j)

    elif args.command == "sector":
        cmd_sector(args.sector, as_json=j, export_fmt=exp)

    elif args.command == "tariff-actions":
        cmd_tariff_actions(as_json=j)

    elif args.command == "rate-check":
        cmd_rate_check(args.codes, as_json=j, export_fmt=exp)

    elif args.command == "chapter-summary":
        cmd_chapter_summary(args.chapter, as_json=j, export_fmt=exp)

    elif args.command == "high-duty":
        cmd_high_duty(args.chapter, threshold=args.threshold,
                      as_json=j, export_fmt=exp)

    elif args.command == "export":
        cmd_export(args.target, chapter=args.chapter,
                   query=args.query, codes_list=args.codes,
                   sector=args.sector, threshold=args.threshold,
                   fmt=args.format)

    # --- Extended: Chapter 99 ----------------------------------------------
    elif args.command == "chapter99":
        cmd_chapter99(as_json=j, export_fmt=exp)
    elif args.command == "chapter99-sub":
        cmd_chapter99_subchapter(args.prefix, as_json=j, export_fmt=exp)
    elif args.command == "overlay":
        cmd_overlay(args.code, as_json=j, export_fmt=exp)
    elif args.command == "release-diff":
        cmd_release_diff(release_a=args.release_a,
                         release_b=args.release_b,
                         chapter=args.chapter,
                         as_json=j, export_fmt=exp)


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
