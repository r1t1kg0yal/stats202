# BIS SDMX Statistics

Sandbox name: `bis_client`
Base URL: `https://stats.bis.org/api/v2`
Auth: None
Transport: GS proxy via `manual_https_request` (Bucket B)
Universe: 29 dataflows, 108 codelists (93 dimension + 15 attribute), 7,280 codes (630 with long-form descriptions, 26 hierarchical codelists), per-flow attribute metadata, per-flow time coverage (first/last period) + series counts, 138 SDMX concepts with descriptions — all embedded; query the ontology BEFORE building a query.

## Triggers

**Primary** — Cross-border banking & shadow banking (LBS locational, CBS consolidated, GLI), credit-to-GDP & credit gaps, debt service ratios, central bank policy rates, effective exchange rates (REER/NEER), OTC and exchange-traded derivatives, residential & commercial property prices, long-run CPI series, debt securities issuance, eurodollar / FCY mismatch, bank nationality, offshore-center intermediation, contagion exposure to stressed countries.

**Not for** — US daily/intraday data (FRED), individual US bank Call Reports (FDIC), company fundamentals (SEC EDGAR), US fiscal cash flows (Treasury), OIS/swap volumes (DTCC), futures positioning (CFTC), prediction-market probabilities. BIS is mostly quarterly / monthly with 3-6 month publication lag.

## Universe at a Glance

29 dataflows, embedded in `bis_client._DATAFLOWS`. Use `bis_client.list_dataflows()` to enumerate at runtime with full coverage data; this table is the static cheat-sheet.

| Flow ID | Alias | Name | Freq | Dims | Coverage |
|---|---|---|---|---|---|
| `WS_LBS_D_PUB` | `lbs` | Locational banking | Q | 12 | 1977-Q4 → |
| `WS_CBS_PUB` | `cbs` | Consolidated banking | Q | 11 | 1983-Q4 → |
| `WS_TC` | `credit` / `total-credit` | Total credit to non-financial sector | Q | 7 | 1947-Q4 → |
| `WS_CREDIT_GAP` | `credit-gap` | Credit-to-GDP gaps | Q | 5 | 1957-Q4 → |
| `WS_DSR` | `dsr` | Debt service ratios | Q | 3 | 1999-Q1 → |
| `WS_CBPOL` | `policy-rates` | Central bank policy rates | M | 2 | 1954-07 → |
| `WS_CBTA` | `central-bank-assets` | Central bank total assets | Q | 6 | 1914-11 → |
| `WS_EER` | `eer` / `fx` | Effective exchange rates | M | 4 | 1994-01 → |
| `WS_XRU` | `exchange-rates` | US dollar exchange rates | M | 4 | 1949-01 → |
| `WS_GLI` | `liquidity` / `global-liquidity` | Global liquidity indicators | Q | 8 | 2000-Q1 → |
| `WS_SPP` | `property` / `property-prices` | Selected residential property prices | Q | 4 | 1970-Q1 → |
| `WS_DPP` | `detailed-property` | Detailed residential property prices | Q | 8 | 1963-Q1 → |
| `WS_CPP` | `commercial-property` | Commercial property prices | Q | 8 | 1945-Q4 → |
| `WS_LONG_CPI` | `cpi` / `consumer-prices` | Consumer prices long series | M | 3 | 1913-01 → |
| `WS_XTD_DERIV` | `etd` / `exchange-traded-deriv` | Exchange-traded derivatives | Q | 6 | 1993-Q1 → |
| `WS_OTC_DERIV2` | `otc` / `otc-derivatives` | OTC derivatives outstanding | H | 14 | 1998-S1 → |
| `WS_DER_OTC_TOV` | `otc-turnover` | OTC derivatives turnover | A | 14 | 1986 → |
| `WS_DEBT_SEC2_PUB` | `debt-securities` / `international-debt` | Debt securities statistics | Q | 15 | 1966-Q1 → |
| `WS_NA_SEC_DSS` | `national-debt` / `national-securities` | National debt securities stats | Q | 18 | 1951-Q4 → |
| `WS_NA_SEC_C3` | — | BIS debt securities stats | Q | 18 | (BIS-published-but-empty) |
| `BIS_REL_CAL` | `release-calendar` | Release calendar | Q | 3 | 2023-Q1 → |
| `WS_CPMI_*` (6 flows) | `cpmi-*` | CPMI payment systems | A | varies | 2012 → |

The `cbs-*`, `lbs-*`, `gli-*` namespaces are NOT separate dataflows — they are query patterns against `WS_CBS_PUB`, `WS_LBS_D_PUB`, `WS_GLI`.

Note: `WS_IDS_PUB` is retired by BIS (now part of `WS_DEBT_SEC2_PUB`); the alias `international-debt` redirects accordingly.

## Discovery Workflow (the kwarg-first model)

PRISM never has to memorize 12-position SDMX keys. The wrapper exposes the entire ontology and translates kwargs → keys with codelist validation at the boundary.

