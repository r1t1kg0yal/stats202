# USASpending.gov Federal Spending

Script: `projects/apis/usaspending/usaspending.py`
Base URL: `https://api.usaspending.gov/api/v2`
Auth: None required
Rate limit: ~0.3s between calls (polite usage)
Dependencies: `requests`


## Triggers

Use for: federal spending totals and trends, agency-level budget authority / obligations / outlays, fiscal impulse (YoY spending acceleration), spending by award type (contracts/grants/loans/direct payments), geographic distribution of federal dollars (state/county/district), keyword award search (infrastructure, semiconductor, defense contracts), fiscal year budget cycle monitoring, spending composition across 9 curated agency groups.

Not for: federal revenue / tax receipts (Treasury Fiscal Data), state/local spending, real-time daily cash flows (Treasury DTS), debt issuance / auctions (TreasuryDirect), Fed balance sheet / monetary policy (FRED / NY Fed), regulatory / rulemaking data (Federal Register), GDP-accounting government spending (FRED NIPA), campaign spending (FEC).


## Data Catalog

### Agency Registry

| Group | Alias | Code | Agency |
|-------|-------|------|--------|
| fiscal | treasury | 015 | Department of the Treasury |
| defense | defense | 097 | Department of Defense |
| defense | homeland | 070 | Department of Homeland Security |
| social | hhs | 075 | Department of Health and Human Services |
| social | ssa | 028 | Social Security Administration |
| social | education | 091 | Department of Education |
| social | veterans | 036 | Department of Veterans Affairs |
| economy | agriculture | 012 | Department of Agriculture |
| economy | commerce | 013 | Department of Commerce |
| economy | sba | 073 | Small Business Administration |
| infrastructure | transportation | 069 | Department of Transportation |
| infrastructure | energy | 089 | Department of Energy |
| housing | hud | 086 | Department of Housing and Urban Development |
| labor | labor | 016 | Department of Labor |
| resources | interior | 014 | Department of the Interior |
| governance | justice | 015 | Department of Justice |
| governance | state | 019 | Department of State |

### Award Type Codes

| Category | Codes | What It Covers |
|----------|-------|----------------|
| contracts | A, B, C, D | Procurement of goods and services (defense hardware, IT, construction) |
| grants | 02, 03, 04, 05 | Financial assistance to states, universities, nonprofits |
| direct_payments | 06, 10 | Transfer payments to individuals (Social Security, Medicare, veterans benefits) |
| loans | 07, 08 | Federal lending (student loans, SBA loans, farm credit) |
| insurance | 09 | Federal insurance programs (FDIC-backed, crop insurance, flood insurance) |
| other | 11 | Miscellaneous financial assistance |

### Fiscal Year Convention

```
FY2025 = October 1, 2024 through September 30, 2025

The fiscal year is named for the calendar year in which it ENDS.
October through December of calendar year N belong to FY(N+1).

Timeline:
  Oct 2024 --|-- Nov --|-- Dec --|-- Jan 2025 --|-- ... --|-- Sep 2025
  <--- Q1 FY2025 --->   <- Q2 ->   <- Q3 ->   <- Q4 ->

Key dates:
  Oct 1:   New FY begins (new appropriations take effect, or CR starts)
  Sep 30:  FY ends ("use it or lose it" spending surge)
  Feb:     President's budget request submitted to Congress
```

### Agency Groups

```
FISCAL          treasury
DEFENSE         defense, homeland
SOCIAL          hhs, ssa, education, veterans
ECONOMY         agriculture, commerce, sba
INFRASTRUCTURE  transportation, energy
HOUSING         hud
LABOR           labor
RESOURCES       interior
GOVERNANCE      justice, state
```

### Agency List Fields (per agency)

| Field | Type | Description |
|-------|------|-------------|
| `agency_name` | string | Full agency name |
| `abbreviation` | string | Agency abbreviation |
| `toptier_code` | string | Top-tier agency code |
| `current_total_budget_authority_amount` | float | Current FY budget authority |
| `active_fq` | string | Active fiscal quarter |
| `active_fy` | string | Active fiscal year |

