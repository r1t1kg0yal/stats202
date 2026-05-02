#!/usr/bin/env python3
"""
SEC EDGAR API Explorer
======================

Complete programmatic access to SEC EDGAR's public data for every US public company:
filings (10-K, 10-Q, 8-K, S-1, DEF 14A, 13F, Form 4, etc.), structured XBRL financials,
full-text search across 20M+ filing documents, company profiles, and cross-company
financial screening.

This is the canonical dataset for US equity textual analysis. Every public company
files with the SEC, and every filing since ~1993 is electronically accessible. XBRL
structured data covers financial statements from 2009 onward with increasing granularity.

API Details
-----------
Data API:   https://data.sec.gov            (submissions, XBRL facts/concepts/frames)
Search API: https://efts.sec.gov/LATEST     (full-text search, Elasticsearch backend)
Archives:   https://www.sec.gov/Archives    (raw filing documents: HTM, TXT, XML)
Tickers:    https://www.sec.gov/files/company_tickers.json
Auth:       User-Agent header required (name + email). No API key needed.
Rate limit: 10 requests/second per IP (SEC enforced via 403 blocks).
Format:     JSON (data APIs), HTML/TXT/XML (filing documents).

Endpoints
---------
/submissions/CIK{cik}.json
    Full filing history for a company. Returns company profile metadata (name, SIC code,
    state, fiscal year end, exchanges, former names) plus up to 1000 recent filings with
    form type, filing date, accession number, and primary document filename.

/api/xbrl/companyfacts/CIK{cik}.json
    All XBRL financial facts ever reported by a company, organized by taxonomy (us-gaap,
    dei, ifrs-full), concept, and unit. This is the structured financial data from 10-K
    and 10-Q filings. A single company's facts JSON can be 1-10MB covering hundreds of
    line items across decades of filings.

/api/xbrl/companyconcept/CIK{cik}/{taxonomy}/{concept}.json
    A single XBRL concept for one company across all filings. Lighter weight than
    companyfacts when you only need one metric.

/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json
    A single concept across ALL filers for a given period. This is the cross-company
    screening endpoint. Example: Revenue for all companies in CY2024. Returns ~2,000-6,000
    companies per concept. Period formats: CY2024 (annual), CY2024Q1 (quarterly),
    CY2024Q1I (instantaneous for balance sheet items).

efts.sec.gov/LATEST/search-index
    Full-text search across all EDGAR filings since 2001. Supports boolean operators
    (AND, OR, NOT), exact phrase matching, wildcards, and filtering by form type, date
    range, CIK, and SIC code. Returns Elasticsearch-style results with aggregation
    facets for SIC industry, state, and entity.

Key Identifiers
---------------
CIK     Central Index Key. SEC's unique company identifier. 10-digit zero-padded.
        Apple: 0000320193, Microsoft: 0000789019, NVIDIA: 0001045810.
Ticker  Exchange ticker symbol. Maps to CIK via company_tickers.json (~10,000 tickers).
SIC     Standard Industrial Classification code. 4-digit industry code.
        7372 = Prepackaged Software, 6022 = State Banks, 2834 = Pharmaceuticals.
Accession Number
        Unique filing identifier. Format: {filer-id}-{yy}-{sequence}.
        Example: 0000320193-24-000123. Used to construct URLs to filing documents.

Filing Types (most common for equity analysis)
----------------------------------------------
10-K    Annual report. MD&A, risk factors, financial statements, notes, exhibits.
        Typically 50,000-100,000 words. Filed within 60 days of fiscal year end (large
        accelerated filers) or 90 days (smaller filers).
10-Q    Quarterly report. Condensed financials, MD&A, risk factor updates.
        Filed within 40/45 days of quarter end. Three per year (Q1, Q2, Q3).
8-K     Current report. Material events: earnings releases, M&A, leadership changes,
        bankruptcy, material agreements. Filed within 4 business days of event.
DEF 14A Definitive proxy statement. Executive compensation, board composition,
        shareholder proposals. Filed ahead of annual meetings.
S-1     IPO registration statement. Complete business description, risk factors,
        financial history, use of proceeds.
13F-HR  Institutional investment manager holdings report. Quarterly portfolio
        disclosure for managers with >$100M AUM. The "whale watching" filing.
4       Insider transaction report. Stock purchases/sales/grants by officers,
        directors, and 10% shareholders. Filed within 2 business days.
SC 13D  Beneficial ownership report. Filed when acquiring >5% of a company's shares
        with activist intent.

Analytical Use Cases
--------------------
- Fundamental equity research: structured financials + 10-K narrative
- Risk factor monitoring: full-text search for emerging risk language
- Earnings quality analysis: XBRL financials + notes text
- Insider activity tracking: Form 4 filings by company or person
- Institutional ownership shifts: 13F-HR quarterly snapshots
- Sector screening: cross-company XBRL frames for financial metrics
- IPO analysis: S-1 text + financial data
- M&A monitoring: 8-K filings with Item 1.01 (material agreements)
- Executive compensation benchmarking: DEF 14A proxy data
- Credit analysis: debt levels, coverage ratios, covenant language in filings

Dependencies
------------
pip install requests

Dual-Mode CLI
-------------
Running without arguments launches the interactive menu.
Running with a subcommand (e.g. `python edgar_scraper.py download AAPL --form 10-K`)
runs non-interactively for scripting and automation.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import html
from collections import OrderedDict
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

SEC_BASE = "https://data.sec.gov"
EFTS_BASE = "https://efts.sec.gov/LATEST/search-index"
SEC_WWW = "https://www.sec.gov"
ARCHIVES = f"{SEC_WWW}/Archives/edgar/data"
TICKERS_URL = f"{SEC_WWW}/files/company_tickers.json"

USER_AGENT = "DataScraper/1.0 (research@example.com)"

# SIC code to industry name mapping (most common for equity analysis)
SIC_INDUSTRIES = {
    "1311": "Crude Petroleum & Natural Gas",
    "2834": "Pharmaceutical Preparations",
    "2836": "Biological Products",
    "2860": "Industrial Chemicals",
    "3559": "Special Industry Machinery",
    "3570": "Computer & Office Equipment",
    "3572": "Computer Storage Devices",
    "3576": "Computer Communications Equipment",
    "3577": "Computer Peripheral Equipment",
    "3621": "Motors & Generators",
    "3663": "Radio & TV Broadcast Equipment",
    "3669": "Communications Equipment",
    "3674": "Semiconductors",
    "3690": "Electronic Components",
    "3714": "Motor Vehicle Parts",
    "3812": "Defense Electronics",
    "3825": "Instruments for Measuring",
    "3841": "Surgical & Medical Instruments",
    "3845": "Electromedical Equipment",
    "4011": "Railroads",
    "4210": "Trucking",
    "4512": "Air Transportation",
    "4513": "Air Courier Services",
    "4813": "Telephone Communications",
    "4911": "Electric Services",
    "4931": "Electric & Gas Services",
    "5045": "Computers & Peripherals",
    "5065": "Electronic Parts & Equipment",
    "5122": "Drugs",
    "5140": "Groceries",
    "5311": "Department Stores",
    "5331": "Variety Stores",
    "5411": "Grocery Stores",
    "5812": "Eating Places",
    "5912": "Drug Stores",
    "5940": "Sporting Goods",
    "5961": "Catalog & Mail-Order Houses",
    "6020": "Savings Institutions",
    "6021": "National Commercial Banks",
    "6022": "State Commercial Banks",
    "6035": "Savings Institution, Federally Chartered",
    "6141": "Personal Credit Institutions",
    "6153": "Short-Term Business Credit",
    "6159": "Federal-Sponsored Credit Agencies",
    "6199": "Finance Services",
    "6211": "Security Brokers & Dealers",
    "6282": "Investment Advice",
    "6311": "Fire, Marine & Casualty Insurance",
    "6321": "Accident & Health Insurance",
    "6331": "Fire, Marine & Casualty Insurance",
    "6399": "Insurance Carriers",
    "6411": "Insurance Agents & Brokers",
    "6500": "Real Estate",
    "6510": "Real Estate Operators",
    "6512": "Operators of Apartment Buildings",
    "6531": "Real Estate Agents & Managers",
    "6552": "Land Subdividers & Developers",
    "6726": "Investment Offices",
    "6770": "Blank Checks",
    "6798": "Real Estate Investment Trusts",
    "7011": "Hotels & Motels",
    "7310": "Services-To Buildings",
    "7361": "Help Supply Services",
    "7363": "Help Supply Services",
    "7370": "Computer Processing & Data Preparation",
    "7371": "Computer Programming & Data Processing",
    "7372": "Prepackaged Software",
    "7374": "Computer Processing & Data Preparation",
    "7389": "Miscellaneous Business Services",
    "7812": "Motion Picture Production",
    "7990": "Amusement & Recreation Services",
    "8000": "Health Services",
    "8011": "Offices & Clinics of Doctors",
    "8049": "Offices & Clinics of Other Health Practitioners",
    "8051": "Skilled Nursing Care Facilities",
    "8060": "Hospitals",
    "8071": "Health Services",
    "8082": "Home Health Care Services",
    "8093": "Specialty Outpatient Facilities",
    "8711": "Engineering Services",
    "8731": "Commercial Physical & Biological Research",
    "8742": "Management Consulting Services",
}

FORM_TYPES_CORE = ["10-K", "10-Q", "8-K"]
FORM_TYPES_EXTENDED = [
    "10-K", "10-Q", "8-K", "20-F", "6-K", "10-K/A", "10-Q/A", "8-K/A",
    "S-1", "S-1/A", "S-3", "S-3/A", "DEF 14A", "DEFA14A",
    "13F-HR", "13F-HR/A", "4", "4/A", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
    "424B2", "424B4", "497", "N-CSR", "NPORT-P",
]

# XBRL concept presets organized by analytical theme
XBRL_INCOME_STATEMENT = OrderedDict([
    ("Revenue", ("us-gaap", "Revenues", "USD")),
    ("CostOfRevenue", ("us-gaap", "CostOfRevenue", "USD")),
    ("GrossProfit", ("us-gaap", "GrossProfit", "USD")),
    ("ResearchAndDevelopment", ("us-gaap", "ResearchAndDevelopmentExpense", "USD")),
    ("OperatingExpenses", ("us-gaap", "OperatingExpenses", "USD")),
    ("OperatingIncome", ("us-gaap", "OperatingIncomeLoss", "USD")),
    ("NetIncome", ("us-gaap", "NetIncomeLoss", "USD")),
    ("EPS_Basic", ("us-gaap", "EarningsPerShareBasic", "USD/shares")),
    ("EPS_Diluted", ("us-gaap", "EarningsPerShareDiluted", "USD/shares")),
])

XBRL_BALANCE_SHEET = OrderedDict([
    ("TotalAssets", ("us-gaap", "Assets", "USD")),
    ("CashAndEquivalents", ("us-gaap", "CashAndCashEquivalentsAtCarryingValue", "USD")),
    ("ShortTermInvestments", ("us-gaap", "ShortTermInvestments", "USD")),
    ("AccountsReceivable", ("us-gaap", "AccountsReceivableNetCurrent", "USD")),
    ("Inventory", ("us-gaap", "InventoryNet", "USD")),
    ("PropertyPlantEquipment", ("us-gaap", "PropertyPlantAndEquipmentNet", "USD")),
    ("Goodwill", ("us-gaap", "Goodwill", "USD")),
    ("IntangibleAssets", ("us-gaap", "IntangibleAssetsNetExcludingGoodwill", "USD")),
    ("TotalLiabilities", ("us-gaap", "Liabilities", "USD")),
    ("CurrentLiabilities", ("us-gaap", "LiabilitiesCurrent", "USD")),
    ("LongTermDebt", ("us-gaap", "LongTermDebt", "USD")),
    ("StockholdersEquity", ("us-gaap", "StockholdersEquity", "USD")),
    ("CommonSharesOutstanding", ("us-gaap", "CommonStockSharesOutstanding", "shares")),
])

XBRL_CASH_FLOW = OrderedDict([
    ("OperatingCashFlow", ("us-gaap", "NetCashProvidedByOperatingActivities", "USD")),
    ("CapitalExpenditure", ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD")),
    ("Depreciation", ("us-gaap", "DepreciationDepletionAndAmortization", "USD")),
    ("DividendsPaid", ("us-gaap", "PaymentsOfDividends", "USD")),
    ("ShareRepurchases", ("us-gaap", "PaymentsForRepurchaseOfCommonStock", "USD")),
])

XBRL_PRESETS = {
    "income": XBRL_INCOME_STATEMENT,
    "balance_sheet": XBRL_BALANCE_SHEET,
    "cash_flow": XBRL_CASH_FLOW,
    "default": OrderedDict(
        list(XBRL_INCOME_STATEMENT.items()) +
        list(XBRL_BALANCE_SHEET.items()) +
        list(XBRL_CASH_FLOW.items())
    ),
}

COMMON_XBRL_CONCEPTS = XBRL_PRESETS["default"]


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

_session = requests.Session()
_session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
})

_last_request_time = 0.0
_request_count = 0
_request_errors = 0


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 0.105:
        time.sleep(0.105 - elapsed)
    _last_request_time = time.time()


def _get(url, params=None, accept_html=False, retries=2):
    """GET with rate limiting, retries, and error handling."""
    global _request_count, _request_errors
    _rate_limit()
    headers = {}
    if accept_html:
        headers["Accept"] = "text/html, application/xhtml+xml, */*"

    for attempt in range(retries + 1):
        try:
            resp = _session.get(url, params=params, timeout=30, headers=headers)
            _request_count += 1
            if resp.status_code == 404:
                return None
            if resp.status_code == 429 or resp.status_code == 403:
                wait = 2 ** (attempt + 1)
                print(f"  [!] Rate limited ({resp.status_code}), waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            ctype = resp.headers.get("Content-Type", "")
            if "json" in ctype:
                return resp.json()
            return resp.text
        except requests.exceptions.Timeout:
            _request_errors += 1
            if attempt < retries:
                print(f"  [!] Timeout, retrying ({attempt+1}/{retries})...")
                time.sleep(1)
            else:
                print(f"  [!] Timeout after {retries+1} attempts: {url}")
                return None
        except requests.exceptions.ConnectionError:
            _request_errors += 1
            if attempt < retries:
                time.sleep(2)
            else:
                return None
    return None


def _request_stats():
    return {"requests": _request_count, "errors": _request_errors}


# ---------------------------------------------------------------------------
# Ticker / CIK mapping
# ---------------------------------------------------------------------------

_ticker_cache = None


def _load_tickers():
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache
    print("  Loading SEC ticker database...")
    data = _get(TICKERS_URL)
    if not data:
        print("  [!] Failed to load ticker database")
        return {}
    _ticker_cache = {}
    for entry in data.values():
        ticker = entry.get("ticker", "").upper()
        cik = str(entry.get("cik_str", ""))
        title = entry.get("title", "")
        if ticker and cik:
            _ticker_cache[ticker] = {"cik": cik, "title": title, "ticker": ticker}
    print(f"  Loaded {len(_ticker_cache):,} tickers")
    return _ticker_cache


def _pad_cik(cik):
    return str(cik).zfill(10)


def resolve_company(query):
    """Resolve a ticker, CIK, or name fragment to a list of company matches."""
    tickers = _load_tickers()
    query_upper = query.strip().upper()

    if query_upper in tickers:
        e = tickers[query_upper]
        return [{"cik": e["cik"], "ticker": e["ticker"], "title": e["title"]}]

    if query_upper.isdigit():
        for e in tickers.values():
            if e["cik"] == query_upper:
                return [{"cik": e["cik"], "ticker": e["ticker"], "title": e["title"]}]

    matches = []
    for e in tickers.values():
        if query_upper in e["title"].upper() or query_upper in e["ticker"]:
            matches.append({"cik": e["cik"], "ticker": e["ticker"], "title": e["title"]})
    return matches[:25]


def _resolve_one(query):
    """Resolve to exactly one company or None."""
    matches = resolve_company(query)
    if not matches:
        print(f"  No company found for '{query}'")
        return None
    if len(matches) > 1:
        print(f"  Found {len(matches)} matches, using first: {matches[0]['ticker']} ({matches[0]['title']})")
    return matches[0]


# ---------------------------------------------------------------------------
# Company profile (from submissions)
# ---------------------------------------------------------------------------

def get_submissions(cik):
    url = f"{SEC_BASE}/submissions/CIK{_pad_cik(cik)}.json"
    return _get(url)


def extract_company_profile(submissions):
    """Extract structured company profile from submissions metadata."""
    if not submissions:
        return None
    profile = {
        "cik": submissions.get("cik", ""),
        "name": submissions.get("name", ""),
        "entity_type": submissions.get("entityType", ""),
        "sic": submissions.get("sic", ""),
        "sic_description": submissions.get("sicDescription", ""),
        "industry": SIC_INDUSTRIES.get(submissions.get("sic", ""), ""),
        "ticker": "",
        "exchanges": submissions.get("exchanges", []),
        "ein": submissions.get("ein", ""),
        "state_of_incorporation": submissions.get("stateOfIncorporation", ""),
        "fiscal_year_end": submissions.get("fiscalYearEnd", ""),
        "category": submissions.get("category", ""),
        "insider_transaction_for_owner_exists": submissions.get("insiderTransactionForOwnerExists", 0),
        "insider_transaction_for_issuer_exists": submissions.get("insiderTransactionForIssuerExists", 0),
    }

    tickers = submissions.get("tickers", [])
    if tickers:
        profile["ticker"] = tickers[0]
        profile["all_tickers"] = tickers

    addresses = submissions.get("addresses", {})
    mailing = addresses.get("mailing", {})
    business = addresses.get("business", {})
    profile["mailing_address"] = {
        "street": mailing.get("street1", ""),
        "street2": mailing.get("street2", ""),
        "city": mailing.get("city", ""),
        "state": mailing.get("stateOrCountry", ""),
        "zip": mailing.get("zipCode", ""),
    }
    profile["business_address"] = {
        "street": business.get("street1", ""),
        "street2": business.get("street2", ""),
        "city": business.get("city", ""),
        "state": business.get("stateOrCountry", ""),
        "zip": business.get("zipCode", ""),
        "phone": business.get("phone", ""),
    }

    former = submissions.get("formerNames", [])
    if former:
        profile["former_names"] = [
            {"name": f.get("name", ""), "from": f.get("from", ""), "to": f.get("to", "")}
            for f in former
        ]

    return profile


def extract_filings(submissions, form_filter=None, max_filings=None):
    """Extract flat list of filings from submissions JSON."""
    recent = submissions.get("filings", {}).get("recent", {})
    if not recent:
        return []

    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    descriptions = recent.get("primaryDocDescription", [])
    report_dates = recent.get("reportDate", [])
    items_list = recent.get("items", [])
    sizes = recent.get("size", [])
    is_xbrl = recent.get("isXBRL", [])

    filings = []
    for i in range(len(forms)):
        if form_filter and forms[i] not in form_filter:
            continue
        filings.append({
            "form": forms[i],
            "filingDate": dates[i] if i < len(dates) else "",
            "accessionNumber": accessions[i] if i < len(accessions) else "",
            "primaryDocument": primary_docs[i] if i < len(primary_docs) else "",
            "primaryDocDescription": descriptions[i] if i < len(descriptions) else "",
            "reportDate": report_dates[i] if i < len(report_dates) else "",
            "items": items_list[i] if i < len(items_list) else "",
            "size": sizes[i] if i < len(sizes) else 0,
            "isXBRL": is_xbrl[i] if i < len(is_xbrl) else 0,
        })
        if max_filings and len(filings) >= max_filings:
            break
    return filings


def build_filing_url(cik, accession_number, primary_doc):
    acc_no_dashes = accession_number.replace("-", "")
    return f"{ARCHIVES}/{int(cik)}/{acc_no_dashes}/{primary_doc}"


def build_filing_index_url(cik, accession_number):
    acc_no_dashes = accession_number.replace("-", "")
    return f"{ARCHIVES}/{int(cik)}/{acc_no_dashes}/"


# ---------------------------------------------------------------------------
# Filing index and document listing
# ---------------------------------------------------------------------------

def get_filing_index(cik, accession_number):
    acc_no_dashes = accession_number.replace("-", "")
    url = f"{ARCHIVES}/{int(cik)}/{acc_no_dashes}/index.json"
    return _get(url)


# ---------------------------------------------------------------------------
# HTML stripping for filing text
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False
        if tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th"):
            self.parts.append("\n")
        if tag == "td":
            self.parts.append("\t")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self):
        raw = "".join(self.parts)
        raw = html.unescape(raw)
        lines = [line.strip() for line in raw.split("\n")]
        deduped = []
        for line in lines:
            if line or (deduped and deduped[-1]):
                deduped.append(line)
        return "\n".join(deduped).strip()


def strip_html(text):
    stripper = _HTMLStripper()
    try:
        stripper.feed(text)
        return stripper.get_text()
    except Exception:
        return re.sub(r"<[^>]+>", " ", text)


# ---------------------------------------------------------------------------
# Filing document download
# ---------------------------------------------------------------------------

def download_filing_text(cik, accession_number, primary_doc):
    url = build_filing_url(cik, accession_number, primary_doc)
    raw = _get(url, accept_html=True)
    if raw is None:
        return None
    if isinstance(raw, dict):
        return json.dumps(raw, indent=2)
    if "<html" in raw.lower()[:500] or "<htm" in raw.lower()[:500]:
        return strip_html(raw)
    return raw


# ---------------------------------------------------------------------------
# 10-K section extraction
# ---------------------------------------------------------------------------

_10K_SECTION_PATTERNS = {
    "risk_factors": [
        r"(?i)item\s*1a[\.\s\-:]+risk\s*factors",
        r"(?i)ITEM\s*1A",
    ],
    "business": [
        r"(?i)item\s*1[\.\s\-:]+business(?!\s*address)",
        r"(?i)ITEM\s*1\b(?!A)",
    ],
    "mda": [
        r"(?i)item\s*7[\.\s\-:]+management.{0,5}s?\s*discussion",
        r"(?i)ITEM\s*7\b(?!A)",
    ],
    "quantitative_disclosures": [
        r"(?i)item\s*7a[\.\s\-:]+quantitative",
        r"(?i)ITEM\s*7A",
    ],
    "financial_statements": [
        r"(?i)item\s*8[\.\s\-:]+financial\s*statements",
        r"(?i)ITEM\s*8\b",
    ],
    "legal_proceedings": [
        r"(?i)item\s*3[\.\s\-:]+legal\s*proceedings",
        r"(?i)ITEM\s*3\b",
    ],
}


def extract_10k_section(text, section_name):
    """Extract a named section from a 10-K filing text.
    Returns the text between the section header and the next Item header, or None."""
    patterns = _10K_SECTION_PATTERNS.get(section_name, [])
    if not patterns:
        return None

    start_pos = None
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            start_pos = match.start()
            break

    if start_pos is None:
        return None

    remainder = text[start_pos:]
    end_match = re.search(r"(?i)\n\s*item\s*\d+[a-zA-Z]?[\.\s\-:]", remainder[100:])
    if end_match:
        return remainder[:100 + end_match.start()].strip()

    return remainder[:50000].strip()


# ---------------------------------------------------------------------------
# XBRL / Company Facts
# ---------------------------------------------------------------------------

def get_company_facts(cik):
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{_pad_cik(cik)}.json"
    return _get(url)


def get_company_concept(cik, taxonomy, concept):
    url = f"{SEC_BASE}/api/xbrl/companyconcept/CIK{_pad_cik(cik)}/{taxonomy}/{concept}.json"
    return _get(url)


def get_frames(taxonomy, concept, unit, period):
    url = f"{SEC_BASE}/api/xbrl/frames/{taxonomy}/{concept}/{unit}/{period}.json"
    return _get(url)


def extract_key_financials(facts, concepts=None, include_quarterly=False):
    """Pull key financial metrics from company facts.
    By default returns annual (10-K) data only. Set include_quarterly=True for 10-Q."""
    if not facts:
        return {}
    if concepts is None:
        concepts = COMMON_XBRL_CONCEPTS

    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    result = {}

    for label, (taxonomy, concept, unit_hint) in concepts.items():
        concept_data = us_gaap.get(concept, {})
        units = concept_data.get("units", {})
        best_unit = None
        for u in units:
            if u == unit_hint or unit_hint in u:
                best_unit = u
                break
        if not best_unit and units:
            best_unit = list(units.keys())[0]
        if best_unit:
            entries = units[best_unit]
            if include_quarterly:
                filtered = entries
            else:
                filtered = [
                    e for e in entries
                    if e.get("form") in ("10-K", "20-F") and e.get("fp") in ("FY", None, "")
                ]
                if not filtered:
                    filtered = [e for e in entries if e.get("form") in ("10-K", "20-F")]
            filtered.sort(key=lambda x: x.get("end", ""))
            result[label] = filtered

    return result


def compute_derived_metrics(key_financials):
    """Compute derived financial ratios from extracted XBRL data."""
    derived = {}

    def _latest(label):
        entries = key_financials.get(label, [])
        if entries:
            return entries[-1].get("val")
        return None

    rev = _latest("Revenue")
    cogs = _latest("CostOfRevenue")
    gp = _latest("GrossProfit")
    opinc = _latest("OperatingIncome")
    ni = _latest("NetIncome")
    assets = _latest("TotalAssets")
    equity = _latest("StockholdersEquity")
    debt = _latest("LongTermDebt")
    cash = _latest("CashAndEquivalents")
    rnd = _latest("ResearchAndDevelopment")
    shares = _latest("CommonSharesOutstanding")

    if rev and rev != 0:
        if gp is not None:
            derived["gross_margin_pct"] = round(gp / rev * 100, 2)
        if opinc is not None:
            derived["operating_margin_pct"] = round(opinc / rev * 100, 2)
        if ni is not None:
            derived["net_margin_pct"] = round(ni / rev * 100, 2)
        if rnd is not None:
            derived["rnd_intensity_pct"] = round(rnd / rev * 100, 2)

    if assets and assets != 0:
        if ni is not None:
            derived["roa_pct"] = round(ni / assets * 100, 2)
        if debt is not None:
            derived["debt_to_assets_pct"] = round(debt / assets * 100, 2)

    if equity and equity != 0:
        if ni is not None:
            derived["roe_pct"] = round(ni / equity * 100, 2)
        if debt is not None:
            derived["debt_to_equity"] = round(debt / equity, 2)

    if debt is not None and cash is not None:
        derived["net_debt"] = debt - cash

    rev_entries = key_financials.get("Revenue", [])
    if len(rev_entries) >= 2:
        prev_rev = rev_entries[-2].get("val")
        curr_rev = rev_entries[-1].get("val")
        if prev_rev and prev_rev != 0 and curr_rev:
            derived["revenue_growth_pct"] = round((curr_rev - prev_rev) / abs(prev_rev) * 100, 2)

    ni_entries = key_financials.get("NetIncome", [])
    if len(ni_entries) >= 2:
        prev_ni = ni_entries[-2].get("val")
        curr_ni = ni_entries[-1].get("val")
        if prev_ni and prev_ni != 0 and curr_ni:
            derived["net_income_growth_pct"] = round((curr_ni - prev_ni) / abs(prev_ni) * 100, 2)

    return derived


# ---------------------------------------------------------------------------
# Full-text search (EFTS)
# ---------------------------------------------------------------------------

def full_text_search(query, forms=None, start_date=None, end_date=None,
                     offset=0, size=10):
    params = {"q": query, "from": offset, "size": size}
    if forms:
        params["forms"] = forms
    if start_date or end_date:
        params["dateRange"] = "custom"
        if start_date:
            params["startdt"] = start_date
        if end_date:
            params["enddt"] = end_date
    return _get(EFTS_BASE, params=params)


def parse_efts_results(data):
    """Parse EFTS search results into hits list and total count."""
    if not data:
        return [], 0
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    hits = []
    for hit in data.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        hits.append({
            "id": hit.get("_id", ""),
            "score": hit.get("_score", 0),
            "entity": (src.get("display_names") or [""])[0],
            "cik": (src.get("ciks") or [""])[0],
            "form": src.get("form", ""),
            "file_type": src.get("file_type", ""),
            "file_date": src.get("file_date", ""),
            "period_ending": src.get("period_ending", ""),
            "accession": src.get("adsh", ""),
            "description": src.get("file_description", ""),
            "location": (src.get("biz_locations") or [""])[0],
            "sic": (src.get("sics") or [""])[0],
        })
    return hits, total


def parse_efts_aggregations(data):
    """Extract aggregation facets from EFTS response (SIC, state, entity, form)."""
    if not data:
        return {}
    aggs = data.get("aggregations", {})
    result = {}
    for agg_name, agg_data in aggs.items():
        buckets = agg_data.get("buckets", [])
        result[agg_name] = [
            {"key": b["key"], "count": b["doc_count"]}
            for b in buckets
        ]
    return result


# ---------------------------------------------------------------------------
# Data persistence
# ---------------------------------------------------------------------------

def _ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _save_json(data, filename):
    _ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    size = os.path.getsize(path)
    print(f"  Saved {path} ({size:,} bytes)")
    return path


def _save_text(text, filename):
    _ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        f.write(text)
    size = os.path.getsize(path)
    print(f"  Saved {path} ({size:,} bytes)")
    return path


def _save_csv(rows, filename, fieldnames=None):
    if not rows:
        print(f"  No data to save for {filename}")
        return None
    _ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  Saved {path} ({len(rows)} rows)")
    return path


def _ts():
    return time.strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _fmt_num(val):
    if val is None:
        return "N/A"
    try:
        f = float(val)
        if f == int(f) and abs(f) < 1e15:
            return f"{int(f):,}"
        return f"{f:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_usd(val):
    if val is None:
        return "N/A"
    try:
        f = float(val)
        if abs(f) >= 1e9:
            return f"${f/1e9:,.2f}B"
        if abs(f) >= 1e6:
            return f"${f/1e6:,.2f}M"
        if abs(f) >= 1e3:
            return f"${f/1e3:,.1f}K"
        return f"${f:,.2f}"
    except (ValueError, TypeError):
        return str(val)


def _fmt_pct(val):
    if val is None:
        return "N/A"
    try:
        return f"{float(val):.1f}%"
    except (ValueError, TypeError):
        return str(val)


def _print_filings_table(filings, limit=30):
    if not filings:
        print("  No filings found.")
        return
    print(f"\n  {'Form':<12} {'Filed':<12} {'Period':<12} {'Accession':<24} {'Description'}")
    print(f"  {'─'*12} {'─'*12} {'─'*12} {'─'*24} {'─'*30}")
    for f in filings[:limit]:
        desc = (f.get("primaryDocDescription") or f.get("description") or "")[:30]
        print(f"  {f['form']:<12} {f.get('filingDate',''):<12} {f.get('reportDate',''):<12} {f.get('accessionNumber',''):<24} {desc}")
    if len(filings) > limit:
        print(f"  ... and {len(filings) - limit} more")
    print(f"  Total: {len(filings)} filings")


def _print_financials_table(key_financials, last_n=5):
    if not key_financials:
        print("  No financial data found.")
        return
    for label, entries in key_financials.items():
        if not entries:
            continue
        recent = entries[-last_n:]
        print(f"\n  {label}:")
        print(f"    {'Period End':<14} {'Value':>18} {'Form':<8} {'Filed'}")
        print(f"    {'─'*14} {'─'*18} {'─'*8} {'─'*12}")
        for e in recent:
            if label in ("EPS_Basic", "EPS_Diluted"):
                val = f"${e.get('val', 'N/A')}"
            elif label == "CommonSharesOutstanding":
                val = _fmt_num(e.get("val"))
            else:
                val = _fmt_usd(e.get("val"))
            print(f"    {e.get('end',''):<14} {val:>18} {e.get('form',''):<8} {e.get('filed','')}")


def _print_profile(profile):
    if not profile:
        print("  No profile data.")
        return
    print(f"\n  Company Profile")
    print(f"  {'='*60}")
    print(f"  Name:          {profile.get('name', 'N/A')}")
    print(f"  CIK:           {profile.get('cik', 'N/A')}")
    print(f"  Ticker(s):     {', '.join(profile.get('all_tickers', [profile.get('ticker', 'N/A')]))}")
    print(f"  Entity Type:   {profile.get('entity_type', 'N/A')}")
    print(f"  SIC:           {profile.get('sic', 'N/A')} - {profile.get('sic_description', profile.get('industry', 'N/A'))}")
    print(f"  Exchanges:     {', '.join(profile.get('exchanges', [])) or 'N/A'}")
    print(f"  State:         {profile.get('state_of_incorporation', 'N/A')}")
    print(f"  Fiscal Year:   {profile.get('fiscal_year_end', 'N/A')}")
    print(f"  Category:      {profile.get('category', 'N/A')}")
    biz = profile.get("business_address", {})
    if biz.get("city"):
        print(f"  Address:       {biz.get('street','')}, {biz.get('city','')}, {biz.get('state','')} {biz.get('zip','')}")
        if biz.get("phone"):
            print(f"  Phone:         {biz['phone']}")
    former = profile.get("former_names", [])
    if former:
        print(f"  Former Names:")
        for fn in former[:5]:
            print(f"    {fn.get('name','')} ({fn.get('from','')[:10]} to {fn.get('to','')[:10]})")


def _print_derived_metrics(derived):
    if not derived:
        return
    print(f"\n  Derived Ratios (latest annual)")
    print(f"  {'─'*40}")
    labels = {
        "gross_margin_pct": "Gross Margin",
        "operating_margin_pct": "Operating Margin",
        "net_margin_pct": "Net Margin",
        "rnd_intensity_pct": "R&D Intensity",
        "roa_pct": "Return on Assets",
        "roe_pct": "Return on Equity",
        "debt_to_equity": "Debt / Equity",
        "debt_to_assets_pct": "Debt / Assets",
        "net_debt": "Net Debt",
        "revenue_growth_pct": "Revenue Growth YoY",
        "net_income_growth_pct": "Net Income Growth YoY",
    }
    for key, label in labels.items():
        val = derived.get(key)
        if val is not None:
            if "pct" in key or "growth" in key or "margin" in key or key in ("roa_pct", "roe_pct"):
                print(f"    {label:<25} {_fmt_pct(val):>12}")
            elif key == "net_debt":
                print(f"    {label:<25} {_fmt_usd(val):>12}")
            else:
                print(f"    {label:<25} {val:>12.2f}")


def _print_search_results(hits, total):
    if not hits:
        print("  No results found.")
        return
    print(f"\n  {total:,} total matches. Showing {len(hits)}:\n")
    for i, h in enumerate(hits, 1):
        print(f"  [{i}] {h['entity']}")
        print(f"      Form: {h['form']}  |  Filed: {h['file_date']}  |  Period: {h['period_ending']}")
        print(f"      Accession: {h['accession']}  |  SIC: {h.get('sic', '')}")
        if h.get("description"):
            print(f"      Desc: {h['description']}")
        print()


# ---------------------------------------------------------------------------
# Command implementations - Core
# ---------------------------------------------------------------------------

def cmd_company_lookup(query=None):
    if query is None:
        query = input("  Ticker, CIK, or company name: ").strip()
    if not query:
        print("  [!] Empty query")
        return None

    matches = resolve_company(query)
    if not matches:
        print(f"  No matches for '{query}'")
        return None

    print(f"\n  Found {len(matches)} match(es):\n")
    print(f"  {'#':<4} {'Ticker':<10} {'CIK':<12} {'Company Name'}")
    print(f"  {'─'*4} {'─'*10} {'─'*12} {'─'*40}")
    for i, m in enumerate(matches, 1):
        print(f"  {i:<4} {m['ticker']:<10} {m['cik']:<12} {m['title']}")
    return matches


def cmd_company_profile(ticker=None, save=False):
    """Get full company profile from submissions metadata."""
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None

    print(f"  Fetching profile for {company['ticker']}...")
    subs = get_submissions(company["cik"])
    if not subs:
        print("  [!] No data returned")
        return None

    profile = extract_company_profile(subs)
    _print_profile(profile)

    filings = extract_filings(subs, max_filings=10)
    if filings:
        print(f"\n  Last 10 filings:")
        _print_filings_table(filings, limit=10)

    if save and profile:
        _save_json(profile, f"profile_{company['ticker']}_{_ts()}.json")

    return profile


def cmd_filing_history(ticker=None, form_filter=None, max_filings=None, save=False):
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None

    cik = company["cik"]
    print(f"  Fetching filings for {company['ticker']} ({company['title']}) CIK={cik}...")

    subs = get_submissions(cik)
    if not subs:
        print("  [!] No submission data returned")
        return None

    form_list = [f.strip() for f in form_filter.split(",")] if form_filter else None
    filings = extract_filings(subs, form_filter=form_list, max_filings=max_filings)
    _print_filings_table(filings)

    if save and filings:
        _save_json({
            "company": company,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "form_filter": form_filter,
            "filing_count": len(filings),
            "filings": filings,
        }, f"filings_{company['ticker']}_{_ts()}.json")

    return {"company": company, "submissions": subs, "filings": filings}


def cmd_filing_download(ticker=None, form_type=None, count=None, save=True):
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None
    cik = company["cik"]

    if form_type is None:
        form_type = input("  Form type (e.g. 10-K, 10-Q, 8-K) [10-K]: ").strip() or "10-K"
    if count is None:
        try:
            count = int(input("  Number of filings to download [1]: ").strip() or "1")
        except ValueError:
            count = 1

    print(f"  Fetching filing list for {company['ticker']}...")
    subs = get_submissions(cik)
    if not subs:
        return None

    filings = extract_filings(subs, form_filter=[form_type], max_filings=count)
    if not filings:
        print(f"  [!] No {form_type} filings found")
        return None

    print(f"  Found {len(filings)} {form_type} filing(s). Downloading...\n")
    downloaded = []
    for i, filing in enumerate(filings, 1):
        acc = filing["accessionNumber"]
        doc = filing["primaryDocument"]
        if not doc:
            print(f"  [{i}/{len(filings)}] Skipping {acc} - no primary document")
            continue

        print(f"  [{i}/{len(filings)}] {filing['form']} filed {filing['filingDate']} (period {filing['reportDate']})")
        url = build_filing_url(cik, acc, doc)
        print(f"    URL: {url}")

        text = download_filing_text(cik, acc, doc)
        if text is None:
            print(f"    [!] Download failed")
            continue

        char_count = len(text)
        word_count = len(text.split())
        print(f"    Downloaded: {char_count:,} chars, ~{word_count:,} words")

        if save:
            safe_date = filing["filingDate"].replace("-", "")
            fname = f"{company['ticker']}_{filing['form'].replace('/', '-')}_{safe_date}.txt"
            path = _save_text(text, fname)
            downloaded.append({"filing": filing, "file": path, "chars": char_count, "words": word_count})
        else:
            downloaded.append({"filing": filing, "chars": char_count, "words": word_count})

    print(f"\n  Downloaded {len(downloaded)}/{len(filings)} filings")
    return downloaded


def cmd_company_financials(ticker=None, preset=None, save=False):
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None
    cik = company["cik"]

    if preset is None:
        preset = "default"

    concepts = XBRL_PRESETS.get(preset, COMMON_XBRL_CONCEPTS)

    print(f"  Fetching XBRL facts for {company['ticker']} ({company['title']})...")
    facts = get_company_facts(cik)
    if not facts:
        print("  [!] No XBRL data available")
        return None

    key_fins = extract_key_financials(facts, concepts=concepts)
    _print_financials_table(key_fins)

    derived = compute_derived_metrics(key_fins)
    _print_derived_metrics(derived)

    if save:
        serializable = {}
        for label, entries in key_fins.items():
            serializable[label] = entries
        _save_json({
            "company": company,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "preset": preset,
            "key_financials": serializable,
            "derived_ratios": derived,
        }, f"financials_{company['ticker']}_{_ts()}.json")

    return {"company": company, "facts": facts, "key_financials": key_fins, "derived": derived}


def cmd_concept_lookup(concept_key=None, period=None, save=False):
    if concept_key is None:
        print("\n  Available concepts:")
        for i, (key, (tax, concept, unit)) in enumerate(COMMON_XBRL_CONCEPTS.items(), 1):
            print(f"    {i:>2}. {key:<30} ({concept})")
        choice = input("\n  Concept number or custom concept name: ").strip()
        keys = list(COMMON_XBRL_CONCEPTS.keys())
        try:
            idx = int(choice) - 1
            concept_key = keys[idx]
        except (ValueError, IndexError):
            concept_key = choice

    if concept_key in COMMON_XBRL_CONCEPTS:
        taxonomy, concept, unit = COMMON_XBRL_CONCEPTS[concept_key]
    else:
        taxonomy = "us-gaap"
        concept = concept_key
        unit = "USD"
        print(f"  Using custom concept: {taxonomy}/{concept}/{unit}")

    if period is None:
        current_year = time.localtime().tm_year
        period = input(f"  Period (e.g. CY{current_year-1}, CY{current_year-1}Q4) [CY{current_year-1}]: ").strip()
        if not period:
            period = f"CY{current_year-1}"

    print(f"  Fetching {concept} / {unit} for {period}...")
    data = get_frames(taxonomy, concept, unit, period)
    if not data:
        print("  [!] No data returned (concept/period may not exist)")
        return None

    frame_data = data.get("data", [])
    print(f"  {len(frame_data):,} companies reported this concept\n")

    frame_data.sort(key=lambda x: abs(x.get("val", 0)), reverse=True)
    print(f"  {'Entity':<40} {'Value':>18} {'CIK':<12}")
    print(f"  {'─'*40} {'─'*18} {'─'*12}")
    for entry in frame_data[:30]:
        val = _fmt_usd(entry.get("val")) if "USD" in unit else _fmt_num(entry.get("val"))
        print(f"  {entry.get('entityName','')[:40]:<40} {val:>18} {entry.get('cik',''):<12}")
    if len(frame_data) > 30:
        print(f"  ... and {len(frame_data) - 30} more")

    if save:
        _save_json(data, f"frames_{concept}_{period}_{_ts()}.json")

    return data


_UNSET = object()


def cmd_full_text_search(query=None, forms=_UNSET, start_date=_UNSET, end_date=_UNSET,
                         max_results=None, save=False):
    if query is None:
        query = input("  Search query: ").strip()
    if not query:
        print("  [!] Empty query")
        return None
    if forms is _UNSET:
        forms_input = input("  Form types (comma-separated, blank for all): ").strip()
        forms = forms_input if forms_input else None
    if start_date is _UNSET:
        start_date = input("  Start date (YYYY-MM-DD, blank for none): ").strip() or None
    if end_date is _UNSET:
        end_date = input("  End date (YYYY-MM-DD, blank for none): ").strip() or None
    if max_results is None:
        try:
            max_results = int(input("  Max results [50]: ").strip() or "50")
        except ValueError:
            max_results = 50

    all_hits = []
    total = None
    aggregations = None
    page_size = min(max_results, 100)
    offset = 0

    while len(all_hits) < max_results:
        remaining = max_results - len(all_hits)
        fetch_size = min(page_size, remaining)
        data = full_text_search(query, forms=forms, start_date=start_date,
                                end_date=end_date, offset=offset, size=fetch_size)
        if not data:
            break

        if aggregations is None:
            aggregations = parse_efts_aggregations(data)

        hits, total = parse_efts_results(data)
        if not hits:
            break
        all_hits.extend(hits)
        offset += len(hits)

        if len(hits) < fetch_size or offset >= total:
            break

        if len(all_hits) % 100 == 0:
            print(f"  ... fetched {len(all_hits):,} / {min(max_results, total):,}")

    _print_search_results(all_hits, total or len(all_hits))

    if aggregations:
        sic_agg = aggregations.get("sic_filter", [])
        if sic_agg:
            print(f"  Top industries (SIC):")
            for bucket in sic_agg[:10]:
                sic_name = SIC_INDUSTRIES.get(bucket["key"], "")
                print(f"    {bucket['key']:<6} {bucket['count']:>6,} filings  {sic_name}")

        state_agg = aggregations.get("biz_states_filter", [])
        if state_agg:
            print(f"\n  Top states:")
            for bucket in state_agg[:10]:
                print(f"    {bucket['key']:<6} {bucket['count']:>6,} filings")

    if save and all_hits:
        _save_json({
            "query": query, "forms": forms, "start_date": start_date, "end_date": end_date,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_matches": total, "results_returned": len(all_hits),
            "aggregations": aggregations,
            "results": all_hits,
        }, f"search_{query[:30].replace(' ','_')}_{_ts()}.json")

    return {"total": total, "hits": all_hits, "aggregations": aggregations}


def cmd_recent_filings(form_type=None, days=None, save=False):
    if form_type is None:
        form_type = input("  Form type (e.g. 10-K, 10-Q, 8-K) [10-K]: ").strip() or "10-K"
    if days is None:
        try:
            days = int(input("  Look back N days [7]: ").strip() or "7")
        except ValueError:
            days = 7

    end_date = time.strftime("%Y-%m-%d")
    start_ts = time.time() - (days * 86400)
    start_date = time.strftime("%Y-%m-%d", time.localtime(start_ts))

    print(f"  Searching for {form_type} filings from {start_date} to {end_date}...")
    data = full_text_search("*", forms=form_type, start_date=start_date,
                            end_date=end_date, offset=0, size=100)
    if not data:
        print("  [!] No data returned")
        return None

    hits, total = parse_efts_results(data)
    _print_search_results(hits, total)

    if save and hits:
        _save_json({
            "form_type": form_type, "start_date": start_date, "end_date": end_date,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_matches": total, "results": hits,
        }, f"recent_{form_type.replace('/','-')}_{_ts()}.json")

    return {"total": total, "hits": hits}


def cmd_bulk_company_pull(tickers_str=None, forms=None, include_financials=True,
                          include_filings=True, max_filings_each=10):
    if tickers_str is None:
        tickers_str = input("  Tickers (comma-separated, e.g. AAPL,MSFT,GOOG): ").strip()
    if not tickers_str:
        print("  [!] No tickers provided")
        return None

    tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
    if forms is None:
        forms_input = input("  Form types (comma-separated) [10-K,10-Q]: ").strip()
        forms = forms_input if forms_input else "10-K,10-Q"
    form_list = [f.strip() for f in forms.split(",")]

    print(f"\n  Bulk pull: {len(tickers)} companies, forms={forms}")
    print(f"  {'='*60}\n")

    ts = _ts()
    results = {}

    for idx, ticker in enumerate(tickers, 1):
        print(f"  [{idx}/{len(tickers)}] {ticker}")
        company = _resolve_one(ticker)
        if not company:
            results[ticker] = {"error": "not found"}
            continue

        cik = company["cik"]
        entry = {"company": company}

        if include_filings:
            print(f"    Fetching filings...")
            subs = get_submissions(cik)
            if subs:
                profile = extract_company_profile(subs)
                entry["profile"] = profile
                filings = extract_filings(subs, form_filter=form_list,
                                          max_filings=max_filings_each)
                entry["filing_count"] = len(filings)
                entry["filings"] = filings
                print(f"    Found {len(filings)} filings | SIC: {profile.get('sic', 'N/A')} ({profile.get('sic_description', '')})")
            else:
                entry["filings"] = []

        if include_financials:
            print(f"    Fetching financials...")
            facts = get_company_facts(cik)
            if facts:
                key_fins = extract_key_financials(facts)
                entry["key_financials"] = key_fins
                derived = compute_derived_metrics(key_fins)
                entry["derived_ratios"] = derived
                available = [k for k, v in key_fins.items() if v]
                margins = []
                if "gross_margin_pct" in derived:
                    margins.append(f"GM={derived['gross_margin_pct']:.0f}%")
                if "net_margin_pct" in derived:
                    margins.append(f"NM={derived['net_margin_pct']:.0f}%")
                if "revenue_growth_pct" in derived:
                    margins.append(f"RevGr={derived['revenue_growth_pct']:+.0f}%")
                print(f"    Got {len(available)} metrics | {' '.join(margins)}")
            else:
                entry["key_financials"] = {}

        results[ticker] = entry
        print()

    _save_json({
        "tickers": tickers, "forms": forms,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "companies": results,
    }, f"bulk_pull_{ts}.json")

    print(f"  Bulk pull complete: {len(tickers)} companies processed")
    return results


def cmd_browse_filing_index(ticker=None, accession=None):
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None
    cik = company["cik"]

    if accession is None:
        print(f"  Fetching recent filings for {company['ticker']}...")
        subs = get_submissions(cik)
        if not subs:
            return None
        filings = extract_filings(subs, max_filings=20)
        _print_filings_table(filings, limit=20)
        idx_input = input("\n  Filing number to browse (1-20): ").strip()
        try:
            idx = int(idx_input) - 1
            accession = filings[idx]["accessionNumber"]
        except (ValueError, IndexError):
            print("  [!] Invalid selection")
            return None

    print(f"\n  Filing index for {accession}:")
    idx_data = get_filing_index(cik, accession)
    if not idx_data:
        print("  [!] Could not load filing index")
        return None

    items = idx_data.get("directory", {}).get("item", [])
    print(f"\n  {'#':<4} {'Name':<50} {'Size':>12} {'Type':<20}")
    print(f"  {'─'*4} {'─'*50} {'─'*12} {'─'*20}")
    for i, item in enumerate(items, 1):
        print(f"  {i:<4} {item.get('name',''):<50} {str(item.get('size','')):>12} {item.get('type',''):<20}")

    return {"company": company, "accession": accession, "documents": items}


# ---------------------------------------------------------------------------
# Command implementations - Recipes (Equity Analyst)
# ---------------------------------------------------------------------------

def cmd_deep_dive(ticker=None, save=True):
    """Full company deep dive: profile + financials + ratios + recent 10-K text sections."""
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None
    cik = company["cik"]
    ts = _ts()

    print(f"\n  === Deep Dive: {company['ticker']} ({company['title']}) ===\n")

    print("[1/4] Company profile...")
    subs = get_submissions(cik)
    profile = extract_company_profile(subs) if subs else None
    _print_profile(profile)

    print("\n[2/4] XBRL financials...")
    facts = get_company_facts(cik)
    key_fins = extract_key_financials(facts) if facts else {}
    _print_financials_table(key_fins)
    derived = compute_derived_metrics(key_fins)
    _print_derived_metrics(derived)

    print("\n[3/4] Filing history (10-K, 10-Q, 8-K)...")
    filings = extract_filings(subs, form_filter=["10-K", "10-Q", "8-K"], max_filings=20) if subs else []
    _print_filings_table(filings, limit=15)

    print("\n[4/4] Latest 10-K sections (risk factors, MD&A)...")
    tenk_filings = extract_filings(subs, form_filter=["10-K"], max_filings=1) if subs else []
    sections = {}
    if tenk_filings:
        filing = tenk_filings[0]
        doc = filing["primaryDocument"]
        if doc:
            text = download_filing_text(cik, filing["accessionNumber"], doc)
            if text:
                for section_name in ["risk_factors", "mda", "business"]:
                    section_text = extract_10k_section(text, section_name)
                    if section_text:
                        word_count = len(section_text.split())
                        print(f"    {section_name}: {word_count:,} words extracted")
                        sections[section_name] = section_text[:200] + "..." if len(section_text) > 200 else section_text
                        if save:
                            _save_text(section_text,
                                       f"{company['ticker']}_{section_name}_{filing['filingDate'].replace('-','')}.txt")

    if save:
        _save_json({
            "company": company,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "profile": profile,
            "key_financials": {k: v for k, v in key_fins.items()},
            "derived_ratios": derived,
            "recent_filings": filings,
            "section_previews": sections,
        }, f"deep_dive_{company['ticker']}_{ts}.json")

    return {"profile": profile, "key_financials": key_fins, "derived": derived, "filings": filings}


def cmd_peer_compare(tickers_str=None, save=False):
    """Side-by-side financial comparison of multiple companies."""
    if tickers_str is None:
        tickers_str = input("  Tickers (comma-separated, e.g. AAPL,MSFT,GOOG): ").strip()
    if not tickers_str:
        return None

    tickers = [t.strip().upper() for t in tickers_str.split(",") if t.strip()]
    print(f"\n  Peer Comparison: {', '.join(tickers)}\n")

    peer_data = {}
    for ticker in tickers:
        company = _resolve_one(ticker)
        if not company:
            continue
        facts = get_company_facts(company["cik"])
        if facts:
            key_fins = extract_key_financials(facts)
            derived = compute_derived_metrics(key_fins)
            peer_data[ticker] = {"company": company, "derived": derived}

    if not peer_data:
        return None

    metrics = [
        ("Revenue (latest)", "Revenue"),
        ("Net Income", "NetIncome"),
        ("Gross Margin", "gross_margin_pct"),
        ("Operating Margin", "operating_margin_pct"),
        ("Net Margin", "net_margin_pct"),
        ("ROE", "roe_pct"),
        ("ROA", "roa_pct"),
        ("Revenue Growth YoY", "revenue_growth_pct"),
        ("R&D Intensity", "rnd_intensity_pct"),
        ("Debt/Equity", "debt_to_equity"),
    ]

    header = f"  {'Metric':<25}" + "".join(f" {t:>12}" for t in peer_data.keys())
    print(header)
    print(f"  {'─'*25}" + "─"*13*len(peer_data))

    for label, key in metrics:
        row = f"  {label:<25}"
        for ticker, data in peer_data.items():
            derived = data["derived"]
            val = derived.get(key)
            if val is not None:
                if "margin" in key or "pct" in key or "growth" in key:
                    row += f" {val:>11.1f}%"
                elif key == "debt_to_equity":
                    row += f" {val:>12.2f}"
                else:
                    row += f" {_fmt_usd(val):>12}"
            else:
                row += f" {'N/A':>12}"
        print(row)

    if save:
        _save_json({
            "tickers": tickers,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "peers": {t: d["derived"] for t, d in peer_data.items()},
        }, f"peer_compare_{'_'.join(tickers[:5])}_{_ts()}.json")

    return peer_data


def cmd_insider_activity(ticker=None, days=None, save=False):
    """Track insider transactions (Form 4) for a company."""
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None

    if days is None:
        try:
            days = int(input("  Look back N days [90]: ").strip() or "90")
        except ValueError:
            days = 90

    end_date = time.strftime("%Y-%m-%d")
    start_ts = time.time() - (days * 86400)
    start_date = time.strftime("%Y-%m-%d", time.localtime(start_ts))

    cik_padded = _pad_cik(company["cik"])
    print(f"  Searching Form 4 filings for {company['ticker']} ({start_date} to {end_date})...")

    subs = get_submissions(company["cik"])
    if not subs:
        return None

    form4s = extract_filings(subs, form_filter=["4", "4/A"], max_filings=50)
    recent = [f for f in form4s if f.get("filingDate", "") >= start_date]

    if not recent:
        print(f"  No Form 4 filings found in the last {days} days")
        return None

    print(f"\n  Found {len(recent)} insider transaction filings:\n")
    _print_filings_table(recent, limit=30)

    if save:
        _save_json({
            "company": company, "days_back": days,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "form_4_filings": recent,
        }, f"insider_{company['ticker']}_{_ts()}.json")

    return recent


def cmd_institutional_holdings(ticker=None, save=False):
    """Find 13F-HR filings mentioning a company (institutional holders)."""
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None

    print(f"  Searching for 13F-HR filings referencing {company['ticker']}...")
    data = full_text_search(
        f'"{company["title"]}"',
        forms="13F-HR",
        start_date=(time.strftime("%Y-%m-%d", time.localtime(time.time() - 180*86400))),
        offset=0, size=50,
    )
    if not data:
        print("  [!] No results")
        return None

    hits, total = parse_efts_results(data)
    _print_search_results(hits[:20], total)

    if save and hits:
        _save_json({
            "company": company,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_matches": total, "results": hits,
        }, f"institutional_{company['ticker']}_{_ts()}.json")

    return {"total": total, "hits": hits}


def cmd_sector_screen(concept_key=None, period=None, min_val=None, max_val=None, sic=None, save=False):
    """Screen companies by a financial metric using XBRL frames."""
    if concept_key is None:
        print("\n  Available screening metrics:")
        for i, (key, (tax, concept, unit)) in enumerate(COMMON_XBRL_CONCEPTS.items(), 1):
            print(f"    {i:>2}. {key:<30} ({concept})")
        choice = input("\n  Metric number or name: ").strip()
        keys = list(COMMON_XBRL_CONCEPTS.keys())
        try:
            concept_key = keys[int(choice) - 1]
        except (ValueError, IndexError):
            concept_key = choice

    if concept_key in COMMON_XBRL_CONCEPTS:
        taxonomy, concept, unit = COMMON_XBRL_CONCEPTS[concept_key]
    else:
        taxonomy, concept, unit = "us-gaap", concept_key, "USD"

    if period is None:
        current_year = time.localtime().tm_year
        period = input(f"  Period [CY{current_year-1}]: ").strip() or f"CY{current_year-1}"

    print(f"  Fetching {concept} for {period}...")
    data = get_frames(taxonomy, concept, unit, period)
    if not data:
        print("  [!] No data")
        return None

    frame_data = data.get("data", [])

    if min_val is not None:
        frame_data = [d for d in frame_data if d.get("val", 0) >= min_val]
    if max_val is not None:
        frame_data = [d for d in frame_data if d.get("val", 0) <= max_val]

    frame_data.sort(key=lambda x: abs(x.get("val", 0)), reverse=True)

    print(f"\n  {len(frame_data):,} companies match\n")
    print(f"  {'Entity':<40} {'Value':>18} {'CIK':<12}")
    print(f"  {'─'*40} {'─'*18} {'─'*12}")
    for entry in frame_data[:50]:
        val = _fmt_usd(entry.get("val")) if "USD" in unit else _fmt_num(entry.get("val"))
        print(f"  {entry.get('entityName','')[:40]:<40} {val:>18} {entry.get('cik',''):<12}")
    if len(frame_data) > 50:
        print(f"  ... and {len(frame_data) - 50} more")

    if save:
        _save_json({
            "concept": concept, "period": period, "unit": unit,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "company_count": len(frame_data),
            "data": frame_data,
        }, f"screen_{concept}_{period}_{_ts()}.json")

    return frame_data


def cmd_risk_factors(ticker=None, save=True):
    """Extract risk factors section from latest 10-K filing."""
    if ticker is None:
        ticker = input("  Ticker or CIK: ").strip()
    company = _resolve_one(ticker)
    if not company:
        return None

    print(f"  Fetching latest 10-K for {company['ticker']}...")
    subs = get_submissions(company["cik"])
    if not subs:
        return None

    filings = extract_filings(subs, form_filter=["10-K"], max_filings=1)
    if not filings:
        print("  [!] No 10-K filings found")
        return None

    filing = filings[0]
    doc = filing["primaryDocument"]
    if not doc:
        return None

    print(f"  Downloading {filing['form']} filed {filing['filingDate']}...")
    text = download_filing_text(company["cik"], filing["accessionNumber"], doc)
    if not text:
        return None

    risk_text = extract_10k_section(text, "risk_factors")
    if not risk_text:
        print("  [!] Could not locate risk factors section")
        return None

    word_count = len(risk_text.split())
    print(f"  Extracted risk factors: {word_count:,} words")
    print(f"\n  Preview (first 500 chars):")
    print(f"  {'─'*60}")
    print(f"  {risk_text[:500]}...")

    if save:
        fname = f"{company['ticker']}_risk_factors_{filing['filingDate'].replace('-','')}.txt"
        _save_text(risk_text, fname)

    return risk_text


def cmd_earnings_season(days=None, save=False):
    """Track recent 10-K and 10-Q filings (earnings season monitor)."""
    if days is None:
        try:
            days = int(input("  Look back N days [14]: ").strip() or "14")
        except ValueError:
            days = 14

    end_date = time.strftime("%Y-%m-%d")
    start_ts = time.time() - (days * 86400)
    start_date = time.strftime("%Y-%m-%d", time.localtime(start_ts))

    print(f"\n  === Earnings Season Monitor ({start_date} to {end_date}) ===\n")

    for form_type in ["10-K", "10-Q"]:
        print(f"  [{form_type}]")
        data = full_text_search("*", forms=form_type, start_date=start_date,
                                end_date=end_date, offset=0, size=100)
        if data:
            hits, total = parse_efts_results(data)
            print(f"    {total:,} total filings in period")
            for h in hits[:15]:
                print(f"    {h['file_date']}  {h['entity'][:50]}")
            if total > 15:
                print(f"    ... and {total - 15} more")
        print()

    return True


# ---------------------------------------------------------------------------
# Interactive CLI
# ---------------------------------------------------------------------------

def _ask_int(prompt, default):
    val = input(f"  {prompt} (default: {default}): ").strip()
    if not val:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def interactive_loop():
    save_mode = True
    while True:
        print(f"""
  ={'='*74}
  SEC EDGAR Explorer
  ={'='*74}

  CORE:
    1.  Company Lookup           Search by ticker, CIK, or name
    2.  Company Profile          Full company metadata (SIC, addresses, exchanges)
    3.  Filing History           List all filings for a company
    4.  Filing Download          Download full filing text (HTML stripped)
    5.  Company Financials       XBRL structured financial data + derived ratios
    6.  Concept Lookup           Single metric across all companies (frames)
    7.  Full-Text Search         Boolean search across all EDGAR filings
    8.  Recent Filings           Latest filings by form type
    9.  Browse Filing Index      View documents within a filing

  EQUITY ANALYST RECIPES:
    20. Deep Dive                Profile + financials + ratios + 10-K sections
    21. Peer Comparison          Side-by-side financial comparison
    22. Risk Factors             Extract risk factors from latest 10-K
    23. Insider Activity         Track Form 4 insider transactions
    24. Institutional Holdings   13F-HR filings (whale watching)
    25. Sector Screen            Screen companies by financial metric
    26. Earnings Season          Recent 10-K/10-Q filing monitor

  BULK:
    30. Bulk Company Pull        Pull filings + financials for multiple tickers

  TOOLS:
    s.  Save mode toggle         (currently: {'ON' if save_mode else 'OFF'})
    st. Request stats            HTTP request counter
    0.  Quit