```python
# 1. WHAT exists?
flows = bis_client.list_dataflows(search="liquidity")
# → [{"flow_id": "WS_GLI", "name": "Global liquidity indicators", ...}]

# 2. WHAT dims does this flow have?
schema = bis_client.get_dataflow("lbs")
# → {"flow_id": "WS_LBS_D_PUB", "dimensions": [
#       {"id": "FREQ", "position": 1, "codelist_id": "CL_FREQ", ...},
#       ...12 dimensions...
#    ], "key_template": "FREQ.L_MEASURE.L_POSITION...."}

# 3. WHAT codes are valid for a dimension?
codes = bis_client.get_codelist("CL_L_POSITION")
# → {"codes": {"C": "Total claims", "L": "Total liabilities", "I": ...}}

# 4. SEARCH for codes by keyword (handles diacritics: turkey ↔ türkiye)
matches = bis_client.search_codes("turkey", cl_id="CL_BIS_IF_REF_AREA")
# → [{"code_id": "TR", "name": "Türkiye"}]

# 5. WHICH flows can answer this question?  (cross-flow discovery)
bis_client.find_dataflows_with_dim("L_REP_CTY")
# → ["WS_LBS_D_PUB", "WS_CBS_PUB"]
bis_client.find_dataflows_with_code("TR")
# → 9 flows where Türkiye is a valid value somewhere in the schema

# 6. PROBE availability BEFORE querying
avail = bis_client.check_availability(
    "lbs", FREQ="Q", L_REP_CTY="US", L_POSITION="C",
    L_PARENT_CTY="5J", L_REP_BANK_TYPE="A",
    L_CP_SECTOR="A", L_CP_COUNTRY="5J", L_POS_TYPE="N",
    L_MEASURE="S", L_INSTR="A", L_CURR_TYPE="A"
)
# → {"series_count": 14, "ok": True,
#    "available_codes": {"L_DENOM": ["CHF", "EUR", "GBP", "JPY", "TO1", "TO3", "UN9"]}}
# Note: USD is NOT in L_DENOM for US reporter (BIS quirk — see Format quirks).

# 7. QUERY using kwargs (wrapper builds key, validates codes)
series = bis_client.query(
    "lbs", FREQ="Q", L_MEASURE="S", L_POSITION="C",
    L_INSTR="A", L_DENOM="TO1", L_CURR_TYPE="A",
    L_PARENT_CTY="5J", L_REP_BANK_TYPE="A", L_REP_CTY="US",
    L_CP_SECTOR="A", L_CP_COUNTRY="5J", L_POS_TYPE="N",
    start="2020"
)

# OR — bootstrap any flow with one call using curated defaults:
series = bis_client.query_default("lbs", start="2020")
# returns the canonical "show me US cross-border claims" slice.
# Verified working live for 28 of 29 dataflows.
# Override individual kwargs as needed:
series = bis_client.query_default("policy-rates", REF_AREA="JP", start="2020")
```

`build_key(...)` raises `ValueError` with up-to-8 valid-code samples and a `get_codelist(...)` pointer if PRISM passes an unknown code. `check_availability(...)` returns `{series_count: 0, ok: False}` (not a 404) when nothing exists for that key shape. `query_default(...)` is the fastest path when PRISM just wants a canonical slice without thinking about dim values.

### Hierarchical codelists, attributes, descriptions

26 codelists are hierarchical (parent-child relations). `CL_DER_INSTR` is the deepest (depth 5: All → Forwards+swaps → Outright forwards / FX swaps → Outright forwards → Non-deliverable forwards). Use:

```python
# Drill down a hierarchy
tree = bis_client.get_code_hierarchy("CL_DER_INSTR")
# → {roots: ["A", "F", "O", "P", "U"], depth: 5,
#    tree: {code_id: {name, parent, children}, ...}}

# Long-form description (630 codes have one beyond their name)
cl = bis_client.get_codelist("CL_OBS_STATUS", detail="full")
# → codes is {code_id: {name, parent?, desc?}}

# Per-flow attributes (returned alongside each observation)
attrs = bis_client.get_attributes("lbs")
# → 11 attribute defs: OBS_STATUS, OBS_CONF, AVAILABILITY, COLLECTION,
#                      DECIMALS, UNIT_MULT, AGG_EQUN, ...

# Decode an attribute value at runtime
meta = bis_client.interpret_attribute("OBS_STATUS", "F")
# → {name: "Forecast value", desc: "Value deemed to assess the magnitude
#    which a quantity will assume at some future time"}
```

When PRISM gets back `series[i]["attributes"]` like `{"OBS_STATUS": "F", "DECIMALS": "2"}`, `interpret_attribute()` is the helper to surface "this is a forecast value" / "rounded to 2 decimals" rather than leaving raw codes.

### Time coverage + series counts (per-flow metadata)

Every dataflow's `get_dataflow()` and `list_dataflows()` output includes:

| Field | Meaning |
|---|---|
| `typical_freq` | "Q" / "M" / "A" / "H" — the publication frequency to use |
| `series_count` | total series in the flow (608k for LBS, 228k for CBS, ~50 for DSR) |
| `first_period` | earliest period in the BIS publication (LBS: 1977-Q4, CPI: 1913-01) |
| `last_period` | latest period as of last `refresh_ontology()` |

Use these to know if a flow has data for your target period BEFORE issuing a query. e.g. `get_dataflow("WS_DSR")["first_period"]` → `"1999-Q1"` — don't ask for DSR pre-1999.

`list_dataflows(frequency="M")` filters to monthly flows: `WS_CBPOL`, `WS_EER`, `WS_LONG_CPI`, `WS_XRU`. The other 25 flows are quarterly / annual / half-yearly.

`describe(flow_id)` renders all of this as a markdown summary line: `DSD: BIS_LBS_DISS v1.0    Dimensions: 12    Frequency: Q    Series: 608,570    Coverage: 1977-Q4 → 2025-Q4`.

### Concepts (semantic backbone)

`get_concept(concept_id)` returns the SDMX concept's name + description for the 138 concepts that carry one (the rest are empty stubs). Useful when PRISM hits an unfamiliar dim_id and wants the formal SDMX semantic — `get_concept("MARKET_ISSUE")` → `{name: "Market Issue", desc: "Market of issuance"}`.

## Decision Table — which dataflow for which question?

| Question | Dataflow | Key dims |
|---|---|---|
| Where do US banks lend cross-border? Where in offshore centers does the eurodollar sit? | `WS_LBS_D_PUB` (`lbs`) | `L_REP_CTY`, `L_CP_COUNTRY`, `L_DENOM`, `L_CP_SECTOR` |
| What's the country-risk exposure of European banks to Türkiye on a guarantor basis? | `WS_CBS_PUB` (`cbs`) | `L_REP_CTY`, `CBS_BASIS=U`, `L_CP_COUNTRY`, `L_POSITION=C` |
| What's the Fed/BoE/BoJ policy rate? | `WS_CBPOL` (`policy-rates`) | `FREQ=M`, `REF_AREA` |
| Which countries are in a credit boom (gap > 10pp)? | `WS_CREDIT_GAP` (`credit-gap`) | `BORROWERS_CTY`, `TC_BORROWERS=P`, `CG_DTYPE=C` |
| Which households / corps have unsustainable debt service? | `WS_DSR` (`dsr`) | `BORROWERS_CTY`, `DSR_BORROWERS` |
| How leveraged is China vs the US? | `WS_TC` (`credit`) | `BORROWERS_CTY`, `TC_BORROWERS=P`, `UNIT_TYPE=770` (% of GDP) |
| Is the dollar overvalued? Real vs nominal effective? | `WS_EER` (`eer`) | `EER_TYPE=R/N`, `EER_BASKET=B/N`, `REF_AREA` |
| Global USD liquidity to non-banks outside US | `WS_GLI` (`liquidity`) | `CURR_DENOM=USD`, `BORROWERS_CTY=3P/4T/...`, `BORROWERS_SECTOR=N` |
| House prices in 9 advanced economies | `WS_SPP` (`property`) | `REF_AREA`, `VALUE=N/R` |
| Office vs retail commercial real estate prices | `WS_CPP` (`commercial-property`) | `REF_AREA`, `RE_TYPE=B/C/G` |
| OTC interest rate swap notional outstanding | `WS_OTC_DERIV2` (`otc`) | `DER_TYPE=A`, `DER_RISK=C`, `DER_INSTR=G` |
| What's coming in the next BIS data release? | `BIS_REL_CAL` (`release-calendar`) | (browse) |

## Schemas (per-flow dimension quick-reference)

The wrapper validates everything against the embedded codelist. These tables list the most common codes — pass the dim id verbatim as a kwarg to `query()` or `build_key()`. Use `get_codelist(<cl_id>)` for the full enumeration.

### `WS_LBS_D_PUB` — Locational Banking Statistics (12 dims)

**Universe:** 158k+ series. 50 reporting countries × 226 counterparties × 12 dimensions of breakdown.

