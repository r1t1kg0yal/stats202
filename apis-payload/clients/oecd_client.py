"""OECD Data Explorer -- SDMX-REST client.

Sandbox name: ``oecd_client``.

Thin transport over the OECD SDMX 2.1 dissemination service at
``sdmx.oecd.org``. The service spans ~1,500 dataflows across 40+ OECD
directorates (national accounts, prices, labour, STES cycle indicators,
Economic Outlook projections, productivity, house prices, trade, government
accounts, ...). This module handles HTTP, SDMX-CSV parsing, value coercion,
key assembly, a curated catalog of headline macro indicators (including the
Economic Outlook forecast vintages), and friendly alias resolution.

Base URL: ``https://sdmx.oecd.org/public/rest``
Auth: none (anonymous public service).
Transport: Bucket C -- plain ``requests`` (no GS proxy).

The wrapper absorbs the mechanics PRISM should not have to remember:

* The full flowRef grammar (``AGENCY,DSD_x@DF_y`` -- version omitted so every
  call rides the latest dataflow version, which matters because OECD bumps
  versions silently, e.g. each Economic Outlook edition).
* ``format=csvfile`` as a QUERY PARAM instead of an Accept header -- the
  OECD CDN caches responses ignoring Accept, so header-based negotiation can
  return XML no matter what you ask for. The query param is cache-proof.
* Structure queries (dataflow list, DSD dimensions, codelists) are returned
  as SDMX-ML XML regardless of Accept for the same CDN reason -- the wrapper
  parses the XML so callers only ever see dicts and lists.
* SDMX key dimension ORDER per dataflow (from the catalog or live DSD).
* Country aliasing: ISO-2 / common names -> ISO-3 (``US`` -> ``USA``).
* ``OBS_VALUE`` float coercion at the boundary; empty selections -> ``[]``.
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence, Union

import requests


BASE_URL = "https://sdmx.oecd.org/public/rest"
DEFAULT_TIMEOUT = 120

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PRISM-oecd_client/1.0"})

_NUMERIC_COLS = ("OBS_VALUE",)

# SDMX-ML namespaces (structure queries always come back as XML 2.1).
_NS_S = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure}"
_NS_C = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common}"


class OECDError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# --------------------------------------------------------------------------
# Alias maps (friendly token -> SDMX code). PRISM never has to remember codes.
# --------------------------------------------------------------------------

# ISO-2 / common name -> ISO-3 (OECD REF_AREA is ISO-3) or OECD aggregate.
AREA_ALIASES = {
    "OECD": "OECD", "OECD TOTAL": "OECD",
    "EURO AREA": "EA20", "EUROZONE": "EA20", "EA": "EA20",
    "EU": "EU27_2020", "EUROPEAN UNION": "EU27_2020",
    "G7": "G7", "G20": "G20",
    "US": "USA", "USA": "USA", "UNITED STATES": "USA", "AMERICA": "USA",
    "CA": "CAN", "CANADA": "CAN",
    "MX": "MEX", "MEXICO": "MEX",
    "BR": "BRA", "BRAZIL": "BRA",
    "AR": "ARG", "ARGENTINA": "ARG",
    "CL": "CHL", "CHILE": "CHL",
    "CO": "COL", "COLOMBIA": "COL",
    "CR": "CRI", "COSTA RICA": "CRI",
    "GB": "GBR", "UK": "GBR", "UNITED KINGDOM": "GBR", "BRITAIN": "GBR",
    "FR": "FRA", "FRANCE": "FRA",
    "DE": "DEU", "GERMANY": "DEU",
    "IT": "ITA", "ITALY": "ITA",
    "ES": "ESP", "SPAIN": "ESP",
    "PT": "PRT", "PORTUGAL": "PRT",
    "NL": "NLD", "NETHERLANDS": "NLD",
    "BE": "BEL", "BELGIUM": "BEL",
    "AT": "AUT", "AUSTRIA": "AUT",
    "IE": "IRL", "IRELAND": "IRL",
    "GR": "GRC", "GREECE": "GRC",
    "SE": "SWE", "SWEDEN": "SWE",
    "NO": "NOR", "NORWAY": "NOR",
    "DK": "DNK", "DENMARK": "DNK",
    "FI": "FIN", "FINLAND": "FIN",
    "IS": "ISL", "ICELAND": "ISL",
    "CH": "CHE", "SWITZERLAND": "CHE",
    "PL": "POL", "POLAND": "POL",
    "CZ": "CZE", "CZECHIA": "CZE", "CZECH REPUBLIC": "CZE",
    "SK": "SVK", "SLOVAKIA": "SVK",
    "SI": "SVN", "SLOVENIA": "SVN",
    "HU": "HUN", "HUNGARY": "HUN",
    "EE": "EST", "ESTONIA": "EST",
    "LV": "LVA", "LATVIA": "LVA",
    "LT": "LTU", "LITHUANIA": "LTU",
    "LU": "LUX", "LUXEMBOURG": "LUX",
    "TR": "TUR", "TURKEY": "TUR", "TURKIYE": "TUR",
    "IL": "ISR", "ISRAEL": "ISR",
    "RU": "RUS", "RUSSIA": "RUS",
    "CN": "CHN", "CHINA": "CHN",
    "JP": "JPN", "JAPAN": "JPN",
    "KR": "KOR", "SOUTH KOREA": "KOR", "KOREA": "KOR",
    "IN": "IND", "INDIA": "IND",
    "ID": "IDN", "INDONESIA": "IDN",
    "AU": "AUS", "AUSTRALIA": "AUS",
    "NZ": "NZL", "NEW ZEALAND": "NZL",
    "ZA": "ZAF", "SOUTH AFRICA": "ZAF",
    "SA": "SAU", "SAUDI ARABIA": "SAU",
}

SEX_ALIASES = {
    "total": "_T", "t": "_T", "all": "_T",
    "male": "M", "men": "M", "m": "M",
    "female": "F", "women": "F", "f": "F",
}

AGE_ALIASES = {
    "total": "Y_GE15", "15+": "Y_GE15", "all": "Y_GE15",
    "youth": "Y15T24", "15-24": "Y15T24",
    "adult": "Y_GE25", "25+": "Y_GE25",
    "working_age": "Y15T64", "15-64": "Y15T64",
}


# --------------------------------------------------------------------------
# Curated catalog of headline macro indicators.
#   flow     : versionless flowRef "AGENCY,DSD@DF"
#   key      : dot-key template; "{area}" substituted, "{sex}"/"{age}" where
#              the flow carries those dims
#   freq     : native frequency of the headline series
#   desc     : one-line description
# All keys verified live against sdmx.oecd.org on build.
# --------------------------------------------------------------------------

CATALOG: Dict[str, Dict[str, Any]] = {
    # --- prices ---
    "cpi_yoy": {
        "flow": "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL",
        "key": "{area}.M.N.CPI.PA._T.N.GY", "freq": "M",
        "desc": "Headline CPI, % change year-on-year (national index)",
    },
    "cpi_index": {
        "flow": "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL",
        "key": "{area}.M.N.CPI.IX._T.N._Z", "freq": "M",
        "desc": "Headline CPI index level (2015=100)",
    },
    "core_cpi_yoy": {
        "flow": "OECD.SDD.TPS,DSD_PRICES@DF_PRICES_ALL",
        "key": "{area}.M.N.CPI.PA._TXCP01_NRG.N.GY", "freq": "M",
        "desc": "Core CPI (ex food & energy), % change year-on-year",
    },
    # --- activity ---
    "gdp_growth": {
        "flow": "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD",
        "key": "Q.Y.{area}.S1.S1.B1GQ._Z._Z._Z.PC.L.G1.T0102", "freq": "Q",
        "desc": "Real GDP growth, % change on previous quarter (SA)",
    },
    "gdp_growth_yoy": {
        "flow": "OECD.SDD.NAD,DSD_NAMAIN1@DF_QNA_EXPENDITURE_GROWTH_OECD",
        "key": "Q.Y.{area}.S1.S1.B1GQ._Z._Z._Z.PC.L.GY.T0102", "freq": "Q",
        "desc": "Real GDP growth, % change year-on-year (SA)",
    },
    # --- labour ---
    "unemployment_rate": {
        "flow": "OECD.SDD.TPS,DSD_LFS@DF_IALFS_UNE_M",
        "key": "{area}.UNE_LF_M.PT_LF_SUB._Z.Y.{sex}.{age}._Z.M", "freq": "M",
        "dims": {"sex": "_T", "age": "Y_GE15"},
        "desc": "Monthly unemployment rate, % of labour force (SA); "
                "sex=/age= overrides",
    },
    "employment_rate": {
        "flow": "OECD.SDD.TPS,DSD_LFS@DF_IALFS_EMP_WAP_Q",
        "key": "{area}.EMP_WAP.PT_WAP_SUB._Z.Y.{sex}.Y15T64._Z.Q", "freq": "Q",
        "dims": {"sex": "_T"},
        "desc": "Employment rate, % of working-age population 15-64 (SA)",
    },
    # --- cycle (STES) ---
    "cli": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_CLI",
        "key": "{area}.M.LI...AA...H", "freq": "M",
        "desc": "Composite Leading Indicator, amplitude-adjusted (100 = trend)",
    },
    "business_confidence": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_CLI",
        "key": "{area}.M.BCICP...AA...H", "freq": "M",
        "desc": "Business confidence index, amplitude-adjusted (100 = trend)",
    },
    "consumer_confidence": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_CLI",
        "key": "{area}.M.CCICP...AA...H", "freq": "M",
        "desc": "Consumer confidence index, amplitude-adjusted (100 = trend)",
    },
    # --- financial (STES FINMARK) ---
    "long_term_rate": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_FINMARK",
        "key": "{area}.M.IRLT.PA._Z._Z._Z._Z.N", "freq": "M",
        "desc": "Long-term (10y government bond) interest rate, % p.a.",
    },
    "short_term_rate": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_FINMARK",
        "key": "{area}.M.IR3TIB.PA._Z._Z._Z._Z.N", "freq": "M",
        "desc": "Short-term (3-month interbank) interest rate, % p.a.",
    },
    "policy_rate": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_FINMARK",
        "key": "{area}.M.IRSTCI.PA._Z._Z._Z._Z.N", "freq": "M",
        "desc": "Immediate/overnight (policy proxy) interest rate, % p.a.",
    },
    "share_prices": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_FINMARK",
        "key": "{area}.M.SHARE.IX._Z._Z._Z._Z.N", "freq": "M",
        "desc": "Share price index (2015=100)",
    },
    "reer": {
        "flow": "OECD.SDD.STES,DSD_STES@DF_FINMARK",
        "key": "{area}.M.CCRE.IX._Z._Z._Z._Z.N", "freq": "M",
        "desc": "Real effective exchange rate, CPI-based (2015=100)",
    },
    # --- housing ---
    "house_prices_real": {
        "flow": "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES",
        "key": "{area}.Q.RHP.IX", "freq": "Q",
        "desc": "Real house price index (2015=100)",
    },
    "house_prices_nominal": {
        "flow": "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES",
        "key": "{area}.Q.HPI.IX", "freq": "Q",
        "desc": "Nominal house price index (2015=100)",
    },
    "house_price_to_income": {
        "flow": "OECD.ECO.MPD,DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES",
        "key": "{area}.Q.HPI_YDH.IX", "freq": "Q",
        "desc": "House price-to-income ratio (2015=100)",
    },
    # --- productivity ---
    "gdp_per_hour": {
        "flow": "OECD.SDD.TPS,DSD_PDB@DF_PDB",
        "key": "{area}.A.GDPHRS._T.USD_PPP_H.V.N._Z.PPP", "freq": "A",
        "desc": "GDP per hour worked, USD current PPP (level)",
    },
    "gdp_per_hour_growth": {
        "flow": "OECD.SDD.TPS,DSD_PDB@DF_PDB",
        "key": "{area}.A.GDPHRS._T.XDC_H.LR.GY._Z._Z", "freq": "A",
        "desc": "Labour productivity (GDP per hour) growth, % y/y",
    },
    # --- Economic Outlook projections (current edition; includes forecasts) ---
    "eo_gdp_growth": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.GDPV_ANNPCT.A", "freq": "A",
        "desc": "Economic Outlook: real GDP growth %, history + OECD forecast",
    },
    "eo_inflation": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.PCP_YTYPCT.A", "freq": "A",
        "desc": "Economic Outlook: CPI inflation %, history + OECD forecast",
    },
    "eo_unemployment": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.UNR.A", "freq": "A",
        "desc": "Economic Outlook: unemployment rate %, history + forecast",
    },
    "eo_gov_debt": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.GGFLQ.A", "freq": "A",
        "desc": "Economic Outlook: general govt gross debt, % of GDP",
    },
    "eo_fiscal_balance": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.NLGQ.A", "freq": "A",
        "desc": "Economic Outlook: general govt net lending, % of GDP",
    },
    "eo_current_account": {
        "flow": "OECD.ECO.MAD,DSD_EO@DF_EO",
        "key": "{area}.CBGDPR.A", "freq": "A",
        "desc": "Economic Outlook: current account balance, % of GDP",
    },
}


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def _request_csv(path: str, params: Dict[str, Any]) -> str:
    """GET a data path expecting SDMX-CSV. ``format=csvfile`` is forced as a
    query param (the CDN ignores Accept headers). 404 = empty selection."""
    url = f"{BASE_URL}/{path}"
    p = dict(params)
    p["format"] = "csvfile"
    resp = _SESSION.get(url, params=p, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 404:
        return ""
    if resp.status_code >= 400:
        raise OECDError(
            f"OECD API HTTP {resp.status_code} for {url}: {resp.text[:300]}"
        )
    # A well-formed empty result can also arrive as a "NoResultsFound" body.
    if resp.text.strip() == "NoResultsFound":
        return ""
    return resp.text


def _request_xml(path: str, params: Optional[Dict[str, Any]] = None) -> ET.Element:
    """GET a structure path. OECD structure endpoints return SDMX-ML XML
    regardless of Accept (CDN caching quirk), so XML is parsed directly."""
    url = f"{BASE_URL}/{path}"
    resp = _SESSION.get(url, params=params or {}, timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        raise OECDError(
            f"OECD API HTTP {resp.status_code} for {url}: {resp.text[:300]}"
        )
    try:
        return ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise OECDError(f"OECD structure response not parseable: {e}") from e


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
        raise OECDError("at least one area (country/aggregate) is required")
    return "+".join(out)


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

_DATAFLOW_CACHE: Optional[List[Dict[str, str]]] = None
_DIM_CACHE: Dict[str, List[str]] = {}


def list_catalog() -> List[Dict[str, str]]:
    """Return the curated headline-indicator catalog as rows.

    Each row: ``name`` (sandbox key), ``flow``, ``desc``.
    """
    return [
        {"name": k, "flow": v["flow"], "desc": v["desc"]}
        for k, v in CATALOG.items()
    ]


def list_dataflows(search: Optional[str] = None) -> List[Dict[str, str]]:
    """List all OECD dataflows (~1,500) with agency / id / version / name.

    Hits ``/dataflow/all/all/latest`` (XML, cached). ``search`` filters
    case-insensitively on id + name substring. Use the returned ``agency``
    and ``id`` to form a flowRef: ``"<agency>,<id>"``.
    """
    global _DATAFLOW_CACHE
    if _DATAFLOW_CACHE is None:
        root = _request_xml("dataflow/all/all/latest")
        flows = []
        for f in root.iter(_NS_S + "Dataflow"):
            name = f.find(_NS_C + "Name")
            flows.append({
                "agency": f.get("agencyID", ""),
                "id": f.get("id", ""),
                "version": f.get("version", ""),
                "name": name.text if name is not None else "",
            })
        for f in flows:
            f["flow_ref"] = f"{f['agency']},{f['id']}"
        _DATAFLOW_CACHE = flows
    if not search:
        return list(_DATAFLOW_CACHE)
    q = search.lower()
    return [
        f for f in _DATAFLOW_CACHE
        if q in f["id"].lower() or q in (f["name"] or "").lower()
    ]


def _split_flow_ref(flow_ref: str) -> tuple:
    """'AGENCY,FLOW[,VERSION]' -> (agency, flow_id)."""
    parts = str(flow_ref).split(",")
    if len(parts) < 2:
        raise OECDError(
            f"flow_ref must be 'AGENCY,FLOW_ID' (got {flow_ref!r}); "
            "find both via list_dataflows(search=...)"
        )
    return parts[0].strip(), parts[1].strip()


def get_dimensions(flow_ref: str) -> List[str]:
    """Ordered dimension ids for a dataflow's DSD (the SDMX key order).

    Hits ``/dataflow/<agency>/<flow>/latest?references=all`` (XML, cached).
    """
    agency, flow_id = _split_flow_ref(flow_ref)
    cache_key = f"{agency},{flow_id}"
    if cache_key in _DIM_CACHE:
        return list(_DIM_CACHE[cache_key])
    root = _request_xml(
        f"dataflow/{agency}/{flow_id}/latest", {"references": "all"}
    )
    dims: List[str] = []
    for dl in root.iter(_NS_S + "DimensionList"):
        entries = []
        for d in dl:
            if d.tag == _NS_S + "Dimension":
                entries.append((int(d.get("position", "0")), d.get("id")))
        entries.sort()
        dims = [e[1] for e in entries if e[1]]
        break
    if not dims:
        raise OECDError(f"no DSD dimensions found for {flow_ref}")
    _DIM_CACHE[cache_key] = dims
    return list(dims)


def get_codelist(flow_ref: str, dimension: str) -> Dict[str, str]:
    """Return ``{code: name}`` for one dimension of a dataflow.

    Pulls the dataflow with ``references=all`` and extracts the codelist the
    dimension's enumeration points at.
    """
    agency, flow_id = _split_flow_ref(flow_ref)
    root = _request_xml(
        f"dataflow/{agency}/{flow_id}/latest", {"references": "all"}
    )
    cl_id = None
    for d in root.iter(_NS_S + "Dimension"):
        if d.get("id") == dimension:
            ref = d.find(_NS_S + "LocalRepresentation/" + _NS_S
                         + "Enumeration/Ref")
            if ref is not None:
                cl_id = ref.get("id")
            break
    if cl_id is None:
        raise OECDError(f"dimension {dimension!r} not found on {flow_ref}")
    for cl in root.iter(_NS_S + "Codelist"):
        if cl.get("id") == cl_id:
            out = {}
            for code in cl.iter(_NS_S + "Code"):
                name = code.find(_NS_C + "Name")
                out[code.get("id", "")] = name.text if name is not None else ""
            return out
    return {}


# --------------------------------------------------------------------------
# Key assembly + data
# --------------------------------------------------------------------------

def build_key(flow_ref: str, **dims: Union[str, Sequence[str]]) -> str:
    """Assemble a dot-separated SDMX key for ``flow_ref`` from named
    dimensions, in the DSD order. Unspecified dims are wildcarded; list
    values are OR-joined with ``+``.

    Example::

        build_key("OECD.SDD.STES,DSD_STES@DF_CLI", REF_AREA="USA",
                  FREQ="M", MEASURE="LI")
        # -> "USA.M.LI......."
    """
    order = get_dimensions(flow_ref)
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
    flow_ref: str,
    key: str = "all",
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    first_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Fetch observations for a dataflow + SDMX key as parsed rows.

    ``flow_ref`` is ``"AGENCY,FLOW_ID"`` (version omitted = latest; append
    ``,<version>`` to pin). ``key`` is the dot-separated dimension filter
    (see ``build_key``); ``"all"`` returns the whole flow -- ALWAYS bound
    that with ``start``/``last_n``, some flows carry millions of rows.
    ``OBS_VALUE`` is coerced to float. Returns ``[]`` when the selection has
    no data.

    Each row carries the dimension columns + ``TIME_PERIOD`` + ``OBS_VALUE``
    plus attributes (``UNIT_MULT``, ``OBS_STATUS``, ``BASE_PER``, ...).
    """
    params: Dict[str, Any] = {}
    if start:
        params["startPeriod"] = start
    if end:
        params["endPeriod"] = end
    if last_n is not None:
        params["lastNObservations"] = int(last_n)
    if first_n is not None:
        params["firstNObservations"] = int(first_n)
    path = f"data/{flow_ref}/{key or 'all'}"
    return _parse_csv(_request_csv(path, params))


