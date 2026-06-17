#!/usr/bin/env python3
"""
CFTC Commitments of Traders (COT) -- Positioning Data Client

Single-script client for CFTC COT data via Socrata API (publicreporting.cftc.gov).
Three report types: Legacy, Disaggregated, Traders in Financial Futures (TFF).
25 curated macro-relevant contracts across rates, FX, equity, energy, metals, ags.

Usage:
    python cftc.py                                # interactive CLI
    python cftc.py latest                         # latest week, all contracts
    python cftc.py latest --group rates           # latest week, rates only
    python cftc.py history UST_10Y --weeks 104    # 2-year history for 10Y
    python cftc.py crowding --years 3             # percentile rankings
    python cftc.py heatmap                        # full cross-asset table
    python cftc.py macro-scan                     # comprehensive positioning scan
    python cftc.py search "crude"                 # search contracts by name
    python cftc.py contracts                      # list curated registry
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta

import requests


# ─── API Configuration ────────────────────────────────────────────────────────

BASE_URL = "https://publicreporting.cftc.gov/resource"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

DATASETS = {
    "tff_fut":      "gpe5-46if",
    "tff_combo":    "yw9f-hn96",
    "disagg_fut":   "72hh-3qpy",
    "disagg_combo": "kh3c-gbw2",
    "legacy_fut":   "6dca-aqww",
    "legacy_combo": "jun7-fc8e",
}


# ─── Curated Contract Registry ────────────────────────────────────────────────
# 25 macro-relevant contracts across 6 asset groups.
# 'report' determines which dataset to query: 'tff' for financials, 'disagg' for physicals.

CONTRACT_REGISTRY = {
    "UST_2Y":     {"code": "042601", "report": "tff",    "group": "rates",  "name": "UST 2-Year"},
    "UST_5Y":     {"code": "044601", "report": "tff",    "group": "rates",  "name": "UST 5-Year"},
    "UST_10Y":    {"code": "043602", "report": "tff",    "group": "rates",  "name": "UST 10-Year"},
    "UST_30Y":    {"code": "020601", "report": "tff",    "group": "rates",  "name": "UST 30-Year Bond"},
    "UST_ULTRA":  {"code": "020604", "report": "tff",    "group": "rates",  "name": "Ultra Bond"},
    "SOFR_3M":    {"code": "134741", "report": "tff",    "group": "rates",  "name": "SOFR 3-Month"},
    "EUR_USD":    {"code": "099741", "report": "tff",    "group": "fx",     "name": "Euro FX"},
    "JPY_USD":    {"code": "097741", "report": "tff",    "group": "fx",     "name": "Japanese Yen"},
    "GBP_USD":    {"code": "096742", "report": "tff",    "group": "fx",     "name": "British Pound"},
    "AUD_USD":    {"code": "232741", "report": "tff",    "group": "fx",     "name": "Australian Dollar"},
    "CAD_USD":    {"code": "090741", "report": "tff",    "group": "fx",     "name": "Canadian Dollar"},
    "MXN_USD":    {"code": "095741", "report": "tff",    "group": "fx",     "name": "Mexican Peso"},
    "CHF_USD":    {"code": "092741", "report": "tff",    "group": "fx",     "name": "Swiss Franc"},
    "NZD_USD":    {"code": "112741", "report": "tff",    "group": "fx",     "name": "New Zealand Dollar"},
    "SP500":      {"code": "13874A", "report": "tff",    "group": "equity", "name": "E-mini S&P 500"},
    "NASDAQ":     {"code": "209742", "report": "tff",    "group": "equity", "name": "E-mini Nasdaq 100"},
    "VIX":        {"code": "1170E1", "report": "tff",    "group": "equity", "name": "VIX Futures"},
    "CRUDE_WTI":  {"code": "067651", "report": "disagg", "group": "energy", "name": "Crude Oil WTI"},
    "NATGAS":     {"code": "023651", "report": "disagg", "group": "energy", "name": "Natural Gas"},
    "GOLD":       {"code": "088691", "report": "disagg", "group": "metals", "name": "Gold"},
    "SILVER":     {"code": "084691", "report": "disagg", "group": "metals", "name": "Silver"},
    "COPPER":     {"code": "085692", "report": "disagg", "group": "metals", "name": "Copper"},
    "CORN":       {"code": "002602", "report": "disagg", "group": "ags",    "name": "Corn"},
    "SOYBEANS":   {"code": "005602", "report": "disagg", "group": "ags",    "name": "Soybeans"},
    "WHEAT_SRW":  {"code": "001602", "report": "disagg", "group": "ags",    "name": "Wheat SRW"},
}

GROUP_ORDER = ["rates", "fx", "equity", "energy", "metals", "ags"]
GROUP_NAMES = {
    "rates":  "RATES",
    "fx":     "FX",
    "equity": "EQUITY INDICES",
    "energy": "ENERGY",
    "metals": "METALS",
    "ags":    "AGRICULTURE",
}

# Unified field names -> actual Socrata column names per report type.
# Verified against live API responses April 2026. Naming is inconsistent across
# datasets (some have _all suffix, some don't; swap has double underscore for short/spread).

FIELD_MAP = {
    "tff": {
        "spec_long":      "lev_money_positions_long",
        "spec_short":     "lev_money_positions_short",
        "spec_spread":    "lev_money_positions_spread",
        "comm_long":      "dealer_positions_long_all",
        "comm_short":     "dealer_positions_short_all",
        "comm_spread":    "dealer_positions_spread_all",
        "asset_mgr_long": "asset_mgr_positions_long",
        "asset_mgr_short":"asset_mgr_positions_short",
        "other_long":     "other_rept_positions_long",
        "other_short":    "other_rept_positions_short",
        "oi":             "open_interest_all",
        "chg_spec_long":  "change_in_lev_money_long",
        "chg_spec_short": "change_in_lev_money_short",
        "chg_comm_long":  "change_in_dealer_long_all",
        "chg_comm_short": "change_in_dealer_short_all",
        "chg_oi":         "change_in_open_interest_all",
        "spec_label":     "Lev Money",
        "comm_label":     "Dealer",
    },
    "disagg": {
        "spec_long":      "m_money_positions_long_all",
        "spec_short":     "m_money_positions_short_all",
        "spec_spread":    "m_money_positions_spread",
        "comm_long":      "prod_merc_positions_long",
        "comm_short":     "prod_merc_positions_short",
        "swap_long":      "swap_positions_long_all",
        "swap_short":     "swap__positions_short_all",
        "other_long":     "other_rept_positions_long",
        "other_short":    "other_rept_positions_short",
        "oi":             "open_interest_all",
        "chg_spec_long":  "change_in_m_money_long_all",
        "chg_spec_short": "change_in_m_money_short_all",
        "chg_comm_long":  "change_in_prod_merc_long",
        "chg_comm_short": "change_in_prod_merc_short",
        "chg_oi":         "change_in_open_interest_all",
        "spec_label":     "Managed $",
        "comm_label":     "Prod/Merch",
    },
}


# ─── HTTP + Parsing ───────────────────────────────────────────────────────────

def _request(dataset_id, params=None, max_retries=3):
    url = f"{BASE_URL}/{dataset_id}.json"
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
                return []
            return r.json()
        except requests.exceptions.Timeout:
            print(f"  [timeout, attempt {attempt + 1}/{max_retries}]")
        except requests.exceptions.ConnectionError:
            print(f"  [connection error, attempt {attempt + 1}/{max_retries}]")
            time.sleep(2)
        except Exception as e:
            print(f"  [error: {e}]")
            return []
    print("  [max retries reached]")
    return []


def _safe_int(row, field, default=0):
    val = row.get(field)
    if val is None:
        return default
    try:
        return int(float(str(val).strip().replace(",", "")))
    except (ValueError, TypeError):
        return default


def _safe_float(row, field, default=0.0):
    val = row.get(field)
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


# ─── Positioning Calculations ─────────────────────────────────────────────────

def _net_spec(row, report_type):
    fm = FIELD_MAP[report_type]
    return _safe_int(row, fm["spec_long"]) - _safe_int(row, fm["spec_short"])


def _net_comm(row, report_type):
    fm = FIELD_MAP[report_type]
    return _safe_int(row, fm["comm_long"]) - _safe_int(row, fm["comm_short"])


def _chg_net_spec(row, report_type):
    fm = FIELD_MAP[report_type]
    return _safe_int(row, fm["chg_spec_long"]) - _safe_int(row, fm["chg_spec_short"])


def _chg_net_comm(row, report_type):
    fm = FIELD_MAP[report_type]
    return _safe_int(row, fm["chg_comm_long"]) - _safe_int(row, fm["chg_comm_short"])


def _get_oi(row, report_type):
    return _safe_int(row, FIELD_MAP[report_type]["oi"])


def _pct_oi(net, oi):
    if oi == 0:
        return 0.0
    return net / oi * 100


def _percentile_rank(value, series):
    if not series:
        return 50.0
    n = len(series)
    count_below = sum(1 for v in series if v < value)
    count_equal = sum(1 for v in series if v == value)
    return (count_below + 0.5 * count_equal) / n * 100


def _ordinal(n):
    n = int(n)
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _crowding_label(pctile):
    if pctile >= 90:
        return "EXTREME LONG"
    if pctile >= 75:
        return "LONG"
    if pctile <= 10:
        return "EXTREME SHORT"
    if pctile <= 25:
        return "SHORT"
    return ""


# ─── Display ──────────────────────────────────────────────────────────────────

def _fmt_num(n, sign=True):
    if sign:
        return f"{n:+,}"
    return f"{n:,}"


def _fmt_pct(p, sign=True):
    if sign:
        return f"{p:+.1f}%"
    return f"{p:.1f}%"


def _bar(pctile, width=20):
    filled = max(0, min(width, int(pctile / 100 * width)))
    return "\u2588" * filled + "\u2591" * (width - filled)


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


def _filter_contracts(group=None, groups=None):
    if group and group != "all":
        return {k: v for k, v in CONTRACT_REGISTRY.items() if v["group"] == group}
    if groups:
        return {k: v for k, v in CONTRACT_REGISTRY.items() if v["group"] in groups}
    return dict(CONTRACT_REGISTRY)


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


# ─── Data Fetchers ────────────────────────────────────────────────────────────

def _fetch_latest(contracts=None, quiet=False):
    if contracts is None:
        contracts = CONTRACT_REGISTRY

    by_report = {}
    for alias, info in contracts.items():
        by_report.setdefault(info["report"], {})[alias] = info

    results = {}
    for idx, (rtype, rcontracts) in enumerate(by_report.items()):
        dataset_id = DATASETS[f"{rtype}_fut"]
        codes = [info["code"] for info in rcontracts.values()]
        codes_str = ",".join(f"'{c}'" for c in codes)

        rows = _request(dataset_id, {
            "$where": f"cftc_contract_market_code IN ({codes_str})",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": len(codes) * 3,
        })

        code_to_alias = {info["code"]: a for a, info in rcontracts.items()}
        seen = set()
        for row in rows:
            code = row.get("cftc_contract_market_code", "").strip()
            if code in code_to_alias and code not in seen:
                seen.add(code)
                results[code_to_alias[code]] = row

        missing = [a for a in rcontracts if a not in results]
        if missing and not quiet:
            print(f"  Note: no data for {', '.join(missing)} in {rtype.upper()}")

        if idx < len(by_report) - 1:
            time.sleep(0.3)

    return results


def _fetch_history(alias, weeks=52):
    info = CONTRACT_REGISTRY.get(alias)
    if not info:
        print(f"  Unknown contract: {alias}")
        return []
    dataset_id = DATASETS[f"{info['report']}_fut"]
    return _request(dataset_id, {
        "$where": f"cftc_contract_market_code='{info['code']}'",
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": weeks,
    })


def _fetch_multi_history(contracts=None, weeks=156):
    if contracts is None:
        contracts = CONTRACT_REGISTRY

    by_report = {}
    for alias, info in contracts.items():
        by_report.setdefault(info["report"], {})[alias] = info

    results = {}
    for idx, (rtype, rcontracts) in enumerate(by_report.items()):
        dataset_id = DATASETS[f"{rtype}_fut"]
        codes = [info["code"] for info in rcontracts.values()]
        codes_str = ",".join(f"'{c}'" for c in codes)
        start_date = (datetime.now() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")

        print(f"  Fetching {rtype.upper()} history ({len(codes)} contracts, ~{weeks} weeks)...")
        rows = _request(dataset_id, {
            "$where": f"cftc_contract_market_code IN ({codes_str}) AND report_date_as_yyyy_mm_dd >= '{start_date}'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 50000,
        })
        print(f"  Got {len(rows)} rows from {rtype.upper()}")

        code_to_alias = {info["code"]: a for a, info in rcontracts.items()}
        for row in rows:
            code = row.get("cftc_contract_market_code", "").strip()
            if code in code_to_alias:
                results.setdefault(code_to_alias[code], []).append(row)

        if idx < len(by_report) - 1:
            time.sleep(0.3)

    return results


# ─── Shared Display ───────────────────────────────────────────────────────────

def _build_summaries(data, contracts, history_data=None):
    summaries = []
    for grp in GROUP_ORDER:
        for alias in contracts:
            if contracts[alias]["group"] != grp or alias not in data:
                continue
            info = CONTRACT_REGISTRY[alias]
            rtype = info["report"]
            row = data[alias]

            net = _net_spec(row, rtype)
            chg = _chg_net_spec(row, rtype)
            oi = _get_oi(row, rtype)
            pct = _pct_oi(net, oi)
            net_c = _net_comm(row, rtype)
            chg_c = _chg_net_comm(row, rtype)

            pctile = 50.0
            if history_data and alias in history_data:
                hist_nets = [_net_spec(r, rtype) for r in history_data[alias]]
                if hist_nets:
                    pctile = _percentile_rank(net, hist_nets)

            summaries.append({
                "alias": alias, "name": info["name"], "group": info["group"],
                "report": rtype,
                "date": _parse_date(row.get("report_date_as_yyyy_mm_dd", "")),
                "oi": oi, "net_spec": net, "chg_spec": chg, "pct_oi": pct,
                "net_comm": net_c, "chg_comm": chg_c, "pctile": pctile,
                "label": _crowding_label(pctile),
            })
    return summaries


def _display_table(summaries, mode="latest", title=None):
    if not summaries:
        print("  No data to display.")
        return

    report_date = max(s["date"] for s in summaries) if summaries else "unknown"
    header = title or "CFTC COT Positioning"
    print(f"\n  {header} (as of {report_date})")
    print("  " + "=" * 85)

    if mode == "crowding":
        hdr = f"  {'Contract':<18} {'Net Spec':>11} {'Chg 1w':>10} {'% OI':>7} {'%ile':>5}  {'':20}  {'Signal'}"
        sep = f"  {'-'*18} {'-'*11} {'-'*10} {'-'*7} {'-'*5}  {'-'*20}  {'-'*14}"
    elif mode == "divergence":
        hdr = f"  {'Contract':<18} {'Spec Net':>11} {'Comm Net':>11} {'Spec Chg':>10} {'Comm Chg':>10}  {'Signal'}"
        sep = f"  {'-'*18} {'-'*11} {'-'*11} {'-'*10} {'-'*10}  {'-'*18}"
    elif mode == "changes":
        hdr = f"  {'Contract':<18} {'Spec Chg':>10} {'Comm Chg':>10} {'OI Chg':>10} {'Net Spec':>11} {'Net Comm':>11}"
        sep = f"  {'-'*18} {'-'*10} {'-'*10} {'-'*10} {'-'*11} {'-'*11}"
    else:
        hdr = f"  {'Contract':<18} {'Net Spec':>11} {'Chg 1w':>10} {'% OI':>7} {'OI':>12}"
        sep = f"  {'-'*18} {'-'*11} {'-'*10} {'-'*7} {'-'*12}"

    current_group = None
    for s in summaries:
        if s["group"] != current_group:
            current_group = s["group"]
            print(f"\n  {GROUP_NAMES.get(current_group, current_group)}")
            print(hdr)
            print(sep)

        if mode == "crowding":
            print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {_fmt_num(s['chg_spec']):>10} "
                  f"{_fmt_pct(s['pct_oi']):>7} {s['pctile']:>4.0f}%  {_bar(s['pctile']):20}  {s['label']}")
        elif mode == "divergence":
            if s["net_spec"] > 0 and s["net_comm"] < 0:
                sig = "Spec L / Comm S"
            elif s["net_spec"] < 0 and s["net_comm"] > 0:
                sig = "Spec S / Comm L"
            else:
                sig = "Aligned"
            print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {_fmt_num(s['net_comm']):>11} "
                  f"{_fmt_num(s['chg_spec']):>10} {_fmt_num(s['chg_comm']):>10}  {sig}")
        elif mode == "changes":
            chg_oi = _safe_int(data_ref.get(s["alias"], {}), FIELD_MAP[s["report"]]["chg_oi"]) if "data_ref" in dir() else 0
            print(f"  {s['name']:<18} {_fmt_num(s['chg_spec']):>10} {_fmt_num(s['chg_comm']):>10} "
                  f"{'':>10} {_fmt_num(s['net_spec']):>11} {_fmt_num(s['net_comm']):>11}")
        else:
            print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {_fmt_num(s['chg_spec']):>10} "
                  f"{_fmt_pct(s['pct_oi']):>7} {_fmt_num(s['oi'], sign=False):>12}")

    print()


def _display_signals(summaries):
    signals = [s for s in summaries if s["label"]]
    if not signals:
        return
    print("  KEY SIGNALS")
    print("  " + "-" * 70)
    for s in signals:
        direction = "short" if "SHORT" in s["label"] else "long"
        risk = "crowded, reversal risk" if "EXTREME" in s["label"] else "building"
        print(f"  - {s['name']}: {s['label']} ({s['pctile']:.0f}th %ile, {_fmt_num(s['net_spec'])} net spec) -- {risk}")
    print()


# ─── Command Functions ────────────────────────────────────────────────────────

def cmd_latest(group=None, as_json=False, export_fmt=None):
    contracts = _filter_contracts(group)
    print("\n  Fetching latest positioning...")
    data = _fetch_latest(contracts)
    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, contracts)

    if as_json:
        out = {s["alias"]: {k: v for k, v in s.items()} for s in summaries}
        print(json.dumps(out, indent=2, default=str))
        return out

    _display_table(summaries, mode="latest", title="CFTC COT -- Latest Positioning")

    if export_fmt:
        _do_export(summaries, "cftc_latest", export_fmt)
    return summaries


def cmd_history(alias, weeks=52, as_json=False, export_fmt=None):
    alias = alias.upper()
    if alias not in CONTRACT_REGISTRY:
        print(f"  Unknown contract '{alias}'. Use 'contracts' to see available aliases.")
        return

    info = CONTRACT_REGISTRY[alias]
    rtype = info["report"]
    print(f"\n  Fetching {weeks}-week history for {info['name']}...")
    rows = _fetch_history(alias, weeks)

    if not rows:
        print("  No data returned.")
        return

    if as_json:
        out = []
        for row in rows:
            out.append({
                "date": _parse_date(row.get("report_date_as_yyyy_mm_dd", "")),
                "oi": _get_oi(row, rtype),
                "net_spec": _net_spec(row, rtype),
                "chg_spec": _chg_net_spec(row, rtype),
                "net_comm": _net_comm(row, rtype),
                "pct_oi": round(_pct_oi(_net_spec(row, rtype), _get_oi(row, rtype)), 2),
            })
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  {info['name']} -- Positioning History ({len(rows)} weeks)")
    print("  " + "=" * 72)
    print(f"  {'Date':<12} {'OI':>12} {'Net Spec':>11} {'Chg 1w':>10} {'Net Comm':>11} {'% OI':>7}")
    print(f"  {'-'*12} {'-'*12} {'-'*11} {'-'*10} {'-'*11} {'-'*7}")

    for row in rows:
        date = _parse_date(row.get("report_date_as_yyyy_mm_dd", ""))
        oi = _get_oi(row, rtype)
        net = _net_spec(row, rtype)
        chg = _chg_net_spec(row, rtype)
        net_c = _net_comm(row, rtype)
        pct = _pct_oi(net, oi)
        print(f"  {date:<12} {_fmt_num(oi, sign=False):>12} {_fmt_num(net):>11} {_fmt_num(chg):>10} "
              f"{_fmt_num(net_c):>11} {_fmt_pct(pct):>7}")

    # Summary stats
    nets = [_net_spec(r, rtype) for r in rows]
    if nets:
        pctile = _percentile_rank(nets[0], nets)
        print(f"\n  Range: {min(nets):+,} to {max(nets):+,}  |  Current %ile: "
              f"{_ordinal(pctile)}  |  Mean: {sum(nets)//len(nets):+,}")

    print()
    if export_fmt:
        out = [{"date": _parse_date(r.get("report_date_as_yyyy_mm_dd", "")),
                "oi": _get_oi(r, rtype), "net_spec": _net_spec(r, rtype),
                "chg_spec": _chg_net_spec(r, rtype), "net_comm": _net_comm(r, rtype)}
               for r in rows]
        _do_export(out, f"cftc_history_{alias}", export_fmt)
    return rows


def cmd_crowding(group=None, years=3, as_json=False, export_fmt=None):
    contracts = _filter_contracts(group)
    weeks = years * 52
    print(f"\n  Computing crowding indicators ({years}Y history, {len(contracts)} contracts)...")

    data = _fetch_latest(contracts, quiet=True)
    time.sleep(0.3)
    history = _fetch_multi_history(contracts, weeks=weeks)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, contracts, history_data=history)

    if as_json:
        out = {s["alias"]: {k: v for k, v in s.items()} for s in summaries}
        print(json.dumps(out, indent=2, default=str))
        return out

    _display_table(summaries, mode="crowding", title=f"CFTC COT -- Crowding ({years}Y History)")
    _display_signals(summaries)

    if export_fmt:
        _do_export(summaries, "cftc_crowding", export_fmt)
    return summaries


def cmd_heatmap(as_json=False, export_fmt=None):
    print("\n  Building full positioning heatmap...")
    data = _fetch_latest(quiet=True)
    time.sleep(0.3)
    history = _fetch_multi_history(weeks=156)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, CONTRACT_REGISTRY, history_data=history)

    if as_json:
        out = {s["alias"]: s for s in summaries}
        print(json.dumps(out, indent=2, default=str))
        return out

    _display_table(summaries, mode="crowding", title="CFTC COT -- Positioning Heatmap")
    _display_signals(summaries)

    if export_fmt:
        _do_export(summaries, "cftc_heatmap", export_fmt)
    return summaries


def cmd_changes(group=None, as_json=False):
    contracts = _filter_contracts(group)
    print("\n  Fetching weekly position changes...")
    data = _fetch_latest(contracts)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, contracts)
    summaries.sort(key=lambda s: abs(s["chg_spec"]), reverse=True)

    if as_json:
        print(json.dumps({s["alias"]: s for s in summaries}, indent=2, default=str))
        return summaries

    dates = {s["date"] for s in summaries}
    report_date = max(dates) if dates else "unknown"
    print(f"\n  CFTC COT -- Weekly Changes (as of {report_date})")
    print("  " + "=" * 78)
    print(f"  {'Contract':<18} {'Spec Chg':>10} {'Comm Chg':>10} {'Net Spec':>11} {'Net Comm':>11} {'Direction'}")
    print(f"  {'-'*18} {'-'*10} {'-'*10} {'-'*11} {'-'*11} {'-'*12}")

    for s in summaries:
        if s["chg_spec"] > 0:
            direction = "adding long" if s["net_spec"] > 0 else "covering"
        elif s["chg_spec"] < 0:
            direction = "adding short" if s["net_spec"] < 0 else "cutting"
        else:
            direction = "flat"
        print(f"  {s['name']:<18} {_fmt_num(s['chg_spec']):>10} {_fmt_num(s['chg_comm']):>10} "
              f"{_fmt_num(s['net_spec']):>11} {_fmt_num(s['net_comm']):>11} {direction}")

    print()
    return summaries


def cmd_extremes(threshold=15, years=3, as_json=False):
    weeks = years * 52
    print(f"\n  Finding positioning extremes (>{100-threshold}th or <{threshold}th %ile, {years}Y)...")

    data = _fetch_latest(quiet=True)
    time.sleep(0.3)
    history = _fetch_multi_history(weeks=weeks)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, CONTRACT_REGISTRY, history_data=history)
    extremes = [s for s in summaries if s["pctile"] <= threshold or s["pctile"] >= (100 - threshold)]

    if not extremes:
        print(f"  No contracts at extremes (threshold: {threshold}th / {100-threshold}th %ile)")
        return

    if as_json:
        print(json.dumps({s["alias"]: s for s in extremes}, indent=2, default=str))
        return extremes

    print(f"\n  CFTC COT -- Positioning Extremes ({years}Y, threshold {threshold}%)")
    print("  " + "=" * 85)

    shorts = sorted([s for s in extremes if s["pctile"] <= threshold], key=lambda s: s["pctile"])
    longs = sorted([s for s in extremes if s["pctile"] >= (100 - threshold)], key=lambda s: -s["pctile"])

    if shorts:
        print("\n  CROWDED SHORTS (potential squeeze / reversal)")
        print(f"  {'Contract':<18} {'Net Spec':>11} {'%ile':>5}  {'':20}  {'Chg 1w':>10}")
        print(f"  {'-'*18} {'-'*11} {'-'*5}  {'-'*20}  {'-'*10}")
        for s in shorts:
            print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {s['pctile']:>4.0f}%  "
                  f"{_bar(s['pctile']):20}  {_fmt_num(s['chg_spec']):>10}")

    if longs:
        print("\n  CROWDED LONGS (potential unwind)")
        print(f"  {'Contract':<18} {'Net Spec':>11} {'%ile':>5}  {'':20}  {'Chg 1w':>10}")
        print(f"  {'-'*18} {'-'*11} {'-'*5}  {'-'*20}  {'-'*10}")
        for s in longs:
            print(f"  {s['name']:<18} {_fmt_num(s['net_spec']):>11} {s['pctile']:>4.0f}%  "
                  f"{_bar(s['pctile']):20}  {_fmt_num(s['chg_spec']):>10}")

    print()
    return extremes


def cmd_divergence(group=None, as_json=False):
    contracts = _filter_contracts(group)
    print("\n  Analyzing speculative vs commercial divergence...")
    data = _fetch_latest(contracts)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, contracts)

    if as_json:
        print(json.dumps({s["alias"]: s for s in summaries}, indent=2, default=str))
        return summaries

    _display_table(summaries, mode="divergence", title="CFTC COT -- Spec vs Commercial Divergence")

    divergent = [s for s in summaries if
                 (s["net_spec"] > 0 and s["net_comm"] < 0) or
                 (s["net_spec"] < 0 and s["net_comm"] > 0)]
    if divergent:
        print("  NOTABLE DIVERGENCES")
        print("  " + "-" * 70)
        for s in divergent:
            if s["net_spec"] < 0 and s["net_comm"] > 0:
                print(f"  - {s['name']}: Specs short but commercials long -- potential bullish fade signal")
            else:
                print(f"  - {s['name']}: Specs long but commercials short -- watch for unwind risk")
        print()

    return summaries


def cmd_dashboard(groups=None, as_json=False, export_fmt=None):
    contracts = _filter_contracts(groups=groups) if groups else CONTRACT_REGISTRY

    if groups:
        label = " + ".join(GROUP_NAMES.get(g, g) for g in groups)
    else:
        label = "Cross-Asset"

    print(f"\n  Building {label} positioning dashboard...")
    data = _fetch_latest(contracts, quiet=True)
    time.sleep(0.3)
    history = _fetch_multi_history(contracts, weeks=156)

    if not data:
        print("  No data returned.")
        return

    summaries = _build_summaries(data, contracts, history_data=history)

    if as_json:
        print(json.dumps({s["alias"]: s for s in summaries}, indent=2, default=str))
        return summaries

    _display_table(summaries, mode="crowding", title=f"CFTC COT -- {label} Dashboard")
    _display_signals(summaries)

    # Divergence section
    divergent = [s for s in summaries if
                 (s["net_spec"] > 0 and s["net_comm"] < 0) or
                 (s["net_spec"] < 0 and s["net_comm"] > 0)]
    if divergent:
        print("  SPEC vs COMMERCIAL DIVERGENCES")
        print("  " + "-" * 70)
        for s in divergent:
            arrow = "Specs S / Comms L" if s["net_spec"] < 0 else "Specs L / Comms S"
            print(f"  - {s['name']}: {arrow}  (Spec: {_fmt_num(s['net_spec'])}, Comm: {_fmt_num(s['net_comm'])})")
        print()

    if export_fmt:
        _do_export(summaries, f"cftc_dashboard", export_fmt)
    return summaries


def cmd_search(query=None, as_json=False):
    if not query:
        query = _prompt("Search contracts by name")
    if not query:
        return

    # Local registry matches
    local = [(a, info) for a, info in CONTRACT_REGISTRY.items()
             if query.lower() in info["name"].lower() or query.lower() in a.lower()]

    if not as_json:
        if local:
            print(f"\n  Curated contracts matching '{query}':")
            print(f"  {'Alias':<16} {'Name':<25} {'Group':<10} {'Report':<8} {'Code'}")
            print(f"  {'-'*16} {'-'*25} {'-'*10} {'-'*8} {'-'*10}")
            for alias, info in local:
                print(f"  {alias:<16} {info['name']:<25} {info['group']:<10} {info['report']:<8} {info['code']}")

    # API search across both datasets
    for ds_label, ds_id in [("TFF", DATASETS["tff_fut"]), ("Disaggregated", DATASETS["disagg_fut"])]:
        rows = _request(ds_id, {
            "$where": f"upper(market_and_exchange_names) LIKE '%{query.upper()}%'",
            "$order": "report_date_as_yyyy_mm_dd DESC",
            "$limit": 100,
            "$select": "cftc_contract_market_code, market_and_exchange_names, open_interest_all",
        })
        if not rows:
            continue

        seen = set()
        results = []
        for r in rows:
            code = r.get("cftc_contract_market_code", "").strip()
            if code not in seen:
                seen.add(code)
                results.append(r)

        if as_json:
            print(json.dumps(results, indent=2))
        else:
            print(f"\n  {ds_label} API matches for '{query}' ({len(results)} contracts):")
            print(f"  {'Code':<12} {'Name':<55} {'OI':>10}")
            print(f"  {'-'*12} {'-'*55} {'-'*10}")
            for r in results[:20]:
                code = r.get("cftc_contract_market_code", "").strip()
                name = r.get("market_and_exchange_names", "")[:55]
                oi = _safe_int(r, "open_interest_all")
                in_registry = " *" if any(info["code"] == code for info in CONTRACT_REGISTRY.values()) else ""
                print(f"  {code:<12} {name:<55} {oi:>10,}{in_registry}")
            if len(results) > 20:
                print(f"  ... and {len(results) - 20} more")

    print()


def cmd_contracts(group=None):
    contracts = _filter_contracts(group)
    print(f"\n  Curated Contract Registry ({len(contracts)} contracts)")
    print("  " + "=" * 72)

    current_group = None
    for alias, info in contracts.items():
        if info["group"] != current_group:
            current_group = info["group"]
            print(f"\n  {GROUP_NAMES.get(current_group, current_group)}")
            print(f"  {'Alias':<14} {'Name':<22} {'CFTC Code':<12} {'Report':<8} {'Exchange'}")
            print(f"  {'-'*14} {'-'*22} {'-'*12} {'-'*8} {'-'*10}")
        exchange = ""
        for ecode, elbl in [("CME", "CME"), ("CBOT", "CBOT"), ("NYME", "NYMEX"),
                             ("COME", "COMEX"), ("CFE", "CFE"), ("ICE", "ICE")]:
            if ecode in info.get("code", ""):
                exchange = elbl
                break
        print(f"  {alias:<14} {info['name']:<22} {info['code']:<12} {info['report']:<8}")

    print(f"\n  Usage: python cftc.py history <ALIAS> --weeks 52")
    print(f"  Example: python cftc.py history UST_10Y --weeks 104\n")


def cmd_export_data(alias=None, weeks=52, fmt="csv"):
    if alias:
        alias = alias.upper()
    if alias and alias not in CONTRACT_REGISTRY:
        print(f"  Unknown contract '{alias}'. Use 'contracts' to see aliases.")
        return
    if alias:
        print(f"\n  Exporting {weeks} weeks of {CONTRACT_REGISTRY[alias]['name']}...")
        rows = _fetch_history(alias, weeks)
        if rows:
            _do_export(rows, f"cftc_{alias}", fmt)
    else:
        print("\n  Exporting latest positioning for all contracts...")
        data = _fetch_latest()
        if data:
            out = []
            for a, row in data.items():
                row["_alias"] = a
                row["_name"] = CONTRACT_REGISTRY[a]["name"]
                out.append(row)
            _do_export(out, "cftc_all_latest", fmt)


def cmd_macro_scan(as_json=False, export_fmt=None):
    return cmd_dashboard(groups=None, as_json=as_json, export_fmt=export_fmt)


# ─── Interactive CLI ──────────────────────────────────────────────────────────

MENU = """
  =====================================================
   CFTC Commitments of Traders -- Positioning Client
  =====================================================

   POSITIONING
     1) latest         Latest week positioning
     2) history        Time series for one contract
     3) changes        Weekly position changes
     4) crowding       Percentile rank vs history

   ANALYSIS
     5) heatmap        Full cross-asset table + crowding
     6) extremes       Contracts at positioning extremes
     7) divergence     Commercial vs speculative divergence

   DASHBOARDS
     8) rates          Rates positioning dashboard
     9) fx             FX positioning dashboard
    10) commodities    Commodities dashboard
    11) macro-scan     Full cross-asset scan

   DATA
    12) search         Search contracts by name
    13) contracts      List curated contract registry
    14) export         Export raw data

   q) quit
