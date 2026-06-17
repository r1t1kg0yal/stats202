"""ILOSTAT (International Labour Organization) -- SDMX-REST client.

Sandbox name: ``ilo_client``.

Thin transport over the ILOSTAT SDMX 2.1 RESTful dissemination service.
The full code grammar (dataflow-ID structure, dimension keys, classification
codes, country/group codes) lives in ``ilo_guide.md``; this module handles
HTTP, SDMX-CSV parsing, value coercion, key assembly, a curated catalog of
headline macro-labour indicators, and friendly alias resolution.

Base URL: ``https://sdmx.ilo.org/rest``
Auth: none (anonymous public service).
Transport: Bucket C -- plain ``requests`` (no GS proxy).

The wrapper absorbs the mechanics PRISM should not have to remember:

* SDMX key dimension ORDER (REF_AREA.FREQ.MEASURE.<classifications>) -- built
  from the catalog or, for arbitrary dataflows, from the live DSD via
  ``build_key`` / ``get_dimensions``.
* The "total" classification codes (``SEX_T``, ``AGE_YTHADULT_YGE15``,
  ``ECO_AGGREGATE_TOTAL``, ...) so a headline call returns one clean series
  per country.
* Country aliasing: ISO-2 / common names / group names -> ISO-3 / X-codes
  (e.g. ``US`` -> ``USA``, ``World`` -> ``X01``, ``BRICS`` -> ``X85``).
* SDMX-CSV parsing and ``OBS_VALUE`` float coercion at the boundary.
"""

from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Optional, Sequence, Union

import requests


BASE_URL = "https://sdmx.ilo.org/rest"
AGENCY = "ILO"
DEFAULT_TIMEOUT = 90
DEFAULT_VERSION = "latest"

_DATA_ACCEPT = "application/vnd.sdmx.data+csv;version=1.0.0"
_STRUCT_ACCEPT = "application/vnd.sdmx.structure+json;version=1.0"

# ILO blocks some default User-Agents (urllib); requests' default works, but a
# stable explicit UA is cheap insurance.
_SESSION = requests.Session()
_SESSION.headers.update({
    "Accept": _DATA_ACCEPT,
    "User-Agent": "PRISM-ilo_client/1.0",
})

# Numeric SDMX-CSV columns coerced to float at the boundary.
_NUMERIC_COLS = ("OBS_VALUE", "UPPER_BOUND", "LOWER_BOUND")

# Static human labels for the common classification codes the catalog uses, so
# PRISM can render breakdowns without a structural-metadata round-trip. Unknown
# codes are returned unchanged by ``code_label``; use ``get_codelist`` for the
# full picture.
_CODE_LABELS = {
    "SEX_T": "Total", "SEX_M": "Male", "SEX_F": "Female", "SEX_O": "Other",
    "AGE_YTHADULT_YGE15": "15+", "AGE_YTHADULT_Y15-24": "Youth (15-24)",
    "AGE_YTHADULT_YGE25": "Adult (25+)", "AGE_YTHADULT_Y15-64": "15-64",
    "AGE_AGGREGATE_YGE15": "15+", "AGE_AGGREGATE_Y25-54": "Prime (25-54)",
    "ECO_AGGREGATE_AGR": "Agriculture",
    "ECO_AGGREGATE_MAN": "Manufacturing",
    "ECO_AGGREGATE_CON": "Construction",
    "ECO_AGGREGATE_MEL": "Mining, utilities & extraction",
    "ECO_AGGREGATE_MKT": "Market services",
    "ECO_AGGREGATE_PUB": "Non-market (public) services",
    "ECO_AGGREGATE_TOTAL": "Total economy",
    "STE_AGGREGATE_EES": "Employees",
    "STE_AGGREGATE_SLF": "Self-employed",
    "STE_AGGREGATE_TOTAL": "Total",
    "CUR_TYPE_LCU": "Local currency", "CUR_TYPE_PPP": "PPP $",
    "CUR_TYPE_USD": "US$", "CUR_NATL_CURRENT": "LCU per US$",
    "AGE_CLDVERSION_Y05-17": "Children (5-17)", "AGE_CLDVERSION_Y05-11": "5-11",
    "AGE_CLDVERSION_Y12-14": "12-14", "AGE_CLDVERSION_Y15-17": "15-17",
    "MIG_STATUS_TOTAL": "Total", "MIG_STATUS_MIGRANT": "Migrants",
    "MIG_STATUS_NONMIG": "Non-migrants",
}


