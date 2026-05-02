# Congress.gov Legislative Data

Script: `projects/apis/congress/congress.py`
Base URL: `https://api.congress.gov/v3`
Auth: API key required (free, from api.congress.gov/sign-up). Set `CONGRESS_API_KEY` env var. `DEMO_KEY` works for testing.
Rate limit: 5,000 requests per hour
Dependencies: `requests`


## Triggers

Use for: tracking bills through the legislative pipeline (introduced through enacted), **House roll call votes with per-member vote breakdown**, **CRS (Congressional Research Service) reports** for nonpartisan policy analysis, debt ceiling and fiscal deadline monitoring, tariff/sanctions/financial regulation bill status, cosponsor analysis for passage probability, presidential nomination tracking (Fed governors, agency heads) with full action + hearing pipeline, macro topic scanning across 10 curated legislative topics, committee action timelines, committee reports (markup documents) and hearings, **treaties** (trade agreements, alliances), **enacted public / private laws** feed, **per-member sponsored and cosponsored legislation** portfolios, related bill cross-references (companion bills, alternate vehicles), keyword search across bill titles.

Not for: executive actions and rule-making (use Federal Register), state-level legislation, real-time floor proceedings (Congressional Record has 1-2 day lag), vote prediction or whip counts from external sources (use the roll-call data here), lobbying data (opensecrets.org), campaign finance (FEC API), full bill text analysis (API returns URL pointers; fetch separately).


## Data Catalog

### Bill Types

| Type | Label | What It Is |
|------|-------|------------|
| hr | House Bill | Standard House legislation |
| s | Senate Bill | Standard Senate legislation |
| hjres | House Joint Resolution | Constitutional amendments, CRs |
| sjres | Senate Joint Resolution | Constitutional amendments, CRs |
| hconres | House Concurrent Resolution | Budget resolutions |
| sconres | Senate Concurrent Resolution | Budget resolutions |
| hres | House Resolution | House-only rules, procedures |
| sres | Senate Resolution | Senate-only rules, procedures |

### Law Types

| Type | Label |
|------|-------|
| pub  | Public Law (force of law, general applicability) |
| priv | Private Law (individual-specific) |

### Curated Macro Topics

| Topic Key | Label | Search Terms |
|-----------|-------|-------------|
| debt_ceiling | Debt Ceiling / Fiscal | debt limit, debt ceiling, borrowing authority, extraordinary measures |
| tax | Tax Policy | tax reform, tax cut, tax increase, TCJA, income tax, capital gains tax |
| tariff | Trade & Tariffs | tariff, trade agreement, customs duty, import tax, trade deficit |
| sanctions | Sanctions & Foreign Policy | sanctions, OFAC, CAATSA, IEEPA, export control |
| financial_reg | Financial Regulation | Dodd-Frank, bank regulation, financial stability, systemic risk, capital requirements |
| fed | Federal Reserve | Federal Reserve, monetary policy, interest rate, FOMC |
| appropriations | Appropriations / Spending | appropriations, continuing resolution, government shutdown, omnibus, spending bill |
| energy | Energy Policy | energy policy, oil drilling, renewable energy, LNG export, strategic petroleum |
| housing | Housing & Mortgage | housing, mortgage, Fannie Mae, Freddie Mac, FHFA, affordable housing |
| crypto | Digital Assets | cryptocurrency, digital asset, stablecoin, blockchain, CBDC |

### Bill Detail Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Official bill title |
| `type` | string | HR, S, HJRES, SJRES, etc. |
| `number` | string | Bill number |
| `congress` | int | Congress number (e.g. 119) |
| `introducedDate` | string | Date introduced |
| `originChamber` | string | House or Senate |
| `policyArea` | object | Policy area classification |
| `sponsors` | list | Sponsor(s) with fullName, party, state |
| `cosponsors` | object | Cosponsor count |
| `latestAction` | object | {actionDate, text} for most recent action |
| `laws` | list | Public law number if enacted |
| `cboCostEstimates` | list | CBO cost estimates with URLs |
| `url` | string | API URL for bill |

### Bill Sub-Endpoint Fields

Each bill has these callable sub-endpoints:

