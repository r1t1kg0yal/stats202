# USITC Harmonized Tariff Schedule Data

Script: `projects/apis/tariffs/tariffs.py`
Base URL: `https://hts.usitc.gov/reststop`
Auth: None required
Rate limit: Not published; client spaces ~0.3s between calls, backs off on HTTP 429
Dependencies: `requests`


## Triggers

Use for: U.S. import duty rate lookups by HTS code or product description, **Chapter 99 policy overlay resolution** (Section 232 steel/aluminum/semi, Section 301 China, reciprocal tariffs, IEEPA, Section 201 safeguards), **effective stacked duty calculation** (base chapter rate + auto-resolved Chapter 99 overlay from footnote references), **15 curated macro sectors** (steel/aluminum, autos, semis, energy, agriculture, pharma, rare earths, textiles, chemicals/feedstocks, batteries/EV, solar, capital equipment, aerospace, copper/metals, medical devices, consumer goods), chapter-level duty distribution summaries, high-duty line screening, batch rate checks, comparing general vs special vs other duty columns, HTS release diffing across vintages.

Not for: country-specific effective landed duty with AD/CVD orders (use Commerce/ITA), real-time CBP classification rulings, non-U.S. tariff schedules (other WCO members), trade volumes or elasticity modeling (Census / UN Comtrade), full text of underlying executive proclamations (use Federal Register).


## Data Catalog

### HTS Structure

| Digits | Name | Role |
|--------|------|------|
| 2 | Chapter | Broadest WCO bucket (01-97 live goods; 98-99 special) |
| 4 | Heading | Product family within chapter |
| 6 | Subheading | International harmonized subheading |
| 8 | US subheading | U.S.-specific split within the 6-digit frame |
| 10 | Statistical suffix | Finest reporting split |

### Duty Rate Columns

| Column | Meaning |
|--------|---------|
| General | Normal trade relations / default statutory rate absent a preference program |
| Special | Preferential rates (FTA partners, GSP when applicable, other special programs) |
| Other | Rates for enumerated non-NTR countries or specific statutory baskets |
| Additional duties | Extra ad valorem or specific duties when encoded on the line |

### Curated Macro Sectors (15)

| Sector key | Label | Chapters | Representative codes |
|------------|-------|----------|---------------------|
| steel_aluminum | Steel & Aluminum | 72, 73, 76 | 7206.10, 7207.11, 7601.10 |
| autos | Automobiles & Parts | 87 | 8703.23, 8703.24, 8708.10 |
| semiconductors | Semiconductors & Electronics | 84, 85 | 8541.10, 8542.31, 8471.30 |
| energy | Energy & Petroleum | 27 | 2709.00, 2710.12, 2711.11 |
| agriculture | Agriculture & Food | 2, 4, 10, 12, 17, 22 | 1001.19, 1005.90, 1201.90 |
| pharma | Pharmaceuticals | 29, 30 | 3004.90 |
| rare_earths | Rare Earths & Critical Minerals | 26, 28 | 2612.10, 2846.90 |
| textiles | Textiles & Apparel | 50, 51, 52, 61, 62 | (none) |
| chemicals | Chemicals & Feedstocks | 28, 29, 38, 39, 40 | 2804.10, 2901.10, 2902.30, 3901.10, 3902.10 |
| batteries_ev | Batteries & EV Components | 85 | 8507.60, 8507.30, 8544.60 |
| solar | Solar & Renewables | 85 | 8541.42, 8541.43 |
| capital_equipment | Capital Equipment & Machine Tools | 84 | 8456.11, 8457.10, 8458.11, 8462.10, 8466.93 |
| aerospace | Aerospace | 88 | 8802.40, 8803.30 |
| copper_metals | Copper & Industrial Metals | 74, 78, 79, 80 | 7403.11, 7408.11 |
| medical_devices | Medical Devices | 90 | 9018.19, 9018.31, 9022.12 |
| consumer_goods | Consumer Goods (Apparel, Footwear, Retail) | 42, 61, 62, 63, 64, 71 | 6404.11, 4202.12, 7113.19 |

