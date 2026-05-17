# Credit — CDS, CDX, iTraxx, IG/HY indices, ratings

Spoke fetched on demand from the Bloomberg Excel hub. Covers credit derivatives (single-name CDS, CDX, iTraxx), Bloomberg cash-bond credit indices (HY / IG / leveraged loans), default-probability fields, recovery rates, and credit-curve construction.

For cash-bond fields (yields, OAS, duration) see `bbg_fixed_income.md`. For openpyxl mechanics and BQL grammar, see the hub.

---

## 1. CDX and iTraxx index series

CDS indices roll every 6 months (March and September). Bloomberg keeps both the **generic** (always-on-the-run) ticker and **series-specific** tickers.

### 1.1 North American CDX

| Index | Generic ticker | Series form |
|---|---|---|
| CDX North American IG 5Y | `CDX IG CDSI GEN 5Y Corp` | `CDX IG <NN> 5Y Corp` (NN = series number) |
| CDX North American HY 5Y | `CDX HY CDSI GEN 5Y Corp` | `CDX HY <NN> 5Y Corp` |
| CDX EM 5Y | `CDX EM CDSI GEN 5Y Corp` | `CDX EM <NN> 5Y Corp` |
| CDX IG Investment Grade 10Y | `CDX IG CDSI GEN 10Y Corp` | |
| CDX HY 10Y | `CDX HY CDSI GEN 10Y Corp` | |

The "generic" form auto-rolls to the on-the-run series and is the right pick for time-series work (avoids series-roll discontinuities). The "series form" is for working with a specific series (e.g. roll trades).

### 1.2 European iTraxx

| Index | Generic ticker |
|---|---|
| iTraxx Main 5Y (Europe IG) | `ITRX MAIN CDSI GEN 5Y Corp` |
| iTraxx Crossover 5Y (Europe HY) | `ITRX XOVER CDSI GEN 5Y Corp` |
| iTraxx SubFin 5Y (Subordinated Financials) | `ITRX SUBFIN CDSI GEN 5Y Corp` |
| iTraxx SovX Western Europe 5Y | `ITRX SOVX WE CDSI GEN 5Y Corp` |
| iTraxx Australia 5Y | `ITRX AUS CDSI GEN 5Y Corp` |
| iTraxx Asia ex-Japan IG 5Y | `ITRX EX JAPAN CDSI GEN 5Y Corp` |
| iTraxx Japan 5Y | `ITRX JAPAN CDSI GEN 5Y Corp` |

### 1.3 Key fields on CDX / iTraxx tickers

| Mnemonic | Meaning |
|---|---|
| `PX_LAST` | Spread (bp) for IG indices, price (cents on dollar) for HY |
| `PX_BID` / `PX_ASK` | Bid / ask |
| `CURVE_NAME` | Underlying curve name |
| `CDS_SPREAD_TICKER_5Y` | 5Y reference |
| `SERIES_NUMBER` | Current series |
| `INDX_MEMBERS` | Constituent reference entities |
| `RECOVERY_RATE` | Standard recovery assumption (typically 40% for IG, 30% for HY) |
| `MATURITY` | Index maturity date |
| `COUPON` | Fixed coupon (100bp / 500bp standard for IG / HY) |
| `CDS_FLAT_SPREAD` / `PAR_CDS_SPREAD_*Y` | Flat / par spread |

```python
ws["A3"] = ArrayFormula(
    "A3:C1262",                                                             # 5Y daily + header
    '=_xll.BDH("CDX IG CDSI GEN 5Y Corp,CDX HY CDSI GEN 5Y Corp","PX_LAST",'
    '"-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
```

---

## 2. Single-name CDS

Single-name CDS tickers use the **RED code** convention. RED codes are 6-character identifiers assigned by Markit (e.g. `001020GP` for Apple Inc Sr Unsec USD). PRISM should not invent RED codes — the user looks them up via `CDSW<GO>` on the terminal.

### 2.1 Ticker patterns

| Pattern | Meaning |
|---|---|
| `CT<RED> Corp` | Standard single-name CDS (e.g. `CT001020GP Corp` for Apple SR USD) |
| `CT<RED>JR Corp` | Junior tier |
| `CT<RED>SUB Corp` | Subordinated tier |
| `CT<RED>5Y Corp` | 5Y tenor |
| `<Issuer> CDS <Tenor> Corp` | Issuer-level form (less reliable than RED) |

### 2.2 Single-name CDS fields

Same as CDX above — the field set is shared. Additional single-name specific fields:

