# Bloomberg Excel Formulas (BQL + DAPI)

- **Module:** `bloomberg_excel`
- **Audience:** PRISM (all interfaces)
- **Tier:** 2 (on-demand)
- **Scope:** Authoring Bloomberg formula strings into Excel cells via `openpyxl`. The formulas evaluate when the user opens the workbook in Excel-with-Bloomberg-add-in. PRISM never executes BQL or blpapi itself — it ships a workbook the user evaluates locally.

PRISM already knows `openpyxl`. This module teaches the formula catalog: legacy DAPI (`BDP` / `BDH` / `BDS` / `BEQS` / `BCURVE` / `BSRCH`), the modern BQL family (`BQL` / `BQL.Query` / `BQL.Dates` / `BQL.Params` / `BQL.Expr`), override flags, field mnemonics by asset class, yellow-key security syntax, and the openpyxl-specific quirks.

---

## 1. Critical openpyxl gotchas (read first)

Bloomberg formulas are NOT standard Excel functions — they are loaded by the Bloomberg add-in at runtime. When PRISM writes them into a cell via `openpyxl`, three quirks apply:

### 1.1 The `_xll.` prefix is mandatory

A formula PRISM writes into `cell.value` MUST be prefixed with `_xll.` or Excel treats it as text and outputs `0.0` (or shows "Removed Records: Formula" on file open).

```python
ws["B2"] = '=_xll.BDP("IBM US Equity","PX_LAST")'                          # CORRECT
ws["B2"] = '=BDP("IBM US Equity","PX_LAST")'                               # BROKEN — outputs 0.0
```

The `_xll.` prefix applies to **every** Bloomberg function: `_xll.BDP`, `_xll.BDH`, `_xll.BDS`, `_xll.BEQS`, `_xll.BCURVE`, `_xll.BSRCH`, `_xll.BQL`, `_xll.BQL.Query`, etc. When the file opens in Excel, the add-in resolves `_xll.<NAME>` to the underlying Bloomberg call.

This rule is openpyxl/xlsxwriter-specific. Users typing `=BDP(...)` directly into Excel do not need it (Excel + add-in resolve the bare name); programmatically-written XLSX files do.

### 1.2 Use double quotes inside the formula, escape with backslash in Python

```python
ws["B2"] = '=_xll.BDP("IBM US Equity","PX_LAST")'                          # CORRECT
ws["B2"] = "=_xll.BDP('IBM US Equity','PX_LAST')"                          # BROKEN — single quotes
ws["B2"] = "=_xll.BDP(\"IBM US Equity\",\"PX_LAST\")"                      # CORRECT (escaped)
```

Use Python single-quoted strings to wrap the formula and double-quoted Bloomberg arguments inside — no escaping needed.

### 1.3 BDS / BDH / BEQS / BQL return ARRAYS — wrap in `ArrayFormula`

`BDP` returns one cell. `BDH` / `BDS` / `BEQS` / `BQL` return multi-cell ranges (history, member lists, screen results, query tables). Bloomberg expects them as **array formulas**. Without `ArrayFormula`, Excel fills only the top-left cell and silently drops the rest.

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active

# Single-cell: plain string
ws["B2"] = '=_xll.BDP("AAPL US Equity","PX_LAST")'

# Multi-cell: ArrayFormula. The range MUST be sized to fit the expected return.
ws["A5"] = ArrayFormula(
    "A5:C260",                                                              # ~1Y daily across 2 fields
    '=_xll.BDH("AAPL US Equity","PX_LAST,PX_VOLUME","-1Y","0D")'
)

