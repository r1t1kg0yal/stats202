# Equities — fields, screening, fundamentals

Spoke fetched on demand from the Bloomberg Excel hub. Covers the equity-specific field surface: pricing / volume / returns, fundamentals (income statement, balance sheet, cash flow), valuation ratios, estimates, holders / peers / segments, index conventions, GICS / BICS classification, and BEQS screening.

For corporate events (earnings calendar, filings, dividends, M&A, corporate actions), fetch `bbg_events.md`. For options on equities / ETFs (chain, Greeks, IV), fetch `bbg_options.md`. For openpyxl mechanics and BQL grammar, see the hub (`bloomberg_excel.md`).

---

## 1. Pricing, volume, returns

| Mnemonic | Meaning | Notes |
|---|---|---|
| `PX_LAST` | Last traded price (close on EOD) | Returned in security's reporting currency |
| `PX_OPEN` / `PX_HIGH` / `PX_LOW` | Day's open / high / low | |
| `PX_BID` / `PX_ASK` / `PX_MID` | Quoted bid / ask / mid | |
| `PX_VOLUME` | Day's share volume | |
| `VWAP` | Volume-weighted average price | |
| `LAST_PRICE` | Alias for `PX_LAST` | |
| `52WK_HIGH` / `52WK_LOW` | 52-week range | |
| `CHG_PCT_1D` / `CHG_PCT_5D` / `CHG_PCT_MTD` / `CHG_PCT_QTD` / `CHG_PCT_YTD` / `CHG_PCT_1Y` | Percent change over horizon | |
| `DAY_TO_DAY_TOT_RETURN_GROSS_DVDS` | Total return including dividends | History-only via `BDH` |
| `TOT_RETURN_INDEX_GROSS_DVDS` | Total-return index level | |
| `TURNOVER` | Day's notional turnover | |
| `BID_SIZE` / `ASK_SIZE` | Quote sizes | |
| `TOT_OPT_VOLUME_CUR_DAY` | Day's options volume | |
| `EQY_BETA` / `BETA_ADJ_OVERRIDABLE_3YR` | Beta | Suffix variants for window |
| `VOLATILITY_30D` / `VOLATILITY_90D` / `VOLATILITY_180D` / `VOLATILITY_360D` | Historical vol | |

Override `CURR=USD` (DAPI) or `currency=USD` (BQL) to convert returned values to USD when comparing across currencies.

---

## 2. Identifiers and descriptive

| Mnemonic | Meaning |
|---|---|
| `NAME` | Bloomberg short name |
| `LONG_COMP_NAME` | Full legal name |
| `SECURITY_DES` | Security description |
| `ID_ISIN` / `ID_CUSIP` / `ID_BB_GLOBAL` (FIGI) / `ID_SEDOL` | Identifiers |
| `EXCH_CODE` | Primary exchange code |
| `COUNTRY_FULL_NAME` / `COUNTRY_ISO` | Domicile |
| `CRNCY` | Reporting currency |

### 2.1 GICS / BICS classification

| Mnemonic | Meaning |
|---|---|
| `GICS_SECTOR_NAME` | GICS Level 1 |
| `GICS_INDUSTRY_GROUP_NAME` | GICS Level 2 |
| `GICS_INDUSTRY_NAME` | GICS Level 3 |
| `GICS_SUB_INDUSTRY_NAME` | GICS Level 4 |
| `BICS_LEVEL_1_SECTOR_NAME` | BICS Level 1 |
| `BICS_LEVEL_2_INDUSTRY_GROUP_NAME` | BICS Level 2 |
| `BICS_LEVEL_3_INDUSTRY_NAME` | BICS Level 3 |
| `INDUSTRY_SECTOR` | Bloomberg industry sector (legacy field, broader buckets than BICS L1) |

Use GICS when the user is comparing to standardised cross-vendor data (S&P / MSCI). Use BICS when the user is staying inside Bloomberg's universe — BICS goes deeper (5 levels) and updates faster.

---

## 3. Fundamentals — income statement, balance sheet, cash flow

