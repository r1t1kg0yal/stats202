"""World Inequality Database (WID.world) — direct REST client.

Sandbox name: ``wid_client``.

Thin transport layer over the WID AWS API Gateway. The full static
ontology (concept codes, dimension tables, traversal patterns) lives in
``wid_guide.md``; this module handles HTTP, variable-code assembly,
chunked retrieval, extrapolation filtering, and DataFrame conversion.

Base URL: ``https://rfap9nitz6.execute-api.eu-west-1.amazonaws.com/prod/``
Auth: ``x-api-key`` header (base64-encoded key). Override via
``WID_API_KEY`` env var (raw key bytes as hex string) or use the
bundled default from the official R package ``sysdata.rda``.
Transport: Bucket C — plain ``requests`` (no GS proxy).
"""

from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Union

import requests


BASE_URL = "https://rfap9nitz6.execute-api.eu-west-1.amazonaws.com/prod/"
DEFAULT_TIMEOUT = 120
CHUNK_SIZE = 10
METADATA_CHUNK_SIZE = 50

# Official R package embedded key (hex); base64-encoded at request time.
_DEFAULT_KEY_HEX = (
    "ad8141c8e0748a868f013c07b6594c23bd732ce6522b421ce6f790a2724f"
)

_SESSION = requests.Session()
_SESSION.headers.update({"Accept": "application/json"})

_SIXLET_RE = re.compile(r"^[a-z]{6}$")
_AREA_RE = re.compile(r"^[A-Z]{2}(-[A-Z]{2,4})?$")
_PERC_RE = re.compile(r"^p[0-9]+(\.[0-9]+)?(p[0-9]+(\.[0-9]+)?)?$")
_AGE_RE = re.compile(r"^[0-9]{3}$")
_POP_CODES = frozenset("ijmfte")

_IMPUTATION_LABELS = {
    "region": "regional imputation",
    "survey": "adjusted surveys",
    "tax": "surveys and tax data",
    "full": "surveys and tax microdata",
    "rescaling": "rescaled fiscal income",
}


class WIDError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


def _api_key_header() -> str:
    raw = os.environ.get("WID_API_KEY", "").strip()
    if raw:
        if re.fullmatch(r"[0-9a-fA-F]+", raw):
            key_bytes = bytes.fromhex(raw)
        else:
            key_bytes = raw.encode("utf-8")
    else:
        key_bytes = bytes.fromhex(_DEFAULT_KEY_HEX)
    return base64.b64encode(key_bytes).decode("ascii")