### Agency Detail Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Agency name |
| `toptier_code` | string | Top-tier code |
| `abbreviation` | string | Abbreviation |
| `agency_id` | int | Internal agency ID |
| `budget_authority_amount` | float | Budget authority |
| `current_total_budget_authority_amount` | float | Current total budget authority |
| `obligated_amount` | float | Total obligations |
| `outlay_amount` | float | Total outlays |
| `percentage_of_total_budget_authority` | float | Pct of total federal budget |
| `mission` | string | Agency mission statement |

### Budgetary Resources Fields (per fiscal year)

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_year` | int | Fiscal year |
| `agency_budgetary_resources` | float | Budget authority |
| `agency_total_obligated` | float | Total obligations |
| `agency_total_outlayed` | float | Total outlays |

### Spending Over Time Fields (per period)

| Field | Type | Description |
|-------|------|-------------|
| `time_period.fiscal_year` | int | Fiscal year |
| `time_period.month` | int | Month (when group_by=month) |
| `aggregated_amount` | float | Total obligations |
| `aggregated_outlay_amount` | float | Total outlays |

### By-Agency Fields (per agency)

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Agency name |
| `id` | int | Agency ID |
| `amount` | float | Total spending amount |

### Geography Fields (per area)

| Field | Type | Description |
|-------|------|-------------|
| `display_name` | string | State/county/district name |
| `shape_code` | string | Geographic code |
| `aggregated_amount` | float | Total spending |
| `per_capita` | float | Per-capita amount |
| `population` | int | Area population |

### Award Fields (per award)

| Field | Type | Description |
|-------|------|-------------|
| `Award ID` | string | Unique award identifier |
| `Recipient Name` | string | Award recipient |
| `Award Amount` | float | Dollar amount |
| `Awarding Agency` | string | Issuing agency |
| `Award Type` | string | Contract/grant/loan/etc |
| `Description` | string | Award description |
| `Start Date` | string | Award start date |
| `End Date` | string | Award end date |

### Total Budget Fields (per period)

| Field | Type | Description |
|-------|------|-------------|
| `fiscal_year` | int | Fiscal year |
| `fiscal_period` | int | Fiscal period (1-12) |
| `total_budgetary_resources` | float | Total budgetary resources |

### Fiscal Snapshot Fields (composite)

| Field | Type | Description |
|-------|------|-------------|
| `fy` | int | Fiscal year |
| `last_updated` | string | Data freshness date |
| `total_budget.budget_authority` | float | Aggregate budget authority |
| `total_budget.period` | int | As-of fiscal period |
| `yoy_change` | float | YoY change in budget authority (%) |
| `prev_budget_authority` | float | Prior FY budget authority |
| `top_agencies` | list | Top 10 agencies by award spending |
| `group_totals` | dict | Per-group agency counts and aliases |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Agencies

```bash
# All top-tier agencies ranked by budget authority
python usaspending.py agencies
python usaspending.py agencies --json
python usaspending.py agencies --export csv
python usaspending.py agencies --export json
```

### Agency Detail

```bash
# Deep dive on a specific agency (by alias or toptier code)
python usaspending.py agency treasury
python usaspending.py agency defense
python usaspending.py agency hhs
python usaspending.py agency treasury --json
python usaspending.py agency defense --json
python usaspending.py agency energy --export csv
```

### Spending Over Time

```bash
# Annual spending (current FY, default 5-year lookback)
python usaspending.py spending
python usaspending.py spending --fy 2025
python usaspending.py spending --fy 2025 --json

# Monthly spending cadence within a FY
python usaspending.py spending --fy 2025 --group-by month
python usaspending.py spending --fy 2026 --group-by month --json

# Filter by award type
python usaspending.py spending --fy 2025 --award-type contracts
python usaspending.py spending --fy 2025 --award-type grants --json
python usaspending.py spending --fy 2025 --award-type direct_payments --json
python usaspending.py spending --fy 2025 --award-type loans
python usaspending.py spending --fy 2025 --group-by month --award-type contracts --json

# Export
python usaspending.py spending --fy 2025 --export csv
python usaspending.py spending --fy 2025 --group-by month --export csv
```

### Top Agencies by Spending

```bash
# Top agencies in a FY (default top 10)
python usaspending.py by-agency
python usaspending.py by-agency --fy 2025
python usaspending.py by-agency --fy 2025 --json
python usaspending.py by-agency --fy 2025 --limit 20
python usaspending.py by-agency --fy 2025 --limit 20 --json