| Mnemonic | Meaning |
|---|---|
| `CDS_REF_OBLIGATION` | Reference obligation security |
| `RED_CODE` | RED code |
| `CDS_TIER` | `SR UNSEC` / `SUB` / `JR SUB` |
| `CDS_CURRENCY` | Reference currency (USD, EUR, JPY) |
| `RESTRUCTURING_TYPE` | `MR` (modified) / `MMR` (modified modified) / `XR` (no restructuring) — varies by jurisdiction |

For systematic CDS-curve work, BQL's `cdscurvemembers()` is the right entry point:

```excel
=_xll.BQL.Query("get(name(), maturity(), spread()) for(cdscurvemembers('AAPL US Equity'))")
```

---

## 3. Cash-bond credit indices

### 3.1 US

| Index | Total Return | OAS | Yield-to-Worst |
|---|---|---|---|
| Bloomberg US Corp IG | `LUACTRUU Index` | `LUACOAS Index` | `LUACYW Index` |
| Bloomberg US Corp HY | `LF98TRUU Index` | `LF98OAS Index` | `LF98YW Index` |
| Bloomberg US Corp BBB | `LCB1TRUU Index` (1) | `LCB1OAS Index` | |
| Bloomberg US Corp BB | `LCB2TRUU Index` (2) | `LCB2OAS Index` | |
| Bloomberg US Corp B | `LCB3TRUU Index` (3) | `LCB3OAS Index` | |
| Bloomberg US Corp CCC | `LCB4TRUU Index` (4) | `LCB4OAS Index` | |
| Bloomberg US Aggregate | `LBUSTRUU Index` | `LBUSOAS Index` | `LBUSYW Index` |
| Bloomberg US Treasury | `LUATTRUU Index` | n/a | `LUATYW Index` |
| Bloomberg US MBS | `LUMSTRUU Index` | `LUMSOAS Index` | `LUMSYW Index` |
| Bloomberg US IG Financials | `LF80TRUU Index` | `LF80OAS Index` | |
| Bloomberg US IG Industrials | `LFFITRUU Index` | `LFFIOAS Index` | |
| Bloomberg US IG Utilities | `LFUTTRUU Index` | `LFUTOAS Index` | |

(1)–(4) — Bloomberg's BBB / BB / B / CCC bucket indices; ratings are based on bond-level Bloomberg composite.

### 3.2 EM / Global

| Index | Ticker |
|---|---|
| Bloomberg EM USD Sovereign | `BEUSTRUU Index` (TR) |
| Bloomberg EM USD Corporate | `BEMSCRPI Index` (TR) — varies by install |
| Bloomberg EM Local Currency Bond | `EMLB Index` (TR) |
| JPMorgan EMBI Global Diversified | `JPEIDIVR Index` (TR), `JEMBSORD Index` (spread) |
| JPMorgan EMBI Plus | `JPMECORE Index` |
| JPMorgan CEMBI Broad Diversified | `JBCDCOMP Index` |

### 3.3 European

| Index | Ticker |
|---|---|
| Bloomberg Pan-European IG Corp | `LECPTREU Index` (TR), `LECPOAS Index` (OAS) |
| Bloomberg Pan-European HY | `LP01TREU Index` (TR), `LP01OAS Index` (OAS) |
| iBoxx EUR Corp | `IBXXEEHY Index` family |
| iBoxx EUR HY | `IBXXEHYI Index` |

### 3.4 Leveraged loans

| Index | Ticker |
|---|---|
| S&P / LSTA US Leveraged Loan | `SPBDAL Index` (TR) |
| Morningstar LSTA US Leveraged Loan | `MLLLI Index` (TR) |
| Bloomberg US High-Yield Loan | `BHYLOANS Index` |
| CS Leveraged Loan | `CSLLLTOT Index` |

---

## 4. Default probability + recovery fields

| Mnemonic | Meaning |
|---|---|
| `DEFAULT_PROBABILITY_1YR` | 1Y default probability (Bloomberg-modelled) |
| `DEFAULT_PROBABILITY_5YR` | 5Y default probability |
| `DRSK_PROB_DFLT_5Y` | DRSK 5Y default risk |
| `RECOVERY_RATE` | Assumed recovery rate |
| `LOSS_GIVEN_DEFAULT` | LGD |
| `CDS_IMPLIED_PROB_DEFAULT` | Probability of default implied by CDS spread |
| `BB_COMPOSITE_RATING` | Bloomberg composite rating |
| `RTG_BLOOMBERG_FIELD` | Bloomberg-derived rating |

For the `DRSK<GO>` model specifically:

| Mnemonic | Meaning |
|---|---|
| `DRSK_OUR_PROB_DEFAULT_TERM` | DRSK term-structure of default probability (BDS) |
| `DRSK_BBG_DFLT_RISK_INDICATOR` | DRSK risk indicator |

---

## 5. Ratings — full catalog

| Mnemonic | Meaning |
|---|---|
| `RTG_SP` | S&P short rating |
| `RTG_SP_LT_LC_ISSUER_CREDIT` | S&P long-term local-currency issuer rating |
| `RTG_SP_LT_FC_ISSUER_CREDIT` | S&P long-term foreign-currency issuer rating |
| `RTG_SP_OUTLOOK` | S&P outlook (`STABLE` / `POS` / `NEG`) |
| `RTG_SP_LAST_REV_DT` | S&P last review date |
| `RTG_MOODY` | Moody's rating |
| `RTG_MDY_LT_CFR` | Moody's long-term corporate family rating |
| `RTG_MDY_OUTLOOK` | Moody's outlook |
| `RTG_MDY_LAST_REV_DT` | Moody's last review date |
| `RTG_FITCH` | Fitch rating |
| `RTG_FITCH_OUTLOOK` | Fitch outlook |
| `RTG_FITCH_LAST_REV_DT` | Fitch last review date |
| `BB_COMPOSITE_RATING` | Bloomberg composite (mid-of-three when 3 agencies rate; else available agency) |
| `RTG_DBRS` | DBRS / Morningstar rating |

### 5.1 Ratings scale (alphanumeric → numeric for ranking)

