#!/usr/bin/env python3
"""
Federal Register -- Regulatory & Policy Document Client

Single-script client for the Federal Register API (federalregister.gov/api/v1).
Tracks executive orders, final/proposed rules, and regulatory actions from
macro-relevant agencies. No auth required.

Usage:
    python federal_register.py                          # interactive CLI
    python federal_register.py latest                   # latest documents
    python federal_register.py executive-orders         # recent executive orders
    python federal_register.py rules --agency treasury  # final rules from Treasury
    python federal_register.py proposed --agency fed    # proposed rules from the Fed
    python federal_register.py significant              # economically significant rules
    python federal_register.py search "tariff"          # full-text search
    python federal_register.py document 2026-07143      # single document details
    python federal_register.py public-inspection        # upcoming filings
    python federal_register.py tracker                  # curated agency tracker
    python federal_register.py pipeline                 # regulatory pipeline snapshot
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

BASE_URL = "https://www.federalregister.gov/api/v1"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

DOC_TYPES = {
    "rule":     "RULE",
    "proposed": "PRORULE",
    "notice":   "NOTICE",
    "presidential": "PRESDOCU",
}

PRESIDENTIAL_SUBTYPES = {
    "executive_order": "Executive Order",
    "memorandum":      "Presidential Memorandum",
    "proclamation":    "Proclamation",
    "determination":   "Determination",
    "notice":          "Presidential Notice",
    "other":           "Other Presidential Document",
}

# Macro-relevant agencies. IDs verified against live /agencies.json April 2026.
AGENCY_REGISTRY = {
    # Financial / banking
    "treasury":   {"id": 497, "name": "Treasury Department", "slug": "treasury-department"},
    "fed":        {"id": 188, "name": "Federal Reserve System", "slug": "federal-reserve-system"},
    "sec":        {"id": 466, "name": "Securities and Exchange Commission", "slug": "securities-and-exchange-commission"},
    "cftc":       {"id": 77,  "name": "Commodity Futures Trading Commission", "slug": "commodity-futures-trading-commission"},
    "fdic":       {"id": 164, "name": "Federal Deposit Insurance Corporation", "slug": "federal-deposit-insurance-corporation"},
    "occ":        {"id": 80,  "name": "Comptroller of the Currency", "slug": "comptroller-of-the-currency"},
    "fhfa":       {"id": 174, "name": "Federal Housing Finance Agency", "slug": "federal-housing-finance-agency"},
    "ncua":       {"id": 335, "name": "National Credit Union Administration", "slug": "national-credit-union-administration"},
    "fincen":     {"id": 194, "name": "Financial Crimes Enforcement Network", "slug": "financial-crimes-enforcement-network"},

    # Trade / customs / sanctions
    "ustr":       {"id": 491, "name": "Trade Representative, Office of United States", "slug": "trade-representative-office-of-united-states"},
    "commerce":   {"id": 54,  "name": "Commerce Department", "slug": "commerce-department"},
    "cbp":        {"id": 501, "name": "U.S. Customs and Border Protection", "slug": "u-s-customs-and-border-protection"},
    "ofac":       {"id": 203, "name": "Foreign Assets Control Office", "slug": "foreign-assets-control-office"},
    "ita":        {"id": 261, "name": "International Trade Administration", "slug": "international-trade-administration"},
    "bis":        {"id": 241, "name": "Industry and Security Bureau", "slug": "industry-and-security-bureau"},
    "usitc":      {"id": 262, "name": "International Trade Commission", "slug": "international-trade-commission"},

    # Economic / statistical
    "bea":        {"id": 118, "name": "Economic Analysis Bureau", "slug": "economic-analysis-bureau"},
    "bls":        {"id": 272, "name": "Labor Statistics Bureau", "slug": "labor-statistics-bureau"},
    "census":     {"id": 42,  "name": "Census Bureau", "slug": "census-bureau"},

    # Fiscal
    "irs":        {"id": 254, "name": "Internal Revenue Service", "slug": "internal-revenue-service"},
    "omb":        {"id": 280, "name": "Management and Budget Office", "slug": "management-and-budget-office"},
    "bfs":        {"id": 196, "name": "Bureau of the Fiscal Service", "slug": "bureau-of-the-fiscal-service"},

    # Energy / climate
    "energy":     {"id": 136, "name": "Energy Department", "slug": "energy-department"},
    "ferc":       {"id": 167, "name": "Federal Energy Regulatory Commission", "slug": "federal-energy-regulatory-commission"},
    "eia":        {"id": 138, "name": "Energy Information Administration", "slug": "energy-information-administration"},
    "epa":        {"id": 145, "name": "Environmental Protection Agency", "slug": "environmental-protection-agency"},
    "nrc":        {"id": 383, "name": "Nuclear Regulatory Commission", "slug": "nuclear-regulatory-commission"},

    # Executive / labor
    "president":  {"id": 538, "name": "Executive Office of the President", "slug": "executive-office-of-the-president"},
    "labor":      {"id": 271, "name": "Labor Department", "slug": "labor-department"},

    # Foreign / security
    "state":      {"id": 476, "name": "State Department", "slug": "state-department"},
    "defense":    {"id": 103, "name": "Defense Department", "slug": "defense-department"},
    "dhs":        {"id": 227, "name": "Homeland Security Department", "slug": "homeland-security-department"},

    # Competition / tech / antitrust
    "ftc":        {"id": 192, "name": "Federal Trade Commission", "slug": "federal-trade-commission"},
    "doj":        {"id": 268, "name": "Justice Department", "slug": "justice-department"},
    "fcc":        {"id": 161, "name": "Federal Communications Commission", "slug": "federal-communications-commission"},
    "nist":       {"id": 352, "name": "National Institute of Standards and Technology", "slug": "national-institute-of-standards-and-technology"},

    # Housing
    "hud":        {"id": 228, "name": "Housing and Urban Development Department", "slug": "housing-and-urban-development-department"},

    # Transportation
    "transport":  {"id": 492, "name": "Transportation Department", "slug": "transportation-department"},
    "faa":        {"id": 159, "name": "Federal Aviation Administration", "slug": "federal-aviation-administration"},

    # Enforcement
    "cfpb":       {"id": 573, "name": "Consumer Financial Protection Bureau", "slug": "consumer-financial-protection-bureau"},
}

# Grouped by analytical relevance. A single agency can appear in multiple groups.
AGENCY_GROUPS = {
    "financial":   ["treasury", "fed", "sec", "cftc", "fdic", "occ", "fhfa", "ncua", "cfpb"],
    "trade":       ["ustr", "commerce", "cbp", "ofac", "ita", "bis", "usitc"],
    "fiscal":      ["treasury", "irs", "omb", "bfs"],
    "energy":      ["energy", "ferc", "eia", "epa", "nrc"],
    "executive":   ["president", "omb"],
    "labor":       ["labor", "bls"],
    "statistical": ["bea", "bls", "census"],
    "sanctions":   ["ofac", "bis", "state", "commerce"],
    "antitrust":   ["ftc", "doj", "fcc"],
    "housing":     ["fhfa", "hud"],
    "tech":        ["ftc", "fcc", "nist", "sec"],
    "foreign":     ["state", "defense", "dhs", "ustr"],
    "financial_crime": ["fincen", "ofac", "irs", "doj"],
}

STANDARD_FIELDS = [
    "title", "type", "subtype", "abstract", "document_number",
    "publication_date", "signing_date", "effective_on",
    "executive_order_number", "action", "agencies",
    "html_url", "pdf_url", "significant",
    "regulation_id_numbers", "cfr_references", "topics",
    "comments_close_on", "dates", "page_views",
]


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


def _build_params(doc_type=None, agency_alias=None, agency_id=None,
                  presidential_type=None, term=None, significant_only=False,
                  date_gte=None, date_lte=None, per_page=20, page=1,
                  order="newest", fields=None):
    params = {"per_page": per_page, "page": page, "order": order}

    if fields is None:
        fields = STANDARD_FIELDS
    for f in fields:
        params[f"fields[]"] = fields  # will be handled below

    if doc_type:
        dtype = DOC_TYPES.get(doc_type, doc_type)
        params["conditions[type][]"] = dtype

    if presidential_type:
        params["conditions[presidential_document_type][]"] = presidential_type

    aid = agency_id
    if agency_alias and not aid:
        entry = AGENCY_REGISTRY.get(agency_alias.lower())
        if entry:
            aid = entry["id"]
    if aid:
        params["conditions[agency_ids][]"] = aid

    if term:
        params["conditions[term]"] = term

    if significant_only:
        params["conditions[significant]"] = 1

    if date_gte:
        params["conditions[publication_date][gte]"] = date_gte
    if date_lte:
        params["conditions[publication_date][lte]"] = date_lte

    # fields[] needs special handling for requests library
    field_list = fields or STANDARD_FIELDS
    for f in field_list:
        pass  # handled via raw URL building below

    return params


def _fetch_documents(doc_type=None, agency_alias=None, agency_id=None,
                     presidential_type=None, term=None, significant_only=False,
                     date_gte=None, date_lte=None, per_page=20, page=1,
                     order="newest"):
    """Core fetcher. Returns (results_list, total_count, description)."""
    # Build URL manually because requests doesn't handle repeated params well
    parts = [f"per_page={per_page}", f"page={page}", f"order={order}"]

    for f in STANDARD_FIELDS:
        parts.append(f"fields[]={f}")

    if doc_type:
        dtype = DOC_TYPES.get(doc_type, doc_type)
        parts.append(f"conditions[type][]={dtype}")

    if presidential_type:
        parts.append(f"conditions[presidential_document_type][]={presidential_type}")

    aid = agency_id
    if agency_alias and not aid:
        entry = AGENCY_REGISTRY.get(agency_alias.lower())
        if entry:
            aid = entry["id"]
    if aid:
        parts.append(f"conditions[agency_ids][]={aid}")

    if term:
        parts.append(f"conditions[term]={requests.utils.quote(str(term))}")

    if significant_only:
        parts.append("conditions[significant]=1")

    if date_gte:
        parts.append(f"conditions[publication_date][gte]={date_gte}")
    if date_lte:
        parts.append(f"conditions[publication_date][lte]={date_lte}")

    url = f"{BASE_URL}/documents.json?{'&'.join(parts)}"
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                print(f"  [API error {r.status_code}: {r.text[:200]}]")
                return [], 0, ""
            data = r.json()
            return (
                data.get("results", []),
                data.get("count", 0),
                data.get("description", ""),
            )
        except Exception as e:
            print(f"  [error: {e}]")
            if attempt < 2:
                time.sleep(2)
    return [], 0, ""


def _fetch_public_inspection(per_page=20):
    data = _request(f"public-inspection-documents.json?per_page={per_page}")
    if not data:
        return [], 0
    return data.get("results", []), data.get("count", 0)


def _fetch_public_inspection_current():
    """PI documents currently on the inspection desk (subset of upcoming)."""
    data = _request("public-inspection-documents/current.json")
    if not data:
        return [], 0
    return data.get("results", []), data.get("count", 0)


def _fetch_public_inspection_by_date(date_str):
    """PI documents filed on a specific date (YYYY-MM-DD)."""
    data = _request(f"public-inspection-documents/{date_str}.json")
    if not data:
        return [], 0
    results = data.get("results", [])
    return results, data.get("count", len(results))


def _fetch_document(doc_number):
    fields = "&".join(f"fields[]={f}" for f in STANDARD_FIELDS + [
        "body_html_url", "full_text_xml_url", "raw_text_url",
        "docket_ids", "regulation_id_number_info",
    ])
    data = _request(f"documents/{doc_number}.json?{fields}")
    return data


def _fetch_agencies():
    return _request("agencies.json")


# --- Facets ------------------------------------------------------------------
# Aggregation endpoints that return counts without fetching individual docs.

FACET_KEYS = ["daily", "weekly", "monthly", "quarterly", "yearly",
              "agency", "topic", "type", "subtype", "section"]


def _fetch_facet(facet_key, doc_type=None, agency_alias=None, agency_id=None,
                 presidential_type=None, term=None, significant_only=False,
                 date_gte=None, date_lte=None):
    """Fetch /documents/facets/{facet_key}.json with optional filters.
    Returns dict keyed by facet value -> {count, name}."""
    parts = []
    if doc_type:
        dtype = DOC_TYPES.get(doc_type, doc_type)
        parts.append(f"conditions[type][]={dtype}")
    if presidential_type:
        parts.append(f"conditions[presidential_document_type][]={presidential_type}")
    aid = agency_id
    if agency_alias and not aid:
        entry = AGENCY_REGISTRY.get(agency_alias.lower())
        if entry:
            aid = entry["id"]
    if aid:
        parts.append(f"conditions[agency_ids][]={aid}")
    if term:
        parts.append(f"conditions[term]={requests.utils.quote(str(term))}")
    if significant_only:
        parts.append("conditions[significant]=1")
    if date_gte:
        parts.append(f"conditions[publication_date][gte]={date_gte}")
    if date_lte:
        parts.append(f"conditions[publication_date][lte]={date_lte}")

    qs = "&".join(parts)
    url = f"{BASE_URL}/documents/facets/{facet_key}.json"
    if qs:
        url = f"{url}?{qs}"
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=30)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            if r.status_code >= 400:
                print(f"  [API error {r.status_code}: {r.text[:200]}]")
                return {}
            return r.json() or {}
        except Exception as e:
            print(f"  [error: {e}]")
            if attempt < 2:
                time.sleep(2)
    return {}


# --- Suggested Searches ------------------------------------------------------

def _fetch_suggested_searches(section=None):
    """Curated topic packs. Without section: returns {section: [pack...]}.
    With section: returns list of packs for that section."""
    endpoint = "suggested_searches.json"
    if section:
        endpoint = f"suggested_searches.json?conditions[sections][]={section}"
    return _request(endpoint) or {}


# --- Parsing Helpers ----------------------------------------------------------

def _agency_names(doc):
    agencies = doc.get("agencies", [])
    if not agencies:
        return "Unknown"
    return ", ".join(a.get("name", a.get("raw_name", "?")) for a in agencies[:3])


def _short_type(doc):
    dtype = doc.get("type", "")
    subtype = doc.get("subtype", "")
    if subtype:
        return subtype
    type_map = {
        "Rule": "RULE",
        "Proposed Rule": "PROPOSED",
        "Notice": "NOTICE",
        "Presidential Document": "PRES DOC",
    }
    return type_map.get(dtype, dtype[:12])


def _truncate(text, length=80):
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def _days_ago(date_str):
    if not date_str:
        return ""
    try:
        pub = datetime.strptime(date_str[:10], "%Y-%m-%d")
        delta = (datetime.now() - pub).days
        if delta == 0:
            return "today"
        if delta == 1:
            return "1d ago"
        return f"{delta}d ago"
    except (ValueError, TypeError):
        return ""


def _parse_date(val):
    if not val:
        return ""
    return str(val)[:10]


# --- Display ------------------------------------------------------------------

def _fmt_num(n, sign=True):
    if sign:
        return f"{n:+,}"
    return f"{n:,}"


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


# --- Display Functions --------------------------------------------------------

def _display_doc_table(docs, title="Federal Register Documents", show_abstract=False):
    if not docs:
        print("  No documents found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)
    print(f"  {'Date':<12} {'Type':<12} {'Doc #':<16} {'Agency':<25} {'Title'}")
    print(f"  {'-'*12} {'-'*12} {'-'*16} {'-'*25} {'-'*40}")

    for doc in docs:
        date = _parse_date(doc.get("publication_date", ""))
        dtype = _short_type(doc)
        doc_num = doc.get("document_number", "")[:16]
        agency = _truncate(_agency_names(doc), 25)
        title_text = _truncate(doc.get("title", ""), 55)

        print(f"  {date:<12} {dtype:<12} {doc_num:<16} {agency:<25} {title_text}")

        if show_abstract:
            abstract = doc.get("abstract", "")
            if abstract:
                print(f"  {'':12} {_truncate(abstract, 90)}")

    print()


def _display_eo_table(docs, title="Executive Orders"):
    if not docs:
        print("  No executive orders found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)
    print(f"  {'EO #':<8} {'Signed':<12} {'Published':<12} {'Title'}")
    print(f"  {'-'*8} {'-'*12} {'-'*12} {'-'*60}")

    for doc in docs:
        eo_num = doc.get("executive_order_number", "")
        if eo_num:
            eo_num = f"EO {eo_num}"
        signed = _parse_date(doc.get("signing_date", ""))
        pub = _parse_date(doc.get("publication_date", ""))
        title_text = _truncate(doc.get("title", ""), 60)
        print(f"  {eo_num:<8} {signed:<12} {pub:<12} {title_text}")

    print()


def _display_document_detail(doc):
    if not doc:
        print("  Document not found.")
        return

    print(f"\n  {'=' * 80}")
    print(f"  DOCUMENT: {doc.get('document_number', 'N/A')}")
    print(f"  {'=' * 80}")
    print(f"  Title:       {doc.get('title', 'N/A')}")
    print(f"  Type:        {doc.get('type', 'N/A')}", end="")
    if doc.get("subtype"):
        print(f" ({doc['subtype']})")
    else:
        print()
    print(f"  Published:   {_parse_date(doc.get('publication_date', ''))}")
    if doc.get("signing_date"):
        print(f"  Signed:      {_parse_date(doc['signing_date'])}")
    if doc.get("effective_on"):
        print(f"  Effective:   {_parse_date(doc['effective_on'])}")
    if doc.get("executive_order_number"):
        print(f"  EO Number:   {doc['executive_order_number']}")
    if doc.get("action"):
        print(f"  Action:      {doc['action']}")

    print(f"  Agency:      {_agency_names(doc)}")

    if doc.get("abstract"):
        print(f"\n  Abstract:")
        abstract = doc["abstract"]
        for i in range(0, len(abstract), 90):
            print(f"    {abstract[i:i+90]}")

    if doc.get("significant"):
        print(f"\n  ** SIGNIFICANT REGULATORY ACTION **")

    if doc.get("regulation_id_numbers"):
        rins = doc["regulation_id_numbers"]
        if isinstance(rins, list):
            print(f"  RIN(s):      {', '.join(str(r) for r in rins)}")

    if doc.get("cfr_references"):
        refs = doc["cfr_references"]
        if isinstance(refs, list):
            cfr_strs = [f"{r.get('title', '?')} CFR {r.get('part', '?')}" for r in refs]
            print(f"  CFR:         {', '.join(cfr_strs)}")

    if doc.get("topics"):
        topics = doc["topics"]
        if isinstance(topics, list):
            print(f"  Topics:      {', '.join(topics[:5])}")

    if doc.get("comments_close_on"):
        print(f"  Comments close: {_parse_date(doc['comments_close_on'])}")

    if doc.get("dates"):
        print(f"  Dates:       {doc['dates'][:100]}")

    print(f"\n  URL:         {doc.get('html_url', 'N/A')}")
    if doc.get("pdf_url"):
        print(f"  PDF:         {doc['pdf_url']}")
    print(f"  {'=' * 80}\n")


def _display_pi_table(docs, title="Public Inspection -- Upcoming Filings"):
    if not docs:
        print("  No public inspection documents found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)
    print(f"  {'Filed':<12} {'Pub Date':<12} {'Type':<12} {'Pages':>6} {'Agency':<25} {'Title'}")
    print(f"  {'-'*12} {'-'*12} {'-'*12} {'-'*6} {'-'*25} {'-'*30}")

    for doc in docs:
        filed = _parse_date(doc.get("filed_at", ""))
        pub = _parse_date(doc.get("publication_date", ""))
        dtype = doc.get("type", "")[:12]
        pages = doc.get("num_pages", "")
        agency = _truncate(_agency_names(doc), 25)
        title_text = _truncate(doc.get("title", ""), 40)

        print(f"  {filed:<12} {pub:<12} {dtype:<12} {pages:>6} {agency:<25} {title_text}")

    print()


def _display_tracker(results_by_agency, title="Macro Agency Tracker"):
    if not results_by_agency:
        print("  No results.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)

    for alias, data in results_by_agency.items():
        info = AGENCY_REGISTRY.get(alias, {})
        name = info.get("name", alias)
        docs = data.get("docs", [])
        count = data.get("count", 0)

        print(f"\n  {name.upper()} ({count} documents in period)")
        if not docs:
            print("    (none)")
            continue

        print(f"  {'Date':<12} {'Type':<12} {'Title'}")
        print(f"  {'-'*12} {'-'*12} {'-'*65}")

        for doc in docs[:8]:
            date = _parse_date(doc.get("publication_date", ""))
            dtype = _short_type(doc)
            title_text = _truncate(doc.get("title", ""), 65)
            print(f"  {date:<12} {dtype:<12} {title_text}")

        if len(docs) > 8:
            print(f"    ... and {len(docs) - 8} more")

    print()


# --- Command Functions --------------------------------------------------------

def cmd_latest(per_page=20, as_json=False, export_fmt=None):
    print("\n  Fetching latest Federal Register documents...")
    docs, count, desc = _fetch_documents(per_page=per_page)

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_doc_table(docs, f"Latest Federal Register Documents ({count:,} total)")

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_latest", export_fmt)
    return docs


def cmd_executive_orders(per_page=20, days=90, as_json=False, export_fmt=None):
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n  Fetching executive orders (last {days} days)...")
    docs, count, desc = _fetch_documents(
        doc_type="presidential",
        presidential_type="executive_order",
        date_gte=date_gte,
        per_page=per_page,
    )

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_eo_table(docs, f"Executive Orders (last {days}d, {count} total)")

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_eo", export_fmt)
    return docs


def cmd_rules(agency_alias=None, per_page=20, days=90, as_json=False, export_fmt=None):
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    label = AGENCY_REGISTRY.get(agency_alias, {}).get("name", "All Agencies") if agency_alias else "All Agencies"
    print(f"\n  Fetching final rules from {label} (last {days} days)...")

    docs, count, desc = _fetch_documents(
        doc_type="rule",
        agency_alias=agency_alias,
        date_gte=date_gte,
        per_page=per_page,
    )

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_doc_table(docs, f"Final Rules -- {label} ({count} in period)", show_abstract=True)

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_rules", export_fmt)
    return docs


def cmd_proposed(agency_alias=None, per_page=20, days=90, as_json=False, export_fmt=None):
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    label = AGENCY_REGISTRY.get(agency_alias, {}).get("name", "All Agencies") if agency_alias else "All Agencies"
    print(f"\n  Fetching proposed rules from {label} (last {days} days)...")

    docs, count, desc = _fetch_documents(
        doc_type="proposed",
        agency_alias=agency_alias,
        date_gte=date_gte,
        per_page=per_page,
    )

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_doc_table(docs, f"Proposed Rules -- {label} ({count} in period)", show_abstract=True)

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_proposed", export_fmt)
    return docs


def cmd_significant(per_page=20, days=180, as_json=False, export_fmt=None):
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n  Fetching significant regulatory actions (last {days} days)...")

    docs, count, desc = _fetch_documents(
        significant_only=True,
        date_gte=date_gte,
        per_page=per_page,
    )

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_doc_table(docs, f"Significant Regulatory Actions ({count} in last {days}d)", show_abstract=True)

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_significant", export_fmt)
    return docs


def cmd_search(term=None, doc_type=None, agency_alias=None, per_page=20,
               as_json=False, export_fmt=None):
    if not term:
        term = _prompt("Search term")
    if not term:
        return

    print(f"\n  Searching Federal Register for '{term}'...")
    docs, count, desc = _fetch_documents(
        term=term,
        doc_type=doc_type,
        agency_alias=agency_alias,
        per_page=per_page,
    )

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_doc_table(docs, f"Search: '{term}' ({count:,} results)", show_abstract=True)

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, f"fedreg_search_{term[:20]}", export_fmt)
    return docs


def cmd_document(doc_number=None, as_json=False):
    if not doc_number:
        doc_number = _prompt("Document number")
    if not doc_number:
        return

    print(f"\n  Fetching document {doc_number}...")
    doc = _fetch_document(doc_number)

    if not doc:
        print("  Document not found.")
        return

    if as_json:
        print(json.dumps(doc, indent=2, default=str))
        return doc

    _display_document_detail(doc)
    return doc


def cmd_public_inspection(per_page=20, as_json=False, export_fmt=None):
    print("\n  Fetching public inspection documents (upcoming filings)...")
    docs, count = _fetch_public_inspection(per_page=per_page)

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_pi_table(docs, f"Public Inspection -- Upcoming ({count} filings)")

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_pi", export_fmt)
    return docs


def cmd_tracker(groups=None, days=30, per_page=10, as_json=False, export_fmt=None):
    if not groups:
        groups = ["financial", "trade", "executive"]

    aliases = []
    for g in groups:
        aliases.extend(AGENCY_GROUPS.get(g, []))
    aliases = list(dict.fromkeys(aliases))  # dedup preserving order

    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    total_agencies = len(aliases)
    results = {}

    print(f"\n  Tracking {total_agencies} agencies (last {days} days)...")

    for idx, alias in enumerate(aliases):
        info = AGENCY_REGISTRY[alias]
        print(f"  [{idx + 1}/{total_agencies}] {info['name']}...")

        docs, count, _ = _fetch_documents(
            agency_alias=alias,
            date_gte=date_gte,
            per_page=per_page,
        )
        results[alias] = {"docs": docs, "count": count}

        if idx < total_agencies - 1:
            time.sleep(0.3)

    if as_json:
        out = {}
        for alias, data in results.items():
            out[alias] = {
                "agency": AGENCY_REGISTRY[alias]["name"],
                "count": data["count"],
                "documents": data["docs"],
            }
        print(json.dumps(out, indent=2, default=str))
        return out

    label = " + ".join(g.upper() for g in groups)
    _display_tracker(results, f"Agency Tracker: {label} (last {days}d)")

    if export_fmt:
        flat = []
        for alias, data in results.items():
            for doc in data["docs"]:
                row = _flatten_single_doc(doc)
                row["_tracker_agency"] = alias
                flat.append(row)
        _do_export(flat, "fedreg_tracker", export_fmt)
    return results


def cmd_pipeline(days=180, as_json=False, export_fmt=None):
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n  Building regulatory pipeline (proposed + final rules, last {days}d)...")

    print("  Fetching proposed rules...")
    proposed, p_count, _ = _fetch_documents(
        doc_type="proposed", date_gte=date_gte, per_page=50
    )
    time.sleep(0.3)

    print("  Fetching final rules...")
    final, f_count, _ = _fetch_documents(
        doc_type="rule", date_gte=date_gte, per_page=50
    )

    if as_json:
        out = {"proposed": proposed, "final": final,
               "proposed_count": p_count, "final_count": f_count}
        print(json.dumps(out, indent=2, default=str))
        return out

    print(f"\n  REGULATORY PIPELINE (last {days} days)")
    print("  " + "=" * 95)
    print(f"  Proposed rules in pipeline: {p_count}")
    print(f"  Final rules published:      {f_count}")

    # Check for proposed rules that have comment deadlines coming up
    upcoming_comments = []
    today = datetime.now().date()
    for doc in proposed:
        close = doc.get("comments_close_on")
        if close:
            try:
                close_date = datetime.strptime(close[:10], "%Y-%m-%d").date()
                if close_date >= today:
                    days_left = (close_date - today).days
                    upcoming_comments.append((doc, days_left))
            except (ValueError, TypeError):
                pass

    if upcoming_comments:
        upcoming_comments.sort(key=lambda x: x[1])
        print(f"\n  OPEN COMMENT PERIODS ({len(upcoming_comments)} rules)")
        print(f"  {'Closes':<12} {'Days':>5} {'Agency':<25} {'Title'}")
        print(f"  {'-'*12} {'-'*5} {'-'*25} {'-'*45}")
        for doc, dl in upcoming_comments[:15]:
            close = _parse_date(doc.get("comments_close_on", ""))
            agency = _truncate(_agency_names(doc), 25)
            title_text = _truncate(doc.get("title", ""), 45)
            print(f"  {close:<12} {dl:>5} {agency:<25} {title_text}")

    # Show financial agency activity
    fin_agencies = set(AGENCY_REGISTRY[a]["id"] for a in AGENCY_GROUPS["financial"])
    fin_proposed = [d for d in proposed if any(
        a.get("id") in fin_agencies for a in d.get("agencies", [])
    )]
    fin_final = [d for d in final if any(
        a.get("id") in fin_agencies for a in d.get("agencies", [])
    )]

    if fin_proposed or fin_final:
        print(f"\n  FINANCIAL REGULATORS ({len(fin_proposed)} proposed, {len(fin_final)} final)")
        all_fin = sorted(fin_proposed + fin_final,
                         key=lambda d: d.get("publication_date", ""), reverse=True)
        print(f"  {'Date':<12} {'Type':<12} {'Agency':<25} {'Title'}")
        print(f"  {'-'*12} {'-'*12} {'-'*25} {'-'*40}")
        for doc in all_fin[:15]:
            date = _parse_date(doc.get("publication_date", ""))
            dtype = _short_type(doc)
            agency = _truncate(_agency_names(doc), 25)
            title_text = _truncate(doc.get("title", ""), 40)
            print(f"  {date:<12} {dtype:<12} {agency:<25} {title_text}")

    print()

    if export_fmt:
        flat = _flatten_docs(proposed + final)
        _do_export(flat, "fedreg_pipeline", export_fmt)
    return {"proposed": proposed, "final": final}


def cmd_agencies(as_json=False):
    if as_json:
        out = {}
        for g, aliases in AGENCY_GROUPS.items():
            out[g] = [{"alias": a, **AGENCY_REGISTRY[a]} for a in aliases
                      if a in AGENCY_REGISTRY]
        print(json.dumps(out, indent=2, default=str))
        return out

    print("\n  Curated Agency Registry (macro-relevant)")
    print("  " + "=" * 70)

    for group_name, aliases in AGENCY_GROUPS.items():
        print(f"\n  {group_name.upper()}")
        print(f"  {'Alias':<14} {'ID':>5}  {'Name'}")
        print(f"  {'-'*14} {'-'*5}  {'-'*45}")
        for alias in aliases:
            info = AGENCY_REGISTRY.get(alias)
            if info:
                print(f"  {alias:<14} {info['id']:>5}  {info['name']}")

    print(f"\n  Total: {len(AGENCY_REGISTRY)} agencies across {len(AGENCY_GROUPS)} groups")
    print(f"  Usage: python federal_register.py rules --agency treasury")
    print(f"  Usage: python federal_register.py tracker --groups financial,trade\n")


# --- Extended Commands: Facets ----------------------------------------------

def cmd_facets(facet_key=None, doc_type=None, agency_alias=None,
               presidential_type=None, term=None, significant_only=False,
               days=None, date_gte=None, date_lte=None, head=25,
               as_json=False, export_fmt=None):
    """Aggregation queries across publication_date/agency/topic/type/subtype/section.
    Returns counts WITHOUT fetching individual documents."""
    if not facet_key:
        facet_key = "monthly"
    if facet_key not in FACET_KEYS:
        print(f"  [unknown facet: {facet_key}]")
        print(f"  Available: {', '.join(FACET_KEYS)}")
        return None

    if days is not None and not date_gte:
        date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    print(f"\n  Fetching facet '{facet_key}' "
          f"(filters: type={doc_type}, agency={agency_alias}, term={term}, "
          f"significant={significant_only}, gte={date_gte}, lte={date_lte})...")

    data = _fetch_facet(
        facet_key,
        doc_type=doc_type,
        agency_alias=agency_alias,
        presidential_type=presidential_type,
        term=term,
        significant_only=significant_only,
        date_gte=date_gte,
        date_lte=date_lte,
    )

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    if not data:
        print("  No facet data returned.")
        return {}

    items = []
    for key, info in data.items():
        if isinstance(info, dict):
            items.append((key, info.get("count", 0), info.get("name", key)))
        else:
            items.append((key, info, key))

    is_time_facet = facet_key in ("daily", "weekly", "monthly",
                                  "quarterly", "yearly")
    if is_time_facet:
        items.sort(key=lambda x: x[0])
    else:
        items.sort(key=lambda x: -x[1])
        items = items[:head]

    label = facet_key.upper()
    total = sum(c for _, c, _ in items)
    print(f"\n  FACET: {label} (showing {len(items)} rows, {total:,} total docs)")
    print("  " + "=" * 80)
    print(f"  {'Key':<35} {'Name':<35} {'Count':>10}")
    print(f"  {'-'*35} {'-'*35} {'-'*10}")

    if is_time_facet:
        bars_total = max((c for _, c, _ in items), default=1)
        for key, cnt, name in items:
            bar_len = int(40 * cnt / bars_total) if bars_total else 0
            bar = "#" * bar_len
            print(f"  {key:<35} {_truncate(name,35):<35} {cnt:>10,}  {bar}")
    else:
        for key, cnt, name in items:
            print(f"  {_truncate(key,35):<35} {_truncate(name,35):<35} {cnt:>10,}")
    print()

    if export_fmt:
        rows = [{"key": k, "name": n, "count": c} for k, c, n in items]
        _do_export(rows, f"fedreg_facet_{facet_key}", export_fmt)
    return data


def cmd_eo_pace(days=365, as_json=False, export_fmt=None):
    """Composite: monthly EO + proclamation + memo counts over N days.
    Useful for visualizing presidential activity rate."""
    date_gte = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    print(f"\n  Building EO pace (last {days} days, monthly)...")

    results = {}
    for sub in ("executive_order", "proclamation", "memorandum"):
        print(f"  Fetching {sub}...")
        data = _fetch_facet(
            "monthly",
            doc_type="presidential",
            presidential_type=sub,
            date_gte=date_gte,
        )
        time.sleep(0.3)
        results[sub] = data or {}

    if as_json:
        print(json.dumps(results, indent=2, default=str))
        return results

    all_months = sorted(set().union(*(set(v.keys()) for v in results.values())))
    if not all_months:
        print("  No data.")
        return results

    print(f"\n  PRESIDENTIAL PACE (last {days}d by month)")
    print("  " + "=" * 90)
    print(f"  {'Month':<14} {'EOs':>6} {'Proclamations':>14} {'Memoranda':>10} "
          f"{'Total':>7}")
    print(f"  {'-'*14} {'-'*6} {'-'*14} {'-'*10} {'-'*7}")
    for m in all_months:
        eo = results["executive_order"].get(m, {}).get("count", 0)
        pr = results["proclamation"].get(m, {}).get("count", 0)
        me = results["memorandum"].get(m, {}).get("count", 0)
        total = eo + pr + me
        label = (results["executive_order"].get(m, {}).get("name")
                 or results["proclamation"].get(m, {}).get("name")
                 or results["memorandum"].get(m, {}).get("name")
                 or m)
        print(f"  {label:<14} {eo:>6} {pr:>14} {me:>10} {total:>7}")
    print()

    if export_fmt:
        rows = []
        for m in all_months:
            rows.append({
                "month": m,
                "name": (results["executive_order"].get(m, {}).get("name")
                         or results["proclamation"].get(m, {}).get("name")
                         or results["memorandum"].get(m, {}).get("name")
                         or m),
                "executive_orders": results["executive_order"].get(m, {}).get("count", 0),
                "proclamations": results["proclamation"].get(m, {}).get("count", 0),
                "memoranda": results["memorandum"].get(m, {}).get("count", 0),
            })
        _do_export(rows, "fedreg_eo_pace", export_fmt)
    return results


# --- Extended Commands: Suggested Searches -----------------------------------

SUGGEST_SECTIONS = ["money", "world", "environment", "science-and-technology",
                    "business-and-industry", "health-and-public-welfare"]


def cmd_suggested(section=None, as_json=False):
    """FR's curated topic packs by section. Each pack = pre-built search query."""
    data = _fetch_suggested_searches(section=section)
    if not data:
        print("  No suggested searches returned.")
        return {}

    if as_json:
        print(json.dumps(data, indent=2, default=str))
        return data

    if isinstance(data, dict) and section and section in data:
        items = data[section]
        if isinstance(items, list):
            _display_suggest_list(items, section)
            return {section: items}

    if isinstance(data, dict):
        for sec, items in data.items():
            if not isinstance(items, list):
                continue
            _display_suggest_list(items, sec)
    return data


