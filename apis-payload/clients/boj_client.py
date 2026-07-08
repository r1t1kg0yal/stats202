"""Bank of Japan Time-Series Data Search -- API client.

Sandbox name: ``boj_client``.

Thin transport over the BOJ Time-Series Data Search API (three endpoints:
``/getDataCode``, ``/getDataLayer``, ``/getMetadata``). Covers every series
in the BOJ statistical warehouse: policy/money-market rates, FX, monetary
base and money stock, BOJ accounts, loans/deposits, TANKAN, corporate goods
and services prices, flow of funds, balance of payments.

Base URL: ``https://www.stat-search.boj.or.jp/api/v1``
Auth: none (anonymous public service).
Transport: Bucket C -- plain ``requests`` (no GS proxy).

The wrapper absorbs the mechanics PRISM should not have to remember:

* Per-frequency date grammar. Parameters take ``YYYY`` (annual/fiscal),
  ``YYYYHH`` (half-year), ``YYYYQQ`` (quarter), ``YYYYMM`` (month -- ALSO
  used for weekly/daily starts); output dates come back as ints in yet
  another per-frequency shape. The wrapper accepts friendly strings
  ("2024", "2024-Q2", "2024-05") and normalizes output dates to ISO-style
  strings ("2024", "2024-Q2", "2024-05", "2024-05-17").
* Pagination: 250 series / 60,000 datapoints per request, resumed via
  NEXTPOSITION -> STARTPOSITION. ``get_data`` / ``get_layer`` auto-paginate.
* The series-code vs time-series-code trap: search-screen codes carry a
  ``DB'`` prefix (``IR01'MADR1Z@D``) that the API REJECTS -- the wrapper
  strips it.
* STATUS/MESSAGE error envelope -> ``BOJError``; missing values arrive as
  JSON null and stay ``None``.
* An embedded database registry (the ~50 DB codes from the API manual) plus
  a curated catalog of verified headline series codes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

import requests


BASE_URL = "https://www.stat-search.boj.or.jp/api/v1"
DEFAULT_TIMEOUT = 90
MAX_CODES_PER_REQUEST = 250

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "PRISM-boj_client/1.0",
    "Accept-Encoding": "gzip",
})


class BOJError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# --------------------------------------------------------------------------
# Database registry (DB code -> description), from the API manual.
# --------------------------------------------------------------------------

DATABASES: Dict[str, str] = {
    # Interest rates on deposits and loans
    "IR01": "Basic discount / basic loan rate (official discount rate)",
    "IR02": "Average interest rates posted at financial institutions by deposit type",
    "IR03": "Average interest rates on time deposits by term",
    "IR04": "Average contract interest rates on loans and discounts",
    # Financial markets
    "FM01": "Uncollateralized overnight call rate (daily)",
    "FM02": "Short-term money market rates (monthly)",
    "FM03": "Amounts outstanding in short-term money market",
    "FM04": "Amounts outstanding in the call money market",
    "FM05": "Issuance, redemption, outstanding of public and corporate bonds",
    "FM06": "Trading of interest-bearing government bonds by purchaser",
    "FM07": "(Reference) Government bond sales over the counter (through 2004)",
    "FM08": "Foreign exchange rates (USD/JPY, EUR/USD, yen index)",
    "FM09": "Effective exchange rates (nominal / real)",
    # Payment and settlement
    "PS01": "Payment and settlement systems",
    "PS02": "Basic figures on fails",
    # Money, deposits and loans
    "MD01": "Monetary base",
    "MD02": "Money stock (M1/M2/M3, broadly-defined liquidity)",
    "MD03": "Monetary survey",
    "MD04": "(Reference) Changes in money stock (M2+CDs) and credit",
    "MD05": "Currency in circulation",
    "MD06": "Sources of changes in BOJ current account balances and market operations",
    "MD07": "Reserves",
    "MD08": "BOJ current account balances by sector",
    "MD09": "Monetary base and the Bank of Japan's transactions",
    "MD10": "Amounts outstanding of deposits by depositor",
    "MD11": "Deposits, vault cash, and loans and bills discounted",
    "MD12": "Deposits, vault cash, loans by prefecture (domestically licensed banks)",
    "MD13": "Principal figures of financial institutions",
    "MD14": "Time deposits: amounts outstanding and new deposits by maturity",
    "LA01": "Loans and bills discounted by sector",
    "LA02": "Loans and discounts by the Bank of Japan",
    "LA03": "Outstanding of loans (others)",
    "LA04": "Commitment lines extended by Japanese banks",
    "LA05": "Senior loan officer opinion survey (large Japanese banks)",
    # Balance sheets
    "BS01": "Bank of Japan accounts",
    "BS02": "Financial institutions accounts",
    # Flow of funds
    "FF": "Flow of funds accounts",
    # Other BOJ statistics
    "OB01": "BOJ transactions with the government",
    "OB02": "Collateral accepted by the Bank of Japan",
    # TANKAN
    "CO": "TANKAN (Short-term economic survey of enterprises)",
    # Prices
    "PR01": "Corporate Goods Price Index (CGPI)",
    "PR02": "Services Producer Price Index (SPPI)",
    "PR03": "Input-Output Price Index of manufacturing by sector (IOPI)",
    "PR04": "Final Demand-Intermediate Demand (FD-ID) price indexes",
    # Public finance
    "PF01": "Treasury receipts and payments",
    "PF02": "National government debt",
    # BOP and BIS-related
    "BP01": "Balance of payments",
    "BIS": "BIS locational / consolidated banking statistics in Japan",
    "DER": "Regular derivatives market statistics in Japan",
    # Others
    "OT": "Others",
}


# --------------------------------------------------------------------------
# Curated catalog of verified headline series.
#   db    : DB name the code lives in
#   codes : one or more series codes (verified live on build)
#   freq  : native frequency letter (D/W/M/Q/S/A)
#   desc  : one-line description
# --------------------------------------------------------------------------

CATALOG: Dict[str, Dict[str, Any]] = {
    # --- rates ---
    "call_rate": {
        "db": "FM01", "codes": ["STRDCLUCON"], "freq": "D",
        "desc": "Uncollateralized overnight call rate, daily average "
                "(the BOJ policy-relevant money-market rate)",
    },
    "call_rate_monthly": {
        "db": "FM02", "codes": ["STRACLUCON"], "freq": "M",
        "desc": "Uncollateralized overnight call rate, monthly average",
    },
    "basic_loan_rate": {
        "db": "IR01", "codes": ["MADR1Z@D"], "freq": "D",
        "desc": "Basic discount rate / basic loan rate (former ODR)",
    },
    # --- FX ---
    "usdjpy": {
        "db": "FM08", "codes": ["FXERD01"], "freq": "D",
        "desc": "USD/JPY spot rate at 9:00 JST, Tokyo market, daily",
    },
    "usdjpy_monthly": {
        "db": "FM08", "codes": ["FXERM07"], "freq": "M",
        "desc": "USD/JPY spot rate 17:00 JST, monthly average",
    },
    "eurusd_tokyo": {
        "db": "FM08", "codes": ["FXERD31"], "freq": "D",
        "desc": "EUR/USD at 9:00 JST, Tokyo market, daily",
    },
    "neer": {
        "db": "FM09", "codes": ["FX180110001"], "freq": "M",
        "desc": "Nominal effective exchange rate of the yen",
    },
    "reer": {
        "db": "FM09", "codes": ["FX180110002"], "freq": "M",
        "desc": "Real effective exchange rate of the yen",
    },
    # --- money ---
    "monetary_base": {
        "db": "MD01", "codes": ["MABS1AN11"], "freq": "M",
        "desc": "Monetary base, average amounts outstanding (100 mn yen)",
    },
    "monetary_base_yoy": {
        "db": "MD01", "codes": ["MABS1AN11@"], "freq": "M",
        "desc": "Monetary base, % change year-on-year",
    },
    "m2": {
        "db": "MD02", "codes": ["MAM1NAM2M2MO"], "freq": "M",
        "desc": "Money stock M2, average amounts outstanding (100 mn yen)",
    },
    "m2_yoy": {
        "db": "MD02", "codes": ["MAM1YAM2M2MO"], "freq": "M",
        "desc": "Money stock M2, % change year-on-year",
    },
    "m3": {
        "db": "MD02", "codes": ["MAM1NAM3M3MO"], "freq": "M",
        "desc": "Money stock M3, average amounts outstanding (100 mn yen)",
    },
    "m3_yoy": {
        "db": "MD02", "codes": ["MAM1YAM3M3MO"], "freq": "M",
        "desc": "Money stock M3, % change year-on-year",
    },
    "reserves": {
        "db": "MD07", "codes": ["MAREM1"], "freq": "M",
        "desc": "Reserves, average outstanding (100 mn yen)",
    },
    # --- TANKAN ---
    "tankan_large_mfg": {
        "db": "CO", "codes": ["TK99F1000601GCQ01000"], "freq": "Q",
        "desc": "TANKAN business conditions DI, large manufacturers, actual",
    },
    "tankan_large_nonmfg": {
        "db": "CO", "codes": ["TK99F2000601GCQ01000"], "freq": "Q",
        "desc": "TANKAN business conditions DI, large non-manufacturers, actual",
    },
    # --- prices ---
    "cgpi": {
        "db": "PR01", "codes": ["PRCG20_2200000000"], "freq": "M",
        "desc": "Producer Price Index (formerly CGPI), all commodities "
                "(2020=100)",
    },
    "export_price_index": {
        "db": "PR01", "codes": ["PRCG20_2400000000"], "freq": "M",
        "desc": "Export Price Index, yen basis, all commodities (2020=100)",
    },
    "import_price_index": {
        "db": "PR01", "codes": ["PRCG20_2600000000"], "freq": "M",
        "desc": "Import Price Index, yen basis, all commodities (2020=100)",
    },
}


# --------------------------------------------------------------------------
# Date handling
# --------------------------------------------------------------------------

def _to_param_date(value: Union[str, int, None]) -> Optional[str]:
    """Friendly period -> API parameter format.

    Accepts "2024", 2024, "2024-05", "2024-Q2", "2024-H1", "202405". Weekly
    and daily series take month granularity ("2024-05" -> "202405"), per the
    API's date grammar.
    """
    if value is None:
        return None
    s = str(value).strip().upper().replace("/", "-")
    if "-" not in s:
        return s
    left, right = s.split("-", 1)
    if right.startswith("Q"):
        return f"{left}0{right[1]}"
    if right.startswith("H") or right.startswith("S"):
        return f"{left}0{right[1]}"
    if right.startswith("M"):
        right = right[1:]
    return f"{left}{right[:2].zfill(2)}"


def _normalize_survey_date(raw: Any, frequency: str) -> str:
    """API output date -> ISO-style string, per the series' frequency label.

    Frequencies arrive as full names ("DAILY", "MONTHLY", "QUARTERLY",
    "SEMIANNUAL", "ANNUAL", "WEEKLY(MONDAY)", "ANNUAL(MAR)").
    """
    s = str(raw)
    f = (frequency or "").upper()
    if f.startswith(("DAILY", "WEEKLY")) and len(s) == 8:
        return f"{s[:4]}-{s[4:6]}-{s[6:]}"
    if f.startswith("QUARTERLY") and len(s) == 6:
        return f"{s[:4]}-Q{int(s[4:])}"
    if f.startswith("SEMIANNUAL") and len(s) == 6:
        return f"{s[:4]}-H{int(s[4:])}"
    if f.startswith("ANNUAL"):
        return s[:4]
    if len(s) == 6:
        return f"{s[:4]}-{s[4:]}"
    return s


def _clean_code(code: str) -> str:
    """Strip the search-screen DB prefix (``IR01'MADR1Z@D`` -> ``MADR1Z@D``);
    the API rejects prefixed time-series codes."""
    s = str(code).strip()
    return s.split("'", 1)[1] if "'" in s else s


# --------------------------------------------------------------------------
# Transport
# --------------------------------------------------------------------------

def _request(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{BASE_URL}/{endpoint}"
    p = {"format": "json", "lang": "en"}
    p.update({k: v for k, v in params.items() if v is not None})
    resp = _SESSION.get(url, params=p, timeout=DEFAULT_TIMEOUT)
    if resp.status_code >= 400:
        raise BOJError(
            f"BOJ API HTTP {resp.status_code} for {url}: {resp.text[:300]}"
        )
    try:
        data = resp.json()
    except ValueError as e:
        raise BOJError(f"BOJ API returned non-JSON: {resp.text[:200]}") from e
    status = data.get("STATUS")
    if status != 200:
        msg = data.get("MESSAGE", "")
        mid = data.get("MESSAGEID", "")
        raise BOJError(f"BOJ API status {status} ({mid}): {msg}")
    return data


def _flatten_resultset(resultset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One output row per (series, date). Metadata-only entries (layer
    headers without a series code) are skipped."""
    rows: List[Dict[str, Any]] = []
    for entry in resultset or []:
        code = entry.get("SERIES_CODE")
        if not code:
            continue
        freq = entry.get("FREQUENCY", "")
        values = entry.get("VALUES") or {}
        dates = values.get("SURVEY_DATES") or []
        vals = values.get("VALUES") or []
        for d, v in zip(dates, vals):
            rows.append({
                "series_code": code,
                "name": entry.get("NAME_OF_TIME_SERIES", ""),
                "unit": entry.get("UNIT", ""),
                "frequency": freq,
                "category": entry.get("CATEGORY", ""),
                "date": _normalize_survey_date(d, freq),
                "value": float(v) if v is not None else None,
            })
    return rows


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------

def list_catalog() -> List[Dict[str, str]]:
    """Return the curated headline-series catalog as rows.

    Each row: ``name`` (sandbox key), ``db``, ``codes``, ``desc``.
    """
    return [
        {"name": k, "db": v["db"], "codes": ",".join(v["codes"]),
         "desc": v["desc"]}
        for k, v in CATALOG.items()
    ]


def list_databases(search: Optional[str] = None) -> List[Dict[str, str]]:
    """The BOJ database registry (DB code -> description). ``search``
    filters case-insensitively on code + description."""
    rows = [{"db": k, "desc": v} for k, v in DATABASES.items()]
    if not search:
        return rows
    q = search.lower()
    return [r for r in rows
            if q in r["db"].lower() or q in r["desc"].lower()]


def get_metadata(db: str) -> List[Dict[str, Any]]:
    """Full series metadata for one database via ``/getMetadata``.

    One row per series: ``series_code``, ``name``, ``unit``, ``frequency``,
    ``category``, ``start``, ``end``, ``last_update``, plus the LAYER1-5
    tree position. Layer-header rows (no series code) are excluded.
    Metadata refreshes daily on the BOJ side.
    """
    data = _request("getMetadata", {"db": db})
    rows = []
    for r in data.get("RESULTSET") or []:
        if not r.get("SERIES_CODE"):
            continue
        freq = r.get("FREQUENCY", "")
        rows.append({
            "series_code": r["SERIES_CODE"],
            "name": r.get("NAME_OF_TIME_SERIES", ""),
            "unit": r.get("UNIT", ""),
            "frequency": freq,
            "category": r.get("CATEGORY", ""),
            "start": _normalize_survey_date(
                r.get("START_OF_THE_TIME_SERIES", ""), freq),
            "end": _normalize_survey_date(
                r.get("END_OF_THE_TIME_SERIES", ""), freq),
            "last_update": str(r.get("LAST_UPDATE", "")),
            "layers": [r.get(f"LAYER{i}") for i in range(1, 6)],
        })
    return rows


def search_series(
    db: str,
    keyword: str = "",
    *,
    frequency: Optional[str] = None,
    include_discontinued: bool = False,
) -> List[Dict[str, Any]]:
    """Search one database's series by name substring (case-insensitive).

    ``frequency`` filters on the output frequency label prefix ("DAILY",
    "MONTHLY", "QUARTERLY", ...). Discontinued series (name starts with
    "(Discontinued)") are excluded unless requested.
    """
    rows = get_metadata(db)
    q = keyword.lower()
    out = []
    for r in rows:
        name = r["name"] or ""
        if not include_discontinued and name.startswith("(Discontinued)"):
            continue
        if q and q not in name.lower() and q not in r["series_code"].lower():
            continue
        if frequency and not r["frequency"].upper().startswith(
                frequency.upper()):
            continue
        out.append(r)
    return out


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------

def get_data(
    db: str,
    codes: Union[str, Sequence[str]],
    *,
    start: Union[str, int, None] = None,
    end: Union[str, int, None] = None,
) -> List[Dict[str, Any]]:
    """Fetch time-series data for explicit series codes via ``/getDataCode``.

    ``codes`` accepts a string or list (all codes must share one frequency
    -- an API rule; mixed-frequency requests raise on the BOJ side). Codes
    with a search-screen ``DB'`` prefix are cleaned automatically. Batches
    of >250 codes and >60,000-datapoint responses are auto-paginated via
    NEXTPOSITION.

    Returns one row per (series, date): ``series_code``, ``name``, ``unit``,
    ``frequency``, ``date`` (normalized), ``value`` (float | None).
    """
    if isinstance(codes, str):
        codes = [codes]
    code_list = [_clean_code(c) for c in codes if str(c).strip()]
    if not code_list:
        raise BOJError("at least one series code is required")

    rows: List[Dict[str, Any]] = []
    for i in range(0, len(code_list), MAX_CODES_PER_REQUEST):
        chunk = code_list[i:i + MAX_CODES_PER_REQUEST]
        position: Optional[int] = None
        while True:
            data = _request("getDataCode", {
                "db": db,
                "code": ",".join(chunk),
                "startDate": _to_param_date(start),
                "endDate": _to_param_date(end),
                "startPosition": position,
            })
            rows.extend(_flatten_resultset(data.get("RESULTSET") or []))
            nxt = data.get("NEXTPOSITION")
            if not nxt:
                break
            position = int(nxt)
    return rows


def get_layer(
    db: str,
    frequency: str,
    layer: Union[str, Sequence[Union[str, int]]] = "*",
    *,
    start: Union[str, int, None] = None,
    end: Union[str, int, None] = None,
    max_pages: int = 20,
) -> List[Dict[str, Any]]:
    """Fetch all series under a layer-tree position via ``/getDataLayer``.

    ``frequency`` is the abbreviation (``CY``/``FY``/``CH``/``FH``/``Q``/
    ``M``/``W``/``D``). ``layer`` is layer-1..5 values, comma-joined or a
    list; ``"*"`` wildcards (a selection matching >1,250 series errors on
    the BOJ side -- narrow the layers). Auto-paginates via NEXTPOSITION.

    Row shape matches ``get_data``.
    """
    if isinstance(layer, (list, tuple)):
        layer = ",".join(str(x) for x in layer)
    rows: List[Dict[str, Any]] = []
    position: Optional[int] = None
    for _ in range(max_pages):
        data = _request("getDataLayer", {
            "db": db,
            "frequency": frequency,
            "layer": layer,
            "startDate": _to_param_date(start),
            "endDate": _to_param_date(end),
            "startPosition": position,
        })
        rows.extend(_flatten_resultset(data.get("RESULTSET") or []))
        nxt = data.get("NEXTPOSITION")
        if not nxt:
            break
        position = int(nxt)
    return rows


def get_indicator(
    name: str,
    *,
    start: Union[str, int, None] = None,
    end: Union[str, int, None] = None,
    drop_missing: bool = False,
) -> List[Dict[str, Any]]:
    """Headline accessor: pull a curated catalog series by friendly name.

    ``name`` is a catalog key (see ``list_catalog``), e.g. ``"usdjpy"``,
    ``"monetary_base"``, ``"tankan_large_mfg"``. Row shape matches
    ``get_data``. ``drop_missing=True`` removes ``None`` observations
    (daily series carry None on weekends/holidays).
    """
    entry = CATALOG.get(name)
    if entry is None:
        raise BOJError(
            f"unknown indicator {name!r}; see list_catalog() for valid keys"
        )
    rows = get_data(entry["db"], entry["codes"], start=start, end=end)
    if drop_missing:
        rows = [r for r in rows if r["value"] is not None]
    return rows


def get_panel(
    names: Sequence[str],
    *,
    start: Union[str, int, None] = None,
    end: Union[str, int, None] = None,
    drop_missing: bool = False,
) -> List[Dict[str, Any]]:
    """Pull several catalog indicators in one combined long-row set.

    Each row keeps its ``indicator`` (catalog key). Useful for
    level + YoY pairs (``["monetary_base", "monetary_base_yoy"]``,
    ``["m2_yoy", "m3_yoy"]``) or FX panels -- ``to_dataframe(rows,
    wide=True)`` gives one column per series.
    """
    rows: List[Dict[str, Any]] = []
    for name in names:
        for r in get_indicator(name, start=start, end=end,
                               drop_missing=drop_missing):
            r["indicator"] = name
            rows.append(r)
    return rows


def to_dataframe(
    rows: List[Dict[str, Any]],
    *,
    wide: bool = False,
):
    """Convert parsed BOJ rows to a pandas DataFrame (long or wide).

    Long: ``series_code``, ``name``, ``date``, numeric ``time`` helper,
    ``value``, ``unit``, ``frequency``. Wide: pivot of ``time`` (index) x
    one column per series (header = series name, falling back to code).
    Null observations are kept in long form and become NaN in wide form.
    """
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("to_dataframe requires pandas") from e

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["time"] = _coerce_time(df["date"])

    if wide:
        header = df["name"].where(df["name"].astype(bool), df["series_code"])
        df = df.assign(_series=header)
        pivot = df.pivot_table(
            index="time", columns="_series", values="value", aggfunc="first"
        )
        return pivot.sort_index()

    cols = ["series_code", "name", "date", "time", "value", "unit",
            "frequency"]
    out = df[[c for c in cols if c in df.columns]].copy()
    return out.sort_values(["series_code", "time"])


def _coerce_time(series):
    """Sortable numeric from normalized BOJ dates ('2024', '2024-05',
    '2024-Q2', '2024-H1', '2024-05-17')."""
    import pandas as pd
    if series is None:
        return None

    def conv(v: Any):
        s = str(v)
        try:
            if "-Q" in s:
                y, q = s.split("-Q")
                return int(y) + (int(q) - 1) / 4.0
            if "-H" in s:
                y, h = s.split("-H")
                return int(y) + (int(h) - 1) / 2.0
            parts = s.split("-")
            if len(parts) == 3:
                return (int(parts[0]) + (int(parts[1]) - 1) / 12.0
                        + (int(parts[2]) - 1) / 372.0)
            if len(parts) == 2:
                return int(parts[0]) + (int(parts[1]) - 1) / 12.0
            return float(s)
        except (ValueError, TypeError):
            return float("nan")

    return series.map(conv)


__all__ = [
    "BASE_URL",
    "CATALOG",
    "DATABASES",
    "BOJError",
    "list_catalog",
    "list_databases",
    "get_metadata",
    "search_series",
    "get_data",
    "get_layer",
    "get_indicator",
    "get_panel",
    "to_dataframe",
]