# Filter by award type
python usaspending.py by-agency --fy 2025 --award-type contracts --limit 15 --json
python usaspending.py by-agency --fy 2025 --award-type grants --limit 15 --json
python usaspending.py by-agency --fy 2025 --award-type direct_payments --json
python usaspending.py by-agency --fy 2025 --award-type loans --json

# Export
python usaspending.py by-agency --fy 2025 --limit 20 --export csv
```

### Geography

```bash
# Spending by state (default)
python usaspending.py by-geography
python usaspending.py by-geography --fy 2025
python usaspending.py by-geography --fy 2025 --json

# County or congressional district level
python usaspending.py by-geography --fy 2025 --geo-layer county
python usaspending.py by-geography --fy 2025 --geo-layer county --json
python usaspending.py by-geography --fy 2025 --geo-layer district
python usaspending.py by-geography --fy 2025 --geo-layer district --json

# Filter by award type
python usaspending.py by-geography --fy 2025 --award-type contracts --json
python usaspending.py by-geography --fy 2025 --award-type grants --json
python usaspending.py by-geography --fy 2025 --geo-layer county --award-type contracts --json

# Export
python usaspending.py by-geography --fy 2025 --export csv
python usaspending.py by-geography --fy 2025 --geo-layer county --export csv
```

### Fiscal Snapshot

```bash
# Flagship macro fiscal pulse (budget auth, YoY change, top agencies, group breakdown)
python usaspending.py fiscal-snapshot
python usaspending.py fiscal-snapshot --json
python usaspending.py fiscal-snapshot --fy 2024
python usaspending.py fiscal-snapshot --fy 2024 --json
python usaspending.py fiscal-snapshot --export json
```

### Awards

```bash
# Keyword award search (sorted by amount desc)
python usaspending.py awards "infrastructure"
python usaspending.py awards "infrastructure" --json
python usaspending.py awards "semiconductor" --fy 2024
python usaspending.py awards "semiconductor" --fy 2024 --award-type contracts --json
python usaspending.py awards "renewable energy" --award-type grants --json
python usaspending.py awards "artificial intelligence" --fy 2025 --json
python usaspending.py awards "defense" --fy 2025 --limit 50 --json

# All awards in a FY (no keyword filter)
python usaspending.py awards --fy 2025 --json
python usaspending.py awards --fy 2025 --award-type contracts --json

# Export
python usaspending.py awards "infrastructure" --export csv
```

### Budget

```bash
# Multi-year total budgetary resources (all FYs, all periods)
python usaspending.py budget
python usaspending.py budget --json
python usaspending.py budget --export csv
python usaspending.py budget --export json
```

### Overview

```bash
# Current FY status summary (budget auth, top 5 agencies, last updated)
python usaspending.py overview
python usaspending.py overview --json
python usaspending.py overview --fy 2024
python usaspending.py overview --fy 2024 --json
python usaspending.py overview --export json
```

### Search

```bash
# Free-text award search (wraps awards command)
python usaspending.py search "defense contract"
python usaspending.py search "defense contract" --json
python usaspending.py search "renewable energy" --award-type grants --json
python usaspending.py search "CHIPS" --fy 2025 --award-type contracts --json
python usaspending.py search "student loan" --award-type loans --json
python usaspending.py search "Medicaid" --fy 2025 --limit 50 --json
```

### Groups

```bash
# List all 17 curated agencies across 9 groups with aliases and codes
python usaspending.py groups
python usaspending.py groups --json
```

### Export

```bash
# Export any command's output to file
python usaspending.py export agencies --format csv
python usaspending.py export agencies --format json
python usaspending.py export spending --fy 2025 --format csv
python usaspending.py export by-agency --fy 2025 --format csv
python usaspending.py export by-geography --fy 2025 --format csv
python usaspending.py export budget --format csv
python usaspending.py export overview --fy 2025 --format json
python usaspending.py export fiscal-snapshot --fy 2025 --format json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to CSV file | All except groups |
| `--export json` | Export to JSON file | All except groups |
| `--fy N` | Fiscal year (default: current FY) | spending, by-agency, by-geography, fiscal-snapshot, awards, overview, search, export |
| `--limit N` | Number of results | by-agency, awards, search |
| `--group-by` | `fiscal_year` or `month` | spending |
| `--award-type` | `contracts`, `grants`, `direct_payments`, `loans`, `insurance`, `other`, `all` | spending, by-agency, by-geography, awards, search |
| `--geo-layer` | `state`, `county`, `district` | by-geography |
| `--format` | `csv` or `json` | export |


