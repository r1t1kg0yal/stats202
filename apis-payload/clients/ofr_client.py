#!/usr/bin/env python3
"""
OFR -- Office of Financial Research API Client (STFM + HFM + FSI)

Single-script client for the U.S. Treasury Office of Financial Research data
APIs. Covers the full public OFR universe:

  Short-term Funding Monitor (STFM):
    fnyr  -- NY Fed Reference Rates (SOFR/EFFR/OBFR/TGCR/BGCR + percentiles + volume)
    mmf   -- U.S. Money Market Fund Data Release (composition + repo + median yields)
    nypd  -- NY Fed Primary Dealer Statistics (positions, fails, repo)
    repo  -- U.S. Repo Markets Data Release (Tri-Party + GCF + DVP rates/volumes)
    tyld  -- Treasury Constant Maturity Rates (1Mo to 30Yr)

  Hedge Fund Monitor (HFM):
    fpf   -- SEC Form PF aggregates (gross/net assets, leverage, liquidity, stress tests)
    tff   -- CFTC Traders in Financial Futures (positioning by category)
    scoos -- Senior Credit Officer Opinion Survey on Dealer Financing Terms
    ficc  -- FICC Sponsored Repo Service Volumes

  OFR Financial Stress Index (FSI):
    Daily 33-variable global stress index with 5 component categories
    (credit, equity valuation, funding, safe assets, volatility) and
    3 region decompositions (US / Other AE / EM).

No auth required. No rate limit documented but polite ~0.2s spacing between calls.

Usage:
    python ofr.py                              # interactive CLI

    # --- Generic API ---
    python ofr.py datasets                     # all datasets across STFM + HFM
    python ofr.py mnemonics --dataset repo     # list all mnemonics in dataset
    python ofr.py search Outstanding           # search across all mnemonics
    python ofr.py query FNYR-SOFR-A            # series metadata
    python ofr.py series FNYR-SOFR-A --start 2025-01-01
    python ofr.py multi FNYR-SOFR-A FNYR-EFFR-A --start 2025-01-01
    python ofr.py spread REPO-GCF_AR_OO-P FNYR-SOFR-A --start 2025-01-01
    python ofr.py dataset-pull tyld --start 2025-01-01

    # --- Curated short-term funding ---
    python ofr.py repo-rates                   # Tri-Party + GCF + DVP overnight rates
    python ofr.py repo-volumes                 # outstanding volumes by segment
    python ofr.py repo-history --segment GCF --term OO --obs 60
    python ofr.py mmf                          # MMF holdings snapshot
    python ofr.py mmf-history --obs 24         # MMF investment history
    python ofr.py yields                       # full Treasury constant-maturity curve
    python ofr.py curve                        # curve with daily/weekly/monthly deltas
    python ofr.py fnyr                         # NY Fed reference rates with percentiles
    python ofr.py pd-financing                 # dealer SB / SL activity
    python ofr.py pd-fails                     # primary dealer fails to deliver/receive

    # --- Curated hedge fund / leverage ---
    python ofr.py form-pf                      # SEC Form PF latest aggregates
    python ofr.py form-pf-strategy             # by-strategy decomposition
    python ofr.py form-pf-stress               # stress test results across funds
    python ofr.py tff                          # CFTC TFF positioning by future
    python ofr.py scoos                        # SCOOS dealer survey
    python ofr.py ficc                         # FICC sponsored repo

    # --- Curated stress ---
    python ofr.py fsi                          # Financial Stress Index latest
    python ofr.py fsi-history --days 365       # FSI time series

    # --- Dashboards ---
    python ofr.py funding-snapshot             # rates + repo + MMF + spread
    python ofr.py stress-snapshot              # FSI + curve + funding
    python ofr.py hf-snapshot                  # hedge fund cross-source positioning
"""

import argparse
import csv
import io
import json
import os
import sys
import time
from collections import OrderedDict
from datetime import datetime, timedelta

import requests


# =============================================================================
# API CONFIGURATION
# =============================================================================

STFM_BASE = "https://data.financialresearch.gov/v1"
HFM_BASE = "https://data.financialresearch.gov/hf/v1"
FSI_CSV_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"

SESSION = requests.Session()
SESSION.headers.update({
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate",
    "User-Agent": "ofr-client/1.0 (research)",
})

REQUEST_DELAY = 0.15
DEFAULT_TIMEOUT = 30


# Dataset registry: which API base each dataset lives on
STFM_DATASETS = {
    "fnyr": {"long_name": "Federal Reserve Bank of New York Reference Rates",
             "short_name": "Reference Rates", "frequency": "Daily"},
    "mmf":  {"long_name": "OFR U.S. Money Market Fund Data Release",
             "short_name": "U.S. Money Market Funds", "frequency": "Monthly"},
    "nypd": {"long_name": "Federal Reserve Bank of New York Primary Dealer Statistics",
             "short_name": "Primary Dealer Statistics", "frequency": "Weekly"},
    "repo": {"long_name": "OFR U.S. Repo Markets Data Release",
             "short_name": "U.S. Repo Markets", "frequency": "Daily"},
    "tyld": {"long_name": "Treasury Constant Maturity Rates",
             "short_name": "Treasury Constant Maturity Rates", "frequency": "Daily"},
}

HFM_DATASETS = {
    "fpf":   {"long_name": "Hedge Fund Aggregates from SEC Form PF",
              "short_name": "SEC Form PF", "frequency": "Quarterly"},
    "tff":   {"long_name": "CFTC Traders in Financial Futures",
              "short_name": "CFTC TFF", "frequency": "Weekly"},
    "scoos": {"long_name": "Senior Credit Officer Opinion Survey on Dealer Financing Terms",
              "short_name": "SCOOS", "frequency": "Quarterly"},
    "ficc":  {"long_name": "FICC Sponsored Repo Service Volumes",
              "short_name": "FICC Sponsored Repo", "frequency": "Monthly"},
}

ALL_DATASETS = {**STFM_DATASETS, **HFM_DATASETS}


def _api_base(dataset):
    """Return the correct API base URL for a given dataset key."""
    if dataset in STFM_DATASETS:
        return STFM_BASE
    if dataset in HFM_DATASETS:
        return HFM_BASE
    raise ValueError(f"Unknown dataset '{dataset}'. "
                     f"Valid: {sorted(ALL_DATASETS.keys())}")


def _api_base_for_mnemonic(mnemonic):
    """Infer API base from a mnemonic prefix."""
    prefix = mnemonic.split("-", 1)[0].lower()
    if prefix in STFM_DATASETS:
        return STFM_BASE
    if prefix in HFM_DATASETS:
        return HFM_BASE
    # Try both -- some mnemonics don't follow strict prefix convention
    return STFM_BASE


# =============================================================================
# CURATED MNEMONIC CATALOGS (the macro-relevant series)
# =============================================================================

# Reference rates -- these are the OFR mnemonics for NY Fed rates
FNYR_RATES = OrderedDict([
    ("SOFR", {"rate": "FNYR-SOFR-A",
              "p1":   "FNYR-SOFR_1Pctl-A",
              "p25":  "FNYR-SOFR_25Pctl-A",
              "p75":  "FNYR-SOFR_75Pctl-A",
              "p99":  "FNYR-SOFR_99Pctl-A",
              "vol":  "FNYR-SOFR_UV-A",
              "label": "Secured Overnight Financing Rate"}),
    ("EFFR", {"rate": "FNYR-EFFR-A",
              "p1":   "FNYR-EFFR_1Pctl-A",
              "p25":  "FNYR-EFFR_25Pctl-A",
              "p75":  "FNYR-EFFR_75Pctl-A",
              "p99":  "FNYR-EFFR_99Pctl-A",
              "vol":  "FNYR-EFFR_UV-A",
              "label": "Effective Federal Funds Rate"}),
    ("OBFR", {"rate": "FNYR-OBFR-A",
              "p1":   "FNYR-OBFR_1Pctl-A",
              "p25":  "FNYR-OBFR_25Pctl-A",
              "p75":  "FNYR-OBFR_75Pctl-A",
              "p99":  "FNYR-OBFR_99Pctl-A",
              "vol":  "FNYR-OBFR_UV-A",
              "label": "Overnight Bank Funding Rate"}),
    ("TGCR", {"rate": "FNYR-TGCR-A",
              "p1":   "FNYR-TGCR_1Pctl-A",
              "p25":  "FNYR-TGCR_25Pctl-A",
              "p75":  "FNYR-TGCR_75Pctl-A",
              "p99":  "FNYR-TGCR_99Pctl-A",
              "vol":  "FNYR-TGCR_UV-A",
              "label": "Tri-Party General Collateral Rate"}),
    ("BGCR", {"rate": "FNYR-BGCR-A",
              "p1":   "FNYR-BGCR_1Pctl-A",
              "p25":  "FNYR-BGCR_25Pctl-A",
              "p75":  "FNYR-BGCR_75Pctl-A",
              "p99":  "FNYR-BGCR_99Pctl-A",
              "vol":  "FNYR-BGCR_UV-A",
              "label": "Broad General Collateral Rate"}),
])

# Treasury Constant Maturity Rates (yield curve)
TCMR_TENORS = OrderedDict([
    ("1M",  {"mnemonic": "TYLD-TCMR-1Mo-A",  "years": 1 / 12}),
    ("2M",  {"mnemonic": "TYLD-TCMR-2Mo-A",  "years": 2 / 12}),
    ("3M",  {"mnemonic": "TYLD-TCMR-3Mo-A",  "years": 3 / 12}),
    ("6M",  {"mnemonic": "TYLD-TCMR-6Mo-A",  "years": 6 / 12}),
    ("1Y",  {"mnemonic": "TYLD-TCMR-1Yr-A",  "years": 1.0}),
    ("2Y",  {"mnemonic": "TYLD-TCMR-2Yr-A",  "years": 2.0}),
    ("3Y",  {"mnemonic": "TYLD-TCMR-3Yr-A",  "years": 3.0}),
    ("5Y",  {"mnemonic": "TYLD-TCMR-5Yr-A",  "years": 5.0}),
    ("7Y",  {"mnemonic": "TYLD-TCMR-7Yr-A",  "years": 7.0}),
    ("10Y", {"mnemonic": "TYLD-TCMR-10Yr-A", "years": 10.0}),
    ("20Y", {"mnemonic": "TYLD-TCMR-20Yr-A", "years": 20.0}),
    ("30Y", {"mnemonic": "TYLD-TCMR-30Yr-A", "years": 30.0}),
])

# Repo segments and terms (Preliminary suffix -P preferred for currency;
# -F = Final, available with delay; -A used when no vintage suffix exists)
REPO_SEGMENTS = ["TRI", "TRIV1", "GCF", "DVP"]
REPO_TERMS = ["OO", "LE30", "G30", "TOT"]  # OO = Overnight/Open
REPO_METRICS = ["AR", "OV", "TV"]  # AR = Avg Rate, OV = Outstanding Vol, TV = Tx Vol

REPO_SEGMENT_LABELS = {
    "TRI":   "Tri-Party (incl. Fed)",
    "TRIV1": "Tri-Party (excl. Fed)",
    "GCF":   "GCF Repo",
    "DVP":   "DVP Service",
}

REPO_TERM_LABELS = {
    "OO":   "Overnight/Open",
    "LE30": "Term <=30 Days",
    "G30":  "Term >30 Days",
    "TOT":  "Total",
}

# Curated repo rate series for snapshot views (overnight, preliminary)
REPO_OVERNIGHT_RATES = OrderedDict([
    ("Tri-Party (excl Fed)", "REPO-TRIV1_AR_OO-P"),
    ("Tri-Party (all)",      "REPO-TRI_AR_OO-P"),
    ("GCF Repo",             "REPO-GCF_AR_OO-P"),
    ("DVP Service",          "REPO-DVP_AR_OO-P"),
])

# Daily transaction volumes -- TV (Transaction Volume) is the only volume metric
# available across all three segments (Tri-Party only publishes TV, not OV).
# DVP and GCF also publish OV (Outstanding Volume) -- see repo-history command.
REPO_TRANSACTION_VOLUMES = OrderedDict([
    ("Tri-Party (excl Fed)", "REPO-TRIV1_TV_TOT-P"),
    ("Tri-Party (all)",      "REPO-TRI_TV_TOT-P"),
    ("GCF Repo",             "REPO-GCF_TV_TOT-P"),
    ("DVP Service",          "REPO-DVP_TV_TOT-P"),
])

# Outstanding volumes -- only DVP and GCF publish these
REPO_OUTSTANDING_VOLUMES = OrderedDict([
    ("GCF Repo",             "REPO-GCF_OV_TOT-P"),
    ("DVP Service",          "REPO-DVP_OV_TOT-P"),
])

# MMF curated series for composition snapshot
MMF_COMPOSITION = OrderedDict([
    ("Total Investments",          "MMF-MMF_TOT-M"),
    ("U.S. Treasury Securities",   "MMF-MMF_T_TOT-M"),
    ("Federal Agency / GSE",       "MMF-MMF_AG_TOT-M"),
    ("Bank-Related Assets",        "MMF-MMF_BRA_TOT-M"),
    ("Repurchase Agreements",      "MMF-MMF_RP_TOT-M"),
    ("  RP backed by Treasury",    "MMF-MMF_RP_T_TOT-M"),
    ("  RP backed by Agency/GSE",  "MMF-MMF_RP_AG_TOT-M"),
    ("  RP backed by Other",       "MMF-MMF_RP_OA_TOT-M"),
    ("  RP w/ FICC clearing",      "MMF-MMF_RP_wFICC-M"),
    ("  RP w/ Federal Reserve",    "MMF-MMF_RP_wFR-M"),
    ("  RP w/ U.S. Fin Inst",      "MMF-MMF_RP_wDFI-M"),
    ("  RP w/ Foreign Fin Inst",   "MMF-MMF_RP_wFFI-M"),
    ("  RP w/ Other Cpty",         "MMF-MMF_RP_wOCP-M"),
    ("Other Assets",               "MMF-MMF_OA_TOT-M"),
])

# Primary dealer financing activity (NYPD).
# OFR's NYPD dataset publishes weekly dealer balance-sheet activity by
# collateral type. NOTE: the broader RP/RRP totals stopped reporting in late
# 2021 -- only securities borrowing/lending and fails-to-deliver/receive remain
# current. For dealer outright NET POSITIONS, see projects/apis/nyfed/nyfed.py.
NYPD_FINANCING = OrderedDict([
    ("SB: Treasury (ex-TIPS)",    "NYPD-PD_SB_T_eTIPS_TOT-A"),
    ("SB: Treasury Total",        "NYPD-PD_SB_T_TOT-A"),
    ("SB: Agency (ex-MBS)",       "NYPD-PD_SB_AG_eMBS_TOT-A"),
    ("SB: Agency MBS",            "NYPD-PD_SB_AG_MBS_TOT-A"),
    ("SB: Corporate Debt",        "NYPD-PD_SB_CORD_TOT-A"),
    ("SL: Treasury (ex-TIPS)",    "NYPD-PD_SL_T_eTIPS_TOT-A"),
    ("SL: Treasury Total",        "NYPD-PD_SL_T_TOT-A"),
])

