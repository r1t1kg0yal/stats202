# Fixed income — bonds, curves, yields, spreads, duration

Spoke fetched on demand from the Bloomberg Excel hub. Covers cash-bond fields: yields, spreads, duration / convexity / DV01, issue-level data (coupon, maturity, calls, sinking funds), ratings, sovereign-curve conventions, and BQL bond-universe patterns.

For credit derivatives (CDS, CDX, iTraxx) and HY / IG indices, fetch `bbg_credit.md`. For openpyxl mechanics and BQL grammar, see the hub.

---

## 1. Yellow keys and on-the-run conventions

| Yellow key | Sector | Example |
|---|---|---|
| `Govt` | Sovereign bonds | `T 4 02/15/34 Govt` (US Treasury), `DBR 2.5 08/15/33 Govt` (Bund), `JGB 0.8 12/20/33 Govt` (JGB), `UKT 4.25 06/07/32 Govt` (Gilt) |
| `Corp` | Corporate bonds | `AAPL 3.85 05/04/43 Corp`, `037833DL1 Corp` (CUSIP form) |
| `Mtge` | Mortgage-backed | `FNCL 5.5 Mtge` (Fannie 30Y 5.5% TBA), `3132J5K Mtge` (specified pool CUSIP) |
| `Muni` | US municipal | `01069DBZ9 Muni` |
| `M-Mkt` | Money market | `<ticker> M-Mkt` |

### 1.1 On-the-run sovereign tickers (auto-roll)

Bloomberg publishes "current" tickers that always point at the most recently issued benchmark — they auto-roll as Treasury issues new bonds:

| Pattern | Meaning |
|---|---|
| `CT2 Govt`, `CT5 Govt`, `CT10 Govt`, `CT30 Govt` | Current US Treasury (2Y, 5Y, 10Y, 30Y on-the-run) |
| `GT2 Govt`, `GT5 Govt`, `GT10 Govt`, `GT30 Govt` | Generic US Treasury (constant-maturity) |
| `GTGBP10Y Govt`, `GTGBP30Y Govt` | UK Gilt 10Y / 30Y generic |
| `GTJPY10Y Govt`, `GTJPY30Y Govt` | JGB 10Y / 30Y generic |
| `GTDEM10Y Govt` (legacy DEM) → use `GTDM10Y Govt` for current German | German benchmark |
| `GTEUR10Y Govt` | Eurozone composite |

`CT*` is the actual on-the-run bond (carries the specific CUSIP). `GT*` is a constant-maturity series interpolated from the curve.

### 1.2 Yield-curve points (yields, not bonds)

| Pattern | Meaning |
|---|---|
| `USGG3M Index`, `USGG2YR Index`, `USGG10YR Index`, `USGG30YR Index` | US Treasury constant-maturity yields |
| `GUKG10 Index`, `GUKG30 Index` | UK Gilt yields |
| `GDBR10 Index`, `GDBR30 Index` | German Bund yields |
| `GJGB10 Index` | JGB 10Y yield |

These are `Index` securities — `PX_LAST` returns the yield directly.

---

## 2. Yield fields

| Mnemonic | Meaning |
|---|---|
| `YLD_YTM_BID` / `YLD_YTM_ASK` / `YLD_YTM_MID` | Yield to maturity (bid / ask / mid) |
| `YLD_CNV_BID` / `YLD_CNV_MID` | Conventional yield |
| `YLD_TO_WORST` | Yield to worst (worst-case for callable bonds) |
| `YLD_TO_MTY_LIVE` | Live yield to maturity |
| `YLD_DISC_BID` | Discount yield (Bills) |
| `YLD_SEMI_ANNUAL` | Yield converted to semi-annual equivalent |
| `YLD_CURRENT_AMT` | Current yield (coupon / price) |
| `BENCHMARK_NAME` | Benchmark security name |
| `SPREAD_TO_BENCHMARK` / `T_BENCHMARK_SPREAD` | Treasury benchmark spread |
| `Z_SPREAD_BID` / `Z_SPREAD_MID` / `Z_SPREAD_ASK` | Z-spread |
| `OAS_BID` / `OAS_MID` / `OAS_ASK` | Option-adjusted spread |
| `ASW_SPREAD_BID` / `ASW_SPREAD_MID` | Asset-swap spread |

