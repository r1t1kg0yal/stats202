# U.S. Treasury Fiscal Data

Sandbox-injected modules: `treasury_client` (Fiscal Data API at `api.fiscaldata.treasury.gov`) + `treasury_direct_client` (TreasuryDirect.gov auction-results / refunding APIs). Both modules share this L2 guide. Anonymous APIs; PRISM routes through the GS proxy.

Base URL (treasury_client): `https://api.fiscaldata.treasury.gov/services/api/fiscal_service`
Base URL (treasury_direct_client): `https://www.treasurydirect.gov`


## Triggers

Use for: Treasury CUSIPs and auction schedules, debt to the penny, historical debt outstanding, MSPD (marketable securities outstanding detail), MTS (Monthly Treasury Statement) receipts/outlays/deficit, DTS (Daily Treasury Statement) operating cash balance and deposits/withdrawals, average interest rates on Treasury securities, Treasury reporting exchange rates, revenue collections, interest expense on public debt, federal debt schedules, TROR (Treasury Report on Receivables), Treasury Offset Program data, savings bonds, SLGS, gold reserve, financial statements (balance sheets, net cost, net position), long-term fiscal projections, social insurance, FRN daily indexes, Treasury buybacks (Liquidity Support / Cash Management operations), TreasuryDirect auction mechanics (highYield, bid-to-cover, auction tail in bps), CUSIP single-lookup, quarterly refunding artifacts.

Not for: overnight reference rates / SOFR / EFFR (NY Fed), SOMA holdings / QT (NY Fed), DAILY yield curve / par yields (FRED — series like DGS10, DGS2, DGS30; NOT in either of these clients), OTC swap volumes (DTCC), futures positioning (CFTC), bank-level financials (FDIC), commercial paper / CD rates (FRED), prediction markets (prediction_markets), primary dealer positioning (NY Fed).


## Decision table: treasury_client vs treasury_direct_client

| Question PRISM is asked | Use this client | Why |
|---|---|---|
| Latest debt to the penny + clean breakdown | `treasury_client.get_debt_summary()` | Convenience accessor; returns clean keys + coerced floats |
| Upcoming auctions (next N) | `treasury_direct_client.<scraper>.next_n_announced(n=N, ...)` | Fresher than Fiscal `upcoming_auctions` (which has staleness incidents); auto-widens window until N records |
| Auction RESULTS (highYield, bid-to-cover, tail bps) | `treasury_direct_client.<scraper>.scrape_auctioned()` or `.scrape_securities_api()` | Fiscal Data auctions_query lacks the auction-mechanics fields |
| Single-CUSIP lookup with results | `treasury_direct_client.<scraper>.scrape_securities_by_cusip(cusip)` | One call returns auction + result + computed `tailBps` |
| MTS receipts/outlays/deficit (monthly) | `treasury_client.get_mts_table(N)` or `.get_mts_table_9_line(name)` | The Fiscal MTS surface; tdir doesn't carry this |
| DTS Operating Cash Balance / TGA | `treasury_client.get_tga_balance()` | Convenience: latest record_date + by-account breakdown + headline |
| Avg interest rate on Bills/Notes/Bonds (curr + 12mo back) | `treasury_client.get_latest_avg_interest_rates()` + `.get_avg_interest_rates(security_type=X, from_date=...)` | Wrapper handles the security_desc translation; latest accessor returns dict by category |
| Treasury buybacks | EITHER `treasury_client.get_buybacks()` OR `treasury_direct_client.<scraper>.scrape_buybacks()` | Both work; treasury_client preferred (Bucket A, simpler) unless GS proxy unavailable |
| Quarterly refunding announcement | `treasury_direct_client.<scraper>.scrape_refunding_latest()` | Tdir-specific |
| Daily yield curve (DGS10 etc.) | NEITHER — use FRED | Not in this client surface |

The decision table is the routing AUTHORITY. When a user prompt mentions a specific client name (e.g. "via TreasuryDirect" or "via Fiscal Data"), honour the named client. When the user prompt is client-agnostic ("show me the next 10 upcoming TIPS"), use this table to pick.


## Format quirks (the wrapper absorbs these — PRISM doesn't have to remember)

These are surface oddities of the upstream APIs. The clients hide them at the boundary; this section exists so PRISM knows NOT to write the workarounds itself.

| Quirk | Where it surfaces | What the wrapper does |
|---|---|---|
| Fiscal Data API returns ALL fields as STRINGS (numbers, dates) | Every endpoint | `treasury_client._request` reads the response's `meta.dataTypes` and coerces numerics on the way back. Pass `coerce_types=False` to opt out. |
| TreasuryDirect returns numeric fields as STRINGS | Every endpoint | `treasury_direct_client._fetch_json(coerce=True)` (default) walks the record through `_NUMERIC_FIELDS` and converts. |
| TIPS labeled `"TIPS Note"` (not just `"TIPS"`) on `upcoming_auctions` | `treasury_client.get_upcoming_auctions / get_cusips / get_auctions_data` | Pass `security_type="TIPS"` (canonical); wrapper translates to `security_type:in:(TIPS,TIPS Note)` via `_build_security_type_filter`. |
| `avg_interest_rates` uses `security_desc` field, NOT `security_type` | `treasury_client.get_avg_interest_rates` | Pass `security_type="Bill"/"Note"/"Bond"/"TIPS"/"FRN"` (canonical); wrapper translates to `security_desc:eq:Treasury <X>`. |
| Bills are quoted in DISCOUNT RATE not yield: `highDiscountRate` / `highInvestmentRate` instead of `highYield` | TreasuryDirect auction records | `treasury_direct_client.get_high_rate(rec)` returns `{"rate": float, "rate_type": "yield"\|"discount"\|"investment", ...}` security-type-aware. |
| Bills' `tailBps` from yield-basis formula returns None | TreasuryDirect auction records | `treasury_direct_client.compute_tail(rec)` uses `highDiscountRate - averageMedianDiscountRate` for Bills, yield-basis for everything else. Auto-attached to records by `scrape_*` methods. |
| `upcoming_auctions` endpoint sometimes surfaces stale records (e.g. 2024 dates returned in 2026) | `treasury_client.get_upcoming_auctions` | Default `only_future=True` filters out rows with `auction_date < today`. Pass `only_future=False` to see everything. |
| TreasuryDirect uses camelCase (`highYield`, `bidToCoverRatio`, `auctionDate`); Fiscal uses snake_case (`tot_pub_debt_out_amt`, `record_date`) | Cross-client work | Casing reflects the upstream APIs; no normalization (would break call-site code). PRISM uses the casing the relevant client returns. |
| `scrape_*` endpoints are TIME-WINDOWED (`days=N`), not COUNT-bounded | TreasuryDirect | `last_n_auctions(security_type, n)` and `next_n_announced(n)` widen the window until N records arrive. |
| `securityTerm` is a free-text string ("10-Year", "2-Year 1-Month", "9-Year 10-Month") with no canonical tenor field | TreasuryDirect | Pass `tenor_years=10` (or any float) to `scrape_securities_api / scrape_announced / scrape_auctioned` — wrapper parses the term and matches with ±5% tolerance. |