def _resolve_multi(value, aliases: Dict[str, str], default: str) -> str:
    """Resolve a friendly value (or list -> '+'-joined) through an alias
    map; None -> default."""
    if value is None:
        return default
    vals = value if isinstance(value, (list, tuple)) else [value]
    return "+".join(
        aliases.get(str(v).strip().lower(), str(v)) for v in vals
    )


def get_indicator(
    name: str,
    areas: Union[str, Sequence[str]],
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    sex: Union[str, Sequence[str], None] = None,
    age: Union[str, Sequence[str], None] = None,
) -> List[Dict[str, Any]]:
    """Headline accessor: pull a curated catalog indicator for one or more
    areas with verified keys and sensible defaults.

    ``name`` is a catalog key (see ``list_catalog``). ``areas`` accepts
    ISO-3, ISO-2, common names, or aggregates (``"OECD"``, ``"euro area"``,
    ``"G7"``, ``"G20"`` -- availability varies by flow). ``sex`` / ``age``
    apply to the labour indicators only (friendly aliases: ``"female"``,
    ``"youth"``, ...; a LIST fans out both codes in one call, e.g.
    ``age=["youth", "total"]``).

    Economic Outlook rows (``eo_*`` names) carry ``is_forecast`` -- True
    for years beyond the current calendar year (OECD projections).

    Rows are sorted by TIME_PERIOD within each area.
    """
    entry = CATALOG.get(name)
    if entry is None:
        raise OECDError(
            f"unknown indicator {name!r}; see list_catalog() for valid keys"
        )
    area_str = _resolve_areas(areas)
    key = entry["key"]
    subs: Dict[str, str] = {"area": area_str}
    defaults = entry.get("dims", {})
    if "{sex}" in key:
        subs["sex"] = _resolve_multi(sex, SEX_ALIASES,
                                     defaults.get("sex", "_T"))
    elif sex is not None:
        raise OECDError(f"indicator {name!r} has no sex dimension")
    if "{age}" in key:
        subs["age"] = _resolve_multi(age, AGE_ALIASES,
                                     defaults.get("age", "Y_GE15"))
    elif age is not None:
        raise OECDError(f"indicator {name!r} has no age dimension")
    rows = get_data(
        entry["flow"], key.format(**subs),
        start=start, end=end, last_n=last_n,
    )
    if name.startswith("eo_"):
        import datetime
        cy = datetime.date.today().year
        for r in rows:
            try:
                r["is_forecast"] = int(str(r.get("TIME_PERIOD"))) > cy
            except (TypeError, ValueError):
                r["is_forecast"] = False
    rows.sort(key=lambda r: (r.get("REF_AREA", ""), r.get("TIME_PERIOD", "")))
    return rows