Use `BEST_FPERIOD_OVERRIDE` (DAPI) or `fpt=` / `fpr=` (BQL) to control fiscal period. Common values: `1FY` (last fiscal year), `1BF` (1 forward), `LTM` (last twelve months), `YTD`.

### 3.1 Income statement

| Mnemonic | Meaning |
|---|---|
| `IS_TOT_REV` / `SALES_REV_TURN` / `REVENUE` | Total revenue / sales |
| `IS_GROSS_PROFIT` | Gross profit |
| `IS_OPER_INC` / `EBIT` | Operating income |
| `EBITDA` | EBITDA |
| `IS_DEPR_AND_AMORT` | Depreciation & amortisation |
| `IS_INT_EXPENSE` | Interest expense |
| `IS_PRETAX_INC` | Pre-tax income |
| `IS_INC_TAX_EXP` | Income tax expense |
| `IS_NET_INCOME` / `NET_INCOME` | Net income |
| `IS_EPS` | Basic EPS |
| `IS_DILUTED_EPS` | Diluted EPS |
| `IS_AVG_NUM_SH_FOR_EPS` | Weighted average shares for EPS |

### 3.2 Balance sheet

| Mnemonic | Meaning |
|---|---|
| `BS_TOT_ASSET` | Total assets |
| `BS_TOT_LIAB2` | Total liabilities |
| `BS_TOT_EQY` | Total equity |
| `BS_CASH_NEAR_CASH_ITEM` | Cash & equivalents |
| `BS_ST_INVEST` | Short-term investments |
| `BS_INVENTORIES` | Inventories |
| `BS_ACCT_RCV` | Accounts receivable |
| `BS_TOTAL_DEBT` / `BS_LT_BORROW` | Total debt / long-term borrowings |
| `BS_NET_DEBT` | Net debt |
| `BS_SH_OUT` / `EQY_SH_OUT` | Shares outstanding |
| `TOT_DEBT_TO_TOT_EQY` | Debt / equity ratio |
| `TOT_DEBT_TO_TOT_ASSETS` | Debt / assets |

### 3.3 Cash flow

| Mnemonic | Meaning |
|---|---|
| `CF_CASH_FROM_OPER` | Operating cash flow |
| `CF_CAP_EXPEND_INC_FIX_ASSETS` | Capex |
| `FREE_CASH_FLOW` | FCF |
| `CFF_PURCHASE_COMMON_PREFERRED_STOCK` | Buybacks (cash spent) |
| `CFF_CASH_DIVIDENDS_PAID` | Dividends paid (cash) |
| `CF_NET_FIN_ACTIVITIES` | Net financing activities |
| `CF_NET_INV_ACTIVITIES` | Net investing activities |

---

## 4. Valuation ratios

| Mnemonic | Meaning |
|---|---|
| `PE_RATIO` | P/E (trailing) |
| `BEST_PE_RATIO` | Forward P/E |
| `PX_TO_BOOK_RATIO` | P/B |
| `PX_TO_SALES_RATIO` | P/S |
| `PX_TO_CASH_FLOW` | P/CF |
| `EV_TO_T12M_EBITDA` | EV/EBITDA (trailing) |
| `BEST_EV_TO_EBITDA` | Forward EV/EBITDA |
| `BEST_PX_SALES` | Forward P/S |
| `CUR_MKT_CAP` | Market cap |
| `CURR_ENTP_VAL` | Enterprise value |
| `RETURN_COM_EQY` / `RETURN_ON_EQUITY` | ROE |
| `RETURN_ON_ASSET` | ROA |
| `RETURN_ON_INV_CAPITAL` | ROIC |
| `OPER_MARGIN` | Operating margin |
| `PROF_MARGIN` | Net margin |
| `GROSS_MARGIN` | Gross margin |
| `DIVIDEND_YIELD` / `EQY_DVD_YLD_IND` | Dividend yield |
| `BUYBACK_RATIO_TR12M` | Buyback yield (trailing) |
| `TOT_RETURN_TR12M` | Trailing 12M total return |

---

## 5. Estimates (consensus)

