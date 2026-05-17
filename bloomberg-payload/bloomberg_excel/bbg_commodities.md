# Commodities — futures, generics, curves, COT, inventories

Spoke fetched on demand from the Bloomberg Excel hub. Covers futures-specific security syntax (generics vs specific contracts), contract-specification fields, term-structure / curve work, CFTC Commitments of Traders positioning, and supply-side inventories.

For openpyxl mechanics and BQL grammar, see the hub. For options on futures (e.g. `CLM4P 60 Comdty`), fetch `bbg_options.md` — the futures-option syntax and Greek fields live there. The yellow key for everything in this spoke is `Comdty` (cash-futures).

---

## 1. Futures ticker syntax

### 1.1 Generic vs specific contracts

| Form | Meaning |
|---|---|
| `CL1 Comdty` | Generic front-month WTI crude (rolls automatically) |
| `CL2 Comdty` | Second-nearby contract |
| `CL3 Comdty`, ... | N-th nearby contract |
| `CLZ4 Comdty` | Specific contract: WTI December 2024 |
| `CLN5 Comdty` | WTI July 2025 |
| `CLZ24 Comdty` (4-digit year, install-dependent) | Same as `CLZ4` on installs that prefer 4-digit |

The generic form (`CL1`) is what PRISM should use for time-series work — it splices contract rolls into a continuous series. The specific form is for working with a single contract's life (e.g. analysing the curve at a point in time).

### 1.2 Month codes

| Code | Month | | Code | Month |
|---|---|---|---|---|
| F | January | | N | July |
| G | February | | Q | August |
| H | March | | U | September |
| J | April | | V | October |
| K | May | | X | November |
| M | June | | Z | December |

So `CLZ4` = WTI for delivery December 2024. `GCM5` = Gold for delivery June 2025.

### 1.3 Roll-adjusted generic conventions

Bloomberg's generic series stitches together contract prices at the roll date. Different methods:

| Suffix / form | Roll method |
|---|---|
| `CL1 Comdty` (default) | Active-contract method (rolls when front loses prominence) |
| `CL1 R:00_0_R Comdty` | Backward-ratio-adjusted |
| `CL1 R:00_0_A Comdty` | Backward-arithmetic-adjusted |
| `CL1 R:00_0_N Comdty` | No adjustment (price discontinuity at roll) |

Default `CL1 Comdty` is fine for charting. For backtests where price continuity matters (e.g. trend-following), the ratio-adjusted variant is preferred.

---

## 2. Major contract tickers

### 2.1 Energy

| Contract | Ticker | Exchange | Multiplier | Unit |
|---|---|---|---|---|
| WTI Crude Oil | `CL1 Comdty` | NYMEX | 1,000 bbl | USD/bbl |
| Brent Crude Oil | `CO1 Comdty` | ICE | 1,000 bbl | USD/bbl |
| Natural Gas (Henry Hub) | `NG1 Comdty` | NYMEX | 10,000 MMBtu | USD/MMBtu |
| Heating Oil (ULSD) | `HO1 Comdty` | NYMEX | 42,000 gal | USD/gal |
| RBOB Gasoline | `XB1 Comdty` | NYMEX | 42,000 gal | USD/gal |
| Gas Oil | `QS1 Comdty` | ICE | 100 metric tons | USD/metric ton |
| Dutch TTF Gas | `TZT1 Comdty` (or `LFP1 Comdty`) | ICE | 1 MWh | EUR/MWh |

### 2.2 Precious metals

| Contract | Ticker | Exchange | Multiplier | Unit |
|---|---|---|---|---|
| Gold | `GC1 Comdty` | COMEX | 100 oz | USD/oz |
| Silver | `SI1 Comdty` | COMEX | 5,000 oz | USD/oz |
| Platinum | `PL1 Comdty` | NYMEX | 50 oz | USD/oz |
| Palladium | `PA1 Comdty` | NYMEX | 100 oz | USD/oz |

### 2.3 Base / industrial metals