def _request(path: str, *, timeout: int = DEFAULT_TIMEOUT) -> Any:
    url = BASE_URL + path.lstrip("/")
    headers = {"x-api-key": _api_key_header()}
    resp = _SESSION.get(url, headers=headers, timeout=timeout)
    if resp.status_code == 403:
        raise WIDError(
            "WID API forbidden (403). Set WID_API_KEY or verify the bundled key."
        )
    if resp.status_code >= 400:
        raise WIDError(f"WID API HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except json.JSONDecodeError as e:
        raise WIDError(f"WID API returned non-JSON body: {resp.text[:200]}") from e


def _follow_large_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    if payload.get("status") != "payload_too_large":
        if payload.get("status") and payload.get("message"):
            raise WIDError(str(payload["message"]))
        return payload
    url = payload.get("download_url")
    if not url:
        raise WIDError("payload_too_large response missing download_url")
    resp = _SESSION.get(url, timeout=DEFAULT_TIMEOUT * 2)
    resp.raise_for_status()
    return resp.json()


def _normalize_list(value: Union[str, Sequence[str]], *, name: str) -> List[str]:
    if isinstance(value, str):
        if value == "all":
            return ["all"]
        return [value]
    out = [str(v) for v in value]
    if not out:
        raise WIDError(f"{name} must not be empty")
    return out


def _validate_sixlets(indicators: List[str]) -> None:
    if indicators == ["all"]:
        return
    bad = [x for x in indicators if not _SIXLET_RE.match(x)]
    if bad:
        raise WIDError(f"indicators must be 6-letter codes; invalid: {bad}")


def _validate_areas(areas: List[str]) -> None:
    if areas == ["all"]:
        return
    bad = [x for x in areas if not _AREA_RE.match(x)]
    if bad:
        raise WIDError(
            f"areas must be XX or XX-YY; invalid: {bad}"
        )


def _validate_years(years: Union[str, Sequence[Union[int, str]]]) -> List[str]:
    if years == "all" or (isinstance(years, list) and years == ["all"]):
        return ["all"]
    if isinstance(years, str):
        years = [years]
    out: List[str] = []
    for y in years:
        ys = str(int(y))
        if len(ys) != 4:
            raise WIDError(f"invalid year: {y}")
        out.append(ys)
    return out


def _validate_perc(perc: List[str]) -> None:
    if perc == ["all"]:
        return
    bad = [x for x in perc if not _PERC_RE.match(x)]
    if bad:
        raise WIDError(f"invalid percentile codes: {bad}")


def _validate_ages(ages: List[str]) -> None:
    if ages == ["all"]:
        return
    bad = [x for x in ages if not _AGE_RE.match(x)]
    if bad:
        raise WIDError(f"ages must be 3-digit codes; invalid: {bad}")


def _validate_pop(pop: List[str]) -> None:
    if pop == ["all"]:
        return
    bad = [x for x in pop if x not in _POP_CODES]
    if bad:
        raise WIDError(f"pop must be one of {sorted(_POP_CODES)}; invalid: {bad}")


def build_variable(
    sixlet: str,
    percentile: str,
    age: str,
    pop: str,
) -> str:
    """Assemble a full API variable code: ``{sixlet}_{perc}_{age}_{pop}``."""
    _validate_sixlets([sixlet])
    _validate_perc([percentile])
    _validate_ages([age])
    _validate_pop([pop])
    return f"{sixlet}_{percentile}_{age}_{pop}"


def _comma_join(items: Iterable[str]) -> str:
    return ",".join(items)


def list_available(
    countries: Union[str, Sequence[str]],
    indicators: Union[str, Sequence[str]] = "all",
) -> List[Dict[str, str]]:
    """Discovery: available (sixlet, percentile, age, pop) combos per country.

    Maps to ``GET /countries-available-variables``.
    """
    areas = _normalize_list(countries, name="countries")
    inds = _normalize_list(indicators, name="indicators")
    _validate_areas(areas)
    _validate_sixlets(inds)

    path = (
        "countries-available-variables?countries="
        f"{_comma_join(areas)}&variables={_comma_join(inds)}"
    )
    payload = _request(path)
    if isinstance(payload, list) and len(payload) == 1:
        payload = payload[0]
    if not isinstance(payload, dict):
        raise WIDError("unexpected discovery response shape")

    rows: List[Dict[str, str]] = []
    for sixlet, by_country in payload.items():
        if not isinstance(by_country, dict):
            continue
        for country, combos in by_country.items():
            if not isinstance(combos, list):
                continue
            for combo in combos:
                if not isinstance(combo, (list, tuple)) or len(combo) < 3:
                    continue
                rows.append({
                    "country": country,
                    "variable": sixlet,
                    "percentile": str(combo[0]),
                    "age": str(combo[1]),
                    "pop": str(combo[2]),
                    "data_code": build_variable(
                        sixlet, str(combo[0]), str(combo[1]), str(combo[2])
                    ),
                })
    return rows


def _parse_values(
    values: List[Any],
    *,
    exclude_extrapolations: bool,
    meta: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    exclude_years: set = set()

    if exclude_extrapolations and meta:
        extrapol = meta.get("extrapolation")
        data_points = meta.get("data_points")
        if extrapol and extrapol not in ("", "null", None):
            try:
                brackets = json.loads(extrapol) if isinstance(extrapol, str) else extrapol
            except (json.JSONDecodeError, TypeError):
                brackets = None
            if brackets:
                dp_set = None
                if data_points and data_points not in ("", "null", None):
                    try:
                        dp_set = set(
                            str(x) for x in (
                                json.loads(data_points)
                                if isinstance(data_points, str) else data_points
                            )
                        )
                    except (json.JSONDecodeError, TypeError):
                        dp_set = None
                for bracket in brackets:
                    if not bracket or len(bracket) < 2:
                        continue
                    lo, hi = int(bracket[0]), int(bracket[1])
                    for y in range(lo + 1, hi + 1):
                        ys = str(y)
                        if dp_set is None or ys not in dp_set:
                            exclude_years.add(ys)

    for item in values or []:
        if isinstance(item, dict):
            year, value = item.get("y"), item.get("v")
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            year, value = item[0], item[1]
        else:
            continue
        ys = str(year)
        if ys in exclude_years:
            continue
        rows.append({"year": ys, "value": value})
    return rows


def get_data(
    countries: Union[str, Sequence[str]],
    variables: Union[str, Sequence[str]],
    *,
    exclude_extrapolations: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch time series for fully-qualified variable codes.

    Maps to ``GET /countries-variables?years=all`` (year filter client-side).
    """
    areas = _normalize_list(countries, name="countries")
    vars_ = _normalize_list(variables, name="variables")
    _validate_areas(areas)
    if not vars_:
        raise WIDError("variables must not be empty")

    path = (
        "countries-variables?countries="
        f"{_comma_join(areas)}&variables={_comma_join(vars_)}&years=all"
    )
    payload = _follow_large_payload(_request(path))
    if isinstance(payload, list) and len(payload) == 1:
        payload = payload[0]
    if not isinstance(payload, dict):
        raise WIDError("unexpected data response shape")

    rows: List[Dict[str, Any]] = []
    for var_code, country_blocks in payload.items():
        if not isinstance(country_blocks, list):
            continue
        for block in country_blocks:
            if not isinstance(block, dict):
                continue
            for country, body in block.items():
                if not isinstance(body, dict):
                    continue
                meta = body.get("meta") or {}
                parsed = _parse_values(
                    body.get("values") or [],
                    exclude_extrapolations=exclude_extrapolations,
                    meta=meta,
                )
                parts = var_code.split("_")
                if len(parts) >= 4:
                    sixlet = parts[0]
                    perc = parts[1]
                    age = parts[2]
                    pop = parts[3]
                    variable = f"{sixlet}{age}{pop}"
                else:
                    sixlet = perc = age = pop = ""
                    variable = var_code
                for pt in parsed:
                    rows.append({
                        "country": country,
                        "indicator": var_code,
                        "variable": variable,
                        "percentile": perc,
                        "year": pt["year"],
                        "value": pt["value"],
                        "unit": meta.get("unit"),
                        "data_quality": meta.get("data_quality"),
                        "imputation": _IMPUTATION_LABELS.get(
                            meta.get("imputation"), meta.get("imputation")
                        ),
                    })
    return rows


def get_metadata(
    countries: Union[str, Sequence[str]],
    variables: Union[str, Sequence[str]],
) -> List[Dict[str, Any]]:
    """Fetch descriptive metadata for variable codes.

    Maps to ``GET /countries-variables-metadata``.
    """
    areas = _normalize_list(countries, name="countries")
    vars_ = _normalize_list(variables, name="variables")
    _validate_areas(areas)

    path = (
        "countries-variables-metadata?countries="
        f"{_comma_join(areas)}&variables={_comma_join(vars_)}"
    )
    payload = _request(path)
    if not isinstance(payload, list) or not payload:
        return []
    meta_func = payload[0].get("metadata_func") or []

    rows: List[Dict[str, Any]] = []
    for entry in meta_func:
        if not isinstance(entry, dict) or len(entry) != 1:
            continue
        var_code = next(iter(entry))
        parts = entry[var_code]
        if not isinstance(parts, list):
            continue

        blocks: Dict[str, Any] = {}
        for part in parts:
            if isinstance(part, dict) and len(part) == 1:
                blocks.update(part)

        name_block = blocks.get("name") or {}
        type_block = blocks.get("type") or {}
        pop_block = blocks.get("pop") or {}
        age_block = blocks.get("age") or {}
        units_block = blocks.get("units") or []
        notes_block = blocks.get("notes") or []

        notes_by_country: Dict[str, Any] = {}
        for note_group in notes_block:
            if not isinstance(note_group, dict):
                continue
            for _concept, note_list in note_group.items():
                if not isinstance(note_list, list):
                    continue
                for note in note_list:
                    if isinstance(note, dict) and note.get("alpha2"):
                        notes_by_country[note["alpha2"]] = note

        for unit_entry in units_block:
            if not isinstance(unit_entry, dict):
                continue
            cc = unit_entry.get("country")
            meta = unit_entry.get("metadata") or {}
            note = notes_by_country.get(cc, {})
            code_parts = var_code.split("_")
            variable = (
                f"{code_parts[0]}{code_parts[2]}{code_parts[3]}"
                if len(code_parts) >= 4 else var_code
            )
            rows.append({
                "country": cc,
                "indicator": var_code,
                "variable": variable,
                "countryname": unit_entry.get("country_name"),
                "shortname": name_block.get("shortname"),
                "shortdes": name_block.get("simpledes"),
                "technicaldes": name_block.get("technicaldes"),
                "shorttype": type_block.get("shortdes"),
                "longtype": type_block.get("longtype"),
                "shortpop": pop_block.get("shortdes"),
                "pop": pop_block.get("longdes"),
                "shortage": age_block.get("shortname"),
                "age": age_block.get("fullname"),
                "unit": meta.get("unit"),
                "unitname": meta.get("unit_name"),
                "source": note.get("source"),
                "method": note.get("method"),
                "quality": note.get("data_quality"),
                "imputation": _IMPUTATION_LABELS.get(
                    note.get("imputation"), note.get("imputation")
                ),
            })
    return rows


def _chunked_get_data(
    countries: Sequence[str],
    variables: Sequence[str],
    *,
    exclude_extrapolations: bool,
) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    vars_list = list(variables)
    for i in range(0, len(vars_list), CHUNK_SIZE):
        chunk = vars_list[i:i + CHUNK_SIZE]
        all_rows.extend(
            get_data(countries, chunk, exclude_extrapolations=exclude_extrapolations)
        )
    return all_rows


def _chunked_get_metadata(
    countries: Sequence[str],
    variables: Sequence[str],
) -> List[Dict[str, Any]]:
    all_rows: List[Dict[str, Any]] = []
    vars_list = list(dict.fromkeys(variables))
    for i in range(0, len(vars_list), METADATA_CHUNK_SIZE):
        chunk = vars_list[i:i + METADATA_CHUNK_SIZE]
        all_rows.extend(get_metadata(countries, chunk))
    return all_rows


def _filter_available(
    rows: List[Dict[str, str]],
    *,
    indicators: List[str],
    perc: List[str],
    ages: List[str],
    pop: List[str],
) -> List[Dict[str, str]]:
    out = rows
    if indicators != ["all"]:
        ind_set = set(indicators)
        out = [r for r in out if r["variable"] in ind_set]
    if perc != ["all"]:
        pset = set(perc)
        out = [r for r in out if r["percentile"] in pset]
    if ages != ["all"]:
        aset = set(ages)
        out = [r for r in out if r["age"] in aset]
    if pop != ["all"]:
        pset = set(pop)
        out = [r for r in out if r["pop"] in pset]
    return out


def download_wid(
    indicators: Union[str, Sequence[str]] = "all",
    areas: Union[str, Sequence[str]] = "all",
    years: Union[str, Sequence[Union[int, str]]] = "all",
    perc: Union[str, Sequence[str]] = "all",
    ages: Union[str, Sequence[str]] = "all",
    pop: Union[str, Sequence[str]] = "all",
    *,
    metadata: bool = False,
    include_extrapolations: bool = True,
) -> List[Dict[str, Any]]:
    """High-level pull mirroring the official R ``download_wid()`` workflow.

    Requires at least one of ``indicators`` or ``areas`` to be narrowed
    (not both ``all``). Discovers availability, filters dimensions, chunks
    data requests, optionally merges metadata.
    """
    inds = _normalize_list(indicators, name="indicators")
    area_list = _normalize_list(areas, name="areas")
    perc_list = _normalize_list(perc, name="perc")
    ages_list = _normalize_list(ages, name="ages")
    pop_list = _normalize_list(pop, name="pop")
    year_list = _validate_years(years)

    if inds == ["all"] and area_list == ["all"]:
        raise WIDError(
            "Specify at least some indicators or areas (not both 'all'). "
            "For the full database use https://wid.world/data/ bulk download."
        )

    _validate_sixlets(inds)
    _validate_areas(area_list)
    _validate_perc(perc_list)
    _validate_ages(ages_list)
    _validate_pop(pop_list)

    sixlets_for_discovery = inds if inds != ["all"] else ["all"]
    discovered: List[Dict[str, str]] = []
    for sixlet in sixlets_for_discovery:
        discovered.extend(list_available(area_list, sixlet))

    matched = _filter_available(
        discovered,
        indicators=inds,
        perc=perc_list,
        ages=ages_list,
        pop=pop_list,
    )
    if not matched:
        return []

    countries = sorted({r["country"] for r in matched})
    data_codes = sorted({r["data_code"] for r in matched})

    rows = _chunked_get_data(
        countries,
        data_codes,
        exclude_extrapolations=not include_extrapolations,
    )

    if year_list != ["all"]:
        yset = set(year_list)
        rows = [r for r in rows if r["year"] in yset]

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for r in rows:
        key = (r["country"], r["indicator"], r["year"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    rows = deduped

    if metadata:
        meta_rows = _chunked_get_metadata(countries, data_codes)
        meta_index = {(m["country"], m["variable"]): m for m in meta_rows}
        enriched: List[Dict[str, Any]] = []
        for r in rows:
            m = meta_index.get((r["country"], r["variable"]), {})
            enriched.append({**m, **r})
        rows = enriched

    rows.sort(key=lambda r: (r["country"], r["variable"], r.get("percentile", ""), r["year"]))
    return rows


def series_to_dataframe(
    rows: List[Dict[str, Any]],
    *,
    value_col: str = "value",
    wide: bool = False,
):
    """Convert parsed WID rows to a pandas DataFrame (long or wide)."""
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover
        raise ImportError("series_to_dataframe requires pandas") from e

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if wide:
        key_cols = [c for c in ("country", "variable", "percentile") if c in df.columns]
        if not key_cols:
            key_cols = ["indicator"]
        series_key = df[key_cols].astype(str).agg("|".join, axis=1)
        df = df.assign(_series=series_key)
        pivot = df.pivot_table(
            index="year", columns="_series", values=value_col, aggfunc="first"
        )
        pivot.index = pd.to_numeric(pivot.index, errors="coerce")
        return pivot.sort_index()

    cols = [c for c in (
        "country", "variable", "percentile", "year", value_col,
        "unit", "shortname", "source", "imputation", "quality",
    ) if c in df.columns]
    out = df[cols].copy()
    out["year"] = pd.to_numeric(out["year"], errors="coerce")
    return out.sort_values([c for c in cols if c != value_col])


__all__ = [
    "BASE_URL",
    "CHUNK_SIZE",
    "WIDError",
    "build_variable",
    "list_available",
    "get_data",
    "get_metadata",
    "download_wid",
    "series_to_dataframe",
]