def _display_suggest_list(items, section):
    print(f"\n  SUGGESTED SEARCHES -- {section.upper()} ({len(items)} packs)")
    print("  " + "=" * 95)
    for it in items:
        if not isinstance(it, dict):
            continue
        title = it.get("title", it.get("slug", "?"))
        slug = it.get("slug", "")
        print(f"\n  {title}")
        print(f"    slug: {slug}")
        desc = it.get("description", "")
        if desc:
            import re
            clean = re.sub(r"<[^>]+>", "", desc).strip()
            clean = clean.replace("&amp;", "&").replace("&#8217;", "'")
            for i in range(0, min(len(clean), 400), 85):
                print(f"    {clean[i:i+85]}")
        search_conditions = it.get("search_conditions", {})
        if search_conditions:
            print(f"    conditions: {json.dumps(search_conditions, default=str)[:150]}")
    print()


# --- Extended Commands: Public Inspection Current/By-Date --------------------

def cmd_pi_current(as_json=False, export_fmt=None):
    print("\n  Fetching documents CURRENTLY on public inspection desk...")
    docs, count = _fetch_public_inspection_current()

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_pi_table(docs, f"Public Inspection -- Currently On Desk ({count} filings)")

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, "fedreg_pi_current", export_fmt)
    return docs


