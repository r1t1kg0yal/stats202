# U.S. Treasury Fiscal Data

Sandbox-injected modules: `treasury_client` (this guide), `treasury_direct_client` (covers separate auction-results / refunding APIs at TreasuryDirect.gov; both share this L2 module). Anonymous API; no auth required at the target. PRISM routes through the GS proxy via `session_and_auth()`.

Base URL: `https://api.fiscaldata.treasury.gov/services/api/fiscal_service`


## Triggers

Use for: Treasury CUSIPs and auction schedules, debt to the penny, historical debt outstanding, MSPD (marketable securities outstanding detail), MTS (Monthly Treasury Statement) receipts/outlays/deficit, DTS (Daily Treasury Statement) operating cash balance and deposits/withdrawals, average interest rates on Treasury securities, Treasury reporting exchange rates, revenue collections, interest expense on public debt, federal debt schedules, TROR (Treasury Report on Receivables), Treasury Offset Program data, savings bonds, SLGS, gold reserve, financial statements (balance sheets, net cost, net position), long-term fiscal projections, social insurance, FRN daily indexes, Treasury buybacks (Liquidity Support / Cash Management operations).

Not for: overnight reference rates / SOFR / EFFR (NY Fed), SOMA holdings / QT (NY Fed), auction results with bid-to-cover / tails (TreasuryDirect), yield curve / par yields (TreasuryDirect or FRED), OTC swap volumes (DTCC), futures positioning (CFTC), bank-level financials (FDIC), commercial paper / CD rates (FRED), prediction markets (prediction_markets), primary dealer positioning (NY Fed).


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
| Single-CUSIP lookup with full auction record | `scrape_securities_by_cusip` | One call returns auction + result + bid-to-cover (and `_compute_tail` adds `tailBps`) |
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
| All `scrape_*` / `fetch_*` methods | return parsed Python (list/dict), no file I/O |
| `_compute_tail` | static helper, mutates record in place; `tailBps = highYield - averageMedianYield` (bp) |
| Bill auction history | chunked into 2-year windows |
| Note/Bond/TIPS/FRN history | chunked into 5-year windows |
| Dedup key on history pulls | `(cusip, auctionDate)` |
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

# Debt to the Penny
# Returns: list of dicts with record_date, tot_pub_debt_out_amt, intragov_hold_amt, etc.
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

# MTS tables: table param is "1"-"9", "6a", "6b", "6c", "6d", "6e"
# Returns: list of dicts

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

# Average interest rates on Treasury securities
# Returns: list of dicts with record_date, security_type_desc (Marketable/Non-marketable),
# security_desc (Treasury Bills/Notes/Bonds/TIPS/FRN/...), avg_interest_rate_amt
# NOTE: this endpoint does NOT have a `security_type` field. The wrapper accepts
# the canonical alias (Bill / Note / Bond / TIPS / FRN) and translates to the
# correct `security_desc:eq:Treasury <X>` filter internally.
rows = treasury_client.get_avg_interest_rates()
rows = treasury_client.get_avg_interest_rates(security_type="Bill")
rows = treasury_client.get_avg_interest_rates(security_type="Note", from_date="2024-01-01")
rows = treasury_client.get_avg_interest_rates(filter_expr="avg_interest_rate_amt:gte:4.0", from_date="2024-01-01")

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
scraper = treasury_direct_client.TreasuryDirectScraper()

# Announced (upcoming, not yet held) auctions
upcoming = scraper.scrape_announced(security_type="Bill", days=30)
# Returns list[dict] with cusip, securityTerm, auctionDate, issueDate,
# offeringAmt, etc. — fields available BEFORE the auction is held.

# Recently auctioned (results published) — adds yield + bid-to-cover
recent = scraper.scrape_auctioned(security_type="Note", days=14)
# Same shape as scrape_announced + highYield, lowYield,
# averageMedianYield, bidToCoverRatio, tailBps (auction-tail bp).

# Single-CUSIP lookup
records = scraper.scrape_securities_by_cusip("912797TD9")
# Returns list[dict]; usually 1 entry, may be more for reopenings.

# Auction-history sweep with date-range chunking
history = scraper.scrape_securities_api(security_type="Bond",
                                         days=730)
# Auto-chunks to avoid the search endpoint's ~2000-record cap.
# Records are sorted by auctionDate desc; tailBps populated.

# Full history (1997-present, all types)
all_history = scraper.scrape_securities_api(full_history=True)

# Debt-to-the-penny — current snapshot
current_debt = scraper.scrape_debt_api(current_only=True)
# Returns dict with effectiveDate, totalDebt, publicDebt,
# governmentHoldings.

# Debt-to-the-penny — historical range
hist = scraper.scrape_debt_api(start_date="2024-01-01",
                                end_date="2024-12-31")
# Returns list[dict] of daily records (chunked into 12-month windows
# internally).

# Buybacks (mirrors treasury_client.get_buybacks; either works)
buybacks = scraper.scrape_buybacks(with_results_only=True)
# Returns list[dict] with operation_date, operation_type
# ("Liquidity Support" / "Cash Management"), security_type,
# total_par_amt_offered, total_par_amt_accepted, settlement_date.

# Quarterly refunding artifact scrapers
refunding = scraper.scrape_refunding_latest()
# Returns dict with title, announcements (list of {date, links}), url.

auction_schedule = scraper.fetch_auction_schedule_xml()
buyback_schedule = scraper.fetch_buyback_schedule_xml()
# Both return list[dict] (one record per scheduled operation).
```