class ILOError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# --------------------------------------------------------------------------
# Alias maps (friendly token -> SDMX code). PRISM never has to remember codes.
# --------------------------------------------------------------------------

SEX_ALIASES = {
    "total": "SEX_T", "t": "SEX_T", "all": "SEX_T",
    "male": "SEX_M", "men": "SEX_M", "m": "SEX_M",
    "female": "SEX_F", "women": "SEX_F", "f": "SEX_F",
}

AGE_ALIASES = {
    "total": "AGE_YTHADULT_YGE15", "15+": "AGE_YTHADULT_YGE15",
    "all": "AGE_YTHADULT_YGE15", " yge15": "AGE_YTHADULT_YGE15",
    "youth": "AGE_YTHADULT_Y15-24", "15-24": "AGE_YTHADULT_Y15-24",
    "adult": "AGE_YTHADULT_YGE25", "25+": "AGE_YTHADULT_YGE25",
    "working_age": "AGE_YTHADULT_Y15-64", "15-64": "AGE_YTHADULT_Y15-64",
    "prime": "AGE_AGGREGATE_Y25-54", "25-54": "AGE_AGGREGATE_Y25-54",
}

CURRENCY_ALIASES = {
    "ppp": "CUR_TYPE_PPP", "lcu": "CUR_TYPE_LCU", "local": "CUR_TYPE_LCU",
    "usd": "CUR_TYPE_USD", "us$": "CUR_TYPE_USD",
}

# ISO-2 / common name / group -> ISO-3 or ILO X-group code. Covers the
# economies PRISM actually queries; full universe via get_areas().
AREA_ALIASES = {
    # groups (validated)
    "WORLD": "X01", "GLOBAL": "X01",
    "BRICS": "X85",
    # G20 / major economies, ISO-2 and names -> ISO-3
    "US": "USA", "USA": "USA", "UNITED STATES": "USA", "AMERICA": "USA",
    "CA": "CAN", "CANADA": "CAN",
    "MX": "MEX", "MEXICO": "MEX",
    "BR": "BRA", "BRAZIL": "BRA",
    "AR": "ARG", "ARGENTINA": "ARG",
    "GB": "GBR", "UK": "GBR", "UNITED KINGDOM": "GBR", "BRITAIN": "GBR",
    "FR": "FRA", "FRANCE": "FRA",
    "DE": "DEU", "GERMANY": "DEU",
    "IT": "ITA", "ITALY": "ITA",
    "ES": "ESP", "SPAIN": "ESP",
    "NL": "NLD", "NETHERLANDS": "NLD",
    "SE": "SWE", "SWEDEN": "SWE",
    "CH": "CHE", "SWITZERLAND": "CHE",
    "RU": "RUS", "RUSSIA": "RUS",
    "TR": "TUR", "TURKEY": "TUR", "TURKIYE": "TUR",
    "CN": "CHN", "CHINA": "CHN",
    "JP": "JPN", "JAPAN": "JPN",
    "KR": "KOR", "SOUTH KOREA": "KOR", "KOREA": "KOR",
    "IN": "IND", "INDIA": "IND",
    "ID": "IDN", "INDONESIA": "IDN",
    "AU": "AUS", "AUSTRALIA": "AUS",
    "ZA": "ZAF", "SOUTH AFRICA": "ZAF",
    "SA": "SAU", "SAUDI ARABIA": "SAU",
    "NG": "NGA", "NIGERIA": "NGA",
    "EG": "EGY", "EGYPT": "EGY",
}


