# API Endpoint Registry — Global Statistical Sources

The nine "global statistical office" client+context pairs in
`projects/apis/apis-payload/` (canonical copies; this file is the
endpoint-level reference). Every endpoint below is verified live. All
nine are Bucket C (plain `requests`, no GS proxy). For the older
US-centric registry (Treasury, FDIC, SEC, ...) see
`projects/apis/dev/endpoints.md`.

Each source exposes the same three-layer shape:

```
ENUMERATE the universe  ──►  SEARCH / INSPECT structure  ──►  PULL data
(catalogs, dataflows,        (dimensions, codelists,          (curated catalog
 databases, datasets)         metadata, constraints)           OR raw keys)
```

---

## 1. OECD — `oecd_client` / `oecd_guide.md`

Base: `https://sdmx.oecd.org/public/rest` — no auth.
Universe: ~1,540 dataflows across 40+ OECD directorates.

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /data/{AGENCY},{FLOW}/{key}?format=csvfile&startPeriod=&endPeriod=&lastNObservations=&firstNObservations=` | Observations, SDMX-CSV. Versionless flowRef = latest edition | `get_data`, `get_indicator` (24 verified keys incl. Economic Outlook forecasts), `get_panel` |
| `GET /dataflow/all/all/latest` | Full dataflow inventory (SDMX-ML XML) | `list_dataflows(search=)` → rows carry ready `flow_ref` |
| `GET /dataflow/{AGENCY}/{FLOW}/latest?references=all` | DSD dimension order + codelists | `get_dimensions`, `get_codelist`, `build_key` |

Quirks absorbed: CDN caches ignoring Accept headers → data uses the
`format=csvfile` query param, structure parsed as XML; 404 / `NoResultsFound`
→ clean `[]`.

## 2. Eurostat — `eurostat_client` / `eurostat_guide.md`

Base: `https://ec.europa.eu/eurostat/api/dissemination` — no auth.
Universe: ~7,000 datasets (EU members + aggregates + some US/JP).

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /statistics/1.0/data/{dataset}?format=JSON&lang=EN&{dim}={code}&sinceTimePeriod=&untilTimePeriod=&lastTimePeriod=` | Observations (JSON-stat 2.0, decoded to tidy rows; NAMED dim filters) | `get_data`, `get_indicator` (18 verified combos), `get_panel`, `describe_dataset` |
| `GET /catalogue/toc/txt?lang=en` | Full table of contents | `search_datasets(keyword)` |
| `GET /sdmx/2.1/contentconstraint/ESTAT/{dataset}` | Populated codes per dimension + TIME_PERIOD coverage (a few KB for any dataset size) | `get_constraints(dataset)` |

Quirks absorbed: Greece=`EL`, per-dataset euro-area aggregate (`EA`/`EA20`/
`EA21`), CA aggregate routing (`bop_c6_q` countries vs `bop_eu6_q`
aggregates with `partner=EXT_<agg>`), HTTP 413 extraction cap →
`get_constraints` discovery path, `latest_per_geo` for EDP ranking.

## 3. Bank of Japan — `boj_client` / `boj_guide.md`

Base: `https://www.stat-search.boj.or.jp/api/v1` — no auth.
Universe: full BOJ warehouse, ~50 databases (PR01 alone ~31,000 series).

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /getDataCode?format=json&lang=en&db={DB}&code={c1,c2,...}&startDate=&endDate=&startPosition=` | Series data by explicit codes (≤250/request, one frequency per call) | `get_data`, `get_indicator` (19 verified codes), `get_panel` |
| `GET /getDataLayer?format=json&lang=en&db={DB}&frequency={CY\|FY\|CH\|FH\|Q\|M\|W\|D}&layer={l1,l2,...}&startDate=&endDate=&startPosition=` | All series under a layer-tree position (≤1,250 matched) | `get_layer` |
| `GET /getMetadata?format=json&lang=en&db={DB}` | Per-database series metadata (daily refresh) | `get_metadata`, `search_series`; `list_databases` (embedded registry) |

Quirks absorbed: per-frequency date grammar both directions (`YYYYQQ` in,
`"2024-Q2"` out), NEXTPOSITION pagination, `DB'code` prefix strip, gzip,
nulls preserved (`drop_missing=` opt-out).

## 4. ChinaData.live — `chinadata_client` / `chinadata_guide.md`