## Domain semantics (what the wrapper can't hide — PRISM needs to know)

| Concept | Why PRISM needs it |
|---|---|
| Original vs Reopening auctions | A 10Y Note "issue" appears as 1 quarterly ORIGINAL + ~8 monthly REOPENINGS in a 12-month window. "How many 10Y Note auctions" is ambiguous; the wrapper exposes `originals_only=True` / `reopenings_only=True` on `scrape_securities_api` so PRISM picks. Default returns BOTH. |
| Bill auction tail = discount-rate basis | Bills are quoted in discount-rate space. The "tail" still measures bid dispersion but in different units than Note/Bond yield-basis tails. `compute_tail` returns the right one per security type — but if PRISM is comparing tails ACROSS Bill and Note auctions it must normalise (or note the units). |
| Bill rates: discount vs bond-equivalent yield | Bills publish BOTH `highDiscountRate` and `highInvestmentRate`. The "investment rate" is the bond-equivalent yield — that's the apples-to-apples comparison vs Note/Bond `highYield`. `get_high_rate(rec)` returns the investment rate for Bills by default. |
| TGA = Federal Reserve Account row in DTS Table 1 | DTS Table 1 has multiple `account_type` rows per `record_date`. The Treasury General Account headline number is the "Federal Reserve Account" row's `close_today_bal`. `get_tga_balance()` exposes both the headline (Fed Reserve Account close) and the breakdown. |
| MTS Table 9 line_code_nbr = federal receipts/outlays hierarchy | MTS-9 publishes a hierarchy keyed by integer `line_code_nbr`. Common ones: 120 = total receipts, 100 = individual income tax, 210 = corporate income tax, 300 = social security tax, 180 = total outlays. `MTS_TABLE_9_LINE_CODES` exposes the canonical ones; `get_mts_table_9_line(name_or_code)` resolves either. |
| Reopening multiplicity for single-CUSIP lookup | `scrape_securities_by_cusip` returns 1+ records — a CUSIP can appear once (original only) or multiple times (original + reopenings). Each row is a distinct auction event; pick by `auctionDate`. |
| Daily yield curve is NOT here | DGS10, DGS2, DGS30 etc. live in FRED, not in either treasury_client or treasury_direct_client. The Fiscal Data API has `avg_interest_rates` (weighted-average rate Treasury PAYS on outstanding stock — different concept). |
| `treasury_client` registers ~80 of the 179 official Fiscal Data endpoints | The registered subset is the macro-relevant curated catalog. For endpoints not in `ENDPOINT_REGISTRY`, call `fetch_official_endpoint_catalog()` to see the gap, then either request a wrapper update or hit the path directly via `_request(endpoint=<path>, ...)`. |


## Data Catalog

### Categories

| Category | Description |
|----------|-------------|
| `auctions` | Auction schedules, CUSIPs, record-setting auction data |
| `debt` | Debt to penny, outstanding, schedules, MSPD, TROR, TOP |
| `accounting` | MTS, DTS, financial reports, reconciliations |
| `interest_rates` | Average rates, exchange rates, yields |
| `securities` | Savings bonds, TreasuryDirect, SLGS, redemption tables |
| `revenue` | Revenue collections, tax receipts |
| `payments` | Judgment Fund, advances |
| `other` | Gold reserve, gift contributions, misc |

### Endpoint Registry -- Auctions (3 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `upcoming_auctions` | `v1/accounting/od/upcoming_auctions` | Treasury Securities Upcoming Auctions |
| `record_setting_auction` | `v2/accounting/od/record_setting_auction` | Record-Setting Auction |
| `frn_daily_indexes` | `v1/accounting/od/frn_daily_indexes` | FRN Daily Indexes |

### Endpoint Registry -- Debt (22 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `debt_to_penny` | `v2/accounting/od/debt_to_penny` | Debt to the Penny |
| `debt_outstanding` | `v2/accounting/od/debt_outstanding` | Historical Debt Outstanding |
| `schedules_fed_debt` | `v1/accounting/od/schedules_fed_debt` | Schedules of Federal Debt by Month |
| `schedules_fed_debt_fytd` | `v1/accounting/od/schedules_fed_debt_fytd` | Schedules of Federal Debt Fiscal Year-to-Date |
| `schedules_fed_debt_daily_activity` | `v1/accounting/od/schedules_fed_debt_daily_activity` | Schedules of Federal Debt Daily Activity |
| `schedules_fed_debt_daily_summary` | `v1/accounting/od/schedules_fed_debt_daily_summary` | Schedules of Federal Debt Daily Summary |
| `mspd_table_1` | `v1/debt/mspd/mspd_table_1` | Summary of Treasury Securities Outstanding |
| `mspd_table_2` | `v1/debt/mspd/mspd_table_2` | Statutory Debt Limit |
| `mspd_table_3_market` | `v1/debt/mspd/mspd_table_3_market` | Detail of Marketable Treasury Securities Outstanding |
| `mspd_table_3_nonmarket` | `v1/debt/mspd/mspd_table_3_nonmarket` | Detail of Non-Marketable Treasury Securities Outstanding |
| `mspd_table_4` | `v1/debt/mspd/mspd_table_4` | MSPD Historical Data |
| `mspd_table_5` | `v1/debt/mspd/mspd_table_5` | Holdings of Treasury Securities in Stripped Form |
| `tror` | `v2/debt/tror` | Treasury Report on Receivables Full Data |
| `tror_collected_outstanding` | `v2/debt/tror/collected_outstanding_recv` | Collected and Outstanding Receivables |
| `tror_delinquent_debt` | `v2/debt/tror/delinquent_debt` | Delinquent Debt |
| `tror_collections_delinquent` | `v2/debt/tror/collections_delinquent_debt` | Collections on Delinquent Debt |
| `tror_written_off` | `v2/debt/tror/written_off_delinquent_debt` | Written Off Delinquent Debt |
| `tror_data_act_compliance` | `v2/debt/tror/data_act_compliance` | 120 Day Delinquent Debt Referral Compliance |
| `top_federal` | `v1/debt/top/top_federal` | Treasury Offset Program - Federal Collections |
| `top_state` | `v1/debt/top/top_state` | Treasury Offset Program - State Programs |
| `title_xii` | `v2/accounting/od/title_xii` | Advances to State Unemployment Funds (SSA Title XII) |
| `interest_uninvested` | `v2/accounting/od/interest_uninvested` | Federal Borrowings Program: Interest on Uninvested Funds |
| `interest_cost_fund` | `v2/accounting/od/interest_cost_fund` | Federal Investments Program: Interest Cost by Fund |

