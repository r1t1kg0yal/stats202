"""AI / data-center buildout -- consolidated thin multi-source client.

Sandbox name: ``ai_buildout_client``.

PHILOSOPHY: thin transport + catalog. This module is deliberately NOT a set
of per-question methods. It exposes (1) a catalog of every dataset/endpoint
across three sources and (2) thin fetchers that return coerced rows. The L2
guide (``ai_buildout_guide.md``) is the SSOT for the full data universe --
dataset slugs, schemas, the Azure OData grammar -- and PRISM writes raw
pandas against these fetchers rather than calling rigid wrappers.

    ai_buildout_client.epoch.catalog()                 # every Epoch dataset
    ai_buildout_client.epoch.get("data_centers")       # -> rows
    ai_buildout_client.epoch.get("chip_sales")         # zip -> {member: rows}
    ai_buildout_client.anthropic.list_files(max_mb=2)  # HF file universe
    ai_buildout_client.anthropic.fetch_csv(path)       # -> rows
    ai_buildout_client.cloud.query("serviceName eq 'Virtual Machines' ...")
    ai_buildout_client.to_dataframe(rows)              # pandas

Sources:
    epoch       Epoch AI -- models, ML hardware, GPU clusters, FRONTIER DATA
                CENTERS (power/MW, capital cost, construction, water), AI chip
                sales/components/owners, AI companies, benchmarks, polling.
                Free CSV/ZIP, no key, CC-BY.
    anthropic   Anthropic Economic Index on Hugging Face. AI adoption by
                occupation/task, automation-vs-augmentation, wages, SOC/O*NET.
                Free, no key, CC-BY.
    cloud       Azure Retail Prices (OData). $/GPU-hour, inference, storage,
                bandwidth -- the full retail catalog. No auth.

Net-new only -- DEFERS to existing apis clients for covered themes (ROUTING):
    capex / XBRL / filings  -> sec_edgar_client  (get_frames, company_facts)
    macro series (FRED)     -> fred_client
    cross-border / credit   -> bis_client
    petroleum / nat-gas     -> eia_client
    grid demand by BA/ISO   -> electricity_client

Transport: Bucket C (plain ``requests``). Rows carry boundary numeric
coercion (numeric strings -> int/float; "" -> None). ZIP datasets unzip to
``{member_csv: rows}``. Size guards steer away from the 40-140 MB raw dumps.
"""

from __future__ import annotations

import csv
import io
import re
import zipfile
from typing import Any, Dict, List, Optional, Sequence, Union

import requests


__all__ = [
    "AIBuildoutError",
    "epoch",
    "anthropic",
    "cloud",
    "SOURCES",
    "ROUTING",
    "list_sources",
    "describe",
    "fetch_csv",
    "fetch_zip",
    "to_dataframe",
]

USER_AGENT = "prism-ai-buildout-client/2.0 (research; contact admin)"
DEFAULT_TIMEOUT = 90

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "*/*"})


class AIBuildoutError(Exception):
    """Raised on validation failures or unrecoverable API errors."""


# --- Boundary type coercion ---------------------------------------------------

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


# --- Transport primitives -----------------------------------------------------


def _get(url: str, *, params=None, headers=None, timeout=DEFAULT_TIMEOUT,
         stream=False) -> requests.Response:
    try:
        resp = _SESSION.get(url, params=params, headers=headers,
                            timeout=timeout, stream=stream)
    except requests.RequestException as e:
        raise AIBuildoutError(f"request failed for {url}: {e}") from e
    if resp.status_code >= 400:
        body = "" if stream else resp.text[:200]
        raise AIBuildoutError(f"HTTP {resp.status_code} for {url}: {body}")
    return resp


def _get_json(url: str, *, params=None, timeout=DEFAULT_TIMEOUT) -> Any:
    resp = _get(url, params=params, timeout=timeout)
    try:
        return resp.json()
    except ValueError as e:
        raise AIBuildoutError(f"non-JSON body from {url}: {resp.text[:200]}") from e


