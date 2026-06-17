#!/usr/bin/env python3
"""
Congress.gov -- Legislative Tracking Client

Single-script client for the Congress.gov API v3 (api.congress.gov).
Tracks bills, amendments, votes, nominations, and committee actions
relevant to macro/rates/cross-asset analysis.

API key required: set CONGRESS_API_KEY env var, or get one at api.congress.gov/sign-up

Usage:
    python congress.py                                  # interactive CLI
    python congress.py latest                           # latest bills with action
    python congress.py bill 119 hr 1                    # specific bill details
    python congress.py actions 119 hr 1                 # bill action timeline
    python congress.py search "debt ceiling"            # search bills by keyword
    python congress.py tracker                          # curated macro bill tracker
    python congress.py members --state NY               # member lookup
    python congress.py nominations                      # pending nominations
    python congress.py summaries 119 hr 1               # bill summaries
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

BASE_URL = "https://api.congress.gov/v3"
SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json"})

API_KEY = os.environ.get("CONGRESS_API_KEY", "")

CURRENT_CONGRESS = 119  # 2025-2027

BILL_TYPES = {
    "hr":     "House Bill",
    "s":      "Senate Bill",
    "hjres":  "House Joint Resolution",
    "sjres":  "Senate Joint Resolution",
    "hconres": "House Concurrent Resolution",
    "sconres": "Senate Concurrent Resolution",
    "hres":   "House Resolution",
    "sres":   "Senate Resolution",
}

# Curated macro-relevant legislative topics for tracking
MACRO_TOPICS = {
    "debt_ceiling": {
        "label": "Debt Ceiling / Fiscal",
        "terms": ["debt limit", "debt ceiling", "borrowing authority", "extraordinary measures"],
    },
    "tax": {
        "label": "Tax Policy",
        "terms": ["tax reform", "tax cut", "tax increase", "TCJA", "income tax", "capital gains tax"],
    },
    "tariff": {
        "label": "Trade & Tariffs",
        "terms": ["tariff", "trade agreement", "customs duty", "import tax", "trade deficit"],
    },
    "sanctions": {
        "label": "Sanctions & Foreign Policy",
        "terms": ["sanctions", "OFAC", "CAATSA", "IEEPA", "export control"],
    },
    "financial_reg": {
        "label": "Financial Regulation",
        "terms": ["Dodd-Frank", "bank regulation", "financial stability", "systemic risk", "capital requirements"],
    },
    "fed": {
        "label": "Federal Reserve",
        "terms": ["Federal Reserve", "monetary policy", "interest rate", "FOMC"],
    },
    "appropriations": {
        "label": "Appropriations / Spending",
        "terms": ["appropriations", "continuing resolution", "government shutdown", "omnibus", "spending bill"],
    },
    "energy": {
        "label": "Energy Policy",
        "terms": ["energy policy", "oil drilling", "renewable energy", "LNG export", "strategic petroleum"],
    },
    "housing": {
        "label": "Housing & Mortgage",
        "terms": ["housing", "mortgage", "Fannie Mae", "Freddie Mac", "FHFA", "affordable housing"],
    },
    "crypto": {
        "label": "Digital Assets",
        "terms": ["cryptocurrency", "digital asset", "stablecoin", "blockchain", "CBDC"],
    },
}


# --- HTTP + Parsing ----------------------------------------------------------

def _get_api_key():
    key = API_KEY or os.environ.get("CONGRESS_API_KEY", "")
    if not key:
        print("  [WARNING] No API key set. Set CONGRESS_API_KEY env var.")
        print("  Get a free key at: https://api.congress.gov/sign-up/")
        return ""
    return key


def _request(endpoint, params=None, max_retries=3):
    key = _get_api_key()
    if not key:
        return None

    url = f"{BASE_URL}/{endpoint}"
    if params is None:
        params = {}
    params["api_key"] = key
    params.setdefault("format", "json")

    for attempt in range(max_retries):
        try:
            r = SESSION.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 5 * (attempt + 1)
                print(f"  [rate limited, waiting {wait}s...]")
                time.sleep(wait)
                continue
            if r.status_code == 403:
                print("  [API key invalid or missing. Set CONGRESS_API_KEY env var.]")
                return None
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


def _paginate(endpoint, params=None, max_items=250):
    """Fetch up to max_items with pagination."""
    if params is None:
        params = {}
    params["limit"] = min(250, max_items)
    params["offset"] = 0

    all_items = []
    while len(all_items) < max_items:
        data = _request(endpoint, params)
        if not data:
            break

        # API returns data under various keys depending on endpoint
        items = _extract_items(data)
        if not items:
            break

        all_items.extend(items)

        # Check pagination
        pagination = data.get("pagination", {})
        if not pagination.get("next"):
            break

        params["offset"] = params.get("offset", 0) + len(items)
        time.sleep(0.2)

    return all_items[:max_items]


def _extract_items(data):
    """Extract the list items from an API response (key varies by endpoint)."""
    for key in ["bills", "actions", "amendments", "members", "nominations",
                "cosponsors", "subjects", "summaries", "committees",
                "relatedBills", "textVersions", "treaties", "hearings",
                "congressionalRecord", "CRSReports", "houseRollCallVotes",
                "houseRollCallVoteMemberVotes", "committeeReports",
                "sponsoredLegislation", "cosponsoredLegislation",
                "titles", "laws"]:
        if key in data:
            return data[key]
    return []


# --- Data Fetchers -----------------------------------------------------------

def _fetch_bills(congress=None, bill_type=None, limit=20, offset=0):
    if congress and bill_type:
        endpoint = f"bill/{congress}/{bill_type}"
    elif congress:
        endpoint = f"bill/{congress}"
    else:
        endpoint = "bill"

    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0

    bills = data.get("bills", [])
    total = data.get("pagination", {}).get("count", len(bills))
    return bills, total


def _fetch_bill_detail(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}")
    if not data:
        return None
    return data.get("bill", data)


def _fetch_bill_actions(congress, bill_type, number, limit=50):
    data = _request(f"bill/{congress}/{bill_type}/{number}/actions", {"limit": limit})
    if not data:
        return []
    return data.get("actions", [])


def _fetch_bill_cosponsors(congress, bill_type, number, limit=250):
    data = _request(f"bill/{congress}/{bill_type}/{number}/cosponsors", {"limit": limit})
    if not data:
        return []
    return data.get("cosponsors", [])


def _fetch_bill_subjects(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}/subjects", {"limit": 100})
    if not data:
        return []
    return data.get("subjects", {})


def _fetch_bill_summaries(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}/summaries", {"limit": 10})
    if not data:
        return []
    return data.get("summaries", [])


def _fetch_bill_text(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}/text", {"limit": 10})
    if not data:
        return []
    return data.get("textVersions", [])


def _fetch_members(limit=20, offset=0, state=None, chamber=None, congress=None):
    params = {"limit": limit, "offset": offset}
    if congress is None:
        congress = CURRENT_CONGRESS

    endpoint = f"member/congress/{congress}"
    if state:
        endpoint = f"member/congress/{congress}/{state}"

    data = _request(endpoint, params)
    if not data:
        return [], 0
    members = data.get("members", [])
    total = data.get("pagination", {}).get("count", len(members))
    return members, total


def _fetch_nominations(congress=None, limit=20):
    if congress is None:
        congress = CURRENT_CONGRESS
    data = _request(f"nomination/{congress}", {"limit": limit})
    if not data:
        return [], 0
    noms = data.get("nominations", [])
    total = data.get("pagination", {}).get("count", len(noms))
    return noms, total


def _fetch_amendments(congress=None, limit=20):
    if congress is None:
        congress = CURRENT_CONGRESS
    data = _request(f"amendment/{congress}", {"limit": limit})
    if not data:
        return [], 0
    amendments = data.get("amendments", [])
    total = data.get("pagination", {}).get("count", len(amendments))
    return amendments, total


# --- CRS Reports --------------------------------------------------------------

def _fetch_crs_reports(limit=20, offset=0):
    data = _request("crsreport", {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    reports = data.get("CRSReports", [])
    total = data.get("pagination", {}).get("count", len(reports))
    return reports, total


def _fetch_crs_report(report_id):
    data = _request(f"crsreport/{report_id}")
    if not data:
        return None
    return data.get("CRSReport", data)


# --- House Roll Call Votes ----------------------------------------------------

def _fetch_house_votes(congress=None, session=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    endpoint = f"house-vote/{congress}"
    if session is not None:
        endpoint = f"house-vote/{congress}/{session}"
    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    votes = data.get("houseRollCallVotes", [])
    total = data.get("pagination", {}).get("count", len(votes))
    return votes, total


def _fetch_house_vote(congress, session, vote_number):
    data = _request(f"house-vote/{congress}/{session}/{vote_number}")
    if not data:
        return None
    vote = data.get("houseRollCallVote")
    if vote is None:
        votes = data.get("houseRollCallVotes", [])
        vote = votes[0] if votes else data
    return vote


def _fetch_house_vote_members(congress, session, vote_number, limit=500):
    data = _request(
        f"house-vote/{congress}/{session}/{vote_number}/members",
        {"limit": limit},
    )
    if not data:
        return []
    members = data.get("houseRollCallVoteMemberVotes")
    if members is None:
        members = data.get("results", data.get("members", []))
    return members


# --- Laws (Enacted) -----------------------------------------------------------

def _fetch_laws(congress=None, law_type=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    endpoint = f"law/{congress}"
    if law_type:
        endpoint = f"law/{congress}/{law_type}"
    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    laws = data.get("bills", data.get("laws", []))
    total = data.get("pagination", {}).get("count", len(laws))
    return laws, total


def _fetch_law_detail(congress, law_type, law_number):
    data = _request(f"law/{congress}/{law_type}/{law_number}")
    if not data:
        return None
    return data.get("bill", data.get("law", data))


# --- Bill Sub-Endpoints (Extended) --------------------------------------------

def _fetch_bill_related(congress, bill_type, number, limit=50):
    data = _request(
        f"bill/{congress}/{bill_type}/{number}/relatedbills",
        {"limit": limit},
    )
    if not data:
        return []
    return data.get("relatedBills", [])


def _fetch_bill_amendments(congress, bill_type, number, limit=100):
    data = _request(
        f"bill/{congress}/{bill_type}/{number}/amendments",
        {"limit": limit},
    )
    if not data:
        return []
    return data.get("amendments", [])


def _fetch_bill_committees(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}/committees")
    if not data:
        return []
    return data.get("committees", [])


def _fetch_bill_titles(congress, bill_type, number):
    data = _request(f"bill/{congress}/{bill_type}/{number}/titles")
    if not data:
        return []
    return data.get("titles", [])


# --- Member Deep Dive ---------------------------------------------------------

def _fetch_member_detail(bioguide_id):
    data = _request(f"member/{bioguide_id}")
    if not data:
        return None
    return data.get("member", data)


def _fetch_member_sponsored(bioguide_id, limit=50, offset=0):
    data = _request(
        f"member/{bioguide_id}/sponsored-legislation",
        {"limit": limit, "offset": offset},
    )
    if not data:
        return [], 0
    items = data.get("sponsoredLegislation", [])
    total = data.get("pagination", {}).get("count", len(items))
    return items, total


def _fetch_member_cosponsored(bioguide_id, limit=50, offset=0):
    data = _request(
        f"member/{bioguide_id}/cosponsored-legislation",
        {"limit": limit, "offset": offset},
    )
    if not data:
        return [], 0
    items = data.get("cosponsoredLegislation", [])
    total = data.get("pagination", {}).get("count", len(items))
    return items, total


# --- Treaties -----------------------------------------------------------------

def _fetch_treaties(congress=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    data = _request(f"treaty/{congress}", {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    treaties = data.get("treaties", [])
    total = data.get("pagination", {}).get("count", len(treaties))
    return treaties, total


def _fetch_treaty_detail(congress, treaty_number, suffix=None):
    endpoint = f"treaty/{congress}/{treaty_number}"
    if suffix:
        endpoint = f"treaty/{congress}/{treaty_number}/{suffix}"
    data = _request(endpoint)
    if not data:
        return None
    return data.get("treaty", data)


def _fetch_treaty_actions(congress, treaty_number, suffix=None):
    endpoint = f"treaty/{congress}/{treaty_number}/actions"
    if suffix:
        endpoint = f"treaty/{congress}/{treaty_number}/{suffix}/actions"
    data = _request(endpoint)
    if not data:
        return []
    return data.get("actions", [])


# --- Committee Reports & Hearings ---------------------------------------------

def _fetch_committee_reports(congress=None, report_type=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    endpoint = f"committee-report/{congress}"
    if report_type:
        endpoint = f"committee-report/{congress}/{report_type}"
    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    reports = data.get("reports", data.get("committeeReports", []))
    total = data.get("pagination", {}).get("count", len(reports))
    return reports, total


def _fetch_hearings(congress=None, chamber=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    endpoint = f"hearing/{congress}"
    if chamber:
        endpoint = f"hearing/{congress}/{chamber}"
    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    hearings = data.get("hearings", [])
    total = data.get("pagination", {}).get("count", len(hearings))
    return hearings, total


def _fetch_hearing_detail(congress, chamber, jacket_number):
    data = _request(f"hearing/{congress}/{chamber}/{jacket_number}")
    if not data:
        return None
    return data.get("hearing", data)


# --- Nomination Deep Dive -----------------------------------------------------

def _fetch_nomination_detail(congress, number):
    data = _request(f"nomination/{congress}/{number}")
    if not data:
        return None
    return data.get("nomination", data)


def _fetch_nomination_actions(congress, number, limit=50):
    data = _request(
        f"nomination/{congress}/{number}/actions",
        {"limit": limit},
    )
    if not data:
        return []
    return data.get("actions", [])


def _fetch_nomination_hearings(congress, number):
    data = _request(f"nomination/{congress}/{number}/hearings")
    if not data:
        return []
    return data.get("hearings", [])


def _fetch_nomination_committees(congress, number):
    data = _request(f"nomination/{congress}/{number}/committees")
    if not data:
        return []
    return data.get("committees", [])


# --- Summaries Feed -----------------------------------------------------------

def _fetch_summaries_feed(congress=None, bill_type=None, limit=20, offset=0):
    if congress is None:
        congress = CURRENT_CONGRESS
    if bill_type:
        endpoint = f"summaries/{congress}/{bill_type}"
    else:
        endpoint = f"summaries/{congress}"
    data = _request(endpoint, {"limit": limit, "offset": offset})
    if not data:
        return [], 0
    summaries = data.get("summaries", [])
    total = data.get("pagination", {}).get("count", len(summaries))
    return summaries, total


# --- Parsing Helpers ----------------------------------------------------------

def _bill_id(bill):
    """Format bill identifier like 'H.R. 1' or 'S. 25'."""
    btype = bill.get("type", "")
    number = bill.get("number", "")
    type_labels = {
        "HR": "H.R.", "S": "S.", "HJRES": "H.J.Res.", "SJRES": "S.J.Res.",
        "HCONRES": "H.Con.Res.", "SCONRES": "S.Con.Res.",
        "HRES": "H.Res.", "SRES": "S.Res.",
    }
    label = type_labels.get(btype.upper(), btype)
    return f"{label} {number}"


def _bill_title(bill, max_len=60):
    title = bill.get("title", "")
    if not title:
        title = bill.get("shortTitle", "") or bill.get("officialTitle", "")
    return _truncate(title, max_len)


def _latest_action(bill):
    la = bill.get("latestAction", {})
    if not la:
        return "", ""
    return la.get("actionDate", "")[:10], la.get("text", "")


def _truncate(text, length=80):
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    if len(text) <= length:
        return text
    return text[:length - 3] + "..."


def _parse_date(val):
    if not val:
        return ""
    return str(val)[:10]


# --- Display ------------------------------------------------------------------

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


def _display_bill_table(bills, title="Bills", show_action=True):
    if not bills:
        print("  No bills found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)

    if show_action:
        print(f"  {'Bill':<14} {'Congress':>8} {'Last Action':<12} {'Title'}")
        print(f"  {'-'*14} {'-'*8} {'-'*12} {'-'*55}")
    else:
        print(f"  {'Bill':<14} {'Congress':>8} {'Title'}")
        print(f"  {'-'*14} {'-'*8} {'-'*65}")

    for bill in bills:
        bid = _bill_id(bill)
        congress = bill.get("congress", "")
        title_text = _bill_title(bill, 55)

        if show_action:
            action_date, action_text = _latest_action(bill)
            print(f"  {bid:<14} {congress:>8} {action_date:<12} {title_text}")
        else:
            print(f"  {bid:<14} {congress:>8} {title_text}")

    print()


def _display_bill_detail(bill):
    if not bill:
        print("  Bill not found.")
        return

    print(f"\n  {'=' * 80}")
    bid = _bill_id(bill)
    congress = bill.get("congress", "")
    print(f"  BILL: {bid} ({congress}th Congress)")
    print(f"  {'=' * 80}")

    title = bill.get("title", "N/A")
    for i in range(0, len(title), 75):
        if i == 0:
            print(f"  Title:       {title[i:i+75]}")
        else:
            print(f"               {title[i:i+75]}")

    print(f"  Type:        {bill.get('type', 'N/A')}")
    print(f"  Introduced:  {_parse_date(bill.get('introducedDate', ''))}")

    if bill.get("sponsors"):
        sponsors = bill["sponsors"]
        if isinstance(sponsors, list):
            for sp in sponsors[:3]:
                name = sp.get("fullName", sp.get("firstName", "") + " " + sp.get("lastName", ""))
                party = sp.get("party", "")
                state = sp.get("state", "")
                print(f"  Sponsor:     {name} ({party}-{state})")
        elif isinstance(sponsors, dict):
            sp = sponsors
            name = sp.get("fullName", sp.get("firstName", "") + " " + sp.get("lastName", ""))
            party = sp.get("party", "")
            state = sp.get("state", "")
            print(f"  Sponsor:     {name} ({party}-{state})")

    if bill.get("originChamber"):
        print(f"  Origin:      {bill['originChamber']}")

    if bill.get("policyArea"):
        pa = bill["policyArea"]
        if isinstance(pa, dict):
            print(f"  Policy Area: {pa.get('name', 'N/A')}")
        else:
            print(f"  Policy Area: {pa}")

    if bill.get("cosponsors"):
        cosponsor_count = bill["cosponsors"]
        if isinstance(cosponsor_count, dict):
            count = cosponsor_count.get("count", 0)
            print(f"  Cosponsors:  {count}")
        else:
            print(f"  Cosponsors:  {cosponsor_count}")

    la = bill.get("latestAction", {})
    if la:
        print(f"\n  Latest Action ({_parse_date(la.get('actionDate', ''))}):")
        action_text = la.get("text", "")
        for i in range(0, len(action_text), 75):
            print(f"    {action_text[i:i+75]}")

    if bill.get("laws"):
        laws = bill["laws"]
        if isinstance(laws, list) and laws:
            for law in laws:
                ltype = law.get("type", "")
                lnum = law.get("number", "")
                print(f"\n  *** ENACTED: {ltype} {lnum} ***")

    if bill.get("cboCostEstimates"):
        estimates = bill["cboCostEstimates"]
        if isinstance(estimates, list) and estimates:
            print(f"\n  CBO Cost Estimates:")
            for est in estimates[:3]:
                print(f"    - {est.get('title', 'N/A')} ({_parse_date(est.get('pubDate', ''))})")
                if est.get("url"):
                    print(f"      {est['url']}")

    url = bill.get("url", "")
    if not url:
        btype = bill.get("type", "").lower()
        num = bill.get("number", "")
        url = f"https://www.congress.gov/bill/{congress}th-congress/{_chamber_slug(btype)}/{num}"
    print(f"\n  URL:         {url}")
    print(f"  {'=' * 80}\n")


def _chamber_slug(bill_type):
    bt = bill_type.upper()
    if bt.startswith("H"):
        return "house-bill"
    if bt.startswith("S"):
        return "senate-bill"
    return bill_type


def _display_actions(actions, bill_label=""):
    if not actions:
        print("  No actions found.")
        return

    title = f"Actions for {bill_label}" if bill_label else "Bill Actions"
    print(f"\n  {title}")
    print("  " + "=" * 80)
    print(f"  {'Date':<12} {'Chamber':<10} {'Action'}")
    print(f"  {'-'*12} {'-'*10} {'-'*55}")

    for action in actions:
        date = _parse_date(action.get("actionDate", ""))
        chamber = action.get("actionCode", "")[:10] if action.get("actionCode") else ""
        atype = action.get("type", "")[:10]
        text = _truncate(action.get("text", ""), 55)
        print(f"  {date:<12} {atype:<10} {text}")

    print()


def _display_nominations(noms, title="Presidential Nominations"):
    if not noms:
        print("  No nominations found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 80)
    print(f"  {'Received':<12} {'#':<10} {'Description'}")
    print(f"  {'-'*12} {'-'*10} {'-'*55}")

    for nom in noms:
        date = _parse_date(nom.get("receivedDate", nom.get("latestAction", {}).get("actionDate", "")))
        num = nom.get("number", "")
        desc = _truncate(nom.get("description", ""), 55)
        la = nom.get("latestAction", {})
        la_text = _truncate(la.get("text", ""), 50)

        print(f"  {date:<12} PN{num:<8} {desc}")
        if la_text:
            print(f"  {'':12} {'':10} -> {la_text}")

    print()


def _display_members(members, title="Members of Congress"):
    if not members:
        print("  No members found.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 80)
    print(f"  {'Name':<30} {'Party':<5} {'State':<6} {'Chamber':<10} {'District'}")
    print(f"  {'-'*30} {'-'*5} {'-'*6} {'-'*10} {'-'*10}")

    for m in members:
        name = m.get("name", "")
        if not name:
            name = f"{m.get('firstName', '')} {m.get('lastName', '')}"
        party = m.get("partyName", m.get("party", ""))[:3]
        state = m.get("state", "")
        terms = m.get("terms", {})
        if isinstance(terms, dict):
            items = terms.get("item", [])
        elif isinstance(terms, list):
            items = terms
        else:
            items = []
        chamber = ""
        district = ""
        if items:
            latest = items[0] if isinstance(items, list) else items
            if isinstance(latest, dict):
                chamber = latest.get("chamber", "")
                district = str(latest.get("district", ""))

        print(f"  {_truncate(name, 30):<30} {party:<5} {state:<6} {chamber:<10} {district}")

    print()


def _display_tracker(results, title="Macro Legislative Tracker"):
    if not results:
        print("  No results.")
        return

    print(f"\n  {title}")
    print("  " + "=" * 95)

    for topic_key, data in results.items():
        topic = MACRO_TOPICS.get(topic_key, {})
        label = topic.get("label", topic_key)
        bills = data.get("bills", [])
        total = data.get("total", 0)

        if not bills:
            print(f"\n  {label.upper()}: (no bills found)")
            continue

        print(f"\n  {label.upper()} ({total} bills)")
        print(f"  {'Bill':<14} {'Last Action':<12} {'Title'}")
        print(f"  {'-'*14} {'-'*12} {'-'*60}")

        for bill in bills[:5]:
            bid = _bill_id(bill)
            action_date, _ = _latest_action(bill)
            title_text = _bill_title(bill, 60)
            print(f"  {bid:<14} {action_date:<12} {title_text}")

        if total > 5:
            print(f"    ... and {total - 5} more")

    print()


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


def _flatten_bill(bill):
    action_date, action_text = _latest_action(bill)
    return {
        "bill_id": _bill_id(bill),
        "congress": bill.get("congress", ""),
        "type": bill.get("type", ""),
        "number": bill.get("number", ""),
        "title": bill.get("title", ""),
        "introduced_date": _parse_date(bill.get("introducedDate", "")),
        "last_action_date": action_date,
        "last_action_text": _truncate(action_text, 200),
        "url": bill.get("url", ""),
    }


def _flatten_bills(bills):
    return [_flatten_bill(b) for b in bills]


# --- Command Functions --------------------------------------------------------

def cmd_latest(congress=None, bill_type=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS

    label = f"{congress}th Congress"
    if bill_type:
        label += f" ({BILL_TYPES.get(bill_type, bill_type)})"

    print(f"\n  Fetching latest bills -- {label}...")
    bills, total = _fetch_bills(congress=congress, bill_type=bill_type, limit=limit)

    if as_json:
        print(json.dumps(bills, indent=2, default=str))
        return bills

    _display_bill_table(bills, f"Latest Bills -- {label} ({total:,} total)")

    if export_fmt:
        _do_export(_flatten_bills(bills), "congress_latest", export_fmt)
    return bills


def cmd_bill(congress, bill_type, number, as_json=False):
    print(f"\n  Fetching {bill_type.upper()} {number} from {congress}th Congress...")
    bill = _fetch_bill_detail(congress, bill_type, number)

    if not bill:
        print("  Bill not found.")
        return

    if as_json:
        print(json.dumps(bill, indent=2, default=str))
        return bill

    _display_bill_detail(bill)
    return bill


def cmd_actions(congress, bill_type, number, limit=50, as_json=False, export_fmt=None):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching actions for {bid} ({congress}th Congress)...")
    actions = _fetch_bill_actions(congress, bill_type, number, limit=limit)

    if as_json:
        print(json.dumps(actions, indent=2, default=str))
        return actions

    _display_actions(actions, bid)

    if export_fmt:
        _do_export(actions, f"congress_actions_{bill_type}_{number}", export_fmt)
    return actions


def cmd_cosponsors(congress, bill_type, number, as_json=False):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching cosponsors for {bid} ({congress}th Congress)...")
    cosponsors = _fetch_bill_cosponsors(congress, bill_type, number)

    if not cosponsors:
        print("  No cosponsors found.")
        return

    if as_json:
        print(json.dumps(cosponsors, indent=2, default=str))
        return cosponsors

    print(f"\n  Cosponsors for {bid} ({len(cosponsors)} total)")
    print("  " + "=" * 60)
    print(f"  {'Name':<30} {'Party':<5} {'State':<6} {'Sponsored'}")
    print(f"  {'-'*30} {'-'*5} {'-'*6} {'-'*12}")

    for c in cosponsors:
        name = c.get("fullName", f"{c.get('firstName', '')} {c.get('lastName', '')}")
        party = c.get("party", "")
        state = c.get("state", "")
        date = _parse_date(c.get("sponsorshipDate", ""))
        print(f"  {_truncate(name, 30):<30} {party:<5} {state:<6} {date}")

    print()
    return cosponsors


def cmd_summaries(congress, bill_type, number, as_json=False):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching summaries for {bid} ({congress}th Congress)...")
    summaries = _fetch_bill_summaries(congress, bill_type, number)

    if not summaries:
        print("  No summaries available.")
        return

    if as_json:
        print(json.dumps(summaries, indent=2, default=str))
        return summaries

    print(f"\n  Summaries for {bid}")
    print("  " + "=" * 80)

    for s in summaries:
        vname = s.get("versionCode", "")
        date = _parse_date(s.get("updateDate", s.get("actionDate", "")))
        text = s.get("text", "")
        # Strip HTML tags for display
        import re
        clean = re.sub(r"<[^>]+>", "", text)
        clean = clean.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

        print(f"\n  Version: {vname} ({date})")
        print(f"  {'-' * 75}")
        for i in range(0, min(len(clean), 500), 80):
            print(f"  {clean[i:i+80]}")
        if len(clean) > 500:
            print(f"  ... ({len(clean) - 500} chars truncated)")

    print()
    return summaries


def cmd_search(term=None, congress=None, limit=20, as_json=False, export_fmt=None):
    """Search bills. Congress.gov API doesn't have a direct search endpoint,
    so we use the bill listing and filter client-side, or search by subject."""
    if not term:
        term = _prompt("Search term")
    if not term:
        return

    if congress is None:
        congress = CURRENT_CONGRESS

    print(f"\n  Searching bills in {congress}th Congress for '{term}'...")

    # The Congress API doesn't have full-text search on bills directly.
    # We fetch recent bills and do client-side filtering, plus check subjects.
    # For better results, we search across both house and senate bills.
    all_matches = []
    term_lower = term.lower()

    for btype in ["hr", "s", "hjres", "sjres"]:
        print(f"  Scanning {BILL_TYPES.get(btype, btype)}...")
        bills, _ = _fetch_bills(congress=congress, bill_type=btype, limit=250)
        matches = [b for b in bills if term_lower in (b.get("title", "") or "").lower()]
        all_matches.extend(matches)
        time.sleep(0.2)

    all_matches.sort(key=lambda b: b.get("latestAction", {}).get("actionDate", ""), reverse=True)

    if as_json:
        print(json.dumps(all_matches[:limit], indent=2, default=str))
        return all_matches[:limit]

    _display_bill_table(all_matches[:limit],
                        f"Search: '{term}' ({len(all_matches)} matches in {congress}th Congress)")

    if export_fmt:
        _do_export(_flatten_bills(all_matches[:limit]),
                   f"congress_search_{term[:20]}", export_fmt)
    return all_matches[:limit]


def cmd_members(state=None, congress=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS

    label = f"{congress}th Congress"
    if state:
        label += f", {state}"

    print(f"\n  Fetching members -- {label}...")
    members, total = _fetch_members(limit=limit, state=state, congress=congress)

    if as_json:
        print(json.dumps(members, indent=2, default=str))
        return members

    _display_members(members, f"Members -- {label} ({total:,} total)")

    if export_fmt:
        _do_export(members, "congress_members", export_fmt)
    return members


def cmd_nominations(congress=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS

    print(f"\n  Fetching nominations ({congress}th Congress)...")
    noms, total = _fetch_nominations(congress=congress, limit=limit)

    if as_json:
        print(json.dumps(noms, indent=2, default=str))
        return noms

    _display_nominations(noms, f"Nominations -- {congress}th Congress ({total:,} total)")

    if export_fmt:
        _do_export(noms, "congress_nominations", export_fmt)
    return noms


def cmd_amendments(congress=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS

    print(f"\n  Fetching amendments ({congress}th Congress)...")
    amendments, total = _fetch_amendments(congress=congress, limit=limit)

    if as_json:
        print(json.dumps(amendments, indent=2, default=str))
        return amendments

    print(f"\n  Amendments -- {congress}th Congress ({total:,} total)")
    print("  " + "=" * 80)
    print(f"  {'Number':<14} {'Type':<10} {'Date':<12} {'Description'}")
    print(f"  {'-'*14} {'-'*10} {'-'*12} {'-'*40}")

    for a in amendments:
        num = a.get("number", "")
        atype = a.get("type", "")
        date = _parse_date(a.get("latestAction", {}).get("actionDate", ""))
        desc = _truncate(a.get("description", a.get("purpose", "")), 40)
        la = a.get("latestAction", {})
        print(f"  {num:<14} {atype:<10} {date:<12} {desc}")

    print()

    if export_fmt:
        _do_export(amendments, "congress_amendments", export_fmt)
    return amendments


def cmd_tracker(congress=None, topics=None, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    if topics is None:
        topics = list(MACRO_TOPICS.keys())

    total_topics = len(topics)
    results = {}

    print(f"\n  Tracking {total_topics} macro topics in {congress}th Congress...")

    for idx, topic_key in enumerate(topics):
        topic = MACRO_TOPICS.get(topic_key)
        if not topic:
            continue

        print(f"  [{idx + 1}/{total_topics}] {topic['label']}...")
        terms = topic["terms"]

        topic_bills = []
        for btype in ["hr", "s", "hjres", "sjres"]:
            bills, _ = _fetch_bills(congress=congress, bill_type=btype, limit=250)
            for bill in bills:
                title = (bill.get("title", "") or "").lower()
                if any(t.lower() in title for t in terms):
                    topic_bills.append(bill)
            time.sleep(0.15)

        topic_bills.sort(key=lambda b: b.get("latestAction", {}).get("actionDate", ""), reverse=True)

        # Dedup by bill number
        seen = set()
        deduped = []
        for b in topic_bills:
            key = f"{b.get('type', '')}-{b.get('number', '')}"
            if key not in seen:
                seen.add(key)
                deduped.append(b)

        results[topic_key] = {"bills": deduped, "total": len(deduped)}

    if as_json:
        out = {}
        for k, v in results.items():
            out[k] = {"label": MACRO_TOPICS[k]["label"],
                       "count": v["total"], "bills": v["bills"]}
        print(json.dumps(out, indent=2, default=str))
        return out

    _display_tracker(results, f"Macro Legislative Tracker ({congress}th Congress)")

    if export_fmt:
        flat = []
        for k, v in results.items():
            for bill in v["bills"]:
                row = _flatten_bill(bill)
                row["_topic"] = k
                flat.append(row)
        _do_export(flat, "congress_tracker", export_fmt)
    return results


def cmd_topics(as_json=False):
    print("\n  Curated Macro Topics for Legislative Tracking")
    print("  " + "=" * 70)

    for key, topic in MACRO_TOPICS.items():
        print(f"\n  {key}")
        print(f"    Label: {topic['label']}")
        print(f"    Terms: {', '.join(topic['terms'][:5])}")

    print(f"\n  Total: {len(MACRO_TOPICS)} topics")
    print(f"  Usage: python congress.py tracker --topics debt_ceiling,tariff,sanctions\n")


# --- Extended Commands: CRS Reports ------------------------------------------

def cmd_crs(limit=20, as_json=False, export_fmt=None):
    print(f"\n  Fetching latest CRS reports (limit {limit})...")
    reports, total = _fetch_crs_reports(limit=limit)

    if as_json:
        print(json.dumps(reports, indent=2, default=str))
        return reports

    if not reports:
        print("  No CRS reports found.")
        return reports

    print(f"\n  CRS REPORTS ({total:,} total available)")
    print("  " + "=" * 95)
    print(f"  {'ID':<10} {'Type':<12} {'Published':<12} {'Title'}")
    print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*55}")
    for r in reports:
        rid = r.get("id", "")
        ctype = r.get("contentType", "")[:12]
        pub = _parse_date(r.get("publishDate", ""))
        title = _truncate(r.get("title", ""), 55)
        print(f"  {rid:<10} {ctype:<12} {pub:<12} {title}")
    print()

    if export_fmt:
        flat = [{
            "id": r.get("id", ""),
            "title": r.get("title", ""),
            "contentType": r.get("contentType", ""),
            "publishDate": _parse_date(r.get("publishDate", "")),
            "status": r.get("status", ""),
            "version": r.get("version", ""),
            "url": r.get("url", ""),
        } for r in reports]
        _do_export(flat, "congress_crs", export_fmt)
    return reports


def cmd_crs_report(report_id, as_json=False):
    print(f"\n  Fetching CRS report {report_id}...")
    report = _fetch_crs_report(report_id)

    if not report:
        print("  Report not found.")
        return None

    if as_json:
        print(json.dumps(report, indent=2, default=str))
        return report

    print(f"\n  {'=' * 80}")
    print(f"  CRS REPORT: {report.get('id', report_id)}")
    print(f"  {'=' * 80}")
    title = report.get("title", "")
    for i in range(0, len(title), 75):
        if i == 0:
            print(f"  Title:        {title[i:i+75]}")
        else:
            print(f"                {title[i:i+75]}")
    print(f"  Content type: {report.get('contentType', 'N/A')}")
    print(f"  Published:    {_parse_date(report.get('publishDate', ''))}")
    print(f"  Updated:      {_parse_date(report.get('updateDate', ''))}")
    print(f"  Version:      {report.get('version', 'N/A')}")
    print(f"  Status:       {report.get('status', 'N/A')}")

    authors = report.get("authors", [])
    if authors:
        names = [a.get("author", a.get("name", "?")) if isinstance(a, dict) else str(a)
                 for a in authors[:5]]
        print(f"  Authors:      {', '.join(names)}")

    topics = report.get("topics", [])
    if topics:
        topic_names = [t.get("name", t.get("topic", "?")) if isinstance(t, dict) else str(t)
                       for t in topics[:8]]
        print(f"  Topics:       {', '.join(topic_names)}")

    summary = report.get("summary", "")
    if summary:
        import re
        clean = re.sub(r"<[^>]+>", "", summary)
        print(f"\n  Summary:")
        for i in range(0, min(len(clean), 600), 80):
            print(f"    {clean[i:i+80]}")
        if len(clean) > 600:
            print(f"    ... ({len(clean) - 600} chars truncated)")

    versions = report.get("versions", [])
    if versions:
        print(f"\n  Versions: {len(versions)} available")

    formats = report.get("formats", [])
    if formats:
        print(f"\n  Formats:")
        for f in formats[:3]:
            if isinstance(f, dict):
                print(f"    - {f.get('format', '?')}: {f.get('url', '?')}")

    url = report.get("url", "")
    if url:
        print(f"\n  URL:          {url}")
    print(f"  {'=' * 80}\n")
    return report


# --- Extended Commands: House Roll Call Votes --------------------------------

def cmd_votes(congress=None, session=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    label = f"{congress}th Congress"
    if session is not None:
        label += f", session {session}"

    print(f"\n  Fetching House roll call votes -- {label}...")
    votes, total = _fetch_house_votes(congress=congress, session=session, limit=limit)

    if as_json:
        print(json.dumps(votes, indent=2, default=str))
        return votes

    if not votes:
        print("  No votes found.")
        return votes

    print(f"\n  HOUSE ROLL CALL VOTES -- {label} ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Roll':>5} {'Session':>7} {'Date':<12} {'Result':<14} {'Bill':<12} {'Type'}")
    print(f"  {'-'*5} {'-'*7} {'-'*12} {'-'*14} {'-'*12} {'-'*30}")
    for v in votes:
        roll = v.get("rollCallNumber", "")
        sess = v.get("sessionNumber", "")
        date = _parse_date(v.get("startDate", ""))
        result = _truncate(v.get("result", ""), 14)
        leg_type = v.get("legislationType", "")
        leg_num = v.get("legislationNumber", "")
        bill = f"{leg_type} {leg_num}" if leg_type else ""
        vtype = _truncate(v.get("voteType", ""), 30)
        print(f"  {roll:>5} {sess:>7} {date:<12} {result:<14} {bill:<12} {vtype}")
    print()

    if export_fmt:
        flat = [{
            "congress": v.get("congress", ""),
            "session": v.get("sessionNumber", ""),
            "rollCallNumber": v.get("rollCallNumber", ""),
            "startDate": _parse_date(v.get("startDate", "")),
            "result": v.get("result", ""),
            "voteType": v.get("voteType", ""),
            "legislationType": v.get("legislationType", ""),
            "legislationNumber": v.get("legislationNumber", ""),
            "url": v.get("url", ""),
            "sourceDataURL": v.get("sourceDataURL", ""),
        } for v in votes]
        _do_export(flat, f"congress_votes_{congress}", export_fmt)
    return votes


def cmd_vote(congress, session, vote_number, as_json=False):
    print(f"\n  Fetching House vote detail: {congress}-{session}-{vote_number}...")
    vote = _fetch_house_vote(congress, session, vote_number)

    if not vote:
        print("  Vote not found.")
        return None

    if as_json:
        print(json.dumps(vote, indent=2, default=str))
        return vote

    print(f"\n  {'=' * 80}")
    print(f"  ROLL CALL: {congress}-{session}-{vote_number}")
    print(f"  {'=' * 80}")
    print(f"  Date:         {_parse_date(vote.get('startDate', ''))}")
    print(f"  Vote type:    {vote.get('voteType', 'N/A')}")
    print(f"  Result:       {vote.get('result', 'N/A')}")

    leg = f"{vote.get('legislationType', '')} {vote.get('legislationNumber', '')}"
    if leg.strip():
        print(f"  Bill:         {leg}")
    if vote.get("legislationUrl"):
        print(f"  Bill URL:     {vote['legislationUrl']}")

    if vote.get("amendmentNumber"):
        print(f"  Amendment:    {vote.get('amendmentType', '')} {vote['amendmentNumber']}")

    question = vote.get("question", "") or vote.get("voteQuestion", "")
    if question:
        print(f"  Question:     {_truncate(question, 70)}")

    tally = vote.get("tally") or vote.get("results")
    if isinstance(tally, dict):
        yea = tally.get("yeas") or tally.get("yea") or tally.get("Yea", "")
        nay = tally.get("nays") or tally.get("nay") or tally.get("Nay", "")
        pres = tally.get("present") or tally.get("Present", "")
        nv = tally.get("notVoting") or tally.get("NotVoting", "")
        if yea or nay:
            print(f"  Tally:        {yea} Yea  |  {nay} Nay  |  {pres} Pres  |  {nv} NV")

    if vote.get("sourceDataURL"):
        print(f"  Clerk XML:    {vote['sourceDataURL']}")
    if vote.get("url"):
        print(f"  API URL:      {vote['url']}")
    print(f"  {'=' * 80}\n")
    return vote


def cmd_vote_members(congress, session, vote_number, as_json=False, export_fmt=None):
    print(f"\n  Fetching member votes for {congress}-{session}-{vote_number}...")
    members = _fetch_house_vote_members(congress, session, vote_number)

    if as_json:
        print(json.dumps(members, indent=2, default=str))
        return members

    if not members:
        print("  No member votes found.")
        return []

    tallies = {}
    for m in members:
        pos = (m.get("voteCast") or m.get("vote") or m.get("position") or "").strip()
        tallies[pos] = tallies.get(pos, 0) + 1

    print(f"\n  MEMBER VOTES: {congress}-{session}-{vote_number} ({len(members)} members)")
    print("  " + "=" * 60)
    for k, v in sorted(tallies.items(), key=lambda kv: -kv[1]):
        if k:
            print(f"  {k:<20} {v:>5}")

    by_pos = {}
    for m in members:
        pos = (m.get("voteCast") or m.get("vote") or m.get("position") or "").strip()
        by_pos.setdefault(pos, []).append(m)

    for pos in ("Yea", "Nay", "Present", "Not Voting"):
        group = by_pos.get(pos, [])
        if not group:
            continue
        by_party = {}
        for m in group:
            p = m.get("voteParty") or m.get("party") or "?"
            by_party[p] = by_party.get(p, 0) + 1
        parts = ", ".join(f"{k}:{v}" for k, v in sorted(by_party.items(), key=lambda kv: -kv[1]))
        print(f"  {pos:<20} party breakdown: {parts}")

    print()

    if export_fmt:
        flat = []
        for m in members:
            flat.append({
                "bioguideID": m.get("bioguideID", ""),
                "firstName": m.get("firstName", ""),
                "lastName": m.get("lastName", ""),
                "voteParty": m.get("voteParty", m.get("party", "")),
                "voteState": m.get("voteState", m.get("state", "")),
                "voteCast": m.get("voteCast", m.get("vote", "")),
            })
        _do_export(flat, f"congress_vote_members_{congress}_{session}_{vote_number}",
                   export_fmt)
    return members


# --- Extended Commands: Laws (Enacted) ---------------------------------------

LAW_TYPES = {
    "pub":  "Public Law",
    "priv": "Private Law",
}


def cmd_laws(congress=None, law_type=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    label = f"{congress}th Congress"
    if law_type:
        label += f" ({LAW_TYPES.get(law_type, law_type)})"

    print(f"\n  Fetching enacted laws -- {label}...")
    laws, total = _fetch_laws(congress=congress, law_type=law_type, limit=limit)

    if as_json:
        print(json.dumps(laws, indent=2, default=str))
        return laws

    if not laws:
        print("  No laws found.")
        return laws

    print(f"\n  ENACTED LAWS -- {label} ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Law #':<12} {'Vehicle':<14} {'Enacted':<12} {'Title'}")
    print(f"  {'-'*12} {'-'*14} {'-'*12} {'-'*55}")
    for b in laws:
        law_list = b.get("laws", [])
        law_num = ""
        if isinstance(law_list, list) and law_list:
            law_num = law_list[0].get("number", "")
        bid = _bill_id(b)
        la = b.get("latestAction", {})
        date = _parse_date(la.get("actionDate", ""))
        title = _bill_title(b, 55)
        print(f"  {law_num:<12} {bid:<14} {date:<12} {title}")
    print()

    if export_fmt:
        rows = []
        for b in laws:
            law_list = b.get("laws", [])
            law_num = law_list[0].get("number", "") if isinstance(law_list, list) and law_list else ""
            row = _flatten_bill(b)
            row["law_number"] = law_num
            rows.append(row)
        _do_export(rows, f"congress_laws_{congress}", export_fmt)
    return laws


def cmd_law(congress, law_type, law_number, as_json=False):
    print(f"\n  Fetching law {law_type.upper()} {congress}-{law_number}...")
    law = _fetch_law_detail(congress, law_type, law_number)
    if not law:
        print("  Law not found.")
        return None
    if as_json:
        print(json.dumps(law, indent=2, default=str))
        return law
    _display_bill_detail(law)
    return law


# --- Extended Commands: Bill Sub-Endpoints -----------------------------------

def cmd_related(congress, bill_type, number, as_json=False, export_fmt=None):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching related bills for {bid} ({congress}th Congress)...")
    related = _fetch_bill_related(congress, bill_type, number)

    if as_json:
        print(json.dumps(related, indent=2, default=str))
        return related

    if not related:
        print("  No related bills found.")
        return []

    print(f"\n  RELATED BILLS for {bid} ({len(related)} bills)")
    print("  " + "=" * 95)
    print(f"  {'Bill':<14} {'Congress':>8} {'Relationship':<25} {'Title'}")
    print(f"  {'-'*14} {'-'*8} {'-'*25} {'-'*45}")
    for r in related:
        rel_bid = _bill_id(r)
        rel_cong = r.get("congress", "")
        rel_types = r.get("relationshipDetails", [])
        if isinstance(rel_types, list) and rel_types:
            rel_str = _truncate(rel_types[0].get("type", ""), 25)
        else:
            rel_str = ""
        title = _bill_title(r, 45)
        print(f"  {rel_bid:<14} {rel_cong:>8} {rel_str:<25} {title}")
    print()

    if export_fmt:
        flat = []
        for r in related:
            row = _flatten_bill(r)
            rel_types = r.get("relationshipDetails", [])
            if isinstance(rel_types, list) and rel_types:
                row["relationship"] = rel_types[0].get("type", "")
                row["identified_by"] = rel_types[0].get("identifiedBy", "")
            flat.append(row)
        _do_export(flat, f"congress_related_{bill_type}_{number}", export_fmt)
    return related


def cmd_bill_amendments(congress, bill_type, number, as_json=False, export_fmt=None):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching amendments for {bid} ({congress}th Congress)...")
    amendments = _fetch_bill_amendments(congress, bill_type, number)

    if as_json:
        print(json.dumps(amendments, indent=2, default=str))
        return amendments

    if not amendments:
        print("  No amendments found.")
        return []

    print(f"\n  AMENDMENTS to {bid} ({len(amendments)} amendments)")
    print("  " + "=" * 95)
    print(f"  {'Number':<14} {'Type':<10} {'Latest Action Date':<18} {'Purpose'}")
    print(f"  {'-'*14} {'-'*10} {'-'*18} {'-'*40}")
    for a in amendments:
        num = f"{a.get('type','')}-{a.get('number','')}"
        atype = a.get("type", "")
        la = a.get("latestAction", {})
        date = _parse_date(la.get("actionDate", ""))
        purp = _truncate(a.get("purpose", a.get("description", "")), 40)
        print(f"  {num:<14} {atype:<10} {date:<18} {purp}")
    print()

    if export_fmt:
        _do_export(amendments, f"congress_bill_amendments_{bill_type}_{number}",
                   export_fmt)
    return amendments


def cmd_bill_committees(congress, bill_type, number, as_json=False):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching committees for {bid} ({congress}th Congress)...")
    committees = _fetch_bill_committees(congress, bill_type, number)

    if as_json:
        print(json.dumps(committees, indent=2, default=str))
        return committees

    if not committees:
        print("  No committees found.")
        return []

    print(f"\n  COMMITTEES for {bid} ({len(committees)} committees)")
    print("  " + "=" * 95)
    for c in committees:
        name = c.get("name", "")
        chamber = c.get("chamber", "")
        ccode = c.get("systemCode", "")
        print(f"\n  {name} [{chamber} / {ccode}]")
        activities = c.get("activities", [])
        if activities:
            for act in activities[:5]:
                date = _parse_date(act.get("date", ""))
                atype = act.get("name", "")
                print(f"    {date} - {atype}")
    print()
    return committees


def cmd_titles(congress, bill_type, number, as_json=False):
    bid = f"{bill_type.upper()} {number}"
    print(f"\n  Fetching titles for {bid} ({congress}th Congress)...")
    titles = _fetch_bill_titles(congress, bill_type, number)

    if as_json:
        print(json.dumps(titles, indent=2, default=str))
        return titles

    if not titles:
        print("  No titles found.")
        return []

    print(f"\n  TITLES for {bid} ({len(titles)} titles)")
    print("  " + "=" * 95)
    print(f"  {'Type':<25} {'Chamber':<10} {'Title'}")
    print(f"  {'-'*25} {'-'*10} {'-'*55}")
    for t in titles:
        ttype = _truncate(t.get("titleType", ""), 25)
        chamber = t.get("chamberName", "")[:10]
        text = _truncate(t.get("title", ""), 55)
        print(f"  {ttype:<25} {chamber:<10} {text}")
    print()
    return titles


# --- Extended Commands: Member Deep Dive --------------------------------------

def cmd_member(bioguide_id, as_json=False):
    print(f"\n  Fetching member detail for {bioguide_id}...")
    member = _fetch_member_detail(bioguide_id)

    if not member:
        print("  Member not found.")
        return None

    if as_json:
        print(json.dumps(member, indent=2, default=str))
        return member

    print(f"\n  {'=' * 80}")
    name = member.get("directOrderName", member.get("name", "N/A"))
    print(f"  MEMBER: {name} ({member.get('bioguideId', bioguide_id)})")
    print(f"  {'=' * 80}")

    party = member.get("partyName", member.get("party", ""))
    state = member.get("state", "")
    print(f"  Party / State: {party} / {state}")

    birth = member.get("birthYear", "")
    if birth:
        print(f"  Born:          {birth}")

    terms = member.get("terms", {})
    items = []
    if isinstance(terms, dict):
        items = terms.get("item", [])
    elif isinstance(terms, list):
        items = terms
    if items:
        print(f"\n  Terms: {len(items)} total")
        for t in items[:6]:
            if isinstance(t, dict):
                ch = t.get("chamber", "")
                tc = t.get("congress", "")
                ts = t.get("startYear", "")
                te = t.get("endYear", "")
                dist = t.get("district", "")
                dstr = f"-{dist}" if dist not in ("", None) else ""
                print(f"    {ch:<10} {tc}th  {ts}-{te}  {state}{dstr}")

    leadership = member.get("leadership", [])
    if leadership:
        print(f"\n  Leadership roles:")
        for L in leadership[:6]:
            if isinstance(L, dict):
                print(f"    {L.get('congress','')}: {L.get('type','')}")

    sponsored = member.get("sponsoredLegislation", {})
    if isinstance(sponsored, dict) and sponsored.get("count"):
        print(f"\n  Sponsored legislation: {sponsored.get('count', 0):,}")
    cosponsored = member.get("cosponsoredLegislation", {})
    if isinstance(cosponsored, dict) and cosponsored.get("count"):
        print(f"  Cosponsored legislation: {cosponsored.get('count', 0):,}")

    addr = member.get("addressInformation", {})
    if isinstance(addr, dict):
        office = addr.get("officeAddress", "")
        if office:
            print(f"\n  Office:        {office}")

    url = member.get("url", "")
    if url:
        print(f"  URL:           {url}")
    print(f"  {'=' * 80}\n")
    return member


def cmd_sponsored(bioguide_id, limit=50, as_json=False, export_fmt=None):
    print(f"\n  Fetching sponsored legislation for {bioguide_id} (limit {limit})...")
    items, total = _fetch_member_sponsored(bioguide_id, limit=limit)

    if as_json:
        print(json.dumps(items, indent=2, default=str))
        return items

    if not items:
        print("  No sponsored legislation found.")
        return []

    print(f"\n  SPONSORED LEGISLATION -- {bioguide_id} ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Bill':<14} {'Congress':>8} {'Date':<12} {'Title'}")
    print(f"  {'-'*14} {'-'*8} {'-'*12} {'-'*55}")
    for b in items:
        bid = _bill_id(b)
        cong = b.get("congress", "")
        date = _parse_date(b.get("introducedDate", ""))
        title = _bill_title(b, 55)
        print(f"  {bid:<14} {cong:>8} {date:<12} {title}")
    print()

    if export_fmt:
        _do_export(_flatten_bills(items), f"congress_sponsored_{bioguide_id}",
                   export_fmt)
    return items


def cmd_cosponsored(bioguide_id, limit=50, as_json=False, export_fmt=None):
    print(f"\n  Fetching cosponsored legislation for {bioguide_id} (limit {limit})...")
    items, total = _fetch_member_cosponsored(bioguide_id, limit=limit)

    if as_json:
        print(json.dumps(items, indent=2, default=str))
        return items

    if not items:
        print("  No cosponsored legislation found.")
        return []

    print(f"\n  COSPONSORED LEGISLATION -- {bioguide_id} ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Bill':<14} {'Congress':>8} {'Date':<12} {'Title'}")
    print(f"  {'-'*14} {'-'*8} {'-'*12} {'-'*55}")
    for b in items:
        bid = _bill_id(b)
        cong = b.get("congress", "")
        date = _parse_date(b.get("introducedDate", b.get("sponsorshipDate", "")))
        title = _bill_title(b, 55)
        print(f"  {bid:<14} {cong:>8} {date:<12} {title}")
    print()

    if export_fmt:
        _do_export(_flatten_bills(items),
                   f"congress_cosponsored_{bioguide_id}", export_fmt)
    return items


# --- Extended Commands: Treaties ---------------------------------------------

def cmd_treaties(congress=None, limit=20, as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS

    print(f"\n  Fetching treaties ({congress}th Congress)...")
    treaties, total = _fetch_treaties(congress=congress, limit=limit)

    if as_json:
        print(json.dumps(treaties, indent=2, default=str))
        return treaties

    if not treaties:
        print("  No treaties found.")
        return []

    print(f"\n  TREATIES -- {congress}th Congress ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'#':<5} {'Suffix':<8} {'Received':<12} {'Topic'}")
    print(f"  {'-'*5} {'-'*8} {'-'*12} {'-'*65}")
    for t in treaties:
        num = t.get("number", "")
        suf = t.get("suffix", "") or ""
        date = _parse_date(t.get("transmittedDate", ""))
        topic = _truncate(t.get("topic", ""), 65)
        print(f"  {num:<5} {suf:<8} {date:<12} {topic}")
    print()

    if export_fmt:
        flat = [{
            "number": t.get("number", ""),
            "suffix": t.get("suffix", ""),
            "congress_received": t.get("congressReceived", ""),
            "congress_considered": t.get("congressConsidered", ""),
            "transmitted_date": _parse_date(t.get("transmittedDate", "")),
            "topic": t.get("topic", ""),
            "url": t.get("url", ""),
        } for t in treaties]
        _do_export(flat, f"congress_treaties_{congress}", export_fmt)
    return treaties


def cmd_treaty(congress, number, suffix=None, as_json=False):
    print(f"\n  Fetching treaty {congress}/{number}{'/'+suffix if suffix else ''}...")
    treaty = _fetch_treaty_detail(congress, number, suffix=suffix)
    if not treaty:
        print("  Treaty not found.")
        return None
    if as_json:
        print(json.dumps(treaty, indent=2, default=str))
        return treaty

    print(f"\n  {'=' * 80}")
    print(f"  TREATY: {congress}-{number}{'/'+suffix if suffix else ''}")
    print(f"  {'=' * 80}")
    print(f"  Topic:            {treaty.get('topic', 'N/A')}")
    print(f"  Transmitted:      {_parse_date(treaty.get('transmittedDate', ''))}")
    print(f"  Congress received: {treaty.get('congressReceived', 'N/A')}")
    print(f"  Congress considered: {treaty.get('congressConsidered', 'N/A')}")
    actions = treaty.get("actions", [])
    if isinstance(actions, dict):
        print(f"  Actions count:    {actions.get('count', 0)}")
    elif isinstance(actions, list):
        print(f"  Actions listed:   {len(actions)}")
    url = treaty.get("url", "")
    if url:
        print(f"  URL:              {url}")
    print(f"  {'=' * 80}\n")
    return treaty


# --- Extended Commands: Committee Reports & Hearings -------------------------

def cmd_committee_reports(congress=None, report_type=None, limit=20,
                          as_json=False, export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    print(f"\n  Fetching committee reports ({congress}th Congress)...")
    reports, total = _fetch_committee_reports(congress=congress,
                                              report_type=report_type,
                                              limit=limit)
    if as_json:
        print(json.dumps(reports, indent=2, default=str))
        return reports
    if not reports:
        print("  No committee reports found.")
        return []

    print(f"\n  COMMITTEE REPORTS -- {congress}th Congress ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Citation':<22} {'Chamber':<10} {'Date':<12} {'Title'}")
    print(f"  {'-'*22} {'-'*10} {'-'*12} {'-'*45}")
    for r in reports:
        citation = r.get("citation", "")
        chamber = r.get("chamber", "")[:10]
        date = _parse_date(r.get("updateDate", r.get("date", "")))
        title = _truncate(r.get("title", ""), 45)
        print(f"  {citation:<22} {chamber:<10} {date:<12} {title}")
    print()

    if export_fmt:
        flat = [{
            "citation": r.get("citation", ""),
            "chamber": r.get("chamber", ""),
            "congress": r.get("congress", ""),
            "type": r.get("type", ""),
            "number": r.get("number", ""),
            "part": r.get("part", ""),
            "updateDate": _parse_date(r.get("updateDate", "")),
            "title": r.get("title", ""),
            "url": r.get("url", ""),
        } for r in reports]
        _do_export(flat, f"congress_committee_reports_{congress}", export_fmt)
    return reports


def cmd_hearings(congress=None, chamber=None, limit=20, as_json=False,
                 export_fmt=None):
    if congress is None:
        congress = CURRENT_CONGRESS
    print(f"\n  Fetching hearings ({congress}th Congress"
          f"{' / ' + chamber if chamber else ''})...")
    hearings, total = _fetch_hearings(congress=congress, chamber=chamber, limit=limit)
    if as_json:
        print(json.dumps(hearings, indent=2, default=str))
        return hearings

    if not hearings:
        print("  No hearings found.")
        return []

    print(f"\n  HEARINGS -- {congress}th Congress ({total:,} total)")
    print("  " + "=" * 95)
    print(f"  {'Jacket':<10} {'Chamber':<10} {'Number':<10} {'Updated'}")
    print(f"  {'-'*10} {'-'*10} {'-'*10} {'-'*15}")
    for h in hearings:
        jn = h.get("jacketNumber", "")
        ch = h.get("chamber", "")[:10]
        num = h.get("number", "")
        upd = _parse_date(h.get("updateDate", ""))
        print(f"  {jn:<10} {ch:<10} {num:<10} {upd}")
    print()

    if export_fmt:
        flat = [{
            "jacketNumber": h.get("jacketNumber", ""),
            "chamber": h.get("chamber", ""),
            "congress": h.get("congress", ""),
            "number": h.get("number", ""),
            "updateDate": _parse_date(h.get("updateDate", "")),
            "url": h.get("url", ""),
        } for h in hearings]
        _do_export(flat, f"congress_hearings_{congress}", export_fmt)
    return hearings


def cmd_hearing(congress, chamber, jacket_number, as_json=False):
    print(f"\n  Fetching hearing {congress}/{chamber}/{jacket_number}...")
    hearing = _fetch_hearing_detail(congress, chamber, jacket_number)
    if not hearing:
        print("  Hearing not found.")
        return None
    if as_json:
        print(json.dumps(hearing, indent=2, default=str))
        return hearing

    print(f"\n  {'=' * 80}")
    print(f"  HEARING: {congress}-{chamber}-{jacket_number}")
    print(f"  {'=' * 80}")
    title = hearing.get("title", "")
    if title:
        for i in range(0, len(title), 75):
            if i == 0:
                print(f"  Title:     {title[i:i+75]}")
            else:
                print(f"             {title[i:i+75]}")
    print(f"  Chamber:   {hearing.get('chamber', 'N/A')}")
    print(f"  Number:    {hearing.get('number', 'N/A')}")
    if hearing.get("citation"):
        print(f"  Citation:  {hearing['citation']}")

    committees = hearing.get("committees", [])
    if committees:
        print(f"\n  Committees:")
        for c in committees[:5]:
            if isinstance(c, dict):
                print(f"    {c.get('name','')} [{c.get('systemCode','')}]")

    dates = hearing.get("dates", [])
    if dates:
        print(f"\n  Dates:")
        for d in dates[:5]:
            if isinstance(d, dict):
                print(f"    {_parse_date(d.get('date',''))}")
    print(f"  {'=' * 80}\n")
    return hearing


# --- Extended Commands: Nomination Deep Dive ---------------------------------

def cmd_nomination(congress, number, as_json=False):
    print(f"\n  Fetching nomination PN{number} ({congress}th Congress)...")
    nom = _fetch_nomination_detail(congress, number)
    if not nom:
        print("  Nomination not found.")
        return None
    if as_json:
        print(json.dumps(nom, indent=2, default=str))
        return nom

    print(f"\n  {'=' * 80}")
    print(f"  NOMINATION: PN{number} ({congress}th Congress)")
    print(f"  {'=' * 80}")
    desc = nom.get("description", "")
    if desc:
        for i in range(0, len(desc), 75):
            if i == 0:
                print(f"  Description:  {desc[i:i+75]}")
            else:
                print(f"                {desc[i:i+75]}")

    print(f"  Received:     {_parse_date(nom.get('receivedDate', ''))}")
    print(f"  Organization: {nom.get('organization', 'N/A')}")

    la = nom.get("latestAction", {})
    if la:
        print(f"\n  Latest action ({_parse_date(la.get('actionDate',''))}):")
        print(f"    {_truncate(la.get('text', ''), 75)}")

    nominees = nom.get("nominees", [])
    if nominees:
        print(f"\n  Nominees: {len(nominees)}")
        for i, n in enumerate(nominees[:5], 1):
            if isinstance(n, dict):
                fn = n.get("firstName", "")
                ln = n.get("lastName", "")
                pos = n.get("positionTitle", "")
                print(f"    {i}) {fn} {ln} - {_truncate(pos, 45)}")

    committees = nom.get("committees", {})
    if isinstance(committees, dict) and committees.get("count"):
        print(f"\n  Committees:   {committees['count']}")
    actions = nom.get("actions", {})
    if isinstance(actions, dict) and actions.get("count"):
        print(f"  Actions:      {actions['count']}")
    hearings = nom.get("hearings", {})
    if isinstance(hearings, dict) and hearings.get("count"):
        print(f"  Hearings:     {hearings['count']}")

    url = nom.get("url", "")
    if url:
        print(f"\n  URL:          {url}")
    print(f"  {'=' * 80}\n")
    return nom


def cmd_nomination_pipeline(congress, number, as_json=False):
    """Aggregate nomination detail + actions + hearings + committees in one view."""
    print(f"\n  Assembling nomination pipeline for PN{number} ({congress}th)...")
    nom = _fetch_nomination_detail(congress, number)
    actions = _fetch_nomination_actions(congress, number)
    hearings = _fetch_nomination_hearings(congress, number)
    committees = _fetch_nomination_committees(congress, number)

    combined = {
        "nomination": nom,
        "actions": actions,
        "hearings": hearings,
        "committees": committees,
    }

    if as_json:
        print(json.dumps(combined, indent=2, default=str))
        return combined

    if nom:
        cmd_nomination(congress, number, as_json=False)

    if actions:
        print(f"\n  ACTION TIMELINE ({len(actions)} actions)")
        print("  " + "=" * 80)
        print(f"  {'Date':<12} {'Type':<14} {'Text'}")
        print(f"  {'-'*12} {'-'*14} {'-'*50}")
        for a in actions:
            date = _parse_date(a.get("actionDate", ""))
            atype = _truncate(a.get("type", ""), 14)
            text = _truncate(a.get("text", ""), 50)
            print(f"  {date:<12} {atype:<14} {text}")

    if hearings:
        print(f"\n  HEARINGS ({len(hearings)} hearings)")
        for h in hearings:
            date = _parse_date(h.get("date", ""))
            num = h.get("number", "")
            ch = h.get("chamber", "")
            print(f"    {date} - {ch} hearing #{num}")

    if committees:
        print(f"\n  COMMITTEES ({len(committees)})")
        for c in committees:
            name = c.get("name", "")
            ch = c.get("chamber", "")
            sc = c.get("systemCode", "")
            print(f"    {name} [{ch}/{sc}]")
    print()
    return combined


# --- Interactive CLI ----------------------------------------------------------

MENU = """
  =====================================================
   Congress.gov -- Legislative Tracking Client
  =====================================================

   BILLS
     1) latest           Latest bills with action
     2) bill             Get specific bill details
     3) actions          Bill action timeline
     4) cosponsors       Bill cosponsors
     5) summaries        Bill summaries
     6) search           Search bills by keyword
     7) related          Related bills (companions, alternates)
     8) bill-amendments  Amendments filed to a bill
     9) bill-committees  Committees that considered a bill
    10) titles           All titles (official + short) for a bill

   MONITORING
    11) tracker          Macro topic tracker
    12) nominations      Presidential nominations list
    13) nomination       Nomination pipeline (detail + actions + hearings)
    14) amendments       Recent amendments
    15) laws             Enacted laws this Congress

   VOTES & ANALYSIS
    16) votes            House roll call votes
    17) vote             Vote detail
    18) vote-members     Per-member vote breakdown

   POLICY RESEARCH
    19) crs              Latest CRS reports
    20) crs-report       Single CRS report detail
    21) committee-reports Committee reports (markup documents)
    22) hearings         Congressional hearings

   MEMBERS & TREATIES
    23) members          Member lookup (by state/congress)
    24) member           Member detail (by bioguide ID)
    25) sponsored        Legislation sponsored by a member
    26) cosponsored      Legislation cosponsored by a member
    27) treaties         Treaties list
    28) treaty           Treaty detail

   REFERENCE
    29) topics           List curated macro topics

   q) quit