### Endpoint Registry -- Accounting / MTS (15 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `mts_table_1` | `v1/accounting/mts/mts_table_1` | Summary of Receipts, Outlays, Deficit/Surplus |
| `mts_table_2` | `v1/accounting/mts/mts_table_2` | Summary of Budget and Off-Budget Results |
| `mts_table_3` | `v1/accounting/mts/mts_table_3` | Summary of Receipts and Outlays |
| `mts_table_4` | `v1/accounting/mts/mts_table_4` | Receipts of the U.S. Government |
| `mts_table_5` | `v1/accounting/mts/mts_table_5` | Outlays of the U.S. Government |
| `mts_table_6` | `v1/accounting/mts/mts_table_6` | Means of Financing the Deficit |
| `mts_table_6a` | `v1/accounting/mts/mts_table_6a` | Analysis of Change in Excess of Liabilities |
| `mts_table_6b` | `v1/accounting/mts/mts_table_6b` | Securities Issued by Federal Agencies |
| `mts_table_6c` | `v1/accounting/mts/mts_table_6c` | Federal Agency Borrowing via Treasury Securities |
| `mts_table_6d` | `v1/accounting/mts/mts_table_6d` | Investments of Federal Government Accounts |
| `mts_table_6e` | `v1/accounting/mts/mts_table_6e` | Guaranteed and Direct Loan Financing |
| `mts_table_7` | `v1/accounting/mts/mts_table_7` | Receipts and Outlays by Month |
| `mts_table_8` | `v1/accounting/mts/mts_table_8` | Trust Fund Impact on Budget Results |
| `mts_table_9` | `v1/accounting/mts/mts_table_9` | Receipts by Source, Outlays by Function |

### Endpoint Registry -- Accounting / DTS (7 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `dts_table_1` | `v1/accounting/dts/dts_table_1` | Operating Cash Balance |
| `dts_table_2` | `v1/accounting/dts/dts_table_2` | Deposits and Withdrawals of Operating Cash |
| `dts_table_3a` | `v1/accounting/dts/dts_table_3a` | Public Debt Transactions |
| `dts_table_3b` | `v1/accounting/dts/dts_table_3b` | Adjustment of Public Debt to Cash Basis |
| `dts_table_3c` | `v1/accounting/dts/dts_table_3c` | Debt Subject to Limit |
| `dts_table_4` | `v1/accounting/dts/dts_table_4` | Federal Tax Deposits (Inter-agency Tax Transfers) |
| `dts_table_5` | `v1/accounting/dts/dts_table_5` | Short-Term Cash Investments |
| `dts_table_6` | `v1/accounting/dts/dts_table_6` | Income Tax Refunds Issued |

### Endpoint Registry -- Accounting / Financial Reports (8 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `statement_net_cost` | `v2/accounting/od/statement_net_cost` | Statements of Net Cost |
| `net_position` | `v1/accounting/od/net_position` | Statements of Operations and Changes in Net Position |
| `reconciliations` | `v1/accounting/od/reconciliations` | Reconciliations of Net Operating Cost |
| `cash_balance` | `v1/accounting/od/cash_balance` | Statements of Changes in Cash Balance |
| `balance_sheets` | `v2/accounting/od/balance_sheets` | Balance Sheets |
| `long_term_projections` | `v1/accounting/od/long_term_projections` | Statements of Long-Term Fiscal Projections |
| `social_insurance` | `v1/accounting/od/social_insurance` | Statements of Social Insurance |
| `insurance_amounts` | `v1/accounting/od/insurance_amounts` | Statements of Changes in Social Insurance Amounts |

### Endpoint Registry -- Interest Rates (5 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `avg_interest_rates` | `v2/accounting/od/avg_interest_rates` | Average Interest Rates on U.S. Treasury Securities |
| `rates_of_exchange` | `v1/accounting/od/rates_of_exchange` | Treasury Reporting Rates of Exchange |
| `interest_expense` | `v2/accounting/od/interest_expense` | Interest Expense on the Public Debt Outstanding |
| `qualified_tax` | `v2/accounting/od/qualified_tax` | Historical Qualified Tax Credit Bond Interest Rates |
| `utf_qtr_yields` | `v2/accounting/od/utf_qtr_yields` | Unemployment Trust Fund Quarterly Yields |

### Endpoint Registry -- Securities (14 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `redemption_tables` | `v2/accounting/od/redemption_tables` | Accrual Savings Bonds Redemption Tables |
| `slgs_statistics` | `v2/accounting/od/slgs_statistics` | Monthly SLGS Securities Program |
| `slgs_savings_bonds` | `v1/accounting/od/slgs_savings_bonds` | Savings Bonds Securities Sold |
| `sb_value` | `v2/accounting/od/sb_value` | Savings Bonds Value Files |
| `slgs_securities` | `v1/accounting/od/slgs_securities` | State and Local Government Series Securities |
| `securities_sales` | `v1/accounting/od/securities_sales` | Securities Issued in TreasuryDirect - Sales |
| `securities_sales_term` | `v1/accounting/od/securities_sales_term` | Securities Sales by Term |
| `securities_transfers` | `v1/accounting/od/securities_transfers` | Transfers of Marketable Securities |
| `securities_conversions` | `v1/accounting/od/securities_conversions` | Conversions of Paper Savings Bonds |
| `securities_redemptions` | `v1/accounting/od/securities_redemptions` | Securities Redemptions |
| `securities_outstanding` | `v1/accounting/od/securities_outstanding` | Securities Outstanding |
| `securities_c_of_i` | `v1/accounting/od/securities_c_of_i` | Certificates of Indebtedness |
| `securities_accounts` | `v1/accounting/od/securities_accounts` | Securities Accounts |
| `savings_bonds_report` | `v1/accounting/od/savings_bonds_report` | Paper Savings Bonds Issues, Redemptions, Maturities by Series |
| `savings_bonds_mud` | `v1/accounting/od/savings_bonds_mud` | Matured Unredeemed Debt |
| `savings_bonds_pcs` | `v1/accounting/od/savings_bonds_pcs` | Piece Information by Series |

### Endpoint Registry -- Revenue (1 endpoint)

| Key | API Path | Table Name |
|-----|----------|------------|
| `revenue_collections` | `v2/revenue/rcm` | U.S. Government Revenue Collections |