Bills are quoted on a discount-rate basis, not YTM. For Bills, use `YLD_DISC_BID` (or `YLD_DISC_MID`). For Notes / Bonds, use `YLD_YTM_BID/MID`.

---

## 3. Risk metrics (duration, convexity, DV01)

| Mnemonic | Meaning |
|---|---|
| `DUR_ADJ_BID` / `DUR_ADJ_MID` | Modified duration |
| `MOD_DUR_BID` / `MOD_DUR_MID` | Modified duration (alias) |
| `EFF_DUR_BID` / `EFF_DUR_MID` | Effective duration (for callable / mortgage-backed) |
| `MAC_DUR_BID` / `MAC_DUR_MID` | Macaulay duration |
| `CNVX_BID` / `CNVX_MID` | Convexity |
| `EFF_CNVX_BID` | Effective convexity |
| `RISK_BID` / `RISK_MID` | DV01 (dollar change per 1bp yield change) |
| `BPV01` / `DV01` | DV01 (aliases) |
| `KEY_RATE_DURATION_*` | Key-rate durations (2Y, 5Y, 10Y, 30Y) — typically BDS-returned |
| `OAD_BID` / `OAD_MID` | Option-adjusted duration |
| `RHO_TO_PARALLEL_SHIFT` | Sensitivity to parallel curve shift |

For callable / structured products, use the `EFF_*` family (effective duration / convexity); they account for the option.

---

## 4. Issue / structural fields

| Mnemonic | Meaning |
|---|---|
| `COUPON` | Coupon rate (% annual) |
| `COUPON_FREQ` | Coupon frequency (1=annual, 2=semi-annual, 4=quarterly, 12=monthly) |
| `COUPON_TYPE` | `Fixed` / `Float` / `Step` / `Zero` / `Variable` |
| `MATURITY` | Maturity date |
| `ISSUE_DT` | Issue date |
| `ANNOUNCE_DT` | Announcement date |
| `AMT_OUTSTANDING` | Outstanding amount (in issue currency) |
| `AMT_OUT_STANDING_USD` | Outstanding amount (USD-equivalent) |
| `AMT_ISSUED` | Original issue size |
| `MIN_INCREMENT` | Trading lot size |
| `DAY_CNT_TY` / `DAY_CNT` | Day count convention (`30/360`, `ACT/ACT`, `ACT/360`, `ACT/365`) |
| `CALC_TYP` | Calculation type code |
| `SERIES` | Bond series (e.g. `144A`, `REGS`) |
| `RANK` | Seniority (`Sr Unsecured`, `Sub`, `Sr Secured`, `Sub Tier 2`) |
| `BASEL_III_DESIGNATION` | Basel III tier (AT1, Tier 2) |
| `MARKET_SECTOR_DES` | Sector designation |
| `MARKET_SECTOR_2_TYP` | Bond market sector type |
| `EQY_FUND_CRNCY` | Reporting currency |
| `INDUSTRY_SECTOR` | Issuer industry |

### 4.1 Callability + sinking-fund schedules

| Mnemonic | Meaning |
|---|---|
| `CALLABLE` | Callable flag (`Y` / `N`) |
| `NXT_CALL_DT` | Next call date |
| `NXT_CALL_PX` | Next call price |
| `CALL_SCHEDULE` | Full call schedule (BDS) |
| `MAKE_WHOLE_CALL` | Make-whole call info |
| `PUTABLE` | Putable flag |
| `NXT_PUT_DT` / `NXT_PUT_PX` | Next put date / price |
| `PUT_SCHEDULE` | Put schedule (BDS) |
| `SINKABLE` | Sinking fund flag |
| `SINK_SCHEDULE` / `SINK_FUND_HIST` | Sinking-fund schedule (BDS) |

