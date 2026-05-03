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
    # Module-level helpers absorbing [W] frictions per D15 Ergonomics
    "get_high_rate", "compute_tail",
]


# TreasuryDirect returns numeric fields as STRINGS (the API quirk that
# motivated friction class A in `prism/api-clients.md` §11). The wrapper
# coerces at the boundary so PRISM never has to remember to float() yields,
# bid-to-cover, debt amounts, par amounts, etc. The set is conservative —
# any field name on this list gets coerced if its value is a non-empty
# numeric string; otherwise it's left alone.
_NUMERIC_FIELDS: Set[str] = {
    # Auction yields / rates
    "highYield", "lowYield", "averageMedianYield",
    "highDiscountRate", "lowDiscountRate", "averageMedianDiscountRate",
    "highInvestmentRate", "lowInvestmentRate",
    "highPrice", "lowPrice", "averageMedianPrice",
    "interestRate", "indexRatioOnIssueDate",
    # Auction statistics
    "bidToCoverRatio", "competitiveBidsAccepted", "competitiveBidsTendered",
    "competitiveTendersAccepted", "noncompetitiveBidsAccepted",
    "noncompetitiveBidsTendered", "noncompetitiveTendersAccepted",
    "primaryDealerAccepted", "primaryDealerTendered",
    "directBidderAccepted", "directBidderTendered",
    "indirectBidderAccepted", "indirectBidderTendered",
    "totalAccepted", "totalTendered", "totalSomaAccepted", "totalSomaTendered",
    # Amounts
    "offeringAmt", "currentlyOutstanding", "originalIssueAmt",
    "totalDebt", "publicDebt", "governmentHoldings",
    "treasuryRetailAccepted",
    # Buybacks
    "total_par_amt_offered", "total_par_amt_accepted",
    "max_par_amt_redeemed", "par_amt_per_offer",
    "nbr_issues_offered", "nbr_issues_accepted", "nbr_issues_eligible",
}