def cmd_pi_by_date(date_str, as_json=False, export_fmt=None):
    print(f"\n  Fetching public inspection documents filed on {date_str}...")
    docs, count = _fetch_public_inspection_by_date(date_str)

    if as_json:
        print(json.dumps(docs, indent=2, default=str))
        return docs

    _display_pi_table(docs, f"Public Inspection -- {date_str} ({count} filings)")

    if export_fmt:
        flat = _flatten_docs(docs)
        _do_export(flat, f"fedreg_pi_{date_str}", export_fmt)
    return docs


# --- Flattening for Export ----------------------------------------------------

def _flatten_single_doc(doc):
    return {
        "document_number": doc.get("document_number", ""),
        "title": doc.get("title", ""),
        "type": doc.get("type", ""),
        "subtype": doc.get("subtype", ""),
        "publication_date": _parse_date(doc.get("publication_date", "")),
        "signing_date": _parse_date(doc.get("signing_date", "")),
        "effective_on": _parse_date(doc.get("effective_on", "")),
        "executive_order_number": doc.get("executive_order_number", ""),
        "action": doc.get("action", ""),
        "agency": _agency_names(doc),
        "abstract": _truncate(doc.get("abstract", ""), 300),
        "significant": doc.get("significant", False),
        "html_url": doc.get("html_url", ""),
        "comments_close_on": _parse_date(doc.get("comments_close_on", "")),
    }