# --------------------------------------------------------------------------
# Curated catalog of headline macro-labour indicators.
#   dataflow : SDMX dataflow id (DF_<DSD_ID>)
#   dims     : ordered classification dimension ids AFTER REF_AREA.FREQ.MEASURE
#   defaults : total/headline code per classification dim (gives one clean
#              series per country); override via get_indicator(sex=, age=, ...)
#   freq     : the frequency the source publishes ("A" annual; reported flows
#              may also have "M"/"Q" for some countries)
#   desc     : one-line description
# Verified live against https://sdmx.ilo.org/rest on build.
# --------------------------------------------------------------------------

CATALOG: Dict[str, Dict[str, Any]] = {
    # --- unemployment ---
    "unemployment_rate": {
        "dataflow": "DF_UNE_DEAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Unemployment rate, % of labour force (reported; some countries M/Q)",
    },
    "unemployment_rate_modelled": {
        "dataflow": "DF_UNE_2EAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Unemployment rate, ILO modelled estimate (harmonized, all countries)",
    },
    "unemployment": {
        "dataflow": "DF_UNE_TUNE_SEX_AGE_NB", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Number of unemployed persons (thousands)",
    },
    # --- employment ---
    "employment_ratio": {
        "dataflow": "DF_EMP_DWAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Employment-to-population ratio, % (reported)",
    },
    "employment_ratio_modelled": {
        "dataflow": "DF_EMP_2WAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Employment-to-population ratio, ILO modelled estimate",
    },
    "employment": {
        "dataflow": "DF_EMP_TEMP_SEX_AGE_NB", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Number of employed persons (thousands)",
    },
    "employment_by_sector": {
        "dataflow": "DF_EMP_TEMP_SEX_ECO_NB", "dims": ["SEX", "ECO"],
        # Clean MECE 6-sector aggregate (no total, no ISIC detail). Pass
        # ECO="ECO_AGGREGATE_TOTAL" for total economy or ECO=None to wildcard
        # all classification versions.
        "defaults": {
            "SEX": "SEX_T",
            "ECO": ["ECO_AGGREGATE_AGR", "ECO_AGGREGATE_MAN",
                    "ECO_AGGREGATE_CON", "ECO_AGGREGATE_MEL",
                    "ECO_AGGREGATE_MKT", "ECO_AGGREGATE_PUB"],
        }, "freq": "A",
        "desc": "Employment by economic activity (6 aggregate sectors; "
                "ECO=ECO_AGGREGATE_TOTAL for total economy)",
    },
    "employment_by_status": {
        "dataflow": "DF_EMP_TEMP_SEX_STE_NB", "dims": ["SEX", "STE"],
        # Employee vs self-employed split (no total). STE=STE_AGGREGATE_TOTAL
        # for total; STE=None to wildcard detailed ICSE classes.
        "defaults": {
            "SEX": "SEX_T",
            "STE": ["STE_AGGREGATE_EES", "STE_AGGREGATE_SLF"],
        }, "freq": "A",
        "desc": "Employment by status (employees vs self-employed split)",
    },
    "employees": {
        "dataflow": "DF_EES_TEES_SEX_AGE_NB", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Number of employees (thousands)",
    },
    # --- labour force / participation ---
    "labour_force_participation": {
        "dataflow": "DF_EAP_DWAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Labour force participation rate, % (reported)",
    },
    "labour_force_participation_modelled": {
        "dataflow": "DF_EAP_2WAP_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Labour force participation rate, ILO modelled estimate",
    },
    "labour_force": {
        "dataflow": "DF_EAP_TEAP_SEX_AGE_NB", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Labour force (economically active population, thousands)",
    },
    "working_age_population": {
        "dataflow": "DF_POP_XWAP_SEX_AGE_NB", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Working-age population (thousands)",
    },
    # --- underutilization / informality / NEET / poverty ---
    "time_related_underemployment_rate": {
        "dataflow": "DF_EMP_2TRU_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Time-related underemployment rate, ILO modelled estimate",
    },
    "labour_underutilization_lu4": {
        "dataflow": "DF_LUU_2LU4_SEX_RT", "dims": ["SEX"],
        "defaults": {"SEX": "SEX_T"}, "freq": "A",
        "desc": "Composite labour underutilization rate (LU4), modelled",
    },
    "combined_underutilization_lu2": {
        "dataflow": "DF_LUU_2LU2_SEX_RT", "dims": ["SEX"],
        "defaults": {"SEX": "SEX_T"}, "freq": "A",
        "desc": "Combined underemployment + unemployment rate (LU2), modelled",
    },
    "informal_employment_rate": {
        "dataflow": "DF_EMP_2IFL_SEX_RT", "dims": ["SEX"],
        "defaults": {"SEX": "SEX_T"}, "freq": "A",
        "desc": "Informal employment rate, % of employment (modelled)",
    },
    "neet_rate": {
        "dataflow": "DF_EIP_NEET_SEX_RT", "dims": ["SEX"],
        "defaults": {"SEX": "SEX_T"}, "freq": "A",
        "desc": "Youth not in employment, education or training (NEET), %",
    },
    "working_poverty_rate": {
        "dataflow": "DF_SDG_0111_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"}, "freq": "A",
        "desc": "Working poverty rate, % of employed below US$3 PPP (SDG 1.1.1)",
    },
    "child_labour_rate": {
        "dataflow": "DF_CLD_XCHL_SEX_AGE_RT", "dims": ["SEX", "AGE"],
        # Child-labour AGE codes are their own classification (5-17 total,
        # plus 5-11 / 12-14 / 15-17 bands) -- NOT the 15+ adult totals.
        "defaults": {"SEX": "SEX_T", "AGE": "AGE_CLDVERSION_Y05-17"}, "freq": "A",
        "desc": "Children in child labour, % of children 5-17 "
                "(AGE=AGE_CLDVERSION_Y05-11/Y12-14/Y15-17 for bands)",
    },
    # --- industrial relations / job quality ---
    "union_density": {
        "dataflow": "DF_ILR_TUMT_NOC_RT", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Trade union density rate, % of employees",
    },
    "collective_bargaining_coverage": {
        "dataflow": "DF_ILR_CBCT_NOC_RT", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Collective bargaining coverage rate, % of employees",
    },
    "fatal_injuries_rate": {
        "dataflow": "DF_INJ_FATL_SEX_MIG_RT", "dims": ["SEX", "MIG"],
        "defaults": {"SEX": "SEX_T", "MIG": "MIG_STATUS_TOTAL"}, "freq": "A",
        "desc": "Fatal occupational injuries per 100,000 workers (SDG 8.8.1)",
    },
    # --- earnings / hours ---
    "mean_monthly_earnings": {
        "dataflow": "DF_EAR_EMTA_SEX_CUR_NB", "dims": ["SEX", "CUR"],
        "defaults": {"SEX": "SEX_T", "CUR": "CUR_TYPE_PPP"}, "freq": "A",
        "desc": "Mean nominal monthly earnings of employees (currency=PPP|LCU|USD)",
    },
    "mean_hourly_earnings": {
        "dataflow": "DF_EAR_EHRA_SEX_CUR_NB", "dims": ["SEX", "CUR"],
        "defaults": {"SEX": "SEX_T", "CUR": "CUR_TYPE_PPP"}, "freq": "A",
        "desc": "Mean nominal hourly earnings of employees (currency=PPP|LCU|USD)",
    },
    "mean_weekly_hours": {
        "dataflow": "DF_HOW_TEMP_SEX_ECO_NB", "dims": ["SEX", "ECO"],
        "defaults": {"SEX": "SEX_T", "ECO": "ECO_AGGREGATE_TOTAL"}, "freq": "A",
        "desc": "Mean weekly hours actually worked per employed person (total economy)",
    },
    # --- productivity / income share (modelled, no classifications) ---
    "labour_income_share": {
        "dataflow": "DF_LAP_2GDP_NOC_RT", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Labour income share as % of GDP, modelled (SDG 10.4.1)",
    },
    "output_per_worker": {
        "dataflow": "DF_GDP_211P_NOC_NB", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Output per worker, GDP constant 2021 international $ at PPP",
    },
    "output_per_hour": {
        "dataflow": "DF_GDP_2HRW_NOC_NB", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Output per hour worked, GDP constant 2021 international $ at PPP",
    },
    "gdp_ppp": {
        "dataflow": "DF_GDP_2TOT_NOC_NB", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "GDP (millions, constant 2021 international $ at PPP), modelled",
    },
    "gender_income_gap": {
        "dataflow": "DF_LAP_2FTM_NOC_RT", "dims": [],
        "defaults": {}, "freq": "A",
        "desc": "Gender income gap: ratio of women's to men's labour income, modelled",
    },
    # --- prices / FX ---
    "cpi": {
        "dataflow": "DF_CPI_XCPI_COI_RT", "dims": ["COI"],
        "defaults": {"COI": "COI_COICOP_CP01T12"}, "freq": "M",
        "desc": "Consumer price index, all items (2017=100); FREQ M or A",
    },
    "cpi_yoy": {
        "dataflow": "DF_CPI_NCYR_COI_RT", "dims": ["COI"],
        "defaults": {"COI": "COI_COICOP_CP01T12"}, "freq": "M",
        "desc": "CPI, all items, % change from previous year",
    },
    "exchange_rate": {
        "dataflow": "DF_CCF_XOXR_CUR_RT", "dims": ["CUR"],
        "defaults": {"CUR": "CUR_NATL_CURRENT"}, "freq": "A",
        "desc": "Official exchange rate, local currency units per US dollar",
    },
}


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def _flow_ref(dataflow: str, version: Optional[str]) -> str:
    """Assemble the SDMX flowRef. The data endpoint rejects the literal
    ``latest`` token, so for the default/latest case the version component is
    omitted entirely (``ILO,DF_xxx``); a pinned version is appended as
    ``ILO,DF_xxx,1.0``."""
    flow = dataflow if dataflow.upper().startswith("DF_") else f"DF_{dataflow}"
    v = version if version is not None else DEFAULT_VERSION
    if v in (None, "", "latest"):
        return f"{AGENCY},{flow}"
    return f"{AGENCY},{flow},{v}"


