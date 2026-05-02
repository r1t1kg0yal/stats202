"""TreasuryDirect.gov API client (PRISM-side library module).

Library-only — no CLI surface. Sandbox-injected as `treasury_direct_client`
per `prism/api-clients.md` §4.

Wraps two distinct surfaces:

  1. The /TA_WS/securities/* and /NP_WS/debt/* JSON APIs at
     www.treasurydirect.gov. Provides auction announcement / result data
     (CUSIPs, security types, yields, bid-to-cover, auction-tail bps),
     debt-to-the-penny, and Treasury buyback operations.

  2. The quarterly refunding artifact scrapers — XML auction-schedule and
     buyback-schedule downloads, plus an HTML scrape of the most recent
     refunding announcement page. These are the pre-auction pipeline
     artifacts (typically published 6-8 weeks ahead of an auction).

Imports `manual_https_request` from PRISM's GS-proxy transport layer
(`gs_app_proxy_negotiate.py`); in staging the same import resolves to the
local stub mirror at
`projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` so this file
runs identically in both environments.

TreasuryDirect is the canonical Bucket B client (per
`prism/api-clients.md` §9 + `prism/gs-proxy.md` §7.2): the standard
`session_and_auth()` adapter leaks an Authorization header that
TreasuryDirect rejects with HTTP 400 Bad Request. The manual CONNECT
tunnel delivers a clean target request.

Surface:
  Constants    BASE_URL, SECURITIES_API, DEBT_API, SECURITY_TYPES (6),
               SECURITIES_ENDPOINTS, DEBT_ENDPOINTS, RATE_LIMIT_SECONDS,
               API_PAGE_SIZE, FULL_HISTORY_START
  Class        TreasuryDirectScraper
                 _fetch, _fetch_json   (private — return _MockResponse
                                         and parsed JSON respectively)
                 scrape_securities_api(security_type, days, full_history)
                                       -> list[dict] auction records
                 scrape_securities_by_cusip(cusip)
                                       -> list[dict] (1 or more records)
                 scrape_debt_api(start_date, end_date, current_only)
                                       -> dict (current) or list (range)
                 scrape_buybacks(from_date, to_date, with_results_only)
                                       -> list[dict] buyback operations
                 scrape_refunding_latest()
                                       -> dict with refunding announcement
                                         metadata (title, date, links)
                 fetch_auction_schedule_xml()
                                       -> list[dict] upcoming auction
                                         schedule (next ~12 weeks)
                 fetch_buyback_schedule_xml()
                                       -> list[dict] upcoming buyback
                                         operations schedule

Status: returned via the `(parsed_data, status_line)` tuple shape from
manual_https_request (per `prism/gs-proxy.md` §6.4). The client wraps
this in `_MockResponse` so call-site code can use the requests-style
`resp.json() / resp.text / resp.status_code / resp.ok` interface.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from time import sleep
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlencode

from ai_development.mcp.gs_app_proxy_negotiate import manual_https_request


BASE_URL = "https://www.treasurydirect.gov"
BASE_HOST = "www.treasurydirect.gov"

SECURITIES_API = f"{BASE_URL}/TA_WS/securities"
DEBT_API = f"{BASE_URL}/NP_WS/debt"

SECURITY_TYPES = ["Bill", "Note", "Bond", "TIPS", "FRN", "CMB"]

SECURITIES_ENDPOINTS = {
    "announced": f"{SECURITIES_API}/announced",
    "auctioned": f"{SECURITIES_API}/auctioned",
    "search":    f"{SECURITIES_API}/search",
}

DEBT_ENDPOINTS = {
    "current": f"{DEBT_API}/current",
    "search":  f"{DEBT_API}/search",
}

# Path templates for the manual_https_request transport (host stripped).
_SECURITIES_PATHS = {
    "announced": "/TA_WS/securities/announced",
    "auctioned": "/TA_WS/securities/auctioned",
    "search":    "/TA_WS/securities/search",
}

_DEBT_PATHS = {
    "current": "/NP_WS/debt/current",
    "search":  "/NP_WS/debt/search",
}

# Refunding artifact paths. NOTE: the exact URL paths for these three
# methods are best-effort guesses pending PRISM-source confirmation. The
# methods are listed in `prism/api-clients.md` §3.2 with their public
# names but the doc does not pin URLs. Smoke demos surface failure
# cleanly (empty list / dict on 404 / parse error) so a wrong URL fails
# loud at first call rather than silently succeeding. When PRISM source
# becomes available, swap these constants to match.
_AUCTION_SCHEDULE_PATH = "/instit/annceresult/press/preanre/auctions.xml"
_BUYBACK_SCHEDULE_PATH = "/instit/annceresult/press/preanre/buybacks.xml"
_REFUNDING_INDEX_PATH = "/auctions/upcoming/"

API_PAGE_SIZE = 250
MAX_API_PAGES = 200
RATE_LIMIT_SECONDS = 0.5

FULL_HISTORY_START = "01/01/1997"


__all__ = [
    "BASE_URL", "BASE_HOST", "SECURITIES_API", "DEBT_API",
    "SECURITY_TYPES", "SECURITIES_ENDPOINTS", "DEBT_ENDPOINTS",
    "API_PAGE_SIZE", "MAX_API_PAGES", "RATE_LIMIT_SECONDS",
    "FULL_HISTORY_START",
    "TreasuryDirectScraper",
]


class _MockResponse:
    """Wraps the (parsed_data, status_line) tuple from manual_https_request
    in a minimal `requests.Response`-like interface.

    Per `prism/gs-proxy.md` §6.4 the documented return shape is:
      - `parsed_data`: dict / list (parsed JSON), str (decoded body), or
        None if no body.
      - `status_line`: STRING like "HTTP/1.1 200 OK", NOT an integer.

    Callers use `resp.status_code` / `resp.text` / `resp.json()` /
    `resp.ok` exactly as they would with a `requests.Response`. The
    recommended validity check (per the same doc section) is
    `isinstance(resp.json(), (dict, list))` rather than parsing
    `resp.status_code`, because the manual tunnel can return a
    well-formed body with a less-than-perfect status line on rare edge
    cases.
    """

    def __init__(self, parsed_data: Any, status_line: str):
        self._parsed = parsed_data
        self._status_line = status_line
        self.status_code = self._parse_status_code(status_line)

    @staticmethod
    def _parse_status_code(status_line: str) -> int:
        # Expected format: "HTTP/1.x <code> <reason>". Edge case:
        # manual_https_request returns the literal string "No HTTP
        # response headers found" when CONNECT succeeded but the
        # response was malformed — we surface that as 0 so .ok is False.
        if not status_line.startswith("HTTP/"):
            return 0
        parts = status_line.split()
        if len(parts) < 2:
            return 0
        try:
            return int(parts[1])
        except ValueError:
            return 0

    @property
    def text(self) -> str:
        if isinstance(self._parsed, str):
            return self._parsed
        if self._parsed is None:
            return ""
        return json.dumps(self._parsed)

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")

    def json(self) -> Any:
        if isinstance(self._parsed, (dict, list)):
            return self._parsed
        if isinstance(self._parsed, str):
            return json.loads(self._parsed)
        raise json.JSONDecodeError("no body to decode", "", 0)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def status_line(self) -> str:
        return self._status_line


class TreasuryDirectScraper:
    """TreasuryDirect.gov data client.

    All `scrape_*` and `fetch_*` methods return parsed Python data
    structures (no file I/O, no caching to disk). Transport is
    `manual_https_request` from `gs_app_proxy_negotiate.py`.
    """

    def __init__(self):
        # Module is sandbox-stateless. No session caching is needed:
        # manual_https_request opens a fresh CONNECT tunnel per call,
        # which is required for TreasuryDirect's header-contamination
        # avoidance per `prism/gs-proxy.md` §8.
        pass

    # ── transport ────────────────────────────────────────────────────

    def _fetch(self, path: str, *, params: Optional[Dict[str, Any]] = None,
               timeout: int = 30) -> _MockResponse:
        """Fetch via manual_https_request; return a `_MockResponse`.

        `path` should start with "/" and exclude the host. `params` is
        forwarded as the query string.
        """
        parsed, status_line = manual_https_request(
            host=BASE_HOST,
            method="GET",
            path=path,
            params=params,
            timeout=timeout,
        )
        return _MockResponse(parsed, status_line)

    def _fetch_json(self, path: str, *, params: Optional[Dict[str, Any]] = None,
                    timeout: int = 30) -> Optional[Any]:
        """Fetch and parse JSON; return dict / list, or None on failure.

        Validity check uses `isinstance(data, (dict, list))` rather than
        parsing the status line (per the recommended pattern in
        `prism/gs-proxy.md` §6.4).
        """
        resp = self._fetch(path, params=params, timeout=timeout)
        try:
            data = resp.json()
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if isinstance(data, (dict, list)):
            return data
        return None

    # ── Securities API ───────────────────────────────────────────────

    @staticmethod
    def _compute_tail(rec: dict) -> None:
        """Compute auction tail = highYield - averageMedianYield (bp).

        The true tail is stop-out vs when-issued, but the API doesn't
        carry WI yields. highYield vs median is a useful intra-auction
        dispersion measure available from the data. Mutates `rec` in
        place by adding/setting `tailBps`.
        """
        try:
            high = rec.get("highYield")
            median = rec.get("averageMedianYield")
            if high and median:
                high_f = float(str(high).strip())
                median_f = float(str(median).strip())
                rec["tailBps"] = round((high_f - median_f) * 100, 2)
            else:
                rec["tailBps"] = None
        except (ValueError, TypeError):
            rec["tailBps"] = None

    def scrape_securities_api(self, *,
                              security_type: Optional[str] = None,
                              days: int = 365,
                              full_history: bool = False) -> List[Dict[str, Any]]:
        """Fetch auction history records from /TA_WS/securities/search.

        Returns a list of auction-record dicts with `tailBps` computed
        per `_compute_tail`. Records are sorted by `auctionDate` desc.

        Args:
            security_type: One of `SECURITY_TYPES` or None for all.
            days: Days back from today (ignored if `full_history`).
            full_history: If True, pulls from `FULL_HISTORY_START`.

        Internally chunks the date range to avoid the search endpoint's
        ~2000-record cap on wide ranges (Bill auctions especially).
        """
        types_to_fetch = (
            [security_type] if (security_type and security_type != "all")
            else SECURITY_TYPES
        )

        if full_history:
            start_date = FULL_HISTORY_START
        else:
            start_date = (datetime.now() - timedelta(days=days)).strftime("%m/%d/%Y")
        end_date = datetime.now().strftime("%m/%d/%Y")

        all_combined: List[Dict[str, Any]] = []
        for sec_type in types_to_fetch:
            records = self._fetch_full_auction_history(sec_type, start_date, end_date)
            if records:
                all_combined.extend(records)

        if all_combined:
            all_combined.sort(key=lambda r: r.get("auctionDate", ""), reverse=True)
            for rec in all_combined:
                self._compute_tail(rec)

        return all_combined

    def _fetch_full_auction_history(self, sec_type: str, start_date: str,
                                    end_date: str) -> List[Dict[str, Any]]:
        """Fetch auction history with date-range chunking.

        The search endpoint returns all matching records in one response
        (up to ~2000) but fails on very wide ranges for high-volume
        types. Chunk into 2-year windows for Bills, 5-year windows for
        everything else.
        """
        try:
            start_dt = datetime.strptime(start_date, "%m/%d/%Y")
        except ValueError:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        try:
            end_dt = datetime.strptime(end_date, "%m/%d/%Y")
        except ValueError:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        chunk_years = 2 if sec_type == "Bill" else 5
        chunk_delta = timedelta(days=chunk_years * 365)

        all_records: List[Dict[str, Any]] = []
        seen_cusip_dates: Set[str] = set()
        current_start = start_dt

        while current_start < end_dt:
            current_end = min(current_start + chunk_delta, end_dt)

            params = {
                "format": "json",
                "type": sec_type,
                "startDate": current_start.strftime("%m/%d/%Y"),
                "endDate": current_end.strftime("%m/%d/%Y"),
                "pagesize": str(API_PAGE_SIZE),
            }
            data = self._fetch_json(_SECURITIES_PATHS["search"], params=params)

            if data and isinstance(data, list):
                for rec in data:
                    if not isinstance(rec, dict):
                        continue
                    dedup_key = f"{rec.get('cusip', '')}_{rec.get('auctionDate', '')}"
                    if dedup_key not in seen_cusip_dates:
                        seen_cusip_dates.add(dedup_key)
                        all_records.append(rec)

            current_start = current_end + timedelta(days=1)
            sleep(RATE_LIMIT_SECONDS)

        return all_records

    def scrape_securities_by_cusip(self, cusip: str) -> List[Dict[str, Any]]:
        """Look up auction records by CUSIP. Returns 1+ records (some
        CUSIPs map to multiple auctions through reopenings)."""
        # Try the search endpoint first (handles reopenings).
        params = {"cusip": cusip, "format": "json"}
        data = self._fetch_json(_SECURITIES_PATHS["search"], params=params)

        # Fall back to the per-CUSIP path if search returns nothing.
        if not data:
            data = self._fetch_json(f"/TA_WS/securities/{cusip}",
                                    params={"format": "json"})

        if not data:
            return []

        records = data if isinstance(data, list) else [data]
        for rec in records:
            if isinstance(rec, dict):
                self._compute_tail(rec)
        return records

    def scrape_announced(self, *, security_type: Optional[str] = None,
                         days: int = 30) -> List[Dict[str, Any]]:
        """Fetch announced auctions (upcoming, not yet held).

        TreasuryDirect's /announced endpoint returns the next round of
        scheduled auctions. Filter by security_type and return up to
        `days` ahead.
        """
        params: Dict[str, Any] = {"format": "json", "days": str(days)}
        if security_type:
            params["type"] = security_type
        data = self._fetch_json(_SECURITIES_PATHS["announced"], params=params)
        if not isinstance(data, list):
            return []
        return data

    def scrape_auctioned(self, *, security_type: Optional[str] = None,
                         days: int = 30) -> List[Dict[str, Any]]:
        """Fetch recently-auctioned securities (results published)."""
        params: Dict[str, Any] = {"format": "json", "days": str(days)}
        if security_type:
            params["type"] = security_type
        data = self._fetch_json(_SECURITIES_PATHS["auctioned"], params=params)
        if not isinstance(data, list):
            return []
        for rec in data:
            if isinstance(rec, dict):
                self._compute_tail(rec)
        return data

    # ── Debt API ─────────────────────────────────────────────────────

    def scrape_debt_api(self, *, start_date: Optional[str] = None,
                        end_date: Optional[str] = None,
                        current_only: bool = False) -> Any:
        """Fetch debt-to-the-penny data.

        Args:
            start_date / end_date: YYYY-MM-DD. If None and not
                `current_only`, defaults to start=2000-01-01,
                end=today.
            current_only: If True, returns only the current debt
                snapshot (one dict). Otherwise returns a list of daily
                records.

        Returns dict (current_only) or list[dict] (range).
        """
        current = self._fetch_json(_DEBT_PATHS["current"], params={"format": "json"})

        if current_only:
            return current if isinstance(current, dict) else {}

        if start_date is None:
            start_date = "2000-01-01"
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        all_records: List[Dict[str, Any]] = []
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        chunk_months = 12

        current_start = start_dt
        while current_start < end_dt:
            current_end = min(current_start + timedelta(days=chunk_months * 30),
                              end_dt)
            params = {
                "startdate": current_start.strftime("%Y-%m-%d"),
                "enddate": current_end.strftime("%Y-%m-%d"),
                "format": "json",
            }
            data = self._fetch_json(_DEBT_PATHS["search"], params=params)
            if isinstance(data, list):
                all_records.extend(data)
            elif isinstance(data, dict) and "data" in data:
                # Some endpoints wrap rows in {"data": [...]}.
                rows = data.get("data")
                if isinstance(rows, list):
                    all_records.extend(rows)
            current_start = current_end + timedelta(days=1)
            sleep(RATE_LIMIT_SECONDS)

        return all_records

    # ── Buybacks ─────────────────────────────────────────────────────

    def scrape_buybacks(self, *, from_date: Optional[str] = None,
                        to_date: Optional[str] = None,
                        with_results_only: bool = False) -> List[Dict[str, Any]]:
        """Fetch Treasury buyback operations.

        Treasury restarted buybacks in 2024. Two operation types:
            - "Liquidity Support": off-the-run repurchases for market
                                    liquidity (most operations).
            - "Cash Management":   managing Treasury cash balance via
                                    bill issuance.

        Args:
            from_date / to_date: ISO YYYY-MM-DD bounds on operation_date.
            with_results_only: If True, drops operations without
                completed results.

        Returns list of buyback operation records with fields including
        operation_date, operation_type, security_type, maturity_bucket,
        total_par_amt_offered, total_par_amt_accepted, settlement_date.
        """
        # Buybacks live on the Fiscal Data API (api.fiscaldata.treasury.gov).
        # We use the Fiscal Data path here through manual_https_request
        # (Bucket B). The caller can also reach buybacks via
        # treasury_client.get_buybacks() which uses Bucket A — both work.
        path = "/services/api/fiscal_service/v1/accounting/od/buybacks_operations"
        params: Dict[str, Any] = {
            "format": "json",
            "page[size]": "1000",
            "sort": "-operation_date",
        }
        filters = []
        if from_date:
            filters.append(f"operation_date:gte:{from_date}")
        if to_date:
            filters.append(f"operation_date:lte:{to_date}")
        if filters:
            params["filter"] = ",".join(filters)

        # Fiscal Data lives on a different host.
        parsed, status_line = manual_https_request(
            host="api.fiscaldata.treasury.gov",
            method="GET",
            path=path,
            params=params,
            timeout=30,
        )
        resp = _MockResponse(parsed, status_line)
        try:
            data = resp.json()
        except (json.JSONDecodeError, TypeError, ValueError):
            return []
        if not isinstance(data, dict) or "data" not in data:
            return []

        rows = data.get("data") or []
        if with_results_only:
            rows = [
                r for r in rows
                if r.get("total_par_amt_accepted")
                and r["total_par_amt_accepted"] != "null"
            ]
        return rows

    # ── Refunding artifacts (HTML / XML scrapes) ─────────────────────

    def scrape_refunding_latest(self) -> Dict[str, Any]:
        """Scrape the latest quarterly refunding announcement.

        Returns a dict with:
            title:        page title
            announcements: list of {date, title, links: [...]} for the
                           most recent ~4 announcements
            url:          the source page URL

        NOTE: URL path is speculative pending PRISM-source confirmation.
        Modern Treasury refunding announcements actually live at
        home.treasury.gov, not www.treasurydirect.gov. If this method
        returns empty `announcements`, the URL probably needs updating.
        """
        resp = self._fetch(_REFUNDING_INDEX_PATH)
        if not resp.ok:
            return {"title": "", "announcements": [], "url":
                    f"{BASE_URL}{_REFUNDING_INDEX_PATH}", "error":
                    resp.status_line}

        html = resp.text
        # Lightweight HTML parsing via regex — this page has stable
        # markup. Extract links to /auctions/quarterly-refunding/
        # subpages and group them by date prefix.
        title_match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else ""

        link_pattern = re.compile(
            r'<a[^>]+href="([^"]*quarterly-refunding[^"]*)"[^>]*>([^<]+)</a>',
            re.IGNORECASE,
        )
        link_hits = link_pattern.findall(html)

        # Group by date — refunding announcement URLs have YYYY-MM in
        # them (e.g. /auctions/quarterly-refunding/2026-Q2/).
        date_groups: Dict[str, List[Dict[str, str]]] = {}
        for href, text in link_hits:
            date_match = re.search(r"(\d{4})-Q([1-4])", href) or \
                         re.search(r"(\d{4})/([0-9]{1,2})", href)
            if not date_match:
                continue
            key = f"{date_match.group(1)}-{date_match.group(2)}"
            full_url = href if href.startswith("http") else f"{BASE_URL}{href}"
            date_groups.setdefault(key, []).append({
                "text": text.strip(),
                "url": full_url,
            })

        announcements = []
        for key in sorted(date_groups.keys(), reverse=True)[:4]:
            announcements.append({
                "date": key,
                "links": date_groups[key],
            })

        return {
            "title": title,
            "announcements": announcements,
            "url": f"{BASE_URL}{_REFUNDING_INDEX_PATH}",
        }

    def fetch_auction_schedule_xml(self) -> List[Dict[str, Any]]:
        """Fetch the upcoming auction schedule XML (next ~12 weeks).

        Returns a list of scheduled auction records with fields including
        auction_date, security_type, security_term, cusip (if assigned),
        announce_date, issue_date.
        """
        resp = self._fetch(_AUCTION_SCHEDULE_PATH)
        if not resp.ok:
            return []
        return self._parse_schedule_xml(resp.text)

    def fetch_buyback_schedule_xml(self) -> List[Dict[str, Any]]:
        """Fetch the upcoming buyback schedule XML.

        Returns a list of scheduled buyback operation records.
        """
        resp = self._fetch(_BUYBACK_SCHEDULE_PATH)
        if not resp.ok:
            return []
        return self._parse_schedule_xml(resp.text)

    @staticmethod
    def _parse_schedule_xml(xml_text: str) -> List[Dict[str, Any]]:
        """Parse a TreasuryDirect schedule XML into a list of dicts.

        TreasuryDirect's schedule XMLs are flat: a root element with
        repeated child elements, each containing simple text fields.
        Strip namespaces if present and convert each child to a dict.
        """
        if not xml_text or not xml_text.strip():
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        records = []
        for child in root:
            rec = {}
            for sub in child:
                tag = sub.tag
                # Strip XML namespace if present: {ns}tag -> tag
                if "}" in tag:
                    tag = tag.split("}", 1)[1]
                rec[tag] = (sub.text or "").strip()
            if rec:
                records.append(rec)
        return records