# Primary dealer fails to deliver/receive
NYPD_FAILS = OrderedDict([
    ("FtD: Treasury (ex-TIPS)",  "NYPD-PD_AFtD_T_eTIPS-A"),
    ("FtD: Treasury TIPS",       "NYPD-PD_AFtD_TIPS-A"),
    ("FtD: Agency (ex-MBS)",     "NYPD-PD_AFtD_AG_eMBS-A"),
    ("FtD: Agency MBS",          "NYPD-PD_AFtD_AG_MBS-A"),
    ("FtD: Corporate",           "NYPD-PD_AFtD_CORS-A"),
    ("FtD: Total",               "NYPD-PD_AFtD_TOT-A"),
    ("FtR: Treasury (ex-TIPS)",  "NYPD-PD_AFtR_T_eTIPS-A"),
    ("FtR: Treasury TIPS",       "NYPD-PD_AFtR_TIPS-A"),
    ("FtR: Agency (ex-MBS)",     "NYPD-PD_AFtR_AG_eMBS-A"),
    ("FtR: Agency MBS",          "NYPD-PD_AFtR_AG_MBS-A"),
    ("FtR: Corporate",           "NYPD-PD_AFtR_CORS-A"),
    ("FtR: Total",               "NYPD-PD_AFtR_TOT-A"),
])

# Form PF aggregate views
FPF_TOTALS = OrderedDict([
    ("Qualifying HF: Gross Assets",      "FPF-ALLQHF_GAV_SUM"),
    ("Qualifying HF: Net Assets",        "FPF-ALLQHF_NAV_SUM"),
    ("Borrowing: Repo",                  "FPF-BORROW_REPO_SUM"),
    ("Borrowing: Prime Brokerage",       "FPF-BORROW_PRIMEBROKER_SUM"),
    ("Borrowing: Other Secured",         "FPF-BORROW_OTHERSECURED_SUM"),
])

FPF_STRATEGIES = ["CREDIT", "EQUITY", "EVENT", "FOF", "FUTURES", "MACRO",
                  "MULTI", "OTHER", "RV"]

FPF_STRATEGY_LABELS = {
    "CREDIT":  "Credit",
    "EQUITY":  "Equity",
    "EVENT":   "Event Driven",
    "FOF":     "Fund of Funds",
    "FUTURES": "Managed Futures",
    "MACRO":   "Macro",
    "MULTI":   "Multi-Strategy",
    "OTHER":   "Other",
    "RV":      "Relative Value",
}

# Stress tests across all qualifying hedge funds (P5 = 5th percentile fund)
FPF_STRESS_TESTS = OrderedDict([
    ("Credit Spreads -250bp",   {"p5": "FPF-ALLQHF_CDSDOWN250BPS_P5",
                                 "p50": "FPF-ALLQHF_CDSDOWN250BPS_P50"}),
    ("Credit Spreads +250bp",   {"p5": "FPF-ALLQHF_CDSUP250BPS_P5",
                                 "p50": "FPF-ALLQHF_CDSUP250BPS_P50"}),
    ("Currency -20%",           {"p5": "FPF-ALLQHF_CURRENCYDOWN20P_P5",
                                 "p50": "FPF-ALLQHF_CURRENCYDOWN20P_P50"}),
    ("Currency +20%",           {"p5": "FPF-ALLQHF_CURRENCYUP20P_P5",
                                 "p50": "FPF-ALLQHF_CURRENCYUP20P_P50"}),
    ("Equity -20%",             {"p5": "FPF-ALLQHF_EQDOWN20P_P5",
                                 "p50": "FPF-ALLQHF_EQDOWN20P_P50"}),
    ("Equity +20%",             {"p5": "FPF-ALLQHF_EQUP20P_P5",
                                 "p50": "FPF-ALLQHF_EQUP20P_P50"}),
])

# CFTC TFF curated futures (codes used in TFF mnemonics)
# Format: TFF-{group}_{contract}_{side}_POSITION (or _DV01, _POS10YREQV)
TFF_GROUPS = OrderedDict([
    ("AI", "Asset Managers / Institutional"),
    ("LF", "Leveraged Funds"),
    ("DI", "Dealers / Intermediaries"),
    ("OR", "Other Reportables"),
])

TFF_CONTRACTS = OrderedDict([
    ("TREAS",  "U.S. Treasuries (aggregate)"),
    ("TU",     "2Y Treasury (TU)"),
    ("FV",     "5Y Treasury (FV)"),
    ("TY",     "10Y Treasury (TY)"),
    ("UXY",    "Ultra 10Y (UXY)"),
    ("US",     "Long Bond (US)"),
    ("WN",     "Ultra Long Bond (WN)"),
    ("FF",     "Fed Funds Futures"),
    ("ED",     "Eurodollar Futures"),
    ("SER",    "3M SOFR (SER)"),
    ("SFR",    "1M SOFR (SFR)"),
    ("SP",     "S&P 500 Futures"),
    ("ND",     "Nasdaq 100 (ND)"),
    ("DJ",     "Dow Jones (DJ)"),
    ("DX",     "U.S. Dollar Index"),
    ("EC",     "Euro FX"),
    ("JY",     "Japanese Yen"),
    ("BP",     "British Pound"),
    ("CD",     "Canadian Dollar"),
    ("AD",     "Australian Dollar"),
    ("SF",     "Swiss Franc"),
    ("VIX",    "VIX Futures"),
    ("BITCOIN", "Bitcoin Futures"),
])

# FICC sponsored repo
FICC_SERIES = OrderedDict([
    ("Sponsored Repo",         "FICC-SPONSORED_REPO_VOL"),
    ("Sponsored Reverse Repo", "FICC-SPONSORED_REVREPO_VOL"),
])


# =============================================================================
# HTTP CORE
# =============================================================================

def _request(url, params=None, max_retries=3, expect_json=True, timeout=DEFAULT_TIMEOUT,
             quiet=False):
    """Generic HTTP GET with retry / 429 backoff. Returns parsed JSON or text."""
    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code >= 400:
                if not quiet:
                    print(f"  [API error {r.status_code} for {url}: {r.text[:200]}]")
                return None
            if not r.text or not r.text.strip():
                return None
            if expect_json:
                try:
                    return r.json()
                except ValueError:
                    print(f"  [non-JSON response: {r.text[:200]}]")
                    return None
            return r.text
        except requests.exceptions.Timeout:
            print(f"  [timeout, attempt {attempt + 1}/{max_retries}]")
        except requests.exceptions.ConnectionError as e:
            print(f"  [connection error attempt {attempt + 1}/{max_retries}: {e}]")
            time.sleep(2)
        except Exception as e:
            print(f"  [error: {e}]")
            return None
    print(f"  [max retries reached for {url}]")
    return None


# =============================================================================
# LOW-LEVEL DATA FETCHERS
# =============================================================================

def fetch_mnemonics(dataset=None, output=None):
    """List all mnemonics. dataset=None lists everything; output='by_dataset' nests."""
    base = _api_base(dataset) if dataset else None
    params = {}
    if dataset:
        params["dataset"] = dataset
    if output:
        params["output"] = output
    if base:
        return _request(f"{base}/metadata/mnemonics", params=params)
    # No dataset: query both APIs and merge
    stfm = _request(f"{STFM_BASE}/metadata/mnemonics", params=params) or []
    hfm = _request(f"{HFM_BASE}/metadata/mnemonics", params=params) or []
    if isinstance(stfm, list) and isinstance(hfm, list):
        return stfm + hfm
    return {"stfm": stfm, "hfm": hfm}


def fetch_search(query, search_hfm=True, search_stfm=True):
    """Search across mnemonics. Returns list with 'mnemonic', 'dataset', 'field', 'value'."""
    results = []
    if search_stfm:
        r = _request(f"{STFM_BASE}/metadata/search", params={"query": query}) or []
        if isinstance(r, list):
            results.extend(r)
        time.sleep(REQUEST_DELAY)
    if search_hfm:
        r = _request(f"{HFM_BASE}/metadata/search", params={"query": query}) or []
        if isinstance(r, list):
            results.extend(r)
    return results


def fetch_query(mnemonic, fields=None):
    """Get full metadata for a single mnemonic."""
    base = _api_base_for_mnemonic(mnemonic)
    params = {"mnemonic": mnemonic}
    if fields:
        params["fields"] = fields
    return _request(f"{base}/metadata/query", params=params)


def fetch_timeseries(mnemonic, label="aggregation", start_date=None, end_date=None,
                     periodicity=None, how=None, remove_nulls=False, time_format=None):
    """Get a single timeseries -- returns list of [date, value] pairs."""
    base = _api_base_for_mnemonic(mnemonic)
    params = {"mnemonic": mnemonic}
    if label and label != "aggregation":
        params["label"] = label
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if periodicity:
        params["periodicity"] = periodicity
    if how:
        params["how"] = how
    if remove_nulls:
        params["remove_nulls"] = "true"
    if time_format:
        params["time_format"] = time_format
    r = _request(f"{base}/series/timeseries", params=params)
    return r if isinstance(r, list) else []


def fetch_full(mnemonic, start_date=None, end_date=None, periodicity=None, how=None,
               remove_nulls=False, time_format=None):
    """Get series + metadata for a single mnemonic. Returns dict {mnemonic: {...}}."""
    base = _api_base_for_mnemonic(mnemonic)
    params = {"mnemonic": mnemonic}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if periodicity:
        params["periodicity"] = periodicity
    if how:
        params["how"] = how
    if remove_nulls:
        params["remove_nulls"] = "true"
    if time_format:
        params["time_format"] = time_format
    return _request(f"{base}/series/full", params=params) or {}


def fetch_multifull(mnemonics, start_date=None, end_date=None, periodicity=None,
                    how=None, remove_nulls=False, time_format=None, quiet=False):
    """Get multiple series in one call. mnemonics is a list. Auto-splits across STFM/HFM."""
    stfm_list = [m for m in mnemonics if _api_base_for_mnemonic(m) == STFM_BASE]
    hfm_list = [m for m in mnemonics if _api_base_for_mnemonic(m) == HFM_BASE]

    out = {}

    def _do(base, mlist):
        if not mlist:
            return
        params = {"mnemonics": ",".join(mlist)}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if periodicity:
            params["periodicity"] = periodicity
        if how:
            params["how"] = how
        if remove_nulls:
            params["remove_nulls"] = "true"
        if time_format:
            params["time_format"] = time_format
        r = _request(f"{base}/series/multifull", params=params, quiet=quiet) or {}
        if isinstance(r, dict):
            out.update(r)

    _do(STFM_BASE, stfm_list)
    if stfm_list and hfm_list:
        time.sleep(REQUEST_DELAY)
    _do(HFM_BASE, hfm_list)
    return out


def fetch_dataset(dataset, vintage=None, start_date=None, end_date=None,
                  periodicity=None, how=None, remove_nulls=False, time_format=None):
    """Pull all series in a dataset."""
    base = _api_base(dataset)
    params = {"dataset": dataset}
    if vintage:
        params["vintage"] = vintage
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if periodicity:
        params["periodicity"] = periodicity
    if how:
        params["how"] = how
    if remove_nulls:
        params["remove_nulls"] = "true"
    if time_format:
        params["time_format"] = time_format
    return _request(f"{base}/series/dataset", params=params) or {}


def fetch_spread(x, y, start_date=None, end_date=None, periodicity=None, how=None,
                 remove_nulls=False, time_format=None):
    """Compute spread = x - y across two series. Both must live on same API."""
    base = _api_base_for_mnemonic(x)
    base_y = _api_base_for_mnemonic(y)
    if base != base_y:
        print(f"  [warn] spread across STFM ({x}) and HFM ({y}) not supported "
              f"by API; falling back to {base}")
    params = {"x": x, "y": y}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if periodicity:
        params["periodicity"] = periodicity
    if how:
        params["how"] = how
    if remove_nulls:
        params["remove_nulls"] = "true"
    if time_format:
        params["time_format"] = time_format
    r = _request(f"{base}/calc/spread", params=params)
    return r if isinstance(r, list) else []


def fetch_fsi_csv():
    """Download the OFR Financial Stress Index CSV. Returns list of dict rows."""
    text = _request(FSI_CSV_URL, expect_json=False, timeout=60)
    if not text:
        return []
    rows = []
    reader = csv.DictReader(io.StringIO(text))
    for r in reader:
        rec = {"date": r.get("Date", "")}
        for k, v in r.items():
            if k == "Date":
                continue
            try:
                rec[k] = float(v) if v not in ("", None) else None
            except (ValueError, TypeError):
                rec[k] = v
        rows.append(rec)
    return rows


# =============================================================================
# UTILS: Parse / Format
# =============================================================================

def _safe_float(val, default=None):
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _last_pair(pairs, default=(None, None)):
    """Return last non-null (date, value) pair from a timeseries list."""
    for d, v in reversed(pairs or []):
        if v is not None:
            return d, v
    return default


def _to_dict(pairs):
    """Convert [[date,val], ...] -> {date: val} dict."""
    return {d: v for d, v in (pairs or []) if v is not None}


def _fmt_pct(p, decimals=2, sign=False):
    if p is None:
        return "--"
    if sign:
        return f"{p:+.{decimals}f}%"
    return f"{p:.{decimals}f}%"


def _fmt_bps(p, sign=True):
    if p is None:
        return "--"
    if sign:
        return f"{p:+.1f}bp"
    return f"{p:.1f}bp"


def _fmt_billions(val, decimals=1, sign=False):
    if val is None:
        return "--"
    if sign:
        return f"{val:+,.{decimals}f}B"
    return f"${val:,.{decimals}f}B"


def _fmt_trillions(val, decimals=2):
    if val is None:
        return "--"
    return f"${val:,.{decimals}f}T"


def _fmt_num(n, sign=False, decimals=0):
    if n is None:
        return "--"
    if decimals > 0:
        return f"{n:+,.{decimals}f}" if sign else f"{n:,.{decimals}f}"
    n = int(round(n))
    return f"{n:+,}" if sign else f"{n:,}"


def _to_billions(val):
    return val / 1e9 if val is not None else None


def _to_trillions(val):
    return val / 1e12 if val is not None else None


def _date_minus(date_str, days):
    """date_str (YYYY-MM-DD) minus N days; returns YYYY-MM-DD."""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return (d - timedelta(days=days)).strftime("%Y-%m-%d")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _years_ago(years):
    return (datetime.now() - timedelta(days=int(365 * years))).strftime("%Y-%m-%d")


def _fmt_change_arrow(curr, prev):
    if curr is None or prev is None:
        return ""
    diff = curr - prev
    if abs(diff) < 1e-9:
        return "  flat"
    return f"  {'up' if diff > 0 else 'dn'}"


# =============================================================================
# UTILS: Prompts / Export
# =============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


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


# =============================================================================
# COMMANDS: Generic API
# =============================================================================

def cmd_datasets(as_json=False, export_fmt=None):
    """List all datasets across STFM + HFM."""
    print("\n  OFR Datasets")
    print("  " + "=" * 90)

    rows = []
    for key, info in STFM_DATASETS.items():
        rows.append({
            "api": "STFM", "key": key,
            "long_name": info["long_name"],
            "frequency": info["frequency"],
        })
    for key, info in HFM_DATASETS.items():
        rows.append({
            "api": "HFM", "key": key,
            "long_name": info["long_name"],
            "frequency": info["frequency"],
        })

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    print(f"  {'API':<6} {'Key':<8} {'Frequency':<12} {'Long Name'}")
    print(f"  {'-'*6} {'-'*8} {'-'*12} {'-'*60}")
    for row in rows:
        print(f"  {row['api']:<6} {row['key']:<8} {row['frequency']:<12} {row['long_name']}")
    print()
    print(f"  Plus: OFR Financial Stress Index (CSV) -- {FSI_CSV_URL}")
    print()

    if export_fmt:
        _do_export(rows, "ofr_datasets", export_fmt)
    return rows