def get_panel(
    names: Sequence[str],
    areas: Union[str, Sequence[str]],
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Pull several catalog indicators in one combined long-row set.

    Each row keeps its ``indicator`` (catalog key) so the set pivots
    cleanly: ``to_dataframe(rows, wide=True)`` yields one column per
    (indicator, area) pair. Useful for q/q + y/y GDP, multi-``eo_*``
    forecast frames, headline + core CPI, etc.
    """
    rows: List[Dict[str, Any]] = []
    for name in names:
        for r in get_indicator(name, areas, start=start, end=end,
                               last_n=last_n):
            r["indicator"] = name
            rows.append(r)
    return rows


def to_dataframe(
    rows: List[Dict[str, Any]],
    *,
    wide: bool = False,
    value_col: str = "OBS_VALUE",
):
    """Convert parsed OECD rows to a pandas DataFrame (long or wide).

    Long: trimmed columns (REF_AREA, varying dimensions, TIME_PERIOD, value,
    OBS_STATUS) plus a numeric ``time`` helper. Wide: pivot of ``time``
    (index) x series, one column per series. Column headers use only the
    dimensions that actually VARY across the rows -- a single-indicator
    multi-country panel gets clean ``REF_AREA`` columns.
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("to_dataframe requires pandas") from e

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["time"] = _coerce_time(df.get("TIME_PERIOD"))

    skip = {"DATAFLOW", "TIME_PERIOD", "time", value_col, "OBS_STATUS",
            "UNIT_MULT", "DECIMALS", "BASE_PER", "CONF_STATUS",
            "REF_YEAR_PRICE", "CURRENCY", "is_forecast"}
    dim_cols = [c for c in df.columns if c not in skip]
    key_cols = [c for c in ("indicator", "REF_AREA") if c in df.columns]
    key_cols += [c for c in dim_cols if c not in key_cols]

    if wide:
        varying = [c for c in key_cols if df[c].nunique(dropna=False) > 1]
        header_cols = varying or (key_cols[:1] if key_cols else [])
        if header_cols:
            series_key = df[header_cols].astype(str).agg(" | ".join, axis=1)
        else:
            series_key = pd.Series([value_col] * len(df), index=df.index)
        df = df.assign(_series=series_key)
        pivot = df.pivot_table(
            index="time", columns="_series", values=value_col, aggfunc="first"
        )
        return pivot.sort_index()

    lead = [c for c in ("indicator", "REF_AREA") if c in df.columns]
    keep = [c for c in [*lead,
                        *[c for c in dim_cols
                          if c not in lead
                          and df[c].nunique(dropna=False) > 1],
                        "TIME_PERIOD", "time", value_col, "OBS_STATUS"]
            if c in df.columns]
    out = df[keep].copy()
    sort_cols = [c for c in ["REF_AREA", "time"] if c in out.columns]
    return out.sort_values(sort_cols) if sort_cols else out


def _coerce_time(series):
    """Best-effort sortable numeric from SDMX TIME_PERIOD strings
    ('2024', '2024-03', '2024-Q1')."""
    import pandas as pd
    if series is None:
        return None

    def conv(v: Any):
        s = str(v)
        try:
            if "-Q" in s:
                y, q = s.split("-Q")
                return int(y) + (int(q) - 1) / 4.0
            if "-" in s:
                y, m = s.split("-")[:2]
                return int(y) + (int(m) - 1) / 12.0
            return float(s)
        except (ValueError, TypeError):
            return float("nan")

    return series.map(conv)


__all__ = [
    "BASE_URL",
    "CATALOG",
    "OECDError",
    "AREA_ALIASES",
    "SEX_ALIASES",
    "AGE_ALIASES",
    "list_catalog",
    "list_dataflows",
    "get_dimensions",
    "get_codelist",
    "build_key",
    "get_data",
    "get_indicator",
    "get_panel",
    "to_dataframe",
]
