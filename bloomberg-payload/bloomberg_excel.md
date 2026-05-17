# Bloomberg Excel Formulas (BQL + DAPI) — Hub

- **Module:** `bloomberg_excel`
- **Audience:** PRISM (all interfaces)
- **Tier:** 2 (on-demand)
- **Scope:** Authoring Bloomberg formula strings into Excel cells via `openpyxl`. The formulas evaluate when the user opens the workbook in Excel-with-Bloomberg-add-in. PRISM never executes BQL or blpapi itself — it ships a workbook the user evaluates locally.
- **PRISM filesystem:** Hub and spokes are siblings under `ai_development/context/modules/static/bloomberg/` (flat directory — no subfolder per spoke group). Mid-session spoke fetches use repo-relative paths from that root, e.g. `context/modules/static/bloomberg/bbg_equities.md`, inside `list_ai_repo(..., mode="full")`.

PRISM already knows `openpyxl`. This module teaches the formula catalog: legacy DAPI (`BDP` / `BDH` / `BDS` / `BEQS` / `BCURVE` / `BSRCH`), the modern BQL family (`BQL` / `BQL.Query` / `BQL.Dates` / `BQL.Params` / `BQL.Expr`), override flags, the universal cross-asset field surface, yellow-key security syntax, and the openpyxl-specific quirks.

**This file is the hub.** Asset-class–specific field catalogs, canonical tickers, and worked patterns live in spokes — see §10. Fetch the spokes you need in ONE `list_ai_repo` call after deciding scope.

---

## 0. PRISM has NO live Bloomberg access — operating constraint

PRISM does **not** have direct Bloomberg access. No `blpapi`, no live BQL execution, no real-time Bloomberg pricing inside PRISM's code sandbox. PRISM is licensed at the user's seat, not the server.

**The only thing PRISM can do with Bloomberg is author a workbook.** The .xlsx file ships to the user via `save_artifact()`. The user opens it in Excel-with-Bloomberg-add-in; the Bloomberg add-in evaluates the formulas against the user's authenticated seat; the user reviews / refreshes / exports / shares back.

The loop:

```
PRISM authors workbook (this skill teaches the formulas to write)
              │
              ▼  save_artifact() → user downloads
              │
USER opens in Excel-with-Bloomberg-add-in (the data evaluates HERE)
              │
              ▼  refresh / inspect / annotate
              │
USER shares back (screenshot, refreshed workbook, written summary, the
                  numbers themselves typed into chat, the file re-uploaded)
              │
              ▼
PRISM iterates on the workbook (edit formulas, re-ship)
```

**Analysis happens at the user's seat, not in PRISM's sandbox.** When the user asks "is CPI surprising to the upside?", PRISM cannot answer from a live Bloomberg pull — it can only:

1. Author a workbook that pulls the relevant data (this skill teaches which formulas).
2. Ship the workbook.
3. Iterate after the user opens and reports back.

If the user wants PRISM to do the analysis itself, route to PRISM's primary data sources (Haver via `pull_haver_data`, FRED via `pull_fred_data`, GS market data, the API clients in `mcp/clients/`). Those run inside the sandbox and can compute live. Bloomberg is the workbook path, not the analysis path.

### 0.1 What Bloomberg gives PRISM that PRISM's primary sources don't

PRISM already has Haver, GS market data, the `mcp/clients/` API surface (20+ clients for FDIC, SEC EDGAR, Treasury, NY Fed, BIS, etc.). Bloomberg's incremental value over those is the proprietary curated data Bloomberg does NOT distribute via cheap APIs:

| Asset class | What Bloomberg uniquely gives |
|---|---|
| Macro | The economist consensus survey itself (`BN_SURVEY_MEDIAN` / `HIGH` / `LOW` / `FORECAST_STANDARD_DEVIATION`) — ~80 sell-side / buy-side economists polled per release. PRISM's primary sources have the actuals but not the consensus. This is the spine of the macro-surprise case study. |
| Equities | Forward analyst consensus across the global investable universe (`BEST_EPS`, `BEST_TARGET_PRICE`, `BEST_SALES`, recommendations / count of analysts). Bloomberg-curated peers (`EQY_BLOOMBERG_PEERS`). Business segments via `segments(...)`. |
| Fixed income | BQL bond universe screening (`bondsuniv()`, `bonds(<issuer>)`, `screenresults(SRCH)`) — cross-sectional screening over hundreds of thousands of bonds. Bloomberg fixed-income indices (`LF98*` / `LUAC*` / `LCB*` / `BEUS*`) with consistent OAS / YTW / duration methodology. |
| Credit | CDX / iTraxx with auto-rolling generic tickers. Composite ratings (`BB_COMPOSITE_RATING`). Default-probability model (`DRSK_*`). Single-name CDS with RED codes. |
| FX | Implied-vol surface (Bloomberg's BVOL composite across 200+ pairs — ATM / 25R / 25B / 10R / 10B per tenor). Forward outrights and points across deliverable and non-deliverable markets. |
| Commodities | CFTC COT data pre-parsed into both the legacy and disaggregated breakdowns (managed money / swap dealer / producer / commercial). LME inventories. Roll-adjustment variants on futures generics. |
| Corporate events | Earnings calendar + actual + estimate EPS history (`ERN_ANN_DT_TIME_HIST_WITH_EPS`). SEC filing URLs (`RR_*` family). Earnings transcript availability flags + URLs (`EVT_*` family — content is terminal-gated; PRISM ships the URL, user clicks through). Dividend history with type classification (`DVD_HIST_ALL` returning special / capital-gain / stock dividends in addition to ordinary). M&A status fields. |
| User-side | The user's own saved EQS / SRCH screens, monitors, portfolios — addressable from the workbook via `BEQS(<screen_name>)`. |

What Bloomberg does NOT give PRISM directly: live execution. The workbook is the contract.

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

ws["B2"] = '=_xll.BDP("AAPL US Equity","PX_LAST")'

ws["A5"] = ArrayFormula(
    "A5:C257",
    '=_xll.BDH("AAPL US Equity","PX_LAST,PX_VOLUME","-1Y","0D","Dts=S","Dir=V")'
)

ws["A1"] = ArrayFormula("A1:A600", '=_xll.BDS("SPX Index","INDX_MEMBERS")')
```

Size the range **precisely** — not generously. Over-allocation locks the workbook in ways that cannot be undone after the user opens the file (see §1.4 for the mechanism). Reference counts:

- `BDH` daily: rows = expected trading days + 1 header (~252/yr for US equities, ~260 for global; 365 for `PER=cd` calendar-day series). Cols = N fields + 1 date col (when `DTS=S`), or N fields (when `DTS=H`).
- `BDS` member lists: SPX ≈ 503, NDX = 100, RTY ≈ 2,000, ACWI ≈ 2,800, sector ETFs 30–500. Counts drift with index reconstitution — use the dedicated-fetch-sheet pattern in §1.4 to absorb the drift.
- `BEQS` saved screens: count is unknown until first refresh. **Isolate on a dedicated sheet** (§1.4) — never embed a `BEQS` array on a sheet the user will edit.
- `BQL`: row count = output cardinality of the `for(...)` clause. `for(['SEC1','SEC2'])` returns one row per security per data item. `for(members(<index>))` matches the BDS counts above. Time-series BQL (`get(px_last(dates=range(...)))`) returns rows = N securities × M periods + 1 header.

### 1.4 `ArrayFormula` footprint is locked — size precisely, isolate the block

`openpyxl.worksheet.formula.ArrayFormula(ref, formula)` serialises as a **legacy CSE array** in the XLSX file:

```xml
<c r="A3"><f t="array" ref="A3:A700">_xll.BDS("SPX Index","INDX_MEMBERS")</f></c>
```

`t="array"` is the same form Excel produces when a user types a formula and presses **Ctrl+Shift+Enter**. Excel 365 with the modern Bloomberg add-in honours the entire `ref` range as an immutable group. Concretely:

- The user **cannot** edit any cell inside `A3:A700`, even rows that look blank because the BDS return only populated `A3:A510`.
- The user **cannot** paste into any cell inside the range — Excel pops "You can't change part of an array."
- The user **cannot** insert or delete rows that intersect the range — same error.
- The footprint is locked the moment the workbook opens; it does **not** shrink to the populated subset after refresh.

Two design rules follow:

1. **Size precisely, not generously.** The "+50% safety margin" instinct is wrong here — every over-allocated row is a row the user cannot reclaim. Compute the expected return shape from the query (use the reference counts in §1.3) and match the range exactly.

2. **Isolate dynamic-count array blocks on a dedicated fetch sheet.** When the cardinality is unknown until refresh (BEQS results, BQL filters, index members that drift with reconstitution) or the user is likely to annotate / edit nearby, the safe layout is two sheets:
   - `_data` (or `_members`, `_query` — leading underscore signals "do not edit"): holds the raw `ArrayFormula` blocks. Loose sizing is acceptable here because the user never edits this sheet.
   - `View` (user-facing): references `_data` via `INDEX` / `OFFSET` / `IFERROR` to display only the populated subset. Annotations, sorts, inserts, and edits happen on this sheet — no array formulas live here, so every cell is freely editable.

Minimal example of the pattern (§7.3 / §7.4 build it out for SPX members + BQL):

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
wb.remove(wb["Sheet"])
ws_data = wb.create_sheet("_members")
ws_view = wb.create_sheet("View")

ws_data["A1"] = ArrayFormula("A1:A700", '=_xll.BDS("SPX Index","INDX_MEMBERS")')

ws_view["A1"] = "Ticker"
for r in range(2, 600):
    ws_view.cell(row=r, column=1, value=f'=IFERROR(INDEX(_members!A:A,{r - 1}),"")')

wb.save("isolated.xlsx")
```

### 1.5 Cached values are not real

`openpyxl` reads cached values via `data_only=True`. Cells with Bloomberg formulas have **NO valid cached value** in a freshly-authored workbook — they're populated only after Excel-with-add-in opens the file. PRISM should never claim a Bloomberg-formula workbook contains real numbers; the file evaluates at open-time.

### 1.6 Refresh-on-open behaviour

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

| Yellow key | Sector | Examples | Spoke |
|---|---|---|---|
| `Equity` | Common stock, ADRs, ETFs, mutual funds, rights, warrants, **listed equity / ETF options** | `AAPL US Equity`, `7203 JT Equity`, `SPY US Equity`, `AAPL US 06/21/24 C200 Equity` (option) | `bbg_equities.md` (cash) / `bbg_options.md` (options) |
| `Govt` | Sovereign bonds (US Treasury, Bunds, JGBs, Gilts) | `T 4 02/15/34 Govt`, `912828YK0 Govt`, `CT10 Govt` (current 10Y) | `bbg_fixed_income.md` |
| `Corp` | Corporate bonds | `AAPL 3.85 05/04/43 Corp`, `037833DL1 Corp` (CUSIP) | `bbg_fixed_income.md`, `bbg_credit.md` |
| `Mtge` | Mortgage-backed (TBAs, agency MBS, CMOs) | `FNCL 5.5 Mtge`, `3132J5K Mtge` | `bbg_fixed_income.md` |
| `Muni` | US municipal bonds | `01069DBZ9 Muni` | `bbg_fixed_income.md` |
| `Pfd` | Preferred shares | `AAPL/P US Pfd` | `bbg_equities.md` |
| `M-Mkt` | Money market (CP, CDs) | `SOALA LNST M-Mkt` | `bbg_fixed_income.md` |
| `Index` | Indices and **listed index options** | `SPX Index`, `LF98TRUU Index` (US HY), `CPI YOY Index`, `SPX 06/21/24 C5500 Index` (option), `VIX Index`, `UX1 Index` (VIX future) | per asset class; index options in `bbg_options.md` |
| `Curncy` | FX spot, forwards, NDFs, FX vol | `EURUSD Curncy`, `USDJPY1M Curncy`, `EURUSDV1M Curncy` | `bbg_fx.md` |
| `Comdty` | Commodity futures and **futures options** | `CLZ4 Comdty` (Dec'24 WTI), `GC1 Comdty` (front gold), `CLM4P 60 Comdty` (option) | `bbg_commodities.md` (futures) / `bbg_options.md` (options) |
| `Port` | Saved Bloomberg portfolio | `U12345678-1 Client` (less common in formulas) | `bbg_equities.md` |

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

| Form | Meaning | Spoke |
|---|---|---|
| `CT10 Govt` | "Current 10-Year UST" — auto-rolls to the current on-the-run issue | `bbg_fixed_income.md` |
| `GT10 Govt`, `GTGBP10Y Govt`, `GTJPY10Y Govt` | Generic 10Y for currency-specific sovereign | `bbg_fixed_income.md` |
| `CL1 Comdty`, `CL2 Comdty` | First / second futures contract (roll-adjusted) | `bbg_commodities.md` |
| `CLN5 Comdty` | Specific futures contract: ticker + month-code + year digit | `bbg_commodities.md` |
| `EURUSD BGN Curncy` | EURUSD with `BGN` pricing source (Bloomberg Generic) | `bbg_fx.md` |
| `EUR1M BGN Curncy` | 1M EUR forward outright | `bbg_fx.md` |

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
| `PER=` | `cd` / `cw` / `cm` / `cq` / `cs` / `cy` / `w` / `m` / `q` / `y` / `s` | Periodicity. `cd` calendar day, `cw` calendar week, `cm` cal. month, `cq` cal. quarter, `cs` semi-annual, `cy` cal. year. Lowercase variants (`w`, `m`, `q`, `y`) use Bloomberg's holiday-aware calendar. |
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

Common universal-shape fields: `INDX_MEMBERS`, `INDX_MWEIGHT`, `TOP_HOLDERS_PUBLIC_FILINGS`, `DVD_HIST_ALL`, `BOND_CHAIN`, `DES_NOTES`. Asset-class-specific `BDS` fields live in the spokes.

```python
ws["A1"] = ArrayFormula("A1:B600", '=_xll.BDS("SPX Index","INDX_MEMBERS")')
ws["A1"] = ArrayFormula("A1:E50", '=_xll.BDS("AAPL US Equity","TOP_20_HOLDERS_PUBLIC_FILINGS")')
ws["A1"] = ArrayFormula(
    "A1:I40",
    '=_xll.BDS("AAPL US Equity","DVD_HIST_ALL","DVD_START_DT=20180101","DVD_END_DT=20241231")'
)
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

Curve IDs: `S23` (USD swap), `S45` (EUR swap), `S141` (JPY swap), `YCSW0023 Index` (full curve ticker form). The full curve catalog is in `bbg_fixed_income.md`.

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

## 6. Universal cross-asset fields

These mnemonics work across every yellow key. Asset-class-specific catalogs (fundamentals, yields, spreads, vol, contract specs, releases, surveys, calendars) live in the spokes.

| Mnemonic | Meaning |
|---|---|
| `NAME` | Bloomberg short name |
| `LONG_COMP_NAME` | Full company name (where applicable) |
| `SECURITY_DES` | Description (incl. coupon/maturity for bonds, contract for futures) |
| `ID_ISIN` | ISIN |
| `ID_CUSIP` | CUSIP |
| `ID_BB_GLOBAL` | FIGI |
| `ID_BB_UNIQUE` | Bloomberg unique ID |
| `PX_LAST` | Last price (varies by asset: stock close, bond yield, fx spot, futures settle, index level) |
| `PX_OPEN` / `PX_HIGH` / `PX_LOW` | Day's OHL (price-bearing securities) |
| `PX_BID` / `PX_ASK` / `PX_MID` | Quoted bid / ask / mid |
| `PX_VOLUME` | Day's volume |
| `LAST_UPDATE` / `LAST_UPDATE_DT` | Last-update timestamp / date |
| `CRNCY` | Reporting currency |
| `COUNTRY_FULL_NAME` / `COUNTRY_ISO` | Domicile |
| `MARKET_SECTOR_DES` | Sector designation (matches the yellow key) |
| `MARKET_STATUS` | OPEN / CLOSED / PRE-OPEN |
| `TRADING_DAY_END_TIME_EOD` | Day's close time |

For everything else — fundamentals, yields, spreads, vol, ratings, contract specs, ECO releases, earnings, filings, dividends — fetch the relevant spoke (§10).

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

### 7.2 Time series patterns

Three building blocks: (1) `BDH` for one or a few securities, parallel-stacked; (2) `BQL` with `dates=range(...)` for many securities or computed/derived series; (3) precise sizing so the `ArrayFormula` range matches the expected output — over-allocation locks the workbook (§1.4).

#### 7.2.1 Sizing math by periodicity

Compute row counts before authoring the `ArrayFormula` range. Header row is always +1.

```python
from datetime import date

def bdh_row_count(start: date, end: date, periodicity: str = "D") -> int:
    """Expected BDH row count INCLUDING the 1-row header.

    Approximate to +/- 1-2 rows due to leap years, market holidays,
    and weekend alignment. Verify after the first refresh and resize
    the ArrayFormula range if needed before re-shipping the workbook.

    periodicity: 'D' trading days (~252/yr), 'W' weeks, 'M' months,
                 'Q' quarters, 'Y' years, 'CD' calendar days
    """
    days = (end - start).days
    years = days / 365.25
    if   periodicity == "D":  observations = round(years * 252)
    elif periodicity == "W":  observations = round(years * 52)
    elif periodicity == "M":  observations = round(years * 12)
    elif periodicity == "Q":  observations = round(years * 4)
    elif periodicity == "Y":  observations = round(years)
    elif periodicity == "CD": observations = days
    else: raise ValueError(f"unknown periodicity {periodicity}")
    return observations + 1
```

Common quick references (header row included; +/- 1-2 in practice):

| Window | `D` (trading) | `W` | `M` | `Q` | `Y` | `CD` |
|---|---|---|---|---|---|---|
| 1Y | 253 | 53 | 13 | 5 | 2 | 366 |
| 2Y | 505 | 105 | 25 | 9 | 3 | 731 |
| 5Y | 1,261 | 261 | 61 | 21 | 6 | 1,827 |
| 10Y | 2,521 | 521 | 121 | 41 | 11 | 3,653 |

#### 7.2.2 Single security, multi-field, daily

```python
from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "History"

ticker = "SPY US Equity"
fields = "PX_LAST,PX_VOLUME,PX_HIGH,PX_LOW"
n_fields = len(fields.split(","))
n_rows = bdh_row_count(date.today() - timedelta(days=365), date.today(), "D")  # 253

ws["A1"] = f"Daily history: {ticker}"

last_col = chr(ord("A") + n_fields)                                         # "E" for 4 fields
ws["A3"] = ArrayFormula(
    f"A3:{last_col}{2 + n_rows}",                                           # A3:E255
    f'=_xll.BDH("{ticker}","{fields}","-1Y","0D","Dts=S","Dir=V")'
)

wb.save("history_single.xlsx")
```

The result lays out as:

```
   A           B          C            D          E
   Date        PX_LAST    PX_VOLUME    PX_HIGH    PX_LOW
   2025-05-16  583.46     42531200     584.10     580.22
   2025-05-17  ...
```

#### 7.2.3 Multi-security, parallel histories (wide layout)

For 2–10 securities, side-by-side `BDH` blocks each carry their own date axis (robust to misaligned calendars across markets / currencies). Place each ticker's block in its own contiguous range so no two `ArrayFormula` footprints overlap.

```python
from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "Comp"

tickers = ["SPY US Equity", "AGG US Equity", "GLD US Equity", "VNQ US Equity"]
field = "PX_LAST"
n_rows = bdh_row_count(date.today() - timedelta(days=5 * 365), date.today(), "D")  # 1261

ws["A1"] = f"5Y daily close, {len(tickers)} ETFs"

for i, ticker in enumerate(tickers):
    col_date = chr(ord("A") + i * 2)                                        # A, C, E, G
    col_val  = chr(ord("B") + i * 2)                                        # B, D, F, H
    ws[f"{col_date}3"] = ArrayFormula(
        f"{col_date}3:{col_val}{2 + n_rows}",
        f'=_xll.BDH("{ticker}","{field}","-5Y","0D","Dts=S","Dir=V")'
    )

wb.save("comp_wide.xlsx")
```

Above ~10 securities switch to `BQL` (§7.2.5) — one server-side call beats N parallel `BDH` refreshes on both latency and refresh-storm risk.

#### 7.2.4 Frequency, currency, total-return overrides

Common variants on the same `BDH` call:

```python
from datetime import date

start = date(2020, 1, 1)
end   = date(2024, 12, 31)

# Monthly, USD-converted, total-return (incl. dividends + splits)
ws["A3"] = ArrayFormula(
    f"A3:B{2 + bdh_row_count(start, end, 'M')}",
    f'=_xll.BDH("MSFT US Equity","DAY_TO_DAY_TOT_RETURN_GROSS_DVDS",'
    f'"{start:%Y%m%d}","{end:%Y%m%d}",'
    f'"Per=cm","Days=T","Fill=P","CURR=USD","CSHADJ=Y","CAPCHG=Y","Dts=S","Dir=V")'
)

# Weekly mid-yield for a Treasury, no fill (preserve gaps in the series)
ws["A3"] = ArrayFormula(
    f"A3:B{2 + bdh_row_count(start, end, 'W')}",
    f'=_xll.BDH("T 4 02/15/34 Govt","YLD_YTM_MID",'
    f'"{start:%Y%m%d}","{end:%Y%m%d}",'
    f'"Per=cw","Days=T","Fill=N","QtyP=Y","Dts=S","Dir=V")'
)

# Calendar-day FX, forward-fill weekends/holidays
ws["A3"] = ArrayFormula(
    f"A3:B{2 + bdh_row_count(start, end, 'CD')}",
    f'=_xll.BDH("USDJPY BGN Curncy","PX_LAST",'
    f'"{start:%Y%m%d}","{end:%Y%m%d}",'
    f'"Per=cd","Days=C","Fill=P","Dts=S","Dir=V")'
)
```

Override flag reminders (full table in §4.3):

- `PER=` — `cd`/`cw`/`cm`/`cq`/`cs`/`cy` calendar-based; `w`/`m`/`q`/`y` use Bloomberg's holiday-aware calendar.
- `DAYS=` — `T` trading, `C` calendar, `W` weekdays, `A` all.
- `FILL=` — `P` previous (right default for prices), `N` `#N/A` (right for spreads/yields where gaps are meaningful), `B` blank, `0` zero.
- `CURR=` — ISO 4217. Applies to the value column, not the date axis.
- `CSHADJ=Y` + `CAPCHG=Y` — full total-return basis (dividends + corporate actions).

#### 7.2.5 Time series via `BQL` (many securities, one server-side call)

When the universe is large (>10 securities, or `members(<index>)`), one `BQL.Query` beats N parallel `BDH` calls — compute happens server-side and the wire is one round-trip.

```python
from datetime import date, timedelta
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "BQL_TS"

tickers = ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity",
           "AMZN US Equity", "META US Equity"]
periods = bdh_row_count(date.today() - timedelta(days=365), date.today(), "M") - 1  # 12
n_rows  = len(tickers) * periods + 1                                                # 61

bql = (
    "get(px_last(dates=range(-1Y, 0D), frq=M, fill=PREV)) "
    "for([" + ",".join(f"'{t}'" for t in tickers) + "])"
)

ws["A3"] = ArrayFormula(
    f"A3:C{2 + n_rows}",                                                    # ID | DATE | VALUE
    f'=_xll.BQL.Query("{bql}")'
)

wb.save("ts_bql.xlsx")
```

BQL's default output schema for time-series `get()` is a **long table**: one row per `(security, date)` pair, with implicit columns `ID | DATE | VALUE` plus the header row. Multiple data items (e.g. `get(name(), px_last(dates=...))`) add one column per item.

Trade-off vs `BDH`:

| | `BDH` × N securities | `BQL.Query` with `for([...])` |
|---|---|---|
| Bloomberg calls per refresh | N | 1 |
| Natural layout | wide (one block per security) | long (one row per security × period) |
| Custom expressions / filters | per-row Excel formula | `let(...)` + `filter(...)` server-side |
| Crossover | best ≤ ~10 securities | best > ~10 securities |
| Locked footprint | sum of N per-security ranges | single ID×DATE table |

### 7.3 Index members + per-member fields (dedicated-fetch-sheet pattern)

Index membership drifts over reconstitutions, so the BDS member array cannot be sized precisely once-and-forever. Isolate the array on a dedicated `_members` fetch sheet and present a clean, editable `View` sheet that references it (§1.4).

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
wb.remove(wb["Sheet"])
ws_data = wb.create_sheet("_members")
ws_view = wb.create_sheet("View")

ws_data["A1"] = ArrayFormula("A1:A700", '=_xll.BDS("SPX Index","INDX_MEMBERS")')

ws_view["A1"] = "Ticker"
ws_view["B1"] = "Market Cap (USD)"
ws_view["C1"] = "P/E"

for r in range(2, 600):
    ws_view.cell(row=r, column=1,
                 value=f'=IFERROR(INDEX(_members!A:A,{r - 1}),"")')
    ws_view.cell(row=r, column=2,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r}&" Equity","CUR_MKT_CAP","EQY_FUND_CRNCY","USD"))')
    ws_view.cell(row=r, column=3,
                 value=f'=IF(A{r}="","",_xll.BDP(A{r}&" Equity","PE_RATIO"))')