## Python Recipes

### Agencies

```python
from usaspending import cmd_agencies

# All top-tier agencies ranked by budget authority
# Returns: list of agency dicts with agency_name, abbreviation, toptier_code,
#          current_total_budget_authority_amount, active_fq, active_fy
agencies = cmd_agencies(as_json=True)
```

### Agency Detail

```python
from usaspending import cmd_agency

# By alias (matches AGENCY_REGISTRY keys)
# Returns: {"detail": {agency fields}, "budgetary_resources": {yearly breakdown}}
defense = cmd_agency(alias="defense", as_json=True)
treasury = cmd_agency(alias="treasury", as_json=True)
hhs = cmd_agency(alias="hhs", as_json=True)
energy = cmd_agency(alias="energy", as_json=True)

# By toptier code
agency = cmd_agency(toptier_code="097", as_json=True)
```

### Spending Over Time

```python
from usaspending import cmd_spending

# Annual spending (5-year lookback)
# Returns: {"results": [{time_period: {fiscal_year}, aggregated_amount, aggregated_outlay_amount}]}
annual = cmd_spending(fy=2025, group_by="fiscal_year", as_json=True)

# Monthly spending cadence
monthly = cmd_spending(fy=2025, group_by="month", as_json=True)

# Filtered by award type
# award_type: "contracts" | "grants" | "direct_payments" | "loans" | "insurance" | "other" | "all"
contracts = cmd_spending(fy=2025, group_by="fiscal_year", award_type="contracts", as_json=True)
grants_monthly = cmd_spending(fy=2025, group_by="month", award_type="grants", as_json=True)
```

### Top Agencies by Spending

```python
from usaspending import cmd_by_agency

# Top N agencies by spending in a FY
# Returns: {"results": [{name, amount, id}]}
top10 = cmd_by_agency(fy=2025, limit=10, as_json=True)
top20 = cmd_by_agency(fy=2025, limit=20, as_json=True)

# Filtered by award type
contract_agencies = cmd_by_agency(fy=2025, limit=15, award_type="contracts", as_json=True)
grant_agencies = cmd_by_agency(fy=2025, limit=15, award_type="grants", as_json=True)
```

### Geography

```python
from usaspending import cmd_by_geography

# By state (default)
# Returns: {"results": [{display_name, shape_code, aggregated_amount, per_capita, population}]}
states = cmd_by_geography(fy=2025, geo_layer="state", as_json=True)

# By county or congressional district
counties = cmd_by_geography(fy=2025, geo_layer="county", as_json=True)
districts = cmd_by_geography(fy=2025, geo_layer="district", as_json=True)

# Filtered by award type
contract_states = cmd_by_geography(fy=2025, geo_layer="state", award_type="contracts", as_json=True)
grant_states = cmd_by_geography(fy=2025, geo_layer="state", award_type="grants", as_json=True)
```

### Fiscal Snapshot

```python
from usaspending import cmd_fiscal_snapshot

# Flagship composite: budget auth, YoY change, top agencies, group breakdown
# Returns: {fy, last_updated, total_budget: {budget_authority, period},
#           yoy_change, prev_budget_authority, top_agencies: [...], group_totals: {...}}
snapshot = cmd_fiscal_snapshot(as_json=True)
snapshot_2024 = cmd_fiscal_snapshot(fy=2024, as_json=True)
```

### Awards & Search

```python
from usaspending import cmd_awards, cmd_search

# Keyword award search (sorted by amount desc)
# Returns: {"results": [{Award ID, Recipient Name, Award Amount, Awarding Agency,
#           Award Type, Description, Start Date, End Date}], "page_metadata": {total}}
infra = cmd_awards(keyword="infrastructure", fy=2025, as_json=True)
chips = cmd_awards(keyword="semiconductor", fy=2024, award_type="contracts", as_json=True)
ai = cmd_awards(keyword="artificial intelligence", fy=2025, limit=50, as_json=True)

# All awards (no keyword)
all_contracts = cmd_awards(fy=2025, award_type="contracts", as_json=True)

# Free-text search (wraps cmd_awards)
results = cmd_search(keyword="renewable energy", award_type="grants", as_json=True)
defense = cmd_search(keyword="defense contract", fy=2025, as_json=True)
```

