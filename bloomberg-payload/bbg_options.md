# Options — chain, Greeks, IV, vol surface

Spoke fetched on demand from the Bloomberg Excel hub. Covers listed options across underlying classes: equity options, ETF options, index options, futures options. Includes the per-option security syntax, OPT_CHAIN BDS field, Greeks (delta / gamma / theta / vega / rho), implied-vol fields, the vol-surface index tickers (BSKW / BVOL family), and skew measurement.

For OTC FX options, see `bbg_fx.md` §5 (FX vol surface). For openpyxl mechanics and BQL grammar, see the hub.

---

## 1. Per-option security syntax

Listed options have their own securities — Bloomberg encodes ticker, expiry, put/call, and strike in the security string. The yellow key follows the underlying.

### 1.1 Stock and ETF options (yellow key `Equity`)

```
AAPL US 06/21/24 C200 Equity            # AAPL Jun 21 2024 $200 call
AAPL US 06/21/24 P195 Equity            # AAPL Jun 21 2024 $195 put
SPY US 12/20/24 C500 Equity             # SPY ETF Dec 20 2024 $500 call
NVDA US 01/17/25 P800 Equity            # NVDA Jan 17 2025 $800 put
TSLA US 03/15/24 C250.50 Equity         # Decimal strikes use `.`
```

Pattern: `<underlying ticker> <exchange> <MM/DD/YY> <C|P><strike> Equity`

Date format is `MM/DD/YY` (or `MM/DD/YYYY` — both accepted). The strike accepts decimals (`C250.50`). The exchange code (`US`, `LN`, `JP`, etc.) matches the underlying's exchange.

Weekly options use the same form — Bloomberg disambiguates by the specific expiry date. Monthly options expire on the 3rd Friday; weekly options expire on every Friday.

### 1.2 Index options (yellow key `Index`)

Index options are cash-settled, not deliverable. Yellow key is `Index`, NOT `Equity`, even when the underlying index (e.g. SPX) is more commonly thought of as equity-related.

```
SPX 06/21/24 C5500 Index                # SPX Jun 21 2024 $5500 call
SPXW 06/14/24 C5400 Index               # SPX Weekly (PM-settled, "W" suffix)
NDX 12/20/24 P19000 Index               # NDX Dec 20 2024 $19000 put
VIX 08/21/24 C18 Index                  # VIX Aug 21 2024 $18 call
RUT 09/20/24 P2000 Index                # Russell 2000 Sep 20 2024 $2000 put
```

The `SPXW` (SPX Weekly) and `SPXQ` (SPX Quarterly) families have their own tickers. The standard `SPX` ticker resolves to the 3rd-Friday monthly contract.

### 1.3 Futures options (yellow key `Comdty`)

Futures options reference a specific futures contract. The syntax embeds the futures month code + put/call + strike.

```
CLM4P 60 Comdty                         # WTI Jun 2024 future, Put, $60 strike
CLM4C 80 Comdty                         # WTI Jun 2024 future, Call, $80 strike
ESM4C 5200 Comdty                       # S&P 500 E-Mini Jun 2024, Call, 5200
GCQ4P 2200 Comdty                       # Gold Aug 2024, Put, $2200
```

Pattern: `<futures-root><month-code><year-digit><P|C> <strike> Comdty`. Month codes are the same as futures (§§ commodities spoke): `F`=Jan, `G`=Feb, ..., `Z`=Dec.

### 1.4 FX options (yellow key `Curncy`)

FX options have multiple ticker conventions depending on whether they're listed (PHLX-style) or OTC-style vol-surface points.

```
EURUSD 06/21/24 C1.10 Curncy            # listed-style: EURUSD Jun 2024 Call $1.10
```

For OTC vol-surface work (where you reference standardised ATM / 25-delta / 10-delta points), use the FX-vol tickers documented in `bbg_fx.md` §5 — `EURUSDV1M Curncy`, `EURUSD25R1M Curncy`, `EURUSD25B1M Curncy`. The listed-options syntax above is rarely used in PRISM workbooks.