def _dsd_id(dataflow: str) -> str:
    """The DSD id is the dataflow id without the DF_ prefix."""
    flow = dataflow.upper()
    return flow[3:] if flow.startswith("DF_") else flow


def _request_csv(path: str, params: Dict[str, Any]) -> str:
    url = f"{BASE_URL}/{path}"
    resp = _SESSION.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    # SDMX returns 404 when a selection matches no data -- a clean empty,
    # not an error.
    if resp.status_code == 404:
        return ""
    if resp.status_code >= 400:
        raise ILOError(
            f"ILO API HTTP {resp.status_code} for {url}: {resp.text[:300]}"
        )
    return resp.text


def _request_json(path: str, params: Dict[str, Any]) -> Any:
    url = f"{BASE_URL}/{path}"
    resp = _SESSION.get(
        url, params=params, timeout=DEFAULT_TIMEOUT,
        headers={"Accept": _STRUCT_ACCEPT},
    )
    if resp.status_code >= 400:
        raise ILOError(
            f"ILO API HTTP {resp.status_code} for {url}: {resp.text[:300]}"
        )
    try:
        return resp.json()
    except ValueError as e:
        raise ILOError(f"ILO API returned non-JSON: {resp.text[:200]}") from e


def _parse_csv(text: str) -> List[Dict[str, Any]]:
    if not text or not text.strip():
        return []
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for raw in reader:
        row = dict(raw)
        for col in _NUMERIC_COLS:
            v = row.get(col)
            if v not in (None, ""):
                try:
                    row[col] = float(v)
                except (TypeError, ValueError):
                    pass
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Alias resolution
# --------------------------------------------------------------------------