Base: `https://chinadata.live/api/v2` — no auth (fair use ~100 req/min).
Universe: ~320 datasets + GACC trade (106 partners × 99 HS2 chapters,
~130 curated HS6/HS8 products), 2018-01 →.

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /datasets` | All dataset metadata | `list_datasets(category=, search=)` |
| `GET /search?q=` | Full-text dataset search | `search_datasets` |
| `GET /data/{dataset_id}` | One dataset + all points | `get_dataset`, `get_series` |
| `GET /trade/countries` | The exact trade-partner universe (~106 slugs + coverage) | `list_trade_countries(search=)` |
| `GET /trade/hs-codes` | The exact curated HS-product universe (~130 codes + flow) | `list_hs_codes(search=, flow=)` |
| `GET /trade/country/{slug}?breakdown=full` | Monthly bilateral trade + HS-chapter breakdowns | `get_country_trade(country, full_breakdown=, since=)` |
| `GET /trade/hs/{code}?flow=&period=&limit=` | HS product/chapter trade + partner rankings | `get_hs_trade` |
| `GET /trade/hs/{code}/country/{slug}?period=` | Bilateral product series (sparse curated pages) | `get_hs_country_trade` |

Quirks absorbed: country→slug aliasing, upstream unit split (country
endpoint USD-thousand vs HS endpoints full-USD → normalized to full USD),
HS-chapter `hs_label` names, suppressed prints stay `None` with QA
passthrough.

## 5. IMF — `imf_client` / `imf_guide.md`

Bases: `https://www.imf.org/external/datamapper/api/v1` (no key) and
`https://api.imf.org/external/sdmx/3.0` (Azure APIM key in
`IMF_API_PRIMARY_KEY`).
Universe: 132 indicators × 13 Datamapper datasets × 241 countries + 129
groups; keyed SDMX for the deep statistical tail.

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /datamapper/api/v1/{indicator}/{entity}?periods=` | Annual series (WEO, FM, GDD, ARA, FPP, ...) | `get_data`, `get_panel`, `get_series`, `latest`, `compare` |
| `GET /datamapper/api/v1/indicators` \| `/countries` \| `/groups` \| `/datasets` | Catalog refresh | `list_indicators`, `search_indicators`, `list_countries`, `list_groups`, `refresh_catalog` |
| `GET /sdmx/3.0/data/dataflow/{agency}/{flow}/{version}/{key}?startPeriod=&endPeriod=` | Keyed sub-annual data (CPI, BOP, IMTS, GFS, FSI, ER, rates) | `sdmx.data`, `sdmx.dataflows` (keyed); `sdmx.catalog`, `sdmx.build_path`, `sdmx.key_grammar` (offline) |

Quirk: the Akamai WAF 403s custom/browser User-Agents but allows default
`python-requests` — the client deliberately sets no custom UA.

## 6. Statistics Canada — `statcan_client` / `statcan_guide.md`

Bases: `https://www150.statcan.gc.ca/t1/wds/rest` (WDS JSON) and
`https://www150.statcan.gc.ca/t1/wds/sdmx/statcan/rest` (SDMX).
Universe: 5,070 active CODR cubes / 622 subjects (embedded index).

| Endpoint | Purpose | Client surface |
|---|---|---|
| `POST /wds/rest/getDataFromVectorsAndLatestNPeriods` etc. | Series by vector id | `get_vector`, `get_series_info` |
| `POST /wds/rest/getCubeMetadata` | Live cube DSD (dimensions + members) | `get_cube_metadata`, `get_dimensions`, `get_dimension_members` |
| `POST /wds/rest/getDataFromCubePidCoordAndLatestNPeriods` | Series by cube + coordinate | `get_data`, `query`, `build_coordinate` |
| `GET /wds/rest/getFullTableDownloadCSV/{pid}/en` | Whole-table CSV export | `get_full_table_url` |
| `GET /wds/sdmx/statcan/rest/data/{DF_PID}/{key}` | SDMX pulls | `get_data_sdmx` |
| (embedded index; no wire call) | Subject/cube enumeration + search | `list_subjects`, `cubes_by_subject`, `search_cubes`, `describe_cube`, `list_catalog`, `search_catalog` |

## 7. WID.world — `wid_client` / `wid_guide.md`