| Pos | Dim | Codelist | Common codes |
|---|---|---|---|
| 1 | `FREQ` | CL_FREQ | `Q`=Quarterly (use this) |
| 2 | `L_MEASURE` | CL_STOCK_FLOW | `S`=Stocks, `F`=FX-adjusted flow, `G`=YoY growth |
| 3 | `L_POSITION` | CL_L_POSITION | `C`=Total claims, `L`=Total liabilities, `D`=Cross-border claims, `I`=International claims, `N`=Net |
| 4 | `L_INSTR` | CL_L_INSTR | `A`=All, `G`=Loans+deposits, `D`=Debt securities, `B`=Credit (loans+debt), `V`=Derivatives, `N`=Repo |
| 5 | `L_DENOM` | CL_CURRENCY_3POS | `TO1`=All currencies, `USD`/`EUR`/`GBP`/`JPY`/`CHF`, `TO3`=Foreign-only, `UN9`=Unallocated |
| 6 | `L_CURR_TYPE` | CL_L_CURR_TYPE | `A`=All, `D`=Domestic ccy, `F`=Foreign ccy, `U`=Unclassified — see Format quirks |
| 7 | `L_PARENT_CTY` | CL_BIS_IF_REF_AREA | `5J`=All parent countries (most common), or specific ISO for bank-nationality slice |
| 8 | `L_REP_BANK_TYPE` | CL_L_BANK_TYPE | `A`=All banks, `D`=Domestic, `B`=Foreign branches, `S`=Foreign subsidiaries |
| 9 | `L_REP_CTY` | CL_BIS_IF_REF_AREA | 50 reporters: US, GB, JP, DE, FR, CH, HK, SG, KY, LU, IE, ... `5A`=All, `5C`=Euro area |
| 10 | `L_CP_SECTOR` | CL_L_SECTOR | `A`=All, `B`=Banks, `N`=Non-banks, `F`=NBFI, `C`=Non-fin corps, `G`=Govt, `H`=Households, `I`=Related offices |
| 11 | `L_CP_COUNTRY` | CL_BIS_IF_REF_AREA | 226 ISOs, `5J`=All, `5C`=Euro area, `4T`=EM aggregate |
| 12 | `L_POS_TYPE` | CL_L_POS_TYPE | `N`=Cross-border, `R`=Local, `I`=Cross-border+Local FCY, `A`=All |

### `WS_CBS_PUB` — Consolidated Banking Statistics (11 dims)

**Universe:** 178k+ series. Aggregates by bank NATIONALITY (HQ) rather than location. Captures ultimate-risk exposure on a guarantor basis.

| Pos | Dim | Codelist | Common codes |
|---|---|---|---|
| 1 | `FREQ` | CL_FREQ | `Q` |
| 2 | `L_MEASURE` | CL_STOCK_FLOW | `S` |
| 3 | `L_REP_CTY` | CL_BIS_IF_REF_AREA | 33 CBS reporters; `5A`=All |
| 4 | `CBS_BANK_TYPE` | CL_BIS_IF_REF_AREA | `4R`=Domestic banks (excl domestic positions) — most common, `4B`=All domestic, `4M`=All banks |
| 5 | `CBS_BASIS` | CL_CBS_BASIS | `F`=Immediate counterparty, `U`=Guarantor, `R`=F+Q, `O`=Outward risk transfers, `P`=Inward, `Q`=Net transfers |
| 6 | `L_POSITION` | CL_L_POSITION | F basis: `I`=International claims (the canonical broad measure). U basis: `C`=Total claims (the equivalent on guarantor) |
| 7 | `L_INSTR` | CL_L_INSTR | `A`=All, `D`=Debt, `G`=Loans, `V`=Derivatives |
| 8 | `REM_MATURITY` | CL_ISSUE_MAT | `A`=All, `U`=Up to 1y, `M`=Over 1-2y, `N`=Over 2y |
| 9 | `CURR_TYPE_BOOK` | CL_CURRENCY_3POS | `TO1`=All |
| 10 | `L_CP_SECTOR` | CL_L_SECTOR | `A`=All, `B`=Banks, `F`=NBFI, `C`=Corps, `H`=Households, `O`=Official, `R`=Non-bank private |
| 11 | `L_CP_COUNTRY` | CL_BIS_IF_REF_AREA | 252 counterparties |

### `WS_GLI` — Global Liquidity Indicators (8 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 1 | `FREQ` | `Q` |
| 2 | `CURR_DENOM` | `USD`, `EUR`, `JPY`, `TO1` |
| 3 | `BORROWERS_CTY` | `3P`=All non-resident (global), `4T`=EM, `4U`/`4W`/`4Y`=Regional EM, individual ISOs |
| 4 | `BORROWERS_SECTOR` | `N`=Non-banks (most common), `G`=Govt, `P`=Non-financial |
| 5 | `LENDERS_SECTOR` | `A`=All, `B`=Banks |
| 6 | `L_POS_TYPE` | `I`=Cross-border + Local FCY (most common), `A`=All |
| 7 | `L_INSTR` | `B`=Total credit, `G`=Bank loans, `D`=Debt securities |
| 8 | `UNIT_MEASURE` | `USD`/`EUR`/`JPY` (outstanding), `771`=YoY growth %, `770`=% of GDP |

