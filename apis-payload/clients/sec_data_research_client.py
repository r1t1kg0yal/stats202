"""SEC Data & Research scraper client (PRISM-side library module).

Sandbox-injected as ``sec_data_research_client``. Covers the structured
datasets, investment-management statistics, and visualization backing
data published at https://www.sec.gov/data-research — the DERA Data
Library (Form N-MFP, N-PORT, 13F, Form D, financial statement sets,
insider transactions, market-structure, etc.), Division of Investment
Management reports (Form PF / private-fund statistics, investment-adviser
statistics, MMF statistics, registered-fund statistics), and the
statistics/visualization gallery pages.

This is deliberately separate from ``sec_edgar_client`` (EDGAR filings,
XBRL company facts, full-text search). Use this client for aggregated /
structured SEC research datasets that are downloaded as ZIP/CSV/XLSX/XML
from sec.gov/data-research pages.

Transport: Bucket B (``manual_https_request``) — same header-contamination
issue as ``sec_edgar_client`` on www.sec.gov.

Surface (module-level aliases mirror the class):
  catalog(section, query)           -> dataset page index (200 pages)
  describe(slug_or_alias)           -> one dataset + live-scraped downloads
  list_files(slug, kind)            -> download URLs (data | docs | all)
  latest(slug, ext)                 -> newest data-file URL for a dataset
  download(slug, dest_dir, ...)     -> scrape + store files locally
  get(slug, file, member, ...)      -> fetch + parse latest (or named) file
  sync(section, dest_dir, ...)      -> batch download a whole section
  sync_universe(cluster, dry_run)   -> plan or run full-universe sync
  plan_sync(...)                    -> dry-run manifest (no downloads)
  cluster(name)                     -> themed subset (form_pf_adjacent, ...)
  summary()                         -> universe counts by section/cluster
  refresh_catalog()                 -> re-crawl page index from sec.gov
  interactive_menu()                -> nested CLI (default when run bare)
  to_dataframe(rows)                -> pandas helper

Default local store (staging demos): ``projects/apis/dev/data/sec_data_research/store/``
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union
from urllib.parse import urljoin, urlparse

# Staging path bootstrap so ``python sec_data_research_client.py`` works
# from apis-payload/clients/ without a harness (PRISM injects paths instead).
_HERE = Path(__file__).resolve()
_APIS_ROOT = _HERE.parents[2]
for _p in (_APIS_ROOT, _APIS_ROOT / "apis-payload" / "clients"):
    _s = str(_p)
    if _s not in sys.path:
        sys.path.insert(0, _s)

import requests

from ai_development.mcp.gs_app_proxy_negotiate import manual_https_request


__all__ = [
    "SecDataResearchError",
    "BASE_URL",
    "SECTIONS",
    "ALIASES",
    "CLUSTERS",
    "ROUTING",
    "DEFAULT_STORE",
    "PAGE_CATALOG",
    "SecDataResearchClient",
    "client",
    "catalog",
    "describe",
    "list_files",
    "latest",
    "download",
    "get",
    "sync",
    "sync_universe",
    "plan_sync",
    "summary",
    "cluster",
    "refresh_catalog",
    "to_dataframe",
    "interactive_menu",
    "main",
]

BASE_URL = "https://www.sec.gov"
BASE_HOST = "www.sec.gov"
USER_AGENT = "paper2md-sec-data-research/1.0 (research@example.com)"
RATE_LIMIT_SECONDS = 0.11

SECTIONS = ("data_library", "investment_management", "statistics", "other")

DEFAULT_STORE = Path(__file__).resolve().parents[2] / "dev/data/sec_data_research/store"

DOWNLOAD_EXT = (".zip", ".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".xml", ".pdf")
DATA_PATH_MARKERS = (
    "/files/data/",
    "/files/dera/",
    "/files/structureddata/",
    "/files/investment/",
    "/files/datastandardsinnovation/",
)

# Common slug aliases (lowercase keys).
ALIASES: Dict[str, str] = {
    # Form PF / private funds
    "form_pf": "division-investment-management-private-fund-statistics",
    "private_funds": "division-investment-management-private-fund-statistics",
    "private_fund_statistics": "division-investment-management-private-fund-statistics",
    "pf_statistics": "division-investment-management-private-fund-statistics",
    # Investment advisers
    "investment_adviser_statistics": "division-investment-management-investment-adviser-statistics",
    "adv_statistics": "division-investment-management-investment-adviser-statistics",
    "form_adv_stats": "division-investment-management-investment-adviser-statistics",
    # Registered funds / MMF stats (IM division)
    "registered_fund_statistics": "division-investment-management-registered-fund-statistics",
    "mmf_statistics": "money-market-fund-statistics",
    # DERA data library — high-traffic sets
    "form_n_mfp": "dera-form-n-mfp-data-sets",
    "n_mfp": "dera-form-n-mfp-data-sets",
    "nmfp": "dera-form-n-mfp-data-sets",
    "mmf_holdings": "dera-form-n-mfp-data-sets",
    "form_13f": "form-13f-data-sets",
    "13f": "form-13f-data-sets",
    "form_n_port": "form-n-port-data-sets",
    "n_port": "form-n-port-data-sets",
    "nport": "form-n-port-data-sets",
    "form_n_cen": "form-n-cen-data-sets",
    "form_d": "form-d-data-sets",
    "reg_d": "form-d-data-sets",
    "financial_statements": "financial-statement-data-sets",
    "fsds": "financial-statement-data-sets",
    "fs_notes": "financial-statement-notes-data-sets",
    "insider": "insider-transactions-data-sets",
    "form_3_4_5": "insider-transactions-data-sets",
    "bdc": "bdc-data-sets",
    "crowdfunding": "crowdfunding-offerings-data-sets",
    "reg_cf": "crowdfunding-offerings-data-sets",
    "reg_a": "regulation-data-sets",
    "transfer_agent": "transfer-agent-data-sets",
    "mmf_info": "money-market-fund-information",
    "series_class": "investment-company-series-class-information",
    "cef": "closed-end-fund-information",
    "ria_foia": "information-about-registered-investment-advisers-exempt-reporting-advisers",
    "municipal_advisors": "information-about-registered-municipal-advisors",
    "vip": "variable-insurance-product-data-sets",
    "market_structure": "market-structure-data-security-exchange",
    "edgar_logs": "edgar-log-file-data-sets",
}

# Themed clusters for menu browse / batch sync (full universe reachable).
CLUSTERS: Dict[str, Dict[str, Any]] = {
    "form_pf_adjacent": {
        "label": "Form PF & adjacent (private funds, advisers, MMF, registered funds, 13F/N-PORT/N-CEN/N-MFP)",
        "match": (
            r"private.fund|form.pf|investment.adviser|mmf|money.market|"
            r"registered.fund|n-port|n-cen|13f|n-mfp|nmfp|series.class|"
            r"closed-end|ria|exempt.reporting"
        ),
    },
    "data_library_all": {
        "label": "Full DERA data library (all structured ZIP/TSV sets)",
        "section": "data_library",
    },
    "investment_management_all": {
        "label": "Division of Investment Management reports (all IM pages)",
        "section": "investment_management",
    },
    "statistics_all": {
        "label": "Statistics & data visualizations (all viz backing pages)",
        "section": "statistics",
    },
    "capital_markets": {
        "label": "IPOs, FROs, Reg D/CF/A, corporate bonds, ABS/CMBS",
        "match": r"ipo|follow.on|regulation-[dacf]|corporate.bond|abs|cmbs|crowdfunding",
    },
    "market_structure": {
        "label": "Market structure / quote life / spreads datasets",
        "match": r"market.structure|marketstructure|spreads.depth|quote",
    },
    "fund_holdings": {
        "label": "Fund holdings & portfolios (N-MFP, N-PORT, 13F, MMF info)",
        "match": r"n-mfp|nmfp|n-port|nport|13f|mmf.info|money.market.fund.info",
    },
    "full_universe": {
        "label": "Entire sec.gov/data-research catalog (200 pages)",
        "all": True,
    },
}

ROUTING = {
    "one company's EDGAR filings / XBRL facts / full-text search": "sec_edgar_client",
    "cross-company XBRL frames (us-gaap concept panels)": "sec_edgar_client.get_frames(...)",
    "raw Form PF filer-level data (confidential — not public)": (
        "Use aggregated private-fund statistics via "
        "sec_data_research_client.get('form_pf') — raw Form PF is not published"
    ),
}

# Populated by dev/build_sec_data_research_client.py (200 dataset pages).
PAGE_CATALOG: List[Dict[str, Any]] = [
    {'slug': 'investment-adviser-statistics', 'title': 'Investment Adviser Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'investment-advisers-clients', 'title': 'Investment Advisers - Clients', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-clients', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-disclosure-information', 'title': 'Investment Advisers - Disclosure Information', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-disclosure-information', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-number-advisers', 'title': 'Investment Advisers - Number of Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-number-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-private-funds-advised-eras', 'title': 'Investment Advisers - Private Funds Advised by ERAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-private-funds-advised-eras', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-private-funds-advised-rias', 'title': 'Investment Advisers - Private Funds Advised by RIAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-private-funds-advised-rias', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-raum', 'title': 'Investment Advisers - RAUM', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-raum', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-ria-activities', 'title': 'Investment Advisers - RIA Activities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-ria-activities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-separately-managed-accounts', 'title': 'Investment Advisers - Separately Managed Accounts', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-separately-managed-accounts', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-total-private-funds-advised-rias-or-eras', 'title': 'Investment Advisers - Total Private Funds Advised by RIAs or ERAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/investment-adviser-statistics/investment-advisers-total-private-funds-advised-rias-or-eras', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-fund-statistics', 'title': 'Money Market Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'money-market-funds-assets-liabilities', 'title': 'Money Market Funds - Assets and Liabilities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-assets-liabilities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-flows', 'title': 'Money Market Funds - Flows', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-flows', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-liquidity', 'title': 'Money Market Funds - Liquidity', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-liquidity', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-maturity', 'title': 'Money Market Funds - Maturity', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-maturity', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-money-market-funds-number-mmfs-advisers', 'title': 'Money Market Funds - Number of MMFs and Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-money-market-funds-number-mmfs-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-portfolio-dispositions', 'title': 'Money Market Funds - Portfolio Dispositions', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-portfolio-dispositions', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-portfolio-securities', 'title': 'Money Market Funds - Portfolio Securities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-portfolio-securities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-repurchase-agreements', 'title': 'Money Market Funds - Repurchase Agreements', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-repurchase-agreements', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-yields', 'title': 'Money Market Funds - Yields', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/money-market-fund-statistics/money-market-funds-yields', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-fund-statistics', 'title': 'Private Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'private-funds-aggregate-fund-assets', 'title': 'Private Funds - Aggregate Fund Assets', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-aggregate-fund-assets', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-beneficial-ownership-funds', 'title': 'Private Funds - Beneficial Ownership of Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-beneficial-ownership-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-liquidity-funds', 'title': 'Private Funds - Liquidity Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-liquidity-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-number-funds-advisers', 'title': 'Private Funds - Number of Funds and Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-number-funds-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-qualifying-hedge-fund-investment-types', 'title': 'Private Funds - Qualifying Hedge Fund Investment Types', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-qualifying-hedge-fund-investment-types', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-qualifying-hedge-fund-strategies', 'title': 'Private Funds - Qualifying Hedge Fund Strategies', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/private-fund-statistics/private-funds-qualifying-hedge-fund-strategies', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-fund-statistics', 'title': 'Registered Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'registered-funds-flows', 'title': 'Registered Funds - Flows', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-flows', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-derivative-investments', 'title': 'Registered Funds - Fund Derivative Investments', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-derivative-investments', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-category', 'title': 'Registered Funds - Fund Portfolio Investments by Category', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-category', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-closed-end-funds', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for Closed-End Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-closed-end-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-etfs', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for ETFs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-etfs', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-mutual-funds', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for Mutual Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-mutual-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-liquidity-classifications', 'title': 'Registered Funds - Liquidity Classifications', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-liquidity-classifications', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-number-funds', 'title': 'Registered Funds - Number of Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-number-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-returns', 'title': 'Registered Funds - Returns', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-returns', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-securities-lending', 'title': 'Registered Funds - Securities Lending', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-securities-lending', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-total-fund-assets', 'title': 'Registered Funds - Total Fund Assets', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-total-fund-assets', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-statistics', 'title': 'Registered Investment Companies Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-investment-companies-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'registered-investment-companies-n-1a-funds', 'title': 'Registered Investment Companies - N-1A Funds (Open-end Management Investment Companies)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-investment-companies-statistics/registered-investment-companies-n-1a-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-n-2-funds', 'title': 'Registered Investment Companies - N-2 Funds (Closed-end Management Investment Companies)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-investment-companies-statistics/registered-investment-companies-n-2-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-securities-lending-lines-credit', 'title': 'Registered Investment Companies - Securities Lending and Lines of Credit', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-investment-companies-statistics/registered-investment-companies-securities-lending-lines-credit', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-service-providers', 'title': 'Registered Investment Companies - Service Providers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/data-visualizations/registered-investment-companies-statistics/registered-investment-companies-service-providers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'division-investment-management-annual-registered-investment-company-update', 'title': 'Division of Investment Management Annual Registered Investment Company Update', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/division-investment-management-annual-registered-investment-company-update', 'n_data': 1, 'n_docs': 2},
    {'slug': 'division-investment-management-investment-adviser-statistics', 'title': 'Division of Investment Management Investment Adviser Statistics', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/division-investment-management-investment-adviser-statistics', 'n_data': 1, 'n_docs': 2},
    {'slug': 'division-investment-management-private-fund-statistics', 'title': 'Division of Investment Management Private Fund Statistics', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/division-investment-management-private-fund-statistics', 'n_data': 7, 'n_docs': 80},
    {'slug': 'division-investment-management-registered-fund-statistics', 'title': 'Division of Investment Management Registered Fund Statistics', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/division-investment-management-registered-fund-statistics', 'n_data': 8, 'n_docs': 9},
    {'slug': 'money-market-fund-statistics', 'title': 'Money Market Fund Statistics', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/money-market-fund-statistics', 'n_data': 49, 'n_docs': 140},
    {'slug': 'mmf-statistics-2021-11', 'title': 'Money Market Fund Statistics, November 2021', 'section': 'investment_management', 'url': 'https://www.sec.gov/data-research/investment-management-data/money-market-fund-statistics/mmf-statistics-2021-11', 'n_data': 0, 'n_docs': 2},
    {'slug': 'administrative-law-judge-initial-decisions-2009-2010', 'title': 'Administrative Law Judge Initial Decisions for 2009 and 2010', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/administrative-law-judge-initial-decisions-2009-2010', 'n_data': 2, 'n_docs': 1},
    {'slug': 'bdc-data-sets', 'title': 'Business Development Company (BDC) Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/bdc-data-sets', 'n_data': 24, 'n_docs': 2},
    {'slug': 'closed-end-fund-information', 'title': 'Closed-End Fund Information', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/closed-end-fund-information', 'n_data': 29, 'n_docs': 1},
    {'slug': 'commission-opinions-adjudicatory-orders-2008-2009-2010', 'title': 'Commission Opinions and Adjudicatory Orders for 2008, 2009 and 2010', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/commission-opinions-adjudicatory-orders-2008-2009-2010', 'n_data': 3, 'n_docs': 1},
    {'slug': 'commission-votes-actions-filed-federal-court-4813', 'title': 'Commission Votes on Actions Filed in Federal Court From April 8, 2013 through August 6, 2019', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/commission-votes-actions-filed-federal-court-4813', 'n_data': 3, 'n_docs': 1},
    {'slug': 'crowdfunding-offerings-data-sets', 'title': 'Crowdfunding Offerings Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/crowdfunding-offerings-data-sets', 'n_data': 40, 'n_docs': 2},
    {'slug': 'dera-form-n-mfp-data-sets', 'title': 'Form N-MFP Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/dera-form-n-mfp-data-sets', 'n_data': 95, 'n_docs': 3},
    {'slug': 'edgar-log-file-data-sets', 'title': 'EDGAR Log File Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/edgar-log-file-data-sets', 'n_data': 0, 'n_docs': 2},
    {'slug': 'financial-statement-data-sets', 'title': 'Financial Statement Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets', 'n_data': 69, 'n_docs': 2},
    {'slug': 'financial-statement-notes-data-sets', 'title': 'Financial Statement and Notes Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/financial-statement-notes-data-sets', 'n_data': 79, 'n_docs': 2},
    {'slug': 'form-13f-data-sets', 'title': 'Form 13F Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets', 'n_data': 53, 'n_docs': 2},
    {'slug': 'form-d-data-sets', 'title': 'Form D Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/form-d-data-sets', 'n_data': 73, 'n_docs': 2},
    {'slug': 'form-n-cen-data-sets', 'title': 'Form N-CEN Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets', 'n_data': 31, 'n_docs': 3},
    {'slug': 'form-n-port-data-sets', 'title': 'Form N-PORT Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets', 'n_data': 26, 'n_docs': 3},
    {'slug': 'information-about-registered-investment-advisers-exempt-reporting-advisers', 'title': 'Information About Registered Investment Advisers and Exempt Reporting Advisers', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/information-about-registered-investment-advisers-exempt-reporting-advisers', 'n_data': 395, 'n_docs': 6},
    {'slug': 'information-about-registered-municipal-advisors', 'title': 'Information About Registered Municipal Advisors', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/information-about-registered-municipal-advisors', 'n_data': 133, 'n_docs': 3},
    {'slug': 'insider-transactions-data-sets', 'title': 'Insider Transactions Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets', 'n_data': 81, 'n_docs': 2},
    {'slug': 'investment-company-series-class-information', 'title': 'Investment Company Series and Class Information', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/investment-company-series-class-information', 'n_data': 34, 'n_docs': 2},
    {'slug': 'market-structure-data-security-exchange', 'title': 'Metrics by Individual Security and Exchange', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/market-structure-data-security-exchange', 'n_data': 56, 'n_docs': 1},
    {'slug': 'marketstructuredata-conditional-cancel', 'title': 'Conditional Cancel and Trade Distributions', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-conditional-cancel', 'n_data': 53, 'n_docs': 1},
    {'slug': 'marketstructuredata-decile-quartile', 'title': 'Summary Metrics by Decile and Quartile', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-decile-quartile', 'n_data': 1, 'n_docs': 1},
    {'slug': 'marketstructuredata-exchange', 'title': 'Summary Metrics by Exchange', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-exchange', 'n_data': 1, 'n_docs': 1},
    {'slug': 'marketstructuredata-hazards-survivors', 'title': 'Hazards and Survivors by Time Period', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-hazards-survivors', 'n_data': 53, 'n_docs': 1},
    {'slug': 'marketstructuredata-security', 'title': 'Metrics by Individual Security', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/marketstructuredata-security', 'n_data': 56, 'n_docs': 1},
    {'slug': 'money-market-fund-information', 'title': 'Money Market Fund Information', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/money-market-fund-information', 'n_data': 291, 'n_docs': 1},
    {'slug': 'mutual-fund-prospectus-riskreturn-summary-data-sets', 'title': 'Mutual Fund Prospectus Risk/Return Summary Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/mutual-fund-prospectus-riskreturn-summary-data-sets', 'n_data': 62, 'n_docs': 2},
    {'slug': 'number-edgar-filings-form-type', 'title': 'Number of EDGAR Filings by Form Type', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/number-edgar-filings-form-type', 'n_data': 1, 'n_docs': 1},
    {'slug': 'opendatasetsshtmlbdc', 'title': 'Business Development Company Report', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/opendatasetsshtmlbdc', 'n_data': 30, 'n_docs': 1},
    {'slug': 'public-company-bankruptcy-cases-opened-monitored', 'title': 'Public Company Bankruptcy Cases Opened and Monitored', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/public-company-bankruptcy-cases-opened-monitored', 'n_data': 6, 'n_docs': 1},
    {'slug': 'regulation-data-sets', 'title': 'Regulation A Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/regulation-data-sets', 'n_data': 44, 'n_docs': 2},
    {'slug': 'sec-administrative-proceedings-2009-through-2013', 'title': 'SEC Administrative Proceedings for 2009 through 2013', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/sec-administrative-proceedings-2009-through-2013', 'n_data': 5, 'n_docs': 1},
    {'slug': 'sec-litigation-releases-2009-2010', 'title': 'SEC Litigation Releases for 2009 and 2010', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/sec-litigation-releases-2009-2010', 'n_data': 2, 'n_docs': 1},
    {'slug': 'security-based-swap-dealers-sbsds', 'title': 'Security-Based Swap Dealers (SBSDs)', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/security-based-swap-dealers-sbsds', 'n_data': 1, 'n_docs': 3},
    {'slug': 'spreads-depth-individual-security', 'title': 'Spreads and Depth by Individual Security', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/spreads-depth-individual-security', 'n_data': 3, 'n_docs': 1},
    {'slug': 'transfer-agent-data-sets', 'title': 'Transfer Agent Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/transfer-agent-data-sets', 'n_data': 78, 'n_docs': 2},
    {'slug': 'variable-insurance-product-data-sets', 'title': 'Variable Insurance Product Data Sets', 'section': 'data_library', 'url': 'https://www.sec.gov/data-research/sec-markets-data/variable-insurance-product-data-sets', 'n_data': 8, 'n_docs': 2},
    {'slug': 'asset-backed-securities-abs-issuances', 'title': 'Asset-Backed Securities (ABS) Issuances', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/asset-backed-securities-abs-issuances', 'n_data': 1, 'n_docs': 4},
    {'slug': 'abs-deal-volume-offering-type', 'title': 'ABS Deal Volume by Offering Type', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/asset-backed-securities-abs-issuances/abs-deal-volume-offering-type', 'n_data': 1, 'n_docs': 2},
    {'slug': 'abs-median-deal-size-deal-type-2014-2024', 'title': 'ABS Median Deal Size by Deal Type (2014 - 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/asset-backed-securities-abs-issuances/abs-median-deal-size-deal-type-2014-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'abs-median-deal-size-deal-type-2014-2025', 'title': 'ABS Median Deal Size by Deal Type (2014 - 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/asset-backed-securities-abs-issuances/abs-median-deal-size-deal-type-2014-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-volume-abs-issuances', 'title': 'Number and Volume of ABS Issuances', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/asset-backed-securities-abs-issuances/number-volume-abs-issuances', 'n_data': 1, 'n_docs': 2},
    {'slug': 'commercial-mortgage-backed-securities-cmbs-issuances', 'title': 'Commercial Mortgage-Backed Securities (CMBS) Issuances', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances', 'n_data': 1, 'n_docs': 4},
    {'slug': 'cmbs-deal-structure-number-classes-deal-2016-2024', 'title': 'CMBS Deal Structure: Number of Classes per Deal (2016 - 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances/cmbs-deal-structure-number-classes-deal-2016-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'cmbs-deal-structure-number-classes-deal-2016-2025', 'title': 'CMBS Deal Structure: Number of Classes per Deal (2016 - 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances/cmbs-deal-structure-number-classes-deal-2016-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-volume-cmbs-issuances-offering-type', 'title': 'Number and Volume of CMBS Issuances by Offering Type', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances/number-volume-cmbs-issuances-offering-type', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-volume-cmbs-issuances-offering-type-2024-2025', 'title': 'Number and Volume of CMBS Issuances by Offering Type (2024 & 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances/number-volume-cmbs-issuances-offering-type-2024-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-volume-cmbs-issuances-offering-type-2024-2025q1', 'title': 'Number and Volume of CMBS Issuances by Offering Type (2024 & 2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/commercial-mortgage-backed-securities-cmbs-issuances/number-volume-cmbs-issuances-offering-type-2024-2025q1', 'n_data': 1, 'n_docs': 2},
    {'slug': 'corporate-bond-offerings', 'title': 'Corporate Bond Offerings', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/corporate-bond-offerings', 'n_data': 1, 'n_docs': 5},
    {'slug': 'corporate-bond-offerings-number-offerings-issuer-location-2024', 'title': 'Corporate Bond Offerings: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/corporate-bond-offerings/corporate-bond-offerings-number-offerings-issuer-location-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'corporate-bond-offerings-number-offerings-issuer-location-2025', 'title': 'Corporate Bond Offerings: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/corporate-bond-offerings/corporate-bond-offerings-number-offerings-issuer-location-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'corporate-bond-offerings-number-proceeds', 'title': 'Corporate Bond Offerings: Number and Proceeds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/corporate-bond-offerings/corporate-bond-offerings-number-proceeds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'corporate-bond-offerings-number-proceeds-major-industry-group', 'title': 'Corporate Bond Offerings: Number and Proceeds by Major Industry Group', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/corporate-bond-offerings/corporate-bond-offerings-number-proceeds-major-industry-group', 'n_data': 1, 'n_docs': 2},
    {'slug': 'data-visualization-gallery', 'title': 'Data Visualization Gallery', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/data-visualization-gallery', 'n_data': 0, 'n_docs': 1},
    {'slug': 'follow-registered-offerings-fros', 'title': 'Follow-on Registered Offerings (FROs)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/follow-registered-offerings-fros', 'n_data': 1, 'n_docs': 3},
    {'slug': 'fros-number-offerings-issuer-location-2024', 'title': 'FROs: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/follow-registered-offerings-fros/fros-number-offerings-issuer-location-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'fros-number-offerings-issuer-location-2025', 'title': 'FROs: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/follow-registered-offerings-fros/fros-number-offerings-issuer-location-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'fros-number-proceeds', 'title': 'FROs: Number and Proceeds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/follow-registered-offerings-fros/fros-number-proceeds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'fros-number-proceeds-major-industry-group', 'title': 'FROs: Number and Proceeds by Major Industry Group', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/follow-registered-offerings-fros/fros-number-proceeds-major-industry-group', 'n_data': 1, 'n_docs': 2},
    {'slug': 'initial-public-offerings-ipos', 'title': 'Initial Public Offerings (IPOs)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/initial-public-offerings-ipos', 'n_data': 1, 'n_docs': 3},
    {'slug': 'ipos-number-offerings-issuer-location-2024', 'title': 'IPOs: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/initial-public-offerings-ipos/ipos-number-offerings-issuer-location-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'ipos-number-offerings-issuer-location-2025', 'title': 'IPOs: Number of Offerings by Issuer Location (2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/initial-public-offerings-ipos/ipos-number-offerings-issuer-location-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'ipos-number-proceeds', 'title': 'IPOs: Number and Proceeds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/initial-public-offerings-ipos/ipos-number-proceeds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'ipos-number-proceeds-major-industry-group', 'title': 'IPOs: Number and Proceeds by Major Industry Group', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/initial-public-offerings-ipos/ipos-number-proceeds-major-industry-group', 'n_data': 1, 'n_docs': 2},
    {'slug': 'investment-adviser-statistics', 'title': 'Investment Adviser Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'investment-advisers-clients', 'title': 'Investment Advisers - Clients', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-clients', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-disclosure-information', 'title': 'Investment Advisers - Disclosure Information', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-disclosure-information', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-number-advisers', 'title': 'Investment Advisers - Number of Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-number-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-private-funds-advised-eras', 'title': 'Investment Advisers - Private Funds Advised by ERAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-private-funds-advised-eras', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-private-funds-advised-rias', 'title': 'Investment Advisers - Private Funds Advised by RIAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-private-funds-advised-rias', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-raum', 'title': 'Investment Advisers - RAUM', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-raum', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-ria-activities', 'title': 'Investment Advisers - RIA Activities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-ria-activities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-separately-managed-accounts', 'title': 'Investment Advisers - Separately Managed Accounts', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-separately-managed-accounts', 'n_data': 1, 'n_docs': 1},
    {'slug': 'investment-advisers-total-private-funds-advised-rias-or-eras', 'title': 'Investment Advisers - Total Private Funds Advised by RIAs or ERAs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/investment-adviser-statistics/investment-advisers-total-private-funds-advised-rias-or-eras', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-fund-statistics', 'title': 'Money Market Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'money-market-funds-assets-liabilities', 'title': 'Money Market Funds - Assets and Liabilities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-assets-liabilities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-flows', 'title': 'Money Market Funds - Flows', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-flows', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-liquidity', 'title': 'Money Market Funds - Liquidity', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-liquidity', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-maturity', 'title': 'Money Market Funds - Maturity', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-maturity', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-number-mmfs-advisers', 'title': 'Money Market Funds - Number of MMFs and Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-number-mmfs-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-portfolio-dispositions', 'title': 'Money Market Funds - Portfolio Dispositions', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-portfolio-dispositions', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-portfolio-securities', 'title': 'Money Market Funds - Portfolio Securities', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-portfolio-securities', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-repurchase-agreements', 'title': 'Money Market Funds - Repurchase Agreements', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-repurchase-agreements', 'n_data': 1, 'n_docs': 1},
    {'slug': 'money-market-funds-yields', 'title': 'Money Market Funds - Yields', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/money-market-fund-statistics/money-market-funds-yields', 'n_data': 1, 'n_docs': 1},
    {'slug': 'municipal-advisors', 'title': 'Municipal Advisors', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors', 'n_data': 1, 'n_docs': 7},
    {'slug': 'number-registered-municipal-advisors-location', 'title': 'Number of Registered Municipal Advisors by Location', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors/number-registered-municipal-advisors-location', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-registered-municipal-advisors-size-apr-1-2025', 'title': 'Number of Registered Municipal Advisors by Size (as of Jan. 1, 2026)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors/number-registered-municipal-advisors-size-apr-1-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-registered-municipal-advisors-size-jan-1-2026', 'title': 'Number of Registered Municipal Advisors by Size (as of Jan. 1, 2026)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors/number-registered-municipal-advisors-size-jan-1-2026', 'n_data': 1, 'n_docs': 2},
    {'slug': 'total-number-registered-municipal-advisors-oct-1-2015-apr-1-2025', 'title': 'Total Number of Registered Municipal Advisors (as of Oct. 1, 2015 - as of Jan. 1, 2026)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors/total-number-registered-municipal-advisors-oct-1-2015-apr-1-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'total-number-registered-municipal-advisors-oct-1-2015-jan-1-2026', 'title': 'Total Number of Registered Municipal Advisors (as of Oct. 1, 2015 - as of Jan. 1, 2026)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/municipal-advisors/total-number-registered-municipal-advisors-oct-1-2015-jan-1-2026', 'n_data': 1, 'n_docs': 2},
    {'slug': 'nationally-recognized-statistical-rating-organizations-nrsros', 'title': 'Nationally Recognized Statistical Rating Organizations (NRSROs)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/nationally-recognized-statistical-rating-organizations-nrsros', 'n_data': 1, 'n_docs': 2},
    {'slug': 'nrsros-number-outstanding-credit-ratings-government-non-government-securities-each-nrsro', 'title': 'NRSROs: Number of Outstanding Credit Ratings on Government and Non-Government Securities by each NRSRO (2014-2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/nationally-recognized-statistical-rating-organizations-nrsros/nrsros-number-outstanding-credit-ratings-government-non-government-securities-each-nrsro', 'n_data': 1, 'n_docs': 2},
    {'slug': 'nrsros-number-outstanding-credit-ratings-rating-category-2014-2024', 'title': 'NRSROs: Number of Outstanding Credit Ratings by Rating Category (2014 - 2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/nationally-recognized-statistical-rating-organizations-nrsros/nrsros-number-outstanding-credit-ratings-rating-category-2014-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'nrsros-number-outstanding-credit-ratings-rating-category-nrsro-2024', 'title': 'NRSROs: Number of Outstanding Credit Ratings by Rating Category and NRSRO (2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/nationally-recognized-statistical-rating-organizations-nrsros/nrsros-number-outstanding-credit-ratings-rating-category-nrsro-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'private-fund-statistics', 'title': 'Private Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'private-funds-aggregate-fund-assets', 'title': 'Private Funds - Aggregate Fund Assets', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics/private-funds-aggregate-fund-assets', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-beneficial-ownership-funds', 'title': 'Private Funds - Beneficial Ownership of Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics/private-funds-beneficial-ownership-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-liquidity-funds', 'title': 'Private Funds - Liquidity Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics/private-funds-liquidity-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-number-funds-advisers', 'title': 'Private Funds - Number of Funds and Advisers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics/private-funds-number-funds-advisers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'private-funds-qualifying-hedge-fund-strategies', 'title': 'Private Funds - Qualifying Hedge Fund Strategies', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/private-fund-statistics/private-funds-qualifying-hedge-fund-strategies', 'n_data': 1, 'n_docs': 1},
    {'slug': 'qualifying-households-under-accredited-investor-financial-criteria', 'title': 'Qualifying Households under Accredited Investor Financial Criteria', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/qualifying-households-under-accredited-investor-financial-criteria', 'n_data': 1, 'n_docs': 3},
    {'slug': 'overall-qualifying-households-under-financial-criteria-1989-2022', 'title': 'Overall Qualifying Households under Financial Criteria (1989 - 2022)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/qualifying-households-under-accredited-investor-financial-criteria/overall-qualifying-households-under-financial-criteria-1989-2022', 'n_data': 1, 'n_docs': 2},
    {'slug': 'qualifying-households-financial-criteria-1989-2022', 'title': 'Qualifying Households by Financial Criteria  (1989 - 2022)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/qualifying-households-under-accredited-investor-financial-criteria/qualifying-households-financial-criteria-1989-2022', 'n_data': 1, 'n_docs': 2},
    {'slug': 'qualifying-households-under-financial-criteria-excluding-retirement-assets-1989-2022', 'title': 'Qualifying Households under Financial Criteria Excluding Retirement Assets (1989 - 2022)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/qualifying-households-under-accredited-investor-financial-criteria/qualifying-households-under-financial-criteria-excluding-retirement-assets-1989-2022', 'n_data': 1, 'n_docs': 2},
    {'slug': 'registered-fund-statistics', 'title': 'Registered Fund Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'registered-funds-flows', 'title': 'Registered Funds - Flows', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-flows', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-derivative-investments', 'title': 'Registered Funds - Fund Derivative Investments', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-fund-derivative-investments', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-category', 'title': 'Registered Funds - Fund Portfolio Investments by Category', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-category', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-closed-end-funds', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for Closed-End Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-closed-end-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-etfs', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for ETFs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-etfs', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-fund-portfolio-investments-country-currency-mutual-funds', 'title': 'Registered Funds - Fund Portfolio Investments by Country and Currency for Mutual Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-country-currency-mutual-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-liquidity-classifications', 'title': 'Registered Funds - Liquidity Classifications', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-liquidity-classifications', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-number-funds', 'title': 'Registered Funds - Number of Funds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-number-funds', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-returns', 'title': 'Registered Funds - Returns', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-returns', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-securities-lending', 'title': 'Registered Funds - Securities Lending', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-securities-lending', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-funds-total-fund-assets', 'title': 'Registered Funds - Total Fund Assets', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-fund-statistics/registered-funds-total-fund-assets', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-statistics', 'title': 'Registered Investment Companies Statistics', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-investment-companies-statistics', 'n_data': 0, 'n_docs': 1},
    {'slug': 'registered-investment-companies-n-1a-funds-open-end-management-investment-companies', 'title': 'Registered Investment Companies - N-1A Funds (Open-end Management Investment Companies)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-investment-companies-statistics/registered-investment-companies-n-1a-funds-open-end-management-investment-companies', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-n-2-funds-closed-end-management-investment-companies', 'title': 'Registered Investment Companies - N-2 Funds (Closed-end Management Investment Companies)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-investment-companies-statistics/registered-investment-companies-n-2-funds-closed-end-management-investment-companies', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-securities-lending-lines-credit', 'title': 'Registered Investment Companies - Securities Lending and Lines of Credit', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-investment-companies-statistics/registered-investment-companies-securities-lending-lines-credit', 'n_data': 1, 'n_docs': 1},
    {'slug': 'registered-investment-companies-service-providers', 'title': 'Registered Investment Companies - Service Providers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/registered-investment-companies-statistics/registered-investment-companies-service-providers', 'n_data': 1, 'n_docs': 1},
    {'slug': 'regulation-a-offerings', 'title': 'Regulation A Offerings', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-a-offerings', 'n_data': 1, 'n_docs': 3},
    {'slug': 'regulation-offerings-number-qualified-offerings-industry', 'title': 'Regulation A Offerings: Number of Qualified Offerings by Industry', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-a-offerings/regulation-offerings-number-qualified-offerings-industry', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-offerings-number-qualified-offerings-issuer-location', 'title': 'Regulation A Offerings: Number of Qualified Offerings by Issuer Location', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-a-offerings/regulation-offerings-number-qualified-offerings-issuer-location', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-offerings-trends-financing-under-regulation-over-time', 'title': 'Regulation A Offerings: Trends in Financing under Regulation A Over Time', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-a-offerings/regulation-offerings-trends-financing-under-regulation-over-time', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-crowdfunding-cf-offerings', 'title': 'Regulation Crowdfunding (CF) Offerings', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-crowdfunding-cf-offerings', 'n_data': 1, 'n_docs': 3},
    {'slug': 'regulation-cf-offerings-distribution-security-types', 'title': 'Regulation CF Offerings: Distribution of Security Types', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-crowdfunding-cf-offerings/regulation-cf-offerings-distribution-security-types', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-cf-offerings-number-offerings-issuer-location', 'title': 'Regulation CF Offerings: Number of Offerings by Issuer Location', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-crowdfunding-cf-offerings/regulation-cf-offerings-number-offerings-issuer-location', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-cf-offerings-number-reported-proceeds', 'title': 'Regulation CF Offerings: Number and Reported Proceeds', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-crowdfunding-cf-offerings/regulation-cf-offerings-number-reported-proceeds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-d-offerings', 'title': 'Regulation D Offerings', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-d-offerings', 'n_data': 1, 'n_docs': 3},
    {'slug': 'regulation-d-offerings-number-offerings-capital-raised', 'title': 'Regulation D Offerings: Number of Offerings and Capital Raised', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-d-offerings/regulation-d-offerings-number-offerings-capital-raised', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-d-offerings-number-offerings-issuer-location', 'title': 'Regulation D Offerings: Number of Offerings by Issuer Location', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-d-offerings/regulation-d-offerings-number-offerings-issuer-location', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-d-offerings-total-amount-raised-issuer-type', 'title': 'Regulation D Offerings: Total Amount Raised by Issuer Type', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-d-offerings/regulation-d-offerings-total-amount-raised-issuer-type', 'n_data': 1, 'n_docs': 2},
    {'slug': 'regulation-offerings', 'title': 'Regulation A Offerings', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/regulation-offerings', 'n_data': 1, 'n_docs': 3},
    {'slug': 'reporting-issuers', 'title': 'Reporting Issuers', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/reporting-issuers', 'n_data': 1, 'n_docs': 4},
    {'slug': 'number-reporting-issuers-calendar-year-2004-2024', 'title': 'Number of Reporting Issuers by Calendar Year (2004 - 2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/reporting-issuers/number-reporting-issuers-calendar-year-2004-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-reporting-issuers-filer-status-reporting-status-2024', 'title': 'Number of Reporting Issuers by Filer Status and Reporting Status (2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/reporting-issuers/number-reporting-issuers-filer-status-reporting-status-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-reporting-issuers-shell-vs-non-shell-2024', 'title': 'Number of Reporting Issuers – Shell vs. Non-shell (2024)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/reporting-issuers/number-reporting-issuers-shell-vs-non-shell-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'security-based-swap-dealers-sbsds', 'title': 'Security-Based Swap Dealers (SBSDs)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/security-based-swap-dealers-sbsds', 'n_data': 1, 'n_docs': 3},
    {'slug': 'geographical-distribution-sbsds', 'title': 'Geographical Distribution of SBSDs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/security-based-swap-dealers-sbsds/geographical-distribution-sbsds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'time-trends-sbsd-registrations', 'title': 'Time Trends in SBSD Registrations', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/security-based-swap-dealers-sbsds/time-trends-sbsd-registrations', 'n_data': 1, 'n_docs': 2},
    {'slug': 'types-sbsds', 'title': 'Types of SBSDs', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/security-based-swap-dealers-sbsds/types-sbsds', 'n_data': 1, 'n_docs': 2},
    {'slug': 'transfer-agents', 'title': 'Transfer Agents', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/transfer-agents', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-registered-tas-location', 'title': 'Number of Registered TAs by Location', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/transfer-agents/number-registered-tas-location', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-registered-tas-regulatory-agency-size', 'title': 'Number of Registered TAs by Regulatory Agency and Size', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/transfer-agents/number-registered-tas-regulatory-agency-size', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-sec-registered-bank-registered-tas-2012-2024', 'title': 'Number of SEC-Registered and Bank-Registered TAs (2012-2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/transfer-agents/number-sec-registered-bank-registered-tas-2012-2024', 'n_data': 1, 'n_docs': 2},
    {'slug': 'number-sec-registered-bank-registered-tas-2012-2025', 'title': 'Number of SEC-Registered and Bank-Registered TAs (2012-2025)', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/transfer-agents/number-sec-registered-bank-registered-tas-2012-2025', 'n_data': 1, 'n_docs': 2},
    {'slug': 'us-households-participation-capital-markets', 'title': 'U.S. Households’ Participation in Capital Markets', 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/us-households-participation-capital-markets', 'n_data': 1, 'n_docs': 2},
    {'slug': 'us-households-participation-capital-markets-median-mean-1989-2022', 'title': "U.S. Households' Participation in Capital Markets: Median and Mean (1989 - 2022)", 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/us-households-participation-capital-markets/us-households-participation-capital-markets-median-mean-1989-2022', 'n_data': 1, 'n_docs': 2},
    {'slug': 'us-households-participation-capital-markets-number-percentage-1989-2022', 'title': "U.S. Households' Participation in Capital Markets: Number and Percentage (1989 - 2022)", 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/us-households-participation-capital-markets/us-households-participation-capital-markets-number-percentage-1989-2022', 'n_data': 1, 'n_docs': 2},
    {'slug': 'us-households-participation-capital-markets-types-holdings-1989-2022', 'title': "U.S. Households' Participation in Capital Markets: Types of Holdings (1989 - 2022)", 'section': 'statistics', 'url': 'https://www.sec.gov/data-research/statistics-data-visualizations/us-households-participation-capital-markets/us-households-participation-capital-markets-types-holdings-1989-2022', 'n_data': 1, 'n_docs': 2},
]


class SecDataResearchError(Exception):
    """Validation / HTTP / parse failures."""


class _MockResponse:
    def __init__(self, parsed_data: Any, status_line: str):
        self._parsed = parsed_data
        self._status_line = status_line
        self.status_code = self._parse_status_code(status_line)

    @staticmethod
    def _parse_status_code(status_line: str) -> int:
        if not status_line or not status_line.startswith("HTTP/"):
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
        raise json.JSONDecodeError("no body", "", 0)

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300


_INT_RE = re.compile(r"^[+-]?\d+$")


def _coerce_scalar(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    s = v.strip()
    if s == "":
        return None
    if _INT_RE.match(s):
        try:
            return int(s)
        except ValueError:
            return s
    try:
        f = float(s)
    except ValueError:
        return s
    if s.lower() in ("nan", "inf", "-inf", "+inf", "infinity"):
        return s
    return f


def _coerce_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: _coerce_scalar(val) for k, val in row.items()} for row in rows]


def _path_from_url(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    host = parsed.netloc or BASE_HOST
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return host, path


def _is_download_url(url: str) -> bool:
    low = url.lower().split("?")[0]
    if any(low.endswith(ext) for ext in DOWNLOAD_EXT):
        return True
    return any(m in low for m in DATA_PATH_MARKERS)


def _basename(url: str) -> str:
    return urlparse(url).path.rsplit("/", 1)[-1]


def _sort_key_url(url: str) -> Tuple:
    """Newest-first heuristic: prefer year/quarter/month tokens in filename."""
    name = _basename(url).lower()
    nums = [int(x) for x in re.findall(r"\d{4,8}", name)]
    return (nums[-1] if nums else 0, name)


class SecDataResearchClient:
    """Scrape, catalog, download, and parse SEC Data & Research datasets."""

    def __init__(
        self,
        *,
        store_root: Optional[Union[str, Path]] = None,
        user_agent: str = USER_AGENT,
        rate_limit: float = RATE_LIMIT_SECONDS,
    ):
        self.store_root = Path(store_root) if store_root else DEFAULT_STORE
        self.user_agent = user_agent
        self.rate_limit = rate_limit
        self._page_catalog: List[Dict[str, Any]] = list(PAGE_CATALOG)
        self._download_cache: Dict[str, Dict[str, List[str]]] = {}
        self._http = requests.Session()
        self._http.headers.update({"User-Agent": self.user_agent, "Accept": "*/*"})

    # --- catalog / discovery -------------------------------------------------

    def resolve_slug(self, name: str) -> str:
        key = (name or "").strip().lower().replace(" ", "_")
        key = ALIASES.get(key, ALIASES.get(name.strip().lower(), key))
        slugs = {p["slug"] for p in self._page_catalog}
        if key in slugs:
            return key
        matches = [s for s in slugs if key in s or s in key]
        if len(matches) == 1:
            return matches[0]
        if matches:
            raise SecDataResearchError(
                f"ambiguous slug {name!r}; matches={matches[:8]}. "
                f"Use catalog() or a full slug."
            )
        raise SecDataResearchError(
            f"unknown dataset {name!r}; see catalog() or ALIASES. "
            f"Known slugs (sample)={sorted(list(slugs))[:12]}"
        )

    def catalog(
        self,
        section: Optional[str] = None,
        query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List dataset pages (slug, title, section, url, n_data, n_docs)."""
        out = self._page_catalog
        if section:
            sec = section.strip().lower()
            out = [p for p in out if p.get("section") == sec]
        if query:
            q = query.strip().lower()
            out = [
                p
                for p in out
                if q in p["slug"].lower() or q in p.get("title", "").lower()
            ]
        return list(out)

    def summary(self) -> Dict[str, Any]:
        """Universe overview: page counts, file counts, clusters."""
        by_section: Dict[str, int] = {}
        data_files = 0
        for p in self._page_catalog:
            by_section[p.get("section", "other")] = by_section.get(p.get("section", "other"), 0) + 1
            data_files += p.get("n_data", 0)
        return {
            "pages": len(self._page_catalog),
            "indexed_data_files": data_files,
            "by_section": by_section,
            "clusters": {k: len(self.cluster(k)) for k in CLUSTERS},
            "aliases": len(ALIASES),
            "store_root": str(self.store_root),
        }

    def cluster(self, name: str) -> List[Dict[str, Any]]:
        """Return catalog pages in a themed cluster."""
        key = (name or "").strip().lower().replace(" ", "_")
        key = {"form_pf": "form_pf_adjacent", "pf": "form_pf_adjacent"}.get(key, key)
        spec = CLUSTERS.get(key)
        if not spec:
            raise SecDataResearchError(
                f"unknown cluster {name!r}; choose from {sorted(CLUSTERS)}"
            )
        if spec.get("all"):
            return list(self._page_catalog)
        if "section" in spec:
            return self.catalog(section=spec["section"])
        if "match" in spec:
            pat = re.compile(spec["match"], re.I)
            return [
                p
                for p in self._page_catalog
                if pat.search(p["slug"]) or pat.search(p.get("title", ""))
            ]
        slugs = set(spec.get("slugs", []))
        return [p for p in self._page_catalog if p["slug"] in slugs]

    def plan_sync(
        self,
        *,
        section: Optional[str] = None,
        cluster: Optional[str] = None,
        latest_only: bool = True,
        min_data_files: int = 0,
        include_docs: bool = False,
    ) -> List[Dict[str, Any]]:
        """Dry-run: list datasets that sync would touch (no downloads)."""
        if cluster:
            pages = self.cluster(cluster)
        elif section:
            pages = self.catalog(section=section)
        else:
            pages = list(self._page_catalog)
        if min_data_files:
            pages = [p for p in pages if p.get("n_data", 0) >= min_data_files]
        plan: List[Dict[str, Any]] = []
        for p in pages:
            n = p.get("n_data", 0) if not include_docs else p.get("n_data", 0) + p.get("n_docs", 0)
            if n == 0 and min_data_files:
                continue
            plan.append(
                {
                    "slug": p["slug"],
                    "title": p["title"],
                    "section": p.get("section"),
                    "n_data": p.get("n_data", 0),
                    "n_docs": p.get("n_docs", 0),
                    "files_per_dataset": 1 if latest_only else max(p.get("n_data", 0), 1),
                    "mode": "latest_only" if latest_only else "all_files",
                }
            )
        return plan

    def describe(self, slug_or_alias: str) -> Dict[str, Any]:
        """Metadata for one dataset plus live-scraped download URLs."""
        slug = self.resolve_slug(slug_or_alias)
        meta = next(p for p in self._page_catalog if p["slug"] == slug)
        files = self.list_files(slug, kind="all", refresh=True)
        return {
            **meta,
            "aliases": [k for k, v in ALIASES.items() if v == slug],
            "data_files": files["data"],
            "docs": files["docs"],
        }

    def refresh_catalog(self) -> List[Dict[str, Any]]:
        """Re-crawl the data-research page index from sec.gov."""
        visited: set[str] = set()
        queue = [
            f"{BASE_URL}/data-research/sec-markets-data?page=0",
            f"{BASE_URL}/data-research/sec-markets-data?page=1",
            f"{BASE_URL}/data-research/investment-management-data",
            f"{BASE_URL}/data-research/statistics-data-visualizations",
        ]
        dataset_pages: set[str] = set()

        while queue and len(visited) < 220:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            html = self._fetch_html(url)
            for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
                href = unescape(m.group(1).split("#")[0])
                if not href:
                    continue
                full = urljoin(url, href)
                if "/data-research/" not in full:
                    continue
                if any(
                    x in full
                    for x in (
                        "/sec-markets-data/",
                        "/investment-management-data/",
                        "/statistics-data-visualizations/",
                        "/data-visualizations/",
                    )
                ):
                    if full not in visited:
                        queue.append(full)
                    if full.count("/") >= 5 and "page=" not in full:
                        dataset_pages.add(full)

        pages: List[Dict[str, Any]] = []
        for url in sorted(dataset_pages):
            html = self._fetch_html(url)
            h1 = re.search(r"<h1[^>]*>([^<]+)", html)
            title = unescape(h1.group(1).strip()) if h1 else url.split("/")[-1]
            slug = url.rstrip("/").split("/")[-1]
            section = "other"
            if "/sec-markets-data/" in url:
                section = "data_library"
            elif "/investment-management-data/" in url:
                section = "investment_management"
            elif "/statistics-data-visualizations/" in url or "/data-visualizations/" in url:
                section = "statistics"
            dl = self._parse_downloads(html, url)
            pages.append(
                {
                    "slug": slug,
                    "title": title,
                    "section": section,
                    "url": url,
                    "n_data": len(dl["data"]),
                    "n_docs": len(dl["docs"]),
                }
            )
        self._page_catalog = pages
        self._download_cache.clear()
        self.store_root.mkdir(parents=True, exist_ok=True)
        (self.store_root.parent / "page_catalog.json").write_text(
            json.dumps(pages, indent=2), encoding="utf-8"
        )
        return pages

    # --- downloads listing ---------------------------------------------------

    def list_files(
        self,
        slug_or_alias: str,
        *,
        kind: str = "data",
        refresh: bool = False,
    ) -> Dict[str, List[str]]:
        """Return download URLs scraped from the dataset page.

        kind: ``data`` | ``docs`` | ``all``
        """
        slug = self.resolve_slug(slug_or_alias)
        if not refresh and slug in self._download_cache:
            cached = self._download_cache[slug]
        else:
            meta = next(p for p in self._page_catalog if p["slug"] == slug)
            html = self._fetch_html(meta["url"])
            cached = self._parse_downloads(html, meta["url"])
            self._download_cache[slug] = cached
        if kind == "docs":
            return {"docs": cached["docs"]}
        if kind == "all":
            return cached
        return {"data": cached["data"]}

    def latest(self, slug_or_alias: str, ext: Optional[str] = None) -> str:
        """Newest data-file URL for a dataset (by filename date heuristic)."""
        urls = self.list_files(slug_or_alias, kind="data")["data"]
        if ext:
            ext = ext if ext.startswith(".") else f".{ext}"
            urls = [u for u in urls if u.lower().split("?")[0].endswith(ext.lower())]
        if not urls:
            raise SecDataResearchError(
                f"no data files for {slug_or_alias!r}"
                + (f" with ext {ext!r}" if ext else "")
            )
        return sorted(urls, key=_sort_key_url, reverse=True)[0]

    # --- storage -------------------------------------------------------------

    def _dest_for(self, slug: str, url: str) -> Path:
        meta = next(p for p in self._page_catalog if p["slug"] == slug)
        return self.store_root / meta["section"] / slug / _basename(url)

    def download_file(
        self,
        url: str,
        dest: Optional[Union[str, Path]] = None,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Download one file; returns local path."""
        dest_path = Path(dest) if dest else self.store_root / "files" / _basename(url)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists() and not overwrite:
            return dest_path
        data = self._fetch_bytes(url)
        dest_path.write_bytes(data)
        return dest_path

    def download(
        self,
        slug_or_alias: str,
        dest_dir: Optional[Union[str, Path]] = None,
        *,
        latest_only: bool = True,
        kind: str = "data",
        overwrite: bool = False,
    ) -> List[Path]:
        """Scrape dataset page and store file(s) under store_root."""
        slug = self.resolve_slug(slug_or_alias)
        urls = self.list_files(slug, kind=kind)["data" if kind == "data" else kind]
        if kind == "docs":
            urls = self.list_files(slug, kind="docs")["docs"]
        elif kind != "data":
            raise SecDataResearchError("kind must be 'data' or 'docs'")
        if latest_only and urls:
            urls = [self.latest(slug)]
        root = Path(dest_dir) if dest_dir else self.store_root / "data" / slug
        saved: List[Path] = []
        for url in urls:
            dest = root / _basename(url) if dest_dir else self._dest_for(slug, url)
            saved.append(self.download_file(url, dest, overwrite=overwrite))
        self._write_manifest(slug, saved)
        return saved

    def sync(
        self,
        section: Optional[str] = None,
        dest_dir: Optional[Union[str, Path]] = None,
        *,
        latest_only: bool = True,
        min_data_files: int = 1,
    ) -> Dict[str, List[Path]]:
        """Batch-download datasets in a section (default: all with n_data>=1)."""
        pages = self.catalog(section=section)
        pages = [p for p in pages if p.get("n_data", 0) >= min_data_files]
        results: Dict[str, List[Path]] = {}
        for p in pages:
            try:
                results[p["slug"]] = self.download(
                    p["slug"],
                    dest_dir=dest_dir,
                    latest_only=latest_only,
                )
            except SecDataResearchError:
                continue
        return results

    def sync_universe(
        self,
        *,
        section: Optional[str] = None,
        cluster: Optional[str] = None,
        latest_only: bool = True,
        min_data_files: int = 0,
        dry_run: bool = False,
        overwrite: bool = False,
        on_progress: Optional[Any] = None,
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Path]]]:
        """Sync an entire section, cluster, or full universe.

        Pass ``dry_run=True`` to return the plan only (no downloads).
        ``on_progress(i, total, slug)`` called per dataset when syncing.
        """
        plan = self.plan_sync(
            section=section,
            cluster=cluster,
            latest_only=latest_only,
            min_data_files=min_data_files,
        )
        if dry_run:
            return plan
        total = len(plan)
        results: Dict[str, List[Path]] = {}
        for i, item in enumerate(plan, 1):
            slug = item["slug"]
            if on_progress:
                on_progress(i, total, slug)
            try:
                results[slug] = self.download(
                    slug,
                    latest_only=latest_only,
                    overwrite=overwrite,
                )
            except SecDataResearchError:
                results[slug] = []
        return results

    # --- parse / fetch -------------------------------------------------------

    def get(
        self,
        slug_or_alias: str,
        *,
        file: Optional[str] = None,
        url: Optional[str] = None,
        member: Optional[str] = None,
        coerce: bool = True,
        max_mb: float = 120,
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]], bytes]:
        """Fetch and parse a dataset file (latest or by basename substring).

        ZIP -> dict of member CSV rows (or one member if member= given).
        CSV/TSV -> rows. XLSX -> first sheet rows (needs openpyxl or pandas).
        XML -> raw bytes (caller parses).
        """
        if url:
            target = url
        elif file:
            urls = self.list_files(slug_or_alias, kind="data")["data"]
            matches = [u for u in urls if file.lower() in _basename(u).lower()]
            if not matches:
                raise SecDataResearchError(f"no file matching {file!r} for {slug_or_alias!r}")
            target = sorted(matches, key=_sort_key_url, reverse=True)[0]
        else:
            target = self.latest(slug_or_alias)
        raw = self._fetch_bytes(target, max_mb=max_mb)
        low = target.lower().split("?")[0]
        if low.endswith(".zip"):
            return self._parse_zip_bytes(raw, member=member, coerce=coerce)
        if low.endswith((".csv", ".tsv")):
            delim = "\t" if low.endswith(".tsv") else ","
            return self._parse_csv_bytes(raw, coerce=coerce, delimiter=delim)
        if low.endswith((".xlsx", ".xls")):
            return self._parse_xlsx_bytes(raw, coerce=coerce)
        if low.endswith(".xml"):
            return raw
        if low.endswith(".json"):
            return json.loads(raw.decode("utf-8", "replace"))
        raise SecDataResearchError(f"unsupported file type for parse: {target}")

    # --- transport -----------------------------------------------------------

    def _fetch_html(self, url: str) -> str:
        host, path = _path_from_url(url)
        parsed, status = manual_https_request(
            host,
            "GET",
            path,
            headers={"User-Agent": self.user_agent, "Accept": "text/html"},
        )
        resp = _MockResponse(parsed, status)
        if not resp.ok and not isinstance(parsed, str):
            raise SecDataResearchError(f"HTTP {resp.status_code} for {url}")
        text = parsed if isinstance(parsed, str) else resp.text
        if "Request Rate Threshold Exceeded" in text:
            raise SecDataResearchError(
                f"SEC rate limit hit for {url}; backoff and retry"
            )
        return text

    def _fetch_bytes(self, url: str, max_mb: float = 200) -> bytes:
        """Binary-safe download (ZIP/CSV/XLSX). Uses requests directly because
        the manual_https_request stub decodes bodies as UTF-8 text."""
        try:
            resp = self._http.get(url, timeout=120)
        except requests.RequestException as e:
            raise SecDataResearchError(f"request failed for {url}: {e}") from e
        if resp.status_code >= 400:
            raise SecDataResearchError(
                f"HTTP {resp.status_code} for {url}: {resp.text[:200]}"
            )
        data = resp.content
        cap = int(max_mb * 1024 * 1024)
        if len(data) > cap:
            raise SecDataResearchError(
                f"{url} is {len(data)/1e6:.1f}MB > max_mb={max_mb}"
            )
        if not data:
            raise SecDataResearchError(f"empty body from {url}")
        if b"Request Rate Threshold Exceeded" in data[:500]:
            raise SecDataResearchError(
                f"SEC rate limit hit for {url}; backoff and retry"
            )
        return data

    @staticmethod
    def _parse_downloads(html: str, base_url: str) -> Dict[str, List[str]]:
        data: List[str] = []
        docs: List[str] = []
        for m in re.finditer(r'href=["\']([^"\']+)["\']', html, re.I):
            href = unescape(m.group(1).split("#")[0])
            if not href or href.startswith("javascript:"):
                continue
            full = urljoin(base_url, href)
            if "sec.gov" not in full or not _is_download_url(full):
                continue
            if full.lower().split("?")[0].endswith(".pdf"):
                docs.append(full)
            else:
                data.append(full)
        seen: set[str] = set()
        data = [u for u in data if not (u in seen or seen.add(u))]  # type: ignore
        seen.clear()
        docs = [u for u in docs if not (u in seen or seen.add(u))]  # type: ignore
        data.sort(key=_sort_key_url, reverse=True)
        docs.sort(key=_sort_key_url, reverse=True)
        return {"data": data, "docs": docs}

    @staticmethod
    def _parse_csv_bytes(
        raw: bytes, *, coerce: bool, delimiter: str = ","
    ) -> List[Dict[str, Any]]:
        text = raw.decode("utf-8", "replace")
        rows = [dict(r) for r in csv.DictReader(io.StringIO(text), delimiter=delimiter)]
        return _coerce_rows(rows) if coerce else rows

    @staticmethod
    def _parse_zip_bytes(
        raw: bytes, *, member: Optional[str], coerce: bool
    ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        z = zipfile.ZipFile(io.BytesIO(raw))
        members = [n for n in z.namelist() if n.endswith((".csv", ".tsv", ".txt"))]

        def parse(name: str) -> List[Dict[str, Any]]:
            with z.open(name) as fh:
                data = fh.read()
            delim = "\t" if name.endswith(".tsv") else ","
            return SecDataResearchClient._parse_csv_bytes(data, coerce=coerce, delimiter=delim)

        if member is not None:
            cands = [member, member + ".csv", member + ".tsv"]
            match = [
                n
                for n in members
                if n in cands or n.split("/")[-1] in cands or member in n
            ]
            if not match:
                raise SecDataResearchError(
                    f"member {member!r} not in zip; members={members[:20]}"
                )
            return parse(match[0])
        return {n: parse(n) for n in members}

    @staticmethod
    def _parse_xlsx_bytes(raw: bytes, *, coerce: bool) -> List[Dict[str, Any]]:
        try:
            import pandas as pd
        except ImportError as e:
            raise SecDataResearchError(
                "pandas required to parse XLSX (private-fund stats Excel)"
            ) from e
        df = pd.read_excel(io.BytesIO(raw), sheet_name=0)
        rows = df.where(df.notna(), None).to_dict(orient="records")
        if coerce:
            return _coerce_rows(rows)
        return rows

    def _write_manifest(self, slug: str, paths: List[Path]) -> None:
        manifest_path = self.store_root / "manifest.json"
        manifest: Dict[str, Any] = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest[slug] = {
            "updated": datetime.now(timezone.utc).isoformat(),
            "files": [str(p) for p in paths],
        }
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def to_dataframe(rows: Sequence[Dict[str, Any]], columns: Optional[Sequence[str]] = None):
    try:
        import pandas as pd
    except ImportError as e:
        raise SecDataResearchError("pandas required for to_dataframe()") from e
    df = pd.DataFrame(list(rows))
    if columns is not None:
        df = df[[c for c in columns if c in df.columns]]
    return df


client = SecDataResearchClient()

catalog = client.catalog
describe = client.describe
list_files = client.list_files
latest = client.latest
download = client.download
get = client.get
sync = client.sync
sync_universe = client.sync_universe
plan_sync = client.plan_sync
summary = client.summary
cluster = client.cluster
refresh_catalog = client.refresh_catalog


# --- Interactive CLI (staging; strip before PRISM drop per api-clients.mdc) ---


def _prompt(msg: str, default: str = "") -> str:
    try:
        raw = input(f"{msg} [{default}]: " if default else f"{msg}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return raw or default


def _pick_slug(pages: List[Dict[str, Any]], label: str = "slug") -> Optional[str]:
    if not pages:
        print("  (empty list)")
        return None
    page_size = 20
    offset = 0
    while True:
        chunk = pages[offset : offset + page_size]
        print(f"\n  {label} ({offset + 1}-{offset + len(chunk)} of {len(pages)}):")
        for i, p in enumerate(chunk, offset + 1):
            nd = p.get("n_data", 0)
            print(f"    {i:3d}. {p['slug']:<52s} n_data={nd}")
        print("    n. next page   p. prev page   s. search filter   q. back")
        choice = _prompt("Pick number or command", "1").lower()
        if choice == "q":
            return None
        if choice == "n" and offset + page_size < len(pages):
            offset += page_size
            continue
        if choice == "s":
            q = _prompt("Filter substring")
            pages = [p for p in pages if q.lower() in p["slug"] or q.lower() in p.get("title", "").lower()]
            offset = 0
            continue
        if choice == "p" and offset >= page_size:
            offset -= page_size
            continue
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(pages):
                return pages[idx]["slug"]
        except ValueError:
            pass
        print(f"  invalid: {choice!r}")


def _menu_dataset_actions(c: SecDataResearchClient, slug: str) -> None:
    while True:
        print(f"\n  Dataset: {slug}")
        print("    1. describe (live scrape URLs)")
        print("    2. list data files")
        print("    3. list doc files (PDF)")
        print("    4. download latest data file")
        print("    5. download ALL data files")
        print("    6. fetch/parse latest (get)")
        print("    7. fetch/parse by file substring")
        print("    q. back")
        act = _prompt("Action", "1").lower()
        if act == "q":
            return
        try:
            if act == "1":
                d = c.describe(slug)
                print(f"    title: {d['title']}")
                print(f"    url:   {d['url']}")
                print(f"    data files ({len(d['data_files'])}):")
                for u in d["data_files"][:8]:
                    print(f"      {_basename(u)}")
                if len(d["data_files"]) > 8:
                    print(f"      ... +{len(d['data_files']) - 8} more")
            elif act == "2":
                for u in c.list_files(slug)["data"][:15]:
                    print(f"      {_basename(u)}")
            elif act == "3":
                for u in c.list_files(slug, kind="docs")["docs"][:10]:
                    print(f"      {_basename(u)}")
            elif act == "4":
                paths = c.download(slug, latest_only=True)
                print(f"    saved: {paths[0]} ({paths[0].stat().st_size / 1e6:.1f} MB)")
            elif act == "5":
                confirm = _prompt("Download ALL files? type YES", "")
                if confirm != "YES":
                    print("    cancelled")
                    continue
                paths = c.download(slug, latest_only=False)
                print(f"    saved {len(paths)} files")
            elif act == "6":
                data = c.get(slug)
                if isinstance(data, dict):
                    print(f"    ZIP members: {list(data.keys())[:10]}")
                    first = next(iter(data.values()))
                    print(f"    first member rows: {len(first)}")
                elif isinstance(data, list):
                    print(f"    rows: {len(data)}")
                else:
                    print(f"    bytes: {len(data)}")
            elif act == "7":
                pat = _prompt("File substring")
                data = c.get(slug, file=pat)
                if isinstance(data, dict):
                    print(f"    members: {list(data.keys())}")
                elif isinstance(data, list):
                    print(f"    rows: {len(data)}")
        except SecDataResearchError as e:
            print(f"    ERROR: {e}")


def _menu_browse_cluster(c: SecDataResearchClient) -> None:
    print("\n  Clusters:")
    keys = sorted(CLUSTERS.keys())
    for i, k in enumerate(keys, 1):
        print(f"    {i}. {k} — {CLUSTERS[k]['label']}")
    sel = _prompt("Cluster number or name", "form_pf_adjacent")
    try:
        key = keys[int(sel) - 1] if sel.isdigit() else sel.strip().lower()
    except (ValueError, IndexError):
        key = sel.strip().lower()
    pages = c.cluster(key)
    print(f"  {len(pages)} pages in cluster {key!r}")
    slug = _pick_slug(pages, key)
    if slug:
        _menu_dataset_actions(c, slug)


def _menu_browse_section(c: SecDataResearchClient) -> None:
    print("\n  Sections:")
    for i, sec in enumerate(SECTIONS, 1):
        n = len(c.catalog(section=sec))
        print(f"    {i}. {sec} ({n} pages)")
    sel = _prompt("Section number or name", "1")
    try:
        sec = SECTIONS[int(sel) - 1] if sel.isdigit() else sel.strip()
    except (ValueError, IndexError):
        sec = sel.strip()
    pages = c.catalog(section=sec)
    slug = _pick_slug(pages, sec)
    if slug:
        _menu_dataset_actions(c, slug)


def _menu_sync(c: SecDataResearchClient) -> None:
    print("\n  Sync scope:")
    print("    1. form_pf_adjacent cluster")
    print("    2. data_library_all")
    print("    3. investment_management_all")
    print("    4. statistics_all")
    print("    5. full_universe (ALL 200 pages)")
    print("    6. custom section")
    print("    7. custom cluster name")
    scope = _prompt("Scope", "1")
    cluster_name = None
    section = None
    if scope == "1":
        cluster_name = "form_pf_adjacent"
    elif scope == "2":
        cluster_name = "data_library_all"
    elif scope == "3":
        cluster_name = "investment_management_all"
    elif scope == "4":
        cluster_name = "statistics_all"
    elif scope == "5":
        cluster_name = "full_universe"
    elif scope == "6":
        section = _prompt("Section name", "data_library")
    elif scope == "7":
        cluster_name = _prompt("Cluster name", "form_pf_adjacent")
    latest = _prompt("Latest file only? (y/n)", "y").lower() != "n"
    plan = c.plan_sync(section=section, cluster=cluster_name, latest_only=latest)
    print(f"\n  Plan: {len(plan)} datasets")
    for item in plan[:12]:
        print(f"    {item['slug']:<50s} n_data={item['n_data']}")
    if len(plan) > 12:
        print(f"    ... +{len(plan) - 12} more")
    mode = _prompt("dry-run only? (y/n/run)", "y").lower()
    if mode == "y":
        return
    if mode != "run" and mode != "n":
        return
    confirm = _prompt(f"RUN sync on {len(plan)} datasets? type YES", "")
    if confirm != "YES":
        print("  cancelled")
        return
    import time as _time

    t0 = _time.time()
    last = t0

    def progress(i: int, total: int, slug: str) -> None:
        nonlocal last
        now = _time.time()
        if now - last >= 5 or i == total:
            print(f"  [{i}/{total}] {slug}")
            last = now

    results = c.sync_universe(
        section=section,
        cluster=cluster_name,
        latest_only=latest,
        on_progress=progress,
    )
    ok = sum(1 for v in results.values() if v)
    print(f"\n  done: {ok}/{len(results)} datasets saved files")


def interactive_menu(c: Optional[SecDataResearchClient] = None) -> None:
    """Nested interactive CLI — default entry when run without arguments."""
    c = c or client
    print("\n" + "=" * 72)
    print("  SEC Data & Research — full universe scraper")
    print(f"  store: {c.store_root}")
    print(f"  pages: {len(c.catalog())} | clusters: {len(CLUSTERS)}")
    print("=" * 72)

    while True:
        print("\n  MAIN MENU")
        print("    1. Universe summary")
        print("    2. Browse by section (data_library / IM / statistics)")
        print("    3. Browse by cluster (form_pf_adjacent, full_universe, ...)")
        print("    4. Search datasets")
        print("    5. Jump to dataset by slug/alias")
        print("    6. Sync planner / runner (dry-run or full universe)")
        print("    7. Refresh catalog from sec.gov (live crawl)")
        print("    8. Set store root")
        print("    q. Quit")
        choice = _prompt("Choice", "1").lower()
        if choice == "q":
            return
        if choice == "1":
            s = c.summary()
            print(json.dumps(s, indent=2))
            print("\n  form_pf_adjacent cluster pages:", s["clusters"].get("form_pf_adjacent"))
        elif choice == "2":
            _menu_browse_section(c)
        elif choice == "3":
            _menu_browse_cluster(c)
        elif choice == "4":
            q = _prompt("Search query")
            pages = c.catalog(query=q)
            print(f"  {len(pages)} matches")
            slug = _pick_slug(pages, f"search:{q}")
            if slug:
                _menu_dataset_actions(c, slug)
        elif choice == "5":
            slug_in = _prompt("Slug or alias (e.g. form_pf, n_mfp, 13f)")
            try:
                slug = c.resolve_slug(slug_in)
                _menu_dataset_actions(c, slug)
            except SecDataResearchError as e:
                print(f"  ERROR: {e}")
        elif choice == "6":
            _menu_sync(c)
        elif choice == "7":
            print("  crawling sec.gov (may take ~2 min)...")
            pages = c.refresh_catalog()
            print(f"  refreshed: {len(pages)} pages")
        elif choice == "8":
            new_root = _prompt("Store root path", str(c.store_root))
            c.store_root = Path(new_root)
            c.store_root.mkdir(parents=True, exist_ok=True)
            print(f"  store set to {c.store_root}")
        else:
            print(f"  unknown choice: {choice!r}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Argparse + interactive menu. Bare invocation opens interactive_menu()."""
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="SEC Data & Research scraper — full universe CLI",
    )
    parser.add_argument("--summary", action="store_true", help="print universe summary")
    parser.add_argument("--catalog", action="store_true")
    parser.add_argument("--section", default=None)
    parser.add_argument("--query", default=None)
    parser.add_argument("--cluster", default=None, help="cluster name e.g. form_pf_adjacent")
    parser.add_argument("--describe", metavar="SLUG")
    parser.add_argument("--list-files", metavar="SLUG")
    parser.add_argument("--get", metavar="SLUG")
    parser.add_argument("--file", default=None)
    parser.add_argument("--member", default=None)
    parser.add_argument("--download", metavar="SLUG")
    parser.add_argument("--all-files", action="store_true")
    parser.add_argument("--sync", action="store_true")
    parser.add_argument("--universe", action="store_true", help="sync full_universe cluster")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--refresh-catalog", action="store_true")
    parser.add_argument("--store", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)

    c = SecDataResearchClient(store_root=args.store) if args.store else client

    if args.summary:
        print(json.dumps(c.summary(), indent=2))
        return 0
    if args.catalog:
        for p in c.catalog(section=args.section, query=args.query):
            print(f"{p['section']:<22s} {p['slug']:<50s} n_data={p['n_data']}")
        return 0
    if args.cluster:
        for p in c.cluster(args.cluster):
            print(f"{p['slug']:<55s} {p['title'][:50]}")
        return 0
    if args.describe:
        print(json.dumps(c.describe(args.describe), indent=2)[:4000])
        return 0
    if args.list_files:
        files = c.list_files(args.list_files, kind="all")
        for u in files.get("data", []) + files.get("docs", []):
            print(u)
        return 0
    if args.get:
        data = c.get(args.get, file=args.file, member=args.member)
        if isinstance(data, dict):
            print(json.dumps({k: len(v) for k, v in data.items()}, indent=2))
        elif isinstance(data, list):
            print(f"rows={len(data)}")
        else:
            print(f"bytes={len(data)}")
        return 0
    if args.download:
        paths = c.download(args.download, latest_only=not args.all_files)
        for p in paths:
            print(p)
        return 0
    if args.sync or args.universe:
        plan = c.plan_sync(
            cluster="full_universe" if args.universe else None,
            section=args.section,
            latest_only=not args.all_files,
        )
        if args.dry_run:
            print(json.dumps(plan, indent=2))
            return 0
        results = c.sync_universe(
            cluster="full_universe" if args.universe else None,
            section=args.section,
            latest_only=not args.all_files,
            on_progress=lambda i, t, s: print(f"[{i}/{t}] {s}"),
        )
        print(f"synced {sum(1 for v in results.values() if v)}/{len(results)}")
        return 0
    if args.refresh_catalog:
        n = len(c.refresh_catalog())
        print(f"refreshed {n} pages")
        return 0

    if sys.stdin.isatty():
        interactive_menu(c)
        return 0
    print("No args and non-TTY stdin; use --summary or --catalog", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
