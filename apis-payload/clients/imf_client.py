"""IMF (International Monetary Fund) -- cross-country macro client.

Sandbox name: ``imf_client``.

TWO TRANSPORT SURFACES (post September-2025 IMF API migration):

1. DATAMAPPER (no key, the v1 backbone). www.imf.org/external/datamapper.
   Covers the IMF's flagship cross-country macro datasets -- World Economic
   Outlook (WEO, with projections out to T+5), Fiscal Monitor (FM), Global
   Debt Database (GDD), Assessing Reserve Adequacy (ARA) and ~9 more. 132
   headline indicators over 241 countries + 129 analytical groups, annual
   frequency, history from 1980. This is the surface every demo/recipe uses.

       imf_client.get_data("real gdp growth", ["USA", "China", "Euro area"])
       imf_client.compare("government debt", ["G7"], year=2025)
       imf_client.latest("inflation", "Brazil")
       imf_client.list_indicators(dataset="WEO")
       imf_client.to_dataframe(rows, pivot="entity")

2. SDMX 3.0 (KEY REQUIRED, documented escape hatch). api.imf.org/external/
   sdmx/3.0. Covers the deep statistical tail the Datamapper does NOT expose
   -- CPI (monthly), Balance of Payments (BOP), trade matrix (IMTS),
   Government Finance Statistics (GFS), Financial Soundness Indicators (FSI),
   Exchange Rates (ER), policy rates (MFS_IR), commodity prices (PCPS); the
   legacy monolithic IFS dataflow was decomposed into these component flows in
   the 2026-05 SDMX 3.0 refactor. Needs
   an Azure APIM ``Ocp-Apim-Subscription-Key`` (free at
   https://datamarketplace.imf.org/) supplied via the ``IMF_API_PRIMARY_KEY``
   env var. Without a key these methods raise a clear ImfError -- they never
   silently fall back to the Datamapper.

       imf_client.sdmx.catalog()                       # curated dataflow list
       imf_client.sdmx.data("CPI", "USA.CPI._T.IX.M")  # needs key

The legacy ``dataservices.imf.org`` JSON/XML service was retired in Sept 2025
and is intentionally NOT supported here.

Net-new vs other apis clients -- DEFERS for overlapping themes (see ROUTING):
    US high-frequency series (CPI, payrolls, rates)  -> fred_client
    cross-border banking / credit / DSR              -> bis_client
    company-level financials / XBRL                  -> sec_edgar_client

Transport: Bucket C (plain ``requests``; no GS-proxy stub dependency).
Values are returned numeric-coerced; entities and indicators accept friendly
aliases ("US", "Euro area", "real gdp growth") that the wrapper resolves to
ISO3 / group / indicator codes internally.
"""

from __future__ import annotations

import collections
import datetime
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Union

import requests


__all__ = [
    "ImfError",
    "get_data",
    "get_panel",
    "get_series",
    "latest",
    "compare",
    "members",
    "BASKETS",
    "list_datasets",
    "list_indicators",
    "search_indicators",
    "get_indicator",
    "describe",
    "list_countries",
    "list_groups",
    "resolve_entity",
    "resolve_indicator",
    "refresh_catalog",
    "to_dataframe",
    "sdmx",
    "INDICATORS",
    "DATASET_SOURCES",
    "GROUPS",
    "COUNTRIES",
    "ROUTING",
]

DEFAULT_TIMEOUT = 60
_DM_BASE = "https://www.imf.org/external/datamapper/api/v1"

# NOTE: do NOT set a custom or browser-spoofing User-Agent. The IMF Akamai
# WAF returns HTTP 403 for custom UAs and for "Mozilla/..." impersonators, but
# allows the default requests UA ("python-requests/X.Y") -- which is what PRISM
# sends too. Leave the session UA at the requests default.
_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})


class ImfError(Exception):
    """Raised on validation failures or unrecoverable IMF API errors."""


# Common multi-country baskets -> member ISO3 lists. Used by get_data/compare
# to expand a friendly basket NAME into its constituent countries (for
# rankings/panels). To get a single aggregate SERIES instead, pass the group
# CODE (e.g. "MAE" for G7, "EU" for the European Union).
BASKETS = {
    "G7": ["USA", "JPN", "DEU", "FRA", "ITA", "GBR", "CAN"],
    "G20": ["ARG", "AUS", "BRA", "CAN", "CHN", "FRA", "DEU", "IND", "IDN",
            "ITA", "JPN", "KOR", "MEX", "RUS", "SAU", "ZAF", "TUR", "GBR", "USA"],
    "BRICS": ["BRA", "RUS", "IND", "CHN", "ZAF"],
}


# Themes deliberately NOT covered here -- they already have a dedicated client.
ROUTING = {
    "US high-frequency macro (CPI MoM, payrolls, rates, IP)": "fred_client",
    "cross-border banking / credit-to-GDP / debt service ratio": "bis_client",
    "company-level financials / XBRL frames / filings": "sec_edgar_client",
    "US Treasury issuance / auctions / debt": "treasury_client / treasury_direct_client",
}


# --- Boundary numeric coercion -----------------------------------------------

_INT_RE = re.compile(r"^[+-]?\d+$")


def _coerce_num(v: Any) -> Any:
    """Coerce a scalar to int/float where possible; "" -> None; pass-through
    otherwise. Datamapper returns JSON numbers already, but mixed string
    payloads (and the SDMX surface) can carry numeric strings."""
    if v is None or isinstance(v, (int, float)):
        return v
    s = str(v).strip()
    if s == "":
        return None
    if _INT_RE.match(s):
        try:
            return int(s)
        except ValueError:
            return s
    try:
        return float(s)
    except ValueError:
        return v


# --- Datamapper transport -----------------------------------------------------


def _dm_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{_DM_BASE}/{path.lstrip('/')}"
    try:
        resp = _SESSION.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as e:
        raise ImfError(f"request failed for {url}: {e}") from e
    if resp.status_code >= 400:
        raise ImfError(f"HTTP {resp.status_code} for {url}: {resp.text[:200]}")
    try:
        return resp.json()
    except ValueError as e:
        raise ImfError(f"non-JSON body from {url}: {resp.text[:200]}") from e


# --- Resolvers (friendly alias -> code) ---------------------------------------


def _build_entity_aliases() -> Dict[str, str]:
    """name (lowercased) -> ISO3 / group code. Curated overrides win; the rest
    is filled from the country + group labels."""
    aliases: Dict[str, str] = {}
    # labels first (group labels do not overwrite a country once curated below)
    for code, label in COUNTRIES.items():
        if label:
            aliases[label.lower()] = code
    for code, label in GROUPS.items():
        if label:
            aliases.setdefault(label.lower(), code)
    aliases.update(_ENTITY_OVERRIDES)
    return aliases


_ENTITY_OVERRIDES = {
    "us": "USA", "u.s.": "USA", "u.s.a.": "USA", "usa": "USA",
    "united states": "USA", "america": "USA", "united states of america": "USA",
    "uk": "GBR", "u.k.": "GBR", "britain": "GBR", "great britain": "GBR",
    "united kingdom": "GBR",
    "china": "CHN", "prc": "CHN", "mainland china": "CHN",
    "south korea": "KOR", "korea": "KOR", "republic of korea": "KOR",
    "north korea": "PRK",
    "russia": "RUS",
    "iran": "IRN", "syria": "SYR", "venezuela": "VEN", "vietnam": "VNM",
    "laos": "LAO", "brunei": "BRN", "moldova": "MDA", "tanzania": "TZA",
    "bolivia": "BOL", "egypt": "EGY",
    "turkey": "TUR", "turkiye": "TUR", "türkiye": "TUR",
    "czechia": "CZE", "czech republic": "CZE",
    "slovakia": "SVK", "slovak republic": "SVK",
    "ivory coast": "CIV", "cote d'ivoire": "CIV", "côte d'ivoire": "CIV",
    "hong kong": "HKG", "macao": "MAC", "macau": "MAC", "taiwan": "TWN",
    "kyrgyzstan": "KGZ", "the gambia": "GMB", "gambia": "GMB",
    "bahamas": "BHS", "kosovo": "UVK",
    "euro area": "EURO", "eurozone": "EURO", "euro zone": "EURO", "ea": "EURO",
    "european union": "EU", "the eu": "EU",
    "world": "WEOWORLD", "global": "WEOWORLD", "the world": "WEOWORLD",
    "advanced economies": "ADVEC", "advanced economy": "ADVEC",
    "developed economies": "ADVEC", "aes": "ADVEC",
    "emerging markets": "EME", "emerging market economies": "EME", "ems": "EME",
    "emerging market and developing economies": "OEMDC", "emdes": "OEMDC",
    "emerging and developing economies": "OEMDC",
    "g7": "MAE", "g-7": "MAE", "group of seven": "MAE",
    "asean-5": "AS5", "asean5": "AS5", "asean 5": "AS5",
    "sub-saharan africa": "SSA", "ssa": "SSA",
    "latin america": "WE", "latin america and the caribbean": "WE",
    "middle east and central asia": "MECA",
    "emerging and developing asia": "DA",
}