---

## 2. `OPT_CHAIN` — the entire chain in one BDS call

The most-used field for option work. Returns every listed option for the underlying — call AND put, every strike, every expiry — in one `BDS` array.

```
=_xll.BDS(<underlying>, "OPT_CHAIN", [optional overrides])
```

Common overrides:

| Override | Values | Effect |
|---|---|---|
| `CHAIN_EXP_DT_OVRD` | `MM/DD/YYYY` or relative | Filter to a single expiry |
| `CHAIN_STRIKE_PX_OVRD` | float | Filter to a single strike |
| `CHAIN_PUT_CALL_TYPE_OVRD` | `C` / `P` | Filter to calls or puts only |
| `CHAIN_ENABLE_FILTERS_OVRD` | `Y` / `N` | Toggle Bloomberg's default filters (e.g. liquid contracts only) |
| `CHAIN_POINTS_OVRD` | integer | Number of strikes around ATM |

```python
ws["A1"] = ArrayFormula(
    "A1:H800",                                                              # SPX has 1500+ active options; size precisely
    '=_xll.BDS("SPX Index","OPT_CHAIN","CHAIN_EXP_DT_OVRD=06/21/2024")'    # 1 expiry only
)
```

Returned columns (exact set varies by install; commonly):

| Col | Content |
|---|---|
| 1 | Option ticker (e.g. `SPX 06/21/24 C5500 Index`) |
| 2 | Strike |
| 3 | Put / Call |
| 4 | Expiry date |
| 5 | Last trade price |
| 6 | Bid |
| 7 | Ask |
| 8 | Volume / Open interest |

**Sizing matters as always.** SPX has ~1,500 active options at any time; AAPL has ~3,000+ (every expiry × every strike × P/C). Filter aggressively via `CHAIN_*_OVRD` overrides, or isolate the array on a dedicated `_chain` fetch sheet per the hub's §1.4 / §7.3 pattern. The chain is a textbook drift-prone count.

---

## 3. Per-option fields

Once PRISM has the option ticker (from `OPT_CHAIN` or constructed directly), `BDP` gives the per-contract analytics.

### 3.1 Pricing

| Mnemonic | Returns |
|---|---|
| `PX_LAST` | Last traded option price |
| `PX_BID` / `PX_ASK` / `PX_MID` | Bid / ask / mid (model or market) |
| `LAST_PRICE_TIME_TODAY_RT` | Last trade timestamp |
| `LAST_TRADE_DATE_TIME` | Most recent trade |
| `MULTIPLIER` | Contract multiplier (100 for stock options, 100 for index, varies for futures options) |

### 3.2 Greeks

| Mnemonic | Returns |
|---|---|
| `OPT_DELTA_BID` / `OPT_DELTA_MID` / `OPT_DELTA_ASK` | Delta (∂price/∂underlying); range `[-1, 0]` for puts, `[0, 1]` for calls |
| `OPT_GAMMA_BID` / `OPT_GAMMA_MID` | Gamma (∂delta/∂underlying); always positive for long options |
| `OPT_THETA_BID` / `OPT_THETA_MID` | Theta (∂price/∂time); negative for long options (time decay) |
| `OPT_VEGA_BID` / `OPT_VEGA_MID` | Vega (∂price/∂IV); always positive for long options |
| `OPT_RHO_BID` / `OPT_RHO_MID` | Rho (∂price/∂interest rate); positive for calls, negative for puts |

Greeks are **Bloomberg-model-derived**, not market-quoted. Bloomberg uses Black-Scholes with model-specific adjustments per asset class (binomial trees for American-style equity options, Black-76 for futures options, etc.). The mid Greeks are the most useful for portfolio risk; the bid / ask variants reflect the IV surface at the bid / ask.

### 3.3 Implied volatility