### Endpoint Registry -- Payments (1 endpoint)

| Key | API Path | Table Name |
|-----|----------|------------|
| `jfics_congress_report` | `v2/payments/jfics/jfics_congress_report` | Judgment Fund: Annual Report to Congress |

### Endpoint Registry -- Other (2 endpoints)

| Key | API Path | Table Name |
|-----|----------|------------|
| `gold_reserve` | `v2/accounting/od/gold_reserve` | U.S. Treasury-Owned Gold |
| `gift_contributions` | `v2/accounting/od/gift_contributions` | Gift Contributions to Reduce the Public Debt |

### Filter Syntax

Format: `field:operator:value`. Multiple filters are comma-separated.

| Operator | Meaning | Example |
|----------|---------|---------|
| `eq` | Equals | `security_type:eq:Bill` |
| `in` | In set | `country_currency_desc:in:(Canada-Dollar,Mexico-Peso)` |
| `gte` | Greater than or equal | `record_date:gte:2024-01-01` |
| `gt` | Greater than | `record_date:gt:2024-01-01` |
| `lte` | Less than or equal | `record_date:lte:2025-12-31` |
| `lt` | Less than | `record_date:lt:2025-01-01` |

Combined example: `security_type:eq:Bill,record_date:gte:2024-01-01,record_date:lte:2025-12-31`

### Sort Syntax

Prefix field name with `-` for descending. Default sort is `-record_date` (newest first).

| Sort | Meaning |
|------|---------|
| `-record_date` | Newest first |
| `record_date` | Oldest first |
| `-tot_pub_debt_out_amt` | Largest debt first |

### Sample Query Patterns

| Description | Key | Filter | Fields |
|-------------|-----|--------|--------|
| Debt to penny, recent 10 | `debt_to_penny` | | `record_date, tot_pub_debt_out_amt` |
| MTS table 9, line 120 (receipts total) | `mts_table_9` | `line_code_nbr:eq:120` | `record_date, classification_desc, current_month_rcpt_outly_amt` |
| Exchange rates Canada/Mexico 2024 | `rates_of_exchange` | `country_currency_desc:in:(Canada-Dollar,Mexico-Peso),record_date:gte:2024-01-01` | `country_currency_desc, exchange_rate, record_date` |
| Revenue by tax category | `revenue_collections` | `tax_category_id:eq:3` | `record_date, net_collections_amt, tax_category_desc` |
| Average rates, Bills only | `avg_interest_rates` | `security_desc:eq:Treasury Bills` | `record_date, security_desc, avg_interest_rate_amt` |
| CUSIPs for TIPS auctions | `upcoming_auctions` | `security_type:eq:TIPS` | `cusip, auction_date, offering_amt` |
| DTS operating cash balance | `dts_table_1` | | `record_date, account_type, close_today_bal, open_today_bal` |
| Gold reserve | `gold_reserve` | | `record_date, fine_troy_oz, book_value_amt` |


## TreasuryDirect Auction Surface (treasury_direct_client)

Sandbox-injected as `treasury_direct_client`. Class-based interface (`TreasuryDirectScraper`). Wraps the live `/TA_WS/securities/*` and `/NP_WS/debt/*` JSON APIs at `www.treasurydirect.gov` plus a few quarterly-refunding artifact scrapers. Distinct from `treasury_client` (Fiscal Data API).

### Use treasury_direct_client (NOT treasury_client) for:

| Need | Method | Why |
|---|---|---|
| Auction results: highYield, lowYield, averageMedianYield, bidToCoverRatio, tailBps | `scrape_auctioned`, `scrape_securities_by_cusip`, `scrape_securities_api` | Fiscal Data API does not expose these auction-mechanics fields |
| Announced auctions (upcoming, not yet held) | `scrape_announced` | More current than Fiscal Data's `upcoming_auctions` |
| Single-CUSIP lookup with full auction record | `scrape_securities_by_cusip` | One call returns auction + result + bid-to-cover; `tailBps` auto-attached (security-type-aware) |
| Buyback operations | `scrape_buybacks` | Mirrors Fiscal Data's `buybacks_operations` endpoint; either client works (Bucket A vs Bucket B) |
| Quarterly refunding announcement metadata | `scrape_refunding_latest` | TreasuryDirect-specific (not in Fiscal Data) |
| Upcoming auction / buyback schedule XML | `fetch_auction_schedule_xml`, `fetch_buyback_schedule_xml` | TreasuryDirect-specific |

Use `treasury_client` (Fiscal Data) for everything else: debt-to-penny, MTS, DTS, MSPD, exchange rates, historical aggregates, the 80+ endpoint registry.

### Transport

| Aspect | Detail |
|---|---|
| Path | manual CONNECT tunnel via `manual_https_request` (NOT `session_and_auth`) |
| Why | TreasuryDirect rejects requests where the standard adapter leaks auth headers (HTTP 400 Bad Request). Manual tunnel sends a clean target request. |
| Wrapping | Internal `_MockResponse` shim wraps the `(parsed_data, status_line)` tuple in a requests-style interface (`status_code` / `text` / `json()` / `ok`) so call sites are identical to standard-transport clients. |

### Behaviour

| Detail | Value |
|---|---|
| All `scrape_*` / `fetch_*` methods | return parsed Python (list/dict), no file I/O. Numeric fields auto-coerced to float / int per `_NUMERIC_FIELDS`. |
| `tailBps` on auction records | Auto-attached by every `scrape_*` method that returns auction records. Security-type-aware per Format quirks above (yield-basis for Notes/Bonds/TIPS/FRN; discount-rate-basis for Bills). For records built outside the `scrape_*` paths, call `treasury_direct_client.compute_tail(rec)` to compute it. |
| `get_high_rate(rec)` accessor | Module-level helper that returns `{"rate", "rate_type", "field_name", "security_type"}` — picks the canonical "high rate" per security type so PRISM never branches on `securityType`. Format quirks above documents the per-type field mapping. |
| Bill auction history | chunked into 2-year windows internally |
| Note/Bond/TIPS/FRN history | chunked into 5-year windows internally |
| Dedup key on history pulls | `(cusip, auctionDate)` — relevant when reasoning about reopenings; for averages within a window, dedup is already applied |
| Default `full_history` start | 2000-01-01 (debt API) / 1997-01-01 (securities API) |

---

## Python Recipes

### Treasury Buybacks

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# All buyback operations (191 total, 2000-present + 2024-present restart)
all_buybacks = treasury_client.get_buybacks()

# Liquidity Support operations only
liq = treasury_client.get_buybacks(operation_type="Liquidity Support")

# Cash Management operations
cash = treasury_client.get_buybacks(operation_type="Cash Management")