def cmd_mnemonics(dataset=None, query=None, limit=80,
                  as_json=False, export_fmt=None):
    """List mnemonics for a dataset or filtered globally."""
    if dataset and dataset not in ALL_DATASETS:
        print(f"  Unknown dataset: {dataset}. Valid: {sorted(ALL_DATASETS.keys())}")
        return

    print(f"\n  Fetching mnemonics{' for ' + dataset if dataset else ' (all)'}...")
    rows = fetch_mnemonics(dataset=dataset)

    if not rows:
        print("  No data returned.")
        return

    if isinstance(rows, list):
        if query:
            ql = query.lower()
            rows = [r for r in rows
                    if ql in r.get("mnemonic", "").lower()
                    or ql in r.get("series_name", "").lower()]

        if as_json:
            print(json.dumps(rows, indent=2))
            return rows

        title_q = f' (filtered: "{query}")' if query else ""
        print(f"\n  {len(rows)} mnemonic{'s' if len(rows) != 1 else ''}{title_q}")
        print("  " + "=" * 105)
        print(f"  {'Mnemonic':<42} {'Series Name'}")
        print(f"  {'-'*42} {'-'*60}")
        for r in rows[:limit]:
            mn = r.get("mnemonic", "")[:42]
            sn = r.get("series_name", "")[:80]
            print(f"  {mn:<42} {sn}")
        if len(rows) > limit:
            print(f"  ... and {len(rows) - limit} more (use --limit to see more)")
        print()

        if export_fmt:
            _do_export(rows, f"ofr_mnemonics_{dataset or 'all'}", export_fmt)
        return rows

    if as_json:
        print(json.dumps(rows, indent=2))
    return rows


def cmd_search(query, as_json=False, export_fmt=None, limit=80):
    """Search across both APIs for mnemonics matching a query (* and ? wildcards)."""
    print(f"\n  Searching OFR for '{query}' (STFM + HFM)...")
    rows = fetch_search(query)

    if not rows:
        print("  No results.")
        return

    # Dedup by mnemonic + field + value
    seen = set()
    deduped = []
    for r in rows:
        key = (r.get("mnemonic"), r.get("field"), r.get("value"))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    if as_json:
        print(json.dumps(deduped, indent=2))
        return deduped

    print(f"\n  {len(deduped)} matches")
    print("  " + "=" * 110)
    print(f"  {'Dataset':<8} {'Mnemonic':<42} {'Field':<22} {'Value'}")
    print(f"  {'-'*8} {'-'*42} {'-'*22} {'-'*30}")

    for r in deduped[:limit]:
        ds = (r.get("dataset") or "")[:8]
        mn = (r.get("mnemonic") or "")[:42]
        fd = (r.get("field") or "")[:22]
        vl = str(r.get("value") or "")[:60]
        print(f"  {ds:<8} {mn:<42} {fd:<22} {vl}")
    if len(deduped) > limit:
        print(f"  ... and {len(deduped) - limit} more (use --limit)")
    print()

    if export_fmt:
        _do_export(deduped, f"ofr_search_{query.replace('*', 'X').replace('?', 'Y')[:20]}",
                   export_fmt)
    return deduped


def cmd_query(mnemonic, fields=None, as_json=False, export_fmt=None):
    """Get full metadata for a single mnemonic."""
    print(f"\n  Fetching metadata for {mnemonic}...")
    data = fetch_query(mnemonic, fields=fields)

    if not data:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(data, indent=2))
        return data

    print(f"\n  {mnemonic}")
    print("  " + "=" * 90)

    desc = data.get("description", {}) if isinstance(data, dict) else {}
    schedule = data.get("schedule", {}) if isinstance(data, dict) else {}
    rel = data.get("release", {}) if isinstance(data, dict) else {}
    unit = data.get("unit", {}) if isinstance(data, dict) else {}

    if isinstance(desc, dict):
        print(f"  Name:         {desc.get('name', '--')}")
        print(f"  Subtype:      {desc.get('subtype', '--')}")
        if desc.get("description"):
            print(f"  Description:  {desc['description'][:200]}")
        if desc.get("subsetting"):
            print(f"  Subsetting:   {desc.get('subsetting')}")
    if isinstance(schedule, dict):
        print(f"\n  Frequency:    {schedule.get('observation_frequency', '--')}")
        print(f"  Period:       {schedule.get('observation_period', '--')}")
        print(f"  Start date:   {schedule.get('start_date', '--')}")
        print(f"  Last update:  {schedule.get('last_update', '--')}")
    if isinstance(unit, dict):
        print(f"\n  Unit:         {unit.get('name', '--')} ({unit.get('type', '--')})")
        print(f"  Magnitude:    10^{unit.get('magnitude', 0)}")
    if isinstance(rel, dict):
        print(f"\n  Release:      {rel.get('long_name', '--')}")

    print()

    if export_fmt:
        _do_export(data, f"ofr_query_{mnemonic.replace('-', '_').replace('/', '_')}",
                   export_fmt)
    return data


def cmd_series(mnemonic, start_date=None, end_date=None, periodicity=None, how=None,
               obs=None, remove_nulls=False, label="aggregation",
               as_json=False, export_fmt=None):
    """Fetch a single timeseries."""
    if obs and not start_date:
        # Approximate start date by working back; depends on frequency
        start_date = _years_ago(2)

    print(f"\n  Fetching {mnemonic} ({start_date or 'all'} to {end_date or 'today'})...")
    rows = fetch_timeseries(mnemonic, label=label, start_date=start_date,
                            end_date=end_date, periodicity=periodicity, how=how,
                            remove_nulls=remove_nulls)

    if not rows:
        print("  No data returned.")
        return

    if obs:
        rows = rows[-obs:]

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    print(f"\n  {mnemonic} ({len(rows)} observations)")
    print("  " + "=" * 60)
    print(f"  {'Date':<12} {'Value':>20}")
    print(f"  {'-'*12} {'-'*20}")

    for d, v in rows[-30:]:
        v_s = f"{v:,.4f}" if isinstance(v, (int, float)) else (str(v) if v is not None else "--")
        print(f"  {d:<12} {v_s:>20}")

    if len(rows) > 30:
        print(f"  ... showing last 30 of {len(rows)}")

    vals = [v for _, v in rows if isinstance(v, (int, float))]
    if vals:
        latest = vals[-1]
        first = vals[0]
        lo = min(vals)
        hi = max(vals)
        avg = sum(vals) / len(vals)
        print(f"\n  Range: {lo:,.4f} -- {hi:,.4f}  |  Mean: {avg:,.4f}  |  "
              f"Latest: {latest:,.4f}")
        if first != 0:
            print(f"  Period change: {latest - first:+,.4f} "
                  f"({(latest - first) / abs(first) * 100:+.2f}%)")
    print()

    if export_fmt:
        out = [{"date": d, "value": v} for d, v in rows]
        _do_export(out, f"ofr_series_{mnemonic.replace('-', '_')}", export_fmt)
    return rows


def cmd_multi(mnemonics, start_date=None, end_date=None, periodicity=None,
              how=None, as_json=False, export_fmt=None):
    """Fetch multiple series side-by-side."""
    if isinstance(mnemonics, str):
        mnemonics = [m.strip() for m in mnemonics.split(",") if m.strip()]

    print(f"\n  Fetching {len(mnemonics)} series...")
    data = fetch_multifull(mnemonics, start_date=start_date, end_date=end_date,
                           periodicity=periodicity, how=how)

    if not data:
        print("  No data returned.")
        return

    if as_json:
        print(json.dumps(data, indent=2))
        return data

    # Build a unified date grid
    all_pairs = {m: data.get(m, {}).get("timeseries", {}).get("aggregation", [])
                 for m in mnemonics}

    all_dates = sorted(set(d for pairs in all_pairs.values() for d, _ in pairs))

    if not all_dates:
        print("  No data points across requested series.")
        return data

    # Latest snapshot summary
    print(f"\n  Multi-Series Snapshot")
    print("  " + "=" * 80)
    print(f"  {'Mnemonic':<38} {'Latest Date':<13} {'Value':>20}")
    print(f"  {'-'*38} {'-'*13} {'-'*20}")
    for m in mnemonics:
        last_d, last_v = _last_pair(all_pairs.get(m, []))
        v_s = f"{last_v:,.4f}" if isinstance(last_v, (int, float)) else (str(last_v) if last_v else "--")
        print(f"  {m:<38} {(last_d or '--'):<13} {v_s:>20}")
    print()

    if export_fmt:
        out = []
        for m in mnemonics:
            for d, v in all_pairs.get(m, []):
                out.append({"mnemonic": m, "date": d, "value": v})
        _do_export(out, "ofr_multi_series", export_fmt)
    return data


def cmd_spread(x, y, start_date=None, end_date=None, obs=None,
               periodicity=None, as_json=False, export_fmt=None):
    """Compute spread = x - y."""
    if obs and not start_date:
        start_date = _years_ago(1)

    print(f"\n  Computing spread: {x} - {y}...")
    rows = fetch_spread(x, y, start_date=start_date, end_date=end_date,
                        periodicity=periodicity)

    if not rows:
        print("  No data returned.")
        return

    if obs:
        rows = rows[-obs:]

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    print(f"\n  Spread: {x} -- {y}  ({len(rows)} obs)")
    print("  " + "=" * 60)
    print(f"  {'Date':<12} {'Spread':>15}")
    print(f"  {'-'*12} {'-'*15}")
    for d, v in rows[-30:]:
        v_s = f"{v:+,.4f}" if isinstance(v, (int, float)) else "--"
        print(f"  {d:<12} {v_s:>15}")

    vals = [v for _, v in rows if isinstance(v, (int, float))]
    if vals:
        latest = vals[-1]
        lo = min(vals)
        hi = max(vals)
        avg = sum(vals) / len(vals)
        print(f"\n  Range: {lo:+,.4f} -- {hi:+,.4f}  |  Mean: {avg:+,.4f}  |  "
              f"Latest: {latest:+,.4f}")
    print()

    if export_fmt:
        out = [{"date": d, "spread": v} for d, v in rows]
        _do_export(out, f"ofr_spread_{x.replace('-', '_')}_{y.replace('-', '_')}", export_fmt)
    return rows


def cmd_dataset_pull(dataset, vintage=None, start_date=None, end_date=None,
                     periodicity=None, how=None, as_json=False, export_fmt=None):
    """Pull all series in a dataset (warning: large)."""
    if dataset not in ALL_DATASETS:
        print(f"  Unknown dataset '{dataset}'. Valid: {sorted(ALL_DATASETS.keys())}")
        return

    print(f"\n  Pulling all series for dataset '{dataset}'...")
    print(f"  This may take a few seconds for large datasets (e.g. fpf=329 series).")
    data = fetch_dataset(dataset, vintage=vintage, start_date=start_date,
                         end_date=end_date, periodicity=periodicity, how=how)

    if not data:
        print("  No data returned.")
        return

    timeseries = data.get("timeseries", {})

    if as_json:
        print(json.dumps(data, indent=2))
        return data

    print(f"\n  Dataset: {data.get('long_name', dataset)} "
          f"({len(timeseries)} series)")
    print("  " + "=" * 100)
    print(f"  {'Mnemonic':<42} {'Latest':<13} {'Value':>16} {'Obs':>8}")
    print(f"  {'-'*42} {'-'*13} {'-'*16} {'-'*8}")

    rows_for_export = []
    for mn, info in sorted(timeseries.items()):
        agg = info.get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(agg)
        v_s = f"{last_v:,.4f}" if isinstance(last_v, (int, float)) else "--"
        print(f"  {mn[:42]:<42} {(last_d or '--'):<13} {v_s:>16} {len(agg):>8}")
        rows_for_export.append({
            "mnemonic": mn,
            "latest_date": last_d,
            "latest_value": last_v,
            "n_obs": len(agg),
        })
    print()

    if export_fmt:
        _do_export(rows_for_export, f"ofr_dataset_{dataset}", export_fmt)
    return data


# =============================================================================
# COMMANDS: Curated -- Reference Rates (FNYR)
# =============================================================================

def cmd_fnyr(obs=30, as_json=False, export_fmt=None):
    """NY Fed reference rates with percentiles + volume."""
    print(f"\n  Fetching NY Fed reference rates (last {obs} business days)...")

    start = _years_ago(0.3)  # ~110 days
    all_mnemonics = []
    for spec in FNYR_RATES.values():
        all_mnemonics.extend([spec["rate"], spec["p1"], spec["p25"], spec["p75"],
                              spec["p99"], spec["vol"]])

    data = fetch_multifull(all_mnemonics, start_date=start)

    snapshot = OrderedDict()
    history = OrderedDict()
    for label, spec in FNYR_RATES.items():
        rate_pairs = data.get(spec["rate"], {}).get("timeseries", {}).get("aggregation", [])
        last_date, rate_val = _last_pair(rate_pairs)
        snapshot[label] = {
            "date": last_date,
            "rate": rate_val,
            "p1":   _last_pair(data.get(spec["p1"], {}).get("timeseries", {}).get("aggregation", []))[1],
            "p25":  _last_pair(data.get(spec["p25"], {}).get("timeseries", {}).get("aggregation", []))[1],
            "p75":  _last_pair(data.get(spec["p75"], {}).get("timeseries", {}).get("aggregation", []))[1],
            "p99":  _last_pair(data.get(spec["p99"], {}).get("timeseries", {}).get("aggregation", []))[1],
            "vol":  _last_pair(data.get(spec["vol"], {}).get("timeseries", {}).get("aggregation", []))[1],
            "label": spec["label"],
        }
        history[label] = rate_pairs[-obs:]

    if as_json:
        print(json.dumps({"snapshot": snapshot, "history": history}, indent=2))
        return snapshot

    print(f"\n  NY Fed Reference Rates (latest)")
    print("  " + "=" * 95)
    print(f"  {'Rate':<6} {'Date':<12} {'Rate%':>8} {'P1%':>8} {'P25%':>8} "
          f"{'P75%':>8} {'P99%':>8} {'Vol ($B)':>12}")
    print(f"  {'-'*6} {'-'*12} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*12}")

    for label, snap in snapshot.items():
        vol_bn = _to_billions(snap['vol'])
        print(f"  {label:<6} {(snap['date'] or '--'):<12} "
              f"{_fmt_pct(snap['rate'], decimals=2):>8} "
              f"{_fmt_pct(snap['p1'], decimals=2):>8} "
              f"{_fmt_pct(snap['p25'], decimals=2):>8} "
              f"{_fmt_pct(snap['p75'], decimals=2):>8} "
              f"{_fmt_pct(snap['p99'], decimals=2):>8} "
              f"{_fmt_billions(vol_bn, decimals=0):>12}")

    print()
    print(f"  Recent history (last {obs} obs)")
    print("  " + "-" * 70)
    header = f"  {'Date':<12}"
    for label in FNYR_RATES:
        header += f" {label:>8}"
    print(header)

    # Build aligned date series across rates
    all_dates = sorted(set(d for label in FNYR_RATES
                           for d, _ in history.get(label, [])))[-obs:]
    rate_lookup = {label: _to_dict(history.get(label, [])) for label in FNYR_RATES}
    for d in all_dates[-min(obs, 25):]:
        line = f"  {d:<12}"
        for label in FNYR_RATES:
            v = rate_lookup[label].get(d)
            line += f" {_fmt_pct(v, decimals=2):>8}" if v is not None else f" {'--':>8}"
        print(line)

    if len(all_dates) > 25:
        print(f"  ... last 25 of {len(all_dates)} dates shown (use --json for full)")
    print()

    if export_fmt:
        out = []
        for d in all_dates:
            row = {"date": d}
            for label in FNYR_RATES:
                row[label.lower()] = rate_lookup[label].get(d)
            out.append(row)
        _do_export(out, "ofr_fnyr", export_fmt)
    return snapshot