```python
ws["A1"] = ArrayFormula(
    "A1:C20",
    '=_xll.BDS("AAPL 3.85 05/04/43 Corp","CALL_SCHEDULE")'
)
```

### 4.2 Cash-flow schedule

```python
ws["A1"] = ArrayFormula(
    "A1:F50",
    '=_xll.BDS("T 4 02/15/34 Govt","DES_CASH_FLOW")'
)
```

Columns: date | type (Coupon / Principal / Sink) | amount | percent of face | day-count-fraction | accrued.

### 4.3 Issuer + parent

| Mnemonic | Meaning |
|---|---|
| `ISSUER` | Issuer legal name |
| `ISSUER_PARENT_NAME` | Parent name |
| `ISSUER_PARENT_TICKER` | Parent's equity ticker |
| `ISSUER_INDUSTRY` | Issuer industry classification |
| `COUNTRY_OF_RISK` | Country of risk (where the credit risk sits) |
| `COUNTRY_OF_DOMICILE` | Country of incorporation |

---

## 5. Ratings

| Mnemonic | Meaning |
|---|---|
| `RTG_SP` | S&P rating |
| `RTG_MOODY` | Moody's rating |
| `RTG_FITCH` | Fitch rating |
| `BB_COMPOSITE_RATING` | Bloomberg composite (mid-of-three) |
| `RTG_SP_LT_LC_ISSUER_CREDIT` | S&P long-term local-currency issuer rating |
| `RTG_MDY_LT_CFR` | Moody's long-term corporate family rating |
| `RTG_SP_OUTLOOK` / `RTG_MDY_OUTLOOK` / `RTG_FITCH_OUTLOOK` | Outlook (`STABLE` / `POS` / `NEG` / `DEVELOPING`) |
| `RTG_SP_LAST_REV_DT` | Last rating change date (S&P) |
| `RTG_MDY_LAST_REV_DT` | Last rating change date (Moody's) |

For BQL filtering:

```
filter(bondsuniv(ACTIVE), and(rtg_sp() in ['BBB+', 'BBB', 'BBB-'], country_iso() == 'US'))
```

---

## 6. Sovereign curves (`BCURVE` + BQL `curvemembers`)

| Curve | DAPI ID | BQL form |
|---|---|---|
| USD Swap | `S23` | `'YCSW0023 Index'` |
| EUR Swap | `S45` | `'YCSW0045 Index'` |
| JPY Swap | `S141` | `'YCSW0141 Index'` |
| GBP Swap | `S110` | `'YCSW0110 Index'` |
| US Treasury (active) | `BS125` | `'YCGT0025 Index'` |
| US Treasury (off-the-run) | `BS125OTR` | `'YCGT0025OTR Index'` |
| UK Gilts | `BS124` | `'YCGT0024 Index'` |
| German Bunds | `BS25` | `'YCGT0016 Index'` |
| JGBs | `BS141` | `'YCGT0103 Index'` |
| US TIPS | `BS127` | `'YCGT0125 Index'` |

DAPI:

```python
ws["A1"] = ArrayFormula(
    "A1:F40",
    '=_xll.BCURVE("S23")'
)
```

BQL — far more flexible:

```excel
=_xll.BQL.Query("get(name(), maturity(), yld_ytm_mid()) for(curvemembers('YCSW0023 Index'))")
```

Returns the entire swap curve with maturity + yield, in long form.

---

## 7. BQL bond patterns

The single most powerful BQL universe builder is `bondsuniv()`. Combined with `filter()`, it lets PRISM screen the entire bond universe by issue characteristics.

### 7.1 Universe scopes

| Scope | Returns |
|---|---|
| `bondsuniv(ACTIVE)` | All actively-traded bonds |
| `bondsuniv(ALL)` | All bonds (incl. matured / called) |
| `bondsuniv(GOVT)` | Sovereigns only |
| `bondsuniv(CORP)` | Corporates only |
| `bondsuniv(MTGE)` | Mortgages |
| `bondsuniv(MUNI)` | Municipals |
| `bondsuniv(PFD)` | Preferreds |

### 7.2 `bonds(<equity>)` — issuer's bond list

```excel
=_xll.BQL.Query("get(name(), maturity(), coupon(), spread(spread_type=Z), duration(duration_type=MODIFIED)) for(bonds('AAPL US Equity'))")
```

Returns every bond issued by Apple. Add `filter(... series() == '144A')` to restrict to a specific tranche.

### 7.3 Common screen — high-grade USD, < 5Y maturity, OAS > 100

```excel
=_xll.BQL.Query("get(name(), maturity(), spread(spread_type=OAS), duration(duration_type=MODIFIED)) for(filter(bondsuniv(ACTIVE), and(crncy()=='USD', rtg_sp() in ['A','A+','A-','AA-','AA','AA+'], maturity() < 5Y, spread(spread_type=OAS) > 100)))")
```

### 7.4 Aggregations — average OAS by sector / maturity bucket

```excel
=_xll.BQL.Query("let(#avg_oas=avg(group(spread(spread_type=OAS), by=[year(maturity()), industry_sector()]));) get(#avg_oas) for(members('LUACTRUU Index'))")
```

`LUACTRUU Index` is the Bloomberg US Corp Investment Grade index — its members are all the IG cash bonds.

### 7.5 BQL field shortcuts

| BQL function | DAPI equivalent |
|---|---|
| `spread(spread_type=OAS)` | `OAS_MID` |
| `spread(spread_type=Z)` | `Z_SPREAD_MID` |
| `spread(spread_type=ASW)` | `ASW_SPREAD_MID` |
| `spread(spread_type=GOV)` | `SPREAD_TO_BENCHMARK` |
| `duration(duration_type=MODIFIED)` | `DUR_ADJ_MID` |
| `duration(duration_type=EFFECTIVE)` | `EFF_DUR_MID` |
| `duration(duration_type=MACAULAY)` | `MAC_DUR_MID` |
| `yld_ytm_mid()` | `YLD_YTM_MID` |
| `coupon()` | `COUPON` |
| `maturity()` | `MATURITY` |
| `amt_outstanding(currency=USD)` | `AMT_OUT_STANDING_USD` |
| `rtg_sp()` | `RTG_SP` |
| `rtg_moody()` | `RTG_MOODY` |
| `crncy()` | `CRNCY` |
| `country_iso()` | `COUNTRY_ISO` |
| `industry_sector()` | `INDUSTRY_SECTOR` |
| `series()` | `SERIES` |
| `axes()` | (no direct DAPI equiv — dealer axes) |

---

## 8. Common benchmark indices (Bloomberg / Barclays family)

| Index | Ticker | Asset class |
|---|---|---|
| Bloomberg US Aggregate (the "Agg") | `LBUSTRUU Index` | US IG fixed income, broad |
| US Treasury (intermediate) | `LT01TRUU Index` (TR), `LT01YW Index` (1-3Y YTW) | US Treasuries |
| US Treasury (long) | `LT07TRUU Index` (TR) | Long-end Treasuries |
| US TIPS | `BCIT1T Index` (TR) | Inflation-linked |
| US Corp IG | `LUACTRUU Index` (TR), `LUACOAS Index` (OAS) | IG cash corps |
| US Corp HY | `LF98TRUU Index` (TR), `LF98OAS Index` (OAS) | HY cash corps |
| US MBS | `LUMSTRUU Index` (TR) | Mortgage-backed |
| EM USD Sov | `BEUSTRUU Index` (TR) | EM dollar sovereigns |
| Euro Corp IG | `LECPTREU Index` (TR) | EUR IG corps |
| Euro Govt | `LEATTREU Index` (TR) | EUR sovereigns |
| Pan-European HY | `LP01TREU Index` (TR) | Pan-European HY |
| Bloomberg Global Agg | `LEGATRUU Index` (TR) | Global IG broad |
| Bloomberg Global HY | `LG30TRUU Index` (TR) | Global HY |
| Bloomberg Municipal | `LMBITR Index` (TR) | US municipals |

For OAS-history workbook patterns, the right "ticker" is the OAS-suffixed variant (`LF98OAS Index`, `LUACOAS Index`). These return the index-level OAS as `PX_LAST`:

```python
ws["A3"] = ArrayFormula(
    "A3:C1262",                                                             # 5Y daily + header
    '=_xll.BDH("LF98OAS Index,LUACOAS Index","PX_LAST","-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
```

This pulls 5Y of US IG vs HY OAS side-by-side.

---

## 9. Mortgage-backed securities (TBAs, agency MBS, pools)

Mortgages have their own yellow key (`Mtge`) and a distinct field family covering prepayment behaviour, weighted-average life, and pool-level descriptive data. Two security types dominate Excel work:

### 9.1 TBA (To-Be-Announced) tickers

TBAs are forward-settling agency MBS contracts traded by coupon and program. Bloomberg's generic tickers:

```
FNCL 5.5 Mtge                # Fannie Mae 30Y, 5.5% coupon (current production)
FNCI 5.5 Mtge                # Fannie Mae 15Y, 5.5% coupon
FNCG 5.5 Mtge                # Ginnie I, 30Y, 5.5%
FNCH 5.5 Mtge                # Ginnie II, 30Y, 5.5%
GNMA II 5.5 Mtge             # Long-form Ginnie II
FHLM Gold 5.5 Mtge           # Freddie Gold (legacy; UMBS supersedes for 30Y new issue)
UMBS 30Y 5.5 Mtge            # UMBS (the unified Fannie / Freddie security post-2019)
```

Pattern: `<program> <coupon> Mtge`. The coupon increments by 50bp typically (3.0, 3.5, 4.0, ..., 7.0). Bloomberg auto-rolls the front-month TBA settlement date.

### 9.2 Specified pool tickers

Specified pools (the actual securitisations) use CUSIP-form tickers:

```
3132J5K Mtge                 # specific Fannie pool
3138Y8K9 Mtge                # specific UMBS pool
```

The user typically gets these from a pool inventory listing; PRISM rarely constructs them from scratch.

### 9.3 Key MBS fields

| Mnemonic | Returns |
|---|---|
| `PX_LAST` | Price (cents on the dollar, e.g. 99.50) |
| `YLD_YTM_MID` | Yield to maturity (assumes assumed prepay) |
| `OAS_MID` | Option-adjusted spread — the right spread for MBS (Z-spread ignores prepay optionality) |
| `OAD_MID` / `EFF_DUR_MID` | Option-adjusted duration |
| `MTG_WAL` | Weighted-average life (years) at assumed prepay speed |
| `MTG_AVG_LIFE` | Alias for WAL |
| `MTG_FACTOR` | Pool factor (fraction of original principal still outstanding) |
| `MTG_PSA` | Current prepay rate in PSA units (100 PSA = 6% CPR after seasoning) |
| `MTG_CPR_1M` / `MTG_CPR_3M` / `MTG_CPR_6M` / `MTG_CPR_12M` | Conditional prepay rate over trailing window |
| `MTG_SMM` | Single monthly mortality |
| `MTG_PCT_PRIN_PAID` | Cumulative percent of original principal repaid |
| `MTG_DEAL_PCT_PAID_DOWN` | Deal-level pay-down |
| `MTG_NEXT_PAY_DT` | Next payment date |
| `MTG_DELAY_CD` | Payment delay days (typical 24 for Fannie, 14 for Ginnie) |
| `MTG_WHLN_BAL_ORIG` | Original face value |
| `MTG_WAC` | Weighted-average coupon (gross of guarantee fee) |
| `MTG_WAM` | Weighted-average maturity |
| `MTG_WALA` | Weighted-average loan age |

### 9.4 BQL mortgage patterns

```excel
=_xll.BQL.Query("get(name(), px_last, mtg_wal(), oas_mid(), mtg_cpr_3m(), mtg_factor()) for(['FNCL 5.5 Mtge', 'FNCL 6.0 Mtge', 'FNCL 6.5 Mtge', 'UMBS 30Y 5.5 Mtge'])")
```

For a coupon stack (one program, ladder of coupons):

```excel
=_xll.BQL.Query("get(name(), px_last, mtg_wal(), oas_mid()) for(['FNCL 3.0 Mtge', 'FNCL 3.5 Mtge', 'FNCL 4.0 Mtge', 'FNCL 4.5 Mtge', 'FNCL 5.0 Mtge', 'FNCL 5.5 Mtge', 'FNCL 6.0 Mtge', 'FNCL 6.5 Mtge'])")
```

### 9.5 Why OAS for MBS (not Z-spread)

Mortgage borrowers can refinance — a free prepayment option that hurts the MBS holder when rates fall. Z-spread treats the bond as a fixed-cashflow bullet and ignores this. OAS strips out the option value, leaving the "true" credit / liquidity premium. **Default to `OAS_MID` for any MBS spread comparison.** Z-spread for MBS is technically reportable but mis-leads.

Bloomberg's OAS computation uses a Monte Carlo over a stochastic interest-rate path with a prepayment model (Bloomberg's BAM model is the standard). The user can override the prepay-model assumption via `MTG_PSA_OVRD` (assumes a PSA-equivalent flat prepay) or `MTG_VECTOR_OVRD` (path-vector). For most Excel work, defaults are fine.