### `WS_TC` — Total Credit to Non-Financial Sector (7 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 1 | `FREQ` | `Q` |
| 2 | `BORROWERS_CTY` | US, GB, JP, DE, CN, ... `XM`=Euro area, `5R`=Advanced, `4T`=EM, `G2`=G20 |
| 3 | `TC_BORROWERS` | `P`=Private non-financial, `C`=Non-financial sector, `G`=Govt, `H`=Households, `N`=Non-financial corps |
| 4 | `TC_LENDERS` | `A`=All sectors, `B`=Banks domestic |
| 5 | `VALUATION` | `M`=Market, `N`=Nominal |
| 6 | `UNIT_TYPE` | `XDC`=Domestic ccy, `USD`, `770`=% of GDP |
| 7 | `TC_ADJUST` | `A`=Adjusted for breaks, `0`=NSA, `1`=SA |

### `WS_CREDIT_GAP` — Credit-to-GDP Gaps (5 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 2 | `BORROWERS_CTY` | 239 countries/aggregates |
| 3 | `TC_BORROWERS` | `P`=Private non-financial (most common) |
| 5 | `CG_DTYPE` | `A`=Credit-to-GDP ratio, `B`=Trend (HP filter), `C`=Gap (actual − trend) |

> **Interpretation:** gap > +10pp = BIS warning threshold (overheating); gap > +20pp = extreme; deeply negative (< −10pp) = deleveraging.

### `WS_DSR` — Debt Service Ratios (3 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 2 | `BORROWERS_CTY` | 101 countries |
| 3 | `DSR_BORROWERS` | `P`=Private non-financial, `H`=Households, `N`=Non-fin corps |

### `WS_CBPOL` — Central Bank Policy Rates (2 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 1 | `FREQ` | `M`=Monthly |
| 2 | `REF_AREA` | 239 central banks; pass `+`-joined: `US+GB+JP+DE+CH` |

### `WS_EER` — Effective Exchange Rates (4 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 2 | `EER_TYPE` | `R`=Real, `N`=Nominal |
| 3 | `EER_BASKET` | `B`=Broad (64 economies), `N`=Narrow (27) |
| 4 | `REF_AREA` | 101 countries |

### `WS_OTC_DERIV2` — OTC Derivatives Outstanding (14 dims)

| Pos | Dim | Common codes |
|---|---|---|
| 1 | `FREQ` | `H`=Half-yearly |
| 2 | `DER_TYPE` | `A`=Notional, `B`=Gross positive MV, `D`=Gross MV, `H`=Gross credit exposure |
| 3 | `DER_INSTR` | `A`=All, `B`=FX incl gold, `C`=Forwards+swaps, `G`=IR swaps, `S`=CDS |
| 4 | `DER_RISK` | `A`=All, `B`=FX, `C`=Interest rate, `D`=Equity, `Y`=Credit |
| 6 | `DER_SECTOR_CPY` | `A`=All, `B`=Reporting dealers, `C`=Other financial, `K`=CCPs, `R`=Other customers, `U`=Non-financial |

(Wildcard the rest with empty kwargs; see `get_dataflow("otc")` for full schema.)

## Format quirks (the wrapper absorbs most; PRISM should know the rest)

The new universe-first design either eliminates these gotchas or surfaces them via `check_availability()`. They're documented here for situations where PRISM is interpreting a result.

| Quirk | What | Wrapper behavior |
|---|---|---|
| **L_DENOM ≠ reporter's domestic ccy** (LBS) | BIS does NOT publish individual-currency LBS breakdowns when the currency equals the reporter's domestic ccy. Querying `L_DENOM=USD, L_REP_CTY=US` returns 404. The aggregate `TO1` (all currencies) DOES include domestic. | `recipe_currency_breakdown(reporter, ...)` picks the right `L_CURR_TYPE` per (reporter, currency) automatically using the embedded `_REPORTER_DOMESTIC_CCY` map. For raw `query()`, probe with `check_availability()` first. |
| **L_POSITION on CBS basis F vs U** | F basis publishes `L_POSITION=I` (International claims). U basis does NOT — use `L_POSITION=C` (Total claims) instead. | `recipe_contagion(target)` picks the right L_POSITION per basis. |
| **Türkiye / native names** | BIS country names use native Unicode (`Türkiye`, not `Turkey`; `Côte d'Ivoire`; `Curaçao`). | `search_codes("turkey")` matches `Türkiye` via diacritic folding + an alias map (also handles UK / US / UAE / Macau / Czech Republic / Myanmar). |
| **Date period formats** | BIS accepts `YYYY`, `YYYY-Q1..Q4`, `YYYY-MM`, `YYYY-MM-DD`. Frequency mismatch returns 404. | Pass any of these as `start=` / `end=`. |
| **L_PARENT_CTY breakdowns** (LBS) | Per-host-country bank-nationality breakdowns are NOT publicly disclosed; only `L_REP_CTY=5A` (all reporters aggregate) × specific `L_PARENT_CTY` is published. Querying a specific (host, parent) pair often 404s. | Use `L_REP_CTY="5A"` when slicing by `L_PARENT_CTY`. |
| **Bilateral redactions** (LBS) | BIS redacts many specific (reporter × counterparty) bilateral cells for confidentiality, especially US-as-counterparty. | `query()` returns `[]` cleanly; use availability + sector / instrument aggregation to triangulate. |
| **OTC frequency** | `WS_OTC_DERIV2` is half-yearly (`FREQ=H`), not quarterly. Period strings are `YYYY-S1` / `YYYY-S2`. | Pass `FREQ="H"`. |
| **CPMI niche** | The 6 `WS_CPMI_*` dataflows cover payment-system stats — annual, ~2-year lag, niche. | Available but rarely the right answer; check competitive overlap with `treasury_client` for US payment data. |