| Contract | Ticker | Exchange | Multiplier | Unit |
|---|---|---|---|---|
| Copper (LME) | `LMCADS03 Comdty` (3-month) / `LP1 Comdty` (generic) | LME | 25 tonnes | USD/tonne |
| Copper (COMEX) | `HG1 Comdty` | COMEX | 25,000 lb | USD/lb |
| Aluminium | `LMAHDS03 Comdty` / `LA1 Comdty` | LME | 25 tonnes | USD/tonne |
| Zinc | `LMZSDS03 Comdty` | LME | 25 tonnes | USD/tonne |
| Nickel | `LMNIDS03 Comdty` | LME | 6 tonnes | USD/tonne |
| Iron Ore (Singapore) | `SCO1 Comdty` (`SGX SCFI`) | SGX | 100 tonnes | USD/tonne |

### 2.4 Agriculturals

Note many ag tickers use a space-separated form (e.g. `S 1` for soybeans — note the space).

| Contract | Ticker | Exchange | Multiplier | Unit |
|---|---|---|---|---|
| Corn | `C 1 Comdty` (note space) | CBOT | 5,000 bu | USc/bu |
| Soybeans | `S 1 Comdty` (note space) | CBOT | 5,000 bu | USc/bu |
| Wheat | `W 1 Comdty` (note space) | CBOT | 5,000 bu | USc/bu |
| Cotton | `CT1 Comdty` | ICE | 50,000 lb | USc/lb |
| Sugar | `SB1 Comdty` | ICE | 112,000 lb | USc/lb |
| Coffee | `KC1 Comdty` | ICE | 37,500 lb | USc/lb |
| Cocoa | `CC1 Comdty` | ICE | 10 tonnes | USD/tonne |
| Live Cattle | `LC1 Comdty` | CME | 40,000 lb | USc/lb |
| Lean Hogs | `LH1 Comdty` | CME | 40,000 lb | USc/lb |
| Soybean Oil | `BO1 Comdty` | CBOT | 60,000 lb | USc/lb |
| Soybean Meal | `SM1 Comdty` | CBOT | 100 short tons | USD/ton |
| Lumber | `LBR1 Comdty` | CME | 110,000 bd ft | USD/1000 bd ft |

### 2.5 Interest-rate futures

Mentioned in `bbg_macro.md` (COT context) and `bbg_fixed_income.md` for completeness:

| Contract | Ticker |
|---|---|
| Fed Funds | `FF1 Comdty` |
| Eurodollar (legacy, mostly retired in favor of SOFR) | `ED1 Comdty` |
| 3M SOFR | `SFR1 Comdty` |
| US 2Y Treasury | `TU1 Comdty` |
| US 5Y Treasury | `FV1 Comdty` |
| US 10Y Treasury | `TY1 Comdty` |
| US Ultra Bond | `UB1 Comdty` |
| US Long Bond | `US1 Comdty` |
| Bund | `RX1 Comdty` |
| BTP | `IK1 Comdty` |
| Gilt | `G 1 Comdty` (note space) |
| JGB | `JB1 Comdty` |

### 2.6 Equity index futures

| Contract | Ticker |
|---|---|
| S&P 500 E-Mini | `ES1 Index` (yellow key is `Index` here, not `Comdty`) |
| Nasdaq 100 E-Mini | `NQ1 Index` |
| Russell 2000 E-Mini | `RTY1 Index` |
| Dow E-Mini | `DM1 Index` |
| EuroStoxx 50 | `VG1 Index` |
| FTSE 100 | `Z 1 Index` (note space) |
| DAX | `GX1 Index` |
| Nikkei 225 | `NX1 Index` |
| Hang Seng | `HI1 Index` |

---

## 3. Contract specification fields

| Mnemonic | Returns |
|---|---|
| `FUT_CONTRACT_SIZE` | Contract size (e.g. 1000 for WTI = 1000 bbl) |
| `FUT_TICK_SIZE` | Minimum price increment |
| `FUT_VAL_PT` | Dollar value per point (`FUT_CONTRACT_SIZE × FUT_TICK_SIZE` for most) |
| `FUT_NOTIONAL` | Notional value at current price |
| `FUT_DELIV_DT_FIRST` | First delivery date |
| `FUT_DELIV_DT_LAST` | Last delivery date |
| `FUT_NOTICE_FIRST` | First notice date (when long positions can be assigned delivery) |
| `FUT_FIRST_TRADE_DT` | First trade date |
| `FUT_LAST_TRADE_DT` | Last trade date |
| `FUT_DAYS_EXPIRE` | Days to expiry |
| `FUT_GENERIC_NAME` | Generic name (e.g. "WTI Crude Oil") |
| `FUT_CUR_GEN_TICKER` | Current generic (the contract underlying `CL1` at any given moment) |
| `OPEN_INT` | Open interest (current contract) |
| `AGG_OPEN_INT` | Aggregated open interest (all contracts of this future) |
| `OPT_OPEN_INT` | Options open interest |
| `EXCHANGE_CODE` | Exchange code (CME, NYMEX, ICE, etc.) |

