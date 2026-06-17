#!/usr/bin/env python3
"""
Treasury International Capital (TIC) -- Cross-Border Capital Flows Client

Single-script client for the U.S. Treasury TIC system (ticdata.treasury.gov).
Covers foreign holdings of U.S. securities (Treasuries, agencies, corporates,
equities), U.S. holdings of foreign securities, gross cross-border flows,
and the Major Foreign Holders headline table. No auth required.

Usage:
    python tic.py                                   # interactive CLI
    python tic.py mfh                               # Major Foreign Holders table
    python tic.py mfh --top 10                      # top 10 holders only
    python tic.py holdings --country Japan           # Japan's holdings of all US LT secs
    python tic.py holdings --country China           # China mainland
    python tic.py tsy-holdings --country Japan       # Japan's Treasury holdings
    python tic.py flows --country Japan              # gross purchase/sale flows
    python tic.py country Japan                      # combined country profile
    python tic.py top-changes                        # biggest MoM movers
    python tic.py snapshot                           # cross-border capital dashboard
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from datetime import datetime

import requests


# --- Configuration -----------------------------------------------------------

BASE_URL = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents"

TIC_FILES = {
    "mfh":          "slt_table5.txt",
    "holdings":     "slt_table1.txt",
    "us_holdings":  "slt_table2.txt",
    "tsy_holdings": "slt_table3.txt",
    "flows":        "slt_table4.txt",
    "mfh_history":  "mfhhis01.txt",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PRISM-TIC-Client/1.0"})

REQUEST_DELAY = 0.3
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Countries that commonly appear with alternate names
COUNTRY_ALIASES = {
    "china": "China, Mainland",
    "china mainland": "China, Mainland",
    "prc": "China, Mainland",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "south korea": "Korea, South",
    "korea": "Korea, South",
    "uae": "United Arab Emirates",
    "hong kong": "Hong Kong",
    "hk": "Hong Kong",
    "taiwan": "Taiwan",
    "caymans": "Cayman Islands",
    "cayman": "Cayman Islands",
    "saudi": "Saudi Arabia",
    "ksa": "Saudi Arabia",
    "switzerland": "Switzerland",
    "swiss": "Switzerland",
    "lux": "Luxembourg",
    "sg": "Singapore",
    "norway": "Norway",
}


# --- HTTP + Parsing ----------------------------------------------------------

def _download(filename, max_retries=3):
    url = f"{BASE_URL}/{filename}"
    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, timeout=60)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                print(f"  [HTTP {r.status_code} for {filename}]")
                return None
            return r.text
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
    s = str(val).strip().replace(",", "")
    if not s or s.lower() in ("n.a.", "n/a", "na", "--", "..."):
        return default
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _fmt_billions(val, decimals=1):
    return f"${val:,.{decimals}f}B"


def _fmt_millions(val, decimals=0):
    if decimals > 0:
        return f"${val:,.{decimals}f}M"
    return f"${val:,.0f}M"


def _fmt_chg(val, unit="B"):
    if unit == "B":
        return f"{val:+,.1f}"
    return f"{val:+,.0f}"


def _prompt(msg, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        val = input(f"  {msg}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return str(default) if default is not None else ""
    return val if val else (str(default) if default is not None else "")


def _resolve_country(name):
    if not name:
        return name
    key = name.strip().lower()
    return COUNTRY_ALIASES.get(key, name.strip())


def _ts():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# --- Parsers -----------------------------------------------------------------

def _parse_mfh(raw):
    """Parse slt_table5.txt -- pivot table with Country rows, date columns, values in $B."""
    lines = raw.strip().split("\n")
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("Country\t"):
            header_idx = i
            break
    if header_idx is None:
        return [], []

    headers = lines[header_idx].split("\t")
    dates = [h.strip() for h in headers[1:] if h.strip()]
    rows = []
    for line in lines[header_idx + 1:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        country = parts[0].strip()
        if not country:
            continue
        values = {}
        for j, date in enumerate(dates):
            idx = j + 1
            if idx < len(parts):
                values[date] = _safe_float(parts[idx])
            else:
                values[date] = 0.0
        rows.append({"country": country, "holdings": values})

    return rows, dates


def _parse_long_table(raw):
    """Parse slt_table{1,2,3,4}.txt -- long-form with Country, Code, Date, metrics."""
    lines = raw.strip().split("\n")
    header_idx = None
    field_names_idx = None

    for i, line in enumerate(lines):
        if line.startswith("Country\tCountry Code\tDate"):
            header_idx = i
            break

    if header_idx is None:
        return [], []

    headers = lines[header_idx].split("\t")
    field_line = lines[header_idx + 1].split("\t") if header_idx + 1 < len(lines) else []

    metric_headers = [h.strip() for h in headers[3:] if h.strip()]
    metric_fields = [f.strip() for f in field_line[3:] if f.strip()]

    if len(metric_fields) >= len(metric_headers):
        col_names = metric_fields[:len(metric_headers)]
    else:
        col_names = metric_headers

    rows = []
    data_start = header_idx + 2 if field_line and field_line[0].strip() == "country" else header_idx + 1

    for line in lines[data_start:]:
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue

        country = parts[0].strip()
        code = parts[1].strip()
        date = parts[2].strip()

        if not country or not date:
            continue

        row = {"country": country, "country_code": code, "date": date}
        for k, col in enumerate(col_names):
            idx = k + 3
            if idx < len(parts):
                row[col] = _safe_float(parts[idx])
            else:
                row[col] = 0.0
        rows.append(row)

    return rows, col_names


def _filter_country(rows, country_name):
    """Filter parsed long-table rows by country name (fuzzy match)."""
    resolved = _resolve_country(country_name)
    lower = resolved.lower()
    return [r for r in rows if r["country"].lower() == lower
            or lower in r["country"].lower()]


def _filter_grand_total(rows):
    """Extract Grand Total rows from long-table data."""
    return [r for r in rows if r.get("country_code") == "99996"]


# --- Export ------------------------------------------------------------------

def _export_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    print(f"  Exported: {path}")


def _export_csv_rows(rows, path):
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
        _export_csv_rows(data, path)


def _prompt_export(data, prefix):
    choice = _prompt("Export? (json/csv/no)", "no")
    if choice in ("json", "csv"):
        _do_export(data, prefix, choice)


# --- Command: mfh -----------------------------------------------------------

def _log(msg, as_json=False):
    print(msg, file=sys.stderr if as_json else sys.stdout)


def cmd_mfh(top=None, as_json=False, export_fmt=None):
    """Major Foreign Holders of Treasury Securities."""
    _log("\n  Fetching Major Foreign Holders of Treasury Securities...", as_json)
    raw = _download(TIC_FILES["mfh"])
    if not raw:
        print("  No data returned.")
        return

    rows, dates = _parse_mfh(raw)
    if not rows:
        print("  Failed to parse MFH data.")
        return

    country_rows = [r for r in rows if r["country"] not in
                    ("Grand Total", "Of Which: Foreign Official",
                     "Of Which: Foreign Official Treasury Bills",
                     "Of Which: Foreign Official T-Bonds & Notes",
                     "All Other")]
    summary_rows = [r for r in rows if r["country"] in
                    ("Grand Total", "Of Which: Foreign Official", "All Other")]

    if top:
        country_rows = country_rows[:top]

    if as_json:
        out = []
        for r in country_rows:
            for date in dates:
                out.append({
                    "country": r["country"],
                    "date": date,
                    "holdings_billions": r["holdings"].get(date, 0.0),
                })
        print(json.dumps(out, indent=2))
        return out

    latest_date = dates[0] if dates else "?"
    prev_date = dates[1] if len(dates) > 1 else None

    print(f"\n  MAJOR FOREIGN HOLDERS OF U.S. TREASURY SECURITIES")
    print(f"  Latest data: {latest_date} (billions of dollars)")
    print("  " + "=" * 78)
    print(f"  {'#':<4} {'Country':<25} {'Latest':>10} {'Prior':>10} {'Chg':>10} {'YoY':>10}")
    print(f"  {'-'*4} {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*10}")

    for i, r in enumerate(country_rows):
        latest_val = r["holdings"].get(dates[0], 0.0) if dates else 0.0
        prior_val = r["holdings"].get(dates[1], 0.0) if len(dates) > 1 else 0.0
        yoy_val = r["holdings"].get(dates[-1], 0.0) if dates else 0.0
        mom_chg = latest_val - prior_val
        yoy_chg = latest_val - yoy_val

        print(f"  {i+1:<4} {r['country']:<25} {latest_val:>10.1f} {prior_val:>10.1f} "
              f"{mom_chg:>+10.1f} {yoy_chg:>+10.1f}")

    for r in summary_rows:
        latest_val = r["holdings"].get(dates[0], 0.0) if dates else 0.0
        prior_val = r["holdings"].get(dates[1], 0.0) if len(dates) > 1 else 0.0
        mom_chg = latest_val - prior_val
        label = r["country"]
        if label == "Grand Total":
            print(f"  {'-'*4} {'-'*25} {'-'*10} {'-'*10} {'-'*10}")
        print(f"  {'':4} {label:<25} {latest_val:>10.1f} {prior_val:>10.1f} "
              f"{mom_chg:>+10.1f}")

    # Official vs private breakdown
    grand = next((r for r in rows if r["country"] == "Grand Total"), None)
    official = next((r for r in rows if r["country"] == "Of Which: Foreign Official"), None)
    if grand and official and dates:
        gt = grand["holdings"].get(dates[0], 0.0)
        off = official["holdings"].get(dates[0], 0.0)
        priv = gt - off
        off_pct = (off / gt * 100) if gt > 0 else 0
        print(f"\n  Official: {_fmt_billions(off)} ({off_pct:.1f}%)  |  "
              f"Private: {_fmt_billions(priv)} ({100-off_pct:.1f}%)  |  "
              f"Total: {_fmt_billions(gt)}")

    print(f"\n  Date range in table: {dates[-1]} to {dates[0]} ({len(dates)} months)")
    print()

    if export_fmt:
        out = []
        for r in rows:
            for date in dates:
                out.append({
                    "country": r["country"],
                    "date": date,
                    "holdings_billions": r["holdings"].get(date, 0.0),
                })
        _do_export(out, "tic_mfh", export_fmt)
    return rows


# --- Command: holdings -------------------------------------------------------

def cmd_holdings(country=None, months=13, as_json=False, export_fmt=None):
    """Foreign holdings of U.S. long-term securities (table 1)."""
    _log("\n  Fetching foreign holdings of U.S. long-term securities...", as_json)
    raw = _download(TIC_FILES["holdings"])
    if not raw:
        print("  No data returned.")
        return

    rows, cols = _parse_long_table(raw)
    if not rows:
        print("  Failed to parse holdings data.")
        return

    if country:
        filtered = _filter_country(rows, country)
        if not filtered:
            print(f"  No data found for '{country}'.")
            return
        resolved_name = filtered[0]["country"]
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]
    else:
        filtered = _filter_grand_total(rows)
        resolved_name = "Grand Total (All Countries)"
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]

    if as_json:
        print(json.dumps(filtered, indent=2))
        return filtered

    print(f"\n  FOREIGN HOLDINGS OF U.S. LONG-TERM SECURITIES -- {resolved_name}")
    print(f"  Values in millions of dollars")
    print("  " + "=" * 100)
    print(f"  {'Date':<10} {'Total':>12} {'Treasuries':>12} {'Agencies':>12} "
          f"{'Corp Bonds':>12} {'Equities':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

    pos_keys = {
        "total": "for_lt_total_pos",
        "tsy": "for_lt_treas_pos",
        "agcy": "for_lt_agcy_pos",
        "corp": "for_lt_corp_pos",
        "eqty": "for_lt_eqty_pos",
    }

    for r in filtered:
        total = r.get(pos_keys["total"], 0)
        tsy = r.get(pos_keys["tsy"], 0)
        agcy = r.get(pos_keys["agcy"], 0)
        corp = r.get(pos_keys["corp"], 0)
        eqty = r.get(pos_keys["eqty"], 0)
        print(f"  {r['date']:<10} {total:>12,.0f} {tsy:>12,.0f} {agcy:>12,.0f} "
              f"{corp:>12,.0f} {eqty:>12,.0f}")

    if len(filtered) >= 2:
        latest = filtered[0]
        prior = filtered[1]
        chg = latest.get(pos_keys["total"], 0) - prior.get(pos_keys["total"], 0)
        print(f"\n  MoM change: {_fmt_chg(chg, 'M')}M")

    if len(filtered) >= 2:
        latest = filtered[0]
        oldest = filtered[-1]
        total_l = latest.get(pos_keys["total"], 0)
        total_o = oldest.get(pos_keys["total"], 0)
        if total_l > 0:
            tsy_pct = latest.get(pos_keys["tsy"], 0) / total_l * 100
            agcy_pct = latest.get(pos_keys["agcy"], 0) / total_l * 100
            corp_pct = latest.get(pos_keys["corp"], 0) / total_l * 100
            eqty_pct = latest.get(pos_keys["eqty"], 0) / total_l * 100
            print(f"  Composition: Treasuries {tsy_pct:.1f}% | Agencies {agcy_pct:.1f}% | "
                  f"Corp Bonds {corp_pct:.1f}% | Equities {eqty_pct:.1f}%")

    print()

    if export_fmt:
        _do_export(filtered, "tic_holdings", export_fmt)
    return filtered


# --- Command: tsy-holdings ---------------------------------------------------

def cmd_tsy_holdings(country=None, months=13, as_json=False, export_fmt=None):
    """Foreign holdings of U.S. Treasury securities (table 3)."""
    _log("\n  Fetching foreign holdings of U.S. Treasury securities...", as_json)
    raw = _download(TIC_FILES["tsy_holdings"])
    if not raw:
        print("  No data returned.")
        return

    rows, cols = _parse_long_table(raw)
    if not rows:
        print("  Failed to parse Treasury holdings data.")
        return

    if country:
        filtered = _filter_country(rows, country)
        if not filtered:
            print(f"  No data found for '{country}'.")
            return
        resolved_name = filtered[0]["country"]
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]
    else:
        filtered = _filter_grand_total(rows)
        resolved_name = "Grand Total (All Countries)"
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]

    if as_json:
        print(json.dumps(filtered, indent=2))
        return filtered

    print(f"\n  FOREIGN HOLDINGS OF U.S. TREASURY SECURITIES -- {resolved_name}")
    print(f"  Values in millions of dollars")
    print("  " + "=" * 95)
    print(f"  {'Date':<10} {'Total TSY':>12} {'Net Sales':>12} "
          f"{'LT TSY':>12} {'LT Net':>12} {'ST TSY':>12} {'ST Net':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

    for r in filtered:
        total = r.get("for_treas_pos", 0)
        total_net = r.get("for_treas_net", 0)
        lt = r.get("for_lt_treas_pos", 0)
        lt_net = r.get("for_lt_treas_net", 0)
        st = r.get("for_st_treas_pos", 0)
        st_net = r.get("for_st_treas_net", 0)
        print(f"  {r['date']:<10} {total:>12,.0f} {total_net:>+12,.0f} "
              f"{lt:>12,.0f} {lt_net:>+12,.0f} {st:>12,.0f} {st_net:>+12,.0f}")

    if len(filtered) >= 2:
        latest = filtered[0]
        prior = filtered[1]
        chg = latest.get("for_treas_pos", 0) - prior.get("for_treas_pos", 0)
        print(f"\n  MoM position change: {_fmt_chg(chg, 'M')}M")
        net = latest.get("for_treas_net", 0)
        print(f"  Net U.S. sales (latest month): {_fmt_chg(net, 'M')}M "
              f"({'buying' if net > 0 else 'selling'})")

    print()

    if export_fmt:
        _do_export(filtered, "tic_tsy_holdings", export_fmt)
    return filtered


# --- Command: flows ----------------------------------------------------------

def cmd_flows(country=None, months=13, as_json=False, export_fmt=None):
    """Gross U.S. purchases and sales of long-term securities (table 4)."""
    _log("\n  Fetching gross cross-border flows in long-term securities...", as_json)
    raw = _download(TIC_FILES["flows"])
    if not raw:
        print("  No data returned.")
        return

    rows, cols = _parse_long_table(raw)
    if not rows:
        print("  Failed to parse flows data.")
        return

    if country:
        filtered = _filter_country(rows, country)
        if not filtered:
            print(f"  No data found for '{country}'.")
            return
        resolved_name = filtered[0]["country"]
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]
    else:
        filtered = _filter_grand_total(rows)
        resolved_name = "Grand Total (All Countries)"
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]

    if as_json:
        print(json.dumps(filtered, indent=2))
        return filtered

    print(f"\n  GROSS CROSS-BORDER FLOWS -- {resolved_name}")
    print(f"  Values in millions of dollars")
    print("  " + "=" * 92)
    print(f"  {'Date':<10} {'US Sales':>12} {'US Purch':>12} {'Net':>12}  "
          f"{'For Sales':>12} {'For Purch':>12} {'Net':>12}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12}  {'-'*12} {'-'*12} {'-'*12}")

    for r in filtered:
        us_sale = r.get("for_lt_total_sale", 0)
        us_purch = r.get("for_lt_total_pur", 0)
        us_net = us_purch - us_sale
        for_sale = r.get("us_lt_total_sale", 0)
        for_purch = r.get("us_lt_total_pur", 0)
        for_net = for_purch - for_sale
        print(f"  {r['date']:<10} {us_sale:>12,.0f} {us_purch:>12,.0f} {us_net:>+12,.0f}  "
              f"{for_sale:>12,.0f} {for_purch:>12,.0f} {for_net:>+12,.0f}")

    print(f"\n  Left: Foreigners trading U.S. securities (Sales to / Purchases from foreigners)")
    print(f"  Right: U.S. residents trading foreign securities (Sales of / Purchases of foreign)")
    print()

    if export_fmt:
        _do_export(filtered, "tic_flows", export_fmt)
    return filtered


# --- Command: top-changes ---------------------------------------------------

def cmd_top_changes(n=15, as_json=False, export_fmt=None):
    """Biggest month-over-month changes in Treasury holdings."""
    _log("\n  Fetching Major Foreign Holders for change analysis...", as_json)
    raw = _download(TIC_FILES["mfh"])
    if not raw:
        print("  No data returned.")
        return

    rows, dates = _parse_mfh(raw)
    if not rows or len(dates) < 2:
        print("  Not enough data for change analysis.")
        return

    skip = {"Grand Total", "Of Which: Foreign Official",
            "Of Which: Foreign Official Treasury Bills",
            "Of Which: Foreign Official T-Bonds & Notes", "All Other"}
    country_rows = [r for r in rows if r["country"] not in skip]

    latest = dates[0]
    prior = dates[1]

    changes = []
    for r in country_rows:
        curr = r["holdings"].get(latest, 0)
        prev = r["holdings"].get(prior, 0)
        if curr == 0 and prev == 0:
            continue
        chg = curr - prev
        pct = (chg / prev * 100) if prev != 0 else 0
        changes.append({
            "country": r["country"],
            "latest": curr,
            "prior": prev,
            "change": chg,
            "pct_change": round(pct, 2),
        })

    changes.sort(key=lambda x: abs(x["change"]), reverse=True)
    top = changes[:n]

    if as_json:
        print(json.dumps(top, indent=2))
        return top

    print(f"\n  TOP {n} MONTH-OVER-MONTH CHANGES IN TREASURY HOLDINGS")
    print(f"  {prior} -> {latest} (billions of dollars)")
    print("  " + "=" * 75)
    print(f"  {'Country':<25} {'Prior':>10} {'Latest':>10} {'Change':>10} {'%Chg':>8}")
    print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")

    for c in top:
        print(f"  {c['country']:<25} {c['prior']:>10.1f} {c['latest']:>10.1f} "
              f"{c['change']:>+10.1f} {c['pct_change']:>+7.1f}%")

    buyers = [c for c in changes if c["change"] > 0]
    sellers = [c for c in changes if c["change"] < 0]
    total_buying = sum(c["change"] for c in buyers)
    total_selling = sum(c["change"] for c in sellers)

    print(f"\n  Net buying:  {len(buyers)} countries, {_fmt_chg(total_buying)}B total")
    print(f"  Net selling: {len(sellers)} countries, {_fmt_chg(total_selling)}B total")
    print(f"  Net flow:    {_fmt_chg(total_buying + total_selling)}B")
    print()

    if export_fmt:
        _do_export(changes, "tic_top_changes", export_fmt)
    return changes


# --- Command: country -------------------------------------------------------

def cmd_country(country_name, months=13, as_json=False, export_fmt=None):
    """Combined country profile across all TIC tables."""
    resolved = _resolve_country(country_name)
    _log(f"\n  Building TIC profile for: {resolved}", as_json)
    all_data = {}

    tables = [
        ("mfh", TIC_FILES["mfh"], "MFH"),
        ("holdings", TIC_FILES["holdings"], "Holdings (Table 1)"),
        ("tsy_holdings", TIC_FILES["tsy_holdings"], "Treasury Holdings (Table 3)"),
        ("flows", TIC_FILES["flows"], "Flows (Table 4)"),
    ]

    total = len(tables)
    for idx, (key, filename, label) in enumerate(tables):
        _log(f"  [{idx+1}/{total}] {label}...", as_json)
        raw = _download(filename)
        if raw:
            if key == "mfh":
                all_data[key] = _parse_mfh(raw)
            else:
                all_data[key] = _parse_long_table(raw)
        if idx < total - 1:
            time.sleep(REQUEST_DELAY)

    if as_json:
        out = {"country": resolved}
        if "mfh" in all_data:
            mfh_rows, mfh_dates = all_data["mfh"]
            match = [r for r in mfh_rows if resolved.lower() in r["country"].lower()]
            if match:
                out["mfh"] = match[0]
        for key in ("holdings", "tsy_holdings", "flows"):
            if key in all_data:
                rows, cols = all_data[key]
                filtered = _filter_country(rows, resolved)
                filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]
                out[key] = filtered
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  TIC COUNTRY PROFILE: {resolved}")
    print("  " + "=" * 80)

    # MFH section
    if "mfh" in all_data:
        mfh_rows, mfh_dates = all_data["mfh"]
        match = [r for r in mfh_rows if resolved.lower() in r["country"].lower()]
        if match:
            r = match[0]
            print(f"\n  TREASURY HOLDINGS (Major Foreign Holders)")
            print(f"  {'-'*60}")
            n_show = min(6, len(mfh_dates))
            header = "  " + "".join(f"{d:>12}" for d in mfh_dates[:n_show])
            print(header)
            vals = "  " + "".join(f"{r['holdings'].get(d, 0):>12.1f}" for d in mfh_dates[:n_show])
            print(vals)
            if len(mfh_dates) >= 2:
                latest = r["holdings"].get(mfh_dates[0], 0)
                prior = r["holdings"].get(mfh_dates[1], 0)
                oldest = r["holdings"].get(mfh_dates[-1], 0)
                print(f"  MoM: {_fmt_chg(latest - prior)}B  |  "
                      f"Period: {_fmt_chg(latest - oldest)}B ({len(mfh_dates)} months)")

    # Holdings section
    if "holdings" in all_data:
        rows, cols = all_data["holdings"]
        filtered = _filter_country(rows, resolved)
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:6]
        if filtered:
            print(f"\n  ALL U.S. LONG-TERM SECURITIES HELD ($M)")
            print(f"  {'-'*60}")
            print(f"  {'Date':<10} {'Total':>12} {'TSY':>10} {'Agency':>10} "
                  f"{'Corp':>10} {'Equity':>10}")
            for r in filtered:
                print(f"  {r['date']:<10} "
                      f"{r.get('for_lt_total_pos', 0):>12,.0f} "
                      f"{r.get('for_lt_treas_pos', 0):>10,.0f} "
                      f"{r.get('for_lt_agcy_pos', 0):>10,.0f} "
                      f"{r.get('for_lt_corp_pos', 0):>10,.0f} "
                      f"{r.get('for_lt_eqty_pos', 0):>10,.0f}")

    # Treasury holdings section
    if "tsy_holdings" in all_data:
        rows, cols = all_data["tsy_holdings"]
        filtered = _filter_country(rows, resolved)
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:6]
        if filtered:
            print(f"\n  U.S. TREASURY SECURITIES HELD ($M)")
            print(f"  {'-'*60}")
            print(f"  {'Date':<10} {'Total':>12} {'Net Sales':>12} "
                  f"{'LT':>10} {'ST':>10}")
            for r in filtered:
                print(f"  {r['date']:<10} "
                      f"{r.get('for_treas_pos', 0):>12,.0f} "
                      f"{r.get('for_treas_net', 0):>+12,.0f} "
                      f"{r.get('for_lt_treas_pos', 0):>10,.0f} "
                      f"{r.get('for_st_treas_pos', 0):>10,.0f}")

    # Flows section
    if "flows" in all_data:
        rows, cols = all_data["flows"]
        filtered = _filter_country(rows, resolved)
        filtered = sorted(filtered, key=lambda x: x["date"], reverse=True)[:6]
        if filtered:
            print(f"\n  GROSS FLOWS -- U.S. SECURITIES ($M)")
            print(f"  {'-'*60}")
            print(f"  {'Date':<10} {'Sales':>12} {'Purchases':>12} {'Net':>12}")
            for r in filtered:
                sale = r.get("for_lt_total_sale", 0)
                purch = r.get("for_lt_total_pur", 0)
                net = purch - sale
                print(f"  {r['date']:<10} {sale:>12,.0f} {purch:>12,.0f} {net:>+12,.0f}")

    print()

    if export_fmt:
        out = []
        if "holdings" in all_data:
            rows, _ = all_data["holdings"]
            filtered = _filter_country(rows, resolved)
            out = sorted(filtered, key=lambda x: x["date"], reverse=True)[:months]
        _do_export(out, f"tic_country_{resolved.replace(' ', '_').replace(',', '')}", export_fmt)
    return all_data


# --- Command: snapshot -------------------------------------------------------

def cmd_snapshot(as_json=False, export_fmt=None):
    """Cross-border capital flows dashboard."""
    _log("\n  Building TIC snapshot...", as_json)

    _log("  [1/3] Major Foreign Holders...", as_json)
    mfh_raw = _download(TIC_FILES["mfh"])
    time.sleep(REQUEST_DELAY)

    _log("  [2/3] Holdings by security type...", as_json)
    hold_raw = _download(TIC_FILES["holdings"])
    time.sleep(REQUEST_DELAY)

    _log("  [3/3] Treasury holdings detail...", as_json)
    tsy_raw = _download(TIC_FILES["tsy_holdings"])

    out = {}

    if mfh_raw:
        mfh_rows, mfh_dates = _parse_mfh(mfh_raw)
    else:
        mfh_rows, mfh_dates = [], []

    if hold_raw:
        hold_rows, hold_cols = _parse_long_table(hold_raw)
    else:
        hold_rows, hold_cols = [], []

    if tsy_raw:
        tsy_rows, tsy_cols = _parse_long_table(tsy_raw)
    else:
        tsy_rows, tsy_cols = [], []

    if as_json:
        out["mfh_latest"] = []
        skip_set = {"Grand Total", "Of Which: Foreign Official",
                    "Of Which: Foreign Official Treasury Bills",
                    "Of Which: Foreign Official T-Bonds & Notes", "All Other"}
        for r in mfh_rows:
            if r["country"] not in skip_set and mfh_dates:
                out["mfh_latest"].append({
                    "country": r["country"],
                    "holdings_bn": r["holdings"].get(mfh_dates[0], 0),
                })
        grand = next((r for r in mfh_rows if r["country"] == "Grand Total"), None)
        official = next((r for r in mfh_rows if r["country"] == "Of Which: Foreign Official"), None)
        if grand and mfh_dates:
            out["grand_total_bn"] = grand["holdings"].get(mfh_dates[0], 0)
        if official and mfh_dates:
            out["foreign_official_bn"] = official["holdings"].get(mfh_dates[0], 0)
        out["latest_date"] = mfh_dates[0] if mfh_dates else None
        print(json.dumps(out, indent=2))
        return out

    # Display dashboard
    print(f"\n  TREASURY INTERNATIONAL CAPITAL (TIC) -- SNAPSHOT")
    print("  " + "=" * 80)

    if mfh_rows and mfh_dates:
        latest = mfh_dates[0]
        prior = mfh_dates[1] if len(mfh_dates) > 1 else None

        grand = next((r for r in mfh_rows if r["country"] == "Grand Total"), None)
        official = next((r for r in mfh_rows if r["country"] == "Of Which: Foreign Official"), None)

        if grand:
            gt = grand["holdings"].get(latest, 0)
            gt_prev = grand["holdings"].get(prior, 0) if prior else 0
            off = official["holdings"].get(latest, 0) if official else 0
            priv = gt - off

            print(f"\n  HEADLINE (as of {latest})")
            print(f"  {'-'*50}")
            print(f"  Total Foreign Holdings of Treasuries: {_fmt_billions(gt)}")
            print(f"  Foreign Official:  {_fmt_billions(off)} ({off/gt*100:.1f}%)")
            print(f"  Foreign Private:   {_fmt_billions(priv)} ({priv/gt*100:.1f}%)")
            if prior:
                print(f"  MoM Change:        {_fmt_chg(gt - gt_prev)}B")

        skip = {"Grand Total", "Of Which: Foreign Official",
                "Of Which: Foreign Official Treasury Bills",
                "Of Which: Foreign Official T-Bonds & Notes", "All Other"}
        top10 = [r for r in mfh_rows if r["country"] not in skip][:10]

        print(f"\n  TOP 10 HOLDERS")
        print(f"  {'-'*50}")
        for i, r in enumerate(top10):
            val = r["holdings"].get(latest, 0)
            prev_val = r["holdings"].get(prior, 0) if prior else 0
            chg = val - prev_val
            print(f"  {i+1:>2}. {r['country']:<22} {_fmt_billions(val):>10}  "
                  f"({_fmt_chg(chg)}B MoM)")

    # Holdings composition (Grand Total from table 1)
    if hold_rows:
        gt_rows = _filter_grand_total(hold_rows)
        if gt_rows:
            latest_h = sorted(gt_rows, key=lambda x: x["date"], reverse=True)[0]
            total = latest_h.get("for_lt_total_pos", 0)
            tsy = latest_h.get("for_lt_treas_pos", 0)
            agcy = latest_h.get("for_lt_agcy_pos", 0)
            corp = latest_h.get("for_lt_corp_pos", 0)
            eqty = latest_h.get("for_lt_eqty_pos", 0)

            print(f"\n  U.S. LONG-TERM SECURITIES HELD BY FOREIGNERS (as of {latest_h['date']})")
            print(f"  {'-'*50}")
            print(f"  Total:       ${total/1e6:,.1f}T")
            if total > 0:
                print(f"  Treasuries:  ${tsy/1e6:,.1f}T ({tsy/total*100:.1f}%)")
                print(f"  Agencies:    ${agcy/1e6:,.1f}T ({agcy/total*100:.1f}%)")
                print(f"  Corp Bonds:  ${corp/1e6:,.1f}T ({corp/total*100:.1f}%)")
                print(f"  Equities:    ${eqty/1e6:,.1f}T ({eqty/total*100:.1f}%)")

    # Top movers from MFH
    if mfh_rows and len(mfh_dates) >= 2:
        latest = mfh_dates[0]
        prior = mfh_dates[1]
        skip = {"Grand Total", "Of Which: Foreign Official",
                "Of Which: Foreign Official Treasury Bills",
                "Of Which: Foreign Official T-Bonds & Notes", "All Other"}
        changes = []
        for r in mfh_rows:
            if r["country"] in skip:
                continue
            curr = r["holdings"].get(latest, 0)
            prev = r["holdings"].get(prior, 0)
            if curr == 0 and prev == 0:
                continue
            changes.append((r["country"], curr - prev))

        changes.sort(key=lambda x: x[1], reverse=True)
        top_buyers = changes[:5]
        top_sellers = changes[-5:]
        top_sellers.reverse()

        print(f"\n  BIGGEST MOVERS ({prior} -> {latest})")
        print(f"  {'-'*50}")
        print(f"  Top Buyers:")
        for name, chg in top_buyers:
            if chg > 0:
                print(f"    {name:<25} {_fmt_chg(chg)}B")
        print(f"  Top Sellers:")
        for name, chg in top_sellers:
            if chg < 0:
                print(f"    {name:<25} {_fmt_chg(chg)}B")

    print()

    if export_fmt:
        out_rows = []
        skip = {"Of Which: Foreign Official Treasury Bills",
                "Of Which: Foreign Official T-Bonds & Notes"}
        for r in mfh_rows:
            if r["country"] in skip:
                continue
            if mfh_dates:
                out_rows.append({
                    "country": r["country"],
                    "date": mfh_dates[0],
                    "holdings_bn": r["holdings"].get(mfh_dates[0], 0),
                })
        _do_export(out_rows, "tic_snapshot", export_fmt)
    return out


# --- Interactive CLI ---------------------------------------------------------

MENU = """
  =====================================================
   Treasury International Capital (TIC) System Client
   Source: ticdata.treasury.gov
  =====================================================

   HOLDINGS & POSITIONS
     1) mfh            Major Foreign Holders of Treasuries
     2) holdings        Foreign holdings of all U.S. LT securities
     3) tsy-holdings    Foreign holdings of U.S. Treasuries
     4) flows           Gross cross-border purchase/sale flows

   ANALYSIS
     5) top-changes     Biggest MoM movers in Treasury holdings
     6) country         Country-specific profile (all tables)

   DASHBOARD
     7) snapshot        Cross-border capital flows overview

   q) quit