| Sub-endpoint | Returns | Key Fields |
|---|---|---|
| `/actions` | Action timeline | actionDate, type, text, actionCode |
| `/cosponsors` | Cosponsor list | fullName, party, state, sponsorshipDate |
| `/subjects` | Policy subjects | policyArea.name, legislativeSubjects[].name |
| `/summaries` | CRS summaries | versionCode, updateDate, text (HTML) |
| `/text` | Text version list | type, date, formats[].url (PDF/XML/HTML) |
| `/titles` | All title aliases | title, titleType, chamberName, titleTypeCode |
| `/relatedbills` | Companion / alternate vehicles | congress, type, number, relationshipDetails[].type |
| `/amendments` | Amendments filed to bill | type, number, purpose, latestAction |
| `/committees` | Committees that handled bill | name, chamber, systemCode, activities[].{date, name} |

### House Roll Call Vote Fields

| Field | Type | Description |
|-------|------|-------------|
| `congress` | int | Congress number |
| `sessionNumber` | int | Session (1 or 2) |
| `rollCallNumber` | int | Roll call number |
| `startDate` | string | Vote start timestamp |
| `result` | string | Passed / Failed / Agreed to / Rejected |
| `voteType` | string | Yea-And-Nay / Recorded Vote / 2/3 Yea-And-Nay |
| `legislationType` | string | HR / S / HJRES / SJRES / etc. |
| `legislationNumber` | string | Bill number voted on |
| `legislationUrl` | string | Link to bill |
| `sourceDataURL` | string | Clerk.house.gov raw XML |
| `url` | string | API URL for this vote |

Per-member drill-down (`/house-vote/{c}/{s}/{n}/members`) returns: `bioguideID`, `firstName`, `lastName`, `voteParty`, `voteState`, `voteCast` (Yea / Nay / Present / Not Voting).

### CRS Report Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | CRS report ID (e.g. R48910, IF11926) |
| `contentType` | string | Reports / Resources (depth indicator) |
| `title` | string | Report title |
| `publishDate` | string | First publication date |
| `updateDate` | string | Last revision date |
| `status` | string | Active / Archived |
| `version` | int | Revision version number |
| `summary` | string | Executive summary HTML (full-detail endpoint) |
| `authors` | list | Author names (full-detail endpoint) |
| `topics` | list | CRS topic classification (full-detail endpoint) |
| `formats` | list | URLs for PDF / HTML / etc. (full-detail endpoint) |
| `url` | string | API URL |

### Treaty Fields

| Field | Type | Description |
|-------|------|-------------|
| `number` | int | Treaty number |
| `suffix` | string | Part suffix (blank for primary) |
| `topic` | string | Subject / agreement type |
| `transmittedDate` | string | Date sent to Senate |
| `congressReceived` | int | Congress that received it |
| `congressConsidered` | int | Congress that took action |
| `actions` | list | Senate committee + floor actions |
| `parts` | object | Treaty components |
| `url` | string | API URL |

### Committee Report / Hearing Fields

Committee reports (`H. Rept.`, `S. Rept.`, `E. Rept.` conference reports):
- `citation`, `chamber`, `congress`, `type`, `number`, `part`, `updateDate`, `title`, `url`

Hearings (committee testimony, witnesses, transcripts):
- `jacketNumber`, `chamber`, `congress`, `number`, `title`, `committees[]`, `dates[]`, `citation`, `url`

### Nomination Fields

