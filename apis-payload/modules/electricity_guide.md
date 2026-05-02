# EIA Electricity Grid Data

Script: `projects/apis/electricity/electricity.py`
Base URL: `https://api.eia.gov/v2/electricity/rto/`
Auth: `EIA_API_KEY` env var (free at https://www.eia.gov/opendata/register.php)
Rate limit: ~0.2s between calls (built into client)
Dependencies: `requests`


## Triggers

Use for: hourly electricity demand by balancing authority, generation by fuel type, fuel mix percentages, interchange flows between regions, peak demand analysis, multi-region demand comparison, macro group snapshots (Big 7, industrial belt, sun belt, tech corridor), daily demand aggregation.

Not for: retail electricity rates or tariff design (different EIA products), real-time nodal LMPs or bid/offer stack (ISO market feeds), non-US grids, behind-the-meter generation, sub-hourly data, long-term capacity expansion planning, weather forecasting, seasonal adjustment (post-process yourself).


## Data Catalog

### Balancing Authorities (14 curated)

| Code | Name | Area | States |
|------|------|------|--------|
| PJM | PJM Interconnection | Mid-Atlantic + Midwest | PA, NJ, DE, MD, VA, WV, OH, IN, IL, MI, KY, NC, TN, DC |
| MISO | Midcontinent ISO | Central US | MN, WI, IA, MO, AR, MS, LA, IN, MI, MT, ND, SD |
| ERCO | ERCOT (Texas) | Texas | TX |
| CISO | California ISO | California | CA |
| ISNE | ISO New England | New England | CT, ME, MA, NH, RI, VT |
| NYIS | New York ISO | New York | NY |
| SWPP | Southwest Power Pool | Central Plains | KS, OK, NE, parts of NM, TX, AR, LA, MO |
| SOCO | Southern Company | Southeast | AL, GA, parts of MS, FL |
| TVA | Tennessee Valley Authority | Tennessee Valley | TN, AL, MS, KY, GA, NC, VA |
| BPAT | Bonneville Power Admin | Pacific Northwest | WA, OR, ID, MT |
| WACM | Western Area (Colorado/Missouri) | Western | CO, NE, WY, MT, SD, ND, MN, IA |
| FPL | Florida Power & Light | Florida | FL |
| DUK | Duke Energy Carolinas | Carolinas | NC, SC |
| AEC | PowerSouth Energy | Alabama | AL |

### Macro Groups

| Group key | Label | Regions |
|-----------|-------|---------|
| `big_seven` | Big 7 RTOs/ISOs | PJM, MISO, ERCO, CISO, ISNE, NYIS, SWPP |
| `industrial_belt` | Industrial Belt | PJM, MISO, TVA |
| `sun_belt` | Sun Belt | ERCO, SOCO, FPL |
| `tech_corridor` | Tech Corridor | CISO, ISNE, NYIS, PJM |

### Fuel Types

| Code | Description |
|------|-------------|
| COL | Coal |
| NG | Natural Gas |
| NUC | Nuclear |
| SUN | Solar |
| WND | Wind |
| WAT | Hydro |
| OIL | Petroleum |
| OTH | Other |
| ALL | All Sources |

### Data Availability

| Series | Typical lag | History |
|--------|-------------|---------|
| Hourly demand | ~1 hour | Since 2015 |
| Hourly generation by fuel | ~1 hour | Since 2015 |
| Hourly interchange | ~1 hour | Since 2015 |

### Demand Fields (per observation)

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Hour timestamp (`YYYY-MM-DDTHH`) |
| `respondent` | string | Balancing authority code |
| `respondent-name` | string | Balancing authority name |
| `type` | string | `D` for demand |
| `value` | int | Demand in MWh |

### Generation Fields (per observation)

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Hour timestamp |
| `respondent` | string | Balancing authority code |
| `fueltype` | string | Fuel code (COL, NG, NUC, SUN, WND, WAT, OIL, OTH) |
| `type-name` | string | Fuel name |
| `value` | int | Generation in MWh |

### Interchange Fields (per observation)

| Field | Type | Description |
|-------|------|-------------|
| `period` | string | Hour timestamp |
| `fromba` | string | Source BA code |
| `toba` | string | Destination BA code |
| `value` | int | Flow in MWh (positive = from -> to) |

### Peak Result Fields (computed)

| Field | Type | Description |
|-------|------|-------------|
| `region` | string | Balancing authority code |
| `peak_mwh` | int | Maximum hourly demand in window |
| `peak_period` | string | Timestamp of peak hour |
| `avg_mwh` | int | Average hourly demand in window |
| `peak_vs_avg_pct` | float | Peak premium over average (%) |
| `hours_analyzed` | int | Total hours in window |
| `days` | int | Lookback days |

### Daily History Fields (computed)

| Field | Type | Description |
|-------|------|-------------|
| `date` | string | Calendar date |
| `total` | int | Total MWh for the day |
| `count` | int | Hours with data |
| `peak` | int | Peak hourly MWh |
| `peak_hour` | string | Timestamp of peak hour |

### Snapshot Entry Fields (computed)

| Field | Type | Description |
|-------|------|-------------|
| `region` | string | Balancing authority code |
| `value` | int | Latest hourly demand (MWh) |
| `period` | string | Timestamp of latest observation |


## CLI Recipes

All commands support `--json` for structured output and `--export csv|json` for file export.

### Demand

```bash
# Hourly demand, defaults (PJM, 24h)
python electricity.py demand
python electricity.py demand --json

# Specific region and window
python electricity.py demand --region PJM --hours 48
python electricity.py demand --region ERCO --hours 72
python electricity.py demand --region CISO --hours 168
python electricity.py demand --region MISO --hours 24 --json
python electricity.py demand --region ISNE --hours 48 --json
python electricity.py demand --region NYIS --hours 96 --json
python electricity.py demand --region TVA --hours 48
python electricity.py demand --region SOCO --hours 24
python electricity.py demand --region BPAT --hours 72
python electricity.py demand --region SWPP --hours 48
python electricity.py demand --region WACM --hours 24
python electricity.py demand --region FPL --hours 48
python electricity.py demand --region DUK --hours 24
python electricity.py demand --region AEC --hours 24

# With export
python electricity.py demand --region PJM --hours 168 --export csv
python electricity.py demand --region ERCO --hours 48 --export json
```

### Daily Demand History

```bash
# Daily totals with peaks, defaults (PJM, 7 days)
python electricity.py demand-history
python electricity.py demand-history --json

# Specific region and window
python electricity.py demand-history --region PJM --days 7
python electricity.py demand-history --region PJM --days 14
python electricity.py demand-history --region PJM --days 21
python electricity.py demand-history --region PJM --days 30
python electricity.py demand-history --region ERCO --days 7 --json
python electricity.py demand-history --region CISO --days 14 --json
python electricity.py demand-history --region MISO --days 7
python electricity.py demand-history --region TVA --days 14
python electricity.py demand-history --region ISNE --days 7
python electricity.py demand-history --region NYIS --days 7

# With export
python electricity.py demand-history --region PJM --days 14 --export csv
python electricity.py demand-history --region ERCO --days 30 --export json
```

### Peak Demand

```bash
# Peak demand hour, defaults (PJM, 3 days)
python electricity.py peak
python electricity.py peak --json

# Specific region and window
python electricity.py peak --region PJM --days 3
python electricity.py peak --region PJM --days 7
python electricity.py peak --region PJM --days 14
python electricity.py peak --region ERCO --days 7 --json
python electricity.py peak --region CISO --days 5 --json
python electricity.py peak --region MISO --days 7
python electricity.py peak --region TVA --days 7
python electricity.py peak --region ISNE --days 7
python electricity.py peak --region NYIS --days 3

# With export
python electricity.py peak --region PJM --days 7 --export csv
python electricity.py peak --region ERCO --days 14 --export json
```

### Generation by Fuel Type

```bash
# Hourly generation by fuel, defaults (PJM, 24h)
python electricity.py generation
python electricity.py generation --json

# Specific region and window
python electricity.py generation --region PJM --hours 24
python electricity.py generation --region ERCO --hours 48
python electricity.py generation --region CISO --hours 168
python electricity.py generation --region MISO --hours 72 --json
python electricity.py generation --region ISNE --hours 48
python electricity.py generation --region NYIS --hours 24
python electricity.py generation --region TVA --hours 48
python electricity.py generation --region BPAT --hours 72

# With export
python electricity.py generation --region CISO --hours 168 --export csv
python electricity.py generation --region ERCO --hours 48 --export json
```

### Fuel Mix

```bash
# Fuel mix percentage at latest hour, defaults (PJM, 24h lookback)
python electricity.py fuel-mix
python electricity.py fuel-mix --json

# Specific region
python electricity.py fuel-mix --region PJM --hours 24
python electricity.py fuel-mix --region ERCO --hours 24
python electricity.py fuel-mix --region CISO --hours 24
python electricity.py fuel-mix --region MISO --hours 48
python electricity.py fuel-mix --region ISNE --hours 24
python electricity.py fuel-mix --region NYIS --hours 24
python electricity.py fuel-mix --region TVA --hours 24
python electricity.py fuel-mix --region BPAT --hours 24
python electricity.py fuel-mix --region CISO --hours 72 --json
python electricity.py fuel-mix --region ERCO --hours 72 --json
python electricity.py fuel-mix --region PJM --hours 72 --json

# With export
python electricity.py fuel-mix --region CISO --hours 24 --export csv
python electricity.py fuel-mix --region ERCO --hours 48 --export json
```

### Interchange

```bash
# Power flow between two BAs, defaults (PJM -> NYIS, 24h)
python electricity.py interchange
python electricity.py interchange --json

# Specific pairs and windows
python electricity.py interchange --from PJM --to NYIS --hours 24
python electricity.py interchange --from PJM --to MISO --hours 48
python electricity.py interchange --from ERCO --to SWPP --hours 24
python electricity.py interchange --from CISO --to BPAT --hours 72
python electricity.py interchange --from ISNE --to NYIS --hours 48
python electricity.py interchange --from MISO --to TVA --hours 24
python electricity.py interchange --from SOCO --to TVA --hours 48
python electricity.py interchange --from PJM --to NYIS --hours 48 --json
python electricity.py interchange --from ERCO --to SWPP --hours 24 --json

# With export
python electricity.py interchange --from PJM --to NYIS --hours 48 --export csv
python electricity.py interchange --from MISO --to TVA --hours 24 --export json
```

### Snapshots & Comparisons

```bash
# Big 7 demand snapshot (latest hour per RTO/ISO)
python electricity.py snapshot
python electricity.py snapshot --json
python electricity.py snapshot --export csv

# Multi-region demand comparison
python electricity.py compare --regions PJM MISO ERCO --hours 24
python electricity.py compare --regions PJM MISO TVA --hours 168
python electricity.py compare --regions ERCO SOCO FPL --hours 48
python electricity.py compare --regions CISO ISNE NYIS PJM --hours 24
python electricity.py compare --regions PJM MISO ERCO CISO ISNE NYIS SWPP --hours 24
python electricity.py compare --regions PJM MISO ERCO --hours 48 --json
python electricity.py compare --regions ERCO SOCO FPL --hours 72 --json
python electricity.py compare --regions PJM MISO TVA --hours 168 --export csv

# Macro group snapshot
python electricity.py group-snapshot --group big_seven
python electricity.py group-snapshot --group industrial_belt
python electricity.py group-snapshot --group sun_belt
python electricity.py group-snapshot --group tech_corridor
python electricity.py group-snapshot --group industrial_belt --json
python electricity.py group-snapshot --group sun_belt --json
python electricity.py group-snapshot --group tech_corridor --json
python electricity.py group-snapshot --group big_seven --export csv
```

### Metadata (no API key required)

```bash
# List all 14 curated balancing authorities
python electricity.py regions
python electricity.py regions --json

# Show macro group definitions
python electricity.py groups
python electricity.py groups --json
```

### Export

```bash
# Demand
python electricity.py export --target demand --region PJM --hours 168 --format csv
python electricity.py export --target demand --region ERCO --hours 48 --format json

# Generation
python electricity.py export --target generation --region MISO --hours 48 --format csv
python electricity.py export --target generation --region CISO --hours 168 --format json

# Interchange
python electricity.py export --target interchange --from PJM --to NYIS --hours 48 --format csv
python electricity.py export --target interchange --from MISO --to TVA --hours 24 --format json

# Fuel mix
python electricity.py export --target fuel-mix --region CISO --hours 24 --format csv
python electricity.py export --target fuel-mix --region ERCO --hours 48 --format json

# Daily history
python electricity.py export --target demand-history --region PJM --days 14 --format csv
python electricity.py export --target demand-history --region ERCO --days 30 --format json

# Peak
python electricity.py export --target peak --region PJM --days 7 --format csv
python electricity.py export --target peak --region CISO --days 14 --format json

# Snapshot
python electricity.py export --target snapshot --format csv
python electricity.py export --target snapshot --format json

# Group snapshot
python electricity.py export --target group-snapshot --group industrial_belt --format csv
python electricity.py export --target group-snapshot --group sun_belt --format json
python electricity.py export --target group-snapshot --group tech_corridor --format csv
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output for programmatic consumption | All commands except `export` |
| `--export csv` | Export to CSV file | demand, generation, interchange, fuel-mix, demand-history, peak, snapshot, compare, group-snapshot |
| `--export json` | Export to JSON file | Same as above |
| `--region CODE` | Balancing authority code | demand, generation, fuel-mix, demand-history, peak, export |
| `--hours N` | Hourly lookback window | demand, generation, fuel-mix, interchange, compare, export |
| `--days N` | Day-based lookback window | demand-history, peak, export |
| `--from CODE` | Interchange source BA | interchange, export |
| `--to CODE` | Interchange destination BA | interchange, export |
| `--regions CODE [CODE ...]` | Multi-region list | compare |
| `--group KEY` | Macro group key | group-snapshot, export |
| `--target NAME` | Export target | export |
| `--format csv\|json` | File format | export |


## Python Recipes

### Demand

```python
from electricity import cmd_demand, cmd_demand_history, cmd_peak

# Hourly demand strip
# Returns: list of dicts with period, respondent, type, value (MWh)
pjm_24h = cmd_demand(region="PJM", hours=24, as_json=True)
erco_48h = cmd_demand(region="ERCO", hours=48, as_json=True)
ciso_168h = cmd_demand(region="CISO", hours=168, as_json=True)
miso_72h = cmd_demand(region="MISO", hours=72, as_json=True)
isne_48h = cmd_demand(region="ISNE", hours=48, as_json=True)
nyis_24h = cmd_demand(region="NYIS", hours=24, as_json=True)
tva_48h = cmd_demand(region="TVA", hours=48, as_json=True)
soco_24h = cmd_demand(region="SOCO", hours=24, as_json=True)
bpat_72h = cmd_demand(region="BPAT", hours=72, as_json=True)

# Daily demand totals with intraday peaks
# Returns: list of dicts with date, total, count, peak, peak_hour
pjm_7d = cmd_demand_history(region="PJM", days=7, as_json=True)
pjm_21d = cmd_demand_history(region="PJM", days=21, as_json=True)
erco_14d = cmd_demand_history(region="ERCO", days=14, as_json=True)
ciso_30d = cmd_demand_history(region="CISO", days=30, as_json=True)

# Peak demand analysis
# Returns: dict with region, peak_mwh, peak_period, avg_mwh, peak_vs_avg_pct
pjm_peak = cmd_peak(region="PJM", days=7, as_json=True)
erco_peak = cmd_peak(region="ERCO", days=7, as_json=True)
ciso_peak = cmd_peak(region="CISO", days=5, as_json=True)
isne_peak = cmd_peak(region="ISNE", days=7, as_json=True)
```

### Generation & Fuel Mix

```python
from electricity import cmd_generation, cmd_fuel_mix

# Hourly generation by fuel type
# Returns: list of dicts with period, respondent, fueltype, type-name, value (MWh)
ciso_gen = cmd_generation(region="CISO", hours=168, as_json=True)
erco_gen = cmd_generation(region="ERCO", hours=48, as_json=True)
pjm_gen = cmd_generation(region="PJM", hours=72, as_json=True)
miso_gen = cmd_generation(region="MISO", hours=48, as_json=True)
bpat_gen = cmd_generation(region="BPAT", hours=72, as_json=True)

# Fuel mix at latest hour in window
# Returns: list of dicts filtered to latest period, with fueltype + value
ciso_mix = cmd_fuel_mix(region="CISO", hours=24, as_json=True)
erco_mix = cmd_fuel_mix(region="ERCO", hours=24, as_json=True)
pjm_mix = cmd_fuel_mix(region="PJM", hours=24, as_json=True)
miso_mix = cmd_fuel_mix(region="MISO", hours=48, as_json=True)
isne_mix = cmd_fuel_mix(region="ISNE", hours=24, as_json=True)
bpat_mix = cmd_fuel_mix(region="BPAT", hours=24, as_json=True)
```

### Interchange

```python
from electricity import cmd_interchange

# Hourly interchange flow between two BAs
# Returns: list of dicts with period, fromba, toba, value (MWh, positive = from -> to)
pjm_nyis = cmd_interchange(from_ba="PJM", to_ba="NYIS", hours=48, as_json=True)
pjm_miso = cmd_interchange(from_ba="PJM", to_ba="MISO", hours=24, as_json=True)
erco_swpp = cmd_interchange(from_ba="ERCO", to_ba="SWPP", hours=24, as_json=True)
ciso_bpat = cmd_interchange(from_ba="CISO", to_ba="BPAT", hours=72, as_json=True)
isne_nyis = cmd_interchange(from_ba="ISNE", to_ba="NYIS", hours=48, as_json=True)
miso_tva = cmd_interchange(from_ba="MISO", to_ba="TVA", hours=24, as_json=True)
soco_tva = cmd_interchange(from_ba="SOCO", to_ba="TVA", hours=48, as_json=True)
```

### Snapshots & Comparisons

```python
from electricity import cmd_snapshot, cmd_compare, cmd_group_snapshot

# Big 7 latest-hour demand snapshot
# Returns: list of dicts with region, value (MWh), period
snap = cmd_snapshot(as_json=True)

# Multi-region demand comparison
# Returns: dict keyed by region -> list of hourly demand dicts
industrial = cmd_compare(regions=["PJM", "MISO", "TVA"], hours=168, as_json=True)
sunbelt = cmd_compare(regions=["ERCO", "SOCO", "FPL"], hours=48, as_json=True)
tech = cmd_compare(regions=["CISO", "ISNE", "NYIS", "PJM"], hours=24, as_json=True)
all_big7 = cmd_compare(regions=["PJM", "MISO", "ERCO", "CISO", "ISNE", "NYIS", "SWPP"], hours=24, as_json=True)

# Macro group snapshot (latest demand per region in group)
# Returns: list of dicts with region, value (MWh), period
ind = cmd_group_snapshot(group="industrial_belt", as_json=True)
sun = cmd_group_snapshot(group="sun_belt", as_json=True)
tech = cmd_group_snapshot(group="tech_corridor", as_json=True)
big7 = cmd_group_snapshot(group="big_seven", as_json=True)
```

### Metadata

```python
from electricity import cmd_regions, cmd_groups

# All 14 curated balancing authorities
# Returns: dict keyed by BA code -> {name, area, states}
regions = cmd_regions(as_json=True)

# Macro group definitions
# Returns: dict keyed by group key -> {label, regions[]}
groups = cmd_groups(as_json=True)
```


## Composite Recipes

### Industrial Activity Pulse

```bash
python electricity.py compare --regions PJM MISO TVA --hours 168 --json
```

PRISM receives: hourly demand for 3 industrial-belt grids over 1 week, totals and averages per region for week-over-week comparison.

```bash
python electricity.py demand-history --region PJM --days 21 --json
```

PRISM receives: daily demand totals and peak hours for PJM over 3 weeks, smoothing hourly noise into daily trend.

```bash
python electricity.py group-snapshot --group industrial_belt --json
python electricity.py group-snapshot --group sun_belt --json
```

PRISM receives: latest demand for industrial belt (PJM+MISO+TVA) and sun belt (ERCO+SOCO+FPL) for cross-group divergence.

### Energy Transition Monitor

```bash
python electricity.py fuel-mix --region CISO --hours 72 --json
python electricity.py fuel-mix --region ERCO --hours 72 --json
python electricity.py fuel-mix --region PJM --hours 72 --json
```

PRISM receives: fuel mix percentages (COL, NG, NUC, SUN, WND, WAT, OIL, OTH) for 3 regions at different transition stages.

```bash
python electricity.py generation --region CISO --hours 168 --json
```

PRISM receives: hourly generation by fuel over full week showing daily shape (solar ramp, gas fill, wind variability).

### Regional Divergence Check

```bash
python electricity.py group-snapshot --group industrial_belt --json
python electricity.py group-snapshot --group sun_belt --json
python electricity.py group-snapshot --group tech_corridor --json
```

PRISM receives: latest demand for all 3 sector-grouped macro regions, enabling industrial vs sun belt vs tech corridor comparison.

### Grid Stress Assessment

```bash
python electricity.py peak --region PJM --days 7 --json
python electricity.py peak --region ERCO --days 7 --json
```

PRISM receives: peak hour, peak MWh, average MWh, and peak-vs-average premium for 2 major grids.

```bash
python electricity.py demand-history --region PJM --days 14 --json
```

PRISM receives: 2-week daily totals and peaks showing sustained vs one-off stress.

```bash
python electricity.py interchange --from PJM --to NYIS --hours 48 --json
```

PRISM receives: 48h power flow between PJM and NYIS (positive = export, net imports = region is short).

### Broad Activity Snapshot

```bash
python electricity.py snapshot --json
```

PRISM receives: latest demand for all 7 major RTOs/ISOs in one call.

```bash
python electricity.py group-snapshot --group industrial_belt --json
```

PRISM receives: manufacturing-sensitive demand (PJM+MISO+TVA) as the industrial component.

### Full Region Deep Dive

```bash
python electricity.py demand --region PJM --hours 168 --json
python electricity.py demand-history --region PJM --days 14 --json
python electricity.py peak --region PJM --days 7 --json
python electricity.py fuel-mix --region PJM --hours 72 --json
python electricity.py generation --region PJM --hours 168 --json
```

PRISM receives: hourly demand strip, daily aggregation with peaks, peak analysis, fuel mix snapshot, and full generation-by-fuel breakdown for one region.


## Cross-Source Recipes

### Electricity + CFTC Energy Positioning

```bash
python electricity.py snapshot --json
python projects/apis/cftc/cftc.py energy --json
```

PRISM receives: Big 7 real-time demand + net speculative energy futures positioning. Physical load vs market bets.

### Electricity + EIA Petroleum/Gas

```bash
python electricity.py fuel-mix --region ERCO --hours 72 --json
python electricity.py fuel-mix --region CISO --hours 72 --json
# Pair with EIA petroleum/gas data for physical supply context
```

PRISM receives: grid-level gas/coal/renewable generation share alongside physical fuel supply balances.

### Electricity + Prediction Markets

```bash
python electricity.py snapshot --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: real-time grid demand + policy probability surface. Activity pulse meets rate expectations.

### Electricity + GDELT Narrative

```bash
python electricity.py group-snapshot --group industrial_belt --json
python projects/apis/gdelt/gdelt.py search --query "power grid" --json
```

PRISM receives: industrial demand levels + media narrative intensity on grid/energy events.

### Electricity + Treasury Fiscal Flow

```bash
python electricity.py group-snapshot --group industrial_belt --json
python electricity.py group-snapshot --group sun_belt --json
python projects/apis/treasury/treasury.py get dts --json
```

PRISM receives: regional demand divergence + TGA cash flows for fiscal drain/release alongside physical activity.

### Electricity + Congress Energy Legislation

```bash
python electricity.py fuel-mix --region CISO --hours 72 --json
python electricity.py fuel-mix --region PJM --hours 72 --json
python projects/apis/congress/congress.py search --query "energy" --json
```

PRISM receives: current fuel mix percentages + active energy legislation pipeline (tax credits, permitting, reliability mandates).


## Setup

1. Register for a free EIA API key: https://www.eia.gov/opendata/register.php
2. `export EIA_API_KEY=your_key_here`
3. `pip install requests`
4. Test metadata: `python electricity.py regions`
5. Test live: `python electricity.py snapshot`


## Architecture

```
electricity.py
  Constants       BASE_URL, API_KEY, REGIONS (14), FUEL_TYPES (9),
                  MACRO_GROUPS (4: big_seven, industrial_belt, sun_belt, tech_corridor)
  HTTP            _request() with retries, rate limit handling (0.2s between calls)
  Data Fetchers   _fetch_demand, _fetch_generation, _fetch_interchange, _fetch_fuel_mix
  Parsing         _parse_period, _format_mwh, _safe_int, _truncate
  Commands (12)   demand, demand-history, peak, generation, fuel-mix, interchange,
                  snapshot, compare, regions, groups, group-snapshot, export
  Export          _do_export, _export_csv, _export_json (timestamped files beside script)
  Interactive     12-item menu -> interactive wrappers with prompts
  Argparse        12 subcommands, all with --json and --export
```

API endpoints:
```
/electricity/rto/region-data/data/       -> hourly demand by BA (type=D)
/electricity/rto/fuel-type-data/data/    -> hourly generation by fuel type
/electricity/rto/interchange-data/data/  -> hourly interchange between BAs
```