---

## 10. Inflation-linked bonds, break-evens, inflation swaps

### 10.1 TIPS (US inflation-linked Treasuries)

```
TII 1.75 01/15/34 Govt       # specific TIPS issue
912828YY0 Govt               # CUSIP form
```

Generic constant-maturity TIPS:

```
GTII5 Govt                   # Generic 5Y TIPS
GTII10 Govt                  # Generic 10Y TIPS
GTII20 Govt                  # Generic 20Y TIPS
GTII30 Govt                  # Generic 30Y TIPS
```

### 10.2 TIPS-specific yield fields

| Mnemonic | Returns |
|---|---|
| `YLD_REAL_BID` / `YLD_REAL_MID` | Real yield (the right yield for TIPS — inflation-adjusted) |
| `YLD_YTM_MID` | Nominal-equivalent yield (less commonly used for TIPS) |
| `INFLATION_ADJ_BID` / `INFLATION_ADJ_MID` | Inflation-adjusted principal value |
| `INDEX_RATIO` | Ratio of current CPI to CPI at issuance (the principal accretion factor) |
| `CPI_BASE_DATE` | Reference CPI base date |
| `CPI_INDEX_REF` | Reference CPI index used (typically `CPURNSA Index`) |
| `BREAKEVEN_YIELD` / `BREAKEVEN_INFLATION` | Break-even inflation rate vs nominal benchmark |