# TIPS buybacks
tips_bb = treasury_client.get_buybacks(security_type="TIPS")

# Only completed operations with results
completed = treasury_client.get_buybacks(with_results_only=True)

# Date range
recent = treasury_client.get_buybacks(from_date="2025-01-01", to_date="2026-04-15")

# Buyback fields: operation_date, operation_type, security_type, maturity_bucket,
# total_par_amt_offered, total_par_amt_accepted, nbr_issues_accepted,
# nbr_issues_eligible, max_par_amt_redeemed, settlement_date, par_amt_per_offer

# Full auction pricing data (bills, notes, bonds, TIPS, FRN)
auction_data = treasury_client.get_auctions_data(security_type="Note", from_date="2025-01-01")
by_cusip = treasury_client.get_auctions_data(cusip="91282CQJ3")
```

### Discovery and Schema

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# Full endpoint registry (80+ entries)
# Returns: dict[str, dict] with endpoint, table_name, category, date_field
registry = treasury_client.get_registry()

# List all keys or keys for a category
# category: "auctions"|"debt"|"accounting"|"interest_rates"|"securities"|"revenue"|"payments"|"other"
all_keys = treasury_client.list_keys()
debt_keys = treasury_client.list_keys("debt")
acct_keys = treasury_client.list_keys("accounting")

# Search endpoints by keyword (matches key or table_name)
# Returns: list of {key, table_name, category, endpoint}
results = treasury_client.search_endpoints("debt")
results = treasury_client.search_endpoints("interest")
results = treasury_client.search_endpoints("mts")
results = treasury_client.search_endpoints("exchange")

# Full manifest for LLM consumption
# Returns: {base_url, categories, endpoints_by_category, filter_format, date_format, total_endpoints}
manifest = treasury_client.get_manifest()

# Sample query patterns
# Returns: list of {desc, key, filter, fields, sort, max_rows}
examples = treasury_client.get_examples()

# Discover field names for any endpoint
# Returns: list[str] of field names
fields = treasury_client.discover_fields("debt_to_penny")
fields = treasury_client.discover_fields("mts_table_9")
fields = treasury_client.discover_fields("avg_interest_rates", sample_filter="security_desc:eq:Treasury Bills")

# Full schema: fields + labels (display names) + dataTypes
# Returns: {key, fields, labels, dataTypes}
schema = treasury_client.discover_schema("debt_to_penny")
schema = treasury_client.discover_schema("dts_table_1")
schema = treasury_client.discover_schema("rates_of_exchange")
```

### Filter Utilities

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# Single field equals value
f = treasury_client.filter_eq("security_type", "Bill")           # "security_type:eq:Bill"

# Field in set of values
f = treasury_client.filter_in("country_currency_desc", ["Canada-Dollar", "Mexico-Peso"])
# "country_currency_desc:in:(Canada-Dollar,Mexico-Peso)"

# Comparison operators
f = treasury_client.filter_gte("record_date", "2024-01-01")       # "record_date:gte:2024-01-01"
f = treasury_client.filter_gt("avg_interest_rate_amt", "4.0")      # "avg_interest_rate_amt:gt:4.0"
f = treasury_client.filter_lte("record_date", "2025-12-31")        # "record_date:lte:2025-12-31"
f = treasury_client.filter_lt("tot_pub_debt_out_amt", "30000000")   # "tot_pub_debt_out_amt:lt:30000000"

# Combine multiple filters
f = treasury_client.build_filter(
    treasury_client.filter_eq("security_type", "Bill"),
    treasury_client.filter_gte("record_date", "2024-01-01"),
    treasury_client.filter_lte("record_date", "2025-12-31"),
)
# "security_type:eq:Bill,record_date:gte:2024-01-01,record_date:lte:2025-12-31"

# Date range shorthand
f = treasury_client.filter_date_range("record_date", from_date="2024-01-01", to_date="2025-12-31")
# "record_date:gte:2024-01-01,record_date:lte:2025-12-31"

f = treasury_client.filter_date_range("record_date", from_date="2024-01-01")
# "record_date:gte:2024-01-01"
```

### Generic Endpoint Access

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# treasury_client.get_endpoint: Fetch all rows (auto-paginates) for any registered key
# Returns: list[dict]
rows = treasury_client.get_endpoint("debt_to_penny", from_date="2024-01-01", to_date="2025-12-31")
rows = treasury_client.get_endpoint("mts_table_1", from_date="2024-01-01", max_pages=5)
rows = treasury_client.get_endpoint("dts_table_1", from_date="2025-01-01", fields=["record_date", "account_type", "close_today_bal"])
rows = treasury_client.get_endpoint("gold_reserve", max_pages=2)
rows = treasury_client.get_endpoint("avg_interest_rates", filter_expr="security_desc:eq:Treasury Bills", from_date="2024-01-01")

# treasury_client.get_endpoint with sort, pagination control
rows = treasury_client.get_endpoint("debt_to_penny", sort="-record_date", page_size=500, max_pages=3)
rows = treasury_client.get_endpoint("mspd_table_3_market", page_number=1, page_size=50)

# treasury_client.get_endpoint with use_date_filters=False to bypass auto date filtering
rows = treasury_client.get_endpoint("record_setting_auction", use_date_filters=False, max_pages=2)
rows = treasury_client.get_endpoint("redemption_tables", use_date_filters=False, max_pages=1)

# treasury_client.get_endpoint with progress callback for long fetches
rows = treasury_client.get_endpoint("debt_to_penny", from_date="2000-01-01", show_progress=True)

# treasury_client.query: Maximum flexibility, returns {data, meta}
result = treasury_client.query("debt_to_penny", max_rows=10)
# result["data"] = list of row dicts, result["meta"] = API metadata

result = treasury_client.query("mts_table_9", filter_expr="line_code_nbr:eq:120",
               fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"],
               from_date="2024-01-01", max_rows=50)

result = treasury_client.query("rates_of_exchange",
               filter_expr="country_currency_desc:in:(Canada-Dollar,Mexico-Peso)",
               from_date="2024-01-01", max_rows=100)

result = treasury_client.query("avg_interest_rates", filter_expr="security_desc:eq:Treasury Bills",
               page_number=1, page_size=20)

# treasury_client.request_page: Single page fetch, returns full API response (data + meta + links)
resp = treasury_client.request_page("debt_to_penny", page_number=1, page_size=10)
# resp["data"], resp["meta"], resp["links"]

resp = treasury_client.request_page("mts_table_9", page_number=1, page_size=50,
                     filter_expr="line_code_nbr:eq:120",
                     fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"])
```