| Mnemonic | Meaning |
|---|---|
| `BEST_EPS` | Forward EPS consensus |
| `BEST_TARGET_PRICE` | Consensus target price |
| `BEST_SALES` | Forward revenue consensus |
| `BEST_EBITDA` | Forward EBITDA consensus |
| `BEST_DPS` | Forward dividend per share consensus |
| `EQY_REC_CONS` / `ANALYST_REC_CONS` | Consensus recommendation (1=Buy, 5=Sell scale) |
| `TOT_BUY_REC` / `TOT_HOLD_REC` / `TOT_SELL_REC` | Count of analysts at each rating |
| `EQY_REC_HIGH` / `EQY_REC_LOW` / `EQY_REC_AVG` | Recommendation distribution |
| `EST_NUM_ANALYSTS` | Number of analysts in consensus |
| `BEST_EPS_NUMEST` | Number of EPS estimates |

Use `BEST_FPERIOD_OVERRIDE=1BF` (next forward fiscal period) or `2BF` (two forward) on DAPI. In BQL: `is_eps(fa_period_offset=1, fa_act_est_data=E, est_source=BST)`.

---

## 6. Index conventions

### 6.1 Common index tickers

| Index | Ticker | Region |
|---|---|---|
| S&P 500 | `SPX Index` | US large-cap |
| Nasdaq 100 | `NDX Index` | US tech |
| Dow Jones Industrial Average | `INDU Index` | US 30 |
| Russell 2000 | `RTY Index` | US small-cap |
| Russell 1000 | `RIY Index` | US 1000 |
| Russell 3000 | `RAY Index` | US broad |
| Wilshire 5000 | `W5000 Index` | US total |
| MSCI World | `MXWO Index` | DM |
| MSCI EM | `MXEF Index` | EM |
| MSCI ACWI | `MXWD Index` | Global |
| EuroStoxx 50 | `SX5E Index` | Eurozone |
| Stoxx Europe 600 | `SXXP Index` | Europe |
| FTSE 100 | `UKX Index` | UK |
| DAX | `DAX Index` | Germany |
| CAC 40 | `CAC Index` | France |
| Nikkei 225 | `NKY Index` | Japan |
| TOPIX | `TPX Index` | Japan broad |
| Hang Seng | `HSI Index` | Hong Kong |
| Shanghai Composite | `SHCOMP Index` | China |
| CSI 300 | `SHSZ300 Index` | China onshore |
| Sensex | `SENSEX Index` | India |
| Nifty 50 | `NIFTY Index` | India |
| KOSPI | `KOSPI Index` | Korea |
| Bovespa | `IBOV Index` | Brazil |
| ASX 200 | `AS51 Index` | Australia |
| TSX Composite | `SPTSX Index` | Canada |

### 6.2 Membership and weight fields (`BDS`)

| Field | Returns |
|---|---|
| `INDX_MEMBERS` | Ticker list (one column) |
| `INDX_MWEIGHT` | Ticker + weight (two columns) |
| `INDX_MWEIGHT_HIST` | Historical weights as of date |
| `INDX_MEMBERS_WITH_NAMES` | Tickers + Bloomberg names |
| `INDEX_ADD_DEL_HIST` | History of index additions / deletions |

```python
ws["A1"] = ArrayFormula(
    "A1:B520",                                                              # SPX ≈ 503 members
    '=_xll.BDS("SPX Index","INDX_MWEIGHT")'
)
```

### 6.3 Index-level aggregates (`BDP`)

| Mnemonic | Meaning |
|---|---|
| `INDX_TOTAL_RETURN` | Total return |
| `INDX_FUND_FLOW` | Aggregated fund flow |
| `EQY_WEIGHTED_AVG_PE` | Cap-weighted P/E |
| `EQY_WEIGHTED_AVG_DVD_YLD` | Cap-weighted dividend yield |
| `EQY_WEIGHTED_AVG_PX_TO_BOOK_RATIO` | Cap-weighted P/B |
| `INDX_DIV_YIELD` | Index dividend yield |
| `INDX_GENERAL_MOVE` | Index move (in points) |

