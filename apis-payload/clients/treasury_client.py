"""U.S. Treasury Fiscal Data API client (PRISM-side library module).

Library-only — no CLI surface. Sandbox-injected as `treasury_client` per
`prism/api-clients.md` §4. Imports `session_and_auth` from PRISM's
GS-proxy transport layer (`gs_app_proxy_negotiate.py`); in staging the
same import resolves to the local stub mirror at
`projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` so this
file runs identically in both environments.

Surface:
  Catalog       BASE_URL, CATEGORIES (8), ENDPOINT_REGISTRY (80+ endpoints),
                FILTER_OPERATORS (6 ops), SAMPLE_QUERIES (8 templates)
  Errors        FiscalDataError (http_status, api_error, api_message)
  Discovery     get_registry, list_keys(category), search_endpoints(q),
                get_manifest, get_examples
  Schema        discover_fields(key), discover_schema(key)
  Filters       filter_eq, filter_in, filter_gte, filter_gt, filter_lte,
                filter_lt, build_filter, filter_date_range
  Query         get_endpoint, query, request_page
  Getters       get_cusips, get_unique_cusips, get_full_cusip_universe,
                get_upcoming_auctions, get_record_setting_auctions,
                get_debt_to_penny, get_avg_interest_rates,
                get_rates_of_exchange, get_revenue_collections,
                get_mts_table, get_dts_table, get_buybacks,
                get_auctions_data

Base URL: https://api.fiscaldata.treasury.gov/services/api/fiscal_service
Docs: https://fiscaldata.treasury.gov/api-documentation/
Auth: none required (anonymous; routed through GS proxy in PRISM).
"""

from __future__ import annotations

import json
import time
import urllib.parse
from typing import Any, Callable, Optional

import requests

from ai_development.mcp.gs_app_proxy_negotiate import session_and_auth


BASE_URL = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


# Module-level transport caching (canonical pattern per prism/api-clients.md
# §3.1). Treasury follows the "no _USE_GS_PROXY flag" variant of the
# tri-modal pattern (per prism/gs-proxy.md §5.3): the import is assumed to
# succeed, and session_and_auth() is called lazily on first request.
_SESSION: Optional[requests.Session] = None
_AUTH: Any = None


def _get_session():
    """Return a cached (session, auth) pair. Builds on first call.

    In PRISM, session_and_auth() returns a Session with the
    KerberosProxyAuthAdapter mounted and HTTPKerberosAuth attached.
    In staging, the stub returns (vanilla requests.Session, None).
    Either way, callers do session.get(url, auth=auth, timeout=...)
    and the same code path works.
    """
    global _SESSION, _AUTH
    if _SESSION is None:
        _SESSION, _AUTH = session_and_auth()
    return _SESSION, _AUTH

__all__ = [
    "BASE_URL", "CATEGORIES", "ENDPOINT_REGISTRY", "FILTER_OPERATORS",
    "filter_eq", "filter_in", "filter_gte", "filter_gt", "filter_lte", "filter_lt",
    "build_filter", "filter_date_range",
    "get_registry", "list_keys", "get_manifest", "search_endpoints",
    "request_page", "discover_fields", "discover_schema",
    "get_endpoint", "query",
    "get_cusips", "get_unique_cusips", "get_full_cusip_universe", "get_upcoming_auctions", "get_record_setting_auctions",
    "get_debt_to_penny", "get_avg_interest_rates", "get_rates_of_exchange",
    "get_revenue_collections", "get_mts_table", "get_dts_table",
    "get_buybacks", "get_auctions_data",
    "get_examples", "FiscalDataError",
]

# API filter operators: eq, in, gte, gt, lte, lt. Format: field:op:value, multi: field:op:val,field2:op:val
FILTER_OPERATORS = ("eq", "in", "gte", "gt", "lte", "lt")

CATEGORIES = {
    "auctions": "Auction schedules, CUSIPs, record-setting auction data",
    "debt": "Debt to penny, outstanding, schedules, MSPD, TROR, TOP",
    "accounting": "MTS, DTS, financial reports, reconciliations",
    "interest_rates": "Average rates, exchange rates, yields",
    "securities": "Savings bonds, TreasuryDirect, SLGS, redemption tables",
    "revenue": "Revenue collections, tax receipts",
    "payments": "Judgment Fund, advances",
    "other": "Gold reserve, gift contributions, misc",
}

