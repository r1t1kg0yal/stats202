# Federal Register Regulatory Data

Script: `projects/apis/federal_register/federal_register.py`
Base URL: `https://www.federalregister.gov/api/v1`
Auth: None required
Rate limit: No formal limit; polite usage recommended
Dependencies: `requests`


## Triggers

Use for: executive order tracking (pace, direction, signing dates), proposed and final rule monitoring by agency, economically significant rules ($100M+ impact), full-text search across all FR document types, single document detail with CFR references and RIN tracking, **public inspection** documents (both `current` desk and by filing date), **faceted aggregations** (daily/weekly/monthly/quarterly/yearly time series, top agencies, top topics, type/subtype/section breakdowns) without iterating through every document, **suggested searches** (FR-curated topic packs for money, trade, sanctions, environment, tech, etc.), **37-agency registry** spanning financial/trade/sanctions/statistical/energy/antitrust/tech/housing/transport groups, regulatory pipeline snapshots (proposed-to-final flow, comment period deadlines).

Not for: legislative process (bills, votes, floor action — use Congress.gov), agency enforcement actions not published in FR, state-level regulations, agency press releases or informal guidance, real-time executive action announcements (FR publishes with 1-3 day lag), historical documents before 1994.


## Data Catalog

### Document Types

| Type | CLI key | API code | Description |
|------|---------|----------|-------------|
| Rule | rule | RULE | Final rules with force of law |
| Proposed Rule | proposed | PRORULE | Rules under consideration, open for comment |
| Notice | notice | NOTICE | Agency announcements, meetings, guidance |
| Presidential Document | presidential | PRESDOCU | Executive orders, proclamations, memoranda |

### Presidential Document Subtypes

| API value | Display |
|-----------|---------|
| `executive_order` | Executive Order |
| `memorandum` | Presidential Memorandum |
| `proclamation` | Proclamation |
| `determination` | Determination |
| `notice` | Presidential Notice |
| `other` | Other Presidential Document |

### Agency Registry (37 agencies, grouped)

#### Financial / Banking

| Alias | ID | Agency |
|-------|----|--------|
| treasury | 497 | Treasury Department |
| fed | 188 | Federal Reserve System |
| sec | 466 | Securities and Exchange Commission |
| cftc | 77 | Commodity Futures Trading Commission |
| fdic | 164 | Federal Deposit Insurance Corporation |
| occ | 80 | Comptroller of the Currency |
| fhfa | 174 | Federal Housing Finance Agency |
| ncua | 335 | National Credit Union Administration |
| fincen | 194 | Financial Crimes Enforcement Network |

#### Trade / Customs / Sanctions

| Alias | ID | Agency |
|-------|----|--------|
| ustr | 491 | Trade Representative, Office of United States |
| commerce | 54 | Commerce Department |
| cbp | 501 | U.S. Customs and Border Protection |
| ofac | 203 | Foreign Assets Control Office |
| ita | 261 | International Trade Administration |
| bis | 241 | Industry and Security Bureau (export controls) |
| usitc | 262 | International Trade Commission |

#### Economic / Statistical

| Alias | ID | Agency |
|-------|----|--------|
| bea | 118 | Economic Analysis Bureau (GDP / income / trade) |
| bls | 272 | Labor Statistics Bureau (CPI / payrolls / JOLTS) |
| census | 42 | Census Bureau |

#### Fiscal

| Alias | ID | Agency |
|-------|----|--------|
| irs | 254 | Internal Revenue Service |
| omb | 280 | Management and Budget Office |
| bfs | 196 | Bureau of the Fiscal Service (DTS / auctions) |

#### Energy / Climate

| Alias | ID | Agency |
|-------|----|--------|
| energy | 136 | Energy Department |
| ferc | 167 | Federal Energy Regulatory Commission |
| eia | 138 | Energy Information Administration |
| epa | 145 | Environmental Protection Agency |
| nrc | 383 | Nuclear Regulatory Commission |