Base: `https://rfap9nitz6.execute-api.eu-west-1.amazonaws.com/prod/` —
`x-api-key` header (bundled official R-package key; `WID_API_KEY`
override).
Universe: 428 concept codes × 282 areas × percentiles × ages × pops
(ontology tables live in the guide).

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /countries-available-variables?countries=&variables=` | Available (sixlet, percentile, age, pop) combos per country | `list_available`, `download_wid` discovery phase |
| `GET /countries-variables?countries=&variables=&years=all` | Time series (follows `payload_too_large` → download_url) | `get_data`, `download_wid` |
| `GET /countries-variables-metadata?countries=&variables=` | Descriptive metadata (names, units, sources, quality) | `get_metadata` |

## 8. AI / Data-center buildout — `ai_buildout_client` / `ai_buildout_guide.md`

Three sources, no auth. Universe: every Epoch dataset (catalog), the full
Anthropic Economic Index HF tree, the whole Azure retail price catalog.

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET https://epoch.ai/data/{dataset}.csv` and `.zip` (models, ml_hardware, gpu_clusters, data_centers/*, ai_chip_*, ai_companies, benchmarks, benchmark_data, polling) | Epoch AI full universe | `epoch.catalog(group=)`, `epoch.get(slug, member=)`, `epoch.url` |
| `GET https://huggingface.co/api/datasets/Anthropic/EconomicIndex/tree/main?recursive=true` | AEI file universe | `anthropic.releases()`, `anthropic.list_files(prefix=, max_mb=)` |
| `GET https://huggingface.co/datasets/Anthropic/EconomicIndex/resolve/main/{path}?download=true` | AEI file fetch | `anthropic.fetch_csv(path_or_alias)` |
| `GET https://prices.azure.com/api/retail/prices?$filter=...` | Azure Retail Prices OData (NextPageLink paginated) | `cloud.query(filter)`, `cloud.region(name)` |

Routing (not covered here by design): capex/XBRL → `sec_edgar_client`,
macro → `fred_client`, cross-border credit → `bis_client`, energy →
`eia_client` / `electricity_client`.

## 9. ILOSTAT — `ilo_client` / `ilo_guide.md`

Base: `https://sdmx.ilo.org/rest` — no auth.
Universe: ~1,200 dataflows (labour statistics, all countries).

| Endpoint | Purpose | Client surface |
|---|---|---|
| `GET /data/ILO,DF_{FLOW}/{key}?format=csv&startPeriod=&endPeriod=&lastNObservations=&firstNObservations=&detail=` | Observations (SDMX-CSV) | `get_data`, `get_indicator` (30-indicator catalog) |
| `GET /dataflow/ILO?detail=allstubs` | Dataflow inventory | `list_dataflows(search=)` |
| `GET /datastructure/ILO/{DSD}?references=none` | Dimension order | `get_dimensions`, `build_key` |
| `GET /codelist/ILO/{CL}` | Codelists (`CL_AREA`, `CL_SEX`, `CL_ECO_AGGREGATE`, ...) | `get_codelist`, `get_areas` |

---

## Cross-source discoverability contract

Every pair passes the same test — from zero knowledge, PRISM can reach any
series in the universe through the client alone:

| Source | Enumerate | Search | Inspect structure | Pull raw |
|---|---|---|---|---|
| oecd | `list_dataflows()` (~1,540) | `list_dataflows("kw")` | `get_dimensions` + `get_codelist` | `build_key` → `get_data` |
| eurostat | TOC (~7,000) | `search_datasets` | `describe_dataset` / `get_constraints` | `get_data(**named_filters)` |
| boj | `list_databases()` (~50 DBs) | `search_series(db, kw)` | `get_metadata(db)` | `get_data` / `get_layer` |
| chinadata | `list_datasets()` + `list_trade_countries()` + `list_hs_codes()` | `search_datasets` | dataset metadata rows | `get_dataset` / trade getters |
| imf | `list_datasets()` (13) + `sdmx.catalog()` | `search_indicators` | `get_indicator(code)` meta | `get_data` / `sdmx.data` |
| statcan | `list_subjects()` → `cubes_by_subject()` (5,070 cubes) | `search_cubes` | `get_cube_metadata` / `get_dimension_members` | `query` / `get_vector` / `get_data_sdmx` |
| wid | guide ontology (428 concepts × 282 areas) | `list_available(country)` | `get_metadata` | `get_data` / `download_wid` |
| ai_buildout | `epoch.catalog()` + `anthropic.list_files()` | catalog search / file prefix | schemas in L2 guide | `epoch.get` / `fetch_csv` / `cloud.query` |
| ilo | `list_dataflows()` (~1,200) | `list_dataflows("kw")` | `get_dimensions` + `get_codelist` | `build_key` → `get_data` |