wb.save("spx_members.xlsx")
```

Why this layout matters:

- The View sheet has no `ArrayFormula` blocks, so the user can sort, filter, insert rows, paste annotations — none of the "you can't change part of an array" errors that would block them on a single-sheet layout.
- `INDEX(_members!A:A, r - 1)` returns `""` once the BDS array runs out, and the `IFERROR` wrapper keeps the View sheet visually clean.
- The per-row `BDP` cells on the View sheet are individual formulas (not array members), so the user can paste-replace any individual BDP with a static value to "pin" a number.

### 7.4 BQL screen + computation (dedicated-fetch-sheet pattern)

The filtered result count is unknown until first refresh, so apply the same `_query` + `View` split as §7.3.

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
wb.remove(wb["Sheet"])
ws_data = wb.create_sheet("_query")
ws_view = wb.create_sheet("View")

bql = (
    'let('
    '#momentum=px_last() / sma(period=200) - 1; '
    '#pe=pe_ratio();'
    ') '
    'get(name(), gics_sector_name(), #pe, #momentum) '
    'for(filter(members(\'SPX Index\'), '
    'and(#pe < 15, #momentum > 0.10, cur_mkt_cap > 5e9)))'
)

ws_data["A1"] = ArrayFormula(
    "A1:E300",
    f'=_xll.BQL.Query("{bql}")'
)

ws_view["A1"] = "Name"
ws_view["B1"] = "Sector"
ws_view["C1"] = "P/E"
ws_view["D1"] = "Momentum"

for r in range(2, 200):
    ws_view.cell(row=r, column=1, value=f'=IFERROR(INDEX(_query!B:B,{r}),"")')
    ws_view.cell(row=r, column=2, value=f'=IFERROR(INDEX(_query!C:C,{r}),"")')
    ws_view.cell(row=r, column=3, value=f'=IFERROR(INDEX(_query!D:D,{r}),"")')
    ws_view.cell(row=r, column=4, value=f'=IFERROR(INDEX(_query!E:E,{r}),"")')

wb.save("bql_momentum.xlsx")
```

