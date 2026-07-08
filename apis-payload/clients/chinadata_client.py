"""ChinaData.live -- China official-statistics aggregator client.

Sandbox name: ``chinadata_client``.

Thin transport over the chinadata.live public JSON API (v2): ~320 cleaned
datasets built from NBS / World Bank / GACC official sources (GDP, CPI,
population, energy, technology, transport, ...) plus monthly GACC customs
trade data by partner country and HS product code.

Base URL: ``https://chinadata.live/api/v2``
Auth: none (no key, no registration; fair-use ~100 req/min).
Transport: Bucket C -- plain ``requests`` (no GS proxy).

The wrapper absorbs the mechanics PRISM should not have to remember:

* Country -> URL-slug mapping for the trade endpoints (``"United States"``
  -> ``united-states``; ``"US"``/``"UK"``/``"South Korea"`` aliases).
* The response envelope (``{"success": true, "data": ...}``) is unwrapped;
  API-level failures raise ``ChinaDataError``.
* Value coercion to float. Suppressed values (negative monthly trade prints
  the source flags for review) arrive as null and STAY ``None``; the raw
  value + QA flags remain available in the response metadata.
* The upstream unit inconsistency between trade endpoint families: the
  country endpoint publishes USD THOUSAND while the HS endpoints publish
  full USD. The wrapper normalizes everything to FULL USD, so every trade
  value this client returns is plain dollars.
* Dataset ids resolved case-insensitively with a live catalog cache.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union

import requests


BASE_URL = "https://chinadata.live/api/v2"
DEFAULT_TIMEOUT = 90

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "PRISM-chinadata_client/1.0"})


class ChinaDataError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# HS chapter (2-digit) -> short English name; attached to breakdown rows as
# hs_label so PRISM never has to map chapter codes by hand.
HS_CHAPTERS = {
    "01": "Live animals", "02": "Meat", "03": "Fish & seafood",
    "04": "Dairy, eggs, honey", "05": "Other animal products",
    "06": "Live plants", "07": "Vegetables", "08": "Fruit & nuts",
    "09": "Coffee, tea, spices", "10": "Cereals",
    "11": "Milling products", "12": "Oil seeds & grains",
    "13": "Lac, gums, resins", "14": "Vegetable plaiting materials",
    "15": "Fats & oils", "16": "Prepared meat & fish",
    "17": "Sugars", "18": "Cocoa", "19": "Cereal & flour preparations",
    "20": "Prepared vegetables & fruit", "21": "Misc edible preparations",
    "22": "Beverages & spirits", "23": "Food residues, animal feed",
    "24": "Tobacco", "25": "Salt, sulphur, stone, cement",
    "26": "Ores, slag, ash", "27": "Mineral fuels & oils",
    "28": "Inorganic chemicals", "29": "Organic chemicals",
    "30": "Pharmaceuticals", "31": "Fertilisers",
    "32": "Tanning, dyes, paints", "33": "Perfumery & cosmetics",
    "34": "Soap, waxes, polishes", "35": "Albuminoids, glues, enzymes",
    "36": "Explosives, matches", "37": "Photographic goods",
    "38": "Misc chemical products", "39": "Plastics",
    "40": "Rubber", "41": "Raw hides & leather",
    "42": "Leather articles", "43": "Furskins",
    "44": "Wood", "45": "Cork", "46": "Straw & basketware",
    "47": "Wood pulp", "48": "Paper & paperboard",
    "49": "Printed books & media", "50": "Silk",
    "51": "Wool & animal hair", "52": "Cotton",
    "53": "Other vegetable fibres", "54": "Man-made filaments",
    "55": "Man-made staple fibres", "56": "Wadding, felt, ropes",
    "57": "Carpets", "58": "Special woven fabrics",
    "59": "Coated/laminated textiles", "60": "Knitted fabrics",
    "61": "Knitted apparel", "62": "Woven apparel",
    "63": "Other textiles, worn clothing", "64": "Footwear",
    "65": "Headgear", "66": "Umbrellas & sticks",
    "67": "Feathers & artificial flowers", "68": "Stone & cement articles",
    "69": "Ceramics", "70": "Glass",
    "71": "Pearls, precious stones & metals", "72": "Iron & steel",
    "73": "Iron & steel articles", "74": "Copper",
    "75": "Nickel", "76": "Aluminium", "78": "Lead",
    "79": "Zinc", "80": "Tin", "81": "Other base metals",
    "82": "Tools & cutlery", "83": "Misc base-metal articles",
    "84": "Machinery & mechanical appliances",
    "85": "Electrical machinery & electronics",
    "86": "Railway equipment", "87": "Vehicles",
    "88": "Aircraft & spacecraft", "89": "Ships & boats",
    "90": "Optical, medical & precision instruments",
    "91": "Clocks & watches", "92": "Musical instruments",
    "93": "Arms & ammunition", "94": "Furniture, lighting, prefab",
    "95": "Toys, games, sports equipment", "96": "Misc manufactures",
    "97": "Art & antiques",
}


# Country aliases -> chinadata.live slugs (beyond simple slugification).
COUNTRY_ALIASES = {
    "US": "united-states", "USA": "united-states",
    "AMERICA": "united-states",
    "UK": "united-kingdom", "GB": "united-kingdom",
    "BRITAIN": "united-kingdom",
    "KOREA": "south-korea", "KR": "south-korea",
    "REPUBLIC OF KOREA": "south-korea",
    "UAE": "united-arab-emirates",
    "RUSSIA": "russia", "RU": "russia",
    "DE": "germany", "JP": "japan", "FR": "france", "IT": "italy",
    "IN": "india", "AU": "australia", "BR": "brazil", "CA": "canada",
    "MX": "mexico", "VN": "vietnam", "TH": "thailand", "SG": "singapore",
    "MY": "malaysia", "ID": "indonesia", "PH": "philippines",
    "NL": "netherlands", "ES": "spain", "SA": "saudi-arabia",
}


def _slugify_country(country: str) -> str:
    up = str(country).strip().upper()
    if up in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[up]
    slug = re.sub(r"[^a-z0-9]+", "-", str(country).strip().lower())
    return slug.strip("-")


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def _request(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{BASE_URL}/{path.lstrip('/')}"
    resp = _SESSION.get(url, params=params or {}, timeout=DEFAULT_TIMEOUT)
    if resp.status_code == 404:
        raise ChinaDataError(
            f"not found: {url} (dataset/country/HS code not in the public "
            "snapshot; check list_datasets()/search_datasets())"
        )
    if resp.status_code >= 400:
        raise ChinaDataError(
            f"ChinaData API HTTP {resp.status_code} for {url}: "
            f"{resp.text[:300]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise ChinaDataError(
            f"ChinaData API returned non-JSON: {resp.text[:200]}"
        ) from e
    if isinstance(data, dict) and data.get("success") is False:
        raise ChinaDataError(f"ChinaData API error: {str(data)[:300]}")
    return data


def _coerce_points(points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Coerce every numeric-looking field to float. Most datasets are
    ``{date, value}``; some (e.g. china-trade-monthly) carry several numeric
    columns as strings."""
    out = []
    for p in points or []:
        row = dict(p)
        for k, v in row.items():
            if k == "date" or v is None or isinstance(v, (int, float)):
                continue
            if isinstance(v, str):
                try:
                    row[k] = float(v)
                except ValueError:
                    pass
        out.append(row)
    return out