### CUSIPs and Auctions

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# CUSIPs from upcoming auctions
# Returns: list of dicts with cusip, security_type, security_term, auction_date, issue_date, offering_amt, reopening
rows = treasury_client.get_cusips()
rows = treasury_client.get_cusips(security_type="Bill")
rows = treasury_client.get_cusips(security_type="TIPS", from_date="2024-01-01")
rows = treasury_client.get_cusips(filter_expr="offering_amt:gte:50000", max_pages=5)
rows = treasury_client.get_cusips(fields=["cusip", "security_type", "auction_date"])

# Unique CUSIPs only
# Returns: sorted list[str]
cusips = treasury_client.get_unique_cusips()
cusips = treasury_client.get_unique_cusips(security_type="Note")
cusips = treasury_client.get_unique_cusips(from_date="2024-01-01", to_date="2025-12-31")

# Full CUSIP universe (upcoming_auctions + frn_daily_indexes)
# Returns: sorted list[str] -- maximizes API coverage
cusips = treasury_client.get_full_cusip_universe()
cusips = treasury_client.get_full_cusip_universe(show_progress=True)
cusips = treasury_client.get_full_cusip_universe(max_pages=10)

# Upcoming auctions
# Returns: list of dicts with full auction schedule fields
auctions = treasury_client.get_upcoming_auctions()
auctions = treasury_client.get_upcoming_auctions(security_type="Bond")
auctions = treasury_client.get_upcoming_auctions(from_date="2025-01-01", to_date="2025-12-31")
auctions = treasury_client.get_upcoming_auctions(filter_expr="offering_amt:gte:100000")

# Record-setting auctions
# Returns: list of dicts
records = treasury_client.get_record_setting_auctions()
records = treasury_client.get_record_setting_auctions(security_type="Bond")
records = treasury_client.get_record_setting_auctions(filter_expr="security_type:in:(Bill,Note)")
```

### Debt

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# === RECOMMENDED: convenience accessor for the headline debt question ===
# Returns: {"as_of": "YYYY-MM-DD", "total_debt": float,
#           "public_held": float, "intragov_held": float}
# Hides: opaque API field names, sort/latest mechanics, type coercion.
summary = treasury_client.get_debt_summary()
# {"as_of": "2026-05-01", "total_debt": 36421517325847.32,
#  "public_held": 28912304019221.45, "intragov_held": 7509213306625.87}

# As-of a specific date
summary = treasury_client.get_debt_summary(as_of="2024-12-31")

# === Raw endpoint when you need the full record / multiple days ===
# Returns: list of dicts with record_date, tot_pub_debt_out_amt,
# debt_held_public_amt, intragov_hold_amt, etc.  All numerics already
# coerced to float per the wrapper's boundary-coercion convention.
rows = treasury_client.get_debt_to_penny()
rows = treasury_client.get_debt_to_penny(from_date="2024-01-01", to_date="2025-12-31")
rows = treasury_client.get_debt_to_penny(fields=["record_date", "tot_pub_debt_out_amt"])
rows = treasury_client.get_debt_to_penny(filter_expr="tot_pub_debt_out_amt:gte:34000000000000", max_pages=5)
rows = treasury_client.get_debt_to_penny(page_number=1, page_size=10)

# Historical Debt Outstanding
rows = treasury_client.get_endpoint("debt_outstanding", max_pages=5)

# Schedules of Federal Debt
rows = treasury_client.get_endpoint("schedules_fed_debt", from_date="2024-01-01", max_pages=3)
rows = treasury_client.get_endpoint("schedules_fed_debt_fytd", from_date="2024-01-01")

# MSPD tables
rows = treasury_client.get_endpoint("mspd_table_1", from_date="2024-01-01")
rows = treasury_client.get_endpoint("mspd_table_3_market", from_date="2025-01-01", max_pages=2)
rows = treasury_client.get_endpoint("mspd_table_3_nonmarket", from_date="2025-01-01")

# Statutory Debt Limit
rows = treasury_client.get_endpoint("mspd_table_2", max_pages=3)

# TROR
rows = treasury_client.get_endpoint("tror", use_date_filters=False, max_pages=2)
rows = treasury_client.get_endpoint("tror_delinquent_debt", use_date_filters=False, max_pages=2)

# Treasury Offset Program
rows = treasury_client.get_endpoint("top_federal", use_date_filters=False, max_pages=2)
```

### Accounting -- MTS and DTS

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# === RECOMMENDED for MTS-9 single-line series (e.g. total receipts) ===
# Accepts either canonical name or raw line_code_nbr.
# MTS_TABLE_9_LINE_CODES exposes: total_receipts (120), individual_income (100),
# corporate_income (210), social_security (300), estate_gift (400),
# excise (500), customs (700), miscellaneous (800), total_outlays (180).
rows = treasury_client.get_mts_table_9_line("total_receipts", from_date="2025-01-01")
rows = treasury_client.get_mts_table_9_line(120, from_date="2025-01-01")  # equivalent

# === RECOMMENDED for the TGA balance question ===
# Returns: {"as_of": "YYYY-MM-DD", "total": float,
#           "by_account_type": {acct: balance, ...}, "headline": float}
# headline = the "Federal Reserve Account" close-of-day balance
# (the canonical "TGA balance" cited in macro reports).
tga = treasury_client.get_tga_balance()

# As-of a specific date
tga = treasury_client.get_tga_balance(as_of="2024-12-31")

# === Raw MTS / DTS access when you need the full table ===
# MTS tables: table param is "1"-"9", "6a", "6b", "6c", "6d", "6e"
# Returns: list of dicts (numerics already coerced to float)

# Receipts, Outlays, Deficit/Surplus
rows = treasury_client.get_mts_table("1", from_date="2024-01-01")

# Receipts by Source, Outlays by Function
rows = treasury_client.get_mts_table("9", from_date="2024-01-01")
rows = treasury_client.get_mts_table("9", filter_expr="line_code_nbr:eq:120",
                     fields=["record_date", "classification_desc", "current_month_rcpt_outly_amt"])

# Means of Financing the Deficit
rows = treasury_client.get_mts_table("6", from_date="2024-01-01")

# Receipts and Outlays by Month
rows = treasury_client.get_mts_table("7", from_date="2023-01-01", max_pages=5)

# Trust Fund Impact
rows = treasury_client.get_mts_table("8", from_date="2024-01-01")

# DTS tables: table param is "1"-"6", "3a", "3b", "3c"
# Returns: list of dicts

# Operating Cash Balance (TGA balance)
rows = treasury_client.get_dts_table("1", from_date="2025-01-01")
rows = treasury_client.get_dts_table("1", from_date="2025-01-01",
                     fields=["record_date", "account_type", "close_today_bal", "open_today_bal"])