#### Executive / Labor

| Alias | ID | Agency |
|-------|----|--------|
| president | 538 | Executive Office of the President |
| labor | 271 | Labor Department |

#### Foreign / Security

| Alias | ID | Agency |
|-------|----|--------|
| state | 476 | State Department |
| defense | 103 | Defense Department |
| dhs | 227 | Homeland Security Department |

#### Competition / Tech / Antitrust

| Alias | ID | Agency |
|-------|----|--------|
| ftc | 192 | Federal Trade Commission |
| doj | 268 | Justice Department |
| fcc | 161 | Federal Communications Commission |
| nist | 352 | National Institute of Standards and Technology |

#### Housing / Transport / Enforcement

| Alias | ID | Agency |
|-------|----|--------|
| hud | 228 | Housing and Urban Development Department |
| transport | 492 | Transportation Department |
| faa | 159 | Federal Aviation Administration |
| cfpb | 573 | Consumer Financial Protection Bureau |

### Agency Groups

| Group key | Aliases |
|-----------|---------|
| financial | treasury, fed, sec, cftc, fdic, occ, fhfa, ncua, cfpb |
| trade | ustr, commerce, cbp, ofac, ita, bis, usitc |
| fiscal | treasury, irs, omb, bfs |
| energy | energy, ferc, eia, epa, nrc |
| executive | president, omb |
| labor | labor, bls |
| statistical | bea, bls, census |
| sanctions | ofac, bis, state, commerce |
| antitrust | ftc, doj, fcc |
| housing | fhfa, hud |
| tech | ftc, fcc, nist, sec |
| foreign | state, defense, dhs, ustr |
| financial_crime | fincen, ofac, irs, doj |

### Document Fields (per result)

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Document title |
| `type` | string | Rule, Proposed Rule, Notice, Presidential Document |
| `subtype` | string | Executive Order, Proclamation, etc. |
| `abstract` | string | Summary/abstract text |
| `document_number` | string | Unique FR document number |
| `publication_date` | string | Date published in FR |
| `signing_date` | string | Date signed (presidential docs) |
| `effective_on` | string | Effective date for rules |
| `executive_order_number` | string | EO number (presidential docs) |
| `action` | string | Regulatory action description |
| `agencies` | list | Issuing agencies with name, id |
| `html_url` | string | URL to FR.gov page |
| `pdf_url` | string | URL to PDF |
| `significant` | bool | Economically significant ($100M+) |
| `regulation_id_numbers` | list | RIN tracking numbers |
| `cfr_references` | list | CFR title/part references |
| `topics` | list | Subject classifications |
| `comments_close_on` | string | Comment period deadline |
| `dates` | string | Date information string |

Single-document detail (`/documents/{num}.json`) adds `body_html_url`, `full_text_xml_url`, `raw_text_url`, `docket_ids`, `regulation_id_number_info`.

Public inspection adds `filed_at`, `num_pages`, `filing_type`.

### Facets

| Facet key | Returns | Use for |
|---|---|---|
| `daily` | `{YYYY-MM-DD: {count, name}}` | daily publication time series |
| `weekly` | `{YYYY-MM-DD: {count, name (week label)}}` | weekly rhythm |
| `monthly` | `{YYYY-MM-01: {count, name}}` | monthly trend |
| `quarterly` | `{YYYY-Qn: {count, name}}` | quarterly rollup |
| `yearly` | `{YYYY: {count, name}}` | yearly rollup |
| `agency` | `{slug: {count, name}}` | top-publishing agencies |
| `topic` | `{slug: {count, name}}` | top regulatory topics |
| `type` | `{code: {count, name}}` | RULE/NOTICE/PRORULE/PRESDOCU mix |
| `subtype` | `{subtype: {count, name}}` | EO vs proclamation vs memo counts |
| `section` | `{slug: {count, name}}` | business/science/env/health/money |