## Composite recipes (multi-query helpers)

22 pre-built multi-query analyses for cross-border / shadow-banking patterns. All return `{start_period, series, summary}` dicts (no print, no file I/O). Five families:

### Cross-flow / cross-cutting

| Recipe | What | Cost |
|---|---|---|
| `recipe_contagion(target, start)` | LBS-locational + CBS-immediate + CBS-guarantor exposure to one target country. `summary["guarantor_minus_immediate"]` > 0 = inward risk transfers. | 3 queries |
| `recipe_shadow_banking_full(start)` | 5-module composite — eurodollar + NBFI cross-sector + USD interbank + offshore centers + FCY mismatch. | ~80-150 queries |
| `recipe_universe_smoke(start)` | Validation harness — runs `query_default()` against every dataflow. | 28-29 queries |

### LBS — Locational Banking (bank-LOCATION basis, 158k+ series)

| Recipe | What | Cost |
|---|---|---|
| `recipe_eurodollar(start, reporters)` | Global USD claims/liabs/growth + per-center FCY positions. Identifies FCY suppliers vs borrowers. | ~30 queries |
| `recipe_nbfi(start, reporters)` | Global NBFI cross-border claims (the canonical "shadow banking" measure). Sectoral breakdown + USD/EUR + per-reporter + YoY growth. | ~30 queries |
| `recipe_interbank(currency, start, reporters)` | Global interbank loans+deposits by currency (repo / money-market proxy) + intra-group flows + per-reporter. | ~25 queries |
| `recipe_offshore_centers(start, centers)` | Per-center deep-dive — total claims/liabs/net + USD share + role label (CREDITOR / DEBTOR). Default 9 systemic centers. | ~30 queries |
| `recipe_bank_nationality(start, parents)` | Cross-border claims by parent HQ country (10 systemic banking nationalities). All-currency + USD slices. | ~20 queries |
| `recipe_currency_breakdown(reporter, currencies, start)` | Per-reporter LBS claims/liabs by currency with `pct_of_total` share. Auto-derives L_CURR_TYPE per (reporter, ccy) pair. | ~16 queries |
| `recipe_fcy_mismatch(reporters, start)` | FCY share of cross-border claims per reporter (FX-vulnerability indicator). | ~28 queries |
| `recipe_sector_matrix(reporter, start)` | For one reporter — counterparty-sector breakdown × (TO1, USD) + instrument decomposition. | ~21 queries |
| `recipe_lbs_exposure_to(target, start, reporters)` | Per-reporter LBS exposure to one target country: aggregate (TO1/USD/EUR) + per-reporter + sectoral breakdown. | ~20 queries |
| `recipe_lbs_bilateral(reporter, counterparty, ccy, sector, ...)` | Single (reporter × counterparty) cell with auto-derived L_CURR_TYPE. | 1 query |
| `recipe_usd_funding(reporter, start)` | USD LIABILITIES (funding side) sectoral breakdown for one reporter. Identifies who provides dollar funding (banks / NBFI / corps / central banks). | ~12 queries |

### CBS — Consolidated Banking (bank-NATIONALITY / HQ basis, 178k+ series)

| Recipe | What | Cost |
|---|---|---|
| `recipe_cbs_foreign_claims(reporter, basis, bank_type, start)` | Foreign claims for one CBS reporter — position breakdown (`I/C/B/M` on F basis; `C/B/D/W/X` on U basis) + sector decomposition. | ~10 queries |
| `recipe_cbs_exposure_to(target, basis, bank_type, start, reporters)` | Aggregate + per-reporter CBS exposure to target country. Use `basis='U'` for ultimate-risk view. | ~14 queries |
| `recipe_cbs_maturity(reporter, basis, bank_type, start)` | Remaining-maturity breakdown (Up to 1y / 1-2y / Over 2y) + computed `short_term_share_pct` (rollover-risk concentration). | 4 queries |
| `recipe_cbs_guarantor_diff(reporter, targets, start)` | Per-target diff between F (immediate) and U (guarantor). Diff > 0 = INWARD_RISK_TRANSFER (parents guaranteeing local subs); diff < 0 = OUTWARD_RISK_TRANSFER. | ~30 queries |

### GLI — Global Liquidity Indicators (currency-indexed)