# Deposits and Withdrawals
rows = treasury_client.get_dts_table("2", from_date="2025-03-01", max_pages=3)

# Public Debt Transactions
rows = treasury_client.get_dts_table("3a", from_date="2025-01-01")

# Debt Subject to Limit
rows = treasury_client.get_dts_table("3c", from_date="2025-01-01")

# Federal Tax Deposits
rows = treasury_client.get_dts_table("4", from_date="2025-01-01")

# Income Tax Refunds Issued
rows = treasury_client.get_dts_table("6", from_date="2025-01-01", to_date="2025-04-30")
```

### Interest Rates and Exchange Rates

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# === RECOMMENDED for "what's the latest avg rate on each security type?" ===
# Returns: {"Bill": float, "Note": float, "Bond": float, "TIPS": float,
#           "FRN": float, "as_of": "YYYY-MM-DD"}
# Hides: security_type -> security_desc translation, multi-call orchestration,
# string-vs-float coercion.
latest = treasury_client.get_latest_avg_interest_rates()

# === Raw avg_interest_rates endpoint for full series + cross-period work ===
# Returns: list of dicts (numerics coerced to float).
# `security_type` accepts the canonical alias (Bill / Note / Bond / TIPS / FRN);
# wrapper translates to the API's `security_desc:eq:Treasury <X>` internally.
rows = treasury_client.get_avg_interest_rates()
rows = treasury_client.get_avg_interest_rates(security_type="Bill")
rows = treasury_client.get_avg_interest_rates(security_type="Note", from_date="2024-01-01")
rows = treasury_client.get_avg_interest_rates(filter_expr="avg_interest_rate_amt:gte:4.0", from_date="2024-01-01")

# Compare current vs 12 months ago (canonical "rates moved by X bp" pattern):
from datetime import date, timedelta
y_ago = (date.today() - timedelta(days=365)).isoformat()
out = {}
for sec in ("Bill", "Note", "Bond"):
    cur = treasury_client.get_avg_interest_rates(security_type=sec, page_size=1, max_pages=1)
    bk  = treasury_client.get_avg_interest_rates(security_type=sec, from_date=y_ago, to_date=y_ago)
    out[sec] = {
        "current": cur[0]["avg_interest_rate_amt"] if cur else None,
        "year_ago": bk[0]["avg_interest_rate_amt"] if bk else None,
    }

# Exchange rates
# Returns: list of dicts with country_currency_desc, exchange_rate, record_date, etc.
rows = treasury_client.get_rates_of_exchange()
rows = treasury_client.get_rates_of_exchange(country_currency=["Canada-Dollar", "Mexico-Peso"])
rows = treasury_client.get_rates_of_exchange(country_currency=["Japan-Yen"], from_date="2024-01-01")
rows = treasury_client.get_rates_of_exchange(country_currency=["Euro Zone-Euro", "United Kingdom-Pound"],
                              from_date="2024-01-01", to_date="2025-12-31")

# Interest expense on public debt
rows = treasury_client.get_endpoint("interest_expense", from_date="2020-01-01", max_pages=5)

# Qualified tax credit bond rates
rows = treasury_client.get_endpoint("qualified_tax", max_pages=3)

# Unemployment Trust Fund quarterly yields
rows = treasury_client.get_endpoint("utf_qtr_yields", from_date="2020-01-01")
```

### Revenue

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# Revenue collections
# Returns: list of dicts with record_date, net_collections_amt, tax_category_desc, etc.
rows = treasury_client.get_revenue_collections()
rows = treasury_client.get_revenue_collections(from_date="2024-01-01", to_date="2025-12-31")
rows = treasury_client.get_revenue_collections(filter_expr="tax_category_id:eq:3")
rows = treasury_client.get_revenue_collections(fields=["record_date", "net_collections_amt", "tax_category_desc"],
                                from_date="2024-01-01")
rows = treasury_client.get_revenue_collections(page_number=1, page_size=50)
```

### Other Endpoints

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# Gold reserve
rows = treasury_client.get_endpoint("gold_reserve", max_pages=2)
rows = treasury_client.get_endpoint("gold_reserve", fields=["record_date", "fine_troy_oz", "book_value_amt"])

# Gift contributions to reduce public debt
rows = treasury_client.get_endpoint("gift_contributions", max_pages=2)

# Balance sheets
rows = treasury_client.get_endpoint("balance_sheets", from_date="2020-01-01")

# Long-term fiscal projections
rows = treasury_client.get_endpoint("long_term_projections", max_pages=3)

# Social insurance
rows = treasury_client.get_endpoint("social_insurance", max_pages=3)

# Savings bonds
rows = treasury_client.get_endpoint("savings_bonds_report", from_date="2024-01-01")
rows = treasury_client.get_endpoint("savings_bonds_mud", from_date="2024-01-01")

# SLGS
rows = treasury_client.get_endpoint("slgs_statistics", from_date="2024-01-01")
rows = treasury_client.get_endpoint("slgs_securities", from_date="2024-01-01")

# Securities in TreasuryDirect
rows = treasury_client.get_endpoint("securities_sales", from_date="2024-01-01")
rows = treasury_client.get_endpoint("securities_outstanding", from_date="2024-01-01")

# Judgment Fund
rows = treasury_client.get_endpoint("jfics_congress_report", max_pages=3)
```

### Error Handling

```python
# All public functions live on the sandbox-injected
# `treasury_client` module; call them as `treasury_client.<fn>(...)`.
# (No import line needed inside execute_analysis_script.)

# treasury_client.FiscalDataError has: http_status, api_error, api_message
try:
    rows = treasury_client.get_endpoint("nonexistent_key")
except ValueError as e:
    # Unknown endpoint key
    pass

try:
    rows = treasury_client.get_endpoint("debt_to_penny", filter_expr="bad_field:eq:foo")
except treasury_client.FiscalDataError as e:
    print(e.http_status)    # e.g. 400
    print(e.api_error)      # API error code
    print(e.api_message)    # API error message
```

### TreasuryDirect Auction API