| Mnemonic | Returns |
|---|---|
| `IMPLIED_VOLATILITY_BID` / `IMPLIED_VOLATILITY_MID` / `IMPLIED_VOLATILITY_ASK` | IV in vol points (e.g. `25.5` = 25.5% annualised) |
| `IVOL_LAST` | Last-traded IV |
| `IVOL_LAST_DT` | Date of last IV update |

For historical IV (the surface evolving over time), pull `BDH` on `IMPLIED_VOLATILITY_MID`:

```python
ws["A3"] = ArrayFormula(
    "A3:B260",
    '=_xll.BDH("AAPL US 06/21/24 C200 Equity","IMPLIED_VOLATILITY_MID","-1Y","0D","Per=cd","Fill=N","Dts=S","Dir=V")'
)
```

Note: the same option's IV history is only meaningful while the option exists (i.e., until expiry). For a long-running "IV at 3M ATM" series, use the vol-surface index tickers in §5 below.

### 3.4 Strike / expiry / structural

| Mnemonic | Returns |
|---|---|
| `OPT_STRIKE_PX` | Strike |
| `OPT_EXPIRE_DT` | Expiry date |
| `OPT_PUT_CALL` | `P` or `C` |
| `OPT_DAYS_EXPIRE` | Days to expiry |
| `OPT_OPEN_INT` | Open interest |
| `OPT_VOLUME` | Day's volume |
| `OPT_UNDL_TICKER` | Underlying ticker |
| `OPT_UNDL_PX` | Underlying price at last update |
| `OPT_AMERICAN_OR_EUROPEAN` | `American` or `European` exercise style |
| `OPT_CONTRACT_SIZE` | Shares per contract (100 standard, 10 for mini, etc.) |
| `OPT_SETTLE_TYP` | `Physical` (deliverable) or `Cash` (index options) |
| `OPT_FIRST_TRADE_DT` | First trading date |

---

## 4. Implied-volatility surface — index tickers