def _resolve_area(area: str) -> str:
    up = str(area).strip().upper()
    return AREA_ALIASES.get(up, up)


def _resolve_areas(areas: Union[str, Sequence[str]]) -> str:
    if isinstance(areas, str):
        areas = [areas]
    out = [_resolve_area(a) for a in areas if str(a).strip()]
    if not out:
        raise ILOError("at least one area (country/group) is required")
    return "+".join(out)


def _resolve_code(value: str, aliases: Dict[str, str]) -> str:
    return aliases.get(str(value).strip().lower(), str(value))


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

_DATAFLOW_CACHE: Optional[List[Dict[str, str]]] = None
_DIM_CACHE: Dict[str, List[str]] = {}


def list_catalog() -> List[Dict[str, str]]:
    """Return the curated headline-indicator catalog as rows.

    Each row: ``name`` (sandbox key), ``dataflow``, ``desc``.
    """
    return [
        {"name": k, "dataflow": v["dataflow"], "desc": v["desc"]}
        for k, v in CATALOG.items()
    ]


def list_dataflows(search: Optional[str] = None) -> List[Dict[str, str]]:
    """List ILOSTAT dataflows (indicators) with data available.

    Hits ``/dataflow/ILO?detail=allstubs`` (cached). ``search`` filters
    case-insensitively on id + name substring. ~1,200 dataflows total.
    """
    global _DATAFLOW_CACHE
    if _DATAFLOW_CACHE is None:
        data = _request_json("dataflow/ILO", {"detail": "allstubs"})
        flows = data.get("data", {}).get("dataflows", [])
        _DATAFLOW_CACHE = [
            {"id": f.get("id", ""), "name": f.get("name", "")} for f in flows
        ]
    if not search:
        return list(_DATAFLOW_CACHE)
    q = search.lower()
    return [
        f for f in _DATAFLOW_CACHE
        if q in f["id"].lower() or q in (f["name"] or "").lower()
    ]


