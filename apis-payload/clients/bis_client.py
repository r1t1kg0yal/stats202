"""BIS SDMX Statistics API client (PRISM-side library module).

Library-only — no CLI surface. Sandbox-injected as `bis_client` per
`prism/api-clients.md` §4. Universe-first design: the entire BIS
SDMX ontology (29 dataflows, 93 dimension codelists, ~7,200 codes)
is embedded as a compact JSON literal so PRISM can DISCOVER what's
available before constructing a query.

Five public layers:

  1. Discovery     list_dataflows / get_dataflow / get_dimensions /
                   get_codelist / search_dataflows / search_codes /
                   describe   — read the ontology

  2. Availability  check_availability(flow_id, **dim_values)  — ask
                   BIS what series actually exist for a partial key
                   BEFORE sending the data query.  Eliminates the
                   "right-shape-key, no-data" empty-result class.

  3. Query         build_key(flow_id, **dim_values)
                   query(flow_id, key=None, **dim_values)
                   — kwarg-based key construction with codelist
                   validation at the boundary.  PRISM never has to
                   remember positional dimension order or memorize
                   codes.

  4. Composite     recipe_contagion / recipe_eurodollar /
                   recipe_currency_breakdown /
                   recipe_shadow_banking_full
                   — multi-query pre-built analyses that return
                   structured dicts.  Drop trivial single-query
                   wrappers (PRISM does those directly via query()).

  5. Refresh       refresh_ontology()  — offline tool to rebuild
                   _BIS_ONTOLOGY from a fresh scrape of /structure
                   endpoints.  PRISM does NOT call this; it's run
                   periodically to keep the embedded data fresh.

Imports `manual_https_request` from PRISM's GS-proxy transport layer
(`gs_app_proxy_negotiate.py`); in staging the same import resolves
to the local stub mirror at
`projects/apis/ai_development/mcp/gs_app_proxy_negotiate.py` so this
file runs identically in both environments.

BIS is the canonical example of why universe-first matters: the
SDMX schema has 12 dimensions on LBS and 11 on CBS with dozens of
valid codes per dimension; hardcoded recipe keys silently 404 when
PRISM strays a single dim off-pattern.  By exposing the full
ontology + availability layer, every PRISM query is grounded.

Surface:
  Constants    BASE_URL, BASE_HOST, DEFAULT_VERSION, DATAFLOW_ALIASES
  Class        BISClient
                 _api_request, _data_request, _availability_request
                 list_dataflows, get_dataflow, get_dimensions,
                 get_codelist, search_dataflows, search_codes,
                 describe, check_availability, build_key, query,
                 recipe_*, refresh_ontology
  Module helpers    a thin wrapper for each public method on the
                    default client instance, so PRISM can call
                    `bis_client.query(...)` directly.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from ai_development.mcp.gs_app_proxy_negotiate import manual_https_request


# ─── Constants ───────────────────────────────────────────────────────────

BASE_URL = "https://stats.bis.org/api/v2"
BASE_HOST = "stats.bis.org"

# All BIS dataflows currently use version 1.0.  refresh_ontology() will
# pick up any version drift and bump per-flow if BIS revises a DSD.
DEFAULT_VERSION = "1.0"

# Headers BIS expects for SDMX-JSON.
_STRUCT_ACCEPT = "application/vnd.sdmx.structure+json;version=1.0.0"
_DATA_ACCEPT = "application/vnd.sdmx.data+json;version=1.0.0"

# Friendly dataflow aliases.  Strict enumeration: each maps to a real
# embedded dataflow id.  Keys lower-case + hyphenated; values match
# the SDMX flow_id verbatim.
DATAFLOW_ALIASES: Dict[str, str] = {
    "lbs":                    "WS_LBS_D_PUB",
    "cbs":                    "WS_CBS_PUB",
    "credit":                 "WS_TC",
    "total-credit":           "WS_TC",
    "credit-gap":             "WS_CREDIT_GAP",
    "dsr":                    "WS_DSR",
    "policy-rates":           "WS_CBPOL",
    "central-bank-assets":    "WS_CBTA",
    "eer":                    "WS_EER",
    "fx":                     "WS_EER",
    "exchange-rates":         "WS_XRU",
    "property":               "WS_SPP",
    "property-prices":        "WS_SPP",
    "commercial-property":    "WS_CPP",
    "detailed-property":      "WS_DPP",
    "cpi":                    "WS_LONG_CPI",
    "consumer-prices":        "WS_LONG_CPI",
    "liquidity":              "WS_GLI",
    "global-liquidity":       "WS_GLI",
    "etd":                    "WS_XTD_DERIV",
    "exchange-traded-deriv":  "WS_XTD_DERIV",
    "otc":                    "WS_OTC_DERIV2",
    "otc-derivatives":        "WS_OTC_DERIV2",
    "otc-turnover":           "WS_DER_OTC_TOV",
    "debt-securities":        "WS_DEBT_SEC2_PUB",
    "international-debt":     "WS_DEBT_SEC2_PUB",  # WS_IDS_PUB retired
    "national-debt":          "WS_NA_SEC_DSS",
    "national-securities":    "WS_NA_SEC_DSS",  # NA_SEC_C3 published-but-empty
    "release-calendar":       "BIS_REL_CAL",
    # CPMI payment system (6 flows, niche but exposed)
    "cpmi-cashless":          "WS_CPMI_CASHLESS",
    "cpmi-systems":           "WS_CPMI_SYSTEMS",
    "cpmi-participants":      "WS_CPMI_PARTICIP",
    "cpmi-devices":           "WS_CPMI_DEVICES",
    "cpmi-institutions":      "WS_CPMI_INSTITUT",
    "cpmi-macro":             "WS_CPMI_MACRO",
    "cpmi-comparative-1":     "WS_CPMI_CT1",
    "cpmi-comparative-2":     "WS_CPMI_CT2",
}


# ─── Embedded BIS ontology ─────────────────────────────────────────────────
#
# Compacted from a scrape of /structure/dataflow/BIS and
# /structure/datastructure/BIS/<DSD>/<VER>?references=children.
#
# Contents:
#   "dataflows"  → 29 entries.  Each has name, description, dsd_id, and an
#                  ordered list of dimensions (id, position, codelist).
#   "codelists"  → 93 entries (DIMENSION codelists only — attribute-only
#                  codelists like CL_ORGANISATION / CL_OBS_STATUS are
#                  excluded from the embedded set; PRISM never queries
#                  by them, and they're returned in response data
#                  anyway).
#
# To refresh: call `refresh_ontology(write_to=__file__)` from outside
# PRISM (it runs ~5 minutes worth of /structure HTTPS calls).  Do NOT
# call this from inside the sandbox.

_BIS_ONTOLOGY_JSON = r"""
{"dataflows":{"BIS_REL_CAL":{"name":"BIS_RELEASE_CALENDAR","description":"","dsd_id":"BIS_RELEASE_CALENDAR","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"CATEGORY","pos":2,"cl":"CL_REL_CAT"},{"id":"RELEASE_TYPE","pos":3,"cl":"CL_REL_TYPE"}],"attributes":[{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"COMMENTARY","cl":null,"status":"Conditional"}],"typical_freq":"Q","series_count":15,"first_period":"2023-Q1","last_period":"2026-Q2"},"WS_CBPOL":{"name":"Central bank policy rates","description":"The interest rate which best captures the monetary authorities' policy intentions.","dsd_id":"BIS_CBPOL","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_BIS_GL_REF_AREA"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"COMPILATION","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"SOURCE_REF","cl":null,"status":"Conditional"},{"id":"SUPP_INFO_BREAKS","cl":null,"status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"M","series_count":49,"first_period":"1954-07","last_period":"2026-04"},"WS_CBS_PUB":{"name":"Consolidated banking","description":"","dsd_id":"BIS_CBS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"L_MEASURE","pos":2,"cl":"CL_STOCK_FLOW"},{"id":"L_REP_CTY","pos":3,"cl":"CL_BIS_IF_REF_AREA"},{"id":"CBS_BANK_TYPE","pos":4,"cl":"CL_BIS_IF_REF_AREA"},{"id":"CBS_BASIS","pos":5,"cl":"CL_CBS_BASIS"},{"id":"L_POSITION","pos":6,"cl":"CL_L_POSITION"},{"id":"L_INSTR","pos":7,"cl":"CL_L_INSTR"},{"id":"REM_MATURITY","pos":8,"cl":"CL_ISSUE_MAT"},{"id":"CURR_TYPE_BOOK","pos":9,"cl":"CL_CURRENCY_3POS"},{"id":"L_CP_SECTOR","pos":10,"cl":"CL_L_SECTOR"},{"id":"L_CP_COUNTRY","pos":11,"cl":"CL_BIS_IF_REF_AREA"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"ORG_VISIBILITY","cl":"CL_ORG_VISIBILITY","status":"Conditional"},{"id":"TITLE_GRP","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_CURRENCY_3POS","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"Q","series_count":228026,"first_period":"1983-Q4","last_period":"2025-Q4"},"WS_CBTA":{"name":"Central bank total assets","description":"","dsd_id":"CBTA","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_BIS_IF_REF_AREA"},{"id":"COMP_METHOD","pos":3,"cl":"CL_BSI_METHOD"},{"id":"UNIT_MEASURE","pos":4,"cl":"CL_UNIT"},{"id":"CURRENCY","pos":5,"cl":"CL_CURRENCY"},{"id":"TRANSFORMATION","pos":6,"cl":"CL_TRANSFORMATION"}],"attributes":[{"id":"DATA_COMP","cl":null,"status":"Conditional"},{"id":"FISCAL_YEAR","cl":null,"status":"Conditional"},{"id":"CONF_STATUS","cl":"CL_CONF_STATUS","status":"Mandatory"},{"id":"METHOD_REF","cl":null,"status":"Conditional"},{"id":"COLLECTION_DETAIL","cl":null,"status":"Conditional"},{"id":"COMMENT_DSET","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"BREAKS","cl":"CL_BREAK_REASON","status":"Conditional"},{"id":"SUPP_INFO_BREAKS","cl":null,"status":"Conditional"},{"id":"COMPILING_ORG","cl":null,"status":"Conditional"},{"id":"DISS_ORG","cl":"CL_ORGANISATION","status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"}],"typical_freq":"Q","series_count":211,"first_period":"1914-11","last_period":"2026-02"},"WS_CPMI_CASHLESS":{"name":"CPMI cashless payments","description":"CPMI cashless payments (T5,T6)","dsd_id":"CPMI_CASHLESS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"MEASURE","pos":3,"cl":"CL_CPMI_MEASURE"},{"id":"INSTRUMENT_TYPE","pos":4,"cl":"CL_TRAN_INSTR_TYPE"},{"id":"DIRECTION","pos":5,"cl":"CL_TRANS_DIR"},{"id":"TERMINAL_LOC","pos":6,"cl":"CL_LOCATION"},{"id":"CARD_ISS_LOC","pos":7,"cl":"CL_LOCATION"},{"id":"DEV_STATE_TECH","pos":8,"cl":"CL_DEV_STATE_TECH"},{"id":"TERMINAL_TYPE","pos":9,"cl":"CL_TERMINAL_TYPE"},{"id":"CARD_FCT","pos":10,"cl":"CL_CARD_FCT"},{"id":"PAYMT_SPEED","pos":11,"cl":"CL_PAYMT_SPD"},{"id":"ISSUER_OR_ONUS","pos":12,"cl":"CL_DEVISS_ONUSP"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"OLD_TABLE","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":1528,"first_period":"2012","last_period":"2024"},"WS_CPMI_CT1":{"name":"CPMI comparative tables type 1","description":"CPMI comparative tables type 1","dsd_id":"CPMI_CT1","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"INDICATOR_CT","pos":3,"cl":"CL_CT_INDICATORS"},{"id":"MEASURE","pos":4,"cl":"CL_CPMI_MEASURE"},{"id":"UNIT_MEASURE","pos":5,"cl":"CL_CPMI_CT_UNIT"},{"id":"INSTRUMENT_TYPE_CT","pos":6,"cl":"CL_CT_INSTR_TYPE"},{"id":"WITH_AND_DEP","pos":7,"cl":"CL_CT_W_AND_DEP"},{"id":"TERMINAL_TYPE_CT","pos":8,"cl":"CL_CT_TERM_TYPES"},{"id":"CARD_TYPE","pos":9,"cl":"CL_CT_CARD_TYPES"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"}],"typical_freq":"A","series_count":5303,"first_period":"2012","last_period":"2024"},"WS_CPMI_CT2":{"name":"CPMI comparative tables type 2","description":"CPMI comparative tables type 2","dsd_id":"CPMI_CT2","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"SYSTEM_TYPE","pos":3,"cl":"CL_CPMI_SYST_TYPE"},{"id":"SYSTEM","pos":4,"cl":"CL_CPMI_SYSTEMS"},{"id":"INDICATOR_CT","pos":5,"cl":"CL_CT_INDICATORS"},{"id":"MEASURE","pos":6,"cl":"CL_CPMI_MEASURE"},{"id":"UNIT_MEASURE","pos":7,"cl":"CL_CPMI_CT_UNIT"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"}],"typical_freq":"A","series_count":1847,"first_period":"2012","last_period":"2024"},"WS_CPMI_DEVICES":{"name":"CPMI payment devices","description":"CPMI payment devices (T4)","dsd_id":"CPMI_DEVICES","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"DEVICE_TYPE","pos":3,"cl":"CL_DEVICE_TYPE"},{"id":"FUNCTION","pos":4,"cl":"CL_DEVICE_FCT"},{"id":"SUB_FUNCTION","pos":5,"cl":"CL_DEVICE_SUB_FCT"},{"id":"TECHNOLOGY","pos":6,"cl":"CL_DEVICE_TECHNOL"},{"id":"ISSUER","pos":7,"cl":"CL_DEVICE_ISSUER"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OLD_TABLE","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":276,"first_period":"2012","last_period":"2024"},"WS_CPMI_INSTITUT":{"name":"CPMI institutions","description":"CPMI institutions (T3)","dsd_id":"CPMI_INSTITUTIONS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"INSTITUTION_TYPE","pos":3,"cl":"CL_CPMI_INST_TYPE"},{"id":"MEASURE","pos":4,"cl":"CL_CPMI_MEASURE"},{"id":"INDICATOR","pos":5,"cl":"CL_CPMI_INDICATORS"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OLD_TABLE","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":615,"first_period":"2012","last_period":"2024"},"WS_CPMI_MACRO":{"name":"CPMI macro","description":"CPMI macro (T1,T2)","dsd_id":"CPMI_MACRO","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"BIS_TOPIC","pos":2,"cl":"CL_CPMI_TOPIC"},{"id":"REP_CTY","pos":3,"cl":"CL_BIS_GL_REF_AREA"},{"id":"BIS_SUFFIX","pos":4,"cl":"CL_CPMI_SUFFIX"}],"attributes":[{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"BIS_UNIT","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"TITLE","cl":null,"status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"A","series_count":675,"first_period":"2012","last_period":"2024"},"WS_CPMI_PARTICIP":{"name":"CPMI participants","description":"CPMI participants (T7,T10,T12,T15)","dsd_id":"CPMI_PARTICIPANTS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"SYSTEM_TYPE","pos":3,"cl":"CL_CPMI_SYST_TYPE"},{"id":"SYSTEM","pos":4,"cl":"CL_CPMI_SYSTEMS"},{"id":"PART_TYPE","pos":5,"cl":"CL_CPMI_PART_TYPE"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"OLD_TABLE","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":2045,"first_period":"2012","last_period":"2024"},"WS_CPMI_SYSTEMS":{"name":"CPMI systems","description":"CPMI systems (T8-9-11-13-14-16-17-18-19)","dsd_id":"CPMI_SYSTEMS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REP_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"MEASURE","pos":3,"cl":"CL_CPMI_MEASURE"},{"id":"SYSTEM_TYPE","pos":4,"cl":"CL_CPMI_SYST_TYPE"},{"id":"SYSTEM","pos":5,"cl":"CL_CPMI_SYSTEMS"},{"id":"INSTRUMENT_TYPE","pos":6,"cl":"CL_CPMI_INSTR_TYP"},{"id":"OTHER_PS_TRANS","pos":7,"cl":"CL_CPMI_SYSTEMS"},{"id":"TYPE_OF_INFO","pos":8,"cl":"CL_CPMI_INFO"}],"attributes":[{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"TABLE","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"OLD_TABLE","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":3138,"first_period":"2012","last_period":"2024"},"WS_CPP":{"name":"Commercial property prices","description":"","dsd_id":"BIS_PROP_PRICES","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_AREA"},{"id":"COVERED_AREA","pos":3,"cl":"CL_RE_COVERED_AREA"},{"id":"RE_TYPE","pos":4,"cl":"CL_RE_TYPE"},{"id":"RE_VINTAGE","pos":5,"cl":"CL_RE_VINTAGE"},{"id":"COMPILING_ORG","pos":6,"cl":"CL_SOURCE"},{"id":"PRICED_UNIT","pos":7,"cl":"CL_PP_PRICED_UNIT"},{"id":"ADJUST_CODED","pos":8,"cl":"CL_ADJUST"}],"attributes":[{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"BREAKS","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"COLLECTION_DETAIL","cl":null,"status":"Conditional"},{"id":"COVERAGE","cl":null,"status":"Conditional"},{"id":"DATA_COMP","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"DOC_METHOD","cl":null,"status":"Conditional"},{"id":"MEASURE_DETAIL","cl":null,"status":"Conditional"},{"id":"META_UPDATE","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"PUBLICATIONS","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"TITLE_GRP","cl":null,"status":"Mandatory"},{"id":"TITLE_GRP_COMPL","cl":null,"status":"Conditional"},{"id":"TITLE_GRP_NAT","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"Q","series_count":52,"first_period":"1945-Q4","last_period":"2025-Q4"},"WS_CREDIT_GAP":{"name":"Credit-to-GDP gaps","description":"","dsd_id":"BIS_CREDIT_GAP","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"BORROWERS_CTY","pos":2,"cl":"CL_BIS_GL_REF_AREA"},{"id":"TC_BORROWERS","pos":3,"cl":"CL_TC_BORROWERS"},{"id":"TC_LENDERS","pos":4,"cl":"CL_L_SECTOR"},{"id":"CG_DTYPE","pos":5,"cl":"CL_CREDT_GAP_DTYPE"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Conditional"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Conditional"}],"typical_freq":"Q","series_count":132,"first_period":"1957-Q4","last_period":"2025-Q3"},"WS_DEBT_SEC2_PUB":{"name":"International debt securities (BIS-compiled)","description":"","dsd_id":"BIS_DEBT_SEC2","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"ISSUER_RES","pos":2,"cl":"CL_BIS_IF_REF_AREA"},{"id":"ISSUER_NAT","pos":3,"cl":"CL_BIS_IF_REF_AREA"},{"id":"ISSUER_BUS_IMM","pos":4,"cl":"CL_ISSUER_BUS"},{"id":"ISSUER_BUS_ULT","pos":5,"cl":"CL_ISSUER_BUS"},{"id":"MARKET","pos":6,"cl":"CL_MARKET"},{"id":"ISSUE_TYPE","pos":7,"cl":"CL_ISSUE_TYPE"},{"id":"ISSUE_CUR_GROUP","pos":8,"cl":"CL_CUR_GROUP"},{"id":"ISSUE_CUR","pos":9,"cl":"CL_ISSUE_CUR"},{"id":"ISSUE_OR_MAT","pos":10,"cl":"CL_ISSUE_MAT"},{"id":"ISSUE_RE_MAT","pos":11,"cl":"CL_ISSUE_MAT"},{"id":"ISSUE_RATE","pos":12,"cl":"CL_ISSUE_RATE"},{"id":"ISSUE_RISK","pos":13,"cl":"CL_ISSUE_RISK"},{"id":"ISSUE_COL","pos":14,"cl":"CL_ISSUE_COL"},{"id":"MEASURE","pos":15,"cl":"CL_MEASURE"}],"attributes":[{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"Q","series_count":223476,"first_period":"1966-Q1","last_period":"2025-Q4"},"WS_DER_OTC_TOV":{"name":"OTC derivatives turnover","description":"OTC derivatives and FX spot - turnover","dsd_id":"BIS_DER","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"DER_TYPE","pos":2,"cl":"CL_OD_TYPE"},{"id":"DER_INSTR","pos":3,"cl":"CL_DER_INSTR"},{"id":"DER_RISK","pos":4,"cl":"CL_MARKET_RISK"},{"id":"DER_REP_CTY","pos":5,"cl":"CL_BIS_IF_REF_AREA"},{"id":"DER_SECTOR_CPY","pos":6,"cl":"CL_SECTOR_CPY"},{"id":"DER_CPC","pos":7,"cl":"CL_BIS_IF_REF_AREA"},{"id":"DER_SECTOR_UDL","pos":8,"cl":"CL_SECTOR_UDL"},{"id":"DER_CURR_LEG1","pos":9,"cl":"CL_BIS_UNIT"},{"id":"DER_CURR_LEG2","pos":10,"cl":"CL_BIS_UNIT"},{"id":"DER_ISSUE_MAT","pos":11,"cl":"CL_ISSUE_MAT"},{"id":"DER_RATING","pos":12,"cl":"CL_RATING"},{"id":"DER_EX_METHOD","pos":13,"cl":"CL_EX_METHOD"},{"id":"DER_BASIS","pos":14,"cl":"CL_DER_BASIS"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"A","series_count":79681,"first_period":"1986","last_period":"2025"},"WS_DPP":{"name":"Detailed residential property prices","description":"","dsd_id":"BIS_PROP_PRICES","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_AREA"},{"id":"COVERED_AREA","pos":3,"cl":"CL_RE_COVERED_AREA"},{"id":"RE_TYPE","pos":4,"cl":"CL_RE_TYPE"},{"id":"RE_VINTAGE","pos":5,"cl":"CL_RE_VINTAGE"},{"id":"COMPILING_ORG","pos":6,"cl":"CL_SOURCE"},{"id":"PRICED_UNIT","pos":7,"cl":"CL_PP_PRICED_UNIT"},{"id":"ADJUST_CODED","pos":8,"cl":"CL_ADJUST"}],"attributes":[{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"BREAKS","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"COLLECTION_DETAIL","cl":null,"status":"Conditional"},{"id":"COVERAGE","cl":null,"status":"Conditional"},{"id":"DATA_COMP","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"DOC_METHOD","cl":null,"status":"Conditional"},{"id":"MEASURE_DETAIL","cl":null,"status":"Conditional"},{"id":"META_UPDATE","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"PUBLICATIONS","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"TITLE_GRP","cl":null,"status":"Mandatory"},{"id":"TITLE_GRP_COMPL","cl":null,"status":"Conditional"},{"id":"TITLE_GRP_NAT","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"Q","series_count":255,"first_period":"1963-Q1","last_period":"2025-Q4"},"WS_DSR":{"name":"Debt service ratios","description":"Debt service costs - comprising interest payments and debt amortisations - as a proportion of income. The DSR is a measure of the financial constraints imposed by indebtedness.","dsd_id":"BIS_DSR","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"BORROWERS_CTY","pos":2,"cl":"CL_AREA"},{"id":"DSR_BORROWERS","pos":3,"cl":"CL_TC_BORROWERS"}],"attributes":[{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"Q","series_count":66,"first_period":"1999-Q1","last_period":"2025-Q3"},"WS_EER":{"name":"Effective exchange rates","description":"","dsd_id":"BIS_EER","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"EER_TYPE","pos":2,"cl":"CL_EER_TYPE"},{"id":"EER_BASKET","pos":3,"cl":"CL_EER_BASKET"},{"id":"REF_AREA","pos":4,"cl":"CL_AREA"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"M","series_count":181,"first_period":"1994-01","last_period":"2026-03"},"WS_GLI":{"name":"Global liquidity indicators","description":"","dsd_id":"BIS_GLI","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"CURR_DENOM","pos":2,"cl":"CL_CURRENCY_3POS"},{"id":"BORROWERS_CTY","pos":3,"cl":"CL_BIS_IF_REF_AREA"},{"id":"BORROWERS_SECTOR","pos":4,"cl":"CL_L_SECTOR"},{"id":"LENDERS_SECTOR","pos":5,"cl":"CL_L_SECTOR"},{"id":"L_POS_TYPE","pos":6,"cl":"CL_L_POS_TYPE"},{"id":"L_INSTR","pos":7,"cl":"CL_L_INSTR"},{"id":"UNIT_MEASURE","pos":8,"cl":"CL_BIS_UNIT"}],"attributes":[{"id":"TITLE","cl":null,"status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Conditional"}],"typical_freq":"Q","series_count":225,"first_period":"2000-Q1","last_period":"2025-Q4"},"WS_LBS_D_PUB":{"name":"Locational banking","description":"","dsd_id":"BIS_LBS_DISS","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"L_MEASURE","pos":2,"cl":"CL_STOCK_FLOW"},{"id":"L_POSITION","pos":3,"cl":"CL_L_POSITION"},{"id":"L_INSTR","pos":4,"cl":"CL_L_INSTR"},{"id":"L_DENOM","pos":5,"cl":"CL_CURRENCY_3POS"},{"id":"L_CURR_TYPE","pos":6,"cl":"CL_L_CURR_TYPE"},{"id":"L_PARENT_CTY","pos":7,"cl":"CL_BIS_IF_REF_AREA"},{"id":"L_REP_BANK_TYPE","pos":8,"cl":"CL_L_BANK_TYPE"},{"id":"L_REP_CTY","pos":9,"cl":"CL_BIS_IF_REF_AREA"},{"id":"L_CP_SECTOR","pos":10,"cl":"CL_L_SECTOR"},{"id":"L_CP_COUNTRY","pos":11,"cl":"CL_BIS_IF_REF_AREA"},{"id":"L_POS_TYPE","pos":12,"cl":"CL_L_POS_TYPE"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"ORG_VISIBILITY","cl":"CL_ORG_VISIBILITY","status":"Conditional"},{"id":"TITLE_GRP","cl":null,"status":"Conditional"},{"id":"UNIT_MEASURE","cl":"CL_CURRENCY_3POS","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"}],"typical_freq":"Q","series_count":608570,"first_period":"1977-Q4","last_period":"2025-Q4"},"WS_LONG_CPI":{"name":"Consumer prices statistics","description":"An index that measures the average change in the price of consumer items (goods and services) purchased by households in a given period. It is based on regular surveys of representative consumption baskets.","dsd_id":"BIS_LONG_CPI","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_AREA"},{"id":"UNIT_MEASURE","pos":3,"cl":"CL_BIS_UNIT"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Conditional"},{"id":"BREAKS","cl":null,"status":"Conditional"},{"id":"COVERAGE","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"M","series_count":126,"first_period":"1913-01","last_period":"2026-03"},"WS_NA_SEC_C3":{"name":"BIS debt securities statistics","description":"","dsd_id":"NA_SEC","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"ADJUSTMENT","pos":2,"cl":"CL_ADJUSTMENT"},{"id":"REF_AREA","pos":3,"cl":"CL_BIS_IF_REF_AREA"},{"id":"COUNTERPART_AREA","pos":4,"cl":"CL_BIS_IF_REF_AREA"},{"id":"REF_SECTOR","pos":5,"cl":"CL_SECTOR"},{"id":"COUNTERPART_SECTOR","pos":6,"cl":"CL_SECTOR"},{"id":"CONSOLIDATION","pos":7,"cl":"CL_NA_CONSOLIDAT"},{"id":"ACCOUNTING_ENTRY","pos":8,"cl":"CL_ACCOUNT_ENTRY"},{"id":"STO","pos":9,"cl":"CL_NA_STO"},{"id":"INSTR_ASSET","pos":10,"cl":"CL_INSTR_ASSET"},{"id":"MATURITY","pos":11,"cl":"CL_MATURITY"},{"id":"EXPENDITURE","pos":12,"cl":"CL_COFOG"},{"id":"UNIT_MEASURE","pos":13,"cl":"CL_UNIT"},{"id":"CURRENCY_DENOM","pos":14,"cl":"CL_UNIT"},{"id":"VALUATION","pos":15,"cl":"CL_VALUATION"},{"id":"PRICES","pos":16,"cl":"CL_NA_PRICES"},{"id":"TRANSFORMATION","pos":17,"cl":"CL_TRANSFORMATION"},{"id":"CUST_BREAKDOWN","pos":18,"cl":"CL_CUST_BREAKDOWN"}],"attributes":[{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"CONF_STATUS","cl":"CL_CONF_STATUS","status":"Mandatory"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"EMBARGO_DATE","cl":null,"status":"Conditional"},{"id":"REF_PERIOD_DETAIL","cl":"CL_REF_PERIOD_DTL","status":"Conditional"},{"id":"REPYEARSTART","cl":null,"status":"Conditional"},{"id":"REPYEAREND","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"TIME_PER_COLLECT","cl":"CL_TIME_COLLECT","status":"Conditional"},{"id":"CUST_BREAKDOWN_LB","cl":null,"status":"Conditional"},{"id":"REF_YEAR_PRICE","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"TABLE_IDENTIFIER","cl":"CL_NA_TABLEID","status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"TITLE_COMPL","cl":null,"status":"Conditional"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"LAST_UPDATE","cl":null,"status":"Conditional"},{"id":"COMPILING_ORG","cl":"CL_ORGANISATION","status":"Conditional"},{"id":"COMMENT_DSET","cl":null,"status":"Conditional"},{"id":"OBS_EDP_WBB","cl":"CL_EDP_WBB","status":"Conditional"},{"id":"COLL_PERIOD","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"GFS_ECOFUNC","cl":"CL_GFS_ECOFUNC","status":"Conditional"},{"id":"GFS_TAXCAT","cl":"CL_GFS_TAXCAT","status":"Conditional"},{"id":"DATA_COMP","cl":null,"status":"Conditional"},{"id":"CURRENCY","cl":"CL_UNIT","status":"Conditional"},{"id":"DISS_ORG","cl":"CL_ORGANISATION","status":"Conditional"}],"typical_freq":"Q","series_count":0,"first_period":null,"last_period":null},"WS_NA_SEC_DSS":{"name":"Debt securities statistics","description":"","dsd_id":"NA_SEC","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"ADJUSTMENT","pos":2,"cl":"CL_ADJUSTMENT"},{"id":"REF_AREA","pos":3,"cl":"CL_BIS_IF_REF_AREA"},{"id":"COUNTERPART_AREA","pos":4,"cl":"CL_BIS_IF_REF_AREA"},{"id":"REF_SECTOR","pos":5,"cl":"CL_SECTOR"},{"id":"COUNTERPART_SECTOR","pos":6,"cl":"CL_SECTOR"},{"id":"CONSOLIDATION","pos":7,"cl":"CL_NA_CONSOLIDAT"},{"id":"ACCOUNTING_ENTRY","pos":8,"cl":"CL_ACCOUNT_ENTRY"},{"id":"STO","pos":9,"cl":"CL_NA_STO"},{"id":"INSTR_ASSET","pos":10,"cl":"CL_INSTR_ASSET"},{"id":"MATURITY","pos":11,"cl":"CL_MATURITY"},{"id":"EXPENDITURE","pos":12,"cl":"CL_COFOG"},{"id":"UNIT_MEASURE","pos":13,"cl":"CL_UNIT"},{"id":"CURRENCY_DENOM","pos":14,"cl":"CL_UNIT"},{"id":"VALUATION","pos":15,"cl":"CL_VALUATION"},{"id":"PRICES","pos":16,"cl":"CL_NA_PRICES"},{"id":"TRANSFORMATION","pos":17,"cl":"CL_TRANSFORMATION"},{"id":"CUST_BREAKDOWN","pos":18,"cl":"CL_CUST_BREAKDOWN"}],"attributes":[{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"CONF_STATUS","cl":"CL_CONF_STATUS","status":"Mandatory"},{"id":"COMMENT_OBS","cl":null,"status":"Conditional"},{"id":"EMBARGO_DATE","cl":null,"status":"Conditional"},{"id":"REF_PERIOD_DETAIL","cl":"CL_REF_PERIOD_DTL","status":"Conditional"},{"id":"REPYEARSTART","cl":null,"status":"Conditional"},{"id":"REPYEAREND","cl":null,"status":"Conditional"},{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Mandatory"},{"id":"TIME_PER_COLLECT","cl":"CL_TIME_COLLECT","status":"Conditional"},{"id":"CUST_BREAKDOWN_LB","cl":null,"status":"Conditional"},{"id":"REF_YEAR_PRICE","cl":null,"status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"TABLE_IDENTIFIER","cl":"CL_NA_TABLEID","status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"},{"id":"TITLE_COMPL","cl":null,"status":"Conditional"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"LAST_UPDATE","cl":null,"status":"Conditional"},{"id":"COMPILING_ORG","cl":"CL_ORGANISATION","status":"Conditional"},{"id":"COMMENT_DSET","cl":null,"status":"Conditional"},{"id":"OBS_EDP_WBB","cl":"CL_EDP_WBB","status":"Conditional"},{"id":"COLL_PERIOD","cl":null,"status":"Conditional"},{"id":"COMMENT_TS","cl":null,"status":"Conditional"},{"id":"GFS_ECOFUNC","cl":"CL_GFS_ECOFUNC","status":"Conditional"},{"id":"GFS_TAXCAT","cl":"CL_GFS_TAXCAT","status":"Conditional"},{"id":"DATA_COMP","cl":null,"status":"Conditional"},{"id":"CURRENCY","cl":"CL_UNIT","status":"Conditional"},{"id":"DISS_ORG","cl":"CL_ORGANISATION","status":"Conditional"}],"typical_freq":"Q","series_count":67198,"first_period":"1951-Q4","last_period":"2025-Q3"},"WS_OTC_DERIV2":{"name":"OTC derivatives outstanding","description":"","dsd_id":"BIS_DER","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"DER_TYPE","pos":2,"cl":"CL_OD_TYPE"},{"id":"DER_INSTR","pos":3,"cl":"CL_DER_INSTR"},{"id":"DER_RISK","pos":4,"cl":"CL_MARKET_RISK"},{"id":"DER_REP_CTY","pos":5,"cl":"CL_BIS_IF_REF_AREA"},{"id":"DER_SECTOR_CPY","pos":6,"cl":"CL_SECTOR_CPY"},{"id":"DER_CPC","pos":7,"cl":"CL_BIS_IF_REF_AREA"},{"id":"DER_SECTOR_UDL","pos":8,"cl":"CL_SECTOR_UDL"},{"id":"DER_CURR_LEG1","pos":9,"cl":"CL_BIS_UNIT"},{"id":"DER_CURR_LEG2","pos":10,"cl":"CL_BIS_UNIT"},{"id":"DER_ISSUE_MAT","pos":11,"cl":"CL_ISSUE_MAT"},{"id":"DER_RATING","pos":12,"cl":"CL_RATING"},{"id":"DER_EX_METHOD","pos":13,"cl":"CL_EX_METHOD"},{"id":"DER_BASIS","pos":14,"cl":"CL_DER_BASIS"}],"attributes":[{"id":"TIME_FORMAT","cl":"CL_TIME_FORMAT","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"H","series_count":4960,"first_period":"1998-S1","last_period":"2025-S1"},"WS_SPP":{"name":"Selected residential property prices","description":"","dsd_id":"BIS_SELECTED_PP","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_AREA"},{"id":"VALUE","pos":3,"cl":"CL_VALUE"},{"id":"UNIT_MEASURE","pos":4,"cl":"CL_BIS_UNIT"}],"attributes":[{"id":"BREAKS","cl":null,"status":"Conditional"},{"id":"COVERAGE","cl":null,"status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"}],"typical_freq":"Q","series_count":244,"first_period":"1970-Q1","last_period":"2025-Q4"},"WS_TC":{"name":"Total credit","description":"","dsd_id":"BIS_TOTAL_CREDIT","version":"2.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"BORROWERS_CTY","pos":2,"cl":"CL_AREA"},{"id":"TC_BORROWERS","pos":3,"cl":"CL_TC_BORROWERS"},{"id":"TC_LENDERS","pos":4,"cl":"CL_TC_LENDERS"},{"id":"VALUATION","pos":5,"cl":"CL_VALUATION"},{"id":"UNIT_TYPE","pos":6,"cl":"CL_BIS_UNIT"},{"id":"TC_ADJUST","pos":7,"cl":"CL_ADJUST"}],"attributes":[{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Conditional"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"UNIT_MEASURE","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"TITLE_TS","cl":null,"status":"Conditional"}],"typical_freq":"Q","series_count":1133,"first_period":"1947-Q4","last_period":"2025-Q3"},"WS_XRU":{"name":"US dollar exchange rates","description":"The price of one country's currency in relation to another.","dsd_id":"BIS_XR","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"REF_AREA","pos":2,"cl":"CL_BIS_IF_REF_AREA"},{"id":"CURRENCY","pos":3,"cl":"CL_CURRENCY_3POS"},{"id":"COLLECTION","pos":4,"cl":"CL_COLLECTION"}],"attributes":[{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Conditional"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Conditional"},{"id":"TITLE","cl":null,"status":"Conditional"}],"typical_freq":"M","series_count":384,"first_period":"1949-01","last_period":"2026-04"},"WS_XTD_DERIV":{"name":"Exchange-traded derivatives","description":"","dsd_id":"BIS_XTD_DERIV","version":"1.0","dimensions":[{"id":"FREQ","pos":1,"cl":"CL_FREQ"},{"id":"OD_TYPE","pos":2,"cl":"CL_OD_TYPE"},{"id":"OD_RISK_CAT","pos":3,"cl":"CL_OD_RISK_CAT"},{"id":"OD_INSTR","pos":4,"cl":"CL_OD_INSTR"},{"id":"ISSUE_CUR","pos":5,"cl":"CL_ISSUE_CUR"},{"id":"XD_EXCHANGE","pos":6,"cl":"CL_BIS_IF_REF_AREA"}],"attributes":[{"id":"COLLECTION","cl":"CL_COLLECTION","status":"Mandatory"},{"id":"AVAILABILITY","cl":"CL_AVAILABILITY","status":"Mandatory"},{"id":"DECIMALS","cl":"CL_DECIMALS","status":"Conditional"},{"id":"BIS_UNIT","cl":"CL_BIS_UNIT","status":"Mandatory"},{"id":"OBS_STATUS","cl":"CL_OBS_STATUS","status":"Mandatory"},{"id":"UNIT_MULT","cl":"CL_UNIT_MULT","status":"Mandatory"},{"id":"OBS_CONF","cl":"CL_CONF_STATUS","status":"Conditional"},{"id":"OBS_PRE_BREAK","cl":null,"status":"Conditional"}],"typical_freq":"Q","series_count":648,"first_period":"1993-Q1","last_period":"2025-Q4"}},"codelists":{"CL_FREQ":{"name":"Code list for Frequency (FREQ)","codes":{"A":"Annual","B":"Daily - business week (not supported)","D":"Daily","E":"Event (not supported)","H":"Half-yearly","M":"Monthly","Q":"Quarterly","W":"Weekly"}},"CL_REL_CAT":{"name":"CL_REL_CAT","codes":{"LBS":"Locational banking statistics","CBS":"Consolidated banking statistics","IDS":"International debt securities","TDDS":"Debt securities statistics","TOTAL_CREDIT":"Credit to the non-financial sector","CREDIT_GAPS":"Credit-to-GDP gaps","DSR":"Debt service ratios","GLI":"Global liquidity","OTC_DER":"OTC derivatives outstanding","XTD_DER":"Exchange-traded derivatives statistics","DER":"Triennial Survey","CPP":"Commercial property prices","RPP":"Residential property prices","SPP":"Selected residential property prices","CPI":"Consumer prices","CBPOL":"Central bank policy rates","XRU":"Bilateral exchange rates","EER":"Effective exchange rates","CPMI":"Payments and financial markets infrastructure","PP":{"name":"Property prices"},"DDS":"Debt securities statistics","DSS":"Debt securities statistics","CBTA":"Central bank total assets","CPMI_CT":{"name":"Retail payments, currency and related indicators"},"CPMI_FMI":"Financial market infrastructures and critical service providers"}},"CL_REL_TYPE":{"name":"CL_REL_TYPE","codes":{"S":"Release","R":"Revision","P":"Preliminary","SPP1":"Selected residential, partial update 1","SPP2":"Selected residential, partial update 2","SPPS":"Selected residential standard release","CRPP":"Commercial and residential","R2":"Revision","DM1":"Daily and monthly data","DM2":"Daily and monthly data","DM3":"Daily and monthly data","DM4":"Daily and monthly data","DM5":"Daily and monthly data","EERD":"Nominal daily data","EERM":"Nominal / real monthly data","DPP":"Detailed residential release"}},"CL_CONF_STATUS":{"name":"Confidentiality Status","codes":{"A":"Primary confidentiality due to small counts","C":"Confidential statistical information","D":"Secondary confidentiality set by the sender, not for publication","E":"Not for publication, restricted for internal use only (equivalent to the code N) until the embargo time elapses; Free for publication (equivalent to the code F) after the embargo time elapses.","F":"Free (free for publication)","G":"Primary confidentiality due to dominance by one or two units","M":"Primary confidentiality due to data declared confidential based on other measures of concentration","N":"Not for publication, restricted for internal use only","O":"Primary confidentiality due to dominance by one unit","S":"Secondary confidentiality set and managed by the receiver, not for publication","T":"Primary confidentiality due to dominance by two units","X":"Confidentiality due to military secrecy"}},"CL_OBS_STATUS":{"name":"Observation Status","codes":{"A":{"name":"Normal value","desc":"To be used as default value if no value is provided or when no special coded qualification is assumed. Usually, it can be assumed that the source agency assigns sufficient confidence to the provided observation and/or the value is not expected to be drama"},"B":{"name":"Time series break","desc":"Observations are characterised as such when different content exists or a different methodology has been applied to this observation as compared with the preceding one (the one given for the previous period)."},"D":{"name":"Definition differs","desc":"Used to indicate slight deviations from the established methodology (footnote-type information); these divergences do not imply a break in time series."},"E":{"name":"Estimated value","desc":"Observation obtained through an estimation methodology (e.g. to produce back-casts) or based on the use of a limited amount of data or ad hoc sampling and through additional calculations (e.g. to produce a value at an early stage of the production stage w"},"F":{"name":"Forecast value","desc":"Value deemed to assess the magnitude which a quantity will assume at some future point of time (as distinct from \"estimated value\" which attempts to assess the magnitude of an already existent quantity)."},"G":{"name":"Experimental value","desc":"Data collected on the basis of definitions or (alternative) collection methods under development. Data not of guaranteed quality as normally expected from provider."},"H":{"name":"Missing value; holiday or weekend","desc":"Used in some daily data flows."},"I":{"name":"Imputed value (CCSA definition)","desc":"Observation imputed by international organisations to replace or fill gaps in national data series, in line with the recommendations of the United Nations Committee for the Coordination of Statistical Activities (CCSA)."},"J":{"name":"Derogation","desc":"Clause in an agreement (e.g. legal act, gentlemen\ufffds agreement) stating that some provisions in the agreement are not to be implemented by designated parties; these derogations may affect the observation or cause a missing value. In general, derogations ar"},"K":{"name":"Data included in another category","desc":"This code is used when data for a given category are missing and are included in another category, sub-total or total. Generally where code \ufffdK\ufffd is used there should be a corresponding code \"W - Includes data from another category\" assigned to the over-cov"},"L":{"name":"Missing value; data exist but were not collected","desc":"Used, for example, when some data are not reported/disseminated because they are below a certain threshold."},"M":{"name":"Missing value; data cannot exist","desc":"Used to denote empty cells resulting from the impossibility to collect a statistical value (e.g. a particular education level or type of institution may be not applicable to a given country's education system)."},"N":{"name":"Not significant","desc":"Used to indicate a value which is not a \"real\" zero (e.g. a result of 0.0004 rounded to zero)."},"O":{"name":"Missing value","desc":"This code is to be used when no breakdown is made between the reasons why data are missing. Data can be missing due to many reasons: data cannot exist, data exist but are not collected (e.g. because they are below a certain threshold or subject to a derog"},"P":{"name":"Provisional value","desc":"An observation is characterised as \"provisional\" when the source agency \ufffd while it bases its calculations on its standard production methodology \ufffd considers that the data, almost certainly, are expected to be revised."},"Q":{"name":"Missing value; suppressed","desc":"Used, for example, when data are suppressed due to statistical confidentiality considerations."},"S":{"name":"Strike and other special events","desc":"Special circumstances (e.g. strike) affecting the observation or causing a missing value."},"U":{"name":"Low reliability","desc":"This indicates existing observations, but for which the user should also be aware of the low quality assigned."},"V":{"name":"Unvalidated value","desc":"Observation as received from the respondent without further evaluation of data quality."},"W":{"name":"Includes data from another category","desc":"This code is used when data include another category, or go beyond the scope of the data collection and are therefore over-covered. Generally, where code \"W\" is used there should be a corresponding code \"K - Data included in another category\" assigned to"}}},"CL_BIS_GL_REF_AREA":{"name":"Reference Area Code for BIS General Economics and Block L","codes":{"00":"Others","0A":"Nordic Investment Bank","0N":"BIS","1X":"ECB","2B":"Residual developing Europe","2R":"Residual developed countries","3C":"Developing Europe","3P":"Total excluding residents","4F":"OPEC countries","4K":"Non-OPEC ldcs","4T":"Emerging market economies (aggregate)","4U":"Developing Latin America & Caribbean","4W":"Developing Africa and Middle East","4Y":"Developing Asia & Pacific","4Z":"European countries outside the euro area","5A":"All reporting countries (aggregate)","5R":"Advanced economies (aggregate)","6O":"Non-US banks in Bahamas(for reporting only)","A2":"Commodity world market prices, USD-basis (The Economist)","A3":"Commodity world market prices, GBP-basis (The Economist)","A6":"Commodity world market prices (Moodys)","A9":"Commodity world market prices (Reuters)","AE":"United Arab Emirates","AF":"Afghanistan","AG":"Antigua and Barbuda","AI":"Anguilla","AL":"Albania","AM":"Armenia","AN":"Netherlands Antilles","AO":"Angola","AR":"Argentina","AT":"Austria","AU":"Australia","AW":"Aruba","AZ":"Azerbaijan","B1":"Oil spot oil spot prices Rotterdam","B2":"Belgium/Luxembourg","BA":"Bosnia and Herzegovina","BB":"Barbados","BD":"Bangladesh","BE":"Belgium","BF":"Burkina Faso","BG":"Bulgaria","BH":"Bahrain","BI":"Burundi","BJ":"Benin","BM":"Bermuda","BN":"Brunei","BO":"Bolivia","BR":"Brazil","BS":"The Bahamas","BT":"Bhutan","BW":"Botswana","BY":"Belarus","BZ":"Belize","CA":"Canada","CD":"Democratic Republic of the Congo","CF":"Central African republic","CG":"Republic of Congo","CH":"Switzerland","CI":"C\u00f4te d'Ivoire","CL":"Chile","CM":"Cameroon","CN":"China","CO":"Colombia","CR":"Costa Rica","CS":"Serbia & Montenegro","CU":"Cuba","CV":"Cabo Verde","CW":"Cura\u00e7ao","CY":"Cyprus","CZ":"Czechia","DE":"Germany","DJ":"Djibouti","DK":"Denmark","DM":"Dominica","DO":"Dominican Republic","DZ":"Algeria","EC":"Ecuador","EE":"Estonia","EG":"Egypt","ER":"Eritrea","ES":"Spain","ET":"Ethiopia","FI":"Finland","FJ":"Fiji","FM":"Micronesia","FR":"France","G2":"G20 (aggregate)","GA":"Gabon","GB":"United Kingdom","GD":"Grenada","GE":"Georgia","GH":"Ghana","GM":"The Gambia","GN":"Guinea","GQ":"Equatorial Guinea","GR":"Greece","GT":"Guatemala","GW":"Guinea-Bissau","GY":"Guyana","HK":"Hong Kong SAR","HN":"Honduras","HR":"Croatia","HT":"Haiti","HU":"Hungary","ID":"Indonesia","IE":"Ireland","IL":"Israel","IN":"India","IQ":"Iraq","IR":"Iran","IS":"Iceland","IT":"Italy","JM":"Jamaica","JO":"Jordan","JP":"Japan","KE":"Kenya","KG":"Kyrgyzstan","KH":"Cambodia","KI":"Kiribati","KM":"Comoros","KN":"St Kitts and Nevis","KP":"North Korea","KR":"Korea","KW":"Kuwait","KY":"Cayman Islands","KZ":"Kazakhstan","LA":"Laos","LB":"Lebanon","LC":"St Lucia","LK":"Sri Lanka","LR":"Liberia","LS":"Lesotho","LT":"Lithuania","LU":"Luxembourg","LV":"Latvia","LY":"Libya","MA":"Morocco","MD":"Moldova","ME":"Montenegro","MG":"Madagascar","MK":"North Macedonia","ML":"Mali","MM":"Myanmar","MN":"Mongolia","MO":"Macao SAR","MR":"Mauritania","MS":"Montserrat","MT":"Malta","MU":"Mauritius","MV":"Maldives","MW":"Malawi","MX":"Mexico","MY":"Malaysia","MZ":"Mozambique","NA":"Namibia","NE":"Niger","NG":"Nigeria","NI":"Nicaragua","NL":"Netherlands","NO":"Norway","NP":"Nepal","NW":"Norway Mainland","NZ":"New Zealand","OM":"Oman","OS":"OSSP countries (aggregate)","PA":"Panama","PE":"Peru","PG":"Papua New Guinea","PH":"Philippines","PK":"Pakistan","PL":"Poland","PT":"Portugal","PY":"Paraguay","QA":"Qatar","RO":"Romania","RS":"Serbia","RU":"Russia","RW":"Rwanda","SA":"Saudi Arabia","SB":"Solomon Islands","SC":"Seychelles","SD":"Sudan","SE":"Sweden","SG":"Singapore","SI":"Slovenia","SK":"Slovakia","SL":"Sierra Leone","SM":"San Marino","SN":"Senegal","SO":"Somalia","SR":"Suriname","SS":"South Sudan","ST":"S\u00e3o Tom\u00e9 and Pr\u00edncipe","SV":"El Salvador","SY":"Syria","SZ":"Eswatini","TD":"Chad","TG":"Togo","TH":"Thailand","TJ":"Tajikistan","TM":"Turkmenistan","TN":"Tunisia","TO":"Tonga","TR":"T\u00fcrkiye","TT":"Trinidad & Tobago","TW":"Chinese Taipei","TZ":"Tanzania","UA":"Ukraine","UG":"Uganda","US":"United States","UY":"Uruguay","UZ":"Uzbekistan","VC":"St Vincent and the Grenadines","VE":"Venezuela","VN":"Vietnam","VU":"Vanuatu","W1":"BIS DBS","WA":"Waemu","WF":"Wallis and Futuna Islands","WK":"Wake Island","WS":"Western Samoa","XA":"Gold (ISO: XAU)","XD":"SDR (ISO: XDR)","XE":"Ecu (iso: XEU)","XM":"Euro area","XN":"EMS: position in band","XW":"World","YE":"Yemen","YU":"Yugoslavia (from 1993 onwards Serbia and Montenegro only)","Z1":"Total of all currencies/world","Z2":"OECD","Z3":"OECD Europe","Z8":"Rest, currencies not incl. elsewhere","Z9":"International development institutions","ZA":"South Africa","ZM":"Zambia","ZW":"Zimbabwe"}},"CL_BIS_UNIT":{"name":"BIS_Unit","codes":{"000":"Unknown","001":"100 - yield","002":"EUR / MWh","003":"Index, 1996 Jan 2 = 100","004":"Euro / troy ounce","005":"US Dollar / troy ounce","006":"US Dollar / lb","007":"US Dollar / US gal","008":"US Dollar / Million British Thermal Unit","009":"US Dollar / Bushel","010":"US Dollar / Bitcoin","100":"Barrels","101":"Canadian Dollar / Constant 1992 Canadian Dollar","102":"Canadian Dollar / Constant 1997 Canadian Dollar","103":"Chained 1992 US Dollar","104":"Chained 1995 Euro","105":"Chained 1995 Luxembourg Franc","106":"Chained 1995 Swedish Krona","107":"Chained 1995/1996 New Zealand Dollar","108":"Chained 1996 US Dollar","109":"Chained 1997 Canadian Dollar","110":"Chained 1999 Norwegian Krone","111":"Chained 2000 / 2001 Australian Dollar","112":"Constant 1970 Belgian Franc","113":"Constant 1970 French Franc","114":"Constant 1970 Greek Drachma","115":"Constant 1970 Italian Lira","116":"Constant 1970 Japanese Yen","117":"Constant 1970 Saudi Riyal","118":"Constant 1972 US Dollar","119":"Constant 1975 Swedish Krona","120":"Constant 1977 Portuguese Escudo","121":"Constant 1980 Belgian Franc","122":"Constant 1980 Danish Krone","123":"Constant 1980 Deutsche Mark","124":"Constant 1980 Dutch Guilder","125":"Constant 1980 French Franc","126":"Constant 1980 Swedish Krona","127":"Constant 1980 Swiss Franc","128":"Constant 1982 US Dollar","129":"Constant 1983 Austrian Shilling","130":"Constant 1985 Deutsche Mark","131":"Constant 1985 Finnish Markka","132":"Constant 1985 Irish Punt","133":"Constant 1985 Italian Lira","134":"Constant 1986 Canadian Dollar","135":"Constant 1986 Spanish Peseta","136":"Constant 1987 Malaysian Ringgit","137":"Constant 1987 US Dollar","138":"Constant 1988 Greek Drachma","139":"Constant 1988 Thai Bath","140":"Constant 2021 Euro","141":"Constant 1990 Belgian Franc","142":"Constant 1990 Dutch Guilder","143":"Constant 1990 Finnish Markka","144":"Constant 1990 Irish Punt","145":"Constant 1990 Italian Lira","146":"Constant 1990 Japanese Yen","147":"Constant 1990 Pound Sterling","148":"Constant 1990 Swedish Krona","149":"Constant 1990 Swiss Franc","150":"Constant 1991 Deutsche Mark","151":"Constant 1991 Norwegian Krone","152":"Constant 1991 Spanish Peseta","153":"Constant 1991 Swedish Krona","154":"Constant 1991 / 1992 New Zealand Dollar","155":"Constant 1992 Canadian Dollar","156":"Constant 1993 Indonesia Rupiah","157":"Constant 1995 Austrian Shilling","158":"Constant 1995 Belgian Franc","159":"Constant 1995 Czech Koruna","160":"Constant 1995 Danish Krone","161":"Constant 1995 Deutsche Mark","162":"Constant 1995 Dutch Guilder","163":"Constant 1995 Euro","164":"Constant 1995 European Currency Unit","165":"Constant 1995 Finnish Markka","166":"Constant 1995 French Franc","167":"Constant 1995 Greek Drachma","168":"Constant 1995 Irish Punt","169":"Constant 1995 Italian Lira","170":"Constant 1995 Japanese Yen","171":"Constant 1995 Luxembourg Franc","172":"Constant 1995 Pound Sterling","173":"Constant 1995 South African Rand","174":"Constant 1995 Spanish Peseta","175":"Constant 1996 US Dollar","176":"Constant 1997 Canadian Dollar","177":"Constant 1998 Hungarian Forint","178":"Constant 2000 Hong Kong Dollar","179":"Constant 1997 Q4 New Zealand Dollar","180":"Previous Year Euro","181":"Previous Year Portuguese Escudo","182":"Cubic Feet","183":"Cubic Meter","184":"Days","185":"Deutsche Mark / Constant 1995 Deutsche Mark","186":"Dutch Guilder / Kilo","187":"Euro / Constant 1995 Euro","188":"Fine Ounces","189":"French Franc / Constant 1980 French Franc","190":"French Franc / Constant 1995 French Franc","191":"Full-Time Equivalence Jobs","192":"Hours","193":"Index, 1914 = 1","194":"Index, 1931 Dec 31 = 100","195":"Index, 1931 Sep 18 = 100","196":"Index, 1937 = 100","197":"Index, 1939 = 100","198":"Index, 1941 / 43 = 10","199":"Index, 1948 Jan = 100","200":"Index, 1953 = 100","201":"Index, 1953 Oct = 100","202":"Index, 1956 Jan 01 = 100","203":"Index, 1958 = 100","204":"Index, 1958 Dec 31 = 100","205":"Index, 1961 = 100","206":"Index, 1962 = 100","207":"Index, 1962 Apr 10 = 100","208":"Index, 1963 = 100","209":"Index, 1964 = 100","210":"Index, 1964 Jul 31 = 100","211":"Index, 1964 Nov = 100","212":"Index, 1965 Dec 31 = 50","213":"Index, 1966 = 100","214":"Index, 1966 Jan = 100","215":"Index, 1967 = 100","216":"Index, 1967 Dec 31 = 100","217":"Index, 1968 = 100","218":"Index, 1968 Jan 04 = 100","219":"Index, 1970 = 100","220":"Index, 1970 May = 100","221":"Index, 1971 = 100","222":"Index, 1971 Feb 05 = 100","223":"Index, 1972 = 100","224":"Index, 1972 Dec 29 = 100","225":"Index, 1973 = 100","226":"Index, 1973 Jan = 100","227":"Index, 1973 Mar = 100","228":"Index, 1974 = 100","229":"Index, 1974 Jan = 100","230":"Index, 1974 Jul to 1981 Jun = 100","231":"Index, 1975 = 100","232":"Index, 1975 = 1000","233":"Index, 1975 Jan = 1000","234":"Index, 1976 = 100","235":"Index, 1976 Q1 = 100","236":"Index, 1977 = 100","237":"Index, 1977 Nov = 100","238":"Index, 1977 Sep = 100","239":"Index, 1978 = 100","240":"Index, 1978 Q1 = 1000","241":"Index, 1979 = 100","242":"Index, 1979 Dec 28 = 100","243":"Index, 1979 Dec 31 = 100","244":"Index, 1979 Dec 31 = 500","245":"Index, 1979 Jun = 100","246":"Index, 1980 = 100","247":"Index, 1980 Dec 30 = 100","248":"Index, 1980 Dec 31 = 100","249":"Index, 1980 Jan 01 = 100","250":"Index, 1980 Jan 01 = 1000","251":"Index, 1980 Q1 = 100","252":"Index, 1981 = 100","253":"Index, 1981 Dec 31 = 100","254":"Index, 1982 = 100","255":"Index, 1982 Dec = 100","256":"Index, 1982 Oct 08 = 100","257":"Index, 1982 Q4 = 1000","258":"Index, 1982/1984 = 100","259":"Index, 1982/1990 = 100","260":"Index, 1983 = 100","261":"Index, 1983 Dec 31 = 100","262":"Index, 1983 Jan = 1000","263":"Index, 1983 Jan 01 = 100","264":"Index, 1983 Nov = 100","265":"Index, 1984 Jan 01 = 1000","266":"Index, 1985 = 100","267":"Index, 1985 Dec = 100","268":"Index, 1985 Jan 02 = 1000","269":"Index, 1985 Q4 = 1000","270":"Index, 1985 Sep = 100","271":"Index, 1986 = 100","272":"Index, 1987 = 100","273":"Index, 1987 Dec = 100","274":"Index, 1987 Dec 30 = 100","275":"Index, 1987 Dec 30 = 1000","276":"Index, 1987 Dec 31 = 1000","277":"Index, 1987 Jan = 100","278":"Index, 1987 Jan 13 = 100","279":"Index, 1987 Jun 01 = 1000","280":"Index, 1988 = 100","281":"Index, 1988 Jan = 100","282":"Index, 1988 Jan 04 = 1000","283":"Index, 1988 Jan 05 = 1000","284":"Index, 1988 Oct 01 = 100","285":"Index, 1988/1989 = 1000","286":"Index, 1989 = 100","287":"Index, 1989 Dec = 3000","288":"Index, 1989 Jul 03 = 100","289":"Index, 1989 Nov = 100","290":"Index, 1989 Nov 15 = 100","291":"Index, 1989 Q2 = 100","292":"Index, 1989 Q4 = 1000","293":"Index, 1989/1990 = 100","294":"Index, 1990 = 100","295":"Index, 1990 Dec 28 = 1000","296":"Index, 1990 H2 = 100","297":"Index, 1990 Q3 = 100","298":"Index, 1990/1991 = 100","299":"Index, 1991 = 100","300":"Index, 1991 Dec = 100","301":"Index, 1991 Dec 31 = 100","302":"Index, 1991 Dec 31 = 1000","303":"Index, 1991 Jan 01 = 1000","304":"Index, 1991 Jan 02 = 1000","305":"Index, 1991 Oct 28 = 100","306":"Index, 1992 = 100","307":"Index, 1992 Jan = 100","308":"Index, 1992 Jan 06 = 1000","309":"Index, 1992 Q4 = 1000","310":"Index, 1993 = 100","311":"Index, 1993 May = 100","312":"Index, 1993 Q1 = 100","313":"Index, 1993 Q4 = 1000","314":"Index, 1994 = 100","315":"Index, 1994 Feb = 100","316":"Index, 1994 Q2 = 100","317":"Index, 1994 Q4 = 100","318":"Index, 1994 Sep 30 = 1000","319":"Index, 1995 = 100","320":"Index, 1995 Dec = 100","321":"Index, 1995 Dec 28 = 100","322":"Index, 1995 Dec 29 = 100","323":"Index, 1995 Jan 02 = 100","324":"Index, 1995 Q1 = 100","325":"Index, 1995 Q3 = 100","326":"Index, 1996 = 100","327":"Index, 1996 Nov 15 = 100","328":"Index, 1997 = 100","329":"Index, 1997 Dec 31 = 1000","330":"Index, 1997 Jan = 100","331":"Index, 1997 Q1 = 100","332":"Index, 1997 Q4 = 1000","333":"Index, 1997 Sep = 100","334":"Index, 1998 = 100","335":"Index, 1998 Dec 31 = 100","336":"Index, 1998 Q4 = 100","337":"Index, 1998/1999 = 100","338":"Index, 1999 = 100","339":"Index, 1999 Dec = 100","340":"Index, 1999 Dec 30 = 1000","341":"Index, 1999 Jan = 100","342":"Index, 1999 Jan 04 = 100","343":"Index, 1999 Jan 04 = 1000","344":"Index, 1999 Q1 = 100","345":"Index, 1999 Q2 = 1000","346":"Index, 1999 Q3 = 1000","347":"Index, 1999/2000 = 100","348":"Index, 2000 = 100","349":"Index, 2000 Mar 17 = 100","350":"Index, 2000 May = 100","351":"Index, 2000/2001 = 100","352":"Index, 2001 = 100","353":"Index, 2001 Dec = 100","354":"Index, 2001 Dec 28 = 1000","355":"Index, 2002 Dec 31 = 5000","356":"Index, Previous year = 100","357":"Index, Trend = 100","358":"Italian Lira / Constant 1990 Italian Lira","359":"Italian Lira / Constant 1995 Italian Lira","360":"Jobs","361":"Luxembourg Franc / Constant 1995 Luxembourg Franc","362":"Man-Days","363":"Man-Years","364":"Months","365":"No Unit Identified","366":"One Thousand Litre","367":"Per cent","368":"Per cent per year","369":"Percentage change against January 1987","370":"Percentage Points","371":"Persons","372":"Points","373":"Pure Number","374":"Shares","375":"Square Meter","376":"Standard Units Of Labour","377":"Units","378":"US Dollar / Barrel","379":"US Dollar / Ton","380":"Chained 2000 Norwegian Krone","381":"Constant 1982 / 1983 New Zealand Dollar","382":"Constant 1996 Chilean Peso","383":"Constant 1999 Saudi Arabian Riyal","384":"Constant 2000 Euro","385":"Constant 2000 Finnish Markka","386":"Euro / Barrel","387":"Index, 1956 Jun = 100","388":"Index, 1970 Q1 = 100","389":"Index, 1972 Jul = 100","390":"Index, 1992 Jun = 100","391":"Index, 1993 Apr = 100","392":"Index, 1996 Q4 = 1000","393":"Constant 2010 Vietnamese Dong","394":"Index, 1998 Dec = 100","395":"Index, 2000 Dec = 100","396":"Index, 2002 = 100","397":"Index, 2002 Feb 28 = 1000","398":"Previous Year Australian Dollar","399":"Index, 2002 Dec = 100","400":"Constant 1968 Swedish Krona","401":"Index, 1993 Q4 = 100","402":"Chained 2001 / 2002 Australian Dollar","403":"Constant 2000 Hungarian Forint","404":"Number of contracts","405":"Index, 2001/2002 = 100","406":"Index, 1994 Dec = 100","407":"Index, 1982 Aug 10 = 100","408":"Index, 1983 Jan 01 = 45.38","409":"Chained 2000 Pound Sterling","410":"Constant 2000 Belgian Franc","411":"Index, Previous year = 1000","412":"Chained 2000 Swedish Krona","413":"Chained 2000 US Dollar","414":"Index, 2003 May = 100","415":"Chained 2001 Norwegian Krone","416":"Index, 2002 Q1 = 100","417":"Index, 1977 Dec = 100","418":"Index, 2002 Q2 = 1000","419":"Previous Year Poland New Zloty","420":"Index, Previous month = 100","421":"Index, 1994 Apr 16 = 1000","422":"Index, 1991 Apr 16 = 1000","423":"Index, 1994 Dec 31 = 1000","424":"Index, 1998 Dec 31 = 12795.6","425":"Constant 1993 Mexican Peso","426":"Index, 2000 Jan = 100","427":"Index, 2000 Sep = 100","428":"Index, 1983 = 43.85","429":"Index, 1991 Jan = 100","430":"Chained 2001 Pound Sterling","431":"Constant 2000 Czech Koruna","432":"Index, 2000 Q4 = 100","433":"Index, 1995 Dec 31 = 100","434":"Index, 1996 Feb = 100","435":"Chained 2002 / 2003 Australian Dollar","436":"Constant 2000 Russian Federation Rouble","437":"Index, Corresponding month of previous year = 100","438":"Index, 2002/2003 = 100","439":"Constant 2000 Indonesia Rupiah","440":"Index, 2001 Q4 = 100","441":"Chained 1995 Czech Koruna","442":"Chained 2000 Swiss Franc","443":"Index, 1938 = 1","444":"Index, 1949 = 100","445":"Herfindahl index, max 10000","446":"Index, Corresponding quarter of previous year = 100","447":"Index, 2003/2004 = 100","448":"Index, 2003 Dec = 1000","449":"Constant 2000 South African Rand","450":"Chained 2002 Norwegian Krone","451":"Index, 2004 Dec 30 = 1000","452":"Index, 1948 = 100","453":"Index, 1938 = 100","454":"Index, 2003 = 100","455":"Index, 2003 Dec = 100","456":"Chained 2000 Japanese Yen","457":"Constant 1970 Malaysian Ringgit","458":"Constant 1978 Malaysian Ringgit","459":"Chained 2010 Israel Shekel","460":"Chained 2000 Austrian Schilling","461":"Chained 2000 Euro","462":"Euro / Chained 2000 Euro","463":"Index, 2003 Q4 = 1000","464":"Constant 2000 French Franc","465":"Index, 1990 Dec 19 = 100","466":"Index, 1994 Jul 20 = 1000","467":"Constant 1993 Argentine Peso","468":"Constant 1995 Slovenian Tolar","469":"Index, 1994 Jan 01 = 100","470":"Chained 2002 Pound Sterling","471":"Chained 2005 Polish Zloty - Millions","472":"Euro / Constant 2000 Euro","473":"French Franc / Constant 2000 French Franc","474":"Index, 2004 Dec = 100","475":"Index, 1998 Q2 = 100","476":"Index, 2002 Jun = 100","477":"Index, 1962 Jan = 100","478":"Constant 2000 Lithuanian Litas","479":"Index, 1993 Jun = 100","480":"Index, 2000 Jan 01 = 100","481":"Index, 1996 Dec = 100","482":"Index, Corresponding period of previous year = 100","483":"Chained 2003 / 2004 Australian Dollar","484":"Index, Year on Year","485":"Index","486":"Constant 1995 Slovakian Koruna","487":"Index, 1986 Jan = 100","488":"Index, 1990 Dec 31 = 32.56","489":"Constant 1987 Turkish Lira","490":"Index, 1995 Jan = 100","491":"Chained 2000 Danish Krone","492":"Diverse","493":"Index, 2000 Jun 30 = 100","494":"Chained 2003 Euro","495":"Index, 2000 Jun 03 = 100","496":"Index, 1999 H2 = 100","497":"Index, 1992 Jul = 100","498":"Index, 1996 Jun 03 = 100","499":"Chained 2003 Norwegian Krone","500":"Index, Previous Quarter = 100","501":"Index, 2000 Oct 20 = 100","502":"Per Cent Per Month","503":"Index, 2005 Q2 = 100","504":"Index, 1942 Mar 27 = 100","505":"Index, 1997 Jun = 100","506":"Previous Year Bulgarian Lev","507":"Index, 2005 Nov 30 = 1000","508":"Index, 1986 Jan 1 = 1","509":"Index, 1990 Dec 31 = 33","510":"Index, 2004 Jan = 100","511":"Constant 2000 Latvian Lat","512":"Index, 2000 Jan 1 = 1000","513":"Index, 1993 Sep 14 = 100","514":"Constant 2000 Estonian Kroon","515":"Per Cent Per Quarter","516":"Constant 1993/1994 Indian Rupee","517":"Index, 1993/1994 = 100","518":"Index, Average Month of 2000 = 100","519":"Index, 2005 = 100","520":"Index, 2004 = 100","521":"Index, 1995 Nov 03 = 1000","522":"Index, 1980 Dec = 100","523":"Constant 1985 Philippine Peso","524":"Index, 2000 Q3 = 100","525":"Chained 2000 Israel Shekel","526":"Index, 2005 Dec = 100","527":"Index, 1990 Feb 28 = 1022.05","528":"Index, 1996 Nov 14 = 1000","529":"Index, 2005 Dec = 5000","530":"Index, 2006 Jan = 100","531":"Constant 2000 Italian Lira","532":"Chained 2000 Italian Lira","533":"Index, 2005 Q4 = 100","534":"Index, 2004/2005 = 100","535":"Index, 1988 May = 100","536":"Index, 1997 Mar = 100","537":"Index, 1998 Jan 1 = 1000","538":"Constant 2000 Slovakian Koruna","539":"Index, 2003 Q1 = 100","540":"Constant 1999/2000 Indian Rupee","541":"Index, 1997 July 1 = 1000","542":"Index, December of previous year = 100","543":"Chained 2004 / 2005 Australian Dollar","544":"Index, 2001 Dec 15 = 100","545":"Constant 2000 Spanish Peseta","546":"Constant 1995 Macedonian Denar","547":"Index, 2006 Q2 = 1000","548":"Constant 2000 Singapore Dollar","549":"Index, 1978/1979 = 100","550":"Index, 2005 Jan = 100","551":"Chained 2000 Lithuanian Litas","552":"Index, 1999 Dec 31 = 100","553":"Chained 2004 Euro","554":"Chained 2004 Norwegian Krone","555":"Index, 1997 Dec = 100","556":"Index, 2006 = 100","557":"Index, 2006 Dec = 100","558":"Index, 1998 Dec 31 = 1279.56","559":"Index, 2004 Dec 31 = 100","560":"Constant 2000 South Korean Won","561":"Constant 1997 Macedonian Denar","562":"Index, 2003 = 1","563":"Index, 2003 Sep = 100","564":"Index, 1980 Jan 04 = 100","565":"Constant 2000 Malaysian Ringgit","566":"Chained 2002 Canadian Dollar","567":"Constant 2002 Canadian Dollar","568":"Canadian Dollar / Constant 2002 Canadian Dollar","569":"Constant 2003 Chilean Peso","570":"Index, 1996-2006=100","571":"Chained 2005 Euro","572":"Constant 1997 Croatian Kuna","573":"Chained 2005 Hong Kong Dollar","574":"Chained 2005 / 2006 Australian Dollar","575":"Chained 2005 Deutsche Mark","576":"Chained 2005 Norwegian Krone","577":"Years","578":"Index, 2005/2006 = 100","579":"Index, 2007 Dec = 100","580":"Constant 1998 Turkish Lira","581":"Index, 2007 = 100","582":"Chained 2006 Hong Kong Dollar","583":"Constant 2003 Mexican Peso","584":"Index, 2008 Apr = 100","585":"Per Thousand","586":"Chained 2005 Israel Shekel","587":"Chained 2006 Euro","588":"Chained 2006 / 2007 Australian Dollar","589":"Index, 2006/2007 = 100","590":"Index, 2007 Nov = 100","591":"Index, 2003 Jan = 100","592":"Index, 1992 Sep = 100","593":"Index, 1995 Jun = 100","594":"Constant 1997 Turkish New Lira","595":"Index, 2008 Dec = 100","596":"Index, 2008 = 100","597":"Chained 2005 South Korean Won","598":"Chained 2007 Hong Kong Dollar","599":"100 Persons","600":"Per Ten Thousand","601":"Chained 2007 Euro","602":"Chained 2005 US Dollar","603":"Index, 2007 Q1 = 100","604":"Index, Average Month of 2005 = 100","605":"Index, 2008 Dec 31 = 100","606":"Constant 2000 Bulgarian Lev","607":"Constant 2001 Bulgarian Lev","608":"Chained 2007 / 2008 Australian Dollar","609":"Index, 2008/2009 = 100","610":"Chained 2007 Norwegian Krone","611":"Constant 2005 South African Rand","612":"Index, 2007/2008 = 100","613":"Index, 2009 = 100","614":"Index, 1996 Jan = 100","615":"Constant 2004/2005 Indian rupee","616":"Chained 2009 Swedish Krona","617":"Constant 2005 Singapore Dollar","618":"Chained 2008 Euro","619":"Chained 2006 Pound Sterling","620":"Chained 2008 Hong Kong Dollar","621":"Index, 2001 = 1000","622":"Index, 2009 = 1000","623":"Index, 28/12/2007 = 3051.83","624":"Chained 2008/2009 Australian Dollar","625":"Index, 2003 Apr 1 = 100","626":"Constant 2003 Russian Federation Rouble","627":"Index, 2nd half of 2010 Dec = 100","628":"Index, 2010 = 100","629":"Index, 2008 Q1 = 100","630":"Index, 2010 Dec = 100","631":"Index, 1993 Jan = 100","632":"Constant 2000 Croatian Kuna","633":"Index, 2010 Q4 = 1000","634":"Index, 2000 H1=100","635":"Index, 2009/2010=100","636":"Chained 2010 Swedish Krona","637":"Constant 2000 Macedonian Denar","638":"Index, 2011 Jun = 100","639":"Constant 2000 Philippine Peso","640":"Index, 2007 Jun = 100","641":"Index, 2009 Jan = 100","642":"Index, 2010 Jan = 100","643":"Constant 2005 Bulgarian Lev","644":"Constant 2005 Hungarian Forint","645":"Constant 2005 Macedonian Denar","646":"Chained 2005 Lithuanian Litas","647":"Constant 2008 Russian Federation Rouble","648":"Chained 2009/2010 Australian Dollar","649":"Chained 2009 Norwegian Krone","650":"Index, 2000 Mar = 100","651":"Index, 2010 Q1 = 100","652":"Chained 2005 Japanese Yen","653":"Chained 2009 Euro","654":"Constant 2005 Euro","655":"Index, 2011 = 100","656":"Chained 2005 Danish Krone","657":"Chained 2002 Thai Baht","658":"Index, 2011 Jun 30 = 1000","659":"Constant 2006 Euro","660":"Constant 2005 Malaysian Ringgit","661":"Chained 2008 Chilean Peso","662":"Index, 1994 Jan = 100","663":"Index, 2012 Apr = 100","664":"Chained 2010 Euro","665":"Chained 2010 Hong Kong Dollar","666":"Index, 2011/2012 = 100","667":"Index, 2006 Q1 = 100","668":"Chained 2010 Norwegian Krone","669":"Index, 2010/2011 = 100","670":"Chained 2010/2011 Australian Dollar","671":"Index, 2012 = 100","672":"Index, 1912 = 100","673":"Chained 2011 Hong Kong Dollar","674":"Chained 2012 Swedish Krona","675":"Constant 2012 Swedish Krona","676":"Index, 2001 Mar = 100","677":"Index, 2013 Mar = 100","678":"Index, 2010 Q4 = 100","679":"Chained 2009 US dollar","680":"Chained 2007 Canadian Dollar","681":"Chained 1990 Algerian Dinar","682":"Index, 1968 Jan = 100","683":"Previous year Bosnian convertible mark","684":"Chained 1990 Chinese Renminbi","685":"Chained 2005 Colombian Peso","686":"Chained 2005 Czech Koruna","687":"Chained 2005 Polish Zloty","688":"Chained 2000 Romanian leu","689":"Chained 1999 Saudi Arabia Riyal","690":"Chained 1988 Thai Baht","691":"Constant 1990 Algerian Dinar","692":"Constant 1990 Chinese Renminbi","693":"Constant 2005 Colombian Peso","694":"Constant 1995 Saudi Arabia Riyal","695":"Constant 2008 Chilean Peso","696":"Constant 1994 Peruvian Sol","697":"Fiscal year 2008 = 100","698":"Chained 2005 Icelandic Krona","699":"Chained 2011 Euro","6AA":"Residual currencies","6BB":"Other currencies","6CC":"Other EMS currencies","700":"Index, 1990 Jan= 100","701":"Chained 2005 Swiss Franc","702":"Constant 2005 Croatian Kuna","703":"Constant 2000 Romanian New Leu","704":"Constant 2005 Icelandic Krona","705":"Constant 2011 Norwegian Krone","706":"Constant 2005 Korean Won","707":"Constant 2008 Mexican Peso","708":"Constant 2010 Israel Shekel","709":"Constant 2005 Polish Zloty","710":"Chained 2005 Hungarian Forint","711":"Chained 2010 Latvian Lat","712":"Constant 2010 Chinese Renminbi","713":"Index, 2013 = 100","714":"Constant 2010 Euro","715":"Chained 2010 Pound Sterling","716":"Chained 2010 Korean won","717":"Index, 2009 Q1 = 100","718":"Index, 2010 Q2 to 2011 Q1 = 100","719":"Index, 2013 Q4 = 100","720":"Constant 2004 Argentine Peso","721":"Index, 2006 Q3 = 100","722":"Index, 2011 Q3 to 2012 Q2 = 100","723":"Constant 2007 Peruvian Sol","724":"Chained 2012 Euro","725":"Constant 2011 Euro","726":"Chained 2010 Croatian Kuna","727":"Constant 2005 Algerian Dinar","728":"Index, 2006 Q4 = 100","729":"Constant 2010 Bulgarian Lev","730":"Chained 2010 Danish Krone","731":"Chained 2010 Swiss Franc","732":"Chained 2010 Czech Koruna","733":"Chained 2010 Lithuanian Litas","734":"Index, October 2013 to September 2014 = 100","735":"Chained 2012 Hong Kong Dollar","736":"Index, 2012/2013 = 100","737":"Chained 2011 Taiwan New Dollar","738":"Index, 1914 = 100","739":"Index, 1951 Jan 01 = 100","740":"Index, 1939 Feb 02 = 100","741":"Index, 1946 Aug 08 =100","742":"Index, 1865 = 100","743":"Index, 1914 Jul 07 = 100","744":"Index, 1982 Jan 01 = 100","745":"Chained 2009/2010 New Zealand Dollar","746":"Index, 2013 Dec = 100","747":"Index, 1960 = 100","748":"Index, 1900 = 100","749":"Index, 1914 Jul = 100","750":"Constant 2010 Czech Koruna","751":"Index, 2001, Oct 1 = 1000","752":"Index, 2005, Oct 1 = 1000","753":"Chained 2010 Serbian Dinar","754":"Index, 2001 June =1000","755":"Constant 2010 Saudi Arabian Riyal","756":"Constant 2000 Peru New Sol","757":"Constant 2007 United Arab Emirates Dirham","758":"Chained 2012 Norwegian Krone","759":"Index, 2014 Dec =100","760":"Constant 2009 Peruvian New Sol","761":"Constant 2010 Indonesian Rupiah","762":"Chained 2013 Swedish krona","763":"Constant 2011/2012 Indian rupee","764":"Index, 2014 = 100","765":"Index, 2011 Dec = 100","766":"Chained 2013 Hong Kong Dollar","767":"Constant 2010 Malaysian Ringgit","768":"Chained 2014 Swedish Krona","769":"Chained 2012 Bosnian convertible mark","770":"Percentage of GDP","771":"Year-on-year changes, in per cent","772":"Euro / Chained 2005 Euro","773":"Chained 2010 Polish Zloty","774":"Chained 1995 Brazilian Real","775":"Constant 2010 South African Rand","776":"Chained 2012 Pound Sterling","777":"Chained 2013 Euro","778":"Constant 2010 Singapore dollar","779":"Index, 2009 December = 100","780":"Index, 2014 Jan = 100","781":"AED/square meter","782":"Chained 2013 Norwegian Krone","783":"Index, 1939 Jan = 100","784":"Index, 1978 - 1979 = 100","785":"Index, 1947 Mar = 100","786":"Index, 1963 Sep - 1964 Aug = 100","787":"Index, 2009 Oct - 2010 Sep = 100","788":"Index, 1988 Apr - 1989 Mar = 100","789":"Previous year Swiss Franc","790":"Index, 1964 Jan = 100","791":"Index, 1981 - 1982 = 100","792":"Index, 1952 - 1953 = 100","793":"Index, 1961 - 1962 = 100","794":"Index, 1970 - 1971 = 100","795":"Index, 1993 - 1994 = 100","796":"Index, 2004 - 2005 = 100","797":"Index, 1953 Apr = 100","798":"Index, 2011 Jul - 2012 Jun = 100","799":"Percentage of GDP (using PPP exchange rates)","800":"Index, 2015 Dec = 100","801":"Index, 2015 = 100","802":"Chained 2011 Russian Rouble","803":"Chained 2014 Hong Kong Dollar","804":"Index, 1977 Apr - 1978 Mar = 100","805":"Index, 2012 Dec = 100","806":"Chained 2015 Swedish Krona","807":"Index, 2014/2015 = 100","808":"Constant 1997 Venezuelan Bolivar Fuerte","809":"Index, 2014 Q4 = 100","810":"Index, 2015 Jan = 100","811":"Chained 2014 Euro","812":"Index, 2014 Nov = 100","813":"Index, 1927 = 1","814":"Chained 2011 Japanese Yen","815":"Index, 2007 Q4 = 100","816":"Index, 2000 Q1 = 100","817":"Index, 2016 Jan = 100","818":"Index, 2014 Q1 = 100","819":"Constant 2011 Russian Federation Rouble","820":"Index, 2016 Nov = 100","821":"Index, 2016 Dec = 100","822":"Chained 2009 Turkish New Lira","823":"Chained 2013 Chilean Peso","824":"Index, 2016 = 100","825":"Index, 2016 Apr = 100","826":"Chained 2015 Hong Kong Dollar","827":"Chained 2016 Swedish Krona","828":"Chained 2015 Israel Shekel","829":"Index, 2001 Jan = 100","830":"Chained 2015 Norwegian Krone","831":"Ton","832":"Index, 2013/2014 = 100","833":"Chained 2016 Russian Federation Rouble","834":"Constant 2013 Mexican Peso","835":"Chained 2015 Pound Sterling","836":"Index, 2017 Q2 = 1000","837":"Constant 2015 Norwegian Krone","838":"Chained 2015 Euro","839":"Index, 2001 Q1 = 100","840":"Index, 2017 = 100","841":"Index, 2016 Oct = 100","842":{"name":"Chained 2016 Hong Kong Dollar"},"843":"Chained 2017 Swedish Krona","844":"Period-to-period change","845":"Chained 2016 Pound Sterling","847":"Volume 2016 Norwegian Krone","848":"Chained 2012 US dollar","849":"Basis Points","850":"Chained 2015 Colombian Peso","851":"Index, 2009Q2 - 2010Q1 = 1000","852":"Chained 2016 Euro","853":"Index, 2010 Mar = 100","854":{"name":"Index, 2018 = 100"},"855":{"name":"Index, 2019 Jan = 100"},"856":{"name":"Index, 2018 Dec = 100"},"857":"Chained 2017 Hong Kong Dollar","858":"Constant 2015 Singapore Dollar","859":"Chained 2015 Singapore Dollar","860":"Chained 2015 Korean won","861":"Constant 2015 Malaysian Ringgit","862":"Index, 2005 Q1 = 100","863":"Index, 2013 Q1 = 100","864":"Constant 2015 Chinese Renminbi","865":"Chained 2017 Euro","866":"Constant 2017 Norwegian Krone","867":"Volume 2017 Norwegian Krone","868":"Chained 2018 Swedish Krona","869":"Constant 2016 Euro","870":"Constant 2015 Bulgarian Lev","871":"Index, 2019 = 100","872":"Constant 2018 Philippine Peso","873":"Chained 2018 Hong Kong Dollar","874":"Chained 2018 Pound Sterling","875":"Index, 2017 Nov = 100","876":"Index, 2017 Oct = 414.5","877":"Index, 2020 Aug = 100","878":"Chained 2015 Japanese Yen","879":"Volume 2018 Norwegian Krone","880":"Constant 2018 Norwegian Krone","881":"Index, 1991 Q1 = 100","882":"Index, 2020 = 100","883":"Index, 2020 Dec =100","884":"Chained 2019 Hong Kong Dollar","885":"Index, 2019/2020 = 100","886":"Constant 2015 South African Rand","887":"Chained 2019 Pound Sterling","888":"Index, 2020 June = 100","889":"Chained 2019 Euro","890":"Volume 2019 Norwegian Krone","891":"Constant 2019 Norwegian Krone","892":"Index, 2020 Jan = 100","893":"Index, 2021 = 100","894":"Index, 2021 Dec = 100","895":"Index, 2022 Jan = 100","896":"Chained 2020 Hong Kong Dollar","897":"Chained 2019 Swedish Krona","898":"Chained 2020 Swedish Krona","899":"Chained 2021 Swedish Krona","900":"Index, 2019 Q4 = 100","901":"Index, 2015 = 1","902":"Constant 2015 Colombian Peso","903":"Chained 2020 Euro","904":"Constant 2015 Euro","905":"Index, 2012 Q4 = 100","906":"Index, 2022 Oct = 100","907":"Index, 1986 Jan 1 = 0.01","908":"Index, 2022 Q3 = 1000","909":"Chained 2021 Hong Kong Dollar","910":"Index, 2010 Aug = 100","911":"Index, 2012 Jun = 100","912":"Index, 2019 Q1 = 100","913":"Index, 2023 Jun = 100","914":"Chained 2017 US dollar","915":"Domestic currency","916":"Constant 2018 Mexican Peso","917":"Constant 2010 Kuwaiti Dinar","918":"Number","919":"Chained 2017 Canadian Dollar","920":"Constant 2017 Canadian Dollar","921":"Index, 2022 = 100","922":"Index, 1989 Jan = 100","923":"Index, 2023 =100","924":"Index, 2023 Dec = 100","925":"Chained 2022 Hong Kong Dollar","926":"Constant 2020 Euro","927":"Chained 2021 Russian Federation Rouble","928":"Constant 2021 Russian Federation Rouble","929":"Constant 2019 Pound Sterling","930":"Chained 2022 Euro","931":"Chained 2021 Euro","932":"Chained 2020 / 2021 Australian Dollar","933":"Chained 2015 Swiss Franc","934":"Chained 2015 Icelandic Krona","935":"Chained 2021 Norwegian Krone","936":"Chained 2023 Swedish Krona","937":"Chained 2020 Korean won","938":"Chained 2018 Philippine Peso","939":"Chained 2016 Taiwan New Dollar","940":"Chained 2018 Chilean Peso","941":"Chained 2020 Czech Koruna","942":"Chained 2015 Hungarian Forint","943":"Constant 2020 Romanian New Leu","944":"Chained 2015 Polish Zloty","945":"Constant 2020 Chinese Renminbi","946":"Chained 2021 Bosnian convertible mark","947":"Constant 2020 Bulgarian Lev","948":"Index, 2024 Jan = 100","949":"Chained 2022 Pound Sterling","950":"Local currency per USD","951":"Local currency per EUR","952":"USD per local currency","953":"EUR per local currency","954":"Euro / Chained 2020 Euro","955":"Index, 2023 Jan = 100","956":"Index, 2024 Dec = 100","957":"Index, 2024 = 100","958":"Chained 2023 Hong Kong Dollar","959":"Index, 2021 June = 100","960":"Index, 2025 Mar = 100","961":"Index, 2021 July = 100","962":"Index, 2022 Q2 to 2023 Q1 = 100","963":"Chained 2020 Japanese Yen","964":"Index, 2025 Oct = 100","965":"Index, 2025 = 100","AED":"UAE dirham","AFA":"Afghanistan Afghani (up to 2003)","AFN":"Afghanistan Afghani","ALL":"Lek","AMD":"Dram","ANG":"Netherlands Antillean guilder","AOA":"Angolan Kwanza","ARA":"Argentinian Austral (legacy)","ARP":"Argentino Peso (legacy)","ARS":"Argentine peso","ATS":"Austrian schilling","AUD":"Australian dollar","AWG":"Aruban florin","AZN":"Azerbaijan manat","BAM":"Bosnian convertible mark","BBD":"Barbados dollar","BDT":"Taka","BEF":"Belgian franc","BEL":"Belgian Financial Franc","BGN":"Lev","BHD":"Bahraini dinar","BIF":"Burundi franc","BMD":"Bermuda Dollar","BND":"Brunei dollar","BOB":"Boliviano","BRB":"Brazilian Cruzeiro (1970-1986)","BRC":"Brazilian Cruzado (legacy)","BRE":"Brazilian Cruzeiro (legacy)","BRI":"Brazilian Reis (legacy)","BRL":"Brazilian real","BRN":"Brazil New Cruzado (legacy)","BRR":"Brazilian Cruzeiro Real (legacy)","BRU":"Brazilian Cruzeiro (1942-1967)","BRW":"Brazilian New Cruzeiro","BSD":"Bahamian dollar","BTN":"Ngultrum","BWP":"Pula","BYB":"Belarusian Roubles","BYN":"Belarusian Ruble","BYR":"Belarusian rouble","BZD":"Belize dollar","CAD":"Canadian dollar","CDF":"Congolese franc","CHF":"Swiss franc","CLF":"Unidad de Fomento","CLP":"Chilean peso","CLS":"o/w CLS eligible pairs","CNY":"Renminbi","COP":"Colombian peso","CRC":"Costa Rica colon","CSD":"Serbian & Montenegru Dinar","CVE":"Cabo Verde escudo","CYP":"Cyprus pound","CZK":"Czech koruna","DEM":"Deutsche mark","DJF":"Djibouti franc","DKK":"Danish krone","DOP":"Dominican peso","DZD":"Algerian dinar","ECS":"Ecuadorian Sucre","EEK":"Estonian kroon","EGP":"Egyptian pound","ERN":"Nakfa","ESP":"Spanish peseta","ETB":"Ethiopian birr","EUR":"Euro","FIM":"Finnish markka","FJD":"Fiji dollar","FRF":"French franc","GBP":"Pound (sterling)","GEL":"Lari","GHS":"Ghana cedi","GMD":"Dalasi","GNF":"Guinean franc","GRD":"Greek drachma","GTQ":"Guatemalan quetzal","GWP":"Guinea Bissau Peso","GYD":"Guyana dollar","HKD":"Hong Kong dollar","HNL":"Lempira","HRK":"Kuna","HTG":"Gourde","HUF":"Forint","IDR":"Rupiah","IEP":"Irish pound","ILS":"New shekel","INR":"Indian rupee","IQD":"Iraqi dinar","IRR":"Iranian rial","ISK":"Icelandic krona","ITL":"Italian lira","JMD":"Jamaican dollar","JOD":"Jordanian dinar","JPY":"Yen","KES":"Kenyan shilling","KGS":"Som","KHR":"Riel","KMF":"Comorian franc","KPW":"North Korean won","KRW":"Won","KWD":"Kuwaiti dinar","KYD":"Cayman Islands dollar","KZT":"Tenge","LAK":"Lao kip","LBP":"Lebanese pound","LKR":"Sri Lanka rupee","LRD":"Liberian dollar","LSL":"Loti","LTL":"Lithuanian litas","LUF":"Luxembourg franc","LVL":"Latvian lats","LYD":"Libyan dinar","MAD":"Moroccan dirham","MDL":"Moldovan leu","MGA":"Malagasy ariary","MGF":"Malagasy Franc","MKD":"Denar","MMK":"Kyat","MNT":"Tugrik","MOP":"Pataca","MRO":"Mauritanian ouguiya","MRU":"Mauritanian ouguiya","MTL":"Maltese lira","MUR":"Mauritius rupee","MVR":"Rufiyaa","MWK":"Malawi kwacha","MXN":"Mexican peso","MXP":"Mexican Peso (historical)","MXV":"Mexican Unidad de Inversion (UDI)","MYR":"Malaysian ringgit","MZN":"Mozambique metical","NAD":"Namibian dollar","NGN":"Naira","NIO":"Cordoba","NLG":"Dutch guilder","NOK":"Norwegian krone","NPR":"Nepalese rupee","NZD":"New Zealand dollar","OMR":"Omani rial","PAB":"Balboa","PEN":"Sol","PGK":"Kina","PHP":"Philippine peso","PKR":"Pakistan rupee","PLN":"Zloty","PLZ":"Poland Zloty","PTE":"Portuguese escudo","PYG":"Guarani","QAR":"Qatari riyal","ROL":"Romanian Leu","RON":"Romanian leu","RSD":"Serbian Dinar","RUB":"Russian rouble","RUR":"Russian Rouble (prior to 1 Januar 1998)","RWF":"Rwanda franc","SAR":"Saudi riyal","SBD":"Solomon Islands dollar","SCR":"Seychelles rupee","SDG":"Sudanese pound","SDR":"SDR","SEK":"Swedish krona","SGD":"Singapore dollar","SIT":"Slovenian tolar","SKK":"Slovak koruna","SLL":"Leone","SOS":"Somali shilling","SPD":"Speciedaler","SRD":"Suriname dollar","SRG":"Suriname Guilder","SSP":"South Sudanese Pound","STD":"Sao Tome and Principe Dobra","STN":"Sao Tomean Dobra","SVC":"El Salvador Colon","SYP":"Syrian pound","SZL":"Lilangeni","THB":"Baht","TJS":"Tajikistani Somoni","TMM":"Turkmenistan Manat (old)","TMT":"Turkmenistan new manat","TND":"Tunisian dinar","TO1":"Total (all currencies)","TOP":"Paanga","TRL":"Turkish Lira (legacy)","TRY":"Turkish lira","TTD":"Trinidad and Tobago dollar","TWD":"New Taiwan dollar","TZS":"Tanzanian shilling","UAH":"Hryvnia","UGX":"Uganda shilling","UN9":"Technical Residual","USD":"US dollar","UYI":"Uruguay Peso en Unidades","UYP":"Uruguayan Peso (historical)","UYU":"Uruguayan peso","UZS":"Sum","VEB":"Venezuela Bolivar","VEF":"Bolivar","VES":"Bolivar soberano","VND":"Dong","VUV":"Vatu","WST":"Tala","XAF":"CFA franc","XCD":"Eastern Caribbean dollar","XDC":"Domestic currency (incl. conv. to current ccy made using a fix parity)","XDR":"SDR (Special Drawing Right)","XEU":"European currency unit","XFO":"Gold franc","XOF":"CFA franc","YER":"Yemeni riyal","YUM":"Yugoslav Dinar","ZAR":"Rand","ZMK":"Zambian Kwacha","ZMW":"Zambian Kwacha","ZWD":"Zimbabwe Dollar","ZWG":"Zimbabwe Gold","ZWL":"Zimbabwe Dollar (fourth)"}},"CL_DECIMALS":{"name":"Decimals codelist (BIS, ECB)","codes":{"0":"Zero","1":"One","10":"Ten","11":"Eleven","12":"Twelve","13":"Thirteen","14":"Fourteen","15":"Fifteen","2":"Two","3":"Three","4":"Four","5":"Five","6":"Six","7":"Seven","8":"Eight","9":"Nine","16":"Sixteen"}},"CL_TIME_FORMAT":{"name":"Possible formats for representation of dates, times or dateranges","codes":{"102":"CCYYMMDD","203":"CCYYMMDDhhmm","602":"CCYY","604":"CCYYS","608":"CCYYQ","610":"CCYYMM","616":"CCYYWW","702":"CCYYCCYY","704":"CCYYSCCYYS","708":"CCYYQCCYYQ","710":"CCYYMMCCYYMM","711":"CCYYMMDDCCYYMMDD","716":"CCYYWWCCYYWW","P1D":"Daily (or Business)","P1M":"Monthly","P1Y":"Annual","P3M":"Quarterly","P6M":"Half-yearly, semester","P7D":"Weekly"}},"CL_UNIT_MULT":{"name":"Unit Multiplier","codes":{"0":"Units","1":"Tens","12":"Trillions","15":"Quadrillions","2":"Hundreds","3":"Thousands","4":"Tens of thousands","6":"Millions","7":"Tens of millions","8":"Hundred millions","9":"Billions"}},"CL_AVAILABILITY":{"name":"Availability","codes":{"A":"All users","B":"BIS only, not for publication","C":"BIS and G-10 central banks only, not for publication","D":"ESCB only, not for publication","E":"ECB only, not for publication","G":"BIS and ESCB only, not for publication","H":"BIS and ECB only, not for publication","I":"BIS, ECB and Central Banks only, not for publication","J":"(BIS) Low frequency free, high frequency restricted","K":"Free, last value not to be published prior to embargo date","L":"(BIS) High frequency free, low frequency restricted","N":"(BIS) Low frequency free, high frequency ECB only","O":"Commission/Eurostat only; not for publication","P":"Commission/Eurostat and ECB only; not for publication","Q":"Commission/Eurostat and ESCB only; not for publication","T":"BIS and IMF only; not for publication","U":"ECB and EMU members only; not for publication","W":"Confidential - For BIS, ECB and G10 NCBs; only named persons","Z":"Restricted - For BIS, ECB, reporting CBs; authorised individuals","X":"BIS only, free"}},"CL_BIS_IF_REF_AREA":{"name":"Reference Area Code for BIS-IFS","codes":{"00":"Others","11":"Technical residual (Non-residents / Cross-border)","1A":"US banks in offshore centres","1B":"International banking facilities","1C":"International organisations","1D":"Official monetary authorities","1E":"Residents/Local","1F":"Cross-border financial centres","1G":"Consortium banks","1H":"Certificates of deposit","1J":"Estimated CDs held for offshore institutions","1K":"Cross-border banking centres","1L":"Holdings of long-term securities res.","1M":"United States excl. IBFs","1N":"Offshore centres","1O":"Caribbean offshore","1P":"Asian offshore","1Q":"Non-reporting offshore centres","1R":"European offshore","1T":"Other offshore","1U":"Botswana/Lesotho","1W":"Unallocated British Overseas Territories","1X":"European Central Bank","1Z":"West Indies UK","2A":"Other developing Europe","2B":"Unallocated emerging Europe","2C":"Former Serbia and Montenegro","2D":"Former Netherlands Antilles","2E":"Residual Eastern Europe","2F":"Unallocated non-reporting emerging Latin America and Caribbean","2G":"Other developing Latin America and Caribbean","2H":"Unallocated emerging Latin America and Caribbean","2J":"Unallocated non-reporting emerging Africa and Middle East","2K":"Unallocated non-reporting offshore centres","2L":"Unallocated non-reporting advanced economies","2M":"Other offshore centres","2N":"Unallocated offshore centres","2O":"Unallocated emerging Asia and Pacific","2P":"Other developing Asia and Pacific","2Q":"Other advanced","2R":"Unallocated advanced economies","2S":"Former Yugoslavia","2T":"Former Soviet Union","2U":"Former Czechoslovakia","2V":"Other developing Africa and Middle East","2W":"Unallocated emerging Africa and Middle East","2X":"Unallocated non-reporting emerging Asia and Pacific","2Y":"Unallocated non-reporting emerging Europe","2Z":"Unallocated West Indies UK","3A":"Non-European developed countries","3C":"Emerging Europe","3E":"Eastern Europe","3P":"All countries excluding residents","3T":{"name":"BIS IBS - LEGACY LEAF LEVEL","desc":"Legacy leaf aggregates"},"3W":"Non-reporting emerging Africa and Middle East","3X":"Non-reporting emerging Asia and Pacific","3Y":"Non-reporting emerging Europe","3Z":"Non-reporting emerging Latin America and Caribbean","4A":"G10 countries","4B":"Domestic banks","4C":"Inside-area foreign banks consolidated by their parent","4D":"Outside area foreign banks","4E":"Inside-area foreign banks not consolidated by their parent","4F":"OPEC countries","4G":"Oil exporters","4H":"Middle East oil exporters","4I":"Other oil exporters","4J":"Other Europe advanced","4K":"Non-opec ldcs","4L":"Other advanced","4M":"All banks (=4B +4C + 4D +4E)","4N":"All including 4C banks, excl. domestic positions (=4O + 4C)","4O":"All excluding 4C banks, excl. domestic positions (= 4R + 4Q +4V)","4P":"Large banking groups","4Q":"Outside area foreign banks(4D), excl. domestic positions","4R":"Domestic banks(4B), excl. domestic positions","4S":"BRIC countries","4T":"Emerging market and developing economies","4U":"Emerging Latin America and Caribbean","4V":"Inside area foreign banks not consol.by parents (4E), excl. domestic positions","4W":"Emerging Africa and Middle East","4Y":"Emerging Asia and Pacific","4Z":"Residual bank","5A":"All reporting countries","5B":"European Union","5C":"Euro area","5D":"Ultimate risk data reporting countries","5E":"European reporting countries","5F":"Other Asian countries","5G":"Non-European countries","5H":"Unallocated BIS reporting countries","5I":"Unallocated - Euro area intergovernmental organizations and agencies","5J":"All countries","5K":"Advanced Europe","5L":"BIS reporting countries","5M":"Unallocated location","5N":"Non-reporting advanced economies","5P":"All other countries","5Q":"Countries with non-public data","5R":"Advanced economies","5S":"Joint BIS-OECD-IMF-Worldbank statistics on external debt","5T":"IBLR currency reporting countries","5U":"Latin America","5V":"IBLN currency reporting countries","5W":"Unallocated non-BIS reporting countries","5X":"Non-BIS reporting countries","5Y":"Unclassified non-residents","5Z":"Non-residents/Cross-border","6A":"European Union 6 - 1958","6B":"European Union 9 - 1973","6C":"European Union 10 - 1981","6D":"European Union 12 - 1986","6E":"EU developing countries","6F":"EU developed countries","6G":"European Union 15 - 1995","6H":"European Union 25 - 2004","6I":"US banks in Cayman Islands","6J":"US banks in Bahamas","6K":"European Union 27 - 2007","6L":"US banks in Panama","6O":"Non-US banks in Bahamas","6P":"Non-US banks in Cayman Islands","6T":{"name":"BIS IBS - LEGACY AGGREGATES","desc":"Legacy aggregates"},"7A":"Euro area 11 - 1999","7B":"Euro area 12 - 2001","7C":"Euro area 13 - 2007","7D":"Euro area 15 - 2008","7E":"Euro area 16 - 2009","7F":"Euro area 17 - 2011","7G":"Euro area 18 - 2014","7H":"Japan offshore market","7I":"Japan non-offshore market","7J":"Japan offshore market residents","7L":"Euro area 20 - 2023","8A":"All exchanges","8B":"North American exchanges","8C":"European exchanges","8E":"Asian/Pacific exchanges","8F":"Asian exchanges","8G":"Australia/New Zealand exchanges","8H":"Non-US exchanges","8K":"Other exchanges","9T":{"name":"BIS IBS - LEGACY DISCONTINUED","desc":"Deleted countries (aggregate)"},"9Z":"Unallocated counterparty country","AD":"Andorra","AE":"United Arab Emirates","AF":"Afghanistan","AG":"Antigua and Barbuda","AI":"Anguilla","AL":"Albania","AM":"Armenia","AN":"Netherlands Antilles","AO":"Angola","AQ":"Antarctica","AR":"Argentina","AS":"American Samoa","AT":"Austria","AU":"Australia","AW":"Aruba","AX":"Aland Islands","AZ":"Azerbaijan","BA":"Bosnia and Herzegovina","BB":"Barbados","BD":"Bangladesh","BE":"Belgium","BF":"Burkina Faso","BG":"Bulgaria","BH":"Bahrain","BI":"Burundi","BJ":"Benin","BL":"Saint Barthelemy","BM":"Bermuda","BN":"Brunei","BO":"Bolivia","BQ":"Bonaire, Sint Eustatius and Saba","BR":"Brazil","BS":"The Bahamas","BT":"Bhutan","BU":"Burma","BV":"Bouvet Island","BW":"Botswana","BY":"Belarus","BZ":"Belize","C1":"Switzerland Trustee positions","C2":"Switzerland excl. Trustee positions","C9":"Czechoslovakia","CA":"Canada","CC":"Cocos (Keeling) Islands","CD":"Democratic Republic of the Congo","CF":"Central African Republic","CG":"Republic of Congo","CH":"Switzerland","CI":"C\u00f4te d'Ivoire","CK":"Cook Islands","CL":"Chile","CM":"Cameroon","CN":"China","CO":"Colombia","CR":"Costa Rica","CS":"Serbia and Montenegro","CT":"Canton and Enderbury Islands","CU":"Cuba","CV":"Cabo Verde","CW":"Cura\u00e7ao","CX":"Christmas Island","CY":"Cyprus","CZ":"Czechia","DD":"German Democratic Republic","DE":"Germany","DJ":"Djibouti","DK":"Denmark","DM":"Dominica","DO":"Dominican Republic","DY":"Dahomey","DZ":"Algeria","EC":"Ecuador","EE":"Estonia","EG":"Egypt","EH":"Western Sahara","ER":"Eritrea","ES":"Spain","ET":"Ethiopia","EU":"European Union","FI":"Finland","FJ":"Fiji","FK":"Falkland Islands","FM":"Micronesia","FO":"Faeroe Islands","FQ":"French Southern and Antarctic Territories","FR":"France","FX":"France, Metropolitan","G1":"United Kingdom incl. Channel Islands","GA":"Gabon","GB":"United Kingdom","GD":"Grenada","GE":"Georgia","GF":"French Guiana","GG":"Guernsey","GH":"Ghana","GI":"Gibraltar","GL":"Greenland","GM":"The Gambia","GN":"Guinea","GP":"Guadeloupe","GQ":"Equatorial Guinea","GR":"Greece","GS":"South Georgia and the South Sandwich Islands","GT":"Guatemala","GU":"Guam","GW":"Guinea-Bissau","GY":"Guyana","HK":"Hong Kong SAR","HM":"Heard Island and McDonald Islands","HN":"Honduras","HR":"Croatia","HT":"Haiti","HU":"Hungary","HV":"Upper Volta","ID":"Indonesia","IE":"Ireland","IL":"Israel","IM":"Isle of Man","IN":"India","IO":"British Indian Ocean Territory","IQ":"Iraq","IR":"Iran","IS":"Iceland","IT":"Italy","J1":"Japan Trustee positions","J2":"Japan excl. Trustee positions","JE":"Jersey","JM":"Jamaica","JO":"Jordan","JP":"Japan","JT":"Johnston Island","KE":"Kenya","KG":"Kyrgyz Republic","KH":"Cambodia","KI":"Kiribati","KM":"Comoros","KN":"St Kitts and Nevis","KP":"North Korea","KR":"Korea","KW":"Kuwait","KY":"Cayman Islands","KZ":"Kazakhstan","LA":"Laos","LB":"Lebanon","LC":"St Lucia","LI":"Liechtenstein","LK":"Sri Lanka","LR":"Liberia","LS":"Lesotho","LT":"Lithuania","LU":"Luxembourg","LV":"Latvia","LY":"Libya","MA":"Morocco","MC":"Monaco","MD":"Moldova","ME":"Montenegro","MF":"Saint Martin (French part)","MG":"Madagascar","MH":"Marshall Islands","MI":"Midway Islands","MK":"North Macedonia","ML":"Mali","MM":"Myanmar","MN":"Mongolia","MO":"Macao SAR","MP":"Northern Marianas islands","MQ":"Martinique","MR":"Mauritania","MS":"Montserrat","MT":"Malta","MU":"Mauritius","MV":"Maldives","MW":"Malawi","MX":"Mexico","MY":"Malaysia","MZ":"Mozambique","NA":"Namibia","NC":"New Caledonia","NE":"Niger","NF":"Norfolk Island","NG":"Nigeria","NH":"New Hebrides","NI":"Nicaragua","NL":"Netherlands","NO":"Norway","NP":"Nepal","NQ":"Dronning Maud Land","NR":"Nauru","NT":"Neutral Zone","NU":"Niue","NZ":"New Zealand","OM":"Oman","PA":"Panama","PC":"Pacific Islands, Trust Territory of the","PE":"Peru","PF":"French Polynesia","PG":"Papua New Guinea","PH":"Philippines","PK":"Pakistan","PL":"Poland","PM":"Saint Pierre and Miquelon","PN":"Pitcairn","PR":"Puerto Rico","PS":"Palestinian Territory","PT":"Portugal","PU":"U.S. Miscellaneous Pacific Islands","PW":"Palau","PY":"Paraguay","PZ":"Panama Canal Zone","QA":"Qatar","RE":"Reunion","RH":"Southern Rhodesia","RO":"Romania","RS":"Serbia","RU":"Russia","RW":"Rwanda","SA":"Saudi Arabia","SB":"Solomon Islands","SC":"Seychelles","SD":"Sudan","SE":"Sweden","SG":"Singapore","SH":"St Helena, Ascension and Tristan da Cunha","SI":"Slovenia","SJ":"Svalbard and Jan Mayen","SK":"Slovakia","SL":"Sierra Leone","SM":"San Marino","SN":"Senegal","SO":"Somalia","SR":"Suriname","SS":"South Sudan","ST":"S\u00e3o Tom\u00e9 and Pr\u00edncipe","SU":"USSR (Soviet Union)","SV":"El Salvador","SX":"Sint Maarten","SY":"Syria","SZ":"Eswatini","TC":"Turks and Caicos Islands","TD":"Chad","TF":"French Southern Territories","TG":"Togo","TH":"Thailand","TJ":"Tajikistan","TK":"Tokelau","TL":"East Timor","TM":"Turkmenistan","TN":"Tunisia","TO":"Tonga","TP":"East Timor","TR":"T\u00fcrkiye","TT":"Trinidad and Tobago","TV":"Tuvalu","TW":"Chinese Taipei","TZ":"Tanzania","U2":"Euro area (Member States and Institutions of the Euro Area) changing composition","UA":"Ukraine","UG":"Uganda","UM":"United States Minor Outlying Islands","US":"United States","UY":"Uruguay","UZ":"Uzbekistan","VA":"Vatican City State","VC":"St Vincent and the Grenadines","VD":"Viet-Nam, Democratic Republic of","VE":"Venezuela","VG":"British Virgin Islands","VI":"Virgin Islands (U.S.)","VN":"Vietnam","VU":"Vanuatu","WA":"Waemu","WF":"Wallis and Futuna Islands","WK":"Wake Island","WS":"Samoa","XM":"Euro area","XW":"World","YD":"Yemen, Democratic","YE":"Yemen","YT":"Mayotte","YU":"Yugoslavia","Z2":"OECD","Z4":"Legacy countries","ZA":"South Africa","ZM":"Zambia","ZR":"Zaire","ZW":"Zimbabwe","_Z":"Not applicable"}},"CL_CBS_BASIS":{"name":"CBS basis","codes":{"F":{"name":"Immediate counterparty basis","desc":"Methodology whereby positions are allocated to the primary party to a contract. In the CBS, claims on an immediate counterparty basis are allocated to the country and sector of the entity to which the funds were lent."},"O":{"name":"Outward risk transfers","desc":"Outward risk transfers reallocate claims out of the country of the immediate counterparty."},"P":{"name":"Inward risk transfers","desc":"Inward risk transfers reallocate claims into the country of the guarantor."},"Q":{"name":"Net risk transfers (Inward-Outward)","desc":"Inward minus outward risk transfers."},"R":"Guarantor basis, calculated (=F+Q)","U":{"name":"Guarantor basis","desc":"Methodology whereby positions are allocated to a third party that has contracted to assume the debts or obligations of the primary party if that party fails to perform. In the CBS, claims on a guarantor basis are allocated to the country and sector of the entity that guarantees the claims (or, in th"},"Y":"Residual reporting basis"}},"CL_COLLECTION":{"name":"Collection","codes":{"A":"Average of observations through period","B":"Beginning of period","E":"End of period","H":"Highest in period","L":"Lowest in period","M":"Middle of period","S":"Summed through period","U":"Unknown","V":"Other","Y":"Annualised summed"}},"CL_CURRENCY_3POS":{"name":"Currency","codes":{"ADP":"Andorran Peseta","AED":"UAE dirham","AFA":"Afghani","AFN":"Afghani","ALK":"Old Lek","ALL":"Lek","AMD":"Dram","ANG":"Netherlands Antillean guilder","AOA":"Angolan Kwanza","AOK":"Kwanza","AON":"New Kwanza","AOR":"Readjusted kwanza","ARA":"Austral","ARP":"Peso Argentino","ARS":"Argentine peso","ARY":"Peso","ATS":"Austrian schilling","AUD":"Australian dollar","AWG":"Aruban florin","AYM":"Azerbaijan Manat","AZM":"Azerbaijanian Manat","AZN":"Azerbaijan manat","BAD":"Dinar","BAM":"Bosnian convertible mark","BBD":"Barbados dollar","BDT":"Taka","BEC":"Convertible Franc","BEF":"Belgian franc","BEL":"Financial Franc","BGJ":"Lev A/52","BGK":"Lev A/62","BGL":"Lev","BGN":"Lev","BHD":"Bahraini dinar","BIF":"Burundi franc","BMD":"Bermudian dollar","BND":"Brunei dollar","BOB":"Boliviano","BOP":"Peso boliviano","BOV":"Bolivian Mvdol","BRB":"Cruzeiro","BRC":"Cruzado","BRE":"Cruzeiro","BRL":"Brazilian real","BRN":"New Cruzado","BRR":"Cruzeiro Real","BSD":"Bahamian dollar","BTN":"Ngultrum","BUK":"Kyat","BWP":"Pula","BYB":"Belarusian Ruble","BYN":"Belarusian Ruble","BYR":"Belarusian rouble","BZD":"Belize dollar","CAD":"Canadian dollar","CDF":"Congolese franc","CHC":"WIR Franc (for electronic)","CHE":"WIR Euro","CHF":"Swiss franc","CHW":"WIR Franc","CLF":"Unidades de fomento","CLP":"Chilean peso","CNH":"Renminbi offshore","CNY":"Renminbi","COP":"Colombian peso","COU":"Unidad de Valor Real","CRC":"Costa Rica colon","CSD":"Serbian Dinar","CSJ":"Krona A/53","CSK":"Koruna","CUC":"Peso Convertible","CUP":"Cuban peso","CVE":"Cabo Verde escudo","CYP":"Cyprus pound","CZK":"Czech koruna","DDM":"Mark der DDR","DEM":"Deutsche mark","DJF":"Djibouti franc","DKK":"Danish krone","DOP":"Dominican peso","DZD":"Algerian dinar","ECS":"Sucre","ECU":"European Currency Unit","ECV":"Unidad de Valor Constante (UVC)","EEK":"Estonian kroon","EGP":"Egyptian pound","ERN":"Nakfa","ESA":"Spanish Peseta","ESB":"Spanish peseta","ESP":"Spanish Peseta","ETB":"Ethiopian Birr","EU1":"Sum of ECU, Euro and legacy currencies now included in the Euro","EUA":"European unit of accounts","EUR":"Euro","EUX":"euro - reported","FC1":"Foreign currency","FIM":"Finnish markka","FJD":"Fiji dollar","FKP":"Falkland Islands pound","FRF":"French franc","GBP":"Pound (sterling)","GEK":"Georgian Coupon","GEL":"Lari","GHC":"Cedi","GHP":"Ghana Cedi","GHS":"Ghana cedi","GIP":"Gibraltar pound","GMD":"Dalasi","GNE":"Syli","GNF":"Guinean franc","GNS":"Syli","GQE":"Ekwele","GRD":"Greek drachma","GTQ":"Guatemalan quetzal","GWE":"Guinea Escudo","GWP":"Guinea-Bissau Peso","GYD":"Guyana dollar","HKD":"Hong Kong dollar","HNL":"Lempira","HRD":"Croatian Dinar","HRK":"Kuna","HTG":"Gourde","HUF":"Forint","IDR":"Rupiah","IEP":"Irish pound","ILN":"Israel Shekel (old)","ILP":"Pound","ILR":"Old Shekel","ILS":"New shekel","INR":"Indian rupee","IQD":"Iraqi dinar","IRR":"Iranian rial","ISJ":"Old Krona","ISK":"Icelandic krona","ITL":"Italian lira","JMD":"Jamaican dollar","JOD":"Jordanian dinar","JPY":"Yen","KES":"Kenyan shilling","KGS":"Som","KHR":"Riel","KMF":"Comorian franc","KPW":"North Korean won","KRW":"Won","KWD":"Kuwaiti dinar","KYD":"Cayman Islands dollar","KZT":"Tenge","LAJ":"Pathet Lao Kip","LAK":"Lao kip","LBP":"Lebanese pound","LC1":"Local currency","LKR":"Sri Lanka rupee","LRD":"Liberian dollar","LSL":"Loti","LSM":"Loti","LTL":"Lithuanian litas","LTT":"Talonas","LUC":"Luxembourg Convertible Franc","LUF":"Luxembourg franc","LUL":"Luxembourg Financial Franc","LVL":"Latvian lats","LVR":"Latvian Ruble","LYD":"Libyan dinar","MAD":"Moroccan dirham","MDL":"Moldovan leu","MGA":"Malagasy ariary","MGF":"Malagasy Franc","MKD":"Denar","MLF":"Mali Franc","MMK":"Kyat","MNT":"Tugrik","MOP":"Pataca","MRO":"Mauritanian ouguiya","MRU":"Mauritanian ouguiya","MTL":"Maltese lira","MTP":"Maltese Pound","MUR":"Mauritius rupee","MVQ":"Maldive Rupee","MVR":"Rufiyaa","MWK":"Malawi kwacha","MXN":"Mexican peso","MXP":"Mexican Peso","MXV":"Mexican Unidad de Inversion","MYR":"Malaysian ringgit","MZE":"Mozambique Escudo","MZM":"Mozambique Metical","MZN":"Mozambique metical","NAD":"Namibian dollar","NGN":"Naira","NIC":"Cordoba","NIO":"Cordoba","NLG":"Dutch guilder","NOK":"Norwegian krone","NPR":"Nepalese rupee","NZD":"New Zealand dollar","OMR":"Omani rial","OTH":"Other currencies","PAB":"Balboa","PEH":"Sol","PEI":"Inti","PEN":"Sol","PES":"Sol","PGK":"Kina","PHP":"Philippine peso","PKR":"Pakistan rupee","PLN":"Zloty","PLZ":"Zloty","PTE":"Portuguese escudo","PYG":"Guarani","QAR":"Qatari riyal","RHD":"Rhodesian Dollar","RL9":"Residual","ROK":"Leu A/52","ROL":"Old Leu","RON":"Romanian leu","RSD":"Serbian Dinar","RUB":"Russian rouble","RUR":"Russian Ruble","RWF":"Rwanda franc","SAR":"Saudi riyal","SBD":"Solomon Islands dollar","SCR":"Seychelles rupee","SDD":"Sudanese Dinar","SDG":"Sudanese pound","SDP":"Sudanese Pound","SDR":"SDR","SEK":"Swedish krona","SGD":"Singapore dollar","SHP":"St Helena pound","SIT":"Slovenian tolar","SKK":"Slovak koruna","SLL":"Leone","SOS":"Somali shilling","SRD":"Suriname dollar","SRG":"Surinam Guilder","SSP":"South Sudanese pound","STD":"Sao Tome Dobra","STN":"Dobra","SUR":"Rouble","SVC":"El Salvador Colon","SYP":"Syrian pound","SZL":"Lilangeni","THB":"Baht","TJR":"Tajik rouble","TJS":"Tajikistani Somoni","TMM":"Turkmenistan Manat","TMT":"Turkmenistan new manat","TND":"Tunisian dinar","TO1":"All currencies","TO2":"All currencies excluding USD, EUR and JPY","TO3":{"name":"All currencies excl. core","desc":"All currencies excluding core (ie USD, EUR, JPY, CHF and GBP)"},"TO4":{"name":"Merrill Lynch Multi Currency","desc":"Merrill Lynch Multi Currency for ICS data loading"},"TOP":"Pa'anga","TPE":"Timor Escudo","TRL":"Old Turkish Lira","TRY":"Turkish lira","TTD":"Trinidad and Tobago dollar","TWD":"New Taiwan dollar","TZS":"Tanzanian shilling","UAH":"Hryvnia","UAK":"Karbovanet","UGS":"Uganda Shilling","UGW":"Old Shilling","UGX":"Uganda shilling","UN9":"Unallocated currencies","USD":"US dollar","USN":"US Dollar (Next day)","USS":"US Dollar (Same day)","UYI":"Uruguay Peso en Unidades Indexadas (URUIURUI)","UYN":"Old Uruguay Peso","UYP":"Uruguayan Peso","UYU":"Uruguayan peso","UZS":"Sum","VEB":"Bolivar","VEF":"Bolivar","VES":"Bolivar Soberano","VNC":"Old Dong","VND":"Dong","VUV":"Vatu","WST":"Tala","XAF":"CFA franc","XAG":"Silver","XAU":"Gold","XBA":"Bond Markets Unit European Composite Unit (EURCO)","XBB":"Bond Markets Unit European Monetary Unit (E.M.U.-6)","XBC":"Bond Markets Unit European Unit of Account 9 (E.U.A.-9)","XBD":"Bond Markets Unit European Unit of Account 17 (E.U.A.-17)","XCD":"Eastern Caribbean dollar","XDR":"Special drawing right","XEU":"European currency unit","XFO":"Gold franc","XFU":"UIC-Franc","XFX":"All currencies other then domestic","XOF":"CFA franc","XPD":"Palladium","XPF":"CFP franc","XPT":"Platinum","XSU":"Sucre","XTS":"Codes specifically reserved for testing purposes","XUA":"ADB Unit of Account","XWX":"ECB / SEC all currencies","XXX":"The codes assigned for transactions where no currency is involved","YDD":"Yemeni Dinar","YER":"Yemeni Rial","YUD":"New Yugoslavian Dinar","YUM":"New Dinar","YUN":"Yugoslavian Dinar","Z06":"ECB / SEC Non-MU currencies combined","Z07":"ECB / SEC All currencies other than domestic, Euro and MU currencies","Z08":"ECB / SEC EU 15 currencies","Z12":"ECB / SEC Euro and Greek Drachma","Z16":"ECB / SEC Other currencies except Greek Drachma","ZAL":"Financial Rand","ZAR":"South African Rand","ZMK":"Zambian Kwacha (former)","ZMW":"Zambian Kwacha","ZRN":"New Zaire","ZRZ":"Zaire","ZWC":"Rhodesian Dollar","ZWD":"Zimbabwe Dollar","ZWG":"Zimbabwe Gold","ZWL":"Zimbabwe Dollar","ZWN":"Zimbabwe Dollar (new)","ZWR":"Zimbabwe Dollar","ZZZ":"Not applicable","XCG":"Caribbean Guilder"}},"CL_ISSUE_MAT":{"name":"Issue maturity code list","codes":{"A":{"name":"Total (all maturities)","desc":"Sum of all maturities."},"B":"On demand and open positions","C":{"name":"Short-term","desc":"Having a maturity up to and including one year or on demand."},"D":{"name":"Over 1 year and up to 5 years","parent":"A","desc":"Between one and five years."},"E":"Commercial papers","F":{"name":"Over 5 years","parent":"A","desc":"More than five years."},"G":{"name":"7 days or less","parent":"A","desc":"Up to seven days."},"H":{"name":"Over 7 days and up to 1 month","parent":"A","desc":"Over seven days and up to one month. Market conventions: 2W (two weeks), 1M (one month)."},"I":"Other short-term issues","J":{"name":"Over 1 month and up to 3 months","parent":"A","desc":"Over one month and up to three months. Market conventions: 3M (three months)."},"K":{"name":"Long-term","desc":"Having a maturity greater than one year."},"L":"Over 3 months and up to 1 year","M":{"name":"Over 1 year and up to and including 2 years","desc":"Claims with a remaining maturity over one year and up to and including two years."},"N":{"name":"Over 2 years","desc":"Claims with a remaining maturity over two years."},"O":"2-5 years","P":{"name":"Over 7 days and up to 1 year","parent":"A","desc":"Between seven days and one year."},"Q":"5-10 years","R":"Overnight and less than 3 months","S":"More than 10 years","T":"3 months and less than 1 year","U":{"name":"Up to and including 1 year","parent":"A","desc":"Short-term."},"W":{"name":"Over 1 year","parent":"A","desc":"Long-term."},"X":{"name":"Unallocated by maturity","desc":"Claims for which the remaining maturity is unknown, or claims that cannot be classified by maturity (eg equities and participations)."},"Y":"Less than 1 year","Z":"1 year and over","0":"Technical Residual","V":{"name":"Over 3 months and up to 6 months","parent":"A","desc":"Over three months and up to six months. Market conventions: 6M (six months)."},"2":{"name":"Over 6 months","parent":"A","desc":"Over six months. Market conventions: 9M (nine months), 1Y (one year)."},"3":{"name":"One day","parent":"G","desc":"One day. Market conventions: O/N (overnight), T/N (tomorrow next), S/N (spot next)."},"4":{"name":"Over 1 day and less than 7 days","parent":"G","desc":"Over one day and up to seven days. Market conventions: S/W (spot week), 1W (one week)."},"5":{"name":"Unallocated maturity of seven days or less","parent":"G","desc":"Up to seven days."}}},"CL_L_INSTR":{"name":"Instrument","codes":{"A":"All instruments","D":{"name":"Debt securities","desc":"Negotiable instrument serving as evidence of a debt. Debt securities include the following instruments: bills, bonds, notes, negotiable certificates of deposit, commercial paper, debentures, asset-backed securities, money market instruments and similar instruments normally traded in financial market"},"E":"Risk-weighted assets","G":{"name":"Loans and deposits","desc":"Non-negotiable debt instruments that are created when a creditor lends funds directly to a debtor. In the LBS, no distinction is made between loans and deposits; they are treated as economically equivalent. Loans and deposits include the cash leg of securities repurchase agreements, working capital "},"I":"Derivatives and Other instruments","K":"Other instruments excluding derivatives","L":"Debt securities, long-term","M":"Debt securities, short-term","R":"Tier 1 capital","S":"Tier 2 capital","U":"Unallocated by instrument","V":{"name":"Derivatives","desc":"HIE_BIS_LBS_DISS_L_INSTR whose value depends on some underlying financial asset, commodity or predefined variable."},"Y":"Residual instrument","B":"Credit (loans & debt securities)","Z":"Debt securities, unallocated maturity","N":"Repo/Rev.Repo","X":"Equity instruments","W":"Allowances for credit losses","O":"Other instruments and unallocated","H":"Residual loans and deposits","J":"Residual other instruments","P":"Residual derivatives & other instruments","T":"Off-balance sheet trustee position"}},"CL_L_POSITION":{"name":"Position type","codes":{"B":{"name":"Local claims","desc":"Local claims are claims on counterparties located in the same country as the banking group\u2019s entity that books the position."},"C":{"name":"Total claims","desc":"A claim is a financial asset that has a counterpart liability. In the CBS, claims exclude financial derivatives. See also \"financial asset\"."},"D":{"name":"Cross-border claims","desc":"Cross-border claims are positions on counterparties located outside the country where the entity that books the position is located."},"F":{"name":"Total assets (financial and non-financial)","desc":"Sum of financial assets and non-financial assets."},"I":{"name":"International claims","desc":"Claim on a non-resident or denominated in a foreign currency. International claims comprise cross-border claims in any currency plus local claims of foreign affiliates denominated in non-local currencies."},"J":"Claims on banks with head offices outside host country","K":{"name":"Capital / equity","desc":"Includes common shares, preferred shares, retained earning"},"L":"Total liabilities","M":{"name":"Local liabilities","desc":"Local liabilities are liabilities on counterparties located in the same country as the banking group\u2019s entity that books the position."},"N":{"name":"Net positions","desc":"Claims minus liabilities"},"S":{"name":"Foreign Claims","desc":"Claim on residents of countries other than the country where the controlling parent is located, ie a claim of a domestic bank on non-residents of the reporting country. Foreign claims comprise local claims of the bank's offices abroad as well as crossborder claims of the bank's offices worldwide."},"W":{"name":"Guarantees extended","desc":"Contingent liabilities that arise from an irrevocable obligation to pay a third-party beneficiary when a client fails to perform certain contractual obligations. Guarantees extended include the notional value of credit protection sold."},"X":{"name":"Credit commitments","desc":"Promise by a creditor to lend up to a specified amount to a borrower on demand. In the CBS, credit commitments refer to commitments that are irrevocable unilaterally by the creditor, ie revocable only with the consent of the borrower."},"Z":{"name":"Other potential exposures","desc":"Sum of derivatives contracts, guarantees extended and credit commitments"},"U":"Residual position type","Y":"Residual balance sheet position"}},"CL_L_SECTOR":{"name":"Counterparty Sector","codes":{"A":"All sectors","B":{"name":"Banks, total","desc":"Business between banks. In the LBS, \"interbank\" typically refers to business between banking offices and thus includes inter-office business."},"C":{"name":"Non-financial corporations","desc":"Entity whose principal activity is the production of market goods or non-financial services. Non-financial corporations include the following entities: legally constituted corporations, branches of non-resident enterprises, quasi-corporations, notional resident units owning land, and resident non-pr"},"F":{"name":"Non-bank financial institutions","desc":"Financial institution, other than a bank, engaged primarily in the provision of financial services and activities auxiliary to financial intermediation, such as fund management. Non-bank financial corporations include the following entities: special purpose vehicles, hedge funds, securities brokers,"},"G":{"name":"General government","desc":"Sectoral classification that refers collectively to the central government, state government, local government and social security funds. General government excludes the central bank and publicly owned corporations."},"H":{"name":"Households and NPISHs","desc":"Group of persons who share the same living accommodation, who pool some or all of their income and wealth, and who consume certain types of goods and services collectively, mainly housing and food. In the LBS and CBS, the household sector refers collectively to households and non-profit institutions"},"I":{"name":"Banks, related offices","desc":"Entities that are part of the same banking group, ie that are within the perimeter of consolidation of the controlling parent institution. Includes the controlling parent institution, the head office of the bank (if different), and branches or subsidiaries that are part of the consolidated reporting"},"J":{"name":"Banks, unrelated banks","desc":"Entities that stay outside a banking group (ie do not have the same consolidated reporting entity)."},"K":"Unallocated non-financial sectors","L":"Unallocated non-financial private sector","M":{"name":"Banks, central banks","desc":"Central banks; currency boards or independent currency authorities that issue national currency that is fully backed by foreign exchange reserves; government-affiliated agencies that are separate institutional units and primarily perform central bank activities; and international organisations that "},"N":{"name":"Non-banks, total","desc":"Entity that is not a bank. Sectoral classification that refers collectively to non-bank financial corporations and the non-financial sector."},"O":{"name":"Official sector","desc":"Sectoral classification used in the CBS that refers collectively to general government, central banks and international organisations."},"P":{"name":"Non-financial sectors","desc":"Sectoral classification that refers collectively to non-financial corporations, general government and households."},"R":{"name":"Non-bank private sector","desc":"Sectoral classification used in CBS that refers collectively to non-bank financial corporations, non-financial corporations and households, ie the non-bank sector excluding general government."},"S":{"name":"Non-financial private sector","desc":"Sectoral classification that refers collectively to non-financial corporations and households, ie the non-financial sector excluding general government."},"U":"Unallocated by sector","Y":"Residual non-bank private sector","Z":"Residual non-financial private sector","X":"Residual by sector"}},"CL_ORG_VISIBILITY":{"name":"Visibility","codes":{"A":"CBs, ESRB and IMF","B":"CBs and ESRB","C":"CBs and IMF","D":"CBs only","E":"Public"}},"CL_STOCK_FLOW":{"name":"Stock, flow","codes":{"F":{"name":"FX and break adjusted change (BIS calculated)","desc":"Change in amount outstanding between two points in time after the impact of methodological changes and exchange rate movements has been eliminated. The adjusted change approximates the flow between two points in time. In the LBS, the adjusted change is calculated by first converting US dollar-equiva"},"S":{"name":"Amounts outstanding / Stocks","desc":"Value of an asset or liability at a point in time."},"R":"Revisions","B":{"name":"Break in stocks","desc":"Changes in assets and liabilities between opening and closing balance sheets that are due neither to transactions between institutional units nor to changes in value. (MFSM, 193)"},"G":{"name":"Annual growth (BIS calculated)","desc":"In the LBS and in the GLI, quarterly growth rates compounded over four quarters."}}},"CL_BSI_METHOD":{"name":"Balance sheet methodology code list","codes":{"A":{"name":"Financial statement or accounting balance sheet","desc":"This methodology follows accounting rules for the compilation of the balance sheet."},"A1":{"name":"Audited financial statement","parent":"A","desc":"This methodology follows accounting rules, generally applied to the audited annual financial statement. For high-frequency data (eg lower than annual), data may not be audited but follows the same methodology."},"A2":{"name":"Other financial statement","parent":"A","desc":"This methodology follows accounting rules but it is not aligned with the methodology underlying the compilation of the annual audited financial statements."},"M":"Monetary statistics or statistical balance sheet","M1":{"name":"Monetary presentation (gross) according to Monetary and Financial Statistics Manual and Compilation Guide","parent":"M"},"M2":{"name":"Harmonised Monetary Statistics of MFIs set out by the guidelines of the European Central Bank","parent":"M"},"M3":{"name":"Analytical Survey","parent":"M"},"_Z":"Not specified","B":{"name":"BIS-spliced","desc":"The spliced series mayfollow multiple methodologies as a result of the splicing performed by the BIS. The methodologies are detailed in the compilation attribute"}}},"CL_TRANSFORMATION":{"name":"Transformation codes","codes":{"GC5Y":"Compound growth rate, over 5 years","D1D1":"Differences, period on period, second order","FO1":"Contribution to growth rate, flow over stock, period on period","FO4":"Contribution to growth rate, flow over stock, over 4 periods","FO12":"Contribution to growth rate, flow over stock, over 12 periods","FO3":"Contribution to growth rate, flow over stock, over 3 periods","EPX":"Monthly index, backdated, PPP exchange rates used for weights","FO6":"Contribution to growth rate, flow over stock, over 6 periods","G3Y":"Growth rate, over 3 years","FO16":"Contribution to growth rate, flow over stock, over 16 periods","A1":"Average, period on period","A3":"3-period moving average","A4":"4-period moving average","A6":"6-period moving average","DY":"Difference, over 1 year","C4G":"Growth rate, period on period, over 4-period cumulated sum","R1":"Revisions, difference to last transmission period","A12":"12-period moving average","C12":"12-period cumulated sum","GYA3":"Growth rate, over 1 year, based on 3-period average","G10":"Growth rate, over 10 periods","GO12":"Contribution to growth rate, over 12 periods","C16":"16 period cumulated sum","G12":"Growth rate, over 12 periods","F1":"Growth rate, flow over stock, period on period","F3":"Growth rate, flow over stock, over 3 periods","G4Y":"Growth rate, over 4 years","F4":"Growth rate, flow over stock, over 4 periods","F6":"Growth rate, flow over stock over 6 periods","GC10Y":"Compound growth rate, over 10 years","GO1":"Contribution to growth rate, period on period","AW12":"Weighted average, over 12 periods","ERX":"Monthly index, backdated, fixed euro conversion rate used for weights","G1":"Growth rate, period on period","GO3":"Contribution to growth rate, over 3 periods","G3":"Growth rate, over 3 periods","G4":"Growth rate, over 4 periods","GO4":"Contribution to growth rate, over 4 periods","N":"Non transformed data","G6":"Growth rate, over 6 periods","GO6":"Contribution to growth rate, over 6 periods","C3":"3-period cumulated sum","C4":"4-period cumulated sum","C6":"6-period cumulated sum","FY":"Growth rate, flow over stock, over 1 year","_Z":"Not applicable","GYA12":"Growth rate, over 1 year, based on 12-period average","F12":"Growth rate, flow over stock over 12 periods","AS1999":"Average since 1999","GR":{"name":"Growth rate, over reference year","desc":"Attribute REF_YEAR_PRICE is mandatory and provides the reference year"},"D1":"Differences, period on period, first order","ACR":"Annual rate of change corrected for the effect of methodological changes where applicable","D4":"Difference period on 4 periods, first order","GOY":"Contribution to growth rate, over 1 year","GY":"Growth rate, over 1 year","LA":"Annual levels","CY":"Cumulated sum, over 1 year","ECX":"Monthly index, backdated, ECU (to 1989) and fixed euro conversion rate (from 1990) used for weights","B":"Adjusted for breaks"}},"CL_CURRENCY":{"name":"Currency of issuance or invoicing code list","codes":{"_T":"All currencies","_X":"Not specified","_Z":"Not applicable","ADF":"Andorran franc (1-1 peg to the French franc)","ADP":"Andorran peseta (1-1 peg to the Spanish peseta)","AED":"United Arab Emirates dirham","AFA":"Afghanistan afghani (old)","AFN":"Afghanistan, Afghanis","ALL":"Albanian lek","AMD":"Armenian dram","ANG":"Netherlands Antillean guilder","AOA":"Angolan kwanza","AON":"Angolan kwanza (old)","AOR":"Angolan kwanza readjustado (old)","ARS":"Argentine peso","ATS":"Austrian schilling","AUD":"Australian dollar","AWG":"Aruban florin/guilder","AZM":"Azerbaijanian manat (old)","AZN":"Azerbaijan, manats","BAM":"Bosnia-Hezergovinian convertible mark","BBD":"Barbados dollar","BDT":"Bangladesh taka","BEF":"Belgian franc","BEL":"Belgian franc (financial)","BGL":"Bulgarian lev (old)","BGN":"Bulgarian lev","BHD":"Bahraini dinar","BIF":"Burundi franc","BMD":"Bermudian dollar","BND":"Brunei dollar","BOB":"Bolivian boliviano","BRL":"Brazilian real","BSD":"Bahamas dollar","BTN":"Bhutan ngultrum","BWP":"Botswana pula","BYB":"Belarussian rouble (old)","BYR":"Belarus, Rubles","BZD":"Belize dollar","CAD":"Canadian dollar","CDF":"Congo franc (ex Zaire)","CHE":"WIR Euro","CHF":"Swiss franc","CHW":"WIR Franc","CLF":"Unidades de fomento","CLP":"Chilean peso","CNY":"Chinese yuan renminbi","COP":"Colombian peso","COU":"Unidad de Valor Real","CRC":"Costa Rican colon","CSD":"Serbian dinar (old)","CUP":"Cuban peso","CVE":"Cape Verde escudo","CYP":"Cypriot pound","CZK":"Czech koruna","DEM":"German mark","DJF":"Djibouti franc","DKK":"Danish krone","DOP":"Dominican peso","DZD":"Algerian dinar","E0":"Euro area changing composition vis-a-vis the EER-12 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB and US)","E1":"Euro area-18 countries vis-a-vis the EER-20 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, LT, HU, PL, RO, HR and CN)","E2":"Euro area-18 countries vis-a-vis the EER-19 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, LT, HU, PL, RO, and CN)","E3":"Euro area-18 countries vis-a-vis the EER-39 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, LT, HU, PL, RO, CN, DZ, AR, BR, CL, HR, IS, IN, ID, IL, MY, MX, MA, NZ, P","E4":"Euro area-18 countries vis-a-vis the EER-12 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB and US)","ECS":"Ecuador sucre (old)","EEK":"Estonian kroon","EGP":"Egyptian pound","ERN":"Erytrean nafka","ESP":"Spanish peseta","ETB":"Ethiopian birr","EUR":"Euro","FIM":"Finnish markka","FJD":"Fiji dollar","FKP":"Falkland Islands pound","FRF":"French franc","GBP":"UK pound sterling","GEL":"Georgian lari","GGP":"Guernsey, Pounds","GHC":"Ghanaian cedi (old)","GHS":"Ghana Cedi","GIP":"Gibraltar pound","GMD":"Gambian dalasi","GNF":"Guinea franc","GRD":"Greek drachma","GTQ":"Guatemalan quetzal","GWP":"Guinea-Bissau Peso","GYD":"Guyanan dollar","H1":"Euro area 18's currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, CY, EE, LV, MT, SK)","H2":"ECB EER-12 group of currencies and Euro area's (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, CY, EE, LV, MT, SK, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, ","H3":"ECB EER-20 group of currencies and Euro area's (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, ","H4":"ECB EER-40 group of currencies and Euro area's (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, ","H5":"ECB EER-21 group of currencies and Euro area's (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, ","H6":"ECB EER-12 group of currencies and Euro area's (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, ","H36":"European Commission IC-36 group of currencies (European Union 27 Member States, i.e. BE, DE, EE, GR, ES, FR, IE, IT, CY, LU, NL, MT, AT, PT, SI, SK, FI, BG, CZ, DK, LV, LT, HU, PL, RO, SE, GB, and US,","H37":"European Commission IC-37 group of currencies (European Union 28 Member States, i.e. BE, DE, EE, GR, ES, FR, IE, IT, CY, LU, NL, MT, AT, PT, SI, SK, FI, BG, CZ, DK, HR, LV, LT, HU, PL, RO, SE, GB, and","HKD":"Hong Kong dollar","HKQ":"Hong Kong dollar (old)","HNL":"Honduran lempira","HRK":"Croatian kuna","HTG":"Haitian gourde","HUF":"Hungarian forint","IDR":"Indonesian rupiah","IEP":"Irish pound","ILS":"Israeli shekel","IMP":"Isle of Man, Pounds","INR":"Indian rupee","IQD":"Iraqi dinar","IRR":"Iranian rial","ISK":"Iceland krona","ITL":"Italian lira","JEP":"Jersey, Pounds","JMD":"Jamaican dollar","JOD":"Jordanian dinar","JPY":"Japanese yen","KES":"Kenyan shilling","KGS":"Kyrgyzstan som","KHR":"Kampuchean real (Cambodian)","KMF":"Comoros franc","KPW":"Korean won (North)","KRW":"Korean won (Republic)","KWD":"Kuwait dinar","KYD":"Cayman Islands dollar","KZT":"Kazakstan tenge","LAK":"Lao kip","LBP":"Lebanese pound","LKR":"Sri Lanka rupee","LRD":"Liberian dollar","LSL":"Lesotho loti","LTL":"Lithuanian litas","LUF":"Luxembourg franc","LVL":"Latvian lats","LYD":"Libyan dinar","MAD":"Moroccan dirham","MDL":"Moldovian leu","MGA":"Madagascar, Ariary","MGF":"Malagasy franc","MKD":"Macedonian denar","MMK":"Myanmar kyat","MNT":"Mongolian tugrik","MOP":"Macau pataca","MRO":"Mauritanian ouguiya","MTL":"Maltese lira","MUR":"Mauritius rupee","MVR":"Maldive rufiyaa","MWK":"Malawi kwacha","MXN":"Mexican peso","MXP":"Mexican peso (old)","MXV":"Mexican Unidad de Inversion (UDI)","MYR":"Malaysian ringgit","MZM":"Mozambique metical (old)","MZN":"Mozambique, Meticais","NAD":"Namibian dollar","NGN":"Nigerian naira","NIO":"Nicaraguan cordoba","NLG":"Netherlands guilder","NOK":"Norwegian krone","NPR":"Nepaleese rupee","NZD":"New Zealand dollar","OMR":"Oman Sul rial","PAB":"Panama balboa","PEN":"Peru nuevo sol","PGK":"Papua New Guinea kina","PHP":"Philippine peso","PKR":"Pakistan rupee","PLN":"Polish zloty","PLZ":"Polish zloty (old)","PTE":"Portuguese escudo","PYG":"Paraguay guarani","QAR":"Qatari rial","ROL":"Romanian leu (old)","RON":"Romanian leu","RSD":"Serbian Dinar","RUB":"Russian rouble","RUR":"Russian ruble (old)","RWF":"Rwanda franc","SAR":"Saudi riyal","SBD":"Solomon Islands dollar","SCR":"Seychelles rupee","SDD":"Sudanese dinar (old)","SDG":"Sudan, Dinars","SDP":"First sudanese Pound","SEK":"Swedish krona","SGD":"Singapore dollar","SHP":"St. Helena pound","SIT":"Slovenian tolar","SKK":"Slovak koruna","SLL":"Sierra Leone leone","SOS":"Somali shilling","SPL":"Seborga, Luigini","SRD":"Suriname, Dollars","SRG":"Suriname guilder (old)","STD":"Sao Tome and Principe dobra","SVC":"El Salvador colon","SYP":"Syrian pound","SZL":"Swaziland lilangeni","THB":"Thai baht","TJR":"Tajikistan rouble (old)","TJS":"Tajikistan, Somoni","TMM":"Turkmenistan manat","TND":"Tunisian dinar","TOP":"Tongan paanga","TPE":"East Timor escudo (old)","TRL":"Turkish lira (old)","TRY":"Turkish lira","TTD":"Trinidad and Tobago dollar","TVD":"Tuvalu Dollars","TWD":"New Taiwan dollar","TZS":"Tanzania shilling","UAH":"Ukraine hryvnia","UGX":"Uganda Shilling","USD":"US dollar","UYI":"Uruguay Peso en Unidades Indexadas","UYU":"Uruguayan peso","UZS":"Uzbekistan sum","VEB":"Venezuela bolivar (old)","VEF":"Venezuelan bolivar fuerte","VND":"Vietnamese dong","VUV":"Vanuatu vatu","WST":"Samoan tala","X1":"All currencies except national currency","X2":"All currencies except: USD","X3":"All currencies except EUR","X4":"All currencies except: EUR, USD","X5":"All currencies except: EUR, JPY, USD","X6":"All currencies except: EUR, CHF, GBP, JPY, USD","X7":"All currencies except: EUR, USD, JPY, GBP, CHF, domestic currency","XAF":"CFA franc / BEAC","XAG":"Silver","XAU":"Gold","XBA":"European composite unit","XBB":"European Monetary unit EC-6","XBC":"European Unit of Account 9(E.U.A.-9)","XBD":"European Unit of Account 17(E.U.A.-17)","XCD":"Eastern Caribbean dollar","XDB":"Currencies included in the SDR basket, gold and SDRs","XDC":"Domestic currency (incl. conversion to current currency made using a fixed parity)","XDM":"Domestic currency (incl. conversion to current currency made using market exchange rate)","XDN":"Domestic currency (currency previously used by a country before joining a Monetary Union)","XDO":"Other currencies not included in the SDR basket, exc. gold and SDRs","XDR":"Special Drawing Rights (S.D.R.)","XEU":"European Currency Unit (E.C.U.)","XFO":"Gold-Franc","XFU":"UIC-Franc","XGO":"Gold fine troy ounces","XNC":"Euro area non-participating foreign currency","XOF":"CFA franc / BCEAO","XPC":"Euro area participating foreign currency","XPD":"Palladium Ounces","XPF":"Pacific franc","XPT":"Platinum","XSU":"Sucre","XTS":"Codes specifically reserved for testing purposes","XUA":"ADB Unit of Account","XXX":"Transactions where no currency is involved","YER":"Yemeni rial","YUM":"Yugoslav dinar (old)","ZAR":"South African rand","ZMK":"Zambian kwacha","ZWD":"Zimbabwe dollar","ZWL":"Fourth Zimbabwe dollar","ZWN":"Zimbabwe dollars (old)","ZWR":"Third Zimbabwe dollar","E5":"Euro area-19 countries vis-a-vis the EER-19 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, HU, PL, RO, HR and CN)","E6":"Euro area-19 countries vis-a-vis the EER-18 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, HU, PL, RO, and CN)","E7":"Euro area-19 countries vis-a-vis the EER-38 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, HU, PL, RO, CN, DZ, AR, BR, CL, HR, IS, IN, ID, IL, MY, MX, MA, NZ, PH, R","E8":"Euro area-19 countries vis-a-vis the EER-12 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US)","H7":"Euro area 19's currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, CY, EE,LT, LV, MT, SK)","H8":"ECB EER-12 group of currencies & Euro area (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, CY, EE, LT, US)","H9":"ECB EER-18 group of currencies and Euro area (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, LV","H10":"ECB EER-38 group of currencies and Euro area (latest composition) currencies (FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,AU,CA,CN,DK,HK,JP,NO,SG,KR,SE,CH,GB,US,CY,CZ,EE,HU,LV,LT,MT,PL,SK,BG,RO,NZ,DZ,AR,BR","H11":"ECB EER-19 group of currencies and Euro area (latest composition) currencies (FR, BE, LU, NL, DE, IT, IE, PT, ES, FI, AT, GR, SI, AU, CA, CN, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, CY, CZ, EE, HU, LV"}},"CL_ORGANISATION":{"name":"Compiling organisation code list","codes":{"1A0":"International organisations","1B0":"UN organisations","1C0":"IMF (International Monetary Fund)","1D0":"World Trade Organisation","1E0":"International Bank for Reconstruction and Development","1F0":"International Development Association","1G0":"ICSID (International Centre for Settlement of Investment Disputes)","1H0":"UNESCO (United Nations Educational, Scientific and Cultural Organisation)","1J0":"FAO (Food and Agriculture Organisation)","1K0":"WHO (World Health Organisation)","1L0":"IFAD (International Fund for Agricultural Development)","1M0":"IFC (International Finance Corporation)","1N0":"MIGA (Multilateral Investment Guarantee Agency)","1O0":"UNICEF (United Nations Children Fund)","1P0":"UNHCR (United Nations High Commissioner for Refugees)","1Q0":"UNRWA (United Nations Relief and Works Agency for Palestine)","1R0":"IAEA (International Atomic Energy Agency)","1S0":"ILO (International Labour Organisation)","1T0":"ITU (International Telecommunication Union)","1U0":"Rest of UN Organisations n.i.e.","1V0":"Universal Postal Union","1X0":"United Nations Office on Drugs and Crimes(UNODC)","1Y0":"The United Nations World Food Programme","4A0":"All the European Union Institutions excluding the ECB and ESM deprecated","4C0":"EIB (European Investment Bank)","4D0":"European Commission (including Eurostat)","4D1":"Statistical Office of the European Commission (Eurostat)","4E0":"EDF (European Development Fund)","4F0":"ECB (European Central Bank)","4G0":"EIF (European Investment Fund)","4H0":"European Community of Steel and Coal deprecated","4J0":"Other EC Institutions, Organs and Organisms covered by General budget deprecated","4J10":"European Parliament","4J20":"Council of the European Union","4J30":"Court of Justice","4J40":"Court of Auditors","4J50":"European Council","4J60":"Economic and Social Committee","4J70":"Committee of Regions","4J80":"Other European Community Institutions, Organs and Organisms deprecated","4J810":"Agency for the Cooperation of Energy Regulators","4J8100":"European Centre for Disease Prevention and Control","4J8110":"European Centre for the Development of Vocational Training","4J8120":"European Chemicals Agency","4J8130":"European Data Protection Supervisor","4J8140":"European Defence Agency","4J8150":"European Environment Agency","4J8160":"European External Action Service","4J8170":"European Fisheries Control Agency","4J8180":"European Food Safety Authority","4J8190":"European Foundation for the Improvement of Living and Working Conditions","4J820":"Body of European Regulators for Electronic Communications","4J8200":"European GNSS Agency","4J8210":"European Institute for Gender Equality","4J8220":"European Institute of Innovation and Technology","4J8230":"European Maritime Safety Agency","4J8240":"European Medicines Agency","4J8250":"European Monitoring Centre for Drugs and Drug Addiction","4J8260":"European Network and Information Security Agency","4J8270":"European Ombudsman","4J8280":"European Personnel Selection Office","4J8290":"European Police College","4J830":"Community Plant Variety Office","4J8300":"European Police Office","4J8310":"European Public Prosecutor's Office","4J8320":"European Railway Agency","4J8330":"European School of Administration","4J8340":"European Training Foundation","4J8350":"European Union Agency for Fundamental Rights","4J8360":"European Union Institute for Security Studies","4J8370":"European Union Intellectual Property Office","4J8380":"European Union Satellite Centre","4J8390":"Publications Office of the European Union","4J840":"Computer Emergency Response Team","4J8400":"The European Union\u2019s Judicial Cooperation Unit","4J8410":"Translation Centre for the Bodies of the European Union","4J8420":"ATHENA Mechanism","4J850":"European Agency for Safety and Health at Work","4J860":"European Agency for the Management of Operational Cooperation at the External Borders","4J870":"European Agency for the operational management of large-scale IT systems in the area of freedom, security and justice","4J880":"European Asylum Support Office","4J890":"European Aviation Safety Agency","4M0":"SRB (Single Resolution Board)","4S0":"ESM (European Stability Mechanism)","4T0":"Joint Committee of the European Supervisory Authorities (ESAs)","4T10":"EBA (European Banking Authority)","4T20":"ESMA (European Securities and Markets Authority)","4T30":"EIOPA (European Insurance and Occupational Pensions Authority)","4U10":"Fusion for Energy","4U20":"EURATOM Supply Agency","4W0":"EFSF (European Financial Stability Facility)","4Y0":"All the European Union Institutions including the ECB and ESM deprecated","5B0":"BIS (Bank for International Settlements)","5C0":"IADB (Inter-American Development Bank)","5D0":"AfDB (African Development Bank)","5E0":"AsDB (Asian Development Bank)","5F0":"EBRD (European Bank for Reconstruction and Development)","5G0":"IIC (Inter-American Investment Corporation)","5H0":"NIB (Nordic Investment Bank)","5I0":"ECCB (Eastern Caribbean Central Bank)","5J0":"IBEC (International Bank for Economic Co-operation)","5K0":"IIB (International Investment Bank)","5L0":"CDB (Caribbean Development Bank)","5M0":"AMF (Arab Monetary Fund)","5N0":"BADEA (Banque arabe pour le d\u00e9veloppement \u00e9conomique en Afrique)","5O0":"BCEAO (Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest)","5P0":"CASDB (Central African States Development Bank)","5Q0":"African Development Fund","5R0":"Asian Development Fund","5S0":"Fonds sp\u00e9cial unifi\u00e9 de d\u00e9veloppement","5T0":"CABEI (Central American Bank for Economic Integration)","5U0":"ADC (Andean Development Corporation)","5W0":"BEAC (Banque des Etats de l`Afrique Centrale)","5X0":"CEMAC (Communaut\u00e9 \u00c9conomique et Mon\u00e9taire de l\u2019Afrique Centrale)","5Y0":"ECCU (Eastern Caribbean Currency Union)","5Z0":"Other International Financial Organisations n.i.e.","5Z10":"Africa Finance Corporation","5Z100":"International Civil Aviation Organization","5Z110":"International Cocoa Organization","5Z120":"International Coffee Organization","5Z130":"International Copper Study Group","5Z140":"International Cotton Advisory Committee","5Z150":"International Grains Council","5Z160":"International Jute Study Group","5Z170":"International Lead and Zinc Study Group","5Z180":"International Maritime Organization","5Z190":"International Maritime Satellite Organization","5Z20":"African Development Bank Group","5Z200":"International Olive Oil Council","5Z210":"International Rubber Study Group","5Z220":"International Sugar Organization","5Z230":"Latin American and the Caribbean Economic System","5Z240":"Latin American Energy Organization","5Z250":"Latin American Integration Association","5Z260":"League of Arab States","5Z270":"Organisation of Eastern Caribbean States","5Z280":"Organization of American States","5Z290":"Organization of Arab Petroleum Exporting Countries","5Z30":"Arab Fund for Economic and Social Development","5z30":"Arab Fund for Economic and Social Development (deprecated)","5Z300":"Organization of Central American States","5Z310":"Organization of the Petroleum Exporting Countries","5Z330":"South Asian Association for Regional Cooperation","5Z340":"United Nations Conference on Trade and Development","5Z350":"West African Economic Community","5Z360":"West African Health Organisation","5Z370":"West African Monetary Agency","5Z380":"West African Monetary Institute","5Z390":"World Council of Churches","5Z40":"Asian Clearing Union","5Z400":"World Intellectual Property Organization","5Z410":"World Meteorological Organization","5Z420":"World Tourism Organization","5Z50":"Colombo Plan","5Z60":"Economic Community of West African States","5Z70":"European Free Trade Association","5Z80":"Fusion for Energy deprecated","5Z90":"Intergovernmental Council of Copper Exporting Countries","6A0":"Other International Organisations (non-financial institutions)","6A10":"African Union","6A20":"Association of Southeast Asian Nations","6A30":"Caribbean Community and Common Market","6A40":"Central American Common Market","6A50":"East African Development Bank","6A60":"ECOWAS Bank for Investment and Development","6A70":"Latin American Association of Development Financing Institutions","6A80":"OPEC Fund for International Development","6B0":"NATO (North Atlantic Treaty Organisation)","6C0":"Council of Europe","6D0":"ICRC (International Committee of the Red Cross)","6E0":"ESA (European Space Agency)","6F0":"EPO (European Patent Office)","6G0":"EUROCONTROL (European Organisation for the Safety of Air Navigation)","6H0":"EUTELSAT (European Telecommunications Satellite Organisation)","6I0":"EMBL (European Molecular Biology Laboratory)","6J0":"INTELSAT (International Telecommunications Satellite Organisation)","6K0":"EBU/UER (European Broadcasting Union/Union europ\u00e9enne de radio-t\u00e9l\u00e9vision)","6L0":"EUMETSAT (European Organisation for the Exploitation of Meteorological Satellites)","6M0":"ESO (European Southern Observatory)","6N0":"ECMWF (European Centre for Medium-Range Weather Forecasts)","6O0":"OECD (Organisation for Economic Co-operation and Development)","6P0":"CERN (European Organisation for Nuclear Research)","6Q0":"IOM (International Organisation for Migration)","6Z0":"Other International Non-Financial Organisations n.i.e.","6Z10":"The Global Fund to Fight AIDS, Tuberculosis and Malaria","6Z20":"International Centre for Migration Policy Development","7A0":"WAEMU (West African Economic and Monetary Union)","7B0":"IDB (Islamic Development Bank)","7C0":"EDB (Eurasian Development Bank )","7D0":"Paris Club Creditor Institutions","7E0":"CEB (Council of Europe Development Bank)","7F0":"International Union of Credit and Investment Insurers","7G0":"Black Sea Trade and Development Banks","7H0":"AFREXIMBANK (African Export-Import Bank)","7I0":"BLADEX (Banco Latino Americano De Comercio Exterior)","7J0":"FLAR (Fondo Latino Americano de Reservas)","7K0":"Fonds Belgo-Congolais d'Amortissement et de Gestion","7L0":"IFFIm (International finance Facility for Immunisation)","7M0":"EUROFIMA (European Company for the Financing of Railroad Rolling Stock)","7N0":"Development Bank of Latin America (Banco de Desarrollo de America Latina)","7O0":"The Eastern and Southern African Trade and Development Bank","9A0":"International Organisations excl. European Community Institutions (4Y)","AD2":"Andorra Finance institute","AE_DU6":"Dubai Financial Services Authority","AE1":"Central Statistical Organization, part of the Ministry of Economy and Planning (United Arab Emirates)","AE2":"Central Bank of the United Arab Emirates","AE4":"Ministry of Finance and Industry (United Arab Emirates)","AF2":"Da Afghanistan Bank","AF4":"Ministry of Finance (Afghanistan, Islamic State of)","AG2":"Eastern Caribbean Central Bank (ECCB) (Antigua and Barbuda)","AG4":"Ministry of Finance (Antigua and Barbuda)","AI1":"Central Statistical Office (Anguilla)","AI4":"Ministry of Finance (Anguilla)","AI99":"Other competent National Authority (Anguilla)","AL1":"Institute of Statistics (Albania)","AL2":"Bank of Albania","AL4":"Minist\u00e8re des Finances (Albania)","AM1":"National Statistics Service (Armenia)","AM2":"Central Bank of Armenia","AM4":"Ministry of Finance and Economy (Armenia)","AM99":"Other competent National Authority (Armenia, Republic of)","AN1":"Central Bureau of Statistics (Netherlands Antilles)","AN2":"Bank of the Netherlands Antilles","AN99":"Other competent National Authority (Netherlands Antilles)","AO1":"National Institute of Statistics (Angola)","AO2":"Banco Nacional de Angola","AO4":"Minist\u00e9rio das Finan\u00e7as (Angola)","AR1":"Instituto Nacional de Estadistica y Censos (Argentina)","AR2":"Banco Central de la Republica Argentina","AR4":"Ministerio de Econom\u00eda (Argentina)","AR99":"Other competent National Authority (Argentina)","AT1":"Statistik \u00d6sterreich (Austria)","AT2":"Oesterreichische Nationalbank (Austria)","AT6":"FMA (Austria Financial Market Authority)","AT99":"Other competent National Authority (Austria)","AU1":"Australian Bureau of Statistics","AU2":"Reserve Bank of Australia","AU5":"Department of the Treasury (Australia)","AU99":"Other competent National Authority (Australia)","AW1":"Central Bureau of Statistics (Aruba)","AW2":"Centrale Bank van Aruba","AW99":"Other competent National Authority (Aruba)","AZ1":"State Statistical Committee of the Republic of Azerbaijan","AZ2":"National Bank of Azerbaijan","AZ4":"Ministry of Finance (Azerbaijan)","AZ99":"Other competent National Authority (Azerbaijan, Republic of)","B22":"EU 15 central banks","B32":"EU 25 central banks","B42":"EU 27 central banks","B52":"EU 28 central banks","B62":"EU27 central banks (fixed composition) as of 31 January 2020 (brexit)","BA1":"Institute of Statistics (Bosnia and Herzegovina)","BA2":"Central Bank of Bosnia and Herzegovina","BA4":"Bosnia and Herzegovina Ministry of Finance and Treasury","BA99":"Other competent National Authority (Bosnia and Herzegovina)","BB1":"Barbados Statistical Service","BB2":"Central Bank of Barbados","BB4":"Ministry of Finance and Economic Affairs (Barbados)","BB99":"Other competent National Authority (Barbados)","BD1":"Bangladesh Bureau of Statistics","BD2":"Bangladesh Bank","BD4":"Ministry of Finance (Bangladesh)","BE1":"Institut National de Statistiques de Belgique","BE2":"Banque Nationale de Belgique (Belgium)","BE3":"Federal Public Service Finance (Belgium)","BE40":"Federal Planning Bureau","BE9":"Bureau van Dijk (Belgium)","BE99":"Other competent National Authority (Belgium)","BF2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (Burkina Faso)","BF4":"Ministere de l'Economie et des Finances (Burkina Faso)","BG1":"National Statistical Institute of Bulgaria","BG2":"Bulgarian National Bank","BG3":"Prime Minister's Office (Bulgaria)","BG4":"Ministry of Finance (Bulgaria)","BG99":"Other competent National Authority (Bulgaria)","BH1":"Directorate of Statistics (Bahrain)","BH2":"Bahrain Monetary Authority","BH4":"Ministry of Finance and National Economy (Bahrain)","BH99":"Other competent National Authority (Bahrain, Kingdom of)","BI2":"Banque de la Republique du Burundi","BI3":"Minist\u00e8re du Plan (Burundi)","BI4":"Minist\u00e8re des finances (Burundi)","BJ1":"Institut National de la Statistique et de l\u2019Analyse Economique (Benin)","BJ2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (Benin)","BJ4":"Minist\u00e8re des Finances (Benin)","BJ99":"Other competent National Authority (Benin)","BM1":"Bermuda Government - Department of Statistics","BM2":"Bermuda Monetary Authority","BM99":"Other competent National Authority (Bermuda)","BN1":"Department of Statistics (Brunei Darussalam)","BN2":"Brunei Currency and Monetary Board (BCMB)","BN3":"Department of Economic Planning and Development (DEPD) (Brunei Darussalam)","BN4":"Ministry of Finance (Brunei Darussalam)","BN99":"Other competent National Authority (Brunei Darussalam)","BO1":"Instituto Nacional de Estadistica (Bolivia)","BO2":"Banco Central de Bolivia","BO3":"Secretar\u00eda Nacional de Hacienda (Bolivia)","BO4":"Ministerio de Hacienda (Bolivia)","BO99":"Other competent National Authority (Bolivia)","BR1":"Brazilian Institute of Statistics and Geography (IBGE) (Brazil)","BR2":"Banco Central do Brasil","BR3":"Ministry of Industry, Commerce and Tourism, Secretariat of Foreign Commerce (SECEX) (Brazil)","BR4":"Ministerio da Fazenda (Brazil)","BS1":"Department of Statistics (Bahamas)","BS2":"The Central Bank of the Bahamas","BS4":"Ministry of Finance (Bahamas)","BS99":"Other competent National Authority (Bahamas, The)","BT1":"Central Statistical Office (Bhutan)","BT2":"Royal Monetary Authority of Bhutan","BT4":"Ministry of Finance (Bhutan)","BW1":"Central Statistics Office (Botswana)","BW2":"Bank of Botswana","BW3":"Department of Customs and Excise (Botswana)","BW4":"Ministry of Finance and Development Planning (Botswana)","BY1":"Ministry of Statistics and Analysis of the Republic of Belarus","BY2":"National Bank of Belarus","BY4":"Ministry of Finance of the Republic of Belarus","BY99":"Other competent National Authority (Belarus)","BZ1":"Central Statistical Office (Belize)","BZ2":"Central Bank of Belize","BZ3":"Ministry of Foreign Affairs (Belize)","BZ4":"Ministry of Finance (Belize)","BZ99":"Other competent National Authority (Belize)","C992":"Central banks of the new EU Member States 2004 (CY,CZ,EE,HU,LV,LT,MT,PL,SK,SI","CA1":"Statistics Canada","CA2":"Bank of Canada","CA99":"Other competent National Authority (Canada)","CD1":"Institute National de la Statistique (Congo, Dem. Rep. of)","CD2":"Banque Centrale du Congo (Congo, Dem. Rep. of)","CD4":"Ministry of Finance and Budget (Congo, Dem. Rep. of)","CD5":"National Office of Research and Development (Congo, Dem. Rep. of)","CD99":"Other competent National Authority (Congo, Democratic Republic of)","CF2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Central African Republic)","CF3":"Presidence de la Republique (Central African Republic)","CF4":"Ministere des Finances, du Plan et de la Cooperation Internationale (Central African Republic)","CG1":"Centre National de la Statistique et des Edudes Economiques (CNSEE) (Congo, Rep of)","CG2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Congo, Rep. of)","CG4":"Minist\u00e8re de l'\u00e9conomie, des finances et du budget (Congo, Rep of)","CG99":"Other competent National Authority (Congo, Republic of)","CH1":"Swiss Federal Statistical Office","CH2":"Swiss National Bank","CH3":"Direction gen\u00e9rale des douanes (Switzerland)","CH4":"Swiss Federal Finance Administration (Switzerland)","CH99":"Other competent National Authority (Switzerland)","CI2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (C\u00f4te d'Ivoire)","CI4":"Minist\u00e8re de l'Economie et des Finances (C\u00f4te d'Ivoire)","CK1":"Cook Islands Statistics Office","CK4":"Cook Islands Ministry of Finance","CL2":"Banco Central de Chile","CL4":"Ministerio de Hacienda (Chile)","CM2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Cameroon)","CM3":"Minist\u00e8re du Plan et de l'Amenagement du Territoire (Cameroon)","CM4":"Minist\u00e8re de l'\u00e9conomie et des finances (Cameroon)","CN1":"National Bureau of Statistics (China, P.R.: Mainland)","CN2":"The People's Bank of China","CN3":"State Administration of Foreign Exchange (China, P.R.: Mainland)","CN4":"Ministry of Finance (China, P.R.: Mainland)","CN5":"General Administration of Customs (China, P.R.: Mainland)","CN99":"Other competent National Authority (China, P.R.: Mainland)","CO1":"Departamento Administrativo Nacional de Estad\u00edsticas (Colombia)","CO2":"Banco de la Rep\u00fablica (Colombia)","CO4":"Ministerio de Hacienda y Cr\u00e9dito P\u00fablico (Colombia)","CO99":"Other competent National Authority (Colombia)","CR1":"Statistical office of Costa Rica","CR2":"Banco Central de Costa Rica","CR4":"Ministerio de Hacienda (Costa Rica)","CS1":"Federal Statistical Office (Serbia and Montenegro)","CS2":"National Bank of Serbia","CS4":"Federal Ministry of Finance (Serbia and Montenegro)","CS99":"Other competent National Authority (Serbia and Montenegro)","CU1":"Oficina National de Estadisticas (Cuba)","CU2":"Banco Central de Cuba","CU99":"Other competent National Authority (Cuba)","CV1":"Instituto Nacional de Estatistica (Cape Verde)","CV2":"Banco de Cabo Verde (Cape Verde)","CV3":"Minist\u00e8re de la coordination \u00e9conomique (Cape Verde)","CV4":"Ministerio das Financas (Cape Verde)","CV99":"Other competent National Authority (Cape Verde)","CW1":"Central Bureau of Statistics (Curacao)","CW2":"Central Bank of Curacao and Sint Maarten","CW99":"Other competent National Authority (Curacao)","CY1":"Department of Statistics and Research (Ministry of Finance) (Cyprus)","CY2":"Central Bank of Cyprus","CY4":"Ministry of Finance (Cyprus)","CY99":"Other competent National Authority (Cyprus)","CZ1":"Czech Statistical Office","CZ2":"Czech National Bank","CZ3":"Ministry of Transport and Communications/Transport Policy (Czech Republic)","CZ4":"Ministry of Finance of the Czech Republic","CZ99":"Other competent National Authority (Czech Republic)","DE1":"Statistisches Bundesamt (Germany)","DE2":"Deutsche Bundesbank (Germany)","DE3":"Kraftfahrt-Bundesamt (Germany)","DE4":"Bundesministerium der Finanzen (Germany)","DE6":"BAFIN (Bundesanstalt fuer Finanzdienstleistungsaufsicht)","DE8":"IFO Institut f\u00fcr Wirtschaftsforschung (Germany)","DE9":"Zentrum fur Europaische Wirtschaftsforschnung (ZEW, Germany)","DE99":"Other competent National Authority (Germany)","DJ1":"Direction Nationale de la Statistique (National Department of Statistics) (Djibouti)","DJ2":"Banque Nationale de Djibouti","DJ3":"Tr\u00e9sor National (Djibouti)","DJ4":"Ministere de l'Economie et des Finances (Djibouti)","DK1":"Danmarks Statistik (Denmark)","DK2":"Danmarks Nationalbank (Denmark)","DK98":"Danish Civil Aviation Administration","DK99":"Other competent National Authority (Denmark)","DM1":"Central Statistical Office (Dominica)","DM2":"Eastern Caribbean Central Bank (ECCB) (Dominica)","DM4":"Ministry of Finance (Dominica)","DM99":"Other competent National Authority (Dominica)","DO2":"Banco Central de la Rep\u00fablica Dominicana","DZ1":"Office National des Statistiques (Algeria)","DZ2":"Banque d\u2019Alg\u00e9rie","DZ4":"Minist\u00e8re des Finances (Algeria)","DZ99":"Other competent National Authority (Algeria)","EC1":"Instituto Nacional de Estadistica y Censos (Ecuador)","EC2":"Banco Central del Ecuador","EC4":"Ministerio de Finanzas y Cr\u00e9dito P\u00fablico (Ecuador)","EC99":"Other competent National Authority (Ecuador)","EE1":"Estonia, State Statistical Office","EE2":"Bank of Estonia","EE4":"Ministry of Finance (Estonia)","EE99":"Other competent National Authority (Estonia)","EG1":"Central Agency for Public Mobilization and Stats. (Egypt)","EG2":"Central Bank of Egypt","EG4":"Ministry of Finance (Egypt)","EG99":"Other competent National Authority (Egypt)","ER2":"Bank of Eritrea","ER4":"Ministry of Finance (Eritrea)","ES1":"Instituto Nacional de Estad\u00edstica (Spain)","ES2":"Banco de Espana (Spain)","ES3":"Departamento de Aduanas (Spain)","ES4":"Ministerio de Econom\u00eda y Hacienda (Spain)","ES5":"Ministerio de Industria, Tourismo y Comerco (Spain)","ES97":"Puertos del Estado/Portel Spain","ES98":"Ministerio de Fomento - AENA","ES99":"Other competent National Authority (Spain)","ET2":"National Bank of Ethiopia","ET3":"Customs and Excise Administration (Ethiopia)","ET4":"Ministry of Finance (Ethiopia)","FI1":"Statistics Finland (Finland)","FI2":"Bank of Finland (Finland)","FI3":"National Board of Customs (Finland)","FI4":"Ministry of Finance ((Finland)","FI97":"Finnish Maritime Administration","FI98":"Finavia(Civil Aviation Administration)","FI99":"Other competent National Authority (Finland)","FJ1":"Bureau of Statistics (Fiji)","FJ2":"Reserve Bank of Fiji","FJ4":"Ministry of Finance and National Planning (Fiji)","FJ99":"Other competent National Authority (Fiji)","FM1":"Office of Planning and Statistics (Micronesia, Federated States of)","FM2":"Federal States of Micronesia Banking Board (Micronesia, Federated States of)","FM99":"Other competent National Authority (Micronesia, Federated States of)","FR1":"Institut National de la Statistique et des Etudes Economiques - INSEE (France)","FR2":"Banque de France (France)","FR3":"Ministere de l Equipement, des Transports et du Logement (France)","FR4":"Minist\u00e8re de l'Economie et des Finance (France)","FR5":"Direction generale des douanes (France)","FR6":"National Council of Credit (France)","FR97":"DTMPL France","FR98":"DGAC(Direction General de l`Aviation Civil)","FR99":"Other competent National Authority (France)","GA2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Gabon)","GA3":"Ministere du Plan (Gabon)","GA4":"Ministry of Economy, Finance and Privatization (Gabon)","GA5":"Tr\u00e9sorier-Payeur G\u00e9n\u00e9ral du Gabon","GB1":"Office for National Statistics (United Kingdom)","GB2":"Bank of England (United Kingdom)","GB3":"Department of Environment, Transport and the Regions (United Kingdom)","GB4":"Department of Trade and Industry (United Kingdom)","GB9":"NTC Economics (United Kingdom)","GB98":"CAA (Civil Aviation Authority)","GB99":"Other competent National Authority (United Kingdom)","GD2":"Eastern Caribbean Central Bank (ECCB) (Grenada)","GD4":"Ministry of Finance (Grenada)","GE1":"State Department for Statistics of Georgia","GE2":"National Bank of Georgia","GE4":"Ministry of Finance (Georgia)","GE99":"Other competent National Authority (Georgia)","GF1":"Institut National de la Statistique et des Etudes Economiques - INSEE - Service regional (Guiana, French)","GF99":"Other competent National Authority (Guiana, French)","GG6":"Financial Services Commission, Guernsey (GG)","GH1":"Ghana Statistical Service","GH2":"Bank of Ghana","GH4":"Ministry of Finance (Ghana)","GH99":"Other competent National Authority (Ghana)","GM1":"Central Statistics Division (Gambia)","GM2":"Central Bank of the Gambia","GM4":"Ministry of Finance and Economic Affairs (Gambia)","GN1":"Service de la Statistique generale et de la Mecanographie (Guinea)","GN2":"Banque Centrale de la Republique de Guinee","GN4":"Ministere de l'Economie et des Finances (Guinea)","GN99":"Other competent National Authority (Guinea)","GP1":"Institut National de la Statistique et des Etudes Economiques - INSEE -Service regional (Guadeloupe)","GP99":"Other competent National Authority (Guadeloupe)","GQ2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Equatorial Guinea)","GQ4":"Ministerio de Econom\u00eda y Hacienda (Equatorial Guinea)","GR1":"National Statistical Service of Greece (Greece)","GR2":"Bank of Greece (Greece)","GR4":"Ministry of Economy and Finance (Greece)","GR98":"Civil Aviation Authority","GR99":"Other competent National Authority (Greece)","GT1":"Instituto Nacional de Estadistica (Guatemala)","GT2":"Banco de Guatemala","GT4":"Ministerio de Finanzas P\u00fablicas (Guatemala)","GT99":"Other competent National Authority (Guatemala)","GU1":"Guam Bureau of Statistics","GW2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (Guinea-Bissau)","GW4":"Ministere de l'Economie et des Finances (Guinea-Bissau)","GY1":"Statistical Bureau / Ministry of Planning (Guyana)","GY2":"Bank of Guyana","GY4":"Ministry of Finance (Guyana)","GY99":"Other competent National Authority (Guyana)","HK1":"Census and Statistics Department (China, P.R.: Hong Kong)","HK2":"Hong Kong Monetary Authority","HK4":"Financial Services and the Treasury Bureau (Treasury) (China, P.R.: Hong Kong)","HK99":"Other competent National Authority (Hong Kong)","HN1":"Direccion General de Censos y Estadisticas (Honduras)","HN2":"Banco Central de Honduras","HN4":"Ministerio de Hacienda y Cr\u00e9dito P\u00fablico (Honduras)","HN99":"Other competent National Authority (Honduras)","HR1":"Central Bureau of Statistics (Croatia)","HR2":"Croatian National Bank","HR4":"Ministry of Finance (Croatia)","HR99":"Other competent National Authority (Croatia)","HT1":"Institut Haitien de Statistique et d' Informatique (Haiti)","HT2":"Banque de la Republique d'Haiti","HT4":"Ministere de l'Economie et des Finances (Haiti)","HT99":"Other competent National Authority (Haiti)","HU1":"Hungarian Central Statistical Office","HU2":"National Bank of Hungary","HU4":"Ministry of Finance (Hungary)","HU99":"Other competent National Authority (Hungary)","I22":"Euro area 12 central banks","I32":"Euro area 13 central banks","I42":"Euro area 15 central banks","I52":"Euro area 16 central banks","I62":"Euro area 17 central banks","I72":"Euro area 18 central banks","I82":"Euro area 19 central banks","ID1":"BPS-Statistics Indonesia","ID2":"Bank Indonesia","ID4":"Ministry of Finance (Indonesia)","ID99":"Other competent National Authority (Indonesia)","IE1":"Central Statistical Office (Ireland)","IE2":"Central Bank of Ireland (Ireland)","IE3":"The Office of the Revenue Commissioners (Ireland)","IE4":"Department of Finance (Ireland)","IE99":"Other competent National Authority (Ireland)","IL1":"Central Bureau of Statistics (Israel)","IL2":"Bank of Israel","IL99":"Other competent National Authority (Israel)","IM6":"Financial Supervision Commission, Isle of Man (IM)","IN1":"Ministry of Statistics and Programme Implementation, CSO (India)","IN2":"Reserve Bank of India","IN4":"Ministry of Finance (India)","IN99":"Other competent National Authority (India)","IQ2":"Central Bank of Iraq","IQ4":"Ministry of Finance (Iraq)","IR2":"The Central Bank of the Islamic Republic of Iran","IS1":"Statistics Iceland","IS2":"Central Bank of Iceland","IS98":"Civil Aviation Administration","IS99":"Other competent National Authority (Iceland)","IT1":"Istituto Nazionale di Statistica (ISTAT) (Italy)","IT2":"Banca d\u2019Italia (Italy)","IT3":"Ufficio Italiano dei Cambi (Italy)","IT4":"Ministero del Tesoro (Italy)","IT9":"Istituto di Studi e Analisi Economica (Italy)","IT99":"Other competent National Authority (Italy)","JE6":"Financial Services Commission, Jersey (JE)","JM1":"Statistical Institute of Jamaica","JM2":"Bank of Jamaica","JM4":"Ministry of Finance and Planning (Jamaica)","JM99":"Other competent National Authority (Jamaica)","JO1":"Department of Statistics (Jordan)","JO2":"Central Bank of Jordan","JO4":"Ministry of Finance (Jordan)","JO99":"Other competent National Authority (Jordan)","JP1":"Bureau of Statistics (Japan)","JP2":"Bank of Japan","JP4":"Ministry of Finance (Japan)","JP6":"Financial Services Agency (Japan)","KE1":"Central Bureau of Statistics (Kenya)","KE2":"Central Bank of Kenya","KE3":"Ministry of Planning and National Development (Kenya)","KE4":"Office of the Vice President and Ministry of Finance (Kenya)","KE99":"Other competent National Authority (Kenya)","KG1":"National Statistical Committee of Kyrgyz Republic","KG2":"National Bank of the Kyrgyz Republic","KG4":"Ministry of Finance (Kyrgyz Republic)","KG99":"Other competent National Authority (Kyrgyz Republic)","KH1":"National Institute of Statistics (Cambodia)","KH2":"National Bank of Cambodia","KH4":"Minist\u00e8re de l'\u00e9conomie et des finances (Cambodia)","KI2":"Bank of Kiribati, Ltd","KI4":"Ministry of Finance and Economic Planning (Kiribati)","KM2":"Banque Centrale des Comoros","KM4":"Ministere des Finances, du budget et du plan (Comoros)","KN1":"Statistical Office (St. Kitts and Nevis)","KN2":"Eastern Caribbean Central Bank (ECCB) (St. Kitts and Nevis)","KN4":"Ministry of Finance (St. Kitts and Nevis)","KR1":"Korea National Statistical Office (KNSO)","KR2":"The Bank of Korea","KR3":"Economic Planning Board (Korea, Republic of)","KR4":"Ministry of Finance and Economy (Korea, Republic of)","KR6":"The Korea Financial Services Commission","KW1":"Statistics and Information Technology Sector (Kuwait)","KW2":"Central Bank of Kuwait","KW4":"Ministry of Finance (Kuwait)","KW99":"Other competent National Authority (Kuwait)","KY1":"Department of Finance & Development / Statistical Office (Cayman Islands)","KY2":"Cayman Islands Monetary Authority","KY99":"Other competent National Authority (Cayman Islands)","KZ1":"National Statistical Agency of the Republic of Kazakhstan","KZ2":"National Bank of the Republic of Kazakhstan","KZ4":"Ministry of Finance (Kazakhstan)","KZ99":"Other competent National Authority (Kazakhstan)","LA2":"Bank of the Lao P.D.R.","LA4":"Ministry of Finance (Lao People's Democratic Republic)","LB1":"Central Administration of Statistics (Lebanon)","LB2":"Banque du Liban (Lebanon)","LB4":"Ministere des finances (Lebanon)","LB99":"Other competent National Authority (Lebanon)","LC1":"Statistical Office (St. Lucia)","LC2":"Eastern Caribbean Central Bank (ECCB) (St. Lucia)","LC4":"Ministry of Finance, International Financial Services and Economic Affairs (St. Lucia)","LI1":"Amt fur Volkswirtschaft","LI99":"Other competent National Authority (Liechtenstein)","LK2":"Central Bank of Sri Lanka","LR1":"Ministry of Planning and Economic Affairs (Liberia)","LR2":"Central Bank of Liberia","LR4":"Ministry of Finance (Liberia)","LR99":"Other competent National Authority (Liberia)","LS1":"Bureau of Statistics (Lesotho)","LS2":"Central Bank of Lesotho","LS4":"Ministry of Finance (Lesotho)","LT1":"Lithuania, Department of Statistics","LT2":"Bank of Lithuania","LT4":"Ministry of Finance (Lithuania)","LT99":"Other competent National Authority (Lithuania)","LU1":"STATEC - Service central de la statistique et des \u00e9tudes \u00e9conomiques du Luxembourg","LU2":"Central Bank of Luxembourg","LU6":"CSSF (Luxembourg Financial Sector Surveillance Commission)","LU99":"Other competent National Authority (Luxembourg)","LV1":"Central Statistical Bureau of Latvia","LV2":"Bank of Latvia","LV3":"The Treasury of the Republic of Latvia","LV6":"FCMC (Latvia Financial and Capital Market Commission)","LV99":"Other competent National Authority (Latvia)","LY1":"Census and Statistics Directorate (Libya)","LY2":"Central Bank of Libya","LY3":"General People's Secretariat of the Treasury (Libya)","LY4":"General Directorate for Economic and Social Planning (Libya)","LY5":"The National Corporation for Information and Documentation (Libya)","LY99":"Other competent National Authority (Libya)","MA1":"Ministere de la Prevision Economique et du Plan (Morocco)","MA2":"Bank Al-Maghrib (Morocco)","MA4":"Minist\u00e8re de l'Economie, des Finances, de la Privatisation et du Tourisme (Morocco)","MA5":"Office des Changes (Morocco)","MA99":"Other competent National Authority (Morocco)","MC1":"Statistical Office (Monaco)","MC2":"Monaco National Central Bank","MC99":"Other competent National Authority (Monaco)","MD1":"National Bureau for Statistics (Moldova)","MD2":"National Bank of Moldova","MD4":"Ministry of Finance (Moldova)","MD99":"Other competent National Authority (Moldova)","ME1":"Statistical Office (Montenegro)","ME2":"Central Bank of Montenegro","MG1":"INSTAT/Exchanges Commerciaux et des Services (Madagascar)","MG2":"Banque Centrale de Madagascar","MG4":"Minist\u00e8re des finances de l'Economie (Madagascar)","MG99":"Other competent National Authority (Madagascar)","MH4":"Ministry of Finance (Marshall Islands, Rep)","MK1":"State Statistical Office (Macedonia)","MK2":"National Bank of the Republic of Macedonia","MK4":"Ministry of Finance (Macedonia)","MK99":"Other competent National Authority (Macedonia, FYR)","ML1":"Direction Nationale de la Statistique et de l\u2019Informatique (DNSI) (Mali)","ML2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (Mali)","ML4":"Minist\u00e8re des Finances et du Commerce (Mali)","ML99":"Other competent National Authority (Mali)","MM1":"Central Statistical Organization (Myanmar)","MM2":"Central Bank of Myanmar","MM4":"Ministry of Finance and Revenue (Myanmar)","MM99":"Other competent National Authority (Myanmar)","MN1":"National Statistical Office (Mongolia)","MN2":"Bank of Mongolia","MN4":"Ministry of Finance and Economy (Mongolia)","MN99":"Other competent National Authority (Mongolia)","MO1":"Statistics and Census Department (China,P.R.:Macao)","MO2":"Monetary Authority of Macau (China,P.R.:Macao)","MO3":"Revenue Bureau of Macao","MO4":"Departamento de Estudos e Planeamento Financeiro (China,P.R.:Macao)","MO99":"Other competent National Authority (China,P.R.:Macao)","MQ1":"Department of Statistics (Martinique)","MQ99":"Other competent National Authority (Martinique)","MR1":"Department of Statistics and Economic Studies (Mauritania)","MR2":"Banque Centrale de Mauritanie","MR3":"Ministere du Plan (Mauritania)","MR4":"Minist\u00e8re des Finances (Mauritania)","MT1":"National Statistics Office (Malta)","MT2":"Central Bank of Malta","MT4":"Ministry of Finance (Malta)","MT6":"MFSA (Malta Financial Services Authority)","MT97":"Malta Maritime Authority","MT98":"Malta International Airport","MT99":"Other competent National Authority (Malta)","MU1":"Central Statistical Office (Mauritius)","MU2":"Bank of Mauritius","MU99":"Other competent National Authority (Mauritius)","MV2":"Maldives Monetary Authority (Maldives)","MV3":"Ministry of Planning and Development (Maldives)","MV4":"Ministry of Finance and Treasury (Maldives)","MW1":"National Statistical Office (Malawi)","MW2":"Reserve Bank of Malawi","MW4":"Ministry of Finance (Malawi)","MW99":"Other competent National Authority (Malawi)","MX1":"Instituto Nacional de Estad\u00edstica Geografia e Informatica (INEGI) (Mexico)","MX2":"Banco de Mexico","MX4":"Secretaria de Hacienda y Cr\u00e9dito P\u00fablico (Mexico)","MX99":"Other competent National Authority (Mexico)","MY1":"Department of Statistics Malaysia","MY2":"Bank Negara Malaysia","MY99":"Other competent National Authority (Malaysia)","MZ1":"Direc\u00e7\u00e3o Nacional de Estat\u00edstica (Mozambique)","MZ2":"Banco de Mo\u00e7ambique","MZ4":"Ministry of Planning and Finance (Mozambique)","MZ99":"Other competent National Authority (Mozambique)","NA1":"Central Bureau of Statistics (Namibia)","NA2":"Bank of Namibia","NA4":"Ministry of Finance (Namibia)","NC1":"Institut Territorial de la Statistique et des Etudes Economiques (New Caledonia)","NC99":"Other competent National Authority (French Territories, New Caledonia)","NE2":"Banque Centrale des \u00c9tats de l\u2019Afrique de l\u2019Ouest (BCEAO) (Niger)","NE3":"Ministere du Plan (Niger)","NE4":"Minist\u00e8re des Finances (Niger)","NG1":"Federal Office of Statistics (Nigeria)","NG2":"Central Bank of Nigeria","NG4":"Federal Ministry of Finance (Nigeria)","NG99":"Other competent National Authority (Nigeria)","NI2":"Banco Central de Nicaragua","NI4":"Ministerio de Hacienda y Cr\u00e9dito P\u00fablico (Nicaragua)","NL1":"Central Bureau voor de Statistiek (Netherlands)","NL2":"Nederlandse Bank (Netherlands)","NL4":"Ministry of Finance (Netherlands)","NL99":"Other competent National Authority (Netherlands)","NO1":"Statistics Norway","NO2":"Norges Bank (Norway)","NO98":"Avinor (Civil Aviation Administration)","NO99":"Other competent National Authority (Norway)","NP1":"Central Bureau of Statistics (Nepal)","NP2":"Nepal Rastra Bank","NP4":"Ministry of Finance (Nepal)","NR1":"Nauru Bureau of Statistics (Nauru)","NR4":"Ministry of Finance (Nauru)","NR99":"Other competent National Authority (Nauru)","NU1":"Statistics Offie Niue","NZ1":"Statistics New Zealand","NZ2":"Reserve Bank of New Zealand","NZ99":"Other competent National Authority (New Zealand)","OM2":"Central Bank of Oman","OM4":"Ministry of Finance (Oman)","PA1":"Directorate of Statistics and Census (Panama)","PA2":"Banco Nacional de Panama","PA3":"Office of the Controller General (Panama)","PA6":"Superintendencia de Bancos (Panama)","PE2":"Banco Central de Reserva del Per\u00fa","PE4":"Ministerio de Econom\u00eda y Finanzas (Peru)","PG1":"National Statistical Office (Papua New Guinea)","PG2":"Bank of Papua New Guinea","PG99":"Other competent National Authority (Papua New Guinea)","PH2":"Central Bank of the Philippines","PH3":"Bureau of the Treasury (Philippines)","PK1":"Pakistan Bureau of Statistics (Pakistan)","PK2":"State Bank of Pakistan","PK4":"Ministry of Finance (Pakistan)","PK99":"Other competent National Authority (Pakistan)","PL1":"Central Statistical Office of Poland","PL2":"Narodowy Bank Polski (Poland)","PL4":"Ministry of Finance (Poland)","PL99":"Other competent National Authority (Poland)","PS1":"Palestinian Central Bureau of Statistics","PS2":"Palestine Monetary Authority","PS99":"Other competent National Authority (West Bank and Gaza)","PT1":"Instituto Nacional de Estat\u00edstica (Portugal)","PT2":"Banco de Portugal (Portugal)","PT3":"Direccao Geral do Or\u00e7amento (DGO) (Portugal)","PT4":"Ministerio Das Financas (Portugal)","PT99":"Other competent National Authority (Portugal)","PW1":"Statistical office (Palau)","PW99":"Other competent National Authority (Palau)","PY2":"Banco Central del Paraguay","PY4":"Ministerio de Hacienda (Paraguay)","QA2":"Qatar Central Bank","QA3":"Customs Department (Qatar)","QA4":"Ministry of Finance, Economy and Commerce (Qatar)","RO1":"Romania, National Commission for Statistics","RO2":"National Bank of Romania","RO4":"Minist\u00e8re des Finances Public (Romania)","RO99":"Other competent National Authority (Romania)","RS1":"Statistical Office of the Republic of Serbia","RS2":"National Bank of Serbia (NBS) (Serbia, Rep. of)","RU1":"Federal State Statistics Service (Russian Federation)","RU2":"Central Bank of Russian Federation","RU3":"State Customs Committee of the Russian Federation","RU4":"Ministry of Finance (Russian Federation)","RU99":"Other competent National Authority (Russian Federation)","RW1":"General Office of Statistics (Rwanda)","RW2":"Banque Nationale Du Rwanda","RW4":"Minist\u00e8re des Finances et Planification Economie (Rwanda)","SA1":"Central Department of Statistics (Saudi Arabia)","SA2":"Saudi Arabian Monetary Agency","SA4":"Ministry of Finance (Saudi Arabia)","SA99":"Other competent National Authority (Saudi Arabia)","SB1":"Statistical Office (Solomon Islands)","SB2":"Central Bank of Solomon Islands","SB4":"Ministry of Finance and Treasury (Solomon Islands)","SC2":"Central Bank of Seychelles","SC4":"Ministry of Finance (Seychelles)","SC6":"Ministry of Administration and Manpower, Management and Information Systems Division (Seychelles)","SD1":"Central Bureau of Statistics (Sudan)","SD2":"Bank of Sudan","SD4":"Ministry of Finance and National Economy (Sudan)","SD99":"Other competent National Authority (Sudan)","SE1":"Statistics Sweden (Sweden)","SE2":"Sveriges Riksbank (Sweden)","SE5":"National Institute of Economic Research (Sweden)","SE99":"Other competent National Authority (Sweden)","SG1":"Ministry of Trade and Industry / Department of Statistics (Singapore)","SG2":"Monetary Authority of Singapore","SG3":"International Enterprise Singapore","SG4":"Ministry of Finance (Singapore)","SG99":"Other competent National Authority (Singapore)","SH1":"Saint Helena Statistical Office","SI1":"Statistical Office of the Republic of Slovenia","SI2":"Bank of Slovenia","SI4":"Ministry of Finance (Slovenia)","SI99":"Other competent National Authority (Slovenia)","SK1":"Statistical Office of the Slovak Republic","SK2":"National Bank of Slovakia","SK4":"Ministry of Finance of the Slovak Republic","SK99":"Other competent National Authority (Slovak Republic)","SL2":"Bank of Sierra Leone","SM1":"Office of Economic Planning and Data Processing Center and Statistics (San Marino)","SM2":"Instituto di Credito Sammarinese / Central Bank (San Marino)","SM4":"Ministry of Finance and Budget (San Marino)","SN1":"Direction de la Prevision et de la Statistique (Senegal)","SN2":"Banque Centrale des \u00c9tats de l'Afrique de l'Ouest (BCEAO) (Senegal)","SN4":"Minist\u00e8re de l'Economie et des Finance (Senegal)","SN99":"Other competent National Authority (Senegal)","SO2":"Central Bank of Somalia","SR1":"General Bureau of Statistics (Suriname)","SR2":"Centrale Bank van Suriname","SR4":"Ministry of Finance (Suriname)","SR99":"Other competent National Authority (Suriname)","SS1":"National Bureau of Statistics (South Sudan)","SS2":"Bank of South Sudan","SS99":"Other competent National Authority (South Sudan)","ST2":"Banco Central de Sao Tome e Principe","ST4":"Ministry of Planning and Financing (S\u00e3o Tom\u00e9 and Pr\u00edncipe)","SV2":"Banco Central de Reserva de El Salvador","SV4":"Ministerio de Hacienda (El Salvador)","SX1":"Bureau for Statistics Sint Maarten","SX99":"Other competent National Authority (Sint Maarten)","SY1":"Central Bureau of Statistics (Syria Arab Rep.)","SY2":"Central Bank of Syria","SY4":"Ministry of Finance (Syrian Arab Rep.)","SY99":"Other competent National Authority (Syrian Arab Republic)","SZ1":"Central Statistical Office (Swaziland)","SZ2":"Central Bank of Swaziland","SZ4":"Ministry of Finance (Swaziland)","TC4":"Ministry of Finance (Turks and Caicos)","TC99":"Other competent National Authority (Turks and Caicos)","TD1":"Institut de la Statistique (INSDEE) (Chad)","TD2":"Banque des \u00c9tats de l\u2019Afrique Centrale (BEAC) (Chad)","TD4":"Ministere des finances (Chad)","TD99":"Other competent National Authority (Chad)","TG2":"Banque Centrale des \u00c9tats de l'Afrique de l'Ouest (BCEAO) (Togo)","TG3":"Ministere du Plan (Togo)","TG4":"Minist\u00e8re de l\u2019Economie des Finances (Togo)","TH2":"Bank of Thailand","TH4":"Ministry of Finance (Thailand)","TH5":"National Economic and Social Development Board (Thailand)","TJ1":"State Statistical Agency of Tajikistan","TJ2":"National Bank of Tajikistan","TJ4":"Ministry of Finance (Tajikistan)","TJ99":"Other competent National Authority (Tajikistan)","TL1":"Statistical Office (Timor Leste)","TL2":"Banco Central de Timor-Leste","TL4":"Ministry of Finance (Timor-Leste)","TL99":"Other competent National Authority (Timor-Leste)","TM1":"National Institute of State Statistics and Information (Turkmenistan)","TM2":"Central Bank of Turkmenistan","TM4":"Ministry of Economy and Finance (Turkmenistan)","TM99":"Other competent National Authority (Turkmenistan)","TN1":"National Institute of Statistics (Tunisia)","TN2":"Banque centrale de Tunisie","TN4":"Minist\u00e8re des Finances (Tunisia)","TO1":"Statistics Department (Tonga)","TO2":"National Reserve Bank of Tonga","TO4":"Ministry of Finance (Tonga)","TO99":"Other competent National Authority (Tonga)","TR1":"State Institute of Statistics (Turkey)","TR2":"Central Bank of the Republic of Turkey","TR3":"Hazine M\u00fcstesarligi (Turkish Treasury)","TR98":"State Airports Authority","TR99":"Other competent National Authority (Turkey)","TT1":"Central Statistical Office (Trinidad and Tobago)","TT2":"Central Bank of Trinidad and Tobago","TT4":"Ministry of Finance (Trinidad and Tobago)","TV1":"Tuvalu Statistics","TW2":"Central Bank of the Republic of China (Taiwan)","TZ1":"National Bureau of Statistics (Tanzania)","TZ2":"Bank of Tanzania","TZ4":"Ministry of Finance (Tanzania)","TZ99":"Other competent National Authority (Tanzania)","U22":"Euro area central banks","U32":"EU central banks not belonging to the Euro area","UA1":"State Statistics Committee of Ukraine","UA2":"National Bank of Ukraine","UA4":"Ministry of Finance (Ukraine)","UA99":"Other competent National Authority (Ukraine)","UG1":"Uganda Bureau of Statistics","UG2":"Bank of Uganda","UG4":"Ministry of Finance, Planning and Economic Development (Uganda)","UG99":"Other competent National Authority (Uganda)","US2":"Federal Reserve Bank of New York (USA)","US3":"Board of Governors of the Federal Reserve System (USA)","US4":"U.S. Department of Treasury (USA)","US4_1":"The Office of Financial Research (OFR)","US5":"U.S. Department of Commerce (USA)","US6":"Bureau of Labor Statistics","US7":"Bureau of Census","US8":"Bureau of Economic Analysis","UY2":"Banco Central del Uruguay","UY4":"Ministerio de Econom\u00eda y Finanzas (Uruguay)","UZ1":"Goskomprognozstat (Uzbekistan)","UZ3":"Ministry of Economy (Uzbekistan)","UZ4":"Ministry of Finance (Uzbekistan)","UZ99":"Other competent National Authority (Uzbekistan)","VA2":"Holy See (Vatican City State) National Central Bank","VC1":"Statistical Unit (St. Vincent and Grenadines)","VC2":"Eastern Caribbean Central Bank (ECCB) (St. Vincent and Grenadines)","VC4":"Ministry of Finance and Planning (St. Vincent and the Grenadines)","VE2":"Banco Central de Venezuela","VE4":"Ministerio de Finanzas (Venezuela)","VG99":"Other competent National Authority (Virgin Islands, British)","VI99":"Other competent National Authority (Virgin Islands, US)","VN1":"General Statistics Office (Vietnam)","VN2":"State Bank of Vietnam","VN99":"Other competent National Authority (Vietnam)","VU1":"Statistical Office (Vanuatu)","VU2":"Reserve Bank of Vanuatu","VU4":"Ministry of Finance and Economic Management (Vanuatu)","VU99":"Other competent National Authority (Vanuatu)","WS1":"Department of Statistics (Samoa)","WS2":"Central Bank of Samoa","WS4":"Samoa Treasury Department","WS99":"Other competent National Authority (Samoa)","XK1":"Kosovo agency of Statistics","XK2":"Central Bank of the Republic of Kosovo","XK4":"Ministry of Finance (Kosovo)","XK99":"Other competent National Authority (Kosovo)","YE1":"Central Statistical Organization (Yemen)","YE2":"Central Bank of Yemen","YE4":"Ministry of Finance (Yemen)","YE99":"Other competent National Authority (Yemen, Republic of)","ZA1":"Central Statistical Service (South Africa)","ZA2":"South African Reserve Bank","ZA3":"Department of Customs and Excise (South Africa)","ZA99":"Other competent National Authority (South Africa)","ZM1":"Central Statistical Office (Zambia)","ZM2":"Bank of Zambia","ZM99":"Other competent National Authority (Zambia)","ZW1":"Central Statistical Office (Zimbabwe)","ZW2":"Reserve Bank of Zimbabwe","ZW4":"Ministry of Finance, Economic Planning and Development (Zimbabwe)","ZW99":"Other competent National Authority (Zimbabwe)","ZZZ":"Unspecified (e.g. any, dissemination, internal exchange etc)"}},"CL_UNIT":{"name":"Unit of measure code list","codes":{"_T":"All currencies","_X":"Not specified","_Z":"Not applicable","ADF":"Andorran franc (1-1 peg to the French franc)","ADP":"Andorran peseta (1-1 peg to the Spanish peseta)","AED":"United Arab Emirates dirham","AFA":"Afghanistan afghani (old)","AFN":"Afghanistan, Afghanis","ALL":"Albanian lek","AMD":"Armenian dram","ANG":"Netherlands Antillean guilder","AOA":"Angolan kwanza","AON":"Angolan kwanza (old)","AOR":"Angolan kwanza readjustado (old)","ARS":"Argentine peso","ATS":"Austrian schilling","AUD":"Australian dollar","AWG":"Aruban florin/guilder","AZM":"Azerbaijanian manat (old)","AZN":"Azerbaijan, manats","BAM":"Bosnia-Hezergovinian convertible mark","BBD":"Barbados dollar","BDT":"Bangladesh taka","BEF":"Belgian franc","BEL":"Belgian franc (financial)","BGL":"Bulgarian lev (old)","BGN":"Bulgarian lev","BHD":"Bahraini dinar","BIF":"Burundi franc","BMD":"Bermudian dollar","BND":"Brunei dollar","BOB":"Bolivian boliviano","BRL":"Brazilian real","BSD":"Bahamas dollar","BTN":"Bhutan ngultrum","BWP":"Botswana pula","BYB":"Belarussian rouble (old)","BYN":"Belarusian Ruble","BYR":"Belarus, Rubles (deprecated)","BZD":"Belize dollar","CAD":"Canadian dollar","CD":"National currency per US dollar (unit for exchange rates and PPP)","CDF":"Congo franc (ex Zaire)","CE":"National currency per Euro (unit for exchange rates and PPP)","CHE":"WIR Euro","CHF":"Swiss franc","CHW":"WIR Franc","CLF":"Unidades de fomento","CLP":"Chilean peso","CNY":"Chinese yuan renminbi","COP":"Colombian peso","COU":"Unidad de Valor Real","CRC":"Costa Rican colon","CSD":"Serbian dinar (old)","CT":"Euro cent","CUP":"Cuban peso","CVE":"Cape Verde escudo","CYP":"Cypriot pound","CZK":"Czech koruna","DEM":"German mark","DJF":"Djibouti franc","DKK":"Danish krone","DOP":"Dominican peso","DY":"Days","DZD":"Algerian dinar","E0":"Currency of EER-12 group of trading partners (of the euro area moving composition): AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","E1":"Currency of EER-20 group of trading partners (of the euro area-18 composition): AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN and HR","E2":"Currency of EER-19 group of trading partners (of the euro area-18 composition): AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN","E3":"Currency of EER-39 group of trading partners (of the euro area-18 composition): AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN and HR,DZ,AR,BR,CL,IS,IN,ID,IL,MY,MX,MA,NZ,PH,RU,ZA,TW,TH,T","E4":"Currency of EER-12 group of trading partners (of the euro area-18 composition): AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","E5":"Currency of EER-19 group of trading partners: AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN and HR","E6":"Currency of EER-18 group of trading partners: AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN","E7":"Currency of EER-38 group of trading partners: AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN and HR,DZ,AR,BR,CL, IS,IN,ID,IL,MY,MX,MA,NZ,PH,RU,ZA,TW,TH,TR,VE","E8":"Currency of EER-12 group of trading partners: AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","ECS":"Ecuador sucre (old)","EEK":"Estonian kroon","EGP":"Egyptian pound","ERN":"Erytrean nafka","ESP":"Spanish peseta","ETB":"Ethiopian birr","EUR":"Euro","EUR_R_ACTIVITY":"Euro; ratio to total activity","EUR_R_B0":"Euro; ratio to EU","EUR_R_B1G":"Euro; ratio to gross value added","EUR_R_B1GQ":"Euro; ratio to gross domestic product","EUR_R_B1GQ_L":"Euro; ratio to gross domestic product (chained linked volume)","EUR_R_B1GQ_LA":"Euro; ratio to gross domestic product (annual levels)","EUR_R_B2":"Euro; ratio to EU15","EUR_R_B4":"Euro; ratio to EU27","EUR_R_B5":"Euro; ratio to EU28","EUR_R_C":"Euro per card","EUR_R_F22A":"Euro; ratio to overnight deposits denominated in all currencies of non-MFIs held in institutions offering payment services to non-MFIs","EUR_R_F5":"Euro; ratio to equity and investment fund shares","EUR_R_I6":"Euro; ratio to Euro Area 17","EUR_R_I7":"Euro; ratio to Euro Area 18","EUR_R_I8":"Euro; ratio to Euro Area 19","EUR_R_I9":"Euro; ratio to Euro Area 20","EUR_R_KG":"Euro per kilogram","EUR_R_KG_L":"EUR per kg Chain linked volumes","EUR_R_PNT":"Euro; ratio to number of transactions","EUR_R_POP":"Euro; ratio to total population","EUR_R_POP6":"Euro per million inhabitants","EUR_R_SAL_HW":"Euro; ratio to employees in hours worked","EUR_R_SAL_PS":"Euro; ratio to employees in persons","EUR_R_T":"Euro per terminal","EUR_R_TT":"Euro; ratio to total payment transactions","EUR_R_U2":"Euro; ratio to Euro Area (changing composition)","FIM":"Finnish markka","FJD":"Fiji dollar","FKP":"Falkland Islands pound","FRF":"French franc","FT":"Full time equivalent","FT_R_ACTIVITY":"Full time equivalents; ratio to total activity","GBP":"UK pound sterling","GEL":"Georgian lari","GGP":"Guernsey, Pounds","GHC":"Ghanaian cedi (old)","GHS":"Ghana Cedi","GIP":"Gibraltar pound","GMD":"Gambian dalasi","GNF":"Guinea franc","GR":"Grams","GRD":"Greek drachma","GT":"Gross tonnage (GT)","GTQ":"Guatemalan quetzal","GW":"Gigawatt","GWHR":"Gigawatt-hour","GWP":"Guinea-Bissau Peso","GYD":"Guyanan dollar","H1":"Currency of Euro area-18 countries: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK","H10":"Currency of Euro area-19 countries and EER-38 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN and HR,D","H11":"Currency of Euro area-19 countries and EER-19 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN and HR","H12":"Currency of Euro area-20 countries: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK,HR","H13":"Currency of Euro area-20 countries and the EER-12 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK,HR and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","H14":"Currency of Euro area-20 countries and the EER-18 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, HU, PL, RO and CN)","H15":"Currency of Euro area-20 countries and the EER-37 group of trading partners (AU, CA, DK, HK, JP, NO, SG, KR, SE, CH, GB, US, BG, CZ, HU, PL, RO, CN, DZ, AR, BR, CL, IS, IN, ID, IL, MY, MX, MA, NZ, PH,","H2":"Currency of Euro area-18 countries and EER-12 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","H3":"Currency of Euro area-18 countries and EER-19 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN","H36":"Currency of European Commission IC-36 group of trading partners: BE,DE,EE,GR,ES,FR,IE,IT,CY,LU,NL,MT,AT,PT,SI,SK,FI,BG,CZ,DK,LV,LT,HU,PL,RO,SE,GB and US,AU,CA,JP,MX,NZ,NO,CH,TR","H37":"Currency of European Commission IC-37 group of trading partners: BE,DE,EE,GR,ES,FR,IE,IT,CY,LU,NL,MT,AT,PT,SI,SK,FI,BG,CZ,DK,HR,LV,LT,HU,PL,RO,SE,GB and US,AU,CA,JP,MX,NZ,NO,CH,TR","H4":"Currency of Euro area-18 countries and EER-39 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN and HR,D","H42":"Currency of European Commission IC-42 group of trading partners : BE,DE,EE,GR,ES,FR,IE,IT,CY,LU,NL,MT,AT,PT,SI,SK,FI,BG,CZ,DK,HR,LV,LT,HU,PL,RO,SE,GB and US,AU,CA,JP,MX,NZ,NO,CH,TR,KR,CN,HK,RU,BR","H5":"Currency of Euro area-18 countries and EER-20 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,CN and HR","H6":"Currency of Euro area-18 countries and EER-21 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,LT,HU,PL,RO,HR,TR,RU","H7":"Currency of Euro area-19 countries: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK","H8":"Currency of Euro area-19 countries and EER-12 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US","H9":"Currency of Euro area-19 countries and EER-18 group of trading partners: FR,BE,LU,NL,DE,IT,IE,PT,ES,FI,AT,GR,SI,CY,EE,LT,LV,MT,SK and AU,CA,DK,HK,JP,NO,SG,KR,SE,CH,GB,US and BG,CZ,HU,PL,RO,CN","HA":"Hectare","HKD":"Hong Kong dollar","HKQ":"Hong Kong dollar (old)","HL":"Hectolitre","HNL":"Honduran lempira","HR":"Hours","HRK":"Croatian kuna","HTG":"Haitian gourde","HUF":"Hungarian forint","HW":"Hours worked","HW_R_ACTIVITY":"Hours worked; ratio to total activity","HW_R_EMP_PS":"Hours worked per person employed","HW_R_POP":"Hours worked per capita","I_EU":"Index, EU=100","I_EU27":"Index, EU27=100","I_EU28":"Index, EU28=100","I00":"Index, 2000=100","I01":"Index, 2001=100","I05":"Index, 2005=100","I06":"Index, 2006=100","I08":"Index, 2008=100","I09":"Index, 2009=100","I10":"Index, 2010=100","I12":"Index, 2012=100","I15":"Index, 2015=100","I90":"Index, 1990=100","I95":"Index, 1995=100","I96":"Index, 1996=100","I99":"Index, 1999=100","IDR":"Indonesian rupiah","IEP":"Irish pound","ILS":"Israeli shekel","IMP":"Isle of Man, Pounds","INR":"Indian rupee","IQD":"Iraqi dinar","IRR":"Iranian rial","ISK":"Iceland krona","ITL":"Italian lira","IX":"Index","IX_R_LE":"Index of notional stocks","JB":"Jobs","JB_R_ACTIVITY":"Jobs; ratio to total activity","JEP":"Jersey, Pounds","JMD":"Jamaican dollar","JOD":"Jordanian dinar","JPY":"Japanese yen","KCAL":"Kilocalorie","KES":"Kenyan shilling","KG":"Kilograms","KG_R_GDP_USD":"kg per dollar of GDP in USD","KGCO2E_R_KG":"Kg of CO2E per Kg of Product","KGOE":"Kilogram of oil equivalent (KGOE)","KGS":"Kyrgyzstan som","KHR":"Kampuchean real (Cambodian)","KL":"Kilolitres","KM":"Kilometre","KM2":"Square kilometre","KMF":"Comoros franc","KPW":"Korean won (North)","KRW":"Korean won (Republic)","KW":"Kilowatt","KWD":"Kuwait dinar","KWHR":"Kilowatt-hour","KYD":"Cayman Islands dollar","KZT":"Kazakstan tenge","LAK":"Lao kip","LBP":"Lebanese pound","LKR":"Sri Lanka rupee","LRD":"Liberian dollar","LSL":"Lesotho loti","LT":"Litres","LTL":"Lithuanian litas","LUF":"Luxembourg franc","LVL":"Latvian lats","LYD":"Libyan dinar","M":"Metre","M3":"Cubic metre","MAD":"Moroccan dirham","MD":"Man Days","MDL":"Moldovian leu","MGA":"Madagascar, Ariary","MGF":"Malagasy franc","MH":"Months","MKD":"Macedonian denar","MMK":"Myanmar kyat","MN":"Minute","MNT":"Mongolian tugrik","MOP":"Macau pataca","MQ":"Square Metres","MRO":"Mauritanian ouguiya","MTL":"Maltese lira","MUR":"Mauritius rupee","MVR":"Maldive rufiyaa","MW":"Megawatt","MWK":"Malawi kwacha","MXN":"Mexican peso","MXP":"Mexican peso (old)","MXV":"Mexican Unidad de Inversion (UDI)","MY":"Man Years","MYR":"Malaysian ringgit","MZM":"Mozambique metical (old)","MZN":"Mozambique, Meticais","NAD":"Namibian dollar","NGN":"Nigerian naira","NIO":"Nicaraguan cordoba","NLG":"Netherlands guilder","NOK":"Norwegian krone","NPR":"Nepaleese rupee","NZD":"New Zealand dollar","OMR":"Oman Sul rial","OZ":"Ounces","PA":"Percent per annum","PAB":"Panama balboa","PC":"Percentage change","PD":"Percentage points","PE":"Euro, converted using purchasing power parities (PPS = EUR for EU28)","PE_B6_R_POP":"Euro, converted using purchasing power parities (PPS = EUR for EU27 as of 31 January 2020 (brexit)); ratio to total population","PE_B6":"Euro, converted using purchasing power parities (PPS = EUR for EU27 as of 31 January 2020 (brexit))","PE_B6_R_SAL_HW":"Euro, converted using purchasing power parities (PPS = EUR for EU27 as of 31 January 2020 (brexit)); ratio to employees in hours worked","PE_B6_R_SAL_PS":"Euro, converted using purchasing power parities (PPS = EUR for EU27 as of 31 January 2020 (brexit)); ratio to employees in persons","PE_R_B2":"Euro, converted using purchasing power parities; ratio to EU15","PE_R_B4":"Euro, converted using purchasing power parities; ratio to EU27","PE_R_B4_POP":"Euro, converted using purchasing power parities; ratio to EU27 per capita","PE_R_B5":"Euro, converted using purchasing power parities; ratio to EU28","PE_R_B5_EMP_HW":"Euro, converted using purchasing power parities; ratio to EU28 hours worked","PE_R_B5_EMP_PS":"Euro, converted using purchasing power parities; ratio to EU28 persons employed","PE_R_B5_POP":"Euro, converted using purchasing power parities; ratio to EU28 per capita","PE_R_B6":"Euro, converted using purchasing power parities; ratio to EU27 as of 31 January 2020 (brexit)","PE_R_B6_POP":"Euro, converted using purchasing power parities; ratio to EU27 as of 31 January 2020 (brexit) per capita","PE_R_I6":"Euro, converted using purchasing power parities; ratio to EuroArea 17","PE_R_I7":"Euro, converted using purchasing power parities; ratio to Euro Area 18","PE_R_I7_EMP_HW":"Euro, converted using purchasing power parities; ratio to Euro Area 18 hours worked","PE_R_I7_EMP_PS":"Euro, converted using purchasing power parities; ratio to Euro Area 18 persons employed","PE_R_I8":"Euro, converted using purchasing power parities; ratio to Euro Area 19","PE_R_I8_EMP_HW":"Euro, converted using purchasing power parities; ratio to Euro Area 19 hours worked","PE_R_I8_EMP_PS":"Euro, converted using purchasing power parities; ratio to Euro Area 19 persons employed","PE_R_I9":"Euro, converted using purchasing power parities; ratio to Euro Area 20","PE_R_I9_EMP_HW":"Euro, converted using purchasing power parities; ratio to Euro Area 20 hours worked","PE_R_I9_EMP_PS":"Euro, converted using purchasing power parities; ratio to Euro Area 20 persons employed","PE_R_KG":"PPS per kg","PE_R_POP":"Euro, converted using purchasing power parities; ratio to total population","PE_R_SAL_HW":"Euro, converted using purchasing power parities; ratio to employees in hours worked","PE_R_SAL_PS":"Euro, converted using purchasing power parities; ratio to employees in persons","PE_R_U2":"Euro, converted using purchasing power parities; ratio to Euro Area (changing composition)","PEN":"Peru nuevo sol","PGK":"Papua New Guinea kina","PHP":"Philippine peso","PKR":"Pakistan rupee","PLN":"Polish zloty","PLZ":"Polish zloty (old)","PM":"Per mill","PN":"Pure number","PN_R_B0":"Pure number; ratio to EU","PN_R_C":"Pure number per card","PN_R_F22A":"Pure number per number of overnight deposits denominated in all currencies of non-MFIs held in institutions offering payment services to non-MFIs","PN_R_POP6":"Pure number per million inhabitants","PN_R_T":"Pure number per terminal","PN_R_TT":"Pure number; ratio to total payment transactions","PO":"Points","PP":"Purchasing power parities","PS":"Persons","PS_R_ACTIVITY":"Persons; ratio to total activity","PS_R_POP":"Total employment per capita","PT":"Percent","PTE":"Portuguese escudo","PU":"US dollar, converted using purchasing power parities","PU_R_B1G":"US $, PPP converted, ratio to value added","PU_R_B1G_S11":"US $ , PPP converted, ratio to value added of non-financial corporations","PU_R_B1G_S12":"US $, PPP converted, ratio to value added of financial corporations","PU_R_B1GQ":"US $, PPP converted, ratio to gross domestic product","PU_R_B2G_S11":"US $, PPP converted, ratio to gross operating surplus of non-financial corporations","PU_R_B2G_S12":"US $ , PPP converted, ratio to gross operating surplus of financial corporations","PU_R_B6G_S1M":"US $, PPP converted, ratio to household and NPISH gross disposable income","PU_R_B6N_S1M":"US $, PPP converted, ratio to household and NPISH net disposable income","PU_R_F_S1M":"US $, PPP converted, ratio to total household and NIPSH financial assets","PU_R_OTE":"US $, PPP converted, ratio to total expenditure of General Government","PU_R_P31_S1M_D":"US $, PPP converted, deflated by final consumption of households and NPISH","PU_R_P41_D":"US $, PPP converted, deflated by actual individual consumption","PU_R_P51G":"US $, PPP converted, ratio to GFCF","PU_R_POP":"Per capita, US $, PPP converted","PU_R_POP_I07Q1":"Per capita, US $, PPP converted, index, 2007q1=100","PU_R_POP_PU_6O":"Index per capita, US $, PPP converted, OECD = 100","PYG":"Paraguay guarani","QAR":"Qatari rial","RO":"Ratio","ROL":"Romanian leu (old)","RON":"Romanian leu","RSD":"Serbian Dinar","RT":"Interest rate","RUB":"Russian rouble","RUR":"Russian ruble (old)","RWF":"Rwanda franc","SAR":"Saudi riyal","SBD":"Solomon Islands dollar","SCR":"Seychelles rupee","SDD":"Sudanese dinar (old)","SDG":"Sudan, Dinars","SDP":"First sudanese Pound","SEK":"Swedish krona","SGD":"Singapore dollar","SHP":"St. Helena pound","SIT":"Slovenian tolar","SKK":"Slovak koruna","SLL":"Sierra Leone leone","SOS":"Somali shilling","SPL":"Seborga, Luigini","SRD":"Suriname, Dollars","SRG":"Suriname guilder (old)","SSP":"South Sudanese Pound","STD":"Sao Tome and Principe dobra","SVC":"El Salvador colon","SYP":"Syrian pound","SZL":"Swaziland lilangeni","TCO2E":"Tonnes of CO2-equivalent","TCO2E_R_POP":"Tonnes of CO2-equivalent per capita","THB":"Thai baht","TJ":"Terajoule","TJR":"Tajikistan rouble (old)","TJS":"Tajikistan, Somoni","TMM":"Turkmenistan manat","TMT":"Turkmenistan New Manat","TN":"Tonnes","TN_R_POP":"Tonnes per capita","TN_RME":"Tonnes in raw material equivalents","TND":"Tunisian dinar","TNMVOCE":"Tonnes of NMVOC equivalent","TNMVOCE_R_POP":"Tonnes of NMVOC equivalent per capita","TNO2E":"Tonnes of NO2-equivalent","TNO2E_R_POP":"Tonnes of NO2-equivalent per capita","TNOE":"Tonnes of oil equivalent (TOE)","TOP":"Tongan paanga","TPE":"East Timor escudo (old)","TRL":"Turkish lira (old)","TRY":"Turkish lira","TSO2E":"Tonnes of SO2-equivalent","TSO2E_R_POP":"Tonnes of SO2-equivalent per capita","TTD":"Trinidad and Tobago dollar","TVD":"Tuvalu Dollars","TWD":"New Taiwan dollar","TZS":"Tanzania shilling","UAH":"Ukraine hryvnia","UGX":"Uganda Shilling","USD":"US dollar","USD_R_CA":"Dollars; Ratio to Current account","USD_R_GS":"Dollars; Ratio to Total goods and services","USD_R_KG":"USD per kilogram","USD_R_POP":"Per capita, US $, exchange rates converted","UT":"Unit described in title","UYI":"Uruguay Peso en Unidades Indexadas","UYU":"Uruguayan peso","UZS":"Uzbekistan sum","VEB":"Venezuela bolivar (old)","VEF":"Venezuelan bolivar fuerte","VND":"Vietnamese dong","VUV":"Vanuatu vatu","WST":"Samoan tala","X1":"All currencies except national domestic currency","X10":"All currencies except: EUR, domestic currency","X11":"All currencies except: EUR, USD, XU3","X12":"All currencies except: EUR, USD, XU3, GBP","X13":"All currencies except: EUR, USD, XU3, GBP, BRL, CAD, CHF, CNY, INR, JPY, KRW, MXN, NOK, RUB, SGD, TRY","X14":"All currencies except: USD, domestic currency","X15":"All currencies except: EUR, JPY, GBP, USD","X2":"All currencies except: USD","X3":"All currencies except EUR","X4":"All currencies except: EUR, USD","X5":"All currencies except: EUR, JPY, USD","X6":"All currencies except: EUR, CHF, GBP, JPY, USD","X7":"All currencies except: EUR, USD, JPY, GBP, CHF","X8":"All currencies except: USD, EUR, GBP, JPY, CHF, CNY, AUD, CAD","X9":"All currencies except: EUR, USD, JPY, domestic currency","XAF":"CFA franc / BEAC","XAG":"Silver","XAU":"Gold","XBA":"Bond Markets Unit European Composite Unit (EURCO)","XBB":"Bond Markets Unit European Monetary Unit (E.M.U.-6)","XBC":"Bond Markets Unit European Unit of Account 9 (E.U.A.-9)","XBD":"Bond Markets Unit European Unit of Account 17 (E.U.A.-17)","XCD":"Eastern Caribbean dollar","XDB":"Currencies included in the SDR basket, gold and SDRs","XDC":"Domestic currency (incl. conversion to current currency made using a fixed parity)","XDC_R_A_S1M":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to total assets of households and NPISHs","XDC_R_B1G":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to gross value added","XDC_R_B1G_CY":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to annual moving sum of sector specific gross value added","XDC_R_B1G_S11":"percentage of value added of non-financial corporations","XDC_R_B1G_S12":"percentage of value added of financial corporations","XDC_R_B1GQ":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to gross domestic product","XDC_R_B1GQ_CY":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to the annual moving sum of gross domestic product","XDC_R_B1GQ_L":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to gross domestic product (chained linked volume)","XDC_R_B1GQ_LA":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to gross domestic product (annual levels)","XDC_R_B1N":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to net value added","XDC_R_B1N_CY":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to annual moving sum of sector specific net value added","XDC_R_B1N_S11":"percentage of net value added of non-financial corporations","XDC_R_B1N_S12":"percentage of net value added of financial corporations","XDC_R_B2G_S11":"percentage of gross operating surplus of non-financial corporations","XDC_R_B2G_S12":"percentage of gross operating surplus of financial corporations","XDC_R_B5G_S1M":"percentage of household and NPISH primary income","XDC_R_B6G_CY":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to the annual moving sum of sector specific gross disposable income","XDC_R_B6G_POP":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to per capita sector specific gross disposable income","XDC_R_B6G_S1M":"percentage of household and NPISH gross disposable income","XDC_R_B6GA":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to sector specific gross disposable income, adjusted for the change in net equity of households in pension fund","XDC_R_B6GA_CY":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to the annual moving sum of sector specific gross disposable income, adjusted for the change in net equity of h","XDC_R_B6GA_POP":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to per capita sector specific gross disposable income, adjusted for the change in net equity of households in p","XDC_R_B6GA_S1M":"percentage of household and NPISH gross disposable income adjusted for the net change in pension entitlements","XDC_R_B6N_S1M":"percentage of household and NPISH net disposable income","XDC_R_B7N_S1M":"percentage of household and NPISH net adjusted disposable income","XDC_R_EMP":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to total employment","XDC_R_EMP_HW":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to total employment in hours worked","XDC_R_EMP_PS":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to total employment in persons","XDC_R_F":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to sector specific assets/liabilities","XDC_R_F_L_S13":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to liabilities of general government","XDC_R_F_L_S1S":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to liabilities of Non-financial corporations, general government and households and NPISH","XDC_R_F_S1":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to financial assets of total economy","XDC_R_F_S11":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to financial assets of non-financial corporations","XDC_R_F_S1M":"percentage of total household and NIPSH financial assets","XDC_R_F2_L_S12K":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to currency and deposits liabilities of the Monetary Financial Institutions","XDC_R_F2T4S_L_S11":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to short-term liabilities of non-financial corporations","XDC_R_F2T4S_L_S12":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to short-term liabilities of financial corporations","XDC_R_F5":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to equity and investment fund shares","XDC_R_F5_L":"Number of times of liability of equity and investment fund shares","XDC_R_F5_L_S11":"Number of times of liability of equity and investment fund shares of non-financial corporations","XDC_R_F5_L_S12":"Number of times of liability of equity and investment fund shares of financial corporations","XDC_R_F51_L":"Number of times of liability of equity","XDC_R_F51_L_S12K":"Number of times of liability of equity of the Monetary Financial Institutions","XDC_R_FD":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to sector specific financing","XDC_R_FI":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to sector specific financial investment","XDC_R_GD":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to Maastricht debt","XDC_R_GF10":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to total expenditure in social protection","XDC_R_I7":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to Euro area 18","XDC_R_I8":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to Euro area 19","XDC_R_LE_N11N":"Gross value added per unit of net fixed assets","XDC_R_OTE":"percentage of total expenditure of General Government","XDC_R_P2_B_ACT":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to intermediate consumption at basic 'prices by activity (same activity for denominator and numerator)","XDC_R_P2_B_ACT_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to intermediate consumption at basic 'prices by activity and by product (same activity and same product for deno","XDC_R_P2_B_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to intermediate consumption at basic 'prices by product (same product for denominator and numerator)","XDC_R_P3_S14_B_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to household final consumption expenditure at basic 'prices by product (same product for denominator and numerat","XDC_R_P3_S14_O_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to household final consumption expenditure at purchasers' prices by product (same product for denominator and nu","XDC_R_P31_S1M_D":"national currency, deflated by final consumption of households and NPISH","XDC_R_P41_D":"national currency, deflated by actual individual consumption","XDC_R_P51G":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to Gross fixed capital formation","XDC_R_P51G_B_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to gross fixed capital formation at basic 'prices by product (same product for denominator and numerator)","XDC_R_P6_B_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to exports at basic 'prices by product (same product for denominator and numerator)","XDC_R_POP":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to total population","XDC_R_SAL_HW":"Domestic currency (incl conversion to current currency made using a fixed parity); ratio to employees in hours worked","XDC_R_SAL_PS":"Domestic currency (incl. conversion to current currency made using a fixed parity); ratio to employees in persons","XDC_R_TS_O_PROD":"Domestic currency (incl. conversion to current currency made using a fix parity); ratio to total supply at purchasers' prices by product (same product for denominator and numerator)","XDD":"Currencies included in the SDR basket (USD, EUR, JPY, GBP, CNY)","XDF":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate)","XDF_R_B0":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate) ; ratio to EU","XDF_R_B1GQ":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate); ratio to GDP","XDF_R_C":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate) per card","XDF_R_F22A":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate); ratio to overnight deposits denominated in all currencies of non-MFIs held in institutions o","XDF_R_PNT":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate); ratio to number of transactions","XDF_R_POP6":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate) per million inhabitants","XDF_R_T":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate) per terminal","XDF_R_TT":"Domestic currency (incl. conversion to current currency made using a fixed parity or market exchange rate); ratio to total payment transactions","XDM":"Domestic currency (incl. conversion to current currency made using market exchange rate)","XDN":"Domestic currency (currency previously used by a country before joining a Monetary Union)","XDO":"Other currencies not included in the SDR basket, exc. gold and SDRs","XDR":"Special Drawing Rights (S.D.R.)","XEU":"European Currency Unit (E.C.U.)","XFO":"Gold-Franc","XFU":"UIC-Franc","XGO":"Gold fine troy ounces","XNC":{"name":"Euro area non-participating foreign currency","desc":"_T (All currencies) = XNC + XPC + XDC"},"XOF":"CFA franc / BCEAO","XPC":{"name":"Euro area participating foreign currency","desc":"_T (All currencies) = XNC + XPC + XDC"},"XPD":"Palladium","XPF":"Pacific franc","XPT":"Platinum","XSU":"Sucre","XTS":"Codes specifically reserved for testing purposes","XU3":"National currencies of an EU Member State not belonging to the euro area (changing composition)","XUA":"ADB Unit of Account","XXCF":"Exchange rate: currency of area per currency of counterpart area with conversion factor to fixed exchange rate series","XXCFA":"Exchange rate (average): currency of area per currency of counterpart area with conversion factor to fixed exchange rate series","XXCFE":"Exchange rate (end of period): currency of area per currency of counterpart area with conversion factor to fixed exchange rate series","XXEXA":"Exchange rate (average): currency of area per currency of counterpart area","XXEXE":"Exchange rate (end of period): currency of area per currency of counterpart area","XXPP":"Purchasing power parities: currency of area per currency of counterpart area","XXX":"Transactions where no currency is involved","YER":"Yemeni rial","YR":"Years","YUM":"Yugoslav dinar (old)","ZAR":"South African rand","ZMK":"Zambian kwacha","ZWD":"Zimbabwe dollar","ZWL":"Fourth zimbabwe dollar","ZWN":"Zimbabwe dollars (old)","ZWR":"Third zimbabwe dollar"}},"CL_BREAK_REASON":{"name":"Code list for concept \u201cBreak in time series\u201d (ID \u201cBREAK_REASON\u201d)","codes":{"METH":{"name":"Methodologies","desc":"Change of methodologies"},"DEF":{"name":"Definition","parent":"METH","desc":"Change in concept(s) and or definition(s)"},"SOURCE":{"name":"Data source","parent":"METH","desc":"Change in data sources"},"CONF":{"name":"Confidentiality","parent":"METH","desc":"Change in confidentiality aspects"},"SAMPLE":{"name":"Sample redesigned","parent":"METH","desc":"Change of sample"},"UNIT":{"name":"Statistical unit(s)","parent":"METH","desc":"Change in statistical unit(s)"},"REF_PER":{"name":"Reference period","parent":"METH","desc":"Change in reference period"},"VAL":{"name":"Valuation methods","parent":"METH","desc":"Change in accounting rules, valuation methods (e.g., from accrual basis to cash basis), etc."},"TRANSF":{"name":"Data transformation","parent":"METH","desc":"Change in methods of data transformation"},"STD":{"name":"Standard(s)","parent":"METH","desc":"Change in international standard(s)"},"WEIGHT":{"name":"Base weight","parent":"METH","desc":"Change in base weight"},"SCOPE":{"name":"Revision of scope or coverage","desc":"Change of scope or coverage"},"CLASS":{"name":"Classifications","desc":"Change of classifications"},"NONSTAT":{"name":"Non-statistical factors","desc":"Change of non-statistical factors"},"ADMIN":{"name":"Administrative procedures","parent":"NONSTAT","desc":"Change in administrative procedures with regard to statistical data from administrative sources"},"CUR":{"name":"Currency","parent":"NONSTAT","desc":"New or revalued currency"},"LEGAL":{"name":"Legal basis","parent":"NONSTAT","desc":"Change of legal and/or institutional basis"},"POL":{"name":"Policy","parent":"NONSTAT","desc":"New or change in economic/fiscal policy"},"_O":{"name":"Other","desc":"Used to cover residual information not contained in other categories of the code list (in some contexts, e.g., classifications, referred to as n.e.s., not elsewhere specified, n.e.c., not elsewhere classified, etc.)"},"_U":{"name":"No data/unknown","desc":"Used to cover unknown reason for the reason for break in time series."}}},"CL_CARD_FCT":{"name":"Card function codelist","codes":{"A":"All","F":"By card with credit function","D":"By card with debit function","E":"By card with delayed debit function","H":"E-money payments","Z":"Not applicable"}},"CL_CPMI_MEASURE":{"name":"CPMI Measure","codes":{"N":"Number","V":"Value"}},"CL_DEVISS_ONUSP":{"name":"Device issuer or on-us payments","codes":{"A":"All issuers and cashless payments","N":{"name":"Non-banks issuers and all cashless payments","parent":"A"},"O":"All issuers and on-us payments only"}},"CL_DEV_STATE_TECH":{"name":"Device state / technology codelist","codes":{"O":{"name":"Present for withdrawals","parent":"P"},"P":{"name":"Device-present, all","parent":"A"},"Q":{"name":"Device-present, paper based","parent":"P"},"R":{"name":"Device-present, other","parent":"P"},"S":{"name":"Device-present, contactless","parent":"P"},"T":{"name":"Device-present, magstripe","parent":"P"},"A":"All","N":{"name":"Device-not-present","parent":"A"}}},"CL_LOCATION":{"name":"Location","codes":{"A":"All","I":{"name":"Inside the country","parent":"A"},"O":{"name":"Outside the country","parent":"A"},"Z":"Not applicable"}},"CL_PAYMT_SPD":{"name":"Payment speed codelist","codes":{"A":"All","F":"Fast payments"}},"CL_TERMINAL_TYPE":{"name":"Type of terminal codelist","codes":{"A":"All","B":"At ATMs","P":"At POS","S":"At bank branches without use of ATMs"}},"CL_TRANS_DIR":{"name":"Transaction direction","codes":{"A":"All","C":{"name":"Cross-border sent","parent":"A"},"D":{"name":"Domestic","parent":"A"},"M":{"name":"At domestic terminals","parent":"D"},"N":{"name":"At domestic ATMs","parent":"D"},"P":{"name":"At domestic POS terminals","parent":"D"},"S":{"name":"At bank branches without ATMs","parent":"D"},"U":{"name":"on us","parent":"D"},"B":{"name":"At ATMs","parent":"A"},"E":"MEMO - Cross-border received","Z":"Not applicable"}},"CL_TRAN_INSTR_TYPE":{"name":"Transaction instrument type","codes":{"A":"Cashless payments, all","B":{"name":"Credit transfers","parent":"A"},"C":{"name":"Direct debits","parent":"A"},"D":{"name":"Cheques","parent":"A"},"E":{"name":"Other payment instruments","parent":"A"},"F":{"name":"Card and e-money payments","parent":"A"},"G":"Card - LEGACY ITEM","H":"E-money - LEGACY ITEM","L":"Withdrawals/deposits, all","M":{"name":"Cash withdrawals","parent":"L"},"N":{"name":"Cash deposits","parent":"L"},"O":{"name":"E-money loading/unloading transactions","parent":"L"},"R":"MEMO - Money remittances"}},"CL_CPMI_CT_UNIT":{"name":"CPMI comparative tables unit","codes":{"A":"In USD","B":"in USD per inhabitant","C":"Per USD, end of period","D":"Per USD, period average","F":"Percent","G":"Annual growth","H":"Annual real growth","I":"In % of GDP","J":"In % of M1","K":"in % of total fast payments","L":"in % of total cashless payments","M":"in % of total withdrawals/deposits","N":"Units","Q":"Per inhabitant","R":"Per million inhabitants","S":"Per transaction","T":"Per day"}},"CL_CT_CARD_TYPES":{"name":"CPMI comparative tables card types","codes":{"A":"Cards, all","B":"Cards, with a cash function","C":"Cards, with a debit function","D":"Cards, with a delayed debit function","E":"Cards, with a credit function","F":"Cards, with an e-money function,all","G":"Cards, with an e-money function, contactless","H":"Cards, with an e-money function, issued by a non-bank","Z":"Not applicable","I":"Cards, with an e-money function, able to initiate device-not-present payments"}},"CL_CT_INDICATORS":{"name":"CPMI comparative tables indicators","codes":{"A":"GDP","B":"Population","C":"GDP per capita","D":"CPI","E":"Exchange rate (domestic currency vis-a-vis USD)","F":"Banknotes and coins","G":"Bank deposits held at the central bank","H":"Interbank deposits","I":"Institutions","J":"Branches or offices","K":"Accounts","M":"Cashless payments","N":"Fast payments","R":"Withdrawals/deposits","T":"Cards","U":"Terminals","V":"Payment transactions","W":"Delivery instructions","X":"All participants","Y":"Directly connected participants","Z":"Clearing members","O":"Securities held","P":"Concentration ratio in terms of volume","Q":"Concentration ratio in terms of value","L":"Payment transactions settled by CLS"}},"CL_CT_INSTR_TYPE":{"name":"CPMI comparative tables instrument types","codes":{"A":"All","B":"Credit transfers","C":"Direct debits","D":"Cheques","E":"Card and e-money payments, all","F":"Card and e-money payments, by card with a debit function","G":"Card and e-money payments, by card with a delayed debit function","H":"Card and e-money payments, by card with a credit function","I":"Card and e-money payments, e-money payments","J":"Other payment instruments","K":"Memo: Money remittances","Z":"Not applicable"}},"CL_CT_TERM_TYPES":{"name":"CPMI comparative tables terminal types","codes":{"A":"POS, all","B":"POS, EFTPOS","C":"POS, EFTPOS and contactless","D":"ATMs, all","E":"ATMs, Cash withdrawal","F":"ATMs, Cash deposit","G":"ATMs, Credit transfer","H":"ATMs, contactless","Z":"Not applicable"}},"CL_CT_W_AND_DEP":{"name":"CPMI comparative tables withdrawals and deposits","codes":{"A":"All","B":"Cash withdrawals with cards issued inside the country, all","C":"Cash withdrawals with cards issued inside the country, at locations inside the country","D":"Cash withdrawals with cards issued inside the country, at locations outside the country","E":"Memo: Cash withdrawals at locations inside the country","F":"With cards issued outside the country","G":"Cash deposits at locations inside and outside the country","H":"With cards issued inside the country at locations inside the country","I":"E-money loading/unloading transactions","Z":"Not applicable"}},"CL_CPMI_SYSTEMS":{"name":"CPMI systems","codes":{"AAAA":"All / Total","AAAP":"All payment systems","AOPS":"All other payment systems","AR1C":"ACyR SA","AR1P":"MEP - Medio Electronico de Pagos","AR1S":"Caja de Valores S.A.","AR2C":"BYMA SA","AR2P":"SNP - Sistema Nacional de Pagos","AR2S":"CRYL - Central de Registro y Liquidacion de Titulos","AR3C":"MAV SA","AR5C":"MAE SA","AR6C":"CRYL","AU1C":"ASX Clear","AU1P":"RITS","AU1S":"ASX Settlement","AU2C":"ASX Clear (Futures)","AU2P":"NPP","AU2S":"Austraclear","BE1P":"T2-BE","BE1S":"NBB clearing","BE2P":"Clearing house","BE2S":"Euroclear Belgium","BE3P":"CEC","BE3S":"Euroclear bank","BE4P":"MCMS (Mastercard Clearing Management System)","BR1C":"BmfBovespa-Equities","BR1P":"STR","BR1S":"BmfBovespa-Equities","BR2C":"BmfBovespa-Derivatives","BR2P":"SITRAF - Large (discontinued)","BR2S":"CETIP","BR3C":"BmfBovespa-Securities","BR3P":"BmfBovespa-FX","BR3S":"SELIC","BR4C":"CETIP","BR4P":"COMPE","BR4S":"BmfBovespa-Central Securities Depository","BR5C":"BmfBovespa-Clearinghouse","BR5P":"SILOC","BR6P":"SITRAF","BR7P":{"name":"SPI","desc":"Instant Payment System"},"CA1C":"ICE NGX","CA1P":"Lynx","CA1S":"CDS","CA2C":"ICE Futures","CA2P":"Automated Clearing Settlement System","CA3C":"CDCC","CA3P":"Interac e-Transfer","CH1C":"SIX x-clear (Total)","CH1P":"Swiss Interbank Clearing","CH1S":"SIX SIS","CH2C":"SIX x-clear of which, in Switzerland","CH3C":"SIX x-clear of which, in Germany","CH4C":"SIX x-clear of which, in United Kingdom","CH5C":"SIX x-clear of which, in Sweden","CH6C":"SIX x-clear of which, in Other","CLSP":"CLS","CN1C":"SD&C","CN1P":"HVPS","CN1S":"SD&C","CN2P":"BEPS","CN2S":"CCDC depository and settlement system","CN3P":"ACH","CN4P":"CUPS","CN5P":"IBPS","DE1C":"Eurex","DE1P":"T2-BBk","DE1S":"Clearstream Banking Frankfurt","DE2C":"Eurex clearing AG","DE2P":"EAF","DE3C":"Eurex clearing AG, of which, in Germany","DE3P":"RPS","DE4P":"STEP2 Card Clearing","ES1C":"BME_Clearing","ES1P":"SNCE","ES1S":"IBERCLEAR","ES2P":"T2-ES","ES3P":"STMP","EU1P":"T2","EU2P":"EURO1 / STEP1","EU3P":"STEP2 XCT Service","EU4P":"STEP2 ICT Service","EU5P":"STEP2 SCT Service","EU6P":"STEP2 SDD B2B Service","EU7P":"STEP2 SDD CORE Service","EU8P":"RT1","EU9P":"Target Instant Payment Settlement (TIPS)","FR1C":"LCH.Clearnet SA (Total)","FR1P":"T2-BdF","FR1S":"Euroclear France","FR2C":"LCH.Clearnet SA, of which, in France","FR2P":"PNS","FR3C":"LCH.Clearnet SA, of which, in Belgium","FR3P":"CORE","FR4C":"LCH.Clearnet SA, of which, in Italy","FR4P":"SEPA-eu","FR5C":"LCH.Clearnet SA, of which, in Netherlands","FR6C":"LCH.Clearnet SA, of which, in the United Kingdom","FR7C":"LCH.Clearnet SA, of which, in Other","GB1C":"ICE Clear Europe","GB1P":"CHAPS Euro","GB1S":"Euroclear UK & Ireland","GB2C":"LME Clear Limited","GB2P":"CHAPS Sterling","GB3C":"CME Clearing Europe Limited","GB3P":"Cheque/credit","GB4C":"LCH.Clearnet Ltd","GB4P":"BACS","GB5P":"Faster Payments Service","GB6P":"LINK","HK1C":"CCASS (HKSCC)","HK1P":"HKD CHATS","HK1S":"CCASS","HK2C":"DCASS (SEOCH)","HK2P":"USD CHATS","HK2S":"CMU","HK3C":"DCASS (HKCC)","HK3P":"EUR CHATS","HK4C":"OCASS (OTC Clear)","HK4P":"HKD Cheques","HK5P":"USD Cheques","HK6P":"HKD Electronic Clearing (ECG)","HK7P":"USD Electronic Clearing (ECG)","HK8P":"RMB CHATS","HK9P":"RMB Cheques","HKAP":"RMB Electronic Clearing (ECG)","HKBP":"HKD Faster Payment System","HKCP":"RMB Faster Payment System","ID1C":"Indonesian Clearing and Guarantee Corporation (KPEI) / E-Clear & E-BOCS","ID1P":"Bank Indonesia Real Time Gross Settlement (BI - RTGS)","ID1S":"Indonesia Central Securities Depository (KSEI) / C - Best","ID2P":"Bank Indonesia National Clearing System","ID2S":"Bank Indonesia Scripless Securities Settlement System (BI-SSSS)","IN1C":"CCIL","IN1P":"RTGS","IN1S":"NDS-SSS","IN2C":"NSCCL","IN2P":"Cheque clearing","IN2S":"NSDL","IN3C":"BOISL","IN3P":"ECS / NECS","IN3S":"CDSL","IN4C":"ICCL","IN4P":"Forex clearing","IN5C":"MCX-SXCCL","IN5P":"NEFT","IN6P":"Card based payments","IN7P":"IMPS","IN8P":"NACH","IN9P":"UPI","IT1C":"CCG","IT1P":"T2-BDI","IT1S":"LDT","IT2P":"BI-COMP","IT2S":"Monte Titoli","IT3S":"EXPRESS II","IT4S":"CAT","JP1C":"Japan Securities Clearing Corporation","JP1P":"BOJ-NET","JP1S":"BOJ-NET JGB Services","JP2C":"Japan Government Bond Clearing Corporation","JP2P":"FXYCS","JP2S":"JASDEC","JP3C":"JASDEC DVP Clearing Corporation","JP3P":"Zengin System","JP4C":"Osaka Securities Exchange","JP4P":"Tokyo Clearing House","JP5C":"Tokyo Financial Exchange","JP5P":"Electronic Clearing House (ECH)","KR1C":"Korea Exchange(KRX)","KR1P":"BOK-Wire+","KR1S":"Korea Securities Depository (KSD)","KR2C":"Korea Securities Depository (KSD)","KR2P":"Check Clearing System","KR3P":"Interbank Shared Networks","MX1C":"CCV","MX1P":"SPEI","MX1S":"Indeval","MX2C":"Asigna","MX2P":"CECOBAN","MX3P":"SPID","NL1C":"EuroCCP (Total)","NL1P":"T2-NL","NL1S":"Euroclear Netherlands","NL2C":"EuroCCP N.V. of which, in Belgium","NL2P":"equensWorldline","NL3C":"EuroCCP N.V. of which, in France","NL4C":"EuroCCP N.V. of which, in Germany","NL5C":"EuroCCP N.V. of which, in Italy","NL6C":"EuroCCP N.V. of which, in Netherlands","NL7C":"EuroCCP N.V. of which, in Sweden","NL8C":"EuroCCP N.V. of which, in Switzerland","NL9C":"EuroCCP N.V. of which, in United Kingdom","NLAC":"EuroCCP N.V. of which, in United States","NLBC":"EuroCCP N.V. of which, in Other","RU1C":"MICEX (discontinued)","RU1P":"BESP System (discontinued)","RU1S":"NDC","RU2C":"RTS CC","RU2P":"VER (discontinued)","RU2S":"DCC","RU3C":"National Settlement Depository (NSD)","RU3P":"MER (discontinued)","RU3S":"National Settlement Depository (NSD)","RU4C":"Central Counterparty National Clearing Centre (CCP NCC)","RU4P":"Payments using letters of advice (discontinued)","RU5P":"NSD Payment System","RU6P":"Bank of Russia Payment System","SA1C":"Saudi Arabia clearing house","SA1P":"SARIE","SA1S":"Tadawul","SA3P":"SADAD Payment system","SE1C":"Stockholmsboersen Clearing","SE1P":"RIX","SE1S":"VPC","SE2C":"SE Nasdaq OMXDM","SE2P":"E-RIX","SE2S":"Euroclear Sweden","SE3P":"Bankgirot","SE4P":"Dataclearing","SE5P":"BIR","SG1C":"CDP","SG1P":"MEPS+(IFT)","SG1S":"SGS","SG2C":"MEPS","SG2P":"SGDCCS","SG2S":"DCSS","SG3P":"USDCCS","SG3S":"CDP","SG4P":"IBG","SG5P":"EFTPOS (discontinued)","SG6P":"FAST","SWFT":"Swift","TR1C":"Takasbank","TR1P":"EFT large","TR1S":"Takasbank","TR2P":"Interbank Card Center","TR2S":"Central Registry Agency","TR3P":"Takasbank Cheque Clearing System","TR3S":"ESTS","TR4P":"EFT retail","TR5P":"Garanti Payment Systems","TR6P":"Paycore Clearing System","TR7P":"Fast System","TR8P":"TAM","US1C":"NSCC","US1P":"CHIPS","US1S":"Fedwire Securities Service","US2C":"FICC","US2P":"Fedwire Funds Service","US2S":"DTC","US3C":"FICC:GSD","US3P":"Cheque clearing: Private","US4C":"FICC:MBSD","US4P":"Cheque clearing: Federal Reserve","US5C":"Nasdaq","US5P":"EPN","US6P":"FedACH","US7P":"NSS","US8P":"Real Time Payments","ZA1P":"SAMOS","ZA1S":"SAFIRES","ZA3P":"SADC-RTGS","ZZZZ":"Not applicable"}},"CL_CPMI_SYST_TYPE":{"name":"Type of CPMI system","codes":{"A":"Payment systems, large-value","B":"Payment systems, retail","C":"Payment systems, fast payments","H":"Payment systems, large-value & retail","I":"Payment systems, large-value & fast payments","J":"Payment systems, retail & fast payments","O":"Payment systems, large-value & retail & fast payments","S":"Swift","T":"Clearing systems, exchange & trading system","U":"Central counterparties/clearing houses","V":"Central securities depositories"}},"CL_DEVICE_FCT":{"name":"Device function","codes":{"A":"Cards, all","B":{"name":"Cards with cash function","parent":"A"},"C":{"name":"Cards with payment function - LEGACY ITEM","parent":"A"},"D":{"name":"Cards with debit function","parent":"C"},"E":{"name":"Cards with delayed debit function","parent":"C"},"F":{"name":"Cards with credit function","parent":"C"},"G":{"name":"Cards with payment function, retailer cards - LEGACY ITEM","parent":"C"},"H":{"name":"Cards with e-money function","parent":"A"},"I":{"name":"Loaded at least once - LEGACY ITEM","parent":"H"},"J":{"name":"Combined debit, cash & e-money - LEGACY ITEM","parent":"H"},"M":"Cash dispensing - LEGACY ITEM","O":{"name":"Cash withdrawal","parent":"M"},"P":{"name":"Cash deposit","parent":"M"},"Q":"Credit transfer","V":"Payment - LEGACY ITEM","U":"Loading / unloading - LEGACY ITEM","K":"E-money payments"}},"CL_DEVICE_ISSUER":{"name":"Device issuer","codes":{"A":"All issuers and cashless payments","N":{"name":"Non-banks issuers and all cashless payments","parent":"A"},"O":"All issuers and on-us payments only"}},"CL_DEVICE_SUB_FCT":{"name":"Device sub functions","codes":{"N":{"name":"Able to initiate device-not-present payments","parent":"A"},"A":"All"}},"CL_DEVICE_TECHNOL":{"name":"Technology used for device","codes":{"A":"All","C":{"name":"Contactless","parent":"A"},"M":{"name":"Magstripe","parent":"A"}}},"CL_DEVICE_TYPE":{"name":"Device types","codes":{"A":"Card","D":"Terminal","E":{"name":"POS, all","parent":"D"},"F":{"name":"EFTPOS","parent":"E"},"P":{"name":"ATM","parent":"D"},"T":{"name":"E-money card terminal - LEGACY ITEM","parent":"D"}}},"CL_CPMI_INDICATORS":{"name":"CPMI indicators","codes":{"A":"Institutions","C":"Branches or offices","F":"Accounts, all","P":{"name":"Internet/PC-linked","parent":"F"},"I":{"name":"Accounts, Internet-linked","parent":"F"}}},"CL_CPMI_INST_TYPE":{"name":"CPMI institution type","codes":{"B1":{"name":"Bank type 1","parent":"BA"},"B2":{"name":"Bank type 2","parent":"BA"},"B3":{"name":"Bank type 3","parent":"BA"},"B4":{"name":"Bank type 4","parent":"BA"},"B5":{"name":"Bank type 5","parent":"BA"},"B6":"Bank type 6","B7":"Bank type 7","B8":"Bank type 8","BA":{"name":"Banks, all","parent":"IA"},"CB":{"name":"Central banks","parent":"IA"},"EA":{"name":"E-money issuers, all","parent":"IA"},"EN":{"name":"E-money issuers - Non-banks","parent":"EA"},"FB":{"name":"Foreign banks","parent":"BA"},"IA":"Institutions, all","N1":{"name":"Non-banks offering storage of value","parent":"NA"},"N2":{"name":"Non-banks relying on storage of value offered by others","parent":"NA"},"NA":{"name":"Non-banks, all","parent":"IA"},"O1":{"name":"Other type 1 - Legacy item","parent":"OA"},"O2":{"name":"Other type 2 - Legacy item","parent":"OA"},"O3":{"name":"Other type 3 - Legacy item","parent":"OA"},"OA":{"name":"Other institutions offering payment services to non-banks","parent":"IA"}}},"CL_CPMI_SUFFIX":{"name":"Custom breakdown","codes":{"01":"Total (notes and coins)","11":"All notes","13":"Notes - denomination 1","15":"Notes - denomination 2","17":"Notes - denomination 3","19":"Notes - denomination 4","21":"Notes - denomination 5","23":"Notes - denomination 6","25":"Notes - denomination 7","27":"Notes - denomination 8","29":"Notes - denomination 9","31":"Notes - denomination 10","33":"Notes - denomination 11","35":"Notes - denomination 12","37":"Notes - denomination 13","39":"Notes - denomination 14","41":"Notes - denomination 15","51":"All coins","53":"Coins - denomination 1","55":"Coins - denomination 2","57":"Coins - denomination 3","59":"Coins - denomination 4","61":"Coins - denomination 5","63":"Coins - denomination 6","65":"Coins - denomination 7","67":"Coins - denomination 8","69":"Coins - denomination 9","71":"Coins - denomination 10","73":"Coins - denomination 11","75":"Coins - denomination 12","R1":"Non applicable","R2":"Non applicable"}},"CL_CPMI_TOPIC":{"name":"Macroeconomic indicator","codes":{"ABBA":"Money stock M1","AFBA":"Currency held by non-banks","AFGA":"Transferable Deposits","AFIA":"Other money supply components of M1","BDCA":"Currency issued","BFHA":"Non-banks currency holdings","BGHA":"Banks' required reserves","BGNA":"Banks' free reserves","BGUA":"Banks' currency holdings","BHBA":"Deposits held by banks","BMPA":"Central bank total refinancing","CESA":"Banks' transferable deposits","RBGA":"GDP at market prices","RZAA":"GDP per capita","UBBA":"Population"}},"CL_CPMI_PART_TYPE":{"name":"Participating types","codes":{"A":"All","D":{"name":"Direct participants, all","parent":"A"},"B":{"name":"Direct participants, Banks","parent":"D"},"C":{"name":"Direct participants, Central bank","parent":"D"},"E":{"name":"Non-banks - LEGACY ITEM","parent":"D"},"F":{"name":"Direct participants, Government","parent":"E"},"G":{"name":"Direct participants, Postal institution","parent":"E"},"H":{"name":"Direct participants, Payment systems, CCPs and SSSs","parent":"E"},"I":{"name":"Direct participants, CCPs/Other CCPs","parent":"H"},"J":{"name":"Direct participants, CSDs","parent":"H"},"K":{"name":"Other financial institutions - LEGACY ITEM","parent":"E"},"L":{"name":"Direct participants, Other","parent":"E"},"N":{"name":"Direct participants, domestic","parent":"A"},"O":{"name":"Direct participants, domestic, Banks","parent":"N"},"P":{"name":"Direct participants, domestic, Central banks","parent":"N"},"Q":{"name":"Direct participants, domestic, CCPs/Other CCPs","parent":"N"},"R":{"name":"Direct participants, domestic, CSDs","parent":"N"},"S":{"name":"Direct participants, domestic, Other","parent":"N"},"T":{"name":"Direct participants, foreign","parent":"A"},"U":{"name":"Direct participants, foreign, Banks","parent":"T"},"V":{"name":"Direct participants, foreign, Central banks","parent":"T"},"W":{"name":"Direct participants, foreign, CCPs/Other CCPs","parent":"T"},"X":{"name":"Direct participants, foreign,CSDs","parent":"T"},"Y":{"name":"Direct participants, foreign, Other","parent":"T"},"Z":{"name":"Indirect participants","parent":"A"},"0":"Members","1":"Sub-members"}},"CL_CPMI_INFO":{"name":"Type of CPMI information","codes":{"C":"Concentration ratio","N":"Netting cycle (RPS)","Z":"Not applicable"}},"CL_CPMI_INSTR_TYP":{"name":"Type of CPMI instrument","codes":{"PA":"Transactions, all","PB":{"name":"Credit transfers","parent":"PA"},"PC":{"name":"Direct debits","parent":"PA"},"PD":{"name":"Cheques","parent":"PA"},"PF":{"name":"Card and e-money payments","parent":"PA"},"PG":{"name":"Card - LEGACY ITEM","parent":"PF"},"PH":{"name":"E-money - LEGACY ITEM","parent":"PF"},"PE":{"name":"Other payment instruments","parent":"PA"},"MM":"Domestic messages","MN":{"name":"Messages sent, all","parent":"MM"},"MO":{"name":"Messages sent, category I","parent":"MN"},"MP":{"name":"Messages sent, category II","parent":"MN"},"MQ":{"name":"Messages received, all","parent":"MM"},"MR":{"name":"Messages received, category I","parent":"MQ"},"MS":{"name":"Messages received, category II","parent":"MQ"},"FA":"Contracts and transactions, all","FB":{"name":"Securities, all","parent":"FA"},"FC":{"name":"Securities, Debt securities","parent":"FB"},"FD":{"name":"Securities, Debt securities, Short-term paper","parent":"FC"},"FE":{"name":"Securities, Debt securities, Bonds","parent":"FC"},"FF":{"name":"Securities, Equity","parent":"FB"},"FG":{"name":"Securities, Other","parent":"FB"},"FH":{"name":"Securities, repurchase transactions","parent":"FB"},"FI":{"name":"Securities, repurchase transactions, Debt securities","parent":"FH"},"FJ":{"name":"Securities, repurchase transactions, Debt securities, Short-term paper","parent":"FI"},"FK":{"name":"Securities, repurchase transactions, Debt securities, Bonds","parent":"FI"},"FM":{"name":"Exchange-traded derivatives","parent":"FA"},"FN":{"name":"Exchange-traded derivatives, Financial futures","parent":"FM"},"FO":{"name":"Exchange-traded derivatives, Financial options","parent":"FM"},"FP":{"name":"Exchange-traded derivatives, Other financial derivatives","parent":"FM"},"FQ":{"name":"Exchange-traded derivatives, Commodity futures","parent":"FM"},"FR":{"name":"Exchange-traded derivatives, Commodity options","parent":"FM"},"FS":{"name":"Exchange-traded derivatives, Other commodity derivatives","parent":"FM"},"FT":{"name":"OTC derivatives","parent":"FA"},"FU":{"name":"OTC Derivatives, Financial futures","parent":"FT"},"FV":{"name":"OTC Derivatives, Financial options","parent":"FT"},"FW":{"name":"OTC Derivatives, Other financial derivatives","parent":"FT"},"FX":{"name":"OTC Derivatives, Commodity futures","parent":"FT"},"FY":{"name":"OTC Derivatives, Commodity options","parent":"FT"},"FZ":{"name":"OTC Derivatives, Other commodity derivatives","parent":"FT"},"DA":"Delivery instructions, all","DD":{"name":"Delivery instructions, DVP trades","parent":"DA"},"DE":{"name":"Delivery instructions, DVP trades, Debt securities","parent":"DD"},"DF":{"name":"Delivery instructions, DVP trades, Debt securities, Short-term paper","parent":"DE"},"DG":{"name":"Delivery instructions, DVP trades, Debt securities, Bonds","parent":"DE"},"DH":{"name":"Delivery instructions, DVP Trades, Equity","parent":"DD"},"DI":{"name":"Delivery instructions, DVP trades, Other","parent":"DD"},"DT":{"name":"Delivery instructions, Free-of-payment trades","parent":"DA"}}},"CL_ADJUST":{"name":"Adjustment codelist","codes":{"0":"Non seasonally adjusted","1":"Seasonally adjusted","A":"Adjusted for breaks","U":"Unadjusted"}},"CL_AREA":{"name":"Reference area code list","codes":{"1X":"ECB","4T":"Emerging market economies (aggregate)","5A":"All reporting economies","5R":"Advanced economies","AE":"United Arab Emirates","AL":"Albania","AR":"Argentina","AT":"Austria","AU":"Australia","BA":"Bosnia and Herzegovina","BE":"Belgium","BE2":"Flanders","BE3":"Wallonia","BG":"Bulgaria","BH":"Bahrain","BM":"Bermuda","BR":"Brazil","BS":"The Bahamas","BY":"Belarus","CA":"Canada","CH":"Switzerland","CL":"Chile","CN":"China","CO":"Colombia","CS":"Serbia & Montenegro","CY":"Cyprus","CZ":"Czechia","DE":"Germany","DEZ1":"West Germany","DEZ2":"East Germany","DK":"Denmark","DZ":"Algeria","EC":"Ecuador","EE":"Estonia","EG":"Egypt","ES":"Spain","FI":"Finland","FR":"France","G2":"G20 economies","GB":"United Kingdom","GR":"Greece","HK":"Hong Kong SAR","HR":"Croatia","HU":"Hungary","ID":"Indonesia","IE":"Ireland","IL":"Israel","IN":"India","IQ":"Iraq","IS":"Iceland","IT":"Italy","JE":"Jersey","JO":"Jordan","JP":"Japan","KR":"Korea","KW":"Kuwait","KZ":"Kazakhstan","LB":"Lebanon","LK":"Sri Lanka","LT":"Lithuania","LU":"Luxembourg","LV":"Latvia","M1":"Multi National","MA":"Morocco","MK":"North Macedonia","MT":"Malta","MX":"Mexico","MY":"Malaysia","NG":"Nigeria","NL":"Netherlands","NO":"Norway","NZ":"New Zealand","OM":"Oman","PA":"Panama","PE":"Peru","PH":"Philippines","PK":"Pakistan","PL":"Poland","PT":"Portugal","PY":"Paraguay","RO":"Romania","RS":"Serbia","RU":"Russia","SA":"Saudi Arabia","SE":"Sweden","SG":"Singapore","SI":"Slovenia","SK":"Slovakia","TH":"Thailand","TN":"Tunisia","TR":"T\u00fcrkiye","TW":"Chinese Taipei","UA":"Ukraine","US":"United States","UY":"Uruguay","VE":"Venezuela","VN":"Vietnam","XM":"Euro area","XW":"World","ZA":"South Africa","_Z":"Not applicable"}},"CL_PP_PRICED_UNIT":{"name":"Price unit","codes":{"0":"Per dwelling","1":"Per square meter","2":"Per 4 square meter","3":"Per cubic meter","4":"Per building","5":"Per property","6":"Pure price","7":"Pure prices","8":"Real price per square meter","9":"Pure price (other)"}},"CL_RE_COVERED_AREA":{"name":"Property covered area","codes":{"0":"Whole country","1":"Whole country excluding capital city","2":"Capital city/biggest city/financial center","3":"Capital/biggest city/financial center and suburbs","4":"Big cities","5":"A big city","6":"Big & medium cities","7":"Medium & small cities","8":"Small cities","9":"Urban areas","A":"Rural area","B":"Changing composition","R":"Region (1)","S":"Region (2)"}},"CL_RE_TYPE":{"name":"Type of real estate","codes":{"0":"All properties","1":"All types of dwellings","2":"Single-family houses","3":"Single-family houses - detached","4":"Single-family houses - terraced","5":"Single-family houses - large","6":"Single-family houses - medium sized","7":"Single-family houses - small","8":"Flats","9":"Multi-dwelling buildings","A":"Commercial property","B":"Commercial property - office premises","C":"Commercial property - retail premises","D":"Office & Retail","G":"Industrial properties","I":"Agricultural properties","K":"Land for all purposes","L":"Land for residential","M":"Land for commercial","N":"Mixed (residential and non-residential) properties","O":"Rented dwellings","P":"Rented flats","Q":"Rented single family houses","R":"All types of non-holidays dwellings","S":"Big flats"}},"CL_RE_VINTAGE":{"name":"Real estate vintage","codes":{"0":"All","1":"Existing","2":"New"}},"CL_SOURCE":{"name":"Data source codelist","codes":{"0":"Central bank","1":"National Statistical Office","2":"Private sector","3":"General Government","4":"Public corporations","5":"IO(Eurostat)"}},"CL_CREDT_GAP_DTYPE":{"name":"Credit gap data type","codes":{"A":"Credit-to-GDP ratios (actual data)","B":{"name":"Credit-to-GDP trend (HP filter)","desc":"The HP filter is a statistical tool used in macroeconomics, especially in real business cycle theory, to remove the cyclical component of a time series."},"C":{"name":"Credit-to-GDP gaps (actual-trend)","desc":"The credit-to-GDP gap is defined as the difference between the credit-to-GDP ratio and its long-run trend, and captures the build-up of excessive credit in a reduced form fashion."}}},"CL_TC_BORROWERS":{"name":"Borrowers","codes":{"C":"Non financial sector","G":"General government","H":{"name":"Households & NPISHs","parent":"P"},"N":{"name":"Non-financial corporations","parent":"P"},"P":"Private non-financial sector"}},"CL_CUR_GROUP":{"name":"Currency group code list","codes":{"A":"All currencies","D":{"name":"Domestic currency","desc":"Currency of the country where the borrower or issuer resides."},"F":{"name":"Foreign currencies","desc":"Non-domestic currency."}}},"CL_ISSUER_BUS":{"name":"Business sector","codes":{"1":"All issuers","2":{"name":"General government","desc":"Sectoral classification that refers collectively to the central government, state government, local government and social security funds. General government excludes the central bank and publicly owned corporations."},"3":"Government (including central bank)","5":"Central government","7":{"name":"Central bank","desc":"Financial institution that exercises control over key aspects of the financial system. Central banks include the following entities: national central banks, central banks of a currency union, currency boards and government-affiliated agencies that are a separate institutional unit and primarily perf"},"A":"Other general government","B":{"name":"Financial corporations","desc":"Entity that is principally engaged in providing financial services, such as financial intermediation, financial risk management or liquidity transformation. Financial corporations include the following entities: central banks, banks and non-bank financial corporations."},"C":{"name":"Financial institutions","desc":"See \"financial corporation\"."},"D":"Other money-issuing corporations","E":"Private banks","F":"Securitisation corporations","G":"Private other financial institutions","H":"Other financial corporations","I":"Public banks","J":{"name":"Non-financial corporations","desc":"Entity whose principal activity is the production of market goods or non-financial services. Non-financial corporations include the following entities: legally constituted corporations, branches of non-resident enterprises, quasi-corporations, notional resident units owning land, and resident non-pr"},"K":"Public other financial institutions","L":"Households & non-profit institutions serving households","M":"Corporate issuers","N":"Memo item: public sector","O":"Private corporates","Q":"Public corporates","S":{"name":"International institutions","desc":"Entity whose members are either national states or other international organisations whose members are national states, and which is established by formal political agreements between its members that have the status of international treaties."}}},"CL_ISSUE_COL":{"name":"Issue collateral type code list","codes":{"A":"All issues","H":"Without collateral","J":"With collateral"}},"CL_ISSUE_CUR":{"name":"Currency of issue","codes":{"AED":"UAE Dirham","AMD":"Armenia Dram","AOA":"Angolan Kwanza","ARS":"Argentine Peso","ATS":"Austrian Schilling","AUD":"Australian Dollar","AWG":"Aruban Florin","AZN":"Azerbaijan manat","BDT":"Taka","BEF":"Belgian Franc","BGN":"Lev","BHD":"Bahraini Dinar","BOB":"Boliviano","BRL":"Brazilian Real","BSD":"Bahamian Dollar","BWP":"Pula","BYR":"Belarusian Ruble","CAD":"Canadian Dollar","CHF":"Swiss Franc","CLF":"Unidades de fomento","CLP":"Chilean Peso","CNY":"Renminbi","COP":"Colombian Peso","CRC":"Costa Rican Colon","CSK":"Czechoslovakia Koruna","CYP":"Cyprus Pound","CZK":"Czech Koruna","DEM":"Deutsche Mark","DKK":"Danish Krone","DOP":"Dominican Peso","DZD":"Algerian Dinar","EEK":"Estonian Kroon","EGP":"Egyptian Pound","ESP":"Spanish Peseta","EU1":"Sum of ECU, Euro and legacy currencies now included in the Euro","EUR":"Euro","FIM":"Finnish Markka","FRF":"French Franc","GBP":"Pound Sterling","GEL":"Georgian Lari","GHS":"Cedi","GRD":"Greek Drachma","GTQ":"Quetzal","HKD":"Hong Kong Dollar","HNL":"Lempira","HRK":"Kuna","HUF":"Forint","IDR":"Rupiah","IEP":"Irish pound","ILS":"New shekel","INR":"Indian Rupee","ISK":"Icelandic krona","ITL":"Italian Lira","JMD":"Jamaican Dollar","JOD":"Jordanian Dinar","JPY":"Yen","KES":"Kenyan Shilling","KGS":"Som","KRW":"Won","KWD":"Kuwaiti Dinar","KZT":"Tenge","LBP":"Lebanese Pound","LKR":"Sri Lanka Rupee","LTL":"Litas","LUF":"Luxembourg Franc","LVL":"Lats","MAD":"Moroccan Dirham","MMK":"Myanmar Kyat","MNT":"Mongolian Tugrik","MOP":"Pataca","MTL":"Maltese Lira","MUR":"Mauritius Rupee","MWK":"Kwacha","MXN":"Mexican Peso","MXV":"Mexican Unidad de Inversion","MYR":"Malaysian Ringgit","MZN":"Mozambique metical","NAD":"Namibia Dollar","NGN":"Naira","NLG":"Dutch Guilder","NOK":"Norwegian Krone","NPR":"Nepalese rupee","NZD":"New Zealand Dollar","OMR":"Rial Omani","OTH":"Other currencies","PEN":"New sol","PHP":"Philippine Peso","PKR":"Pakistan Rupee","PLN":"Zloty","PTE":"Portuguese Escudo","PYG":"Guarani","QAR":"Qatari Rial","RON":"Romanian Leu","RSD":"Serbian Dinar","RUB":"Russian rouble","RWF":"Rwandan Franc","SAR":"Saudi Riyal","SEK":"Swedish Krona","SGD":"Singapore Dollar","SIT":"Tolar","SKK":"Slovak Koruna","THB":"Baht","TND":"Tunisian Dinar","TO1":"Total all currencies","TRY":"New Turkish Lira","TTD":"Trinidad and Tobago Dollar","TWD":"New Taiwan Dollar","TZS":"Tanzanian Shilling","UAH":"Hryvnia","UGX":"Uganda Shilling","USD":"US Dollar","UYU":"Uruguayan peso","UZS":"Sum","VEF":"Bolivar Fuerte","VES":"Bolivar Soberano","VND":"Dong","XAF":"CFA Franc BEAC","XAU":"Fine Ounces","XDR":"SDR","XEU":"European Currency Unit","XOF":"CFA Franc BCEAO","XWX":"ECB / SEC all currencies","Z06":"ECB / SEC Non-MU currencies combined","Z07":"ECB / SEC All currencies other than domestic, Euro and MU currencies","Z08":"ECB / SEC EU 15 currencies","Z12":"ECB / SEC Euro and Greek Drachma","Z16":"ECB / SEC Other currencies except Greek Drachma","ZAR":"Rand","ZMK":"Kwacha","ZMW":"Zambian Kwacha","ZWN":"New Zimbabwe Dollar"}},"CL_ISSUE_RATE":{"name":"Rate Type","codes":{"A":"All interest rates","C":{"name":"Fixed interest rate","desc":"Interest rate that is fixed for the life of the debt instrument or for a certain number of years. At the date of inception, the timing and value of coupon payments and principal repayments are known."},"D":"Asset price-linked","E":"Variable interest rate","F":"Asset priced linked + Interest rate linked variable interest rate","G":"Equity-related","I":"Convertibles","K":"Warrants","M":"Inflation-linked","N":"Interest rate-linked"}},"CL_ISSUE_RISK":{"name":"Issue risk code list","codes":{"A":"All credit ratings","B":"Test"}},"CL_ISSUE_TYPE":{"name":"Issue Type","codes":{"A":"All issue types","C":{"name":"Foreign issues","desc":"Bond denominated in the local currency of the country where the bond is issued, issued by a foreign borrower, and registered for sale to investors in the country where it is issued. For example, a US dollar-denominated bond issued in the US market by an issuer that resides outside the United States."},"E":"Euromarket issues","G":"Not applicable"}},"CL_MARKET":{"name":"Market of issue","codes":{"1":"All markets","A":{"name":"Domestic market","desc":"A security is classified as domestic if all (i) the location of the issue's registration, (ii) the governing law, and (iii) the listing location point to the residence of the immediate issuer."},"C":{"name":"International markets","desc":"A security is classified as international if at least one of (i) the location of the issue's registration, (ii) the governing law, or (iii) the listing location is different from the residence of the immediate issuer."}}},"CL_MEASURE":{"name":"Measure code list","codes":{"A":"Announced issues","C":{"name":"Gross issues","desc":"Face value of securities issued during a specified period."},"E":{"name":"Redemptions","desc":"Return of an investor's principal. Usually occurs at maturity date, but can also occur during the lifetime of a bond (eg partial or early redemption)."},"G":{"name":"Net issues","desc":"Gross issuance during a specified period minus redemptions during the same period. Net issuance may differ from changes in amounts outstanding during the period because the latter may be impacted by changes in market value, foreign exchange movements, debt restructurings and other adjustments."},"I":"Amounts outstanding","K":"Amounts outstanding, remaining maturity up to one year","L":"Revaluations during the period","M":"Other changes in volume","N":"Original average maturity, in years","O":"Remaining average maturity, in years"}},"CL_DER_BASIS":{"name":"Code Basis","codes":{"A":{"name":"Gross - gross","desc":"Not adjusted for inter-dealer double-counting."},"B":{"name":"Net - gross","desc":"Adjusted for local inter-dealer double-counting."},"C":{"name":"Net - net","desc":"Adjusted for local and cross-border inter-dealer double-counting."}}},"CL_DER_INSTR":{"name":"Code Derivatives Instruments","codes":{"A":{"name":"Total (all instruments)","desc":"Sum of all instrument in relevant risk category."},"B":{"name":"Spot","parent":"A","desc":"The exchange of two currencies at a rate agreed on the date of the contract for value or delivery (cash settlement) within two business days."},"C":{"name":"Forwards and swaps","parent":"A","desc":"Total forwards, FX swaps and currency swaps."},"D":{"name":"Outright forwards and FX swaps","parent":"C","desc":"Total forwards and FX swaps."},"E":{"name":"Outright forwards","parent":"D","desc":"Contracts to exchange two currencies at a rate agreed on the date of the contract for value or delivery (cash settlement) at some time in the future (more than two business days later)."},"F":"Forward contracts for diff.","G":{"name":"Non-deliverable forwards","parent":"E","desc":"Non-deliverable forwards are settled in cash (very often in US dollars, or any other pre-agreed currency), without physical delivery of the two underlying currencies at maturity."},"H":{"name":"FX swaps","parent":"D","desc":"Contracts to exchange two currencies (principal amount only) on a specific date at a rate agreed at the time of the conclusion of the contract (the short leg), and a reverse exchange of the same two currencies at a date further in the future at a rate (generally different from the rate applied to th"},"I":{"name":"Currency swaps","parent":"C","desc":"Contracts to exchange streams of interest payments in different currencies for an agreed period of time and potenital exchange of principal amounts in different currencies at a pre agreed exchange rate at maturity."},"J":{"name":"Deliverable forwards","parent":"E","desc":"Forwards with physical delivery of the two underlying currencies at maturity."},"L":{"name":"Forward rate agreements and IR swaps","parent":"A","desc":"Total FRA and IR swaps."},"M":{"name":"Forward rate agreements","parent":"L","desc":"Contracts where the rate to be paid or received on a specific obligation for a set period of time, beginning at some time in the future, is determined at contract initiation."},"N":{"name":"Interest rate swaps","parent":"L","desc":"Contracts to exchange periodic payments related to interest rates on a single currency (fixed for floating or floating for floating based on different indices)."},"O":"Currency swaps - exchange of notional","P":"Currency swaps - only exchange of interest","Q":{"name":"Futures","parent":"A","desc":"Contracts to buy or sell a specific asset at a set future date for a set price."},"R":{"name":"Options","parent":"A","desc":"In FX derivatives segment, contracts that confer the right to buy or sell a currency with another currency at a specified exchange rate during a specified period. In interest rate derivatives segment, option contracts that confer the right to pay or receive a specific interest rate on a predetermine"},"S":{"name":"Options sold","parent":"R","desc":"The right to purchase under OTC option contracts."},"T":{"name":"Options bought","parent":"R","desc":"The right to sell under OTC option contracts."},"U":{"name":"Credit default swaps","desc":"Contracts in which the protection buyer (risk shedder) pays a fixed periodic fee in return for a contingent payment by the protection seller (risk taker), triggered by a credit event on a reference entity. This is total value of all components."},"V":{"name":"Single-name","parent":"U","desc":"CDS where the reference entity is a single named entity, eg a corporation."},"W":{"name":"Multi-name","parent":"U","desc":"CDS referencing more than one name as in portfolio or basket credit default swaps or credit default swap indices"},"X":{"name":"Index products","parent":"W","desc":"Multi-name credit default swap contracts with constituent reference credits and a fixed coupon that are determined by an administrator such Markit (which administers the CDX indexes and the iTraxx indexes)."},"Z":{"name":"Other instruments","parent":"A","desc":"Derivative products where decomposition into individual plain vanilla instruments such as forwards, swaps or options is impractical or impossible."},"1":{"name":"Technical residual (options)","parent":"R","desc":"BIS only. Technical residual."},"0":{"name":"Technical residual (outright forwards)","parent":"E","desc":"BIS only. Technical residual."},"2":{"name":"Technical residual (out. forwards/FX swaps)","parent":"D","desc":"BIS only. Technical residual."},"3":{"name":"Technical residual (Forwards and swaps)","parent":"C","desc":"BIS only. Technical residual."},"4":{"name":"Residual (forward rate and IR swaps)","parent":"L","desc":"BIS only. Technical residual."},"Y":{"name":"Technical residual (total)","parent":"A","desc":"BIS only. Technical residual."},"5":{"name":"Technical residual (Credit default swaps)","parent":"U","desc":"BIS only. Technical residual."},"6":{"name":"Technical residual (Multi-name)","parent":"W","desc":"BIS only. Technical residual."},"K":{"name":"Overnight indexed swaps","parent":"N","desc":"Contracts to exchange periodic payments related to interest rates on a single currency, fixed for floating where the periodic floating payment is based on a designated overnight rate or overnight index rate."},"8":{"name":"Other interest rate swaps","parent":"N","desc":"Contracts to exchange periodic payments related to interest rates on a single currency, fixed for floating or floating for floating based on different indices. Exclude overnight indexed swap."},"7":{"name":"Technical residual (Interest rate swaps)","parent":"N","desc":"BIS only. Technical residual."}}},"CL_EX_METHOD":{"name":"Code Execution Method","codes":{"1":{"name":"Single bank proprietary platforms","parent":"3","desc":"Trading system owned and operated by a bank."},"2":{"name":"Voice broker","parent":"3","desc":"Trade agreed by a voice."},"3":{"name":"Total (all methods)","desc":"Sum of all executions methods."},"4":{"name":"Voice - direct","parent":"3","desc":"Trades originated in person, by phone, by telefax or through general messaging systems, regardless of how trades are subsequently matched. Not intermediated by a third party."},"5":{"name":"Voice - indirect","parent":"3","desc":"Trade agreed by a voice method and intermediated by a third party (eg a voice broker)."},"6":{"name":"Electronic - direct - single bank system","parent":"3","desc":"Electronic trading system owned and operated by a bank for both in-house use and other banks and non-bank clients on a \u201cwhite label\u201d/prime brokerage basis (Autobahn, BARX, Velocity, UBS Neo)."},"7":{"name":"Electronic - direct - other","parent":"3","desc":"Other direct electronic trading systems. For example, the client receives a dedicated price stream directly from the reporting dealer (Bloomberg Chat, Refinitiv Conversational Dealing, direct API price streams)."},"8":{"name":"Electronic - indirect - Reuters EBS","parent":"3","desc":"Electronic trading platforms that have historically been geared towards the non-disclosed inter-dealer market; plus any other central limit order book (CLOB) venues that do not allow partitioning of liquidity via the use of customised tags (Refinitiv Matching, EBS Market, EBS Hedge Ai, BGC mid, FXal"},"9":{"name":"Electronic - indirect - other ECN","parent":"W","desc":"Subset of electronic - indirect - disclosed."},"K":{"name":"Interdealer direct","parent":"3","desc":"Trades executed between two dealers where both dealers participate in the triennial survey and are not intermediated by a third party."},"L":{"name":"Customer direct","parent":"3","desc":"Trades executed between the reporting dealer and either a customer or a non-reporting dealer that are not intermediated by a third party."},"M":{"name":"Electronic Broking System","parent":"3","desc":"Trades executed via automated order matching system for foreign exchange dealers."},"N":{"name":"Multi-bank dealing systems","parent":"3","desc":"Trades executed via a single-bank proprietary platform or a multi-bank dealing system."},"X":{"name":"Electronic - indirect - Dark pools","parent":"W","desc":"Subset of electronic - indirect - disclosed."},"Y":{"name":"Electronic - indirect - other","parent":"3","desc":"Undistributed electronic - indirect."},"Z":{"name":"Undistributed","parent":"3","desc":"Not allocated to any execution method."},"0":"Technical Residuals","W":{"name":"Electronic - indirect - Disclosed venues","parent":"3","desc":"Multi-bank dealing systems that facilitate trading on a disclosed basis or that allow for price discrimination."},"R":"Technical residual (Electronic - indirect - Disclosed venues)"}},"CL_MARKET_RISK":{"name":"Code Market Risk","codes":{"A":{"name":"Total (all risk categories)","desc":"Sum of all risk categories."},"B":{"name":"Foreign exchange","parent":"C","desc":"Contracts to exchange currencies in the forward market."},"C":{"name":"Foreign exchange including gold","parent":"A","desc":"Contracts to exchange currencies or gold in the forward market."},"D":{"name":"Interest rate","parent":"A","desc":"Contracts related to an interest-bearing financial instrument whose cash flows are determined by referencing interest rates or another interest rate contract."},"E":{"name":"Equity","parent":"A","desc":"Contracts that have a return, or a portion of their return, linked to the price of a particular equity or to an index of equity prices."},"F":{"name":"Single equity","parent":"E","desc":"Contracts that have a return, or a portion of their return, linked to the price of a particular equity."},"G":{"name":"Equity index","parent":"E","desc":"Contracts that have a return, or a portion of their return, linked to the price of an index of equities."},"J":{"name":"Commodities","parent":"A","desc":"Contracts that have a return, or a portion of their return, linked to the price of, or to a price index of, a commodity such as a precious metal (other than gold), petroleum, lumber or agricultural products."},"K":{"name":"Precious metals","parent":"J","desc":"Sum of all precious metals."},"L":{"name":"Gold","parent":"J","desc":"Gold."},"M":{"name":"Other precious metals","parent":"J","desc":"Any precious metal other than gold."},"N":"Non-precious metals","O":"Agricultural commodities","P":"Energy products","Q":"Other commodities","T":{"name":"Credit Derivatives","parent":"A","desc":"Contracts in which the payout is linked primarily to some measure of the creditworthiness of a particular reference credit."},"U":{"name":"Other derivatives","parent":"A","desc":"Contract that do not involve an exposure to foreign exchange, interest rate, equity, commodity or credit risk."},"Z":{"name":"Unallocated","parent":"A","desc":"Contract that was not allocated to any risk category."},"0":{"name":"Technical residual (total)","parent":"A","desc":"BIS only. Technical residual."},"1":"Technical residual (Non-souvereigns)","2":"Technical residual (Portfolio or structured)","3":"Technical residual (Securitised products)"}},"CL_OD_TYPE":{"name":"Measure (notional amount, credit exposures, market values)","codes":{"A":{"name":"Outstanding - notional amounts","desc":"Nominal or notional amounts outstanding are the gross nominal or notional value of all deals concluded and not yet settled at the reporting date."},"B":{"name":"Gross positive market values","parent":"D","desc":"Gross positive market value of a dealer's outstanding contracts is the sum of the replacement values of all contracts that are in a current gain position to the reporter at current market prices (and therefore, if they were settled immediately, would represent claims on counterparties)."},"C":{"name":"Gross negative market values","parent":"D","desc":"Gross negative market value is the sum of the values of all contracts that have a negative value on the reporting date (ie those that are in a current loss position and therefore, if they were settled immediately, would represent liabilities of the dealer to its counterparties)."},"D":{"name":"Outstanding - gross market values","desc":"Sum of the absolute values of all outstanding derivatives contracts with either positive or negative replacement values evaluated at market prices prevailing on the reporting date. The term \"gross\" indicates that contracts with positive and negative replacement values with the same counterparty are "},"E":{"name":"Gross positive credit exposure","parent":"H","desc":"Corresponds to the market value after taking account of legally enforceable bilateral netting agreements (for contracts that have a positive market value)."},"F":{"name":"Gross negative credit exposure","parent":"H","desc":"Corresponds to the market value after taking account of legally enforceable bilateral netting agreements (for contracts that have a negative market value)."},"H":{"name":"Outstanding - gross credit exposure","desc":"Gross market value minus amounts netted with the same counterparty across all risk categories under legally enforceable bilateral netting agreements. Gross credit exposure provides a measure of exposure to counterparty credit risk (before collateral)."},"I":"Premia collected","J":"Premia paid","K":{"name":"Turnover - notional amounts","desc":"Total amount of derivatives contracts traded in a period."},"L":{"name":"Outstanding - number of contracts","desc":"Number of contracts outstanding at period end."},"M":{"name":"Turnover - number of contracts","desc":"Turnover expressed in number of contracts during a period."},"Q":{"name":"Herfindahl index","desc":"Measure of market concentration, defined as the sum of the squared market shares of each individual entity. The index ranges from 0 to 10,000. If only one entity dominates the market, the measure will have the (maximum) value of 10,000."},"R":{"name":"Number of dealers","desc":"Number of reporting dealers providing the data."},"S":{"name":"Notional amounts - bought","desc":"Notional amounts which the reporting bank has the right to purchase under OTC option contracts."},"T":{"name":"Notional amounts - sold","desc":"Notional amounts which the reporting bank has the right to sell under OTC option contracts."},"U":{"name":"Turnover - notional amounts (daily average)","desc":"Total amount of derivatives contracts traded in a day, calculated as the amount traded over a specified time period divided by the number of business days within this period."},"V":{"name":"Turnover - number of contracts (daily average)","desc":"Turnover expressed in daily average number of contracts during the reporting period."},"W":"Carrying amounts - gross","X":"Carrying amounts - net","Y":"Short sales - Market value","G":"Free Credit Balances - notional amounts"}},"CL_RATING":{"name":"Code Rating","codes":{"0":"Technical residual (total)","1":"Technical residual (Investment grade)","2":"Total gross financial obligations settled","3":"Settlement via applicable PvP systems (gross)","4":"Settlement subject to netting (gross)","_":"Technical residual - level 4","5":"o/w net amount (value after netting)","6":"Gross amounts settled intragroup and settled with an internal risk mitigation mechanism","7":"o/w Inter-branch settlement (gross)","8":"o/w Inter-affiliate settlement (gross)","9":"o/w amounts settled over bank accounts where the reporting dealer controls the timing of settlement (gross)","A":{"name":"Total (all ratings)","desc":"Sum of all ratings."},"B":{"name":"Investment grade","parent":"A","desc":"Investement grade (AAA to BBB)."},"C":"Trades settled on a gross bilateral basis","D":{"name":"AAA / AA","parent":"B","desc":"Upper investment-grade (AAA or AA)."},"F":{"name":"A / BBB","parent":"B","desc":"Lower investment-grade (A or BBB)."},"G":"o/w trades eligible for applicable PvP systems but settled on a gross bilateral basis","H":{"name":"Below investment grade","parent":"A","desc":"Non-investment grade (BB or below)."},"I":{"name":"Total turnover","desc":"Sum of April turnover for settlements."},"J":{"name":"Turnover to be settled with a single payment (ie non-deliverable)","parent":"I","desc":"Part of April turnover that should be settled with a single payment."},"K":{"name":"Turnover to be settled with two payments (ie spot and forwards)","parent":"I","desc":"Part of April turnover that should be settled with two payments."},"L":{"name":"Turnover to be settled with four payments (ie swaps)","parent":"I","desc":"Part of April turnover that should be settled with four payments."},"M":{"name":"Two sided turnover subject to netting (before netting)","parent":"I","desc":"Sum of April turnover that should be settled with two or four payments."},"N":{"name":"Net payable amount of two sided turnover subject to netting (after netting)","desc":"Turnover to be settled results from April and previous months turnovoer after netting in April."},"O":{"name":"Payment versus payment (PvP = c1 + c2 + c3)","desc":"Payment versus payment (PVP) settlements."},"P":{"name":"Via CLS","parent":"O","desc":"Settled via CLS (PVP)."},"Q":{"name":"Via other PvP or equivalent settlement methods","parent":"O","desc":"Settled via other PVP methods."},"R":{"name":"Via \"same clearer\" or \"on-us\" accounts without exposure to settlement risk","parent":"O","desc":"Same clearer (or on-us) without exposure to settlement risk (PVP)."},"S":{"name":"Non-PvP","desc":"Other than payment versus payment settlements (non-PVP)."},"T":{"name":"Via \"same clearer\" or \"on-us\" accounts with exposure to settlement risk","parent":"S","desc":"Same clearer (or on-us) with exposure to settlement risk (non-PVP)."},"U":"o/w trades not eligible for applicable PvP systems and settled on a gross bilateral basis","@":"Technical residual - level U","V":"o/w currency pair is not eligible for applicable PvP systems (gross)","W":"o/w trade type is not eligible for applicable PvP systems (gross)","X":"o/w counterparty is not a member (direct or indirect) of applicable PvP systems (gross)","Y":"Trades that had an original settlement date in the reporting period but failed to settle during the reporting period (gross)","Z":{"name":"Non-rated","parent":"A","desc":"Not rated or no data about rating."},"E":"Other"}},"CL_SECTOR_CPY":{"name":"Code Counterparty sector","codes":{"A":{"name":"Total (all counterparties)","desc":"Sum of all counterparties."},"B":{"name":"Reporting dealers","parent":"A","desc":"Financial institutions that participate as reporters in the Triennial Survey."},"C":{"name":"Other financial institutions","parent":"A","desc":"Financial institutions that are not classified as \u201creporting dealers\u201d in the survey."},"D":{"name":"Non-reporting banks","parent":"C","desc":"Smaller or regional commercial banks, publicly owned banks, securities firms or investment banks that are not directly participating as reporting dealers."},"E":{"name":"Institutional investors","parent":"C","desc":"Institutional investors such as mutual funds, pension funds, insurance and reinsurance companies and endowments"},"F":{"name":"Hedge funds and proprietary trading firms","parent":"C","desc":"Investment funds and various types of money managers, including commodity trading advisers. Proprietary trading firms (PTFs) that invest, hedge or speculate for their own account. Also include PTFs that employ their technology for the purpose of electronic market-making and specialised \u201chigh frequen"},"G":{"name":"Official sector financial institutions","parent":"C","desc":"Central banks, sovereign wealth funds, international financial institutions of the public sector (BIS, IMF etc), development banks and agencies."},"H":{"name":"Undistributed","parent":"C","desc":"Counterparties not classified in any other financials subgroup."},"K":{"name":"Central Counterparties","parent":"C","desc":"Central counterparties are entities that interpose between counterparties to contracts traded in one or more financial markets, becoming the buyer to every seller and the seller to every buyer."},"L":{"name":"Banks and securities firms","parent":"C","desc":"Subset of other financial used in CDS reporting."},"M":{"name":"Insurance and financial guaranty firms","parent":"C","desc":"Subset of other financial used in CDS reporting."},"N":{"name":"SPVs, SPCs or SPEs","parent":"C","desc":"Subset of other financial used in CDS reporting."},"O":{"name":"Hedge funds","parent":"C","desc":"Subset of other financial used in CDS reporting."},"P":{"name":"Other residual financial institutions","parent":"C","desc":"All remaining financial institutions."},"U":{"name":"Non-financial customers","parent":"A","desc":"Mainly non-financial counterparties, such as corporations and non-financial government entities."},"V":{"name":"Prime brokered","parent":"A","desc":"Prime brokers are defined as institutions (usually large and highly rated banks) facilitating trades for their clients (often institutional funds, hedge funds and other proprietary trading firms). They enable those clients to conduct trades, subject to credit limits, with a group of predetermined th"},"W":{"name":"Retail-driven","parent":"A","desc":"Trades initiated by retail investors, where \u201cretail investors\u201d refers to private individuals executing, on their own behalf (ie not for any institution), speculative, leveraged and cash-settled foreign exchange transactions."},"X":{"name":"Related Party Trades","parent":"A","desc":"Trades of reporting dealers with their subsidiaries and affiliated firms."},"Y":{"name":"Own branches and subsidiaries","parent":"A","desc":"Entity owned or otherwise controlled by a banking group, including head office, branch office or subsidiary."},"Z":{"name":"Non-reporters","parent":"A","desc":"Entities that to not participate in the survey."},"0":"Technical residual (total)","1":"Technical residual (other financial institutions)","Q":{"name":"Non-bank electronic market-makers","parent":"A","desc":"Group of trades in disclosed market making by principal trading firms."},"R":{"name":"Other customers","parent":"A","desc":"Group of trades prime brokered for anonymous PTF trading."},"2":"Technical residual (Prime brokered)","I":{"name":"Back-to-back trades","parent":"A","desc":"Trades where the liabilities, obligations and rights of the second deal are exactly the same as those of the original deal. They are normally conducted between affiliates, but can also involve other unrelated entities."},"J":{"name":"Compression trades","parent":"A","desc":"Compression is a process of replacing multiple offsetting derivatives contracts with fewer deals of the same net risk to reduce the notional value of the portfolio."}}},"CL_SECTOR_UDL":{"name":"Code Risk Category","codes":{"A":{"name":"Total (all sectors)","desc":"Sum of CDS underlying."},"B":{"name":"Sovereigns","parent":"A","desc":"CDS underlying issued by governments."},"C":{"name":"Non-sovereigns","parent":"A","desc":"CDS underlying not issued by governments."},"F":{"name":"Financial firms","parent":"C","desc":"CDS underlying issued by financial institutions."},"G":{"name":"Non-financial firms","parent":"C","desc":"CDS underlying issued by non-financial institutions."},"J":{"name":"Portfolio or structured","parent":"C","desc":"CDS underlying is a portfolio or a collection of structured products."},"K":{"name":"Securitised products","parent":"J","desc":"CDS underlying is a structured product."},"L":{"name":"ABS & MBS","parent":"K","desc":"CDS underlying is ABS or MBS."},"M":{"name":"Other","parent":"K","desc":"CDS underlying is any other structured product that is not ABS or MBS."},"N":{"name":"Multiple Sectors","parent":"J","desc":"CDS underlying is a portfolio of instruments by multiple sectors."},"0":"Technical residual (total)","1":"Error for C","2":"Error for J","3":"Error for K"}},"CL_EER_BASKET":{"name":"Effective exchange rates basket code list","codes":{"B":"Broad (64 economies)","N":"Narrow (27 economies)"}},"CL_EER_TYPE":{"name":"Effective exchange rates type code list","codes":{"N":{"name":"Nominal","desc":"Weighted average of bilateral exchange rates. BIS-calculated NEERs are geometric trade-weighted averages of bilateral exchange rates. An increase in the index indicates an appreciation. See also \"effective exchange rate\" and \"real effective exchange rate\"."},"R":{"name":"Real","desc":"NEER adjusted by some measure of relative prices or costs; changes in the REER thus take into account both nominal exchange rate developments and the inflation differential vis-\u00e0-vis trade partners. BIS-calculated REERs are adjusted by relativeconsumer prices. An increase in the index indicates an a"}}},"CL_L_POS_TYPE":{"name":"Location","codes":{"A":"All","N":{"name":"Cross-border","desc":"Position on a non-resident - for example, claim on or liability to a counterparty located in a country other than the country where the banking office that books the position is located."},"R":{"name":"Local","desc":"Claim on or liability to a counterparty located in the same country as the banking office that books the position. Opposite of a \"cross-border position\"."},"U":"Unallocated","I":"Cross-border & Local in FCY","F":{"name":"Foreign collateral","parent":"A","desc":"SFTs whose collateral that has been issued by an entity located in a country other than reporting country"},"D":{"name":"Domestic collateral","parent":"A","desc":"SFTs whose collateral that has been issued by an entity located in the same country as the reporting country"},"Z":{"name":"Not applicable","parent":"A","desc":"SFTs for which the collateral position type breakdown does not apply or is not available"}}},"CL_L_BANK_TYPE":{"name":"Reporting Bank Type","codes":{"A":"All reporting banks/institutions (domestic, foreign, consortium and unclassified)","B":{"name":"Foreign branches","desc":"Unincorporated entity wholly owned by another entity."},"D":{"name":"Domestic banks","desc":"Bank whose controlling parent is located in the respective BIS reporting country - for example, a bank with a controlling parent located in the United States is a US domestic bank."},"S":{"name":"Foreign subsidiaries","desc":"A separately incorporated entity in which another entity has a majority or full participation."},"U":{"name":"Consortium and unclassified","desc":"A consortium bank is a bank owned by two or more entities, in which no single entity has a controlling interest."}}},"CL_L_CURR_TYPE":{"name":"Currency type","codes":{"A":"All currencies (=D+F+U)","D":{"name":"Domestic currency (ie currency of bank location country)","desc":"The domestic currency refers to the currency that is legal tender in the reporting country, which is typically the currency issued by the reporting country\u2019s central bank or monetary authority. In the LBS, the terms \u201cdomestic currency\u201d and \u201clocal currency\u201d are used interchangeably. By contrast, in t"},"F":{"name":"Foreign currency (ie currencies foreign to bank location country)","desc":"Currencies other than domestic currency (or local currency) are foreign currencies."},"U":"Unclassified currency"}},"CL_ADJUSTMENT":{"name":"Adjustment indicator","codes":{"_Z":"Not applicable","T":"Trend","C":"Trend-cycle data, calendar adjusted","R":"Trend-cycle data, not calendar adjusted","K":{"name":"Calendar component","desc":"Synonyms: Calendar effects; calendar factors"},"X":{"name":"Seasonal component","desc":"Synonyms: Seasonal effects; seasonal factors"},"M":{"name":"Seasonal and calendar components","desc":"Synonyms: Seasonal and calendar effects; seasonal and calendar factors"},"I":{"name":"Irregular component","desc":"Synonym: Irregular effects"},"N":{"name":"Neither seasonally adjusted nor calendar adjusted data","desc":"Synonyms: Raw data; unadjusted data"},"S":"Seasonally adjusted data, not calendar adjusted","W":"Calendar adjusted data, not seasonally adjusted","Y":"Calendar and seasonally adjusted data"}},"CL_COFOG":{"name":"COFOG","codes":{"_T":"Total","GF01":"General public services","GF0101":"Executive and legislative organs, financial and fiscal affairs, external affairs","GF0102":"Foreign economic aid","GF0103":"General services","GF0104":"Basic research","GF0105":"R&D General public services","GF0106":"General public services n.e.c.","GF0107":"Public debt transactions","GF0108":"Transfers of a general character between different levels of government","GF02":"Defence","GF0201":"Military defence","GF0202":"Civil defence","GF0203":"Foreign military aid","GF0204":"R&D Defence","GF0205":"Defence n.e.c.","GF03":"Public order and safety","GF0301":"Police services","GF0302":"Fire-protection services","GF0303":"Law courts","GF0304":"Prisons","GF0305":"R&D Public order and safety","GF0306":"Public order and safety n.e.c.","GF04":"Economic affairs","GF0401":"General economic, commercial and labour affairs","GF0402":"Agriculture, forestry, fishing and hunting","GF0403":"Fuel and energy","GF0404":"Mining, manufacturing and construction","GF0405":"Transport","GF0406":"Communication","GF0407":"Other industries","GF0408":"R&D Economic affairs","GF0409":"Economic affairs n.e.c.","GF05":"Environment protection","GF0501":"Waste management","GF0502":"Waste water management","GF0503":"Pollution abatement","GF0504":"Protection of biodiversity and landscape","GF0505":"R&D Environmental protection","GF0506":"Environmental protection n.e.c.","GF06":"Housing and community amenities","GF0601":"Housing development","GF0602":"Community development","GF0603":"Water supply","GF0604":"Street lighting","GF0605":"R&D Housing and community amenities","GF0606":"Housing and community amenities n.e.c.","GF07":"Health","GF0701":"Medical products, appliances and equipment","GF0702":"Outpatient services","GF0703":"Hospital services","GF0704":"Public health services","GF0705":"R&D Health","GF0706":"Health n.e.c.","GF08":"Recreation, culture and religion","GF0801":"Recreational and sporting services","GF0802":"Cultural services","GF0803":"Broadcasting and publishing services","GF0804":"Religious and other community services","GF0805":"R&D Recreation, culture and religion","GF0806":"Recreation, culture and religion n.e.c.","GF09":"Education","GF0901":"Pre-primary and primary education","GF0902":"Secondary education","GF0903":"Post-secondary non-tertiary education","GF0904":"Tertiary education","GF0905":"Education not definable by level","GF0906":"Subsidiary services to education","GF0907":"R&D Education","GF0908":"Education n.e.c.","GF10":"Social protection","GF1001":"Sickness and disability","GF1002":"Old age","GF1003":"Survivors","GF1004":"Family and children","GF1005":"Unemployment","GF1006":"Housing","GF1007":"Social exclusion n.e.c.","GF1008":"R&D Social protection","GF1009":"Social protection n.e.c.","_Z":"Not applicable","GF1002_3":"Old age and survivors"}},"CL_CUST_BREAKDOWN":{"name":"Custom breakdown code list (NA)","codes":{"_T":"Total","C_XX":"Social instruments (use of proceeds), assurance level unspecified, standard unspecified","C01":"Custom 01","C02":"Custom 02","C03":"Custom 03","C04":"Custom 04","C05":"Custom 05","C06":"Custom 06","C07":"Custom 07","C08":"Custom 08","C09":"Custom 09","C10":"Custom 10","C11":"Custom 11","C12":"Custom 12","C13":"Custom 13","C14":"Custom 14","C15":"Custom 15","C16":"Custom 16","C17":"Custom 17","C18":"Custom 18","C19":"Custom 19","C20":"Custom 20","C21":"Custom 21","C22":"Custom 22","C23":"Custom 23","C24":"Custom 24","C25":"Custom 25","C26":"Custom 26","C27":"Custom 27","C28":"Custom 28","C29":"Custom 29","C30":"Custom 30","C31":"Custom 31","C32":"Custom 32","C33":"Custom 33","C34":"Custom 34","C35":"Custom 35","C36":"Custom 36","C37":"Custom 37","C38":"Custom 38","C39":"Custom 39","C40":"Custom 40","C41":"Custom 41","C42":"Custom 42","C43":"Custom 43","C44":"Custom 44","C45":"Custom 45","C46":"Custom 46","C47":"Custom 47","C48":"Custom 48","C49":"Custom 49","C50":"Custom 50","C51":"Custom 51","C52":"Custom 52","C53":"Custom 53","C54":"Custom 54","C55":"Custom 55","C56":"Custom 56","C57":"Custom 57","C58":"Custom 58","C59":"Custom 59","C60":"Custom 60","C61":"Custom 61","C62":"Custom 62","C63":"Custom 63","C64":"Custom 64","C65":"Custom 65","C66":"Custom 66","C67":"Custom 67","C68":"Custom 68","C69":"Custom 69","C70":"Custom 70","C71":"Custom 71","C72":"Custom 72","C73":"Custom 73","C74":"Custom 74","C75":"Custom 75","C76":"Custom 76","C77":"Custom 77","C78":"Custom 78","C79":"Custom 79","C80":"Custom 80","C81":"Custom 81","C82":"Custom 82","C83":"Custom 83","C84":"Custom 84","C85":"Custom 85","C86":"Custom 86","C87":"Custom 87","C88":"Custom 88","C89":"Custom 89","C90":"Custom 90","C91":"Custom 91","C92":"Custom 92","C93":"Custom 93","C94":"Custom 94","C95":"Custom 95","C96":"Custom 96","C97":"Custom 97","C98":"Custom 98","C99":"Custom 99","FAM":"Government assistance to the financial sector","FC":"EDP Financial Crisis concept","FND":"Direct Investment","FND1":"Direct investor in direct investment enterprises","FND1D2":"Direct investment excluding direct investment between fellow enterprises","FND2":"Direct investment enterprises in direct investor","FND3":"Direct Investment between fellow enterprises","FNF":"Financial Derivatives and Employee Stock Options","FNO":"Other Investment","FNP":"Portfolio Investment","FNR":"Reserve Assets","FNTXD":"All functional categories (total) excluding Direct Investment","G_XX":"Green instruments (use of proceeds), assurance level unspecified, standard unspecified","L":"LCD table","L_EFSF":"EFSF guarantor (Intergovernmental lending ) - LCD concept","L_I":{"name":"Imputed - LCD concept","desc":"L_I = L_ICP + L_ICL"},"L_ICC":"Cash collateral related to financial derivatives - LCD concept","L_ICL":"Cashless at inception - LCD concept","L_ICP":{"name":"Cash payment at inception - LCD concept","desc":"L_ICP = L_ICC + L_ISL"},"L_IDBK":"Rerouted from Development Banks - LCD concept","L_IPEC":"Public-Private Partnership (PPP), EPC and Concessions on GG BS - LCD concept","L_IRXR":"Other imputations or rearrangements - LCD concept","L_ISL":"Loan component in Off Market Swaps - LCD concept","L_IT":"Long Term payables, including trade credits (F.89 reclassified in F.4) - LCD concept","L_LSM":{"name":"Assistance [INSTR_ASSET] under [REF_AREA] stability mechanism - LCD concept","desc":"In combination with INSTR_ASSET F4 and REF_AREA 4D the code should be read as \"Assistance loan under EU stability mechanism\""},"L_N_F":"Nominal/face value difference - LCD concept","L_OA":"Methodological adjustments to EDP perimeter - LCD concept","L_S":"Serviced - LCD concept","L_X":"Not allocated/unallocated - LCD concept","L_XLSM":{"name":"[INSTR_ASSET] other than Assistance [INSTR_ASSET] under [REF_AREA] stability mechanism (L_LSM) - LCD concept","desc":"In combination with INSTR_ASSET F4 and REF_AREA 4D the code should be read as \"Loan other than Assistance loan under EU stability mechanism (L_LSM)\""},"L_XX":"Sustainability-linked instruments, assurance level unspecified, standard unspecified","S_XX":"Sustainable instruments (use of proceeds), assurance level unspecified, standard unspecified","VFCA":"Looking through via financing conduits, extended concept (direct + indirect)","VFCI":"Looking through (via) financing conduits - indirect approach","VIFA":"Looking through via investment fund shares, total (direct + indirect holdings)","VIFI":"Looking through (via) non-MMF investment fund shares - indirect approach","VIFM":"Looking through (via) money market fund shares - indirect approach","Z_XX":"Not green, not social, not sustainable and not sustainability-linked instruments, assurance level unspecified, standard unspecified"}},"CL_EDP_WBB":{"name":"EDP working balance basis","codes":{"C":"Cash","A":"Accrual","M":"Mixed","_O":"Other"}},"CL_GFS_ECOFUNC":{"name":"GFS economic function","codes":{"C":"Consumption tax","LEYRS":"Labour taxes on Employers","LEES":"Labour taxes on Employees","LNON":"Labour tax on the non-employed (pensioners/ unemployed)","KIC":"Capital tax on the income of corporations","KIH":"Capital tax on the income of households","KISE":"Capital tax on the income of self-employed","KS":"Capital tax on Stocks of Wealth","SPLIT1":"PIT Split between Lees, Lnon, KIH, KISe","SPLIT2":"Split between Lnon and KISe","_T":"Total","_Z":"Not applicable"}},"CL_GFS_TAXCAT":{"name":"GFS tax category","codes":{"_T":"Total","AT":"Alcohol and tabacco tax","E":"Energy tax","O":"Other taxes on property","P":"Pollution tax","RP":"Recurrent taxes on immovable property","RS":"Resource tax","T":"Transport tax"}},"CL_INSTR_ASSET":{"name":"Instrument and Assets Classification","codes":{"_Z":"Not applicable","F":{"name":"Total financial assets/liabilities","desc":"F= F1+F2+F3+F4+F5+F6+F7+F8; In some data flow definitions the integrity rules are shown in a different format in order to explain to users their practical implementation. However, in none of the cases double counting is allowed."},"F_G":"Liabilities and assets outside general government under guarantee","F_NG":{"name":"Total assets/liabilities (financial and gross non-financial)","desc":"F_NG=F+NG"},"F_NN":{"name":"Total assets/liabilities (financial and net non-financial)","desc":"F_NN=F+NN"},"F_SPV":"Liabilities related to special purpose entities (EDP-FC concept)","F_SPVG":"Guarantees provided to special purpose vehicles (FAM concept)","F1":"Monetary gold and SDRs","F11":{"name":"Monetary gold","desc":"F11=F11A+F11B"},"F11A":"Gold bullion","F11B":"Unallocated gold accounts","F11Z":"Monetary gold, of which gold under swap for cash collateral","F12":"SDRs","F12FR":"SDRs, fixed rate","F12VR":"SDRs, variable rate","F2":{"name":"Currency and deposits","desc":"F2=F21+F22+F29"},"F2_F4":{"name":"Loans, currency and deposits: Currency and deposits + Loans","desc":"F2_F4 = F2+F4"},"F21":"Currency","F22":{"name":"Transferable deposits","desc":"F22=F221+F229"},"F221":"Inter-bank positions","F221C":"Inter-bank positions, of which intra-Eurosystem Technical claims","F221T":"Inter-bank positions, of which TARGET accounts","F229":"Other transferable deposits","F2291":"Other transferable deposits, except overnight deposits","F29":{"name":"Other deposits","desc":"F29=F29A+F29B+F29C+F29E"},"F29A":"Deposits with agreed maturity","F29B":"Deposits redeemable at notice","F29C":"Repurchase agreements","F29E":"Coins issuance, as liability of government","F2A":"Currency and overnight deposits","F2B":"Currency and monetary deposits","F2FR":"Currency and deposits, fixed rate","F2M":{"name":"Deposits","desc":"F2M=F22+F29"},"F2MF":"Non-monetary deposits","F2MM":"Monetary deposits","F2T4":{"name":"Currency and deposits, debt securities and loans","desc":"F2+F3+F4"},"F2T4_71":{"name":"Numerator for financial sector leverage","desc":"F2T4_71=F2+F3+F4+F71"},"F2T4S":{"name":"Short-term liabilities","desc":"F2T4S=F2+F31+F41"},"F2T6":{"name":"Currency and deposits; debt securities; loans; equity and investment fund shares; insurance, pension and standardized guarantee schemes","desc":"F2+F3+F4+F5+F6"},"F2VR":"Currency and deposits, variable rate","F3":{"name":"Debt securities","desc":"F3=F3A+F3VR+F3C, F3= F3ECAFX+ F3ECAF1+ F3ECAF2+ F3ECAF3+ F3ECAF4_5"},"F3A":"Debt securities, fixed rate issues","F3B":{"name":"Debt securities, floating rate issues (e.g. variable interest)","desc":"deprecated, replaced by F3VR"},"F3C":"Debt securities, zero coupon bonds","F3D":"Debt securities issued with embedded options (puttable bonds)","F3ECAF1":"Debt securities, ECAF credit quality step 1","F3ECAF2":"Debt securities, ECAF credit quality step 2","F3ECAF3":"Debt securities, ECAF credit quality step 3","F3ECAF4_5":"Debt securities, ECAF credit quality step 4 and 5","F3ECAFX":"Debt securities, no ratings information","F3F":"Non-monetary securities","F3FR":{"name":"Debt securities, fixed rate","desc":"F3FR=F3A+F3C"},"F3H":"High quality tradable securities","F3LS":"Securities issued under liquidity schemes","F3M":"Monetary securities","F3T4":{"name":"Debt securities and loans","desc":"F3+F4"},"F3VR":{"name":"Debt securities, variable rate","desc":"F3VR= F3VRA+F3VRB+F3VRC"},"F3VRA":"Inflation-linked variable rate","F3VRB":"Interest rate-linked variable rate","F3VRC":"Asset price-linked variable rate","F4":{"name":"Loans","desc":"For OECD table 7HH: F4A=F4A1+F4A2 at short term; F4A=F4AK+F4A29 at long term"},"F41":"Credit lines","F41A":"Credit lines; unconditional, undrawn","F4A":"Consumer credit","F4A1":"Revolving credit","F4A11":"Credit cards","F4A19":"Other lines of credit","F4A2":"Non-revolving credit","F4A21":"Automobile loans","F4A22":"Other loans for consumer durables","F4A29":"Other installment credit, including student loans","F4A291":"Student long-term loans","F4A299":"Other installment credit, excluding student loans","F4AK":{"name":"Loans for consumer durables","desc":"F4AK=F4A21+F4A22"},"F4B":{"name":"Loans for house purchasing","desc":"F4B=F4B1+F4B2"},"F4B1":"Mortgage guaranteed","F4B2":"Mortgage unguaranteed","F4C":"Loans for other purpose","F4CL":"Concessional loans","F4D":"Repurchase agreements, securities lending and margin lending insofar as recorded as loans","F4FR":"Loans, fixed rate","F4M2":"Non-performing loans","F4NP":"Nonperforming loans","F4P":"Lending by RRF programme (pandemic recovery)","F4R":"Repo loans","F4RX":"Other loans","F4S":"Lending by SURE programme (pandemic recovery)","F4VR":"Loans, variable rate","F5":{"name":"Equity and investment fund shares/units","desc":"F5=F51+F52; F5=F5A+F5B; F5=F5D+F5E"},"F51":{"name":"Equity","desc":"F51=F511+F512+F519, F51=F51A+F51B"},"F511":"Listed shares","F512":"Unlisted shares","F519":"Other equity","F51A":"Equity: other than reinvestment of earnings","F51B":"Equity: reinvestment of earnings","F51K":{"name":"Shares","desc":"F511+F512"},"F51M":{"name":"Unlisted shares and other equity","desc":"F512+F519"},"F52":{"name":"Investment fund shares/units","desc":"F52=F521+F522, F52=F52A+F52B"},"F521":"Money market fund shares/units","F521B":"Money market fund shares/units: reinvestment of earnings","F522":"Non-MMF investment fund shares/units","F5221":"Real Estate Fund Shares","F5222":"Bond Fund Shares","F5223":"Mixed Fund Shares","F5224":"Equity Fund Shares","F5229":"Other Fund Shares","F52A":"Investment fund shares/units: other than reinvestment of earnings","F52B":"Investment fund shares/units: reinvestment of earnings","F5A":"Equity and investment fund shares/units: other than reinvestment of earnings","F5AE":"Equity and investment fund shares/units: other than reinvestment of earnings: Extension of capital","F5AF":"Equity and investment fund shares/units: other than reinvestment of earnings: Financial restructuring","F5AG":"Equity and investment fund shares/units: other than reinvestment of earnings: Greenfield","F5AM":"Equity and investment fund shares/units: other than reinvestment of earnings: Merger & Acquisitions (M&A) type","F5B":"Equity and investment fund shares/units: reinvestment of earnings","F5BE":"Equity and investment fund shares/units: reinvestment of earnings: Extension of capital","F5BG":"Equity and investment fund shares/units: reinvestment of earnings: Greenfield","F5I":"Equity and investment fund shares of which equity injection","F5O":{"name":"Equity and investment fund shares other than privatisations and equity injections","desc":"F5O=F5-F5P-F5I"},"F5OP":"Shares and other equity other than portfolio investments","F5P":"Equity and investment fund shares of which privatisation","F5PN":"Portfolio investments, net","F6":{"name":"Insurance, pension and standardized guarantee schemes","desc":"F6=F61+F62+F63+F64+F65+F66"},"F61":"Non-life insurance technical reserves","F62":"Life insurance and annuity entitlements","F62A":"Life insurance and annuity entitlements, of which unit linked","F62B":"Life insurance and annuity entitlements, of which non-unit-linked","F63":"Pension entitlements","F63_65":{"name":"Pension entitlements and entitlements to non-pension benefits","desc":"F63_65=F63+F65"},"F63A":"Pension entitlements, of which defined contribution","F63A1":"Pension entitlements, defined contribution, managed by Autonomous Pension Funds","F63A2":"Pension entitlements, defined contribution, managed by Non-autonomous Pension Funds","F63A3":"Pension entitlements, defined contribution, managed by Insurers","F63B":"Pension entitlements, of which defined benefit","F63B1":"Pension entitlements, defined benefit, managed by Autonomous Pension Funds","F63B2":"Pension entitlements, defined benefit, managed by Non-autonomous Pension Funds","F63B3":"Pension entitlements, defined benefit, managed by Insurers","F63C":"Pension entitlements, of which hybrid schemes","F63C1":"Pension entitlements, hybrid schemes, managed by Autonomous Pension Funds","F63C2":"Pension entitlements, hybrid schemes, managed by Non-autonomous Pension Funds","F63C3":"Pension entitlements, hybrid schemes, managed by Insurers","F63F":{"name":"Pension entitlements, managed by Autonomous Pension Funds","desc":"F63F=F63A1+F63B1+F63C1"},"F63H":{"name":"Pension entitlements, managed by Non-autonomous Pension Funds","desc":"F63H=F63A2+F63B2+F63C2"},"F63I":{"name":"Pension entitlements, managed by Insurers","desc":"F63I=F63A3+F63B3+F63C3"},"F63O":"Other Pension Plans, including Unfunded Pension Plans","F63O1":"Unfunded Pension Plans","F63O9":"Other Pension Plans","F64":"Claims of pension funds on pension managers","F65":"Entitlements to non-pension benefits","F66":"Provisions for calls under standardized guarantees","F6FR":"Insurance, pension and standardized guarantee schemes, fixed rate","F6M":{"name":"Pension entitlements, claims of pension funds on pension managers and entitlements to non-pension benefits","desc":"F6M=F63+F64+F65"},"F6N":{"name":"Life insurance and annuity entitlements, pension entitlements, claims of pension funds on pension managers and entitlements to non-pension benefits","desc":"F62+F63+F64+F65"},"F6O":{"name":"Non-life insurance technical provisions and provisions for calls under standardized guarantees","desc":"F6O=F61+F66"},"F6P":{"name":"Claims of pension funds on pension managers and entitlements to non-pension benefits","desc":"F6P=F64+F65"},"F6VR":"Insurance, pension and standardized guarantee schemes, variable rate","F7":{"name":"Financial derivatives and employee stock options","desc":"F7=F71+F72"},"F71":{"name":"Financial derivatives","desc":"F71=F711+F712"},"F711":"Options type","F711A":"Options","F711B":"Other option-type contracts","F712":"Forward type","F712A":"Forwards","F712B":"Futures","F712C":"Swaps","F712D":"Other forward-type contracts","F71FF":"Forwards and futures","F71FO":"Forwards, futures and options","F71K":"Interest relating to swaps and forward rate arrangements (FRAs) (+/-)","F71R":"Other derivatives","F72":"Employee stock options","F7T8":{"name":"Financial derivatives and employee stock options; other accounts receivable/payable","desc":"F7T8=F7+F8"},"F8":{"name":"Other accounts receivable/payable","desc":"F8=F81+F89"},"F81":{"name":"Trade credits and advances","desc":"F81=F81A+F81B"},"F81A":"Trade credits","F81A1":"Trade credits relating to P.2 intermediate consumption and other","F81A2":"Trade credits relating to D.7 current transfers","F81A3":"Trade credits relating to D.9 capital transfers","F81A4":"Trade credits relating to P.51 gross fixed capital formation","F81AX":"Trade credits relating to military equipment","F81B":"Advances","F89":"Other accounts receivable/payable, excluding trade credits and advances","F89A":"Other accounts receivable/payable, other than trade credits, related to taxes","F89A_B":"Other accounts receivable/payable, other than trade credits, related to taxes and social contributions","F89A1":"Other accounts receivable/payable, related to D.2 taxes on production and imports","F89A2":"Other accounts receivable/payable, related to D.5 taxes on income, wealth, etc.","F89A3":"Other accounts receivable/payable, related to D.91 capital taxes","F89B":"Other accounts receivable/payable, other than trade credits, related to social contributions","F89B1":"Other accounts receivable/payable, related to D.611 and D.613 actual social contributions","F89C":"Other accounts receivable/payable, other than trade credits, related to EU flows","F89D":"Other accounts receivable/payable, other than trade credits, related to Military Expenditure","F8FR":"Other accounts receivable/payable, fixed rate","F8VR":"Other accounts receivable/payable, variable rate","F9":"Other financial assets/liabilities, non elsewhere classified","FAC":"Debt assumption/cancellation","FCA":"Asset swaps, securities lending without cash collateral and repurchase agreements","FCGA":{"name":"Guarantees and asset swaps/lending (FAM concept)","desc":"FCGA=F_SPVG+FXSPVG+FCA"},"FCV":"Debt related to special purpose vehicles (FAM concept)","FCY":"Explicit contingent liabilities","FCY1":"Publicly guaranteed debt","FCY2":"Other types of one-off guarantees","FCZ":"Net implicit obligations for social security benefits","FD":"Financing","FD2":{"name":"SDRs, currency and deposits, debt securities and loans","desc":"FD2=F12+F2+F3+F4"},"FD3":{"name":"SDRs, currency and deposits, debt securities, loans and other accounts payable","desc":"FD3=F12+F2+F3+F4+F8"},"FD4":{"name":"Debt instruments (GFSM/PSDSG)","desc":"FD4=F12+F2+F3+F4+F6+F8"},"FE":{"name":"Total financial assets/liabilities (FDI): Extension of capital","desc":"FE=F5AE+F5BE+FLH"},"FF":"Non-monetary financial assets","FG":{"name":"Total financial assets/liabilities (FDI): Greenfield","desc":"FG=F5AG+F5BG+FLG"},"FGD":{"name":"Total impact on gross debt","desc":"FGD=FGDD+FGDI"},"FGDD":"Direct impact on gross debt","FGDI":"Indirect impact on gross debt","FGED":{"name":"Gross external debt","desc":"FGED= F12+F2+F3+F4+F6+F8; In some data flow definitions the integrity rules are shown in a different format in order to explain to users their practical implementation. However, in none of the cases double counting is allowed."},"FI":"Financial investment","FIA":"Impaired assets","FINM":"Property - real state","FJ":"Arrears","FK":"Reserve Position in the IMF","FL":{"name":"Debt instruments (FDI)","desc":"FL = F229 + F29 + F3 + F4 + F61 + F62 + F64 + F66 + F8"},"FLA":{"name":"Debt instruments other than insurance, pension, and standardised schemes","desc":"FLA=F2+F3+F4+F8+F12"},"FLA1":"Debt instruments other than SDRs, insurance, pension, and standardised schemes","FLB":{"name":"Debt instrument other than intercompany lending","desc":"FLB=F12+F2+F3+F4+F6+F8"},"FLC":{"name":"Debt instrument other than intercompany lending and SDRs","desc":"FLC=F2+F3+F4+F6+F8"},"FLD":"Debt instruments, domestic creditors","FLE":"Debt instruments, external creditors","FLF":{"name":"Other FDI debt instruments","desc":"FLF=FL-F4-F3-F81"},"FLG":"Debt instruments (FDI): Greenfield","FLH":"Debt instruments (FDI): Extension of capital","FM":"Monetary financial assets","FN":{"name":"Other liabilities/assets (GFS concept)","desc":"FN=F1+F8 for assets; FN=F1+F5+F8 for liabilities"},"FNDL":"Other financial transactions within EDP of which: transactions in debt liabilities (+/-)","FNDX":"Other financial transactions within EDP","FNED":{"name":"Net external debt","desc":"FNED= F11B+F12+F2+F3+F4+F6+F8; In some data flow definitions the integrity rules are shown in a different format in order to explain to users their practical implementation. However, in none of the cases double counting is allowed."},"FO":{"name":"Equity and debt instruments (BPM6)","desc":"FO=F5+F6+FLA"},"FO1":{"name":"Investment fund shares/units, insurance, pension, and standardized guaranteed schemes","desc":"FO1=F52+F6"},"FO2":{"name":"Investment fund shares/units, life insurance, and pension","desc":"FO2=F52+F62+F6M"},"FOAL":"Other assets and liabilities of general government entities (assets/liabilities as defined for EDP financial crisis tables and to be used with custom breakdown FC)","FP":"Debt (non-standard definition)","FPT":{"name":"Debt securities; loans; pension entitlements, claims of pension funds on pension managers and entitlements to non-pension benefits; trade credits and advances","desc":"FPT=F3+F4+F6M+F81"},"FPU":"Amount outstanding in the government debt from the financing of public undertakings deprecated","FQ":"Remaining net assets of non-financial corporations, insurance corporations and pension funds deprecated","FR":"Assets in remaining net flows of households deprecated","FR0":{"name":"Other instruments than insurance and technical reserves (F6); equity (F5); securities (F3); currency and deposits (F2)","desc":"F-F6-F5-F3-F2"},"FR1":{"name":"Securities (Equity, investment fund shares/units and debt securities)","desc":"FR1=F3+F5"},"FR1Z":"Securities under repo for cash collateral","FR2":{"name":"Other reserve assets (currency, deposits, securities, financial derivatives and other claims)","desc":"FR2=FR3+FR4"},"FR3":{"name":"Securities; currency and deposits","desc":"FR3=F5+F3+F2"},"FR3A":{"name":"Securities, except investment fund shares; currency and deposits","desc":"FR3A=F2+F3+F51"},"FR4":{"name":"Other reserve assets (financial derivatives, loans to non-banks and other)","desc":"FR4=F71+F4+FR411"},"FR41":{"name":"Other claims (other reserve assets than Currency, deposits, securities and financial derivatives)","desc":"FR41=F4+FR411"},"FR411":{"name":"Reserve assets other than gold, SDRs, IMF reserve position, currency, deposits, securities, financial derivatives and loans (to non-banks)","desc":"FR411=F6+F8"},"FR5":{"name":"Other foreign currency assets (securities, deposits, loans, financial derivatives and gold not included in reserve assets)","desc":"FR5=F3+F5+F2+F4+F71+F11+FR51"},"FR51":"Other ( remaining part of other foreign currency assets (not included in reserve assets))","FR6":{"name":"Currency and deposits, loans and securities","desc":"FR6=F3+F5+F2+F4"},"FR8":{"name":"Other (flows related to repos and reverse repos, trade credits and other accounts payable/receivable)","desc":"FR8=F29C+F81A+F89"},"FR9":{"name":"Other instruments than forwards, futures and options","desc":"FR9=F-F71FO"},"FS":{"name":"Other accounts receivable/payable plus financial derivatives","desc":"F71+F8"},"FT":"Other, mainly inter-company loans","FU":"Remaining net assets of households deprecated","FV":{"name":"Other liabilities (F.5, F.6 and F.8)","desc":"FV=F5+F6+F8"},"FW1":{"name":"Loans +Insurance, pension and standardized guarantee schemes + Trade credits and advances + Other Equity","desc":"FW1= F4 + F6 + F81 + F519"},"FW2":{"name":"Loans + Insurance, pension and standardized guarantee schemes + SDRs + Trade credits and advances + Other Equity","desc":"FW2 = F4 + F6 + F12 + F81 + F519"},"FW3":{"name":"Other Debt Liabilities: Insurance, pension and standardized guarantee schemes + SDRs + Other accounts receivable/payable, excluding trade credits and advances","desc":"FW3 = F6 + F12+ F89"},"FX4":{"name":"Total financial assets/liabilities other than loans","desc":"FX4=F-F4"},"FXF2":{"name":"Financial instruments other than currency and deposits","desc":"FR10=F-F2"},"FXGG":"Guarantees provided to other sectors than general government","FXSPVG":"Other guarantees provided (FAM concept)","FY":{"name":"Other debt assets/liabilities: insurance, pension and standardized guarantee schemes + other accounts receivable/payable, excluding trade credits and advances","desc":"FY=F6+F89"},"FZ":{"name":"Debt securities and financial derivatives","desc":"F71+F3"},"GD":"Maastricht debt","GDA":"Maarstricht debt of which variable interest rate (GFS concept)","GDB":"Maastricht debt of which fixed interest rate (GFS concept)","GDM1":"Memo: Privatisation proceeds allocated to redemption of debt (GFS concept)","GDM2":"Memo: Universal Mobile Telecommunications System proceeds allocated to redemption of debt (GFS concept)","GDXFAM":{"name":"Government debt excluding government assistance to the financial corporations","desc":"government debt (GD) - impact on government debt related to government assistance to the financial corporations"},"N111G":"Dwellings (gross)","N111N":"Dwellings (net)","N1121G":"Buildings other than dwellings (gross)","N1121N":"Buildings other than dwellings (net)","N1122G":"Other structures (gross)","N1122N":"Other structures (net)","N1123G":"Land improvements (gross)","N1123N":"Land improvements (net)","N112G":"Other buildings and structures (gross)","N112N":"Other buildings and structures (net)","N1131G":"Transport equipment (gross)","N1131N":"Transport equipment (net)","N11321G":"Computer hardware (gross)","N11321N":"Computer hardware (net)","N11322G":"Telecommunications equipment (gross)","N11322N":"Telecommunications equipment (net)","N1132G":"ICT equipment (gross)","N1132N":"ICT equipment (net)","N1139G":"Other machinery and equipment (gross)","N1139N":"Other machinery and equipment (net)","N113G":"Machinery and equipment (gross)","N113KG":{"name":"ICT equipment and other machinery and equipment (Machinery and equipment other than transport equipment) (gross)","desc":"N113KG=N1132G+N1139G"},"N113KN":{"name":"ICT equipment and other machinery and equipment (Machinery and equipment other than transport equipment) (net)","desc":"N113KN=N1132N+N1139N"},"N113N":"Machinery and equipment (net)","N114G":"Weapons systems (gross)","N114N":"Weapons systems (net)","N1151G":"Animal resources yielding repeat products (gross)","N1151N":"Animal resources yielding repeat products (net)","N1152G":"Tree, crop and plant resources yielding repeat products (gross)","N1152N":"Tree, crop and plant resources yielding repeat products (net)","N115G":"Cultivated biological resources (gross)","N115N":"Cultivated biological resources (net)","N116G":"Costs of ownership transfer on non-produced assets (gross)","N116N":"Costs of ownership transfer on non-produced assets (net)","N1171G":"Research and development (gross)","N1171N":"Research and development (net)","N1172G":"Mineral exploration and evaluation (gross)","N1172N":"Mineral exploration and evaluation (net)","N11731G":"Computer software (gross)","N11731N":"Computer software (net)","N11732G":"Databases (gross)","N11732N":"Databases (net)","N1173G":"Computer software and databases (gross)","N1173N":"Computer software and databases (net)","N1174G":"Entertainment, literary or artistic originals (gross)","N1174N":"Entertainment, literary or artistic originals (net)","N1179G":"Other intellectual property products (gross)","N1179N":"Other intellectual property products (net)","N117G":"Intellectual property products (gross)","N117N":"Intellectual property products (net)","N11G":"Fixed assets by type of asset (gross)","N11KG":{"name":"Total construction (Buildings and structures) (gross)","desc":"N11KG=N111G+N112G"},"N11KN":{"name":"Total construction (Buildings and structures) (net)","desc":"N11KN=N111N+N112N"},"N11LG":{"name":"Cultivated assets and intangible fixed assets (gross)","desc":"N115G+N117G"},"N11LN":{"name":"Cultivated assets and intangible fixed assets (net)","desc":"N115N+N117N"},"N11MG":{"name":"Machinery and equipment and weapons systems (gross)","desc":"N11MG=N113G+N114G"},"N11MN":{"name":"Machinery and equipment and weapons systems (net)","desc":"N11MN=N113N+N114N"},"N11N":"Fixed assets by type of asset (net)","N11OG":{"name":"Other machinery and equipment and weapons systems (gross)","desc":"N11OG=N1139G+N114G"},"N11ON":{"name":"Other machinery and equipment and weapons systems (net)","desc":"N11ON=N1139N+N114N"},"N11PG":{"name":"Other fixed assets (gross)","desc":"N11PG=N115G+N116G+N117G"},"N11PN":{"name":"Other fixed assets (net)","desc":"N11PN=N115N+N116N+N117N"},"N11RG":{"name":"Fixed assets other than dwellings (gross)","desc":"N11RG=N11G-N111G"},"N11RN":{"name":"Fixed assets other than dwellings (net)","desc":"N11RN=N11N-N111N"},"N121G":"Materials and supplies (gross)","N121N":"Materials and supplies (net)","N1221G":"Work-in-progress on cultivated biological assets (gross)","N1221N":"Work-in-progress on cultivated biological assets (net)","N1222G":"Other work-in-progress (gross)","N1222N":"Other work-in-progress (net)","N122G":"Work-in-progress (gross)","N122N":"Work-in-progress (net)","N123G":"Finished goods (gross)","N123N":"Finished goods (net)","N124G":"Military inventories (gross)","N124N":"Military inventories (net)","N125G":"Goods for resale (gross)","N125N":"Goods for resale (net)","N12G":"Inventories by type of inventory (gross)","N12N":"Inventories by type of inventory (net)","N131G":"Precious metals and stones (gross)","N131N":"Precious metals and stones (net)","N132G":"Antiques and other art objects (gross)","N132N":"Antiques and other art objects (net)","N133G":"Other valuables (gross)","N133N":"Other valuables (net)","N13G":"Valuables (gross)","N13N":"Valuables (net)","N1G":"Produced non-financial assets (gross)","N1MG":{"name":"Inventories by type of inventory and valuables (gross)","desc":"N12G+N13G"},"N1MN":{"name":"Inventories by type of inventory and valuables (net)","desc":"N12N+N13N"},"N1N":"Produced non-financial assets (net)","N1OG":{"name":"Fixed assets by type of assets and inventories (gross)","desc":"N1OG=N11G+N12G"},"N1ON":{"name":"Fixed assets by type of assets and inventories (net)","desc":"N1ON=N11N+N12N"},"N2111":{"name":"Land underlying buildings and structures","desc":"N2111=N21111+N21112"},"N21111":"Land underlying dwellings","N21112":"Land underlying other buildings and structures","N211121":"Land underlying buildings other than dwellings","N2111A":"Land underlying dwellings [deprecated, replaced by N21111]","N2111AG":"Land underlying dwellings (gross)","N2111AN":"Land underlying dwellings (net)","N2111G":"Land underlying buildings and structures (gross)","N2111N":"Land underlying buildings and structures (net)","N21121":"Agricultural land","N21122":"Forestry land","N21123":"Surface water used for aquaculture","N2112G":"Land under cultivation (gross)","N2112N":"Land under cultivation (net)","N2113G":"Recreational land and associated surface water (gross)","N2113N":"Recreational land and associated surface water (net)","N2119G":"Other land and associated surface water (gross)","N2119N":"Other land and associated surface water (net)","N211G":"Land (gross)","N211N":"Land (net)","N212G":"Mineral and energy reserves (gross)","N212N":"Mineral and energy reserves (net)","N213G":"Non-cultivated biological resources (gross)","N213N":"Non-cultivated biological resources (net)","N214G":"Water resources (gross)","N214N":"Water resources (net)","N2151G":"Radio spectra (gross)","N2151N":"Radio spectra (net)","N2159G":"Other (gross)","N2159N":"Other (net)","N215G":"Other natural resources (gross)","N215N":"Other natural resources (net)","N215UN":"Universal Mobile Telecommunications System (net)","N21G":"Natural resources (gross)","N21KG":{"name":"Other naturally occurring assets (gross)","desc":"N21KG = N213G + N214G + N215G"},"N21KN":{"name":"Other naturally occuRring assets (net)","desc":"N21KN = N213N + N214N + N215N"},"N21N":"Natural resources (net)","N21OG":{"name":"Non-cultivated biological resources and water resources (gross)","desc":"N21OG=N213G+N214G"},"N21ON":{"name":"Non-cultivated biological resources and water resources (net)","desc":"N21ON=N213N+N214N"},"N221G":"Marketable operating leases (gross)","N221N":"Marketable operating leases (net)","N222G":"Permissions to use natural resources (gross)","N222N":"Permissions to use natural resources (net)","N223G":"Permissions to undertake specific activities (gross)","N223N":"Permissions to undertake specific activities (net)","N224G":"Entitlement to future goods and services on an exclusive basis (gross)","N224N":"Entitlement to future goods and services on an exclusive basis (net)","N22G":"Contracts, leases and licences (gross)","N22N":"Contracts, leases and licences (net)","N23G":"Purchases less sales of goodwill and marketing assets (gross)","N23N":"Purchases less sales of goodwill and marketing assets (net)","N2G":"Non-produced non-financial assets (gross)","N2KG":{"name":"Intangible nonproduced assets (gross)","desc":"N2KG = N22G + N23G"},"N2KN":{"name":"Intangible nonproduced assets (net)","desc":"N2KN = N22N + N23N"},"N2N":"Non-produced non-financial assets (net)","NENDI":"Net international investment position excluding non-defaultable instruments","NG":"All non-financial assets (gross)","NKG":"Non-financial assets, other than dwellings and lands (gross)","NKN":"Non-financial assets, other than dwellings and lands (net)","NLG":{"name":"All non-financial assets, other than inventories (gross)","desc":"NLG=N11G+N13G+N2G"},"NM111N":"Dwellings and land underlying buildings and structures (net)","NMN":"Consumer durable (net)","NN":"All non-financial assets (net)","NUN":"Housing wealth (net)","NYN":"Non-financial assets (includes total produced fixed assets and land underlying dwellings) (net)"}},"CL_MATURITY":{"name":"Original and Residual Maturity","codes":{"_X":"Not allocated / unspecified","_Z":"Not applicable","L":"Long-term original maturity (over 1 year or no stated maturity)","LL":"Long-term original maturity (over 1 year) with long-term residual maturity (over 1 year)","LM_1":"Long-term original maturity (over 1 year) with residual maturity up to 1 month","LM13":"Long-term original maturity (over 1 year) with residual maturity over 1 month and up to 3 months","LM3C":"Long-term original maturity (over 1 year) with residual maturity over 3 months and up to 12 months","LS":"Long-term original maturity (over 1 year) with short-term residual maturity (up to 1 year)","LY12":"Long-term original maturity (over 1 year) with residual maturity over 1 year and up to 2 years","LY13":"Long-term original maturity (over 1 year) with residual maturity over 1 year and up to 3 years","LY15":"Long-term original maturity (over 1 year) with residual maturity over 1 year and up to 5 years","LY2_":"Long-term original maturity (over 1 year) with residual maturity over 2 years","LY23":"Long-term original maturity (over 1 year) with residual maturity over 2 years and up to 3 years","LY25":"Long-term original maturity (over 1 year) with residual maturity over 2 years and up to 5 years","LY34":"Long-term original maturity (over 1 year) with residual maturity over 3 years and up to 4 years","LY35":"Long-term original maturity (over 1 year) with residual maturity over 3 years and up to 5 years","LY45":"Long-term original maturity (over 1 year) with residual maturity over 4 years and up to 5 years","LY5_":"Long-term original maturity (over 1 year) with residual maturity over 5 years","LY56":"Long-term original maturity (over 1 year) with residual maturity over 5 years and up to 6 years","LY5A":"Long-term original maturity (over 1 year) with residual maturity over 5 years and up to 10 years","LY67":"Long-term original maturity (over 1 year) with residual maturity over 6 years and up to 7 years","LY78":"Long-term original maturity (over 1 year) with residual maturity over 7 years and up to 8 years","LY89":"Long-term original maturity (over 1 year) with residual maturity over 8 years and up to 9 years","LY9A":"Long-term original maturity (over 1 year) with residual maturity over 9 years and up to 10 years","LYA_":"Long-term original maturity (over 1 year) with residual maturity over 10 years","LYAF":"Long-term original maturity (over 1 year) with residual maturity over 10 years and up to 15 years","LYAI":"Long-term original maturity (over 1 year) with residual maturity over 10 years and up to 30 years","LYFG":"Long-term original maturity (over 1 year) with residual maturity over 15 years and up to 20 years","LYGH":"Long-term original maturity (over 1 year) with residual maturity over 20 years and up to 25 years","LYHI":"Long-term original maturity (over 1 year) with residual maturity over 25 years and up to 30 years","LYI_":"Long-term original maturity (over 1 year) with residual maturity over 30 years","M_1":"Original maturity up to 1 month","M_1M_1":"Original maturity up to 1 month with residual maturity up to 1 month","M_3":"Original maturity up to 3 months","M13":"Original maturity over 1 month and up to 3 months","M3C":"Original maturity over 3 months and up to 12 months","S":"Short-term original maturity (up to 1 year)","SM_1":"Short-term original maturity (up to 1 year) with residual maturity up to 1 month","SM_3":"Short-term original maturity (up to 1 year) with residual maturity up to 3 months","SM13":"Short-term original maturity (up to 1 year) with residual maturity over 1 month and up to 3 months","SM3C":"Short-term original maturity (up to 1 year) with residual maturity over 3 months and up to 12 months","T":"All original maturities","TL":"All original maturities with long-term residual maturity (over 1 year)","TM_1":"All original maturities with residual maturity up to 1 month","TM_3":"All original maturities with residual maturity up to 3 months","TM13":"All original maturities with residual maturity over 1 month and up to 3 months","TM36":"All original maturities with residual maturity over 3 months and up to 6 months","TM3C":"All original maturities with residual maturity over 3 months and up to 12 months","TM69":"All original maturities with residual maturity over 6 months and up to 9 months","TM9C":"All original maturities with residual maturity over 9 months and up to 12 months","TS":"All original maturities with short-term residual maturity (up to 1 year)","TT":"Total residual maturity","TY12":"All original maturities with residual maturity over 1 year and up to 2 years","TY13":"All original maturities with residual maturity over 1 year and up to 3 years","TY15":"All original maturities with residual maturity over 1 year and up to 5 years","TY23":"All original maturities with residual maturity over 2 years and up to 3 years","TY25":"All original maturities with residual maturity over 2 years and up to 5 years","TY34":"All original maturities with residual maturity over 3 years and up to 4 years","TY35":"All original maturities with residual maturity over 3 years and up to 5 years","TY45":"All original maturities with residual maturity over 4 years and up to 5 years","TY5_":"All original maturities with residual maturity over 5 years","TY56":"All original maturities with residual maturity over 5 years and up to 6 years","TY57":"All original maturities with residual maturity over 5 years and up to 7 years","TY5A":"All original maturities with residual maturity over 5 years and up to 10 years","TY67":"All original maturities with residual maturity over 6 years and up to 7 years","TY78":"All original maturities with residual maturity over 7 years and up to 8 years","TY7A":"All original maturities with residual maturity over 7 years and up to 10 years","TY89":"All original maturities with residual maturity over 8 years and up to 9 years","TY9A":"All original maturities with residual maturity over 9 years and up to 10 years","TYA_":"All original maturities with residual maturity over 10 years","TYAF":"All original maturities with residual maturity over 10 years and up to 15 years","TYAI":"All original maturities with residual maturity over 10 years and up to 30 years","TYFG":"All original maturities with residual maturity over 15 years and up to 20 years","TYFI":"All original maturities with residual maturity over 15 years and up to 30 years","TYGH":"All original maturities with residual maturity over 20 years and up to 25 years","TYHI":"All original maturities with residual maturity over 25 years and up to 30 years","TYI_":"All original maturities with residual maturity over 30 years","XLS":"Long-term original maturity with short-term embedded put option","XY_2":"Unspecified original maturities with residual maturity up to 2 years","XY12":"Unspecified original maturities with residual maturity over 1 year and up to 2 years","XY23":"Unspecified original maturities with residual maturity over 2 years and up to 3 years","XY34":"Unspecified original maturities with residual maturity over 3 years and up to 4 years","XY45":"Unspecified original maturities with residual maturity over 4 years and up to 5 years","XY56":"Unspecified original maturities with residual maturity over 5 years and up to 6 years","XY67":"Unspecified original maturities with residual maturity over 6 years and up to 7 years","XY78":"Unspecified original maturities with residual maturity over 7 years and up to 8 years","XY89":"Unspecified original maturities with residual maturity over 8 years and up to 9 years","XY9A":"Unspecified original maturities with residual maturity over 9 years and up to 10 years","XYAF":"Unspecified original maturities with residual maturity over 10 years and up to 15 years","XYFG":"Unspecified original maturities with residual maturity over 15 years and up to 20 years","XYGH":"Unspecified original maturities with residual maturity over 20 years and up to 25 years","XYHI":"Unspecified original maturities with residual maturity over 25 years and up to 30 years","XYI_":"Unspecified original maturities with residual maturity over 30 years","Y_2M36":"Original maturity up to 2 years and residual maturity between 3 months and 6 months","Y12":"Original maturity over 1 year and up to 2 years","Y13":"Original maturity over 1 year and up to 3 years","Y15":"Original maturity over 1 year and up to 5 years","Y2_":"Original maturity over 2 years","Y23":"Original maturity over 2 years and up to 3 years","Y25":"Original maturity over 2 years and up to 5 years","Y34":"Original maturity over 3 years and up to 4 years","Y35":"Original maturity over 3 years and up to 5 years","Y45":"Original maturity over 4 years and up to 5 years","Y5_":"Original maturity over 5 years","Y56":"Original maturity over 5 years and up to 6 years","Y57":"Original maturity over 5 years and up to 7 years","Y5A":"Original maturity over 5 years and up to 10 years","Y67":"Original maturity over 6 years and up to 7 years","Y78":"Original maturity over 7 years and up to 8 years","Y7A":"Original maturity over 7 years and up to 10 years","Y89":"Original maturity over 8 years and up to 9 years","Y9A":"Original maturity over 9 years and up to 10 years","YA_":"Original maturity over 10 years","YAF":"Original maturity over 10 years and up to 15 years","YAI":"Original maturity over 10 years and up to 30 years","YFG":"Original maturity over 15 years and up to 20 years","YFI":"Original maturity over 15 years and up to 30 years","YGH":"Original maturity over 20 years and up to 25 years","YHI":"Original maturity over 25 years and up to 30 years","YI_":"Original maturity over 30 years"}},"CL_NA_CONSOLIDAT":{"name":"Consolidation codes","codes":{"_X":"Unspecified consolidation status","_Z":"Not applicable","C":"Consolidated","CI":"Consolidating item","N":"Non-consolidated","NC":"Non-consolidated between sub-sectors but consolidated within sub-sector","P":"Partially consolidated or aggregate containing both consolidated and non-consolidated items"}},"CL_NA_PRICES":{"name":"Price codes","codes":{"_Z":"Not applicable","D":"Deflator (index)","DR":"Deflator (rebased)","L":"Chain linked volume","LR":"Chain linked volume (rebased)","O":"Previous year's replacement costs","Q":"Constant prices","QR":"Constant prices (rebased)","R":"Real terms","RR":"Real terms (rebased)","U":"Current replacement cost","V":"Current prices","VQ":"Current prices (constant converter)","Y":"Previous year prices"}},"CL_NA_STO":{"name":"Stocks, Transactions, Other Flows","codes":{"_X":"Unspecified","_Z":"Not applicable","ACT":{"name":"Economically active population","desc":"ACT=EPEA"},"B":"Balancing and net worth items","B10":"Changes in net worth","B101":"Changes in net worth due to saving and capital transfers","B101A":"Net transactions in assets and liabilities","B102":"Changes in net worth due to other changes in volume of assets","B103":"Changes in net worth due to nominal holding gains and losses","B1031":"Changes in net worth due to neutral holding gains and losses","B1032":"Changes in net worth due to real holding gains and losses","B10K":"Changes in net worth due to other changes","B10R":{"name":"Remaining changes in net worth","desc":"B10R=B10-(P5-NP-P51C+F.FM+F.FF-F.F4+B10K.NYN+K.F)"},"B10T":{"name":"Changes in net worth due to other economic flows","desc":"B10T=B102+B103"},"B11":"External balance of goods and services","B111":"External balance of goods","B112":"External balance of services","B12":"Current external balance","B1G":"Value added, gross","B1GQ":"Gross domestic product at market prices","B1GXP119":{"name":"Value added excluding FISIM","desc":"only required if FISIM are not allocated"},"B1N":"Value added, net","B1NQ":"Net domestic product at market prices","B2A3G":"Operating surplus and mixed income, gross","B2A3N":"Operating surplus and mixed income, net","B2AD4":{"name":"Operating surplus, mixed and net property income","desc":"B2AD4=B2A3G+D4 = B2G+B3G+D4"},"B2G":"Operating surplus, gross","B2N":"Operating surplus, net","B3G":"Mixed income, gross","B3N":"Mixed income, net","B4G":"Entrepreneurial income (gross)","B4N":"Entrepreneurial income (net)","B5G":"Balance of primary incomes, gross / National income, gross","B5GQ":{"name":"Gross national income in market prices [deprecated]","desc":"deprecated, replaced by B5G"},"B5GQ95":"Gross national income (SNA93/ESA95)","B5GQ95XF":"Gross national income (SNA93/ESA95) excluding FISIM allocation","B5N":"Balance of primary incomes, net / National income, net","B5NQ":{"name":"Net national income in market prices [deprecated]","desc":"deprecated, replaced by B5N"},"B6G":"Disposable income, gross","B6GA":{"name":"Disposable income, gross, adjusted for the net change in pension entitlements","desc":"B6G + D8(credit) - D8(debit)"},"B6N":"Disposable income, net","B7G":"Adjusted disposable income, gross","B7N":"Adjusted disposable income, net","B8G":"Saving, gross","B8N":"Saving, net","B9":"Net lending(+) / net borrowing (-)","B90":"Net worth","B9F":"Net financial transactions","B9FX9":"Discrepancy between the financial (B9F) and non-financial (B9) net lending/borrowing","B9P":{"name":"Net lending/net borrowing excluding interest payable (primary deficit or surplus)","desc":"B9P = B9 + D41 D"},"B9XFAM":{"name":"Net lending (+) / net borrowing (-) excluding government assistance to the financial corporations","desc":"net lending/borrowing (B9) of general government \u2013 impact on net lending/borrowing (B9) related to government assistance to the financial corporations"},"BF90":"Financial net worth","BF90A":{"name":"Financial net worth adjusted for pension liabilities","desc":"BF90A=BF90+F6M"},"CIFFOB":"Cif/ fob adjustments","COM_HW":"Hourly compensation","COM_PS":"Compensation per employee","D":"Distributive transactions","D1":"Compensation of employees","D1_D29X39":{"name":"Compensation of employees and other taxes excluding other subsidies on products","desc":"D1_D29X39=D1+D29-D39"},"D11":"Wages and salaries","D12":"Employers' social contributions","D121":"Employers' actual social contributions (primary income)","D1211":"Employers' actual pension contributions (primary income)","D1212":"Employers' actual non-pension contributions (primary income)","D122":"Employers' imputed social contributions (primary income)","D1221":"Employers' imputed pension contributions (primary income)","D1222":"Employers' imputed non-pension contributions (primary income)","D2":"Taxes on production and imports","D21":"Taxes on products","D211":"Value added type taxes","D211E":"Value Added Tax paid to the EU (deprecated)","D212":"Taxes and duties on imports excluding Value Added Tax","D2121":"Import duties","D2122":"Taxes on imports excluding Value Added Tax and duties","D2122A":"Levies on imported agricultural products","D2122B":"Monetary compensatory amounts on imports","D2122C":"Excise duties","D2122D":"General sales taxes","D2122E":"Taxes on specific services","D2122F":"Profits of import monopolies","D212K":{"name":"Customs and other import duties","desc":"D212K=D2121+D2122A+D2122B"},"D213":"Export taxes","D213A":"Levies on exported goods and services, other than export duties and monetary comp. amounts on exports","D213B":"Profits of export monopolies","D213C":"Taxes resulting from multiple exchange rate regimes","D213D":"Export taxes, exchange taxes","D214":"Taxes on products except Value Added Tax, import and export taxes","D214A":"Excise duties and consumption taxes","D214B":"Stamp taxes","D214C":"Taxes on financial and capital transactions","D214D":"Car registration taxes","D214E":"Taxes on entertainment","D214F":"Taxes on lotteries, gambling and betting","D214G":"Taxes on insurance premiums","D214H":"Other taxes on specific services","D214I":"General sales or turnover taxes","D214I1":"General sales taxes","D214I2":"Turnover and other general taxes on goods and services","D214J":"Profits of fiscal monopolies","D214K":"Export duties and monetary comp. amounts on exports","D214L":"Other taxes on products n. e. c.","D21EU":"Taxes on products involving EU Institutions, traditional EU own resources (custom and agricultural duties)","D21K":{"name":"Total sales taxes","desc":"D21K=D2122D+D214I1"},"D21L":{"name":"Total excises","desc":"D21L=D2122C+D214A"},"D21M":{"name":"General taxes on goods and services","desc":"D21M=D211+D21K+D214I2+D214C"},"D21N":{"name":"Taxes on specific services","desc":"D21N=D214E+D214F+D214G+D214H"},"D21O":{"name":"Total taxes on exports","desc":"D21O=D213A+D214K"},"D21P":{"name":"Profits of export or import monopolies","desc":"D21P=D213B+D2122F"},"D21Q":{"name":"Total exchange taxes","desc":"D21Q=D213D+D59E1"},"D21X31":"Taxes less subsidies on products","D21X31X211":"Taxes less subsidies on products excluding VAT","D29":"Other taxes on production","D29A":"Taxes on land, buildings or other structures","D29B":"Taxes on the use of fixed assets","D29B1":"Taxes on the use of motor vehicles","D29B2":"Taxes on the use of other machinery or equipment","D29C":"Total wage bill and payroll taxes","D29D":"Taxes on international transactions","D29E":"Business and professional licences","D29F":"Taxes on pollution","D29G":"Under-compensation of Value Added Tax (flat rate system)","D29H":"Other taxes on production n. e. c.","D29H1":"Other taxes on production n. e. c.; recurrent taxes on net wealth","D29H2":"Other taxes on production n. e. c.; other recurrent taxes on property","D29H3":"Other taxes on production n. e. c.; other taxes on goods and services","D29H4":"Other taxes on production n. e. c.; other taxes on production","D29X39":"Other taxes on production minus other subsidies on production","D2M":"Indirect taxes on energy","D2N":{"name":"Indirect taxes excluding VAT and indirect taxes on energy","desc":"D2N=D2-D211-D2M"},"D2NOA":{"name":"Taxes on production and imports, other than for own-account capital formation","desc":"D2NOA=D2(debit)-P5OA41"},"D2R":{"name":"Other taxes on goods and services","desc":"D2R=D214L+D29G+D29H3"},"D2S":{"name":"Taxes on goods and services","desc":"D2S=D21M+D2122T4B+D214J+D21O+D2Q+D2R"},"D2T":{"name":"Other taxes on international trade and transactions","desc":"D2T=D2122E+D29D+D59E2"},"D2U":{"name":"Taxes on international trade and transactions","desc":"D2U=D212K+D21O+D21P+D213C+D213D+D2T"},"D2X3":"Taxes on production and imports less subsidies","D3":"Subsidies","D31":"Subsidies on products","D311":"Import subsidies","D312":"Export subsidies","D319":"Other subsidies on products","D31P":"Subsidies on products, payable (positive sign, for reporting in GFS presentation)","D39":"Other subsidies on production","D39P":"Other subsidies on production, payable (positive sign, for reporting in GFS presentation)","D39R":"Other subsidies on production, receivable (positive sign, for reporting in GFS presentation)","D3P":"Subsidies, payable (positive sign, for reporting in GFS presentation)","D4":"Property income","D4_7":{"name":"Property income and other current transfers","desc":"D4_7=D4+D7"},"D41":"Interest","D41A":"Interest accrued (not yet paid)","D41G":"Interest before FISIM allocation","D41SP":"Interest from the European instrument for temporary Support to mitigate Unemployment Risks in an Emergency (SURE) and the Recovery and Resilience Facility (RRF) loans","D42":"Distributed income of corporations","D421":"Dividends","D422":"Withdrawals from income of quasi-corporations","D43":"Reinvested earnings on FDI (Excluding IF)","D43S":"Reinvested earnings on FDI (Including IF)","D44":"Other investment income","D441":"Investment income attributable to insurance policyholders","D442":"Investment income payable on pension entitlements","D443":"Investment income attributable to collective investment fund share holders","D4431":"Dividends distributed to collective investment fund shareholders (IF)","D4432":"Reinvested earnings attributable to collective investment fund shareholders (IF)","D44K":{"name":"Property income from investment income disbursements","desc":"D44K=D441+D443"},"D45":"Rent","D4K":{"name":"Property income attributed to insurance policy holders and rent","desc":"D4K=D441+D45"},"D4M":"Interest and rents","D4N":{"name":"Property income other than interest","desc":"D4N=D42+D43+D44+D45"},"D4P":{"name":"Investment income (D4 less D45) (BOP)","desc":"D4P=D4-D45"},"D4R":{"name":"Investment income","desc":"D4R=D4-D41-D45=D4-D4K"},"D5":"Current taxes on income, wealth, etc.","D51":"Taxes on income","D51A":"Taxes on individual or household income excluding holding gains","D51B":"Taxes on the income or profits of corporations excluding holding gains","D51C":"Taxes on holding gains","D51C1":"Taxes on individual or household holding gains","D51C2":"Taxes on holding gains of corporations","D51C3":"Other taxes on holding gains n.e.c","D51D":"Taxes on winnings from lottery or gambling","D51D1":"Taxes on individuals' winnings from lottery or gambling","D51D2":"Taxes on corporations' winnings from lottery or gambling","D51D3":"Other taxes on winnings from lottery or gambling n.e.c.","D51E":"Other taxes on income n.e.c.","D51G1":{"name":"Taxes on income, payable by individuals","desc":"D51G1=D51M+D51D1"},"D51G2":{"name":"Taxes on income, payable by corporations and other enterprises","desc":"D51G2=D51O+D51D2"},"D51G3":{"name":"Other taxes on income, profits, and capital gains","desc":"D51G3=D51C3+D51D3+D51E"},"D51M":{"name":"Taxes on individual or household income including holding gains","desc":"D51M=D51A+D51C1"},"D51O":{"name":"Taxes on the income or profits of corporations including holding gains","desc":"D51O=D51B+D51C2"},"D59":"Other current taxes","D59A":"Current taxes on capital","D59A1":"Current taxes on land, buildings and other structures","D59A2":"Recurrent taxes on net wealth","D59A3":"Other recurrent taxes on property","D59A4":"Current taxes on ownership of motor vehicles","D59B":"Poll taxes","D59C":"Expenditure taxes","D59D":"Payments by households for licences","D59D1":"Payments by households for licenses to use motor vehicle taxes","D59D2":"Payments by households for radio and television licenses","D59D3":"Payments by households for other licenses and permits","D59E":"Other current taxes on international transactions","D59E1":"Other current taxes on international transactions; exchange taxes","D59E2":"Other current taxes on international transactions; other","D59F":"Other current taxes n.e.c.","D6":"Social contributions and social benefits","D61":"Net social contributions","D611":{"name":"Employers' actual social contributions","desc":"D611= D121"},"D6111":{"name":"Employers' actual pension contributions","desc":"D6111= D1211"},"D6111A":"Social security actual pension contributions by employers","D6111B":"Employment related schemes actual pension contributions by employers","D6112":{"name":"Employers' actual non-pension contributions","desc":"D6112 = D1212"},"D6112A":"Social security actual nonpension contributions by employers","D6112B":"Employment related schemes actual nonpension contributions by employers","D611C":"Compulsory employers' actual social contributions","D611V":"Voluntary employers' actual social contributions","D612":{"name":"Employers' imputed social contributions","desc":"D612 = D122"},"D6121":{"name":"Employers' imputed pension contributions","desc":"D6121 = D1221"},"D6122":{"name":"Employers' imputed non-pension contributions","desc":"D6122 = D1222"},"D613":"Households' actual social contributions","D6131":"Households' actual pension contributions","D6131A1":"Social security actual pension contributions by employees","D6131A2":"Social security actual pension contributions by self-employed or nonemployed","D6131B":"Employment related schemes actual pension contributions by employees","D6132":"Households' actual non-pension contributions","D6132A1":"Social security actual nonpension contributions by employees","D6132A2":"Social security actual nonpension contributions by self-employed or nonemployed","D6132B":"Employment related schemes actual nonpension contributions by employees","D613C":"Compulsory households' actual social contributions","D613CE":"Compulsory employees' actual social contributions","D613CN":"Compulsory actual social contributions by the non-employed","D613CS":"Compulsory actual social contributions by the self-employed","D613V":"Voluntary households' actual social contributions","D614":"Households' social contribution supplements","D6141":"Households' pension contribution supplements","D6142":"Households' non-pension contribution supplements","D619":"Other (actuarial) change of pension entitlements in social security pension schemes","D61N":{"name":"Actual social contributions from employers and households","desc":"D61N=D611+D613"},"D61SC":"Social insurance scheme service charges (-)","D62":"Social benefits other than social transfers in kind","D62_63":{"name":"Social benefits and social transfers in kind","desc":"D62_63=D62+D63"},"D621":"Social security benefits in cash","D6211":"Social security pension benefits","D6212":"Social security non-pension benefits in cash","D622":"Other social insurance benefits","D6221":"Other social insurance pension benefits","D6222":"Other social insurance non-pension benefits","D623":"Social assistance benefits in cash","D62O":"Other social allowances (payments of family, education, medical services and other allowances)","D62P":"Retirement and survivors' Pensions","D63":"Social transfers in kind","D631":"Social transfers in kind - non-market production","D632":"Social transfers in kind - purchased market production","D6321":"Social transfers in kind - purchased market production, social security","D6322":"Social transfers in kind - purchased market production, employment-related schemes","D6323":"Social transfers in kind - purchased market production, social assistance","D6K":{"name":"Social transfers, other than social transfers in kind minus net social contributions","desc":"D62(credit)-D61(debit)"},"D6L":{"name":"Social contribution and social benefits, other than social transfer in kind","desc":"D6L=D61+D62"},"D6M":{"name":"Social benefits other than social transfers in kind and social transfers in kind - purchased market production","desc":"D6M=D62+D632"},"D7":"Other current transfers","D71":"Net non-life insurance premiums","D711":"Net non-life direct insurance premiums","D712":"Net non-life reinsurance premiums","D71A":"Net premiums of nonlife insurance schemes other than standardized guarantee","D71B":"Fees for standardized guarantee schemes","D72":"Non-life insurance claims","D721":"Non-life direct insurance claims","D722":"Non-life reinsurance claims","D73":"Current transfers within general government","D73_74":{"name":"Current grants to/from governments and international organizations","desc":"D73_74=D73+D74"},"D74":"Current international cooperation","D75":"Miscellaneous current transfers","D751":"Current transfers to NPISHs","D752":"Current transfers between resident and non-resident households","D759":"Other miscellaneous current transfers","D759A":"Fines, penalties, and forfeits","D759B":"Other miscellaneous current transfers , other than fines, penalties, and forfeits","D76":{"name":"Value Added Tax and GNI - based EU own resources","desc":"D76 = D761+D762+D763"},"D761":"VAT-based third EU own resource","D762":"GNI-based fourth EU own resource","D762K":"Current transfers of which UK rebate","D763":"Miscellaneous non-tax contribution of the government to the institutions of the EU","D763A":"Miscellaneous non-tax contribution of the government to the institutions of the European Union (EU): of which plastics contribution - EU own resource","D7K":{"name":"Miscellaneous current transfers and VAT- and GNI-based own resources [deprecated]","desc":"D7K=D75+D76"},"D7L":{"name":"Current transfers within general government, current international cooperation and miscellaneous current transfers","desc":"D7L=D73+D74+D75"},"D7N":{"name":"Current international cooperation, miscellaneous current transfers and VAT and GNI-based EU own resources","desc":"D7N=D74+D75+D76"},"D7NP":"Current transfers financed by the Recovery and Resilience Facility (RRF)","D7O":{"name":"Secondary income: All miscellaneous current transfers","desc":"D7O=D75+D76"},"D8":"Adjustment for the change in pension entitlements","D81":"Transfer of pension entitlements between schemes","D82":"Change in entitlements due to negotiated changes in scheme structure","D9":"Capital transfers","D91":"Capital taxes","D91A":"Taxes on capital transfers","D91B":"Capital levies","D91C":"Other capital taxes n.e.c.","D92":"Investment grants","D99":"Other capital transfers","D995":"Capital transfers from general government to relevant sectors representing taxes and social contributions assessed but unlikely to be collected","D995A":"Taxes on products assessed but unlikely to be collected","D995B":"Other taxes on production assessed but unlikely to be collected","D995C":"Taxes on income assessed but unlikely to be collected","D995D":"Other current taxes assessed but unlikely to be collected","D995E":"Employers actual social contributions assessed but unlikely to be collected","D995F":"Households' actual social contributions assessed but unlikely to be collected","D995FE":"Employees' actual social contributions assessed but unlikely to be collected","D995FN":"Actual social contributions by non-employed persons assessed but unlikely to be collected","D995FS":"Actual social contributions by self-employed persons assessed but unlikely to be collected","D995G":"Capital taxes assessed but unlikely to be collected","D99A":"Nonlife insurance capital claims","D99B":"Other capital transfers not elsewhere classified","D99CG":"Calls on guarantees","D99CI":"Capital injections recorded as capital transfers","D9IMA":"Capital transfers recorded in the context of asset purchases","D9N":{"name":"Other capital transfers and investment grants","desc":"D9N=D92+D99"},"D9NP":"Capital transfers financed by the Recovery and Resilience Facility (RRF)","D9O":{"name":"Other capital transfers and investment grants, excluding nonlife insurance capital claims","desc":"D9O=D92+D99B; D9O=D9N-D99A"},"D9P":{"name":"Capital transfers, excluding nonlife insurance capital claims","desc":"D9P=D91+D92+D99B; D9P=D9-D99A"},"DG":{"name":"Grants to/from governments and international organizations","desc":"DG=D73+D74+D9N(requires counterparty)"},"DG1":"Grants in cash","DG2":"Grants in kind","DK":{"name":"Taxes on property","desc":"DK=DK1+DK2+DK3+D91A+D91B"},"DK1":{"name":"Recurrent taxes on immovable property","desc":"DK1=D29A+D59A1"},"DK2":{"name":"Recurrent taxes on net wealth","desc":"DK2=D29H1+D59A2"},"DK3":{"name":"Other recurrent taxes on property","desc":"DK3=D29H2+D59A3"},"DL":{"name":"Taxes on use of goods and on permission to use goods and perform activities","desc":"DL=DL1+DL2"},"DL1":{"name":"Motor vehicles taxes [IMF GFSM definition]","desc":"DL1=D214D+D29B1+D59A4+D59D1"},"DL2":{"name":"Other taxes on use of goods and on permission to use goods or perform activities","desc":"DL2=D29E+D29F+D59D2+D59D3+D29B2"},"EMP":"Total employment","EUO":"European Union (EU) own resources and miscellaneous contributions","F":"Transactions in financial assets and liabilities","GB8ZG":{"name":"Gross operating balance","desc":"GB8ZG=GOTRG-GOTEE"},"GB8ZN":{"name":"Net operating balance","desc":"GB8ZN=GOTRG-GOTEE+P51M"},"GB9":{"name":"Net lending(+) / net borrowing (-) [IMF GFSM definition]","desc":"GB9=GOTRG-GOTEG; B9G=GOTRG-GOTEE-P5L"},"GB9P":{"name":"Primary net lending(+) / net borrowing (-) [IMF GFSM definition]","desc":"GB9P=GB9+D41G(debit)"},"GCL":"Implicit transfers resulting from concessional interest rates","GCNFB":"Net cash inflow from financial activities","GD1":{"name":"Compensation of employees, excluding for own-account capital formation [IMF GFSM definition]","desc":"GD1=D1-P5OA1"},"GD11":{"name":"Wages and salaries, excluding for own-account capital formation [IMF GFSM definition]","desc":"GD11=GD11A+GD11B GD11=D11-P5OA11-P5OA12"},"GD11A":"Wages and salaries in cash, excluding for own-account capital formation [IMF GFSM definition]","GD11B":"Wages and salaries in kind, excluding for own-account capital formation [IMF GFSM definition]","GD12":{"name":"Employers' social contributions, excluding for own-account capital formation [IMF GFSM definition]","desc":"GD12=GD121+GD122 GD12=D12-P5OA13-P5OA14"},"GD121":{"name":"Employers' actual social contributions, excluding for own-account capital formation [IMF GFSM definition]","desc":"GD121=D121-P5OA13"},"GD122":{"name":"Employers' imputed social contributions, excluding for own-account capital formation [IMF GFSM definition]","desc":"GD122=D122-P5OA14"},"GD3NOA":{"name":"Subsidies, other than for own-account capital formation","desc":"GD3NOA=D3(credit)-P5OA42"},"GD4":{"name":"Property income before FISIM allocation, excluding investment income payable on pension entitlements [IMF GFSM definition]","desc":"GD4=D41G+D421+D422+D44K+D45+D43"},"GD4N":{"name":"Property income other than interest, excluding investment income payable on pension entitlements [IMF GFSM definition]","desc":"GD4N=D42+D43+D44K+D45"},"GD61":{"name":"Social contributions, excluding employment related schemes' pension contribution [IMF GFSM definition]","desc":"GD61=GD61A+GD61B"},"GD61A":{"name":"Social security contributions","desc":"GD61A=GD61A1+GD61A2+GD61A3+GD61A4"},"GD61A1":{"name":"Social security contributions, employee contributions","desc":"GD61A1=D6131A1+D6132A1"},"GD61A2":{"name":"Social security contributions, employer contributions","desc":"GD61A2=D6111A+D6112A"},"GD61A3":{"name":"Social security contributions, self-employed or nonemployed contributions","desc":"GD61A3=D6131A2+D6132A2"},"GD61A4":"Social security contributions, unallocable contributions","GD61B":{"name":"Other social contributions","desc":"GD61B=GD61B1+D6112B+D6122"},"GD61B1":{"name":"Other social contributions, employee contributions","desc":"GD61B1=D6132B+D6142"},"GD62":{"name":"Social benefits in cash, excluding other social insurance pension benefits [IMF GFSM definition]","desc":"GD62=D621+D6222+D623"},"GD6M":{"name":"Social benefits, excluding other social insurance pension benefits and social transfers in kind - non-market production [IMF GFSM definition]","desc":"GD6M=D621+D6222+D623+D632; GD6M=GD6M1+GD6M2+GD6M3"},"GD6M1":{"name":"Social security benefits","desc":"GD6M1=D621+D6321"},"GD6M2":{"name":"Employer social benefits, excluding pension benefits [IMF GFSM definition]","desc":"GD6M2=D6222+D6322"},"GD6M3":{"name":"Social assistance benefits","desc":"GD6M3=D623+D6323"},"GD71A":{"name":"Premiums of nonlife insurance schemes other than standardized guarantees","desc":"GD71A(credit)=D71A(credit)+P118 GD71A(debit)=D71A(debit)+P28"},"GD75":{"name":"Miscellaneous current transfers , other than fines, penalties, and forfeits","desc":"GD75=D75-D759B"},"GD7P":{"name":"Premiums, fees, and current claims","desc":"GD7P=GD71A+D71B+D72"},"GD7Q":{"name":"Premiums, fees, and claims related to nonlife insurance and standardized guarantee schemes","desc":"GD7Q=GD7P+D99A"},"GD7R":{"name":"Current transfers not elsewhere classified","desc":"GD7R(credit)=D3NOA+GD75 GD7R(debit)=D2NOA+D5+D75"},"GD7Z":{"name":"Transfers not elsewhere classified","desc":"GD7Z(credit)=GD7R(credit)+D9O GD7Z(debit)=GD7R(debit)+D9P"},"GDM":{"name":"Other taxes [IMF GFSM definition]","desc":"GDM=GDM1+GDM2"},"GDM1":{"name":"Other taxes, payable solely by business","desc":"GDM1=D214B+D29H4"},"GDM2":{"name":"Other taxes, payable by other than business or unidentifiable","desc":"GDM2=D59B+D59C+D59F"},"GDXB9":"Deficit-debt adjustment","GDXN":{"name":"Time of recording and other differences in DDA analysis (ECB concept)","desc":"GDXN=GDXB9 - FR6 - other flows"},"GOOE":{"name":"Other expense [IMF GFSM definition]","desc":"GOOE=GD4N+GD7Z+GD7Q(debit)"},"GOOR":{"name":"Other revenue [IMF GFSM definition]","desc":"GOOR=GD4+GP1+D759A+GD7Z+GD7Q(credit)"},"GOTE":{"name":"Total government expenditure [IMF GFSM definition]","desc":"GOTEG=GOTEE+P5NP"},"GOTEE":{"name":"Total expense","desc":"GOTEE=GD1+GP2+P51M+GD41+D3+DG+GD6M+GOOE"},"GOTEEG":{"name":"Expense, excluding consumption of fixed capital","desc":"GOTEEG=GD1+GP2+GD41+D3+DG+GD6M+GOOE"},"GOTR":{"name":"Total government revenue [IMF GFSM definition]","desc":"GOTR=ODA+GD61+DG+GOOR"},"GP1":{"name":"Sales of goods and services","desc":"GP1=GP11+P131+P12B"},"GP11":{"name":"Sales by market establishments","desc":"GP11=P11-P118-P119"},"GP2":{"name":"Use of goods and services","desc":"GP2=P2-P28-P29-P5OA2"},"GP51C":{"name":"Consumption of fixed capital (use of fixed assets) [IMF GFSM definition]","desc":"GP51C=P51C-P5OA3"},"IN":{"name":"Primary and secondary income","desc":"IN=D1+D2+D3+D4+D5+D6+D7+D8; IN=IN1+IN2"},"IN1":{"name":"Primary income","desc":"IN1=D1+D2+D3+D4"},"IN2":{"name":"Secondary income","desc":"IN2=D5+D6+D7+D8"},"IN21":{"name":"Secondary income: current transfers","desc":"IN21=D5+D6+D7"},"IN22":{"name":"Secondary income: Other current transfers excluding personal transfers","desc":"IN22=IN2-D752"},"K":"Changes in positions other than transactions","K1":"Economic appearance of assets","K2":"Economic disappearances of non-produced assets","K21":"Depletion of natural resources","K22":"Other economic disappearances of non-produced assets","K3":"Catastrophic losses","K4":"Uncompensated seizures","K5":"Other changes in volume not elsewhere classified","K6":"Changes in classification","K61":"Changes in sector classification and structure","K62":"Changes in classification of assets and liabilities","K7":"Revaluations / Nominal holding gains and losses","K71":"Neutral holding gains and losses","K72":"Real holding gains and losses","K7A":"Revaluations due to exchange rate changes","K7B":"Revaluations due to other price changes","K7B1":"Other valuation effects of which due to issuance and redemption value","KA":"Other changes excluding revaluations","KX":"Other volume changes in debt liabilities (K.3, K.4, K.5) (-)","LE":"Closing balance sheet/Positions/Stocks","LPR_HW":"Labour Productivity (per hours worked)","LPR_PS":"Labour Productivity (per persons)","LS":"Opening balance sheet/Positions/Stocks","LX":"Changes in balance sheet/Positions/Stocks","NP":"Acquisitions less disposals of non-produced assets","O21X31":"Adjustment product taxes less subsidies","OB9":"Net lending/borrowing under EDP","OCE":{"name":"Total current expenditure","desc":"OCE = OCT+D41 D+D1 D+P2 D"},"OCEXD41":{"name":"Primary current expenditure","desc":"OCE - D41"},"OCR":{"name":"Total current revenue","desc":"OCR= D5+D2+D61+OOCR+P11+P12+P131"},"OCT":{"name":"Social benefits other than social transfers in kind + social transfers in kind, purchased market production + subsidies payable + current taxes on income, wealth, etc. + other taxes on production + pr","desc":"OCT = OSP-D3 C+OOCT"},"OD41":"Interest, including flows on swaps and FRA's","ODA":"Total tax receipts","ODB":"Total receipts from taxes and social contributions after deduction of amounts assessed but unlikely to be collected","ODC":"Total receipts from taxes and social contributions (including imputed social contributions) after deduction of amounts assessed but unlikely to be collected","ODD":"Tax burden = total receipts from taxes and compulsory social contributions after deduction of amounts assessed but unlikely to be collected","ODH":"Memo: Difference between deliveries and corresponding cash payment (EDP concept)","OEA":"Intermediate consumption, other taxes on production, current taxes on income and wealth, etc., and adjustment for the change in net equity of households in pension funds reserves","OEB":"Other taxes on production, current taxes on income and wealth, etc. and adjustment for the change in net equity of households in pension funds reserves","OEC":{"name":"Intermediate consumption + Other taxes on production + Current taxes on income, wealth, etc. + Adjustment for the change in pension entitlements","desc":"OEC=P2+D29+D5+D8"},"OED":{"name":"Other taxes on production + Current taxes on income, wealth, etc. + Adjustment for the change in pension entitlements","desc":"OED=D29+D5+D8"},"OESA95":"Total impact of differences in definitions between ESA2010 and ESA95 on GNI","OESA9501A":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: R&D created by a market producer","OESA9501B":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: R&D created by a non-market producer","OESA9502":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Valuation of output for own final use for market producers","OESA9503":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Non-life insurance - Output, claims due to catastrophes, and reinsurance","OESA9504":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Weapon systems in government recognised as capital assets","OESA9505":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Decommissioning costs for large capital assets","OESA9506":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Government, public and private sector classification","OESA9507":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Small tools","OESA9508":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: VAT-based third EU own resource","OESA9509":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Index-linked debt instruments","OESA9510":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Central Bank - allocation of output","OESA9511":"Impact of differences in definitions between ESA2010 and ESA95 on GNI: Land improvements recognised as a separate asset","OGF":{"name":"Guarantee fees receivable","desc":"sum of guarantee fees recorded as P.131 and D.75"},"OIN":{"name":"Gross disposable income minus final consumption expenditure","desc":"B6G-P3"},"OKE":{"name":"Total capital expenditure","desc":"OKE = P51G+P52+P53+NP+D9 C"},"OM2":"Member State's net revenue from pre-acceding programmes","OOCE":{"name":"Current taxes on income, wealth, etc., Other taxes on production, Property income other than interest, Other current transfers and Adjustment for the change in pension entitlements","desc":"OOCE = D29 + D4N + D5 + D7 + D8"},"OOCR":{"name":"Other current revenue","desc":"OOCR = D39 + D4 + D7"},"OOCT":{"name":"Current taxes on income, wealth, etc. + other taxes on production + property income other than interest + other current transfers excluding current transfers to NPISH","desc":"OOCT=D29 + D4 - D41 + D5 + D7 -D751 + D8"},"OOE":{"name":"Total government expenditure excluding: interest, calls on guarantees, capital injections recorded as capital transfers","desc":"OOE=OTE-D41-D99CG-D99CI"},"OOEE":{"name":"Total government expenditure excluding: interest, calls on guarantees, capital injections recorded as capital transfers, capital transfers recorded in the context of asset purchases","desc":"OOEE=OTE-D41-D99CG-D99CI-D99IMA"},"OOR":{"name":"Other revenue","desc":"OOR=OTR-OGF-D41-D42"},"OP":"Purchases","OPI":{"name":"Gross disposable income - gross operating surplus and mixed income - compensation of employees - social contribution and social benefits, other than social transfer in kind - current taxes on income, ","desc":"OPI=B6G-B2A3G-D1-D61-D62-D5"},"ORADJ":"Adjustments for scope and valuation of Maastricht debt","ORD41A":"Difference between interest paid (+) and accrued (EDP D.41)(-)","ORD41FA":"Difference between interest (EDP D.41) accrued(-) and paid (+) of which: interest flows attributable to swaps and FRAs","ORFCD":"Appreciation(+)/depreciation(-) of foreign-currency debt","ORINV":"Issuances above(-)/below(+) nominal value","ORNF":"Non-financial transactions not included in the working balance","OROA":"Other adjustments (+/-) in EDP Table 2","ORRNV":"Redemptions of debt above(+)/below(-) nominal value","ORWB":"Working balance","ORWB_E":"Working balance (+/-) of entities not part of the subsector","OSA":{"name":"Savings, gross plus net capital transfers","desc":"B8G+D9"},"OSP":{"name":"Social benefits other than social transfers in kind and social transfers in kind - purchased market production + current transfers to NPISHs","desc":"OSP = D.62 D+ D.632 +D751= D6M+D751"},"OTE":"Total government expenditure","OTEK":{"name":"Total expenditure other than Compensation of employees, Social benefits and social transfers in kind for products supplied to HH via market producers, Intermediate consumption and Gross fixed capital ","desc":"OTEK=OTE-D1-D6O-P51-P2"},"OTEXD41":{"name":"Primary expenditure","desc":"OTEXD41=OTE-D41"},"OTGL":"Trading gain or loss","OTR":"Total government revenue","OTRE":"Net revenue / cost for general government (only including transactions as defined for EDP financial crisis tables and to be used with custom breakdown FC)","OTSR":"Total receipts from taxes and social contributions","OTTM":"Trade and transport margins","OTTM1":"Trade margins","OTTM2":"Transport margins","P":"Transactions in products","P1":"Output","P11":"Market output","P118":"Implicit service fees in nonlife insurance premiums and standardized guarantees","P119":"Financial Intermediation Services Indirectly Measured (FISIM)","P12":"Output for own final use","P12_GFSM_D1":"Output for own final use, cost attributable to compensation of employees (GFSM purpose)","P12_GFSM_P2":"Output for own final use, cost attributable to intermediate consumption (GFSM purpose)","P12_GFSM_P51C":"Output for own final use, cost attributable to consumption of fixed capital (GFSM purpose)","P12A":"Own-account capital formation","P12B":"Production of goods and services used as compensation of employees in kind","P13":"Non-market output","P131":"Payments for other non-market output","P131A":"Administrative fees","P131B":"Incidental sales by nonmarket establishments","P132":"Other non-market output, n.e.c.","P1M":{"name":"Market output and output for own final use","desc":"P1M=P1-P131"},"P1O":{"name":"Market output, output for own final use and payments for other non-market output","desc":"P1O=P11+P12+P131"},"P2":"Intermediate consumption","P28":"Service charges payable to providers of nonlife insurance","P29":"Intermediate consumption resulting from FISIM allocation","P3":{"name":"Final consumption expenditure","desc":"P3=P31+P32"},"P3_P51G":{"name":"Final domestic demand excluding inventories","desc":"P3_P51G=P3+P51G"},"P31":"Individual consumption expenditure","P311":"Individual consumption expenditure of durable goods","P312":"Individual consumption expenditure of semi-durable goods","P313":"Individual consumption expenditure of non-durable goods","P314":"Individual consumption expenditure of services","P31K":{"name":"Individual consumption expenditure of semi-durable and non-durable goods and services","desc":"P31K=P312+P313+P314"},"P32":"Collective consumption expenditure","P3T5":{"name":"Total final domestic demand","desc":"P3T5=P3+P5"},"P3T6":{"name":"Total demand","desc":"P3T6=P3+P5+P6"},"P4":"Actual final consumption","P41":"Actual individual consumption","P42":"Actual collective consumption","P5":"Gross capital formation","P511":"Acquisitions less disposals of fixed assets","P5111":"Acquisitions of new fixed assets","P5112":"Acquisitions of existing fixed assets","P5113":"Disposals of existing fixed assets","P512":"Costs of ownership transfer on non-produced assets","P51C":"Consumption of fixed capital","P51C1":"Consumption of fixed capital on gross operating surplus","P51C2":"Consumption of fixed capital on gross mixed income","P51G":"Gross fixed capital formation","P51N":"Net fixed capital formation","P52":"Changes in inventories","P53":"Acquisitions less disposals of valuables","P5K":{"name":"Changes in inventories (P52), acquisition less disposals of valuables (P53) and acquisition less disposals of non-financial non-produced assets (NP)","desc":"P5K=P52+P53+NP"},"P5L":{"name":"Gross capital formation and acquisitions less disposals of non-produced assets","desc":"P5+NP"},"P5LN":{"name":"Net capital formation and acquisitions less disposals of non-produced assets","desc":"P5+NP-P51C"},"P5M":{"name":"Changes in inventories and acquisition less disposals of valuables","desc":"P5M=P52+P53"},"P5N":"Net capital formation","P5OA":{"name":"Own-account capital formation","desc":"P5OA=P5OA1+P5OA2+P5OA3+P5OA4"},"P5OA1":{"name":"Own-account capital formation, compensation of employees","desc":"P5OA1=P5OA11+P5OA12+P5OA13+P5OA14"},"P5OA11":{"name":"Own-account capital formation, wages and salaries in cash","desc":"Under GFS code 2111"},"P5OA12":{"name":"Own-account capital formation, wages and salaries in kind","desc":"Under GFS code 2112"},"P5OA13":{"name":"Own-account capital formation, actual employers' social contributions","desc":"Under GFS code 2121"},"P5OA14":{"name":"Own-account capital formation, imputed employers' social contributions","desc":"Under GFS code 2122"},"P5OA2":"Own-account capital formation, intermediate consumption","P5OA3":"Own-account capital formation, consumption of fixed capital","P5OA4":{"name":"Own-account capital formation, other taxes on production minus other subsidies on production","desc":"P5OA4=P5OA41-P5OA42"},"P5OA41":"Own-account capital formation, other taxes on production","P5OA42":"Own-account capital formation, other subsidies on production","P6":"Exports of goods and services","P61":"Exports of goods","P61A":"Re-export of goods","P61B":"Export on second hand goods","P61C":"Merchanting","P61D":"goods sent abroad before processing (outward processing, ie. your country is the principal)","P61E":"goods sent abroad after processing (inward processing, ie. your country processes)","P62":"Exports of services","P62D":"processing fees","P62F":"Exports of FISIM","P6A":"Re-exports","P7":"Imports of goods and services","P71":"Imports of goods","P72":"Imports of services","P72F":"Imports of FISIM","POP":"Total population","PTC":"Total payable tax credits","PTOT":{"name":"Term of trade","desc":"(P6.V/P6.L)/(P7.V/P7.L)*100"},"RDEP":"Depreciation rate (PIM)","RRET":"Retirement rate (PIM)","RREV":"Revaluation rate (PIM)","RTOT":{"name":"Total rate (PIM)","desc":"RTOT = RDEP + RRET + RREV"},"SAL":"Employees","SELF":"Self employed","T":"Transactions","TC":"of which payable tax credits that exceed the taxpayer's liability","TFU":"Total final use","TR1":"Total resources production account","TR211":"Total resources generation of income account","TR212":"Total resources allocation of primary income account","TR22":"Total resources secondary distribution of income account","TR241":"Total resources use of disposable income account","TR311":"Total change in liabilities and net worth, change in net worth due to: saving and capital transfers account","TR312":"Total change in liabilities and net worth, acquisitions of non-financ:i al assets accounts","TS":"Total supply","TU":"Total use","TU1":"Total uses production account","TU211":"Total uses generation of income account","TU212":"Total uses allocation of primary income account","TU22":"Total uses secondary distribution of income account","TU241":"Total uses use of disposable income account","TU311":"Total change in assets, change in net worth due to saving and capital: transfers account","TU312":"Total change in assets, acquisitions of non-financial assets accounts","TUADJ":"Total intermediate consumption/final use","TUXP7":"Domestic use","ULC_HW":"Unit Labour Cost (based on hours worked)","ULC_PS":"Unit Labour Cost (based on persons)","UNE":{"name":"Unemployed persons","desc":"Registered unemployment"},"UPR":"Unit profits","YA0":"Statistical discrepancy (expenditure approach)","YA1":"Statistical discrepancy (production approach)","YA2":"Statistical discrepancy (income approach)","YA3":"Statistical discrepancies in Stock Flow Adjustment","YA3O":"Other statistical discrepancies (+/-) in Stock Flow Adjustment","YSD1":"Transaction imbalance","YSD2":"Budget imbalance"}},"CL_NA_TABLEID":{"name":"NA Table IDs","codes":{"ECB_GFS_1A":"ECB GFS Guideline, Table 1A: Government revenue and expenditure","ECB_GFS_1B":"ECB GFS Guideline, Table 1B: EU budget transactions","ECB_GFS_1C":"ECB GFS Guideline, Table 1C: Government final consumption expenditure and other non-financial transactions","ECB_GFS_2A":"ECB GFS Guideline, Table 2A: Government deficit and its financing","ECB_GFS_2B":"ECB GFS Guideline, Table 2B: Transactions in Maastricht debt - consolidation","ECB_GFS_3A":"ECB GFS Guideline, Table 3A: Government gross debt","ECB_GFS_3B":"ECB GFS Guideline, Table 3B: Government gross debt - consolidating elements","EDP_FC":"Supplementary tables for the financial crisis","EDP1":"EDP Table 1 - Reporting of government deficit/surplus and debt levels","EDP2":"EDP Table 2 - Transition between the public accounts budget balance and the central government deficit/surplus","EDP3":"EDP Table 3 - Contributions of the deficit/surplus and the other relevant factors to the variation in the debt level and the consolidation of debt","EDP4":"EDP Table 4 - Other data in accordance with the statements contained in the Council minutes of 22/11/1993","EDPQ":"Questionnaire related to the EDP notification tables","GFS_ALL":"ECB GFS Guideline, all GFS tables","IMF_GFS_BS":"IMF IFS GFS, Balance sheet","IMF_GFS_S2":"IMF GFS Yearbook, Statement II: Statement of sources and uses of cash","IMF_GFS_SO":"IMF IFS GFS, Statement of operations","IMF_GFS_T1":"IMF GFS Yearbook, Table 1 - Revenue","IMF_GFS_T2":"IMF GFS Yearbook, Table 2 - Expense","IMF_GFS_T3":"IMF GFS Yearbook, Table 3 - Transactions in assets and liabilities","IMF_GFS_T4":"IMF GFS Yearbook, Table 4 - Revaluations in assets and liabilities","IMF_GFS_T5":"IMF GFS Yearbook, Table 5 - Other volume changes in assets and liabilities","IMF_GFS_T6":"IMF GFS Yearbook, Table 6 - Stock Positions in assets and liabilities","IMF_GFS_T6A":"IMF GFS Yearbook, Table 6A - Debt Liabilities at Nominal/Market Value","IMF_GFS_T6B":"IMF GFS Yearbook, Table 6B - Debt Liabilities at Face Value","IMF_GFS_T7":"IMF GFS Yearbook, Table 7 - Expenditure by Functions of Government (COFOG)","IMF_GFS_T8A":"IMF GFS Yearbook, Table 8A - Transactions in financial assets and liabilities by counterpart sector","IMF_GFS_T8B":"IMF GFS Yearbook, Table 8B - Stock positions in financial assets and liabilities by counterpart sector","IMF_GFS_T9":"IMF GFS Yearbook, Table 9 - Other economic flows in assets and liabilities","MUFA_ALL":"ECB MUFA Guideline, all MUFA tables","MUFA1":"ECB MUFA Guideline, Table 1: Non-consolidated financial assets","MUFA10":"ECB MUFA Guideline, Table 1: Consolidated financial assets","MUFA11":"ECB MUFA Guideline, Table 2: Consolidated financial liabilities","MUFA2":"ECB MUFA Guideline, Table 2: Non-consolidated financial liabilities","MUFA3":"ECB MUFA Guideline, Table 3: Deposits","MUFA4":"ECB MUFA Guideline, Table 4: Short-term loans","MUFA5":"ECB MUFA Guideline, Table 5: Long-term loans","MUFA6":"ECB MUFA Guideline, Table 6: Shot-term debt securities","MUFA7":"ECB MUFA Guideline, Table 7: Long-term debt securities","MUFA8":"ECB MUFA Guideline, Table 8: Listed shares","MUFA9":"ECB MUFA Guideline, Table 9: Investment fund shares","PSD":"Table PSD - Public sector debt","R15_FIN_SF":"G-20 recommendation 15 framework - financial stocks and flows","R15_NONFIN_S":"G-20 recommendation 15 framework - stocks of non-financial assets","R15_NONFIN_T":"G-20 recommendation 15 framework - non-financial transactions","T0101":"Table 0101 - Gross value added at basic prices and gross domestic product at market prices","T0101T0103":"Tables 0101, 0102 and 0103","T0102":"Table 0102 - GDP identity from the expenditure side","T0103":"Table 0103 - GDP identity from the income side","T0107":"Table 0107 - Disposable income, saving, net lending / borrowing","T0110":"Table 0110 - Population and employment","T0111":"Table 0111 - Employment by industry","T0117":"Table 0117 - Final consumption expenditure of households by durability","T0117_0501_0502":"Tables 0117, 0501 and 0502","T0119":"Table 0119 - Simplified non-financial accounts by institutional sector","T0120":"Table 0120 - Exports of goods (fob) and services by Member States of the EU / third countries.","T0121":"Table 0121 - Imports of goods (fob) and services by Member States of the EU/third countries","T0199":"Table 01xx - Source from various table 01 sub-tables","T01EMP":"Table 01EMP - Employment and breakdown by industry and population","T01GDP":"Table 01GDP - GDP, components and breakdowns","T0200":"Table 0200 - Main aggregates of general government","T0301":"Table 0301- Output and income","T0302":"Table 0302 - Capital formation","T0302_2200":"Tables 0302 and 2200","T0303":"Table 0303 - Employment","T0501":"Table 0501 - Final consumption expenditure of households by purpose","T0502":"Table 0502 - Final consumption expenditure of households","T0610":"Table 0610 - Financial accounts by sector (transactions), consolidated","T0611":"Table 0611 - Other change in volume accounts, consolidated","T0612":"Table 0612 - Revaluation of financial instruments accounts, consolidated","T0620":"Table 0620 - Financial accounts by sector (transactions), non-consolidated","T0621":"Table 0621 - Other change in volume accounts, non-consolidated","T0622":"Table 0622 - Revaluation of financial instruments accounts, non-consolidated","T0625":"Table 0625 - Financial accounts by sector (transactions), counterpart information, non-consolidated","T0710":"Table 0710 - Balance sheets for financial assets and liabilities (stocks), consolidated","T0720":"Table 0720 - Balance sheets for financial assets and liabilities (stocks), non-consolidated","T0725":"Table 0725 - Balance sheets for financial assets and liabilities (stocks), counterpart information, non-consolidated","T0800":"Table 0800 - Non-financial accounts by sector - annual","T0801":"Table 0801 - Non-financial accounts by sector - quarterly","T0801SA":"Table 0801SA - QSA Quarterly sector accounts: seasonally adjusted and volume data","T0900":"Table 0900 - Detailed tax and social contribution receipts by type of tax or social contribution and receiving sub-sector including the list of taxes and social contributions according to national cla","T0999":"Table 0999 - Questionnaire NTL - Detailed list of taxes and social contributions according to national classification","T1001":"Table 1001 - Tables by region (NUTS II)","T1002":"Table 1002 - Tables by industry and by region (NUTS II)","T1100":"Table 1100 - General Government expenditure by function","T1200":"Table 1200 - Tables by industry, A6 and by region (NUTS III)","T1300":"Table 1300 - Households accounts by region (NUTS II)","T1500":"Table 1500 - Supply table at basic prices, including a transformation into purchasers' prices","T1600":"Table 1600 - Use Table at purchasers' prices","T1601":"Table 1601 - Use table for domestic input at purchasers' prices","T1602":"Table 1602 - Use table for imports at purchasers' prices","T1610":"Table 1610 - Use table at basic prices","T1611":"Table 1611 - Use table for domestic input at basic prices","T1612":"Table 1612 - Use table for imports at basic prices","T1620":"Table 1620 - Trade and transport margins","T1630":"Table 1630 - Taxes less subsidies on products","T1631":"Table 1631 - Taxes less subsidies on products - excluding VAT","T1632":"Table 1632 - Value added tax","T1633":"Table 1633 - Taxes on products","T1634":"Table 1634 - Subsidies on products","T1700":"Table 1700 - Symmetric Input-output table (product*product)","T1750":"Table 1700 - Symmetric Input-output table (industry*industry)","T1800":"Table 1800 - Symmetric Input-output table for domestic production (product*product)","T1850":"Table 1850 - Symmetric Input-output table for domestic production (industry*industry)","T1900":"Table 1900 - Symmetric Input-output table for imports (product*product)","T1950":"Table 1950 - Symmetric Input-output table for imports (industry*industry)","T2000":"Table 2000 - Cross-classification of fixed assets by industry and by asset","T2200":"Table 2200 - Cross-classification of gross fixed capital formation by industry and by asset","T2500":"Table 2500 - Quarterly non-financial accounts for general government","T2600":"Table 2600 - Balance sheets for non-financial assets","T2700":"Table 2700 - Quarterly financial accounts of general government","T2800":"Table 2800 - Quarterly government debt (Maastricht debt)","T2899":"Table 2899 - Quarterly intergovernmental lending by counter-party government","T2900":"Table 2900 - Pension schemes in social insurance: base case","T2901":"Table 2901 - Pension schemes in social insurance: sensitivity analysis 1","T2902":"Table 2902 - Pension schemes in social insurance: sensitivity analysis 2","T7HH":"Table 7HH - Households' assets and liabilities","T7II":"Table 7II - Institutional investors","TSB720":"Table SB720 - Non-bank financial intermediation (financial stocks), non-consolidated"}},"CL_REF_PERIOD_DTL":{"name":"Reference period detail codes","codes":{"C":"Calendar year","F02":"Fiscal year starting in February","F03":"Fiscal year starting in March","F04":"Fiscal year starting in April","F05":"Fiscal year starting in May","F06":"Fiscal year starting in June","F07":"Fiscal year starting in July","F08":"Fiscal year starting in August","F09":"Fiscal year starting in September","F10":"Fiscal year starting in October","F11":"Fiscal year starting in November","F12":"Fiscal year starting in December","F_O":"Fiscal year (other definition)"}},"CL_SECTOR":{"name":"Sector codes","codes":{"_Z":"Not applicable","S1":{"name":"Total economy","desc":"S1=S11+S12+S13+S14+S15+S1N"},"S11":"Non financial corporations","S11001":"Public non financial corporations","S110011":"Public non financial corporations, which are part of domestic multinationals","S11001C":"Public non financial corporations controlled by central government","S11002":"National private non financial corporations","S110021":"National private non financial corporations, which are part of domestic multinationals","S11003":"Foreign controlled non financial corporations","S1100P":{"name":"Private nonfinancial corporations","desc":"S1100P=S11002+S11003"},"S11A":"Post office giro","S11B":"Head offices of non financial corporations","S11DO":{"name":"Domestically controlled non-financial corporations","desc":"S11DO=S11001+S11002"},"S11E":"Electronic money non-financial corporations","S11U":"Non-financial corporations (sub-sector not identified)","S12":{"name":"Financial corporations","desc":"S12=S12K+S12M"},"S12001":"Public financial corporations","S120011":"Public financial corporations, which are part of domestic multinationals","S12001C":"Public financial corporations controlled by central government","S12002":"National private financial corporations","S120021":"National private financial corporations which are part of domestic multinationals","S12003":"Foreign controlled financial corporations","S1200P":{"name":"Private financial corporations","desc":"S1200P=S12002+S12003"},"S121":"Central bank","S122":"Deposit taking corporations, except the Central Bank","S12201":"Public deposit taking corporations, except the Central Bank","S12202":"National private deposit taking corporations, except the Central Bank","S12203":"Foreign controlled deposit taking corporations, except the Central Bank","S1220P":{"name":"Private deposit-taking corporations","desc":"S1220P=S12202+S12203"},"S122A":"Banks headquartered in the reporting country or currency area","S122B":"Banks headquartered outside the reporting country or currency area","S122C":"Credit institutions","S122U":"Deposit taking corporations, except the Central Bank (sub-sector not identified)","S122Z":"Deposit-taking corporations except the central bank and excluding electronic money institutions principally engaged in financial intermediation","S123":"Money market funds","S12301":"Public money market funds","S12302":"National private money market funds","S12303":"Foreign controlled money market funds","S123A":"Constant Net Asset Value (NAV) MMFs","S123B":"Variable NAV MMFs","S123U":"Money market funds (sub-sector not identified)","S124":{"name":"Non MMF investment funds","desc":"S124=S124A+S124B"},"S12401":"Public non MMF investment funds","S12402":"National private non MMF investment funds","S12403":"Foreign controlled non MMF investment funds","S124A":{"name":"Open-end Non MMFs","desc":"S124=S124A+S124B; S124=S12401+S12402+S12403"},"S124A1":"Non-MMFs Open end funds - Real estate funds","S124A2":"Non-MMFs Open end funds - Equity funds","S124A3":"Non-MMFs Open end funds - Bond funds","S124A4":"Non-MMFs Open end funds - Mixed or balanced funds","S124A5":"Non-MMFs Open end funds - Hedge funds","S124A9":{"name":"Other Non-MMFs Open end funds","desc":"S124A9 = S124A - S124A1 - S124A2 \u2013S 124A3 - S124A4 \u2013 S124A5"},"S124B":{"name":"Closed-end Non MMFs","desc":"S124B=S124B1+S124B2+S124B3+S124B4+S124B5+S124B9"},"S124B1":"Closed-end Real Estate Funds","S124B2":"Closed-end Equity funds","S124B3":"Closed-end Bond funds","S124B4":"Closed-end Mixed funds","S124B5":"Closed-end Hedge funds","S124B9":{"name":"Other closed-end Non MMFs","desc":"S124B9=S124B-S124B1-S124B2-S124B3-S124B4-S124B5"},"S124U":"Non MMF investment funds (sub-sector not identified)","S125":"Other financial intermediaries, except insurance corporations and pension funds","S12501":"Public other financial intermediaries, except insurance corporations and pension funds","S12502":"National private other financial intermediaries, except insurance corporations and pension funds","S12503":"Foreign controlled other financial intermediaries, except insurance corporations and pension funds","S125A":{"name":"Financial vehicle corporations engaged in securitisation","desc":"(part of S125)"},"S125B":"Financial corporations engaged in lending","S125C":"Security and derivative dealers","S125D":"Specialised financial corporations","S125D1":"Clearing houses, which are part of specialised financial corporations (deprecated)","S125E":{"name":"Other OFIs","desc":"S125E = S125 \u2013 S125A \u2013 S125B \u2013 S125C \u2013 S125D"},"S125E1":"Central clearing counterparties, which are part of other OFIs","S125U":"Other financial intermediaries, except insurance corporations and pension funds (sub-sector not identified)","S125W":{"name":"Other financial intermediaries, excluding financial vehicle corporations engaged in securitizations","desc":"S125W = S125 - S125A"},"S126":"Financial auxiliaries","S12601":"Public financial auxiliaries","S12602":"National private financial auxiliaries","S12603":"Foreign controlled financial auxiliaries","S126B":"Head offices of financial corporations","S126C":"Payment institutions","S126U":"Financial auxiliaries (sub-sector not identified)","S127":"Captive financial institutions and money lenders","S12701":"Public captive financial institutions and money lenders","S12702":"National private captive financial institutions and money lenders","S12703":"Foreign controlled captive financial institutions and money lenders","S1271":"Trusts, estate and agency accounts","S1272":"Corporate groups' captive financial entities","S1272A":"Of which: Foreign owned SPE-type captives","S1273":{"name":"Other captive finance companies and money lenders","desc":"S1273 = S127 \u2013 S1271 \u2013 S1272"},"S1274":"Other captive finance companies and money lenders (deprecated)","S127A":"Holding companies","S127U":"Captive financial institutions and money lenders (sub-sector not identified)","S128":{"name":"Insurance corporations","desc":"S128=S1281+S1282"},"S12801":"Public insurance corporations","S12802":"National private insurance corporations","S12803":"Foreign controlled insurance corporations","S1281":"Life Insurance Corporations","S1282":"Non-life Insurance Corporations","S128A":"Reinsurance corporations","S128B":"Life insurance corporations excluding reinsurance corporations","S128C":"Non-life insurance corporations excluding reinsurance corporations","S128D":"Composite life and non-life insurance corporations excluding reinsurance corporations","S128U":"Insurance corporations (sub-sector not identified)","S129":"Pension funds","S12901":"Public pension funds","S12902":"National private pension funds","S12903":"Foreign controlled pension funds","S129A":"Defined benefit funds","S129B":"Defined contribution funds","S129U":"Pension funds (sub-sector not identified)","S12A":"Banks and other financial institutions headquartered in the reporting country or currency area","S12B":"Banks and other financial institutions headquartered outside the reporting country or currency area","S12C":{"name":"Deposit taking corporations","desc":"S12C=S121+S122"},"S12D":{"name":"Financial corporations other than central banks","desc":"S12D=S12-S121"},"S12DO":"Domestically controlled financial corporations","S12E":"Electronic money institutions","S12K":{"name":"Monetary financial institutions (MFI)","desc":"S12K=S121+S122+S123"},"S12KU":"Monetary financial institutions (sub-sector not identified)","S12L":{"name":"Investment Funds (MMFs and non-MMFs)","desc":"S12L=S123+S124 S12L=S12L1+S12L2+S12L3+S12L4+S12L5+S12L9 S12L=S12LO+S124B"},"S12L1":{"name":"Real estate funds","desc":"S12L1=S12LO1+S124B1"},"S12L2":{"name":"Equity funds","desc":"S12L2=S12LO2+S124B2"},"S12L3":{"name":"Bond funds","desc":"S12L3=S12LO3+S124B3"},"S12L4":{"name":"Mixed funds","desc":"S12L4=S12LO4+S124B4"},"S12L5":{"name":"Hedge funds","desc":"S12L5=S12LO5+S124B5"},"S12L9":{"name":"Other funds (other than equity, bond, mixed, real estate and hedge funds)","desc":"S12L9=S12LO9+S124B9"},"S12LO":{"name":"Open-end Investment Funds","desc":"S12LO=S123+S124A S12LO=S12LO1+S12LO2+S12LO3+S12LO4+S12LO5+S12LO9"},"S12LO1":"Open-end Real Estate Funds","S12LO2":"Open-end Equity funds","S12LO3":"Open-end Bond funds","S12LO4":"Open-end Mixed funds","S12LO5":"Open-end Hedge funds","S12LO9":{"name":"Other open-end funds","desc":"S12LO9=S12LO-S12LO1-S12LO2-S12LO3-S12LO4-S12LO5"},"S12M":{"name":"Financial corporations other than MFIs","desc":"S124+S125+S126+S127+S128+S129"},"S12N":{"name":"Other financial institutions (Financial corporations other than MFIs, insurance corporations, pension funds and financial auxiliaries)","desc":"S12N=S124+S125+S127"},"S12O":{"name":"Other financial institutions (Financial corporations other than MFIs, insurance corporations, pension funds and non MMFs Investment Funds)","desc":"S12O=S125+S126+S127"},"S12P":{"name":"Other financial institutions (Financial corporations other than MFIs, insurance corporations and pension funds)","desc":"S12P=S124+S125+S126+S127"},"S12PU":"Other Financial Institutions (sub-sector not identified)","S12Q":{"name":"Insurance corporations and Pension Funds","desc":"S12Q=S128+S129"},"S12QU":"Other insurance corporations and pension funds (sub-sector not identified)","S12R":{"name":"Other financial corporations","desc":"S12R=S123+S124+S125+S126+S127+S128+S129"},"S12R01":{"name":"Other public financial corporations","desc":"S12R=S12301+S12401+S12501+S12601+S12701+S12801+S12901"},"S12R0P":{"name":"Other private financial corporations","desc":"S12R=S12302+S12303+S12402+S12403+S12502+S12503+S12602+S12603+S12702+S12703+S12802+S12803+S12902+S12903"},"S12S":"Other Forms of Institutional Savings","S12SP":"Financial corporations, SPEs","S12T":{"name":"Monetary financial institutions other than central bank","desc":"S12T=S122+S123"},"S12U":"Financial corporations other than the central bank","S12V":"Financial corporations other than central banks and credit institutions","S13":{"name":"General government","desc":"S13=S1311+S1312+S1313+S1314; S13=S1321+S1322+S1323"},"S131":"General government excluding social security","S1311":"Central government excluding social security","S13111":"Central government, budgetary units","S13112":"Central government, extra-budgetary units","S1311B":"Budgetary Central Government","S1312":"State government excluding social security","S13121":"State government, budgetary units","S13122":"State government, extra-budgetary units","S1313":"Local government excluding social security","S13131":"Local government, budgetary units","S13132":"Local government, extra-budgetary units","S1314":"Social security funds","S13141":"Social security funds, budgetary units","S13142":"Social security funds, extra-budgetary units","S1315":"European institutions and bodies (EU accounts)","S1321":"Central government including social security","S1322":"State government including social security","S1323":"Local government including social security","S133":"General government non profit institutions","S1331":"Central government non profit institutions","S1332":"State government non profit institutions","S1333":"Local government non profit institutions","S134":"General government involved in monetary policy operations","S13L":{"name":"Central and state government excluding social security","desc":"S13L=S1311+S1312"},"S13M":{"name":"State and local government excluding social security","desc":"S13M=S1312+S1313"},"S13O":{"name":"General government, except central government","desc":"S13O=S13-S1311"},"S13P":{"name":"General government, except state government","desc":"S13P=S13-S1312"},"S13R":{"name":"General government, except local government","desc":"S13R=S13-S1313"},"S13T":{"name":"General government, except social security funds","desc":"S13T=S13-S1314"},"S13U":"Other General Government (sub-sector not identified)","S14":"Households","S141":"Employers","S142":"Own account workers","S143":"Employees","S144":"Recipients of property and transfer income","S1441":"Recipients of property income","S1442":"Recipients of pensions","S1443":"Recipients of other transfers","S15":"Non profit institutions serving households","S15002":"National private","S15003":"Foreign controlled","S1A":"Affiliates","S1B":{"name":"Not affiliates","desc":"S1B=S1-S1A"},"S1F":"Financial intermediaries (CDIS)","S1G":"All resident sectors excluding financial intermediaries (CDIS)","S1H":"Issuer headquartered in the reporting country or currency area","S1K":{"name":"Corporations","desc":"S1K=S11+S12"},"S1K1":{"name":"Public corporations","desc":"S1K1=S11001+S12001"},"S1KK":"Central banks and general government","S1KP":{"name":"Private corporations","desc":"S1KP=S1100P+S1200P"},"S1L":{"name":"General government, households and non profit institutions serving households","desc":"S1L=S13+S14+S15"},"S1M":{"name":"Households and non profit institutions serving households (NPISH)","desc":"S1M=S14+S15"},"S1MU":"Other households and non-profit institutions serving households (sub-sector not identified)","S1N":"Not sectorised","S1O":{"name":"Other sectors than MFIs and central government","desc":"S1O=S1V+S12M+S13O; S1O=S11+S14+S15+S124+S125+S126+S127+S128+S129+S1312+S1313+S1314"},"S1P":{"name":"Other sectors than MFIs and general government","desc":"S1P=S1V+S12M; S1P=S11+S14+S15+S124+S125+S126+S127+S128+S129"},"S1Q":{"name":"Other sectors than MFIs","desc":"S1Q=S1S+S12M; S1Q=S11+S13+S14+S15+S124+S125+S126+S127+S128+S129"},"S1R":{"name":"Non financial sectors, except households","desc":"S1R=S11+S13+S15"},"S1S":{"name":"Non-financial corporations, general government and households and NPISH","desc":"S1S=S11+S13+S14+S15"},"S1SP":{"name":"Total economy, SPEs","desc":"S1SP=S12SP+S1SSP"},"S1SSP":"Non-financial corporations, SPEs","S1T":{"name":"Non-financial corporations and general government","desc":"S1T=S11+S13"},"S1U":{"name":"Non financial sectors, except central government","desc":"S1U=S1V+S13O; S1U=S11+S14+S15+S1312+S1313+S1314"},"S1V":{"name":"Non financial corporations, households and NPISH","desc":"S1V=S11+S14+S15"},"S1W":{"name":"Other sectors than general government","desc":"S1W=S11+S12+S14+S15+S1N"},"S1X":{"name":"Monetary authorities","desc":"S1X=S121+ S134"},"S1XA":"Monetary authorities and international organizations","S1Y":{"name":"Other sectors than monetary authorities","desc":"S1Y=S1-S1X-S1N"},"S1Z":{"name":"Sectors other than deposit-taking corporations and general government (Other Sectors - BPM6)","desc":"S1Z=S11+S14+S15+S123+S124 +S125+S126+S127+S128+S129"},"S1ZK":{"name":"Other sectors than central bank","desc":"S1ZK=S1-S121-S1N"},"S1ZL":{"name":"Other sectors than central bank and general government","desc":"S1ZL=S1-S121-S13-S1N"},"S1ZM":{"name":"Other sectors than central government","desc":"S1ZM=S1-S1311-S1N"},"S1ZN":{"name":"Other sectors than state government","desc":"S1ZN=S1-S1312-S1N"},"S1ZO":{"name":"Other sectors including non-financial corporations, money market funds, non-MMF investment funds, OFIs, insurance corporations, pension funds, general government or a central bank","desc":"S1ZO=S1-S1M-S122= S11+S13+S121+S123+S124+S125+S128+S129"},"S1ZP":{"name":"Other sectors than local government","desc":"S1ZP=S1-S1313-S1N"},"S1ZQ":{"name":"Other sectors than social security funds","desc":"S1ZQ=S1-S1314-S1N"},"S1ZR":{"name":"Other sectors than financial corporations and general government","desc":"S1ZR=S1-S12-S13-S1N"},"S1ZS":{"name":"Public sector","desc":"S1ZS=S11001+S12001+S13"},"S1ZT":{"name":"National private financial and non financial corporations","desc":"S1ZT=S11002+S12002+S15002"},"S1ZU":"Sectors other than central bank, credit institutions and general government","S1ZV":{"name":"All sectors other than households and NPISH","desc":"S1ZV=S1-S1M;S1ZV=S11+S13+S121+S122+S123+S124+S125+S128+S129"},"SZP":"Other than general government, clearing and settlement organisations and other financial institutions","SZU":"Institutions of the European Union (ESA GFS concept)","SZV":{"name":"General government and institutions of the European Union (ESA GFS concept)","desc":"SZV=SZU+S13"},"SZX":"Institutions financed by the European Union (EU) budget (including the European Development Fund (EDF))","SZY":"General government and institutions financed by the European Union (EU) budget (including the European Development Fund (EDF))"}},"CL_VALUATION":{"name":"Valuation","codes":{"_X":"Not allocated/unspecified (including all kinds of valuation methods)","_Z":"Not applicable","A":"Accrual","B":"Basic prices","C":"Cash","E":"Accumulation of FDI equity capital flow","F":"Face value","H":"Historic acquisition cost","I":"Stock market price index applied to accumulated FDI equity capital flow","M":"Market value","N":"Nominal value","O":"Purchasers prices","P":"Producer prices","R":"Redemption value","S":"Standard valuation based on SNA/ESA","T":"Net marked to market value","U":"Fair value","V":"Book value","W":"Notional valuation"}},"CL_ACCOUNT_ENTRY":{"name":"Accounting entry code list","codes":{"_X":"Unspecified","_Z":"Not applicable","A":"Assets (Net Acquisition of)","AD":"Gross sales of assets (decrease)","AI":"Gross acquisition of assets (increase)","AS":"Assets - short position","B":"Balance (Credits minus Debits)","C":"Credit (Resources)","CL":"Contingent liabilities (EDP and GFS)","D":"Debit (Uses)","FI":"Inflows (reserves template)","FN":"Net flows (reserves template)","FO":"Outflows (reserves template)","II":"Net income on inward FDI","IO":"Net income on outward FDI","L":"Liabilities (Net Incurrence of)","LD":"Gross decrease in liabilities","LI":"Gross incurrence of liabilities","N":"Net (Assets minus Liabilities)","NE":"Net Liabilities (Liabilities minus Assets)","NI":"Net FDI Inward","NO":"Net FDI Outward","DT":"Transformation use","DE":"End use","DER":"End use, of which emissions relevant","EC":"Economy to environment","EN":"Environment to economy","C_EN":"Credit (Environment + Economy)","D_EN":"Debit (Environment + Economy)","DT_EN":"Transformation use (Environment + Economy)","DE_EN":"End use (Environment + Economy)"}},"CL_TIME_COLLECT":{"name":"Time period collection code list","codes":{"A":"Average of observations through period","B":"Beginning of period","E":"End of period","H":"Highest in period","L":"Lowest in period","M":"Middle of period","S":"Summed through period","U":"Unknown","V":"Other","Y":"Annualised summed"}},"CL_VALUE":{"name":"Value","codes":{"R":"Real","N":"Nominal"}},"CL_TC_LENDERS":{"name":"Lenders","codes":{"A":"All sectors","B":"Banks, domestic"}},"CL_OD_INSTR":{"name":"Instrument","codes":{"A":"All instruments","B":"Total foreign exchange including gold","C":{"name":"Forwards and swaps","desc":"A forward a is contract between two parties for the delayed delivery of financial instruments or commodities in which the buyer agrees to purchase and the seller agrees to deliver, on an agreed future date, a specified instrument or commodity at an agreed price oryield. Forward contracts are general"},"D":"Forwards and swaps including gold","E":{"name":"Currency swaps","desc":"Contract between two parties to exchange sequences of payments during a specified period, where each sequence is tied to a different currency. At the end of the swap, principal amounts in the different currencies are usually exchanged."},"F":{"name":"Forward rate agreements","desc":"Interest rate forward contract in which the rate to be paid or received on a specific obligation for a set period of time, beginning at some time in the future, is determined at contract initiation."},"G":{"name":"Interest rate swaps","desc":"Contract to exchange periodic payments related to interest rates on a single currency; can be fixed for floating, or floating for floating based on different indices. This group includes those swaps whose notional principal is amortised according to a fixed schedule independent of interest rates."},"H":"Options, total","I":"Options sold","J":"Options sold including gold","K":"Options bought","L":"Options bought including gold","M":"Other instruments","N":{"name":"Single-name CDS","desc":"Credit derivative where the reference entity is a single name."},"O":{"name":"Multi-name CDS","desc":"CDS contract that references more than one name - for example, portfolio or basket CDS, or CDS index."},"P":"FX Forwards and swaps + Currency swaps","Q":"IR Forward rate agreements + Interest rate swaps","R":{"name":"Index products","desc":"Multi-name CDS contracts with constituent reference credits and a fixed coupon that are determined by an administrator such as Markit (which administers the CDX and iTraxx indices). Index products include tranches of CDS indices."},"S":{"name":"Credit default swaps","desc":"Contract whereby the seller commits to repay an obligation (eg bond) underlying the contract at par in the event of a default. To produce this guarantee, a regular premium is paid by the buyer during a specified period."},"T":"Total futures"}},"CL_OD_RISK_CAT":{"name":"Risk category","codes":{"A":"All categories","B":"Foreign exchange","C":"Interest rate","D":"Equity","E":"Gold","F":"Precious metals","G":"Other commodities","H":"All commodities","I":{"name":"Interest rate, short-term","desc":"Derivative whose redemption value is linked to specified credit-related events, such as bankruptcy, credit downgrade, non-payment or default of a borrower. For example, a lender might use a credit derivative to hedge the risk that a borrower might default. Common credit derivatives include credit de"},"J":"Interest rate, long-term","K":"Financials","L":"Agricultural commodities","M":"Energy products","N":"Non-precious metals","P":"Precious metals incl gold","S":"Stockmarket index","W":"Other risk categories n.i.e.","Y":"Credit derivatives","Z":"Other"}}},"concepts":{"COMMENTARY":{"name":"COMMENTARY","desc":"COMMENTARY URL"},"MARKET_ISSUE":{"name":"Market Issue","desc":"Market of issuance"},"COLL_PERIOD":{"name":"Collection period","desc":"Period in which data was collected"},"CURRENCY":{"name":"Currency code used for compilation","desc":"Used to specify the underlying currency if in UNIT_MEASURE e.g. XDC is used"},"DISS_ORG":{"name":"Dissemination organisation","desc":"The organisation disseminating the data"},"ACCESSIBILITY":{"name":"Accessibility","desc":"The ease and the conditions under which statistical information can be obtained."},"ACCURACY":{"name":"Accuracy","desc":"Closeness of computations or estimates to the exact or true values that the statistics were intended to measure."},"ACCURACY_OVERALL":{"name":"Accuracy - overall","desc":"Assessment of accuracy, linked to a certain data set or domain, which is summarising the various components into one single measure."},"NONSAMPLING_ERR":{"name":"Accuracy - non-sampling error","desc":"Error in sample estimates which cannot be attributed to sampling fluctuations."},"SAMPLING_ERR":{"name":"Accuracy - sampling error","desc":"That part of the difference between a population value and an estimate thereof, derived from a random sample, which is due to the fact that only a subset of the population is enumerated."},"ADJUSTMENT":{"name":"Adjustment","desc":"The set of procedures employed to modify statistical data to enable it to conform to national or international standards or to address data quality differences when compiling specific data sets."},"ADJUST_CODED":{"name":"Adjustment - coded","desc":"Type of adjustment used, represented by a code."},"ADJUST_DETAIL":{"name":"Adjustment - detail","desc":"Textual description of the type of adjustment used."},"AGE":{"name":"Age","desc":"The length of time that a person has lived or a thing has existed."},"BASE_PER":{"name":"Base Period","desc":"The period of time used as the base of an index number, or to which a constant price series refers."},"CIVIL_STATUS":{"name":"Civil status","desc":"Legal, conjugal status of each individual in relation to the marriage laws or customs of the country."},"CLARITY":{"name":"Clarity","desc":"The extent to which easily comprehensible metadata are available, where these metadata are necessary to give a full understanding of statistical data."},"CLASS_SYSTEM":{"name":"Classification system","desc":"Arrangement or division of objects into groups based on characteristics which the objects have in common."},"COHERENCE":{"name":"Coherence","desc":"Adequacy of statistics to be combined in different ways and for various uses."},"COHER_X_DOM":{"name":"Coherence - cross-domain","desc":"Extent to which statistics are reconcilable with those obtained through other data sources or statistical domains."},"COHER_INTERNAL":{"name":"Coherence - internal","desc":"Extent to which statistics are consistent within a given data set."},"COMMENT":{"name":"Comment","desc":"Supplementary descriptive text which can be attached to data or metadata."},"COMPARABILITY":{"name":"Comparability","desc":"The extent to which differences between statistics can be attributed to differences between the true values of the statistical characteristics."},"COMPAR_DOMAINS":{"name":"Comparability - between domains","desc":"Extent to which statistics are comparable between different statistical domains."},"COMPAR_GEO":{"name":"Comparability - geographical","desc":"Extent to which statistics are comparable between geographical areas."},"COMPAR_TIME":{"name":"Comparability - over time","desc":"Extent to which statistics are comparable or reconcilable over time."},"COMPILING_ORG":{"name":"Compiling agency","desc":"The organisation compiling the data being reported."},"CONF":{"name":"Confidentiality","desc":"A property of data indicating the extent to which their unauthorised disclosure could be prejudicial or harmful to the interest of the source or other relevant parties."},"CONF_DATA_TR":{"name":"Confidentiality - data treatment","desc":"Rules applied for treating the data set to ensure statistical confidentiality and prevent unauthorised disclosure."},"CONF_POLICY":{"name":"Confidentiality - policy","desc":"Legislative measures or other formal procedures which prevent unauthorised disclosure of data that identify a person or economic entity either directly or indirectly."},"CONF_STATUS":{"name":"Confidentiality - status","desc":"Information about the confidentiality status of the object to which this attribute is attached."},"CONTACT":{"name":"Contact","desc":"Individual or organisational contact points for the data or metadata, including information on how to reach the contact points."},"CONTACT_EMAIL":{"name":"Contact email address","desc":"E-mail address of the contact points for the data or metadata."},"CONTACT_FAX":{"name":"Contact fax number","desc":"Fax number of the contact points for the data or metadata."},"CONTACT_MAIL":{"name":"Contact mail address","desc":"The postal address of the contact points for the data or metadata."},"CONTACT_NAME":{"name":"Contact name","desc":"The name of the contact points for the data or metadata."},"CONTACT_ORGANISATION":{"name":"Contact organisation","desc":"The name of the organisation of the contact points for the data or metadata."},"ORGANISATION_UNIT":{"name":"Contact organisation unit","desc":"An addressable subdivision of an organisation."},"CONTACT_FUNCT":{"name":"Contact person function","desc":"The area of technical responsibility of the contact, such as \"methodology\", \"database management\" or \"dissemination\"."},"CONTACT_PHONE":{"name":"Contact phone number","desc":"The telephone number of the contact points for the data or metadata."},"COST_BURDEN":{"name":"Cost and burden","desc":"Costs associated with the collection and production of a statistical product and burden on respondents."},"COST_BURDEN_EFF":{"name":"Cost and burden - efficiency management","desc":"Cost-benefit analysis, effectiveness of execution of medium term statistical programmes, and ensuring efficient use of resources."},"COST_BURDEN_RES":{"name":"Cost and burden - resources","desc":"Staff, facilities, computing resources, and financing to undertake statistical production."},"VIS_AREA":{"name":"Counterpart reference area","desc":"The secondary area, as opposed to reference area, to which the measured data is in relation."},"COVERAGE":{"name":"Coverage","desc":"The definition of the population that statistics aim to cover."},"COVERAGE_SECTOR":{"name":"Coverage - sector","desc":"Main economic or other sectors covered by the statistics."},"COVERAGE_TIME":{"name":"Coverage - time","desc":"The length of time for which data are available."},"COLL_METHOD":{"name":"Data collection","desc":"Systematic process of gathering data for official statistics."},"DATA_COMP":{"name":"Data compilation","desc":"Operations performed on data to derive new information according to a given set of rules."},"DATA_EDITING":{"name":"Data editing","desc":"Activity aimed at detecting and correcting errors, logical inconsistencies and suspicious data."},"DATA_PRES":{"name":"Data presentation","desc":"Description of the disseminated data."},"DATA_DESCR":{"name":"Data presentation - data description","desc":"Main characteristics of the data set described in an easily understandable manner, referring to the data and indicators disseminated."},"DISS_DET":{"name":"Data presentation - disseminated detail","desc":"Disseminated domain, measure, and time period breakdowns of statistics in the dataset."},"DATA_PROVIDER":{"name":"Data provider","desc":"Organisation which produces data or metadata."},"DATA_REV":{"name":"Data revision","desc":"Any change in a value of a statistic released to the public."},"REV_POLICY":{"name":"Data revision - policy","desc":"Policy aimed at ensuring the transparency of disseminated data, whereby preliminary data are compiled that are later revised."},"REV_PRACTICE":{"name":"Data revision - practice","desc":"Information on the data revision practice."},"REV_STUDY":{"name":"Data revision - studies","desc":"Information about data revision studies and analyses."},"DSI":{"name":"Data set identifier","desc":"Sequence of characters identifying the data set with which it is associated."},"DATA_UPDATE":{"name":"Data update","desc":"The date on which the data element was inserted or modified in the database."},"DATA_VALIDATION":{"name":"Data validation","desc":"Process of monitoring the results of data compilation and ensuring the quality of the statistical results."},"DATA_VAL_INTER":{"name":"Data validation - intermediate","desc":"Validation that intermediate calculations leading to statistical outputs have been correctly done."},"DATA_VAL_OUTPUT":{"name":"Data validation - output","desc":"Assessment of discrepancies and other problems in statistical outputs."},"DATA_VAL_SOURCE":{"name":"Data validation - source","desc":"Assessment of discrepancies and other problems related to source data."},"DECIMALS":{"name":"Decimals","desc":"The number of digits of an observation to the right of a decimal point."},"DISS_FORMAT":{"name":"Dissemination format","desc":"Media by which statistical data and metadata are disseminated."},"MICRO_DAT_ACC":{"name":"Dissemination format - microdata access","desc":"Information on whether micro-data are also disseminated."},"NEWS_REL":{"name":"Dissemination format - news release","desc":"Regular or ad hoc press releases linked to the data."},"ONLINE_DB":{"name":"Dissemination format - online database","desc":"Information about online databases in which the disseminated data can be accessed."},"PUBLICATIONS":{"name":"Dissemination format - publications","desc":"Regular or ad hoc publications in which the data are made available to the public."},"DISS_OTHER":{"name":"Dissemination format - other formats","desc":"References to the most important other data dissemination done."},"DOC_METHOD":{"name":"Documentation on methodology","desc":"Descriptive text and references to methodological documents available."},"ADV_NOTICE":{"name":"Documentation on methodology - advance notice","desc":"Policy on notifying the public of changes in methodology, indicating whether the public is notified before a methodological change affects disseminated data and, if so, how long before."},"EDUCATION_LEV":{"name":"Education level","desc":"The highest level of an educational programme the person has successfully completed."},"EMBARGO_TIME":{"name":"Embargo time","desc":"The exact time at which the data could be made available to the public."},"FREQ":{"name":"Frequency","desc":"The time interval at which observations occur over a given time period."},"FREQ_DETAIL":{"name":"Frequency - detail","desc":"A further specification of the frequency to include more detailed information about the type of frequency and frequencies not commonly used."},"FREQ_COLL":{"name":"Frequency - data collection","desc":"Frequency with which the source data are collected."},"FREQ_DISS":{"name":"Frequency - data dissemination","desc":"The time interval at which the statistics are disseminated over a given time period."},"GROSS_NET":{"name":"Grossing / Netting","desc":"Form of consolidation used in presenting the data."},"IND_TYPE":{"name":"Index type","desc":"The type of index number used in the statistical production process."},"INST_MANDATE":{"name":"Institutional mandate","desc":"Set of rules or other formal set of instructions assigning responsibility as well as the authority to an organisation for the collection, processing, and dissemination of statistics."},"INST_MAN_SHAR":{"name":"Institutional mandate - data sharing","desc":"Arrangements or procedures for data sharing and coordination between data producing agencies."},"INST_MAN_LA_OA":{"name":"Institutional mandate - legal acts and other agreements","desc":"Legal acts or other formal or informal agreements that assign responsibility as well as the authority to an agency for the collection, processing, and dissemination of statistics."},"I_M_RES_REL":{"name":"Institutional mandate - respondent relations","desc":"Measures to encourage statistical reporting and/or to sanction non-reporting."},"M_AGENCY":{"name":"Maintenance agency","desc":"The organisation or other expert body that maintains a domain-specific data or metadata structure definition."},"META_UPDATE":{"name":"Metadata update","desc":"The date on which the metadata element was inserted or modified in the database."},"META_CERTIFIED":{"name":"Metadata update - last certified","desc":"Date of the latest certification provided by the domain manager to confirm that the metadata posted are still up-to-date, even if the content has not been amended."},"META_POSTED":{"name":"Metadata update - last posted","desc":"Date of the latest dissemination of the metadata."},"META_LAST_UPDATE":{"name":"Metadata update - last update","desc":"Date of last update of the content of the metadata."},"OBS_VALUE":{"name":"Observation","desc":"The value of a particular variable at a particular period."},"OBS_PRE_BREAK":{"name":"Observation pre-break value","desc":"The observation, at a time series break period, that was calculated using the old methodology."},"OBS_STATUS":{"name":"Observation status","desc":"Information on the quality of a value or an unusual or missing value."},"OCCUPATION":{"name":"Occupation","desc":"Job or position held by an individual who performs a set of tasks and duties."},"ORIG_DATA_ID":{"name":"Originator data identifier","desc":"The data identifier as found in the originating database."},"PROF":{"name":"Professionalism","desc":"The standard, skill and ability suitable for producing statistics of good quality."},"PROF_COND":{"name":"Professionalism - code of conduct","desc":"Provision for assuring the qualifications of staff and allowing staff to perform their functions without intervention motivated by non-statistical objectives."},"PROF_IMP":{"name":"Professionalism - impartiality","desc":"Description of the elements providing assurances that statistics are produced on an impartial basis."},"PROF_METH":{"name":"Professionalism - methodology","desc":"Describes the elements providing assurances that the choices of sources and statistical techniques as well as decisions about dissemination are informed solely by statistical considerations."},"PROF_STAT_COM":{"name":"Professionalism - statistical commentary","desc":"Describes the elements providing assurances that the statistical entity is entitled to comment on erroneous interpretation and misuse of statistics."},"PUNCTUALITY":{"name":"Punctuality","desc":"Time lag between the actual delivery of the data and the target date when it should have been delivered."},"QUALITY_MGMNT":{"name":"Quality management","desc":"Systems and frameworks in place within an organisation to manage the quality of statistical products and processes."},"QUALITY_ASSMNT":{"name":"Quality management - quality assessment","desc":"Overall assessment of data quality, based on standard quality criteria."},"QUALITY_ASSURE":{"name":"Quality management - quality assurance","desc":"Guidelines focusing on quality in general and dealing with quality of statistical programmes, including measures for ensuring the efficient use of resources."},"QUALITY_DOC":{"name":"Quality management - documentation","desc":"Documentation on procedures applied for quality management and quality assessment."},"RECORDING":{"name":"Recording basis","desc":"Processes and standards employed in calculating statistical aggregates."},"REF_AREA":{"name":"Reference area","desc":"The country or geographic area to which the measured statistical phenomenon relates."},"REF_PERIOD":{"name":"Reference period","desc":"The period of time or point in time to which the measured observation is intended to refer."},"REF_PER_WGTS":{"name":"Reference period - weights","desc":"Dates or periods to which the observations used to compile the weights refer."},"REL_POLICY":{"name":"Release policy","desc":"Rules for disseminating statistical data to interested parties."},"REL_POL_LEG_ACTS":{"name":"Release policy - legal acts and other agreements","desc":"Legal acts and other agreements pertaining to data access."},"REL_COMMENT":{"name":"Release policy - policy commentary","desc":"Description of whether or not a ministerial commentary is provided on the occasion of statistical release."},"REL_CAL_POLICY":{"name":"Release policy - release calendar","desc":"The schedule of statistical release dates."},"REL_CAL_ACCESS":{"name":"Release policy - release calendar access","desc":"Access to the release calendar information."},"REL_POL_TRA":{"name":"Release policy - transparency","desc":"Dissemination of the release policy to the public."},"REL_POL_US_AC":{"name":"Release policy - user access","desc":"The policy for release of the data to users, the scope of dissemination (e.g. to the public, to selected users), how users are informed that the data are being released, and whether the policy provides for the dissemination of statistical data to all users at the same time. It also describes the pol"},"RELEVANCE":{"name":"Relevance","desc":"The degree to which statistical information meets the real or perceived needs of clients."},"COMPLETENESS":{"name":"Relevance - completeness","desc":"The extent to which all statistics that are needed are available."},"USER_NEEDS":{"name":"Relevance - user needs","desc":"Description of users and their respective needs with respect to the statistical data."},"USER_SAT":{"name":"Relevance - user satisifaction","desc":"Measure to determine user satisfaction."},"REP_AGENCY":{"name":"Reporting agency","desc":"The organisation that supplies the data for a given instance of the statistics."},"SAMPLING":{"name":"Sampling","desc":"The process of selecting a number of cases from all the cases in a particular group or universe."},"SEX":{"name":"Sex","desc":"The state of being male or female."},"SOURCE_TYPE":{"name":"Source data","desc":"Characteristics and components of the raw statistical data used for compiling statistical aggregates."},"STAT_CONC_DEF":{"name":"Statistical concepts and definitions","desc":"Statistical characteristics of statistical observations."},"STAT_POP":{"name":"Statistical population","desc":"The total membership or population or \"universe\" of a defined class of people, objects or events."},"STAT_UNIT":{"name":"Statistical unit","desc":"Entity for which information is sought and for which statistics are ultimately compiled."},"TIME_FORMAT":{"name":"Time format","desc":"Technical format in which time is represented for the measured phenomenon."},"TIME_PERIOD":{"name":"Time period","desc":"The period of time or point in time to which the measured observation refers."},"TIME_PER_COLLECT":{"name":"Time period - collection","desc":"Dates or periods during which the observations have been collected (such as middle, average or end of period) to compile the indicator for the target reference period."},"TIMELINESS":{"name":"Timeliness","desc":"Length of time between data availability and the event or phenomenon they describe."},"TIME_OUTPUT":{"name":"Timeliness - output","desc":"The lapse of time between the end of a reference period and dissemination of the data."},"TIME_SOURCE":{"name":"Timeliness - source data","desc":"The time between the end of a reference period and actual receipt of the data by the compiling agency."},"TITLE":{"name":"Title","desc":"Textual label used as identification of a statistical object."},"UNIT_MULT":{"name":"Unit multiplier","desc":"Exponent in base 10 specified so that multiplying the observation numeric values by 10^UNIT_MULT gives a value expressed in the unit of measure."},"UNIT_MEASURE":{"name":"Unit of measure","desc":"The unit in which the data values are measured."},"UNIT_MEAS_DETAIL":{"name":"Unit of measure detail","desc":"Additional textual information on the unit of measure."},"VALUATION":{"name":"Valuation","desc":"The definition of the price per unit, for goods and services, flows and asset stocks."}}}
"""

# Module-level ontology accessors.  Loaded once at import time.
_BIS_ONTOLOGY: Dict[str, Any] = json.loads(_BIS_ONTOLOGY_JSON)
_DATAFLOWS: Dict[str, Dict[str, Any]] = _BIS_ONTOLOGY["dataflows"]
_CODELISTS: Dict[str, Dict[str, Any]] = _BIS_ONTOLOGY["codelists"]
_CONCEPTS: Dict[str, Any] = _BIS_ONTOLOGY.get("concepts", {})
del _BIS_ONTOLOGY_JSON  # reclaim the parsed copy is what we need


# Code entries in _CODELISTS are stored compactly: a plain string when
# the code only has a name, a dict {name, parent?, desc?} when it has
# extra metadata (parent for hierarchical codelists, desc for long-form
# descriptions).  These accessors normalize the read.

def _code_name(entry: Any) -> str:
    """Return a code's display name regardless of compact-or-dict storage."""
    return entry["name"] if isinstance(entry, dict) else str(entry)


def _code_parent(entry: Any) -> Optional[str]:
    """Return a code's parent code id (None if root or not hierarchical)."""
    return entry.get("parent") if isinstance(entry, dict) else None


def _code_desc(entry: Any) -> Optional[str]:
    """Return a code's long-form description (None if not present)."""
    return entry.get("desc") if isinstance(entry, dict) else None


def _resolve_flow(flow_id_or_alias: str) -> str:
    """Resolve a dataflow alias or id to a canonical flow_id.

    Raises KeyError with a helpful message listing valid aliases /
    flow_ids when neither matches.  Always returns a flow_id that
    exists in the embedded ontology — bad aliases (pointing to
    retired flows) raise rather than silently returning a stale id.
    """
    if flow_id_or_alias in _DATAFLOWS:
        return flow_id_or_alias
    alias_key = flow_id_or_alias.lower().replace("_", "-")
    if alias_key in DATAFLOW_ALIASES:
        target = DATAFLOW_ALIASES[alias_key]
        if target not in _DATAFLOWS:
            raise KeyError(
                f"Alias '{flow_id_or_alias}' points to '{target}' which is "
                f"not in the embedded ontology (likely retired by BIS).  "
                f"Run refresh_ontology() to update."
            )
        return target
    suggestions = []
    needle = flow_id_or_alias.lower()
    for fid, flow in _DATAFLOWS.items():
        if needle in fid.lower() or needle in flow["name"].lower():
            suggestions.append(fid)
    msg = f"Unknown dataflow '{flow_id_or_alias}'."
    if suggestions:
        msg += f" Did you mean: {', '.join(suggestions[:5])}?"
    msg += (f" Use list_dataflows() to enumerate all {len(_DATAFLOWS)} flows"
            f" or {len(DATAFLOW_ALIASES)} aliases.")
    raise KeyError(msg)


def _flow_version(flow_id: str) -> str:
    """Return the SDMX URL version for a dataflow (per-flow, not global).

    Most BIS dataflows are at "1.0", but a few are revisioned (WS_TC is
    "2.0" as of 2026-05-09).  The embedded ontology carries the
    correct version for each flow.  Falls back to DEFAULT_VERSION
    ("1.0") if the flow is not in the embedded ontology.
    """
    return _DATAFLOWS.get(flow_id, {}).get("version", DEFAULT_VERSION)


# ─── Per-flow exemplar kwargs ─────────────────────────────────────────────
# Verified 2026-05-09 against live BIS: each entry is a minimal kwarg set
# that returns at least 1 series.  Use via query_default(flow_id) when
# PRISM wants a "show me something useful from this flow" call without
# having to figure out which dimensions are required.  Each maps to ONE
# specific slice (single country / single ccy / single sector) so the
# return is small and informative.
_FLOW_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "BIS_REL_CAL":     {"FREQ": "Q"},
    "WS_CBPOL":        {"FREQ": "M", "REF_AREA": "US"},
    "WS_CBS_PUB":      {"FREQ": "Q", "L_MEASURE": "S", "L_REP_CTY": "5A",
                        "CBS_BANK_TYPE": "4R", "CBS_BASIS": "F",
                        "L_POSITION": "I", "L_INSTR": "A", "REM_MATURITY": "A",
                        "CURR_TYPE_BOOK": "TO1", "L_CP_SECTOR": "A",
                        "L_CP_COUNTRY": "TR"},
    "WS_CBTA":         {"FREQ": "M", "REF_AREA": "US"},
    "WS_CPP":          {"FREQ": "Q", "REF_AREA": "US"},
    "WS_CREDIT_GAP":   {"FREQ": "Q", "BORROWERS_CTY": "US",
                        "TC_BORROWERS": "P", "TC_LENDERS": "A", "CG_DTYPE": "C"},
    "WS_DEBT_SEC2_PUB": {"FREQ": "Q", "ISSUER_RES": "US"},
    "WS_DER_OTC_TOV":  {"FREQ": "A", "DER_TYPE": "U", "DER_RISK": "B"},
    "WS_DPP":          {"FREQ": "Q", "REF_AREA": "US"},
    "WS_DSR":          {"FREQ": "Q", "BORROWERS_CTY": "US", "DSR_BORROWERS": "P"},
    "WS_EER":          {"FREQ": "M", "EER_TYPE": "R", "EER_BASKET": "B",
                        "REF_AREA": "US"},
    "WS_GLI":          {"FREQ": "Q", "CURR_DENOM": "USD",
                        "BORROWERS_CTY": "3P", "BORROWERS_SECTOR": "N",
                        "LENDERS_SECTOR": "A", "L_POS_TYPE": "I",
                        "L_INSTR": "B", "UNIT_MEASURE": "USD"},
    "WS_LBS_D_PUB":    {"FREQ": "Q", "L_MEASURE": "S", "L_POSITION": "C",
                        "L_INSTR": "A", "L_DENOM": "TO1", "L_CURR_TYPE": "A",
                        "L_PARENT_CTY": "5J", "L_REP_BANK_TYPE": "A",
                        "L_REP_CTY": "US", "L_CP_SECTOR": "A",
                        "L_CP_COUNTRY": "5J", "L_POS_TYPE": "N"},
    "WS_LONG_CPI":     {"FREQ": "M", "REF_AREA": "US"},
    "WS_NA_SEC_C3":    {"FREQ": "Q"},  # BIS-published-but-empty as of 2026-05-09
    "WS_NA_SEC_DSS":   {"FREQ": "Q", "REF_AREA": "US"},
    "WS_OTC_DERIV2":   {"FREQ": "H", "DER_TYPE": "A", "DER_RISK": "A"},
    "WS_SPP":          {"FREQ": "Q", "REF_AREA": "US", "VALUE": "N"},
    "WS_TC":           {"FREQ": "Q", "BORROWERS_CTY": "US", "TC_BORROWERS": "P",
                        "TC_LENDERS": "A", "VALUATION": "M", "UNIT_TYPE": "770",
                        "TC_ADJUST": "A"},
    "WS_XRU":          {"FREQ": "M", "REF_AREA": "US"},
    "WS_XTD_DERIV":    {"FREQ": "Q", "OD_TYPE": "A", "OD_RISK_CAT": "C",
                        "OD_INSTR": "A"},
    # CPMI flows — annual frequency, REP_CTY (not REF_AREA)
    "WS_CPMI_CASHLESS":{"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_CT1":     {"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_CT2":     {"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_DEVICES": {"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_INSTITUT":{"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_MACRO":   {"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_PARTICIP":{"FREQ": "A", "REP_CTY": "US"},
    "WS_CPMI_SYSTEMS": {"FREQ": "A", "REP_CTY": "US"},
}


def get_default_kwargs(flow_id: str) -> Dict[str, Any]:
    """Return a known-working kwarg set for a dataflow.

    Each dataflow has a hand-curated "show me something useful"
    minimal-kwargs set verified to return at least one series live
    against BIS.  PRISM uses this to bootstrap any flow without
    having to figure out which dim values are required.

    Args:
        flow_id: flow id or alias.

    Returns:
        dict of kwargs suitable for `query(flow_id, **kwargs)`.
        Empty dict if no defaults are registered for the flow
        (and a comment in the source explains why — typically the
        flow has no published series).
    """
    fid = _resolve_flow(flow_id)
    return dict(_FLOW_DEFAULTS.get(fid, {}))


def query_default(flow_id: str, *, start: Optional[str] = None,
                  end: Optional[str] = None,
                  timeout: int = 120,
                  **overrides: Any) -> List[Dict[str, Any]]:
    """Convenience wrapper: query(flow_id) using the curated defaults.

    Equivalent to ``query(flow_id, **{**get_default_kwargs(flow_id),
    **overrides}, start=start, end=end)``.

    Useful for "show me something from this flow" exploratory calls.
    PRISM doesn't have to know which dims are required — the embedded
    defaults cover the verified-working slice.

    Args:
        flow_id:    flow id or alias.
        start:      Optional start period.
        end:        Optional end period.
        **overrides: Override individual kwargs from the default set.

    Returns:
        list of series dicts (same shape as query()).
    """
    kwargs = get_default_kwargs(flow_id)
    kwargs.update(overrides)
    return query(flow_id, start=start, end=end, timeout=timeout, **kwargs)


# ─── _MockResponse shim (Bucket B) ────────────────────────────────────────


class _MockResponse:
    """Wraps the (parsed_data, status_line) tuple from manual_https_request
    in a `requests.Response`-like interface.

    Per `prism/gs-proxy.md` §6.4 the documented return shape is:
      - `parsed_data`: dict / list (parsed JSON), str (decoded body), or
        None if no body.
      - `status_line`: STRING like "HTTP/1.1 200 OK", NOT an integer.
    """

    def __init__(self, parsed_data: Any, status_line: str):
        self._parsed = parsed_data
        self._status_line = status_line
        self.status_code = self._parse_status_code(status_line)

    @staticmethod
    def _parse_status_code(status_line: str) -> int:
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


# ─── Transport (Bucket B: manual_https_request) ────────────────────────────


def _build_path(*segments: str, query_params: Optional[Dict[str, str]] = None) -> str:
    """Construct an absolute /api/v2/... path with the query string baked in.

    PRISM's manual_https_request does naive `&`-joined query-string
    concatenation without urlencode, so we bake the query string into
    the path here to bypass that.  The staging stub uses requests'
    proper urlencode; both shapes work transparently because we
    pre-encode known parameters ourselves.
    """
    path = "/api/v2/" + "/".join(segments)
    if query_params:
        # BIS query params are always plain ASCII tokens (date strings,
        # format names, mode flags) that don't need percent-encoding.
        # Keep it simple but stable.
        qs = "&".join(f"{k}={v}" for k, v in query_params.items() if v is not None)
        if qs:
            path = f"{path}?{qs}"
    return path


def _request(path: str, *, accept: str = _STRUCT_ACCEPT, timeout: int = 60) -> _MockResponse:
    """Single HTTPS request via the GS-proxy (or staging stub).

    Returns a _MockResponse.  Caller is responsible for status / shape
    checks (use `isinstance(resp.json(), (dict, list))` per
    prism/gs-proxy.md §6.4 rather than parsing status_code, since the
    manual tunnel can return a body with a less-than-perfect status
    line on edge cases).
    """
    headers = {"Accept": accept}
    parsed, status_line = manual_https_request(
        host=BASE_HOST,
        method="GET",
        path=path,
        headers=headers,
        timeout=timeout,
    )
    return _MockResponse(parsed, status_line)


def _api_request_json(path: str, *, accept: str = _STRUCT_ACCEPT,
                      timeout: int = 60) -> Optional[Any]:
    """Fetch and return parsed JSON, or None on any failure shape.

    Uses isinstance(data, (dict, list)) for validity checking per
    `prism/gs-proxy.md` §6.4.
    """
    resp = _request(path, accept=accept, timeout=timeout)
    try:
        data = resp.json()
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return data if isinstance(data, (dict, list)) else None


# ─── Layer 1: Discovery ───────────────────────────────────────────────────


def list_dataflows(*, search: Optional[str] = None,
                   frequency: Optional[str] = None) -> List[Dict[str, Any]]:
    """List all 29 BIS dataflows with id, name, description, dim count.

    Args:
        search:    Case-insensitive substring filter on id / name /
                   description.  None = no filter.
        frequency: Filter by typical frequency.  Accepted: "Q", "M", "A",
                   "H", "D".  Inferred from the FREQ codelist + the
                   convention that all flows currently support Q / M / A
                   in their FREQ codelist; we surface the practical
                   reporting frequency (e.g. CBPOL is monthly, LBS is
                   quarterly).  None = no filter.

    Returns:
        list of dicts: {flow_id, name, description, dsd_id,
                        num_dimensions, dim_ids (list[str]),
                        aliases (list[str])}
    """
    needle = (search or "").lower().strip()
    out = []
    aliases_by_flow: Dict[str, List[str]] = {}
    for alias, fid in DATAFLOW_ALIASES.items():
        aliases_by_flow.setdefault(fid, []).append(alias)
    for fid, flow in _DATAFLOWS.items():
        if needle and needle not in fid.lower() and needle not in flow["name"].lower() \
                and needle not in flow.get("description", "").lower():
            # Also check aliases for the search term
            if not any(needle in a for a in aliases_by_flow.get(fid, [])):
                continue
        if frequency and flow.get("typical_freq") != frequency:
            continue
        dim_ids = [d["id"] for d in flow["dimensions"]]
        out.append({
            "flow_id": fid,
            "name": flow["name"],
            "description": flow.get("description", ""),
            "dsd_id": flow.get("dsd_id", ""),
            "num_dimensions": len(flow["dimensions"]),
            "dim_ids": dim_ids,
            "aliases": sorted(aliases_by_flow.get(fid, [])),
            "typical_freq": flow.get("typical_freq"),
            "series_count": flow.get("series_count", 0),
            "first_period": flow.get("first_period"),
            "last_period": flow.get("last_period"),
        })
    out.sort(key=lambda x: x["flow_id"])
    return out


def get_dataflow(flow_id: str) -> Dict[str, Any]:
    """Full ontology entry for a single dataflow.

    Args:
        flow_id: SDMX flow id (e.g. 'WS_LBS_D_PUB') or alias (e.g. 'lbs').

    Returns:
        {flow_id, name, description, dsd_id, version,
         dimensions: [{id, position, codelist_id, codelist_name,
                       num_codes}],
         key_template (str), num_dimensions (int),
         typical_freq (str | None — "Q", "M", "A", "H"),
         series_count (int — total series in the flow),
         first_period (str — earliest period in BIS publication),
         last_period (str — latest period as of last refresh)}

    Time-coverage fields (`first_period` / `last_period` / `series_count`)
    are baked in from the last `refresh_ontology()` run; they age
    slowly (BIS data start-dates are stable; recent periods drift by
    a quarter or two).  PRISM uses these to know if a flow has data
    for the period it wants BEFORE issuing a query.
    """
    fid = _resolve_flow(flow_id)
    flow = _DATAFLOWS[fid]
    dims = []
    for d in flow["dimensions"]:
        cl_id = d.get("cl")
        cl_entry = _CODELISTS.get(cl_id) if cl_id else None
        dims.append({
            "id": d["id"],
            "position": d["pos"],
            "codelist_id": cl_id,
            "codelist_name": cl_entry["name"] if cl_entry else None,
            "num_codes": len(cl_entry["codes"]) if cl_entry else 0,
        })
    key_template = ".".join(d["id"] for d in flow["dimensions"])
    return {
        "flow_id": fid,
        "name": flow["name"],
        "description": flow.get("description", ""),
        "dsd_id": flow.get("dsd_id", ""),
        "version": flow.get("version", DEFAULT_VERSION),
        "dimensions": dims,
        "key_template": key_template,
        "num_dimensions": len(dims),
        "typical_freq": flow.get("typical_freq"),
        "series_count": flow.get("series_count", 0),
        "first_period": flow.get("first_period"),
        "last_period": flow.get("last_period"),
    }


def get_concept(concept_id: str) -> Dict[str, Any]:
    """Return the SDMX concept's name + long-form description.

    Concepts are the semantic backbone of SDMX — each dimension/attribute
    has a `concept` (e.g. dim "L_REP_CTY" carries the concept "REP_CTY"
    meaning "Reporting country").  138 of BIS's concepts carry a
    long-form description beyond the name (the rest are empty stubs);
    this helper returns the rich entries.

    Args:
        concept_id: Concept id (e.g. "MARKET_ISSUE", "OBS_STATUS",
                    "COLL_PERIOD").

    Returns:
        {concept_id, name (str | None), desc (str | None)} —
        name/desc both None if the concept has no embedded description.
    """
    entry = _CONCEPTS.get(concept_id)
    if entry is None:
        return {"concept_id": concept_id, "name": None, "desc": None}
    if isinstance(entry, str):
        return {"concept_id": concept_id, "name": entry, "desc": None}
    return {
        "concept_id": concept_id,
        "name": entry.get("name"),
        "desc": entry.get("desc"),
    }


def get_dimensions(flow_id: str) -> List[Dict[str, Any]]:
    """Ordered list of dimensions for a dataflow with their codelists.

    Convenience wrapper around get_dataflow(flow_id)["dimensions"].
    """
    return get_dataflow(flow_id)["dimensions"]


def get_codelist(cl_id: str, *,
                 contains: Optional[str] = None,
                 detail: str = "names") -> Dict[str, Any]:
    """Return a codelist with all valid codes.

    Args:
        cl_id:    Codelist id (e.g. 'CL_L_POSITION', 'CL_BIS_IF_REF_AREA').
        contains: Optional case-insensitive substring filter on either
                  code id or human name.  None = return all codes.
        detail:   Output shape:
                    'names' (default) — codes is {code_id: name_str}.
                                        Lossy but minimal.
                    'full'             — codes is {code_id: {name, parent?,
                                        desc?}}.  Preserves hierarchy +
                                        long-form descriptions for the
                                        773 codes that have them.

    Returns:
        {codelist_id, name, codes: <see detail>,
         num_codes, total_codes,
         is_hierarchical (bool — True iff any code has a parent)}

    If cl_id is not in the embedded set, a KeyError is raised with
    the closest matches as suggestions.
    """
    if cl_id not in _CODELISTS:
        suggestions = [c for c in _CODELISTS if cl_id.lower() in c.lower()][:5]
        msg = f"Unknown codelist '{cl_id}'."
        if suggestions:
            msg += f" Did you mean: {', '.join(suggestions)}?"
        msg += (f" {len(_CODELISTS)} codelists are embedded; use "
                "list_dataflows() then get_dataflow(flow_id)['dimensions'] "
                "to see which codelists each dataflow uses.")
        raise KeyError(msg)
    cl = _CODELISTS[cl_id]
    all_codes = cl["codes"]
    needle = contains.lower() if contains else None

    out_codes: Dict[str, Any] = {}
    has_hierarchy = False
    for code_id, entry in all_codes.items():
        name = _code_name(entry)
        if needle and needle not in code_id.lower() and needle not in name.lower():
            continue
        parent = _code_parent(entry)
        desc = _code_desc(entry)
        if parent:
            has_hierarchy = True
        if detail == "full":
            obj: Dict[str, Any] = {"name": name}
            if parent:
                obj["parent"] = parent
            if desc:
                obj["desc"] = desc
            out_codes[code_id] = obj
        else:
            out_codes[code_id] = name

    # Always check is_hierarchical against full set, not filtered
    if not has_hierarchy:
        for entry in all_codes.values():
            if _code_parent(entry):
                has_hierarchy = True
                break

    return {
        "codelist_id": cl_id,
        "name": cl["name"],
        "codes": out_codes,
        "num_codes": len(out_codes),
        "total_codes": len(all_codes),
        "is_hierarchical": has_hierarchy,
    }


def get_code_hierarchy(cl_id: str) -> Dict[str, Any]:
    """Build a parent → children tree for a hierarchical codelist.

    Useful for browsing the conceptual structure of dimensions like
    `CL_DER_INSTR` (derivative instrument tree) where there's a
    natural drill-down from "All instruments (A)" → "FX (B)" → ...

    Args:
        cl_id: Codelist id.

    Returns:
        {
            "codelist_id": str,
            "name":        str,
            "is_hierarchical": bool,
            "roots":       [code_id, ...]  # codes with no parent
            "tree":        {code_id: {"name": str, "children": [code_id, ...]}}
            "depth":       int   # max depth of the tree
        }
    """
    cl = get_codelist(cl_id)  # raises KeyError if missing
    raw = _CODELISTS[cl_id]["codes"]
    children_of: Dict[str, List[str]] = {}
    name_of: Dict[str, str] = {}
    parent_of: Dict[str, Optional[str]] = {}
    for code_id, entry in raw.items():
        parent = _code_parent(entry)
        name_of[code_id] = _code_name(entry)
        parent_of[code_id] = parent
        children_of.setdefault(parent, []).append(code_id)
    roots = sorted(children_of.get(None, []))
    tree: Dict[str, Dict[str, Any]] = {}
    for code_id in raw:
        tree[code_id] = {
            "name": name_of[code_id],
            "parent": parent_of[code_id],
            "children": sorted(children_of.get(code_id, [])),
        }

    def _depth(code_id: str, seen: set) -> int:
        if code_id in seen:
            return 0
        seen.add(code_id)
        kids = children_of.get(code_id, [])
        if not kids:
            return 1
        return 1 + max(_depth(k, seen) for k in kids)

    max_depth = 0
    for r in roots:
        max_depth = max(max_depth, _depth(r, set()))

    return {
        "codelist_id": cl_id,
        "name": _CODELISTS[cl_id]["name"],
        "is_hierarchical": cl["is_hierarchical"],
        "roots": roots,
        "tree": tree,
        "depth": max_depth,
    }


def get_attributes(flow_id: str) -> List[Dict[str, Any]]:
    """Return per-flow attribute metadata (what comes back with each obs).

    BIS dataflows publish per-observation attributes like OBS_STATUS
    (Normal / Estimated / Forecast / Provisional), CONF_STATUS
    (Confidentiality), DECIMALS (number of decimal places),
    UNIT_MULT (unit multiplier), BREAK_REASON, AVAILABILITY, etc.

    PRISM uses these to interpret returned series correctly: an
    observation with `OBS_STATUS = 'F'` is a forecast value, not a
    historical reading.

    Args:
        flow_id: flow id or alias.

    Returns:
        list of {id, codelist_id, codelist_name, status (Mandatory /
        Conditional)} dicts in declaration order.
    """
    fid = _resolve_flow(flow_id)
    flow = _DATAFLOWS[fid]
    out = []
    for a in flow.get("attributes", []) or []:
        cl = a.get("cl")
        cl_name = _CODELISTS[cl]["name"] if cl and cl in _CODELISTS else None
        out.append({
            "id": a["id"],
            "codelist_id": cl,
            "codelist_name": cl_name,
            "assignment_status": a.get("status", ""),
        })
    return out


def interpret_attribute(attr_id: str, code: str, *,
                         flow_id: Optional[str] = None) -> Dict[str, Any]:
    """Decode an attribute code into its human meaning + long-form description.

    PRISM gets back attribute values like ``"attributes": {"OBS_STATUS":
    "A", "DECIMALS": "2"}`` — this helper turns that into something
    interpretable: `interpret_attribute("OBS_STATUS", "A")` →
    `{"name": "Normal value", "desc": "To be used as default..."}`.

    Args:
        attr_id: Attribute id (e.g. "OBS_STATUS", "CONF_STATUS").
        code:    Code value returned in the attribute.
        flow_id: Optional flow_id to scope the codelist lookup.  If
                 None, scans all flows for an attribute with this id.

    Returns:
        {attr_id, code, codelist_id, name, desc} dict.  `name` and
        `desc` are None if the attribute or code is unknown.
    """
    target_cl = None
    if flow_id:
        fid = _resolve_flow(flow_id)
        for a in _DATAFLOWS[fid].get("attributes", []) or []:
            if a["id"] == attr_id:
                target_cl = a.get("cl")
                break
    else:
        # Scan all flows
        for fid, flow in _DATAFLOWS.items():
            for a in flow.get("attributes", []) or []:
                if a["id"] == attr_id:
                    target_cl = a.get("cl")
                    if target_cl:
                        break
            if target_cl:
                break
    out = {"attr_id": attr_id, "code": code, "codelist_id": target_cl,
           "name": None, "desc": None}
    if target_cl and target_cl in _CODELISTS:
        cl = _CODELISTS[target_cl]
        if code in cl["codes"]:
            entry = cl["codes"][code]
            out["name"] = _code_name(entry)
            out["desc"] = _code_desc(entry)
    return out


def search_dataflows(keyword: str) -> List[Dict[str, Any]]:
    """Search dataflows by keyword across id / name / description / aliases.

    Convenience wrapper for list_dataflows(search=keyword).
    """
    return list_dataflows(search=keyword)


def _ascii_fold(text: str) -> str:
    """Strip diacritics + lowercase for fuzzy matching.

    BIS stores country names with native Unicode characters (e.g.
    'Türkiye', not 'Turkey'; 'Côte d'Ivoire'; 'Curaçao').  PRISM users
    search in plain ASCII.  We fold both sides to normalised ASCII.
    """
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Country-name aliases for searches where BIS's official name diverges
# from common usage (PRISM users say "Turkey", BIS publishes "Türkiye").
# Diacritic folding handles most cases; this list covers the rest.
_NAME_ALIASES: Dict[str, List[str]] = {
    # search-token (already ASCII-folded)  →  list of synonyms (also folded)
    "turkey":           ["turkiye"],
    "south korea":      ["korea", "korea, republic of", "republic of korea"],
    "north korea":      ["dprk", "democratic people's republic of korea"],
    "russia":           ["russian federation"],
    "iran":             ["islamic republic of iran"],
    "syria":            ["syrian arab republic"],
    "venezuela":        ["bolivarian republic of venezuela"],
    "tanzania":         ["united republic of tanzania"],
    "moldova":          ["republic of moldova"],
    "uk":               ["united kingdom", "great britain", "britain"],
    "us":               ["united states", "united states of america"],
    "uae":              ["united arab emirates"],
    "hong kong":        ["hong kong sar", "hong kong sar of china"],
    "macau":            ["macao", "macao sar", "macao sar of china"],
    "taiwan":           ["chinese taipei", "taiwan, china"],
    "ivory coast":      ["cote d'ivoire", "cote divoire"],
    "czech republic":   ["czechia"],
    "myanmar":          ["burma"],
}


def find_dataflows_with_dim(dim_id: str) -> List[str]:
    """Return all flow_ids that have a dimension with this id.

    e.g. find_dataflows_with_dim("L_REP_CTY") → ["WS_LBS_D_PUB",
    "WS_CBS_PUB"] — the two LBS/CBS dataflows that use a "reporting
    country" dimension.

    Useful for cross-flow discovery when PRISM is reasoning about
    which dataflows share a concept.
    """
    out = []
    for fid, flow in _DATAFLOWS.items():
        if any(d["id"] == dim_id for d in flow["dimensions"]):
            out.append(fid)
    return sorted(out)


def find_dataflows_with_code(code: str, *,
                             cl_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all dataflows that have a dimension whose codelist contains
    this code.

    e.g. find_dataflows_with_code("TR") returns every dataflow that
    can be sliced by Türkiye (any of CL_BIS_IF_REF_AREA, CL_BIS_GL_REF_AREA,
    CL_AREA, ... — wherever TR is a valid code).

    Args:
        code:  Code id (case-sensitive — BIS codes are case-sensitive,
               e.g. "TR" not "tr").
        cl_id: Restrict to a specific codelist; None = check all
               codelists this code appears in.

    Returns:
        list of {flow_id, dim_id, codelist_id} matches, sorted by
        flow_id.
    """
    # Find all codelists containing this code
    matching_cls = []
    for clid, cl in _CODELISTS.items():
        if cl_id and clid != cl_id:
            continue
        if code in cl["codes"]:
            matching_cls.append(clid)

    if not matching_cls:
        return []

    out = []
    for fid, flow in _DATAFLOWS.items():
        for d in flow["dimensions"]:
            if d.get("cl") in matching_cls:
                out.append({
                    "flow_id": fid,
                    "dim_id": d["id"],
                    "codelist_id": d["cl"],
                })
    return sorted(out, key=lambda x: (x["flow_id"], x["dim_id"]))


def dimension_cross_reference() -> Dict[str, Dict[str, Any]]:
    """Build a cross-reference of every dimension across all dataflows.

    For each unique dim_id, lists which flows use it and what
    codelist they reference.

    Useful for: "where does the SECTOR concept appear?" → returns
    every flow with a sector-shaped dimension.

    Returns:
        {dim_id: {"flows": [flow_id, ...], "codelists": {cl_id: count}}}
    """
    xref: Dict[str, Dict[str, Any]] = {}
    for fid, flow in _DATAFLOWS.items():
        for d in flow["dimensions"]:
            did = d["id"]
            if did not in xref:
                xref[did] = {"flows": [], "codelists": {}}
            xref[did]["flows"].append(fid)
            cl = d.get("cl")
            if cl:
                xref[did]["codelists"][cl] = xref[did]["codelists"].get(cl, 0) + 1
    for did in xref:
        xref[did]["flows"] = sorted(xref[did]["flows"])
    return dict(sorted(xref.items()))


def search_codes(keyword: str, *, cl_id: Optional[str] = None,
                 max_results: int = 50) -> List[Dict[str, Any]]:
    """Fuzzy search for codes across one or all codelists.

    Matches on code id or human name with diacritic-folded substring
    matching plus a small alias map (Turkey↔Türkiye, UK↔United
    Kingdom, etc.).  Address the common ergonomic mismatch where BIS
    publishes native Unicode names while PRISM users type ASCII
    English.

    Args:
        keyword:     Case-insensitive substring to find in code id or name.
        cl_id:       Restrict search to one codelist; None = all 93.
        max_results: Cap on returned matches (default 50).

    Returns:
        list of {codelist_id, code_id, name} tuples ordered by
        (codelist_id, code_id).  Useful for "what's the code for
        Turkey?" / "show me all 'derivatives' codes".
    """
    needle_raw = keyword.strip()
    if not needle_raw:
        return []
    needle = _ascii_fold(needle_raw)
    # Expand search terms via aliases
    needles = {needle}
    if needle in _NAME_ALIASES:
        needles.update(_NAME_ALIASES[needle])
    # Reverse-lookup: if user typed a synonym, also include the canonical key
    for canonical, syns in _NAME_ALIASES.items():
        if needle in syns:
            needles.add(canonical)

    targets = [cl_id] if cl_id else list(_CODELISTS.keys())
    matches = []
    for clid in targets:
        cl = _CODELISTS.get(clid)
        if not cl:
            continue
        for code_id, entry in cl["codes"].items():
            name = _code_name(entry)
            code_folded = _ascii_fold(code_id)
            name_folded = _ascii_fold(name)
            if any(n in code_folded or n in name_folded for n in needles):
                matches.append({
                    "codelist_id": clid,
                    "code_id": code_id,
                    "name": name,
                })
                if len(matches) >= max_results:
                    return matches
    return matches


def describe(flow_id: str) -> str:
    """Render a dataflow's full schema as a markdown-ish summary string.

    Useful when PRISM wants a single readable surface to reason over
    before constructing a query.

    Args:
        flow_id: flow id or alias.

    Returns:
        Multi-line string with dataflow header, dimension table,
        and a key template line.  No print side-effects.
    """
    info = get_dataflow(flow_id)
    lines = [
        f"# {info['flow_id']} — {info['name']}",
        f"",
        f"DSD: {info['dsd_id']} v{info['version']}    "
        f"Dimensions: {info['num_dimensions']}    "
        f"Frequency: {info.get('typical_freq') or '—'}",
    ]
    if info.get("series_count"):
        lines.append(
            f"Series: {info['series_count']:,}    "
            f"Coverage: {info.get('first_period') or '—'} → "
            f"{info.get('last_period') or '—'}"
        )
    if info.get("description"):
        lines.append("")
        lines.append(info["description"])
    lines.append("")
    lines.append(f"Key template: `{info['key_template']}`")
    lines.append("")
    lines.append("| Pos | Dim | Codelist | Codes |")
    lines.append("|-----|-----|----------|-------|")
    for d in info["dimensions"]:
        cl = d.get("codelist_id") or "—"
        n = d.get("num_codes", 0)
        lines.append(f"| {d['position']} | {d['id']} | {cl} | {n} |")
    return "\n".join(lines)


# ─── Layer 2: Availability ────────────────────────────────────────────────


def check_availability(flow_id: str, *,
                       key: Optional[str] = None,
                       timeout: int = 60,
                       **dim_values: Any) -> Dict[str, Any]:
    """Ask BIS what series exist for a partial key BEFORE querying data.

    The most powerful primitive for avoiding empty-result surprises.
    Hits /availability/dataflow/BIS/{FLOW}/{VER}/{KEY} which returns
    every codelist value that has at least one matching series.

    Args:
        flow_id:    flow id or alias.
        key:        SDMX dimension key string.  If passed, dim_values
                    are ignored.  Pass an empty/wildcard key (e.g.
                    "all" or just dots) to scope by zero pre-filters.
        timeout:    HTTP timeout in seconds.
        **dim_values:  Named partial key.  E.g.
                       check_availability("lbs", FREQ="Q", L_REP_CTY="US")
                       returns the count + dim breakdown of series
                       matching just those constraints.

    Returns:
        {
            "flow_id":       canonical flow id,
            "key":           the SDMX key actually sent,
            "series_count":  int,           # 0 means nothing exists
            "available_codes": {            # what BIS reports as available
                <DIM_ID>: [list of code ids that have data],
                ...
            },
            "ok":            bool (True iff series_count > 0),
        }
    """
    fid = _resolve_flow(flow_id)
    if key is None:
        key = build_key(fid, **dim_values)
    avail_path = _build_path(
        "availability", "dataflow", "BIS", fid, _flow_version(fid), key,
        query_params={"mode": "available", "references": "none",
                      "format": "sdmx-json"},
    )
    raw = _api_request_json(avail_path, timeout=timeout)
    if not raw:
        return {"flow_id": fid, "key": key, "series_count": 0,
                "available_codes": {}, "ok": False}
    try:
        constraints = raw["data"].get("contentConstraints") or []
        constraint = constraints[0] if constraints else {}
        annots = {a["id"]: a.get("title", "")
                  for a in constraint.get("annotations", [])}
        try:
            series_count = int(annots.get("series_count", 0))
        except (TypeError, ValueError):
            series_count = 0
        kv_map: Dict[str, List[str]] = {}
        for kv in (constraint.get("cubeRegions") or [{}])[0].get("keyValues", []):
            kv_map[kv["id"]] = list(kv.get("values", []))
        return {
            "flow_id": fid,
            "key": key,
            "series_count": series_count,
            "available_codes": kv_map,
            "ok": series_count > 0,
        }
    except (KeyError, IndexError, TypeError):
        return {"flow_id": fid, "key": key, "series_count": 0,
                "available_codes": {}, "ok": False}


# ─── Layer 3: Query construction ───────────────────────────────────────────


def build_key(flow_id: str, **dim_values: Any) -> str:
    """Build a valid SDMX dimension key from named dimension values.

    The wrapper does the heavy lifting:
      - Looks up the dataflow's dimension order from the embedded
        ontology.  PRISM does NOT have to remember positions.
      - Validates each provided dim_value against its codelist
        (raises ValueError on unknown codes; lists the closest
        valid codes in the message).
      - Wildcards any dimension you don't pass (empty string in the
        key, which BIS treats as "all values for this dim").
      - Accepts list / tuple values and joins with "+" for SDMX OR.
      - Accepts string values that already contain "+" (passes
        through verbatim after validation of each component).

    Args:
        flow_id:        flow id or alias.
        **dim_values:   keyword arguments matching dimension ids.
                        e.g. build_key("lbs", FREQ="Q", L_POSITION="C",
                                       L_REP_CTY="US", L_INSTR="A")

    Returns:
        SDMX key string in the form "v1.v2.v3...vN" with empty
        positions for unspecified dimensions.

    Raises:
        ValueError: if an unknown dimension id or unknown code is
                    passed.  The error message includes the dataflow's
                    valid dim ids and (for code errors) up to 8 valid
                    codes for that dimension.
    """
    fid = _resolve_flow(flow_id)
    dims = _DATAFLOWS[fid]["dimensions"]
    dim_by_id = {d["id"]: d for d in dims}
    valid_ids = [d["id"] for d in dims]

    unknown = [k for k in dim_values if k not in dim_by_id]
    if unknown:
        raise ValueError(
            f"Unknown dimension(s) for {fid}: {unknown}.  "
            f"Valid dimensions (in key order): {valid_ids}."
        )

    # Build per-position values, validate codes
    parts: List[str] = []
    for d in sorted(dims, key=lambda x: x["pos"]):
        dim_id = d["id"]
        cl_id = d.get("cl")
        val = dim_values.get(dim_id)
        if val is None or val == "":
            parts.append("")
            continue
        # Coerce list / tuple / set to "+"-joined string
        if isinstance(val, (list, tuple, set)):
            tokens = [str(v).strip() for v in val if str(v).strip()]
        else:
            tokens = [t.strip() for t in str(val).split("+") if t.strip()]
        # Validate against codelist
        if cl_id and cl_id in _CODELISTS:
            valid_codes = _CODELISTS[cl_id]["codes"]
            invalid = [t for t in tokens if t not in valid_codes]
            if invalid:
                # Suggest close matches
                hints = []
                for bad in invalid:
                    bad_lc = bad.lower()
                    near = [c for c in valid_codes
                            if bad_lc in c.lower()
                            or bad_lc in _code_name(valid_codes[c]).lower()][:5]
                    hints.append(f"'{bad}' (closest: {near or 'none'})")
                sample = list(valid_codes.keys())[:8]
                raise ValueError(
                    f"Invalid code(s) for dimension {dim_id} ({cl_id}) "
                    f"on {fid}: {', '.join(hints)}.  "
                    f"Valid codes start with: {sample} "
                    f"(use get_codelist('{cl_id}') for the full list, "
                    f"or search_codes('<keyword>', cl_id='{cl_id}'))."
                )
        parts.append("+".join(tokens))
    return ".".join(parts)


def query(flow_id: str, *,
          key: Optional[str] = None,
          start: Optional[str] = None,
          end: Optional[str] = None,
          detail: str = "full",
          timeout: int = 120,
          **dim_values: Any) -> List[Dict[str, Any]]:
    """Fetch BIS time series via the SDMX data API.

    Args:
        flow_id:     flow id or alias (e.g. 'WS_CBPOL' or 'policy-rates').
        key:         SDMX dimension key string.  If None, **dim_values
                     are used to build_key() the request.
        start:       Start period (e.g. '2020', '2020-Q1', '2020-01').
        end:         End period (same shapes).
        detail:      'full' (default), 'dataonly', 'serieskeysonly',
                     or 'nodata'.
        timeout:     HTTP timeout in seconds (BIS data calls can be slow
                     on wide queries).
        **dim_values:  Used iff key is None.  See build_key().

    Returns:
        list of series dicts (empty list on 404 / no data):
            {
                "key":          "Q.S.C.A.TO1.A.5J.A.US.A..N",
                "dimensions":   {DIM_ID: {"id": str, "name": str}, ...},
                "attributes":   {ATTR_ID: str, ...},
                "observations": {"2024-Q1": 1234.56, "2024-Q2": ..., ...},
            }
    """
    fid = _resolve_flow(flow_id)
    if key is None:
        key = build_key(fid, **dim_values)
    elif key in ("", None):
        key = "all"

    qp = {"format": "sdmx-json", "detail": detail}
    if start:
        qp["startPeriod"] = start
    if end:
        qp["endPeriod"] = end

    data_path = _build_path("data", "dataflow", "BIS", fid, _flow_version(fid), key,
                            query_params=qp)
    resp = _request(data_path, accept=_DATA_ACCEPT, timeout=timeout)
    # 404 = no series matching key.  Fail loud upstream — return [].
    if resp.status_code == 404:
        return []
    raw = resp.json() if resp.ok else None
    if not isinstance(raw, dict):
        return []
    return _parse_sdmx_data(raw)


def _parse_sdmx_data(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse SDMX-JSON data response into a list of series dicts."""
    datasets = raw.get("data", {}).get("dataSets", [])
    if not datasets:
        return []

    structure = raw.get("data", {}).get("structure", {})
    dim_defs = structure.get("dimensions", {}).get("series", []) or []
    obs_dim = structure.get("dimensions", {}).get("observation", []) or []
    attr_defs = structure.get("attributes", {}).get("series", []) or []

    time_values: List[str] = []
    if obs_dim:
        time_values = [v.get("id", v.get("name", str(i)))
                       for i, v in enumerate(obs_dim[0].get("values", []))]

    series_list: List[Dict[str, Any]] = []
    ds = datasets[0]
    for series_key_str, series_obj in ds.get("series", {}).items():
        try:
            key_indices = [int(k) for k in series_key_str.split(":")]
        except ValueError:
            continue
        dimensions: Dict[str, Dict[str, str]] = {}
        key_parts: List[str] = []
        for i, dim_def in enumerate(dim_defs):
            idx = key_indices[i] if i < len(key_indices) else 0
            values = dim_def.get("values", [])
            if 0 <= idx < len(values):
                val = values[idx]
                dimensions[dim_def.get("id", f"dim_{i}")] = {
                    "id": val.get("id", ""),
                    "name": val.get("name", ""),
                }
                key_parts.append(val.get("id", ""))
            else:
                key_parts.append("?")

        attributes: Dict[str, str] = {}
        attr_indices = series_obj.get("attributes", []) or []
        for i, attr_def in enumerate(attr_defs):
            attr_vals = attr_def.get("values", []) or []
            if i < len(attr_indices) and attr_indices[i] is not None:
                aidx = attr_indices[i]
                if 0 <= aidx < len(attr_vals):
                    attributes[attr_def.get("id", f"attr_{i}")] = attr_vals[aidx].get("name", "")

        observations: Dict[str, Optional[float]] = {}
        for obs_key, obs_val in (series_obj.get("observations") or {}).items():
            try:
                obs_idx = int(obs_key)
            except ValueError:
                continue
            period = time_values[obs_idx] if 0 <= obs_idx < len(time_values) else obs_key
            value = obs_val[0] if obs_val else None
            try:
                observations[period] = float(value) if value is not None else None
            except (TypeError, ValueError):
                observations[period] = value

        series_list.append({
            "key": ".".join(key_parts),
            "dimensions": dimensions,
            "attributes": attributes,
            "observations": observations,
        })
    return series_list


# ─── Layer 4: Composite recipes (multi-query helpers) ─────────────────────


def _latest_value(series: List[Dict[str, Any]]) -> Tuple[Optional[float], Optional[str]]:
    """Extract (latest_value, latest_period) from a series list (first match)."""
    if not series:
        return None, None
    s = series[0] if isinstance(series, list) else series
    obs = s.get("observations") if isinstance(s, dict) else None
    if not obs:
        return None, None
    latest = max(obs.keys())
    return obs[latest], latest


def recipe_contagion(target: str, *,
                     start: str = "2010", end: Optional[str] = None) -> Dict[str, Any]:
    """Three-view exposure analysis for a single target country.

    Combines:
      - LBS: who lends to <target> from where (locational basis)
      - CBS immediate: who's exposed by HQ nationality, before risk transfers
      - CBS guarantor: ultimate risk after guarantees / risk transfers

    Args:
        target: Counterparty country ISO code (TR, RU, AR, CN, ES, ...)
                or BIS aggregate (4T = EM, etc.)
        start:  Start period
        end:    End period (None = latest)

    Returns:
        {
            "target": <target>,
            "generated_at": <iso8601>,
            "series": {
                "lbs_aggregate":         [...],   # all reporters → target
                "lbs_per_reporter":      {...},   # per-reporter breakdown
                "cbs_immediate":         [...],   # all reporters, basis F
                "cbs_guarantor":         [...],   # all reporters, basis U
            },
            "summary": {
                "lbs_aggregate":     {"value": float, "period": str},
                "cbs_immediate":     {"value": float, "period": str},
                "cbs_guarantor":     {"value": float, "period": str},
                "guarantor_minus_immediate": float,  # > 0 = risk transfers in
            },
        }
    """
    out: Dict[str, Any] = {
        "target": target,
        "start_period": start,
        "series": {},
        "summary": {},
    }

    # LBS: cross-border claims on target, all reporters aggregate
    lbs_agg = query(
        "WS_LBS_D_PUB",
        key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                      L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                      L_PARENT_CTY="5J", L_REP_BANK_TYPE="A",
                      L_REP_CTY="5A", L_CP_SECTOR="A", L_CP_COUNTRY=target,
                      L_POS_TYPE="N"),
        start=start, end=end,
    )
    out["series"]["lbs_aggregate"] = lbs_agg
    v, p = _latest_value(lbs_agg)
    if v is not None:
        out["summary"]["lbs_aggregate"] = {"value": v, "period": p}

    # CBS: international claims on target, immediate counterparty (F).
    # On F basis the canonical broad measure is L_POSITION=I
    # (International claims = cross-border + local in foreign currency).
    cbs_imm = query(
        "WS_CBS_PUB",
        key=build_key("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY="5A", CBS_BANK_TYPE="4R", CBS_BASIS="F",
                      L_POSITION="I", L_INSTR="A", REM_MATURITY="A",
                      CURR_TYPE_BOOK="TO1", L_CP_SECTOR="A",
                      L_CP_COUNTRY=target),
        start=start, end=end,
    )
    out["series"]["cbs_immediate"] = cbs_imm
    v_imm, p_imm = _latest_value(cbs_imm)
    if v_imm is not None:
        out["summary"]["cbs_immediate"] = {"value": v_imm, "period": p_imm}

    # CBS: total claims on target, guarantor basis (U).  On U basis BIS
    # does NOT publish L_POSITION=I — the canonical broad measure is
    # L_POSITION=C (Total claims) which is the ultimate-risk equivalent.
    cbs_gtor = query(
        "WS_CBS_PUB",
        key=build_key("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY="5A", CBS_BANK_TYPE="4R", CBS_BASIS="U",
                      L_POSITION="C", L_INSTR="A", REM_MATURITY="A",
                      CURR_TYPE_BOOK="TO1", L_CP_SECTOR="A",
                      L_CP_COUNTRY=target),
        start=start, end=end,
    )
    out["series"]["cbs_guarantor"] = cbs_gtor
    v_gtor, p_gtor = _latest_value(cbs_gtor)
    if v_gtor is not None:
        out["summary"]["cbs_guarantor"] = {"value": v_gtor, "period": p_gtor}

    if v_imm is not None and v_gtor is not None:
        try:
            out["summary"]["guarantor_minus_immediate"] = float(v_gtor) - float(v_imm)
        except (TypeError, ValueError):
            pass
    return out


def recipe_eurodollar(*, start: str = "2010", end: Optional[str] = None,
                      reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Eurodollar system overview — global USD claims/liabs/growth +
    per-center FCY positions.

    Args:
        start:     Start period.
        end:       End period.
        reporters: List of LBS reporter ISO codes.  Default = major
                   offshore + onshore centers (GB, JP, FR, DE, CH, HK,
                   SG, CA, AU, NL, IE, LU, US, KY).
    """
    if reporters is None:
        reporters = ["GB", "JP", "FR", "DE", "CH", "HK", "SG", "CA",
                     "AU", "NL", "IE", "LU", "US", "KY"]

    out: Dict[str, Any] = {"start_period": start, "series": {},
                           "summary": {"per_center": {}}}

    # Global aggregate
    for measure_code, key_label in (("S", "global_usd_claims"),):
        for pos in ("C", "L"):
            label = f"global_usd_{'claims' if pos == 'C' else 'liabs'}"
            s = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE=measure_code,
                              L_POSITION=pos, L_INSTR="A", L_DENOM="USD",
                              L_CURR_TYPE="A", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
            out["series"][label] = s
            v, p = _latest_value(s)
            if v is not None:
                out["summary"][label] = {"value": v, "period": p}

    # YoY growth (L_MEASURE=G)
    growth = query(
        "WS_LBS_D_PUB",
        key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="G", L_POSITION="C",
                      L_INSTR="A", L_DENOM="USD", L_CURR_TYPE="A",
                      L_PARENT_CTY="5J", L_REP_BANK_TYPE="A",
                      L_REP_CTY="5A", L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                      L_POS_TYPE="N"),
        start=start, end=end,
    )
    out["series"]["global_usd_growth_yoy"] = growth
    v, p = _latest_value(growth)
    if v is not None:
        out["summary"]["global_usd_growth_yoy"] = {"value": v, "period": p}

    # Per-center FCY claims & liabs
    for rep in reporters:
        try:
            c = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                              L_CURR_TYPE="F", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
            l = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="L", L_INSTR="A", L_DENOM="TO1",
                              L_CURR_TYPE="F", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
        except ValueError:
            # Reporter ISO not in the LBS codelist — skip rather than blow up.
            continue
        out["series"][f"{rep}_fcy_claims"] = c
        out["series"][f"{rep}_fcy_liabs"] = l
        cv, _ = _latest_value(c)
        lv, _ = _latest_value(l)
        if cv is not None or lv is not None:
            cv = cv or 0
            lv = lv or 0
            out["summary"]["per_center"][rep] = {
                "fcy_claims": cv,
                "fcy_liabs": lv,
                "fcy_net": cv - lv,
                "role": "FCY_SUPPLIER" if (cv - lv) > 0 else "FCY_BORROWER",
            }
    return out


# Reporter → domestic currency map for LBS (48 reporting jurisdictions).
# BIS publishes individual-currency LBS breakdowns only for FOREIGN
# currencies (the reporter's domestic currency is rolled up into TO1
# but never broken out individually).  L_CURR_TYPE has to match:
#   D when L_DENOM == reporter's domestic ccy  (mostly empty in practice)
#   F when L_DENOM != reporter's domestic ccy  (the foreign-ccy slice)
#   A only when L_DENOM in (TO1, TO3, UN9) — the aggregates
# This map encodes the domestic-currency rule so PRISM never has to
# remember it.
_REPORTER_DOMESTIC_CCY: Dict[str, str] = {
    "AT": "EUR", "AU": "AUD", "BE": "EUR", "BH": "BHD", "BM": "USD",
    "BR": "BRL", "BS": "BSD", "CA": "CAD", "CH": "CHF", "CL": "CLP",
    "CN": "CNY", "CW": "ANG", "CY": "EUR", "DE": "EUR", "DK": "DKK",
    "ES": "EUR", "FI": "EUR", "FR": "EUR", "GB": "GBP", "GG": "GBP",
    "GR": "EUR", "HK": "HKD", "ID": "IDR", "IE": "EUR", "IM": "GBP",
    "IN": "INR", "IT": "EUR", "JE": "GBP", "JP": "JPY", "KR": "KRW",
    "KY": "USD", "LU": "EUR", "MO": "MOP", "MX": "MXN", "MY": "MYR",
    "NL": "EUR", "NO": "NOK", "PA": "USD", "PH": "PHP", "PT": "EUR",
    "RU": "RUB", "SA": "SAR", "SE": "SEK", "SG": "SGD", "TR": "TRY",
    "TW": "TWD", "US": "USD", "ZA": "ZAR",
    # Aggregates: treat as A for L_CURR_TYPE (no single domestic ccy)
    "5A": None, "5C": "EUR", "5J": None,
}


def _curr_type_for(reporter: str, ccy: str) -> str:
    """Pick L_CURR_TYPE based on reporter + L_DENOM.

    Per the BIS LBS publishing convention (verified against
    /availability/ probes 2026-05-09):
      - L_DENOM in ("TO1", "TO3", "UN9")  →  L_CURR_TYPE = "A"
      - L_DENOM == reporter's domestic ccy  →  L_CURR_TYPE = "D"
      - L_DENOM != reporter's domestic ccy  →  L_CURR_TYPE = "F"
    """
    if ccy in ("TO1", "TO3", "UN9"):
        return "A"
    domestic = _REPORTER_DOMESTIC_CCY.get(reporter)
    if domestic is None:
        # Unknown reporter or aggregate without a single domestic ccy
        # → A (will work for TO1/TO3/UN9; explicit currencies may 404)
        return "A"
    return "D" if ccy == domestic else "F"


def recipe_currency_breakdown(reporter: str, *,
                              start: str = "2010",
                              end: Optional[str] = None,
                              currencies: Optional[List[str]] = None) -> Dict[str, Any]:
    """Cross-border claims & liabilities broken down by currency for one reporter.

    Wrapper absorbs the BIS L_CURR_TYPE quirk: per-currency breakdowns
    require D / F (depending on whether the currency is domestic or
    foreign for the reporter) while aggregate dimensions (TO1 / TO3 /
    UN9) require A.  PRISM doesn't have to remember this — pass a
    reporter and a currency list, get the right slice.

    Args:
        reporter:   LBS reporter ISO (US, GB, JP, DE, CH, HK, SG, ...).
        start:      Start period.
        end:        End period.
        currencies: List of L_DENOM codes.  Default = TO1 + the 5
                    major currencies + TO3 (foreign-only) + UN9
                    (unallocated).
    """
    if currencies is None:
        currencies = ["TO1", "USD", "EUR", "GBP", "JPY", "CHF", "TO3", "UN9"]

    out: Dict[str, Any] = {"reporter": reporter, "start_period": start,
                           "series": {}, "summary": {}}
    domestic = _REPORTER_DOMESTIC_CCY.get(reporter)
    if domestic is not None:
        out["domestic_currency"] = domestic

    for ccy in currencies:
        ct = _curr_type_for(reporter, ccy)
        for pos in ("C", "L"):
            label = f"{ccy.lower()}_{'claims' if pos == 'C' else 'liabs'}"
            try:
                s = query(
                    "WS_LBS_D_PUB",
                    key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                                  L_POSITION=pos, L_INSTR="A", L_DENOM=ccy,
                                  L_CURR_TYPE=ct, L_PARENT_CTY="5J",
                                  L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
                                  L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                                  L_POS_TYPE="N"),
                    start=start, end=end,
                )
            except ValueError:
                continue
            out["series"][label] = s
            v, p = _latest_value(s)
            if v is not None:
                out["summary"][label] = {
                    "value": v, "period": p,
                    "l_curr_type": ct,
                }
    # Compute % share of total
    tot, _ = _latest_value(out["series"].get("to1_claims", []))
    if tot:
        for k, v in list(out["summary"].items()):
            if k.endswith("_claims") and k != "to1_claims":
                try:
                    v["pct_of_total"] = float(v["value"]) / float(tot) * 100.0
                except (TypeError, ValueError, ZeroDivisionError):
                    pass
    return out


def recipe_shadow_banking_full(*, start: str = "2015",
                               end: Optional[str] = None) -> Dict[str, Any]:
    """Composite shadow-banking analysis — five sub-modules combined.

    Modules (each is a separate dict key):
      1. eurodollar          — recipe_eurodollar()
      2. nbfi_global         — global cross-border claims by counterparty
                                sector (banks vs NBFI vs corps vs gov)
      3. interbank_usd       — global USD interbank loans+deposits
                                (instrument=G, sector=B), claims and liabs
      4. offshore_centers    — total cross-border claims+liabs+net for the
                                core offshore set (GB, HK, SG, KY, LU, IE)
      5. fcy_mismatch        — domestic vs foreign currency claim split
                                for the major reporters

    Returns:
        {start_period, series (raw), summary (latest values per module)}
    """
    out: Dict[str, Any] = {
        "start_period": start,
        "modules": {},
        "summary": {},
    }

    # Module 1: eurodollar
    out["modules"]["eurodollar"] = recipe_eurodollar(start=start, end=end)
    out["summary"]["eurodollar_global_usd_claims"] = (
        out["modules"]["eurodollar"]["summary"].get("global_usd_claims"))

    # Module 2: NBFI / cross-sector global
    sector_codes = {"A": "All", "B": "Banks", "I": "Related offices",
                    "F": "NBFI", "C": "Non-financial corps",
                    "G": "Government", "H": "Households", "N": "Non-banks"}
    nbfi_summary: Dict[str, Any] = {}
    nbfi_series: Dict[str, Any] = {}
    for code, label in sector_codes.items():
        s = query(
            "WS_LBS_D_PUB",
            key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                          L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                          L_CURR_TYPE="A", L_PARENT_CTY="5J",
                          L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                          L_CP_SECTOR=code, L_CP_COUNTRY="5J",
                          L_POS_TYPE="N"),
            start=start, end=end,
        )
        nbfi_series[f"sector_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            nbfi_summary[label] = {"value": v, "period": p}
    out["modules"]["nbfi_global"] = {"series": nbfi_series,
                                     "summary": nbfi_summary}

    # Module 3: interbank USD
    interbank_c = query(
        "WS_LBS_D_PUB",
        key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="C", L_INSTR="G", L_DENOM="USD",
                      L_CURR_TYPE="A", L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                      L_CP_SECTOR="B", L_CP_COUNTRY="5J", L_POS_TYPE="N"),
        start=start, end=end,
    )
    interbank_l = query(
        "WS_LBS_D_PUB",
        key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="L", L_INSTR="G", L_DENOM="USD",
                      L_CURR_TYPE="A", L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                      L_CP_SECTOR="B", L_CP_COUNTRY="5J", L_POS_TYPE="N"),
        start=start, end=end,
    )
    out["modules"]["interbank_usd"] = {
        "series": {"claims": interbank_c, "liabs": interbank_l},
        "summary": {
            "claims": dict(zip(("value", "period"), _latest_value(interbank_c))),
            "liabs": dict(zip(("value", "period"), _latest_value(interbank_l))),
        },
    }

    # Module 4: offshore centers
    centers = ["GB", "HK", "SG", "KY", "LU", "IE", "JE"]
    offshore_summary: Dict[str, Any] = {}
    offshore_series: Dict[str, Any] = {}
    for ctr in centers:
        try:
            c = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                              L_CURR_TYPE="A", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=ctr,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
            l = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="L", L_INSTR="A", L_DENOM="TO1",
                              L_CURR_TYPE="A", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=ctr,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
        except ValueError:
            continue
        offshore_series[f"{ctr}_claims"] = c
        offshore_series[f"{ctr}_liabs"] = l
        cv, _ = _latest_value(c)
        lv, _ = _latest_value(l)
        if cv is not None or lv is not None:
            cv = cv or 0
            lv = lv or 0
            offshore_summary[ctr] = {
                "claims": cv, "liabs": lv,
                "net": cv - lv,
                "role": "CREDITOR" if (cv - lv) > 0 else "DEBTOR",
            }
    out["modules"]["offshore_centers"] = {"series": offshore_series,
                                          "summary": offshore_summary}

    # Module 5: FCY mismatch
    major_reporters = ["US", "GB", "JP", "DE", "FR", "CH", "AU", "CA",
                       "HK", "SG", "KR", "BR", "MX", "TR"]
    fcy_summary: Dict[str, Any] = {}
    fcy_series: Dict[str, Any] = {}
    for rep in major_reporters:
        try:
            all_ccy = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                              L_CURR_TYPE="A", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
            fcy = query(
                "WS_LBS_D_PUB",
                key=build_key("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                              L_POSITION="C", L_INSTR="A", L_DENOM="TO3",
                              L_CURR_TYPE="F", L_PARENT_CTY="5J",
                              L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                              L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                              L_POS_TYPE="N"),
                start=start, end=end,
            )
        except ValueError:
            continue
        fcy_series[f"{rep}_total"] = all_ccy
        fcy_series[f"{rep}_fcy"] = fcy
        tot, _ = _latest_value(all_ccy)
        fcyv, _ = _latest_value(fcy)
        if tot and fcyv is not None:
            try:
                fcy_summary[rep] = {
                    "total_claims": tot,
                    "fcy_claims": fcyv,
                    "fcy_share_pct": (float(fcyv) / float(tot) * 100.0) if tot else None,
                }
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    out["modules"]["fcy_mismatch"] = {"series": fcy_series,
                                      "summary": fcy_summary}

    return out


def recipe_credit_gap_warnings(*, threshold: float = 10.0,
                                start: str = "2020",
                                end: Optional[str] = None,
                                countries: Optional[List[str]] = None) -> Dict[str, Any]:
    """Find countries currently above the BIS credit-to-GDP gap warning threshold.

    BIS designates a credit-to-GDP gap > +10pp as a warning signal of
    overheating; > +20pp as extreme.  Negative gaps mean deleveraging
    (typically post-crisis).

    Args:
        threshold: Gap threshold in pp (default 10 = BIS standard
                   warning).  Pass negative for deleveraging filter.
        start:     Start period.
        end:       End period.
        countries: Optional list of country ISOs to restrict to;
                   None = a sensible global set (G20 + EU + offshore).

    Returns:
        {threshold, generated_at, summary: [{country, gap, period,
         flag}], series_by_country: {iso: [series]}}
    """
    if countries is None:
        countries = [
            "US", "GB", "JP", "DE", "FR", "IT", "ES", "NL", "CH", "CA",
            "AU", "NZ", "SE", "NO", "FI", "DK", "BE", "AT", "PT", "IE",
            "CN", "IN", "BR", "MX", "RU", "TR", "ZA", "KR", "ID",
            "TH", "MY", "PH", "AR", "CL", "PE", "CO", "EG", "PK",
            "PL", "CZ", "HU", "RO",
        ]
    out: Dict[str, Any] = {
        "threshold": threshold,
        "start_period": start,
        "summary": [],
        "series_by_country": {},
    }
    for ctry in countries:
        try:
            series = query("WS_CREDIT_GAP", FREQ="Q", BORROWERS_CTY=ctry,
                           TC_BORROWERS="P", TC_LENDERS="A", CG_DTYPE="C",
                           start=start, end=end)
        except ValueError:
            continue
        out["series_by_country"][ctry] = series
        if not series:
            continue
        v, p = _latest_value(series)
        if v is None:
            continue
        flag = "WARN" if v > threshold else (
            "EXTREME_DELEVERAGE" if v < -threshold else "NORMAL"
        )
        if v > 20:
            flag = "EXTREME_OVERHEATING"
        out["summary"].append({
            "country": ctry,
            "gap_pp": v,
            "period": p,
            "flag": flag,
        })
    out["summary"].sort(key=lambda x: x["gap_pp"], reverse=True)
    return out


def recipe_policy_rate_cycle(*, countries: Optional[List[str]] = None,
                             start: str = "2020",
                             end: Optional[str] = None) -> Dict[str, Any]:
    """Snapshot of where each central bank is in its rate cycle.

    For each country: latest rate, peak rate over the window, trough
    rate over the window, distance from peak / trough in pp,
    direction-of-travel over last 6 months.

    Args:
        countries: List of REF_AREA codes; None = major DM + EM.
        start:     Start period.
        end:       End period.

    Returns:
        {generated_at, summary: [{country, latest, peak, trough,
         from_peak_pp, from_trough_pp, last_6mo_change_pp, direction}]}
    """
    if countries is None:
        countries = [
            "US", "GB", "JP", "XM", "CH", "CA", "AU", "SE", "NO", "NZ",
            "BR", "IN", "MX", "ZA", "TR", "KR", "ID", "PL", "HU",
        ]
    out: Dict[str, Any] = {"start_period": start, "summary": []}
    for ctry in countries:
        try:
            series = query("WS_CBPOL", FREQ="M", REF_AREA=ctry,
                           start=start, end=end)
        except ValueError:
            continue
        if not series:
            continue
        obs = series[0].get("observations", {})
        if not obs:
            continue
        sorted_periods = sorted(obs.keys())
        nums: List[Tuple[str, float]] = []
        for p in sorted_periods:
            v = obs[p]
            if v is None:
                continue
            try:
                nums.append((p, float(v)))
            except (TypeError, ValueError):
                continue
        if not nums:
            continue
        latest_p, latest_v = nums[-1]
        peak_p, peak_v = max(nums, key=lambda x: x[1])
        trough_p, trough_v = min(nums, key=lambda x: x[1])
        # 6-month change
        if len(nums) >= 7:
            six_back = nums[-7][1]
            change_6mo = latest_v - six_back
        else:
            change_6mo = None
        direction = (
            "CUTTING" if change_6mo is not None and change_6mo < -0.05
            else "HIKING" if change_6mo is not None and change_6mo > 0.05
            else "ON_HOLD"
        )
        out["summary"].append({
            "country": ctry,
            "latest_rate": latest_v,
            "latest_period": latest_p,
            "peak_rate": peak_v,
            "peak_period": peak_p,
            "trough_rate": trough_v,
            "trough_period": trough_p,
            "from_peak_pp": latest_v - peak_v,
            "from_trough_pp": latest_v - trough_v,
            "last_6mo_change_pp": change_6mo,
            "direction": direction,
        })
    return out


def recipe_lbs_bilateral(reporter: str, counterparty: str, *,
                         currency: str = "TO1", sector: str = "A",
                         instrument: str = "A", position: str = "C",
                         pos_type: str = "N",
                         start: str = "2010",
                         end: Optional[str] = None) -> Dict[str, Any]:
    """Bilateral LBS query: one reporter vs one counterparty country.

    All LBS dimensions exposed as kwargs; auto-derives L_CURR_TYPE
    from the (reporter, currency) pair using `_REPORTER_DOMESTIC_CCY`.
    Returns the raw series + a 1-line summary of the latest value.

    Args:
        reporter:     Reporting country ISO (US, GB, JP, ...).
        counterparty: Counterparty country ISO (CN, TR, 5C, ...).
        currency:     L_DENOM (TO1, USD, EUR, GBP, JPY, CHF, TO3, UN9).
        sector:       L_CP_SECTOR (A, B, N, F, C, G, H, I).
        instrument:   L_INSTR (A, G, D, B, V).
        position:     L_POSITION (C=Claims, L=Liabs, N=Net).
        pos_type:     L_POS_TYPE (N=Cross-border, R=Local, I=XB+Local FCY).

    Returns:
        {reporter, counterparty, currency, sector, series, summary}
    """
    ct = _curr_type_for(reporter, currency)
    series = query(
        "WS_LBS_D_PUB",
        FREQ="Q", L_MEASURE="S", L_POSITION=position,
        L_INSTR=instrument, L_DENOM=currency, L_CURR_TYPE=ct,
        L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
        L_CP_SECTOR=sector, L_CP_COUNTRY=counterparty,
        L_POS_TYPE=pos_type, start=start, end=end,
    )
    out: Dict[str, Any] = {
        "reporter": reporter,
        "counterparty": counterparty,
        "currency": currency,
        "sector": sector,
        "instrument": instrument,
        "position": position,
        "pos_type": pos_type,
        "l_curr_type": ct,
        "series": series,
        "summary": {},
    }
    v, p = _latest_value(series)
    if v is not None:
        out["summary"] = {"value": v, "period": p}
    return out


def recipe_nbfi(*, start: str = "2010", end: Optional[str] = None,
                reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Non-bank financial intermediation (shadow banking) cross-border exposure.

    Queries LBS with `L_CP_SECTOR=F` (Non-bank financial institutions
    — money market funds, hedge funds, finance companies, securitisation
    vehicles, etc.).  This is the core "shadow banking" measure.

    Args:
        start:     Start period.
        end:       End period.
        reporters: List of LBS reporter ISO codes.  Default = the 16
                   major reporting centers covering ~90% of global
                   cross-border NBFI exposure.

    Returns:
        {start_period, series, summary} where:
          - series.global_nbfi_<ccy> for total NBFI claims by currency
          - series.<rep>_nbfi_claims per reporter
          - series.global_nbfi_growth (YoY)
          - summary maps each to {value, period}
    """
    if reporters is None:
        reporters = ["US", "GB", "JP", "DE", "FR", "CH", "HK", "SG",
                     "CA", "AU", "NL", "IE", "LU", "IT", "ES", "BE"]

    out: Dict[str, Any] = {"start_period": start, "series": {}, "summary": {}}

    # Cross-border claims by counterparty sector (global aggregate).
    sector_codes = {"A": "All", "B": "Banks", "I": "Related offices",
                    "F": "NBFI", "C": "Non-financial corps",
                    "G": "Government", "H": "Households", "N": "Non-banks"}
    for code, label in sector_codes.items():
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                  L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR=code, L_CP_COUNTRY="5J", L_POS_TYPE="N",
                  start=start, end=end)
        out["series"][f"sector_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][f"sector_{label}"] = {"value": v, "period": p}

    # USD + EUR NBFI specifically
    for ccy in ("USD", "EUR"):
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                  L_INSTR="A", L_DENOM=ccy, L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR="F", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                  start=start, end=end)
        out["series"][f"nbfi_{ccy.lower()}_global"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][f"nbfi_{ccy.lower()}_global"] = {"value": v, "period": p}

    # NBFI claims by reporting center
    out["summary"]["nbfi_by_reporter"] = {}
    for rep in reporters:
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                      L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                      L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                      L_CP_SECTOR="F", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                      start=start, end=end)
        except ValueError:
            continue
        out["series"][f"{rep}_nbfi_claims"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["nbfi_by_reporter"][rep] = {"value": v, "period": p}

    # YoY growth of NBFI claims
    growth = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="G", L_POSITION="C",
                   L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                   L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                   L_CP_SECTOR="F", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                   start=start, end=end)
    out["series"]["nbfi_global_growth_yoy"] = growth
    v, p = _latest_value(growth)
    if v is not None:
        out["summary"]["nbfi_global_growth_yoy"] = {"value": v, "period": p}
    return out


def recipe_interbank(*, currency: str = "USD", start: str = "2010",
                     end: Optional[str] = None,
                     reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Interbank loans & deposits — repo / money-market proxy.

    Queries LBS with `L_INSTR=G` (Loans & deposits) + `L_CP_SECTOR=B`
    (Banks).  This captures the cross-border interbank market —
    historically a strong proxy for repo / money-market stress.

    Also returns intra-group (related offices, `L_CP_SECTOR=I`)
    positions which capture internal bank-group liquidity flows.

    Args:
        currency: L_DENOM (USD / EUR / JPY / GBP / CHF).
        start:    Start period.
        end:      End period.
        reporters: Per-reporter breakdown.  Default = 12 major centers.
    """
    if reporters is None:
        reporters = ["US", "GB", "JP", "FR", "DE", "CH", "HK", "SG",
                     "CA", "KY", "LU", "IE"]

    out: Dict[str, Any] = {"currency": currency, "start_period": start,
                           "series": {}, "summary": {"per_reporter": {}}}

    # Global interbank claims + liabilities in currency
    for pos, label in (("C", "claims"), ("L", "liabs")):
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION=pos,
                  L_INSTR="G", L_DENOM=currency, L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR="B", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                  start=start, end=end)
        out["series"][f"global_interbank_{label}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][f"global_interbank_{label}"] = {"value": v, "period": p}

    # Intra-group positions (related offices)
    for pos, label in (("C", "claims"), ("L", "liabs")):
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION=pos,
                  L_INSTR="A", L_DENOM=currency, L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR="I", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                  start=start, end=end)
        out["series"][f"intragroup_{label}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][f"intragroup_{label}"] = {"value": v, "period": p}

    # Per-reporter interbank claims
    for rep in reporters:
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                      L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                      L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                      L_CP_SECTOR="B", L_CP_COUNTRY="5J", L_POS_TYPE="N",
                      start=start, end=end)
        except ValueError:
            continue
        out["series"][f"{rep}_interbank_claims"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["per_reporter"][rep] = {"value": v, "period": p}

    return out


def recipe_offshore_centers(*, start: str = "2010", end: Optional[str] = None,
                            centers: Optional[List[str]] = None) -> Dict[str, Any]:
    """Per-center cross-border intermediation analysis.

    For each offshore center: total cross-border claims + liabilities,
    net position, USD share, EUR share, FCY share.  Identifies role
    (FCY supplier vs borrower) and currency hub specialization.

    Args:
        start:    Start period.
        end:      End period.
        centers:  List of LBS reporter ISO codes treated as offshore /
                  onshore intermediation centers.  Default = the 9
                  systemically-important centers (GB, HK, SG, KY, LU,
                  IE, JE, CH, JP) — covers ~85% of global cross-border
                  intermediation outside the US.
    """
    if centers is None:
        centers = ["GB", "HK", "SG", "KY", "LU", "IE", "JE", "CH", "JP"]

    out: Dict[str, Any] = {"start_period": start, "series": {},
                           "summary": {}}

    for ctr in centers:
        out["summary"][ctr] = {}
        for pos, label in (("C", "claims"), ("L", "liabs")):
            try:
                s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                          L_POSITION=pos, L_INSTR="A", L_DENOM="TO1",
                          L_CURR_TYPE="A", L_PARENT_CTY="5J",
                          L_REP_BANK_TYPE="A", L_REP_CTY=ctr,
                          L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                          L_POS_TYPE="N", start=start, end=end)
            except ValueError:
                continue
            out["series"][f"{ctr}_{label}"] = s
            v, _ = _latest_value(s)
            if v is not None:
                out["summary"][ctr][f"total_{label}"] = v

        # USD share (foreign currency for non-US centers)
        try:
            ct = _curr_type_for(ctr, "USD")
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="C", L_INSTR="A", L_DENOM="USD",
                      L_CURR_TYPE=ct, L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY=ctr,
                      L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                      L_POS_TYPE="N", start=start, end=end)
            out["series"][f"{ctr}_usd_claims"] = s
            v, _ = _latest_value(s)
            if v is not None:
                out["summary"][ctr]["usd_claims"] = v
        except ValueError:
            pass

        # Compute net + role
        c = out["summary"][ctr].get("total_claims")
        l = out["summary"][ctr].get("total_liabs")
        if c is not None and l is not None:
            try:
                net = float(c) - float(l)
                out["summary"][ctr]["net"] = net
                out["summary"][ctr]["role"] = "CREDITOR" if net > 0 else "DEBTOR"
            except (TypeError, ValueError):
                pass
    return out


def recipe_bank_nationality(*, start: str = "2010", end: Optional[str] = None,
                            parents: Optional[List[str]] = None) -> Dict[str, Any]:
    """Global cross-border claims by bank nationality (parent HQ country).

    Per BIS publication policy, only the `L_REP_CTY=5A` (all-reporters
    aggregate) × `L_PARENT_CTY=<country>` combination is published —
    individual host × parent pairs are confidentiality-redacted.

    Args:
        start:    Start period.
        end:      End period.
        parents:  Parent HQ ISO codes.  Default = 10 systemic banking
                  nationalities (US, JP, DE, FR, CN, GB, CH, NL, IT, ES).
    """
    if parents is None:
        parents = ["US", "JP", "DE", "FR", "CN", "GB", "CH", "NL", "IT", "ES"]

    out: Dict[str, Any] = {"start_period": start, "series": {},
                           "summary": {"by_parent": {}}}

    for parent in parents:
        out["summary"]["by_parent"][parent] = {}
        for ccy in ("TO1", "USD"):
            try:
                s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                          L_POSITION="C", L_INSTR="A", L_DENOM=ccy,
                          L_CURR_TYPE="A", L_PARENT_CTY=parent,
                          L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                          L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                          L_POS_TYPE="N", start=start, end=end)
            except ValueError:
                continue
            out["series"][f"{parent}_{ccy.lower()}_claims"] = s
            v, p = _latest_value(s)
            if v is not None:
                out["summary"]["by_parent"][parent][f"{ccy.lower()}_claims"] = {
                    "value": v, "period": p,
                }
    return out


def recipe_fcy_mismatch(*, start: str = "2010", end: Optional[str] = None,
                        reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Foreign-currency cross-border share by reporter (FX-vulnerability indicator).

    For each reporter: All-currency total vs Foreign-currency total →
    `fcy_share_pct`.  High share signals FX exposure (and FX-funding
    vulnerability if liabilities side > claims side in foreign ccy).

    Args:
        start:     Start period.
        end:       End period.
        reporters: ISO list.  Default = 14 major + EM reporters.
    """
    if reporters is None:
        reporters = ["US", "GB", "JP", "DE", "FR", "CH", "AU", "CA",
                     "HK", "SG", "KR", "BR", "MX", "TR"]

    out: Dict[str, Any] = {"start_period": start, "series": {},
                           "summary": {}}

    for rep in reporters:
        all_ccy = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                         L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                         L_CURR_TYPE="A", L_PARENT_CTY="5J",
                         L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                         L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                         L_POS_TYPE="N", start=start, end=end)
        fcy = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                     L_POSITION="C", L_INSTR="A", L_DENOM="TO3",
                     L_CURR_TYPE="F", L_PARENT_CTY="5J",
                     L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                     L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                     L_POS_TYPE="N", start=start, end=end)
        out["series"][f"{rep}_total"] = all_ccy
        out["series"][f"{rep}_fcy"] = fcy
        tot, p = _latest_value(all_ccy)
        fcyv, _ = _latest_value(fcy)
        if tot and fcyv is not None:
            try:
                share = float(fcyv) / float(tot) * 100.0
                out["summary"][rep] = {
                    "total_claims": tot, "fcy_claims": fcyv,
                    "fcy_share_pct": share, "period": p,
                }
            except (TypeError, ValueError, ZeroDivisionError):
                pass
    return out


def recipe_sector_matrix(reporter: str, *, start: str = "2010",
                          end: Optional[str] = None) -> Dict[str, Any]:
    """Per-reporter counterparty-sector breakdown (with currency + instrument splits).

    For one reporter, decompose cross-border claims by counterparty
    sector (Banks, NBFI, Non-financial corps, Government, Households,
    Related offices) — both all-currency and USD.  Plus instrument
    breakdown across the same sectors.

    Args:
        reporter: LBS reporter ISO (US, GB, JP, ...).
        start:    Start period.
        end:      End period.
    """
    sectors = {"A": "All", "B": "Banks", "F": "NBFI",
               "C": "Non-financial corps", "G": "Government",
               "H": "Households", "I": "Related offices",
               "N": "Non-banks"}
    instruments = {"A": "All", "G": "Loans+deposits", "D": "Debt",
                   "B": "Credit", "V": "Derivatives"}

    out: Dict[str, Any] = {"reporter": reporter, "start_period": start,
                           "series": {}, "summary": {"by_sector": {},
                                                      "by_instrument": {}}}

    # By sector (all-currency + USD)
    for code, label in sectors.items():
        out["summary"]["by_sector"][label] = {}
        for ccy in ("TO1", "USD"):
            ct = _curr_type_for(reporter, ccy)
            try:
                s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                          L_POSITION="C", L_INSTR="A", L_DENOM=ccy,
                          L_CURR_TYPE=ct, L_PARENT_CTY="5J",
                          L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
                          L_CP_SECTOR=code, L_CP_COUNTRY="5J",
                          L_POS_TYPE="N", start=start, end=end)
            except ValueError:
                continue
            out["series"][f"sector_{code}_{ccy.lower()}"] = s
            v, p = _latest_value(s)
            if v is not None:
                out["summary"]["by_sector"][label][ccy.lower()] = {
                    "value": v, "period": p,
                }

    # By instrument (all sectors aggregate)
    for code, label in instruments.items():
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="C", L_INSTR=code, L_DENOM="TO1",
                      L_CURR_TYPE="A", L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
                      L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                      L_POS_TYPE="N", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"instrument_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_instrument"][label] = {"value": v, "period": p}

    return out


def recipe_lbs_exposure_to(target: str, *, start: str = "2010",
                            end: Optional[str] = None,
                            reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """Per-reporter LBS exposure to one target counterparty country.

    Aggregate (all reporters) total/USD/EUR claims on target country,
    plus per-reporter breakdown of who is exposed and by how much,
    plus sectoral breakdown of the aggregate.

    Args:
        target:    Counterparty country ISO.
        start:     Start period.
        end:       End period.
        reporters: Per-reporter breakdown reporters.  Default = 12
                   major centers.
    """
    if reporters is None:
        reporters = ["US", "GB", "JP", "DE", "FR", "CH", "ES", "IT",
                     "AT", "BE", "NL", "HK"]

    out: Dict[str, Any] = {"target": target, "start_period": start,
                           "series": {}, "summary": {"by_reporter": {},
                                                      "by_sector": {}}}

    # Aggregate claims (all reporters) — TO1, USD, EUR
    for ccy in ("TO1", "USD", "EUR"):
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                  L_INSTR="A", L_DENOM=ccy, L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR="A", L_CP_COUNTRY=target, L_POS_TYPE="N",
                  start=start, end=end)
        out["series"][f"aggregate_{ccy.lower()}_claims"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][f"aggregate_{ccy.lower()}_claims"] = {
                "value": v, "period": p,
            }

    # Per-reporter breakdown
    for rep in reporters:
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="C", L_INSTR="A", L_DENOM="TO1",
                      L_CURR_TYPE="A", L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY=rep,
                      L_CP_SECTOR="A", L_CP_COUNTRY=target,
                      L_POS_TYPE="N", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"{rep}_to_{target}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_reporter"][rep] = {"value": v, "period": p}

    # Sectoral breakdown of aggregate exposure
    sectors = {"B": "Banks", "F": "NBFI", "C": "Corps", "G": "Govt",
               "H": "Households"}
    for code, label in sectors.items():
        s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S", L_POSITION="C",
                  L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
                  L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="5A",
                  L_CP_SECTOR=code, L_CP_COUNTRY=target, L_POS_TYPE="N",
                  start=start, end=end)
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_sector"][label] = {"value": v, "period": p}
    return out


def recipe_usd_funding(reporter: str, *, start: str = "2010",
                        end: Optional[str] = None) -> Dict[str, Any]:
    """USD liabilities (funding) structure for one reporter.

    Decomposes USD cross-border LIABILITIES by funding sector — who
    is providing dollar funding to banks in this jurisdiction?
    Banks (interbank), NBFI (money market funds, hedge funds),
    Non-financial corps (corporate deposits), Central banks (FX
    swap lines, repo arrangements), Government, Households,
    Related offices (intra-group).

    Plus instrument breakdown: loans+deposits vs debt securities vs
    derivatives.

    Args:
        reporter: LBS reporter ISO (e.g. "GB" for the eurodollar hub,
                  "JP" for Japanese banks' USD funding).
        start:    Start period.
        end:      End period.
    """
    sectors = {"A": "All", "B": "Banks", "I": "Related offices",
               "F": "NBFI", "C": "Non-financial corps",
               "M": "Central banks", "G": "Government", "H": "Households"}
    instruments = {"A": "All", "G": "Loans+deposits",
                   "D": "Debt securities", "V": "Derivatives"}

    ct = _curr_type_for(reporter, "USD")
    out: Dict[str, Any] = {"reporter": reporter, "currency": "USD",
                           "l_curr_type": ct, "start_period": start,
                           "series": {}, "summary": {"by_sector": {},
                                                      "by_instrument": {}}}

    # USD liabilities by funding sector
    for code, label in sectors.items():
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="L", L_INSTR="A", L_DENOM="USD",
                      L_CURR_TYPE=ct, L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
                      L_CP_SECTOR=code, L_CP_COUNTRY="5J",
                      L_POS_TYPE="N", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"sector_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_sector"][label] = {"value": v, "period": p}

    # USD liabilities by instrument
    for code, label in instruments.items():
        try:
            s = query("WS_LBS_D_PUB", FREQ="Q", L_MEASURE="S",
                      L_POSITION="L", L_INSTR=code, L_DENOM="USD",
                      L_CURR_TYPE=ct, L_PARENT_CTY="5J",
                      L_REP_BANK_TYPE="A", L_REP_CTY=reporter,
                      L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                      L_POS_TYPE="N", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"instrument_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_instrument"][label] = {"value": v, "period": p}
    return out


def recipe_cbs_foreign_claims(reporter: str, *, basis: str = "F",
                              bank_type: str = "4R",
                              start: str = "2010",
                              end: Optional[str] = None) -> Dict[str, Any]:
    """CBS foreign claims for one reporter (consolidated by HQ nationality).

    Returns total foreign claims + cross-border / local breakdown +
    sectoral decomposition (Banks / NBFI / Corps / Households /
    Official) for the reporter's banking system on a consolidated
    basis (HQ aggregation, immediate or guarantor).

    Args:
        reporter:   CBS reporter ISO (33 reporting jurisdictions).
        basis:      F = immediate counterparty (default), U = guarantor,
                    R = guarantor calculated (F+Q).
        bank_type:  4R = domestic banks excl. domestic positions
                    (default; the canonical "foreign claims" measure).
                    4B = all domestic banks, 4M = all banks incl. foreign.
        start:      Start period.
        end:        End period.
    """
    out: Dict[str, Any] = {"reporter": reporter, "basis": basis,
                           "bank_type": bank_type, "start_period": start,
                           "series": {}, "summary": {"by_position": {},
                                                      "by_sector": {}}}

    # Position breakdown.  On F basis: I (intl), C, B, M.  On U: C, B, D, W, X.
    if basis == "F":
        positions = {"I": "International claims (cross-border + local FCY)",
                     "C": "Total claims",
                     "B": "Local claims (in counterparty country)",
                     "M": "Local liabilities"}
    else:
        positions = {"C": "Total claims (ultimate-risk)",
                     "B": "Local claims",
                     "D": "Cross-border claims",
                     "W": "Guarantees extended",
                     "X": "Credit commitments"}

    for code, label in positions.items():
        try:
            s = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY=reporter, CBS_BANK_TYPE=bank_type,
                      CBS_BASIS=basis, L_POSITION=code, L_INSTR="A",
                      REM_MATURITY="A", CURR_TYPE_BOOK="TO1",
                      L_CP_SECTOR="A", L_CP_COUNTRY="5J",
                      start=start, end=end)
        except ValueError:
            continue
        out["series"][f"position_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_position"][label] = {"value": v, "period": p}

    # Sectoral breakdown (use the canonical broad measure)
    canonical_pos = "I" if basis == "F" else "C"
    sectors = {"A": "All", "B": "Banks", "F": "NBFI", "C": "Corps",
               "H": "Households", "O": "Official"}
    for code, label in sectors.items():
        try:
            s = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY=reporter, CBS_BANK_TYPE=bank_type,
                      CBS_BASIS=basis, L_POSITION=canonical_pos,
                      L_INSTR="A", REM_MATURITY="A",
                      CURR_TYPE_BOOK="TO1", L_CP_SECTOR=code,
                      L_CP_COUNTRY="5J", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"sector_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_sector"][label] = {"value": v, "period": p}
    return out


def recipe_cbs_exposure_to(target: str, *, basis: str = "F",
                            bank_type: str = "4R",
                            start: str = "2010",
                            end: Optional[str] = None,
                            reporters: Optional[List[str]] = None) -> Dict[str, Any]:
    """CBS exposure to one target country (which national banking systems are exposed).

    Returns aggregate (all-reporters) international/total claims on
    target country, plus per-reporter breakdown of which national
    banking systems carry the most exposure.  Use `basis='U'` for
    ultimate-risk view (after risk transfers).

    Args:
        target:     Counterparty country ISO.
        basis:      F (immediate) or U (guarantor / ultimate risk).
        bank_type:  4R (default — domestic banks excl. domestic),
                    4B (all domestic), 4M (all banks).
        start:      Start period.
        end:        End period.
        reporters:  Reporter ISOs for the per-reporter breakdown.
                    Default = the CBS reporters with the largest
                    exposures historically.
    """
    if reporters is None:
        reporters = ["US", "GB", "JP", "DE", "FR", "ES", "IT", "CH",
                     "AT", "BE", "NL", "AU", "CA"]

    canonical_pos = "I" if basis == "F" else "C"

    out: Dict[str, Any] = {"target": target, "basis": basis,
                           "bank_type": bank_type, "start_period": start,
                           "series": {}, "summary": {"by_reporter": {}}}

    # Aggregate
    s = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S", L_REP_CTY="5A",
              CBS_BANK_TYPE=bank_type, CBS_BASIS=basis,
              L_POSITION=canonical_pos, L_INSTR="A", REM_MATURITY="A",
              CURR_TYPE_BOOK="TO1", L_CP_SECTOR="A", L_CP_COUNTRY=target,
              start=start, end=end)
    out["series"]["aggregate"] = s
    v, p = _latest_value(s)
    if v is not None:
        out["summary"]["aggregate"] = {"value": v, "period": p}

    # Per-reporter
    for rep in reporters:
        try:
            s = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY=rep, CBS_BANK_TYPE=bank_type,
                      CBS_BASIS=basis, L_POSITION=canonical_pos,
                      L_INSTR="A", REM_MATURITY="A",
                      CURR_TYPE_BOOK="TO1", L_CP_SECTOR="A",
                      L_CP_COUNTRY=target, start=start, end=end)
        except ValueError:
            continue
        out["series"][f"{rep}_to_{target}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"]["by_reporter"][rep] = {"value": v, "period": p}
    return out


def recipe_cbs_maturity(reporter: str, *, basis: str = "F",
                         bank_type: str = "4R",
                         start: str = "2010",
                         end: Optional[str] = None) -> Dict[str, Any]:
    """CBS remaining-maturity breakdown for one reporter.

    Splits foreign claims by remaining maturity bucket — Up to 1 year
    (U) / Over 1-2 years (M) / Over 2 years (N).  High short-term
    share signals rollover / refinancing risk.

    Note: Maturity breakdown is only published with `L_INSTR='A'` and
    `CURR_TYPE_BOOK='TO1'` on F basis at `L_POSITION='I'`.

    Args:
        reporter:  CBS reporter ISO.
        basis:     F (default) or U.
        bank_type: 4R (default).
        start:     Start period.
        end:       End period.
    """
    canonical_pos = "I" if basis == "F" else "C"
    maturities = {"A": "All maturities",
                  "U": "Up to 1 year (short-term)",
                  "M": "Over 1-2 years (medium-term)",
                  "N": "Over 2 years (long-term)"}

    out: Dict[str, Any] = {"reporter": reporter, "basis": basis,
                           "start_period": start, "series": {},
                           "summary": {}}

    for code, label in maturities.items():
        try:
            s = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                      L_REP_CTY=reporter, CBS_BANK_TYPE=bank_type,
                      CBS_BASIS=basis, L_POSITION=canonical_pos,
                      L_INSTR="A", REM_MATURITY=code,
                      CURR_TYPE_BOOK="TO1", L_CP_SECTOR="A",
                      L_CP_COUNTRY="5J", start=start, end=end)
        except ValueError:
            continue
        out["series"][f"maturity_{code}"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][label] = {"value": v, "period": p}

    # Compute short-term share if both available
    short = out["summary"].get("Up to 1 year (short-term)", {}).get("value")
    total = out["summary"].get("All maturities", {}).get("value")
    if short and total:
        try:
            out["summary"]["short_term_share_pct"] = float(short) / float(total) * 100.0
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    return out


def recipe_cbs_guarantor_diff(reporter: str, *,
                               targets: Optional[List[str]] = None,
                               start: str = "2010",
                               end: Optional[str] = None) -> Dict[str, Any]:
    """CBS immediate vs guarantor basis diff (risk transfer detection).

    For each target country, compute foreign-claims on immediate
    counterparty basis (F, L_POSITION=I) vs guarantor basis (U,
    L_POSITION=C).  Diff > 0 = inward risk transfers (parent banks
    guaranteeing local subs); diff < 0 = outward risk transfers
    (guarantees provided to entities outside that country).

    Args:
        reporter: CBS reporter ISO.
        targets:  Counterparty ISOs.  Default = a panel of
                  systemically-important + EM countries.
        start:    Start period.
        end:      End period.
    """
    if targets is None:
        targets = ["US", "GB", "DE", "FR", "JP", "CN", "TR", "RU",
                   "MX", "BR", "IN", "ID", "ZA", "AR", "5A"]

    out: Dict[str, Any] = {"reporter": reporter, "start_period": start,
                           "series": {}, "summary": {}}

    for target in targets:
        try:
            imm = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                        L_REP_CTY=reporter, CBS_BANK_TYPE="4R",
                        CBS_BASIS="F", L_POSITION="I", L_INSTR="A",
                        REM_MATURITY="A", CURR_TYPE_BOOK="TO1",
                        L_CP_SECTOR="A", L_CP_COUNTRY=target,
                        start=start, end=end)
            gtor = query("WS_CBS_PUB", FREQ="Q", L_MEASURE="S",
                         L_REP_CTY=reporter, CBS_BANK_TYPE="4R",
                         CBS_BASIS="U", L_POSITION="C", L_INSTR="A",
                         REM_MATURITY="A", CURR_TYPE_BOOK="TO1",
                         L_CP_SECTOR="A", L_CP_COUNTRY=target,
                         start=start, end=end)
        except ValueError:
            continue
        out["series"][f"{target}_immediate"] = imm
        out["series"][f"{target}_guarantor"] = gtor
        v_imm, p_imm = _latest_value(imm)
        v_gtor, p_gtor = _latest_value(gtor)
        if v_imm is not None and v_gtor is not None:
            try:
                diff = float(v_gtor) - float(v_imm)
                out["summary"][target] = {
                    "immediate": v_imm,
                    "guarantor": v_gtor,
                    "diff": diff,
                    "direction": "INWARD_RISK_TRANSFER" if diff > 0
                                 else "OUTWARD_RISK_TRANSFER" if diff < 0
                                 else "NEUTRAL",
                    "period": p_imm,
                }
            except (TypeError, ValueError):
                pass
    return out


def recipe_gli_currency(*, currency: str = "USD",
                         regions: Optional[List[str]] = None,
                         start: str = "2010",
                         end: Optional[str] = None) -> Dict[str, Any]:
    """Global liquidity indicators by currency (USD / EUR / JPY).

    Total credit to non-bank borrowers outside the currency's home
    country.  This is the canonical "eurodollar / euroeuro / euroyen"
    aggregate that BIS publishes as its global-liquidity indicator.

    Args:
        currency: USD / EUR / JPY (the 3 currencies BIS tracks at GLI
                  granularity).
        regions:  Borrower regions.  Default = global + 4 EM regions.
        start:    Start period.
        end:      End period.
    """
    if regions is None:
        regions = ["3P", "4T", "4U", "4W", "4Y"]
        # 3P=All non-resident, 4T=EM, 4U=Latin America+Caribbean,
        # 4W=Africa+Middle East, 4Y=Asia+Pacific

    out: Dict[str, Any] = {"currency": currency, "start_period": start,
                           "series": {}, "summary": {}}

    instruments = {"B": "Total credit", "G": "Bank loans",
                   "D": "Debt securities"}

    for region in regions:
        out["summary"][region] = {}
        for instr_code, instr_label in instruments.items():
            try:
                s = query("WS_GLI", FREQ="Q", CURR_DENOM=currency,
                          BORROWERS_CTY=region, BORROWERS_SECTOR="N",
                          LENDERS_SECTOR="A", L_POS_TYPE="I",
                          L_INSTR=instr_code, UNIT_MEASURE=currency,
                          start=start, end=end)
            except ValueError:
                continue
            out["series"][f"{region}_{instr_code}"] = s
            v, p = _latest_value(s)
            if v is not None:
                out["summary"][region][instr_label] = {
                    "value": v, "period": p,
                }

    # YoY growth (region=3P=global)
    try:
        growth = query("WS_GLI", FREQ="Q", CURR_DENOM=currency,
                       BORROWERS_CTY="3P", BORROWERS_SECTOR="N",
                       LENDERS_SECTOR="A", L_POS_TYPE="I", L_INSTR="B",
                       UNIT_MEASURE="771",  # YoY growth %
                       start=start, end=end)
        out["series"]["global_yoy_growth"] = growth
        v, p = _latest_value(growth)
        if v is not None:
            out["summary"]["global_yoy_growth_pct"] = {
                "value": v, "period": p,
            }
    except ValueError:
        pass
    return out


def recipe_gli_all_currencies(*, start: str = "2010",
                               end: Optional[str] = None) -> Dict[str, Any]:
    """Compare USD vs EUR vs JPY global liquidity (the trilemma view).

    For each of USD / EUR / JPY: total credit to non-bank borrowers
    outside the currency's home country, in the currency's native
    units, plus YoY growth.  Useful for "is dollar liquidity growing
    faster than euro liquidity?" type questions.

    Args:
        start: Start period.
        end:   End period.
    """
    out: Dict[str, Any] = {"start_period": start, "series": {},
                           "summary": {}}
    for ccy in ("USD", "EUR", "JPY"):
        out["summary"][ccy] = {}
        # Outstanding in native units
        s = query("WS_GLI", FREQ="Q", CURR_DENOM=ccy,
                  BORROWERS_CTY="3P", BORROWERS_SECTOR="N",
                  LENDERS_SECTOR="A", L_POS_TYPE="I", L_INSTR="B",
                  UNIT_MEASURE=ccy, start=start, end=end)
        out["series"][f"{ccy}_outstanding"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][ccy]["outstanding"] = {"value": v, "period": p}

        # YoY growth
        s = query("WS_GLI", FREQ="Q", CURR_DENOM=ccy,
                  BORROWERS_CTY="3P", BORROWERS_SECTOR="N",
                  LENDERS_SECTOR="A", L_POS_TYPE="I", L_INSTR="B",
                  UNIT_MEASURE="771", start=start, end=end)
        out["series"][f"{ccy}_growth_yoy"] = s
        v, p = _latest_value(s)
        if v is not None:
            out["summary"][ccy]["growth_yoy_pct"] = {
                "value": v, "period": p,
            }
    return out


def recipe_universe_smoke(*, start: str = "2024",
                          end: Optional[str] = None) -> Dict[str, Any]:
    """Validate every dataflow returns data via its embedded defaults.

    Runs `query_default(flow_id, start=start)` against every
    dataflow registered in the embedded ontology that has a
    `_FLOW_DEFAULTS` entry.  Reports per-flow result + total
    coverage.

    Useful as a smoke test of the universe-first layer + as a way
    for PRISM to confirm the ontology is healthy before doing any
    serious analysis.

    Args:
        start: Start period (default "2024" — keeps result small).
        end:   End period.

    Returns:
        {generated_at, total_flows, ok_flows, empty_flows,
         error_flows, results: [{flow_id, status, n_series,
         latest_period, latest_value, error}]}
    """
    out: Dict[str, Any] = {
        "start_period": start,
        "total_flows": len(_DATAFLOWS),
        "ok_flows": 0,
        "empty_flows": 0,
        "error_flows": 0,
        "results": [],
    }
    for fid in sorted(_DATAFLOWS.keys()):
        if fid not in _FLOW_DEFAULTS:
            out["results"].append({
                "flow_id": fid, "status": "NO_DEFAULT",
                "n_series": 0, "error": "no _FLOW_DEFAULTS entry",
            })
            out["error_flows"] += 1
            continue
        try:
            series = query_default(fid, start=start, end=end)
        except Exception as e:
            out["results"].append({
                "flow_id": fid, "status": "ERROR",
                "n_series": 0, "error": f"{type(e).__name__}: {e}",
            })
            out["error_flows"] += 1
            continue
        if not series:
            out["results"].append({
                "flow_id": fid, "status": "EMPTY",
                "n_series": 0,
            })
            out["empty_flows"] += 1
            continue
        v, p = _latest_value(series)
        out["results"].append({
            "flow_id": fid, "status": "OK",
            "n_series": len(series),
            "latest_period": p,
            "latest_value": v,
        })
        out["ok_flows"] += 1
    return out


# ─── PRISM ergonomics: pandas conversion + multi-flow alignment ──────────
#
# Per Design Principle #7 (Engines Absorb Friction).  PRISM lives in
# pandas.  Without these helpers PRISM has to write 10 lines of
# series-iteration code on every BIS query.  pandas is lazy-imported so
# the module itself has no pandas runtime dependency at import time.


def series_to_dataframe(series: List[Dict[str, Any]], *,
                        value_col: Optional[str] = None,
                        period_col: str = "period",
                        dim_cols: bool = True,
                        wide: bool = False) -> Any:
    """Convert a BIS series list to a pandas DataFrame.

    Tall (default): one row per (series, period).  Columns:
      - dim columns (one per dimension, with the dim id as column name)
      - {period_col}: period string (e.g. "2024-Q3")
      - {value_col or "value"}: numeric observation

    Wide: pivot so each series becomes a column.  Columns:
      - {period_col}: period (index)
      - one column per series (named with the series key)

    Args:
        series:     List returned by query() / query_default() /
                    recipe_*() (the latter's "series" sub-dicts).
        value_col:  Column name for the observation.  Defaults to
                    "value" (tall) or the series key (wide).
        period_col: Column name for the period.  Default "period".
        dim_cols:   When True (tall mode), include each dim id as a
                    column with its code value.  False = just period
                    and value.
        wide:       When True, return a wide DataFrame.

    Returns:
        pandas.DataFrame.

    Raises:
        ImportError if pandas is not available.
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "series_to_dataframe requires pandas.  Install via "
            "`pip install pandas` (PRISM's sandbox already has it)."
        ) from e

    if not series:
        return pd.DataFrame()

    if wide:
        cols: Dict[str, Dict[str, Any]] = {}
        for s in series:
            label = value_col or s.get("key", "")
            obs = s.get("observations") or {}
            cols[label] = obs
        df = pd.DataFrame(cols)
        df.index.name = period_col
        return df.sort_index()

    rows: List[Dict[str, Any]] = []
    val_label = value_col or "value"
    for s in series:
        dim_record: Dict[str, Any] = {}
        if dim_cols:
            for dim_id, dim in (s.get("dimensions") or {}).items():
                dim_record[dim_id] = dim.get("id") if isinstance(dim, dict) else dim
        for period, value in (s.get("observations") or {}).items():
            row = dict(dim_record)
            row[period_col] = period
            row[val_label] = value
            rows.append(row)
    df = pd.DataFrame(rows)
    if rows:
        df = df.sort_values(period_col).reset_index(drop=True)
    return df


def fetch_aligned(specs: List[Dict[str, Any]], *,
                  start: Optional[str] = None,
                  end: Optional[str] = None,
                  on: str = "period",
                  how: str = "outer") -> Any:
    """Query multiple flows in one call and merge by period into a wide DataFrame.

    Each spec is a dict:
        {"name": "<column name>",     # required — becomes the column header
         "flow_id": "<flow or alias>", # required
         "kwargs": {...}}              # optional kwargs for query()

    All series are reduced to a single value per period (first series
    if multiple match).  Merged on `period` with `how` join.  Useful
    for cross-flow analysis: "show me US policy rate vs credit gap vs
    inflation in one frame".

    Args:
        specs:  List of spec dicts (see above).
        start:  Start period applied to all queries.
        end:    End period applied to all queries.
        on:     Column to merge on (default "period").
        how:    pandas merge how ("outer" / "inner" / "left").

    Returns:
        pandas.DataFrame indexed by period with one column per spec.

    Raises:
        ImportError if pandas not available.
        KeyError if a spec is missing "name" or "flow_id".

    Example:
        df = bis_client.fetch_aligned([
            {"name": "policy_rate",
             "flow_id": "policy-rates",
             "kwargs": {"FREQ": "M", "REF_AREA": "US"}},
            {"name": "credit_gap",
             "flow_id": "credit-gap",
             "kwargs": {"FREQ": "Q", "BORROWERS_CTY": "US",
                        "TC_BORROWERS": "P", "TC_LENDERS": "A",
                        "CG_DTYPE": "C"}},
            {"name": "cpi_yoy",
             "flow_id": "cpi",
             "kwargs": {"FREQ": "M", "REF_AREA": "US",
                        "UNIT_MEASURE": "771"}},
        ], start="2010")
        # → DataFrame with columns ["policy_rate", "credit_gap",
        #     "cpi_yoy"] indexed by period (string).  Mixed-frequency
        #     periods sit alongside each other (NaN-filled where one
        #     series doesn't have data for that period).
    """
    try:
        import pandas as pd
    except ImportError as e:
        raise ImportError(
            "fetch_aligned requires pandas."
        ) from e

    cols: Dict[str, Dict[str, Any]] = {}
    for spec in specs:
        if "name" not in spec or "flow_id" not in spec:
            raise KeyError(
                f"fetch_aligned spec must have 'name' and 'flow_id' keys; "
                f"got {list(spec.keys())}"
            )
        name = spec["name"]
        flow_id = spec["flow_id"]
        kwargs = dict(spec.get("kwargs") or {})
        try:
            series = query(flow_id, start=start, end=end, **kwargs)
        except Exception:
            series = []
        if not series:
            cols[name] = {}
            continue
        # Take first series's observations
        cols[name] = series[0].get("observations") or {}

    df = pd.DataFrame(cols)
    df.index.name = on
    return df.sort_index()


def latest(flow_id: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
    """Return the latest single observation for a flow, with metadata.

    Convenience for "what's the current US policy rate?" style
    queries.  Uses `query_default` overrides if no kwargs supplied.

    Args:
        flow_id:    flow id or alias.
        **kwargs:   Override / supplement default kwargs (FREQ,
                    REF_AREA, etc.).

    Returns:
        {value, period, dimensions (dict), attributes (dict),
         flow_id, key} for the latest observation across all
        returned series, or None if nothing matches.
    """
    fid = _resolve_flow(flow_id)
    final_kwargs = dict(_FLOW_DEFAULTS.get(fid, {}))
    final_kwargs.update(kwargs)
    series = query(fid, **final_kwargs)
    best_period, best_value, best_meta = None, None, None
    for s in series:
        obs = s.get("observations") or {}
        if not obs:
            continue
        latest_p = max(obs.keys())
        if best_period is None or latest_p > best_period:
            best_period = latest_p
            best_value = obs[latest_p]
            best_meta = s
    if best_meta is None:
        return None
    return {
        "value": best_value,
        "period": best_period,
        "dimensions": best_meta.get("dimensions") or {},
        "attributes": best_meta.get("attributes") or {},
        "flow_id": fid,
        "key": best_meta.get("key", ""),
    }


# ─── Layer 5: Refresh tool (offline) ──────────────────────────────────────


def refresh_ontology(*, write_to: Optional[str] = None,
                     verbose: bool = False,
                     probe_coverage: bool = True) -> Dict[str, Any]:
    """Re-fetch the full BIS SDMX ontology and return a fresh compact dict.

    Walks /structure/dataflow/BIS, then for each unique DSD calls
    /structure/datastructure/BIS/{DSD}/{VER}?references=children to get
    dimensions + ALL codelists (dim + attribute) + concepts in one
    shot.  Optionally probes /availability and /data for per-flow time
    coverage + series counts.

    The output matches the embedded-ontology shape exactly so when
    `write_to` is set, the file's `_BIS_ONTOLOGY_JSON` block is
    drop-in-replaced without losing any of the structural fields the
    embedded version carries (per-flow versions, attributes, time
    coverage, codelist hierarchies, code descriptions, concept
    descriptions).

    Args:
        write_to:       Optional path to a Python file containing the
                        triple-quoted `_BIS_ONTOLOGY_JSON = r\"\"\"...\"\"\"`
                        block.  When provided, the file is rewritten
                        in-place.  When None, just returns the dict.
        verbose:        Print per-DSD / per-flow progress.
        probe_coverage: When True (default), probe each flow's time
                        coverage + series count via live HTTP calls.
                        Adds ~30-60s.  Set False to skip and produce
                        a structure-only refresh.

    Returns:
        {"dataflows":  {flow_id: {name, description, dsd_id, version,
                                  dimensions, attributes, typical_freq,
                                  series_count, first_period,
                                  last_period}},
         "codelists":  {cl_id: {name, codes: {code_id: name_str | dict}}},
         "concepts":   {concept_id: name_str | dict}}
    """
    flows_path = _build_path("structure", "dataflow", "BIS",
                             query_params={"format": "sdmx-json"})
    flows_raw = _api_request_json(flows_path, timeout=120)
    if not flows_raw:
        raise RuntimeError("Could not fetch /structure/dataflow/BIS")
    raw_flows = flows_raw.get("data", {}).get("dataflows", []) or []

    flows_out: Dict[str, Any] = {}
    all_cls: Dict[str, Any] = {}
    all_concepts: Dict[str, Any] = {}
    seen_dsds: Dict[str, Any] = {}

    for i, flow in enumerate(raw_flows, 1):
        fid = flow["id"]
        dsd_urn = flow.get("structure", "")
        dsd_part = dsd_urn.split("DataStructure=BIS:")[-1] if "DataStructure=BIS:" in dsd_urn else ""
        dsd_id = dsd_part.split("(")[0]
        version = dsd_part.split("(")[1].rstrip(")") if "(" in dsd_part else DEFAULT_VERSION

        if verbose:
            print(f"[{i}/{len(raw_flows)}] {fid} (DSD: {dsd_id} v{version})")

        cache_key = f"{dsd_id}@{version}"
        if cache_key in seen_dsds:
            dsd = seen_dsds[cache_key]
        else:
            dsd_path = _build_path("structure", "datastructure", "BIS", dsd_id, version,
                                   query_params={"format": "sdmx-json",
                                                 "references": "children"})
            dsd_raw = _api_request_json(dsd_path, timeout=120)
            if not dsd_raw:
                if verbose:
                    print(f"  ! Could not fetch DSD {dsd_id}")
                continue
            dsd = dsd_raw.get("data", {})
            seen_dsds[cache_key] = dsd

            # Collect ALL codelists from this DSD (dim + attribute, with
            # parent + desc preserved per the compact-or-dict policy).
            for cl in dsd.get("codelists", []) or []:
                cl_id = cl["id"]
                if cl_id in all_cls:
                    continue
                codes: Dict[str, Any] = {}
                for code in cl.get("codes", []) or []:
                    code_id = code["id"]
                    name = ' '.join((code.get("name") or code_id).split())[:200]
                    parent = code.get("parent")
                    desc = code.get("description")
                    if parent or desc:
                        d: Dict[str, Any] = {"name": name}
                        if parent:
                            d["parent"] = parent
                        if desc:
                            desc_str = ' '.join(desc.split())[:300]
                            if desc_str != name:
                                d["desc"] = desc_str
                        codes[code_id] = d
                    else:
                        codes[code_id] = name
                all_cls[cl_id] = {
                    "name": ' '.join((cl.get("name") or "").split()).strip(),
                    "codes": codes,
                }

            # Collect concepts that carry descriptions.
            for cs in dsd.get("conceptSchemes", []) or []:
                for concept in cs.get("concepts", []) or []:
                    c_id = concept["id"]
                    if c_id in all_concepts:
                        continue
                    name = ' '.join((concept.get("name") or "").split()).strip()
                    desc = concept.get("description", "")
                    if desc and desc.strip():
                        desc_str = ' '.join(desc.split())[:300]
                        if name and desc_str != name:
                            all_concepts[c_id] = {"name": name, "desc": desc_str}
                        elif name:
                            all_concepts[c_id] = name
                        else:
                            all_concepts[c_id] = {"desc": desc_str}

        ds = (dsd.get("dataStructures") or [{}])[0]
        components = ds.get("dataStructureComponents", {})

        # Dimensions
        dims_raw = components.get("dimensionList", {}).get("dimensions", []) or []
        dim_list = []
        for d in sorted(dims_raw, key=lambda x: x.get("position", 0)):
            cl_urn = d.get("localRepresentation", {}).get("enumeration", "")
            cl_id = None
            if "Codelist=" in cl_urn:
                try:
                    cl_id = cl_urn.split("Codelist=")[1].split(":")[1].split("(")[0]
                except (IndexError, KeyError):
                    cl_id = None
            dim_list.append({"id": d["id"], "pos": d.get("position", 0), "cl": cl_id})

        # Attributes — embed per-flow so PRISM knows what to expect in
        # returned observations.
        attrs_raw = components.get("attributeList", {}).get("attributes", []) or []
        attr_list = []
        for a in attrs_raw:
            cl_urn = a.get("localRepresentation", {}).get("enumeration", "")
            cl_id = None
            if "Codelist=" in cl_urn:
                try:
                    cl_id = cl_urn.split("Codelist=")[1].split(":")[1].split("(")[0]
                except (IndexError, KeyError):
                    cl_id = None
            attr_list.append({
                "id": a["id"],
                "cl": cl_id,
                "status": a.get("assignmentStatus", ""),
            })

        flows_out[fid] = {
            "name": ' '.join((flow.get("name") or "").split()).strip(),
            "description": ' '.join((flow.get("description") or "").split()).strip()[:300],
            "dsd_id": dsd_id,
            "version": version,
            "dimensions": dim_list,
            "attributes": attr_list,
        }

    # Probe time coverage + series counts (slow — one HTTP call per flow).
    if probe_coverage:
        if verbose:
            print(f"\nProbing time coverage for {len(flows_out)} flows...")
        # Best-effort frequency map (frequencies that actually publish).
        freq_codes = ["Q", "M", "A", "H", "S"]
        for j, (fid, flow) in enumerate(sorted(flows_out.items()), 1):
            if verbose:
                print(f"  [{j}/{len(flows_out)}] {fid}")
            n_dims = len(flow["dimensions"])
            best_count, best_freq = 0, None
            if flow["dimensions"] and flow["dimensions"][0]["id"] == "FREQ":
                for f in freq_codes:
                    wildcard = f + "." * (n_dims - 1)
                    try:
                        avail = check_availability(fid, key=wildcard, timeout=15)
                        c = avail["series_count"]
                        if c > best_count:
                            best_count = c
                            best_freq = f
                    except Exception:
                        continue
            else:
                wildcard = "." * (n_dims - 1)
                try:
                    avail = check_availability(fid, key=wildcard, timeout=15)
                    best_count = avail["series_count"]
                except Exception:
                    pass
            flow["typical_freq"] = best_freq
            flow["series_count"] = best_count

            # Probe time range via a default query
            kwargs = _FLOW_DEFAULTS.get(fid, {})
            if kwargs and best_count > 0:
                try:
                    series = query(fid, start="1900", end="2100",
                                   timeout=30, **kwargs)
                    all_periods = set()
                    for s in series:
                        all_periods.update(s.get("observations", {}).keys())
                    if all_periods:
                        flow["first_period"] = min(all_periods)
                        flow["last_period"] = max(all_periods)
                except Exception:
                    pass

    ontology = {
        "dataflows": flows_out,
        "codelists": all_cls,
        "concepts": all_concepts,
    }

    if write_to:
        compact_json = json.dumps(ontology, separators=(",", ":"), ensure_ascii=True)
        with open(write_to, "r") as f:
            text = f.read()
        match = re.search(r'_BIS_ONTOLOGY_JSON\s*=\s*r"""(.*?)"""', text, re.DOTALL)
        if not match:
            raise RuntimeError(f"Could not locate _BIS_ONTOLOGY_JSON block in {write_to}")
        new_block = f'_BIS_ONTOLOGY_JSON = r"""\n{compact_json}\n"""'
        new_text = text[:match.start()] + new_block + text[match.end():]
        with open(write_to, "w") as f:
            f.write(new_text)
        if verbose:
            print(f"Wrote refreshed ontology to {write_to}")

    return ontology


# ─── Public surface ───────────────────────────────────────────────────────

__all__ = [
    # Constants
    "BASE_URL", "BASE_HOST", "DEFAULT_VERSION", "DATAFLOW_ALIASES",
    # Discovery
    "list_dataflows", "get_dataflow", "get_dimensions", "get_codelist",
    "get_code_hierarchy", "get_attributes", "interpret_attribute",
    "get_concept",
    "search_dataflows", "search_codes", "describe",
    "find_dataflows_with_dim", "find_dataflows_with_code",
    "dimension_cross_reference",
    # Defaults / exemplar query
    "get_default_kwargs", "query_default",
    # Availability
    "check_availability",
    # Query
    "build_key", "query",
    # PRISM ergonomics (DataFrame conversion + multi-flow alignment)
    "series_to_dataframe", "fetch_aligned", "latest",
    # Composite recipes — cross-flow + cross-cutting
    "recipe_contagion", "recipe_shadow_banking_full",
    "recipe_universe_smoke",
    # Composite recipes — LBS (locational, by reporter location)
    "recipe_eurodollar", "recipe_nbfi", "recipe_interbank",
    "recipe_offshore_centers", "recipe_bank_nationality",
    "recipe_currency_breakdown", "recipe_fcy_mismatch",
    "recipe_sector_matrix", "recipe_lbs_exposure_to",
    "recipe_lbs_bilateral", "recipe_usd_funding",
    # Composite recipes — CBS (consolidated, by HQ nationality)
    "recipe_cbs_foreign_claims", "recipe_cbs_exposure_to",
    "recipe_cbs_maturity", "recipe_cbs_guarantor_diff",
    # Composite recipes — GLI (global liquidity indicators)
    "recipe_gli_currency", "recipe_gli_all_currencies",
    # Composite recipes — country-fundamentals
    "recipe_credit_gap_warnings", "recipe_policy_rate_cycle",
    # Refresh
    "refresh_ontology",
]