For long-running vol-surface work (e.g. "S&P 500 3-month ATM volatility history over 10 years"), the right approach is NOT per-option fields (each option's life is short) — it's **vol-surface index tickers** that Bloomberg maintains as continuous series.

### 4.1 ATM vol tickers per major underlying

| Underlying | 1M ATM | 3M ATM | 6M ATM | 1Y ATM |
|---|---|---|---|---|
| S&P 500 | `SPXVV1M Index` | `SPXVV3M Index` | `SPXVV6M Index` | `SPXVV1Y Index` |
| NDX | `NDXV1M Index` | `NDXV3M Index` | `NDXV6M Index` | `NDXV1Y Index` |
| RTY | `RTYV1M Index` | `RTYV3M Index` | `RTYV6M Index` | `RTYV1Y Index` |
| DJIA | `INDUVV1M Index` (varies by install) | | | |
| Single stocks | `<ticker>V1M Equity` | `<ticker>V3M Equity` | (e.g. `AAPLV3M Equity`) | |

Pull these as ordinary `Index` securities:

```python
ws["A3"] = ArrayFormula(
    "A3:B1827",                                                             # 5Y daily
    '=_xll.BDH("SPXVV3M Index","PX_LAST","-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
```

Returns the 3-month ATM IV in vol points across history. This is what the buy-side commonly calls "3M ATM vol" in research charts.

### 4.2 Skew tickers (risk reversals + butterflies)

Bloomberg publishes skew surfaces as `Index` securities for the major underlyings. The convention follows FX-vol but with delta points:

| Pattern | Meaning |
|---|---|
| `SPX25R1M Index` | SPX 1M 25-delta risk reversal |
| `SPX25B1M Index` | SPX 1M 25-delta butterfly |
| `SPX10R3M Index` | SPX 3M 10-delta risk reversal |
| `SPX10B3M Index` | SPX 3M 10-delta butterfly |

Risk reversal (`R`) measures call-vs-put skew: a negative RR means OTM puts are more expensive than OTM calls (the typical equity market regime — investors paying for crash protection). Butterfly (`B`) measures wing-vs-ATM richness: higher BF means fatter tails priced in.

For broader / smaller-cap underlyings, BSKW (`BSKW<GO>` on terminal) is the navigation page.

### 4.3 VIX family

| Ticker | Meaning |
|---|---|
| `VIX Index` | CBOE Volatility Index (30-day expected SPX vol, model-free) |
| `VVIX Index` | Volatility of VIX (vol-of-vol) |
| `VXN Index` | NDX volatility |
| `VXTH Index` | VIX Tail Hedge index |
| `SKEW Index` | CBOE Skew (tail-risk implied by deep-OTM puts) |
| `VXEEM Index` | EM Volatility |
| `VIX9D Index` | 9-day VIX |
| `VIX3M Index` | 3-month VIX |
| `VIX6M Index` | 6-month VIX |

VIX futures use the standard futures-generic convention (yellow key `Index`):

| Ticker | Meaning |
|---|---|
| `UX1 Index` | Front-month VIX future |
| `UX2 Index` | Second VIX future |
| `UX1 R:00_0_R Index` | Ratio-adjusted continuous VIX-front |

The slope `UX2 - UX1` is the canonical "VIX term structure" signal — positive = contango (normal); negative = backwardation (stress regime).

### 4.4 Realised vol fields

For comparing implied to realised:

| Mnemonic | Returns |
|---|---|
| `VOLATILITY_30D` | 30-day realised vol (annualised) |
| `VOLATILITY_90D` | 90-day realised vol |
| `VOLATILITY_180D` | 180-day realised vol |
| `VOLATILITY_360D` | 360-day realised vol |
| `STD_DEV_RETURNS_30D` | 30-day stdev of daily returns |

The implied-realised spread (`SPXVV3M Index - VOLATILITY_90D`, both annualised) is a common signal. Positive spread means options are pricing in more vol than recent history; negative means options look cheap vs realised.

---

## 5. BQL options patterns

BQL coverage of listed options is limited compared to fundamentals. The most useful patterns:

### 5.1 Pull chain via BQL

```excel
=_xll.BQL.Query("get(name(), opt_strike_px(), opt_put_call(), opt_expire_dt(), px_last, implied_volatility_mid(), opt_delta_mid()) for(options('AAPL US Equity', expiry_date=06/21/2024))")
```

The BQL `options()` universe builder filters by expiry, strike range, put/call. Behaviour varies by enterprise install — verify with the user before authoring against `options()`.

### 5.2 Greek time series

```excel
=_xll.BQL.Query("get(opt_delta_mid(dates=range(-3M, 0D), frq=D)) for(['SPY US 06/21/24 C500 Equity'])")
```

Returns the delta history for a specific contract over its tradable life.

### 5.3 Cross-section of vol-surface tickers (compare ATM vol across underlyings)

```excel
=_xll.BQL.Query("get(name(), px_last) for(['SPXVV1M Index', 'SPXVV3M Index', 'SPXVV6M Index', 'NDXV1M Index', 'NDXV3M Index', 'RTYV1M Index', 'VIX Index', 'VXN Index'])")
```

---

## 6. Worked patterns

### 6.1 Pull SPX option chain for nearest expiry, with Greeks

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
wb.remove(wb["Sheet"])
ws_data = wb.create_sheet("_chain")
ws_data.sheet_state = "hidden"
ws_view = wb.create_sheet("Chain")

UNDL  = "SPX Index"
EXPIRY = "06/21/2024"
N_ROWS = 600

ws_data["A1"] = ArrayFormula(
    f"A1:H{N_ROWS}",
    f'=_xll.BDS("{UNDL}","OPT_CHAIN",'
    f'"CHAIN_EXP_DT_OVRD={EXPIRY}",'
    f'"CHAIN_ENABLE_FILTERS_OVRD=Y")'
)

hdrs = ["Option ticker", "Strike", "P/C", "Expiry",
        "Last", "Bid", "Ask", "Open Int",
        "Delta", "Gamma", "Theta", "Vega", "IV"]
for c, h in enumerate(hdrs, start=1):
    ws_view.cell(row=1, column=c, value=h)

for r in range(2, N_ROWS):
    src = r - 1
    for c in range(1, 9):
        col = chr(ord("A") + c - 1)
        ws_view.cell(row=r, column=c,
                     value=f'=IFERROR(INDEX(_chain!{col}:{col},{src}),"")')
    ws_view.cell(row=r, column=9,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r},"OPT_DELTA_MID"))')
    ws_view.cell(row=r, column=10,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r},"OPT_GAMMA_MID"))')
    ws_view.cell(row=r, column=11,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r},"OPT_THETA_MID"))')
    ws_view.cell(row=r, column=12,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r},"OPT_VEGA_MID"))')
    ws_view.cell(row=r, column=13,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r},"IMPLIED_VOLATILITY_MID"))')

