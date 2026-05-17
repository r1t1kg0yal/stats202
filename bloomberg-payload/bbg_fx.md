# FX — spot, forwards, NDFs, vol surface, carry

Spoke fetched on demand from the Bloomberg Excel hub. Covers FX-specific security syntax and field surface: spot / forward / NDF tickers, pricing sources, forward-points fields, the implied-volatility surface (ATM vol, risk reversals, butterflies), interest-rate differentials, and carry calculations.

For openpyxl mechanics and BQL grammar, see the hub. The yellow key for everything in this spoke is `Curncy`.

---

## 1. Pair conventions

FX pairs use the standard market convention `<base><quote>` (e.g. `EURUSD` = "how many USD per 1 EUR"). The pair as a Bloomberg security:

```
EURUSD Curncy             # spot, broker-composite quote
USDJPY Curncy             # spot
USDIDR Curncy             # spot (NDF currency)
```

Major pair conventions to know:

| Pair | Convention | Quote-side |
|---|---|---|
| EURUSD | USD per EUR | EUR is base |
| GBPUSD | USD per GBP | GBP is base |
| AUDUSD | USD per AUD | AUD is base |
| NZDUSD | USD per NZD | NZD is base |
| USDJPY | JPY per USD | USD is base |
| USDCHF | CHF per USD | USD is base |
| USDCAD | CAD per USD | USD is base |
| USDMXN, USDBRL | Local per USD | USD is base for most EM crosses |

