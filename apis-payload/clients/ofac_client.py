#!/usr/bin/env python3
"""
OFAC Sanctions -- SDN List Client

Single-script client for OFAC (Office of Foreign Assets Control) Specially
Designated Nationals (SDN) list. Downloads and parses SDN CSV files from the
US Treasury. Curated macro-relevant program groupings for Russia, China, Iran,
North Korea, terrorism, narcotics, Venezuela, and cyber sanctions. No auth
required -- data is publicly accessible static files.

Usage:
    python ofac.py                                        # interactive CLI
    python ofac.py download                               # download latest SDN files
    python ofac.py search "rosneft"                       # search entities by name
    python ofac.py entity 12345                           # detailed entity lookup
    python ofac.py country Russia                         # filter by country
    python ofac.py program SDGT                           # filter by program code
    python ofac.py programs                               # list all programs with counts
    python ofac.py types                                  # summary by entity type
    python ofac.py macro-programs                         # curated macro groupings
    python ofac.py stats                                  # full summary statistics
    python ofac.py geo-focus                              # geopolitical grouping counts
    python ofac.py vessels                                # vessel-only listing
    python ofac.py export --target search --term rosneft  # export filtered data
    python ofac.py search "bank" --json                   # JSON output
    python ofac.py programs --export json                 # export to file
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime

import requests


# --- Configuration ------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "PRISM-OFAC-SDN/1.0 (macro-sanctions-analysis)",
})

DOWNLOAD_URLS = {
    "sdn.csv": "https://www.treasury.gov/ofac/downloads/sdn.csv",
    "add.csv": "https://www.treasury.gov/ofac/downloads/add.csv",
    "alt.csv": "https://www.treasury.gov/ofac/downloads/alt.csv",
    "sdn_comments.csv": "https://www.treasury.gov/ofac/downloads/sdn_comments.csv",
    "cons_prim.csv": "https://www.treasury.gov/ofac/downloads/consolidated/cons_prim.csv",
}

SDN_COLUMNS = [
    "ent_num", "SDN_Name", "SDN_Type", "Program", "Title",
    "Call_Sign", "Vess_type", "Tonnage", "GRT", "Vess_flag",
    "Vess_owner", "Remarks",
]

ADD_COLUMNS = [
    "ent_num", "Add_Num", "Address", "City", "Country", "Add_Remarks",
]

ALT_COLUMNS = [
    "ent_num", "Alt_Num", "Alt_Type", "Alt_Name", "Alt_Remarks",
]

MACRO_PROGRAMS = {
    "russia": {
        "label": "Russia / Ukraine",
        "programs": ["UKRAINE-EO13661", "UKRAINE-EO13662", "UKRAINE-EO13685",
                     "RUSSIA-EO14024", "RUSSIA-EO14066", "RUSSIA-EO14068"],
    },
    "china": {
        "label": "China",
        "programs": ["CMIC-EO13959", "CHINA-EO13936", "NS-CMIC-EO13959",
                     "HONGKONG-EO13936"],
    },
    "iran": {
        "label": "Iran",
        "programs": ["IRAN", "IRAN-TRA", "IRAN-EO13846", "IRAN-EO13871",
                     "IFSR", "IRGC", "NPWMD"],
    },
    "north_korea": {
        "label": "North Korea",
        "programs": ["DPRK", "DPRK2", "DPRK3", "DPRK4"],
    },
    "terrorism": {
        "label": "Terrorism / SDGT",
        "programs": ["SDGT", "SDT", "FTO"],
    },
    "narcotics": {
        "label": "Narcotics",
        "programs": ["SDNT", "SDNTK"],
    },
    "venezuela": {
        "label": "Venezuela",
        "programs": ["VENEZUELA", "VENEZUELA-EO13850", "VENEZUELA-EO13884"],
    },
    "cyber": {
        "label": "Cyber",
        "programs": ["CYBER2", "CYBER-EO13694"],
    },
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)


# --- Download / Load ----------------------------------------------------------

_SDN_CACHE = None
_ADDR_CACHE = None
_ALT_CACHE = None


def _download_file(url, dest):
    resp = SESSION.get(url, stream=True, timeout=60)
    resp.raise_for_status()
    total = int(resp.headers.get("Content-Length", 0))
    downloaded = 0
    start = time.time()

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)
            downloaded += len(chunk)
            elapsed = time.time() - start
            if total > 0:
                pct = downloaded / total * 100
                rate = downloaded / elapsed if elapsed > 0 else 0
                print(f"\r  {os.path.basename(dest)}: {downloaded:,} / {total:,} bytes "
                      f"({pct:.1f}%) - {rate / 1024:.0f} KB/s", end="", flush=True)
            else:
                print(f"\r  {os.path.basename(dest)}: {downloaded:,} bytes downloaded", end="", flush=True)

    elapsed = time.time() - start
    print(f"\r  {os.path.basename(dest)}: {downloaded:,} bytes - done ({elapsed:.1f}s)" + " " * 20)

    last_mod = resp.headers.get("Last-Modified", "unknown")
    return {"file": os.path.basename(dest), "bytes": downloaded, "last_modified": last_mod}


def _ensure_data():
    sdn_path = os.path.join(DATA_DIR, "sdn.csv")
    if not os.path.exists(sdn_path):
        print("  SDN data not found locally. Downloading...")
        for fname in ["sdn.csv", "add.csv", "alt.csv"]:
            url = DOWNLOAD_URLS[fname]
            dest = os.path.join(DATA_DIR, fname)
            _download_file(url, dest)
        print()


def _clean_field(val):
    val = val.strip().strip('"').strip()
    if val == "-0-":
        return ""
    return val


def _split_programs(raw):
    raw = raw.strip()
    if not raw or raw == "-0-":
        return []
    raw = raw.strip("[]").strip()
    return [p.strip() for p in raw.split("] [") if p.strip()]


def _parse_csv_no_header(filepath, columns):
    rows = []
    if not os.path.exists(filepath):
        return rows
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for raw_row in reader:
            if not raw_row:
                continue
            first = raw_row[0].strip()
            if first == "-0-" and len(raw_row) == 1:
                continue
            cleaned = [_clean_field(c) for c in raw_row]
            if len(cleaned) < len(columns):
                cleaned.extend([""] * (len(columns) - len(cleaned)))
            row = {}
            for i, col in enumerate(columns):
                row[col] = cleaned[i] if i < len(cleaned) else ""
            if row.get("ent_num"):
                try:
                    row["ent_num"] = int(row["ent_num"])
                except ValueError:
                    pass
            rows.append(row)
    return rows


def _load_sdn():
    global _SDN_CACHE
    if _SDN_CACHE is not None:
        return _SDN_CACHE
    _ensure_data()
    path = os.path.join(DATA_DIR, "sdn.csv")
    _SDN_CACHE = _parse_csv_no_header(path, SDN_COLUMNS)
    return _SDN_CACHE


def _load_addresses():
    global _ADDR_CACHE
    if _ADDR_CACHE is not None:
        return _ADDR_CACHE
    _ensure_data()
    path = os.path.join(DATA_DIR, "add.csv")
    rows = _parse_csv_no_header(path, ADD_COLUMNS)
    _ADDR_CACHE = defaultdict(list)
    for r in rows:
        _ADDR_CACHE[r["ent_num"]].append(r)
    return _ADDR_CACHE


def _load_alt_names():
    global _ALT_CACHE
    if _ALT_CACHE is not None:
        return _ALT_CACHE
    _ensure_data()
    path = os.path.join(DATA_DIR, "alt.csv")
    rows = _parse_csv_no_header(path, ALT_COLUMNS)
    _ALT_CACHE = defaultdict(list)
    for r in rows:
        _ALT_CACHE[r["ent_num"]].append(r)
    return _ALT_CACHE


# --- Data Access --------------------------------------------------------------

def _get_entities():
    return _load_sdn()


def _get_addresses():
    return _load_addresses()


def _get_alt_names():
    return _load_alt_names()


# --- Search / Filter ----------------------------------------------------------

def _search_entities(term):
    entities = _get_entities()
    term_lower = term.lower()
    return [e for e in entities if term_lower in e.get("SDN_Name", "").lower()]


def _filter_by_program(program):
    entities = _get_entities()
    program_upper = program.upper()
    results = []
    for e in entities:
        progs = _split_programs(e.get("Program", ""))
        for p in progs:
            if program_upper in p.upper():
                results.append(e)
                break
    return results


def _filter_by_country(country):
    entities = _get_entities()
    addresses = _get_addresses()
    country_lower = country.lower()
    matching_ent_nums = set()
    for ent_num, addr_list in addresses.items():
        for addr in addr_list:
            if country_lower in addr.get("Country", "").lower():
                matching_ent_nums.add(ent_num)
                break
    return [e for e in entities if e.get("ent_num") in matching_ent_nums]


def _filter_by_type(entity_type):
    entities = _get_entities()
    type_lower = entity_type.lower()
    return [e for e in entities if e.get("SDN_Type", "").lower() == type_lower]


# --- Display Functions --------------------------------------------------------

def _display_entity_table(entities, title="RESULTS"):
    if not entities:
        print(f"\n  No entities found.\n")
        return

    print(f"\n  {title}")
    print("  " + "=" * 90)
    print(f"  {'EntNum':>8}  {'Name':<40} {'Type':<12} {'Program':<20} {'Title':<15}")
    print(f"  {'-'*8}  {'-'*40} {'-'*12} {'-'*20} {'-'*15}")

    for e in entities[:200]:
        ent = e.get("ent_num", "")
        name = e.get("SDN_Name", "")[:38]
        stype = e.get("SDN_Type", "") or ""
        stype = stype[:10]
        progs = _split_programs(e.get("Program", ""))
        prog = ", ".join(progs)[:18] if progs else ""
        title_f = e.get("Title", "")[:13]
        print(f"  {ent:>8}  {name:<40} {stype:<12} {prog:<20} {title_f:<15}")

    shown = min(len(entities), 200)
    print(f"\n  --- showing {shown} of {len(entities)} entities ---\n")


def _display_entity_detail(entity, addresses, alt_names):
    ent_num = entity.get("ent_num")
    print(f"\n  ENTITY DETAIL: {ent_num}")
    print("  " + "=" * 70)

    for col in SDN_COLUMNS:
        val = entity.get(col, "")
        if not val:
            continue
        if col == "Program":
            progs = _split_programs(val)
            print(f"  {col:<15} {', '.join(progs)}")
        else:
            print(f"  {col:<15} {val}")

    addr_list = addresses.get(ent_num, [])
    if addr_list:
        print(f"\n  ADDRESSES ({len(addr_list)})")
        print(f"  {'-'*60}")
        for a in addr_list:
            parts = [a.get("Address", ""), a.get("City", ""), a.get("Country", "")]
            full = ", ".join(p for p in parts if p)
            remarks = a.get("Add_Remarks", "")
            print(f"    {full}")
            if remarks:
                print(f"      Remarks: {remarks}")

    alt_list = alt_names.get(ent_num, [])
    if alt_list:
        print(f"\n  ALTERNATE NAMES ({len(alt_list)})")
        print(f"  {'-'*60}")
        for a in alt_list:
            atype = a.get("Alt_Type", "")
            aname = a.get("Alt_Name", "")
            print(f"    [{atype}] {aname}")

    print()


def _display_program_summary(program_counts):
    print(f"\n  SANCTIONS PROGRAMS ({len(program_counts)} unique)")
    print("  " + "=" * 60)
    print(f"  {'Program':<35} {'Entities':>10}")
    print(f"  {'-'*35} {'-'*10}")

    for prog, count in sorted(program_counts.items(), key=lambda x: -x[1]):
        print(f"  {prog:<35} {count:>10,}")

    total = sum(program_counts.values())
    print(f"  {'-'*35} {'-'*10}")
    print(f"  {'TOTAL designations':<35} {total:>10,}")
    print()


def _display_stats(stats):
    print(f"\n  SDN LIST STATISTICS")
    print("  " + "=" * 60)
    print(f"  Total entities:  {stats['total_entities']:>10,}")
    print()

    print(f"  BY TYPE")
    print(f"  {'-'*35} {'-'*10}")
    for t, c in sorted(stats["by_type"].items(), key=lambda x: -x[1]):
        print(f"  {t:<35} {c:>10,}")
    print()

    print(f"  TOP 10 PROGRAMS")
    print(f"  {'-'*35} {'-'*10}")
    for prog, count in stats["top_programs"][:10]:
        print(f"  {prog:<35} {count:>10,}")
    print()

    print(f"  TOP 10 COUNTRIES")
    print(f"  {'-'*35} {'-'*10}")
    for country, count in stats["top_countries"][:10]:
        print(f"  {country:<35} {count:>10,}")
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

def cmd_download(as_json=False, export_fmt=None):
    results = []
    files_to_get = ["sdn.csv", "add.csv", "alt.csv", "sdn_comments.csv"]
    print(f"\n  Downloading {len(files_to_get)} OFAC SDN files...\n")

    for fname in files_to_get:
        url = DOWNLOAD_URLS[fname]
        dest = os.path.join(DATA_DIR, fname)
        info = _download_file(url, dest)
        results.append(info)

    global _SDN_CACHE, _ADDR_CACHE, _ALT_CACHE
    _SDN_CACHE = None
    _ADDR_CACHE = None
    _ALT_CACHE = None

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print(f"\n  DOWNLOAD SUMMARY")
    print("  " + "=" * 60)
    print(f"  {'File':<25} {'Size':>12} {'Last-Modified':<25}")
    print(f"  {'-'*25} {'-'*12} {'-'*25}")
    for r in results:
        print(f"  {r['file']:<25} {r['bytes']:>12,} {r['last_modified']:<25}")
    print()

    if export_fmt:
        _do_export(results, "ofac_download", export_fmt)


def cmd_search(term=None, as_json=False, export_fmt=None):
    if not term:
        return

    print(f"\n  Searching for '{term}'...")
    matches = _search_entities(term)

    if as_json:
        print(json.dumps(matches, indent=2, default=str))
        return

    _display_entity_table(matches, f"SEARCH: '{term}'")

    if export_fmt:
        _do_export(matches, f"ofac_search_{term.replace(' ', '_')}", export_fmt)


def cmd_entity(ent_num=None, as_json=False, export_fmt=None):
    if ent_num is None:
        return

    try:
        ent_num = int(ent_num)
    except ValueError:
        print(f"  [invalid entity number: {ent_num}]")
        return

    entities = _get_entities()
    addresses = _get_addresses()
    alt_names = _get_alt_names()

    entity = None
    for e in entities:
        if e.get("ent_num") == ent_num:
            entity = e
            break

    if not entity:
        print(f"  [entity {ent_num} not found]")
        return

    if as_json:
        out = dict(entity)
        out["addresses"] = addresses.get(ent_num, [])
        out["alt_names"] = alt_names.get(ent_num, [])
        print(json.dumps(out, indent=2, default=str))
        return

    _display_entity_detail(entity, addresses, alt_names)

    if export_fmt:
        out = dict(entity)
        out["addresses"] = addresses.get(ent_num, [])
        out["alt_names"] = alt_names.get(ent_num, [])
        _do_export(out, f"ofac_entity_{ent_num}", export_fmt)


def cmd_country(country=None, as_json=False, export_fmt=None):
    if not country:
        return

    print(f"\n  Filtering by country: {country}...")
    matches = _filter_by_country(country)

    if as_json:
        print(json.dumps(matches, indent=2, default=str))
        return

    _display_entity_table(matches, f"COUNTRY: {country}")

    if export_fmt:
        _do_export(matches, f"ofac_country_{country.replace(' ', '_')}", export_fmt)


def cmd_program(program=None, as_json=False, export_fmt=None):
    if not program:
        return

    print(f"\n  Filtering by program: {program}...")
    matches = _filter_by_program(program)

    if as_json:
        print(json.dumps(matches, indent=2, default=str))
        return

    _display_entity_table(matches, f"PROGRAM: {program}")

    if export_fmt:
        _do_export(matches, f"ofac_program_{program}", export_fmt)


def cmd_programs(as_json=False, export_fmt=None):
    entities = _get_entities()
    program_counts = Counter()
    for e in entities:
        for p in _split_programs(e.get("Program", "")):
            program_counts[p] += 1

    if as_json:
        print(json.dumps(dict(program_counts.most_common()), indent=2))
        return

    _display_program_summary(dict(program_counts))

    if export_fmt:
        rows = [{"program": p, "count": c} for p, c in program_counts.most_common()]
        _do_export(rows, "ofac_programs", export_fmt)


def cmd_types(as_json=False, export_fmt=None):
    entities = _get_entities()
    type_counts = Counter()
    for e in entities:
        t = e.get("SDN_Type", "").strip()
        type_counts[t or "(unspecified)"] += 1

    if as_json:
        print(json.dumps(dict(type_counts.most_common()), indent=2))
        return

    print(f"\n  ENTITY TYPES")
    print("  " + "=" * 50)
    print(f"  {'Type':<25} {'Count':>10}")
    print(f"  {'-'*25} {'-'*10}")
    for t, c in type_counts.most_common():
        print(f"  {t:<25} {c:>10,}")
    total = sum(type_counts.values())
    print(f"  {'-'*25} {'-'*10}")
    print(f"  {'TOTAL':<25} {total:>10,}")
    print()

    if export_fmt:
        rows = [{"type": t, "count": c} for t, c in type_counts.most_common()]
        _do_export(rows, "ofac_types", export_fmt)


def cmd_macro_programs(as_json=False, export_fmt=None):
    if as_json:
        print(json.dumps(MACRO_PROGRAMS, indent=2))
        return

    print(f"\n  MACRO-RELEVANT SANCTIONS PROGRAMS")
    print("  " + "=" * 60)

    for key in MACRO_PROGRAMS:
        group = MACRO_PROGRAMS[key]
        label = group["label"]
        progs = group["programs"]
        print(f"\n  {label} [{key}]")
        print(f"  {'-' * len(label)}")
        for p in progs:
            print(f"    {p}")

    print()

    if export_fmt:
        rows = []
        for key, group in MACRO_PROGRAMS.items():
            for p in group["programs"]:
                rows.append({"group": key, "label": group["label"], "program": p})
        _do_export(rows, "ofac_macro_programs", export_fmt)


def cmd_stats(as_json=False, export_fmt=None):
    print("\n  Computing SDN statistics...")
    entities = _get_entities()
    addresses = _get_addresses()

    type_counts = Counter()
    program_counts = Counter()
    for e in entities:
        t = e.get("SDN_Type", "").strip()
        type_counts[t or "(unspecified)"] += 1
        for p in _split_programs(e.get("Program", "")):
            program_counts[p] += 1

    country_counts = Counter()
    for ent_num, addr_list in addresses.items():
        countries_seen = set()
        for addr in addr_list:
            c = addr.get("Country", "").strip()
            if c and c not in countries_seen:
                country_counts[c] += 1
                countries_seen.add(c)

    stats = {
        "total_entities": len(entities),
        "by_type": dict(type_counts.most_common()),
        "top_programs": program_counts.most_common(10),
        "top_countries": country_counts.most_common(10),
        "unique_programs": len(program_counts),
        "unique_countries": len(country_counts),
    }

    if as_json:
        json_safe = dict(stats)
        json_safe["top_programs"] = [{"program": p, "count": c} for p, c in stats["top_programs"]]
        json_safe["top_countries"] = [{"country": c, "count": n} for c, n in stats["top_countries"]]
        print(json.dumps(json_safe, indent=2))
        return

    _display_stats(stats)

    if export_fmt:
        json_safe = dict(stats)
        json_safe["top_programs"] = [{"program": p, "count": c} for p, c in stats["top_programs"]]
        json_safe["top_countries"] = [{"country": c, "count": n} for c, n in stats["top_countries"]]
        _do_export(json_safe, "ofac_stats", export_fmt)


def cmd_geo_focus(as_json=False, export_fmt=None):
    print("\n  Computing geopolitical focus areas...")
    entities = _get_entities()

    results = {}
    for key, group in MACRO_PROGRAMS.items():
        label = group["label"]
        progs = set(group["programs"])
        count = 0
        for e in entities:
            entity_progs = set(_split_programs(e.get("Program", "")))
            if progs.intersection(entity_progs):
                count += 1
        results[key] = {"label": label, "entity_count": count, "programs": list(progs)}

    if as_json:
        print(json.dumps(results, indent=2))
        return

    print(f"\n  GEOPOLITICAL FOCUS -- ENTITY COUNTS")
    print("  " + "=" * 60)
    print(f"  {'Region':<25} {'Entities':>10}  Programs")
    print(f"  {'-'*25} {'-'*10}  {'-'*30}")

    for key in MACRO_PROGRAMS:
        r = results[key]
        prog_str = ", ".join(sorted(r["programs"]))[:30]
        print(f"  {r['label']:<25} {r['entity_count']:>10,}  {prog_str}")

    total = sum(r["entity_count"] for r in results.values())
    print(f"  {'-'*25} {'-'*10}")
    print(f"  {'TOTAL (may overlap)':<25} {total:>10,}")
    print()

    if export_fmt:
        rows = [{"region": key, "label": r["label"], "entity_count": r["entity_count"]}
                for key, r in results.items()]
        _do_export(rows, "ofac_geo_focus", export_fmt)


def cmd_vessels(as_json=False, export_fmt=None):
    print("\n  Filtering vessels...")
    vessels = _filter_by_type("vessel")

    if as_json:
        print(json.dumps(vessels, indent=2, default=str))
        return

    if not vessels:
        print("  No vessels found.\n")
        return

    print(f"\n  VESSELS ({len(vessels)})")
    print("  " + "=" * 100)
    print(f"  {'EntNum':>8}  {'Name':<30} {'Flag':<15} {'Type':<15} "
          f"{'Tonnage':>10} {'Owner':<20}")
    print(f"  {'-'*8}  {'-'*30} {'-'*15} {'-'*15} {'-'*10} {'-'*20}")

    for v in vessels[:200]:
        ent = v.get("ent_num", "")
        name = v.get("SDN_Name", "")[:28]
        flag = v.get("Vess_flag", "")[:13]
        vtype = v.get("Vess_type", "")[:13]
        tonnage = v.get("Tonnage", "")[:8]
        owner = v.get("Vess_owner", "")[:18]
        print(f"  {ent:>8}  {name:<30} {flag:<15} {vtype:<15} {tonnage:>10} {owner:<20}")

    shown = min(len(vessels), 200)
    print(f"\n  --- showing {shown} of {len(vessels)} vessels ---\n")

    if export_fmt:
        _do_export(vessels, "ofac_vessels", export_fmt)


def cmd_export(target=None, fmt="json", term=None, ent_num=None,
               country=None, program=None):
    dispatch = {
        "search": lambda: cmd_search(term=term, export_fmt=fmt),
        "entity": lambda: cmd_entity(ent_num=ent_num, export_fmt=fmt),
        "country": lambda: cmd_country(country=country, export_fmt=fmt),
        "program": lambda: cmd_program(program=program, export_fmt=fmt),
        "programs": lambda: cmd_programs(export_fmt=fmt),
        "types": lambda: cmd_types(export_fmt=fmt),
        "macro-programs": lambda: cmd_macro_programs(export_fmt=fmt),
        "stats": lambda: cmd_stats(export_fmt=fmt),
        "geo-focus": lambda: cmd_geo_focus(export_fmt=fmt),
        "vessels": lambda: cmd_vessels(export_fmt=fmt),
    }

    fn = dispatch.get(target)
    if not fn:
        print(f"  [unknown export target: {target}]")
        print(f"  Available: {', '.join(sorted(dispatch.keys()))}")
        return
    fn()


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  ================================================
   OFAC Sanctions -- SDN List Client
  ================================================

   DATA
     1) download        Download latest SDN files
     2) search          Search entities by name
     3) entity          Detailed lookup by entity number

   FILTERS
     4) country         Filter by country
     5) program         Filter by sanctions program
     6) vessels         Vessel-only listing

   ANALYSIS
     7) programs        List all programs with counts
     8) types           Summary by entity type
     9) macro-programs  Curated macro program groupings
    10) stats           Full summary statistics
    11) geo-focus       Geopolitical grouping counts

   EXPORT
    12) export          Export filtered data

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


def _i_download():
    cmd_download()


def _i_search():
    term = _prompt("Search term")
    if not term:
        return
    cmd_search(term=term)


def _i_entity():
    ent_num = _prompt("Entity number")
    if not ent_num:
        return
    cmd_entity(ent_num=ent_num)


def _i_country():
    country = _prompt("Country name")
    if not country:
        return
    cmd_country(country=country)


def _i_program():
    program = _prompt("Program code (e.g. SDGT, IRAN)")
    if not program:
        return
    cmd_program(program=program)


def _i_vessels():
    cmd_vessels()


def _i_programs():
    cmd_programs()


def _i_types():
    cmd_types()


def _i_macro_programs():
    cmd_macro_programs()


def _i_stats():
    cmd_stats()


def _i_geo_focus():
    cmd_geo_focus()


def _i_export():
    targets = ["search", "entity", "country", "program", "programs",
               "types", "macro-programs", "stats", "geo-focus", "vessels"]
    print(f"  Targets: {', '.join(targets)}")
    target = _prompt("Command to export")
    fmt = _prompt_choice("Format", ["json", "csv"], "json")

    if target == "search":
        term = _prompt("Search term")
        cmd_search(term=term, export_fmt=fmt)
    elif target == "entity":
        ent_num = _prompt("Entity number")
        cmd_entity(ent_num=ent_num, export_fmt=fmt)
    elif target == "country":
        country = _prompt("Country name")
        cmd_country(country=country, export_fmt=fmt)
    elif target == "program":
        program = _prompt("Program code")
        cmd_program(program=program, export_fmt=fmt)
    elif target == "programs":
        cmd_programs(export_fmt=fmt)
    elif target == "types":
        cmd_types(export_fmt=fmt)
    elif target == "macro-programs":
        cmd_macro_programs(export_fmt=fmt)
    elif target == "stats":
        cmd_stats(export_fmt=fmt)
    elif target == "geo-focus":
        cmd_geo_focus(export_fmt=fmt)
    elif target == "vessels":
        cmd_vessels(export_fmt=fmt)
    else:
        print(f"  [unknown export target: {target}]")


COMMAND_MAP = {
    "1":  _i_download,
    "2":  _i_search,
    "3":  _i_entity,
    "4":  _i_country,
    "5":  _i_program,
    "6":  _i_vessels,
    "7":  _i_programs,
    "8":  _i_types,
    "9":  _i_macro_programs,
    "10": _i_stats,
    "11": _i_geo_focus,
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

EXPORT_TARGETS = ["search", "entity", "country", "program", "programs",
                  "types", "macro-programs", "stats", "geo-focus", "vessels"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="ofac.py",
        description="OFAC Sanctions -- SDN List Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("download", help="Download latest SDN files")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search entities by name")
    s.add_argument("term", help="Search term (case-insensitive)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("entity", help="Detailed entity lookup by number")
    s.add_argument("ent_num", help="Entity number")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("country", help="Filter entities by country")
    s.add_argument("country", help="Country name (substring match)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("program", help="Filter by sanctions program code")
    s.add_argument("program", help="Program code (e.g. SDGT, IRAN)")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("programs", help="List all programs with entity counts")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("types", help="Summary by entity type")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("macro-programs", help="Curated macro program groupings")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("stats", help="Full summary statistics")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("geo-focus", help="Geopolitical grouping entity counts")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("vessels", help="Vessel-only listing")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("export", help="Export filtered data")
    s.add_argument("target", choices=EXPORT_TARGETS)
    s.add_argument("--format", choices=["csv", "json"], default="json")
    s.add_argument("--term", help="Search term (for search target)")
    s.add_argument("--ent-num", help="Entity number (for entity target)")
    s.add_argument("--country", help="Country (for country target)")
    s.add_argument("--program", help="Program code (for program target)")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "download":
        cmd_download(as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(term=args.term, as_json=j, export_fmt=exp)
    elif args.command == "entity":
        cmd_entity(ent_num=args.ent_num, as_json=j, export_fmt=exp)
    elif args.command == "country":
        cmd_country(country=args.country, as_json=j, export_fmt=exp)
    elif args.command == "program":
        cmd_program(program=args.program, as_json=j, export_fmt=exp)
    elif args.command == "programs":
        cmd_programs(as_json=j, export_fmt=exp)
    elif args.command == "types":
        cmd_types(as_json=j, export_fmt=exp)
    elif args.command == "macro-programs":
        cmd_macro_programs(as_json=j, export_fmt=exp)
    elif args.command == "stats":
        cmd_stats(as_json=j, export_fmt=exp)
    elif args.command == "geo-focus":
        cmd_geo_focus(as_json=j, export_fmt=exp)
    elif args.command == "vessels":
        cmd_vessels(as_json=j, export_fmt=exp)
    elif args.command == "export":
        cmd_export(target=args.target, fmt=args.format,
                   term=args.term, ent_num=args.ent_num,
                   country=args.country, program=args.program)


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