Two BQL quoting points to remember:

- The Python f-string is single-quoted; the Excel formula wraps the BQL body in double quotes (`=_xll.BQL.Query("...")`); the BQL body itself uses single quotes for security identifiers and index names (`members('SPX Index')`). Three layers of quoting, each consistent — no escaping needed when you stack them this way.
- BQL's output column count = (number of `get(...)` items) + 1 implicit `ID` column. `get(name(), gics_sector_name(), #pe, #momentum)` yields 5 columns (`ID` first). Size the `ArrayFormula` range accordingly on the fetch sheet.

### 7.5 Reading a Bloomberg-driven workbook back

When the user uploads a file containing Bloomberg formulas:

```python
from openpyxl import load_workbook

wb = load_workbook("user_workbook.xlsx", data_only=False)
for row in wb.active.iter_rows():
    for cell in row:
        if cell.value and isinstance(cell.value, str) and cell.value.startswith("=_xll."):
            print(cell.coordinate, cell.value)

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
| Under-sized array range | Truncated results, no warning | Compute the precise expected count (§1.3 reference counts; §7.2.1 sizing helper) and match the range exactly — `INDEX(_data!…, n)` on a view sheet absorbs small under-sizing |
| Over-allocated `ArrayFormula` range (e.g. `A1:A1000` for SPX members) | "You can't change part of an array" when the user tries to edit / paste / insert anywhere inside the range — even the rows that look blank are locked | Size precisely; for dynamic-count results (BEQS, BQL filters, drifting index members) isolate the array on a dedicated `_fetch` sheet and present a clean `View` via `INDEX` / `IFERROR` (§1.4, §7.3, §7.4) |
| Misspelled field mnemonic | Cell returns `#N/A Field Not Applicable` | Confirm via `FLDS<GO>`; spoke files (§10) carry the curated catalog |
| Wrong yellow key (`AAPL US` without `Equity`) | `#N/A Invalid Security` | Always include yellow key |
| Mixing currencies without override | Aggregated metrics nonsensical | Pass `EQY_FUND_CRNCY=USD` (DAPI) or `currency=USD` (BQL) |
| Asking for forward fundamentals without period override | Returns last reported (LTM/FY0) instead of forward | DAPI: add `BEST_FPERIOD_OVERRIDE=1BF`. BQL: `pe_ratio(fpt=A, fpr=1BF)` |
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