If the user asks for "yen", default to `USDJPY Curncy` (and explain that it's JPY per USD). The reverse (`JPYUSD`) exists but is non-canonical.

---

## 2. Pricing sources

By default `EURUSD Curncy` returns Bloomberg's composite. Override with a pricing-source suffix:

| Suffix | Source |
|---|---|
| `BGN` | Bloomberg Generic — the canonical composite |
| `CMPN` | New York composite |
| `CMPL` | London composite |
| `CMPT` | Tokyo composite |
| `BFIX` | Bloomberg FX fixing (1500 LDN, 1600 LDN, 1100 NY, 1500 TYO, etc.) |
| `WMCO` (legacy `WMR`) | WM/Reuters fixing (4pm London) |
| `FED` | Federal Reserve H.10 noon rate |
| `ECB` | ECB reference rate (1:15 pm CET) |
| `BOE` | Bank of England 4pm fix |
| `RBA` | Reserve Bank of Australia fix |

```
EURUSD BGN Curncy        # Bloomberg generic
EURUSD WMCO Curncy       # WM/Reuters 4pm London
EURUSD ECB Curncy        # ECB reference (1:15 CET)
```

For backtesting / book-of-record work, `WMCO` is the industry-standard fix. For real-time work, `BGN` is the default.

---

## 3. Forwards and outrights

### 3.1 Forward outright tickers

```
EURUSD1M Curncy           # 1-month outright forward (price)
EURUSD3M Curncy           # 3-month outright forward
EURUSD6M Curncy           # 6-month outright forward
EURUSD1Y Curncy           # 1-year outright forward
EURUSD2Y Curncy           # 2-year outright forward
EURUSD5Y Curncy           # 5-year (longer tenors)
```

Tenor codes: `ON` (overnight), `TN` (tom-next), `SN` (spot-next), `1W`, `2W`, `1M`, `2M`, `3M`, `6M`, `9M`, `1Y`, `2Y`, `3Y`, `5Y`, `10Y`.

Tenor suffix-with-pricing-source pattern:

```
EURUSD1M BGN Curncy
EURUSD3M WMCO Curncy
```

### 3.2 Forward points

Forward points are quoted in **pips** (fractional units of the quote currency). Conventions:

- For EURUSD: 1 pip = 0.0001 (so 50 pips = 0.0050)
- For USDJPY: 1 pip = 0.01 (so 50 pips = 0.50)

Field names:

| Mnemonic | Returns |
|---|---|
| `PX_LAST` (on `EURUSD1M Curncy`) | Outright forward rate |
| `PX_LAST` (on `EUR1M Curncy`) — note this is "forward points only" form | Forward points |
| `FORWARD_POINTS_BID` / `FORWARD_POINTS_ASK` / `FORWARD_POINTS_MID` | Forward points (regardless of which ticker form) |
| `PX_FWD_NDF_PT_BID` | NDF forward points |
| `FRD_FAIR_VALUE` | Fair-value forward (rate-derived) |

The difference: `EURUSD1M Curncy` returns the outright (`1.0850`); `EUR1M Curncy` returns just the points (`50`). PRISM should always use the outright form unless the user explicitly asks for points.

---

## 4. NDFs (non-deliverable forwards)

NDFs are used for currencies with capital controls (CNY, INR, KRW, BRL, IDR, PHP, TWD, etc.). They settle in USD against a fix and don't physically deliver the local currency.

### 4.1 NDF tickers

```
USDINR1M NDF Curncy       # 1-month INR NDF
USDIDR1M NDF Curncy       # 1-month IDR NDF
USDPHP1M NDF Curncy       # 1-month PHP NDF
USDCNY1M NDF Curncy       # 1-month onshore CNY NDF (less standard)
USDKRW1M NDF Curncy       # 1-month KRW NDF
USDTWD1M NDF Curncy       # 1-month TWD NDF
USDBRL1M NDF Curncy       # 1-month BRL NDF
```

The `NDF` infix is what differentiates from the deliverable forward. Without `NDF` the ticker resolves to the deliverable forward (which may not exist for currencies with active capital controls — the cell returns `#N/A`).

### 4.2 CNY vs CNH (onshore vs offshore RMB)

| Pair | Meaning |
|---|---|
| `USDCNY Curncy` | Onshore CNY (mainland fixing) |
| `USDCNH Curncy` | Offshore CNH (Hong Kong / London market) |
| `USDCNY1M NDF Curncy` | Onshore NDF |
| `USDCNH1M Curncy` | Offshore deliverable forward |

The basis between CNY and CNH (often 100-500 pips wide during stress) is a tradeable signal. Pull both side-by-side for the comparison.

---

## 5. Implied volatility surface

The FX option market quotes vol in a standardised set of points: ATM, 25-delta risk reversal, 25-delta butterfly, 10-delta risk reversal, 10-delta butterfly — per tenor.

### 5.1 Ticker conventions

```
EURUSDV1M Curncy          # 1-month ATM volatility
EURUSDV3M Curncy          # 3-month ATM volatility
EURUSDV6M Curncy          # 6-month ATM volatility
EURUSDV1Y Curncy          # 1-year ATM volatility
EURUSD25R1M Curncy        # 1-month 25-delta risk reversal
EURUSD25R3M Curncy        # 3-month 25-delta risk reversal
EURUSD25B1M Curncy        # 1-month 25-delta butterfly
EURUSD10R3M Curncy        # 3-month 10-delta risk reversal
EURUSD10B3M Curncy        # 3-month 10-delta butterfly
```

Pattern: `<pair><X>R<tenor> Curncy` for risk reversal, `<pair><X>B<tenor> Curncy` for butterfly, where `X` is the delta (`25` or `10`).

Pull as ordinary `PX_LAST`:

```python
ws["A1"] = '=_xll.BDP("EURUSDV1M Curncy","PX_LAST")'                      # 1M ATM in vol points
```

### 5.2 Risk reversal vs butterfly — what they tell you

| Quote | Meaning |
|---|---|
| RR > 0 | Out-of-the-money calls (on the base) are more expensive than OTM puts — market is positioned for base appreciation, or hedging tail upside |
| RR < 0 | OTM puts are more expensive — market is positioned for base depreciation / paying for downside protection |
| BF | Always > 0; measures wing-vs-ATM richness. Larger BF = fatter tails priced in. |

EURUSD RR is typically negative in EUR-distress regimes (everyone wants USD calls / EUR puts). USDJPY RR is typically negative for JPY-strengthening tails (yen safe haven).

### 5.3 Implied-vol fields

| Mnemonic | Returns |
|---|---|
| `PX_LAST` | Implied vol in vol points (e.g. 8.5 = 8.5% annualised) |
| `IMPLIED_VOLATILITY_ATM` | ATM vol (when pulled from a non-vol-ticker like `EURUSD Curncy`) |
| `IVOL_ATM_3M` | 3M ATM vol shorthand |
| `IVOL_BUTTERFLY_25D_3M` | 3M 25-delta butterfly |
| `IVOL_RISKREVERSAL_25D_3M` | 3M 25-delta risk reversal |

### 5.4 Historical vol

| Mnemonic | Returns |
|---|---|
| `VOLATILITY_30D` | 30-day realised vol (annualised) |
| `VOLATILITY_90D` | 90-day realised vol |
| `VOLATILITY_180D` | 180-day realised vol |
| `RHO_HIST_VOL_30D` | 30-day historical vol (alias) |
| `STD_DEV_RETURNS_30DY` | 30-day stdev of returns |

The implied-realised spread (`IVOL_ATM_3M - VOLATILITY_90D` annualised) is a common signal — positive means implied > realised (you can sell vol cheaper than the market is realising; the asymmetry of selling vs buying makes this trickier).

---

## 6. Carry — interest-rate differential

Carry is the funding-currency interest rate minus the long-currency rate. For G10 pairs, the canonical proxy is the OIS / overnight-rate differential.

### 6.1 Direct IR-differential tickers

| Pattern | Returns |
|---|---|
| `IRDR1Y Curncy` | (USD - foreign) 1Y interest-rate differential — varies by install |
| `<pair>BV<tenor> Curncy` | Basis-swap vol (less common) |

For most desks, the cleaner approach is to pull the legs separately:

```python
# 1Y carry: USD OIS minus EUR OIS
ws["B1"] = '=_xll.BDP("USSO1 Curncy","PX_LAST")'                          # USD OIS 1Y
ws["B2"] = '=_xll.BDP("EUSWE1Y Curncy","PX_LAST")'                        # EUR OIS 1Y
ws["B3"] = '=B1-B2'                                                       # carry in pp
```

### 6.2 OIS tickers by currency (1Y unless noted)

| Currency | Ticker |
|---|---|
| USD | `USSO1 Curncy` (`USSO2`, `USSO3`, ... for longer tenors) |
| EUR | `EUSWE1Y Curncy` (or `EONIA1Y Curncy` legacy) |
| GBP | `BPSWS1 Curncy` |
| JPY | `JYSO1 Curncy` |
| AUD | `ADSO1 Curncy` |
| NZD | `NDSO1 Curncy` |
| CAD | `CDSO1 Curncy` |
| CHF | `SFSNT1 Curncy` |
| NOK | `NKSWNI1 Curncy` |
| SEK | `SKSOR1 Curncy` |

For EM carry trade work, use central-bank policy rates instead of OIS (less liquid OIS markets):

| Currency | Policy rate ticker |
|---|---|
| BRL | `BZSTSETA Index` |
| MXN | `MXONBR Index` |
| TRY | `TUBR1WK Index` |
| ZAR | `SARPRATE Index` |
| INR | `INRRP Index` |
| IDR | `IDBIRATE Index` |

---

## 7. Cross-currency basis

Cross-currency basis is the spread you pay (or receive) to swap USD for foreign currency at maturity, beyond the interest-rate differential. Persistently negative basis indicates USD funding stress.

| Pattern | Returns |
|---|---|
| `EUBSC1 Curncy` | 1-year EUR/USD basis swap |
| `EUBSC5 Curncy` | 5-year EUR/USD basis swap |
| `JYBSC1 Curncy` | 1-year JPY/USD basis swap |
| `BPBSC1 Curncy` | 1-year GBP/USD basis swap |

Pull as `PX_LAST` — value in bp.

---

## 8. BQL FX patterns

BQL coverage of FX is thinner than equity or fixed income. The most useful FX functions:

```excel
=_xll.BQL.Query("get(name(), px_last) for(['EURUSD Curncy', 'USDJPY Curncy', 'GBPUSD Curncy'])")
```

For an FX-vol time series:

```excel
=_xll.BQL.Query("get(px_last(dates=range(-1Y, 0D), frq=D, fill=PREV)) for(['EURUSDV1M Curncy', 'EURUSDV3M Curncy', 'EURUSDV1Y Curncy'])")
```

For a basket of carry pairs:

```excel
=_xll.BQL.Query("get(name(), px_last, volatility_30d) for(['AUDUSD Curncy', 'NZDUSD Curncy', 'USDBRL Curncy', 'USDMXN Curncy', 'USDZAR Curncy'])")
```

There is no BQL `fxsurface()` builder — for the full vol surface, the user pulls the 5-7 standard surface tickers per pair / tenor.

---

## 9. Anti-patterns specific to FX

| Mistake | Symptom | Fix |
|---|---|---|
| Pulling `JPYUSD Curncy` for "yen against the dollar" | Non-canonical; may return `#N/A` or an inverted convention | Use `USDJPY Curncy`; quote convention is JPY per USD |
| Pulling `EURUSD Curncy` for the 1M outright | Returns spot, not 1M forward | Use `EURUSD1M Curncy` for the outright forward; `EUR1M Curncy` for just the points |
| Using `EURUSD Curncy` history without pricing-source override | Composite quotes drift slightly day-over-day vs published fixes | For backtesting against published references, pin to `WMCO` (4pm London) or `BFIX` |
| Pulling EM forwards without `NDF` infix | Returns `#N/A` for INR / IDR / KRW / TWD / BRL | Add `NDF` between pair and tenor: `USDINR1M NDF Curncy` |
| Treating `EURUSD25R3M Curncy` as a price | It's a vol in vol points (pp annualised), not a price | Header labels: "vol pts" or "% annualised" |
| Conflating CNY (onshore) and CNH (offshore) for "China FX" | Different markets, different liquidity | If unsure, default to `USDCNH Curncy` (offshore is more universally accessible); note onshore vs offshore in the header |
| Pulling FX forward points without specifying tenor | The bare `EUR Curncy` doesn't exist; bare pair tickers default to spot | Always include tenor in the ticker for forwards |
| Using EUR/USD basis-swap (`EUBSC*`) as if it's the IR differential | Basis-swap is the spread BEYOND the IR-differential, not the IR-differential itself | IR-differential = OIS(USD) − OIS(EUR); basis = the additional spread |

---

## 10. Quick reference

```
─────────────────────────────────────────────────────────────────────
  FX SECURITY SYNTAX
─────────────────────────────────────────────────────────────────────
  Spot:                EURUSD Curncy                  composite
  Spot (pinned):       EURUSD WMCO Curncy             4pm London fix
  Forward outright:    EURUSD3M Curncy                3M outright rate
  Forward points:      EUR3M Curncy                   3M points only
  NDF:                 USDINR1M NDF Curncy            1M INR NDF
  ATM vol:             EURUSDV3M Curncy               3M ATM vol
  25Δ risk reversal:   EURUSD25R3M Curncy             3M 25-delta RR
  25Δ butterfly:       EURUSD25B3M Curncy             3M 25-delta BF
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  CARRY LEGS — OIS BY CURRENCY (1Y, suffix for longer)
─────────────────────────────────────────────────────────────────────
  USD            USSO1 Curncy
  EUR            EUSWE1Y Curncy
  GBP            BPSWS1 Curncy
  JPY            JYSO1 Curncy
  AUD            ADSO1 Curncy
  NZD            NDSO1 Curncy
  CAD            CDSO1 Curncy
  CHF            SFSNT1 Curncy
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  PRICING SOURCES — WHEN TO USE WHICH
─────────────────────────────────────────────────────────────────────
  BGN          Default; Bloomberg composite              real-time work
  WMCO         WM/Reuters 4pm London fix                 book-of-record / backtest
  BFIX         Bloomberg FX fix                          benchmark-tracking
  CMPN/L/T     NY / London / Tokyo composites            regional analysis
  FED          Federal Reserve H.10 noon                 official reference
  ECB          ECB 1:15 CET reference                    EU regulatory
─────────────────────────────────────────────────────────────────────
```