wb.save("spx_chain.xlsx")
```

The pattern follows the hub §7.3 dedicated-fetch-sheet idiom: `_chain` carries the raw `OPT_CHAIN` BDS array (sized loosely); the `Chain` user-facing sheet projects via `INDEX` for the chain columns and pulls Greeks per-row via `BDP` calls. Sorts / filters / annotations live on the user-facing sheet without hitting array-formula locks.

### 6.2 SPX vol-surface dashboard (5Y history of ATM term structure + skew)

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "VolSurface"

ws["A1"] = "SPX vol-surface — 5Y daily history"

tickers = ",".join([
    "SPXVV1M Index", "SPXVV3M Index", "SPXVV6M Index", "SPXVV1Y Index",
    "SPX25R1M Index", "SPX25R3M Index",
    "SPX25B1M Index", "SPX25B3M Index",
    "VIX Index", "SKEW Index",
])

ws["A3"] = ArrayFormula(
    "A3:K1827",                                                             # 5Y daily + header
    f'=_xll.BDH("{tickers}","PX_LAST","-5Y","0D",'
    f'"Per=cd","Fill=P","Dts=S","Dir=V")'
)

wb.save("spx_vol_surface.xlsx")
```

After refresh: column A = date, columns B:K = the 10 vol-surface series side-by-side. Downstream Excel charts plot the term structure (1M / 3M / 6M / 1Y) and the skew evolution.

### 6.3 VIX term structure (front-month vs second-month spread)

```python
ws["A3"] = ArrayFormula(
    "A3:D1262",                                                             # 5Y daily
    '=_xll.BDH("UX1 Index,UX2 Index,VIX Index","PX_LAST","-5Y","0D",'
    '"Per=cd","Fill=P","Dts=S","Dir=V")'
)
ws["E2"] = "UX2 - UX1 (contango = +)"
for r in range(3, 1265):
    ws.cell(row=r, column=5, value=f'=IF(OR(B{r}="",C{r}=""),"",C{r}-B{r})')
```

Positive `UX2 - UX1` = contango (normal regime); negative = backwardation (stress regime). Pair with `VIX Index` itself for the level.

---

## 7. Anti-patterns specific to options

| Mistake | Symptom | Fix |
|---|---|---|
| Wrong yellow key for index options (`SPX 06/21/24 C5500 Equity`) | `#N/A Invalid Security` | Index options use `Index` yellow key, not `Equity` (even though SPX is "equity-like") |
| Pulling `OPT_DELTA` (no suffix) | Returns BID or null depending on install | Always specify suffix: `OPT_DELTA_MID` for portfolio-risk work, `OPT_DELTA_BID/ASK` if you specifically want market-quoted directionality |
| Using `BDH` on per-option IV for "long-running ATM vol history" | History ends at option expiry | Use vol-surface index tickers (`SPXVV3M Index` etc.) for continuous ATM history; per-option IV is for the option's lifespan only |
| `OPT_CHAIN` with no `CHAIN_EXP_DT_OVRD` for SPX / AAPL | Returns 1,500-3,000+ rows; array-formula lockup; refresh is slow | Filter to one expiry at a time; or pull `OPT_CHAIN_LIVE` for only actively-traded contracts |
| Treating Greeks as market quotes | They drift when the underlying IV surface moves | Greeks are Bloomberg-model values from the prevailing IV surface; document this in workbook notes |
| Confusing strikes for futures options (`CLM4P 60 Comdty` vs `CLM4 P60 Comdty`) | Wrong parsing | The form is `<root><month-code><year><P|C> <strike> Comdty` — no space between month code and P/C, space before strike |
| Mixing American and European exercise for time-decay analysis | American options decay differently near expiry due to early-exercise premium | Check `OPT_AMERICAN_OR_EUROPEAN` per contract; equity options are American, index options are European |
| Pulling vol-surface index tickers (`SPXVV3M Index`) and treating as price | They're vol points (% annualised), not prices | Label workbook columns "vol pts" / "% annualised" |
| Forgetting weeklies vs monthlies for index options (`SPX` vs `SPXW` vs `SPXQ`) | Different settlement times (AM vs PM), different liquidity | The Bloomberg ticker disambiguates; use `SPXW` for PM-settled weeklies, `SPX` for AM-settled standard |