# Members of an index — sizing is approximate; over-allocate
ws["A1"] = ArrayFormula("A1:A600", '=_xll.BDS("SPX Index","INDX_MEMBERS")')
```

Sizing rules of thumb:
- `BDH` daily: rows = (end - start) trading days (~252/year) + 1 header; cols = N fields + 1 date col.
- `BDS` index members: ~600 rows for SPX, ~3,500 for Russell 3000, ~30 for sector ETFs.
- `BEQS` screen: depends on screen — start with 500 rows × 20 cols and trim after first refresh.
- `BQL`: depends on query — `for(members(<index>))` is the index size.

### 1.4 Cached values are not real

`openpyxl` reads cached values via `data_only=True`. Cells with Bloomberg formulas have **NO valid cached value** in a freshly-authored workbook — they're populated only after Excel-with-add-in opens the file. PRISM should never claim a Bloomberg-formula workbook contains real numbers; the file evaluates at open-time.

### 1.5 Refresh-on-open behaviour

Workbooks PRISM ships will recalculate on first open if the user has the Bloomberg add-in active. To force refresh, users press `F9` or click the Bloomberg ribbon's `Refresh Workbook`. PRISM should mention this in the message accompanying the file delivery.

---

## 2. Decision: BQL or DAPI?

Both families coexist. They're not interchangeable — pick by the question PRISM is answering.

| Question shape | Pick | Why |
|---|---|---|
| One value, one security: "AAPL last price" | `BDP` | Single-cell, simplest |
| Time series, one or a few securities: "AAPL daily close 2020-now" | `BDH` | Native historical surface, accepts relative dates |
| Static descriptive list: "SPX members", "AAPL top 10 holders", "10Y UST cash flows" | `BDS` | Bulk descriptive return |
| Saved equity screen results: "my MOMENTUM screen" | `BEQS` | Saved screen execution |
| Yield curve constituents: "S23 / EUR swap curve members" | `BCURVE` | Native curve resolution |
| Universe screening with computation: "all SPX members where PE < 15 AND momentum > sector avg" | `BQL` (or `BQL.Query`) | DAPI cannot compute peer-relative; BQL runs server-side |
| Time-aware aggregation: "average HY OAS by sector by maturity-year" | `BQL.Query` | Group + bin in one call |
| Custom expressions / variables / let-bindings | `BQL.Query` with `let(...)` | DAPI has no variable binding |
| Technical indicators on the fly (EMA / RSI / Z-score) | `BQL.Query` | DAPI requires per-row formulas; BQL has `emavg()`, `rsi()`, `zscore()` |

Rules of thumb:
- **DAPI is row-by-row, client-side.** Each `BDH` / `BDP` is one Bloomberg call. 100 securities × 5 fields = 500 cells, each refreshing independently. Slower for large universes.
- **BQL is one query, server-side.** Compute happens on Bloomberg's cloud; returns a table. Better for >50 securities, custom calculations, conditional filtering.
- **BQL is newer (2018+) and not all enterprise installs have it.** If unsure, default to DAPI for compatibility and offer BQL as an alternative.
- **Mixing is fine.** A workbook can have a BQL block (universe definition + calculations) plus DAPI cells for specific overrides.

---

## 3. Security syntax (yellow keys + identifier types)

Every Bloomberg formula and BQL query identifies a security with the syntax `<identifier> <market sector>`. The market sector is the "yellow key" — case-insensitive but conventionally Title Case.

### 3.1 Yellow-key catalog

| Yellow key | Sector | Examples |
|---|---|---|
| `Equity` | Common stock, ADRs, ETFs, mutual funds, rights, options, warrants | `AAPL US Equity`, `7203 JT Equity`, `SPY US Equity` |
| `Govt` | Sovereign bonds (US Treasury, Bunds, JGBs, Gilts) | `T 4 02/15/34 Govt`, `912828YK0 Govt`, `CT10 Govt` (current 10Y) |
| `Corp` | Corporate bonds | `AAPL 3.85 05/04/43 Corp`, `037833DL1 Corp` (CUSIP) |
| `Mtge` | Mortgage-backed (TBAs, agency MBS, CMOs) | `FNCL 5.5 Mtge`, `3132J5K Mtge` |
| `Muni` | US municipal bonds | `01069DBZ9 Muni` |
| `Pfd` | Preferred shares | `AAPL/P US Pfd` |
| `M-Mkt` | Money market (CP, CDs) | `SOALA LNST M-Mkt` |
| `Index` | Equity / fixed-income / economic indices | `SPX Index`, `LF98TRUU Index` (US HY), `CPI YOY Index` |
| `Curncy` | FX spot, forwards, NDFs | `EURUSD Curncy`, `USDJPY1M Curncy`, `IRDR1Y Curncy` |
| `Comdty` | Commodities futures + options | `CLZ4 Comdty` (Dec'24 WTI), `GC1 Comdty` (front gold) |
| `Port` | Saved Bloomberg portfolio | `U12345678-1 Client` (less common in formulas) |

### 3.2 Identifier types (any of these works in front of the yellow key)

| Type | Example | Notes |
|---|---|---|
| Bloomberg ticker | `AAPL US Equity` | Most common; ticker + 2-letter exchange |
| CUSIP (9 chars) | `037833100 Equity` | US securities only |
| ISIN (12 chars) | `/isin/US0378331005 Equity` | International standard; prefix `/isin/` |
| SEDOL (7 chars) | `/sedol/2046251 Equity` | UK-origin standard; prefix `/sedol/` |
| FIGI (12 chars) | `/bbgid/BBG000B9XRY4 Equity` | Bloomberg Global Identifier; prefix `/bbgid/` |
| BB unique | `BBG000B9XRY4 Equity` | Same FIGI without prefix (sometimes works) |
| Composite ticker | `AAPL Equity` | Bloomberg-composited (uses Bloomberg's "primary" exchange routing) |

Tickers are most ergonomic (`AAPL US Equity`); ISINs/CUSIPs are robust against ticker changes (M&A, exchange relocations) and the right pick when the user gives PRISM a static identifier list.

### 3.3 Special syntactic forms

| Form | Meaning |
|---|---|
| `CT10 Govt` | "Current 10-Year UST" — auto-rolls to the current on-the-run issue |
| `GT10 Govt`, `GTGBP10Y Govt`, `GTJPY10Y Govt` | Generic 10Y for currency-specific sovereign |
| `CL1 Comdty`, `CL2 Comdty` | First / second futures contract (roll-adjusted by Bloomberg's generic-rolling logic) |
| `CLN5 Comdty` | Specific futures contract: `CL` + month-code (`F`/`G`/`H`/`J`/`K`/`M`/`N`/`Q`/`U`/`V`/`X`/`Z`) + year digit |
| `EURUSD BGN Curncy` | EURUSD with `BGN` pricing source (Bloomberg Generic) |
| `EUR1M BGN Curncy` | 1M EUR forward outright |

Futures month codes: `F`=Jan, `G`=Feb, `H`=Mar, `J`=Apr, `K`=May, `M`=Jun, `N`=Jul, `Q`=Aug, `U`=Sep, `V`=Oct, `X`=Nov, `Z`=Dec.

---

## 4. DAPI (legacy Excel functions)

The five core DAPI functions handle ~95% of typical Bloomberg-Excel work.

### 4.1 `BDP` — Bloomberg Data Point (single cell)

Returns ONE value to ONE cell. Static or real-time data.

```
=_xll.BDP(security, field, [override_field_1, override_value_1, ...])
```

| Argument | Required | Example |
|---|---|---|
| `security` | yes | `"IBM US Equity"`, `"912828YK0 Govt"` |
| `field` | yes | `"PX_LAST"`, `"DVD_YLD_IND"`, `"NAME"` |
| Optional: pairs of `override_field`/`override_value` | no | `"EQY_FUND_CRNCY","EUR"` to override the reporting currency |

```python
ws["B2"] = '=_xll.BDP("AAPL US Equity","PX_LAST")'
ws["B3"] = '=_xll.BDP("AAPL US Equity","CUR_MKT_CAP","EQY_FUND_CRNCY","EUR")'
ws["B4"] = '=_xll.BDP(A4,"NAME")'                                          # cell-reference identifier
```

### 4.2 `BDH` — Bloomberg Data History (time series)

Returns historical data for one security, one or more fields, over a date range.

```
=_xll.BDH(security, field(s), start_date, end_date, [optional_args...])
```

| Argument | Required | Example |
|---|---|---|
| `security` | yes | `"AAPL US Equity"` |
| `field(s)` | yes | `"PX_LAST"` or `"PX_LAST,PX_VOLUME"` (comma-separated for multi-field) |
| `start_date` | yes | Absolute: `"01/01/2020"`, `"20200101"`. Relative: `"-1Y"`, `"-6M"`, `"-30D"`, `"-2CY"` |
| `end_date` | yes | Same formats; empty string `""` = today |
| Optional: pairs of `override_field`/`override_value` | no | See override flag table |

Returns a 2D array: row 0 is field names header, column 0 is dates.

```python
from openpyxl.worksheet.formula import ArrayFormula
ws["A1"] = ArrayFormula(
    "A1:C260",
    '=_xll.BDH("AAPL US Equity","PX_LAST,PX_VOLUME","-1Y","0D","Dir=V","Dts=H","cols=2;rows=260")'
)
```

### 4.3 `BDH` override flag catalog

Override flags are passed as `"<flag>=<value>"` pairs at the end of the call. Most common ones:

| Flag | Values | Effect |
|---|---|---|
| `CURR=` | `USD` / `EUR` / `JPY` / any ISO 4217 | Currency conversion of returned values |
| `PER=` | `cd` / `cw` / `cm` / `cq` / `cs` / `cy` / `w` / `m` / `q` / `y` / `s` (see below) | Periodicity. `cd` calendar day, `cw` calendar week, `cm` cal. month, `cq` cal. quarter, `cs` semi-annual, `cy` cal. year. Lowercase variants (`w`, `m`, `q`, `y`) use Bloomberg's holiday-aware calendar. |
| `DAYS=` | `T` (trading), `W` (weekdays), `C` (calendar), `A` (all) | Day filter. `T` is most common for prices. |
| `FILL=` | `B` (blank), `N` (`#N/A`), `P` (previous), `0` (zero), `.5` (literal value) | Missing-value fill |
| `CSHADJ=` / `CSHADJUST=` | `Y` / `N` | Cash-adjusted prices (default `N`) |
| `CSHFLOW=` | `Y` (cash adj. + dividends), `N` | Total return basis |
| `CAPCHG=` | `Y` / `N` | Adjust for capital changes (splits/spinoffs) |
| `DPDF=` / `USEDPDF=` | `Y` / `N` | Use user's `DPDF<GO>` settings |
| `QUOTE=` | `B` (best), `L` (last), `Y` (yield) | Price source preference |
| `QTYP=` | `Y` (yield to maturity), `T` (true yield), `D` (discount) | Bond quote type |
| `POINTS=` | `Y` / `N` | FX/rates: return in points vs. percent |
| `DIR=` | `V` (vertical), `H` (horizontal) | Output orientation |
| `DTS=` | `S` (show dates), `H` (hide) | Include date column? |
| `COLS=` / `ROWS=` | integer, or `H`/`HA` | Header rows/cols |
| `EQY_FUND_CRNCY` | ISO ccy | Override the security's reporting currency |
| `BEST_FPERIOD_OVERRIDE` | `1BF` / `2BF` / `1FY` / `2FY` etc. | Forward fiscal period (1BF = 1 forward, 2BF = 2 forward) |
| `FUND_PER` | `Q` (quarterly), `S` (semi-annual), `A` (annual) | Fundamentals periodicity |
| `RELATIVE_DATE` | `Y` / `N` | Treat dates as relative |