_COUNTRY_TRADE_KEYS = ("exports", "imports", "balance")


def _scale_country_trade(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize the country endpoint's USD-thousand values to FULL USD
    (monthly rows + HS-chapter breakdowns). Suppressed ``None`` values and
    the QA metadata (``suppressed_values`` raw prints) are left untouched."""
    for row in payload.get("monthly") or []:
        for k in _COUNTRY_TRADE_KEYS:
            if row.get(k) is not None:
                row[k] = float(row[k]) * 1000.0
    for side in ("export_breakdown", "import_breakdown"):
        for row in payload.get(side) or []:
            for k in ("val_month", "val_ytd"):
                if row.get(k) is not None:
                    row[k] = float(row[k]) * 1000.0
            code = str(row.get("hs_code", ""))
            row["hs_label"] = HS_CHAPTERS.get(code[:2], code)
    return payload


def _filter_since(rows: List[Dict[str, Any]],
                  since: Optional[str]) -> List[Dict[str, Any]]:
    """Keep monthly rows at or after ``since`` ("2022" or "2022-06")."""
    if not since:
        return rows
    s = str(since)
    y = int(s.split("-")[0])
    m = int(s.split("-")[1]) if "-" in s else 1
    cutoff = y * 100 + m
    out = []
    for r in rows:
        if isinstance(r.get("month"), str) and "-" in r["month"]:
            parts = r["month"].split("-")
            key = int(parts[0]) * 100 + int(parts[1])
        elif "year" in r and "month" in r:
            key = int(r["year"]) * 100 + int(r["month"])
        else:
            out.append(r)
            continue
        if key >= cutoff:
            out.append(r)
    return out


# --------------------------------------------------------------------------
# Datasets
# --------------------------------------------------------------------------

_CATALOG_CACHE: Optional[List[Dict[str, Any]]] = None


def list_datasets(
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List all datasets (metadata only, no data points; cached).

    Each row: ``id``, ``title``, ``category``, ``description``, ``source``,
    ``unit``, ``frequency``, ``tags``. ``category`` filters exactly
    (case-insensitive; e.g. ``"economy"``, ``"energy"``, ``"technology"``,
    ``"transport"``); ``search`` filters on id/title/description substring.
    """
    global _CATALOG_CACHE
    if _CATALOG_CACHE is None:
        data = _request("datasets")
        _CATALOG_CACHE = data.get("data", [])
    rows = list(_CATALOG_CACHE)
    if category:
        c = category.lower()
        rows = [r for r in rows if (r.get("category") or "").lower() == c]
    if search:
        q = search.lower()
        rows = [
            r for r in rows
            if q in (r.get("id") or "").lower()
            or q in (r.get("title") or "").lower()
            or q in (r.get("description") or "").lower()
        ]
    return rows


def search_datasets(query: str) -> List[Dict[str, Any]]:
    """Server-side full-text search across dataset titles, descriptions,
    and tags via ``/search``."""
    data = _request("search", {"q": query})
    return data.get("data", [])


def get_dataset(dataset_id: str) -> Dict[str, Any]:
    """Fetch one dataset with metadata AND all data points via
    ``/data/<id>``.

    Returns the dataset dict: ``id``, ``title``, ``category``, ``unit``,
    ``frequency``, ``source``, ``description``, and ``data`` = list of
    ``{date, value}`` points (value coerced to float; dates are strings --
    ``"2023"`` yearly, ``"2023-05"`` monthly). Read ``unit`` before
    interpreting magnitudes (many NBS series are "100 Million CNY").
    """
    data = _request(f"data/{str(dataset_id).strip().lower()}")
    ds = data.get("data", {})
    ds["data"] = _coerce_points(ds.get("data", []))
    return ds


def get_series(dataset_id: str) -> List[Dict[str, Any]]:
    """Just the data points of a dataset: ``[{date, value}, ...]``."""
    return get_dataset(dataset_id).get("data", [])


# --------------------------------------------------------------------------
# Trade (GACC monthly customs data)
# --------------------------------------------------------------------------

_TRADE_COUNTRIES_CACHE: Optional[List[Dict[str, Any]]] = None
_HS_CODES_CACHE: Optional[List[Dict[str, Any]]] = None


def list_trade_countries(search: Optional[str] = None) -> List[Dict[str, Any]]:
    """The exact partner-country universe of the trade endpoints via
    ``/trade/countries`` (~106 partners; cached).

    Each row: ``slug`` (what the trade endpoints take), ``name``,
    ``first_month``, ``latest_month``, ``total_months``, ``hs2_codes``,
    ``status``. ``search`` filters on name/slug substring. Use this instead
    of guessing whether a partner is covered.
    """
    global _TRADE_COUNTRIES_CACHE
    if _TRADE_COUNTRIES_CACHE is None:
        data = _request("trade/countries")
        _TRADE_COUNTRIES_CACHE = data.get("countries", [])
    rows = list(_TRADE_COUNTRIES_CACHE)
    if search:
        q = search.lower()
        rows = [r for r in rows
                if q in (r.get("name") or "").lower()
                or q in (r.get("slug") or "").lower()]
    return rows


def list_hs_codes(
    search: Optional[str] = None,
    *,
    flow: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """The exact curated HS-product universe of ``get_hs_trade`` via
    ``/trade/hs-codes`` (~130 products/chapters; cached).

    Each row: ``hs_code``, ``flow`` ("export"/"import" -- the flow that
    product page carries), ``commodity_name``, ``first_month``,
    ``latest_month``. ``search`` filters on code/name substring; ``flow``
    filters exactly. Any 2-digit chapter also works with ``get_hs_trade``
    even if not listed here; this is the curated 6/8-digit product set.
    """
    global _HS_CODES_CACHE
    if _HS_CODES_CACHE is None:
        data = _request("trade/hs-codes")
        _HS_CODES_CACHE = data.get("codes", [])
    rows = list(_HS_CODES_CACHE)
    if flow:
        f = flow.lower()
        rows = [r for r in rows if (r.get("flow") or "").lower() == f]
    if search:
        q = search.lower()
        rows = [r for r in rows
                if q in (r.get("hs_code") or "")
                or q in (r.get("commodity_name") or "").lower()]
    return rows


def get_country_trade(
    country: str,
    *,
    full_breakdown: bool = False,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """China's monthly trade with one partner via ``/trade/country/<slug>``.

    Values are normalized to **full USD**. Returns:

    * ``monthly`` -- ``[{year, month, exports, imports, balance}, ...]``
      (exports = China's exports TO the partner). A ``None`` value means
      the source suppressed a flagged print (see ``suppressed_values``).
    * ``export_breakdown`` / ``import_breakdown`` -- latest-month HS-chapter
      composition: ``[{hs_code, val_month, val_ytd}, ...]`` (full USD).
    * ``coverage``, ``latest_period``, ``source``, ``qa_flags``.

    ``full_breakdown=True`` adds compact per-month breakdown rows
    (``breakdown=full``). ``since`` trims ``monthly`` to periods >= the
    given ``"YYYY"`` / ``"YYYY-MM"``.
    """
    slug = _slugify_country(country)
    params = {"breakdown": "full"} if full_breakdown else None
    payload = _scale_country_trade(_request(f"trade/country/{slug}", params))
    if since:
        payload["monthly"] = _filter_since(payload.get("monthly") or [],
                                           since)
    return payload


def get_hs_trade(
    hs_code: Union[str, int],
    *,
    flow: str = "export",
    period: str = "all",
    limit: int = 20,
    since: Optional[str] = None,
) -> Dict[str, Any]:
    """China's trade in one HS product/chapter via ``/trade/hs/<code>``.

    ``hs_code``: 2-digit chapter (``"85"``), or curated HS6/HS8 product
    (``"850760"`` lithium-ion batteries). ``flow``: ``"export"`` or
    ``"import"`` (product coverage varies -- the response's
    ``available_flows`` says what exists). ``period``: ``"all"`` or a year.
    ``limit``: partner-ranking rows (public cap 20). ``since`` trims
    ``monthly`` to periods >= ``"YYYY"`` / ``"YYYY-MM"``.

    Returns ``monthly`` (total trade in the product; ``value_usd`` plus a
    flow-named alias column), ``top_partners`` (cumulative over ``period``)
    / ``latest_partners`` (latest month only), ``growth_countries`` (YoY
    movers), ``commodity`` (name), ``years``, ``coverage``. All values
    full USD.
    """
    params = {"flow": flow, "period": period, "limit": int(limit)}
    payload = _request(f"trade/hs/{str(hs_code).strip()}", params)
    if since:
        payload["monthly"] = _filter_since(payload.get("monthly") or [],
                                           since)
    return payload


def get_hs_country_trade(
    hs_code: Union[str, int],
    country: str,
    *,
    period: str = "all",
) -> Dict[str, Any]:
    """One HS product x one partner country via
    ``/trade/hs/<code>/country/<slug>`` (monthly bilateral values, USD
    thousand).

    Coverage is SPARSE: this endpoint serves only curated "HS-country
    opportunity pages", and most product x country pairs are not in the
    public snapshot (clean ``ChinaDataError`` "not found"). For bilateral
    composition, prefer ``get_country_trade(...)['export_breakdown']``
    (latest-month HS chapters) or ``get_hs_trade(...)['top_partners']``
    (partner ranking for a product).
    """
    slug = _slugify_country(country)
    return _request(
        f"trade/hs/{str(hs_code).strip()}/country/{slug}",
        {"period": period},
    )


# --------------------------------------------------------------------------
# DataFrame helpers
# --------------------------------------------------------------------------

def to_dataframe(data: Union[List[Dict[str, Any]], Dict[str, Any]]):
    """Convert client output to a pandas DataFrame.

    Accepts: a dataset dict from ``get_dataset`` (uses its ``data`` points;
    adds a numeric ``time`` column), a list of ``{date, value}`` points, or
    a list of trade ``monthly`` rows (``{year, month, exports, imports,
    balance}`` -- adds a ``period`` string and numeric ``time``).
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("to_dataframe requires pandas") from e

    if isinstance(data, dict):
        data = data.get("data", [])
    if not data:
        return pd.DataFrame()

    df = pd.DataFrame(data)
    if "month" in df.columns and df["month"].astype(str).str.contains("-").any():
        # HS-endpoint monthly rows: month is already "YYYY-MM"
        df["period"] = df["month"].astype(str)
        parts = df["period"].str.split("-", expand=True)
        df["time"] = (parts[0].astype(int)
                      + (parts[1].astype(int) - 1) / 12.0)
        return df.sort_values("time")
    if {"year", "month"}.issubset(df.columns):
        df["period"] = (df["year"].astype(int).astype(str) + "-"
                        + df["month"].astype(int).astype(str).str.zfill(2))
        df["time"] = df["year"].astype(int) + (df["month"].astype(int) - 1) / 12.0
        return df.sort_values("time")
    if "date" in df.columns:
        def conv(s: str):
            s = str(s)
            try:
                if "-" in s:
                    y, m = s.split("-")[:2]
                    return int(y) + (int(m) - 1) / 12.0
                return float(s)
            except (TypeError, ValueError):
                return float("nan")
        df["time"] = df["date"].map(conv)
        return df.sort_values("time")
    return df


__all__ = [
    "BASE_URL",
    "ChinaDataError",
    "COUNTRY_ALIASES",
    "HS_CHAPTERS",
    "list_datasets",
    "search_datasets",
    "get_dataset",
    "get_series",
    "list_trade_countries",
    "list_hs_codes",
    "get_country_trade",
    "get_hs_trade",
    "get_hs_country_trade",
    "to_dataframe",
]
