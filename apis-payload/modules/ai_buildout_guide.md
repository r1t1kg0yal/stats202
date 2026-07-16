# AI / Data-Center Buildout

Sandbox name: `ai_buildout_client`
Layer: consolidated free pipes for a SemiAnalysis-style AI-buildout flow-of-funds — compute, chips, supercomputers, **frontier data centers (power/MW, capital cost, construction, water)**, AI adoption, and cloud GPU/inference pricing.
Auth: none for any source. Transport: Bucket C (plain `requests`).
Design: **thin client + catalog.** This module is transport + a dataset catalog, not per-question methods. This guide is the SSOT for the full data universe; **you write raw pandas/OData** against the thin fetchers. Returns are list-of-dicts with boundary numeric coercion (numeric strings already `int`/`float`; `""` -> `None`). `ai_buildout_client.to_dataframe(rows)` for pandas.

## Thin surface (write your own analysis on top)

| Call | Returns |
|---|---|
| `ai_buildout_client.epoch.catalog([group])` | list of all Epoch datasets (slug, group, kind, members, desc, url) |
| `ai_buildout_client.epoch.get(slug[, member=])` | CSV dataset -> rows; ZIP dataset -> `{member: rows}` (or one member's rows) |
| `ai_buildout_client.epoch.url(slug)` | resolve a slug to its download URL |
| `ai_buildout_client.anthropic.releases()` | release folders, newest first |
| `ai_buildout_client.anthropic.list_files(prefix, max_mb)` | CSV files (path + size_mb) in the HF repo |
| `ai_buildout_client.anthropic.fetch_csv(path_or_alias, max_mb)` | rows for a file path or curated alias |
| `ai_buildout_client.cloud.query(odata_filter)` | all rows across pages for an Azure Retail Prices `$filter` |
| `ai_buildout_client.cloud.region(name)` | "US East" -> "eastus" |
| `ai_buildout_client.fetch_csv(url)` / `fetch_zip(url[, member])` | generic CSV/ZIP fetch (size-guarded) |

Size guards: `fetch_csv`/`fetch_zip` raise (not truncate) above `max_mb` — steers away from the 40-140 MB Anthropic raw dumps. Raise `max_mb` to override.

## Triggers

**Primary** — Physical + demand layers with no clean feed elsewhere: training-compute and cost of frontier models; **AI-capability trajectory** (Epoch Capabilities Index + benchmark scores over time — FrontierMath, SWE-bench, GPQA, ARC-AGI, GDPval, METR time-horizons); AI accelerator specs/prices; GPU-cluster and **frontier data-center** fleet (power MW, capital cost, construction timelines, water use); AI chip sales/components/owners (units, H100-equivalents, power, wafer/CoWoS/HBM consumption, compute distribution); AI company revenue/funding/valuation; where AI is used by occupation/task (adoption, automation-vs-augmentation); cloud GPU rental $/hr and inference $/token; **CVE disclosure trends** among notable vendors (`cve_severity_monthly`).

**Not for** (route to the existing client) — company capex/filings (`sec_edgar_client`), macro series (`fred_client`), cross-border banking (`bis_client`), petroleum/nat-gas (`eia_client`), grid demand by balancing authority (`electricity_client`).

## Decision table — route these elsewhere

| Question | Client + call |
|---|---|
| Hyperscaler/neocloud **capex** panel | `sec_edgar_client.get_frames("us-gaap","PaymentsToAcquirePropertyPlantAndEquipment","USD","CY2025Q3")` |
| One company's financials over time | `sec_edgar_client.get_company_concept(cik,"us-gaap",concept)` |
| Macro rates/GDP/CPI/IP | `fred_client` |
| Cross-border banking, credit-to-GDP, DSR | `bis_client` |
| Petroleum, nat-gas, STEO | `eia_client` |
| Electricity demand by balancing authority/ISO | `electricity_client` |

`ai_buildout_client.describe()` returns the same routing programmatically (`ROUTING`).

---

## EPOCH AI — full dataset catalog

`epoch.get(slug)` for CSV; `epoch.get(slug, member="...")` for ZIP bundles. Aliases in parentheses.

| Slug (aliases) | Group | Kind | Contents |
|---|---|---|---|
| `notable_models` (`models`,`notable`) | models | csv | recommended cut; 3500+ models |
| `frontier_models` (`frontier`) | models | csv | top-10 by training compute at release |
| `large_scale_models` (`large_scale`) | models | csv | >= 1e23 FLOP |
| `all_models` (`all`) | models | csv | every model |
| `biology_models` (`biology`) | models | csv | bio/biomedical subset |
| `ml_hardware` (`hardware`,`accelerators`) | hardware | csv | 170+ AI accelerators |
| `gpu_clusters` (`clusters`,`supercomputers`) | compute_facilities | csv | 500+ clusters/supercomputers |
| `data_centers` (`datacenters`) | compute_facilities | csv | frontier AI data centers (project-level) |
| `data_center_timelines` (`timelines`) | compute_facilities | csv | per-DC time series (power/cost/water) |
| `data_center_chillers` | compute_facilities | csv | cooling chiller reference |
| `data_center_cooling_towers` | compute_facilities | csv | cooling tower reference |
| `chip_sales` (`sales`) | chips | zip | chip sales (units/H100e/power/cost) |
| `chip_components` (`components`) | chips | zip | logic wafer/CoWoS/HBM consumption |
| `chip_owners` (`owners`) | chips | zip | compute distribution among owners |
| `ai_companies` (`companies`) | companies | csv | revenue/funding/valuation/staff |
| `benchmarks` (`capabilities`) | capabilities | csv | per-run benchmark scores |
| `benchmark_data` (`benchmarking_hub`,`eci`) | capabilities | zip | Benchmarking Hub: Epoch Capabilities Index + ~50 per-benchmark series |
| `polling` | adoption | csv | AI-usage polling by demographic |
| `cve_severity_monthly` (`cve`,`cyber`,`vulnerabilities`) | cyber | csv | monthly High+Critical CVE counts from 21 notable CNAs |

Epoch's Cyber Vulnerabilities explorer (`epoch.ai/data/cve`) is built on
the CVE Program's `cvelistV5` GitHub dump. This client ships the thin
public aggregate CSV Epoch publishes for analysis; it does **not** mirror
the multi-GB record-level JSON tree.

### Key schemas (column names are exact; types are post-coercion)

**Models** (`notable_models`/`frontier_models`/`large_scale_models`/`all_models`): `Model`, `Organization`, `Country (of organization)`, `Publication date` (str `YYYY-MM-DD`), `Domain`, `Task`, `Parameters` (float), `Training compute (FLOP)` (float), `Training dataset size (total)` (float), `Training compute cost (2023 USD)` (float), `Training hardware`, `Hardware quantity` (int), `Training power draw (W)` (float), `Frontier model`, `Citations` (int), `Open model weights?`.

**`ml_hardware`**: `Hardware name`, `Manufacturer`, `Type`, `Release date`, `Release price (USD)` (float), `Tensor-FP16/BF16 performance (FLOP/s)`, `FP8 performance (FLOP/s)`, `FP4 performance (FLOP/s)`, `Memory (bytes)`, `Memory bandwidth (byte/s)`, `TDP (W)`, `Process size (nm)`, `Transistors (millions)` (all float).

**`gpu_clusters`**: `Name`, `Status` (download is `Existing` only), `Owner`, `Country` (e.g. `United States of America`, `China`), `Location`, `First Operational Date`, `H100 equivalents` (float), `Chip type (primary)`, `Chip quantity (primary)` (int), `Total number of AI chips` (int), `Power Capacity (MW)` (float, `None` if not estimated), `Hardware Cost`, `Sector`, `latitude`, `longitude` (float).

**`data_centers`** (frontier, project-level): `Name`, `Current H100 equivalents` (float), `Current power (MW)` (float), `Current total capital cost (2025 USD billions)` (float), `Owner`, `Users`, `Project`, `Investors`, `Construction companies`, `Energy companies`, `Country`, `Address`.
**`data_center_timelines`**: `Date`, `Construction status`, `IT power (MW)`, `Power (MW)`, `H100 equivalents`, `Performance (8-bit OP/s)`, `Total capital cost (2025 USD billions)`, `Compute cost (...)`, `Construction cost (...)`, `Annual operating cost (...)`, `Water use (MGD)`, `Data center` (the DC name, joins to `data_centers.Name`).

**`chip_sales`** members (`epoch.get("chip_sales", member=...)`): `organizations`, `chip_types` (`H100e`, `Cost per chip (approx.)`, `TDP (W)`, `8-bit OP/s`), `timelines_by_chip`, `cumulative_timelines`, `cumulative_timelines_by_designer`. The designer/manufacturer key is **`Chip manufacturer`** (`Nvidia`, `AMD`, `Google`, `Amazon`, `Huawei`, `Cambricon`); **`Name`** is just a window label (e.g. `"AMD total Q1 2024 to Q1 2025"`). Time axis = `End date` (with `Start date`). Metrics come as `(median, 5th percentile, 95th percentile)` triples: `Compute estimate in H100e (median)`, `Number of units (median)`, `Power in MW (median)`. Use `cumulative_timelines_by_designer` for the spend/power/compute trajectory by designer.

**`chip_components`** members: `quarterly_by_chip`, `quarterly_by_designer`, `cumulative_by_chip`, `cumulative_by_designer` (`Logic wafers (median)`, `Logic cost (USD) (median)`, CoWoS/HBM columns), `supply_denominators`, `cumulative_supply_denominators` (`Logic supply (median)`, `CoWoS supply (median)`).
**`chip_owners`** members: `cumulative_by_designer`, `quarters_by_chip_type`, `cumulative_by_chip_type` (`Owner`, `Chip manufacturer`, `Chip type`, `Compute estimate in H100e (median)`, `Number of Units (median)`).

**`ai_companies`**: `Name`, `Company type`, `Product Domain(s)`, `Staff count` (int), `Annualized revenue (USD)` (float), `Valuation` (float), `Total equity funding` (float), `Founding date`.
**`benchmarks`**: `task`, `model`, `Best score (across scorers)`, `Status`, `billable_input_tokens`, `billable_output_tokens`.
**`benchmark_data`** (ZIP, `epoch.get("benchmark_data", member=...)`): the AI-capability trajectory layer. Member `epoch_capabilities_index` (the headline **Epoch Capabilities Index** — one aggregate capability score per model: `Model version`, `ECI Score`, `Release date`, `Organization`, `Country`, `Model accessibility`, `Training compute (FLOP)`, `Confidence`, `Display name`). ~50 per-benchmark members (`frontiermath`, `frontiermath_tier_4`, `swe_bench_verified`, `gpqa_diamond`, `math_level_5`, `simpleqa_verified`, `gdpval_external`, `metr_time_horizons_external`, `arc_agi_external`, `arc_agi_2_external`, `hle_external`, `mmlu_external`, `gsm8k_external`, ...) each shaped `Model version`, `mean_score`, `Best score (across scorers)`, `Release date`, `Organization`, `Country`, `Training compute (FLOP)`, `stderr`, `id`. Member `eci_scaling` carries the ECI-vs-compute fit (`a`, `b`, `scaling_anchor1/2`, `..._eci`). Call `epoch.get("benchmark_data")` (no member) to enumerate every series.
**`polling`**: `Question`, `Response`, `Overall` + demographic columns (`Age: 18-29`, `Income: $100K+`, ...).
**`cve_severity_monthly`**: `month` (`YYYY-MM`), `critical` (int), `high` (int) — notable-CNA High/Critical counts only.

---

## ANTHROPIC ECONOMIC INDEX (Hugging Face)

Repo `Anthropic/EconomicIndex`. Discover with `releases()` + `list_files(prefix, max_mb)`; fetch with `fetch_csv(path_or_alias)`.

**Curated aliases** (small rollups, fetch by alias):

| Alias | Path | Columns |
|---|---|---|
| `job_exposure` | `labor_market_impacts/job_exposure.csv` | `occ_code` (SOC), `title`, `observed_exposure` (0-1) |
| `task_penetration` | `labor_market_impacts/task_penetration.csv` | `task`, `penetration` (0-1) |
| `automation_augmentation` | `release_2025_03_27/automation_vs_augmentation_by_task.csv` | `task_name`, `feedback_loop`,`directive`,`task_iteration`,`validation`,`learning`,`filtered` |
| `task_usage` | `release_2025_03_27/task_pct_v2.csv` | `task_name`, `pct` (share of usage) |
| `soc_structure` | `release_2025_03_27/SOC_Structure.csv` | SOC occupation hierarchy |
| `wages` | `release_2025_02_10/wage_data.csv` | BLS wage by occupation |

**File taxonomy** — `labor_market_impacts/` holds the release-agnostic rollups (`job_exposure`, `task_penetration`). Each `release_YYYY_MM_DD/` holds that vintage's outputs: `automation_vs_augmentation*`, `task_pct_v1/v2`, `onet_task_statements`, `SOC_Structure`, `wage_data`, plus (2025-09-15+) geographic/GDP/population inputs under `data/input` + `data/intermediate`. Newest releases (`release_2026_03_24`, `release_2026_01_15`) carry only the **40-140 MB raw conversation dumps** (`aei_raw_*`) — use `list_files(prefix="release_2026_03_24", max_mb=2)` to confirm before fetching; the curated rollups live in the 2025 releases. Always `list_files(max_mb=2)` to find small files.

---

## CLOUD — Azure Retail Prices (OData, no auth)

`cloud.query(odata_filter)` runs a `$filter` and returns all rows across pages. The **whole Azure catalog** is reachable — write the filter from this grammar.

**Filter grammar:** `field eq 'value'` joined by ` and `; `contains(field,'substr')`; values are **case-sensitive**. Filterable fields: `serviceName`, `serviceFamily`, `armRegionName`, `armSkuName`, `meterName`, `productName`, `skuName`, `priceType`, `productId`, `skuId`, `meterId`, `isPrimaryMeterRegion`. **`unitOfMeasure` is NOT OData-filterable** — fetch then filter in pandas.

**Row fields:** `armSkuName`, `retailPrice` (float), `unitPrice` (float), `unitOfMeasure` (`1 Hour` for VMs; `1M` / `1K` = per-million / per-thousand tokens for inference), `armRegionName`, `meterName`, `productName`, `serviceName`, `serviceFamily`, `type` (= priceType), `currencyCode`, `isPrimaryMeterRegion` (bool), `effectiveStartDate`.

**serviceFamily catalog (20):** `AI + Machine Learning`, `Analytics`, `Azure Communication Services`, `Blockchain`, `Compute`, `Containers`, `Data`, `Databases`, `Developer Tools`, `Integration`, `Internet of Things`, `Management and Governance`, `Microsoft Syntex`, `Networking`, `Other`, `Quantum Computing`, `Security`, `Storage`, `Web`, `Windows Virtual Desktop`.

**Buildout-relevant entry points:**

| Layer | Filter |
|---|---|
| GPU VM rental ($/hr) | `serviceName eq 'Virtual Machines' and contains(armSkuName,'Standard_ND')` (families NC/ND/NV) |
| Specific accelerator | `... and contains(armSkuName,'H100')` (chips: H100/H200/A100/A10/T4/V100/GB200/RTXPRO6000/MI300) |
| AI inference ($/M tokens) | `serviceName eq 'Foundry Models'` then pandas-filter `unitOfMeasure == '1M'` (productName = model e.g. `Azure OpenAI GPT5`; meterName ends `1M Tokens`) |
| Managed ML | `serviceName eq 'Azure Machine Learning'` |
| Storage | `serviceFamily eq 'Storage'` |
| Egress bandwidth | `serviceName eq 'Bandwidth'` |

**Pricing meter semantics:** `priceType eq 'Consumption'` = pay-as-you-go (vs `'Reservation'`). On-demand GPU price = exclude `meterName` containing `Spot` or `Low Priority`. Linux = `productName` without `Windows`. Add `isPrimaryMeterRegion eq true` to the filter to dedupe regional mirrors (it IS OData-filterable). `cloud.region("US East")` -> `"eastus"`.

---

## Recipes (write your own — these are starting points)

```python
import pandas as pd
ab = ai_buildout_client

# 1. Frontier data-center power + capex buildout (the binding constraint)
dc = ab.to_dataframe(ab.epoch.get("data_centers"))
top_power = dc.sort_values("Current power (MW)", ascending=False)[
    ["Name","Owner","Current power (MW)","Current total capital cost (2025 USD billions)","Country"]].head(15)
# per-DC trajectory over time:
tl = ab.to_dataframe(ab.epoch.get("data_center_timelines"))
tl["date"] = pd.to_datetime(tl["Date"], errors="coerce")

# 2. AI chip compute + power build by designer (H100e + MW over time)
des = ab.to_dataframe(ab.epoch.get("chip_sales", member="cumulative_timelines_by_designer"))
des["date"] = pd.to_datetime(des["End date"], errors="coerce")   # Name is a window label
build = des.sort_values("date")[["date","Chip manufacturer","Compute estimate in H100e (median)","Power in MW (median)"]]

# 3. Frontier model training-compute trend (NOT pre-sorted; sort yourself)
m = ab.to_dataframe(ab.epoch.get("frontier"))
m["date"] = pd.to_datetime(m["Publication date"], errors="coerce")
trend = m.dropna(subset=["Training compute (FLOP)","date"]).sort_values("date")

# 3b. AI-capability trajectory: Epoch Capabilities Index over time
eci = ab.to_dataframe(ab.epoch.get("benchmark_data", member="epoch_capabilities_index"))
eci["date"] = pd.to_datetime(eci["Release date"], errors="coerce")
eci_curve = eci.dropna(subset=["ECI Score","date"]).sort_values("date")
# one specific benchmark's score trajectory (frontier saturation):
fm = ab.to_dataframe(ab.epoch.get("benchmark_data", member="swe_bench_verified"))
fm["date"] = pd.to_datetime(fm["Release date"], errors="coerce")
fm_curve = fm.dropna(subset=["mean_score","date"]).sort_values("date")

# 4. AI companies by revenue / funding
co = ab.to_dataframe(ab.epoch.get("ai_companies"))
by_rev = co.sort_values("Annualized revenue (USD)", ascending=False)

# 5. AI adoption + usage-weighted automation vs augmentation
je = ab.to_dataframe(ab.anthropic.fetch_csv("job_exposure"))
top_occ = je.sort_values("observed_exposure", ascending=False).head(20)
aa = ab.to_dataframe(ab.anthropic.fetch_csv("automation_augmentation"))
tu = ab.to_dataframe(ab.anthropic.fetch_csv("task_usage"))
mix = aa.merge(tu, on="task_name", how="inner")
automation   = (mix[["directive","feedback_loop"]].sum(axis=1) * mix["pct"]).sum()
augmentation = (mix[["task_iteration","learning","validation"]].sum(axis=1) * mix["pct"]).sum()

# 6. Azure GPU $/hr on-demand H100 in US East
rows = ab.cloud.query(
    f"serviceName eq 'Virtual Machines' and armRegionName eq '{ab.cloud.region('US East')}' "
    f"and contains(armSkuName,'H100') and priceType eq 'Consumption' and isPrimaryMeterRegion eq true")
g = ab.to_dataframe(rows)
ondemand = g[~g["meterName"].str.contains("Spot|Low Priority", na=False)
             & ~g["productName"].str.contains("Windows", na=False)]
cheapest = ondemand.sort_values("retailPrice").iloc[0]

# 7. Azure inference $ per 1M tokens (unitOfMeasure is NOT OData-filterable; filter in pandas)
inf = ab.to_dataframe(ab.cloud.query("serviceName eq 'Foundry Models'"))
tokens = inf[inf["unitOfMeasure"] == "1M"]   # productName = model; meterName ends "1M Tokens"
by_model = tokens.sort_values("retailPrice", ascending=False)[
    ["productName","meterName","retailPrice","armRegionName"]]

# 8. Hyperscaler capex panel -- DEFER to sec_edgar_client (its own L2 loads in PRISM)
# Named-ticker panel (recommended): resolve_company returns a LIST of {cik,ticker,title}.
capex = {}
for t in ["MSFT", "GOOGL", "AMZN", "META"]:
    cik = sec_edgar_client.resolve_company(t)[0]["cik"]
    capex[t] = sec_edgar_client.get_company_concept(
        cik, "us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment")
# Or one cross-filer cut for a period (frame rows carry cik + entityName + val):
panel = sec_edgar_client.get_frames(
    "us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment", "USD", "CY2025Q3")

# 9. Frontier DC buildout vs hyperscaler capex (side-by-side; different grains, no join key)
tl = ab.to_dataframe(ab.epoch.get("data_center_timelines"))
tl["date"] = pd.to_datetime(tl["Date"], errors="coerce")
dc_power_ts = tl.groupby("date", as_index=False)["Power (MW)"].sum()
# capex (company x quarter) and dc_power_ts (date x MW) align on period, not a shared key --
# present as two panels / a dual-axis view, not a merge.
```

## Domain semantics

- **H100e / H100 equivalents** = compute normalized to one H100; Epoch's cross-chip compute unit (used in clusters, data centers, chip sales/owners).
- **`gpu_clusters` vs `data_centers`.** `gpu_clusters` = broad historical hardware facilities (a cluster may be part of one building). `data_centers` = project-level frontier DCs from satellite/permit/disclosures, focused on the largest current/upcoming sites; ~15% of global delivered AI compute as of late 2025. Power estimates carry ~1.4x 80%-confidence uncertainty; cost ~1.6x. User/owner tags `Speculative`/`Likely` flag low-confidence affiliations.
- **Uncertainty triples.** Chip datasets report `(5th percentile, median, 95th percentile)` columns — use the `median` for point estimates.
- **Automation vs augmentation (Anthropic).** Automation = `directive` + `feedback_loop`; Augmentation = `task_iteration` + `learning` + `validation`; `filtered` excluded (shares won't sum to 1). Usage-weight by merging with `task_usage` on `task_name` (recipe 5).
- **`observed_exposure`** = share of an occupation's O*NET tasks seen in Claude usage (adoption proxy, not wages/employment).
- **Frontier models are NOT pre-sorted by compute** — `frontier` is the *set* of release-time top-10 models; sort by `Training compute (FLOP)` yourself.
- **Epoch dates are strings** (`YYYY-MM-DD`) — `pd.to_datetime` for a time axis.
- **`polling` slug is date-stamped** (`polling_on_ai_usage_mar_2026`); confirm the current slug via `epoch.catalog(group="adoption")` if it 404s.

## Coverage gaps (next sources, deferred)

Keyed sources queued (need free API keys): EIA v2 electricity RTO load by ISO, Census C30 data-center construction + BTOS AI-adoption, BEA NIPA data-center investment, BLS PPI 518210 cloud deflator. The financing layer (FINRA TRACE, EDGAR ABS/8-K full-text) is genuinely thin in free data. Company capex is reachable today via `sec_edgar_client` Frames (recipe 8).