def _read_capped(resp: requests.Response, max_mb: Optional[float], url: str = "") -> bytes:
    cap = int(max_mb * 1024 * 1024) if max_mb else None
    declared = resp.headers.get("Content-Length")
    if cap and declared and int(declared) > cap:
        raise AIBuildoutError(
            f"{url} is {int(declared) / 1e6:.1f}MB > max_mb={max_mb}; raise "
            f"max_mb to fetch it, or pick a smaller dataset."
        )
    buf = bytearray()
    for chunk in resp.iter_content(8192):
        buf.extend(chunk)
        if cap and len(buf) > cap:
            raise AIBuildoutError(
                f"{url} exceeded max_mb={max_mb}; raise max_mb to fetch it, "
                f"or pick a smaller dataset."
            )
    return bytes(buf)


def _parse_csv_text(text: str, coerce: bool) -> List[Dict[str, Any]]:
    rows = [dict(r) for r in csv.DictReader(io.StringIO(text))]
    return _coerce_rows(rows) if coerce else rows


def fetch_csv(url: str, *, params=None, max_mb: Optional[float] = 50,
              coerce: bool = True) -> List[Dict[str, Any]]:
    """Fetch any CSV URL into list-of-dicts (numeric-coerced). Size-guarded."""
    resp = _get(url, params=params, stream=True)
    data = _read_capped(resp, max_mb, url)
    return _parse_csv_text(data.decode("utf-8", "replace"), coerce)