"""


def _i_latest():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    print(f"  Bill types: {', '.join(BILL_TYPES.keys())}")
    btype = _prompt("Bill type (or 'all')", "all")
    n = _prompt("Number of bills", "20")
    btype = None if btype == "all" else btype
    cmd_latest(congress=int(congress), bill_type=btype, limit=int(n))

def _i_bill():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_bill(int(congress), btype, number)

def _i_actions():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_actions(int(congress), btype, number)

def _i_cosponsors():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_cosponsors(int(congress), btype, number)

def _i_summaries():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_summaries(int(congress), btype, number)

def _i_search():
    term = _prompt("Search term")
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    cmd_search(term=term, congress=int(congress))

def _i_related():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_related(int(congress), btype, number)

def _i_bill_amendments():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_bill_amendments(int(congress), btype, number)

def _i_bill_committees():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_bill_committees(int(congress), btype, number)

def _i_titles():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    btype = _prompt("Bill type (hr/s/hjres/sjres)", "hr")
    number = _prompt("Bill number")
    cmd_titles(int(congress), btype, number)

def _i_tracker():
    print(f"  Available topics: {', '.join(MACRO_TOPICS.keys())}")
    topics = _prompt("Topics (comma-separated or 'all')", "all")
    topic_list = None if topics == "all" else [t.strip() for t in topics.split(",")]
    cmd_tracker(topics=topic_list)

def _i_nominations():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    cmd_nominations(congress=int(congress))

def _i_nomination():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    num = _prompt("Nomination number (e.g. 123)")
    cmd_nomination_pipeline(int(congress), num)

def _i_amendments():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    cmd_amendments(congress=int(congress))

def _i_laws():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    ltype = _prompt("Law type (pub/priv/all)", "all")
    ltype = None if ltype == "all" else ltype
    cmd_laws(congress=int(congress), law_type=ltype)

def _i_votes():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    session = _prompt("Session (1/2/all)", "all")
    sess = None if session == "all" else int(session)
    cmd_votes(congress=int(congress), session=sess)

def _i_vote():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    session = _prompt("Session", "1")
    vote_num = _prompt("Roll call number")
    cmd_vote(int(congress), int(session), int(vote_num))

def _i_vote_members():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    session = _prompt("Session", "1")
    vote_num = _prompt("Roll call number")
    cmd_vote_members(int(congress), int(session), int(vote_num))

def _i_crs():
    n = _prompt("Number of reports", "20")
    cmd_crs(limit=int(n))

def _i_crs_report():
    rid = _prompt("Report ID (e.g. R48910)")
    cmd_crs_report(rid)

def _i_committee_reports():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    cmd_committee_reports(congress=int(congress))

def _i_hearings():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    chamber = _prompt("Chamber (house/senate/nochamber/all)", "all")
    chamber = None if chamber == "all" else chamber
    cmd_hearings(congress=int(congress), chamber=chamber)

def _i_members():
    state = _prompt("State code (e.g. NY, CA, or 'all')", "all")
    state = None if state == "all" else state.upper()
    cmd_members(state=state)

def _i_member():
    bio = _prompt("Bioguide ID (e.g. W000817 for Warren)")
    cmd_member(bio)

def _i_sponsored():
    bio = _prompt("Bioguide ID")
    n = _prompt("Limit", "50")
    cmd_sponsored(bio, limit=int(n))

def _i_cosponsored():
    bio = _prompt("Bioguide ID")
    n = _prompt("Limit", "50")
    cmd_cosponsored(bio, limit=int(n))

def _i_treaties():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    cmd_treaties(congress=int(congress))

def _i_treaty():
    congress = _prompt("Congress number", str(CURRENT_CONGRESS))
    num = _prompt("Treaty number")
    suffix = _prompt("Suffix (blank for none)", "")
    cmd_treaty(int(congress), int(num), suffix=suffix or None)

def _i_topics():
    cmd_topics()


COMMAND_MAP = {
    "1":  _i_latest,
    "2":  _i_bill,
    "3":  _i_actions,
    "4":  _i_cosponsors,
    "5":  _i_summaries,
    "6":  _i_search,
    "7":  _i_related,
    "8":  _i_bill_amendments,
    "9":  _i_bill_committees,
    "10": _i_titles,
    "11": _i_tracker,
    "12": _i_nominations,
    "13": _i_nomination,
    "14": _i_amendments,
    "15": _i_laws,
    "16": _i_votes,
    "17": _i_vote,
    "18": _i_vote_members,
    "19": _i_crs,
    "20": _i_crs_report,
    "21": _i_committee_reports,
    "22": _i_hearings,
    "23": _i_members,
    "24": _i_member,
    "25": _i_sponsored,
    "26": _i_cosponsored,
    "27": _i_treaties,
    "28": _i_treaty,
    "29": _i_topics,
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
            print("  Enter 1-29 or q to quit")


# --- Argparse -----------------------------------------------------------------

VALID_BILL_TYPES = list(BILL_TYPES.keys()) + ["all"]
VALID_TOPIC_KEYS = list(MACRO_TOPICS.keys())


def build_argparse():
    p = argparse.ArgumentParser(
        prog="congress.py",
        description="Congress.gov -- Legislative Tracking Client",
    )
    sub = p.add_subparsers(dest="command")

    # latest
    s = sub.add_parser("latest", help="Latest bills with action")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--type", choices=VALID_BILL_TYPES, default="all")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # bill
    s = sub.add_parser("bill", help="Get specific bill details")
    s.add_argument("congress", type=int, help="Congress number (e.g. 119)")
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()), help="Bill type")
    s.add_argument("number", help="Bill number")
    s.add_argument("--json", action="store_true")

    # actions
    s = sub.add_parser("actions", help="Bill action timeline")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--count", type=int, default=50)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # cosponsors
    s = sub.add_parser("cosponsors", help="Bill cosponsors")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")

    # summaries
    s = sub.add_parser("summaries", help="Bill summaries")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")

    # search
    s = sub.add_parser("search", help="Search bills by keyword")
    s.add_argument("term", help="Search term")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # tracker
    s = sub.add_parser("tracker", help="Macro topic tracker")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--topics", default=None,
                   help="Comma-separated topics: " + ",".join(VALID_TOPIC_KEYS))
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # nominations
    s = sub.add_parser("nominations", help="Presidential nominations")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # amendments
    s = sub.add_parser("amendments", help="Recent amendments")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # members
    s = sub.add_parser("members", help="Member lookup")
    s.add_argument("--state", default=None, help="State code (e.g. NY)")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # topics
    s = sub.add_parser("topics", help="List curated macro topics")

    # --- Extended: CRS Reports ----------------------------------------------
    s = sub.add_parser("crs", help="Latest CRS reports")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("crs-report", help="Single CRS report detail")
    s.add_argument("report_id", help="CRS report ID (e.g. R48910)")
    s.add_argument("--json", action="store_true")

    # --- Extended: House Roll Call Votes ------------------------------------
    s = sub.add_parser("votes", help="House roll call votes")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--session", type=int, default=None)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("vote", help="Single House roll call vote detail")
    s.add_argument("congress", type=int)
    s.add_argument("session", type=int)
    s.add_argument("vote_number", type=int)
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("vote-members", help="Per-member vote breakdown")
    s.add_argument("congress", type=int)
    s.add_argument("session", type=int)
    s.add_argument("vote_number", type=int)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # --- Extended: Laws -----------------------------------------------------
    s = sub.add_parser("laws", help="Enacted public / private laws")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--law-type", choices=["pub", "priv"], default=None)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("law", help="Specific law detail")
    s.add_argument("congress", type=int)
    s.add_argument("law_type", choices=["pub", "priv"])
    s.add_argument("law_number")
    s.add_argument("--json", action="store_true")

    # --- Extended: Bill Sub-Endpoints ---------------------------------------
    s = sub.add_parser("related", help="Related bills (companions, alternates)")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("bill-amendments", help="Amendments filed to a bill")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("bill-committees", help="Committees that considered a bill")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("titles", help="All titles (official + short) for a bill")
    s.add_argument("congress", type=int)
    s.add_argument("bill_type", choices=list(BILL_TYPES.keys()))
    s.add_argument("number")
    s.add_argument("--json", action="store_true")

    # --- Extended: Member Deep Dive -----------------------------------------
    s = sub.add_parser("member", help="Member detail by bioguide ID")
    s.add_argument("bioguide_id", help="Bioguide ID (e.g. W000817 for Warren)")
    s.add_argument("--json", action="store_true")

    s = sub.add_parser("sponsored", help="Legislation sponsored by a member")
    s.add_argument("bioguide_id")
    s.add_argument("--count", type=int, default=50)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("cosponsored", help="Legislation cosponsored by a member")
    s.add_argument("bioguide_id")
    s.add_argument("--count", type=int, default=50)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    # --- Extended: Treaties -------------------------------------------------
    s = sub.add_parser("treaties", help="Treaties submitted for ratification")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("treaty", help="Single treaty detail")
    s.add_argument("congress", type=int)
    s.add_argument("number", type=int)
    s.add_argument("--suffix", default=None, help="Optional treaty part suffix")
    s.add_argument("--json", action="store_true")

    # --- Extended: Committee Reports & Hearings -----------------------------
    s = sub.add_parser("committee-reports", help="Committee markup reports")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--report-type",
                   choices=["hrpt", "srpt", "erpt"], default=None,
                   help="hrpt=House, srpt=Senate, erpt=Exec (conf reports)")
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("hearings", help="Committee hearings")
    s.add_argument("--congress", type=int, default=CURRENT_CONGRESS)
    s.add_argument("--chamber", choices=["house", "senate", "nochamber"],
                   default=None)
    s.add_argument("--count", type=int, default=20)
    s.add_argument("--json", action="store_true")
    s.add_argument("--export", choices=["csv", "json"])

    s = sub.add_parser("hearing", help="Single hearing detail")
    s.add_argument("congress", type=int)
    s.add_argument("chamber", choices=["house", "senate", "nochamber"])
    s.add_argument("jacket_number")
    s.add_argument("--json", action="store_true")

    # --- Extended: Nomination Pipeline --------------------------------------
    s = sub.add_parser("nomination",
                       help="Full nomination pipeline (detail + actions + hearings)")
    s.add_argument("congress", type=int)
    s.add_argument("number", help="Nomination number (e.g. 123)")
    s.add_argument("--json", action="store_true")

    return p


def run_noninteractive(args):
    j = getattr(args, "json", False)
    exp = getattr(args, "export", None)
    cnt = getattr(args, "count", 20)
    congress = getattr(args, "congress", CURRENT_CONGRESS)

    if args.command == "latest":
        btype = getattr(args, "type", "all")
        btype = None if btype == "all" else btype
        cmd_latest(congress=congress, bill_type=btype, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "bill":
        cmd_bill(args.congress, args.bill_type, args.number, as_json=j)
    elif args.command == "actions":
        cmd_actions(args.congress, args.bill_type, args.number, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "cosponsors":
        cmd_cosponsors(args.congress, args.bill_type, args.number, as_json=j)
    elif args.command == "summaries":
        cmd_summaries(args.congress, args.bill_type, args.number, as_json=j)
    elif args.command == "search":
        cmd_search(term=args.term, congress=congress, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "tracker":
        topic_list = [t.strip() for t in args.topics.split(",")] if args.topics else None
        cmd_tracker(congress=congress, topics=topic_list, as_json=j, export_fmt=exp)
    elif args.command == "nominations":
        cmd_nominations(congress=congress, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "amendments":
        cmd_amendments(congress=congress, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "members":
        state = getattr(args, "state", None)
        cmd_members(state=state, congress=congress, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "topics":
        cmd_topics(as_json=j)

    # --- Extended: CRS Reports ----------------------------------------------
    elif args.command == "crs":
        cmd_crs(limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "crs-report":
        cmd_crs_report(args.report_id, as_json=j)

    # --- Extended: House Votes ---------------------------------------------
    elif args.command == "votes":
        session = getattr(args, "session", None)
        cmd_votes(congress=congress, session=session, limit=cnt,
                  as_json=j, export_fmt=exp)
    elif args.command == "vote":
        cmd_vote(args.congress, args.session, args.vote_number, as_json=j)
    elif args.command == "vote-members":
        cmd_vote_members(args.congress, args.session, args.vote_number,
                         as_json=j, export_fmt=exp)

    # --- Extended: Laws ----------------------------------------------------
    elif args.command == "laws":
        ltype = getattr(args, "law_type", None)
        cmd_laws(congress=congress, law_type=ltype, limit=cnt,
                 as_json=j, export_fmt=exp)
    elif args.command == "law":
        cmd_law(args.congress, args.law_type, args.law_number, as_json=j)

    # --- Extended: Bill Sub-Endpoints --------------------------------------
    elif args.command == "related":
        cmd_related(args.congress, args.bill_type, args.number,
                    as_json=j, export_fmt=exp)
    elif args.command == "bill-amendments":
        cmd_bill_amendments(args.congress, args.bill_type, args.number,
                            as_json=j, export_fmt=exp)
    elif args.command == "bill-committees":
        cmd_bill_committees(args.congress, args.bill_type, args.number,
                            as_json=j)
    elif args.command == "titles":
        cmd_titles(args.congress, args.bill_type, args.number, as_json=j)

    # --- Extended: Members ------------------------------------------------
    elif args.command == "member":
        cmd_member(args.bioguide_id, as_json=j)
    elif args.command == "sponsored":
        cmd_sponsored(args.bioguide_id, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "cosponsored":
        cmd_cosponsored(args.bioguide_id, limit=cnt, as_json=j, export_fmt=exp)

    # --- Extended: Treaties -----------------------------------------------
    elif args.command == "treaties":
        cmd_treaties(congress=congress, limit=cnt, as_json=j, export_fmt=exp)
    elif args.command == "treaty":
        suffix = getattr(args, "suffix", None)
        cmd_treaty(args.congress, args.number, suffix=suffix, as_json=j)

    # --- Extended: Committee Reports & Hearings ---------------------------
    elif args.command == "committee-reports":
        rtype = getattr(args, "report_type", None)
        cmd_committee_reports(congress=congress, report_type=rtype, limit=cnt,
                              as_json=j, export_fmt=exp)
    elif args.command == "hearings":
        chamber = getattr(args, "chamber", None)
        cmd_hearings(congress=congress, chamber=chamber, limit=cnt,
                     as_json=j, export_fmt=exp)
    elif args.command == "hearing":
        cmd_hearing(args.congress, args.chamber, args.jacket_number, as_json=j)

    # --- Extended: Nomination Pipeline ------------------------------------
    elif args.command == "nomination":
        cmd_nomination_pipeline(args.congress, args.number, as_json=j)


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