### Statutory Tariff Actions Registry (22 actions)

| Action key | Year | Overlay prefix | Description |
|------------|------|---------------|-------------|
| section_232_steel | 2018 | 9903.81 | Section 232 Steel (25%) |
| section_232_aluminum | 2018 | 9903.85 | Section 232 Aluminum (10%) |
| section_232_aluminum_russia_200 | 2023 | 9903.85.67 | Section 232 Aluminum Russia 200% |
| section_232_semiconductors | 2025 | 9903.79 | Section 232 Semiconductors |
| section_232_derivative | 2025 | 9903.82 | Section 232 Al/Steel/Cu Derivatives |
| section_301_list1 | 2018 | 9903.88 | Section 301 China List 1 ($34B) |
| section_301_list2 | 2018 | 9903.88 | Section 301 China List 2 ($16B) |
| section_301_list3 | 2018 | 9903.88 | Section 301 China List 3 ($200B) |
| section_301_list4a | 2019 | 9903.88 | Section 301 China List 4A ($112B) |
| section_301_china_usmca_2024 | 2024 | 9903.91 | Section 301 China USMCA-adjacent (Sep 2024) |
| section_301_china_cranes_2024 | 2024 | 9903.92 | Section 301 Ship-to-Shore Cranes |
| section_201_solar | 2018 | 9903.45 | Section 201 Solar Safeguard |
| ieepa_russia | 2022 | 9903.90 | IEEPA Russia Sanctions |
| ieepa_oil_russia | 2024 | 9903.27 | IEEPA Oil/Fuel Russia |
| reciprocal_mexico | 2025 | 9903.01 | Reciprocal Tariffs - Mexico (Feb 2025) |
| reciprocal_broad_2025 | 2025 | 9903.02 | Reciprocal Tariffs Broad (Apr 2025) |
| reciprocal_country_2025 | 2025 | 9903.03 | Reciprocal Tariffs Country-Specific |
| usmca_carveouts_2025 | 2025 | 9903.94 | USMCA Carveouts / Exclusions |
| aircraft_civil_2025 | 2025 | 9903.96 | Civil Aircraft Tariffs (2025) |
| hdv_2025 | 2025 | 9903.74 | Medium/Heavy-Duty Vehicle Safeguard |
| softwood_lumber_2025 | 2025 | 9903.76 | Softwood Lumber Safeguard |

### Chapter 99 Subchapter Registry (28 regimes)

Chapter 99 is where all executive/statutory tariff *overlays* live. Base chapters 1-97 give the statutory rate; Chapter 99 entries specify "applicable subheading + X%" that stacks on top based on country of origin or covered product. Footnotes on base-chapter lines like "See 9903.88.01" point to the applicable overlay.

| Prefix | Regime | Typical Overlay |
|--------|--------|------------------|
| 9903.01 | IEEPA - Mexico | base + 25% |
| 9903.02 | IEEPA - Global Reciprocal | base + 15% to +40% |
| 9903.03 | IEEPA - Country Reciprocal | varies by country |
| 9903.04 | USMCA TRQ (Dairy) | quota-gated |
| 9903.08 | Section 201 (Bath Prep) | ad valorem |
| 9903.17 | USMCA TRQ (Sugar/Dairy) | quota-gated |
| 9903.18 | USMCA TRQ (Beef/Poultry) | quota-gated |
| 9903.19 | Food Product Quotas | quota-gated |
| 9903.27 | IEEPA Russia Oil | varies |
| 9903.40 | Section 201 Tire Safeguard | ad valorem phase-down |
| 9903.41 | IEEPA Leather | + duty |
| 9903.45 | Section 201 Solar Safeguard | ad valorem phase-down |
| 9903.52 | Special Agriculture Quota | quota-gated |
| 9903.53 | Softwood Lumber - Canada by Region | varies |
| 9903.54 | Argentina Beef | quota-gated |
| 9903.55 | Temporary Importation Bond Quotas | quota-gated |
| 9903.74 | Section 232 HDV (Heavy Duty Vehicles) | ad valorem |
| 9903.76 | Section 232 Softwood Timber | ad valorem |
| 9903.79 | Section 232 Semiconductors | varies |
| 9903.82 | Section 232 Al/Steel/Cu Derivatives | + 25% derivatives |
| 9903.85 | Section 232 Aluminum-Russia | + 200% |
| 9903.88 | Section 301 China (Lists 1-4A) | + 7.5% / + 15% / + 25% |
| 9903.89 | IEEPA Nicaragua | ad valorem |
| 9903.90 | IEEPA Russian Federation | ad valorem |
| 9903.91 | Section 301 China USMCA-Adjacent | + 25% / higher |
| 9903.92 | Section 301 China Cranes/Heavy Equipment | + 25% to + 100% |
| 9903.94 | USMCA Reciprocal Carveouts | excluded (pass-through) |
| 9903.96 | IEEPA Civil Aircraft | ad valorem |

