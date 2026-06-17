# OFAC Sanctions -- SDN List Data

Script: `projects/apis/ofac/ofac.py`
Data source: `treasury.gov/ofac/downloads/`
Auth: None
Coverage: ~12,000+ entities, updated multiple times per week
Dependencies: `requests`


## Triggers

Use for: SDN entity search, sanctions program filtering, country-level designation counts, vessel/maritime sanctions lists, macro program groupings (Russia, China, Iran, DPRK, terrorism, narcotics, Venezuela, cyber), entity type breakdowns, geopolitical focus dashboards, snapshot exports for diff-based addition/removal detection.

Not for: non-U.S. sanctions regimes (EU/UK/UN), license applications or legal advice, real-time KYC/compliance screening, Federal Register rule text, parsed SDN comments, consolidated non-SDN lists, intraday enforcement timing (CSV publication lags press releases).


## Data Catalog

### Entity Types

| SDN_Type | Description |
|----------|-------------|
| Individual | Natural persons |
| Entity | Organizations, firms, NGOs, government bodies |
| Vessel | Ships and boats |
| Aircraft | Planes and helicopters |

### Curated Macro Programs

8 groupings in `MACRO_PROGRAMS` -- entities counted if any program code intersects the group. Cross-group overlap expected.

| Group key | Label | Program codes |
|-----------|-------|---------------|
| russia | Russia / Ukraine | UKRAINE-EO13661, UKRAINE-EO13662, UKRAINE-EO13685, RUSSIA-EO14024, RUSSIA-EO14066, RUSSIA-EO14068 |
| china | China | CMIC-EO13959, CHINA-EO13936, NS-CMIC-EO13959, HONGKONG-EO13936 |
| iran | Iran | IRAN, IRAN-TRA, IRAN-EO13846, IRAN-EO13871, IFSR, IRGC, NPWMD |
| north_korea | North Korea | DPRK, DPRK2, DPRK3, DPRK4 |
| terrorism | Terrorism / SDGT | SDGT, SDT, FTO |
| narcotics | Narcotics | SDNT, SDNTK |
| venezuela | Venezuela | VENEZUELA, VENEZUELA-EO13850, VENEZUELA-EO13884 |
| cyber | Cyber | CYBER2, CYBER-EO13694 |

### SDN Data Fields (sdn.csv)

No header row in source file. Columns:

| Column | Contents |
|--------|----------|
| ent_num | Unique entity identifier (integer) |
| SDN_Name | Primary sanctioned name |
| SDN_Type | Individual, Entity, Vessel, or Aircraft |
| Program | One or more sanctions program codes (`] [` delimited) |
| Title | Honorific or role title |
| Call_Sign | Vessel or aircraft call sign |
| Vess_type | Vessel type description |
| Tonnage | Vessel tonnage |
| GRT | Gross register tonnage |
| Vess_flag | Vessel flag state |
| Vess_owner | Vessel owner information |
| Remarks | Free-text Treasury remarks |

### Address Fields (add.csv)

| Column | Contents |
|--------|----------|
| ent_num | Links to SDN entity |
| Add_Num | Address record number |
| Address | Street or location line |
| City | City |
| Country | Country (used for `country` filter, substring match) |
| Add_Remarks | Address-specific remarks |

### Alternate Name Fields (alt.csv)

| Column | Contents |
|--------|----------|
| ent_num | Links to SDN entity |
| Alt_Num | Alternate name record number |
| Alt_Type | Type of alias |
| Alt_Name | Alternate spelling or name |
| Alt_Remarks | Remarks for alias |

### Sanctions Program Codes