def get_dimensions(dataflow: str) -> List[str]:
    """Ordered dimension ids for a dataflow's DSD (REF_AREA, FREQ, MEASURE,
    then classifications). Hits ``/datastructure/ILO/<DSD>`` (cached).
    """
    dsd = _dsd_id(dataflow)
    if dsd in _DIM_CACHE:
        return list(_DIM_CACHE[dsd])
    data = _request_json(f"datastructure/{AGENCY}/{dsd}", {"references": "none"})
    structs = data.get("data", {}).get("dataStructures", [])
    if not structs:
        raise ILOError(f"no DSD found for {dataflow}")
    dims = [
        d["id"]
        for d in structs[0]["dataStructureComponents"]["dimensionList"]["dimensions"]
    ]
    _DIM_CACHE[dsd] = dims
    return list(dims)


def get_codelist(codelist_id: str) -> Dict[str, str]:
    """Return a codelist as ``{code: name}``.

    e.g. ``get_codelist("CL_AREA")`` (countries + groups),
    ``get_codelist("CL_SEX")``, ``get_codelist("CL_ECO_AGGREGATE")``.
    """
    cl = codelist_id if codelist_id.upper().startswith("CL_") else f"CL_{codelist_id}"
    data = _request_json(f"codelist/{AGENCY}/{cl}", {})
    cls = data.get("data", {}).get("codelists", [])
    if not cls:
        return {}
    return {c.get("id", ""): c.get("name", "") for c in cls[0].get("codes", [])}


def get_areas(groups_only: bool = False) -> Dict[str, str]:
    """Country + group reference-area codes (``CL_AREA``).

    Countries are ISO-3; groups (World, regions, income levels, BRICS, G20,
    ...) use ``X##`` codes. ``groups_only`` keeps just the X-codes.
    """
    areas = get_codelist("CL_AREA")
    if groups_only:
        return {k: v for k, v in areas.items() if k.startswith("X")}
    return areas


# --------------------------------------------------------------------------
# Key assembly + data
# --------------------------------------------------------------------------

def build_key(dataflow: str, **dims: Union[str, Sequence[str]]) -> str:
    """Assemble a dot-separated SDMX key for ``dataflow`` from named
    dimensions, in the DSD order. Unspecified dims are wildcarded; list
    values are OR-joined with ``+``.

    Example::

        build_key("DF_UNE_DEAP_SEX_AGE_RT", REF_AREA="USA", FREQ="A",
                  SEX="SEX_T")
        # -> "USA.A..SEX_T."
    """
    order = get_dimensions(dataflow)
    parts: List[str] = []
    for d in order:
        v = dims.get(d)
        if v is None:
            parts.append("")
        elif isinstance(v, (list, tuple)):
            parts.append("+".join(str(x) for x in v))
        else:
            parts.append(str(v))
    return ".".join(parts)