---

## 8. Quick reference

```
─────────────────────────────────────────────────────────────────────
  OPTION SECURITY SYNTAX BY UNDERLYING CLASS
─────────────────────────────────────────────────────────────────────
  Stock / ETF:    AAPL US 06/21/24 C200 Equity
                  format: <undl> <mkt> <MM/DD/YY> <C|P><strike> Equity
  Index:          SPX 06/21/24 C5500 Index
                  (note: cash-settled, Index yellow key)
                  Weeklies: SPXW 06/14/24 C5400 Index
  Futures:        CLM4P 60 Comdty  (WTI Jun-24 fut, Put, $60)
                  format: <root><month><year><P|C> <strike> Comdty
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  KEY PER-OPTION FIELDS
─────────────────────────────────────────────────────────────────────
  Greeks (mid):  OPT_DELTA_MID, OPT_GAMMA_MID,
                 OPT_THETA_MID, OPT_VEGA_MID, OPT_RHO_MID
  IV:            IMPLIED_VOLATILITY_MID / BID / ASK
  Strike/expiry: OPT_STRIKE_PX, OPT_EXPIRE_DT, OPT_PUT_CALL,
                 OPT_DAYS_EXPIRE
  Open int / vol:OPT_OPEN_INT, OPT_VOLUME
  Underlying:    OPT_UNDL_TICKER, OPT_UNDL_PX
  Structural:    OPT_AMERICAN_OR_EUROPEAN, OPT_SETTLE_TYP,
                 OPT_CONTRACT_SIZE, MULTIPLIER
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  VOL-SURFACE INDEX TICKERS
─────────────────────────────────────────────────────────────────────
  SPX ATM by tenor:    SPXVV1M / SPXVV3M / SPXVV6M / SPXVV1Y Index
  NDX ATM by tenor:    NDXV1M / NDXV3M / NDXV6M / NDXV1Y Index
  RTY ATM by tenor:    RTYV1M / RTYV3M / RTYV6M Index
  SPX skew:            SPX25R1M / SPX25R3M Index (risk reversal)
                       SPX25B1M / SPX25B3M Index (butterfly)
  VIX family:          VIX Index, VVIX Index, SKEW Index,
                       VIX9D / VIX3M / VIX6M Index
  VIX futures:         UX1 Index, UX2 Index (front / second)
  NDX vol:             VXN Index
  Single-stock ATM:    <tkr>V1M Equity, <tkr>V3M Equity
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  OPT_CHAIN OVERRIDES
─────────────────────────────────────────────────────────────────────
  CHAIN_EXP_DT_OVRD       single expiry filter (MM/DD/YYYY)
  CHAIN_STRIKE_PX_OVRD    single strike filter
  CHAIN_PUT_CALL_TYPE_OVRD  C or P only
  CHAIN_POINTS_OVRD       N strikes around ATM
  CHAIN_ENABLE_FILTERS_OVRD  Y / N — Bloomberg's default liquid-only filter
─────────────────────────────────────────────────────────────────────
```
