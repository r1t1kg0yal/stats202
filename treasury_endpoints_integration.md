# Treasury & TreasuryDirect — New Endpoints Integration Guide

Target files in PRISM:
- `treasury_client.py`           (PRISM-side Fiscal Data API wrapper + TIC scraper)
- `treasury_direct_client.py`    (PRISM-side TreasuryDirect.gov scraper)
- Consolidated skill file        (combined Treasury + TreasuryDirect SKILL.md)
- TIC skill file                 (separate, written by Ritik)

This doc is self-contained. You should not need to read the staging
`treasury.py` / `treasurydirect.py` to fold these in — every endpoint below
ships with its full URL, parameter spec, response schema, sample row, and
suggested CLI / Python signatures.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HOW TO READ THIS DOC                                                        │
│                                                                              │
│  Section 1   Quick-reference map of every gap, by tier and target client     │
│  Section 2   Fiscal Data API additions       → treasury_client.py            │
│  Section 3   TIC (foreign holdings) scraper  → treasury_client.py            │
│  Section 4   Quarterly refunding XML feeds   → treasury_direct_client.py     │
│  Section 5   Consolidated skill file updates (paste-ready)                   │
│  Section 6   Integration checklist                                           │
│  Section 7   Appendices: filter syntax, schemas, sample responses            │
└─────────────────────────────────────────────────────────────────────────────┘
```

Note: TIC code lives inside `treasury_client.py` but is documented in its own
dedicated skill file (written separately). Section 5 of this doc — the
consolidated Treasury skill file updates — therefore omits TIC entries on
purpose.

---

## 1. Quick-Reference Map

```
┌──────────────────────────────────────────┬──────────────────────────────┬──────────────┐
│ Source                                   │ Target client                │ Tier / impact│
├──────────────────────────────────────────┼──────────────────────────────┼──────────────┤
│ Fiscal Data API (within api.fiscaldata.treasury.gov)                                    │
│   buybacks_security_details              │ treasury_client.py           │ T1  high     │
│   tips_cpi_data_summary                  │ treasury_client.py           │ T1  high     │
│   tips_cpi_data_detail                   │ treasury_client.py           │ T1  high     │
│   ofs2_estimated_ownership_treasury      │ treasury_client.py           │ T1  high     │
│   ofs1_distribution_federal_securities   │ treasury_client.py           │ T1  med      │
│   pdo1_offerings_regular_weekly_…        │ treasury_client.py           │ T2  med      │
│   pdo2_offerings_marketable_securities_… │ treasury_client.py           │ T2  med      │
│   federal_maturity_rates                 │ treasury_client.py           │ T2  med      │
│   receipts_by_department                 │ treasury_client.py           │ T2  med      │
│   slgs_demand_deposit_rates              │ treasury_client.py           │ T2  low-med  │
│   slgs_time_deposit_rates                │ treasury_client.py           │ T2  low-med  │
│   fcp1 / fcp2 / fcp3 (FX positions)      │ treasury_client.py           │ T2  low-med  │
│   esf1_balances + esf2_statement_net_cost│ treasury_client.py           │ T2  low-med  │
│                                                                                          │
│ Outside Fiscal Data API                                                                  │
│   TIC monthly data files                 │ treasury_client.py           │ T1  high     │
│     mfh.txt, snetus.csv, etc.            │   (separate TIC skill file)  │              │
│                                                                                          │
│   Quarterly refunding XMLs               │ treasury_direct_client.py    │ T1  med-high │
│     auction-schedule.xml                 │                              │              │
│     buyback-schedule.xml                 │                              │              │
│     primary-dealer-survey.pdf            │                              │              │
└──────────────────────────────────────────┴──────────────────────────────┴──────────────┘
```

Recommended integration order (highest data-per-effort first):

```
┌──────────────────────────────────────────────────────────────────────┐
│  1.  buybacks_security_details      one endpoint, big PRISM value    │
│  2.  tips_cpi_data_summary/detail   two endpoints, TIPS depth        │
│  3.  ofs2_estimated_ownership_…     one endpoint, "who owns debt"    │
│  4.  TIC scraper                    foreign holdings (own skill)     │
│  5.  pdo1 / pdo2 + ofs1             auction history depth            │
│  6.  Quarterly refunding XMLs       forward-looking issuance pipe    │
│  7.  Remaining T2 endpoints         batch add to registry            │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 2. Fiscal Data API Additions → `treasury_client.py`

### Pattern reminder (so you can adapt to PRISM's wrapper)

```
Base URL  : https://api.fiscaldata.treasury.gov/services/api/fiscal_service
Auth      : none
Pagination: page[number]=N, page[size]=M  (default 100, max 10000 per page)
Filtering : filter=field:op:value[,field:op:value…]
            ops: eq, in, gte, gt, lte, lt
            in-set: field:in:(v1,v2,v3)
Sorting   : sort=field   (prefix - for desc)
Fields    : fields=f1,f2,f3   (column projection)
Format    : format=json | csv | xml
```

If your `treasury_client.py` mirrors the staging design, each new endpoint
needs exactly:

1. One entry in the endpoint registry (key, path, table_name, category, date_field).
2. Optional domain helper (`get_buybacks_cusips()`, `get_tips_index_ratios()`, …) that wraps the generic `get_endpoint(key, …)`.
3. Optional CLI subcommand if the endpoint deserves first-class CLI access.

For each endpoint below, I give you:
- **Path**, **Description**, **Total rows**, **Date field**
- **Schema** (field, type, description)
- **Sample row** (live as of 2026-04-30)
- **CLI signatures** to add (PRISM-side, adapt naming)
- **Python helper signatures** to add
- **Skill file blurb** (paste-ready)
- **PRISM use cases**

---

### 2.1  `buybacks_security_details` — CUSIP-level buyback fills

```
Path        : v1/accounting/od/buybacks_security_details
Table name  : Treasury Securities Buybacks Security Details
Category    : auctions  (or new sub-cat: buybacks)
Date field  : operation_date
Total rows  : 4,960 (2000-2001 + 2024-present)
Granularity : one row per CUSIP per buyback operation
Companion   : buybacks_operations  (already wired)  — joins on operation_date + operation_start_time_est
```

Schema:

```
┌──────────────────────────────┬─────────────┬──────────────────────────────────────┐
│ Field                        │ Type        │ Description                          │
├──────────────────────────────┼─────────────┼──────────────────────────────────────┤
│ operation_date               │ DATE        │ Operation date  (join key 1)         │
│ operation_start_time_est     │ STRING      │ "10:30 AM"     (join key 2)          │
│ cusip_nbr                    │ STRING      │ 9-char CUSIP                         │
│ coupon_rate_pct              │ PERCENTAGE  │ Coupon rate of the bought-back issue │
│ maturity_date                │ DATE        │ Issue's stated maturity              │
│ par_amt_accepted             │ CURRENCY    │ Par amount Treasury repurchased      │
│ weighted_avg_accepted_price  │ CURRENCY3   │ Weighted-avg price across accepted   │
└──────────────────────────────┴─────────────┴──────────────────────────────────────┘
```

Sample row (raw API response):

```json
{
  "operation_date": "2000-03-09",
  "operation_start_time_est": "10:30 AM",
  "cusip_nbr": "912810DP0",
  "coupon_rate_pct": "11.250",
  "maturity_date": "2015-02-15",
  "par_amt_accepted": "160000000.00",
  "weighted_avg_accepted_price": "144.779"
}
```