## 10. Spokes — fetch what the workflow needs

The hub above is sufficient for cross-asset price/ID work. Anything that depends on asset-class-specific fields, special tickers, screening conventions, or contract specifics lives in a spoke.

**Working model: decide the spoke list HERE during preflight, then fetch the hub-loaded spoke set in ONE `list_ai_repo` call.** Do not fetch a single spoke and come back for more later — pick the full list now.

### 10.1 Spoke menu

| Spoke | What it carries | Pick when... |
|---|---|---|
| `context/modules/static/bloomberg/bbg_equities.md` | Equity-specific fields (fundamentals, ratios, estimates, holdings), GICS / BICS classification, BEQS screens, INDX_MEMBERS conventions, peers / segments, factor / momentum signals | User asks about a stock, ETF, sector, index members, screening, fundamentals, valuation ratios, holders |
| `context/modules/static/bloomberg/bbg_fixed_income.md` | Govt / Corp / Mtge / Muni yellow keys, on-the-run conventions (CT*, GT*), yields (YLD_YTM_*, YLD_TO_WORST), spreads (OAS, Z-spread, ASW), duration / convexity / DV01, BCURVE swap-curve IDs, BQL `bondsuniv` / `bonds` patterns, issue-level data (calls, ratings, sinking funds), cash-flow schedules | Bond pricing, yield curves, duration / risk metrics, issue-level analysis, sovereign curves |
| `context/modules/static/bloomberg/bbg_credit.md` | CDS instruments (RED codes, SR / SUB tiers), CDX / iTraxx index series (CDX HY, CDX IG, iTraxx Main, Crossover, SubFin, SovX), Bloomberg HY / IG cash-bond indices (LF98TRUU, LUACTRUU, LUACTRPP), ratings (RTG_SP / RTG_MOODY / RTG_FITCH), default / recovery fields | Credit derivatives, IG / HY index analysis, ratings work, credit-curve work |
| `context/modules/static/bloomberg/bbg_macro.md` | ECO release index tickers (CPI YOY Index, NFP P Index, USURTOT Index, etc.), Bloomberg survey fields (ACTUAL_RELEASE, BN_SURVEY_MEDIAN, BN_SURVEY_HIGH/LOW, FORECAST_STANDARD_DEVIATION), surprise indices (CESI* family), central-bank meeting fields, WIRP / OIS-implied policy paths, CFTC COT, nowcast indices. Includes the canonical pattern for pulling release-actuals-vs-surveys history | Macro release work, surprise indices, central-bank expectations, positioning data |
| `context/modules/static/bloomberg/bbg_fx.md` | Spot / forward / NDF security syntax (`EURUSD Curncy`, `EURUSD1M Curncy`, `USDIDR1M NDF Curncy`), pricing sources (`BGN`, `CMPN`, `BFIX`), forward-points fields, implied-vol surface (`EURUSDV1M Curncy`, risk reversals `EURUSD25R1M Curncy`, butterflies `EURUSD25B1M Curncy`), carry / IR differentials | FX spot / forward, FX vol surface, NDFs, carry analysis |
| `context/modules/static/bloomberg/bbg_commodities.md` | Futures-generic conventions (`CL1`, `CL2`, ... vs specific `CLZ4`), month-code calendar, continuous-roll variants, contract-spec fields (`FUT_CONTRACT_SIZE`, `FUT_TICK_SIZE`, `FUT_VAL_PT`), inventory / supply data (DOE_*, USDA_*), CFTC positioning fields, calendar-spread helpers | Futures contracts, term structure, inventories, COT positioning |
| `context/modules/static/bloomberg/bbg_events.md` | Earnings calendar + actuals + estimates (`ANR_EARNINGS_DATE_TIME_HIST`, `ERN_ANN_DT_TIME_HIST_WITH_EPS`, `DY895`, BQL `actual_eps()` / `estimate_eps()`), dividend history (`DVD_HIST_ALL` with `DVD_START_DT` / `DVD_END_DT`), SEC filings (`RR_LIST_OF_FILINGS_WITH_DATES`, `RR_FILING_DOC_URL`), earnings transcript availability via `EVT<GO>` event tracker (URL-bearing, terminal-gated content), corporate actions (splits, spinoffs, IPOs, buybacks), M&A status fields. Includes the canonical pattern for pulling filings + earnings history for one company | Earnings work, filings / 10-K / 10-Q discovery, transcripts, dividend history, corporate actions, M&A status |
| `context/modules/static/bloomberg/bbg_options.md` | Per-option security syntax across underlying classes (stock / ETF / index / futures), `OPT_CHAIN` BDS field + filters, Greeks (`OPT_DELTA_MID` / `OPT_GAMMA_MID` / `OPT_THETA_MID` / `OPT_VEGA_MID` / `OPT_RHO_MID`), implied volatility (`IMPLIED_VOLATILITY_MID`), vol-surface index tickers (`SPXVV3M Index`, `SPX25R1M Index` skew, `VIX Index` / `VVIX Index`, VIX futures `UX1`/`UX2 Index`). Includes the canonical chain-with-Greeks and vol-surface dashboard patterns | Options chain, Greeks, IV history, vol-surface time series, VIX term structure, skew analysis |