# =============================================================================
# COMMANDS: Curated -- Repo Markets (REPO)
# =============================================================================

def cmd_repo_rates(obs=30, as_json=False, export_fmt=None):
    """Tri-Party + GCF + DVP overnight repo rates."""
    print(f"\n  Fetching curated repo overnight rates (last {obs} business days)...")
    start = _years_ago(0.3)
    mnemonics = list(REPO_OVERNIGHT_RATES.values())

    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for label, mn in REPO_OVERNIGHT_RATES.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "rate": last_v,
            "history": pairs[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    print(f"\n  Repo Overnight Rates (latest)")
    print("  " + "=" * 80)
    print(f"  {'Segment':<24} {'Date':<12} {'Rate%':>8} {'Mnemonic'}")
    print(f"  {'-'*24} {'-'*12} {'-'*8} {'-'*32}")

    for label, snap in snapshot.items():
        print(f"  {label:<24} {(snap['date'] or '--'):<12} "
              f"{_fmt_pct(snap['rate'], decimals=2):>8} {snap['mnemonic']}")

    # Cross-rate spread analysis
    rates = {k: v["rate"] for k, v in snapshot.items() if v["rate"] is not None}
    if "GCF Repo" in rates and "Tri-Party (excl Fed)" in rates:
        spread = (rates["GCF Repo"] - rates["Tri-Party (excl Fed)"]) * 100
        print(f"\n  GCF -- Tri-Party (excl Fed): {_fmt_bps(spread)}")
        if abs(spread) > 5:
            note = "Elevated -- secured funding fragmentation" if spread > 0 else "Inverted -- unusual flow"
        else:
            note = "Normal"
        print(f"  Assessment: {note}")
    if "DVP Service" in rates and "GCF Repo" in rates:
        spread = (rates["DVP Service"] - rates["GCF Repo"]) * 100
        print(f"  DVP -- GCF: {_fmt_bps(spread)} (DVP typically rich vs GCF)")

    print()
    print(f"  Recent history (last {min(obs, 20)} obs)")
    print("  " + "-" * 95)
    header = f"  {'Date':<12}"
    for label in REPO_OVERNIGHT_RATES:
        header += f" {label[:18]:>20}"
    print(header)

    all_dates = sorted(set(d for snap in snapshot.values() for d, _ in snap["history"]))[-obs:]
    rate_lookup = {label: _to_dict(snap["history"]) for label, snap in snapshot.items()}
    for d in all_dates[-min(obs, 20):]:
        line = f"  {d:<12}"
        for label in REPO_OVERNIGHT_RATES:
            v = rate_lookup[label].get(d)
            line += f" {_fmt_pct(v, decimals=2):>20}" if v is not None else f" {'--':>20}"
        print(line)

    print()

    if export_fmt:
        out = []
        for d in all_dates:
            row = {"date": d}
            for label, snap in snapshot.items():
                row[snap["mnemonic"]] = rate_lookup[label].get(d)
            out.append(row)
        _do_export(out, "ofr_repo_rates", export_fmt)
    return snapshot


def cmd_repo_volumes(obs=30, as_json=False, export_fmt=None):
    """Repo daily transaction volumes (all 3 segments) + outstanding (DVP, GCF)."""
    print(f"\n  Fetching repo volumes (last {obs} business days)...")
    start = _years_ago(0.3)

    tv_mnemonics = list(REPO_TRANSACTION_VOLUMES.values())
    ov_mnemonics = list(REPO_OUTSTANDING_VOLUMES.values())
    all_mns = tv_mnemonics + ov_mnemonics

    data = fetch_multifull(all_mns, start_date=start)

    tv_snapshot = OrderedDict()
    for label, mn in REPO_TRANSACTION_VOLUMES.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        tv_snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "volume_raw": last_v,
            "volume_bn": _to_billions(last_v) if last_v else None,
            "history": pairs[-obs:],
        }

    ov_snapshot = OrderedDict()
    for label, mn in REPO_OUTSTANDING_VOLUMES.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        ov_snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "volume_raw": last_v,
            "volume_bn": _to_billions(last_v) if last_v else None,
            "history": pairs[-obs:],
        }

    snapshot = {"transaction_volumes": tv_snapshot, "outstanding_volumes": ov_snapshot}

    # For backward compat with dashboards, expose flat dict at top level too
    flat = OrderedDict()
    for label, snap in tv_snapshot.items():
        flat[label] = {**snap, "value_bn": snap["volume_bn"]}
    for label, snap in ov_snapshot.items():
        flat[f"{label} (Outstanding)"] = {**snap, "value_bn": snap["volume_bn"]}

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return flat

    print(f"\n  Repo Daily Transaction Volumes (latest)")
    print("  " + "=" * 80)
    print(f"  {'Segment':<24} {'Date':<12} {'Daily Vol ($B)':>16}")
    print(f"  {'-'*24} {'-'*12} {'-'*16}")
    for label, snap in tv_snapshot.items():
        print(f"  {label:<24} {(snap['date'] or '--'):<12} "
              f"{_fmt_billions(snap['volume_bn']):>16}")

    print(f"\n  Repo Outstanding Volumes (latest, DVP + GCF only)")
    print("  " + "-" * 80)
    print(f"  {'Segment':<24} {'Date':<12} {'Outstanding ($B)':>18}")
    print(f"  {'-'*24} {'-'*12} {'-'*18}")
    for label, snap in ov_snapshot.items():
        print(f"  {label:<24} {(snap['date'] or '--'):<12} "
              f"{_fmt_billions(snap['volume_bn']):>18}")

    print()
    print(f"  Daily Transaction Volume History (last {min(obs, 12)} obs)")
    print("  " + "-" * 105)
    header = f"  {'Date':<12}"
    for label in REPO_TRANSACTION_VOLUMES:
        header += f" {label[:20]:>22}"
    print(header)

    all_dates = sorted(set(d for snap in tv_snapshot.values() for d, _ in snap["history"]))[-obs:]
    vol_lookup = {label: _to_dict(snap["history"]) for label, snap in tv_snapshot.items()}
    for d in all_dates[-min(obs, 12):]:
        line = f"  {d:<12}"
        for label in REPO_TRANSACTION_VOLUMES:
            v = vol_lookup[label].get(d)
            line += f" {_fmt_billions(_to_billions(v)):>22}" if v is not None else f" {'--':>22}"
        print(line)
    print()

    if export_fmt:
        out = []
        for d in all_dates:
            row = {"date": d}
            for label, snap in tv_snapshot.items():
                v = vol_lookup[label].get(d)
                row["TV_" + snap["mnemonic"]] = _to_billions(v) if v is not None else None
            out.append(row)
        _do_export(out, "ofr_repo_volumes", export_fmt)
    return flat


def cmd_repo_history(segment="GCF", term="OO", metric="AR", vintage="P",
                     obs=60, as_json=False, export_fmt=None):
    """History of a specific repo rate or volume series."""
    seg = segment.upper()
    if seg == "TRIPARTY":
        seg = "TRI"
    if seg not in REPO_SEGMENTS:
        print(f"  Unknown segment '{segment}'. Valid: {REPO_SEGMENTS}")
        return
    term = term.upper()
    if term not in REPO_TERMS:
        print(f"  Unknown term '{term}'. Valid: {REPO_TERMS}")
        return
    metric = metric.upper()
    if metric not in REPO_METRICS:
        print(f"  Unknown metric '{metric}'. Valid: {REPO_METRICS}")
        return
    vintage = vintage.upper()
    if vintage not in ("P", "F"):
        print(f"  Unknown vintage '{vintage}'. Use 'P' (preliminary) or 'F' (final)")
        return

    mn = f"REPO-{seg}_{metric}_{term}-{vintage}"
    print(f"\n  Fetching {mn}...")
    rows = fetch_timeseries(mn, start_date=_years_ago(2))

    if not rows:
        print("  No data returned.")
        return

    rows = rows[-obs:]

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    seg_label = REPO_SEGMENT_LABELS.get(seg, seg)
    term_label = REPO_TERM_LABELS.get(term, term)
    metric_label = {"AR": "Average Rate", "OV": "Outstanding Volume",
                    "TV": "Transaction Volume"}.get(metric, metric)

    print(f"\n  {seg_label} -- {metric_label} -- {term_label} ({vintage})")
    print("  " + "=" * 70)
    print(f"  Mnemonic: {mn}  ({len(rows)} obs)")
    print(f"  {'Date':<12} {'Value':>15}")
    print(f"  {'-'*12} {'-'*15}")

    for d, v in rows[-30:]:
        if metric == "AR":
            v_s = _fmt_pct(v, decimals=3)
        else:
            v_s = _fmt_billions(_to_billions(v)) if isinstance(v, (int, float)) else "--"
        print(f"  {d:<12} {v_s:>15}")

    vals = [v for _, v in rows if isinstance(v, (int, float))]
    if vals:
        latest = vals[-1]
        lo = min(vals)
        hi = max(vals)
        avg = sum(vals) / len(vals)
        if metric == "AR":
            print(f"\n  Range: {lo:.3f}% -- {hi:.3f}%  |  Mean: {avg:.3f}%  |  Latest: {latest:.3f}%")
        else:
            print(f"\n  Range: {_fmt_billions(_to_billions(lo))} -- {_fmt_billions(_to_billions(hi))}"
                  f"  |  Mean: {_fmt_billions(_to_billions(avg))}  |  "
                  f"Latest: {_fmt_billions(_to_billions(latest))}")
    print()

    if export_fmt:
        out = [{"date": d, "value": v} for d, v in rows]
        _do_export(out, f"ofr_repo_{seg}_{metric}_{term}", export_fmt)
    return rows


# =============================================================================
# COMMANDS: Curated -- Money Market Funds (MMF)
# =============================================================================

def cmd_mmf(as_json=False, export_fmt=None):
    """MMF holdings composition latest snapshot."""
    print("\n  Fetching MMF holdings composition...")
    start = _years_ago(2)
    mnemonics = list(MMF_COMPOSITION.values())
    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for label, mn in MMF_COMPOSITION.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        # 12mo ago value
        prior_year_v = None
        if last_d:
            try:
                ly_target = _date_minus(last_d, 365)
                # Find closest <= ly_target
                for d, v in pairs:
                    if d <= ly_target and v is not None:
                        prior_year_v = v
            except Exception:
                pass
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "value_raw": last_v,
            "value_bn": _to_billions(last_v) if last_v else None,
            "value_tn": _to_trillions(last_v) if last_v else None,
            "yoy_pct": ((last_v - prior_year_v) / prior_year_v * 100)
                        if last_v and prior_year_v else None,
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    last_date = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  MMF Holdings Composition (as of {last_date})")
    print("  " + "=" * 75)
    print(f"  {'Category':<32} {'Value ($B)':>14} {'YoY %':>10}")
    print(f"  {'-'*32} {'-'*14} {'-'*10}")

    for label, snap in snapshot.items():
        bn = snap["value_bn"]
        yoy = snap["yoy_pct"]
        print(f"  {label:<32} {_fmt_billions(bn):>14} "
              f"{_fmt_pct(yoy, decimals=1, sign=True):>10}")

    total = snapshot.get("Total Investments", {}).get("value_tn")
    if total:
        print(f"\n  Total MMF Industry: {_fmt_trillions(total)}")

    rp_fed = snapshot.get("  RP w/ Federal Reserve", {}).get("value_bn")
    if rp_fed is not None:
        if rp_fed > 500:
            assessment = "Heavy ON RRP usage -- substantial excess liquidity"
        elif rp_fed > 100:
            assessment = "Moderate ON RRP usage"
        elif rp_fed > 20:
            assessment = "Low ON RRP -- reserves declining"
        else:
            assessment = "Minimal ON RRP -- monitor reserve scarcity"
        print(f"  Fed RP Usage: {_fmt_billions(rp_fed)}  -- {assessment}")
    print()

    if export_fmt:
        rows = []
        for label, snap in snapshot.items():
            rows.append({
                "label": label.strip(),
                "mnemonic": snap["mnemonic"],
                "date": snap["date"],
                "value_bn": snap["value_bn"],
                "yoy_pct": snap["yoy_pct"],
            })
        _do_export(rows, "ofr_mmf", export_fmt)
    return snapshot


def cmd_mmf_history(obs=24, as_json=False, export_fmt=None):
    """MMF holdings time series across major categories."""
    print(f"\n  Fetching MMF holdings history (last {obs} months)...")
    # Pull a smaller curated set
    keys = ["Total Investments", "U.S. Treasury Securities",
            "Repurchase Agreements", "  RP w/ Federal Reserve",
            "Bank-Related Assets", "Federal Agency / GSE"]
    mnemonics = [MMF_COMPOSITION[k] for k in keys]
    data = fetch_multifull(mnemonics, start_date=_years_ago(obs / 12 + 1))

    history = OrderedDict()
    for label, mn in zip(keys, mnemonics):
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        history[label] = pairs[-obs:]

    if as_json:
        print(json.dumps(history, indent=2))
        return history

    all_dates = sorted(set(d for pairs in history.values() for d, _ in pairs))[-obs:]

    print(f"\n  MMF Investment History ({len(all_dates)} months)")
    print("  " + "=" * 110)
    header = f"  {'Date':<12}"
    for label in keys:
        header += f" {label.strip()[:14]:>16}"
    print(header)
    print("  " + "-" * 110)

    lookups = {label: _to_dict(history.get(label, [])) for label in keys}
    for d in all_dates:
        line = f"  {d:<12}"
        for label in keys:
            v = lookups[label].get(d)
            line += f" {_fmt_billions(_to_billions(v)):>16}" if v is not None else f" {'--':>16}"
        print(line)

    if len(all_dates) >= 2:
        first = all_dates[0]
        last = all_dates[-1]
        print(f"\n  Change from {first} to {last}:")
        for label in keys:
            v0 = lookups[label].get(first)
            v1 = lookups[label].get(last)
            if v0 and v1:
                chg = _to_billions(v1 - v0)
                pct = (v1 - v0) / v0 * 100
                print(f"    {label.strip():<32} {_fmt_billions(chg, sign=True):>14} "
                      f"({pct:+.1f}%)")

    print()

    if export_fmt:
        out = []
        for d in all_dates:
            row = {"date": d}
            for label in keys:
                v = lookups[label].get(d)
                row[label.strip()] = _to_billions(v) if v is not None else None
            out.append(row)
        _do_export(out, "ofr_mmf_history", export_fmt)
    return history