### HTS Code Fields (per result — with field preservation)

| Field | Type | Description |
|-------|------|-------------|
| `htsno` | string | HTS number at indent level |
| `description` | string | Product description |
| `superior` | string | Parent heading (hierarchy traversal) |
| `indent` | string | Indent level in schedule hierarchy |
| `statistical_suffix` | string | Finest-granularity reporting split |
| `general` | string | General duty rate string |
| `special` | string | Special duty rate string |
| `other` | string | Other duty rate string |
| `unit1` | string | Primary unit of quantity |
| `unit2` | string | Secondary unit of quantity |
| `units` | string | All units joined |
| `footnotes` | string | All footnote text joined with column attribution `[cols] text` |
| `footnote_refs` | string | Auto-extracted 9903.xx references from footnotes |
| `quota_quantity` | string | Quota quantity if applicable |
| `additional_duties` | string | Additional duty strings |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export where noted.

### Code Lookup & Search

```bash
# Lookup by HTS number (prefix match)
python tariffs.py lookup 8703.23 --json
python tariffs.py lookup 7206.10 --export csv
python tariffs.py lookup 2709 --json

# Keyword search on descriptions
python tariffs.py search "crude petroleum" --json
python tariffs.py search "aluminum" --export json
python tariffs.py search "lithium battery" --json
python tariffs.py search "semiconductor" --json
```

### Chapter Operations

```bash
python tariffs.py chapter 72 --json
python tariffs.py chapter 87 --export csv
python tariffs.py chapter 85 --json        # electronics
python tariffs.py chapter 99 --json        # all overlays

python tariffs.py releases --json
```

### Duty Detail

```bash
python tariffs.py duty 8703.23.01 --json
python tariffs.py duty 7206.10.0000 --json
python tariffs.py duty 2709.00.1000 --json
python tariffs.py duty 8542.31 --export csv
```

### Batch Rate Check

```bash
python tariffs.py rate-check 7206.10 7601.10 2709.00 --json
python tariffs.py rate-check 8541.10 8542.31 8471.30 --export csv
```

### Chapter Analytics

```bash
python tariffs.py chapter-summary 72 --json
python tariffs.py chapter-summary 87 --json

# High-duty lines
python tariffs.py high-duty 72 --threshold 25 --json
python tariffs.py high-duty 87 --threshold 10 --json
python tariffs.py high-duty 17 --threshold 50 --json
```

### Macro Sector Tools

```bash
# Registry metadata
python tariffs.py macro-sectors --json

# Pull all codes + rates across a sector's chapters
# sector choices: steel_aluminum, autos, semiconductors, energy, agriculture,
#                 pharma, rare_earths, textiles, chemicals, batteries_ev,
#                 solar, capital_equipment, aerospace, copper_metals,
#                 medical_devices, consumer_goods
python tariffs.py sector steel_aluminum --json
python tariffs.py sector autos --json
python tariffs.py sector semiconductors --export csv
python tariffs.py sector chemicals --json
python tariffs.py sector batteries_ev --json
python tariffs.py sector solar --json
python tariffs.py sector capital_equipment --json
python tariffs.py sector aerospace --json
python tariffs.py sector copper_metals --json
python tariffs.py sector medical_devices --json
python tariffs.py sector consumer_goods --json

# Major tariff actions reference (22 actions with overlay prefixes)
python tariffs.py tariff-actions --json
```