All facets accept the same filters as `/documents.json`: type, agency_ids, term, significant, publication_date[gte|lte], presidential_document_type.

### Suggested Search Sections

FR publishes curated topic packs indexed by section. Each pack has a `title`, `slug`, `description`, and `search_conditions` object ready to feed back into `/documents.json`.

| Section | Sample packs |
|---------|--------------|
| money | Dodd-Frank Wall Street Reform; Stock & Commodities Trading; Government Contracts; Economic Sanctions & Foreign Assets Control; Bank Secrecy & Financial Crime; Truth in Lending (Regulation Z); Quarterly Expatriation Publications; 13 more |
| world | Immigration & Border Control; International Trade (Anti-Dumping); Controlled Exports (CCL & USML); Denied Persons & Specially Designated Nationals; Arms Sales Notifications; NAFTA; ACE (Automated Commercial Environment); 6 more |
| environment | Endangered & Threatened Species; plus 14 more |
| science-and-technology | Broadband Policy; plus 9 more |
| business-and-industry | Automobile Safety & Fuel Economy; plus 12 more |
| health-and-public-welfare | Health Care Reform; plus 26 more |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` where noted.

### Latest Documents

```bash
python federal_register.py latest
python federal_register.py latest --count 50 --json
python federal_register.py latest --export csv
```

### Executive Orders

```bash
python federal_register.py executive-orders --days 90 --count 20 --json
python federal_register.py executive-orders --days 30 --json
python federal_register.py executive-orders --days 14 --json
python federal_register.py executive-orders --export csv
```

### Final & Proposed Rules

```bash
# Final rules by agency
python federal_register.py rules --agency treasury --days 90 --json
python federal_register.py rules --agency sec --days 180 --json
python federal_register.py rules --agency fed --json
python federal_register.py rules --agency cftc --json
python federal_register.py rules --agency ofac --days 30 --json
python federal_register.py rules --agency bis --days 30 --json         # export controls
python federal_register.py rules --agency ita --days 30 --json         # AD/CVD determinations
python federal_register.py rules --agency nrc --json
python federal_register.py rules --agency epa --json
python federal_register.py rules --agency cfpb --json

# Proposed rules
python federal_register.py proposed --agency fed --days 90 --json
python federal_register.py proposed --agency sec --days 180 --json
python federal_register.py proposed --agency treasury --days 90 --json
python federal_register.py proposed --agency fdic --json
python federal_register.py proposed --agency fincen --json
```

### Significant Rules

```bash
python federal_register.py significant --days 180 --json
python federal_register.py significant --days 60 --count 20 --json
python federal_register.py significant --days 365 --count 50 --json
```

### Full-Text Search

```bash
# Basic
python federal_register.py search "tariff" --json
python federal_register.py search "stablecoin" --json
python federal_register.py search "Section 232" --json
python federal_register.py search "IEEPA" --json

# Filter by type
python federal_register.py search "tariff" --type presidential --json
python federal_register.py search "tariff" --type rule --json

# Filter by agency
python federal_register.py search "sanctions" --agency ofac --json
python federal_register.py search "capital requirements" --agency fed --json
python federal_register.py search "export control" --agency bis --json

# Combined
python federal_register.py search "tariff" --type rule --agency commerce --json
```

### Suggested Topic Packs (FR-Curated Queries)

```bash
# All sections
python federal_register.py suggested --json

# Specific section
python federal_register.py suggested --section money --json
python federal_register.py suggested --section world --json
python federal_register.py suggested --section business-and-industry --json
```

Each pack includes a ready-to-use `search_conditions` object you can extract and feed into a follow-up `search` or `documents.json` call.

### Facets (Aggregation without document iteration)

```bash
# Time-series
python federal_register.py facet daily --days 30 --json
python federal_register.py facet weekly --days 180 --json
python federal_register.py facet monthly --days 365 --json
python federal_register.py facet quarterly --days 365 --json
python federal_register.py facet yearly --json