def _coerce_numeric(val: Any) -> Any:
    """Coerce a numeric field if it parses as int/float; else return as-is."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if not isinstance(val, str):
        return val
    s = val.strip()
    if s == "" or s.lower() == "null":
        return None
    try:
        return float(s) if ("." in s or "e" in s.lower()) else int(s)
    except ValueError:
        return val


def _coerce_record(rec: Any) -> Any:
    """In-place type coercion for a TreasuryDirect record (or list of them).

    Walks `_NUMERIC_FIELDS` and converts each present value at the
    boundary. PRISM gets back floats / ints / None, never numeric strings.
    """
    if isinstance(rec, list):
        for r in rec:
            _coerce_record(r)
        return rec
    if isinstance(rec, dict):
        for k in _NUMERIC_FIELDS:
            if k in rec:
                rec[k] = _coerce_numeric(rec[k])
    return rec


# ── Module-level helpers absorbing security-type-specific quirks ──────────


def get_high_rate(rec: dict) -> dict[str, Any]:
    """Return the canonical "high rate" for an auction record, regardless
    of security type.

    Treasury auction records use DIFFERENT field names depending on the
    security being auctioned:

      Notes / Bonds / TIPS / FRN  -> highYield (yield basis)
      Bills                        -> highDiscountRate (discount rate),
                                       highInvestmentRate (bond-equivalent
                                                            yield)

    PRISM should never have to branch on `securityType` to pick the right
    field. Returns:

        {
            "rate":         float,    # the canonical "high rate"
            "rate_type":    str,      # "yield" | "discount" | "investment"
            "field_name":   str,      # the actual API field used
            "security_type": str,     # passed through for context
        }

    For Bills: rate_type = "investment" by default (bond-equivalent yield;
    the apples-to-apples comparison with note/bond yields). Pass via the
    record's `securityType` key.
    """
    sec = (rec.get("securityType") or "").strip()
    if sec == "Bill":
        inv = _coerce_numeric(rec.get("highInvestmentRate"))
        if inv is not None:
            return {"rate": inv, "rate_type": "investment", "field_name": "highInvestmentRate", "security_type": sec}
        disc = _coerce_numeric(rec.get("highDiscountRate"))
        if disc is not None:
            return {"rate": disc, "rate_type": "discount", "field_name": "highDiscountRate", "security_type": sec}
        return {"rate": None, "rate_type": "investment", "field_name": "highInvestmentRate", "security_type": sec}
    yld = _coerce_numeric(rec.get("highYield"))
    return {"rate": yld, "rate_type": "yield", "field_name": "highYield", "security_type": sec}


def compute_tail(rec: dict) -> Optional[float]:
    """Compute auction tail in basis points, security-type-aware.

    Notes / Bonds / TIPS / FRN: tail = highYield - averageMedianYield (bp)
    Bills:                       tail = highDiscountRate
                                          - averageMedianDiscountRate (bp,
                                          on discount-rate basis)

    Returns the tail in BPS (multiplied by 100) or None if the relevant
    fields are missing / unparseable.

    The computation is exposed as a module-level helper so PRISM can call
    `treasury_direct_client.compute_tail(rec)` without instantiating the
    scraper or remembering which field-pair to use per security type.
    """
    sec = (rec.get("securityType") or "").strip()
    if sec == "Bill":
        high = _coerce_numeric(rec.get("highDiscountRate"))
        median = _coerce_numeric(rec.get("averageMedianDiscountRate"))
    else:
        high = _coerce_numeric(rec.get("highYield"))
        median = _coerce_numeric(rec.get("averageMedianYield"))
    if high is None or median is None:
        return None
    try:
        return round((float(high) - float(median)) * 100, 2)
    except (TypeError, ValueError):
        return None


def _parse_tenor_years(security_term: str) -> Optional[float]:
    """Convert a TreasuryDirect securityTerm string to years (float).

    Examples:
      "10-Year"           -> 10.0
      "2-Year"            -> 2.0
      "30-Year"           -> 30.0
      "1-Month"           -> 0.0833
      "13-Week"           -> 0.25
      "26-Week"           -> 0.5
      "52-Week"           -> 1.0
      "2-Year 1-Month"    -> 2.0833 (sum of components)
      "5-Year 1-Month"    -> 5.0833
      "9-Year 10-Month"   -> 9.833 (TIPS reopenings often have odd terms)

    Returns None if no parseable tenor component is found.
    """
    if not security_term:
        return None
    s = security_term.strip()
    total = 0.0
    found = False
    for part in s.split():
        if "-" not in part:
            continue
        num_str, unit = part.split("-", 1)
        try:
            num = float(num_str)
        except ValueError:
            continue
        unit_lower = unit.lower().rstrip("s")
        if unit_lower == "year":
            total += num
        elif unit_lower == "month":
            total += num / 12.0
        elif unit_lower == "week":
            total += num / 52.0
        elif unit_lower == "day":
            total += num / 365.0
        else:
            continue
        found = True
    return total if found else None


def _matches_tenor(security_term: str, target_years: float, *, tolerance: float = 0.05) -> bool:
    """Check whether a securityTerm string matches a target tenor (in years).

    Used by `scrape_securities_api(tenor_years=...)` to filter records by
    canonical maturity. ±0.05y default tolerance handles odd reopening
    terms (e.g. "9-Year 10-Month" matches target 10).
    """
    parsed = _parse_tenor_years(security_term)
    if parsed is None:
        return False
    # Tighter match for sub-year tenors (Bills); looser for multi-year.
    tol = max(tolerance, target_years * 0.05) if target_years >= 1 else tolerance
    return abs(parsed - target_years) <= tol


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
                    timeout: int = 30, coerce: bool = True) -> Optional[Any]:
        """Fetch and parse JSON; return dict / list, or None on failure.

        Validity check uses `isinstance(data, (dict, list))` rather than
        parsing the status line (per the recommended pattern in
        `prism/gs-proxy.md` §6.4).

        With `coerce=True` (default), runs every record through
        `_coerce_record` so numeric fields come back as floats / ints
        rather than the strings TreasuryDirect's API returns. Pass
        `coerce=False` for the rare case where raw strings are needed.
        """
        resp = self._fetch(path, params=params, timeout=timeout)
        try:
            data = resp.json()
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if isinstance(data, (dict, list)):
            if coerce:
                _coerce_record(data)
            return data
        return None

    # ── Securities API ───────────────────────────────────────────────

    @staticmethod
    def _compute_tail(rec: dict) -> None:
        """Compute auction tail in bp; mutate `rec` in place.

        Delegates to the security-type-aware module helper `compute_tail`
        so Bills (discount-rate basis) and Notes/Bonds/TIPS/FRN (yield
        basis) both produce a meaningful tailBps. Per the doctrine,
        PRISM never has to remember which field-pair to use.
        """
        rec["tailBps"] = compute_tail(rec)

    def scrape_securities_api(self, *,
                              security_type: Optional[str] = None,
                              days: int = 365,
                              full_history: bool = False,
                              tenor_years: Optional[float] = None,
                              originals_only: bool = False,
                              reopenings_only: bool = False) -> List[Dict[str, Any]]:
        """Fetch auction history records from /TA_WS/securities/search.

        Returns a list of auction-record dicts with `tailBps` computed
        per `compute_tail` (security-type-aware). Records are sorted by
        `auctionDate` desc and have all numeric fields coerced to
        float / int per the boundary-coercion convention.

        Args:
            security_type:    One of `SECURITY_TYPES` or None for all.
            days:             Days back from today (ignored if
                              `full_history`).
            full_history:     If True, pulls from `FULL_HISTORY_START`.
            tenor_years:      If set, filter records by maturity tenor.
                              Matches by parsing `securityTerm` (e.g.
                              "10-Year", "2-Year 1-Month") into years.
                              Use 10 for 10Y notes, 2 for 2Y notes, 30
                              for 30Y bonds, 0.083 for 1-month bills,
                              etc.  Tolerance: ±0.05 years.
            originals_only:   If True, drop reopenings (`reopening` !=
                              "Yes"). Original issues only.
            reopenings_only:  If True, keep only reopenings.

        `originals_only` and `reopenings_only` address friction class E
        (10Y Notes are quarterly originals + monthly reopenings; PRISM
        doesn't have to filter post-hoc).

        `tenor_years` addresses friction "no documented selector for
        tenor" surfaced by the RBR subagent on prompt 10 (10-Year Note
        filtering).

        Internally chunks the date range to avoid the search endpoint's
        ~2000-record cap on wide ranges (Bill auctions especially).
        """
        if originals_only and reopenings_only:
            raise ValueError("Pass at most one of originals_only / reopenings_only.")
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

        if tenor_years is not None:
            all_combined = [r for r in all_combined if _matches_tenor(r.get("securityTerm", ""), tenor_years)]

        if originals_only:
            all_combined = [r for r in all_combined if (r.get("reopening") or "").strip().lower() != "yes"]
        elif reopenings_only:
            all_combined = [r for r in all_combined if (r.get("reopening") or "").strip().lower() == "yes"]

        return all_combined

    def last_n_auctions(self, *, security_type: str,
                        n: int = 5,
                        tenor_years: Optional[float] = None,
                        originals_only: bool = False) -> List[Dict[str, Any]]:
        """Fetch the most recent N completed auctions of a security type.

        TreasuryDirect's search endpoint is time-windowed (`days=N`) not
        count-bounded. PRISM should never have to guess "how many days
        back equals 5 Bill auctions?" — this helper does the right thing
        by widening the window until N records arrive (or the full
        history cap is hit).

        Args:
            security_type:   "Bill" / "Note" / "Bond" / "TIPS" / "FRN"
            n:               Number of most-recent auctions to return.
            tenor_years:     Optional tenor filter (see scrape_securities_api).
            originals_only:  Optional: exclude reopenings.

        Returns the N most recent records sorted auctionDate desc.
        Addresses friction class "Time window vs last N auctions" surfaced
        by the RBR subagent on prompts 14 and 10.
        """
        # Bills auction weekly+ so 90 days usually covers 5; Notes/Bonds need
        # wider windows. Start at 90 days; double until enough records or 5y cap.
        for window in (90, 180, 365, 730, 1825):
            recs = self.scrape_securities_api(
                security_type=security_type,
                days=window,
                tenor_years=tenor_years,
                originals_only=originals_only,
            )
            if len(recs) >= n:
                return recs[:n]
        # Last attempt with full history.
        recs = self.scrape_securities_api(
            security_type=security_type,
            full_history=True,
            tenor_years=tenor_years,
            originals_only=originals_only,
        )
        return recs[:n]

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
                         days: int = 30,
                         tenor_years: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetch announced auctions (upcoming, not yet held).

        TreasuryDirect's /announced endpoint returns the next round of
        scheduled auctions. Filter by security_type and return up to
        `days` ahead.

        `tenor_years` filters by canonical maturity (e.g. 10 for 10Y
        notes, 30 for 30Y bonds, 0.083 for 1-month bills) using
        `_matches_tenor` against `securityTerm`.
        """
        params: Dict[str, Any] = {"format": "json", "days": str(days)}
        if security_type:
            params["type"] = security_type
        data = self._fetch_json(_SECURITIES_PATHS["announced"], params=params)
        if not isinstance(data, list):
            return []
        if tenor_years is not None:
            data = [r for r in data if _matches_tenor(r.get("securityTerm", ""), tenor_years)]
        return data

    def scrape_auctioned(self, *, security_type: Optional[str] = None,
                         days: int = 30,
                         tenor_years: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetch recently-auctioned securities (results published).

        `tenor_years` filters by canonical maturity. Records have
        `tailBps` computed (security-type-aware).
        """
        params: Dict[str, Any] = {"format": "json", "days": str(days)}
        if security_type:
            params["type"] = security_type
        data = self._fetch_json(_SECURITIES_PATHS["auctioned"], params=params)
        if not isinstance(data, list):
            return []
        for rec in data:
            if isinstance(rec, dict):
                self._compute_tail(rec)
        if tenor_years is not None:
            data = [r for r in data if _matches_tenor(r.get("securityTerm", ""), tenor_years)]
        return data

    def next_n_announced(self, *, n: int = 10,
                         security_type: Optional[str] = None,
                         tenor_years: Optional[float] = None) -> List[Dict[str, Any]]:
        """Fetch the NEXT N upcoming announced auctions, expanding the
        search horizon as needed.

        TreasuryDirect's /announced endpoint is `days`-bounded; PRISM
        should never have to guess "how many days back captures the
        next 10 TIPS announcements?" — this helper widens the window
        until N records arrive.

        Sorted ascending by `auctionDate` (nearest first). Addresses
        friction class "scrape_announced days horizon" surfaced by the
        RBR subagent on prompt 12.
        """
        for window in (30, 60, 120, 240, 365, 730):
            recs = self.scrape_announced(
                days=window,
                security_type=security_type,
                tenor_years=tenor_years,
            )
            if len(recs) >= n:
                recs.sort(key=lambda r: r.get("auctionDate", ""))
                return recs[:n]
        # Best effort: return whatever we got at the widest window.
        recs = self.scrape_announced(days=730, security_type=security_type, tenor_years=tenor_years)
        recs.sort(key=lambda r: r.get("auctionDate", ""))
        return recs[:n]

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