### 10.3 Break-even inflation tickers

The "break-even" is the difference between a nominal Treasury yield and a real TIPS yield of the same maturity — the inflation rate at which nominal and TIPS produce equal returns. Bloomberg publishes BEI directly:

| Ticker | Meaning |
|---|---|
| `USGGBE05 Index` | US 5Y break-even inflation |
| `USGGBE10 Index` | US 10Y break-even inflation |
| `USGGBE30 Index` | US 30Y break-even inflation |
| `USGGBE02 Index` | US 2Y break-even inflation |
| `GEGGBE10 Index` | German 10Y break-even (HICP-linked) |
| `BPGGBE10 Index` | UK 10Y break-even (RPI-linked) |

Pull as ordinary `Index` securities — `PX_LAST` returns the BEI in percent.

### 10.4 Inflation swap curves

| Pattern | Meaning |
|---|---|
| `USSWIT1 Curncy` through `USSWIT30 Curncy` | USD zero-coupon inflation swap rates (CPI-U linked) |
| `EUSWIB1 Curncy` etc. | EUR inflation swaps (HICP ex-tobacco linked) |
| `BPSWIB1 Curncy` etc. | GBP inflation swaps (RPI linked) |
| `JYSWIE1 Curncy` etc. | JPY inflation swaps |