| Recipe | What | Cost |
|---|---|---|
| `recipe_gli_currency(currency, regions, start)` | Total credit / bank loans / debt securities by region for one currency. Default regions = global (3P) + 4 EM regions (4T/4U/4W/4Y). | ~15 queries |
| `recipe_gli_all_currencies(start)` | USD vs EUR vs JPY trilemma — outstanding in native units + YoY growth for each. | 6 queries |

### Country fundamentals

| Recipe | What | Cost |
|---|---|---|
| `recipe_credit_gap_warnings(threshold, start, countries)` | 42-country panel of credit-to-GDP gaps. Flags WARN (>+10pp) / EXTREME_OVERHEATING (>+20pp) / EXTREME_DELEVERAGE (<−10pp). | ~42 queries |
| `recipe_policy_rate_cycle(countries, start)` | Latest rate, peak/trough, distance from peak, 6mo change, direction (CUTTING / HIKING / ON_HOLD). | per country |

For everything not covered (`property-prices`, `dsr`, `eer`, `cpi`, `total-credit`, `derivatives`, etc.), call `query("flow", FREQ=..., **dim_kwargs)` directly — `query_default(fid)` is the fast bootstrap.

## Output schema (series object)

`query(...)` returns `list[dict]` where each dict is:

```python
{
    "key":          "Q.S.C.A.TO1.A.5J.A.US.A.5J.N",   # SDMX dimension key
    "dimensions":   {DIM_ID: {"id": str, "name": str}, ...},
    "attributes":   {ATTR_ID: str, ...},   # e.g. UNIT_MEASURE = "USD bn"
    "observations": {"2024-Q1": 1234.56, "2024-Q2": ...},  # period → float|None
}
```

Numeric observations are coerced to `float` at the boundary; `None` for missing periods. Periods are strings in the source frequency (`"2024-Q3"`, `"2024-09"`, `"2024"`).

## PRISM ergonomics — pandas conversion + multi-flow alignment

PRISM lives in pandas. These helpers convert series → DataFrame and merge across flows so PRISM doesn't write 10 lines of iteration on every BIS query.

```python
# Tall DataFrame: one row per (series, period); columns include each
# dimension id + period + value
df = bis_client.series_to_dataframe(
    bis_client.query("policy-rates", FREQ="M", REF_AREA="US+GB+JP+DE"),
    value_col="rate"
)
#    FREQ REF_AREA  period   rate
#       M       US 2024-01  5.375
#       M       GB 2024-01  5.250
#       ...

# Wide DataFrame: one column per series, period as index
df_wide = bis_client.series_to_dataframe(series, wide=True)

# Cross-flow alignment: merge multiple flows by period (mixed
# frequencies sit alongside each other; NaN where one isn't observed)
df = bis_client.fetch_aligned([
    {"name": "policy_rate", "flow_id": "policy-rates",
     "kwargs": {"FREQ": "M", "REF_AREA": "US"}},
    {"name": "credit_gap",  "flow_id": "credit-gap",
     "kwargs": {"FREQ": "Q", "BORROWERS_CTY": "US",
                "TC_BORROWERS": "P", "TC_LENDERS": "A", "CG_DTYPE": "C"}},
    {"name": "dsr_pp",      "flow_id": "dsr",
     "kwargs": {"FREQ": "Q", "BORROWERS_CTY": "US", "DSR_BORROWERS": "P"}},
], start="2020")
# → DataFrame with columns ["policy_rate", "credit_gap", "dsr_pp"]
#   indexed by period.

# Latest single observation (with metadata)
result = bis_client.latest("policy-rates", REF_AREA="US")
# → {value: 3.625, period: "2026-04", dimensions: {...},
#    attributes: {...}, flow_id: "WS_CBPOL", key: "M.US"}
```