---

## 7. Holders, peers, segments

### 7.1 Top holders

```python
ws["A1"] = ArrayFormula(
    "A1:E25",
    '=_xll.BDS("AAPL US Equity","TOP_20_HOLDERS_PUBLIC_FILINGS")'
)
```

Columns: holder name | shares held | percent out | filing date | value.

Other holder fields:

| Field | Returns |
|---|---|
| `TOP_HOLDERS_PUBLIC_FILINGS` | Top holders (unbounded; pair with `BDS_HOLDER_COUNT` override) |
| `PCT_INSIDER_SHARES_OUT` | Insider ownership % |
| `EQY_INST_PCT_SH_OUT` | Institutional ownership % |
| `EQY_SHORT_INTEREST` | Short interest (shares) |
| `EQY_SHORT_INT_PCT_OF_OUT_NUM` | Short interest as % of float |

### 7.2 Peers

| Field | Returns |
|---|---|
| `EQY_BLOOMBERG_PEERS` | Bloomberg-curated peer list (BDS) |
| `EQY_PEER_GROUP_CRNCY_ADJ_PE` | Peer-group average P/E (currency-adjusted) |

BQL peer builder: `peers('AAPL US Equity')` — universe.

### 7.3 Segments (revenue / income by line of business)

DAPI:

| Field | Returns |
|---|---|
| `PRODUCT_SEG_RPT_REVENUE` | Reported revenue by product segment (BDS) |
| `PRODUCT_SEG_RPT_OP_INC` | Reported operating income by product segment |
| `GEOGRAPHIC_SEG_REV` | Revenue by geography |
| `SEGMENT_REPORTED_OR_ESTIMATED_LEVEL_1` | Segment hierarchy (BDS) |

BQL is much more flexible — use `segments()`:

```excel
=_xll.BQL.Query("get(segment_name(), sales_rev_turn(fpt=q, fpr=range(2023Q1, 2024Q4))) for(segments('AAPL US Equity', type=reported, hierarchy=PRODUCT, level=1))")
```

| `segments()` parameter | Values |
|---|---|
| `type=` | `reported` (as filed) / `estimated` (Bloomberg-modelled) |
| `hierarchy=` | `PRODUCT` / `GEO` |
| `level=` | 1 / 2 / 3 (deeper levels are more granular) |

---

## 8. BQL equity screening

The canonical pattern: define variables in `let()`, screen with `filter()`, compose aggregates with `group()`.

### 8.1 Value screen with momentum filter

```excel
=_xll.BQL.Query("let(#pe=pe_ratio(); #mom=px_last() / sma(period=200) - 1;) get(name(), gics_sector_name(), #pe, #mom) for(filter(members('SPX Index'), and(#pe < 15, #mom > 0.10, cur_mkt_cap > 5e9)))")
```

### 8.2 Quality screen (high ROE, low debt, growing FCF)

```excel
=_xll.BQL.Query("let(#roe=return_on_equity(fpt=A, fpr=0); #de=tot_debt_to_tot_eqy(fpt=A); #fcfg=pct_chg(free_cash_flow(fpt=A, fpr=range(-3, 0)), period=3);) get(name(), #roe, #de, #fcfg) for(filter(members('SPX Index'), and(#roe > 0.15, #de < 1.0, #fcfg > 0.10)))")
```

### 8.3 Sector-aggregate (average P/E by GICS sector for an index)

```excel
=_xll.BQL.Query("let(#avg_pe=avg(group(pe_ratio(), gics_sector_name()));) get(#avg_pe) for(members('SPX Index'))")
```

### 8.4 Technical (EMA crossover + RSI)

```excel
=_xll.BQL.Query("let(#ema20=emavg(period=20); #ema200=emavg(period=200); #rsi=rsi(close=px_last(), period=14);) get(name(), #ema20, #ema200, #rsi) for(filter(members('SPX Index'), and(#ema20 > #ema200, #rsi > 53)))")
```

---

## 9. BEQS — saved equity screens