Inflation swaps + the break-even from cash TIPS tell a similar story but with different mechanics:

- **Break-even** is a derived statistic (nominal − real), affected by liquidity premia, supply-demand of TIPS specifically.
- **Inflation swap** is a market-traded derivative — cleaner read on inflation expectations.

For inflation-expectations forecasting work, default to swaps. For backtest-against-published-references work, default to break-even.

### 10.5 CPI index tickers used as references

| Ticker | Meaning |
|---|---|
| `CPURNSA Index` | US CPI All Urban Consumers, NSA (the reference for TIPS indexation) |
| `CPI Index` | US CPI, SA |
| `EUR HICP Index` (varies) | EUR Harmonised Index of Consumer Prices |
| `UKRPI Index` | UK Retail Prices Index |

These are released indices; pulling history matches the `bbg_macro.md` §2.3 pattern (`BDH` with `Per=cm` for the monthly cadence).

### 10.6 The canonical "real rates + BEI" workbook

```python
ws["A3"] = ArrayFormula(
    "A3:G1262",                                                             # 5Y daily
    '=_xll.BDH('
    '"GTII10 Govt,GT10 Govt,USGGBE10 Index,USSWIT10 Curncy,USGG10YR Index,GTII5 Govt,USGGBE05 Index",'
    '"PX_LAST,YLD_REAL_MID","-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
```