""")
        choice = input("  Choice: ").strip().lower()

        try:
            if choice in ("0", "q", "quit", "exit"):
                print("  Goodbye.")
                break
            elif choice == "1":
                cmd_company_lookup()
            elif choice == "2":
                cmd_company_profile(save=save_mode)
            elif choice == "3":
                cmd_filing_history(save=save_mode)
            elif choice == "4":
                cmd_filing_download(save=save_mode)
            elif choice == "5":
                cmd_company_financials(save=save_mode)
            elif choice == "6":
                cmd_concept_lookup(save=save_mode)
            elif choice == "7":
                cmd_full_text_search(save=save_mode)
            elif choice == "8":
                cmd_recent_filings(save=save_mode)
            elif choice == "9":
                cmd_browse_filing_index()
            elif choice == "20":
                cmd_deep_dive(save=save_mode)
            elif choice == "21":
                cmd_peer_compare(save=save_mode)
            elif choice == "22":
                cmd_risk_factors(save=save_mode)
            elif choice == "23":
                cmd_insider_activity(save=save_mode)
            elif choice == "24":
                cmd_institutional_holdings(save=save_mode)
            elif choice == "25":
                cmd_sector_screen(save=save_mode)
            elif choice == "26":
                cmd_earnings_season(save=save_mode)
            elif choice == "30":
                cmd_bulk_company_pull()
            elif choice == "s":
                save_mode = not save_mode
                print(f"  Save mode: {'ON' if save_mode else 'OFF'}")
            elif choice == "st":
                stats = _request_stats()
                print(f"  Requests: {stats['requests']}  Errors: {stats['errors']}")
            else:
                print("  [!] Invalid choice")
        except KeyboardInterrupt:
            print("\n  Interrupted.")
        except Exception as e:
            print(f"  [!] Error: {e}")


# ---------------------------------------------------------------------------
# Non-interactive CLI
# ---------------------------------------------------------------------------

def build_argparse():
    parser = argparse.ArgumentParser(
        description="SEC EDGAR API Explorer - filings, financials, full-text search, and equity analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Core
  python edgar_scraper.py lookup AAPL
  python edgar_scraper.py profile MSFT --save
  python edgar_scraper.py filings MSFT --forms 10-K,10-Q --max 20 --save
  python edgar_scraper.py download TSLA --form 10-K --count 3
  python edgar_scraper.py financials GOOG --save
  python edgar_scraper.py financials AMZN --preset income --save
  python edgar_scraper.py concept Revenue --period CY2024 --save
  python edgar_scraper.py search "artificial intelligence" --forms 10-K --start 2024-01-01 --save
  python edgar_scraper.py recent --form 8-K --days 3 --save

  # Equity analyst recipes
  python edgar_scraper.py deep-dive NVDA
  python edgar_scraper.py peer-compare AAPL,MSFT,GOOG,META --save
  python edgar_scraper.py risk-factors TSLA
  python edgar_scraper.py insider AAPL --days 90
  python edgar_scraper.py holdings NVDA --save
  python edgar_scraper.py screen Revenue --period CY2024 --save
  python edgar_scraper.py earnings-season --days 14

  # Bulk
  python edgar_scraper.py bulk AAPL,MSFT,GOOG,AMZN,NVDA,TSLA --forms 10-K
  python edgar_scraper.py browse AAPL
"""
    )
    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("lookup", help="Find company by ticker, CIK, or name")
    p.add_argument("query", help="Ticker, CIK, or company name fragment")

    p = sub.add_parser("profile", help="Full company profile metadata")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("filings", help="List filings for a company")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--forms", help="Comma-separated form types to filter")
    p.add_argument("--max", type=int, help="Max number of filings")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("download", help="Download full filing text")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--form", default="10-K", help="Form type (default: 10-K)")
    p.add_argument("--count", type=int, default=1, help="Number of filings")
    p.add_argument("--no-save", action="store_true")

    p = sub.add_parser("financials", help="Get XBRL financial data + derived ratios")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--preset", default="default", choices=list(XBRL_PRESETS.keys()),
                   help="Financial data preset (default, income, balance_sheet, cash_flow)")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("concept", help="Single metric across all companies")
    p.add_argument("concept", help="Concept key (e.g. Revenue, NetIncome) or XBRL tag")
    p.add_argument("--period", help="Period (e.g. CY2024, CY2024Q1)")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("search", help="Full-text search across all filings")
    p.add_argument("query", help="Search query (AND, OR, NOT, quotes)")
    p.add_argument("--forms", help="Comma-separated form types")
    p.add_argument("--start", help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", help="End date (YYYY-MM-DD)")
    p.add_argument("--max", type=int, default=50, help="Max results")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("recent", help="Recent filings by form type")
    p.add_argument("--form", default="10-K", help="Form type (default: 10-K)")
    p.add_argument("--days", type=int, default=7, help="Look back N days")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("browse", help="Browse filing index documents")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--accession", help="Specific accession number")

    # Equity analyst recipes
    p = sub.add_parser("deep-dive", help="Full company deep dive with 10-K sections")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--no-save", action="store_true")

    p = sub.add_parser("peer-compare", help="Side-by-side financial comparison")
    p.add_argument("tickers", help="Comma-separated tickers")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("risk-factors", help="Extract risk factors from latest 10-K")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--no-save", action="store_true")

    p = sub.add_parser("insider", help="Track Form 4 insider transactions")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--days", type=int, default=90, help="Look back N days")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("holdings", help="Find 13F-HR filings for institutional holders")
    p.add_argument("ticker", help="Ticker or CIK")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("screen", help="Screen companies by financial metric")
    p.add_argument("concept", help="Concept key or XBRL tag")
    p.add_argument("--period", help="Period (e.g. CY2024)")
    p.add_argument("--save", action="store_true")

    p = sub.add_parser("earnings-season", help="Recent 10-K/10-Q filing monitor")
    p.add_argument("--days", type=int, default=14, help="Look back N days")
    p.add_argument("--save", action="store_true")

    # Bulk
    p = sub.add_parser("bulk", help="Bulk pull for multiple companies")
    p.add_argument("tickers", help="Comma-separated tickers")
    p.add_argument("--forms", default="10-K,10-Q", help="Form types")
    p.add_argument("--max-each", type=int, default=10, help="Max filings per company")
    p.add_argument("--no-financials", action="store_true")
    p.add_argument("--no-filings", action="store_true")

    return parser


def run_noninteractive(args):
    cmd = args.command

    if cmd == "lookup":
        cmd_company_lookup(query=args.query)
    elif cmd == "profile":
        cmd_company_profile(ticker=args.ticker, save=args.save)
    elif cmd == "filings":
        cmd_filing_history(ticker=args.ticker, form_filter=args.forms,
                           max_filings=args.max, save=args.save)
    elif cmd == "download":
        cmd_filing_download(ticker=args.ticker, form_type=args.form,
                            count=args.count, save=not args.no_save)
    elif cmd == "financials":
        cmd_company_financials(ticker=args.ticker, preset=args.preset, save=args.save)
    elif cmd == "concept":
        period = args.period or f"CY{time.localtime().tm_year - 1}"
        cmd_concept_lookup(concept_key=args.concept, period=period, save=args.save)
    elif cmd == "search":
        cmd_full_text_search(query=args.query,
                             forms=args.forms if args.forms else None,
                             start_date=args.start if args.start else None,
                             end_date=args.end if args.end else None,
                             max_results=args.max, save=args.save)
    elif cmd == "recent":
        cmd_recent_filings(form_type=args.form, days=args.days, save=args.save)
    elif cmd == "browse":
        cmd_browse_filing_index(ticker=args.ticker, accession=args.accession)
    elif cmd == "deep-dive":
        cmd_deep_dive(ticker=args.ticker, save=not args.no_save)
    elif cmd == "peer-compare":
        cmd_peer_compare(tickers_str=args.tickers, save=args.save)
    elif cmd == "risk-factors":
        cmd_risk_factors(ticker=args.ticker, save=not args.no_save)
    elif cmd == "insider":
        cmd_insider_activity(ticker=args.ticker, days=args.days, save=args.save)
    elif cmd == "holdings":
        cmd_institutional_holdings(ticker=args.ticker, save=args.save)
    elif cmd == "screen":
        period = args.period or f"CY{time.localtime().tm_year - 1}"
        cmd_sector_screen(concept_key=args.concept, period=period, save=args.save)
    elif cmd == "earnings-season":
        cmd_earnings_season(days=args.days, save=args.save)
    elif cmd == "bulk":
        cmd_bulk_company_pull(tickers_str=args.tickers, forms=args.forms,
                              include_financials=not args.no_financials,
                              include_filings=not args.no_filings,
                              max_filings_each=args.max_each)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  SEC EDGAR API Explorer")
        print("  =====================")
        print(f"  Data API:    {SEC_BASE}")
        print(f"  Search API:  {EFTS_BASE}")
        print(f"  Archives:    {ARCHIVES}")
        print(f"  Rate limit:  10 req/sec (enforced)")
        print(f"  Auth:        User-Agent header only (no API key)")
        print(f"  Data dir:    {DATA_DIR}")
        interactive_loop()


if __name__ == "__main__":
    main()