Relative date strings for start/end:
- `0D` / `-30D` — calendar days back
- `-1W` / `-4W` — weeks back
- `-1M` / `-6M` — months back
- `-1Q` / `-2Q` — quarters back
- `-1Y` / `-5Y` / `-10Y` — years back
- `-1FY` / `-2FY` — fiscal years back
- `-1CQ` / `-6CQ` — calendar quarters back

### 4.4 `BDS` — Bloomberg Data Set (multi-cell descriptive)

Returns a multi-cell array of descriptive / list data.

```
=_xll.BDS(security, field, [optional_args...])
```

Common fields: `INDX_MEMBERS`, `INDX_MWEIGHT`, `TOP_HOLDERS_PUBLIC_FILINGS`, `DVD_HIST_ALL`, `BOND_CHAIN`, `DES_NOTES`, `INTERNAL_REVENUE_BREAKDOWN`, `EQY_FUND_CRNCY_RPT`.

```python
ws["A1"] = ArrayFormula("A1:B600", '=_xll.BDS("SPX Index","INDX_MEMBERS")')
ws["A1"] = ArrayFormula("A1:E50", '=_xll.BDS("AAPL US Equity","TOP_20_HOLDERS_PUBLIC_FILINGS")')
ws["A1"] = ArrayFormula("A1:F100", '=_xll.BDS("912828YK0 Govt","DES_CASH_FLOW")')
```

### 4.5 `BEQS` — Bloomberg Equity Screening

Executes a saved Bloomberg `EQS<GO>` screen.

```
=_xll.BEQS(screen_name, [ScreenType=B|C], [Group=<name>], [Asof=<date>])
```

| Argument | Notes |
|---|---|
| `screen_name` | Quoted name as it appears in `EQS<GO>` |
| `ScreenType=B` | User screen (Bloomberg sample). Default. |
| `ScreenType=C` | User custom screen (saved by the running user) |
| `Group=` | If user has multiple screen groups |
| `Asof=` | Point-in-time evaluation date |

```python
ws["A1"] = ArrayFormula(
    "A1:T500",
    '=_xll.BEQS("Increasing Option Call Volume","ScreenType=B")'
)
```

If the screen name doesn't exist, the cell returns `#N/A Invalid Screen Name`.

### 4.6 `BCURVE` — yield curve constituents

Returns the members of a curve (e.g. swap curves, corporate curves).

```
=_xll.BCURVE(curve_id, [columns...])
```

Curve IDs: `S23` (USD swap), `S45` (EUR swap), `S141` (JPY swap), `YCSW0023 Index` (full curve ticker form).

```python
ws["A1"] = ArrayFormula("A1:E40", '=_xll.BCURVE("S23")')
```

For programmatic curve work, BQL's `curvemembers()` is more flexible.

### 4.7 `BSRCH` — Bloomberg Search

Executes a fixed-income search (analogous to `BEQS` for FI).

```
=_xll.BSRCH(search_name)
```

Example: `BSRCH("COMDTY:NGFLOW")`. Less common than `BEQS`; many enterprise installs don't expose `BSRCH` to add-in callers.

### 4.8 Legacy aliases (informational; do NOT use)

| Function | Status |
|---|---|
| `BLP` / `BLPH` / `BLPS` | Pre-2013 legacy. Bloomberg's Formula Conversion Tool migrates these to `BDP`/`BDH`/`BDS`. PRISM should always emit the new family. |
| `BFXFRWD` / `BFXVOL` | Specialised FX forms; use `BDP`/`BDH` with `Curncy` securities + appropriate fields instead. |

---

## 5. BQL (Bloomberg Query Language) — modern family

BQL is a declarative query language that runs server-side on Bloomberg's cloud. Five Excel entry-point functions:

| Function | Purpose |
|---|---|
| `BQL` | Single-call, query-string-or-formula body |
| `BQL.Query` | Compose query from `let` / `get` / `for` / `with` / `preferences` clauses |
| `BQL.Dates` | Build a date range / list to feed `dates=` parameters |
| `BQL.Params` | Build a parameter set (cell-driven inputs) |
| `BQL.Expr` | Build a reusable expression / variable |

### 5.1 Query structure (the core grammar)

```
let(<variable_definitions>;)
get(<output_data_items>)
for(<universe>)
with(<execution_parameters>)
preferences(<output_settings>)
```

`get(...)` and `for(...)` are mandatory. `let(...)`, `with(...)`, `preferences(...)` are optional.

```excel
=_xll.BQL("get(px_last) for(['IBM US Equity'])")
```

### 5.2 `BQL.Query` examples

Single security, single field:
```excel
=_xll.BQL.Query("get(px_last) for(['AAPL US Equity'])")
```

Multiple securities, multiple fields:
```excel
=_xll.BQL.Query("get(name(), px_last, cur_mkt_cap) for(['AAPL US Equity', 'MSFT US Equity', 'GOOGL US Equity'])")
```

With `let` for reusable variables:
```excel
=_xll.BQL.Query("let(#dur=duration(duration_type=MODIFIED); #zsprd=spread(spread_type=Z);) get(name(), #dur, #zsprd) for(filter(bondsuniv(ACTIVE), crncy()=='USD' and country_iso()=='US'))")
```

Aggregation by group:
```excel
=_xll.BQL.Query("let(#avg_pe=avg(group(pe_ratio(), gics_sector_name()));) get(#avg_pe) for(members('SPX Index'))")
```

Technical screening (price > 200-day EMA AND RSI > 70):
```excel
=_xll.BQL.Query("let(#ema200=emavg(period=200); #rsi=rsi(close=px_last());) get(name(), #ema200, #rsi) for(filter(members('SPX Index'), and(px_last() > #ema200, #rsi > 70)))")
```

In openpyxl: wrap with `ArrayFormula` because the result is a table.

### 5.3 Universe builders (`for(...)`)

| Builder | Returns | Example |
|---|---|---|
| `[<list>]` | Explicit security list | `['AAPL US Equity', 'MSFT US Equity']` |
| `members('<index>')` | Index constituents | `members('SPX Index')`, `members('LF98TRUU Index')` (US HY) |
| `peers(<sec>)` | Peer companies | `peers('AAPL US Equity')` |
| `holdings(<fund>)` | Fund holdings | `holdings('SPY US Equity')` |
| `screenresults(type=<EQS\|SRCH>, screen_name=<name>)` | Saved screen results | `screenresults(type=SRCH, screen_name='@COCO')` |
| `bondsuniv(<scope>)` | Bond universe | `bondsuniv(ACTIVE)`, `bondsuniv(ALL)`, `bondsuniv(GOVT)` |
| `bonds(<equity>)` | All bonds of an issuer | `bonds('AAPL US Equity')` |
| `segments(<sec>, type=<reported\|estimated>, hierarchy=<PRODUCT\|GEO>, level=<n>)` | Company business segments | `segments('GTN US Equity', type=reported, hierarchy=PRODUCT, level=1)` |
| `curvemembers(<curve>)` | Yield curve members | `curvemembers('YCSW0023 Index')` |
| `filter(<universe>, <condition>)` | Subset of any universe by condition | `filter(members('SPX Index'), pe_ratio() < 15)` |
| `translatesymbols(<list>, <type>)` | Convert local tickers to fundamental/composite | `translatesymbols(['AAPL UQ Equity'], type=COMPOSITE)` |

`filter()` conditions chain with `and(...)` / `or(...)` / `not(...)` and use comparison operators `==`, `!=`, `>`, `<`, `>=`, `<=`, plus `in` and `notin`.

```
filter(members('SPX Index'), and(gics_sector_name() == 'Information Technology', pe_ratio() < 25, cur_mkt_cap > 100e9))
```

### 5.4 Aggregation / grouping functions

| Function | Returns |
|---|---|
| `avg(<expr>)` | Mean |
| `sum(<expr>)` | Sum |
| `min(<expr>)` / `max(<expr>)` | Min / max |
| `count(<expr>)` | Count of non-null values |
| `last(<expr>)` | Most recent value |
| `first(<expr>)` | Earliest value |
| `median(<expr>)` | Median |
| `stdev(<expr>)` | Standard deviation |
| `group(<expr>, <key>, by=[<keys>])` | Pivot/grouping; `by=` accepts a list for multi-level |
| `cumulate(<expr>)` | Running sum |
| `pct_chg(<expr>, period=<N>)` | Percent change over N periods |
| `dropna(<expr>)` | Drop nulls (typically wraps a price series before charting) |

Combining: `avg(group(pe_ratio(), gics_sector_name()))` — average PE per sector.

### 5.5 Statistical / technical functions

| Function | Args | Returns |
|---|---|---|
| `zscore(<expr>)` | (with optional `period=`) | Z-score |
| `corr(<x>, <y>)` | Two series | Correlation coefficient |
| `regr(<y>, <x>)` | Two series | Regression result (slope, intercept, R²) |
| `sma(period=<N>)` | Simple moving average | Series |
| `emavg(period=<N>)` | Exponential moving average | Series |
| `rsi(close=<expr>, period=<N>)` | Relative strength index (default period=14) | Series |
| `macd(fast=<N>, slow=<N>, signal=<N>)` | MACD | Series |
| `boll_band(period=<N>, num_stdev=<n>)` | Bollinger band | Series |
| `return_series(calc_interval=<range>, per=<D\|W\|M\|Q\|Y>)` | Return time series | Series |
| `rank(<expr>)` | Cross-sectional ranking | Integer |
| `pct_rank(<expr>)` | Percentile rank (0-1) | Float |

### 5.6 Date helpers

| Helper | Example |
|---|---|
| `range(<start>, <end>)` | `range(-1Y, 0D)` — 1Y window ending today |
| `range(<start_date>, <end_date>)` | `range(2020-01-01, 2023-12-31)` |
| Relative tokens | `0D`, `-1D`, `-1W`, `-1M`, `-1Q`, `-1Y`, `-1FY`, `-1CY`, `-1CQ` |
| Fiscal-period tokens | `2024Q3`, `2023A`, `2025FY` |
| Forward periods (estimates) | `1BF` (1 forward), `2BF`, `0BF` (current) |