### 10.2 The single fetch call

```python
list_ai_repo(
    file_paths=["context/modules/static/bloomberg/bbg_equities.md", "context/modules/static/bloomberg/bbg_events.md"],
    mode="full",
)
```

Pass ONLY `file_paths` and `mode` actively; omit every other parameter. **Do NOT call `get_context()` again** — it is one-shot per user message. **Do NOT make a second `list_ai_repo` call later for spokes you forgot** — pick the full list now.

**Common combos** (one call, copy-paste verbatim):

| Build shape | Single call to copy |
|---|---|
| Single-asset equity workbook | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_equities.md"], mode="full")` |
| Index member fundamentals | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_equities.md"], mode="full")` |
| Earnings preview / filings inheritance | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_equities.md", "context/modules/static/bloomberg/bbg_events.md"], mode="full")` |
| Bond cash-flow / duration workbook | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_fixed_income.md"], mode="full")` |
| HY / IG spread time series | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_fixed_income.md", "context/modules/static/bloomberg/bbg_credit.md"], mode="full")` |
| CDS / CDX positioning workbook | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_credit.md"], mode="full")` |
| Macro release calendar / surprise history | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_macro.md"], mode="full")` |
| FX vol surface dashboard | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_fx.md"], mode="full")` |
| Commodity term structure | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_commodities.md"], mode="full")` |
| Cross-asset macro dashboard (releases + rates + FX) | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_macro.md", "context/modules/static/bloomberg/bbg_fixed_income.md", "context/modules/static/bloomberg/bbg_fx.md"], mode="full")` |
| Options chain + Greeks workbook | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_options.md"], mode="full")` |
| Vol-surface dashboard (SPX / NDX / VIX term structure) | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_options.md"], mode="full")` |
| Single stock with options overlay (cash + options chain) | `list_ai_repo(file_paths=["context/modules/static/bloomberg/bbg_equities.md", "context/modules/static/bloomberg/bbg_options.md"], mode="full")` |