Returns:
- `GTII10 Govt` real yield (TIPS) + price
- `GT10 Govt` nominal yield + price
- `USGGBE10 Index` 10Y break-even (derived)
- `USSWIT10 Curncy` 10Y inflation swap
- `USGG10YR Index` 10Y nominal yield (constant maturity)
- `GTII5 Govt` 5Y TIPS
- `USGGBE05 Index` 5Y break-even

Downstream Excel: chart real yields (10Y / 5Y), nominal yield, BEI, inflation swap — gives the full nominal / real / inflation-expectations picture in one chart.

---

## 11. Anti-patterns specific to FI

| Mistake | Symptom | Fix |
|---|---|---|
| Using `YLD_YTM_*` on US Treasury Bills | Returns `#N/A` — Bills publish discount yield | Use `YLD_DISC_BID/MID` for Bills, or pull Bill yields from `USGGT3M Index` (constant-maturity proxy) |
| Pulling Z-spread on a callable bond and ignoring OAS | Z-spread doesn't account for the embedded option | Use `OAS_*` for callable / mortgage-backed; Z-spread is the bullet-bond view |
| Sorting bonds in `bondsuniv(ALL)` without filtering for active | Returns matured bonds (yields are stale) | Default to `bondsuniv(ACTIVE)` unless the user explicitly wants historical |
| Using `MOD_DUR` for a mortgage-backed bond | Modified duration ignores prepayment optionality | Use `EFF_DUR_*` for MBS / callable corps |
| Using Z-spread on MBS | Ignores the embedded prepay option; understates the spread the user is bearing | Use `OAS_MID` for MBS — Bloomberg's BAM model strips out option value |
| Pulling `YLD_YTM_MID` for TIPS and treating as the yield | Returns nominal-equivalent yield; TIPS quote in real terms | Use `YLD_REAL_MID` for TIPS yield; `BREAKEVEN_INFLATION` for the implied inflation |
| Mixing 5Y TIPS with 10Y nominal for break-even | Mismatched maturity inflates / deflates the BEI | Match the maturity buckets; or use the published BEI ticker (`USGGBE10 Index` etc.) directly |
| Comparing inflation swaps and break-evens as identical | They share a direction but diverge on liquidity + TIPS-supply effects | Note the source in the workbook header; default to swaps for clean inflation-expectations work |
| Pulling Treasury futures via `Govt` yellow key | Wrong yellow key — futures are `Comdty` | `TY1 Comdty` (10Y futures), `US1 Comdty` (long-bond futures), `TU1 Comdty` (2Y futures) |
| Mixing par-yield and spot-yield curve | Treasury constant-maturity (`USGG10YR Index`) is par-yield equivalent; swap curve is zero-coupon — they're not directly comparable | Document the curve convention in the workbook header |
| BCURVE with a misspelled curve ID | Returns `#N/A Invalid Curve` | Use `YCSW<00xx> Index` form for BQL (more discoverable); `S23` shorthand only with DAPI BCURVE |