def _build_indicator_aliases() -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for code, (label, _unit, _ds) in INDICATORS.items():
        if label:
            aliases.setdefault(label.lower(), code)
    aliases.update(_INDICATOR_OVERRIDES)
    return aliases


_INDICATOR_OVERRIDES = {
    "real gdp growth": "NGDP_RPCH", "gdp growth": "NGDP_RPCH",
    "real gdp": "NGDP_RPCH", "growth": "NGDP_RPCH", "gdp growth rate": "NGDP_RPCH",
    "gdp": "NGDPD", "nominal gdp": "NGDPD", "gdp current prices": "NGDPD",
    "gdp usd": "NGDPD", "gdp in usd": "NGDPD", "gdp size": "NGDPD",
    "gdp per capita": "NGDPDPC",
    "gdp ppp": "PPPGDP", "ppp gdp": "PPPGDP", "gdp at ppp": "PPPGDP",
    "gdp per capita ppp": "PPPPC",
    "ppp share": "PPPSH", "share of world gdp": "PPPSH", "world gdp share": "PPPSH",
    "inflation": "PCPIPCH", "cpi inflation": "PCPIPCH", "inflation rate": "PCPIPCH",
    "average inflation": "PCPIPCH", "consumer prices": "PCPIPCH",
    "end of period inflation": "PCPIEPCH", "eop inflation": "PCPIEPCH",
    "unemployment": "LUR", "unemployment rate": "LUR", "jobless rate": "LUR",
    "population": "LP",
    "current account": "BCA_NGDPD", "current account balance": "BCA_NGDPD",
    "cab": "BCA_NGDPD", "current account to gdp": "BCA_NGDPD",
    "current account usd": "BCA",
    "government debt": "GGXWDG_NGDP", "gross debt": "GGXWDG_NGDP",
    "public debt": "GGXWDG_NGDP", "debt to gdp": "GGXWDG_NGDP",
    "government gross debt": "GGXWDG_NGDP", "sovereign debt": "GGXWDG_NGDP",
    "debt": "GGXWDG_NGDP",
    "fiscal balance": "GGXCNL_NGDP", "budget balance": "GGXCNL_NGDP",
    "net lending": "GGXCNL_NGDP", "net lending/borrowing": "GGXCNL_NGDP",
    "fiscal deficit": "GGXCNL_NGDP", "general government balance": "GGXCNL_NGDP",
    "deficit": "GGXCNL_NGDP", "overall balance": "GGXCNL_NGDP",
    "gross government debt": "GGXWDG_NGDP",
    "general government gross debt": "GGXWDG_NGDP",
    "primary balance": "GGXONLB_G01_GDP_PT",
    "revenue": "GGR_G01_GDP_PT", "government revenue": "GGR_G01_GDP_PT",
    "expenditure": "G_X_G01_GDP_PT", "government expenditure": "G_X_G01_GDP_PT",
    "household debt": "HH_ALL",
    "corporate debt": "NFC_ALL", "nonfinancial corporate debt": "NFC_ALL",
    "private debt": "Privatedebt_all",
    "long-run public debt": "d", "historical public debt": "d",
    "public debt history": "d",
}


_ENTITY_ALIASES: Dict[str, str] = {}
_INDICATOR_ALIASES: Dict[str, str] = {}


def _ensure_alias_maps() -> None:
    global _ENTITY_ALIASES, _INDICATOR_ALIASES
    if not _ENTITY_ALIASES:
        _ENTITY_ALIASES = _build_entity_aliases()
    if not _INDICATOR_ALIASES:
        _INDICATOR_ALIASES = _build_indicator_aliases()


def _suggest(token: str, pool: Sequence[str], n: int = 6) -> List[str]:
    t = token.lower()
    hits = [p for p in pool if t in p.lower()]
    return sorted(hits)[:n]


def resolve_entity(name: Union[str, int]) -> str:
    """Resolve a country/group input to its IMF code. Accepts ISO3 codes
    ("USA"), group codes ("ADVEC"), and friendly names ("US", "Euro area",
    "G7", "China"). Raises ImfError with suggestions on no match."""
    _ensure_alias_maps()
    s = str(name).strip()
    if not s:
        raise ImfError("empty entity")
    up = s.upper()
    if up in COUNTRIES or up in GROUPS:
        return up
    hit = _ENTITY_ALIASES.get(s.lower())
    if hit:
        return hit
    sugg = _suggest(s, list(COUNTRIES.values()) + list(GROUPS.values()))
    raise ImfError(
        f"unknown entity {name!r}. Pass an ISO3 country code, a group code, "
        f"or a known name. Similar labels: {sugg}. "
        f"See list_countries() / list_groups()."
    )


def resolve_indicator(name: str) -> str:
    """Resolve an indicator input to its IMF code. Accepts codes
    ("NGDP_RPCH"), exact labels ("Real GDP growth"), and friendly aliases
    ("real gdp growth", "inflation", "government debt"). Raises ImfError with
    suggestions on no match."""
    _ensure_alias_maps()
    s = str(name).strip()
    if not s:
        raise ImfError("empty indicator")
    if s in INDICATORS:
        return s
    low = s.lower()
    for key in (low, low.replace("-", " "), " ".join(low.split())):
        hit = _INDICATOR_ALIASES.get(key)
        if hit:
            return hit
    sugg = _suggest(s, [f"{c} ({lbl})" for c, (lbl, _u, _d) in INDICATORS.items()])
    raise ImfError(
        f"unknown indicator {name!r}. Pass an indicator code or a known "
        f"label/alias. Similar: {sugg}. See list_indicators()."
    )


def members(basket: str) -> List[str]:
    """Member ISO3 codes for a multi-country basket ("G7", "G20", "BRICS").
    Use for cross-country rankings/panels. For a single aggregate series pass
    the group code instead (e.g. "MAE" for the G7 aggregate)."""
    key = str(basket).strip().upper().replace("-", "").replace(" ", "")
    b = BASKETS.get(key)
    if b:
        return list(b)
    raise ImfError(
        f"unknown basket {basket!r}; known: {sorted(BASKETS)}. For a single "
        f"aggregate series use the group code (e.g. 'MAE' for G7)."
    )