| Code | Description |
|------|-------------|
| SDGT | Specially Designated Global Terrorist |
| SDT | Specially Designated Terrorist (legacy) |
| FTO | Foreign Terrorist Organization |
| SDNT / SDNTK | Specially Designated Narcotics Traffickers |
| IRAN | Core Iran sanctions program |
| IRAN-TRA | Iran transactions / trade-related |
| IRAN-EO13846 / IRAN-EO13871 | Iran executive order programs |
| IFSR | Iranian Financial Sanctions Regulations |
| IRGC | Islamic Revolutionary Guard Corps |
| NPWMD | Weapons of mass destruction proliferators |
| UKRAINE-EO13661 / EO13662 / EO13685 | Ukraine-related executive orders |
| RUSSIA-EO14024 / EO14066 / EO14068 | Russia executive order programs |
| DPRK / DPRK2 / DPRK3 / DPRK4 | North Korea program family |
| CMIC-EO13959 / NS-CMIC-EO13959 | Chinese military-industrial complex |
| CHINA-EO13936 / HONGKONG-EO13936 | Hong Kong / China executive orders |
| VENEZUELA / EO13850 / EO13884 | Venezuela program family |
| CYBER2 / CYBER-EO13694 | Cyber-related designations |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Download & Refresh

```bash
# Download latest SDN bundle (sdn.csv, add.csv, alt.csv, sdn_comments.csv)
python ofac.py download
python ofac.py download --json
python ofac.py download --export json
```

### Search & Lookup

```bash
# Search entities by name (substring, case-insensitive)
python ofac.py search "rosneft"
python ofac.py search "bank" --json
python ofac.py search "sberbank" --export csv
python ofac.py search "petroleum" --json
python ofac.py search "Huawei" --json
python ofac.py search "tanker" --json
python ofac.py search "NIOC" --json

# Entity detail by ent_num (includes addresses and alt names)
python ofac.py entity 12345
python ofac.py entity 12345 --json
python ofac.py entity 12345 --export json
```

### Filters

```bash
# Filter by address country (substring match)
python ofac.py country Russia
python ofac.py country "United Arab Emirates" --json
python ofac.py country Iran --json
python ofac.py country China --json
python ofac.py country "Korea" --json
python ofac.py country Turkey --json

# Filter by program code (substring match on each program token)
python ofac.py program IRAN
python ofac.py program SDGT --json
python ofac.py program SDGT --export csv
python ofac.py program RUSSIA-EO14024 --json
python ofac.py program CMIC --json
python ofac.py program DPRK --json
python ofac.py program UKRAINE-EO13661 --json
python ofac.py program CYBER --json
python ofac.py program VENEZUELA --json
python ofac.py program IRAN-EO13846 --json
python ofac.py program IRAN-TRA --json

# Vessel-only rows (SDN_Type == vessel)
python ofac.py vessels
python ofac.py vessels --json
python ofac.py vessels --export csv
```

### Analysis

```bash
# List all program codes with entity counts
python ofac.py programs
python ofac.py programs --json
python ofac.py programs --export csv

# Summary counts by SDN_Type
python ofac.py types
python ofac.py types --json
python ofac.py types --export json

# Curated macro program groupings (codes per group)
python ofac.py macro-programs
python ofac.py macro-programs --json
python ofac.py macro-programs --export csv

# Full summary statistics (total, by type, top programs, top countries)
python ofac.py stats
python ofac.py stats --json
python ofac.py stats --export json

# Entity counts per macro grouping (overlap possible across groups)
python ofac.py geo-focus
python ofac.py geo-focus --json
python ofac.py geo-focus --export json
```

### Export

```bash
# Export subcommand: positional target + filters + --format
python ofac.py export search --term rosneft --format json
python ofac.py export entity --ent-num 12345 --format json
python ofac.py export country --country Iran --format csv
python ofac.py export program --program IRAN --format csv
python ofac.py export programs --format json
python ofac.py export types --format csv
python ofac.py export macro-programs --format json
python ofac.py export stats --format json
python ofac.py export geo-focus --format csv
python ofac.py export vessels --format json
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands |
| `--export csv` | Export to timestamped CSV file | All commands |
| `--export json` | Export to timestamped JSON file | All commands |
| `--format` | `json` or `csv` for export subcommand | export only |


## Python Recipes

### Download & Search

```python
from ofac import cmd_download, cmd_search, cmd_entity

# Download latest SDN files (refreshes cache)
cmd_download()

# Search entities by name
# Returns: list of SDN row dicts with ent_num, SDN_Name, SDN_Type, Program, etc.
matches = cmd_search(term="rosneft", as_json=True)
matches = cmd_search(term="petroleum", as_json=True)
matches = cmd_search(term="tanker", as_json=True)
matches = cmd_search(term="Huawei", as_json=True)
matches = cmd_search(term="bank", as_json=True)