`BQL.Dates(<spec>)` is a sheet-level helper for cell-driven date builds:

```excel
=_xll.BQL.Dates("range(-1Y, 0D)")
=_xll.BQL.Dates(C3, C4)                                                    # cell-driven
```

### 5.7 `with(...)` execution parameters

Tune behaviour without changing the query body:

| Parameter | Values | Effect |
|---|---|---|
| `fill=<PREV \| NEXT \| value>` | `PREV` repeats last known value; `NEXT` uses next; literal value substitutes | Missing-data behaviour |
| `mode=<CACHED \| LIVE>` | Default `CACHED` | Live-tick streaming (rarer) |
| `currency=<ISO>` | Any ISO 4217 | Currency override (applies to all amount fields) |
| `dates=<range>` / `dates=<list>` | Date list/range | Apply to time-series data items |
| `frq=<D \| W \| M \| Q \| Y>` | Periodicity | For time series |

```
with(fill=PREV, currency=USD, dates=range(-1Y, 0D), frq=D)
```

### 5.8 Field-level parameters (passed inside data items)

Most fields accept inline parameters in parentheses:

```
px_last(currency=EUR)                                                      # currency override
pe_ratio(fa_period_type=A, fa_period_offset=-1)                            # last fiscal year, annual
sales_rev_turn(fpt=q, fpr=range(2023Q1, 2024Q4))                           # quarterly revenue, time-windowed
emavg(period=20)                                                           # 20-period EMA on default close series
spread(spread_type=Z)                                                      # Z-spread (bond)
duration(duration_type=MODIFIED)                                           # modified duration (bond)
```

Common field-level parameters:

| Parameter | Used by | Values |
|---|---|---|
| `currency=` | Any amount field | ISO 4217 |
| `fpt=` (fiscal period type) | Fundamentals | `A` (annual), `Q` (quarterly), `S` (semi-annual), `LTM` (last 12M), `YTD` |
| `fpr=` (fiscal period reference) | Fundamentals | Single period (`2024Q3`) or range (`range(2020A, 2024A)`) |
| `fa_period_type` / `fa_period_offset` | Fundamentals | Same as `fpt` / numeric offset |
| `est_source=` | Estimates | `BST` (Bloomberg standard), `MEAN`, `MEDIAN`, `HIGH`, `LOW`, `COMPANY` |
| `fa_act_est_data=` | Mixed actuals/estimates | `A` (actuals), `E` (estimates), `BLEND` |
| `dates=` | Time-series fields | Date range / list |
| `period=` | Technical indicators | Integer |

### 5.9 `BQL.Params` — cell-driven parameter set

Builds a parameter object from cell references so users can edit the screen without rewriting the query:

```excel
=_xll.BQL.Params("currency", C2, "frq", C3, "fill", C4)
```

Then reference inside `BQL.Query` via the named param object.

### 5.10 `BQL.Expr` — named reusable expression

Defines an expression once for reuse across queries:

```excel
=_xll.BQL.Expr("#momentum", "px_last() / sma(period=200) - 1")
```

---

## 6. Field mnemonic catalog (curated)

Bloomberg has tens of thousands of fields. This catalog covers the ones PRISM hits in 90% of authoring work. For exhaustive search, the user runs `FLDS<GO>` on a Bloomberg terminal — PRISM should mention this when a needed field isn't here.

DAPI and BQL share these mnemonics (case-insensitive in BQL, conventionally lowercase in BQL examples and uppercase in DAPI examples). Some fields have a function-call form in BQL (`px_last()`) and a flat form in DAPI (`PX_LAST`).

### 6.1 Equity prices, volume, returns

| Mnemonic | Meaning | Yellow key |
|---|---|---|
| `PX_LAST` | Last traded price (adjusted close on EOD) | Equity / Index / Curncy / Comdty |
| `PX_OPEN` / `PX_HIGH` / `PX_LOW` | Day's OHL | Equity / Index / Curncy / Comdty |
| `PX_BID` / `PX_ASK` / `PX_MID` | Quoted bid / ask / mid | Equity / Curncy / Govt / Corp |
| `PX_VOLUME` | Day's volume | Equity / Comdty |
| `PX_LAST_BID` / `PX_LAST_ASK` | Most recent bid / ask quote | Equity / Curncy |
| `VWAP` | Volume-weighted average price | Equity |
| `OPEN_PRICE` / `LAST_PRICE` | Aliases | Equity |
| `TURNOVER` | Day's notional turnover | Equity |
| `BID_SIZE` / `ASK_SIZE` | Quote sizes | Equity / Curncy |
| `CHG_PCT_1D` / `CHG_PCT_5D` / `CHG_PCT_YTD` / `CHG_PCT_1Y` | Percent change over horizon | Equity / Index |
| `DAY_TO_DAY_TOT_RETURN_GROSS_DVDS` | Total return incl. dividends | Equity / Index |
| `52WK_HIGH` / `52WK_LOW` | 52-week range | Equity |
| `TOT_RETURN_INDEX_GROSS_DVDS` | TR index (gross) for time-series | Equity / Index |

### 6.2 Equity identifiers, descriptive

| Mnemonic | Meaning |
|---|---|
| `NAME` | Bloomberg short name |
| `LONG_COMP_NAME` | Full company name |
| `SECURITY_DES` | Description (incl. coupon/maturity for bonds) |
| `ID_ISIN` | ISIN |
| `ID_CUSIP` | CUSIP |
| `ID_BB_GLOBAL` | FIGI |
| `ID_BB_UNIQUE` | Bloomberg unique ID |
| `EXCH_CODE` | Primary exchange code |
| `COUNTRY_FULL_NAME` / `COUNTRY_ISO` | Domicile |
| `CRNCY` | Reporting currency |
| `INDUSTRY_SECTOR` | Bloomberg industry sector |
| `GICS_SECTOR_NAME` / `GICS_INDUSTRY_GROUP_NAME` / `GICS_INDUSTRY_NAME` / `GICS_SUB_INDUSTRY_NAME` | GICS hierarchy |
| `BICS_LEVEL_1_SECTOR_NAME` / `BICS_LEVEL_2_INDUSTRY_GROUP_NAME` | Bloomberg Industry Classification |

### 6.3 Equity fundamentals (income statement, balance sheet, cash flow, ratios)