"""


def _i_latest():
    group = _prompt_choice("Asset group", ["all"] + GROUP_ORDER, "all")
    cmd_latest(group=group if group != "all" else None)

def _i_history():
    alias = _prompt("Contract alias (e.g. UST_10Y, GOLD, EUR_USD)")
    weeks = _prompt("Number of weeks", "52")
    cmd_history(alias=alias, weeks=int(weeks))

def _i_changes():
    group = _prompt_choice("Asset group", ["all"] + GROUP_ORDER, "all")
    cmd_changes(group=group if group != "all" else None)

def _i_crowding():
    group = _prompt_choice("Asset group", ["all"] + GROUP_ORDER, "all")
    years = _prompt("History period in years", "3")
    cmd_crowding(group=group if group != "all" else None, years=int(years))

def _i_heatmap():
    cmd_heatmap()

def _i_extremes():
    threshold = _prompt("Percentile threshold", "15")
    years = _prompt("History years", "3")
    cmd_extremes(threshold=int(threshold), years=int(years))

def _i_divergence():
    group = _prompt_choice("Asset group", ["all"] + GROUP_ORDER, "all")
    cmd_divergence(group=group if group != "all" else None)

def _i_rates():
    cmd_dashboard(groups=["rates"])

def _i_fx():
    cmd_dashboard(groups=["fx"])

def _i_commodities():
    cmd_dashboard(groups=["energy", "metals", "ags"])

def _i_macro_scan():
    cmd_macro_scan()

def _i_search():
    cmd_search()

def _i_contracts():
    group = _prompt_choice("Asset group", ["all"] + GROUP_ORDER, "all")
    cmd_contracts(group=group if group != "all" else None)

def _i_export():
    mode = _prompt_choice("Export mode", ["contract", "all"], "all")
    fmt = _prompt_choice("Format", ["csv", "json"], "csv")
    if mode == "contract":
        alias = _prompt("Contract alias")
        weeks = _prompt("Number of weeks", "52")
        cmd_export_data(alias=alias, weeks=int(weeks), fmt=fmt)
    else:
        cmd_export_data(fmt=fmt)


COMMAND_MAP = {
    "1":  _i_latest,
    "2":  _i_history,
    "3":  _i_changes,
    "4":  _i_crowding,
    "5":  _i_heatmap,
    "6":  _i_extremes,
    "7":  _i_divergence,
    "8":  _i_rates,
    "9":  _i_fx,
    "10": _i_commodities,
    "11": _i_macro_scan,
    "12": _i_search,
    "13": _i_contracts,
    "14": _i_export,
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
            print("  Enter 1-14 or q to quit")


# ─── Argparse ─────────────────────────────────────────────────────────────────

VALID_GROUPS = ["all", "rates", "fx", "equity", "energy", "metals", "ags"]


def build_argparse():
    p = argparse.ArgumentParser(
        prog="cftc.py",
        description="CFTC Commitments of Traders -- Positioning Data Client",
    )
    sub = p.add_subparsers(dest="command")

    # latest
    s = sub.add_parser("latest", help="Latest week positioning")
    s.add_argument("--group", choices=VALID_GROUPS, default="all")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # history
    s = sub.add_parser("history", help="Time series for one contract")
    s.add_argument("contract", help="Contract alias (e.g. UST_10Y)")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # changes
    s = sub.add_parser("changes", help="Weekly position changes")
    s.add_argument("--group", choices=VALID_GROUPS, default="all")
    s.add_argument("--json", action="store_true")

    # crowding
    s = sub.add_parser("crowding", help="Percentile rank vs history")
    s.add_argument("--group", choices=VALID_GROUPS, default="all")
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # heatmap
    s = sub.add_parser("heatmap", help="Full cross-asset table + crowding")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # extremes
    s = sub.add_parser("extremes", help="Contracts at positioning extremes")
    s.add_argument("--threshold", type=int, default=15)
    s.add_argument("--years", type=int, default=3)
    s.add_argument("--json", action="store_true")

    # divergence
    s = sub.add_parser("divergence", help="Spec vs commercial divergence")
    s.add_argument("--group", choices=VALID_GROUPS, default="all")
    s.add_argument("--json", action="store_true")

    # dashboards
    s = sub.add_parser("rates", help="Rates positioning dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fx", help="FX positioning dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("commodities", help="Commodities positioning dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("macro-scan", help="Full cross-asset positioning scan")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # data
    s = sub.add_parser("search", help="Search contracts by name")
    s.add_argument("query", help="Search term")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("contracts", help="List curated contract registry")
    s.add_argument("--group", choices=VALID_GROUPS, default="all")

    s = sub.add_parser("export", help="Export raw data")
    s.add_argument("--contract", help="Contract alias (omit for all)")
    s.add_argument("--weeks", type=int, default=52)
    s.add_argument("--format", choices=["csv", "json"], default="csv")

    return p


def run_noninteractive(args):
    grp = getattr(args, "group", "all")
    grp = grp if grp != "all" else None
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)

    if args.command == "latest":
        cmd_latest(group=grp, as_json=j, export_fmt=exp)
    elif args.command == "history":
        cmd_history(alias=args.contract, weeks=args.weeks, as_json=j, export_fmt=exp)
    elif args.command == "changes":
        cmd_changes(group=grp, as_json=j)
    elif args.command == "crowding":
        cmd_crowding(group=grp, years=args.years, as_json=j, export_fmt=exp)
    elif args.command == "heatmap":
        cmd_heatmap(as_json=j, export_fmt=exp)
    elif args.command == "extremes":
        cmd_extremes(threshold=args.threshold, years=args.years, as_json=j)
    elif args.command == "divergence":
        cmd_divergence(group=grp, as_json=j)
    elif args.command == "rates":
        cmd_dashboard(groups=["rates"], as_json=j, export_fmt=exp)
    elif args.command == "fx":
        cmd_dashboard(groups=["fx"], as_json=j, export_fmt=exp)
    elif args.command == "commodities":
        cmd_dashboard(groups=["energy", "metals", "ags"], as_json=j, export_fmt=exp)
    elif args.command == "macro-scan":
        cmd_macro_scan(as_json=j, export_fmt=exp)
    elif args.command == "search":
        cmd_search(query=args.query, as_json=j)
    elif args.command == "contracts":
        cmd_contracts(group=grp)
    elif args.command == "export":
        cmd_export_data(alias=args.contract, weeks=args.weeks, fmt=args.format)


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