For each generic series (CL1, GC1, ...), `FUT_CUR_GEN_TICKER` gives you the specific contract currently underlying the generic. Useful for understanding where the curve is centred.

---

## 4. Term structure / curve

### 4.1 Pulling the curve

To get the front 12 contracts of WTI for a snapshot view of the curve:

```python
contracts = [f"CL{i} Comdty" for i in range(1, 13)]
for i, c in enumerate(contracts, start=2):
    ws.cell(row=i, column=1, value=c)
    ws.cell(row=i, column=2, value=f'=_xll.BDP("{c}","FUT_CUR_GEN_TICKER")')
    ws.cell(row=i, column=3, value=f'=_xll.BDP("{c}","FUT_DELIV_DT_LAST")')
    ws.cell(row=i, column=4, value=f'=_xll.BDP("{c}","PX_LAST")')
    ws.cell(row=i, column=5, value=f'=_xll.BDP("{c}","OPEN_INT")')
```

The `FUT_DELIV_DT_LAST` column orders the contracts chronologically — that's the x-axis of a "curve at a snapshot" chart.

### 4.2 Calendar spreads

The simplest calendar spread is `CL1 - CL2` (front-month minus second-month). PRISM authors this as an Excel formula:

```python
ws["A1"] = '=_xll.BDP("CL1 Comdty","PX_LAST") - _xll.BDP("CL2 Comdty","PX_LAST")'
```

For history of a calendar spread, pull both legs via `BDH` and subtract column-wise:

```python
ws["A3"] = ArrayFormula(
    "A3:C1262",
    '=_xll.BDH("CL1 Comdty,CL2 Comdty","PX_LAST","-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
ws["D2"] = "CL1-CL2 (contango = +)"
for r in range(3, 1265):
    ws.cell(row=r, column=4, value=f'=IF(OR(B{r}="",C{r}=""),"",B{r}-C{r})')
```

Backwardation = `CL1 - CL2 > 0` (spot premium to forward). Contango = `< 0`. Backwardation is the typical regime for assets with carry costs (industrial metals, energy in tight markets); contango is typical for assets with storage costs (oil in oversupply, agriculturals at harvest).

### 4.3 BQL term-structure pattern

```excel
=_xll.BQL.Query("get(name(), fut_deliv_dt_last(), px_last) for(['CL1 Comdty', 'CL2 Comdty', 'CL3 Comdty', 'CL4 Comdty', 'CL5 Comdty', 'CL6 Comdty', 'CL7 Comdty', 'CL8 Comdty', 'CL9 Comdty', 'CL10 Comdty', 'CL11 Comdty', 'CL12 Comdty'])")
```

One round-trip, returns the entire curve sorted by delivery date.

---

## 5. CFTC Commitments of Traders (COT)

Weekly positioning data published every Friday with Tuesday-close data. The full COT field family on each futures ticker:

### 5.1 Non-commercial (speculators) — the most-watched bucket

| Mnemonic | Returns |
|---|---|
| `COT_NON_COMMERCIAL_LONG` | Long contracts |
| `COT_NON_COMMERCIAL_SHORT` | Short contracts |
| `COT_NON_COMMERCIAL_NET` | Net (long − short) |
| `COT_NON_COMMERCIAL_PCT_OF_OI` | NC long as % of open interest |

### 5.2 Commercial (hedgers)

| Mnemonic | Returns |
|---|---|
| `COT_COMMERCIAL_LONG` | Long contracts |
| `COT_COMMERCIAL_SHORT` | Short contracts |
| `COT_COMMERCIAL_NET` | Net |
| `COT_COMMERCIAL_PCT_OF_OI` | Commercial long as % of OI |