Joining to `buybacks_operations`: each row in the operations table can be matched to its CUSIPs via `(operation_date, operation_start_time_est)`.

Live verify URL:

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/buybacks_security_details?page[size]=5&sort=-operation_date&format=json
```

CLI to add:

```bash
# In PRISM CLI, mirror your existing buybacks command shape
treasury_client.py buybacks-cusips
treasury_client.py buybacks-cusips --from-date 2024-01-01
treasury_client.py buybacks-cusips --cusip 912810DP0
treasury_client.py buybacks-cusips --operation-date 2026-04-15
```

Python helper signature to add:

```python
def get_buyback_security_details(
    from_date: str | None = None,
    to_date: str | None = None,
    cusip: str | None = None,
    operation_date: str | None = None,
    fields: list[str] | None = None,
    max_pages: int = 50,
) -> list[dict]:
    """
    CUSIP-level buyback fill data.
    Pairs with get_buybacks() (operations-level) on (operation_date, operation_start_time_est).
    """
```

Skill file blurb:

```markdown
| `buybacks_security_details` | `v1/accounting/od/buybacks_security_details` | Treasury Buybacks Security Details (CUSIP-level fills) |
```

PRISM use cases:
- Identify which off-the-run CUSIPs Treasury actually repurchased in each buyback (vs. just which were eligible).
- Monitor liquidity-support buyback "appetite" by tenor / coupon vintage.
- Cross-reference against SOMA holdings (NY Fed) and dealer inventory (NY Fed PD positions) to ask: did the buyback actually drain the float of that line?

---

### 2.2  `tips_cpi_data_summary` — TIPS reference CPI per CUSIP

```
Path        : v1/accounting/od/tips_cpi_data_summary
Table name  : Reference CPI Numbers and Daily Index Ratios (Summary)
Category    : interest_rates  (or new sub-cat: tips)
Date field  : original_issue_date  (NOT record_date)
Total rows  : ~53 (one row per TIPS CUSIP issued since 1997)
Granularity : one row per CUSIP, with reference CPI on dated date
```

Schema:

```
┌──────────────────────────────┬─────────────┬───────────────────────────────────────┐
│ Field                        │ Type        │ Description                           │
├──────────────────────────────┼─────────────┼───────────────────────────────────────┤
│ cusip                        │ STRING      │ TIPS CUSIP                            │
│ interest_rate                │ PERCENTAGE  │ Coupon rate                           │
│ security_term                │ STRING      │ "5-Year" / "10-Year" / "30-Year"     │
│ original_auction_date        │ DATE        │ First auction date                    │
│ maturity_date                │ DATE        │                                       │
│ series                       │ STRING      │ "TIPS of April 2028"                  │
│ original_issue_date          │ DATE        │                                       │
│ dated_date                   │ DATE        │ Coupon-accrual start                  │
│ ref_cpi_on_dated_date        │ NUMBER      │ Reference CPI baseline                │
│ additional_issue_date        │ STRING      │ For reopenings (or "null")            │
└──────────────────────────────┴─────────────┴───────────────────────────────────────┘
```

Sample row:

```json
{
  "cusip": "912810FD5",
  "interest_rate": "3.625000",
  "security_term": "30-Year",
  "original_auction_date": "1998-04-08",
  "maturity_date": "2028-04-15",
  "series": "TIPS of April 2028",
  "original_issue_date": "1998-04-15",
  "dated_date": "1998-04-15",
  "ref_cpi_on_dated_date": "161.740000",
  "additional_issue_date": "null"
}
```

Live verify URL:

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/tips_cpi_data_summary?page[size]=5&format=json
```

Python helper:

```python
def get_tips_summary(
    cusip: str | None = None,
    security_term: str | None = None,
    fields: list[str] | None = None,
) -> list[dict]:
    """All TIPS CUSIPs ever issued, with their dated-date reference CPI."""
```

Skill blurb:

```markdown
| `tips_cpi_data_summary` | `v1/accounting/od/tips_cpi_data_summary` | TIPS Reference CPI on Dated Date (per CUSIP, ~53 rows) |
```

PRISM use cases:
- Resolve a TIPS CUSIP to its baseline reference CPI (denominator for index-ratio computations).
- Build the TIPS universe list for downstream queries (reopening lookups, breakeven computation).

---

### 2.3  `tips_cpi_data_detail` — TIPS daily index ratios per CUSIP

```
Path        : v1/accounting/od/tips_cpi_data_detail
Table name  : Reference CPI Numbers and Daily Index Ratios (Details)
Category    : interest_rates
Date field  : index_date
Total rows  : 134,895 (daily × all TIPS CUSIPs since 1997)
Granularity : one row per CUSIP per calendar date
```

Schema:

```
┌──────────────────────────┬────────┬──────────────────────────────────────────────┐
│ Field                    │ Type   │ Description                                  │
├──────────────────────────┼────────┼──────────────────────────────────────────────┤
│ cusip                    │ STRING │ TIPS CUSIP                                   │
│ original_issue_date      │ DATE   │                                              │
│ index_date               │ DATE   │ Calendar date for this index ratio           │
│ ref_cpi                  │ NUMBER │ Reference CPI for index_date                 │
│ index_ratio              │ NUMBER │ ref_cpi / ref_cpi_on_dated_date              │
│ pdf_link                 │ STRING │ Treasury PDF filename                        │
│ xml_link                 │ STRING │ Treasury XML filename                        │
└──────────────────────────┴────────┴──────────────────────────────────────────────┘
```

Sample row:

```json
{
  "cusip": "912810FD5",
  "original_issue_date": "1998-04-15",
  "index_date": "2010-07-01",
  "ref_cpi": "218.00900",
  "index_ratio": "1.34790",
  "pdf_link": "CPI_20100617.pdf",
  "xml_link": "CPI_20100617.xml"
}
```