For sorting / filtering, PRISM may need to convert alphanumeric ratings to a numeric scale. The convention (S&P / Fitch / Bloomberg composite all align; Moody's is a separate alphabet):

| S&P / Fitch | Moody's | Numeric |
|---|---|---|
| AAA | Aaa | 1 |
| AA+ | Aa1 | 2 |
| AA | Aa2 | 3 |
| AA- | Aa3 | 4 |
| A+ | A1 | 5 |
| A | A2 | 6 |
| A- | A3 | 7 |
| BBB+ | Baa1 | 8 |
| BBB | Baa2 | 9 |
| BBB- | Baa3 | 10 |
| BB+ | Ba1 | 11 |
| BB | Ba2 | 12 |
| BB- | Ba3 | 13 |
| B+ | B1 | 14 |
| B | B2 | 15 |
| B- | B3 | 16 |
| CCC+ | Caa1 | 17 |
| CCC | Caa2 | 18 |
| CCC- | Caa3 | 19 |
| CC | Ca | 20 |
| C | C | 21 |
| D | (no equiv — Moody's stays at C) | 22 |

Investment grade = numeric ≤ 10 (BBB- / Baa3). High yield = numeric ≥ 11 (BB+ / Ba1).

---

## 6. Spreads over time — the canonical workbook

The most common credit-workbook ask: "give me a time series of IG vs HY OAS, with sector breakdowns, monthly."

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "Spreads"

START = "-10Y"
N_ROWS = 121                                                                # 10Y monthly + header

ws["A1"] = "US IG vs HY OAS — 10Y monthly"

oas_tickers = ",".join([
    "LUACOAS Index",                                                        # IG
    "LF98OAS Index",                                                        # HY
    "LCB1OAS Index",                                                        # BBB
    "LCB2OAS Index",                                                        # BB
    "LCB3OAS Index",                                                        # B
    "LCB4OAS Index",                                                        # CCC
])

ws["A3"] = ArrayFormula(
    f"A3:G{2 + N_ROWS}",                                                    # date + 6 tickers
    f'=_xll.BDH("{oas_tickers}","PX_LAST","{START}","0D",'
    f'"Per=cm","Fill=P","Dts=S","Dir=V")'
)

wb.save("credit_spreads.xlsx")
```

To add a CDX overlay for the same period:

```python
ws["I3"] = ArrayFormula(
    f"I3:K{2 + N_ROWS}",
    f'=_xll.BDH("CDX IG CDSI GEN 5Y Corp,CDX HY CDSI GEN 5Y Corp","PX_LAST",'
    f'"{START}","0D","Per=cm","Fill=P","Dts=S","Dir=V")'
)
```

---

## 7. BQL credit patterns

### 7.1 Filter the HY index by sector and maturity

```excel
=_xll.BQL.Query("get(name(), maturity(), spread(spread_type=OAS), industry_sector(), rtg_sp()) for(filter(members('LF98TRUU Index'), and(industry_sector() == 'Energy', maturity() < 5Y)))")
```

### 7.2 Maturity-wall analysis (the HY index)

Verified pattern from `polars-bloomberg/Examples-BQL.ipynb`:

```excel
=_xll.BQL.Query("let(#mv=sum(group(amt_outstanding(currency=USD), by=[year(maturity()), industry_sector()]));) get(#mv) for(members('LF98TRUU Index'))")
```

Returns the dollar amount of HY bonds maturing each year × industry sector — useful for refinancing-wall charts.

### 7.3 Cross-section of dealer axes (where dealers want to trade)

```excel
=_xll.BQL.Query("let(#ax=axes();) get(security_des, #ax) for(filter(bondsuniv(ACTIVE), and(crncy()=='USD', basel_iii_designation() == 'Additional Tier 1', country_iso() == 'SE')))")
```

`axes()` returns dealer-published axes (where dealers want to trade); useful for finding liquid bonds with two-sided markets.

### 7.4 CDS curve construction

```excel
=_xll.BQL.Query("get(name(), maturity(), spread(), dv01()) for(cdscurvemembers('AAPL US Equity'))")
```

`cdscurvemembers()` returns the CDS curve points (1Y / 3Y / 5Y / 7Y / 10Y) for an issuer.

---

## 8. Anti-patterns specific to credit

| Mistake | Symptom | Fix |
|---|---|---|
| Pulling CDX HY `PX_LAST` and assuming it's a spread | HY indices are **price-quoted** (cents on the dollar), not spread-quoted | For spreads: use `PAR_CDS_SPREAD_5Y` or `CDS_FLAT_SPREAD` |
| Using a series-specific CDX ticker for time series | Series rolls every 6 months; the ticker becomes "off-the-run" | Use the generic form (`CDX IG CDSI GEN 5Y Corp`) for time series |
| Conflating Z-spread and OAS for callable / mortgage bonds | Z-spread doesn't account for embedded options | Use `OAS_*` for callables / MBS; use Z-spread for bullet bonds only |
| Pulling single-name CDS by issuer name without RED code | Returns wrong tier / restructuring variant | Look up the RED code via `CDSW<GO>` first; use `CT<RED> Corp` form |
| Treating BBB+ and Baa1 as different ratings | They're the same letter on different agency scales | Use `BB_COMPOSITE_RATING` for cross-agency comparison |
| Pulling `LF98OAS Index` for global HY | LF98* is US-only HY | For European HY use `LP01OAS Index`; for Pan-European IG use `LECPOAS Index` |
| Mixing `LECPOAS Index` (EUR) and `LUACOAS Index` (USD) in basis-point comparisons without currency notation | Spreads are in bp but represent different risk-free curves | Note the ccy in column header; do not arithmetic across them |

---

## 9. Quick reference

```
─────────────────────────────────────────────────────────────────────
  CDS INDEX TICKERS — GENERIC FORMS
─────────────────────────────────────────────────────────────────────
  CDX IG 5Y                  CDX IG CDSI GEN 5Y Corp     spread, bp
  CDX HY 5Y                  CDX HY CDSI GEN 5Y Corp     price, cents
  CDX EM 5Y                  CDX EM CDSI GEN 5Y Corp     spread, bp
  iTraxx Main 5Y             ITRX MAIN CDSI GEN 5Y Corp  spread, bp
  iTraxx Crossover 5Y        ITRX XOVER CDSI GEN 5Y Corp spread, bp
  iTraxx SubFin 5Y           ITRX SUBFIN CDSI GEN 5Y Corp
  iTraxx SovX WE 5Y          ITRX SOVX WE CDSI GEN 5Y Corp
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  CASH-BOND OAS INDEX TICKERS — US
─────────────────────────────────────────────────────────────────────
  US Agg OAS               LBUSOAS Index
  US IG OAS                LUACOAS Index
  US HY OAS                LF98OAS Index
  US BBB OAS               LCB1OAS Index
  US BB OAS                LCB2OAS Index
  US B OAS                 LCB3OAS Index
  US CCC OAS               LCB4OAS Index
  US MBS OAS               LUMSOAS Index
  US IG Financials OAS     LF80OAS Index
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  RATINGS NUMERIC EQUIVALENCE
─────────────────────────────────────────────────────────────────────
  IG / HY boundary:   numeric 10 (BBB-/Baa3) vs 11 (BB+/Ba1)
  Highest grade:      AAA / Aaa = 1
  Default:            D = 22 (S&P/Fitch); C = 21 (Moody's terminal)
─────────────────────────────────────────────────────────────────────
```