def get_data(
    dataflow: str,
    key: str = "",
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    first_n: Optional[int] = None,
    detail: Optional[str] = None,
    version: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Fetch observations for a dataflow + SDMX key as parsed rows.

    ``key`` is the dot-separated dimension filter (see ``build_key``); empty
    key returns the whole dataflow (bound it with ``start`` / ``last_n``).
    ``OBS_VALUE`` is coerced to float. Returns ``[]`` when the selection has
    no data (SDMX 404).

    Each row carries the dimension columns + ``TIME_PERIOD`` + ``OBS_VALUE``
    plus attributes (``UNIT_MEASURE``, ``OBS_STATUS``, ``SOURCE``, notes).
    """
    flow_ref = _flow_ref(dataflow, version)
    path = f"data/{flow_ref}/{key}"
    params: Dict[str, Any] = {"format": "csv"}
    if start:
        params["startPeriod"] = start
    if end:
        params["endPeriod"] = end
    if last_n is not None:
        params["lastNObservations"] = int(last_n)
    if first_n is not None:
        params["firstNObservations"] = int(first_n)
    if detail:
        params["detail"] = detail
    return _parse_csv(_request_csv(path, params))


def get_indicator(
    name: str,
    areas: Union[str, Sequence[str]],
    *,
    freq: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    sex: Optional[str] = None,
    age: Optional[str] = None,
    currency: Optional[str] = None,
    version: Optional[str] = None,
    **classif_overrides: Union[str, Sequence[str]],
) -> List[Dict[str, Any]]:
    """Headline accessor: pull a curated catalog indicator for one or more
    countries with sensible total-classification defaults.

    ``name`` is a catalog key (see ``list_catalog``). ``areas`` accepts
    ISO-3, ISO-2, common names, or group names (``World``, ``BRICS``).
    ``sex`` / ``age`` / ``currency`` take friendly aliases
    (``"female"``, ``"youth"``, ``"ppp"``). Raw classification codes can be
    passed as keyword overrides (e.g. ``ECO="ECO_AGGREGATE_MAN"``).

    Returns one clean series per country for the default totals; pass a
    breakdown code (or omit a default via ``ECO=None``) to fan out.
    """
    entry = CATALOG.get(name)
    if entry is None:
        raise ILOError(
            f"unknown indicator {name!r}; see list_catalog() for valid keys"
        )
    dims = entry["dims"]
    chosen = dict(entry["defaults"])

    if sex is not None and "SEX" in dims:
        chosen["SEX"] = _resolve_code(sex, SEX_ALIASES)
    if age is not None and "AGE" in dims:
        chosen["AGE"] = _resolve_code(age, AGE_ALIASES)
    if currency is not None and "CUR" in dims:
        chosen["CUR"] = _resolve_code(currency, CURRENCY_ALIASES)
    for dim, code in classif_overrides.items():
        chosen[dim] = code  # raw override; None wildcards

    freq_code = freq or entry.get("freq", "A")
    area_str = _resolve_areas(areas)

    # REF_AREA . FREQ . MEASURE(wild) . <classifications...>
    parts: List[str] = [area_str, freq_code, ""]
    for d in dims:
        v = chosen.get(d)
        if v is None or (isinstance(v, str) and not v):
            parts.append("")
        elif isinstance(v, (list, tuple)):
            parts.append("+".join(str(x) for x in v))
        else:
            parts.append(str(v))
    key = ".".join(parts)

    return get_data(
        entry["dataflow"], key,
        start=start, end=end, last_n=last_n, version=version,
    )


def code_label(code: str) -> str:
    """Human label for a classification code (e.g. ``"ECO_AGGREGATE_AGR"`` ->
    ``"Agriculture"``). Unknown codes are returned unchanged. Use with
    ``df["ECO"].map(ilo_client.code_label)`` or ``get_codelist`` for full
    codelists."""
    return _CODE_LABELS.get(code, code)


def mark_forecasts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Add an ``is_forecast`` bool to each row (in place).

    On ILO modelled series the actual years carry ``OBS_STATUS == "R"`` and
    the forward projection years are blank; reported series have no ``"R"``.
    A row is flagged a forecast when its ``OBS_STATUS`` is blank AND its
    series (same REF_AREA + classifications) contains at least one ``"R"``
    observation. Reported-only series are never flagged.
    """
    classif = ("SEX", "AGE", "ECO", "STE", "OCU", "CUR", "COI", "MIG")
    modelled_series = set()
    for r in rows:
        if r.get("OBS_STATUS") == "R":
            modelled_series.add(
                (r.get("REF_AREA"), *(r.get(c) for c in classif))
            )
    for r in rows:
        skey = (r.get("REF_AREA"), *(r.get(c) for c in classif))
        r["is_forecast"] = (
            skey in modelled_series and not (r.get("OBS_STATUS") or "").strip()
        )
    return rows


def to_dataframe(
    rows: List[Dict[str, Any]],
    *,
    wide: bool = False,
    value_col: str = "OBS_VALUE",
    label: bool = False,
):
    """Convert parsed ILO rows to a pandas DataFrame (long or wide).

    Long: trimmed columns (REF_AREA, classifications, TIME_PERIOD, value,
    UNIT_MEASURE, SOURCE) plus a numeric ``time`` helper. Wide: pivot of
    ``time`` (index) x series, one column per series. Column labels use only
    the classification dimensions that actually VARY across the rows -- a
    single-indicator multi-country panel gets clean ``REF_AREA`` columns.

    ``label=True`` adds ``<DIM>_label`` columns (human names via
    ``code_label``) and uses those labels for wide-column headers.
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("to_dataframe requires pandas") from e

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["time"] = _coerce_time(df.get("TIME_PERIOD"))

    classif_cols = [
        c for c in ("SEX", "AGE", "ECO", "STE", "OCU", "CUR", "COI", "MIG")
        if c in df.columns
    ]
    key_cols = [c for c in ["REF_AREA", *classif_cols] if c in df.columns]

    if label:
        for c in classif_cols:
            df[f"{c}_label"] = df[c].map(code_label)

    if wide:
        # Only the dimensions that distinguish series belong in the header.
        varying = [c for c in key_cols if df[c].nunique(dropna=False) > 1]
        header_cols = varying or (key_cols[:1] if key_cols else [])
        if label:
            header_cols = [
                f"{c}_label" if f"{c}_label" in df.columns else c
                for c in header_cols
            ]
        if header_cols:
            series_key = df[header_cols].astype(str).agg(" | ".join, axis=1)
        else:
            series_key = pd.Series([value_col] * len(df), index=df.index)
        df = df.assign(_series=series_key)
        pivot = df.pivot_table(
            index="time", columns="_series", values=value_col, aggfunc="first"
        )
        return pivot.sort_index()

    label_cols = [f"{c}_label" for c in classif_cols if label]
    cols = [
        c for c in [*key_cols, *label_cols, "TIME_PERIOD", "time", value_col,
                    "UNIT_MEASURE", "OBS_STATUS", "SOURCE"]
        if c in df.columns
    ]
    out = df[cols].copy()
    return out.sort_values([c for c in key_cols + ["time"] if c in out.columns])


def _coerce_time(series):
    """Best-effort sortable numeric/period from SDMX TIME_PERIOD strings
    ('2024', '2024-M03', '2024-Q1')."""
    import pandas as pd
    if series is None:
        return None

    def conv(v: Any):
        s = str(v)
        try:
            if "-M" in s:
                y, m = s.split("-M")
                return int(y) + (int(m) - 1) / 12.0
            if "-Q" in s:
                y, q = s.split("-Q")
                return int(y) + (int(q) - 1) / 4.0
            return float(s)
        except (ValueError, TypeError):
            return float("nan")

    return series.map(conv)


__all__ = [
    "BASE_URL",
    "CATALOG",
    "ILOError",
    "SEX_ALIASES",
    "AGE_ALIASES",
    "CURRENCY_ALIASES",
    "AREA_ALIASES",
    "list_catalog",
    "list_dataflows",
    "get_dimensions",
    "get_codelist",
    "get_areas",
    "build_key",
    "get_data",
    "get_indicator",
    "to_dataframe",
    "code_label",
    "mark_forecasts",
]