| Mnemonic | Meaning |
|---|---|
| **Income statement** | |
| `IS_TOT_REV` / `SALES_REV_TURN` / `REVENUE` | Sales / total revenue |
| `IS_OPER_INC` / `EBIT` | Operating income |
| `EBITDA` | EBITDA |
| `IS_DEPR_AND_AMORT` | D&A |
| `IS_NET_INCOME` / `NET_INCOME` | Net income |
| `IS_DILUTED_EPS` / `IS_EPS` | EPS (diluted / basic) |
| `IS_GROSS_PROFIT` | Gross profit |
| **Balance sheet** | |
| `BS_TOT_ASSET` | Total assets |
| `BS_TOT_LIAB2` | Total liabilities |
| `BS_NET_DEBT` | Net debt |
| `BS_CASH_NEAR_CASH_ITEM` | Cash & equivalents |
| `BS_SH_OUT` / `EQY_SH_OUT` | Shares outstanding |
| `TOT_DEBT_TO_TOT_EQY` | Debt / equity |
| `BS_TOT_EQY` | Total equity |
| **Cash flow** | |
| `CF_CASH_FROM_OPER` | Operating cash flow |
| `CF_CAP_EXPEND_INC_FIX_ASSETS` | Capex |
| `FREE_CASH_FLOW` | FCF |
| **Profitability / valuation ratios** | |
| `RETURN_COM_EQY` / `RETURN_ON_EQUITY` | ROE |
| `RETURN_ON_ASSET` | ROA |
| `RETURN_ON_INV_CAPITAL` | ROIC |
| `OPER_MARGIN` | Operating margin |
| `PROF_MARGIN` | Net margin |
| `PE_RATIO` | P/E |
| `PX_TO_BOOK_RATIO` | P/B |
| `PX_TO_SALES_RATIO` | P/S |
| `EV_TO_T12M_EBITDA` | EV/EBITDA (trailing) |
| `CUR_MKT_CAP` / `MARKET_CAPITALIZATION` | Market cap |
| `CURR_ENTP_VAL` | Enterprise value |
| `DIVIDEND_YIELD` / `EQY_DVD_YLD_IND` | Dividend yield |
| `BETA_RAW_OVERRIDABLE` / `BETA` | Beta |
| **Estimates (forward)** | |
| `BEST_EPS` | Consensus forward EPS |
| `BEST_TARGET_PRICE` | Mean target price |
| `BEST_PE_RATIO` | Forward P/E |
| `BEST_EV_TO_EBITDA` | Forward EV/EBITDA |
| `BEST_PX_SALES` | Forward P/S |
| `EQY_REC_CONS` / `ANALYST_REC_CONS` | Consensus recommendation |
| `BEST_SALES` | Consensus revenue |

Use `BEST_FPERIOD_OVERRIDE` (DAPI) or `fpt=`/`fpr=` (BQL) to control fiscal period for these.

### 6.4 Fixed income (yields, spreads, duration, ratings)

| Mnemonic | Meaning |
|---|---|
| **Yield** | |
| `YLD_YTM_BID` / `YLD_YTM_ASK` / `YLD_YTM_MID` | Yield to maturity (bid/ask/mid) |
| `YLD_CNV_BID` / `YLD_CNV_MID` | Conventional yield |
| `YLD_TO_WORST` | Yield to worst |
| `YLD_TO_MTY_LIVE` | Live YTM |
| **Risk metrics** | |
| `DUR_ADJ_BID` / `MOD_DUR_BID` / `MOD_DUR_MID` | Modified duration |
| `EFF_DUR_BID` / `EFF_DUR_MID` | Effective duration |
| `CNVX_BID` / `CNVX_MID` | Convexity |
| `EFF_CNVX_BID` | Effective convexity |
| `RISK_BID` / `RISK_MID` / `BPV01` / `DV01` | DV01 / risk per bp |
| **Spreads** | |
| `OAS_BID` / `OAS_MID` / `OAS_ASK` | Option-adjusted spread |
| `Z_SPREAD_BID` / `Z_SPREAD_MID` | Z-spread |
| `ASW_SPREAD_BID` / `ASW_SPREAD_MID` | Asset-swap spread |
| `SPREAD_TO_BENCHMARK` / `T_BENCHMARK_SPREAD` | Treasury benchmark spread |
| **Issue / structural** | |
| `COUPON` | Coupon rate |
| `MATURITY` | Maturity date |
| `ISSUE_DT` / `ANNOUNCE_DT` | Issuance / announcement date |
| `AMT_OUTSTANDING` / `AMT_OUT_STANDING_USD` | Outstanding (issuer / USD-equivalent) |
| `AMT_ISSUED` | Original issue size |
| `COUPON_FREQ` | Coupon frequency (1=annual, 2=semi-annual, 4=quarterly) |
| `COUPON_TYPE` | Fixed / Float / Step / Zero |
| `DAY_CNT_TY` / `DAY_CNT` | Day count convention (e.g. `30/360`, `ACT/ACT`) |
| `CALC_TYP` | Calculation type |
| `MARKET_SECTOR_DES` | Sector designation |
| `CALLABLE` | Callable flag (Y/N) |
| `NXT_CALL_DT` / `NXT_CALL_PX` | Next call date / price |
| `BENCHMARK_NAME` | Benchmark security name |
| **Issuer** | |
| `ISSUER` | Issuer legal name |
| `ISSUER_PARENT_NAME` | Parent |
| **Ratings** | |
| `RTG_SP` / `RTG_MOODY` / `RTG_FITCH` | Big-three ratings |
| `BB_COMPOSITE_RATING` | Bloomberg composite |
| `RTG_SP_OUTLOOK` / `RTG_MDY_OUTLOOK` | Outlook (Stable/Pos/Neg) |

### 6.5 FX

| Mnemonic | Meaning |
|---|---|
| `PX_LAST` | Spot rate (for `EURUSD Curncy`, etc.) |
| `BID` / `ASK` | Quoted bid/ask |
| `IMPLIED_VOLATILITY_ATM` / `IVOL_ATM_3M` | ATM implied vol |
| `FORWARD_POINTS_BID` / `FORWARD_POINTS_ASK` | Forward points |
| `PX_FWD_NDF_PT_BID` | NDF forward points |
| `RHO_HIST_VOL_30D` | 30-day historical vol |

FX-specific securities: `EURUSD Curncy` (spot), `EURUSD1M Curncy` (1M outright), `EURUSD1M BGN Curncy` (with pricing source), `IRDR1Y Curncy` (1Y interest-rate differential).