# Entity detail with addresses and alt names
# Returns (display): SDN fields + addresses + alternate names
# Use as_json=True for JSON dict with addresses[] and alt_names[]
cmd_entity(ent_num=12345, as_json=True)
```

### Filters

```python
from ofac import cmd_country, cmd_program, cmd_vessels

# Filter by address country (substring)
# Returns: list of SDN row dicts for entities with matching address country
ru = cmd_country(country="Russia", as_json=True)
iran = cmd_country(country="Iran", as_json=True)
uae = cmd_country(country="United Arab Emirates", as_json=True)
china = cmd_country(country="China", as_json=True)
turkey = cmd_country(country="Turkey", as_json=True)

# Filter by program code (substring)
# Returns: list of SDN row dicts for entities in matching programs
iran_prog = cmd_program(program="IRAN", as_json=True)
sdgt = cmd_program(program="SDGT", as_json=True)
russia = cmd_program(program="RUSSIA-EO14024", as_json=True)
cmic = cmd_program(program="CMIC", as_json=True)
dprk = cmd_program(program="DPRK", as_json=True)
cyber = cmd_program(program="CYBER", as_json=True)
venezuela = cmd_program(program="VENEZUELA", as_json=True)

# Vessel-only extract
# Returns: list of SDN row dicts where SDN_Type == Vessel
ships = cmd_vessels(as_json=True)
```

### Analysis

```python
from ofac import cmd_programs, cmd_types, cmd_macro_programs, cmd_stats, cmd_geo_focus

# All programs with entity counts
# Returns: dict of {program_code: count} sorted by count desc
programs = cmd_programs(as_json=True)

# Entity type breakdown
# Returns: dict of {type: count}
types = cmd_types(as_json=True)

# Curated macro program groupings
# Returns: MACRO_PROGRAMS dict with group keys, labels, and program code lists
macro = cmd_macro_programs(as_json=True)

# Full summary statistics
# Returns: {total_entities, by_type, top_programs: [{program, count}],
#           top_countries: [{country, count}], unique_programs, unique_countries}
stats = cmd_stats(as_json=True)

# Entity counts per macro grouping
# Returns: dict keyed by group -> {label, entity_count, programs}
geo = cmd_geo_focus(as_json=True)
```

### Export

```python
from ofac import cmd_export