```python
# Class-based interface — instantiate the scraper once and reuse.
# All numeric fields (yields, bid-to-cover, debt amounts, par amounts)
# come back as floats / ints — the wrapper coerces at the boundary
# via the _NUMERIC_FIELDS set. PRISM never has to float() these.
scraper = treasury_direct_client.TreasuryDirectScraper()

# === RECOMMENDED for "next N upcoming auctions" ===
# Wrapper auto-widens the search horizon until N records arrive.
# Sorted ascending by auctionDate (nearest first).
next_tips = scraper.next_n_announced(n=10, security_type="TIPS")
# tenor_years filters by canonical maturity (10 = 10Y, 30 = 30Y, etc.)
next_10y_notes = scraper.next_n_announced(n=10, security_type="Note", tenor_years=10)

# === RECOMMENDED for "last N completed auctions" ===
# Wrapper auto-widens window until N arrive (no need to guess `days=`).
last_5_bills = scraper.last_n_auctions(security_type="Bill", n=5)
last_5_10y_notes = scraper.last_n_auctions(
    security_type="Note", n=5, tenor_years=10, originals_only=True
)

# === Single-CUSIP lookup ===
records = scraper.scrape_securities_by_cusip("912797TD9")
# Returns list[dict]; 1 entry for original-only CUSIPs, more for reopenings.
# tailBps is populated security-type-aware (yield-basis for Notes/Bonds/TIPS,
# discount-rate-basis for Bills).

# === Auction-history sweep with new filters ===
history = scraper.scrape_securities_api(
    security_type="Note",
    days=365,
    tenor_years=10,           # filter to 10-Year Notes only
    originals_only=True,      # exclude monthly reopenings
)
# tenor_years parses securityTerm strings ("10-Year", "9-Year 10-Month",
# "1-Month", etc.) into canonical years with ±5% tolerance.
# originals_only / reopenings_only address the original-vs-reopening
# multiplicity (a 10Y Note appears as 1 quarterly original + monthly
# reopenings).

# Full history (1997-present, all types)
all_history = scraper.scrape_securities_api(full_history=True)

# === Announced (upcoming) auctions — raw access ===
upcoming = scraper.scrape_announced(security_type="Bill", days=30)
upcoming_30y = scraper.scrape_announced(security_type="Bond", days=120, tenor_years=30)

# === Recently auctioned (results published) — raw access ===
recent = scraper.scrape_auctioned(security_type="Note", days=14)
# All scrape_auctioned records have tailBps computed (security-type-aware).

# === Security-type-aware accessors (use these, not raw highYield) ===
# get_high_rate returns the right rate field for any security type:
#   Notes/Bonds/TIPS/FRN  -> highYield
#   Bills                 -> highInvestmentRate (bond-equivalent yield)
#                            with highDiscountRate as fallback
for rec in recent:
    info = treasury_direct_client.get_high_rate(rec)
    print(rec["cusip"], info["rate"], info["rate_type"])

# compute_tail handles Bill (discount-rate basis) vs others (yield basis).
# Already attached as tailBps on records returned by scrape_*; this is for
# computing the tail on a record built by some other path.
tail_bp = treasury_direct_client.compute_tail(rec)

# === Debt-to-the-penny via TreasuryDirect ===
# Current snapshot (clean dict with camelCase keys).
current_debt = scraper.scrape_debt_api(current_only=True)
# {"effectiveDate": "2026-05-01", "totalDebt": 36421517325847.32,
#  "publicDebt": 28912304019221.45, "governmentHoldings": 7509213306625.87}
# (vs treasury_client.get_debt_summary() which uses snake_case keys but
# is otherwise equivalent — pick by which client your prompt is in.)

# Historical range
hist = scraper.scrape_debt_api(start_date="2024-01-01", end_date="2024-12-31")

# === Buybacks ===
buybacks = scraper.scrape_buybacks(with_results_only=True)
# Either client works for buybacks; treasury_client.get_buybacks() is
# simpler (Bucket A, no manual_https_request hop) when GS proxy is up.

# === Quarterly refunding artifacts ===
refunding = scraper.scrape_refunding_latest()
auction_schedule = scraper.fetch_auction_schedule_xml()
buyback_schedule = scraper.fetch_buyback_schedule_xml()

# === Comparative two-window auction-demand pattern ===
# "Compare last N auctions to prior M-month baseline" — common analytical
# shape for auction-demand questions. The wrapper exposes the pieces;
# PRISM composes them.
from datetime import datetime, timedelta

scraper = treasury_direct_client.TreasuryDirectScraper()

# Step 1: Recent N auctions (sorted auctionDate desc).
recent = scraper.last_n_auctions(security_type="Bill", n=5)

# Step 2: Prior baseline window (e.g. 6 months) excluding the recent N.
recent_dates = {r.get("auctionDate") for r in recent}
baseline_window_days = 180
prior_pool = scraper.scrape_securities_api(
    security_type="Bill",
    days=baseline_window_days + 30,  # buffer past the recent set
)
prior = [r for r in prior_pool if r.get("auctionDate") not in recent_dates][:30]
# (prior list is sorted auctionDate desc; take the first ~30 to get the
# 6-month baseline excluding the recent cluster. Adjust slice if your
# definition of "prior 6 months" needs sharper bounds.)

# Step 3: Average bid-to-cover and tailBps across each window.
def _avg(records, key):
    vals = [r[key] for r in records if r.get(key) is not None]
    return sum(vals) / len(vals) if vals else None

recent_btc  = _avg(recent, "bidToCoverRatio")
prior_btc   = _avg(prior, "bidToCoverRatio")
recent_tail = _avg(recent, "tailBps")
prior_tail  = _avg(prior, "tailBps")

# Step 4: Verdict ("stronger / weaker / in line").
# Higher btc + lower tail = stronger demand.
btc_delta  = (recent_btc - prior_btc) if (recent_btc and prior_btc) else None
tail_delta = (recent_tail - prior_tail) if (recent_tail and prior_tail) else None
```


## Coverage gap (per D14 Completeness invariant)

The `treasury_client.ENDPOINT_REGISTRY` curates the macro-relevant subset of the official Fiscal Data API surface. As of 2026-05-02 the registry has ~80 endpoints; the official API has **179 endpoints** total per <https://fiscaldata.treasury.gov/api-documentation/>. The ~100 unregistered ones are mostly newer programs (ARP / IIJA / IRA spending sub-tables, smaller dataset variants).

If PRISM is asked about a Treasury concept that isn't covered by the registered endpoints:

```python
# Check what's missing.
catalog = treasury_client.fetch_official_endpoint_catalog()
# Returns: {"registered_locally": 80, "official_total": 179,
#           "official_url": "https://fiscaldata.treasury.gov/api-documentation/",
#           "datasets_url": "https://fiscaldata.treasury.gov/datasets/", ...}

# Hit a known endpoint path directly via _request even if it's not registered.
# (Path lives on the dataset's API Quick Guide page on fiscaldata.treasury.gov.)
resp = treasury_client._request("v2/accounting/od/<some_unregistered_path>", page_size=10)
rows = resp["data"]
```

PRISM should also surface this gap to the user when relevant ("the Treasury Fiscal Data API has 179 endpoints and we currently expose ~80; the dataset you're asking about may need a wrapper update — see fiscaldata.treasury.gov/datasets/").