def _flatten_docs(docs):
    return [_flatten_single_doc(d) for d in docs]


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   Federal Register -- Regulatory & Policy Client
  =====================================================

   DOCUMENTS
     1) latest              Latest documents
     2) executive-orders    Recent executive orders
     3) rules               Final rules (by agency)
     4) proposed            Proposed rules (by agency)
     5) significant         Economically significant rules

   SEARCH
     6) search              Full-text search
     7) document            Get document by number
     8) suggested           Curated topic packs by section

   MONITORING
     9) public-inspection   Upcoming filings (pre-publication)
    10) pi-current          Currently on public inspection desk
    11) pi-by-date          Public inspection filings by date
    12) tracker             Multi-agency activity tracker
    13) pipeline            Regulatory pipeline snapshot

   AGGREGATION (Facets)
    14) facet               Counts by facet (time/agency/topic/type/section)
    15) eo-pace             EO + proclamation + memo counts by month

   REFERENCE
    16) agencies            List curated agencies

   q) quit
"""


def _i_latest():
    n = _prompt("Number of documents", "20")
    cmd_latest(per_page=int(n))

def _i_executive_orders():
    days = _prompt("Days to look back", "90")
    n = _prompt("Max results", "20")
    cmd_executive_orders(per_page=int(n), days=int(days))

def _i_rules():
    print(f"  Available agencies: {', '.join(AGENCY_REGISTRY.keys())}")
    agency = _prompt("Agency alias (or 'all')", "all")
    days = _prompt("Days to look back", "90")
    agency = None if agency == "all" else agency
    cmd_rules(agency_alias=agency, days=int(days))

def _i_proposed():
    print(f"  Available agencies: {', '.join(AGENCY_REGISTRY.keys())}")
    agency = _prompt("Agency alias (or 'all')", "all")
    days = _prompt("Days to look back", "90")
    agency = None if agency == "all" else agency
    cmd_proposed(agency_alias=agency, days=int(days))

def _i_significant():
    days = _prompt("Days to look back", "180")
    cmd_significant(days=int(days))

def _i_search():
    term = _prompt("Search term")
    print(f"  Filter by type? (rule/proposed/notice/presidential/all)")
    dtype = _prompt("Type", "all")
    dtype = None if dtype == "all" else dtype
    cmd_search(term=term, doc_type=dtype)

def _i_document():
    doc_num = _prompt("Document number (e.g. 2026-07143)")
    cmd_document(doc_number=doc_num)

def _i_suggested():
    print(f"  Sections: {', '.join(SUGGEST_SECTIONS)}")
    sec = _prompt("Section (blank for all)", "money")
    cmd_suggested(section=sec or None)

def _i_public_inspection():
    cmd_public_inspection()

def _i_pi_current():
    cmd_pi_current()

def _i_pi_by_date():
    date_str = _prompt("Date (YYYY-MM-DD)", datetime.now().strftime("%Y-%m-%d"))
    cmd_pi_by_date(date_str)

def _i_tracker():
    print(f"  Available groups: {', '.join(AGENCY_GROUPS.keys())}")
    groups = _prompt("Groups (comma-separated)", "financial,trade,executive")
    days = _prompt("Days to look back", "30")
    group_list = [g.strip() for g in groups.split(",")]
    cmd_tracker(groups=group_list, days=int(days))

def _i_pipeline():
    days = _prompt("Days to look back", "180")
    cmd_pipeline(days=int(days))

def _i_facet():
    print(f"  Facet keys: {', '.join(FACET_KEYS)}")
    fkey = _prompt("Facet key", "monthly")
    print(f"  Type filter: rule/proposed/notice/presidential/all")
    dtype = _prompt("Type", "all")
    dtype = None if dtype == "all" else dtype
    agency = _prompt("Agency alias (or 'all')", "all")
    agency = None if agency == "all" else agency
    days = _prompt("Days to look back (blank for no filter)", "365")
    term = _prompt("Search term (optional)", "")
    term = term or None
    significant = _prompt("Significant only? (y/N)", "n").lower() in ("y", "yes")
    cmd_facets(facet_key=fkey, doc_type=dtype, agency_alias=agency,
               term=term, significant_only=significant,
               days=int(days) if days else None)

def _i_eo_pace():
    days = _prompt("Days to look back", "365")
    cmd_eo_pace(days=int(days))

def _i_agencies():
    cmd_agencies()


COMMAND_MAP = {
    "1":  _i_latest,
    "2":  _i_executive_orders,
    "3":  _i_rules,
    "4":  _i_proposed,
    "5":  _i_significant,
    "6":  _i_search,
    "7":  _i_document,
    "8":  _i_suggested,
    "9":  _i_public_inspection,
    "10": _i_pi_current,
    "11": _i_pi_by_date,
    "12": _i_tracker,
    "13": _i_pipeline,
    "14": _i_facet,
    "15": _i_eo_pace,
    "16": _i_agencies,
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

VALID_AGENCIES = list(AGENCY_REGISTRY.keys()) + ["all"]
VALID_TYPES = list(DOC_TYPES.keys()) + ["all"]
VALID_GROUPS = list(AGENCY_GROUPS.keys())


def build_argparse():
    p = argparse.ArgumentParser(
        prog="federal_register.py",
        description="Federal Register -- Regulatory & Policy Document Client",
    )
    sub = p.add_subparsers(dest="command")

    # latest
    s = sub.add_parser("latest", help="Latest documents")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # executive-orders
    s = sub.add_parser("executive-orders", help="Recent executive orders")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # rules
    s = sub.add_parser("rules", help="Final rules by agency")
    s.add_argument("--agency", choices=VALID_AGENCIES, default="all")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # proposed
    s = sub.add_parser("proposed", help="Proposed rules by agency")
    s.add_argument("--agency", choices=VALID_AGENCIES, default="all")
    s.add_argument("--days", type=int, default=90)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # significant
    s = sub.add_parser("significant", help="Economically significant rules")
    s.add_argument("--days", type=int, default=180)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # search
    s = sub.add_parser("search", help="Full-text search")
    s.add_argument("term", help="Search term")
    s.add_argument("--type", choices=VALID_TYPES, default="all")
    s.add_argument("--agency", choices=VALID_AGENCIES, default="all")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # document
    s = sub.add_parser("document", help="Get document by number")
    s.add_argument("doc_number", help="Document number (e.g. 2026-07143)")
    s.add_argument("--json", action="store_true")

    # public-inspection
    s = sub.add_parser("public-inspection", help="Upcoming filings")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # tracker
    s = sub.add_parser("tracker", help="Multi-agency activity tracker")
    s.add_argument("--groups", default="financial,trade,executive",
                   help="Comma-separated groups: " + ",".join(VALID_GROUPS))
    s.add_argument("--days", type=int, default=30)
    s.add_argument("--count", type=int, default=10)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # pipeline
    s = sub.add_parser("pipeline", help="Regulatory pipeline snapshot")
    s.add_argument("--days", type=int, default=180)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # agencies
    s = sub.add_parser("agencies", help="List curated agencies")
    s.add_argument("--json", action="store_true")

    # --- Extended: Facets ----------------------------------------------------
    s = sub.add_parser("facet",
                       help="Aggregation counts by facet (time, agency, topic, type, section)")
    s.add_argument("facet_key", choices=FACET_KEYS,
                   help="daily|weekly|monthly|quarterly|yearly|agency|topic|type|subtype|section")
    s.add_argument("--type", dest="doc_type",
                   choices=list(DOC_TYPES.keys()) + ["all"], default="all")
    s.add_argument("--agency", choices=VALID_AGENCIES, default="all")
    s.add_argument("--presidential-type",
                   choices=list(PRESIDENTIAL_SUBTYPES.keys()), default=None)
    s.add_argument("--term", default=None, help="Optional search term")
    s.add_argument("--significant", action="store_true",
                   help="Filter to economically significant")
    s.add_argument("--days", type=int, default=None,
                   help="Publication date window (days)")
    s.add_argument("--date-gte", default=None,
                   help="Publication date >= YYYY-MM-DD")
    s.add_argument("--date-lte", default=None,
                   help="Publication date <= YYYY-MM-DD")
    s.add_argument("--head", type=int, default=25,
                   help="Top-N non-time facets")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("eo-pace",
                       help="Monthly EO + proclamation + memo counts")
    s.add_argument("--days", type=int, default=365)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # --- Extended: Suggested Searches ---------------------------------------
    s = sub.add_parser("suggested",
                       help="Curated topic packs (pre-built queries by section)")
    s.add_argument("--section", choices=SUGGEST_SECTIONS, default=None)
    s.add_argument("--json", action="store_true")

    # --- Extended: Public Inspection Current / By-Date ----------------------
    s = sub.add_parser("pi-current",
                       help="Documents currently on public inspection desk")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("pi-by-date",
                       help="Public inspection filings on a specific date")
    s.add_argument("date", help="YYYY-MM-DD")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    cnt = getattr(args, "count", 20)
    days = getattr(args, "days", 90)

    agency = getattr(args, "agency", "all")
    agency = None if agency == "all" else agency

    if args.command == "latest":
        cmd_latest(per_page=cnt, as_json=j, export_fmt=exp)
    elif args.command == "executive-orders":
        cmd_executive_orders(per_page=cnt, days=days, as_json=j, export_fmt=exp)
    elif args.command == "rules":
        cmd_rules(agency_alias=agency, per_page=cnt, days=days, as_json=j, export_fmt=exp)
    elif args.command == "proposed":
        cmd_proposed(agency_alias=agency, per_page=cnt, days=days, as_json=j, export_fmt=exp)
    elif args.command == "significant":
        cmd_significant(per_page=cnt, days=days, as_json=j, export_fmt=exp)
    elif args.command == "search":
        dtype = getattr(args, "type", "all")
        dtype = None if dtype == "all" else dtype
        cmd_search(term=args.term, doc_type=dtype, agency_alias=agency,
                   per_page=cnt, as_json=j, export_fmt=exp)
    elif args.command == "document":
        cmd_document(doc_number=args.doc_number, as_json=j)
    elif args.command == "public-inspection":
        cmd_public_inspection(per_page=cnt, as_json=j, export_fmt=exp)
    elif args.command == "tracker":
        group_list = [g.strip() for g in args.groups.split(",")]
        cmd_tracker(groups=group_list, days=days, per_page=cnt, as_json=j, export_fmt=exp)
    elif args.command == "pipeline":
        cmd_pipeline(days=days, as_json=j, export_fmt=exp)
    elif args.command == "agencies":
        cmd_agencies(as_json=j)

    # --- Extended: Facets ---------------------------------------------------
    elif args.command == "facet":
        dtype = getattr(args, "doc_type", "all")
        dtype = None if dtype == "all" else dtype
        cmd_facets(
            facet_key=args.facet_key,
            doc_type=dtype,
            agency_alias=agency,
            presidential_type=getattr(args, "presidential_type", None),
            term=getattr(args, "term", None),
            significant_only=getattr(args, "significant", False),
            days=getattr(args, "days", None),
            date_gte=getattr(args, "date_gte", None),
            date_lte=getattr(args, "date_lte", None),
            head=getattr(args, "head", 25),
            as_json=j,
            export_fmt=exp,
        )
    elif args.command == "eo-pace":
        cmd_eo_pace(days=days, as_json=j, export_fmt=exp)

    # --- Extended: Suggested Searches ---------------------------------------
    elif args.command == "suggested":
        cmd_suggested(section=getattr(args, "section", None), as_json=j)

    # --- Extended: Public Inspection ----------------------------------------
    elif args.command == "pi-current":
        cmd_pi_current(as_json=j, export_fmt=exp)
    elif args.command == "pi-by-date":
        cmd_pi_by_date(args.date, as_json=j, export_fmt=exp)


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