`series_to_dataframe` and `fetch_aligned` lazy-import pandas (raise `ImportError` with a clear message if pandas is unavailable; PRISM's sandbox always has it).

## When to use BIS vs other PRISM clients

| Question | BIS | Other |
|---|---|---|
| "What's the Fed's current policy rate?" | `bis_client.query("policy-rates", FREQ="M", REF_AREA="US")` (monthly, 1-month lag) | `fred_client` for daily target rate or NY Fed effective |
| "How big is the US bank credit market?" | `bis_client.query("credit", BORROWERS_CTY="US", TC_BORROWERS="P", VALUATION="N", UNIT_TYPE="XDC", TC_ADJUST="A")` (quarterly, structural) | `fred_client TOTBKCR` (weekly, real-time) |
| "Who's exposed to Türkiye?" | `recipe_contagion("TR")` (all reporters, F + U basis) | — |
| "Spanish banks' loans to US corps?" | LBS bilateral with redaction risk | — |
| "House price index for US?" | `bis_client.query("property", FREQ="Q", REF_AREA="US", VALUE="N", UNIT_MEASURE="...")` (BIS-curated, 9 economies) | FRED `CSUSHPISA` for monthly Case-Shiller |
| "Real-time bank deposit data?" | — | `fdic_client` (Call Reports) or `fred_client` |
| "Treasury auction tail?" | — | `treasury_direct_client` |

BIS owns: cross-border banking, structural credit, debt service, BIS-curated property indices, OTC derivatives outstanding, REER. Other PRISM clients own: high-frequency US data, bank-level financials, security-level data.

## Full API surface (49 entries in `bis_client.__all__`)

The complete primitive index — every public function PRISM can call. Organized by purpose; all sections above reference these.

### Discovery (read the embedded ontology)

| Primitive | Returns | Use when |
|---|---|---|
| `list_dataflows(search=, frequency=)` | list of dataflow summaries (with coverage) | "What datasets exist?" / "Which monthly flows are there?" |
| `get_dataflow(fid)` | full schema + coverage + version | "What's the schema for X?" |
| `get_dimensions(fid)` | ordered dim list (sugar over `get_dataflow`) | "What dims does X have?" |
| `get_codelist(cl_id, contains=, detail=)` | codes (string-or-dict) + `is_hierarchical` | "What are valid values for this dim?" |
| `get_code_hierarchy(cl_id)` | parent → children tree + depth | "How do these codes nest?" |
| `get_attributes(fid)` | per-flow attribute defs | "What metadata comes back with each obs?" |
| `interpret_attribute(attr, code, flow_id=)` | `{name, desc}` for an attribute value | "What does OBS_STATUS=F mean?" |
| `get_concept(concept_id)` | SDMX concept name + desc | "What does the concept MARKET_ISSUE mean?" |
| `search_dataflows(keyword)` | sugar over `list_dataflows(search=)` | "Find flows about X" |
| `search_codes(keyword, cl_id=)` | code matches across (or within) codelists | "What's the code for Türkiye?" |
| `describe(fid)` | markdown summary string | "Give me one-glance schema + coverage" |
| `find_dataflows_with_dim(dim_id)` | flow_ids that have this dim | "Which flows share L_REP_CTY?" |
| `find_dataflows_with_code(code, cl_id=)` | flows where this code is valid | "Where can I query Türkiye?" |
| `dimension_cross_reference()` | every dim_id × flows × codelists | "Full xref of all dimensions" |

### Defaults / exemplar query

| Primitive | Returns | Use when |
|---|---|---|
| `get_default_kwargs(fid)` | curated minimal kwargs that work | "What's a working slice for X?" |
| `query_default(fid, **overrides)` | series for the default slice | "Show me something useful from X" |

### Availability + query (the data layer)

| Primitive | Returns | Use when |
|---|---|---|
| `check_availability(fid, key=, **dim)` | series_count + available_codes per dim | Probe BEFORE querying — eliminates silent 404s |
| `build_key(fid, **dim)` | SDMX key string (validates codes) | Manual key construction; raises ValueError on bad codes |
| `query(fid, key=, start=, end=, **dim)` | list of series dicts | Get the data |

### PRISM ergonomics (pandas + multi-flow)

| Primitive | Returns | Use when |
|---|---|---|
| `series_to_dataframe(series, value_col=, wide=)` | pandas DataFrame | Convert series to tidy / wide DataFrame |
| `fetch_aligned(specs, start, end)` | wide DataFrame indexed by period | Cross-flow merge on period |
| `latest(fid, **kwargs)` | dict with most-recent observation + metadata | "What's the current X?" one-liner |

### Composite recipes (22 multi-query analyses)

| Family | Recipes |
|---|---|
| Cross-flow / cross-cutting | `recipe_contagion`, `recipe_shadow_banking_full`, `recipe_universe_smoke` |
| LBS — Locational | `recipe_eurodollar`, `recipe_nbfi`, `recipe_interbank`, `recipe_offshore_centers`, `recipe_bank_nationality`, `recipe_currency_breakdown`, `recipe_fcy_mismatch`, `recipe_sector_matrix`, `recipe_lbs_exposure_to`, `recipe_lbs_bilateral`, `recipe_usd_funding` |
| CBS — Consolidated | `recipe_cbs_foreign_claims`, `recipe_cbs_exposure_to`, `recipe_cbs_maturity`, `recipe_cbs_guarantor_diff` |
| GLI — Global Liquidity | `recipe_gli_currency`, `recipe_gli_all_currencies` |
| Country fundamentals | `recipe_credit_gap_warnings`, `recipe_policy_rate_cycle` |

(Detailed recipe table earlier in this doc.)

### Refresh + constants

| Primitive | What |
|---|---|
| `refresh_ontology(write_to=, probe_coverage=)` | Re-fetch ontology from live BIS; rewrites embedded JSON if `write_to` set. Offline-only — do not call from PRISM sandbox. |
| `BASE_URL`, `BASE_HOST`, `DEFAULT_VERSION`, `DATAFLOW_ALIASES` | Module constants. `DATAFLOW_ALIASES` has 37 entries mapping friendly aliases to flow_ids. |