### Chapter 99 Overlays (Effective Tariff Layer)

```bash
# Chapter 99 subchapter registry (28 policy regimes)
python tariffs.py chapter99 --json
python tariffs.py chapter99 --export csv

# Pull all lines under a Chapter 99 subchapter
python tariffs.py chapter99-sub 9903.88 --json    # Section 301 China (66 lines)
python tariffs.py chapter99-sub 9903.82 --json    # Al/Steel/Cu derivatives
python tariffs.py chapter99-sub 9903.01 --json    # Mexico reciprocal
python tariffs.py chapter99-sub 9903.02 --json    # broad reciprocal
python tariffs.py chapter99-sub 9903.91 --json    # China USMCA-adjacent
python tariffs.py chapter99-sub 9903.45 --json    # solar safeguard
python tariffs.py chapter99-sub 9903.79 --json    # semiconductors
python tariffs.py chapter99-sub 9903.85 --json    # aluminum-Russia 200%

# Auto-resolve effective stacked duty (base + overlays from footnote refs)
python tariffs.py overlay 7206.10 --json
python tariffs.py overlay 7206.10.00.00 --json
python tariffs.py overlay 8541.42 --json         # solar cell
python tariffs.py overlay 8703.23 --json         # passenger car
python tariffs.py overlay 2709.00 --json         # crude petroleum
python tariffs.py overlay 8507.60 --json         # lithium battery
```

### Release Diff (Rate-Change Tracking)

```bash
# Compare two HTS releases for a chapter (releases from /releaseList)
python tariffs.py release-diff --chapter 72 --json
python tariffs.py release-diff --release-a 2025HTSRev6 --release-b 2026HTSRev5 --chapter 99 --json
python tariffs.py release-diff --chapter 76 --export csv
```

### Export Dispatcher

```bash
# Writes timestamped file next to the script
python tariffs.py export chapter --chapter 72 --format csv
python tariffs.py export sector --sector autos --format json
python tariffs.py export rate-check --codes 7206.10 7601.10 --format json
python tariffs.py export high-duty --chapter 73 --threshold 30 --format csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output | All commands except export |
| `--export csv\|json` | Export to file | lookup, search, chapter, duty, sector, rate-check, chapter-summary, high-duty, chapter99, chapter99-sub, overlay, release-diff |
| `--threshold N` | Minimum general-column duty % | high-duty |
| `--chapter N` | Chapter number | chapter, chapter-summary, high-duty, release-diff |
| `--release-a / --release-b` | Release names to compare | release-diff |


## Python Recipes

### Extended Commands

```python
from tariffs import (
    cmd_lookup, cmd_search, cmd_chapter, cmd_duty, cmd_rate_check,
    cmd_chapter_summary, cmd_high_duty, cmd_macro_sectors, cmd_sector,
    cmd_tariff_actions, cmd_releases,
    cmd_chapter99, cmd_chapter99_subchapter, cmd_overlay,
    cmd_release_diff,
)

# New sectors
batteries = cmd_sector("batteries_ev", as_json=True)
chemicals = cmd_sector("chemicals", as_json=True)
medical = cmd_sector("medical_devices", as_json=True)

# Chapter 99 registry + subchapter pulls
registry = cmd_chapter99(as_json=True)
sec301 = cmd_chapter99_subchapter("9903.88", as_json=True)
reciprocal_mx = cmd_chapter99_subchapter("9903.01", as_json=True)

# Auto-resolve effective tariff with overlays
# Returns: {base, base_general, base_parsed_pct, overlay_references, overlays[]}
eff = cmd_overlay("7206.10", as_json=True)
eff = cmd_overlay("8541.42", as_json=True)  # solar

# Release diffing
diff = cmd_release_diff(chapter=72, as_json=True)  # latest two
diff = cmd_release_diff(release_a="2025HTSRev6",
                        release_b="2026HTSRev5",
                        chapter=99, as_json=True)