`BEQS` evaluates a saved `EQS<GO>` screen. The screen must already exist on the user's Bloomberg account.

```python
ws["A1"] = ArrayFormula(
    "A1:T500",
    '=_xll.BEQS("My Momentum Screen","ScreenType=C")'                       # C = user custom
)
```

`ScreenType=B` is the default (Bloomberg sample); `ScreenType=C` is user-saved.

PRISM cannot define new EQS screens. If the user describes a screen but hasn't saved it, the right move is to author the equivalent `BQL.Query` (§8) directly. BQL replicates ~95% of EQS criteria and has the advantage of being entirely portable in the workbook.

---

## 10. ETFs and funds

| Field | Returns |
|---|---|
| `FUND_NET_ASSET_VAL` | NAV per share |
| `FUND_TOTAL_ASSETS` | AUM |
| `FUND_EXPENSE_RATIO` | TER (annualised) |
| `FUND_INCEPT_DT` | Inception date |
| `FUND_OBJECTIVE_LONG` | Long-form objective |
| `FUND_BMARK_TICKER` | Benchmark ticker |
| `FUND_BENCHMARK_NAME` | Benchmark name |
| `EQY_FUND_TRACK_ERROR_3YR` | 3Y tracking error vs benchmark |
| `FUND_HOLDINGS_AS_OF_DT` | Holdings as-of date |
| `FUND_HOLDINGS_AS_OF_DT_LAST_RPT_DT` | Last report date |

Holdings list:

```python
ws["A1"] = ArrayFormula(
    "A1:E600",                                                              # SPY ≈ 503 holdings
    '=_xll.BDS("SPY US Equity","FUND_HOLDINGS")'
)
```

Or BQL: `holdings('SPY US Equity')` returns the holdings universe.

---

## 11. Trading microstructure (intraday, VWAP, spreads)

### 11.1 VWAP / TWAP fields

| Mnemonic | Returns |
|---|---|
| `VWAP` | Day's volume-weighted average price |
| `VWAP_BID` / `VWAP_ASK` | VWAP filtered to bid / ask sides |
| `TWAP` | Time-weighted average price (less commonly available; install-dependent) |
| `EQY_PREV_VWAP` | Prior day's VWAP |
| `OPEN_VWAP` | VWAP at the open |
| `CLOSE_VWAP` | VWAP at the close |

For a multi-day VWAP series, pull as `BDH` (one observation per day):

```python
ws["A3"] = ArrayFormula(
    "A3:B254",
    '=_xll.BDH("AAPL US Equity","VWAP","-1Y","0D","Per=cd","Days=T","Dts=S","Dir=V")'
)
```

### 11.2 Bid-ask spread metrics

| Mnemonic | Returns |
|---|---|
| `BID_ASK_SPREAD_AVG_30D` | 30-day average bid-ask spread (in price units) |
| `BID_ASK_SPREAD_AVG_5D` / `_AVG_1D` | Shorter-window averages |
| `BID_ASK_SPREAD_AVG_PCT_30D` | Spread as % of mid |
| `QUOTED_SPREAD_BPS` | Quoted spread in basis points |
| `EFFECTIVE_SPREAD_BPS` | Effective spread (incorporates execution prices) |
| `BID_ASK_SPREAD` | Live spread (snapshot) |

### 11.3 Trade-level metrics

| Mnemonic | Returns |
|---|---|
| `TURNOVER` | Day's notional turnover (price × volume) |
| `EQY_TURNOVER_VAL_3M_AVG` | 3M average daily turnover |
| `EQY_AVG_TRADE_SIZE_30D` | Average trade size |
| `NUM_TRADES_RT` | Number of trades (real-time count) |
| `BLOCK_TRADE_COUNT_*` | Count of block-size trades |
| `PRIMARY_EXCH_PCT_VOL` | Share of volume on the primary exchange |
| `OFF_EXCHANGE_VOL_PCT` | Share of off-exchange / dark / TRF volume |

### 11.4 Intraday history (limited)

For sub-daily price history, `BDH` accepts an `Interval=` flag for OHLC bars:

```
=_xll.BDH(security, "OPEN,HIGH,LOW,CLOSE,VOLUME", start_dt, end_dt, "Interval=60", "Dts=S", "Dir=V")
```

Common intervals: `1`, `5`, `15`, `30`, `60` (minutes). Limitations:

- **History depth is short.** Most installs cap intraday history at 5-7 calendar days for 1-minute bars; up to ~90 days for 60-minute bars. Confirm with the user; intraday rarely goes back further than ~6 months under any granularity.
- **Sub-second tick data** (`BTKS<GO>`) is a separate Bloomberg product; not addressable via standard DAPI.
- **Trading hours apply.** US equities default to 09:30 – 16:00 ET. Pre-market / after-hours bars require `EVT_TIME_PRD=ALL_DAY` override.

```python
from datetime import date, timedelta

start = (date.today() - timedelta(days=5)).strftime("%Y%m%d")
end   = date.today().strftime("%Y%m%d")
ws["A3"] = ArrayFormula(
    "A3:F500",                                                              # ~5 days × ~7 hours × 60 bars + buffer
    f'=_xll.BDH("AAPL US Equity","OPEN,HIGH,LOW,CLOSE,VOLUME",'
    f'"{start}","{end}","Interval=1","Dts=S","Dir=V")'
)
```

### 11.5 Realised volatility (downstream of price)

| Mnemonic | Returns |
|---|---|
| `VOLATILITY_30D` / `_90D` / `_180D` / `_360D` | Realised vol (annualised) |
| `STD_DEV_RETURNS_30D` | 30-day return stdev |

For the implied-vs-realised view (typical "vol risk premium" workbook): pair with the vol-surface tickers from `bbg_options.md` (e.g. `SPXVV3M Index - VOLATILITY_90D`).

### 11.6 When to NOT use this surface

PRISM authors workbooks that refresh on open — they snapshot at refresh time. The trading-microstructure fields are most useful for:

- **End-of-day analytics** (VWAP, spread averages, turnover trends) — these are well-suited to PRISM workbooks.
- **Short-window intraday backtests** (last 5 days, 1-minute bars) — possible but tight.

Not suited:

- **Live trading boards** — use `RTD` formulas (refreshes while open) instead of `BDP` / `BDH`. PRISM doesn't author RTD-driven workbooks.
- **Tick-level execution analysis** — terminal `BTKS<GO>` / `TSM<GO>` products. PRISM cannot author into these.
- **Order-routing decisions** — EMSX / AIM; out of scope.

---

## 12. Quick reference

```
─────────────────────────────────────────────────────────────────────
  COMMON SCREENS — TEMPLATES
─────────────────────────────────────────────────────────────────────
  Value:        filter(<idx>, and(pe_ratio() < 15, px_to_book_ratio() < 1.5))
  Quality:      filter(<idx>, and(return_on_equity(fpt=A) > 0.15,
                                   tot_debt_to_tot_eqy(fpt=A) < 1.0))
  Momentum:     filter(<idx>, px_last() / sma(period=200) > 1.10)
  Mean rev:     filter(<idx>, and(rsi() < 30, beta_adj_overridable_3yr() < 1.3))
  Defensive:    filter(<idx>, and(beta_adj_overridable_3yr() < 0.7,
                                   eqy_dvd_yld_ind > 0.03))
  Growth:       filter(<idx>, and(sales_rev_turn(fpt=A, fpr=-1) > 0,
                                   pct_chg(sales_rev_turn(fpt=A, fpr=range(-3,0)),
                                            period=3) > 0.10))
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  COMMON INDICES
─────────────────────────────────────────────────────────────────────
  US:           SPX Index, NDX Index, RTY Index, INDU Index
  Global:       MXWD Index (ACWI), MXWO Index (World), MXEF Index (EM)
  Europe:       SX5E Index (EuroStoxx), SXXP Index (Stoxx 600), UKX Index
  Asia:         NKY Index, TPX Index (Japan), HSI Index, SHSZ300 Index
─────────────────────────────────────────────────────────────────────
```