def _expand_entities(entities: Sequence[Union[str, int]]) -> List[str]:
    """Resolve entities to codes, expanding any basket NAME (G7/G20/BRICS) into
    its member countries. Deduped, order-preserving."""
    out: List[str] = []
    for e in entities:
        key = str(e).strip().upper().replace("-", "").replace(" ", "")
        if key in BASKETS:
            out.extend(BASKETS[key])
        else:
            out.append(resolve_entity(e))
    seen: set = set()
    res: List[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


def _entity_label(code: str) -> str:
    return COUNTRIES.get(code) or GROUPS.get(code) or code


# --- Discovery ----------------------------------------------------------------


def list_datasets() -> List[Dict[str, Any]]:
    """List the Datamapper datasets (no key) with indicator counts. Each row:
    code, name, source, n_indicators."""
    counts = collections.Counter(d for _l, _u, d in INDICATORS.values())
    out = []
    for ds, (name, src) in DATASET_SOURCES.items():
        out.append({"code": ds, "name": name, "source": src,
                    "n_indicators": counts.get(ds, 0)})
    out.sort(key=lambda r: -r["n_indicators"])
    return out


def list_indicators(dataset: Optional[str] = None,
                    keyword: Optional[str] = None) -> List[Dict[str, Any]]:
    """List indicators (code, label, unit, dataset). Filter by dataset code
    (e.g. "WEO", "FM", "GDD") and/or a keyword matched against label+code."""
    ds = dataset.strip().upper() if dataset else None
    kw = keyword.strip().lower() if keyword else None
    out = []
    for code, (label, unit, d) in INDICATORS.items():
        if ds and d != ds:
            continue
        if kw and kw not in label.lower() and kw not in code.lower():
            continue
        out.append({"code": code, "label": label, "unit": unit, "dataset": d})
    out.sort(key=lambda r: (r["dataset"], r["code"]))
    return out


def search_indicators(keyword: str) -> List[Dict[str, Any]]:
    """Keyword search over the indicator catalog (label + code)."""
    return list_indicators(keyword=keyword)


def get_indicator(code: str) -> Dict[str, Any]:
    """Full metadata for one indicator (resolves aliases): code, label, unit,
    dataset, dataset_name, source."""
    c = resolve_indicator(code)
    label, unit, d = INDICATORS[c]
    name, src = DATASET_SOURCES.get(d, (d, ""))
    return {"code": c, "label": label, "unit": unit, "dataset": d,
            "dataset_name": name, "source": src}


def describe(indicator: Optional[str] = None) -> Dict[str, Any]:
    """With no arg: a one-call overview of the whole client (surface, dataset
    list, counts, routing, the keyed SDMX pointer). With an indicator: its
    metadata (== get_indicator)."""
    if indicator is not None:
        return get_indicator(indicator)
    return {
        "surface": "Datamapper (no key): get_data / get_series / latest / "
                   "compare / list_indicators / list_datasets / "
                   "list_countries / list_groups / to_dataframe",
        "datasets": list_datasets(),
        "n_indicators": len(INDICATORS),
        "n_countries": len(COUNTRIES),
        "n_groups": len(GROUPS),
        "frequency": "annual; WEO/FM include projections out to ~T+5",
        "routing": ROUTING,
        "sdmx": "imf_client.sdmx.catalog() -- keyed deep datasets "
                "(CPI/BOP/IMTS/GFS/FSI/ER/MFS_IR/PCPS); needs "
                "IMF_API_PRIMARY_KEY",
    }


def list_countries(keyword: Optional[str] = None) -> Dict[str, str]:
    """The 241 countries/economies (ISO3 -> name). Filter by keyword."""
    if not keyword:
        return dict(COUNTRIES)
    kw = keyword.strip().lower()
    return {c: n for c, n in COUNTRIES.items()
            if kw in n.lower() or kw in c.lower()}


def list_groups(keyword: Optional[str] = None) -> Dict[str, str]:
    """The 129 analytical groups/aggregates (code -> label). Filter by
    keyword. Use these codes as entities in get_data/compare just like
    countries (e.g. "ADVEC", "EURO", "MAE" for G7)."""
    if not keyword:
        return dict(GROUPS)
    kw = keyword.strip().lower()
    return {c: n for c, n in GROUPS.items()
            if kw in n.lower() or kw in c.lower()}


# --- Core data ----------------------------------------------------------------


def get_data(indicator: str,
             entities: Optional[Union[str, Sequence[Union[str, int]]]] = None,
             start: Optional[Union[int, str]] = None,
             end: Optional[Union[int, str]] = None,
             coerce: bool = True) -> List[Dict[str, Any]]:
    """Pull a Datamapper indicator into tidy long rows.

    Args:
        indicator: code or friendly alias ("real gdp growth", "NGDP_RPCH").
        entities: a single name/code, a list of them, or None for ALL
            economies (countries + groups the indicator covers). Names are
            resolved to codes ("US" -> "USA", "Euro area" -> "EURO",
            "G7" -> "MAE").
        start, end: inclusive year bounds (ints or strings).
        coerce: numeric-coerce values (default True).

    Entities also accept basket NAMES ("G7", "G20", "BRICS"), which expand to
    their member countries (for rankings/panels). For a single aggregate
    series pass the group code instead (e.g. "MAE" for the G7 aggregate).

    Returns:
        list of dicts: indicator, indicator_label, unit, dataset, entity,
        entity_label, year (int), value, is_projection (bool: year > current
        calendar year -- best-effort WEO/FM forecast flag). Sorted by
        (entity, year). Omitting start/end returns the full available history.

    Raises:
        ImfError on an unknown indicator (the Datamapper API silently returns
        its country catalog at HTTP 200 for unknown codes; the wrapper detects
        this and raises rather than handing back garbage).

    Note: WEO/FM values past the current calendar year are IMF PROJECTIONS,
    not actuals (the API does not flag the actual/forecast boundary).
    """
    code = resolve_indicator(indicator)
    ents: Optional[List[str]] = None
    if entities is not None:
        if isinstance(entities, (str, int)):
            entities = [entities]
        ents = _expand_entities(entities)

    # The Datamapper only honours a SINGLE-entity server-side filter; a
    # multi-entity path (slash- or comma-separated) silently returns ALL
    # economies. So fetch one entity server-side when exactly one is asked
    # for, otherwise fetch the whole indicator and filter client-side. Either
    # way we filter to `ents` defensively so the result is always exactly what
    # was requested.
    path = code + "/" + ents[0] if ents and len(ents) == 1 else code
    data = _dm_get(path)

    values = data.get("values") if isinstance(data, dict) else None
    if not isinstance(values, dict) or code not in values:
        if isinstance(data, dict) and ("countries" in data or "groups" in data
                                       or "indicators" in data):
            raise ImfError(
                f"unknown indicator {indicator!r} (resolved {code!r}); the "
                f"Datamapper API returns its reference catalog instead of data "
                f"for unknown codes. See list_indicators()."
            )
        where = f" for entities {ents}" if ents else ""
        raise ImfError(f"no data returned for indicator {code!r}{where}.")

    series = values[code]  # {entity: {year: value}}
    if ents:
        want = set(ents)
        series = {e: v for e, v in series.items() if e in want}
        if not series:
            raise ImfError(
                f"indicator {code!r} has no data for {ents} (the IMF dataset "
                f"may not cover these economies). See list_indicators() / "
                f"list_countries()."
            )
    label, unit, ds = INDICATORS.get(code, ("", "", ""))
    start_i = int(start) if start not in (None, "") else None
    end_i = int(end) if end not in (None, "") else None
    cy = datetime.date.today().year

    rows: List[Dict[str, Any]] = []
    for ent, yv in series.items():
        if not isinstance(yv, dict):
            continue
        for y, v in yv.items():
            try:
                yi = int(y)
            except (TypeError, ValueError):
                continue
            if start_i is not None and yi < start_i:
                continue
            if end_i is not None and yi > end_i:
                continue
            rows.append({
                "indicator": code, "indicator_label": label, "unit": unit,
                "dataset": ds, "entity": ent, "entity_label": _entity_label(ent),
                "year": yi, "value": _coerce_num(v) if coerce else v,
                "is_projection": yi > cy,
            })
    rows.sort(key=lambda r: (r["entity"], r["year"]))
    return rows


def get_panel(indicators: Sequence[str],
              entities: Optional[Union[str, Sequence[Union[str, int]]]] = None,
              start: Optional[Union[int, str]] = None,
              end: Optional[Union[int, str]] = None,
              coerce: bool = True) -> List[Dict[str, Any]]:
    """Pull several indicators into one combined long-row set (each row keeps
    its indicator/dataset). Convenience over calling get_data per indicator;
    feed straight into to_dataframe and pivot/melt in pandas."""
    out: List[Dict[str, Any]] = []
    for ind in indicators:
        out.extend(get_data(ind, entities, start=start, end=end, coerce=coerce))
    return out


def get_series(indicator: str, entity: Union[str, int],
               start: Optional[Union[int, str]] = None,
               end: Optional[Union[int, str]] = None,
               coerce: bool = True) -> List[Dict[str, Any]]:
    """One entity's time series for an indicator: list of {year, value}."""
    rows = get_data(indicator, [entity], start=start, end=end, coerce=coerce)
    return [{"year": r["year"], "value": r["value"]} for r in rows]


def latest(indicator: str, entity: Union[str, int],
           include_forecast: bool = True) -> Optional[Dict[str, Any]]:
    """Most recent observation for indicator+entity (full row dict, or None).

    include_forecast=True (default) returns the latest available value, which
    for WEO/FM is typically a PROJECTION. Set include_forecast=False to cap at
    the current calendar year as a best-effort "latest actual" heuristic (the
    API does not expose the true actual/forecast boundary)."""
    rows = get_data(indicator, [entity])
    if not rows:
        return None
    if not include_forecast:
        cy = datetime.date.today().year
        rows = [r for r in rows if r["year"] <= cy]
        if not rows:
            return None
    return max(rows, key=lambda r: r["year"])


def compare(indicator: str, entities: Sequence[Union[str, int]],
            year: Optional[Union[int, str]] = None,
            coerce: bool = True) -> Dict[str, Any]:
    """Cross-sectional snapshot of one indicator across entities for a single
    year (defaults to the latest year present). Returns
    {indicator, indicator_label, unit, year, data: [{entity, entity_label,
    value}]} with data sorted high -> low (None values last)."""
    code = resolve_indicator(indicator)
    rows = get_data(code, entities, coerce=coerce)
    if not rows:
        return {"indicator": code, "year": None, "data": []}
    yi = int(year) if year not in (None, "") else max(r["year"] for r in rows)
    label, unit, _ds = INDICATORS.get(code, ("", "", ""))
    data = [{"entity": r["entity"], "entity_label": r["entity_label"],
             "value": r["value"]} for r in rows if r["year"] == yi]
    data.sort(key=lambda r: (r["value"] is None, -(r["value"] or 0)))
    return {"indicator": code, "indicator_label": label, "unit": unit,
            "year": yi, "data": data}


def refresh_catalog() -> Dict[str, Any]:
    """Hit the live Datamapper /indicators, /countries, /groups endpoints and
    return the current universe (does NOT mutate the embedded snapshot). Use to
    detect indicators/datasets added since this client's embedded catalog.
    Returns {indicators, countries, groups, counts, new_indicators}."""
    ind = (_dm_get("indicators") or {}).get("indicators", {})
    cty = (_dm_get("countries") or {}).get("countries", {})
    grp = (_dm_get("groups") or {}).get("groups", {})
    new = sorted(set(ind) - set(INDICATORS))
    return {
        "indicators": ind, "countries": cty, "groups": grp,
        "counts": {"indicators": len(ind), "countries": len(cty),
                   "groups": len(grp)},
        "new_indicators": new,
    }


def to_dataframe(rows: Sequence[Dict[str, Any]],
                 pivot: Optional[str] = None):
    """Convert get_data rows to a pandas DataFrame (lazy import).

    pivot=None    -> tidy long frame (one row per entity-year).
    pivot="entity"-> wide: index=year, columns=entity, values=value.
    pivot="year"  -> wide: index=entity, columns=year, values=value."""
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover - pandas present in PRISM
        raise ImfError("pandas is required for to_dataframe()") from e
    df = pd.DataFrame(list(rows))
    if pivot == "entity" and not df.empty:
        return df.pivot_table(index="year", columns="entity", values="value")
    if pivot == "year" and not df.empty:
        return df.pivot_table(index="entity", columns="year", values="value")
    return df


# --- SDMX 3.0 keyed escape hatch ---------------------------------------------


class _SdmxSurface:
    """Key-gated access to the IMF SDMX 3.0 API (api.imf.org) for the deep
    datasets the Datamapper does not expose. Every method that hits the wire
    requires an Azure APIM subscription key in one of the env vars in
    ``KEY_ENV`` (get one at https://datamarketplace.imf.org/). Without a key
    these methods raise ImfError -- they never fall back to the Datamapper.

    Catalog/grammar helpers (catalog, build_path, key_grammar) work offline.

    NOTE: the on-the-wire parser (_parse_sdmx_json) targets SDMX-JSON 2.0.0
    and is verified only against the documented format, not against a live
    keyed call (no key in staging). Verify on first keyed use in PRISM.
    """

    BASE = "https://api.imf.org/external/sdmx/3.0"
    KEY_ENV = ("IMF_API_PRIMARY_KEY", "IMF_SDMX_SUBSCRIPTION_KEY",
               "IMF_API_KEY", "IMF_API_SECONDARY_KEY")

    # Curated dataflow catalog (post-2026-05 SDMX 3.0 refactor). version "+"
    # = latest; known explicit versions noted. Confirm live via dataflows().
    CATALOG: Dict[str, Dict[str, str]] = {
        "CPI": {"agency": "IMF.STA", "version": "+", "freq": "M/Q/A",
                "name": "Consumer Price Index",
                "note": "v5.0.0; split out of legacy IFS in 2026-05 refactor."},
        "BOP": {"agency": "IMF.STA", "version": "+", "freq": "Q",
                "name": "Balance of Payments (detailed)",
                "note": "v21.0.0."},
        "BOP_AGG": {"agency": "IMF.STA", "version": "+", "freq": "Q",
                    "name": "Balance of Payments -- Aggregates", "note": ""},
        "IMTS": {"agency": "IMF.STA", "version": "+", "freq": "M/Q",
                 "name": "International Merchandise Trade Statistics",
                 "note": "v1.0.0; replaces the retired DOTS; bilateral flows "
                         "need a partner-country dimension."},
        "DOT": {"agency": "IMF.STA", "version": "+", "freq": "M/Q",
                "name": "Direction of Trade Statistics (legacy)",
                "note": "Superseded by IMTS in 2026-05; may 404."},
        "GFS_COFOG": {"agency": "IMF.STA", "version": "+", "freq": "A",
                      "name": "Government Finance Statistics -- COFOG",
                      "note": "v11.0.0."},
        "FSI": {"agency": "IMF.STA", "version": "+", "freq": "Q",
                "name": "Financial Soundness Indicators",
                "note": "NPLs, capital adequacy, ROA/ROE."},
        "ER": {"agency": "IMF.STA", "version": "+", "freq": "M",
               "name": "Exchange Rates (NEER/REER + bilateral)",
               "note": "v4.0.1; ENDA_/ENDE_XDC_USD_RATE retired -- use "
                       "USD_XDC.PA_RT / EOP_RT."},
        "MFS_IR": {"agency": "IMF.STA", "version": "+", "freq": "M",
                   "name": "Monetary & Financial Statistics -- Interest Rates "
                           "(policy rates)",
                   "note": "v8.0.1."},
        "PCPS": {"agency": "IMF.RES", "version": "+", "freq": "M",
                 "name": "Primary Commodity Price System",
                 "note": "v9.0.0; moved IMF.STA -> IMF.RES in 2026-05."},
        "CDIS": {"agency": "IMF.STA", "version": "+", "freq": "A",
                 "name": "Coordinated Direct Investment Survey (FDI stocks)",
                 "note": ""},
        "CPIS": {"agency": "IMF.STA", "version": "+", "freq": "SA/A",
                 "name": "Coordinated Portfolio Investment Survey", "note": ""},
        "WEO": {"agency": "IMF.RES", "version": "+", "freq": "A",
                "name": "World Economic Outlook",
                "note": "Prefer the no-key Datamapper (imf_client.get_data)."},
        "FM": {"agency": "IMF.FAD", "version": "+", "freq": "A",
               "name": "Fiscal Monitor",
               "note": "Prefer the no-key Datamapper (imf_client.get_data)."},
    }

    def has_key(self) -> bool:
        """True if a subscription key is configured in the environment."""
        return any(os.environ.get(e, "").strip() for e in self.KEY_ENV)

    def _key(self) -> str:
        for e in self.KEY_ENV:
            v = os.environ.get(e, "").strip()
            if v:
                return v
        raise ImfError(
            "IMF SDMX 3.0 requires an Azure APIM subscription key. Set "
            "IMF_API_PRIMARY_KEY (free at https://datamarketplace.imf.org/). "
            "The no-key Datamapper surface (imf_client.get_data / compare / "
            "latest) covers WEO + Fiscal Monitor + Global Debt + reserves "
            "without a key."
        )

    def catalog(self, keyword: Optional[str] = None) -> List[Dict[str, str]]:
        """The curated SDMX 3.0 dataflow catalog (offline). Each row: dataflow,
        agency, version, freq, name, note. Filter by keyword."""
        kw = keyword.strip().lower() if keyword else None
        out = []
        for flow, m in self.CATALOG.items():
            if kw and kw not in flow.lower() and kw not in m["name"].lower():
                continue
            out.append({"dataflow": flow, "agency": m["agency"],
                        "version": m["version"], "freq": m["freq"],
                        "name": m["name"], "note": m["note"]})
        return out

    def key_grammar(self) -> str:
        """How to build the SDMX 3.0 series key (the dot-joined dimension
        path). The wire path is /data/dataflow/{agency}/{flow}/{version}/{key};
        {key} is dimension values joined by '.', '*' wildcards an omitted
        dimension, '+' ORs values within a dimension. Example (CPI):
        'USA.CPI._T.IX.M' = country.indicator.coverage.type.frequency. Use '*'
        for all of a dataflow."""
        return self.key_grammar.__doc__ or ""

    def _resolve_flow(self, dataflow: str):
        if "," in dataflow:
            parts = [p.strip() for p in dataflow.split(",")]
            agency = parts[0]
            flow = parts[1] if len(parts) > 1 else ""
            version = parts[2] if len(parts) > 2 else "+"
            return agency, flow, version
        flow = dataflow.strip().upper()
        m = self.CATALOG.get(flow)
        if m:
            return m["agency"], flow, m.get("version", "+")
        return "IMF.STA", flow, "+"  # best-effort default agency

    def build_path(self, dataflow: str, key: str = "*",
                   agency: Optional[str] = None,
                   version: Optional[str] = None) -> str:
        """Build the SDMX 3.0 data path (offline; no request). Useful to see
        exactly what would be hit."""
        a, f, v = self._resolve_flow(dataflow)
        a = agency or a
        v = version or v
        keyseg = key.strip() if key and key.strip() else "*"
        return f"/data/dataflow/{a}/{f}/{v}/{keyseg}"

    def data(self, dataflow: str, key: str = "*",
             start: Optional[str] = None, end: Optional[str] = None,
             agency: Optional[str] = None, version: Optional[str] = None,
             coerce: bool = True) -> List[Dict[str, Any]]:
        """Fetch SDMX 3.0 data into tidy rows (KEY REQUIRED).

        Args:
            dataflow: a catalog code ("CPI", "BOP", "IMTS") or an explicit
                "AGENCY,FLOW,VERSION" string.
            key: the dot-joined series key ('USA.CPI._T.IX.M'); '*' = all.
            start, end: SDMX period strings (e.g. "2020", "2020-01").
            agency, version: override the catalog defaults.

        Returns rows with one column per series dimension plus TIME_PERIOD and
        value. Raises ImfError without a key, or on HTTP 204/404 (the IMF
        gateway masks a missing/invalid key as 204/404)."""
        sub = self._key()
        path = self.build_path(dataflow, key=key, agency=agency, version=version)
        params: Dict[str, Any] = {}
        if start not in (None, ""):
            params["startPeriod"] = str(start)
        if end not in (None, ""):
            params["endPeriod"] = str(end)
        headers = {"Ocp-Apim-Subscription-Key": sub,
                   "Accept": "application/vnd.sdmx.data+json;version=2.0.0"}
        url = self.BASE + path
        try:
            resp = _SESSION.get(url, params=params, headers=headers,
                                timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ImfError(f"SDMX request failed for {url}: {e}") from e
        if resp.status_code in (204, 404):
            raise ImfError(
                f"IMF SDMX returned HTTP {resp.status_code} for {path} -- "
                f"usually a missing/invalid subscription key or an unknown "
                f"dataflow/key. The Azure gateway masks auth failures as "
                f"204/404. Check IMF_API_PRIMARY_KEY and sdmx.catalog()."
            )
        if resp.status_code >= 400:
            raise ImfError(f"HTTP {resp.status_code} for {url}: {resp.text[:200]}")
        try:
            payload = resp.json()
        except ValueError as e:
            raise ImfError(f"non-JSON SDMX body from {url}: {resp.text[:200]}") from e
        return _parse_sdmx_json(payload, coerce=coerce)

    def dataflows(self) -> List[Dict[str, Any]]:
        """Live list of all SDMX 3.0 dataflows (KEY REQUIRED). Returns
        [{id, agency, version, name}]. Use to confirm/refresh CATALOG."""
        sub = self._key()
        url = self.BASE + "/structure/dataflow/IMF"
        headers = {"Ocp-Apim-Subscription-Key": sub,
                   "Accept": "application/vnd.sdmx.structure+json;version=2.0.0"}
        try:
            resp = _SESSION.get(url, headers=headers, timeout=DEFAULT_TIMEOUT)
        except requests.RequestException as e:
            raise ImfError(f"SDMX structure request failed: {e}") from e
        if resp.status_code in (204, 404):
            raise ImfError(
                f"IMF SDMX returned HTTP {resp.status_code} for the dataflow "
                f"list -- check IMF_API_PRIMARY_KEY."
            )
        if resp.status_code >= 400:
            raise ImfError(f"HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        flows = (((data.get("data") or {}).get("dataflows"))
                 or data.get("dataflows") or [])
        out = []
        for f in flows:
            name = f.get("name")
            if isinstance(name, dict):
                name = name.get("en") or next(iter(name.values()), "")
            out.append({"id": f.get("id"), "agency": f.get("agencyID"),
                        "version": f.get("version"), "name": name})
        return out


def _parse_sdmx_json(payload: Dict[str, Any], coerce: bool = True
                     ) -> List[Dict[str, Any]]:
    """Parse an SDMX-JSON 2.0.0 data message into tidy rows. Targets the
    standard series/observation shape: series keyed by colon-joined dimension
    indices, observations keyed by the observation-dimension index, with the
    structure's dimension value lists giving the code for each index."""
    data = payload.get("data") or payload
    structs = data.get("structures") or data.get("structure") or []
    if isinstance(structs, dict):
        structs = [structs]
    datasets = data.get("dataSets") or data.get("datasets") or []
    rows: List[Dict[str, Any]] = []
    st = structs[0] if structs else {}
    dims = (st.get("dimensions") or {})
    ser_dims = dims.get("series", []) or []
    obs_dims = dims.get("observation", []) or []

    for ds in datasets:
        series = ds.get("series")
        if isinstance(series, dict):
            for skey, sval in series.items():
                idx = [int(x) for x in skey.split(":") if x != ""]
                base: Dict[str, Any] = {}
                for i, d in enumerate(ser_dims):
                    vals = d.get("values", [])
                    if i < len(idx) and idx[i] < len(vals):
                        base[d.get("id")] = vals[idx[i]].get("id")
                for okey, oval in (sval.get("observations") or {}).items():
                    period = None
                    try:
                        oi = int(okey)
                    except (TypeError, ValueError):
                        oi = -1
                    if obs_dims and 0 <= oi < len(obs_dims[0].get("values", [])):
                        period = obs_dims[0]["values"][oi].get("id")
                    val = oval[0] if isinstance(oval, list) and oval else oval
                    row = dict(base)
                    row["TIME_PERIOD"] = period
                    row["value"] = _coerce_num(val) if coerce else val
                    rows.append(row)
        else:
            for okey, oval in (ds.get("observations") or {}).items():
                idx = [int(x) for x in okey.split(":") if x != ""]
                row = {}
                alldims = ser_dims + obs_dims
                for i, d in enumerate(alldims):
                    vals = d.get("values", [])
                    if i < len(idx) and idx[i] < len(vals):
                        row[d.get("id")] = vals[idx[i]].get("id")
                val = oval[0] if isinstance(oval, list) and oval else oval
                row["value"] = _coerce_num(val) if coerce else val
                rows.append(row)
    return rows


sdmx = _SdmxSurface()


# =============================================================================
# Embedded Datamapper catalog snapshot (live as of 2026-06-14; WEO April 2026,
# Fiscal Monitor April 2026, Global Debt Database Sep 2025). Refresh via
# refresh_catalog().
# =============================================================================

# code -> (label, unit, dataset_code)
INDICATORS = {
    # --- WEO: World Economic Outlook (15) ---
    'BCA': ('Current account balance U.S. dollars', 'Billions of U.S. dollars', 'WEO'),
    'BCA_NGDPD': ('Current account balance, percent of GDP', 'Percent of GDP', 'WEO'),
    'GGXCNL_NGDP': ('General government net lending/borrowing', 'Percent of GDP', 'WEO'),
    'GGXWDG_NGDP': ('General government gross debt', 'Percent of GDP', 'WEO'),
    'LP': ('Population', 'Millions of people', 'WEO'),
    'LUR': ('Unemployment rate', 'Percent', 'WEO'),
    'NGDPD': ('GDP, current prices', 'Billions of U.S. dollars', 'WEO'),
    'NGDPDPC': ('GDP per capita, current prices', 'U.S. dollars per capita', 'WEO'),
    'NGDP_RPCH': ('Real GDP growth', 'Annual percent change', 'WEO'),
    'PCPIEPCH': ('Inflation rate, end of period consumer prices', 'Annual percent change', 'WEO'),
    'PCPIPCH': ('Inflation rate, average consumer prices', 'Annual percent change', 'WEO'),
    'PPPEX': ('Implied PPP conversion rate', 'National currency per international dollar', 'WEO'),
    'PPPGDP': ('GDP, current prices', 'Purchasing power parity; billions of international dollars', 'WEO'),
    'PPPPC': ('GDP per capita, current prices', 'Purchasing power parity; international dollars per capita', 'WEO'),
    'PPPSH': ('GDP based on PPP, share of world', 'Percent of World', 'WEO'),
    # --- FM: Fiscal Monitor (8) ---
    'GGCBP_G01_PGDP_PT': ('Cyclically adjusted primary balance', '% of Potential GDP', 'FM'),
    'GGCB_G01_PGDP_PT': ('Cyclically adjusted balance', '% of Potential GDP', 'FM'),
    'GGR_G01_GDP_PT': ('Revenue', '% of GDP', 'FM'),
    'GGXCNL_G01_GDP_PT': ('Net lending/borrowing (also referred as overall balance)', '% of GDP', 'FM'),
    'GGXONLB_G01_GDP_PT': ('Primary net lending/borrowing (also referred as primary balance)', '% of GDP', 'FM'),
    'GGXWDN_G01_GDP_PT': ('Net debt', '% of GDP', 'FM'),
    'G_XWDG_G01_GDP_PT': ('Gross debt position', '% of GDP', 'FM'),
    'G_X_G01_GDP_PT': ('Expenditure', '% of GDP', 'FM'),
    # --- GDD: Global Debt Database (10) ---
    'CG_DEBT_GDP': ('Central Government Debt', 'Percent of GDP', 'GDD'),
    'GG_DEBT_GDP': ('General Government Debt', 'Percent of GDP', 'GDD'),
    'HH_ALL': ('Household debt, all instruments', 'Percent of GDP', 'GDD'),
    'HH_LS': ('Household debt, loans and debt securities', 'Percent of GDP', 'GDD'),
    'NFC_ALL': ('Nonfinancial corporate debt, all instruments', 'Percent of GDP', 'GDD'),
    'NFC_LS': ('Nonfinancial corporate debt, loans and debt securities', 'Percent of GDP', 'GDD'),
    'NFPS_DEBT_GDP': ('Nonfinancial Public Sector Debt', 'Percent of GDP', 'GDD'),
    'PS_DEBT_GDP': ('Public Sector Debt', 'Percent of GDP', 'GDD'),
    'PVD_LS': ('Private debt, loans and debt securities', 'Percent of GDP', 'GDD'),
    'Privatedebt_all': ('Private debt, all instruments', 'Percent of GDP', 'GDD'),
    # --- ARA: Assessing Reserve Adequacy (4) ---
    'Reserves_ARA': ('Ratio of reserve/ARA metric', 'Unit', 'ARA'),
    'Reserves_M': ('Reserve/(Import/12)', 'Unit', 'ARA'),
    'Reserves_M2': ('Reserves/Broad Money', 'Unit', 'ARA'),
    'Reserves_STD': ('Reserves/Short-term Debt (STD)', 'Unit', 'ARA'),
    # --- DEBT: Historical Public Debt (FAD) (1) ---
    'DEBT1': ('Gross public debt (historical)', '% of GDP', 'DEBT'),
    # --- FPP: Public Finances in Modern History (8) ---
    'd': ('Gross public debt, percent of GDP', '% of GDP', 'FPP'),
    'exp': ('Government expenditure, percent of GDP', '% of GDP', 'FPP'),
    'ie': ('Interest paid on public debt, percent of GDP', '% of GDP', 'FPP'),
    'pb': ('Government primary balance, percent of GDP', '% of GDP', 'FPP'),
    'prim_exp': ('Government primary expenditure, percent of GDP', '% of GDP', 'FPP'),
    'rev': ('Government revenue, percent of GDP', '% of GDP', 'FPP'),
    'rgc': ('Real GDP growth rate, percent', '', 'FPP'),
    'rltir': ('Real long term government bond yield, percent', '', 'FPP'),
    # --- CF: Capital Flows in Developing Economies (18) ---
    'DebtA': ('Debt Securities Assets', 'Millions of US Dollars', 'CF'),
    'DebtForg': ('Debt Forgiveness', 'Millions of US Dollars', 'CF'),
    'DebtL': ('Debt Securities Liabilities', 'Millions of US Dollars', 'CF'),
    'Deriv': ('Financial Derivatives', 'Millions of US Dollars', 'CF'),
    'DirectAbroad': ('Direct Investment Abroad', 'Millions of US Dollars', 'CF'),
    'DirectIn': ('Direct Investment In Country', 'Millions of US Dollars', 'CF'),
    'EquityA': ('Equity Securities Assets', 'Millions of US Dollars', 'CF'),
    'EquityL': ('Equity Securities Liabilities', 'Millions of US Dollars', 'CF'),
    'GDP': ('Nominal GDP', 'Millions of US Dollars', 'CF'),
    'OtherA': ('Other Investment Assets', 'Millions of US Dollars', 'CF'),
    'OtherGov': ('Proxy for Official Other Investment Liabilities', 'Millions of US Dollars', 'CF'),
    'OtherL': ('Other Investment Liabilities', 'Millions of US Dollars', 'CF'),
    'Portfa': ('Portfolio Investment Assets', 'Millions of US Dollars', 'CF'),
    'Portfl': ('Portfolio Investment Liabilities', 'Millions of US Dollars', 'CF'),
    'PrivInexDI': ('Private Inflows excluding Direct Investment', 'Millions of US Dollars', 'CF'),
    'PrivInexDIGDP': ('Private Inflows excluding Direct Investment (% of GDP)', 'Percent', 'CF'),
    'PrivOutexDI': ('Private Outflows excluding Direct Investment', 'Millions of US Dollars', 'CF'),
    'PrivOutexDIGDP': ('Private Outflows excluding Direct Investment (% of GDP)', 'Percent', 'CF'),
    # --- CL: Wang-Jahan Capital Openness Index (18) ---
    'FM_ka': ('Financial Market Openness Index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_bo': ('Bond openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_cc': ('Commercial credit openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_ci': ('Collective investment openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_di': ('Direct investment openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_dr': ('Derivative investment openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_eq': ('Equity openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_fc': ('Financial credit openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_gu': ('Guarantee openness index (1=fully liberalized)', 'Units', 'CL'),
    'Ka_mm': ('Money market openness index (1=fully liberalized)', 'Units', 'CL'),
    'Nonres_ka': ('Nonresident Openness Index (1=fully liberalized)', 'Units', 'CL'),
    'Res_ka': ('Resident Openness Index (1=fully liberalized)', 'Units', 'CL'),
    'ka_in': ('Openness of Capital Inflows Index (1=fully liberalized)', 'Units', 'CL'),
    'ka_ldi': ('Direct investment liquidation openness index (1=fully liberalized)', 'Units', 'CL'),
    'ka_new': ('Overall Openness Index (all asset categories)', 'Units', 'CL'),
    'ka_out': ('Openness of Capital Outflows Index (1=fully liberalized)', 'Units', 'CL'),
    'ka_pct': ('Personal capital transaction openness index (1=fully liberalized)', 'Units', 'CL'),
    'ka_ret': ('Real estate capital transaction openness index (1=fully liberalized)', 'Units', 'CL'),
    # --- AFRREO: Sub-Saharan Africa Regional Economic Outlook (26) ---
    'BCA_GDP': ('External Current Account, Incl.Grants (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'BFD_GDP': ('Net Foreign Direct Investment (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'BM_GDP': ('Imports of Goods and Services (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'BRASS_MI': ('Reserves (Months of Imports)', 'Months of imports of goods and services', 'AFRREO'),
    'BT_GDP': ('Trade Balance (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'BX_GDP': ('Exports of Goods and Services (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'DG_GDP': ('External Debt, Official Debt, Debtor Based (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'ENEER': ('Nominal Effective Exchange Rates (2010=100)', 'Annual Average Index, 2010 = 100', 'AFRREO'),
    'EREER': ('Real Effective Exchange Rates (2010=100)', 'Annual Average Index, 2010 = 100', 'AFRREO'),
    'FDSAOP_GDP': ('Claims on Nonfinancial Private Sector (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'FDSAOP_PCH': ('Claims on Nonfinancial Private Sector (%)', 'Annual percent change', 'AFRREO'),
    'FMB_GDP': ('Broad Money (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'FMB_PCH': ('Broad Money Growth', 'Annual percent change', 'AFRREO'),
    'GGRXG_GDP': ('Government Revenue, Excluding Grants (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'GGXCNLXG_GDP': ('Overall Fiscal Balance, Excluding Grants (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'GGXCNL_GDP': ('Overall Fiscal Balance, Including Grants (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'GGXWDG_GDP': ('Government Debt (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'GGX_GDP': ('Government Expenditure (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'NGDPRPC_PCH': ('Real Per Capita GDP Growth', 'Annual percent change', 'AFRREO'),
    'NGDPXO_RPCH': ('Real Non-Oil GDP Growth', 'Annual percent change', 'AFRREO'),
    'NGDP_R_PCH': ('Real GDP Growth', 'Annual percent change', 'AFRREO'),
    'NGS_GDP': ('Gross National Savings (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'NI_GDP': ('Total Investment (% of GDP)', 'Percent of GDP', 'AFRREO'),
    'PCPIE_PCH': ('Consumer Prices, End of Period (Annual % Change)', 'Annual average percent change', 'AFRREO'),
    'PCPI_PCH': ('Consumer Prices, Average (Annual % Change)', 'Annual average percent change', 'AFRREO'),
    'TTT': ('Terms of Trade (Index, 2010 = 100)', 'Index, 2010 = 100', 'AFRREO'),
    # --- FR_FC: Fiscal Rules & Fiscal Councils (2) ---
    'FC_dummy': ('Fiscal Council Indicator', 'Index', 'FR_FC'),
    'FR_ind': ('Fiscal Rule Indicator', 'Index', 'FR_FC'),
    # --- GD: Gender Development & Budgeting (3) ---
    'GDI_TC': ('Gender Development Index (GDI) Time Consistent', 'Index', 'GD'),
    'GII_TC': ('Gender Inequality Index (GII) Time Consistent', 'Index', 'GD'),
    'GRB_dummy': ('Gender Budgeting Indicator', 'Index', 'GD'),
    # --- SPRLU: Export Diversification (14) ---
    'SITC1_0': ('Food and live animals', 'Index', 'SPRLU'),
    'SITC1_1': ('Beverages and tobacco', 'Index', 'SPRLU'),
    'SITC1_2': ('Crude materials, inedible, except fuels', 'Index', 'SPRLU'),
    'SITC1_3': ('Mineral fuels, lubricants and related materials', 'Index', 'SPRLU'),
    'SITC1_4': ('Animal and vegetable oils and fats', 'Index', 'SPRLU'),
    'SITC1_5': ('Chemicals', 'Index', 'SPRLU'),
    'SITC1_6': ('Manufact goods classified chiefly by material', 'Index', 'SPRLU'),
    'SITC1_7': ('Machinery and transport equipment', 'Index', 'SPRLU'),
    'SITC1_8': ('Miscellaneous manufactured articles', 'Index', 'SPRLU'),
    'SITC1_9': ('Commodity & transactions not classified accord to kind', 'Index', 'SPRLU'),
    'SITC1_total': ('Export Quality Index', 'Index', 'SPRLU'),
    'extensive': ('Extensive Margin', 'Index', 'SPRLU'),
    'intensive': ('Intensive Margin', 'Index', 'SPRLU'),
    'total_theil': ('Export Diversification Index', 'Index', 'SPRLU'),
    # --- AIPI: AI Preparedness Index (5) ---
    'AI_PI': ('AI Preparedness Index', 'Index', 'AIPI'),
    'DI': ('Digital Infrastructure', 'Index', 'AIPI'),
    'HCLMP': ('Human Capital and Labor Market Policies', 'Index', 'AIPI'),
    'IEI': ('Innovation and Economic Integration', 'Index', 'AIPI'),
    'RE': ('Regulation and Ethics', 'Index', 'AIPI'),
}

# dataset code -> (human name, latest source string)
DATASET_SOURCES = {
    'AFRREO': ('Sub-Saharan Africa Regional Economic Outlook', 'AFR Regional Economic Outlook (April 2026)'),
    'AIPI': ('AI Preparedness Index', 'AI Preparedness Index - April 2024'),
    'ARA': ('Assessing Reserve Adequacy (ARA)', 'Assessing Reserve Adequacy - ARA'),
    'CF': ('Capital Flows in Developing Economies', 'Capital Flows in Developing Economies'),
    'CL': ('Wang-Jahan Capital Openness Index', 'Wang-Jahan Index'),
    'DEBT': ('Historical Public Debt (FAD)', 'Fiscal Affairs Departmental Data'),
    'FM': ('Fiscal Monitor', 'Fiscal Monitor (April 2026)'),
    'FPP': ('Public Finances in Modern History', 'Public Finances in Modern History Database (Dec 2025)'),
    'FR_FC': ('Fiscal Rules & Fiscal Councils', 'Fiscal Rules and Fiscal Councils dataset (2025)'),
    'GD': ('Gender Development & Budgeting', 'Stotsky et al. (2016)'),
    'GDD': ('Global Debt Database', 'Global Debt Database (Sep 2025)'),
    'SPRLU': ('Export Diversification', 'IMF Export Diversification and Quality Database'),
    'WEO': ('World Economic Outlook', 'World Economic Outlook (April 2026)'),
}

# 129 analytical groups/aggregates (code -> label). Use as entities like
# countries. Note many "World" variants exist per dataset (WEOWORLD is the
# WEO world aggregate; "world"/"global" alias to WEOWORLD).
GROUPS = {
    'ADVEC': 'Advanced economies',
    'AEEUEJ': 'Adv econ excl US, Euro, Japan',
    'AFR': 'Africa (Analytical)',
    'ARAWORLD': 'World (ARA)',
    'AS5': 'ASEAN-5',
    'BOPWORLD': 'World (BOP)',
    'CCWORLD': 'World (Capital Flows)',
    'CEE': 'Central and Eastern Europe',
    'CEMAC': 'CEMAC',
    'CFAFZ': 'CFA Franc Zone',
    'CFWORLD': 'World (Capital Flows)',
    'CIS': 'Commonwealth of Independent States',
    'CISM': 'Commonwealth of Independent States and Mongolia',
    'COMESA': 'COMESA (SSA members)',
    'DA': 'Emerging and Developing Asia',
    'EAC': 'East African Community',
    'EAC-5': 'East African Community',
    'ECCU': 'Eastern Caribbean Currency Union',
    'ECOWAS': 'Economic Community of West African States',
    'EDE': 'Emerging and Developing Europe',
    'EEF': 'Export earnings: fuel',
    'EENF': 'Export earnings: nonfuel',
    'EME': 'Emerging market economies',
    'EU': 'European Union',
    'EUR': 'Europe',
    'EURO': 'Euro area',
    'EUROAREA': 'Euro area',
    'FADGDWORLD': 'All countries - Global Debt',
    'FAD_ADV': 'Advanced Economies (FAD)',
    'FAD_AFR': 'African Group (FAD)',
    'FAD_APD': 'Asia & Pacific Group (FAD)',
    'FAD_C1': 'Category I (FAD)',
    'FAD_C2': 'Category II (FAD)',
    'FAD_C3': 'Category III (FAD)',
    'FAD_C4': 'Category IV (FAD)',
    'FAD_C5': 'Category V (FAD)',
    'FAD_C6': 'Category VI (FAD)',
    'FAD_EMAsia': 'Emerging Asia (FAD)',
    'FAD_EMD': 'Emerging and Developing Countries (FAD)',
    'FAD_EME': 'Emerging Market (FAD)',
    'FAD_EUR': 'European Group (FAD)',
    'FAD_EuroArea': 'Euro Area (FAD)',
    'FAD_G20': 'G-20 (FAD)',
    'FAD_G20Adv': 'G-20 Advanced (FAD)',
    'FAD_G20Emg': 'G-20 Emerging (FAD)',
    'FAD_G7': 'G-7 (FAD)',
    'FAD_LIC': 'Low Income (FAD)',
    'FAD_MCD': 'Middle East and Central Asia Group (FAD)',
    'FAD_NG20': 'Non G-20 (FAD)',
    'FAD_NG7': 'Non G-7 (FAD)',
    'FAD_NOFAST': 'Non-Oil Fast (FAD)',
    'FAD_NOHIC': 'Non-Oil High Income (FAD)',
    'FAD_NOLIC': 'Non-Oil Low Income (FAD)',
    'FAD_NOMED': 'Non-Oil Medium (FAD)',
    'FAD_NOMIC': 'Non-Oil Middle Income (FAD)',
    'FAD_NOSLOW': 'Non-Oil Slow (FAD)',
    'FAD_OP': 'Oil Producers (FAD)',
    'FAD_OtherAdv': 'Other Advanced (FAD)',
    'FAD_Rest': 'Rest (FAD)',
    'FAD_WHD': 'Western Hemisphere Group (FAD)',
    'FAD_WORLD': 'World (FAD)',
    'FLERRC': 'Countries without conventional exchange rate pegs',
    'FM_AdvG20': 'Advanced G-20',
    'FM_EMEAsia': 'Emerging and Middle-Income Asia',
    'FM_EMEEU': 'Emerging and Middle-Income Europe',
    'FM_EMEG20': 'Emerging G-20',
    'FM_EMELA': 'Emerging and Middle-Income Latin America',
    'FM_EMEME': 'Emerging and Middle-Income MENA and Pakistan',
    'FM_EMG': 'Emerging Market and Middle-Income Economies',
    'FM_LIC': 'Low-Income Countries (FM)',
    'FM_LICAsia': 'Low-Income Developing Asia',
    'FM_LICLA': 'Low-Income Developing Latin America',
    'FM_LICO': 'Low-Income Developing Others',
    'FM_LICOP': 'Low-Income Developing Oil Producers',
    'FM_LICSSA': 'Low-Income Developing Sub-Saharan Africa',
    'FM_LIDC': 'Low-Income Developing Countries (FM)',
    'FRC': 'Countries in fragile and conflict-affected situations',
    'FR_FCWORLD': 'All countries - Fiscal Rules & Fiscal Councils',
    'FR_FC_ADV': 'Advanced Economies (FR_FC)',
    'FR_FC_EME': 'Emerging Market and Developing Economies (FR_FC)',
    'FR_FC_EU': 'European Union (FR_FC)',
    'FR_FC_NonEU': 'Non European Union (FR_FC)',
    'FXERRC': 'Countries with conventional exchange rate pegs',
    'GDWORLD': 'World (Global Debt)',
    'IIO': 'International Organizations',
    'LIC': 'Low-income countries',
    'LICXF': 'LICs excluding fragile/conflict-affected',
    'LL': 'Landlocked',
    'MAE': 'Major advanced economies (G7)',
    'MAF': 'Emerging Asia excl Japan incl NIEs',
    'MCA': 'EM and dev econ incl sel adv econ',
    'MDRI': 'MDRI countries',
    'ME': 'Middle East (Analytical)',
    'MECA': 'Middle East and Central Asia',
    'MENA': 'Middle East and North Africa',
    'MENAP': 'Middle East, North Africa, Afghanistan, and Pakistan',
    'MIC': 'Middle-income countries',
    'MIC854': 'MICs excluding Nigeria and South Africa',
    'NO824': 'Non-oil',
    'NONC872': 'Coastal',
    'NONRESINT': 'Non-resource-intensive countries',
    'OAE': 'Other advanced economies',
    'OEMDC': 'Emerging market and developing economies',
    'OEXP': 'Oil-exporting countries',
    'OIM808': 'Oil-importing countries excluding South Africa',
    'OIMP': 'Oil-importing countries',
    'OTH': 'Other Groups',
    'OXEN853': 'Oil-exporting countries excluding Nigeria',
    'PRGF': 'Countries eligible for PRGF',
    'RESINT': 'Resource-intensive countries',
    'SACU': 'SACU',
    'SADC': 'SADC',
    'SPR_FLIDC': 'Frontier LIDCs (median)',
    'SPR_GD_AM': 'Advanced Economies (SPR)',
    'SPR_GD_EM': 'Emerging Markets (SPR)',
    'SPR_GD_LIDC': 'Low Income Developing Countries (SPR)',
    'SPR_HIC': 'High Income Countries (median)',
    'SPR_LIDC': 'Low-Income Developing Countries (median)',
    'SSA': 'Sub-Saharan Africa',
    'SSENS': 'SSA excluding Nigeria and South Africa',
    'SSXSD': 'Sub-Saharan Africa, excluding South Sudan',
    'SSXZ': 'SSA excluding Zimbabwe',
    'WAEMU': 'WAEMU',
    'WE': 'Latin America and the Caribbean',
    'WEOWORLD': 'World',
    'gb_othersource': 'Other countries (gender budgeting)',
    'gbcasestudy': 'Gender budgeting case-study country',
    'gbtier_1': 'Prominent gender budgeting countries',
    'gbtier_2': 'Other gender budgeting countries',
}

# 241 countries/economies (ISO3 -> name)
COUNTRIES = {
    'ABW': 'Aruba',
    'AFG': 'Afghanistan',
    'AGO': 'Angola',
    'AIA': 'Anguilla',
    'ALB': 'Albania',
    'AND': 'Andorra',
    'ARE': 'United Arab Emirates',
    'ARG': 'Argentina',
    'ARM': 'Armenia',
    'ASM': 'American Samoa',
    'ATG': 'Antigua and Barbuda',
    'ATI': 'Antigua and Barbuda (ATI)',
    'ATL': 'Atlantic aggregate',
    'AUS': 'Australia',
    'AUT': 'Austria',
    'AZE': 'Azerbaijan',
    'BDI': 'Burundi',
    'BEL': 'Belgium',
    'BEN': 'Benin',
    'BES': 'Bonaire, Sint Eustatius and Saba',
    'BFA': 'Burkina Faso',
    'BGD': 'Bangladesh',
    'BGR': 'Bulgaria',
    'BHR': 'Bahrain',
    'BHS': 'Bahamas, The',
    'BIH': 'Bosnia and Herzegovina',
    'BLR': 'Belarus',
    'BLZ': 'Belize',
    'BMU': 'Bermuda',
    'BOL': 'Bolivia',
    'BRA': 'Brazil',
    'BRB': 'Barbados',
    'BRN': 'Brunei Darussalam',
    'BTN': 'Bhutan',
    'BWA': 'Botswana',
    'CAF': 'Central African Republic',
    'CAN': 'Canada',
    'CHE': 'Switzerland',
    'CHI': 'Channel Islands',
    'CHL': 'Chile',
    'CHN': "China, People's Republic of",
    'CIV': "Côte d'Ivoire",
    'CMR': 'Cameroon',
    'COD': 'Congo, Dem. Rep. of the',
    'COG': 'Congo, Republic of',
    'COK': 'Cook Islands',
    'COL': 'Colombia',
    'COM': 'Comoros',
    'CPV': 'Cabo Verde',
    'CRI': 'Costa Rica',
    'CUB': 'Cuba',
    'CUW': 'Curacao',
    'CYM': 'Cayman Islands',
    'CYP': 'Cyprus',
    'CZE': 'Czech Republic',
    'DEU': 'Germany',
    'DJI': 'Djibouti',
    'DMA': 'Dominica',
    'DNK': 'Denmark',
    'DOM': 'Dominican Republic',
    'DZA': 'Algeria',
    'ECU': 'Ecuador',
    'EGY': 'Egypt',
    'ERI': 'Eritrea',
    'ESH': 'Western Sahara',
    'ESP': 'Spain',
    'EST': 'Estonia',
    'ETH': 'Ethiopia',
    'FIN': 'Finland',
    'FJI': 'Fiji',
    'FLK': 'Falkland Islands',
    'FRA': 'France',
    'FRO': 'Faeroe Islands',
    'FSM': 'Micronesia, Fed. States of',
    'GAB': 'Gabon',
    'GBR': 'United Kingdom',
    'GEO': 'Georgia',
    'GHA': 'Ghana',
    'GIB': 'Gibraltar',
    'GIN': 'Guinea',
    'GLP': 'Guadeloupe',
    'GMB': 'Gambia, The',
    'GNB': 'Guinea-Bissau',
    'GNQ': 'Equatorial Guinea',
    'GRC': 'Greece',
    'GRD': 'Grenada',
    'GRL': 'Greenland',
    'GTM': 'Guatemala',
    'GUF': 'French Guiana',
    'GUM': 'Guam',
    'GUY': 'Guyana',
    'HKG': 'Hong Kong SAR',
    'HND': 'Honduras',
    'HRV': 'Croatia',
    'HTI': 'Haiti',
    'HUN': 'Hungary',
    'IDN': 'Indonesia',
    'IMY': 'Isle of Man',
    'IND': 'India',
    'IOT': 'British Indian Ocean Territories',
    'IRL': 'Ireland',
    'IRN': 'Iran',
    'IRQ': 'Iraq',
    'ISL': 'Iceland',
    'ISR': 'Israel',
    'ITA': 'Italy',
    'JAM': 'Jamaica',
    'JOR': 'Jordan',
    'JPN': 'Japan',
    'KAZ': 'Kazakhstan',
    'KEN': 'Kenya',
    'KGZ': 'Kyrgyz Republic',
    'KHM': 'Cambodia',
    'KIR': 'Kiribati',
    'KNA': 'Saint Kitts and Nevis',
    'KOR': 'Korea, Republic of',
    'KOS': 'Kosovo',
    'KWT': 'Kuwait',
    'LAO': 'Lao P.D.R.',
    'LBN': 'Lebanon',
    'LBR': 'Liberia',
    'LBY': 'Libya',
    'LCA': 'Saint Lucia',
    'LIE': 'Liechtenstein',
    'LKA': 'Sri Lanka',
    'LSO': 'Lesotho',
    'LTU': 'Lithuania',
    'LUX': 'Luxembourg',
    'LVA': 'Latvia',
    'MAC': 'Macao SAR',
    'MAR': 'Morocco',
    'MCO': 'Monaco',
    'MDA': 'Moldova',
    'MDG': 'Madagascar',
    'MDV': 'Maldives',
    'MEX': 'Mexico',
    'MFX': 'Saint Martin',
    'MHL': 'Marshall Islands',
    'MKD': 'North Macedonia',
    'MLI': 'Mali',
    'MLT': 'Malta',
    'MMR': 'Myanmar',
    'MNE': 'Montenegro',
    'MNG': 'Mongolia',
    'MNP': 'Northern Mariana Islands',
    'MOZ': 'Mozambique',
    'MRT': 'Mauritania',
    'MSR': 'Montserrat',
    'MTQ': 'Martinique',
    'MUS': 'Mauritius',
    'MWI': 'Malawi',
    'MYS': 'Malaysia',
    'MYT': 'Mayotte',
    'NAM': 'Namibia',
    'NCL': 'New Caledonia',
    'NER': 'Niger',
    'NGA': 'Nigeria',
    'NIC': 'Nicaragua',
    'NIU': 'Niue',
    'NLD': 'Netherlands',
    'NOR': 'Norway',
    'NPL': 'Nepal',
    'NRU': 'Nauru',
    'NZL': 'New Zealand',
    'OMN': 'Oman',
    'PAK': 'Pakistan',
    'PAN': 'Panama',
    'PCN': 'Pitcairn',
    'PER': 'Peru',
    'PHL': 'Philippines',
    'PLW': 'Palau',
    'PNG': 'Papua New Guinea',
    'POL': 'Poland',
    'PRI': 'Puerto Rico',
    'PRK': "Korea, Dem. People's Rep. of",
    'PRT': 'Portugal',
    'PRY': 'Paraguay',
    'PYF': 'French Polynesia',
    'QAT': 'Qatar',
    'REU': 'Reunion',
    'ROU': 'Romania',
    'RUS': 'Russian Federation',
    'RWA': 'Rwanda',
    'SAU': 'Saudi Arabia',
    'SDN': 'Sudan',
    'SEN': 'Senegal',
    'SGP': 'Singapore',
    'SHN': 'Saint Helena',
    'SJM': 'Svalbard and Jan Mayen Islands',
    'SLB': 'Solomon Islands',
    'SLE': 'Sierra Leone',
    'SLV': 'El Salvador',
    'SMR': 'San Marino',
    'SOM': 'Somalia',
    'SPM': 'Saint-Pierre and Miquelon',
    'SRB': 'Serbia',
    'SSD': 'South Sudan, Republic of',
    'STP': 'São Tomé and Príncipe',
    'SUR': 'Suriname',
    'SVK': 'Slovak Republic',
    'SVN': 'Slovenia',
    'SWE': 'Sweden',
    'SWZ': 'Eswatini',
    'SXM': 'Sint Maarten',
    'SYC': 'Seychelles',
    'SYR': 'Syria',
    'TCA': 'Turks and Caicos Islands',
    'TCD': 'Chad',
    'TGO': 'Togo',
    'THA': 'Thailand',
    'TJK': 'Tajikistan',
    'TKL': 'Tokelau',
    'TKM': 'Turkmenistan',
    'TLS': 'Timor-Leste',
    'TON': 'Tonga',
    'TTO': 'Trinidad and Tobago',
    'TUN': 'Tunisia',
    'TUR': 'Türkiye, Republic of',
    'TUV': 'Tuvalu',
    'TWN': 'Taiwan Province of China',
    'TZA': 'Tanzania',
    'UGA': 'Uganda',
    'UKR': 'Ukraine',
    'URY': 'Uruguay',
    'USA': 'United States',
    'UVK': 'Kosovo',
    'UZB': 'Uzbekistan',
    'VAT': 'Holy See',
    'VCT': 'Saint Vincent and the Grenadines',
    'VEN': 'Venezuela',
    'VGB': 'British Virgin Islands',
    'VIR': 'United States Virgin Islands',
    'VNM': 'Vietnam',
    'VUT': 'Vanuatu',
    'WBG': 'West Bank and Gaza',
    'WLF': 'Wallis and Futuna Islands',
    'WSM': 'Samoa',
    'YEM': 'Yemen',
    'ZAF': 'South Africa',
    'ZMB': 'Zambia',
    'ZWE': 'Zimbabwe',
}