def fetch_zip(url: str, *, member: Optional[str] = None, max_mb: Optional[float] = 80,
              coerce: bool = True) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Fetch a ZIP of CSVs. Returns ``{member_name: rows}`` for the whole
    bundle, or just ``rows`` when ``member`` is given (with or without the
    ``.csv`` suffix; matches on basename too)."""
    resp = _get(url, stream=True)
    data = _read_capped(resp, max_mb, url)
    z = zipfile.ZipFile(io.BytesIO(data))
    members = [n for n in z.namelist() if n.endswith(".csv")]

    def parse(name: str) -> List[Dict[str, Any]]:
        with z.open(name) as fh:
            return _parse_csv_text(fh.read().decode("utf-8", "replace"), coerce)

    if member is not None:
        cands = [member, member + ".csv"]
        match = [n for n in members
                 if n in cands or n.split("/")[-1] in cands]
        if not match:
            raise AIBuildoutError(
                f"member {member!r} not in zip; members={members}"
            )
        return parse(match[0])
    return {n: parse(n) for n in members}


def to_dataframe(rows: Sequence[Dict[str, Any]], columns: Optional[Sequence[str]] = None):
    """Convert list-of-dicts rows to a pandas DataFrame (lazy import)."""
    try:
        import pandas as pd
    except ImportError as e:  # pragma: no cover - pandas present in PRISM
        raise AIBuildoutError("pandas is required for to_dataframe()") from e
    df = pd.DataFrame(list(rows))
    if columns is not None:
        df = df[[c for c in columns if c in df.columns]]
    return df


# --- Epoch AI -----------------------------------------------------------------

_EPOCH_BASE = "https://epoch.ai/data"


class _EpochSource:
    """Catalog + thin fetch for every Epoch AI dataset (CSV + ZIP bundles)."""

    BASE = _EPOCH_BASE

    # slug -> dataset metadata. kind csv -> get() returns rows; kind zip ->
    # get() returns {member: rows} (pass member= for one CSV).
    DATASETS: Dict[str, Dict[str, Any]] = {
        # --- Models ---
        "notable_models": {"kind": "csv", "group": "models",
            "url": f"{_EPOCH_BASE}/notable_ai_models.csv",
            "desc": "Recommended analysis cut of notable ML models (compute, params, cost, hardware)."},
        "frontier_models": {"kind": "csv", "group": "models",
            "url": f"{_EPOCH_BASE}/frontier_ai_models.csv",
            "desc": "Models that were top-10 by training compute at release."},
        "large_scale_models": {"kind": "csv", "group": "models",
            "url": f"{_EPOCH_BASE}/large_scale_ai_models.csv",
            "desc": "Models trained with >= 1e23 FLOP."},
        "all_models": {"kind": "csv", "group": "models",
            "url": f"{_EPOCH_BASE}/all_ai_models.csv",
            "desc": "Every model in the database (3500+)."},
        "biology_models": {"kind": "csv", "group": "models",
            "url": f"{_EPOCH_BASE}/biology_models.csv",
            "desc": "Biology/biomedical ML models subset."},
        # --- Hardware ---
        "ml_hardware": {"kind": "csv", "group": "hardware",
            "url": f"{_EPOCH_BASE}/ml_hardware.csv",
            "desc": "AI accelerators: perf by precision (FLOP/s), memory, bandwidth, TDP, release price, node."},
        # --- Compute facilities ---
        "gpu_clusters": {"kind": "csv", "group": "compute_facilities",
            "url": f"{_EPOCH_BASE}/gpu_clusters.csv",
            "desc": "500+ GPU clusters/supercomputers: H100e, chip type+qty, power MW, owner, location, status."},
        "data_centers": {"kind": "csv", "group": "compute_facilities",
            "url": f"{_EPOCH_BASE}/data_centers/data_centers.csv",
            "desc": "Frontier AI data centers (project-level): current H100e, power MW, capital cost ($B), owner, users, investors."},
        "data_center_timelines": {"kind": "csv", "group": "compute_facilities",
            "url": f"{_EPOCH_BASE}/data_centers/data_center_timelines.csv",
            "desc": "Per-data-center time series: power MW, H100e, capital/compute/construction/operating cost, water use, construction status."},
        "data_center_chillers": {"kind": "csv", "group": "compute_facilities",
            "url": f"{_EPOCH_BASE}/data_centers/data_center_chillers.csv",
            "desc": "Cooling chiller equipment reference (capacity kW, dimensions)."},
        "data_center_cooling_towers": {"kind": "csv", "group": "compute_facilities",
            "url": f"{_EPOCH_BASE}/data_centers/data_center_cooling_towers.csv",
            "desc": "Cooling tower equipment reference (capacity kW, dimensions)."},
        # --- Chips (ZIP bundles, multiple member CSVs) ---
        "chip_sales": {"kind": "zip", "group": "chips",
            "url": f"{_EPOCH_BASE}/ai_chip_sales.zip",
            "members": ["organizations", "chip_types", "timelines_by_chip",
                        "cumulative_timelines", "cumulative_timelines_by_designer"],
            "desc": "AI chip sales: units, H100e compute, power MW, cost over time by chip + designer."},
        "chip_components": {"kind": "zip", "group": "chips",
            "url": f"{_EPOCH_BASE}/ai_chip_components.zip",
            "members": ["quarterly_by_chip", "quarterly_by_designer",
                        "cumulative_by_chip", "cumulative_by_designer",
                        "supply_denominators", "cumulative_supply_denominators"],
            "desc": "Logic wafer / CoWoS packaging / HBM consumption by chip + designer, with supply denominators."},
        "chip_owners": {"kind": "zip", "group": "chips",
            "url": f"{_EPOCH_BASE}/ai_chip_owners.zip",
            "members": ["cumulative_by_designer", "quarters_by_chip_type",
                        "cumulative_by_chip_type"],
            "desc": "AI compute distribution among owners (H100e, units) by chip type + designer."},
        # --- Companies / capabilities / polling ---
        "ai_companies": {"kind": "csv", "group": "companies",
            "url": f"{_EPOCH_BASE}/ai_companies.csv",
            "desc": "AI companies: staff, annualized revenue, valuation, equity funding, founding date."},
        "benchmarks": {"kind": "csv", "group": "capabilities",
            "url": f"{_EPOCH_BASE}/benchmarks.csv",
            "desc": "Per-run benchmark scores by task + model, with billable token counts."},
        "benchmark_data": {"kind": "zip", "group": "capabilities",
            "url": f"{_EPOCH_BASE}/benchmark_data.zip",
            "members": ["epoch_capabilities_index", "frontiermath",
                        "frontiermath_tier_4", "swe_bench_verified",
                        "gpqa_diamond", "math_level_5", "simpleqa_verified",
                        "gdpval_external", "metr_time_horizons_external",
                        "arc_agi_external", "arc_agi_2_external", "hle_external",
                        "mmlu_external", "otis_mock_aime_2024_2025", "eci_scaling"],
            "desc": "Benchmarking Hub: Epoch Capabilities Index (member "
                    "'epoch_capabilities_index' = single headline AI-capability "
                    "trajectory by model+date) plus ~50 per-benchmark score "
                    "series (frontiermath, swe_bench_verified, gpqa_diamond, "
                    "arc_agi(_2), gdpval, hle, metr_time_horizons, ...). Call "
                    "with no member= to list/return every series."},
        "polling": {"kind": "csv", "group": "adoption",
            "url": f"{_EPOCH_BASE}/polling_on_ai_usage_mar_2026.csv",
            "desc": "Polling on AI usage/adoption broken out by demographics (age, income, etc.)."},
    }

    _ALIASES = {
        "models": "notable_models", "notable": "notable_models",
        "frontier": "frontier_models",
        "large_scale": "large_scale_models", "large-scale": "large_scale_models",
        "all": "all_models", "biology": "biology_models",
        "hardware": "ml_hardware", "accelerators": "ml_hardware",
        "clusters": "gpu_clusters", "supercomputers": "gpu_clusters",
        "datacenters": "data_centers", "data centers": "data_centers",
        "timelines": "data_center_timelines",
        "companies": "ai_companies", "capabilities": "benchmarks",
        "benchmarking_hub": "benchmark_data", "benchmark_hub": "benchmark_data",
        "eci": "benchmark_data", "capabilities_index": "benchmark_data",
        "sales": "chip_sales", "components": "chip_components",
        "owners": "chip_owners",
    }

    def catalog(self, group: Optional[str] = None) -> List[Dict[str, Any]]:
        """List datasets (slug, group, kind, members, desc, url). Filter by
        group: models / hardware / compute_facilities / chips / companies /
        capabilities / adoption."""
        out = []
        for slug, meta in self.DATASETS.items():
            if group and meta["group"] != group:
                continue
            row = {"slug": slug, "group": meta["group"], "kind": meta["kind"],
                   "desc": meta["desc"], "url": meta["url"]}
            if meta["kind"] == "zip":
                row["members"] = meta["members"]
            out.append(row)
        return out

    def groups(self) -> List[str]:
        return sorted({m["group"] for m in self.DATASETS.values()})

    def _resolve(self, name: str) -> str:
        key = (name or "").strip().lower().replace(" ", "_")
        key = self._ALIASES.get(key, self._ALIASES.get(name.strip().lower(), key))
        if key not in self.DATASETS:
            raise AIBuildoutError(
                f"unknown Epoch dataset {name!r}; see epoch.catalog(). "
                f"slugs={sorted(self.DATASETS)}"
            )
        return key

    def url(self, name: str) -> str:
        """Resolve a dataset slug/alias to its download URL."""
        return self.DATASETS[self._resolve(name)]["url"]

    def get(self, name: str, *, member: Optional[str] = None,
            coerce: bool = True, max_mb: float = 80
            ) -> Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
        """Fetch a dataset by slug/alias. CSV datasets return rows; ZIP
        datasets return ``{member: rows}`` (or one member's rows if
        ``member`` is passed)."""
        key = self._resolve(name)
        meta = self.DATASETS[key]
        if meta["kind"] == "zip":
            return fetch_zip(meta["url"], member=member, coerce=coerce, max_mb=max_mb)
        if member is not None:
            raise AIBuildoutError(f"{key!r} is a CSV dataset; drop the member= arg.")
        return fetch_csv(meta["url"], coerce=coerce, max_mb=max_mb)


# --- Anthropic Economic Index -------------------------------------------------


class _AnthropicSource:
    """Thin discovery + fetch for the Anthropic Economic Index HF dataset."""

    REPO = "Anthropic/EconomicIndex"
    _TREE = f"https://huggingface.co/api/datasets/{REPO}/tree/main"
    _RESOLVE = f"https://huggingface.co/datasets/{REPO}/resolve/main"

    # Curated small rollups (alias -> repo path). Discover the rest via
    # list_files(); the guide documents the per-release file taxonomy.
    CURATED = {
        "job_exposure": "labor_market_impacts/job_exposure.csv",
        "task_penetration": "labor_market_impacts/task_penetration.csv",
        "automation_augmentation": "release_2025_03_27/automation_vs_augmentation_by_task.csv",
        "task_usage": "release_2025_03_27/task_pct_v2.csv",
        "soc_structure": "release_2025_03_27/SOC_Structure.csv",
        "wages": "release_2025_02_10/wage_data.csv",
    }

    def releases(self) -> List[str]:
        """Release folders, newest first (latest analyses live in the newest)."""
        tree = _get_json(self._TREE)
        out = [x["path"] for x in tree
               if x.get("type") == "directory" and x["path"].startswith("release_")]
        return sorted(out, reverse=True)

    def list_files(self, prefix: Optional[str] = None,
                   max_mb: Optional[float] = None) -> List[Dict[str, Any]]:
        """List CSV files (path + size_mb), optionally filtered by path prefix
        (a release folder or ``labor_market_impacts``) and/or a size cap."""
        tree = _get_json(self._TREE, params={"recursive": "true"})
        out = []
        for x in tree:
            p = x["path"]
            if not p.endswith(".csv"):
                continue
            if prefix and not p.startswith(prefix):
                continue
            size_mb = round(x.get("size", 0) / 1e6, 3)
            if max_mb is not None and size_mb > max_mb:
                continue
            out.append({"path": p, "size_mb": size_mb})
        return sorted(out, key=lambda r: r["path"])

    def fetch_csv(self, path_or_alias: str, *, max_mb: float = 25,
                  coerce: bool = True) -> List[Dict[str, Any]]:
        """Fetch a file by repo-relative path, or by a CURATED alias. Size-
        guarded -- the raw per-conversation dumps are 40-140 MB; raise max_mb
        to override."""
        path = self.CURATED.get(path_or_alias.strip().lower(), path_or_alias)
        url = f"{self._RESOLVE}/{path.lstrip('/')}"
        return fetch_csv(url, params={"download": "true"}, coerce=coerce, max_mb=max_mb)


# --- Cloud GPU / AI service pricing (Azure Retail Prices, OData) ---------------


class _CloudSource:
    """Thin OData query over the Azure Retail Prices catalog (no auth).

    The whole catalog is reachable -- PRISM writes the ``$filter`` using the
    grammar in the guide. v1 = Azure; AWS Price List + GCP Billing Catalog
    are deferred (see ROUTING)."""

    AZURE_ENDPOINT = "https://prices.azure.com/api/retail/prices"

    SERVICE_FAMILIES = (
        "AI + Machine Learning", "Analytics", "Azure Communication Services",
        "Blockchain", "Compute", "Containers", "Data", "Databases",
        "Developer Tools", "Integration", "Internet of Things",
        "Management and Governance", "Microsoft Syntex", "Networking", "Other",
        "Quantum Computing", "Security", "Storage", "Web",
        "Windows Virtual Desktop",
    )
    # GPU VM families (armSkuName prefix Standard_<fam>): ND training tier
    # (A100/H100/H200/GB200), NC compute/inference, NV visualization.
    GPU_VM_FAMILIES = ("NC", "ND", "NV")
    GPU_CHIPS = ("H100", "H200", "A100", "A10", "T4", "V100", "GB200",
                 "RTXPRO6000", "MI300")
    FILTERABLE_FIELDS = (
        "armRegionName", "location", "meterId", "meterName", "productId",
        "skuId", "productName", "skuName", "serviceName", "serviceId",
        "serviceFamily", "priceType", "armSkuName",
    )
    _REGION_ALIASES = {
        "us east": "eastus", "east us": "eastus", "useast": "eastus",
        "us east 2": "eastus2", "east us 2": "eastus2",
        "us west": "westus", "west us": "westus",
        "us west 2": "westus2", "west us 2": "westus2",
        "us west 3": "westus3", "west us 3": "westus3",
        "us central": "centralus", "central us": "centralus",
        "us south central": "southcentralus", "south central us": "southcentralus",
        "us north central": "northcentralus", "north central us": "northcentralus",
        "west europe": "westeurope", "north europe": "northeurope",
        "uk south": "uksouth", "southeast asia": "southeastasia",
        "japan east": "japaneast",
    }

    @classmethod
    def region(cls, name: Optional[str]) -> Optional[str]:
        """Normalize a friendly region name to its ARM code ("US East" ->
        "eastus"). Pass-through if already a code/unknown."""
        if not name:
            return name
        return cls._REGION_ALIASES.get(name.strip().lower(), name.strip())

    def query(self, filter: str, *, currency: str = "USD", max_pages: int = 20,
              coerce: bool = True) -> List[Dict[str, Any]]:
        """Run an Azure Retail Prices ``$filter`` and return all rows across
        pages (NextPageLink handled). Each row has armSkuName, retailPrice,
        unitOfMeasure, armRegionName, meterName, productName, serviceName,
        serviceFamily, type, etc."""
        params = {"$filter": filter}
        if currency and currency.upper() != "USD":
            params["currencyCode"] = currency.upper()
        out: List[Dict[str, Any]] = []
        url: Optional[str] = self.AZURE_ENDPOINT
        first = True
        pages = 0
        while url and pages < max_pages:
            data = _get_json(url, params=params if first else None)
            out.extend(data.get("Items", []))
            url = data.get("NextPageLink")
            first = False
            pages += 1
        return _coerce_rows(out) if coerce else out


# --- Source instances + discovery ---------------------------------------------

epoch = _EpochSource()
anthropic = _AnthropicSource()
cloud = _CloudSource()


SOURCES = {
    "epoch": {
        "name": "Epoch AI",
        "layer": "compute / chips / supercomputers / data centers / companies",
        "auth": "none (free CSV + ZIP, CC-BY)",
        "surface": "epoch.catalog([group]) / epoch.get(slug[, member]) / epoch.url(slug)",
    },
    "anthropic": {
        "name": "Anthropic Economic Index",
        "layer": "AI adoption / labor impact",
        "auth": "none (Hugging Face, CC-BY)",
        "surface": "anthropic.releases() / anthropic.list_files(prefix, max_mb) / "
                   "anthropic.fetch_csv(path_or_alias, max_mb)",
    },
    "cloud": {
        "name": "Azure Retail Prices (OData)",
        "layer": "compute valuation ($/GPU-hour, inference, storage, bandwidth)",
        "auth": "none",
        "surface": "cloud.query(odata_filter) / cloud.region(name)",
    },
}


# Themes this client deliberately does NOT cover -- they already have a client.
ROUTING = {
    "company capex / XBRL / filings": "sec_edgar_client (get_frames, "
        "get_company_facts, get_company_concept) -- e.g. Frames on "
        "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment for a hyperscaler "
        "capex panel",
    "macro time series (rates, GDP, CPI, IP)": "fred_client",
    "cross-border banking / credit / DSR": "bis_client",
    "petroleum / natural gas / STEO": "eia_client",
    "electricity demand by balancing authority / ISO": "electricity_client",
}


def list_sources() -> Dict[str, Dict[str, Any]]:
    """The sources this client covers (summary registry)."""
    return SOURCES


def describe(source: Optional[str] = None) -> Dict[str, Any]:
    """Describe one source (surface, auth, layer) or all + routing. For Epoch
    also pass through ``epoch.catalog()`` for the dataset list."""
    if source is None:
        return {"sources": SOURCES, "routing": ROUTING}
    key = source.strip().lower()
    if key not in SOURCES:
        raise AIBuildoutError(
            f"unknown source {source!r}; choose from {sorted(SOURCES)} "
            f"(other themes routed via ROUTING)"
        )
    return SOURCES[key]