When in doubt, lean toward including more spokes. The marginal cost of an extra spoke is small; the cost of a forbidden second `list_ai_repo` call (or worse, authoring against guessed field names) is large.

---

## 11. When this skill is not enough

Bloomberg's surface is enormous, but more fundamentally PRISM operates one step removed from Bloomberg itself (§0). PRISM authors the workbook; the user evaluates it. When the user wants something PRISM cannot author or that requires live data:

| Need | Tell user |
|---|---|
| "Tell me what CPI just printed" / any live analysis from Bloomberg | PRISM cannot pull Bloomberg data directly (§0). Either: (a) PRISM authors a workbook the user refreshes and shares back, or (b) PRISM uses primary sources — Haver (`pull_haver_data`), FRED (`pull_fred_data`), GS market data (`pull_market_data`), or the `mcp/clients/` API surface — which run inside the sandbox. |
| Field discovery (mnemonic for an exotic metric not in the spokes) | "Run `FLDS<GO>` on a Bloomberg terminal — type the keyword and the search filters fields" |
| Function builder (DAPI argument suggestions) | "In Excel, type `=_xll.BDH(` and click `More Functions...` → `Help on this function`" |
| BQL Builder (interactive query builder) | "Type `BQL<GO>` on the terminal for the visual query builder" |
| Override flag for a niche field | "Open the field's `FLDS<GO>` page → optional arguments tab" |
| Uncommon yellow key (e.g. `Loan`, `Cmdt`) | "Confirm the security loads on the terminal first; the yellow key shows in the description bar" |
| Streaming / RTD / API-based data | "BDP/BDH refresh on workbook open. For real-time tick streams, the user needs `RTD<GO>` formulas or the Bloomberg API (blpapi). PRISM cannot consume either." |
| Saved screens not yet defined | "PRISM cannot define new EQS / SRCH screens for you. Save the screen in `EQS<GO>` / `SRCH<GO>` first, then BEQS / BSRCH evaluate it" |
| Earnings transcript text content | The transcript document itself is terminal-gated — `EVT<GO>` shows it on the terminal but the text is not exposed to Excel. PRISM can author a workbook listing event dates + Bloomberg's document URL; the user clicks through on the terminal to read the actual transcript. |
| News content / `NW<GO>` text | News article body is not exposed to Excel-add-in formulas; PRISM can pull news *metadata* (count, sentiment scores per `NEWS_SENTIMENT_*`) but not the text. |
| Chat / IB messages / `MSG<GO>` history | Bloomberg Vault (`BVLT<GO>` / Bloomberg Vault Excel add-in) is the compliance-archive product. The standard Bloomberg Excel add-in does NOT expose IB / MSG content as DAPI fields. PRISM cannot author a workbook that pulls chat history. Tell the user: "Use `MSG<GO>` on terminal to read live; use Bloomberg Vault for archival export — both require user-side action; PRISM is not in this loop." |
| Real-time tick streaming via RTD | `=RTD("blpapi", ...)` updates while Excel is OPEN; PRISM ships refresh-on-open workbooks, so the user has to keep Excel open + active to capture streams. Most PRISM workbooks should stick to `BDP` / `BDH` / `BDS`. Use RTD only when the explicit ask is a live trading board. |
| PORT analytics / risk decomposition | Bloomberg PORT (`PORT<GO>`) is a terminal-resident analytics product with thin Excel hooks. PRISM can replicate beta / sector decomposition via BQL aggregations (`bbg_equities.md` §8), but the full factor / scenario / attribution surface is terminal-only. Direct the user to `PORT<GO>` for serious risk work. |

The skill covers what PRISM authors *into a workbook*. Anything live-tick, anything that requires reading Bloomberg's document / chat / news content, full PORT analytics, or any in-sandbox analysis against Bloomberg data is out of scope.