# Full endpoint registry: 80+ endpoints. date_field = primary date filter field for generic queries.
ENDPOINT_REGISTRY: dict[str, dict] = {
    # Auctions
    "upcoming_auctions": {"endpoint": "v1/accounting/od/upcoming_auctions", "table_name": "Treasury Securities Upcoming Auctions", "category": "auctions", "date_field": "record_date"},
    "record_setting_auction": {"endpoint": "v2/accounting/od/record_setting_auction", "table_name": "Record-Setting Auction", "category": "auctions"},
    "frn_daily_indexes": {"endpoint": "v1/accounting/od/frn_daily_indexes", "table_name": "FRN Daily Indexes", "category": "auctions", "date_field": "record_date"},
    # Debt
    "debt_to_penny": {"endpoint": "v2/accounting/od/debt_to_penny", "table_name": "Debt to the Penny", "category": "debt", "date_field": "record_date"},
    "debt_outstanding": {"endpoint": "v2/accounting/od/debt_outstanding", "table_name": "Historical Debt Outstanding", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt": {"endpoint": "v1/accounting/od/schedules_fed_debt", "table_name": "Schedules of Federal Debt by Month", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_fytd": {"endpoint": "v1/accounting/od/schedules_fed_debt_fytd", "table_name": "Schedules of Federal Debt Fiscal Year-to-Date", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_daily_activity": {"endpoint": "v1/accounting/od/schedules_fed_debt_daily_activity", "table_name": "Schedules of Federal Debt Daily Activity", "category": "debt", "date_field": "record_date"},
    "schedules_fed_debt_daily_summary": {"endpoint": "v1/accounting/od/schedules_fed_debt_daily_summary", "table_name": "Schedules of Federal Debt Daily Summary", "category": "debt", "date_field": "record_date"},
    "mspd_table_1": {"endpoint": "v1/debt/mspd/mspd_table_1", "table_name": "Summary of Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_2": {"endpoint": "v1/debt/mspd/mspd_table_2", "table_name": "Statutory Debt Limit", "category": "debt", "date_field": "record_date"},
    "mspd_table_3_market": {"endpoint": "v1/debt/mspd/mspd_table_3_market", "table_name": "Detail of Marketable Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_3_nonmarket": {"endpoint": "v1/debt/mspd/mspd_table_3_nonmarket", "table_name": "Detail of Non-Marketable Treasury Securities Outstanding", "category": "debt", "date_field": "record_date"},
    "mspd_table_4": {"endpoint": "v1/debt/mspd/mspd_table_4", "table_name": "MSPD Historical Data", "category": "debt", "date_field": "record_date"},
    "mspd_table_5": {"endpoint": "v1/debt/mspd/mspd_table_5", "table_name": "Holdings of Treasury Securities in Stripped Form", "category": "debt", "date_field": "record_date"},
    "tror": {"endpoint": "v2/debt/tror", "table_name": "Treasury Report on Receivables Full Data", "category": "debt"},
    "tror_collected_outstanding": {"endpoint": "v2/debt/tror/collected_outstanding_recv", "table_name": "Collected and Outstanding Receivables", "category": "debt"},
    "tror_delinquent_debt": {"endpoint": "v2/debt/tror/delinquent_debt", "table_name": "Delinquent Debt", "category": "debt"},
    "tror_collections_delinquent": {"endpoint": "v2/debt/tror/collections_delinquent_debt", "table_name": "Collections on Delinquent Debt", "category": "debt"},
    "tror_written_off": {"endpoint": "v2/debt/tror/written_off_delinquent_debt", "table_name": "Written Off Delinquent Debt", "category": "debt"},
    "tror_data_act_compliance": {"endpoint": "v2/debt/tror/data_act_compliance", "table_name": "120 Day Delinquent Debt Referral Compliance", "category": "debt"},
    "top_federal": {"endpoint": "v1/debt/top/top_federal", "table_name": "Treasury Offset Program - Federal Collections", "category": "debt"},
    "top_state": {"endpoint": "v1/debt/top/top_state", "table_name": "Treasury Offset Program - State Programs", "category": "debt"},
    "title_xii": {"endpoint": "v2/accounting/od/title_xii", "table_name": "Advances to State Unemployment Funds (SSA Title XII)", "category": "debt", "date_field": "record_date"},
    "interest_uninvested": {"endpoint": "v2/accounting/od/interest_uninvested", "table_name": "Federal Borrowings Program: Interest on Uninvested Funds", "category": "debt", "date_field": "record_date"},
    "interest_cost_fund": {"endpoint": "v2/accounting/od/interest_cost_fund", "table_name": "Federal Investments Program: Interest Cost by Fund", "category": "debt", "date_field": "record_date"},
    # Accounting - MTS
    "mts_table_1": {"endpoint": "v1/accounting/mts/mts_table_1", "table_name": "Summary of Receipts, Outlays, Deficit/Surplus", "category": "accounting", "date_field": "record_date"},
    "mts_table_2": {"endpoint": "v1/accounting/mts/mts_table_2", "table_name": "Summary of Budget and Off-Budget Results", "category": "accounting", "date_field": "record_date"},
    "mts_table_3": {"endpoint": "v1/accounting/mts/mts_table_3", "table_name": "Summary of Receipts and Outlays", "category": "accounting", "date_field": "record_date"},
    "mts_table_4": {"endpoint": "v1/accounting/mts/mts_table_4", "table_name": "Receipts of the U.S. Government", "category": "accounting", "date_field": "record_date"},
    "mts_table_5": {"endpoint": "v1/accounting/mts/mts_table_5", "table_name": "Outlays of the U.S. Government", "category": "accounting", "date_field": "record_date"},
    "mts_table_6": {"endpoint": "v1/accounting/mts/mts_table_6", "table_name": "Means of Financing the Deficit", "category": "accounting", "date_field": "record_date"},
    "mts_table_6a": {"endpoint": "v1/accounting/mts/mts_table_6a", "table_name": "Analysis of Change in Excess of Liabilities", "category": "accounting", "date_field": "record_date"},
    "mts_table_6b": {"endpoint": "v1/accounting/mts/mts_table_6b", "table_name": "Securities Issued by Federal Agencies", "category": "accounting", "date_field": "record_date"},
    "mts_table_6c": {"endpoint": "v1/accounting/mts/mts_table_6c", "table_name": "Federal Agency Borrowing via Treasury Securities", "category": "accounting", "date_field": "record_date"},
    "mts_table_6d": {"endpoint": "v1/accounting/mts/mts_table_6d", "table_name": "Investments of Federal Government Accounts", "category": "accounting", "date_field": "record_date"},
    "mts_table_6e": {"endpoint": "v1/accounting/mts/mts_table_6e", "table_name": "Guaranteed and Direct Loan Financing", "category": "accounting", "date_field": "record_date"},
    "mts_table_7": {"endpoint": "v1/accounting/mts/mts_table_7", "table_name": "Receipts and Outlays by Month", "category": "accounting", "date_field": "record_date"},
    "mts_table_8": {"endpoint": "v1/accounting/mts/mts_table_8", "table_name": "Trust Fund Impact on Budget Results", "category": "accounting", "date_field": "record_date"},
    "mts_table_9": {"endpoint": "v1/accounting/mts/mts_table_9", "table_name": "Receipts by Source, Outlays by Function", "category": "accounting", "date_field": "record_date"},
    # Accounting - DTS
    "dts_table_1": {"endpoint": "v1/accounting/dts/dts_table_1", "table_name": "Operating Cash Balance", "category": "accounting", "date_field": "record_date"},
    "dts_table_2": {"endpoint": "v1/accounting/dts/dts_table_2", "table_name": "Deposits and Withdrawals of Operating Cash", "category": "accounting", "date_field": "record_date"},
    "dts_table_3a": {"endpoint": "v1/accounting/dts/dts_table_3a", "table_name": "Public Debt Transactions", "category": "accounting", "date_field": "record_date"},
    "dts_table_3b": {"endpoint": "v1/accounting/dts/dts_table_3b", "table_name": "Adjustment of Public Debt to Cash Basis", "category": "accounting", "date_field": "record_date"},
    "dts_table_3c": {"endpoint": "v1/accounting/dts/dts_table_3c", "table_name": "Debt Subject to Limit", "category": "accounting", "date_field": "record_date"},
    "dts_table_4": {"endpoint": "v1/accounting/dts/dts_table_4", "table_name": "Federal Tax Deposits (Inter-agency Tax Transfers)", "category": "accounting", "date_field": "record_date"},
    "dts_table_5": {"endpoint": "v1/accounting/dts/dts_table_5", "table_name": "Short-Term Cash Investments", "category": "accounting", "date_field": "record_date"},
    "dts_table_6": {"endpoint": "v1/accounting/dts/dts_table_6", "table_name": "Income Tax Refunds Issued", "category": "accounting", "date_field": "record_date"},
    # Accounting - Financial Report
    "statement_net_cost": {"endpoint": "v2/accounting/od/statement_net_cost", "table_name": "Statements of Net Cost", "category": "accounting", "date_field": "record_date"},
    "net_position": {"endpoint": "v1/accounting/od/net_position", "table_name": "Statements of Operations and Changes in Net Position", "category": "accounting", "date_field": "record_date"},
    "reconciliations": {"endpoint": "v1/accounting/od/reconciliations", "table_name": "Reconciliations of Net Operating Cost", "category": "accounting", "date_field": "record_date"},
    "cash_balance": {"endpoint": "v1/accounting/od/cash_balance", "table_name": "Statements of Changes in Cash Balance", "category": "accounting", "date_field": "record_date"},
    "balance_sheets": {"endpoint": "v2/accounting/od/balance_sheets", "table_name": "Balance Sheets", "category": "accounting", "date_field": "record_date"},
    "long_term_projections": {"endpoint": "v1/accounting/od/long_term_projections", "table_name": "Statements of Long-Term Fiscal Projections", "category": "accounting", "date_field": "record_date"},
    "social_insurance": {"endpoint": "v1/accounting/od/social_insurance", "table_name": "Statements of Social Insurance", "category": "accounting", "date_field": "record_date"},
    "insurance_amounts": {"endpoint": "v1/accounting/od/insurance_amounts", "table_name": "Statements of Changes in Social Insurance Amounts", "category": "accounting", "date_field": "record_date"},
    # Interest rates
    "avg_interest_rates": {"endpoint": "v2/accounting/od/avg_interest_rates", "table_name": "Average Interest Rates on U.S. Treasury Securities", "category": "interest_rates", "date_field": "record_date"},
    "rates_of_exchange": {"endpoint": "v1/accounting/od/rates_of_exchange", "table_name": "Treasury Reporting Rates of Exchange", "category": "interest_rates", "date_field": "record_date"},
    "interest_expense": {"endpoint": "v2/accounting/od/interest_expense", "table_name": "Interest Expense on the Public Debt Outstanding", "category": "interest_rates", "date_field": "record_date"},
    "qualified_tax": {"endpoint": "v2/accounting/od/qualified_tax", "table_name": "Historical Qualified Tax Credit Bond Interest Rates", "category": "interest_rates", "date_field": "record_date"},
    "utf_qtr_yields": {"endpoint": "v2/accounting/od/utf_qtr_yields", "table_name": "Unemployment Trust Fund Quarterly Yields", "category": "interest_rates", "date_field": "record_date"},
    # Securities
    "redemption_tables": {"endpoint": "v2/accounting/od/redemption_tables", "table_name": "Accrual Savings Bonds Redemption Tables", "category": "securities"},
    "slgs_statistics": {"endpoint": "v2/accounting/od/slgs_statistics", "table_name": "Monthly SLGS Securities Program", "category": "securities", "date_field": "record_date"},
    "slgs_savings_bonds": {"endpoint": "v1/accounting/od/slgs_savings_bonds", "table_name": "Savings Bonds Securities Sold", "category": "securities", "date_field": "record_date"},
    "sb_value": {"endpoint": "v2/accounting/od/sb_value", "table_name": "Savings Bonds Value Files", "category": "securities"},
    "slgs_securities": {"endpoint": "v1/accounting/od/slgs_securities", "table_name": "State and Local Government Series Securities", "category": "securities", "date_field": "record_date"},
    "securities_sales": {"endpoint": "v1/accounting/od/securities_sales", "table_name": "Securities Issued in TreasuryDirect - Sales", "category": "securities", "date_field": "record_date"},
    "securities_sales_term": {"endpoint": "v1/accounting/od/securities_sales_term", "table_name": "Securities Sales by Term", "category": "securities", "date_field": "record_date"},
    "securities_transfers": {"endpoint": "v1/accounting/od/securities_transfers", "table_name": "Transfers of Marketable Securities", "category": "securities", "date_field": "record_date"},
    "securities_conversions": {"endpoint": "v1/accounting/od/securities_conversions", "table_name": "Conversions of Paper Savings Bonds", "category": "securities", "date_field": "record_date"},
    "securities_redemptions": {"endpoint": "v1/accounting/od/securities_redemptions", "table_name": "Securities Redemptions", "category": "securities", "date_field": "record_date"},
    "securities_outstanding": {"endpoint": "v1/accounting/od/securities_outstanding", "table_name": "Securities Outstanding", "category": "securities", "date_field": "record_date"},
    "securities_c_of_i": {"endpoint": "v1/accounting/od/securities_c_of_i", "table_name": "Certificates of Indebtedness", "category": "securities", "date_field": "record_date"},
    "securities_accounts": {"endpoint": "v1/accounting/od/securities_accounts", "table_name": "Securities Accounts", "category": "securities", "date_field": "record_date"},
    "savings_bonds_report": {"endpoint": "v1/accounting/od/savings_bonds_report", "table_name": "Paper Savings Bonds Issues, Redemptions, Maturities by Series", "category": "securities", "date_field": "record_date"},
    "savings_bonds_mud": {"endpoint": "v1/accounting/od/savings_bonds_mud", "table_name": "Matured Unredeemed Debt", "category": "securities", "date_field": "record_date"},
    "savings_bonds_pcs": {"endpoint": "v1/accounting/od/savings_bonds_pcs", "table_name": "Piece Information by Series", "category": "securities", "date_field": "record_date"},
    # Revenue
    "revenue_collections": {"endpoint": "v2/revenue/rcm", "table_name": "U.S. Government Revenue Collections", "category": "revenue", "date_field": "record_date"},
    # Payments
    "jfics_congress_report": {"endpoint": "v2/payments/jfics/jfics_congress_report", "table_name": "Judgment Fund: Annual Report to Congress", "category": "payments", "date_field": "record_date"},
    # Buybacks
    "buybacks_operations": {"endpoint": "v1/accounting/od/buybacks_operations", "table_name": "Treasury Securities Buyback Operations", "category": "auctions", "date_field": "operation_date"},
    # Auctions (full auction data)
    "auctions_query": {"endpoint": "v1/accounting/od/auctions_query", "table_name": "Treasury Securities Auctions Data", "category": "auctions", "date_field": "record_date"},
    # Other
    "gold_reserve": {"endpoint": "v2/accounting/od/gold_reserve", "table_name": "U.S. Treasury-Owned Gold", "category": "other", "date_field": "record_date"},
    "gift_contributions": {"endpoint": "v2/accounting/od/gift_contributions", "table_name": "Gift Contributions to Reduce the Public Debt", "category": "other", "date_field": "record_date"},
}


class FiscalDataError(Exception):
    """Raised when the Fiscal Data API returns an error or request fails."""
    def __init__(self, message: str, *, http_status: Optional[int] = None, api_error: Optional[str] = None, api_message: Optional[str] = None):
        super().__init__(message)
        self.http_status = http_status
        self.api_error = api_error
        self.api_message = api_message


def get_registry() -> dict[str, dict]:
    """Return full endpoint registry. LLM can inspect keys, categories, date_field, table_name."""
    return dict(ENDPOINT_REGISTRY)


def list_keys(category: Optional[str] = None) -> list[str]:
    """List endpoint keys. category: auctions|debt|accounting|interest_rates|securities|revenue|payments|other."""
    if category:
        if category not in CATEGORIES:
            raise ValueError(f"Unknown category: {category}. Valid: {list(CATEGORIES.keys())}")
        return sorted(k for k, v in ENDPOINT_REGISTRY.items() if v.get("category") == category)
    return sorted(ENDPOINT_REGISTRY.keys())


def search_endpoints(q: str) -> list[dict[str, Any]]:
    """Search endpoints by key or table_name. Returns list of {key, table_name, category, endpoint}."""
    q = q.lower()
    out = []
    for key, info in ENDPOINT_REGISTRY.items():
        if q in key.lower() or q in info.get("table_name", "").lower():
            out.append({"key": key, "table_name": info["table_name"], "category": info.get("category", ""), "endpoint": info["endpoint"]})
    return out


SAMPLE_QUERIES: list[dict[str, Any]] = [
    {"desc": "Debt to penny, recent 10 rows", "key": "debt_to_penny", "fields": ["record_date", "tot_pub_debt_out_amt"], "sort": "-record_date", "max_rows": 10},
    {"desc": "MTS table 9, line 120 (receipts total)", "key": "mts_table_9", "filter": "line_code_nbr:eq:120", "fields": ["record_date", "classification_desc", "current_month_rcpt_outly_amt"]},
    {"desc": "Exchange rates Canada/Mexico 2024", "key": "rates_of_exchange", "filter": "country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2024-01-01", "fields": ["country_currency_desc", "exchange_rate", "record_date"]},
    {"desc": "Revenue collections by tax category", "key": "revenue_collections", "filter": "tax_category_id:eq:3", "fields": ["record_date", "net_collections_amt", "tax_category_desc"]},
    {"desc": "Average interest rates, Bills only", "key": "avg_interest_rates", "filter": "security_desc:eq:Treasury Bills", "fields": ["record_date", "security_desc", "avg_interest_rate_amt"]},
    {"desc": "CUSIPs for upcoming TIPS auctions", "key": "upcoming_auctions", "filter": "security_type:eq:TIPS", "fields": ["cusip", "auction_date", "offering_amt"]},
    {"desc": "DTS operating cash balance", "key": "dts_table_1", "fields": ["record_date", "account_type", "close_today_bal", "open_today_bal"]},
    {"desc": "Gold reserve", "key": "gold_reserve", "fields": ["record_date", "fine_troy_oz", "book_value_amt"]},
]


def get_examples() -> list[dict[str, Any]]:
    """Return sample query patterns. LLM can adapt these for its needs."""
    return list(SAMPLE_QUERIES)


def get_manifest() -> dict[str, Any]:
    """Full manifest for LLM: categories, endpoints by category, filter format, base URL."""
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for key, info in ENDPOINT_REGISTRY.items():
        cat = info.get("category", "other")
        by_cat.setdefault(cat, []).append({"key": key, "table_name": info["table_name"], "endpoint": info["endpoint"], "date_field": info.get("date_field")})
    return {
        "base_url": BASE_URL,
        "categories": dict(CATEGORIES),
        "endpoints_by_category": by_cat,
        "filter_format": "field:op:value; ops: eq,in,gte,gt,lte,lt; multi: field:op:val,field2:op:val",
        "date_format": "YYYY-MM-DD",
        "total_endpoints": len(ENDPOINT_REGISTRY),
    }


def _build_url(endpoint: str, *, fields: Optional[list[str]] = None, filter_expr: Optional[str] = None, sort: Optional[str] = None, page_number: int = 1, page_size: int = 100) -> str:
    params: dict[str, str] = {"format": "json", "page[number]": str(page_number), "page[size]": str(page_size)}
    if fields:
        params["fields"] = ",".join(fields)
    if filter_expr:
        params["filter"] = filter_expr
    if sort:
        params["sort"] = sort
    return f"{BASE_URL}/{endpoint.lstrip('/')}?{urllib.parse.urlencode(params)}"


def _request(endpoint: str, *, fields: Optional[list[str]] = None, filter_expr: Optional[str] = None, sort: Optional[str] = None, page_number: int = 1, page_size: int = 100, timeout: float = 30.0) -> dict[str, Any]:
    url = _build_url(endpoint, fields=fields, filter_expr=filter_expr, sort=sort, page_number=page_number, page_size=page_size)
    session, auth = _get_session()
    try:
        resp = session.get(url, auth=auth, timeout=timeout, headers={"Accept": "application/json"})
    except requests.exceptions.RequestException as e:
        raise FiscalDataError(f"Request failed: {e}")
    if resp.status_code >= 400:
        try:
            err_body = resp.json()
            msg = err_body.get("message", err_body.get("error", f"HTTP {resp.status_code}"))
        except Exception:
            msg = f"HTTP {resp.status_code}: {resp.reason}"
        raise FiscalDataError(msg, http_status=resp.status_code)
    try:
        out = resp.json()
    except Exception as e:
        raise FiscalDataError(f"Invalid JSON response: {e}")
    if "error" in out:
        raise FiscalDataError(
            out.get("message", out.get("error", "API error")),
            api_error=str(out.get("error", "")),
            api_message=str(out.get("message", "")),
        )
    return out


def _fetch_all_pages(
    endpoint: str,
    *,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    progress_callback: Optional[Callable[[int, int, int], None]] = None,
) -> list[dict[str, Any]]:
    all_data: list[dict[str, Any]] = []
    page, total_pages = 1, 1
    last_progress_time = 0.0
    while page <= total_pages:
        resp = _request(endpoint, fields=fields, filter_expr=filter_expr, sort=sort, page_number=page, page_size=page_size)
        all_data.extend(resp.get("data", []))
        total_pages = resp.get("meta", {}).get("total-pages", 1)
        if progress_callback and (page == 1 or time.monotonic() - last_progress_time >= 5.0):
            progress_callback(len(all_data), page, total_pages)
            last_progress_time = time.monotonic()
        if max_pages and page >= max_pages:
            break
        if page >= total_pages:
            break
        page += 1
    return all_data


def _get_endpoint_path(key: str) -> str | None:
    info = ENDPOINT_REGISTRY.get(key)
    return info["endpoint"] if info else None


# --- Filter utilities (LLM-friendly) ---

def filter_eq(field: str, value: str) -> str:
    """Build filter: field equals value. Example: filter_eq('security_type', 'Bill')"""
    return f"{field}:eq:{value}"


def filter_in(field: str, values: list[str]) -> str:
    """Build filter: field in set. Example: filter_in('country_currency_desc', ['Canada-Dollar','Mexico-Peso'])"""
    return f"{field}:in:({','.join(values)})"


def filter_gte(field: str, value: str) -> str:
    """Build filter: field >= value. Example: filter_gte('record_date', '2024-01-01')"""
    return f"{field}:gte:{value}"


def filter_gt(field: str, value: str) -> str:
    """Build filter: field > value."""
    return f"{field}:gt:{value}"


def filter_lte(field: str, value: str) -> str:
    """Build filter: field <= value."""
    return f"{field}:lte:{value}"


def filter_lt(field: str, value: str) -> str:
    """Build filter: field < value."""
    return f"{field}:lt:{value}"


def build_filter(*clauses: str) -> str:
    """Combine filter clauses with comma. Example: build_filter(filter_gte('record_date','2024-01-01'), filter_eq('security_type','Bill'))"""
    return ",".join(c for c in clauses if c)


def filter_date_range(field: str, from_date: Optional[str] = None, to_date: Optional[str] = None) -> str:
    """Build date range filter. Returns combined clause or empty string."""
    clauses = []
    if from_date:
        clauses.append(filter_gte(field, from_date))
    if to_date:
        clauses.append(filter_lte(field, to_date))
    return build_filter(*clauses) if clauses else ""


def request_page(
    key: str,
    *,
    page_number: int = 1,
    page_size: int = 100,
    fields: Optional[list[str]] = None,
    filter_expr: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch a single page. Returns full API response (data + meta + links). Use for slicing or exploring."""
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}")
    return _request(
        info["endpoint"],
        fields=fields,
        filter_expr=filter_expr,
        sort=sort,
        page_number=page_number,
        page_size=page_size,
    )


def discover_fields(key: str, *, sample_filter: Optional[str] = None) -> list[str]:
    """Fetch one row and return field names for the endpoint. Helps LLM choose fields for queries."""
    schema = discover_schema(key, sample_filter=sample_filter)
    return schema["fields"]


def discover_schema(key: str, *, sample_filter: Optional[str] = None) -> dict[str, Any]:
    """Fetch schema: fields, labels (display names), dataTypes. Use for building queries."""
    resp = request_page(key, page_size=1, filter_expr=sample_filter)
    rows = resp.get("data", [])
    meta = resp.get("meta", {})
    labels = meta.get("labels", {}) or {}
    data_types = meta.get("dataTypes", {}) or {}
    if rows:
        fields = list(rows[0].keys())
    else:
        fields = list(labels.keys()) if labels else []
    return {
        "key": key,
        "fields": fields,
        "labels": labels,
        "dataTypes": data_types,
    }


def get_endpoint(
    key: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
    use_date_filters: bool = True,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """
    Generic fetcher for any registered endpoint.
    - filter_expr: Raw API filter (field:op:value). Combined with date filters unless use_date_filters=False.
    - page_number: If set, fetch only that page (1-based). Ignores max_pages.
    - use_date_filters: If False, from_date/to_date are ignored; use filter_expr for full control.
    """
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}. Available: {list(ENDPOINT_REGISTRY.keys())}")
    endpoint = info["endpoint"]
    filters: list[str] = []
    if filter_expr:
        filters.append(filter_expr)
    if use_date_filters:
        date_field = info.get("date_field")
        if date_field and from_date:
            filters.append(f"{date_field}:gte:{from_date}")
        if date_field and to_date:
            filters.append(f"{date_field}:lte:{to_date}")
    combined_filter = ",".join(filters) if filters else None
    default_sort = f"-{info.get('date_field', 'record_date')}" if info.get("date_field") and not sort else sort

    if page_number is not None:
        resp = _request(endpoint, fields=fields, filter_expr=combined_filter, sort=default_sort, page_number=page_number, page_size=page_size)
        return resp.get("data", [])

    def _progress(n: int, p: int, total: int) -> None:
        print(f"  Fetched {n} rows (page {p}/{total})...", flush=True)

    return _fetch_all_pages(
        endpoint,
        fields=fields,
        filter_expr=combined_filter,
        sort=default_sort,
        page_size=page_size,
        max_pages=max_pages,
        progress_callback=_progress if show_progress else None,
    )


def query(
    key: str,
    *,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_number: Optional[int] = None,
    page_size: int = 100,
    max_rows: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    use_date_filters: bool = True,
) -> dict[str, Any]:
    """
    Maximum-flexibility query. Returns dict with 'data' and optionally 'meta'.
    - page_number: Fetch single page (1-based).
    - max_rows: Cap total rows when paginating (stops after enough rows).
    - All filter/sort/field params passed through to API.
    """
    info = ENDPOINT_REGISTRY.get(key)
    if not info:
        raise ValueError(f"Unknown endpoint key: {key}")
    filters: list[str] = []
    if filter_expr:
        filters.append(filter_expr)
    if use_date_filters and info.get("date_field"):
        df = info["date_field"]
        if from_date:
            filters.append(f"{df}:gte:{from_date}")
        if to_date:
            filters.append(f"{df}:lte:{to_date}")
    comb = ",".join(filters) if filters else None
    default_sort = f"-{info.get('date_field', 'record_date')}" if info.get("date_field") and not sort else sort

    if page_number is not None:
        resp = _request(info["endpoint"], fields=fields, filter_expr=comb, sort=default_sort or "-record_date", page_number=page_number, page_size=page_size)
        return {"data": resp.get("data", []), "meta": resp.get("meta", {})}

    all_rows: list[dict[str, Any]] = []
    page = 1
    last_resp: dict[str, Any] = {}
    while True:
        resp = _request(info["endpoint"], fields=fields, filter_expr=comb, sort=default_sort or "-record_date", page_number=page, page_size=page_size)
        last_resp = resp
        rows = resp.get("data", [])
        all_rows.extend(rows)
        total_pages = resp.get("meta", {}).get("total-pages", 1)
        if max_rows and len(all_rows) >= max_rows:
            all_rows = all_rows[:max_rows]
            break
        if page >= total_pages or not rows:
            break
        page += 1
    return {"data": all_rows, "meta": last_resp.get("meta", {})}


def get_cusips(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """CUSIPs from upcoming auctions. Pass filter_expr for arbitrary API filters."""
    endpoint = _get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    flds = fields or ["cusip", "security_type", "security_term", "auction_date", "issue_date", "offering_amt", "reopening"]
    return _fetch_all_pages(endpoint, fields=flds, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_unique_cusips(*, security_type: Optional[str] = None, from_date: Optional[str] = None, to_date: Optional[str] = None) -> list[str]:
    rows = get_cusips(security_type=security_type, from_date=from_date, to_date=to_date)
    return sorted(set(r.get("cusip") for r in rows if r.get("cusip")))


def get_full_cusip_universe(
    *,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    show_progress: bool = False,
) -> list[str]:
    """
    Full CUSIP universe via API: union of upcoming_auctions + frn_daily_indexes.
    Treasury Securities Auctions Data (historical 1979-present) has no public API endpoint;
    this combines all CUSIP-exposing endpoints to maximize coverage.
    """
    cusips: set[str] = set()
    endpoints_with_cusip = [
        ("upcoming_auctions", ["cusip", "security_type", "security_term", "auction_date", "issue_date"]),
        ("frn_daily_indexes", ["cusip", "frn", "original_issue_date"]),
    ]
    for key, fields in endpoints_with_cusip:
        ep = _get_endpoint_path(key)
        if not ep:
            continue
        def _progress(label: str):
            def cb(n: int, p: int, t: int) -> None:
                print(f"  {label}: {n} rows (page {p}/{t})...", flush=True)
            return cb
        rows = _fetch_all_pages(
            ep,
            fields=fields,
            page_size=page_size,
            max_pages=max_pages,
            progress_callback=_progress(key) if show_progress else None,
        )
        for r in rows:
            if r.get("cusip"):
                cusips.add(r["cusip"])
    return sorted(cusips)


def get_upcoming_auctions(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Upcoming auctions. Pass filter_expr for arbitrary filters (e.g. auction_date:gte:2024-01-01)."""
    endpoint = _get_endpoint_path("upcoming_auctions")
    if not endpoint:
        raise ValueError("upcoming_auctions endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"auction_date:gte:{from_date}")
    if to_date:
        filters.append(f"auction_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_record_setting_auctions(
    *,
    security_type: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 100,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Record-setting auctions. Pass filter_expr for additional filters."""
    endpoint = _get_endpoint_path("record_setting_auction")
    if not endpoint:
        raise ValueError("record_setting_auction endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort, page_size=page_size, max_pages=max_pages)


def get_debt_to_penny(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Debt to the Penny. Pass filter_expr for arbitrary filters, fields to select columns."""
    return get_endpoint(
        "debt_to_penny",
        from_date=from_date,
        to_date=to_date,
        filter_expr=filter_expr,
        fields=fields,
        sort=sort or "-record_date",
        page_size=page_size,
        max_pages=max_pages,
        page_number=page_number,
    )


# avg_interest_rates uses `security_desc` for "Treasury Bills" / "Treasury
# Notes" etc., NOT `security_type`. This map lets callers pass the canonical
# short name (Bill / Note / Bond / TIPS / FRN) and the wrapper translates to
# the correct API field+value.
_AVG_RATES_SECURITY_DESC = {
    "Bill":  "Treasury Bills",
    "Note":  "Treasury Notes",
    "Bond":  "Treasury Bonds",
    "TIPS":  "Treasury Inflation-Protected Securities (TIPS)",
    "FRN":   "Treasury Floating Rate Notes (FRN)",
}


def get_avg_interest_rates(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Average interest rates on Treasury securities.

    `security_type` accepts the canonical short alias (Bill / Note / Bond /
    TIPS / FRN). Internally translates to the API's `security_desc:eq:Treasury
    <X>` filter — the avg_interest_rates endpoint does NOT have a `security_type`
    field. Pass `filter_expr` instead for any other filter shape.
    """
    endpoint = _get_endpoint_path("avg_interest_rates")
    if not endpoint:
        raise ValueError("avg_interest_rates endpoint not in registry")
    filters = []
    if security_type:
        sec_desc = _AVG_RATES_SECURITY_DESC.get(security_type, security_type)
        filters.append(f"security_desc:eq:{sec_desc}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages)


def get_rates_of_exchange(
    *,
    country_currency: Optional[list[str]] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Exchange rates. Pass filter_expr for arbitrary filters (e.g. country_currency_desc:in:(...))."""
    endpoint = _get_endpoint_path("rates_of_exchange")
    if not endpoint:
        raise ValueError("rates_of_exchange endpoint not in registry")
    filters = []
    if country_currency:
        filters.append(f"country_currency_desc:in:({','.join(country_currency)})")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages)


def get_revenue_collections(
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Revenue collections. Pass filter_expr (e.g. tax_category_id:eq:3) or fields for specific columns."""
    return get_endpoint(
        "revenue_collections",
        from_date=from_date,
        to_date=to_date,
        filter_expr=filter_expr,
        fields=fields,
        sort=sort or "-record_date",
        page_size=page_size,
        max_pages=max_pages,
        page_number=page_number,
    )


def get_mts_table(
    table: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch MTS table. table: 1-9, 6a, 6b, 6c, 6d, 6e. filter_expr e.g. line_code_nbr:eq:120 for specific line."""
    key = f"mts_table_{table}"
    if key not in ENDPOINT_REGISTRY:
        raise ValueError(f"Unknown MTS table: {table}. Valid: 1-9, 6a, 6b, 6c, 6d, 6e")
    return get_endpoint(key, from_date=from_date, to_date=to_date, filter_expr=filter_expr, fields=fields, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages, page_number=page_number)


def get_dts_table(
    table: str,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
    page_number: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Fetch DTS table. table: 1-6, 3a, 3b, 3c. filter_expr for account_type, etc."""
    key = f"dts_table_{table}"
    if key not in ENDPOINT_REGISTRY:
        raise ValueError(f"Unknown DTS table: {table}. Valid: 1-6, 3a, 3b, 3c")
    return get_endpoint(key, from_date=from_date, to_date=to_date, filter_expr=filter_expr, fields=fields, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages, page_number=page_number)


def get_buybacks(
    *,
    operation_type: Optional[str] = None,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    with_results_only: bool = False,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Treasury buyback operations. operation_type: 'Cash Management'|'Liquidity Support'. security_type: 'Nominal Coupons'|'TIPS'."""
    endpoint = _get_endpoint_path("buybacks_operations")
    if not endpoint:
        raise ValueError("buybacks_operations endpoint not in registry")
    filters = []
    if operation_type:
        filters.append(f"operation_type:eq:{operation_type}")
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"operation_date:gte:{from_date}")
    if to_date:
        filters.append(f"operation_date:lte:{to_date}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    rows = _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-operation_date", page_size=page_size, max_pages=max_pages)
    if with_results_only:
        rows = [r for r in rows if r.get("total_par_amt_accepted") and r["total_par_amt_accepted"] != "null"]
    return rows


def get_auctions_data(
    *,
    security_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    cusip: Optional[str] = None,
    filter_expr: Optional[str] = None,
    fields: Optional[list[str]] = None,
    sort: Optional[str] = None,
    page_size: int = 1000,
    max_pages: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Treasury securities auction data (bills, notes, bonds, TIPS, FRN). Includes pricing, rates, bid-to-cover."""
    endpoint = _get_endpoint_path("auctions_query")
    if not endpoint:
        raise ValueError("auctions_query endpoint not in registry")
    filters = []
    if security_type:
        filters.append(f"security_type:eq:{security_type}")
    if from_date:
        filters.append(f"record_date:gte:{from_date}")
    if to_date:
        filters.append(f"record_date:lte:{to_date}")
    if cusip:
        filters.append(f"cusip:eq:{cusip}")
    if filter_expr:
        filters.append(filter_expr)
    fe = ",".join(filters) if filters else None
    return _fetch_all_pages(endpoint, fields=fields, filter_expr=fe, sort=sort or "-record_date", page_size=page_size, max_pages=max_pages)