### Budget

```python
from usaspending import cmd_budget

# Multi-year total budgetary resources
# Returns: {"results": [{fiscal_year, fiscal_period, total_budgetary_resources}]}
budget = cmd_budget(as_json=True)
```

### Overview

```python
from usaspending import cmd_overview

# Current FY status summary
# Returns: {fy, total_budget_authority, fiscal_period, top_5_agencies, last_updated}
overview = cmd_overview(as_json=True)
overview_2024 = cmd_overview(fy=2024, as_json=True)
```

### Groups

```python
from usaspending import cmd_groups

# All 9 groups with member agencies
# Returns: dict keyed by group -> {alias: {code, name, group}}
groups = cmd_groups(as_json=True)
```

### Constants

```python
from usaspending import (AGENCY_REGISTRY, GROUP_ORDER, GROUP_NAMES,
                         AWARD_TYPE_CODES, VALID_AWARD_TYPES, _current_fy)

# Iterate agencies by group
for alias, info in AGENCY_REGISTRY.items():
    if info["group"] == "defense":
        print(f"{alias}: {info['name']} ({info['code']})")

# Current fiscal year
fy = _current_fy()

# Award type code lookup
contract_codes = AWARD_TYPE_CODES["contracts"]  # ["A", "B", "C", "D"]
```


## Composite Recipes

### Fiscal Impulse Tracker

```bash
python usaspending.py fiscal-snapshot --json
python usaspending.py spending --fy 2026 --json
python usaspending.py spending --fy 2025 --json
python usaspending.py budget --json
```

PRISM receives: aggregate budget authority with YoY change (the fiscal impulse signal), top 10 agencies by award spending, group breakdown, current vs prior FY annual spending totals for side-by-side comparison, multi-year budget authority series for long-run fiscal trajectory.

### Spending Composition Analysis

```bash
python usaspending.py by-agency --fy 2026 --limit 20 --json
python usaspending.py agency defense --json
python usaspending.py agency hhs --json
python usaspending.py agency veterans --json
python usaspending.py by-agency --fy 2026 --award-type contracts --limit 15 --json
python usaspending.py by-agency --fy 2026 --award-type grants --limit 15 --json
python usaspending.py by-agency --fy 2026 --award-type direct_payments --limit 15 --json
```

PRISM receives: top 20 agencies ranked by spending, per-agency detail (budget authority, obligations, outlays, multi-year trend) for defense/HHS/VA, contract vs grant vs direct payment decomposition across agencies.

### Geographic Fiscal Flow

```bash
python usaspending.py by-geography --fy 2026 --json
python usaspending.py by-geography --fy 2026 --award-type contracts --json
python usaspending.py by-geography --fy 2026 --award-type grants --json
python usaspending.py by-geography --fy 2026 --geo-layer county --json
```

PRISM receives: state-level spending ranked by total, contract geography vs grant geography for divergence analysis, county-level granularity for concentration patterns.

### Policy Program Investigation

```bash
python usaspending.py awards "semiconductor" --fy 2025 --award-type contracts --json
python usaspending.py awards "infrastructure" --fy 2025 --json
python usaspending.py search "renewable energy" --award-type grants --json
python usaspending.py search "artificial intelligence" --fy 2025 --json
python usaspending.py agency energy --json
python usaspending.py agency commerce --json
```

PRISM receives: individual awards by keyword with recipient, amount, agency, description for CHIPS/IIJA/IRA tracking, DOE and Commerce agency totals as denominator context for program share calculation.

### Budget Cycle Monitor

```bash
python usaspending.py overview --json
python usaspending.py spending --fy 2026 --group-by month --json
python usaspending.py budget --json
python usaspending.py fiscal-snapshot --json
```

PRISM receives: FY status summary with budget authority and last-updated timestamp, monthly spending cadence for seasonality and CR detection, multi-year budget authority trend, full fiscal snapshot with YoY change.

### Defense Spending Deep Dive

```bash
python usaspending.py agency defense --json
python usaspending.py agency homeland --json
python usaspending.py by-agency --fy 2026 --award-type contracts --limit 10 --json
python usaspending.py awards "defense" --fy 2026 --award-type contracts --limit 25 --json
python usaspending.py by-geography --fy 2026 --award-type contracts --json
```