### 6.6 Commodities (futures)

| Mnemonic | Meaning |
|---|---|
| `PX_LAST` | Last price |
| `OPEN_INT` / `AGG_OPEN_INT` | Open interest (single contract / aggregated) |
| `FUT_CONTRACT_SIZE` | Contract multiplier |
| `FUT_TICK_SIZE` | Tick size |
| `FUT_VAL_PT` | Value per point |
| `FUT_DELIV_DT_FIRST` / `FUT_DELIV_DT_LAST` | Delivery dates |
| `FUT_NOTICE_FIRST` | First notice date |
| `FUT_FIRST_TRADE_DT` / `FUT_LAST_TRADE_DT` | First / last trade date |
| `FUT_GENERIC_NAME` / `FUT_CUR_GEN_TICKER` | Generic naming |
| `FUT_DAYS_EXPIRE` | Days to expiry |
| `CO_FUTPX_PRC_CDR` | Front-month price |

### 6.7 Indices

| Mnemonic | Meaning |
|---|---|
| `PX_LAST` | Index level |
| `INDX_MEMBERS` | Constituent list (returns 1 column of tickers) |
| `INDX_MWEIGHT` | Member tickers + weights (returns 2 columns) |
| `INDX_MWEIGHT_HIST` | Historical weights |
| `INDX_TOTAL_RETURN` | Index total return |
| `INDX_FUND_FLOW` | Fund flows |
| `EQY_WEIGHTED_AVG_PE` / `EQY_WEIGHTED_AVG_DVD_YLD` | Index aggregate ratios |
| `BICS_LEVEL_1_INDUSTRY_NAME` | Sector classification |

### 6.8 Common across all asset classes

| Mnemonic | Meaning |
|---|---|
| `LATEST_PERIOD_END_DT_FULL_RECORD` | As-of date for the latest fundamentals |
| `LAST_UPDATE` | Last-update timestamp |
| `EQY_FUND_CRNCY` | Reporting currency |
| `MARKET_STATUS` | OPEN / CLOSED / PRE-OPEN |
| `TRADING_DAY_END_TIME_EOD` | Day's close time |

---

## 7. openpyxl integration patterns

### 7.1 Single-cell data points

```python
from openpyxl import Workbook

wb = Workbook()
ws = wb.active
ws.title = "Snapshot"

ws["A1"] = "Ticker"
ws["B1"] = "Last Price"
ws["C1"] = "Market Cap (USD)"

tickers = ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity"]
for i, ticker in enumerate(tickers, start=2):
    ws.cell(row=i, column=1, value=ticker)
    ws.cell(row=i, column=2, value=f'=_xll.BDP("{ticker}","PX_LAST")')
    ws.cell(row=i, column=3,
            value=f'=_xll.BDP("{ticker}","CUR_MKT_CAP","EQY_FUND_CRNCY","USD")')

wb.save("snapshot.xlsx")
```

### 7.2 Time series block (`BDH` + ArrayFormula)

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "History"

ticker = "SPY US Equity"
fields = "PX_LAST,PX_VOLUME"
n_rows = 260                                                                # ~1Y daily

ws["A1"] = f'Daily history: {ticker}'

ws["A3"] = ArrayFormula(
    f"A3:C{2 + n_rows + 1}",                                                # +1 for header
    f'=_xll.BDH("{ticker}","{fields}","-1Y","0D","Dir=V","Dts=H","cols=2;rows={n_rows}")'
)

wb.save("history.xlsx")
```

### 7.3 Index members + per-member fields

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active

ws["A1"] = "S&P 500 members + market cap"

# Pull member list (~600 rows worth of room)
ws["A3"] = ArrayFormula("A3:A700", '=_xll.BDS("SPX Index","INDX_MEMBERS")')

# Per-row BDP — references the member ticker in column A
for row in range(3, 700):
    ws.cell(row=row, column=2,
            value=f'=IF(A{row}="","",_xll.BDP(A{row}&" Equity","CUR_MKT_CAP"))')
    ws.cell(row=row, column=3,
            value=f'=IF(A{row}="","",_xll.BDP(A{row}&" Equity","PE_RATIO"))')

wb.save("spx_members.xlsx")
```

The `IF(A<row>="",...)` guard avoids `#N/A` errors when `INDX_MEMBERS` returns fewer rows than the over-allocated range.

### 7.4 BQL screen + computation

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active

ws["A1"] = "SPX low-PE momentum stocks"

bql = (
    'let('
    '#momentum=px_last() / sma(period=200) - 1; '
    '#pe=pe_ratio();'
    ') '
    'get(name(), gics_sector_name(), #pe, #momentum) '
    'for(filter(members(\'SPX Index\'), '
    'and(#pe < 15, #momentum > 0.10, cur_mkt_cap > 5e9)))'
)

ws["A3"] = ArrayFormula(
    "A3:E100",
    f'=_xll.BQL.Query("{bql}")'
)

wb.save("bql_momentum.xlsx")
```

Note the inner BQL string uses single quotes for `members('SPX Index')` (BQL syntax) — that's fine because the Python string is double-quoted. The whole `=_xll.BQL.Query("...")` call uses double quotes around the BQL body to satisfy Excel's formula parser.

### 7.5 Reading a Bloomberg-driven workbook back

When the user uploads a file containing Bloomberg formulas:

```python
from openpyxl import load_workbook

# Read formulas (PRISM's typical case — interpret what's authored)
wb = load_workbook("user_workbook.xlsx", data_only=False)
for row in wb.active.iter_rows():
    for cell in row:
        if cell.value and isinstance(cell.value, str) and cell.value.startswith("=_xll."):
            print(cell.coordinate, cell.value)

