# SEC Data & Research (structured datasets + IM statistics)

Sandbox name: `sec_data_research_client`
Base URL: `https://www.sec.gov/data-research`
Auth: SEC User-Agent header only (no API key). Respect ~10 req/s fair-access limit.
Transport: Bucket B for HTML page scrapes (`manual_https_request`); binary file downloads use `requests` (ZIP/CSV/XLSX must stay byte-accurate).
Design: **catalog + scraper + local store.** 200 dataset pages indexed; download URLs scraped live from each page; files stored under `store_root` (default staging: `projects/apis/dev/data/sec_data_research/store/`).

## Triggers

**Use for** — Aggregated SEC research datasets scraped from https://www.sec.gov/data-research:

| Section | What you get |
|---|---|
| `data_library` (36 pages) | DERA structured ZIP/TSV sets: Form N-MFP (MMF holdings), N-PORT (fund portfolios), 13F, Form D, N-CEN, financial statement data sets, insider transactions (Forms 3/4/5), BDC, crowdfunding, Reg A, transfer agent, market-structure, RIA FOIA ADV extracts, municipal advisors, series/class, CEF, VIP, etc. |
| `investment_management` (6 pages) | Division of Investment Management statistics: **Form PF private-fund stats** (PDF + Excel), investment-adviser statistics, **MMF statistics**, registered-fund statistics, annual RIC update. |
| `statistics` (158 pages) | Visualization backing CSV/PDF for IPOs, Reg D/CF/A offerings, ABS/CMBS, corporate bonds, reporting issuers, NRSROs, municipal advisors, registered investment companies, private-fund viz slices, investment-adviser viz slices. |

**Not for** (route elsewhere):

| Question | Client |
|---|---|
| One company's EDGAR filings, XBRL facts, full-text search | `sec_edgar_client` |
| Cross-company XBRL frames (us-gaap concept panels) | `sec_edgar_client.get_frames(...)` |
| Raw filer-level Form PF (confidential) | Not public — use aggregated `sec_data_research_client.get('form_pf')` only |

`sec_data_research_client.ROUTING` returns the same table programmatically.

## Thin surface

| Call | Returns |
|---|---|
| `catalog(section, query)` | 200 dataset pages (`slug`, `title`, `section`, `url`, `n_data`, `n_docs`) |
| `describe(slug_or_alias)` | page metadata + live-scraped `data_files` / `docs` URL lists |
| `list_files(slug, kind='data')` | `{'data': [...]}` or `{'docs': [...]}` |
| `latest(slug, ext=None)` | newest data-file URL (filename date heuristic) |
| `download(slug, dest_dir, latest_only=True)` | scrape + store; returns local `Path`s |
| `get(slug, file=, member=, url=)` | fetch + parse: ZIP -> `{member: rows}`, CSV -> rows, XLSX -> rows |
| `sync(section, dest_dir, latest_only=True)` | batch download all datasets in a section |
| `sync_universe(cluster=, section=, dry_run=)` | plan or run cluster/section/full-universe sync |
| `plan_sync(cluster=, section=, latest_only=)` | dry-run manifest only |
| `cluster(name)` | themed page list (`form_pf_adjacent`, `full_universe`, ...) |
| `summary()` | universe counts by section + cluster sizes |
| `refresh_catalog()` | re-crawl the 200-page index from sec.gov |
| `to_dataframe(rows)` | pandas helper |

**Aliases** (common): `form_pf`, `n_mfp`, `form_13f`, `form_n_port`, `form_d`, `financial_statements`, `insider`, `bdc`, `mmf_statistics`, `registered_fund_statistics`, `ria_foia`, etc. — see `ALIASES` in the client.

## Data library — key datasets

Full list: `catalog(section='data_library')`. High-traffic sets:

| Slug (alias) | Form / topic | Typical file | Parse |
|---|---|---|---|
| `dera-form-n-mfp-data-sets` (`n_mfp`, `mmf_holdings`) | Form N-MFP monthly MMF portfolio | `*_nmfp.zip` (~weekly) | ZIP of TSV tables |
| `form-n-port-data-sets` (`n_port`) | Form N-PORT fund holdings | `2026q1_nport.zip` | ZIP of TSV |
| `form-13f-data-sets` (`13f`) | Institutional 13F holdings | `*_form13f.zip` (quarterly) | ZIP |
| `form-d-data-sets` (`form_d`, `reg_d`) | Reg D private offerings | `2026q1_d.zip` | ZIP (~6 CSV members) |
| `form-n-cen-data-sets` | Investment company census | quarterly ZIP | ZIP |
| `financial-statement-data-sets` (`fsds`) | XBRL financial statement extracts | `2026q1.zip` | ZIP (SUB/NUM/PRE/TAG tables) |
| `financial-statement-notes-data-sets` | FS note tags | quarterly ZIP | ZIP |
| `insider-transactions-data-sets` (`insider`) | Forms 3/4/5 | `2026q1_form345.zip` | ZIP |
| `bdc-data-sets` (`bdc`) | Business development companies | monthly ZIP | ZIP |
| `money-market-fund-information` (`mmf_info`) | MMF disclosure CSV/XML | `mmf-YYYY-MM.csv` | CSV rows (monthly) |
| `crowdfunding-offerings-data-sets` | Reg CF | quarterly ZIP | ZIP |
| `regulation-data-sets` | Reg A | quarterly ZIP | ZIP |
| `transfer-agent-data-sets` | Transfer agents | quarterly ZIP | ZIP |
| `information-about-registered-investment-advisers-exempt-reporting-advisers` (`ria_foia`) | Form ADV FOIA | many ZIP snapshots | ZIP |
| `market-structure-data-security-exchange` | Market structure | quarterly ZIP | ZIP |
| `investment-company-series-class-information` | Series/class master | periodic ZIP | ZIP |
| `closed-end-fund-information` (`cef`) | CEF data | periodic ZIP | ZIP |

ZIP members vary by dataset — call `get(slug)` with no `member=` to enumerate keys, then `get(slug, member='SUB')` (example for FSDS).

## Investment management — Form PF / advisers / MMF / registered funds

| Slug (alias) | Source forms | Files | Notes |
|---|---|---|---|
| `division-investment-management-private-fund-statistics` (`form_pf`) | Form PF + ADV (aggregated) | quarterly PDF + `*-supporting-data.xlsx` or `.xlsx` | **Not filer-level PF.** Masked aggregates (`***`). Excel has 140+ tables from 2013Q1. |
| `division-investment-management-investment-adviser-statistics` | Form ADV | PDF + supporting XLSX | RIA industry aggregates |
| `money-market-fund-statistics` (`mmf_statistics`) | Form N-MFP derived | monthly PDF + XLSX | IM division MMF trends |
| `division-investment-management-registered-fund-statistics` | Form N-PORT/N-CEN derived | PDF + supporting XLSX | Registered fund aggregates |
| `division-investment-management-annual-registered-investment-company-update` | RIC annual | PDF | Narrative + charts |

**Form PF domain semantics:** Only SEC-registered advisers with >= $150M private-fund AUM file Form PF. Smaller RIAs, ERAs, and state advisers appear only via Form ADV aggregates. Published stats are >= ~6 months lagged, rounded/masked. For Fed-level private-fund aggregates also see FRB Financial Accounts.

## Statistics / visualizations section

158 pages — mostly one backing CSV/PDF per visualization (IPO counts, Reg D proceeds by issuer type, ABS/CMBS issuance, corporate bond offerings, accredited-investor households, etc.). Discover with `catalog(section='statistics', query='ipo')`. Many pages are chart-only with a single CSV attachment.

## Format quirks (wrapper absorbs)