### 5.3 Other reportable + non-reportable

| Mnemonic | Returns |
|---|---|
| `COT_NON_REPORTABLE_LONG` / `COT_NON_REPORTABLE_SHORT` / `COT_NON_REPORTABLE_NET` | Small traders (retail-ish) |
| `COT_NUM_TRADERS_LARGE` | Count of large traders |
| `COT_OPEN_INTEREST` | Total open interest in CFTC report (matches `OPEN_INT` from exchange) |

### 5.4 Disaggregated breakdown (CFTC Disaggregated COT)

For agriculturals + energy + metals (introduced 2009), Bloomberg also publishes:

| Mnemonic | Returns |
|---|---|
| `COT_PRODUCER_LONG` / `COT_PRODUCER_SHORT` | Producer / Merchant / Processor / User |
| `COT_SWAP_DEALER_LONG` / `COT_SWAP_DEALER_SHORT` | Swap Dealer |
| `COT_MANAGED_MONEY_LONG` / `COT_MANAGED_MONEY_SHORT` | Managed Money (CTAs, hedge funds) |
| `COT_OTHER_REPORTABLE_LONG` / `COT_OTHER_REPORTABLE_SHORT` | Other Reportable |

Managed money is what most market commentary refers to as "speculators" — sharper than the legacy non-commercial bucket because it excludes index traders.

### 5.5 Pulling the COT history

```python
ws["A3"] = ArrayFormula(
    "A3:F261",                                                              # 5Y weekly + header
    '=_xll.BDH("CL1 Comdty",'
    '"COT_NON_COMMERCIAL_LONG,COT_NON_COMMERCIAL_SHORT,COT_NON_COMMERCIAL_NET,'
    'COT_MANAGED_MONEY_LONG,COT_MANAGED_MONEY_SHORT",'
    '"-5Y","0D","Per=cw","Fill=N","Dts=S","Dir=V")'
)
```

Note `Fill=N` here — COT prints once a week, so blank rows are real data gaps (not values to forward-fill).

---

## 6. Inventories and supply data

Commodity-specific inventory data is published as `Index` securities — not `Comdty`. PRISM looks up the right index ticker via `ECO<GO>` or the relevant agency's release calendar.

### 6.1 Energy

| Indicator | Ticker | Source |
|---|---|---|
| DOE Crude Oil Inventories | `DOEASCRD Index` | DOE EIA |
| DOE Cushing Stockpile | `DOESCRUD Index` | DOE EIA |
| DOE Gasoline Inventories | `DOESGAS Index` | DOE EIA |
| DOE Distillate Inventories | `DOESDIST Index` | DOE EIA |
| DOE Refinery Utilization | `DOEUTOP Index` | DOE EIA |
| Baker Hughes US Rig Count | `BAKETOT Index` | Baker Hughes |
| API Crude (Tuesday) | `APIDCRUDE Index` | API |

### 6.2 Agriculturals (USDA)

| Indicator | Ticker |
|---|---|
| USDA WASDE Corn Ending Stocks | varies (look up via `WASDE<GO>`) |
| USDA Grain Stocks Corn | `USDACGSY Index` (varies) |

USDA / WASDE field structure is install-specific; the user looks up the right release index via `ECO<GO>` filtering by country=US and category=Agriculture.

### 6.3 Metals (LME)

| Indicator | Ticker |
|---|---|
| LME Copper Stocks (tonnes) | `LMCAJBS Comdty` |
| LME Aluminium Stocks | `LMAHJBS Comdty` |
| LME Zinc Stocks | `LMZSJBS Comdty` |
| LME Nickel Stocks | `LMNIJBS Comdty` |

(yellow key here is `Comdty`, not `Index`, because LME stocks are quoted alongside the metals).

---

## 7. BQL commodity patterns

BQL commodity coverage is more limited than equity / fixed income. Useful patterns:

```excel
=_xll.BQL.Query("get(name(), px_last, open_int) for(['CL1 Comdty', 'GC1 Comdty', 'NG1 Comdty', 'HG1 Comdty', 'S 1 Comdty', 'C 1 Comdty', 'W 1 Comdty'])")
```

For curve work, BQL has `chain()`:

```excel
=_xll.BQL.Query("get(name(), fut_deliv_dt_last(), px_last) for(chain('CL Comdty'))")
```

Returns all listed contracts for WTI ordered by expiry. Add `filter(... fut_deliv_dt_last() < 1Y)` to restrict to the front year.

---

## 8. Anti-patterns specific to commodities

| Mistake | Symptom | Fix |
|---|---|---|
| Pulling `CL Comdty` (without a number) | Returns `#N/A` | Always specify generic position (`CL1`, `CL2`) or specific (`CLZ4`) |
| Forgetting the space in ag tickers | `C1 Comdty` returns wrong / non-existent contract | Use `C 1 Comdty` for corn; `S 1` for soybeans; `W 1` for wheat. The space is part of the ticker. |
| Using `CL1 Comdty` for backtests without considering roll discontinuities | Price jumps at roll dates create false signals | Use `R:00_0_R` ratio-adjusted suffix for backtests |
| Pulling COT data with `Fill=P` | Forward-fills weekly data to daily, creating fake observations | Use `Fill=N` for COT — gaps are real |
| Treating `OPEN_INT` and `COT_OPEN_INTEREST` as different | They're the same number reported by different sources (exchange vs CFTC) | Use either; cross-check if values diverge (rare) |
| Confusing `CL1` generic with continuous-price series for option pricing | Generic series has roll discontinuities; option pricing wants specific contract | Use the specific contract (`CLZ4`) for option work; generic for charting / regression |
| Equity index futures with `Comdty` yellow key | `Comdty` doesn't resolve for equity index futures | Use `Index` yellow key: `ES1 Index` (S&P E-mini), not `Comdty` |
| LME copper as `HG1 Comdty` | `HG` is COMEX copper, not LME | LME: `LMCADS03 Comdty` (3M outright) or `LP1 Comdty` (generic 1M) |

---

## 9. Quick reference

```
─────────────────────────────────────────────────────────────────────
  GENERICS — TOP FUTURES CONTRACTS
─────────────────────────────────────────────────────────────────────
  Energy:        CL1, CO1, NG1, HO1, XB1
                 (WTI, Brent, Nat Gas, Heating, RBOB)
  Metals:        GC1, SI1, HG1, LMCADS03, LMAHDS03
                 (Gold, Silver, Cu-COMEX, Cu-LME, Al-LME)
  Ag:            C 1, S 1, W 1, CT1, SB1, KC1
                 (Corn, Soy, Wheat, Cotton, Sugar, Coffee — spaces matter)
  Rates:         TU1, FV1, TY1, US1, UB1, FF1, SFR1
  Eq Index:      ES1 Index, NQ1 Index, RTY1 Index, VG1 Index
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  CONTRACT SPEC FIELDS
─────────────────────────────────────────────────────────────────────
  Size:          FUT_CONTRACT_SIZE
  Tick:          FUT_TICK_SIZE
  $/point:       FUT_VAL_PT
  Delivery:      FUT_DELIV_DT_FIRST / FUT_DELIV_DT_LAST
  Notice:        FUT_NOTICE_FIRST
  OI:            OPEN_INT / AGG_OPEN_INT
  Generic resolves to:  FUT_CUR_GEN_TICKER
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  COT (CFTC POSITIONING) — KEY FIELDS
─────────────────────────────────────────────────────────────────────
  Legacy non-commercial (speculators):
    COT_NON_COMMERCIAL_LONG/_SHORT/_NET
  Disaggregated (post-2009):
    COT_MANAGED_MONEY_LONG/_SHORT
    COT_PRODUCER_LONG/_SHORT
    COT_SWAP_DEALER_LONG/_SHORT
  Total OI:
    COT_OPEN_INTEREST or OPEN_INT
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  ROLL ADJUSTMENT SUFFIXES (FOR GENERICS)
─────────────────────────────────────────────────────────────────────
  CL1 Comdty                          default; active-contract method
  CL1 R:00_0_R Comdty                 backward-ratio-adjusted
  CL1 R:00_0_A Comdty                 backward-arithmetic-adjusted
  CL1 R:00_0_N Comdty                 no adjustment (raw discontinuity)
─────────────────────────────────────────────────────────────────────
```