"""


def _i_mfh():
    top = _prompt("Top N countries (or enter for all)", "")
    top = int(top) if top else None
    cmd_mfh(top=top)

def _i_holdings():
    country = _prompt("Country (or enter for Grand Total)", "")
    country = country if country else None
    months = int(_prompt("Months of history", "13"))
    cmd_holdings(country=country, months=months)

def _i_tsy_holdings():
    country = _prompt("Country (or enter for Grand Total)", "")
    country = country if country else None
    months = int(_prompt("Months of history", "13"))
    cmd_tsy_holdings(country=country, months=months)

def _i_flows():
    country = _prompt("Country (or enter for Grand Total)", "")
    country = country if country else None
    months = int(_prompt("Months of history", "13"))
    cmd_flows(country=country, months=months)

def _i_top_changes():
    n = int(_prompt("Number of top movers", "15"))
    cmd_top_changes(n=n)

def _i_country():
    country = _prompt("Country name")
    if country:
        months = int(_prompt("Months of history", "13"))
        cmd_country(country, months=months)

def _i_snapshot():
    cmd_snapshot()


COMMAND_MAP = {
    "1": _i_mfh,
    "2": _i_holdings,
    "3": _i_tsy_holdings,
    "4": _i_flows,
    "5": _i_top_changes,
    "6": _i_country,
    "7": _i_snapshot,
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
            print("  Enter 1-7 or q to quit")


# --- Argparse ----------------------------------------------------------------

def build_argparse():
    p = argparse.ArgumentParser(
        prog="tic.py",
        description="Treasury International Capital (TIC) -- Cross-Border Capital Flows Client",
    )
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("mfh", help="Major Foreign Holders of Treasury Securities")
    s.add_argument("--top", type=int, help="Show only top N holders")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("holdings", help="Foreign holdings of U.S. long-term securities")
    s.add_argument("--country", help="Country name (default: Grand Total)")
    s.add_argument("--months", type=int, default=13)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("tsy-holdings", help="Foreign holdings of U.S. Treasury securities")
    s.add_argument("--country", help="Country name (default: Grand Total)")
    s.add_argument("--months", type=int, default=13)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("flows", help="Gross cross-border purchase/sale flows")
    s.add_argument("--country", help="Country name (default: Grand Total)")
    s.add_argument("--months", type=int, default=13)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("top-changes", help="Biggest MoM changes in Treasury holdings")
    s.add_argument("--top", type=int, default=15, help="Number of movers to show")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("country", help="Country-specific profile across all tables")
    s.add_argument("name", help="Country name")
    s.add_argument("--months", type=int, default=13)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("snapshot", help="Cross-border capital flows dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "mfh":
        cmd_mfh(top=args.top, as_json=j, export_fmt=exp)
    elif args.command == "holdings":
        cmd_holdings(country=args.country, months=args.months, as_json=j, export_fmt=exp)
    elif args.command == "tsy-holdings":
        cmd_tsy_holdings(country=args.country, months=args.months, as_json=j, export_fmt=exp)
    elif args.command == "flows":
        cmd_flows(country=args.country, months=args.months, as_json=j, export_fmt=exp)
    elif args.command == "top-changes":
        cmd_top_changes(n=args.top, as_json=j, export_fmt=exp)
    elif args.command == "country":
        cmd_country(args.name, months=args.months, as_json=j, export_fmt=exp)
    elif args.command == "snapshot":
        cmd_snapshot(as_json=j, export_fmt=exp)


# --- Main --------------------------------------------------------------------

def main():
    parser = build_argparse()
    args = parser.parse_args()

    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