- **Slug aliases** — `form_pf`, `13f`, `n_mfp`, etc. resolve to canonical page slugs via `ALIASES`.
- **Latest file** — `latest(slug)` sorts by numeric tokens in filename (year/quarter/month), not HTTP Last-Modified.
- **ZIP parse** — `get(slug)` returns `{member_path: rows}` for all CSV/TSV members; pass `member=` substring match.
- **Numeric coercion** — CSV/XLSX string numerics coerced to int/float at boundary; empty strings -> `None`.
- **Rate limits** — SEC returns "Request Rate Threshold Exceeded" HTML on aggressive crawls; client raises `SecDataResearchError` (backoff, don't retry blindly).
- **Size guard** — `get(..., max_mb=120)` default; raise for full-history 13F/N-MFP ZIPs if needed.

## Storage layout

```
{store_root}/
  manifest.json                          # per-slug download log
  data_library/{slug}/{filename}.zip
  investment_management/{slug}/{file}.xlsx
  statistics/{slug}/{file}.csv
```

`download(slug)` writes under section/slug. `sync(section='data_library')` batch-fetches latest file per dataset.

## Python recipes

```python
# 1. Discover the universe
sec_data_research_client.catalog()                          # all 200 pages
sec_data_research_client.catalog(section="data_library")
sec_data_research_client.catalog(query="money market")

# 2. Form PF — latest supporting Excel (aggregated industry stats)
meta = sec_data_research_client.describe("form_pf")
url = sec_data_research_client.latest("form_pf", ext="xlsx")
rows = sec_data_research_client.get("form_pf")               # parses XLSX sheet 0

# 3. MMF holdings — Form N-MFP latest ZIP
bundle = sec_data_research_client.get("n_mfp")               # all TSV members
# or one table:
sub = sec_data_research_client.get("n_mfp", member="MFPORT")

# 4. 13F institutional holdings — latest quarter ZIP
sec_data_research_client.download("form_13f", latest_only=True)
holdings = sec_data_research_client.get("form_13f")

# 5. Reg D private placements — latest quarter
reg_d = sec_data_research_client.get("form_d")               # ~6 CSV members

# 6. Financial statement data sets (XBRL extract tables)
fsds = sec_data_research_client.get("financial_statements")
# members typically include SUB, NUM, PRE, TAG, etc.

# 7. Batch sync an entire section to local store
sec_data_research_client.sync(section="investment_management", latest_only=True)

# 8. MMF monthly CSV (not N-MFP ZIP — lighter monthly disclosure file)
mmf_rows = sec_data_research_client.get("mmf_info", file="mmf-2026-04.csv")
df = sec_data_research_client.to_dataframe(mmf_rows)
```

## sec_edgar_client vs sec_data_research_client

| Need | Client |
|---|---|
| Apple 10-K text, company XBRL facts, CIK lookup | `sec_edgar_client` |
| All filers' Revenue in CY2025Q3 (XBRL frame) | `sec_edgar_client.get_frames(...)` |
| Aggregated private-fund AUM/strategy stats (Form PF derived) | `sec_data_research_client.get('form_pf')` |
| MMF portfolio holdings across all funds (N-MFP) | `sec_data_research_client.get('n_mfp')` |
| All 13F holdings for a quarter (structured ZIP) | `sec_data_research_client.get('form_13f')` |
| Reg D capital raised panels | `sec_data_research_client.get('form_d')` |

## Clusters & full-universe sync

| Cluster | Reach |
|---|---|
| `form_pf_adjacent` | Form PF IM page + private-fund viz slices + adviser stats + MMF (N-MFP/stats/viz) + registered funds + N-PORT/N-CEN/13F + RIA FOIA |
| `data_library_all` | All 36 DERA structured datasets |
| `investment_management_all` | All 6 IM division report pages |
| `statistics_all` | All 158 visualization backing pages |
| `capital_markets` | IPOs, FROs, Reg D/CF/A, corporate bonds, ABS/CMBS |
| `fund_holdings` | N-MFP, N-PORT, 13F, MMF info |
| `full_universe` | All 200 catalog pages |

```python
sec_data_research_client.cluster("form_pf_adjacent")
sec_data_research_client.plan_sync(cluster="full_universe")              # dry-run
sec_data_research_client.sync_universe(cluster="form_pf_adjacent", dry_run=True)
sec_data_research_client.sync_universe(cluster="full_universe")          # RUN — huge
```

## Interactive CLI (staging)

```bash
python projects/apis/apis-payload/clients/sec_data_research_client.py
```

Bare run opens nested menu: summary → browse section/cluster → search → per-dataset actions (describe / list / download latest or ALL / get) → sync planner (dry-run) → full-universe sync (type YES).

Non-interactive: `--summary`, `--catalog [--section] [--query]`, `--cluster NAME`, `--describe SLUG`, `--list-files SLUG`, `--get SLUG`, `--download SLUG [--all-files]`, `--sync --universe --dry-run`, `--refresh-catalog`.

Strip `if __name__` before PRISM drop; library API unchanged.