# Distribution
python federal_register.py facet agency --days 30 --head 20 --json
python federal_register.py facet topic --days 180 --head 30 --json
python federal_register.py facet type --days 30 --json
python federal_register.py facet subtype --days 90 --json
python federal_register.py facet section --days 30 --json

# Filtered facets
python federal_register.py facet monthly --type presidential --days 365 --json
python federal_register.py facet monthly --type rule --agency fed --days 365 --json
python federal_register.py facet monthly --term "tariff" --days 365 --json
python federal_register.py facet agency --significant --days 90 --json
python federal_register.py facet daily --type presidential \
    --presidential-type executive_order --days 30 --json
```

### EO Pace (Composite)

```bash
# Monthly EO + proclamation + memo counts
python federal_register.py eo-pace --days 365 --json
python federal_register.py eo-pace --days 90 --export csv
python federal_register.py eo-pace --days 730 --json    # 2yr history
```

### Single Document Detail

```bash
python federal_register.py document 2026-05635 --json
python federal_register.py document 2026-07143 --json
```

### Public Inspection (Pre-Publication)

```bash
# General upcoming filings
python federal_register.py public-inspection --count 20 --json

# Currently on the inspection desk (active right now)
python federal_register.py pi-current --json
python federal_register.py pi-current --export csv

# Filings for a specific date
python federal_register.py pi-by-date 2026-04-16 --json
python federal_register.py pi-by-date 2026-04-15 --export csv
```

### Multi-Agency Tracker

```bash
python federal_register.py tracker --groups financial,trade --days 30 --json
python federal_register.py tracker --groups financial --days 60 --json
python federal_register.py tracker --groups trade --days 30 --json
python federal_register.py tracker --groups fiscal --days 30 --json
python federal_register.py tracker --groups energy --days 30 --json
python federal_register.py tracker --groups executive --days 14 --json
python federal_register.py tracker --groups sanctions --days 30 --json
python federal_register.py tracker --groups statistical --days 30 --json
python federal_register.py tracker --groups antitrust --days 60 --json
python federal_register.py tracker --groups tech --days 60 --json
python federal_register.py tracker --groups financial_crime --days 30 --json
```

### Regulatory Pipeline

```bash
python federal_register.py pipeline --days 180 --json
python federal_register.py pipeline --days 90 --json
```

### Agency Reference

```bash
python federal_register.py agencies --json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output | All commands |
| `--export csv\|json` | Export to file | latest, executive-orders, rules, proposed, significant, search, public-inspection, pi-current, pi-by-date, tracker, pipeline, facet, eo-pace |
| `--count N` | Results per page | most commands |
| `--days N` | Lookback period | EO / rules / proposed (90) / significant (180) / tracker (30) / pipeline (180) / facet / eo-pace |
| `--agency ALIAS` | Agency filter | rules, proposed, search, facet |
| `--type TYPE` | Document type | search, facet |
| `--groups G1,G2` | Agency groups | tracker |
| `--significant` | Filter to $100M+ | facet |
| `--term TEXT` | Keyword filter | facet |
| `--date-gte / --date-lte` | Explicit date window | facet |
| `--head N` | Top-N for non-time facets | facet |
| `--section SECTION` | money/world/env/etc. | suggested |
| `--presidential-type TYPE` | executive_order, memorandum, etc. | facet |


## Python Recipes