---

## 12. Quick reference

```
─────────────────────────────────────────────────────────────────────
  ON-THE-RUN / GENERIC SOVEREIGN TICKERS
─────────────────────────────────────────────────────────────────────
  Current OTR USTs:    CT2 / CT5 / CT10 / CT30 Govt
  Generic CM USTs:     GT2 / GT5 / GT10 / GT30 Govt
  CM yields:           USGG2YR / USGG5YR / USGG10YR / USGG30YR Index
  Bunds:               GDBR10 / GDBR30 Index
  Gilts:               GUKG10 / GUKG30 Index
  JGBs:                GJGB10 Index
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  YIELD / SPREAD / RISK METRICS — BID/MID/ASK SUFFIXES
─────────────────────────────────────────────────────────────────────
  YTM:                YLD_YTM_BID/MID/ASK
  Z-spread:           Z_SPREAD_BID/MID/ASK
  OAS:                OAS_BID/MID/ASK   (use this for callables)
  ASW spread:         ASW_SPREAD_BID/MID
  Treasury spread:    SPREAD_TO_BENCHMARK / T_BENCHMARK_SPREAD
  Modified duration:  DUR_ADJ_BID/MID    or MOD_DUR_BID/MID
  Effective duration: EFF_DUR_BID/MID    (callable / MBS)
  DV01:               RISK_BID/MID       or BPV01 / DV01
  Convexity:          CNVX_BID/MID, EFF_CNVX_BID
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  BQL BOND UNIVERSE + FIELDS
─────────────────────────────────────────────────────────────────────
  Universe:    bondsuniv(ACTIVE|ALL|GOVT|CORP|MTGE|MUNI|PFD)
               bonds('<equity>')           — issuer's bonds
               curvemembers('YCSW0023 Index')
  Fields:      spread(spread_type=OAS|Z|ASW|GOV)
               duration(duration_type=MODIFIED|EFFECTIVE|MACAULAY)
               yld_ytm_mid(), coupon(), maturity()
               amt_outstanding(currency=USD)
               rtg_sp(), rtg_moody()
               crncy(), country_iso(), industry_sector()
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  MORTGAGES — TBA TICKERS + KEY FIELDS
─────────────────────────────────────────────────────────────────────
  TBA generics:        FNCL 5.5 Mtge (Fannie 30Y, 5.5% coupon)
                       FNCI 5.5 Mtge (Fannie 15Y)
                       UMBS 30Y 5.5 Mtge (unified Fannie/Freddie)
  Spread:              OAS_MID  (use OAS, not Z-spread)
  Duration:            EFF_DUR_MID  (option-aware)
  Life:                MTG_WAL  (weighted-avg life)
  Prepay:              MTG_CPR_3M / MTG_PSA / MTG_FACTOR
  Pool descriptive:    MTG_WAC, MTG_WAM, MTG_WALA
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  INFLATION-LINKED — TIPS, BEI, INFLATION SWAPS
─────────────────────────────────────────────────────────────────────
  TIPS generics:       GTII5 / GTII10 / GTII30 Govt
  TIPS real yield:     YLD_REAL_MID
  Break-even:          USGGBE05 / USGGBE10 / USGGBE30 Index
  Inflation swaps:     USSWIT1 ... USSWIT30 Curncy
  Real-rate CM yield:  USGGT05 / USGGT10 Index
  CPI reference:       CPURNSA Index (the TIPS-linked one, NSA)
─────────────────────────────────────────────────────────────────────
```
