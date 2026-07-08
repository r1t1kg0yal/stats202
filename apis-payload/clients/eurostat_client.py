"""Eurostat -- EU statistical office dissemination API client.

Sandbox name: ``eurostat_client``.

Thin transport over Eurostat's ``statistics/1.0`` JSON-stat dissemination
API (data) plus the catalogue TOC (discovery). ~7,000 datasets covering EU
member states + aggregates: HICP inflation, national accounts, labour,
government finance (EDP debt/deficit), short-term business statistics,
energy prices, demography, balance of payments.

Base URL: ``https://ec.europa.eu/eurostat/api/dissemination``
Auth: none (anonymous public service).
Transport: Bucket C -- plain ``requests`` (no GS proxy).

The wrapper absorbs the mechanics PRISM should not have to remember:

* JSON-stat 2.0 decoding -- the API returns values as a sparse
  ``{linear_index: value}`` map over a row-major dimension hypercube; the
  wrapper unrolls that into tidy rows with one column per dimension (code
  AND human label).
* Dimension filters are NAMED query params (``coicop=CP00&geo=DE``) -- no
  positional SDMX key, no dimension order to remember.
* Geo aliasing: common names / ISO-2 -> Eurostat codes (``Greece`` -> ``EL``,
  not ``GR``), plus the per-dataset euro-area aggregate quirk (``EA`` vs
  ``EA20`` vs ``EA21``) resolved from the catalog entry.
* Value coercion to float; missing observations dropped.
* The current-account routing quirk: country-level CA lives in ``bop_c6_q``
  while EA/EU aggregates live in ``bop_eu6_q`` -- ``get_indicator`` routes
  automatically.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import requests


BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination"
DATA_URL = f"{BASE_URL}/statistics/1.0/data"
TOC_URL = f"{BASE_URL}/catalogue/toc/txt"
CONSTRAINT_URL = f"{BASE_URL}/sdmx/2.1/contentconstraint/ESTAT"
DEFAULT_TIMEOUT = 120

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PRISM-eurostat_client/1.0"})


class EurostatError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# --------------------------------------------------------------------------
# Geo aliasing. Eurostat uses ISO-2 codes with two exceptions (EL = Greece,
# UK = United Kingdom) plus aggregate codes. Names resolved case-insensitively.
# --------------------------------------------------------------------------

GEO_ALIASES = {
    "EURO AREA": "EA20", "EUROZONE": "EA20",
    "EU": "EU27_2020", "EUROPEAN UNION": "EU27_2020",
    "AUSTRIA": "AT", "BELGIUM": "BE", "BULGARIA": "BG", "CROATIA": "HR",
    "CYPRUS": "CY", "CZECHIA": "CZ", "CZECH REPUBLIC": "CZ",
    "DENMARK": "DK", "ESTONIA": "EE", "FINLAND": "FI", "FRANCE": "FR",
    "GERMANY": "DE", "GREECE": "EL", "GR": "EL", "HUNGARY": "HU",
    "ICELAND": "IS", "IRELAND": "IE", "ITALY": "IT", "LATVIA": "LV",
    "LITHUANIA": "LT", "LUXEMBOURG": "LU", "MALTA": "MT",
    "NETHERLANDS": "NL", "NORWAY": "NO", "POLAND": "PL", "PORTUGAL": "PT",
    "ROMANIA": "RO", "SLOVAKIA": "SK", "SLOVENIA": "SI", "SPAIN": "ES",
    "SWEDEN": "SE", "SWITZERLAND": "CH",
    "TURKEY": "TR", "TURKIYE": "TR",
    "UNITED KINGDOM": "UK", "BRITAIN": "UK", "GB": "UK",
    "UNITED STATES": "US", "USA": "US", "JAPAN": "JP",
}

# Euro-area aggregate code differs by dataset family; catalog entries carry
# the right one via "ea". Raw get_data callers pass exact codes themselves.
_EA_TOKENS = {"EA20", "EA21", "EA", "EA19", "EUROZONE", "EURO AREA"}


# --------------------------------------------------------------------------
# Curated catalog of headline indicators.
#   dataset  : Eurostat dataset code
#   filters  : named dimension filters that pin ONE clean series per geo
#   ea       : the euro-area aggregate code THIS dataset uses (None = no
#              euro-area series in the dataset)
#   freq     : native frequency
#   desc     : one-line description
# All filter combos verified live on build.
# --------------------------------------------------------------------------

CATALOG: Dict[str, Dict[str, Any]] = {
    # --- prices ---
    "hicp_yoy": {
        "dataset": "prc_hicp_manr",
        "filters": {"coicop": "CP00", "unit": "RCH_A"},
        "ea": "EA", "freq": "M",
        "desc": "HICP all-items inflation, % change year-on-year",
    },
    "hicp_core_yoy": {
        "dataset": "prc_hicp_manr",
        "filters": {"coicop": "TOT_X_NRG_FOOD", "unit": "RCH_A"},
        "ea": "EA", "freq": "M",
        "desc": "Core HICP (ex energy & food) inflation, % y/y",
    },
    "hicp_index": {
        "dataset": "prc_hicp_midx",
        "filters": {"coicop": "CP00", "unit": "I15"},
        "ea": "EA", "freq": "M",
        "desc": "HICP all-items index (2015=100)",
    },
    "ppi_yoy": {
        "dataset": "sts_inppd_m",
        "filters": {"indic_bt": "PRC_PRR_DOM", "nace_r2": "B-E36",
                    "s_adj": "NSA", "unit": "PCH_SM"},
        "ea": "EA20", "freq": "M",
        "desc": "Producer prices, domestic market (industry), % y/y",
    },
    # --- activity ---
    "gdp_growth": {
        "dataset": "namq_10_gdp",
        "filters": {"unit": "CLV_PCH_PRE", "s_adj": "SCA",
                    "na_item": "B1GQ"},
        "ea": "EA20", "freq": "Q",
        "desc": "Real GDP growth, % change on previous quarter (SCA)",
    },
    "gdp_growth_yoy": {
        "dataset": "namq_10_gdp",
        "filters": {"unit": "CLV_PCH_SM", "s_adj": "SCA",
                    "na_item": "B1GQ"},
        "ea": "EA20", "freq": "Q",
        "desc": "Real GDP growth, % change year-on-year (SCA)",
    },
    "gdp_level": {
        "dataset": "namq_10_gdp",
        "filters": {"unit": "CP_MEUR", "s_adj": "SCA", "na_item": "B1GQ"},
        "ea": "EA20", "freq": "Q",
        "desc": "Nominal GDP, million EUR, current prices (SCA)",
    },
    "industrial_production": {
        "dataset": "sts_inpr_m",
        "filters": {"nace_r2": "B-D", "s_adj": "SCA", "unit": "I21",
                    "indic_bt": "PRD"},
        "ea": "EA20", "freq": "M",
        "desc": "Industrial production index, mining-manufacturing-"
                "utilities (2021=100, SCA)",
    },
    "retail_trade": {
        "dataset": "sts_trtu_m",
        "filters": {"indic_bt": "VOL_SLS", "nace_r2": "G47",
                    "s_adj": "SCA", "unit": "I21"},
        "ea": "EA20", "freq": "M",
        "desc": "Retail trade volume index (2021=100, SCA)",
    },
    # --- labour ---
    "unemployment_rate": {
        "dataset": "une_rt_m",
        "filters": {"s_adj": "SA", "age": "TOTAL", "unit": "PC_ACT",
                    "sex": "T"},
        "ea": "EA21", "freq": "M",
        "desc": "Unemployment rate, % of active population (SA); "
                "sex=/age= overrides",
    },
    "employment_rate": {
        "dataset": "lfsi_emp_q",
        "filters": {"s_adj": "SA", "indic_em": "EMP_LFS", "unit": "PC_POP",
                    "sex": "T", "age": "Y20-64"},
        "ea": "EA20", "freq": "Q",
        "desc": "Employment rate, % of population 20-64 (SA)",
    },
    "wage_growth": {
        "dataset": "lc_lci_r2_q",
        "filters": {"s_adj": "SCA", "lcstruct": "D11", "unit": "PCH_SM",
                    "nace_r2": "B-S"},
        "ea": "EA20", "freq": "Q",
        "desc": "Labour cost index, wages & salaries, % y/y (SCA)",
    },
    # --- government finance (EDP) ---
    "gov_debt": {
        "dataset": "gov_10dd_edpt1",
        "filters": {"na_item": "GD", "sector": "S13", "unit": "PC_GDP"},
        "ea": "EA20", "freq": "A",
        "desc": "General government gross (Maastricht) debt, % of GDP",
    },
    "gov_deficit": {
        "dataset": "gov_10dd_edpt1",
        "filters": {"na_item": "B9", "sector": "S13", "unit": "PC_GDP"},
        "ea": "EA20", "freq": "A",
        "desc": "General government net lending (+) / borrowing (-), % of GDP",
    },
    # --- external ---
    "current_account": {
        "dataset": "bop_c6_q",  # countries; EA/EU aggregates auto-route
        "filters": {"currency": "MIO_EUR", "sector10": "S1",
                    "sectpart": "S1", "bop_item": "CA", "stk_flow": "BAL",
                    "partner": "WRL_REST"},
        "ea": "EA20", "ea_dataset": "bop_eu6_q", "freq": "Q",
        "desc": "Current account balance vs rest of world, million EUR",
    },
    # --- energy ---
    "gas_price_households": {
        "dataset": "nrg_pc_202",
        "filters": {"siec": "G3000", "nrg_cons": "GJ20-199", "unit": "KWH",
                    "tax": "I_TAX", "currency": "EUR"},
        "ea": "EA20", "freq": "S",
        "desc": "Household natural gas price, EUR/kWh incl. taxes "
                "(band 20-200 GJ, semi-annual)",
    },
    "electricity_price_households": {
        "dataset": "nrg_pc_204",
        "filters": {"nrg_cons": "KWH2500-4999", "unit": "KWH",
                    "tax": "I_TAX", "currency": "EUR"},
        "ea": "EA20", "freq": "S",
        "desc": "Household electricity price, EUR/kWh incl. taxes "
                "(band 2500-5000 kWh, semi-annual)",
    },
    # --- demography ---
    "population": {
        "dataset": "demo_pjan",
        "filters": {"sex": "T", "age": "TOTAL", "unit": "NR"},
        "ea": "EA20", "freq": "A",
        "desc": "Population on 1 January, persons",
    },
}


# --------------------------------------------------------------------------
# Transport + JSON-stat decoding
# --------------------------------------------------------------------------

def _request_json(dataset: str, params: List) -> Dict[str, Any]:
    url = f"{DATA_URL}/{dataset}"
    qs = [("format", "JSON"), ("lang", "EN")] + params
    resp = _SESSION.get(url, params=qs, timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        detail = resp.text[:400]
        try:
            err = resp.json().get("error")
            if isinstance(err, list) and err:
                detail = err[0].get("label", detail)
        except ValueError:
            pass
        raise EurostatError(
            f"Eurostat API HTTP {resp.status_code} for {dataset}: {detail}"
        )
    try:
        return resp.json()
    except ValueError as e:
        raise EurostatError(
            f"Eurostat API returned non-JSON: {resp.text[:200]}"
        ) from e


def _jsonstat_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Unroll a JSON-stat 2.0 response into tidy rows.

    One row per observation: each dimension contributes ``<dim>`` (code) and
    ``<dim>_label`` columns; the observation lands in ``value`` (float).
    Missing cells (not present in the sparse value map) are skipped.
    """
    dim_ids: List[str] = payload.get("id", [])
    sizes: List[int] = payload.get("size", [])
    values: Dict[str, Any] = payload.get("value", {}) or {}
    if not dim_ids or not values:
        return []

    # Per-dimension: position -> (code, label)
    axes: List[List[tuple]] = []
    for did in dim_ids:
        cat = payload["dimension"][did]["category"]
        index = cat.get("index")
        labels = cat.get("label", {})
        if index is None:  # single-category dim may omit index
            codes = list(labels) or [""]
            axis = [(c, labels.get(c, c)) for c in codes]
        else:
            if isinstance(index, list):
                ordered = index
            else:
                ordered = sorted(index, key=lambda k: index[k])
            axis = [(c, labels.get(c, c)) for c in ordered]
        axes.append(axis)

    # Row-major strides over the hypercube.
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]

    rows: List[Dict[str, Any]] = []
    for k, v in values.items():
        if v is None:
            continue
        lin = int(k)
        row: Dict[str, Any] = {}
        for i, did in enumerate(dim_ids):
            pos = (lin // strides[i]) % sizes[i]
            code, label = axes[i][pos]
            row[did] = code
            row[f"{did}_label"] = label
        try:
            row["value"] = float(v)
        except (TypeError, ValueError):
            row["value"] = v
        rows.append(row)
    rows.sort(key=lambda r: r.get("time", ""))
    return rows


# --------------------------------------------------------------------------
# Alias resolution
# --------------------------------------------------------------------------

def _resolve_geo(geo: str, ea_code: Optional[str] = None) -> str:
    up = str(geo).strip().upper()
    if ea_code and up in _EA_TOKENS:
        return ea_code
    return GEO_ALIASES.get(up, up)


def _as_list(v: Union[str, Sequence[str], None]) -> List[str]:
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

_TOC_CACHE: Optional[List[Dict[str, str]]] = None


def list_catalog() -> List[Dict[str, str]]:
    """Return the curated headline-indicator catalog as rows.

    Each row: ``name`` (sandbox key), ``dataset``, ``desc``.
    """
    return [
        {"name": k, "dataset": v["dataset"], "desc": v["desc"]}
        for k, v in CATALOG.items()
    ]


def search_datasets(keyword: str) -> List[Dict[str, str]]:
    """Full-text search over the Eurostat catalogue table of contents
    (~7,000 dataset leaves; cached after first call).

    Returns rows: ``code``, ``title``, ``data_start``, ``data_end``,
    ``last_update``.
    """
    global _TOC_CACHE
    if _TOC_CACHE is None:
        resp = _SESSION.get(TOC_URL, params={"lang": "en"},
                            timeout=DEFAULT_TIMEOUT)
        if resp.status_code >= 400:
            raise EurostatError(
                f"Eurostat TOC HTTP {resp.status_code}: {resp.text[:200]}"
            )
        rows = []
        for line in resp.text.splitlines()[1:]:
            parts = [p.strip().strip('"') for p in line.split("\t")]
            if len(parts) < 7 or parts[2] not in ("dataset", "table"):
                continue
            rows.append({
                "code": parts[1],
                "title": parts[0].strip(),
                "last_update": parts[3],
                "data_start": parts[5],
                "data_end": parts[6],
            })
        _TOC_CACHE = rows
    q = keyword.lower()
    return [
        r for r in _TOC_CACHE
        if q in r["code"].lower() or q in r["title"].lower()
    ]


def get_constraints(dataset: str) -> Dict[str, List[str]]:
    """Return the POPULATED code values per dimension:
    ``{dim_id: [codes...]}`` (plus ``TIME_PERIOD`` coverage).

    Uses the SDMX content-constraint endpoint -- a few KB for any dataset,
    so it works where ``describe_dataset`` would exceed the extraction cap
    on very large datasets. Codes only (no labels); pair with
    ``describe_dataset(dataset, <narrow filters>)`` when labels are needed.
    """
    url = f"{CONSTRAINT_URL}/{str(dataset).strip().lower()}"
    resp = _SESSION.get(url, timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        raise EurostatError(
            f"Eurostat constraint HTTP {resp.status_code} for {dataset}: "
            f"{resp.text[:200]}"
        )
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError as e:
        raise EurostatError(f"constraint response not parseable: {e}") from e
    ns_s = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/structure}"
    ns_c = "{http://www.sdmx.org/resources/sdmxml/schemas/v2_1/common}"
    out: Dict[str, List[str]] = {}
    for cr in root.iter(ns_s + "CubeRegion"):
        for kv in cr.iter(ns_c + "KeyValue"):
            dim = kv.get("id", "")
            out[dim.lower() if dim != "TIME_PERIOD" else dim] = [
                v.text for v in kv.iter(ns_c + "Value") if v.text
            ]
    return out


def describe_dataset(
    dataset: str, **filters: Union[str, Sequence[str]]
) -> Dict[str, Dict[str, str]]:
    """Return the dataset's dimensions with valid codes + labels:
    ``{dim_id: {code: label}}``.

    Fetches the latest period only (cheap). Optional named filters narrow
    the probe (e.g. ``geo="DE"``); a dimension you filtered shows only the
    requested codes, unfiltered dimensions show the full code universe.
    ``time`` is included with the probed period(s). Very large datasets can
    exceed the extraction cap (HTTP 413) when probed unfiltered -- use
    ``get_constraints(dataset)`` for the populated code lists in that case.
    """
    params: List = [("lastTimePeriod", 1)]
    for k, v in filters.items():
        for x in _as_list(v):
            params.append((k, x))
    payload = _request_json(dataset, params)
    out: Dict[str, Dict[str, str]] = {}
    for did in payload.get("id", []):
        cat = payload["dimension"][did]["category"]
        labels = cat.get("label", {})
        index = cat.get("index", {})
        codes = (index if isinstance(index, list)
                 else sorted(index, key=lambda k: index[k]))
        out[did] = {c: labels.get(c, c) for c in codes}
    return out


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def get_data(
    dataset: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    **filters: Union[str, Sequence[str]],
) -> List[Dict[str, Any]]:
    """Fetch observations from any Eurostat dataset as tidy rows.

    Dimension filters are NAMED kwargs with exact Eurostat codes
    (``coicop="CP00"``, ``geo=["DE", "FR"]`` -- lists fan out). ``geo``
    values go through the alias map (``"Germany"`` works). Unfiltered
    dimensions return every code -- filter tightly or the extraction gets
    big (the API rejects extractions over ~50 groups with HTTP 413).

    ``start``/``end`` map to ``sinceTimePeriod``/``untilTimePeriod``
    (``"2020"``, ``"2020-01"``, ``"2020-Q1"``); ``last_n`` to
    ``lastTimePeriod``. Rows carry ``<dim>`` + ``<dim>_label`` columns per
    dimension plus float ``value``; missing observations are dropped.
    """
    params: List = []
    if start:
        params.append(("sinceTimePeriod", start))
    if end:
        params.append(("untilTimePeriod", end))
    if last_n is not None:
        params.append(("lastTimePeriod", int(last_n)))
    for k, v in filters.items():
        vals = _as_list(v)
        if k == "geo":
            vals = [_resolve_geo(x) for x in vals]
        for x in vals:
            params.append((k, x))
    return _jsonstat_rows(_request_json(dataset, params))


def get_indicator(
    name: str,
    geos: Union[str, Sequence[str]],
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
    **overrides: Union[str, Sequence[str]],
) -> List[Dict[str, Any]]:
    """Headline accessor: pull a curated catalog indicator for one or more
    geos with verified dimension filters.

    ``name`` is a catalog key (see ``list_catalog``). ``geos`` accepts
    Eurostat codes (``DE``), common names (``"Germany"``, ``"Greece"``), and
    ``"euro area"`` / ``"EU"`` -- the wrapper substitutes the euro-area
    aggregate code this dataset actually uses (``EA`` vs ``EA20`` vs
    ``EA21``). Keyword overrides replace catalog filters (e.g.
    ``sex="F"``, ``age="Y_LT25"``, ``coicop="NRG"``).
    """
    entry = CATALOG.get(name)
    if entry is None:
        raise EurostatError(
            f"unknown indicator {name!r}; see list_catalog() for valid keys"
        )
    ea_code = entry.get("ea")
    geo_list = [_resolve_geo(g, ea_code) for g in _as_list(geos)]
    if not geo_list:
        raise EurostatError("at least one geo is required")

    filters = dict(entry["filters"])
    filters.update(overrides)

    # The current-account split: EA/EU aggregates live in a sibling dataset
    # with a different partner grammar (rest-of-world = EXT_<aggregate>).
    ea_dataset = entry.get("ea_dataset")
    if ea_dataset:
        agg = [g for g in geo_list
               if g in ("EA20", "EA19", "EA21", "EU27_2020", "EU28")]
        cty = [g for g in geo_list if g not in agg]
        rows: List[Dict[str, Any]] = []
        if cty:
            rows += get_data(entry["dataset"], start=start, end=end,
                             last_n=last_n, geo=cty, **filters)
        for g in agg:
            agg_filters = dict(filters)
            agg_filters["partner"] = f"EXT_{g}"
            agg_filters["s_adj"] = "NSA"
            rows += get_data(ea_dataset, start=start, end=end,
                             last_n=last_n, geo=g, **agg_filters)
        rows.sort(key=lambda r: (r.get("geo", ""), r.get("time", "")))
        return rows

    rows = get_data(entry["dataset"], start=start, end=end, last_n=last_n,
                    geo=geo_list, **filters)
    rows.sort(key=lambda r: (r.get("geo", ""), r.get("time", "")))
    return rows


def latest_per_geo(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Newest observation per geo (and per ``indicator`` when present).

    Use for cross-country rankings on annual data where countries report
    with different lags -- pull a couple of periods (``last_n=2`` or
    ``start=``) and reduce with this instead of trusting ``last_n=1`` to
    align.
    """
    best: Dict[Any, Dict[str, Any]] = {}
    for r in rows:
        k = (r.get("indicator"), r.get("geo"))
        if k not in best or str(r.get("time", "")) > str(best[k].get("time", "")):
            best[k] = r
    return sorted(best.values(),
                  key=lambda r: (str(r.get("indicator")), str(r.get("geo"))))


def get_panel(
    names: Sequence[str],
    geos: Union[str, Sequence[str]],
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    last_n: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Pull several catalog indicators in one combined long-row set.

    Each row keeps its ``indicator`` (catalog key), so
    ``to_dataframe(rows, wide=True)`` yields one column per
    (indicator, geo) series. Useful for headline + core HICP, debt +
    deficit, gas + electricity, etc.
    """
    rows: List[Dict[str, Any]] = []
    for name in names:
        for r in get_indicator(name, geos, start=start, end=end,
                               last_n=last_n):
            r["indicator"] = name
            rows.append(r)
    return rows


def to_dataframe(
    rows: List[Dict[str, Any]],
    *,
    wide: bool = False,
    label: bool = False,
):
    """Convert tidy Eurostat rows to a pandas DataFrame (long or wide).

    Long: dimension code columns that VARY + ``time`` (numeric helper from
    the period string) + ``value``. Wide: pivot of ``time`` x series, one
    column per series (headers from the varying dimensions; ``label=True``
    uses human labels instead of codes).
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("to_dataframe requires pandas") from e

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    period_col = "time" if "time" in df.columns else None
    df["_t"] = _coerce_time(df[period_col]) if period_col else None

    dim_cols = [c for c in ("indicator",) if c in df.columns]
    dim_cols += [c for c in df.columns
                 if not c.endswith("_label") and c not in
                 ("value", "_t", "time", "freq", "indicator")]
    varying = [c for c in dim_cols if df[c].nunique(dropna=False) > 1]

    if wide:
        header_cols = varying or dim_cols[:1]
        if label:
            header_cols = [
                f"{c}_label" if f"{c}_label" in df.columns else c
                for c in header_cols
            ]
        if header_cols:
            series_key = df[header_cols].astype(str).agg(" | ".join, axis=1)
        else:
            series_key = pd.Series(["value"] * len(df), index=df.index)
        df = df.assign(_series=series_key)
        pivot = df.pivot_table(
            index="_t", columns="_series", values="value", aggfunc="first"
        )
        pivot.index.name = "time"
        return pivot.sort_index()

    keep = []
    for c in varying:
        keep.append(c)
        if label and f"{c}_label" in df.columns:
            keep.append(f"{c}_label")
    keep += ["time", "_t", "value"]
    out = df[[c for c in keep if c in df.columns]].copy()
    out = out.rename(columns={"_t": "time_num"})
    sort_cols = [c for c in ["geo", "time_num"] if c in out.columns]
    return out.sort_values(sort_cols) if sort_cols else out


def _coerce_time(series):
    """Sortable numeric from Eurostat period strings ('2024', '2024-03',
    '2024-Q1', '2024-S2', '2024-W05')."""
    import pandas as pd
    if series is None:
        return None

    def conv(v: Any):
        s = str(v)
        try:
            if "-Q" in s:
                y, q = s.split("-Q")
                return int(y) + (int(q) - 1) / 4.0
            if "-S" in s:
                y, h = s.split("-S")
                return int(y) + (int(h) - 1) / 2.0
            if "-W" in s:
                y, w = s.split("-W")
                return int(y) + (int(w) - 1) / 53.0
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
    "EurostatError",
    "GEO_ALIASES",
    "list_catalog",
    "search_datasets",
    "describe_dataset",
    "get_constraints",
    "get_data",
    "get_indicator",
    "get_panel",
    "latest_per_geo",
    "to_dataframe",
]