Live verify URL:

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/tips_cpi_data_detail?filter=cusip:eq:912810FD5,index_date:gte:2025-01-01&page[size]=10&format=json
```

CLI to add:

```bash
treasury_client.py tips-index-ratio --cusip 912810FD5 --from-date 2025-01-01
treasury_client.py tips-index-ratio --cusip 912810FD5 --on-date 2026-04-15
```

Python helper:

```python
def get_tips_index_ratios(
    cusip: str,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """Daily reference CPI + index ratio for a single TIPS CUSIP."""
```

Skill blurb:

```markdown
| `tips_cpi_data_detail` | `v1/accounting/od/tips_cpi_data_detail` | TIPS Daily Index Ratios per CUSIP (~135k rows) |
```

PRISM use cases:
- Compute clean inflation-accrued par for any TIPS CUSIP on any date — the unit conversion factor for moving between nominal and real par.
- Settlement calc: if a buyer purchased TIPS today, what's the inflation-adjusted amount paid? `par × index_ratio_today`.
- Real-yield analysis: combine with `auctions_query` (already wired) to compute breakeven trajectories.

---

### 2.4  `ofs2_estimated_ownership_treasury_securities` — Holdings by holder type

```
Path        : v1/accounting/tb/ofs2_estimated_ownership_treasury_securities
Table name  : Estimated Ownership of U.S. Treasury Securities (Treasury Bulletin OFS-2)
Category    : debt  (or new sub-cat: holdings)
Date field  : record_date  (quarterly publication; end_of_month is end-quarter)
Total rows  : ~768 (covers ~96 quarters × 8 holder categories)
Granularity : one row per (quarter, holder-type)
Source      : Federal Reserve Z.1 Flow of Funds, Table L.209
```

Schema:

```
┌──────────────────────────┬────────────┬─────────────────────────────────────────────┐
│ Field                    │ Type       │ Description                                 │
├──────────────────────────┼────────────┼─────────────────────────────────────────────┤
│ record_date              │ DATE       │ Publication date                            │
│ end_of_month             │ DATE       │ End-of-quarter date the holding refers to   │
│ securities_owner         │ STRING     │ "Depository Institutions",                  │
│                          │            │ "Federal Reserve And Government Accounts",  │
│                          │            │ "Foreign And International",                │
│                          │            │ "Insurance Companies", "Mutual Funds",      │
│                          │            │ "Pension Funds", "State And Local Govts",   │
│                          │            │ "Other Investors"                           │
│ securities_bil_amt       │ CURRENCY1  │ $ Billions held                             │
└──────────────────────────┴────────────┴─────────────────────────────────────────────┘
```

Sample rows:

```json
[
  {"record_date":"2021-03-31","end_of_month":"2014-12-31",
   "securities_owner":"Depository Institutions","securities_bil_amt":"516.8"},
  {"record_date":"2021-03-31","end_of_month":"2014-12-31",
   "securities_owner":"Federal Reserve And Government Accounts","securities_bil_amt":"7578.9"}
]
```

Live verify URL:

```
https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/ofs2_estimated_ownership_treasury_securities?sort=-end_of_month&page[size]=20&format=json
```

CLI to add:

```bash
treasury_client.py ownership                          # latest snapshot, all holders
treasury_client.py ownership --holder "Foreign And International" --from-date 2010-01-01
treasury_client.py ownership --as-of 2024-12-31
```

Python helper:

```python
def get_estimated_ownership(
    holder: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
) -> list[dict]:
    """Quarterly estimated ownership of US Treasuries by holder category."""
```

Skill blurb:

```markdown
| `ofs2_estimated_ownership_treasury_securities` | `v1/accounting/tb/ofs2_estimated_ownership_treasury_securities` | Estimated Ownership of UST by Holder Type (Z.1 Table L.209) |
```

PRISM use cases:
- The single most important "who owns the debt" snapshot. Anchors any narrative about marginal Treasury buyer.
- Pair with TIC for foreign breakdown by country.
- Pair with NY Fed SOMA for Fed share.
- Pair with Z.1 (FRED) for non-Treasury holders detail.

---

### 2.5  `ofs1_distribution_federal_securities_class_investors_type_issues`

```
Path        : v1/accounting/tb/ofs1_distribution_federal_securities_class_investors_type_issues
Table name  : Distribution of Federal Securities by Class of Investors and Type of Issues (OFS-1)
Category    : debt
Date field  : record_date
Total rows  : ~4,641
Granularity : (record_date, securities_classification, investors_classification, issues_type)
```

Schema:

```
┌────────────────────────────┬────────────┬────────────────────────────────────────────┐
│ Field                      │ Type       │ Description                                │
├────────────────────────────┼────────────┼────────────────────────────────────────────┤
│ record_date                │ DATE       │ Publication date                           │
│ end_fiscal_year_or_month   │ DATE       │ End of FY or month the data refers to      │
│ securities_classification  │ STRING     │ Treasury marketable / nonmarketable /      │
│                            │            │   agency / etc.                            │
│ investors_classification   │ STRING     │ Held by govt accounts / FRBs / private     │
│ issues_type                │ STRING     │ Sub-category (often duplicates investors)  │
│ securities_mil_amt         │ CURRENCY0  │ $ Millions                                 │
│ src_line_nbr               │ INTEGER    │ Source-line number                         │
└────────────────────────────┴────────────┴────────────────────────────────────────────┘
```

Sample rows:

```json
[
  {"record_date":"2021-03-31","end_fiscal_year_or_month":"2016-09-30",
   "securities_classification":"Agencies securities",
   "investors_classification":"Held by government accounts",
   "issues_type":"Held by government accounts",
   "securities_mil_amt":"4","src_line_nbr":"1"},
  {"record_date":"2021-03-31","end_fiscal_year_or_month":"2016-09-30",
   "securities_classification":"Agencies securities",
   "investors_classification":"Held by private investors",
   "issues_type":"Held by private investors",
   "securities_mil_amt":"24363","src_line_nbr":"1"}
]
```

CLI to add:

```bash
treasury_client.py federal-distribution
treasury_client.py federal-distribution --as-of 2024-09-30
treasury_client.py federal-distribution --filter "investors_classification:eq:Held by private investors"
```

Skill blurb:

```markdown
| `ofs1_distribution_federal_securities_class_investors_type_issues` | `v1/accounting/tb/ofs1_distribution_federal_securities_class_investors_type_issues` | Distribution of Federal Securities by Investor Class & Issue Type (OFS-1) |
```

PRISM use cases:
- Companion to OFS-2 (estimated ownership) — gives the issuer-side view.
- Cross-tabulation: see how much of agency vs Treasury debt is held inside government accounts (intragov) vs by the public.

---

### 2.6  `pdo1_offerings_regular_weekly_treasury_bills`

```
Path        : v1/accounting/tb/pdo1_offerings_regular_weekly_treasury_bills
Table name  : Treasury Bulletin PDO-1 — Offerings of Regular Weekly Treasury Bills
Category    : auctions
Date field  : record_date  (typically auction_date)
Granularity : one row per bill auction (4w, 8w, 13w, 17w, 26w)
```

Expected fields (based on Treasury Bulletin published structure):

```
auction_date, security_term, issue_date, maturity_date,
high_rate_pct, total_competitive_bids_amt, total_competitive_awards_amt,
total_noncompetitive_awards_amt, total_awards_amt
```

Quick verify (run from your PRISM env):

```bash
curl 'https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/pdo1_offerings_regular_weekly_treasury_bills?page[size]=2&format=json'
```

Note: this duplicates much of `auctions_query` (already wired) but is the official Treasury Bulletin presentation, easier to chart for "weekly bill calendar" displays.

Skill blurb:

```markdown
| `pdo1_offerings_regular_weekly_treasury_bills` | `v1/accounting/tb/pdo1_offerings_regular_weekly_treasury_bills` | Treasury Bulletin PDO-1 — Bills auction history |
```

---

### 2.7  `pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills`

```
Path        : v1/accounting/tb/pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills
Table name  : Treasury Bulletin PDO-2 — Offerings of Marketable Securities Other than Bills
Category    : auctions
Date field  : record_date
Granularity : per non-bill auction (notes, bonds, TIPS, FRN, CMB)
```

Expected fields (subset, mirrors PDO-2 published columns):

```
auction_date, security_term, issue_date, maturity_date, coupon_rate_pct,
high_yield, bid_to_cover_ratio, offering_amt, total_competitive_awards_amt,
total_noncompetitive_awards_amt, total_awards_amt
```

Skill blurb:

```markdown
| `pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills` | `v1/accounting/tb/pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills` | Treasury Bulletin PDO-2 — Notes/Bonds/TIPS/FRN/CMB auction history |
```

---

### 2.8  `federal_maturity_rates`

```
Path        : v1/accounting/od/federal_maturity_rates
Table name  : Federal Credit Similar Maturity Rates
Category    : interest_rates
Date field  : record_date
Granularity : monthly per maturity bucket
```

Use case: published monthly rates on outstanding fixed-rate UST bucketed by remaining maturity (1m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y). Often used by the Federal Credit Reform Act for subsidy estimation.

Skill blurb:

```markdown
| `federal_maturity_rates` | `v1/accounting/od/federal_maturity_rates` | Federal Credit Similar Maturity Rates (monthly avg by remaining-maturity bucket) |
```

---

### 2.9  `receipts_by_department`

```
Path        : v1/accounting/od/receipts_by_department
Table name  : Receipts by Department
Category    : revenue
Date field  : record_date
```

Use case: receipts attributed to specific federal agencies / MAIN-SUB codes. Granular complement to `mts_table_4` (Receipts of the U.S. Government) and `revenue_collections`.

Skill blurb:

```markdown
| `receipts_by_department` | `v1/accounting/od/receipts_by_department` | Receipts by Department (line-item with MAIN/SUB codes) |
```

---

### 2.10  `slgs_demand_deposit_rates` and 2.11 `slgs_time_deposit_rates`

```
Path A      : v1/accounting/od/slgs_demand_deposit_rates
Path B      : v1/accounting/od/slgs_time_deposit_rates
Category    : interest_rates
Date field  : record_date
Granularity : daily
```

Use case: Daily SLGS (State and Local Government Series) demand and time-deposit rates. Used by states/munis to invest tax-exempt-bond proceeds at IRS-permitted yields. SLGS rate floor is a less-watched but real reference for short-end funding.

Skill blurbs:

```markdown
| `slgs_demand_deposit_rates` | `v1/accounting/od/slgs_demand_deposit_rates` | Daily SLGS Demand Deposit Rate |
| `slgs_time_deposit_rates`   | `v1/accounting/od/slgs_time_deposit_rates`   | Daily SLGS Time Deposit Rate by Tenor |
```

---

### 2.12  `fcp1_weekly_…`, `fcp2_monthly_…`, `fcp3_quarterly_…`

Foreign Currency Positions of major US market participants (FX exposure of large banks / non-banks).

```
fcp1_weekly_report_major_market_participants     v1/accounting/tb/fcp1_…   weekly
fcp2_monthly_report_major_market_participants    v1/accounting/tb/fcp2_…   monthly
fcp3_quarterly_report_large_market_participants  v1/accounting/tb/fcp3_…   quarterly
```

Use case: derivative & FX positions disclosed by US banks/dealers above $50bn / $5bn thresholds. Less granular than CFTC TFF but covers OTC FX too.

Skill blurbs:

```markdown
| `fcp1_weekly_report_major_market_participants`    | `v1/accounting/tb/fcp1_weekly_report_major_market_participants`    | FX Positions Weekly (large dealers) |
| `fcp2_monthly_report_major_market_participants`   | `v1/accounting/tb/fcp2_monthly_report_major_market_participants`   | FX Positions Monthly (large dealers) |
| `fcp3_quarterly_report_large_market_participants` | `v1/accounting/tb/fcp3_quarterly_report_large_market_participants` | FX Positions Quarterly (mid-size participants) |
```

---

### 2.13  `esf1_balances` and `esf2_statement_net_cost`

```
esf1_balances              v1/accounting/tb/esf1_balances              quarterly
esf2_statement_net_cost    v1/accounting/tb/esf2_statement_net_cost    quarterly
```

Use case: Exchange Stabilization Fund — balance sheet (ESF-1) and net cost (ESF-2). The fund Treasury uses for FX intervention, IMF subscription, occasional emergency lending facilities (CARES Act). Periodically interesting for dollar-policy narratives.

Skill blurbs:

```markdown
| `esf1_balances`            | `v1/accounting/tb/esf1_balances`            | Exchange Stabilization Fund — Balances |
| `esf2_statement_net_cost`  | `v1/accounting/tb/esf2_statement_net_cost`  | Exchange Stabilization Fund — Net Cost |
```

---

## 3. TIC (Treasury International Capital) → fold into `treasury_client.py`

Foreign holdings and cross-border flows of US securities. **Most macro-relevant
gap.** China/Japan UST holdings are not currently collectible via either
staging scraper. TIC code lives inside `treasury_client.py` (alongside the
Fiscal Data wrappers) so PRISM only loads one client; documentation lives in a
separate TIC skill file.

### 3.1  Where the data lives

```
Landing page : https://ticdata.treasury.gov/
              https://home.treasury.gov/data/treasury-international-capital-tic-system-home-page

Major Foreign Holders of Treasuries (THE table everyone watches):
  https://ticdata.treasury.gov/Publish/mfh.txt              (current month, plain text)
  https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfh.txt   (mirror)

Net Foreign Purchases of Long-Term US Securities by Country:
  https://www.treasury.gov/resource-center/data-chart-center/tic/Documents/snetus.csv   (CSV)
  https://www.treasury.gov/ticdata/Publish/snetus.txt                                    (text)

Monthly archive (ZIP files of all monthly tables, by release date):
  https://www.treasury.gov/resource-center/data-chart-center/tic/Pages/ticarchives.aspx

Each monthly archive ZIP (since 2010-ish) contains:
  • mfh.txt / mfh.html      Major Foreign Holders of UST (by country)
  • snetus.csv / snetus.txt Net Foreign Purchases LT, by country
  • slt-section1*.csv       Aggregate Holdings of LT Securities (TIC Form SLT)
  • slt-section2*.csv       Cross-border transactions in LT Securities
  • B-tables (banking)      TIC Form B claims/liabilities
  • C-tables (nonbank)      TIC Form C claims/liabilities
  • D-tables (derivatives)  TIC Form D
  • country-codes.txt       Country code → name mapping
```

### 3.2  Sample of `mfh.txt` (live data)

```
 MAJOR FOREIGN HOLDERS OF TREASURY SECURITIES
 (in billions of dollars)
 HOLDINGS 1/ AT END OF PERIOD

                       Jan    Dec    Nov    Oct    Sep    Aug    Jul    Jun  ...
 Country               2023   2022   2022   2022   2022   2022   2022   2022 ...
                       ----   ----   ----   ----   ----   ----   ----   ---- ...

Japan                  1104.4 1076.3 1082.3 1064.4 1116.4 1196.0 1230.7 1232.7 ...
China, Mainland         859.4  867.1  870.2  877.9  901.7  938.6  939.2  938.8 ...
United Kingdom          668.3  654.5  645.8  641.3  664.8  646.5  636.6  617.3 ...
…
All Other               437.2  439.2  424.9  408.3  414.1  408.5  407.7  407.2 ...
Grand Total            7402.5 7318.7 7268.6 7133.1 7251.5 7492.7 7485.5 7417.0 ...

Of which:
 For. Official         3713.9 3678.1 3670.8 3614.0 3713.7 3876.9 3895.0 3855.3 ...
 Treasury Bills         249.6  238.7  217.2  203.8  220.0  230.5  234.0  238.3 ...
 T-Bonds & Notes       3464.3 3439.3 3453.6 3410.2 3493.7 3646.4 3661.0 3616.9 ...
```

Format: fixed-width text, 13 monthly columns rolling, `Country` left-aligned, amounts right-aligned. Bottom block has aggregate splits (foreign-official, bills, bonds-notes).

### 3.3  Add to `treasury_client.py`

These functions live alongside the Fiscal Data wrappers in the same module —
PRISM only loads one client. Prefix with `tic_` to keep namespacing clean from
the Fiscal Data helpers.

```python
# In treasury_client.py — TIC sub-section

TIC_BASE         = "https://ticdata.treasury.gov"
TIC_ARCHIVE_BASE = "https://www.treasury.gov/resource-center/data-chart-center/tic"
TIC_PUBLISH_BASE = "https://ticdata.treasury.gov/Publish"

TIC_CURRENT_FILES = {
    "mfh":      f"{TIC_PUBLISH_BASE}/mfh.txt",
    "snetus":   f"{TIC_ARCHIVE_BASE}/Documents/snetus.csv",
    "slt_s1":   f"{TIC_ARCHIVE_BASE}/Documents/slt-table1.csv",
    "slt_s2":   f"{TIC_ARCHIVE_BASE}/Documents/slt-table2.csv",
    # … etc
}

def get_tic_mfh() -> list[dict]:
    """Parse fixed-width mfh.txt → [{country, asof, amount_bn}, …]
    Plus aggregate rows: 'Foreign Official', 'Treasury Bills', 'T-Bonds & Notes', 'Grand Total'."""

def get_tic_snetus() -> list[dict]:
    """CSV → [{country, period, net_purchases_mn}, …]"""

def list_tic_archives() -> list[dict]:
    """Scrape the archives page → [{release_date, label, zip_url}, …]"""

def fetch_tic_archive(release_date: str, dest_dir: Path) -> Path:
    """Download a monthly TIC archive ZIP and unpack to dest_dir."""

def get_tic_country_holdings(country: str, months: int = 12) -> list[dict]:
    """Convenience: country's UST holdings over the last N months."""

def get_tic_top_holders(top_n: int = 20, asof: str | None = None) -> list[dict]:
    """Convenience: top N foreign holders at the most recent (or specified) date."""
```

CLI to add (under a `tic-*` subcommand prefix to keep them grouped in the
interactive menu):

```bash
treasury_client.py tic-mfh                                   # latest snapshot, all countries
treasury_client.py tic-mfh --country "Japan" --months 24
treasury_client.py tic-mfh --country "China, Mainland" --months 24
treasury_client.py tic-snetus
treasury_client.py tic-snetus --country "Euro Area"
treasury_client.py tic-top --n 20                            # top 20 holders, current
treasury_client.py tic-archives                              # list available archive ZIPs
treasury_client.py tic-archive --release 2025-12-19          # download + unpack one archive
```

PRISM use cases (for the separate TIC skill file, not the consolidated Treasury skill):
- Foreign demand for Treasuries by country / region. Pairs with auction indirect bidder allocation (`auctions_query`) and Fed FIMA noncompetitive (also in `auctions_query`).
- Reserve-manager flow analysis: China + Japan + UK + Belgium (Euroclear hub) as joint signal.
- Cross-border banking flows for dollar-funding stress narratives (B-tables).
- Pair with NY Fed FIMA repo data for foreign-official cash-management view.

Notes worth carrying into the TIC skill file:
- MFH is the canonical "China dumping Treasuries?" data source.
- Numbers are billion USD.
- Custodial reporting; TIC does NOT capture beneficial-owner attribution accurately
  when securities are held in third-country custody (see TIC FAQ #7).
- Release calendar: monthly on the 15th business day of the following-following month
  (e.g. Mar 2025 data released mid-May 2025).

---

## 4. Quarterly Refunding XML Schedules → `treasury_direct_client.py`

The forward-looking complement to historical `auctions_query`. Treasury publishes its **next-quarter auction schedule and buyback schedule** as XML files alongside each Quarterly Refunding announcement (early Feb / May / Aug / Nov).

### 4.1  Where they live

```
Landing page (latest):
  https://www.treasury.gov/resource-center/data-chart-center/quarterly-refunding/Pages/Latest.aspx

Archive page:
  https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives

Per-quarter outputs released at the refunding (typical filenames):
  • auction-schedule.xml            (auction calendar: dates, sizes, types)
  • buyback-schedule.xml            (buyback calendar)
  • TreasuryPresentationToTBAC.pdf  (already crawled by treasurydirect.py)
  • TBAC_Charge_*.pdf               (TBAC discussion charts)
  • TBAC_Report_to_Secretary.pdf
  • TBAC_Recommended_Financing_Table.pdf
  • Primary_Dealer_Survey_Q*.pdf    (dealer survey results)
  • Quarterly_Release_Data.xlsx     (Excel data tables)
  • QuarterlyRefundingStatement.txt (financing estimate)
```

The XML schedules are stable across quarters but file names embed the year/quarter.

### 4.2  Quarterly Refunding event schedule (calendar)

```
Q1 refunding:   first Mon-Wed of Feb       covers Feb-Apr
Q2 refunding:   first Mon-Wed of May       covers May-Jul
Q3 refunding:   first Mon-Wed of Aug       covers Aug-Oct
Q4 refunding:   first Mon-Wed of Nov       covers Nov-Jan
```

Mid-quarter primary-dealer-survey release: Friday before the next refunding (typically ~10-12 weeks after the prior refunding).

### 4.3  What to add to `treasury_direct_client.py`

Three new scraping passes, one per artifact class:

```python
# Add to treasury_direct_client.py

REFUNDING_LATEST_URL  = "https://www.treasury.gov/resource-center/data-chart-center/quarterly-refunding/Pages/Latest.aspx"
REFUNDING_ARCHIVE_URL = "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/quarterly-refunding-archives"

def scrape_refunding_latest(self) -> dict:
    """Scrape the 'most recent quarterly refunding documents' page.
    Returns a dict with categorized URLs and metadata for the latest event:
      {
        "release_date_estimates": "2026-02-02",
        "release_date_documents": "2026-02-04",
        "release_date_pd_survey": "2026-04-17",
        "auction_schedule_xml":   "https://…/auction-schedule.xml",
        "buyback_schedule_xml":   "https://…/buyback-schedule.xml",
        "tbac_presentation_pdf":  "…",
        "tbac_charge_pdfs":       ["…", "…"],
        "tbac_report_pdf":        "…",
        "tbac_minutes_pdf":       "…",
        "primary_dealer_survey_pdf": "…",
        "quarterly_release_xlsx": "…",
        "policy_statement_pdf":   "…",
        "financing_estimates_pdf":"…",
      }
    Saves all artifacts to <output_dir>/refunding/<release_date>/."""

def scrape_refunding_archive(self, last_n_quarters: int = 4) -> list[dict]:
    """Walk the archive page, return a list like scrape_refunding_latest()
    for each historical refunding event, going back `last_n_quarters`.
    Saves artifacts to <output_dir>/refunding/<release_date>/."""

def fetch_auction_schedule_xml(self, url: str) -> list[dict]:
    """Parse auction-schedule.xml → projected auctions
    Each entry: {announcement_date, auction_date, settlement_date,
                 security_type, security_term, offering_amt, reopening}"""

def fetch_buyback_schedule_xml(self, url: str) -> list[dict]:
    """Parse buyback-schedule.xml → planned buyback windows
    Each entry: {operation_date, settlement_date, operation_type,
                 security_type, maturity_bucket, max_par_amt}"""
```

CLI to add:

```bash
treasury_direct_client.py refunding-latest                 # scrape latest event
treasury_direct_client.py refunding-archive --quarters 8   # scrape last 2y
treasury_direct_client.py refunding-schedule               # parse auction XML only
treasury_direct_client.py refunding-buyback-schedule       # parse buyback XML only
```

Skill file blurb:

```markdown
### Quarterly Refunding (treasury_direct_client.py refunding-*)

Each quarter (Feb / May / Aug / Nov), Treasury releases:
- Forward-looking auction schedule (XML) — projected auction dates, sizes, types
- Forward-looking buyback schedule (XML) — planned buyback windows by maturity bucket
- TBAC discussion charts (PDF)
- TBAC report to Secretary, minutes, recommended financing table (PDF)
- Primary Dealer Survey results (PDF, mid-quarter release)

The auction-schedule.xml is the canonical "what auctions are coming next quarter"
data source. Pairs with Fiscal Data `upcoming_auctions` (~88 rows, near-term only).
```

PRISM use cases:
- Forward issuance pipeline. `upcoming_auctions` is short (~88 rows). The refunding XML covers the full next quarter.
- TBAC borrowing recommendations vs actual issuance. Watch dealer survey median deficit assumptions vs OMB/CBO.
- Buyback pipeline. Operations-level `buybacks_operations` is historical; the buyback XML schedule shows what's *planned*.

---

## 5. Consolidated Skill File Updates (paste-ready)

Below are markdown chunks ready to paste into your consolidated PRISM skill file. Section names assume the existing structure mirrors what's in staging (`Triggers`, `Data Catalog`, `Endpoint Registry`, `CLI Recipes`, `Python Recipes`, `Composite Recipes`, `Cross-Source Recipes`, `Setup`, `Architecture`).

TIC is intentionally excluded from these updates — it has its own dedicated skill file.

### 5.1  Update the `Triggers` section

Add the bolded items below to the existing "Use for:" line in the Triggers block:

```markdown
Use for: Treasury auction results, CUSIP-level auction lookup, bid-to-cover
ratios, **CUSIP-level buyback fills (par accepted, weighted-avg price)**, debt
to the penny, MSPD reports, **TIPS reference CPI and daily index ratios per
CUSIP**, **estimated ownership of US Treasuries by holder type (Fed, foreign,
depository, etc.)**, **distribution of federal securities by investor class
(Treasury Bulletin OFS-1)**, **quarterly refunding documents including forward
auction-schedule XML, buyback-schedule XML, TBAC presentations, primary dealer
surveys**, savings bond rate tables, RSS feed monitoring.
```

### 5.2  Add to the Endpoint Registry table — Auctions / Buybacks

```markdown
| `buybacks_security_details` | `v1/accounting/od/buybacks_security_details` | Treasury Securities Buybacks Security Details (CUSIP-level fills) |
```

### 5.3  Add to the Endpoint Registry table — Debt / Holdings

```markdown
| `ofs1_distribution_federal_securities_class_investors_type_issues` | `v1/accounting/tb/ofs1_distribution_federal_securities_class_investors_type_issues` | Distribution of Federal Securities by Investor Class & Type of Issues (OFS-1) |
| `ofs2_estimated_ownership_treasury_securities` | `v1/accounting/tb/ofs2_estimated_ownership_treasury_securities` | Estimated Ownership of US Treasury Securities by Holder Type (OFS-2 / Z.1 L.209) |
```

### 5.4  Add to the Endpoint Registry table — Interest Rates

```markdown
| `tips_cpi_data_summary`        | `v1/accounting/od/tips_cpi_data_summary`        | TIPS Reference CPI on Dated Date (per CUSIP) |
| `tips_cpi_data_detail`         | `v1/accounting/od/tips_cpi_data_detail`         | TIPS Daily Reference CPI + Index Ratios (per CUSIP) |
| `federal_maturity_rates`       | `v1/accounting/od/federal_maturity_rates`       | Federal Credit Similar Maturity Rates (monthly avg by remaining-maturity bucket) |
| `slgs_demand_deposit_rates`    | `v1/accounting/od/slgs_demand_deposit_rates`    | Daily SLGS Demand Deposit Rate |
| `slgs_time_deposit_rates`      | `v1/accounting/od/slgs_time_deposit_rates`      | Daily SLGS Time Deposit Rate by Tenor |
```

### 5.5  Add to the Endpoint Registry table — Treasury Bulletin auction history

```markdown
| `pdo1_offerings_regular_weekly_treasury_bills` | `v1/accounting/tb/pdo1_offerings_regular_weekly_treasury_bills` | Treasury Bulletin PDO-1 — Regular Weekly Bills auction history |
| `pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills` | `v1/accounting/tb/pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills` | Treasury Bulletin PDO-2 — Notes/Bonds/TIPS/FRN/CMB auction history |
```

### 5.6  Add to the Endpoint Registry table — Revenue / FX / ESF

```markdown
| `receipts_by_department`                          | `v1/accounting/od/receipts_by_department` | Receipts by Department (line-item, MAIN/SUB codes) |
| `fcp1_weekly_report_major_market_participants`    | `v1/accounting/tb/fcp1_weekly_report_major_market_participants`    | Foreign Currency Positions Weekly (large dealers) |
| `fcp2_monthly_report_major_market_participants`   | `v1/accounting/tb/fcp2_monthly_report_major_market_participants`   | Foreign Currency Positions Monthly (large dealers) |
| `fcp3_quarterly_report_large_market_participants` | `v1/accounting/tb/fcp3_quarterly_report_large_market_participants` | Foreign Currency Positions Quarterly (mid-size participants) |
| `esf1_balances`                                    | `v1/accounting/tb/esf1_balances`                                   | Exchange Stabilization Fund — Balances |
| `esf2_statement_net_cost`                          | `v1/accounting/tb/esf2_statement_net_cost`                         | Exchange Stabilization Fund — Net Cost |
```

### 5.7  Add to CLI Recipes

(Paste the four sub-sections below verbatim into your skill file's CLI Recipes section.)

#### CUSIP-level Buyback Fills

```bash
treasury_client.py buybacks-cusips                              # all, default sort
treasury_client.py buybacks-cusips --json
treasury_client.py buybacks-cusips --from-date 2024-01-01
treasury_client.py buybacks-cusips --cusip 912810DP0
treasury_client.py buybacks-cusips --operation-date 2026-04-15
```

#### TIPS Reference CPI / Index Ratios

```bash
treasury_client.py tips-summary                                  # all TIPS CUSIPs
treasury_client.py tips-summary --cusip 912810FD5
treasury_client.py tips-index-ratio --cusip 912810FD5 --on-date 2026-04-15
treasury_client.py tips-index-ratio --cusip 912810FD5 --from-date 2025-01-01
```

#### Estimated Ownership / Distribution

```bash
treasury_client.py ownership                                    # latest, all holders
treasury_client.py ownership --holder "Foreign And International" --from-date 2010-01-01
treasury_client.py ownership --as-of 2024-12-31
treasury_client.py federal-distribution
treasury_client.py federal-distribution --as-of 2024-09-30
```

#### Quarterly Refunding

```bash
treasury_direct_client.py refunding-latest                       # most recent event
treasury_direct_client.py refunding-archive --quarters 8         # last 2 years
treasury_direct_client.py refunding-schedule                     # parse auction-schedule.xml
treasury_direct_client.py refunding-buyback-schedule             # parse buyback-schedule.xml
```

### 5.8  Add to Python Recipes

(Paste the four sub-sections below verbatim into your skill file's Python Recipes section.)

#### CUSIP-level Buybacks (joining operations and security details)

```python
from treasury_client import get_buybacks, get_buyback_security_details

operations = get_buybacks(from_date="2024-01-01")          # already wired
details    = get_buyback_security_details(from_date="2024-01-01")  # NEW

# Join key: (operation_date, operation_start_time_est)
by_op = {(o["operation_date"], o["operation_start_time_est"]): o for o in operations}
for d in details:
    op = by_op.get((d["operation_date"], d["operation_start_time_est"]))
    if op:
        d["operation_type"] = op.get("operation_type")
        d["maturity_bucket"] = op.get("maturity_bucket")
```

#### TIPS Index Ratio Lookup

```python
from treasury_client import get_tips_summary, get_tips_index_ratios

tips_universe = get_tips_summary()
ratios = get_tips_index_ratios(cusip="912810FD5", from_date="2025-01-01")
# ratios is a list of {cusip, original_issue_date, index_date, ref_cpi, index_ratio, ...}
```

#### Estimated Ownership Snapshot

```python
from treasury_client import get_estimated_ownership

latest = get_estimated_ownership(from_date="2024-01-01", to_date="2024-12-31")
foreign = get_estimated_ownership(holder="Foreign And International", from_date="2010-01-01")
```

#### Quarterly Refunding

```python
from treasury_direct_client import scrape_refunding_latest, fetch_auction_schedule_xml

latest = scrape_refunding_latest()
# Returns dict with all artifact URLs and metadata

projected = fetch_auction_schedule_xml(latest["auction_schedule_xml"])
# Each entry: {announcement_date, auction_date, security_type, security_term,
#             offering_amt, reopening, settlement_date, ...}
```

### 5.9  Add to Composite Recipes

(Paste the four sub-sections below verbatim into your skill file's Composite Recipes section.)

#### CUSIP-level Buyback Forensics

```bash
treasury_client.py get buybacks_operations --from-date 2024-01-01 --json
treasury_client.py buybacks-cusips --from-date 2024-01-01 --json
treasury_client.py auctions-data --from-date 2024-01-01 --json
```

PRISM receives: every liquidity-support and cash-management buyback since the program restarted (Jan 2024) at operation-level + per-CUSIP fill detail + the full auction-history record for those CUSIPs (to compare buyback-execution price vs original auction price).

#### TIPS Inflation-Accrual Universe

```bash
treasury_client.py tips-summary --json
treasury_client.py get tips_cpi_data_detail --filter "index_date:gte:2025-01-01" --json
treasury_client.py auctions-data --filter "security_type:eq:TIPS" --from-date 2020-01-01 --json
```

PRISM receives: the full TIPS CUSIP universe with reference-CPI baselines + daily index ratios for 2025+ + auction history for breakeven analysis.

#### Holdings Composition Snapshot

```bash
treasury_client.py ownership --as-of 2024-12-31
treasury_client.py federal-distribution --as-of 2024-12-31
```

PRISM receives: the "who owns the debt" mosaic from the issuer-side — Z.1 holder breakdown + investor-class issue-type breakdown. (Combine with TIC for foreign-by-country detail; that recipe lives in the TIC skill file.)

#### Forward Issuance Pipeline

```bash
treasury_direct_client.py refunding-latest
treasury_client.py auctions --json                         # upcoming_auctions (Fiscal Data)
treasury_client.py get debt_to_penny --from-date $(date -v-30d +%Y-%m-%d) --json
```

PRISM receives: the latest quarterly refunding forward auction schedule + Fiscal Data near-term auctions + recent debt-to-the-penny trajectory. Forward issuance vs current debt level for funding-cliff analysis.

### 5.10  Add to Cross-Source Recipes

(Paste the two sub-sections below verbatim into your skill file's Cross-Source Recipes section. Adjust the `GS/data/apis/.../*.py` invocations to match PRISM's path conventions.)

#### Buyback CUSIP Forensics + SOMA Holdings

```bash
treasury_client.py buybacks-cusips --from-date 2024-01-01
GS/data/apis/nyfed/nyfed.py soma-holdings --json
GS/data/apis/nyfed/nyfed.py pd-positions --count 12 --json
```

PRISM receives: which off-the-runs Treasury bought back + Fed's SOMA portfolio composition + dealer Treasury inventory. Tests whether buybacks actually drained the float of those CUSIPs (or were Fed-held, or are dealer-warehoused).

#### Forward Refunding + Dealer Survey + Fed Path

```bash
treasury_direct_client.py refunding-latest
GS/data/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
GS/data/apis/cftc/cftc.py rates --json
```

PRISM receives: TBAC presentation + dealer auction-size survey medians + market-implied Fed path + speculative SOFR/UST positioning. The full "what's coming + what does the market expect" picture for the next quarter.

---

## 6. Integration Checklist

```
┌────────────────────────────────────────────────────────────────────────────┐
│  treasury_client.py                                                         │
└────────────────────────────────────────────────────────────────────────────┘
  Fiscal Data API additions
  [ ] Add registry entries (Section 5.2 - 5.6) for all T1 + T2 endpoints
  [ ] Add domain helpers:
        get_buyback_security_details()
        get_tips_summary()
        get_tips_index_ratios()
        get_estimated_ownership()
        get_federal_distribution()
        (optional) get_pdo1_offerings(), get_pdo2_offerings(),
                   get_federal_maturity_rates(), get_receipts_by_department(),
                   get_slgs_*, get_fcp_*, get_esf_*
  [ ] Add CLI subcommands (Section 5.7) for the helpers above
  [ ] Update interactive menu to expose new categories (buybacks-cusips,
      tips, ownership, distribution, …)
  [ ] (Optional) Add new CATEGORIES entries:
        - "buybacks"    (move buybacks_operations + security_details here)
        - "holdings"    (ownership / distribution)
        - "tips"        (CPI summary / detail)

  TIC scraper (Section 3) — folded into the same module
  [ ] Add module-level constants TIC_BASE / TIC_ARCHIVE_BASE / TIC_PUBLISH_BASE
      and TIC_CURRENT_FILES dict
  [ ] Implement get_tic_mfh() — fixed-width text parser
  [ ] Implement get_tic_snetus() — CSV parser
  [ ] Implement list_tic_archives() / fetch_tic_archive() — ZIP downloader
  [ ] Implement get_tic_country_holdings() / get_tic_top_holders() conveniences
  [ ] Add CLI subcommands: tic-mfh / tic-snetus / tic-top / tic-archives / tic-archive
  [ ] Add a TIC group to the interactive menu

┌────────────────────────────────────────────────────────────────────────────┐
│  treasury_direct_client.py                                                  │
└────────────────────────────────────────────────────────────────────────────┘
  [ ] Add scrape_refunding_latest() method
  [ ] Add scrape_refunding_archive(last_n_quarters=N) method
  [ ] Add fetch_auction_schedule_xml() and fetch_buyback_schedule_xml() parsers
  [ ] Add CLI: refunding-latest / refunding-archive /
              refunding-schedule / refunding-buyback-schedule
  [ ] Add to interactive menu

┌────────────────────────────────────────────────────────────────────────────┐
│  Consolidated Treasury skill file                                           │
└────────────────────────────────────────────────────────────────────────────┘
  [ ] Update Triggers section (Section 5.1)
  [ ] Append to Endpoint Registry tables (Sections 5.2 – 5.6)
  [ ] Append CLI Recipes (Section 5.7)
  [ ] Append Python Recipes (Section 5.8)
  [ ] Append Composite Recipes (Section 5.9)
  [ ] Append Cross-Source Recipes (Section 5.10)
  [ ] Update Architecture / Setup blocks if they list module count

┌────────────────────────────────────────────────────────────────────────────┐
│  TIC skill file (separate, written by Ritik)                                │
└────────────────────────────────────────────────────────────────────────────┘
  [ ] Out of scope for this doc — TIC documentation lives separately

┌────────────────────────────────────────────────────────────────────────────┐
│  Smoke tests                                                                 │
└────────────────────────────────────────────────────────────────────────────┘
  [ ] python treasury_client.py buybacks-cusips --limit 3
  [ ] python treasury_client.py tips-summary --json
  [ ] python treasury_client.py tips-index-ratio --cusip 912810FD5 --from-date 2025-01-01
  [ ] python treasury_client.py ownership --as-of 2024-12-31
  [ ] python treasury_client.py tic-mfh --country "Japan" --months 12
  [ ] python treasury_direct_client.py refunding-latest
```

---

## 7. Appendices

### Appendix A — Fiscal Data API filter syntax (refresher)

```
field:operator:value          single clause
clause1,clause2,clause3       multiple clauses combined with AND
field:in:(v1,v2,v3)           in-set membership

operators:  eq, in, gte, gt, lte, lt
dates:      YYYY-MM-DD

Examples:
  filter=record_date:gte:2024-01-01,record_date:lte:2025-12-31
  filter=security_type:eq:Bill,record_date:gte:2024-01-01
  filter=country_currency_desc:in:(Canada-Dollar,Mexico-Peso)
  filter=cusip:eq:912810FD5,index_date:gte:2025-01-01
```

Combined params:

```
?fields=field1,field2&filter=record_date:gte:2024-01-01&sort=-record_date&page[size]=100&page[number]=1&format=json
```

Pagination semantics:

```
page[size]   default 100, max 10000
page[number] 1-based
total-count  in response.meta
total-pages  in response.meta
links.next   convenience link to next page (or null at last)
```

### Appendix B — Endpoint quick-cards (live verify URLs)

```
buybacks_security_details
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/buybacks_security_details?page[size]=5&sort=-operation_date&format=json

tips_cpi_data_summary
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/tips_cpi_data_summary?page[size]=5&format=json

tips_cpi_data_detail
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/tips_cpi_data_detail?filter=cusip:eq:912810FD5,index_date:gte:2025-01-01&page[size]=10&format=json

ofs2_estimated_ownership_treasury_securities
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/ofs2_estimated_ownership_treasury_securities?sort=-end_of_month&page[size]=20&format=json

ofs1_distribution_federal_securities_class_investors_type_issues
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/ofs1_distribution_federal_securities_class_investors_type_issues?sort=-record_date&page[size]=20&format=json

pdo1 / pdo2
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/pdo1_offerings_regular_weekly_treasury_bills?page[size]=2&format=json
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/pdo2_offerings_marketable_securities_other_regular_weekly_treasury_bills?page[size]=2&format=json

federal_maturity_rates
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/federal_maturity_rates?page[size]=5&format=json

receipts_by_department
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/receipts_by_department?page[size]=5&format=json

slgs_demand_deposit_rates / slgs_time_deposit_rates
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/slgs_demand_deposit_rates?page[size]=5&format=json
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/slgs_time_deposit_rates?page[size]=5&format=json

fcp1 / fcp2 / fcp3
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/fcp1_weekly_report_major_market_participants?page[size]=2&format=json
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/fcp2_monthly_report_major_market_participants?page[size]=2&format=json
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/fcp3_quarterly_report_large_market_participants?page[size]=2&format=json

esf1 / esf2
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/esf1_balances?page[size]=2&format=json
  https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/tb/esf2_statement_net_cost?page[size]=2&format=json

TIC Major Foreign Holders (live)
  https://ticdata.treasury.gov/Publish/mfh.txt
  https://www.treasury.gov/resource-center/data-chart-center/tic/Documents/snetus.csv

Quarterly Refunding (latest event)
  https://www.treasury.gov/resource-center/data-chart-center/quarterly-refunding/Pages/Latest.aspx
```

### Appendix C — PRISM use-case index by endpoint

```
┌─────────────────────────────────────────┬───────────────────────────────────────────────┐
│ Endpoint                                │ Primary PRISM use-case                        │
├─────────────────────────────────────────┼───────────────────────────────────────────────┤
│ buybacks_security_details                │ Off-the-run float drainage                    │
│ tips_cpi_data_summary / _detail          │ TIPS index-ratio computation, breakeven     │
│ ofs2_estimated_ownership_treasury        │ "Who owns the debt" canonical snapshot      │
│ ofs1_distribution_federal_securities     │ Issuer-side investor-class breakdown        │
│ pdo1 / pdo2                              │ Treasury-Bulletin-style auction history     │
│ federal_maturity_rates                   │ Weighted average UST cost by remaining mat  │
│ receipts_by_department                   │ Agency-attributed revenue (not just MTS)    │
│ slgs_demand / slgs_time                  │ Munis short-end reference rates             │
│ fcp1 / fcp2 / fcp3                       │ FX exposure of large dealers (OTC)          │
│ esf1 / esf2                              │ FX intervention vehicle balance / activity  │
│ TIC mfh                                  │ Foreign holdings by country (China/Japan)   │
│ TIC snetus                               │ Net foreign LT purchases by country         │
│ refunding auction-schedule.xml           │ Forward issuance pipeline (next quarter)    │
│ refunding buyback-schedule.xml           │ Forward buyback pipeline                    │
│ refunding TBAC presentation              │ Treasury debt-management framing            │
│ refunding primary dealer survey          │ Sell-side consensus on issuance / deficits  │
└─────────────────────────────────────────┴───────────────────────────────────────────────┘
```

### Appendix D — Verifying data freshness

```
buybacks_security_details: ~1-2 days after each operation
tips_cpi_data_detail:      monthly with CPI release (~mid-month for prior month)
ofs2_estimated_ownership:  quarterly (~1-2 quarters lag from end-of-quarter)
ofs1_distribution:         quarterly (~1-2 quarters lag)
pdo1 / pdo2:               monthly with Treasury Bulletin
fcp1:                      weekly (T+5 release)
fcp2:                      monthly (T+15 release)
fcp3:                      quarterly
esf1 / esf2:               quarterly
TIC mfh:                   monthly (~6-week lag from end-of-month)
TIC snetus:                monthly (~6-week lag)
Quarterly refunding XMLs:  4× per year (Feb / May / Aug / Nov)
```

---

End of guide.