# =============================================================================
# COMMANDS: Curated -- Treasury Yield Curve (TYLD)
# =============================================================================

def cmd_yields(obs=20, as_json=False, export_fmt=None):
    """Treasury constant maturity yield curve -- full curve latest + recent history."""
    print("\n  Fetching Treasury constant maturity yield curve...")
    start = _years_ago(0.3)
    mnemonics = [t["mnemonic"] for t in TCMR_TENORS.values()]
    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for tenor, info in TCMR_TENORS.items():
        pairs = data.get(info["mnemonic"], {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        snapshot[tenor] = {
            "mnemonic": info["mnemonic"],
            "years": info["years"],
            "date": last_d,
            "yield": last_v,
            "history": pairs[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    latest_date = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  Treasury Constant Maturity Curve (as of {latest_date})")
    print("  " + "=" * 70)
    print(f"  {'Tenor':<8} {'Yield %':>10} {'Mnemonic'}")
    print(f"  {'-'*8} {'-'*10} {'-'*30}")

    yields_list = []
    for tenor, snap in snapshot.items():
        y = snap["yield"]
        if y is not None:
            yields_list.append((tenor, y))
        print(f"  {tenor:<8} {_fmt_pct(y, decimals=2):>10} {snap['mnemonic']}")

    # Curve shape diagnostics
    yld = {t: y for t, y in yields_list}
    print(f"\n  Curve Slopes")
    print("  " + "-" * 40)
    for a, b in [("2Y", "10Y"), ("3M", "10Y"), ("5Y", "30Y"), ("10Y", "30Y")]:
        if a in yld and b in yld:
            sp = (yld[b] - yld[a]) * 100
            shape = "steepening" if sp > 0 else "inverted"
            print(f"  {a}-{b}:  {_fmt_bps(sp)}  ({shape})")

    if "3M" in yld and "10Y" in yld:
        sp = (yld["3M"] - yld["10Y"]) * 100
        print(f"\n  3M-10Y inversion (Fed-favored recession signal): {_fmt_bps(sp)}")
        if sp > 50:
            print(f"  Signal: STRONGLY INVERTED -- historical recession lead indicator")
        elif sp > 0:
            print(f"  Signal: INVERTED")
        else:
            print(f"  Signal: NORMAL (positively sloped)")
    print()

    if export_fmt:
        out = [{
            "tenor": t,
            "years": snapshot[t]["years"],
            "mnemonic": snapshot[t]["mnemonic"],
            "date": snapshot[t]["date"],
            "yield_pct": snapshot[t]["yield"],
        } for t in TCMR_TENORS]
        _do_export(out, "ofr_yields", export_fmt)
    return snapshot


def cmd_curve(as_json=False, export_fmt=None):
    """Treasury yield curve with daily/weekly/monthly/yearly deltas."""
    print("\n  Fetching Treasury curve with deltas...")
    start = _years_ago(2)
    mnemonics = [t["mnemonic"] for t in TCMR_TENORS.values()]
    data = fetch_multifull(mnemonics, start_date=start)

    today_yield = OrderedDict()
    history = OrderedDict()
    for tenor, info in TCMR_TENORS.items():
        pairs = data.get(info["mnemonic"], {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        today_yield[tenor] = (last_d, last_v)
        history[tenor] = pairs

    latest_date = next((d for d, v in today_yield.values() if d), None)
    if not latest_date:
        print("  No data returned.")
        return

    def _yield_at(tenor, target_date):
        """Find yield at-or-before target_date."""
        prev = None
        for d, v in history[tenor]:
            if v is None:
                continue
            if d > target_date:
                break
            prev = (d, v)
        return prev[1] if prev else None

    # Compute target dates
    targets = OrderedDict([
        ("Today",  latest_date),
        ("1d ago", _date_minus(latest_date, 1)),
        ("1w ago", _date_minus(latest_date, 7)),
        ("1m ago", _date_minus(latest_date, 30)),
        ("3m ago", _date_minus(latest_date, 90)),
        ("1y ago", _date_minus(latest_date, 365)),
    ])

    table = OrderedDict()
    for tenor in TCMR_TENORS:
        row = OrderedDict()
        for label, td in targets.items():
            if label == "Today":
                row[label] = today_yield[tenor][1]
            else:
                row[label] = _yield_at(tenor, td)
        table[tenor] = row

    if as_json:
        print(json.dumps({"date": latest_date, "table": table}, indent=2))
        return table

    print(f"\n  Treasury Yield Curve with Deltas (as of {latest_date})")
    print("  " + "=" * 100)
    header = f"  {'Tenor':<6}"
    for label in targets:
        header += f" {label:>10}"
    header += f" {'1d Δbp':>10} {'1w Δbp':>10} {'1m Δbp':>10} {'1y Δbp':>10}"
    print(header)
    print("  " + "-" * 100)

    for tenor, row in table.items():
        line = f"  {tenor:<6}"
        for label in targets:
            line += f" {_fmt_pct(row[label], decimals=2):>10}"

        today_v = row["Today"]
        for label in ["1d ago", "1w ago", "1m ago", "1y ago"]:
            prior = row[label]
            if today_v is not None and prior is not None:
                d_bp = (today_v - prior) * 100
                line += f" {_fmt_bps(d_bp):>10}"
            else:
                line += f" {'--':>10}"
        print(line)

    print()

    if export_fmt:
        out = []
        for tenor, row in table.items():
            rec = {"tenor": tenor}
            for label in targets:
                rec[label.replace(" ago", "_ago").replace(" ", "_")] = row[label]
            out.append(rec)
        _do_export(out, "ofr_curve", export_fmt)
    return table


# =============================================================================
# COMMANDS: Curated -- Primary Dealer (NYPD)
# =============================================================================

def cmd_pd_financing(obs=12, as_json=False, export_fmt=None):
    """Primary dealer securities borrowing / lending activity (NYPD via OFR).

    NYPD reports weekly dealer activity by collateral type. The OFR-published
    repo/reverse-repo aggregates are stale (stopped late 2021) -- this command
    focuses on the active SB (Securities Borrowed) and SL (Securities Lent)
    series. For real-time repo/RRP operations, use nyfed.py.
    """
    print(f"\n  Fetching primary dealer SB/SL activity (last {obs} weeks)...")
    start = _years_ago(2)
    mnemonics = list(NYPD_FINANCING.values())
    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for label, mn in NYPD_FINANCING.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        # Filter nulls
        non_null = [(d, v) for d, v in pairs if v is not None]
        last_d, last_v = (non_null[-1] if non_null else (None, None))
        prev_v = non_null[-2][1] if len(non_null) >= 2 else None
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "value_raw": last_v,
            "value_bn": _to_billions(last_v) if last_v is not None else None,
            "wow_chg_bn": _to_billions(last_v - prev_v)
                          if last_v is not None and prev_v is not None else None,
            "history": non_null[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    latest_date = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  Primary Dealer Securities Lending / Borrowing (as of {latest_date})")
    print(f"  SB=Securities Borrowed (dealer borrows securities)")
    print(f"  SL=Securities Lent (dealer lends securities)")
    print("  " + "=" * 90)
    print(f"  {'Series':<28} {'Volume ($B)':>14} {'1w Chg':>14} {'Mnemonic'}")
    print(f"  {'-'*28} {'-'*14} {'-'*14} {'-'*26}")

    for label, snap in snapshot.items():
        bn = snap["value_bn"]
        chg = snap["wow_chg_bn"]
        print(f"  {label:<28} {_fmt_billions(bn):>14} "
              f"{_fmt_billions(chg, sign=True):>14} {snap['mnemonic']}")

    # Net securities intermediation
    sb_t = snapshot.get("SB: Treasury Total", {}).get("value_bn")
    sl_t = snapshot.get("SL: Treasury Total", {}).get("value_bn")
    if sb_t is not None and sl_t is not None:
        net = sb_t - sl_t
        print(f"\n  Net Treasury Sec Lending (SB -- SL): {_fmt_billions(net, sign=True)}")
        if net > 0:
            print(f"  Dealers net borrowers of Treasuries (covering shorts / spec demand)")
        else:
            print(f"  Dealers net lenders of Treasuries (long inventory financed via SL)")

    print()
    print(f"  Note: OFR's broader repo/RRP totals (NYPD-PD_RP_TOT-A, "
          f"NYPD-PD_RRP_TOT-A) stopped publishing in late 2021. "
          f"For real-time repo data use nyfed.py.")
    print()

    if export_fmt:
        rows = []
        for label, snap in snapshot.items():
            rows.append({
                "label": label,
                "mnemonic": snap["mnemonic"],
                "date": snap["date"],
                "value_bn": snap["value_bn"],
                "wow_chg_bn": snap["wow_chg_bn"],
            })
        _do_export(rows, "ofr_pd_financing", export_fmt)
    return snapshot


def cmd_pd_fails(obs=8, as_json=False, export_fmt=None):
    """Primary dealer fails to deliver / receive."""
    print(f"\n  Fetching primary dealer fails (last {obs} weeks)...")
    start = _years_ago(2)
    mnemonics = list(NYPD_FAILS.values())
    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for label, mn in NYPD_FAILS.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "value_bn": _to_billions(last_v) if last_v is not None else None,
            "history": pairs[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    latest_date = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  Primary Dealer Fails to Deliver (FtD) and Receive (FtR) (as of {latest_date})")
    print("  " + "=" * 75)
    print(f"  {'Series':<28} {'Latest ($B)':>14} {'Mnemonic'}")
    print(f"  {'-'*28} {'-'*14} {'-'*22}")

    for label, snap in snapshot.items():
        print(f"  {label:<28} {_fmt_billions(snap['value_bn']):>14} {snap['mnemonic']}")

    # Check for elevated fails
    ftd_total = snapshot.get("FtD: Total", {}).get("value_bn")
    if ftd_total is not None:
        if ftd_total > 100:
            print(f"\n  FtD Assessment: {_fmt_billions(ftd_total)} elevated -- "
                  f"settlement strain or scarcity")
        else:
            print(f"\n  FtD Assessment: {_fmt_billions(ftd_total)} normal")
    print()

    if export_fmt:
        rows = []
        for label, snap in snapshot.items():
            rows.append({
                "label": label,
                "mnemonic": snap["mnemonic"],
                "date": snap["date"],
                "value_bn": snap["value_bn"],
            })
        _do_export(rows, "ofr_pd_fails", export_fmt)
    return snapshot


# =============================================================================
# COMMANDS: Curated -- Hedge Fund Form PF (FPF)
# =============================================================================

def cmd_form_pf(obs=8, as_json=False, export_fmt=None):
    """SEC Form PF latest aggregates: gross/net assets + borrowing breakdown."""
    print(f"\n  Fetching SEC Form PF aggregates (last {obs} quarters)...")
    start = _years_ago(obs / 4 + 1)
    mnemonics = list(FPF_TOTALS.values())
    data = fetch_multifull(mnemonics, start_date=start)

    snapshot = OrderedDict()
    for label, mn in FPF_TOTALS.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        prev_v = None
        if len(pairs) >= 2:
            for d, v in reversed(pairs[:-1]):
                if v is not None:
                    prev_v = v
                    break
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "value_raw": last_v,
            "value_tn": _to_trillions(last_v) if last_v is not None else None,
            "value_bn": _to_billions(last_v) if last_v is not None else None,
            "qoq_pct": ((last_v - prev_v) / prev_v * 100)
                       if last_v and prev_v else None,
            "history": pairs[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    latest_date = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  SEC Form PF -- Hedge Fund Aggregates (as of {latest_date})")
    print("  " + "=" * 90)
    print(f"  {'Metric':<32} {'Latest':>16} {'QoQ %':>10} {'Mnemonic'}")
    print(f"  {'-'*32} {'-'*16} {'-'*10} {'-'*30}")

    for label, snap in snapshot.items():
        if snap["value_tn"] and snap["value_tn"] >= 1.0:
            v_s = _fmt_trillions(snap["value_tn"])
        else:
            v_s = _fmt_billions(snap["value_bn"])
        print(f"  {label:<32} {v_s:>16} "
              f"{_fmt_pct(snap['qoq_pct'], decimals=1, sign=True):>10} "
              f"{snap['mnemonic']}")

    gav = snapshot.get("Qualifying HF: Gross Assets", {}).get("value_raw")
    nav = snapshot.get("Qualifying HF: Net Assets", {}).get("value_raw")
    if gav and nav:
        leverage = gav / nav
        print(f"\n  Aggregate Gross/Net leverage: {leverage:.2f}x  "
              f"(GAV/NAV ratio)")

    repo = snapshot.get("Borrowing: Repo", {}).get("value_raw")
    pb = snapshot.get("Borrowing: Prime Brokerage", {}).get("value_raw")
    other = snapshot.get("Borrowing: Other Secured", {}).get("value_raw")
    total_borrow = sum(x for x in (repo, pb, other) if x)
    if total_borrow:
        print(f"\n  Borrowing Composition (% of total ${_to_billions(total_borrow):,.0f}B)")
        if repo:
            print(f"    Repo:            {_fmt_billions(_to_billions(repo))} "
                  f"({repo / total_borrow * 100:.1f}%)")
        if pb:
            print(f"    Prime Brokerage: {_fmt_billions(_to_billions(pb))} "
                  f"({pb / total_borrow * 100:.1f}%)")
        if other:
            print(f"    Other Secured:   {_fmt_billions(_to_billions(other))} "
                  f"({other / total_borrow * 100:.1f}%)")
    print()

    if export_fmt:
        rows = [{
            "label": label,
            "mnemonic": snap["mnemonic"],
            "date": snap["date"],
            "value_raw": snap["value_raw"],
            "value_bn": snap["value_bn"],
            "qoq_pct": snap["qoq_pct"],
        } for label, snap in snapshot.items()]
        _do_export(rows, "ofr_form_pf", export_fmt)
    return snapshot


def cmd_form_pf_strategy(as_json=False, export_fmt=None):
    """Form PF gross / net asset breakdown by strategy."""
    print("\n  Fetching Form PF by strategy...")
    # Some strategies (FOF, FUTURES) don't publish BORROWING_SUM; pull GAV/NAV
    # in one batch and BORROWING in a separate forgiving batch.
    series_map = OrderedDict()
    gav_nav_mns = []
    bor_mns = []
    for s in FPF_STRATEGIES:
        gav_mn = f"FPF-STRATEGY_{s}_GAV_SUM"
        nav_mn = f"FPF-STRATEGY_{s}_NAV_SUM"
        bor_mn = f"FPF-STRATEGY_{s}_BORROWING_SUM"
        series_map[s] = {"gav": gav_mn, "nav": nav_mn, "borrow": bor_mn}
        gav_nav_mns.extend([gav_mn, nav_mn])
        bor_mns.append(bor_mn)

    data = fetch_multifull(gav_nav_mns, start_date=_years_ago(2))
    # Borrowing -- pull individually so one bad mnemonic doesn't kill the batch
    # Some strategies (FOF, FUTURES) genuinely don't publish BORROWING, so quiet=True.
    for bor_mn in bor_mns:
        bor_data = fetch_multifull([bor_mn], start_date=_years_ago(2), quiet=True)
        if bor_data:
            data.update(bor_data)

    rows = OrderedDict()
    for s, refs in series_map.items():
        gav = _last_pair(data.get(refs["gav"], {}).get("timeseries", {}).get("aggregation", []))[1]
        nav = _last_pair(data.get(refs["nav"], {}).get("timeseries", {}).get("aggregation", []))[1]
        bor = _last_pair(data.get(refs["borrow"], {}).get("timeseries", {}).get("aggregation", []))[1]
        last_d = _last_pair(data.get(refs["gav"], {}).get("timeseries", {}).get("aggregation", []))[0]
        rows[s] = {
            "label": FPF_STRATEGY_LABELS.get(s, s),
            "date": last_d,
            "gav_bn": _to_billions(gav) if gav else None,
            "nav_bn": _to_billions(nav) if nav else None,
            "borrow_bn": _to_billions(bor) if bor else None,
            "leverage": (gav / nav) if gav and nav else None,
        }

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    latest = next((r["date"] for r in rows.values() if r["date"]), "--")
    print(f"\n  Form PF by Strategy (as of {latest})")
    print("  " + "=" * 90)
    print(f"  {'Strategy':<22} {'GAV ($B)':>12} {'NAV ($B)':>12} {'Lev x':>8} "
          f"{'Borrowing ($B)':>16}")
    print(f"  {'-'*22} {'-'*12} {'-'*12} {'-'*8} {'-'*16}")

    sorted_rows = sorted(rows.values(), key=lambda r: r["gav_bn"] or 0, reverse=True)
    for r in sorted_rows:
        print(f"  {r['label']:<22} {_fmt_billions(r['gav_bn']):>12} "
              f"{_fmt_billions(r['nav_bn']):>12} "
              f"{(r['leverage'] or 0):>7.2f}x "
              f"{_fmt_billions(r['borrow_bn']):>16}")

    total_gav = sum(r["gav_bn"] for r in rows.values() if r["gav_bn"])
    total_nav = sum(r["nav_bn"] for r in rows.values() if r["nav_bn"])
    if total_gav and total_nav:
        print(f"\n  Aggregate: GAV {_fmt_billions(total_gav)}  |  "
              f"NAV {_fmt_billions(total_nav)}  |  "
              f"Leverage {total_gav / total_nav:.2f}x")
    print()

    if export_fmt:
        _do_export(list(rows.values()), "ofr_form_pf_strategy", export_fmt)
    return rows


def cmd_form_pf_stress(as_json=False, export_fmt=None):
    """Form PF stress test results across stress scenarios."""
    print("\n  Fetching Form PF stress test results...")
    mnemonics = []
    for spec in FPF_STRESS_TESTS.values():
        mnemonics.extend([spec["p5"], spec["p50"]])

    data = fetch_multifull(mnemonics, start_date=_years_ago(3))

    rows = OrderedDict()
    for scenario, spec in FPF_STRESS_TESTS.items():
        p5 = _last_pair(data.get(spec["p5"], {}).get("timeseries", {}).get("aggregation", []))[1]
        p50 = _last_pair(data.get(spec["p50"], {}).get("timeseries", {}).get("aggregation", []))[1]
        last_d = _last_pair(data.get(spec["p5"], {}).get("timeseries", {}).get("aggregation", []))[0]
        rows[scenario] = {
            "date": last_d,
            "p5_pct":  p5,
            "p50_pct": p50,
            "p5_mnemonic": spec["p5"],
            "p50_mnemonic": spec["p50"],
        }

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    latest = next((r["date"] for r in rows.values() if r["date"]), "--")
    print(f"\n  Form PF Stress Test Results (as of {latest})")
    print(f"  P5 = effect on 5th-percentile (worst-affected) fund")
    print(f"  P50 = effect on median fund")
    print("  " + "=" * 75)
    print(f"  {'Scenario':<30} {'P5 effect':>14} {'P50 effect':>14}")
    print(f"  {'-'*30} {'-'*14} {'-'*14}")

    for scenario, r in rows.items():
        p5_s = _fmt_pct(r["p5_pct"], decimals=2, sign=True) if r["p5_pct"] is not None else "--"
        p50_s = _fmt_pct(r["p50_pct"], decimals=2, sign=True) if r["p50_pct"] is not None else "--"
        print(f"  {scenario:<30} {p5_s:>14} {p50_s:>14}")
    print()

    if export_fmt:
        out = [{
            "scenario": k,
            "date": r["date"],
            "p5_pct": r["p5_pct"],
            "p50_pct": r["p50_pct"],
        } for k, r in rows.items()]
        _do_export(out, "ofr_form_pf_stress", export_fmt)
    return rows


# =============================================================================
# COMMANDS: Curated -- CFTC Traders in Financial Futures (TFF)
# =============================================================================

def cmd_tff(group="LF", as_json=False, export_fmt=None):
    """CFTC Traders in Financial Futures positioning by category."""
    group = group.upper()
    if group not in TFF_GROUPS:
        print(f"  Unknown group '{group}'. Valid: {list(TFF_GROUPS.keys())}")
        return

    print(f"\n  Fetching CFTC TFF positioning for {TFF_GROUPS[group]} ({group})...")

    # AI / DI / OR only publish TREAS-aggregate series; LF publishes the full
    # 23-contract surface. Restrict contract list per group accordingly.
    if group == "LF":
        contracts = list(TFF_CONTRACTS.keys())
    else:
        contracts = ["TREAS"]

    # AI/DI/OR don't publish NET_POSITION (only LONG/SHORT), so we'll compute
    # NET = LONG - SHORT manually for those. Pull contracts individually to
    # avoid one missing mnemonic poisoning the whole batch.
    data = {}
    for contract in contracts:
        sub_mns = [
            f"TFF-{group}_{contract}_LONG_POSITION",
            f"TFF-{group}_{contract}_SHORT_POSITION",
        ]
        if group == "LF":
            sub_mns.append(f"TFF-{group}_{contract}_NET_POSITION")
        sub_data = fetch_multifull(sub_mns, start_date=_years_ago(2), quiet=True)
        if sub_data:
            data.update(sub_data)

    rows = OrderedDict()
    contract_iter = [(c, TFF_CONTRACTS[c]) for c in contracts if c in TFF_CONTRACTS]
    for contract, label in contract_iter:
        long_mn = f"TFF-{group}_{contract}_LONG_POSITION"
        short_mn = f"TFF-{group}_{contract}_SHORT_POSITION"
        net_mn = f"TFF-{group}_{contract}_NET_POSITION"
        long_pairs = data.get(long_mn, {}).get("timeseries", {}).get("aggregation", [])
        short_pairs = data.get(short_mn, {}).get("timeseries", {}).get("aggregation", [])
        net_pairs = data.get(net_mn, {}).get("timeseries", {}).get("aggregation", [])

        long_d, long_v = _last_pair(long_pairs)
        _, short_v = _last_pair(short_pairs)
        net_d, net_v = _last_pair(net_pairs)

        # Compute NET if not published (AI/DI/OR groups)
        if net_v is None and long_v is not None and short_v is not None:
            net_v = long_v - short_v
            net_d = long_d

        if long_v is None and short_v is None and net_v is None:
            continue

        # Compute prior-week net for change
        prev_net = None
        if net_pairs:
            for d, v in reversed(net_pairs[:-1]):
                if v is not None:
                    prev_net = v
                    break
        # Fallback: compute prev_net from LONG/SHORT pairs
        if prev_net is None and len(long_pairs) >= 2 and len(short_pairs) >= 2:
            long_lookup = _to_dict(long_pairs)
            short_lookup = _to_dict(short_pairs)
            common_dates = sorted(set(long_lookup) & set(short_lookup))
            if len(common_dates) >= 2:
                pd_ = common_dates[-2]
                prev_net = long_lookup[pd_] - short_lookup[pd_]

        rows[contract] = {
            "label": label,
            "date": net_d or long_d,
            "long_bn": _to_billions(long_v) if long_v else None,
            "short_bn": _to_billions(short_v) if short_v else None,
            "net_bn": _to_billions(net_v) if net_v is not None else None,
            "wow_chg_bn": _to_billions(net_v - prev_net)
                          if net_v is not None and prev_net is not None else None,
        }

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    latest = next((r["date"] for r in rows.values() if r["date"]), "--")
    print(f"\n  TFF Positioning -- {TFF_GROUPS[group]} (as of {latest})")
    print(f"  Notional positions in $bn")
    print("  " + "=" * 95)
    print(f"  {'Contract':<8} {'Description':<28} {'Long':>12} {'Short':>12} "
          f"{'Net':>12} {'1w Chg':>12}")
    print(f"  {'-'*8} {'-'*28} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

    sorted_rows = sorted(rows.items(), key=lambda x: abs(x[1]["net_bn"] or 0), reverse=True)
    for code, r in sorted_rows:
        print(f"  {code:<8} {r['label'][:28]:<28} "
              f"{_fmt_billions(r['long_bn']):>12} "
              f"{_fmt_billions(r['short_bn']):>12} "
              f"{_fmt_billions(r['net_bn'], sign=True):>12} "
              f"{_fmt_billions(r['wow_chg_bn'], sign=True):>12}")

    print()

    if export_fmt:
        out = []
        for code, r in rows.items():
            out.append({
                "group": group,
                "contract": code,
                "description": r["label"],
                "date": r["date"],
                "long_bn": r["long_bn"],
                "short_bn": r["short_bn"],
                "net_bn": r["net_bn"],
                "wow_chg_bn": r["wow_chg_bn"],
            })
        _do_export(out, f"ofr_tff_{group}", export_fmt)
    return rows


# =============================================================================
# COMMANDS: Curated -- SCOOS / FICC
# =============================================================================

def cmd_scoos(obs=8, as_json=False, export_fmt=None):
    """Senior Credit Officer Opinion Survey -- latest dealer survey."""
    print(f"\n  Fetching SCOOS dealer survey (last {obs} quarters)...")
    raw = fetch_mnemonics(dataset="scoos") or []
    if not raw:
        print("  No data returned.")
        return

    series_list = [{"mnemonic": s["mnemonic"], "name": s["series_name"]} for s in raw]
    mnemonics = [s["mnemonic"] for s in series_list]

    data = fetch_multifull(mnemonics, start_date=_years_ago(obs / 4 + 1))

    rows = OrderedDict()
    for s in series_list:
        mn = s["mnemonic"]
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        prev_v = None
        if len(pairs) >= 2:
            for d, v in reversed(pairs[:-1]):
                if v is not None:
                    prev_v = v
                    break
        rows[mn] = {
            "name": s["name"],
            "date": last_d,
            "value": last_v,
            "qoq_chg": (last_v - prev_v) if last_v is not None and prev_v is not None else None,
        }

    if as_json:
        print(json.dumps(rows, indent=2))
        return rows

    latest = next((r["date"] for r in rows.values() if r["date"]), "--")
    print(f"\n  SCOOS Dealer Survey (as of {latest})")
    print(f"  Net % of dealer respondents reporting changes (positive = tightening)")
    print("  " + "=" * 110)
    print(f"  {'Series':<32} {'Latest':>10} {'QoQ Δ':>10} {'Description'}")
    print(f"  {'-'*32} {'-'*10} {'-'*10} {'-'*55}")

    for mn, r in rows.items():
        print(f"  {mn[:32]:<32} {_fmt_num(r['value'], decimals=1):>10} "
              f"{_fmt_num(r['qoq_chg'], decimals=1, sign=True):>10} "
              f"{r['name'][:60]}")
    print()

    if export_fmt:
        out = [{
            "mnemonic": mn,
            "name": r["name"],
            "date": r["date"],
            "value": r["value"],
            "qoq_chg": r["qoq_chg"],
        } for mn, r in rows.items()]
        _do_export(out, "ofr_scoos", export_fmt)
    return rows


def cmd_ficc(obs=24, as_json=False, export_fmt=None):
    """FICC sponsored repo volumes."""
    print(f"\n  Fetching FICC sponsored repo (last {obs} months)...")
    mnemonics = list(FICC_SERIES.values())
    data = fetch_multifull(mnemonics, start_date=_years_ago(obs / 12 + 1))

    snapshot = OrderedDict()
    for label, mn in FICC_SERIES.items():
        pairs = data.get(mn, {}).get("timeseries", {}).get("aggregation", [])
        last_d, last_v = _last_pair(pairs)
        prev_v = None
        if len(pairs) >= 2:
            for d, v in reversed(pairs[:-1]):
                if v is not None:
                    prev_v = v
                    break
        snapshot[label] = {
            "mnemonic": mn,
            "date": last_d,
            "value_bn": _to_billions(last_v) if last_v else None,
            "value_tn": _to_trillions(last_v) if last_v else None,
            "mom_chg_bn": _to_billions(last_v - prev_v) if last_v and prev_v else None,
            "history": pairs[-obs:],
        }

    if as_json:
        print(json.dumps(snapshot, indent=2))
        return snapshot

    latest = next((s["date"] for s in snapshot.values() if s["date"]), "--")
    print(f"\n  FICC Sponsored Repo Service Volumes (as of {latest})")
    print("  " + "=" * 75)
    print(f"  {'Service':<24} {'Volume':>16} {'1m Chg':>14} {'Mnemonic'}")
    print(f"  {'-'*24} {'-'*16} {'-'*14} {'-'*22}")

    for label, snap in snapshot.items():
        if snap["value_tn"] and snap["value_tn"] >= 1.0:
            v_s = _fmt_trillions(snap["value_tn"])
        else:
            v_s = _fmt_billions(snap["value_bn"])
        print(f"  {label:<24} {v_s:>16} "
              f"{_fmt_billions(snap['mom_chg_bn'], sign=True):>14} {snap['mnemonic']}")

    print()
    print(f"  Recent history (last {min(obs, 12)} months, $bn)")
    print("  " + "-" * 70)
    header = f"  {'Date':<12}"
    for label in FICC_SERIES:
        header += f" {label[:24]:>26}"
    print(header)

    all_dates = sorted(set(d for snap in snapshot.values() for d, _ in snap["history"]))[-obs:]
    lookups = {label: _to_dict(snap["history"]) for label, snap in snapshot.items()}
    for d in all_dates[-min(obs, 12):]:
        line = f"  {d:<12}"
        for label in FICC_SERIES:
            v = lookups[label].get(d)
            line += f" {_fmt_billions(_to_billions(v)):>26}" if v is not None else f" {'--':>26}"
        print(line)

    print()

    if export_fmt:
        out = []
        for d in all_dates:
            row = {"date": d}
            for label, snap in snapshot.items():
                v = lookups[label].get(d)
                row[snap["mnemonic"]] = _to_billions(v) if v else None
            out.append(row)
        _do_export(out, "ofr_ficc", export_fmt)
    return snapshot


# =============================================================================
# COMMANDS: Curated -- Financial Stress Index (FSI)
# =============================================================================

def cmd_fsi(as_json=False, export_fmt=None):
    """OFR Financial Stress Index latest with components and regions."""
    print("\n  Fetching OFR Financial Stress Index...")
    rows = fetch_fsi_csv()

    if not rows:
        print("  No data returned.")
        return

    latest = rows[-1]
    week_ago = rows[-6] if len(rows) >= 6 else rows[0]
    month_ago = rows[-22] if len(rows) >= 22 else rows[0]
    year_ago = rows[-252] if len(rows) >= 252 else rows[0]

    if as_json:
        out = {
            "latest": latest,
            "week_ago": week_ago,
            "month_ago": month_ago,
            "year_ago": year_ago,
            "all_time_min": min(rows, key=lambda r: r.get("OFR FSI") or 99),
            "all_time_max": max(rows, key=lambda r: r.get("OFR FSI") or -99),
        }
        print(json.dumps(out, indent=2, default=str))
        return latest

    print(f"\n  OFR Financial Stress Index (as of {latest['date']})")
    print(f"  33-variable daily global stress index. Positive = above-average stress.")
    print("  " + "=" * 80)

    fsi = latest.get("OFR FSI")
    print(f"\n  HEADLINE FSI:  {fsi:+.3f}")
    if fsi is None:
        regime = "--"
    elif fsi > 4:
        regime = "CRISIS-LEVEL stress (e.g. GFC 2008, COVID 2020)"
    elif fsi > 2:
        regime = "ELEVATED stress -- material strain in markets"
    elif fsi > 0.5:
        regime = "Mildly elevated -- above-average stress"
    elif fsi > -0.5:
        regime = "Near average"
    elif fsi > -2:
        regime = "Calm regime -- below-average stress"
    else:
        regime = "Very calm -- complacent risk environment"
    print(f"  Regime:        {regime}")

    # Deltas
    print(f"\n  Recent Movement")
    print("  " + "-" * 50)
    for label, prior in [("1d ago", rows[-2] if len(rows) >= 2 else None),
                          ("1w ago", week_ago),
                          ("1m ago", month_ago),
                          ("1y ago", year_ago)]:
        if prior:
            prior_v = prior.get("OFR FSI")
            if prior_v is not None and fsi is not None:
                chg = fsi - prior_v
                print(f"  {label:<10} {prior['date']}  FSI={prior_v:+.3f}  "
                      f"Δ={chg:+.3f}")

    # Component breakdown
    print(f"\n  Component Breakdown (today)")
    print("  " + "-" * 60)
    print(f"  {'Component':<22} {'Today':>10} {'1m Δ':>10}")
    print(f"  {'-'*22} {'-'*10} {'-'*10}")
    for comp in ["Credit", "Equity valuation", "Safe assets", "Funding", "Volatility"]:
        today_v = latest.get(comp)
        prior_v = month_ago.get(comp)
        if today_v is not None:
            chg = (today_v - prior_v) if prior_v is not None else None
            chg_s = f"{chg:+.3f}" if chg is not None else "--"
            print(f"  {comp:<22} {today_v:>+10.3f} {chg_s:>10}")

    # Regional breakdown
    print(f"\n  Regional Breakdown (today)")
    print("  " + "-" * 60)
    print(f"  {'Region':<28} {'Today':>10} {'1m Δ':>10}")
    print(f"  {'-'*28} {'-'*10} {'-'*10}")
    for region in ["United States", "Other advanced economies", "Emerging markets"]:
        today_v = latest.get(region)
        prior_v = month_ago.get(region)
        if today_v is not None:
            chg = (today_v - prior_v) if prior_v is not None else None
            chg_s = f"{chg:+.3f}" if chg is not None else "--"
            print(f"  {region:<28} {today_v:>+10.3f} {chg_s:>10}")

    # Historical context
    fsi_vals = [r.get("OFR FSI") for r in rows if r.get("OFR FSI") is not None]
    if fsi_vals:
        all_max = max(fsi_vals)
        all_min = min(fsi_vals)
        all_avg = sum(fsi_vals) / len(fsi_vals)
        # Percentile
        rank = sum(1 for v in fsi_vals if v < fsi)
        pct = rank / len(fsi_vals) * 100
        print(f"\n  Historical Context (since 2000)")
        print("  " + "-" * 60)
        print(f"  All-time high:    {all_max:+.3f}")
        print(f"  All-time low:     {all_min:+.3f}")
        print(f"  Long-run mean:    {all_avg:+.3f}")
        print(f"  Today's percentile: {pct:.1f} ({len(fsi_vals)} observations)")
    print()

    if export_fmt:
        out = {"latest": latest,
               "week_ago": week_ago,
               "month_ago": month_ago,
               "year_ago": year_ago}
        _do_export([out["latest"]], "ofr_fsi", export_fmt)
    return latest


def cmd_fsi_history(days=365, as_json=False, export_fmt=None):
    """OFR FSI time series."""
    print(f"\n  Fetching OFR FSI (last {days} days)...")
    rows = fetch_fsi_csv()

    if not rows:
        print("  No data returned.")
        return

    rows = rows[-days:]

    if as_json:
        print(json.dumps(rows, indent=2, default=str))
        return rows

    print(f"\n  OFR FSI History ({len(rows)} obs)")
    print("  " + "=" * 100)
    print(f"  {'Date':<12} {'FSI':>10} {'Credit':>10} {'EqVal':>10} "
          f"{'SafeAsst':>10} {'Funding':>10} {'Vol':>10} {'US':>10} {'OAE':>10} {'EM':>10}")
    print(f"  {'-'*12} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*10} "
          f"{'-'*10} {'-'*10} {'-'*10}")

    for r in rows[-30:]:
        line = f"  {r['date']:<12}"
        for k in ["OFR FSI", "Credit", "Equity valuation", "Safe assets",
                  "Funding", "Volatility", "United States",
                  "Other advanced economies", "Emerging markets"]:
            v = r.get(k)
            line += f" {v:>+10.3f}" if v is not None else f" {'--':>10}"
        print(line)

    if len(rows) > 30:
        print(f"  ... showing last 30 of {len(rows)} (use --json for full)")

    fsi_vals = [r.get("OFR FSI") for r in rows if r.get("OFR FSI") is not None]
    if fsi_vals:
        print(f"\n  Period: {rows[0]['date']} to {rows[-1]['date']}")
        print(f"  Range: {min(fsi_vals):+.3f} -- {max(fsi_vals):+.3f}  |  "
              f"Mean: {sum(fsi_vals)/len(fsi_vals):+.3f}  |  "
              f"Latest: {fsi_vals[-1]:+.3f}")
    print()

    if export_fmt:
        _do_export(rows, "ofr_fsi_history", export_fmt)
    return rows


# =============================================================================
# DASHBOARDS: composite views
# =============================================================================

def cmd_funding_snapshot(as_json=False, export_fmt=None):
    """Combined funding view: rates + repo + MMF + spreads."""
    print("\n  Building funding snapshot...")

    print("  [1/4] Reference rates...")
    fnyr = cmd_fnyr(obs=5, as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [2/4] Repo rates...")
    repo_rates = cmd_repo_rates(obs=5, as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [3/4] Repo volumes...")
    repo_vols = cmd_repo_volumes(obs=5, as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [4/4] MMF composition...")
    mmf = cmd_mmf(as_json=True)

    out = {"rates": fnyr, "repo_rates": repo_rates, "repo_volumes": repo_vols,
           "mmf": mmf, "timestamp": datetime.now().isoformat()}

    if as_json:
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║          OFR FUNDING SNAPSHOT                                ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝")

    sofr = (fnyr or {}).get("SOFR", {}).get("rate")
    effr = (fnyr or {}).get("EFFR", {}).get("rate")
    obfr = (fnyr or {}).get("OBFR", {}).get("rate")
    tgcr = (fnyr or {}).get("TGCR", {}).get("rate")
    bgcr = (fnyr or {}).get("BGCR", {}).get("rate")
    date = (fnyr or {}).get("SOFR", {}).get("date", "--")

    print(f"\n  REFERENCE RATES (as of {date})")
    print("  " + "-" * 50)
    if sofr is not None:
        print(f"  SOFR  {_fmt_pct(sofr)}    EFFR  {_fmt_pct(effr)}    OBFR  {_fmt_pct(obfr)}")
        print(f"  TGCR  {_fmt_pct(tgcr)}    BGCR  {_fmt_pct(bgcr)}")

    if sofr is not None and effr is not None:
        sp = (sofr - effr) * 100
        print(f"\n  SOFR - EFFR: {_fmt_bps(sp)}")

    print(f"\n  REPO MARKET (overnight rates)")
    print("  " + "-" * 50)
    for label, snap in (repo_rates or {}).items():
        if snap.get("rate") is not None:
            print(f"  {label:<24}  {_fmt_pct(snap['rate'])}")

    print(f"\n  REPO MARKET (outstanding volumes)")
    print("  " + "-" * 50)
    for label, snap in (repo_vols or {}).items():
        if snap.get("value_bn") is not None:
            print(f"  {label:<24}  {_fmt_billions(snap['value_bn'])}")

    print(f"\n  MMF POSITIONING")
    print("  " + "-" * 50)
    total_tn = (mmf or {}).get("Total Investments", {}).get("value_tn")
    if total_tn is not None:
        print(f"  Total Industry: {_fmt_trillions(total_tn)}")
    rp_fed_bn = (mmf or {}).get("  RP w/ Federal Reserve", {}).get("value_bn")
    if rp_fed_bn is not None:
        print(f"  ON RRP (MMF):   {_fmt_billions(rp_fed_bn)}")
    rp_t_bn = (mmf or {}).get("  RP backed by Treasury", {}).get("value_bn")
    if rp_t_bn is not None:
        print(f"  Treasury Repo:  {_fmt_billions(rp_t_bn)}")
    print()

    if export_fmt:
        flat = {
            "timestamp": out["timestamp"],
            "date": date,
            "sofr": sofr, "effr": effr, "obfr": obfr, "tgcr": tgcr, "bgcr": bgcr,
            "sofr_effr_bps": (sofr - effr) * 100 if sofr is not None and effr is not None else None,
            "repo_triv1_oo": (repo_rates or {}).get("Tri-Party (excl Fed)", {}).get("rate"),
            "repo_gcf_oo": (repo_rates or {}).get("GCF Repo", {}).get("rate"),
            "repo_dvp_oo": (repo_rates or {}).get("DVP Service", {}).get("rate"),
            "mmf_total_tn": total_tn,
            "mmf_rrp_bn": rp_fed_bn,
        }
        _do_export([flat], "ofr_funding_snapshot", export_fmt)
    return out


def cmd_stress_snapshot(as_json=False, export_fmt=None):
    """FSI + curve + funding -- comprehensive stress monitor."""
    print("\n  Building stress snapshot...")

    print("  [1/3] OFR FSI...")
    fsi = cmd_fsi(as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [2/3] Treasury yield curve...")
    curve = cmd_yields(as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [3/3] Repo rates...")
    repo = cmd_repo_rates(obs=5, as_json=True)

    out = {"fsi": fsi, "curve": curve, "repo": repo,
           "timestamp": datetime.now().isoformat()}

    if as_json:
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║          OFR STRESS SNAPSHOT                                 ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝")

    fsi_v = (fsi or {}).get("OFR FSI")
    print(f"\n  FINANCIAL STRESS INDEX (as of {(fsi or {}).get('date', '--')})")
    print(f"  Headline FSI: {fsi_v:+.3f}" if fsi_v is not None else "  No FSI data")

    if fsi_v is not None:
        print(f"\n  Component Contributions")
        for comp in ["Credit", "Equity valuation", "Safe assets", "Funding", "Volatility"]:
            v = fsi.get(comp)
            if v is not None:
                bar_len = int(abs(v) * 10) if abs(v) < 4 else 40
                bar = "█" * bar_len
                sign = "+" if v >= 0 else "-"
                print(f"    {comp:<22} {sign}{abs(v):.3f}  {bar}")

    yields_today = {t: snap.get("yield") for t, snap in (curve or {}).items()}
    print(f"\n  TREASURY CURVE (as of {(curve or {}).get('10Y', {}).get('date', '--')})")
    if "2Y" in yields_today and "10Y" in yields_today:
        sp_2_10 = (yields_today["10Y"] - yields_today["2Y"]) * 100 \
                   if yields_today["2Y"] and yields_today["10Y"] else None
        print(f"  3M={_fmt_pct(yields_today.get('3M'))}  "
              f"2Y={_fmt_pct(yields_today.get('2Y'))}  "
              f"10Y={_fmt_pct(yields_today.get('10Y'))}  "
              f"30Y={_fmt_pct(yields_today.get('30Y'))}")
        print(f"  2Y-10Y slope: {_fmt_bps(sp_2_10)}")
    if "3M" in yields_today and "10Y" in yields_today \
       and yields_today["3M"] and yields_today["10Y"]:
        sp = (yields_today["3M"] - yields_today["10Y"]) * 100
        signal = "INVERTED (recession signal)" if sp > 0 else "Normal"
        print(f"  3M-10Y inversion: {_fmt_bps(sp)}  -- {signal}")

    print(f"\n  FUNDING (Repo)")
    for label, snap in (repo or {}).items():
        if snap.get("rate") is not None:
            print(f"  {label:<24}  {_fmt_pct(snap['rate'])}")
    print()

    if export_fmt:
        _do_export([out], "ofr_stress_snapshot", export_fmt)
    return out


def cmd_hf_snapshot(as_json=False, export_fmt=None):
    """Hedge fund cross-source positioning snapshot."""
    print("\n  Building hedge fund snapshot...")

    print("  [1/4] Form PF totals...")
    fpf = cmd_form_pf(as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [2/4] Form PF by strategy...")
    strategy = cmd_form_pf_strategy(as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [3/4] CFTC TFF (Leveraged Funds)...")
    tff = cmd_tff(group="LF", as_json=True)
    time.sleep(REQUEST_DELAY)

    print("  [4/4] FICC sponsored repo...")
    ficc = cmd_ficc(obs=6, as_json=True)

    out = {"form_pf": fpf, "strategy": strategy, "tff": tff, "ficc": ficc,
           "timestamp": datetime.now().isoformat()}

    if as_json:
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  ╔══════════════════════════════════════════════════════════════╗")
    print(f"  ║          OFR HEDGE FUND SNAPSHOT                             ║")
    print(f"  ╚══════════════════════════════════════════════════════════════╝")

    gav = (fpf or {}).get("Qualifying HF: Gross Assets", {}).get("value_raw")
    nav = (fpf or {}).get("Qualifying HF: Net Assets", {}).get("value_raw")
    print(f"\n  AGGREGATE BALANCE SHEET (Form PF)")
    print(f"  Gross Assets: {_fmt_trillions(_to_trillions(gav))}  "
          f"Net Assets: {_fmt_trillions(_to_trillions(nav))}")
    if gav and nav:
        print(f"  Aggregate Leverage: {gav / nav:.2f}x")

    print(f"\n  TOP STRATEGIES BY GAV")
    sorted_strat = sorted((strategy or {}).items(),
                           key=lambda x: x[1].get("gav_bn") or 0, reverse=True)[:5]
    for s, r in sorted_strat:
        if r.get("gav_bn"):
            print(f"  {r['label']:<22}  GAV: {_fmt_billions(r['gav_bn'])}  "
                  f"Leverage: {(r.get('leverage') or 0):.2f}x")

    print(f"\n  TFF LEVERAGED FUND POSITIONING (top by absolute net)")
    sorted_tff = sorted((tff or {}).items(),
                         key=lambda x: abs(x[1].get("net_bn") or 0), reverse=True)[:8]
    for code, r in sorted_tff:
        if r.get("net_bn") is not None:
            print(f"  {r['label']:<28}  Net: {_fmt_billions(r['net_bn'], sign=True)}")

    print(f"\n  FICC SPONSORED REPO")
    for label, snap in (ficc or {}).items():
        if snap.get("value_bn") is not None:
            v = snap.get("value_tn") if snap.get("value_tn", 0) >= 1 else snap.get("value_bn")
            v_s = _fmt_trillions(v) if snap.get("value_tn", 0) >= 1 else _fmt_billions(v)
            print(f"  {label:<24}  {v_s}")
    print()

    if export_fmt:
        _do_export([out], "ofr_hf_snapshot", export_fmt)
    return out


# =============================================================================
# INTERACTIVE MENU
# =============================================================================

MENU = """
  =====================================================
   OFR -- Office of Financial Research API Client
   STFM (5 datasets) + HFM (4 datasets) + FSI
  =====================================================

  GENERIC API
     1) datasets       List all OFR datasets
     2) mnemonics      List mnemonics for a dataset
     3) search         Search across all mnemonics
     4) query          Get metadata for a mnemonic
     5) series         Fetch a single timeseries
     6) multi          Fetch multiple series
     7) spread         Compute spread between two series
     8) dataset-pull   Pull full dataset (all series)

  CURATED -- SHORT-TERM FUNDING
     9) fnyr           NY Fed reference rates + percentiles
    10) repo-rates     Tri-Party + GCF + DVP overnight rates
    11) repo-volumes   Repo outstanding volumes by segment
    12) repo-history   History of a specific repo series
    13) mmf            MMF holdings composition
    14) mmf-history    MMF investment time series

  CURATED -- TREASURY
    15) yields         Treasury constant maturity curve
    16) curve          Curve with daily/weekly/monthly deltas

  CURATED -- DEALER FINANCING (NYPD via OFR)
    17) pd-financing   Primary dealer repo / RRP / sec lending activity
    18) pd-fails       Primary dealer fails to deliver/receive

  CURATED -- HEDGE FUNDS
    19) form-pf            SEC Form PF aggregates
    20) form-pf-strategy   Form PF by strategy
    21) form-pf-stress     Stress test results
    22) tff                CFTC TFF positioning
    23) scoos              SCOOS dealer survey
    24) ficc               FICC sponsored repo

  CURATED -- STRESS
    25) fsi             Financial Stress Index
    26) fsi-history     FSI time series

  DASHBOARDS
    27) funding-snapshot   Rates + repo + MMF
    28) stress-snapshot    FSI + curve + funding
    29) hf-snapshot        Hedge fund cross-source

   q) quit
"""


# Interactive wrappers: each prompts then dispatches to cmd_*
def _i_datasets():
    cmd_datasets()

def _i_mnemonics():
    ds = _prompt(f"Dataset ({'/'.join(ALL_DATASETS.keys())} or empty for all)", "")
    q = _prompt("Filter (substring, optional)", "")
    cmd_mnemonics(dataset=ds or None, query=q or None)

def _i_search():
    q = _prompt("Search query (* and ? wildcards supported)")
    if not q:
        print("  Query required.")
        return
    cmd_search(q)

def _i_query():
    mn = _prompt("Mnemonic (e.g. FNYR-SOFR-A)")
    if not mn:
        return
    cmd_query(mn)

def _i_series():
    mn = _prompt("Mnemonic")
    if not mn:
        return
    start = _prompt("Start date YYYY-MM-DD (optional)", _years_ago(1))
    end = _prompt("End date YYYY-MM-DD (optional)", _today())
    cmd_series(mn, start_date=start, end_date=end)

def _i_multi():
    mns_str = _prompt("Mnemonics (comma-separated)")
    if not mns_str:
        return
    start = _prompt("Start date YYYY-MM-DD", _years_ago(1))
    cmd_multi(mns_str, start_date=start)

def _i_spread():
    x = _prompt("Mnemonic X")
    y = _prompt("Mnemonic Y")
    if not x or not y:
        return
    obs = _prompt("Number of observations", "60")
    cmd_spread(x, y, obs=int(obs))

def _i_dataset_pull():
    ds = _prompt(f"Dataset ({'/'.join(ALL_DATASETS.keys())})")
    if ds not in ALL_DATASETS:
        print(f"  Unknown dataset")
        return
    start = _prompt("Start date YYYY-MM-DD (optional)", _years_ago(2))
    cmd_dataset_pull(ds, start_date=start)

def _i_fnyr():
    obs = _prompt("Observations (recent)", "30")
    cmd_fnyr(obs=int(obs))

def _i_repo_rates():
    obs = _prompt("Observations", "30")
    cmd_repo_rates(obs=int(obs))

def _i_repo_volumes():
    obs = _prompt("Observations", "30")
    cmd_repo_volumes(obs=int(obs))

def _i_repo_history():
    seg = _prompt(f"Segment ({'/'.join(REPO_SEGMENTS)})", "GCF")
    term = _prompt(f"Term ({'/'.join(REPO_TERMS)})", "OO")
    metric = _prompt(f"Metric ({'/'.join(REPO_METRICS)})", "AR")
    vintage = _prompt("Vintage (P=preliminary / F=final)", "P")
    obs = _prompt("Observations", "60")
    cmd_repo_history(segment=seg, term=term, metric=metric, vintage=vintage, obs=int(obs))

def _i_mmf():
    cmd_mmf()

def _i_mmf_history():
    obs = _prompt("Months", "24")
    cmd_mmf_history(obs=int(obs))

def _i_yields():
    cmd_yields()

def _i_curve():
    cmd_curve()

def _i_pd_financing():
    obs = _prompt("Weeks", "12")
    cmd_pd_financing(obs=int(obs))

def _i_pd_fails():
    obs = _prompt("Weeks", "8")
    cmd_pd_fails(obs=int(obs))

def _i_form_pf():
    obs = _prompt("Quarters", "8")
    cmd_form_pf(obs=int(obs))

def _i_form_pf_strategy():
    cmd_form_pf_strategy()

def _i_form_pf_stress():
    cmd_form_pf_stress()

def _i_tff():
    g = _prompt(f"Group ({'/'.join(TFF_GROUPS.keys())})", "LF")
    cmd_tff(group=g)

def _i_scoos():
    obs = _prompt("Quarters", "8")
    cmd_scoos(obs=int(obs))

def _i_ficc():
    obs = _prompt("Months", "24")
    cmd_ficc(obs=int(obs))

def _i_fsi():
    cmd_fsi()

def _i_fsi_history():
    days = _prompt("Days", "365")
    cmd_fsi_history(days=int(days))

def _i_funding_snapshot():
    cmd_funding_snapshot()

def _i_stress_snapshot():
    cmd_stress_snapshot()

def _i_hf_snapshot():
    cmd_hf_snapshot()


COMMAND_MAP = {
    "1":  _i_datasets,    "2":  _i_mnemonics,    "3":  _i_search,
    "4":  _i_query,       "5":  _i_series,       "6":  _i_multi,
    "7":  _i_spread,      "8":  _i_dataset_pull, "9":  _i_fnyr,
    "10": _i_repo_rates,  "11": _i_repo_volumes, "12": _i_repo_history,
    "13": _i_mmf,         "14": _i_mmf_history,  "15": _i_yields,
    "16": _i_curve,       "17": _i_pd_financing, "18": _i_pd_fails,
    "19": _i_form_pf,     "20": _i_form_pf_strategy, "21": _i_form_pf_stress,
    "22": _i_tff,         "23": _i_scoos,        "24": _i_ficc,
    "25": _i_fsi,         "26": _i_fsi_history,
    "27": _i_funding_snapshot, "28": _i_stress_snapshot, "29": _i_hf_snapshot,
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
        elif choice in ("h", "help", "?", "menu"):
            print(MENU)
        else:
            print(f"  Unknown command: {choice}")
            print(f"  Enter 1-{len(COMMAND_MAP)}, h for menu, q to quit.")


# =============================================================================
# ARGPARSE
# =============================================================================

def build_argparse():
    p = argparse.ArgumentParser(
        prog="ofr.py",
        description="OFR -- Office of Financial Research API Client (STFM + HFM + FSI)",
    )
    sub = p.add_subparsers(dest="command")

    # Generic
    s = sub.add_parser("datasets", help="List all OFR datasets")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("mnemonics", help="List mnemonics for a dataset")
    s.add_argument("--dataset", choices=list(ALL_DATASETS.keys()))
    s.add_argument("--query", help="Filter substring")
    s.add_argument("--limit", type=int, default=80)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("search", help="Search mnemonics across all OFR APIs")
    s.add_argument("query", help="Search string (supports * and ?)")
    s.add_argument("--limit", type=int, default=80)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("query", help="Get metadata for a mnemonic")
    s.add_argument("mnemonic")
    s.add_argument("--fields")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("series", help="Fetch a single timeseries")
    s.add_argument("mnemonic")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--periodicity", choices=["A", "Q", "M", "W", "D", "B"])
    s.add_argument("--how", choices=["first", "last", "mean", "median", "sum"])
    s.add_argument("--obs", type=int)
    s.add_argument("--label", default="aggregation")
    s.add_argument("--remove-nulls", action="store_true")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("multi", help="Fetch multiple timeseries")
    s.add_argument("mnemonics", nargs="+", help="Mnemonics (space or comma separated)")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--periodicity", choices=["A", "Q", "M", "W", "D", "B"])
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("spread", help="Compute spread = X - Y between two series")
    s.add_argument("x")
    s.add_argument("y")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--obs", type=int, default=60)
    s.add_argument("--periodicity", choices=["A", "Q", "M", "W", "D", "B"])
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("dataset-pull", help="Pull full dataset")
    s.add_argument("dataset", choices=list(ALL_DATASETS.keys()))
    s.add_argument("--vintage", choices=["p", "f", "a"], help="Preliminary/Final/As-of")
    s.add_argument("--start", help="Start date YYYY-MM-DD")
    s.add_argument("--end", help="End date YYYY-MM-DD")
    s.add_argument("--periodicity", choices=["A", "Q", "M", "W", "D", "B"])
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Curated -- short-term funding
    s = sub.add_parser("fnyr", help="NY Fed reference rates with percentiles")
    s.add_argument("--obs", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("repo-rates", help="Tri-Party + GCF + DVP overnight rates")
    s.add_argument("--obs", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("repo-volumes", help="Repo outstanding volumes")
    s.add_argument("--obs", type=int, default=30)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("repo-history", help="History of a specific repo series")
    s.add_argument("--segment", choices=REPO_SEGMENTS, default="GCF")
    s.add_argument("--term", choices=REPO_TERMS, default="OO")
    s.add_argument("--metric", choices=REPO_METRICS, default="AR")
    s.add_argument("--vintage", choices=["P", "F"], default="P")
    s.add_argument("--obs", type=int, default=60)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("mmf", help="MMF holdings composition")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("mmf-history", help="MMF investment time series")
    s.add_argument("--obs", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Curated -- treasury
    s = sub.add_parser("yields", help="Treasury constant maturity curve")
    s.add_argument("--obs", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("curve", help="Treasury curve with deltas")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Curated -- dealers
    s = sub.add_parser("pd-financing", help="Primary dealer repo / RRP / sec lending")
    s.add_argument("--obs", type=int, default=12)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("pd-fails", help="Primary dealer fails to deliver/receive")
    s.add_argument("--obs", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Curated -- hedge funds
    s = sub.add_parser("form-pf", help="SEC Form PF aggregates")
    s.add_argument("--obs", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("form-pf-strategy", help="Form PF by strategy")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("form-pf-stress", help="Form PF stress test results")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("tff", help="CFTC TFF positioning")
    s.add_argument("--group", choices=list(TFF_GROUPS.keys()), default="LF")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("scoos", help="SCOOS dealer survey")
    s.add_argument("--obs", type=int, default=8)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("ficc", help="FICC sponsored repo")
    s.add_argument("--obs", type=int, default=24)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Curated -- stress
    s = sub.add_parser("fsi", help="OFR Financial Stress Index")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("fsi-history", help="FSI time series")
    s.add_argument("--days", type=int, default=365)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # Dashboards
    s = sub.add_parser("funding-snapshot", help="Rates + repo + MMF dashboard")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("stress-snapshot", help="FSI + curve + funding")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("hf-snapshot", help="Hedge fund cross-source")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    cmd = args.command

    if cmd == "datasets":
        cmd_datasets(as_json=j, export_fmt=exp)
    elif cmd == "mnemonics":
        cmd_mnemonics(dataset=args.dataset, query=args.query, limit=args.limit,
                      as_json=j, export_fmt=exp)
    elif cmd == "search":
        cmd_search(args.query, as_json=j, export_fmt=exp, limit=args.limit)
    elif cmd == "query":
        cmd_query(args.mnemonic, fields=args.fields, as_json=j, export_fmt=exp)
    elif cmd == "series":
        cmd_series(args.mnemonic, start_date=args.start, end_date=args.end,
                   periodicity=args.periodicity, how=args.how, obs=args.obs,
                   label=args.label, remove_nulls=args.remove_nulls,
                   as_json=j, export_fmt=exp)
    elif cmd == "multi":
        # Allow mixing comma and space separation
        flat = []
        for m in args.mnemonics:
            flat.extend(x.strip() for x in m.split(",") if x.strip())
        cmd_multi(flat, start_date=args.start, end_date=args.end,
                  periodicity=args.periodicity, as_json=j, export_fmt=exp)
    elif cmd == "spread":
        cmd_spread(args.x, args.y, start_date=args.start, end_date=args.end,
                   obs=args.obs, periodicity=args.periodicity,
                   as_json=j, export_fmt=exp)
    elif cmd == "dataset-pull":
        cmd_dataset_pull(args.dataset, vintage=args.vintage, start_date=args.start,
                         end_date=args.end, periodicity=args.periodicity,
                         as_json=j, export_fmt=exp)
    elif cmd == "fnyr":
        cmd_fnyr(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "repo-rates":
        cmd_repo_rates(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "repo-volumes":
        cmd_repo_volumes(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "repo-history":
        cmd_repo_history(segment=args.segment, term=args.term, metric=args.metric,
                         vintage=args.vintage, obs=args.obs,
                         as_json=j, export_fmt=exp)
    elif cmd == "mmf":
        cmd_mmf(as_json=j, export_fmt=exp)
    elif cmd == "mmf-history":
        cmd_mmf_history(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "yields":
        cmd_yields(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "curve":
        cmd_curve(as_json=j, export_fmt=exp)
    elif cmd == "pd-financing":
        cmd_pd_financing(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "pd-fails":
        cmd_pd_fails(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "form-pf":
        cmd_form_pf(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "form-pf-strategy":
        cmd_form_pf_strategy(as_json=j, export_fmt=exp)
    elif cmd == "form-pf-stress":
        cmd_form_pf_stress(as_json=j, export_fmt=exp)
    elif cmd == "tff":
        cmd_tff(group=args.group, as_json=j, export_fmt=exp)
    elif cmd == "scoos":
        cmd_scoos(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "ficc":
        cmd_ficc(obs=args.obs, as_json=j, export_fmt=exp)
    elif cmd == "fsi":
        cmd_fsi(as_json=j, export_fmt=exp)
    elif cmd == "fsi-history":
        cmd_fsi_history(days=args.days, as_json=j, export_fmt=exp)
    elif cmd == "funding-snapshot":
        cmd_funding_snapshot(as_json=j, export_fmt=exp)
    elif cmd == "stress-snapshot":
        cmd_stress_snapshot(as_json=j, export_fmt=exp)
    elif cmd == "hf-snapshot":
        cmd_hf_snapshot(as_json=j, export_fmt=exp)


def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        interactive_loop()


if __name__ == "__main__":
    main()