```python
from federal_register import (
    cmd_latest, cmd_executive_orders, cmd_rules, cmd_proposed,
    cmd_significant, cmd_search, cmd_document,
    cmd_public_inspection, cmd_pi_current, cmd_pi_by_date,
    cmd_tracker, cmd_pipeline, cmd_agencies,
    cmd_facets, cmd_eo_pace, cmd_suggested,
)

# Facets (one-call aggregations)
agency_top = cmd_facets(facet_key="agency", days=30, head=20, as_json=True)
time_series = cmd_facets(facet_key="monthly", days=365, as_json=True)
eo_monthly = cmd_facets(facet_key="monthly", doc_type="presidential",
                        presidential_type="executive_order",
                        days=365, as_json=True)
sig_by_agency = cmd_facets(facet_key="agency", significant_only=True,
                           days=90, head=25, as_json=True)
tariff_by_month = cmd_facets(facet_key="monthly", term="tariff",
                             days=365, as_json=True)

# Composite EO pace
pace = cmd_eo_pace(days=365, as_json=True)

# FR-curated topic packs
packs = cmd_suggested(section="money", as_json=True)
world_packs = cmd_suggested(section="world", as_json=True)

# Public inspection
current = cmd_pi_current(as_json=True)
by_date = cmd_pi_by_date("2026-04-16", as_json=True)
```


## Composite Recipes

### Policy Landscape Scan (Fast Daily)

```bash
python federal_register.py facet agency --days 7 --head 10 --json
python federal_register.py facet type --days 7 --json
python federal_register.py executive-orders --days 14 --json
python federal_register.py pi-current --json
```

PRISM receives: top 10 publishing agencies last week + doc type distribution + recent EOs + what's on the desk today.

### Regulatory Pace Over Time

```bash
python federal_register.py eo-pace --days 730 --json
python federal_register.py facet monthly --type rule --days 730 --json
python federal_register.py facet monthly --significant --days 730 --json
python federal_register.py facet monthly --agency ofac --days 730 --json
```

PRISM receives: 2-year monthly time series for presidential actions, final rules, significant actions, and OFAC sanctions output.

### Trade Policy Deep Dive

```bash
python federal_register.py search "tariff" --type presidential --json
python federal_register.py tracker --groups trade --days 30 --json
python federal_register.py rules --agency bis --days 60 --json
python federal_register.py rules --agency ita --days 60 --json
python federal_register.py search "Section 232" --json
python federal_register.py suggested --section world --json
```

PRISM receives: tariff-related presidential documents, USTR/Commerce/CBP/OFAC/ITA/BIS/USITC activity, BIS export control rules, ITA AD/CVD determinations, Section 232 implementation, curated world section packs.

### Financial Regulation Monitor

```bash
python federal_register.py tracker --groups financial --days 60 --json
python federal_register.py proposed --agency fed --days 180 --json
python federal_register.py proposed --agency sec --days 180 --json
python federal_register.py proposed --agency fincen --days 180 --json
python federal_register.py pipeline --days 180 --json
python federal_register.py suggested --section money --json
python federal_register.py facet agency --days 30 --head 15 --json
```

PRISM receives: financial regulator activity (9 agencies including NCUA and CFPB), Fed/SEC/FinCEN proposed rules, pipeline snapshot, curated money topic packs, most-active agencies overall.

### Sanctions Activity Check

```bash
python federal_register.py rules --agency ofac --days 30 --json
python federal_register.py rules --agency bis --days 30 --json
python federal_register.py rules --agency state --days 30 --json
python federal_register.py search "sanctions" --type notice --json
python federal_register.py search "SDN" --json
python federal_register.py tracker --groups sanctions --days 30 --json
```

PRISM receives: OFAC final rules (designations, license actions), BIS export control actions, State Dept sanctions notices, SDN list updates, cross-agency sanctions activity aggregated.

### Pre-Publication Intelligence

```bash
python federal_register.py pi-current --json
python federal_register.py public-inspection --count 30 --json
python federal_register.py pi-by-date 2026-04-15 --json
python federal_register.py significant --days 14 --count 20 --json
python federal_register.py tracker --groups financial,trade,executive --days 14 --json
```

PRISM receives: what's on the desk right now (highest lead time), upcoming filings window, a specific filing date's filings, recent significant actions, short-window tracker context.

### Single Topic Investigation