| Field | Type | Description |
|-------|------|-------------|
| `number` | string | Nomination number (PN###) |
| `description` | string | Nominee and position |
| `organization` | string | Agency / department |
| `receivedDate` | string | Date received by Senate |
| `latestAction` | object | {actionDate, text} |
| `nominees` | list | Individual nominees (if multi-person nom) |
| `committees` | object | Committees reviewing (count + URL) |
| `actions` | object | Action count + URL |
| `hearings` | object | Hearing count + URL |
| `url` | string | API URL |

Nomination has drill-down sub-endpoints: `/actions`, `/hearings`, `/committees`.

### Member Fields

Basic list (`/member/congress/{c}[/{state}]`): `name`, `bioguideId`, `partyName`, `state`, `terms.item[]`.

Member detail (`/member/{bioguideId}`): adds `directOrderName`, `birthYear`, `leadership[]` (roles held), `sponsoredLegislation.count`, `cosponsoredLegislation.count`, `addressInformation.officeAddress`, and full term history.

Member portfolio endpoints:
- `/member/{bio}/sponsored-legislation` — all bills authored
- `/member/{bio}/cosponsored-legislation` — all bills signed on as cosponsor


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` where noted.

### Latest Bills

```bash
python congress.py latest
python congress.py latest --congress 119 --count 20 --json
python congress.py latest --congress 118 --count 20 --json
python congress.py latest --type hr --json
python congress.py latest --type s --json
python congress.py latest --type hjres --congress 119 --json
python congress.py latest --export csv
```

### Bill Detail & Sub-Endpoints

```bash
# Core bill detail
python congress.py bill 119 hr 1 --json

# Action timeline
python congress.py actions 119 hr 1 --json
python congress.py actions 119 hr 1 --count 100 --export csv

# Cosponsors, summaries
python congress.py cosponsors 119 hr 1 --json
python congress.py summaries 119 hr 1 --json

# Related bills (House/Senate companions, alternate vehicles)
python congress.py related 119 hr 1 --json
python congress.py related 119 s 25 --export csv

# Amendments filed to this bill
python congress.py bill-amendments 119 hr 1 --json

# Committees that considered this bill
python congress.py bill-committees 119 hr 1 --json

# All titles (official + short + popular)
python congress.py titles 119 hr 1 --json
```

### Enacted Laws

```bash
# All enacted laws this Congress
python congress.py laws --congress 119 --json
python congress.py laws --congress 119 --count 50 --export csv

# Filter by law type
python congress.py laws --congress 119 --law-type pub --json
python congress.py laws --congress 119 --law-type priv --json

# Specific law detail
python congress.py law 119 pub 82 --json
python congress.py law 118 pub 5 --json
```

### House Roll Call Votes

```bash
# Latest votes
python congress.py votes --congress 119 --count 20 --json

# Filter by session (1 = 2025, 2 = 2026 in 119th)
python congress.py votes --congress 119 --session 1 --json
python congress.py votes --congress 119 --session 2 --export csv

# Single vote detail
python congress.py vote 119 1 240 --json

# Per-member vote breakdown (yea/nay/present/not voting by party)
python congress.py vote-members 119 1 240 --json
python congress.py vote-members 119 1 240 --export csv
```

### CRS Reports (Policy Research)

```bash
# Latest CRS reports (across all topics)
python congress.py crs --count 20 --json
python congress.py crs --count 50 --export csv

# Single CRS report (full summary, authors, topics, formats)
python congress.py crs-report R48910 --json
python congress.py crs-report IF11926 --json
```

### Committee Reports & Hearings

```bash
# Committee markup reports (H. Rept. / S. Rept. / conference reports)
python congress.py committee-reports --congress 119 --json
python congress.py committee-reports --congress 119 --report-type hrpt --json
python congress.py committee-reports --congress 119 --report-type srpt --export csv

# Hearings
python congress.py hearings --congress 119 --json
python congress.py hearings --congress 119 --chamber house --json
python congress.py hearings --congress 119 --chamber senate --json

# Single hearing detail (witnesses, dates, committees)
python congress.py hearing 119 house 63346 --json
```

### Nominations

```bash
# Nomination list
python congress.py nominations --congress 119 --count 30 --json

# Full nomination pipeline (detail + actions + hearings + committees)
python congress.py nomination 119 123 --json
```

### Treaties

```bash
# Treaties submitted to Senate for ratification
python congress.py treaties --congress 119 --json

# Treaty detail
python congress.py treaty 119 1 --json
python congress.py treaty 119 1 --suffix A --json
```

### Members

```bash
# Member list (by state or all)
python congress.py members --congress 119 --json
python congress.py members --state NY --json
python congress.py members --state CA --json

# Member detail (by bioguide ID)
python congress.py member W000817 --json        # Warren
python congress.py member H001073 --json        # Hagerty

# Member's sponsored legislation portfolio
python congress.py sponsored W000817 --count 50 --json
python congress.py sponsored H001073 --export csv

# Member's cosponsored legislation
python congress.py cosponsored W000817 --count 50 --json
```

### Search & Macro Topic Tracker

```bash
# Keyword search across bill titles
python congress.py search "tariff" --congress 119 --json
python congress.py search "debt ceiling" --congress 119 --count 20 --json
python congress.py search "IEEPA" --congress 119 --count 15 --json
python congress.py search "stablecoin" --congress 119 --json

# Macro topic tracker (10 topics, cross-chamber)
python congress.py tracker --json
python congress.py tracker --topics debt_ceiling,tariff,sanctions --json
python congress.py tracker --topics financial_reg,fed,crypto --json
python congress.py tracker --topics appropriations --export csv
```

### Reference

```bash
python congress.py topics            # list all curated macro topics
python congress.py amendments --congress 119 --count 20 --json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv\|json` | Export to CSV/JSON file | latest, actions, search, tracker, nominations, amendments, members, crs, votes, laws, related, bill-amendments, sponsored, cosponsored, treaties, committee-reports, hearings, vote-members |
| `--count N` | Results per page | latest, actions, search, nominations, amendments, members, crs, votes, laws, sponsored, cosponsored, committee-reports, hearings, treaties |
| `--congress N` | Congress number (default 119) | most commands |
| `--type TYPE` | Bill type filter | latest |
| `--topics T1,T2` | Comma-separated topic keys | tracker |
| `--state XX` | State code | members |
| `--session N` | Session (1/2) | votes |
| `--law-type TYPE` | pub/priv | laws |
| `--chamber CH` | house/senate/nochamber | hearings |
| `--report-type TYPE` | hrpt/srpt/erpt | committee-reports |


## Python Recipes

### Extended Commands

```python
from congress import (
    cmd_crs, cmd_crs_report,
    cmd_votes, cmd_vote, cmd_vote_members,
    cmd_laws, cmd_law,
    cmd_related, cmd_bill_amendments, cmd_bill_committees, cmd_titles,
    cmd_member, cmd_sponsored, cmd_cosponsored,
    cmd_treaties, cmd_treaty,
    cmd_committee_reports, cmd_hearings, cmd_hearing,
    cmd_nomination, cmd_nomination_pipeline,
)

# CRS research feed
reports = cmd_crs(limit=20, as_json=True)
report = cmd_crs_report("R48910", as_json=True)

# Votes
votes = cmd_votes(congress=119, limit=20, as_json=True)
vote = cmd_vote(119, 1, 240, as_json=True)
members = cmd_vote_members(119, 1, 240, as_json=True)

# Laws
laws = cmd_laws(congress=119, law_type="pub", limit=50, as_json=True)
law = cmd_law(119, "pub", "82", as_json=True)

# Bill sub-endpoints
related = cmd_related(119, "hr", "1", as_json=True)
amendments = cmd_bill_amendments(119, "hr", "1", as_json=True)
committees = cmd_bill_committees(119, "hr", "1", as_json=True)
titles = cmd_titles(119, "hr", "1", as_json=True)

# Member deep dive
member = cmd_member("W000817", as_json=True)
sponsored = cmd_sponsored("W000817", limit=50, as_json=True)
cosponsored = cmd_cosponsored("W000817", limit=50, as_json=True)

# Treaties & hearings
treaties = cmd_treaties(congress=119, as_json=True)
treaty = cmd_treaty(119, 1, as_json=True)
reports = cmd_committee_reports(congress=119, report_type="hrpt", as_json=True)
hearings = cmd_hearings(congress=119, chamber="house", as_json=True)

# Full nomination pipeline
pipeline = cmd_nomination_pipeline(119, "123", as_json=True)
```


## Composite Recipes

### Legislative Landscape Scan (Fast Daily Summary)

```bash
python congress.py tracker --topics debt_ceiling,tariff,sanctions,financial_reg,fed,crypto --json
python congress.py latest --congress 119 --count 20 --json
python congress.py laws --congress 119 --count 10 --json
python congress.py crs --count 10 --json
```

PRISM receives: per-topic bill counts + recent activity for 6 macro topics; 20 most recent bill actions across all types; 10 most recent enacted laws; 10 most recent CRS policy reports.

### Whip Count Reality Check

```bash
python congress.py votes --congress 119 --session 1 --count 30 --json
python congress.py vote 119 1 240 --json
python congress.py vote-members 119 1 240 --export csv
python congress.py search "debt ceiling" --congress 119 --json
```

PRISM receives: recent House roll calls with pass/fail results, detailed tally for a specific vote, per-member party-split breakdown, bills matching topic for context.

### Bill Deep Dive (Full Context)

```bash
python congress.py bill 119 hr 1 --json
python congress.py actions 119 hr 1 --json
python congress.py cosponsors 119 hr 1 --json
python congress.py summaries 119 hr 1 --json
python congress.py related 119 hr 1 --json
python congress.py bill-amendments 119 hr 1 --json
python congress.py bill-committees 119 hr 1 --json
python congress.py titles 119 hr 1 --json
```

PRISM receives: comprehensive bill state — sponsor, policy area, action timeline, cosponsor bipartisan analysis, CRS summary, House/Senate companion bills, filed amendments, committee activity, all title aliases.

### Policy Research Pack (Macro Topic)

```bash
python congress.py search "stablecoin" --congress 119 --json
python congress.py crs --count 30 --json
python congress.py crs-report R48910 --json
python congress.py committee-reports --congress 119 --json
```

PRISM receives: bills mentioning the topic, recent CRS reports (scan titles for relevance), selected CRS report full text, committee markup reports.

### Nomination Pipeline Review

```bash
python congress.py nominations --congress 119 --count 50 --json
python congress.py nomination 119 123 --json
python congress.py latest --type sjres --congress 119 --json
```

PRISM receives: full nomination list with status, single-nom drill-down (detail + actions + hearings + committees), Senate joint resolutions.

### Member Power-Mapping

```bash
python congress.py member W000817 --json                       # Warren bio
python congress.py sponsored W000817 --count 50 --json          # her bills
python congress.py cosponsored W000817 --count 50 --json        # her signals
python congress.py member H001073 --json                       # Hagerty bio
python congress.py sponsored H001073 --count 50 --json
```

PRISM receives: member bios with leadership roles, what key lawmakers are actively writing, what they're signaling support for.

### Trade Policy Architecture (Legislative Side)

```bash
python congress.py tracker --topics tariff,sanctions --json
python congress.py treaties --congress 119 --json
python congress.py search "IEEPA" --congress 119 --json
python congress.py search "Section 301" --congress 119 --json
python congress.py search "USMCA" --congress 119 --json
python congress.py committee-reports --congress 119 --report-type hrpt --json
```

PRISM receives: tariff and sanctions bills in flight, treaties under Senate consideration, IEEPA authority bills, Section 301 framework bills, USMCA modifications, committee reports for framework analysis.


## Cross-Source Recipes

### Legislative Intent + Regulatory Implementation

```bash
python congress.py tracker --topics financial_reg,fed --json
python projects/apis/federal_register/federal_register.py tracker --groups financial --days 30 --json
```

PRISM receives: bills directing financial regulators + what those regulators are actually publishing.

### Votes + Market Probability

```bash
python congress.py votes --congress 119 --session 1 --count 30 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fiscal --json
```

PRISM receives: recent roll call votes with results + market-implied probabilities.

### Debt Ceiling + Treasury Cash

```bash
python congress.py tracker --topics debt_ceiling,appropriations --json
python congress.py laws --congress 119 --count 20 --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: legislative vehicles, enacted laws feed for tracking CRs that became law, Treasury daily cash balance.

### Trade Legislation + Tariff Rates

```bash
python congress.py tracker --topics tariff --json
python congress.py treaties --congress 119 --json
python projects/apis/tariffs/tariffs.py chapter99 --json
python projects/apis/tariffs/tariffs.py tariff-actions --json
```

PRISM receives: tariff authority bills in the pipeline, pending trade treaties, Chapter 99 policy regime registry, statutory tariff action registry.

### Fed Pipeline + Nominations + FOMC

```bash
python congress.py nominations --congress 119 --count 30 --json
python congress.py nomination 119 ## --json                     # fill ## with target PN
python projects/apis/nyfed/nyfed.py rates --json
```

PRISM receives: Fed governor and agency head nomination pipeline with full action/hearing timeline + current overnight rate complex.

### Policy Research + Media Narrative

```bash
python congress.py crs --count 30 --json
python projects/apis/gdelt/gdelt.py search "debt ceiling Congress" --json
```

PRISM receives: authoritative CRS policy analysis + media volume and sentiment on same topics for narrative-vs-analysis comparison.


## Setup

1. Get a free API key: https://api.congress.gov/sign-up/
2. Set environment variable: `export CONGRESS_API_KEY=your_key_here`
3. Or use `DEMO_KEY` for testing (lower rate limits, sufficient for ~50 requests)
4. Test: `python congress.py latest --count 5`
5. Full test: `python congress.py tracker --topics debt_ceiling --json`


## Architecture

```
congress.py
  Constants       BASE_URL, API_KEY, CURRENT_CONGRESS (119),
                  BILL_TYPES (8), LAW_TYPES (2),
                  MACRO_TOPICS (10 topics with search term lists)
  HTTP            _request() with API key injection, retries, rate limit handling
                  _paginate() for multi-page fetches up to max_items
  Data Fetchers   _fetch_bills, _fetch_bill_detail, _fetch_bill_actions,
                  _fetch_bill_cosponsors, _fetch_bill_subjects,
                  _fetch_bill_summaries, _fetch_bill_text,
                  _fetch_bill_related, _fetch_bill_amendments,
                  _fetch_bill_committees, _fetch_bill_titles,
                  _fetch_members, _fetch_member_detail,
                  _fetch_member_sponsored, _fetch_member_cosponsored,
                  _fetch_nominations, _fetch_nomination_detail,
                  _fetch_nomination_actions, _fetch_nomination_hearings,
                  _fetch_nomination_committees,
                  _fetch_amendments,
                  _fetch_crs_reports, _fetch_crs_report,
                  _fetch_house_votes, _fetch_house_vote,
                  _fetch_house_vote_members,
                  _fetch_laws, _fetch_law_detail,
                  _fetch_treaties, _fetch_treaty_detail,
                  _fetch_treaty_actions,
                  _fetch_committee_reports, _fetch_hearings,
                  _fetch_hearing_detail,
                  _fetch_summaries_feed
  Commands (30+)  Core: latest, bill, actions, cosponsors, summaries,
                        search, tracker, nominations, amendments, members,
                        topics
                  Bill sub: related, bill-amendments, bill-committees, titles
                  Votes:    votes, vote, vote-members
                  Laws:     laws, law
                  Research: crs, crs-report, committee-reports,
                            hearings, hearing
                  Members:  member, sponsored, cosponsored
                  Treaties: treaties, treaty
                  Nom pipe: nomination (aggregates detail+actions+hearings)
  Interactive     29-item menu -> interactive wrappers with prompts
  Argparse        30+ subcommands, all with --json and --export where applicable
```

API endpoints used:

```
/bill                                           -> list bills
/bill/{congress}                                -> bills for a congress
/bill/{congress}/{type}                         -> bills by type
/bill/{congress}/{type}/{number}                -> bill detail
/bill/{congress}/{type}/{number}/actions        -> bill actions
/bill/{congress}/{type}/{number}/cosponsors     -> bill cosponsors
/bill/{congress}/{type}/{number}/summaries      -> CRS summaries per bill
/bill/{congress}/{type}/{number}/subjects       -> policy subjects
/bill/{congress}/{type}/{number}/text           -> bill text version index
/bill/{congress}/{type}/{number}/titles         -> all title aliases
/bill/{congress}/{type}/{number}/relatedbills   -> companion / alternate bills
/bill/{congress}/{type}/{number}/amendments     -> amendments filed to bill
/bill/{congress}/{type}/{number}/committees     -> committees considering bill
/law/{congress}                                 -> enacted laws this Congress
/law/{congress}/{type}                          -> public vs private
/law/{congress}/{type}/{number}                 -> specific law detail
/amendment/{congress}                           -> all amendments
/summaries/{congress}[/{type}]                  -> bulk summaries feed
/member/congress/{congress}                     -> members of a congress
/member/congress/{congress}/{state}             -> members by state
/member/{bioguideId}                            -> member detail + bio
/member/{bioguideId}/sponsored-legislation      -> member's sponsored bills
/member/{bioguideId}/cosponsored-legislation    -> member's cosponsored bills
/nomination/{congress}                          -> nomination list
/nomination/{congress}/{number}                 -> nomination detail
/nomination/{congress}/{number}/actions         -> nomination actions
/nomination/{congress}/{number}/hearings        -> nomination hearings
/nomination/{congress}/{number}/committees      -> review committees
/house-vote/{congress}                          -> roll call votes
/house-vote/{congress}/{session}                -> votes in a session
/house-vote/{congress}/{session}/{number}       -> vote detail
/house-vote/{congress}/{session}/{number}/members -> per-member positions
/crsreport                                      -> CRS report list
/crsreport/{reportNumber}                       -> CRS report full detail
/treaty/{congress}                              -> treaty list
/treaty/{congress}/{number}[/{suffix}]          -> treaty detail
/treaty/{congress}/{number}[/{suffix}]/actions  -> treaty actions
/committee-report/{congress}[/{type}]           -> committee markup reports
/hearing/{congress}[/{chamber}]                 -> hearings
/hearing/{congress}/{chamber}/{jacketNumber}    -> hearing detail
```