```


## Composite Recipes

### Sector Tariff Exposure Scan

```bash
python tariffs.py macro-sectors --json
python tariffs.py sector steel_aluminum --json
python tariffs.py chapter-summary 72 --json
python tariffs.py chapter-summary 73 --json
python tariffs.py chapter-summary 76 --json
python tariffs.py chapter99-sub 9903.82 --json
```

PRISM receives: all 16 curated macro sectors, full rate sheet for steel/aluminum, per-chapter summaries (total codes, free/dutiable split, rate distribution), and Chapter 99 derivatives overlay for the stacked layer.

### Effective Tariff Deep Dive (Single Code)

```bash
python tariffs.py duty 7206.10.0000 --json
python tariffs.py overlay 7206.10 --json
python tariffs.py chapter99-sub 9903.91 --json
```

PRISM receives: base HTS detail, auto-resolved overlay lookup from footnote refs, and the Chapter 99 subchapter context for the applicable policy regime. Effective duty = base rate + applicable overlay.

### Chapter 99 Policy Regime Scan

```bash
python tariffs.py chapter99 --json
python tariffs.py chapter99-sub 9903.88 --json   # Section 301 China
python tariffs.py chapter99-sub 9903.01 --json   # Mexico reciprocal
python tariffs.py chapter99-sub 9903.02 --json   # broad reciprocal
python tariffs.py chapter99-sub 9903.79 --json   # semiconductors
python tariffs.py chapter99-sub 9903.45 --json   # solar
python tariffs.py tariff-actions --json
```

PRISM receives: 28-subchapter policy regime index + line-level overlays for 5 key regimes + statutory action registry.

### High-Duty Screening Across Sectors

```bash
python tariffs.py high-duty 72 --threshold 25 --json
python tariffs.py high-duty 87 --threshold 10 --json
python tariffs.py high-duty 29 --threshold 5 --json
python tariffs.py high-duty 17 --threshold 50 --json
python tariffs.py chapter99-sub 9903.85 --json        # 200% aluminum-Russia
```

PRISM receives: high-duty lines across steel, autos, pharma, sugar (all chapters 1-97) plus the highest-magnitude Chapter 99 overlay.

### Battery / EV Supply Chain Tariff Exposure

```bash
python tariffs.py sector batteries_ev --json
python tariffs.py overlay 8507.60 --json
python tariffs.py search "lithium" --json
python tariffs.py search "cathode" --json
python tariffs.py chapter99-sub 9903.91 --json      # China USMCA adjustments
python tariffs.py chapter99-sub 9903.88 --json      # Section 301 China
```

PRISM receives: battery/EV sector rate sheet, effective stacked duty for a lithium-ion cell, keyword matches for supply chain inputs, and the two Chapter 99 regimes most likely to apply to Chinese origins.

### Semiconductor Sector Full Stack

```bash
python tariffs.py sector semiconductors --json
python tariffs.py overlay 8542.31 --json
python tariffs.py overlay 8541.10 --json
python tariffs.py chapter99-sub 9903.79 --json      # Section 232 semi
python tariffs.py chapter99-sub 9903.88 --json      # Section 301 China
python tariffs.py search "wafer" --json
```

PRISM receives: base semiconductor rates, effective stacked duty for specific codes, both applicable Chapter 99 regimes, and adjacent upstream/input codes.

### Release Vintage Comparison

```bash
python tariffs.py releases --json
python tariffs.py release-diff --chapter 99 --json
python tariffs.py release-diff --chapter 72 --json
python tariffs.py release-diff --chapter 87 --json
```

PRISM receives: available release versions + rate changes across latest two revisions for Chapter 99 overlays, steel, and autos.


## Cross-Source Recipes

### Tariff Rates + Legislative Authority

```bash
python tariffs.py tariff-actions --json
python tariffs.py chapter99 --json
python projects/apis/congress/congress.py search "IEEPA" --congress 119 --json
python projects/apis/congress/congress.py tracker --topics tariff --json
python projects/apis/congress/congress.py treaties --congress 119 --json
```

PRISM receives: statutory action registry + Chapter 99 policy regimes + bills constraining/expanding presidential tariff authority + active tariff legislation + pending trade treaties.

### Effective Tariff + Implementing Proclamations

```bash
python tariffs.py overlay 7206.10 --json
python tariffs.py chapter99-sub 9903.82 --json
python projects/apis/federal_register/federal_register.py search "tariff" --type presidential --json
python projects/apis/federal_register/federal_register.py search "Section 232" --json
python projects/apis/federal_register/federal_register.py suggested --section world --json
```

PRISM receives: effective stacked rate for a specific code + Chapter 99 derivatives context + executive proclamations establishing the overlay + Section 232 implementation docs + FR-curated trade topic packs.

### Tariff Rates + Agricultural Positioning

```bash
python tariffs.py sector agriculture --json
python tariffs.py chapter99-sub 9903.17 --json
python tariffs.py chapter99-sub 9903.18 --json
python projects/apis/cftc/cftc.py agriculture --json
```

PRISM receives: statutory duty rates for ag chapters + USMCA TRQ overlays + speculative positioning in tariff-sensitive commodities.

### Tariff Rates + Market-Implied Policy

```bash
python tariffs.py tariff-actions --json
python tariffs.py chapter99 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset trade_policy --json
```

PRISM receives: tariff action + regime registry + market-implied probabilities of escalation/de-escalation.


## Setup

1. No API key required
2. `pip install requests`
3. Test: `python tariffs.py releases --json`
4. Overlay test: `python tariffs.py chapter99`
5. Full test: `python tariffs.py sector steel_aluminum --json`
6. Effective-tariff test: `python tariffs.py overlay 7206.10 --json`


## Architecture

```
tariffs.py
  Constants       BASE_URL, MACRO_CHAPTERS (16 sectors), TARIFF_ACTIONS (22),
                  CHAPTER99_SUBCHAPTERS (28 regimes), SECTOR_KEYS
  HTTP            _request() with retries, rate limit backoff, 0.3s spacing
  Data Fetchers   _fetch_search, _fetch_export_range, _fetch_chapter,
                  _fetch_releases
  Parsing         _parse_rate, _flatten_code (preserves superior/indent/
                  statisticalSuffix/unit1/unit2/footnote_refs),
                  _format_footnotes (with column attribution),
                  _extract_overlay_refs (regex for 9903.xx refs),
                  _classify_overlay (map ref to Chapter 99 registry)
  Commands (16)   lookup, search, chapter, releases, duty, macro-sectors,
                  sector, tariff-actions, rate-check, chapter-summary,
                  high-duty, chapter99, chapter99-sub, overlay, release-diff,
                  export
  Interactive     16-item menu -> interactive wrappers with prompts
  Argparse        16 subcommands, all with --json and --export where applicable
```

API endpoints used:

```
/search?keyword=...                     -> keyword or HTS number search (up to 100 results)
/exportList?from=...&to=...&format=JSON -> range export (all codes in range, incl. Chapter 99)
/releaseList                            -> available schedule versions
```

### Architecture Notes

- **Overlay resolution** (`cmd_overlay`) combines a base-chapter lookup with
  follow-up searches on any `9903.xx` references found in footnotes. This
  surfaces the Section 232 / 301 / IEEPA overlay that actually applies to a
  specific line, producing an effective stacked-duty view.
- **Chapter 99 registry** in code (`CHAPTER99_SUBCHAPTERS`) was built from a
  live scan of all `9903.xx` subchapters in the most recent HTS release. The
  28 prefixes present correspond to actively used policy regimes.
- **Footnote attribution** in `_format_footnotes` now prepends
  `[general,special,other]` column markers so downstream consumers know
  which rate column each footnote applies to (general-column-only notes are
  the overlay-relevance signal).
- **Release diffing** uses the `release` query parameter on `/exportList`
  when supported by USITC. The API does not guarantee historical data on
  all releases; when data is returned unchanged across releases, the
  difference is safely reported as zero rather than erroring.
```