```bash
python federal_register.py search "stablecoin" --json
python federal_register.py search "stablecoin" --type rule --json
python federal_register.py search "stablecoin" --type proposed --json
python federal_register.py facet monthly --term "stablecoin" --days 730 --json
python federal_register.py suggested --section money --json
```

PRISM receives: all stablecoin docs, final-only, proposed-only, 2yr monthly trend, curated Dodd-Frank / Truth-in-Lending adjacent packs.


## Cross-Source Recipes

### Regulatory Implementation + Legislative Intent

```bash
python federal_register.py tracker --groups financial --days 30 --json
python projects/apis/congress/congress.py tracker --topics financial_reg,fed --json
```

PRISM receives: what financial regulators are publishing + what bills Congress is passing that direct them.

### Trade Policy Architecture

```bash
python federal_register.py search "tariff" --type presidential --json
python federal_register.py rules --agency bis --days 60 --json
python projects/apis/tariffs/tariffs.py chapter99 --json
python projects/apis/tariffs/tariffs.py overlay 7206.10 --json
```

PRISM receives: executive trade actions + BIS export control rules + Chapter 99 policy regime registry + effective stacked duty for a sample code.

### EO Pace + Market Probability

```bash
python federal_register.py eo-pace --days 180 --json
python federal_register.py pi-current --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset executive --json
```

PRISM receives: presidential action tempo, immediate pipeline (what's on inspection desk), and market-implied probabilities.

### Sanctions + Cross-Border Flows

```bash
python federal_register.py rules --agency ofac --days 30 --json
python federal_register.py tracker --groups sanctions --days 30 --json
python projects/apis/bis/bis.py lbs --json
```

PRISM receives: OFAC/BIS/State sanctions activity + BIS (BIS.org) locational banking for flow impact.

### Regulatory Pipeline + Corporate Response

```bash
python federal_register.py proposed --agency sec --days 180 --json
python projects/apis/sec_edgar/sec_edgar.py recent --form-type 8-K --json
```

PRISM receives: SEC proposed rules + corporate 8-Ks that may respond.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python federal_register.py latest --count 5`
4. Full test: `python federal_register.py tracker --groups financial,trade --days 14 --json`
5. Aggregation test: `python federal_register.py facet monthly --days 365 --json`


## Architecture

```
federal_register.py
  Constants       BASE_URL, DOC_TYPES (4), PRESIDENTIAL_SUBTYPES (6),
                  AGENCY_REGISTRY (37 agencies), AGENCY_GROUPS (13 groups),
                  STANDARD_FIELDS (20 fields), FACET_KEYS (10),
                  SUGGEST_SECTIONS (6)
  HTTP            _request() with retries, rate limit handling
                  _fetch_documents() core fetcher w/ manual URL for repeated params
                  _fetch_public_inspection(), _fetch_public_inspection_current(),
                  _fetch_public_inspection_by_date(), _fetch_document(),
                  _fetch_agencies(), _fetch_facet(), _fetch_suggested_searches()
  Commands (17)   latest, executive-orders, rules, proposed, significant,
                  search, document, public-inspection, tracker, pipeline,
                  agencies, facet, eo-pace, suggested, pi-current, pi-by-date
  Interactive     16-item menu -> interactive wrappers with prompts
  Argparse        17 subcommands, all with --json and --export where applicable
```

API endpoints used:

```
/documents.json?...                    -> filtered document search
/documents/{doc_number}.json           -> single document detail
/documents/facets/{daily|weekly|monthly|quarterly|yearly}.json
                                       -> time-series aggregation
/documents/facets/{agency|topic|type|subtype|section}.json
                                       -> distribution aggregation
/public-inspection-documents.json      -> upcoming filings
/public-inspection-documents/current.json   -> currently on desk
/public-inspection-documents/{YYYY-MM-DD}.json  -> filings on a date
/suggested_searches.json               -> curated topic packs
/suggested_searches.json?conditions[sections][]=SECTION
                                       -> packs for specific section
/agencies.json                         -> full agency list (~470)
```