# Read cached values (only meaningful if the user opened in Excel + add-in + saved)
wb = load_workbook("user_workbook.xlsx", data_only=True)
```

If `data_only=True` returns `None` for Bloomberg cells, the user has not refreshed the file in Excel. Tell them to open + refresh + save before re-uploading.

---

## 8. Anti-patterns and common pitfalls

| Mistake | Symptom | Fix |
|---|---|---|
| Forgetting `_xll.` prefix | Cell shows `0.0` or formula text | Always emit `=_xll.<FUNC>(...)` from openpyxl |
| Using single quotes for arguments | `#NAME?` or formula recovery error on file open | Double quotes always: `"AAPL US Equity"` not `'AAPL US Equity'` |
| Plain string for `BDH` / `BDS` / `BEQS` / `BQL` | Only top-left cell populated; rest blank | Wrap in `ArrayFormula` with a sized range |
| Under-sized array range | Truncated results, no warning | Over-allocate (1.5× expected); empty trailing cells are harmless |
| Misspelled field mnemonic | Cell returns `#N/A Field Not Applicable` | Confirm via `FLDS<GO>`; common ones in §6 |
| Wrong yellow key (`AAPL US` without `Equity`) | `#N/A Invalid Security` | Always include yellow key |
| Mixing currencies without override | Aggregated metrics nonsensical | Pass `EQY_FUND_CRNCY=USD` (DAPI) or `currency=USD` (BQL) |
| Asking for forward fundamentals without period override | Returns last reported (LTM/FY0) instead of forward | DAPI: add `BEST_FPERIOD_OVERRIDE=1BF`. BQL: `pe_ratio(fpt=A, fpr=1BF)` |
| Treating Bills as YLD_YTM | Bills publish discount rate, not yield | Use `YLD_DISC_BID` for Bills, or convert to bond-equivalent |
| Using `BDH` for 5,000 securities × 252 days | Refresh storms, slow workbook | Use `BQL.Query` with `for(members(...))` — single server-side call |
| Claiming the workbook contains values | The user opens it and sees `#N/A Requesting Data...` momentarily, then real values | Tell users the workbook needs Bloomberg add-in + refresh |
| Hardcoding dates inside `BDH` | Stale on reuse | Prefer relative dates: `"-1Y"`, `"0D"` |
| Using `BLP`/`BLPH` (legacy) | Works but flagged for migration | Use `BDP`/`BDH`/`BDS` family always |
| Writing BQL with inconsistent quote nesting | Excel parse error | Excel-side: `=_xll.BQL.Query("get(...) for(['IBM US Equity'])")` — outer double quotes for Excel, inner single for BQL string lists |
| Missing `IF(<member>="",...)` guard around per-member DAPI | `#N/A` cascades for empty rows | Always guard against blank ticker cells |

---

## 9. Quick reference cheat sheet

```
─────────────────────────────────────────────────────────────────────
  FORMULA                   PURPOSE                       COVERAGE
─────────────────────────────────────────────────────────────────────
  =_xll.BDP(s, f, ...)      single value                  any
  =_xll.BDH(s, f, sd, ed)   time series                   any
  =_xll.BDS(s, f, ...)      bulk/list (ArrayFormula)      any
  =_xll.BEQS(name, ...)     saved equity screen           Equity
  =_xll.BCURVE(curve_id)    yield curve members           Govt/Corp
  =_xll.BSRCH(name)         saved FI search               FI
  =_xll.BQL(body)           BQL (string body)             any
  =_xll.BQL.Query(body)     BQL (preferred for Excel)     any
  =_xll.BQL.Dates(spec)     date range builder            -
  =_xll.BQL.Params(...)     parameter set                 -
  =_xll.BQL.Expr(name, e)   named expression              -
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  YELLOW KEY      ASSET CLASS                    EXAMPLE SECURITY
─────────────────────────────────────────────────────────────────────
  Equity          stocks / ETFs / mutual funds   AAPL US Equity
  Govt            sovereign bonds                T 4 02/15/34 Govt
  Corp            corporate bonds                AAPL 3.85 05/04/43 Corp
  Mtge            mortgage-backed                FNCL 5.5 Mtge
  Muni            US municipal bonds             01069DBZ9 Muni
  Pfd             preferred shares               AAPL/P US Pfd
  Index           indices                        SPX Index
  Curncy          FX                             EURUSD Curncy
  Comdty          commodity futures              CLZ4 Comdty
  M-Mkt           money market                   <ticker> M-Mkt
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  BDH FLAG       VALUES                       PURPOSE
─────────────────────────────────────────────────────────────────────
  CURR=          USD/EUR/JPY/...              currency conversion
  PER=           cd/cw/cm/cq/cy/w/m/q/y       periodicity
  DAYS=          T/W/C/A                      day filter
  FILL=          B/N/P/0/.5                   missing-value fill
  CSHADJ=        Y/N                          cash adjustments
  CAPCHG=        Y/N                          capital changes
  DPDF=          Y/N                          use user's DPDF settings
  DIR=           V/H                          orientation
  DTS=           S/H                          show/hide dates
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  BQL CLAUSE     SHAPE                                   OPTIONAL?
─────────────────────────────────────────────────────────────────────
  let(...;)      reusable variable definitions           yes
  get(...)       output data items                       NO
  for(...)       universe                                NO
  with(...)      execution params (fill, currency, ...)  yes
  preferences()  output settings                         yes
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  BQL UNIVERSE BUILDER       RETURNS
─────────────────────────────────────────────────────────────────────
  ['SEC1', 'SEC2', ...]      explicit list
  members('<index>')         index constituents
  peers('<sec>')             peer companies
  holdings('<fund>')         fund holdings
  bonds('<equity>')          all bonds of issuer
  bondsuniv(ACTIVE|ALL|...)  bond universe scope
  segments('<sec>', ...)     business segments
  curvemembers('<curve>')    yield curve members
  screenresults(...)         saved screen
  filter(<u>, <cond>)        subset of universe
─────────────────────────────────────────────────────────────────────
```

---

## 10. When this skill is not enough

Bloomberg's surface is enormous. PRISM should fall back to user-side terminal commands when:

| Need | Tell user |
|---|---|
| Field discovery (mnemonic for an exotic metric) | "Run `FLDS<GO>` on a Bloomberg terminal — type the keyword and the search filters fields" |
| Function builder (DAPI argument suggestions) | "In Excel, type `=_xll.BDH(` and click `More Functions...` → `Help on this function`" |
| BQL Builder (interactive query builder) | "Type `BQL<GO>` on the terminal for the visual query builder" |
| Override flag for a niche field | "Open the field's `FLDS<GO>` page → optional arguments tab" |
| Uncommon yellow key (e.g. `Loan`, `Cmdt`) | "Confirm the security loads on the terminal first; the yellow key shows in the description bar" |
| Streaming / RTD / API-based data | "BDP/BDH refresh on workbook open. For real-time tick streams, the user needs `RTD<GO>` formulas or the Bloomberg API (blpapi)" |

The skill covers what PRISM authors *into a workbook*. Anything live-tick or beyond Excel's per-cell evaluation model is out of scope.