# Export any command result to file
cmd_export(target="stats", fmt="json")
cmd_export(target="vessels", fmt="csv")
cmd_export(target="search", fmt="json", term="rosneft")
cmd_export(target="country", fmt="csv", country="Russia")
cmd_export(target="program", fmt="json", program="IRAN")
cmd_export(target="geo-focus", fmt="json")
cmd_export(target="programs", fmt="csv")
```


## Composite Recipes

### SDN Snapshot Dashboard

```bash
python ofac.py download
python ofac.py stats --json
python ofac.py geo-focus --json
```

PRISM receives: refreshed SDN data, total entity count with type breakdown and top programs/countries, entity counts across 8 macro groupings (russia, china, iran, north_korea, terrorism, narcotics, venezuela, cyber).

### Russia / Ukraine Deep Dive

```bash
python ofac.py geo-focus --json
python ofac.py program RUSSIA-EO14024 --json
python ofac.py program UKRAINE-EO13661 --json
python ofac.py program RUSSIA-EO14066 --json
python ofac.py country Russia --json
```

PRISM receives: russia macro grouping count, entities under primary Russia EO, entities under Ukraine EO, entities under secondary Russia EO, Russia-addressed entities (gap between program and country counts reveals sanctions evasion jurisdictions like UAE, Turkey, Georgia).

### Iran Oil & Vessel Tracker

```bash
python ofac.py program IRAN --json
python ofac.py program IRAN-TRA --json
python ofac.py program IRAN-EO13846 --json
python ofac.py vessels --json
python ofac.py search "tanker" --json
python ofac.py search "NIOC" --json
```

PRISM receives: all entities under core Iran program, Iran transactions entities, petroleum-specific authority entities, all sanctioned vessels with flag/owner/tonnage, tanker-related name matches, NIOC-related entities.

### China Tech / CMIC Scan

```bash
python ofac.py macro-programs --json
python ofac.py program CMIC --json
python ofac.py program CHINA --json
python ofac.py search "semiconductor" --json
python ofac.py search "Huawei" --json
```

PRISM receives: macro program code reference, CMIC-designated entities (investment-restricted), broader China program entities, semiconductor and Huawei name matches.

### Sanctions Snapshot Export (for Diff)

```bash
python ofac.py download --export json
python ofac.py stats --export json
python ofac.py programs --export json
python ofac.py geo-focus --export json
```

PRISM receives: timestamped exports of full SDN data, stats, program histograms, and geo-focus counts. Compare successive snapshots by subtracting ent_num sets to detect additions (new designations) and removals (delistings).

### Entity Investigation

```bash
python ofac.py search "TARGET_NAME" --json
python ofac.py entity {ENT_NUM} --json
python ofac.py program {PROGRAM_CODE} --json
```

PRISM receives: search matches with ent_num, full entity detail with addresses and alternate names, all entities in the same program for context.


## Cross-Source Recipes

### Sanctions + Legislation

```bash
python ofac.py geo-focus --json
python projects/apis/congress/congress.py search "sanctions" --json
```

PRISM receives: SDN designation counts by macro grouping + active sanctions legislation. Legislative pipeline frames future OFAC actions.

### Sanctions + Prediction Markets

```bash
python ofac.py stats --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset geopolitical --json
```

PRISM receives: SDN universe size and program distribution + market-implied geopolitical probabilities. Sanctions intensity vs priced-in risk.

### Iran Sanctions + Energy

```bash
python ofac.py program IRAN --json
python ofac.py vessels --json
python projects/apis/eia/eia.py petroleum --json
```

PRISM receives: Iran-designated entity count + sanctioned vessel fleet + petroleum supply data. Maritime enforcement intensity vs physical flows.

### Russia Sanctions + Commodity Positioning

```bash
python ofac.py program RUSSIA-EO14024 --json
python projects/apis/cftc/cftc.py energy --json
```

PRISM receives: Russia program designation count + speculative energy positioning. Sanctions escalation vs commodity market bets.

### Sanctions + Media Narrative

```bash
python ofac.py geo-focus --json
python projects/apis/gdelt/gdelt.py events --theme sanctions --json
```

PRISM receives: SDN macro grouping counts + media narrative intensity around sanctions. Designation events vs narrative coverage.

### Sanctions + Public Attention

```bash
python ofac.py geo-focus --json
python projects/apis/wikipedia/wikipedia.py compare Tariff Trade_war Sanctions_\(law\) --days 30 --json
```

PRISM receives: SDN designation distribution + public Wikipedia attention on trade/sanctions topics. Institutional action vs grassroots awareness.


## Setup

1. No API key required
2. `pip install requests`
3. Download data: `python ofac.py download`
4. Test: `python ofac.py stats --json`


## Architecture

```
ofac.py
  Constants       DOWNLOAD_URLS (5), SDN_COLUMNS (12), ADD_COLUMNS (6),
                  ALT_COLUMNS (5), MACRO_PROGRAMS (8 groups)
  HTTP            SESSION with User-Agent, _download_file() with progress
  Data Loading    _parse_csv_no_header, _load_sdn, _load_addresses,
                  _load_alt_names (all cached after first load)
  Search/Filter   _search_entities, _filter_by_program, _filter_by_country,
                  _filter_by_type, _split_programs
  Commands (12)   download, search, entity, country, program, programs,
                  types, macro-programs, stats, geo-focus, vessels, export
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        12 subcommands, all with --json and --export
```

Data files:
```
treasury.gov/ofac/downloads/sdn.csv          -> SDN entities (no header)
treasury.gov/ofac/downloads/add.csv          -> addresses (no header)
treasury.gov/ofac/downloads/alt.csv          -> alternate names (no header)
treasury.gov/ofac/downloads/sdn_comments.csv -> comments (downloaded, not parsed)
```