PRISM receives: DOD and DHS agency detail with budget authority/obligations/outlays, top 10 contract-spending agencies, individual defense contract awards with recipients and amounts, geographic distribution of contract dollars.

### Social Program Tracker

```bash
python usaspending.py agency hhs --json
python usaspending.py agency ssa --json
python usaspending.py agency veterans --json
python usaspending.py agency education --json
python usaspending.py by-agency --fy 2026 --award-type direct_payments --limit 10 --json
python usaspending.py by-geography --fy 2026 --award-type direct_payments --json
```

PRISM receives: HHS/SSA/VA/Education agency detail, top agencies by direct payment spending, geographic distribution of transfer payments.


## Cross-Source Recipes

### Fiscal Impulse + Treasury Cash Flow

```bash
python usaspending.py fiscal-snapshot --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: federal spending commitments (obligations) + actual Treasury cash flows. Commitment-to-disbursement lag analysis: obligation surge today implies outlay surge in 3-12 months.

### Federal Spending + Shutdown Probability

```bash
python usaspending.py overview --json
python usaspending.py spending --fy 2026 --group-by month --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: current FY budget status + monthly spending cadence + market-implied policy probabilities. High shutdown odds combined with flat monthly spending signals CR drag.

### Geographic Spending + Regional Electricity

```bash
python usaspending.py by-geography --fy 2026 --json
python usaspending.py by-geography --fy 2026 --award-type contracts --json
python projects/apis/electricity/electricity.py demand --json
```

PRISM receives: state-level federal spending + regional electricity demand. Cross-validates fiscal flow with real economic activity by region.

### Defense Spending + Trade Policy

```bash
python usaspending.py agency defense --json
python usaspending.py awards "defense" --fy 2026 --award-type contracts --json
python projects/apis/tariffs/tariffs.py snapshot --json
```

PRISM receives: defense agency budget + individual defense contracts + tariff regime snapshot. Defense procurement costs are directly affected by trade policy on imported materials and components.

### Fiscal Stance + BIS Cross-Country

```bash
python usaspending.py fiscal-snapshot --json
python usaspending.py budget --json
python projects/apis/bis/bis.py credit --json
```

PRISM receives: US fiscal impulse (YoY spending change) + multi-year budget trajectory + BIS cross-country credit data. Relative fiscal positioning for FX and rates analysis.

### Federal Lending + Bank Stress

```bash
python usaspending.py by-agency --fy 2026 --award-type loans --limit 10 --json
python usaspending.py awards "loan" --fy 2026 --award-type loans --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: top agencies by federal lending volume + individual loan awards + bank-level stress indicators. Federal lending activity vs private credit conditions.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python usaspending.py agencies`
4. Full test: `python usaspending.py fiscal-snapshot`


## Architecture

```
usaspending.py
  Constants       BASE_URL, AGENCY_REGISTRY (17), GROUP_ORDER (9), GROUP_NAMES,
                  AWARD_TYPE_CODES (7 categories), VALID_AWARD_TYPES
  Helpers         _current_fy(), _fy_dates(), _fmt_dollars(), _fmt_pct()
  HTTP            _get() and _post() with retries, rate limit handling
  Data Fetchers   _fetch_toptier_agencies, _fetch_agency_detail,
                  _fetch_budgetary_resources, _fetch_total_budgetary_resources,
                  _fetch_spending_over_time, _fetch_spending_over_time_range,
                  _fetch_spending_by_agency, _fetch_spending_by_geography,
                  _fetch_spending_by_award, _fetch_federal_spending,
                  _fetch_last_updated
  Commands (12)   agencies, agency, spending, by-agency, by-geography,
                  fiscal-snapshot, awards, budget, overview, search, groups, export
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        12 subcommands, all with --json and --export
```

API endpoints:
```
GET  references/toptier_agencies/                    -> all top-tier agencies
GET  agency/{toptier_code}/                          -> agency detail
GET  agency/{toptier_code}/budgetary_resources/      -> agency budget history
GET  references/total_budgetary_resources/           -> total federal budget
GET  awards/last_updated/                            -> data freshness
POST search/spending_over_time/                      -> spending time series
POST search/spending_by_category/awarding_agency/    -> spending by agency
POST search/spending_by_geography/                   -> spending by geography
POST search/spending_by_award/                       -> award-level search
POST spending/                                       -> federal spending summary
```
