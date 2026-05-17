# Corporate events, earnings, filings, dividends, M&A

Spoke fetched on demand from the Bloomberg Excel hub. Covers the corporate-calendar surface: earnings (calendar + actuals + estimates), SEC filings, dividends, corporate actions (splits / spinoffs / IPOs / buybacks), and M&A status. Works for every yellow key but most fields are equity-specific.

For openpyxl mechanics, BQL grammar, and override flags, see the hub (`bloomberg_excel.md`). For equity-side fundamentals (income statement, balance sheet, ratios), see `bbg_equities.md`.

---

## 1. Earnings calendar — when does the company report

### 1.1 The single-cell next-earnings fields (`BDP`)

| Field | Returns | Notes |
|---|---|---|
| `EARN_ANN_DT_NEXT` | Next earnings announcement date | `BDP` |
| `EARN_ANN_TIME_NEXT` | Next earnings announcement time | `BDP` |
| `ANR_EARNINGS_DATE_TIME` | Datetime of next earnings | `BDP` |
| `ANNOUNCEMENT_DT` | Date of last announcement | `BDP` |
| `LATEST_ANNOUNCEMENT_DT` | Latest announcement date (any event type) | `BDP` |
| `ERN_ANN_TIME_OF_DAY` | "BMO" (before market open) / "AMC" (after market close) / "DMT" (during market trading) | `BDP` |
| `IS_NEXT_EARNINGS_DATE_ESTIMATED` | Y if Bloomberg-estimated, N if confirmed | `BDP` |
| `EARN_PERIOD_NEXT_RPT_DT` | Fiscal period covered by next report (e.g. "2024 Q4") | `BDP` |

```python
ws["A1"] = "Ticker"
ws["B1"] = "Next Earnings Date"
ws["C1"] = "Time of Day"
ws["D1"] = "Period Covered"
ws["E1"] = "Estimated?"

tickers = ["AAPL US Equity", "MSFT US Equity", "GOOGL US Equity", "META US Equity"]
for i, t in enumerate(tickers, start=2):
    ws.cell(row=i, column=1, value=t)
    ws.cell(row=i, column=2, value=f'=_xll.BDP("{t}","EARN_ANN_DT_NEXT")')
    ws.cell(row=i, column=3, value=f'=_xll.BDP("{t}","ERN_ANN_TIME_OF_DAY")')
    ws.cell(row=i, column=4, value=f'=_xll.BDP("{t}","EARN_PERIOD_NEXT_RPT_DT")')
    ws.cell(row=i, column=5, value=f'=_xll.BDP("{t}","IS_NEXT_EARNINGS_DATE_ESTIMATED")')
```

### 1.2 The full earnings-history field (`BDS`)

The single most useful BDS field for earnings work:

| Field | Returns | Columns |
|---|---|---|
| `ERN_ANN_DT_TIME_HIST_WITH_EPS` | Historical earnings dates + actual + estimate EPS | Period \| Announcement Date \| Announcement Time \| Actual EPS \| Comparable EPS \| Estimated EPS |
| `DY895` | Same surface as above (legacy alias commonly cited in field-search results) | Same |
| `ANR_EARNINGS_DATE_TIME_HIST` | Historical earnings dates only | Period \| Announcement Date \| Announcement Time |
| `ERN_ANN_DT_TIME_HIST_WITH_EPS_HIST` | Extended with prior-period and revision history | Same as base + revision flags |

```python
from openpyxl.worksheet.formula import ArrayFormula

ws["A1"] = "Period"
ws["B1"] = "Date"
ws["C1"] = "Time"
ws["D1"] = "Actual EPS"
ws["E1"] = "Comparable EPS"
ws["F1"] = "Estimated EPS"

ws["A3"] = ArrayFormula(
    "A3:F60",                                                               # ~15Y quarterly + header
    '=_xll.BDS("AAPL US Equity","ERN_ANN_DT_TIME_HIST_WITH_EPS")'
)
```

The output is one row per fiscal-quarter announcement, sorted chronologically. PRISM should size `BDS` ranges to ~60 rows for 15Y of quarterly history; smaller companies with shorter listing history return fewer rows (the trailing rows come back blank — `INDEX` on a view sheet handles that cleanly).

### 1.3 Surprise calculations (downstream in Excel)

After the BDS populates columns A:F, compute:

| Metric | Formula | Notes |
|---|---|---|
| Surprise (absolute) | `=IF(OR(D{r}="",F{r}=""),"",D{r}-F{r})` | Actual − estimated |
| Surprise (%) | `=IF(OR(D{r}="",F{r}="",F{r}=0),"",(D{r}-F{r})/ABS(F{r}))` | Per-share surprise normalised by absolute estimate |
| YoY growth | `=IF(OR(D{r}="",E{r}=""),"",(D{r}-E{r})/ABS(E{r}))` | Actual − comparable (prior year) |
| Beat / miss / inline flag | `=IF(D{r}="","",IF(D{r}>F{r}*1.02,"Beat",IF(D{r}<F{r}*0.98,"Miss","Inline")))` | 2% tolerance (adjust as desired) |

### 1.4 Earnings transcripts, audio, and slides — `EVT<GO>` family

Bloomberg captures **earnings call transcripts, audio recordings, and slide decks** for most listed companies that hold earnings calls, plus investor days, capital-markets days, M&A calls, and other corporate events. The terminal interface is `EVT<GO>` (per-security: type the ticker, then `EVT<GO>`).

**What PRISM can author into a workbook, and what's out of reach:**

| Surface | Pull via DAPI? | Notes |
|---|---|---|
| List of historical earnings calls + dates | Yes (`BDS`) | Event list with date, event type, ID |
| Content-availability flags per event (transcript Y/N, audio Y/N, slides Y/N) | Yes (`BDS`) | One column per content type |
| Document / viewer URL per event | Yes (`BDS`) | Returns a Bloomberg-hosted URL; user clicks through on the terminal to view |
| Transcript text body | **No** | The transcript text is terminal-gated. Excel-add-in callers cannot pull the transcript body as a cell value. |
| Audio recording bytes | **No** | Terminal-side streaming only. |
| Slide deck PDF body | **No** | Terminal-side viewing only; the URL field returns a viewer link. |

**Field names are install-dependent.** Bloomberg's events-tracker field family varies across enterprise installs (some carry `EVT_*` prefixes, others `EARNINGS_CALL_*`). PRISM should verify the exact mnemonic the user's install exposes by typing `FLDS<GO>` and searching `transcript` or `EVT`. Common patterns to expect:

| Pattern | Likely returns |
|---|---|
| `EVT_LIST_HIST` (`BDS`) | Historical event list — typically date \| event type \| announcement type \| document URL \| content-availability flags |
| `EVT_BBG_EVT_TYPE` | Event type classifier ("Earnings Call", "Investor Day", "M&A Call", "Conference Presentation", "Guidance Update") |
| `EVT_CONTENT_AVAILABILITY_FLAGS` | Bitmask / string indicating which of transcript / audio / slides are available |
| `EVT_DOC_URL` | Bloomberg-hosted viewer URL for the event |
| `EVT_NEXT_ANNOUNCE_DT_TIME` | Next scheduled event datetime |
| `EVT_RECENT_ANNOUNCE_DT_TIME` | Most recent event datetime |

```python
# Pattern: list every event for one issuer, with URL hyperlinks
ws["A3"] = ArrayFormula(
    "A3:E100",                                                              # date | type | content-flags | URL | description
    '=_xll.BDS("AAPL US Equity","EVT_LIST_HIST")'
)
```

**The workflow PRISM should author:**

1. `BDS` returns the event list with metadata and Bloomberg URLs.
2. PRISM's view sheet wraps each URL in `HYPERLINK(<url>,"Open transcript")` (like the SEC filings pattern in §7).
3. The user clicks through; the terminal opens the document; the user reads / copy-pastes content into their workflow.

**For programmatic transcript text access**, Bloomberg has a separate offering — the AI-Powered Document Search released in 2023 — exposed on the terminal as part of the analytics suite, not through Excel. Third-party alternatives PRISM might mention when the user explicitly needs the transcript body inside an analysis pipeline: S&P Capital IQ Transcripts, AlphaSense, FactSet StreetEvents, Refinitiv StreetEvents.

**Out-of-Excel content has the same pattern as SEC filings (§2).** PRISM ships the URL; the user does the reading. PRISM cannot consume the document content itself.

---

## 2. SEC filings (`RR_*` family — Regulatory Reports)

Bloomberg's regulatory-reports field family exposes SEC filing data (US issuers) plus parallel international regulatory filings.

### 2.1 The filing-list fields

| Field | Returns | Argument needed |
|---|---|---|
| `RR_LIST_OF_FILINGS_WITH_DATES` | All filings with type + date | None (defaults to recent) |
| `FILING_PAGE_LIST` | Same surface, terminal-style page | None |
| `RR_FILINGS_BY_DATE` | Filings within a date range | `RR_START_DT` / `RR_END_DT` overrides |
| `RR_FILING_DOC_URL` | Direct URL to a specific filing document | Returns the most recent unless restricted |
| `RR_FILING_DOCUMENT_TYPE` | Filing type code (10-K, 10-Q, 8-K, etc.) | |
| `RR_FILING_DOCUMENT_DESCRIPTION` | Filing description text | |
| `RR_LATEST_10K_DT` | Date of most recent 10-K | `BDP` |
| `RR_LATEST_10Q_DT` | Date of most recent 10-Q | `BDP` |
| `RR_LATEST_8K_DT` | Date of most recent 8-K | `BDP` |

```python
# Latest filing dates — single cells
ws["A1"] = "Filing"
ws["B1"] = "Latest Date"
filings = [
    ("Latest 10-K",     "RR_LATEST_10K_DT"),
    ("Latest 10-Q",     "RR_LATEST_10Q_DT"),
    ("Latest 8-K",      "RR_LATEST_8K_DT"),
]
for i, (label, field) in enumerate(filings, start=2):
    ws.cell(row=i, column=1, value=label)
    ws.cell(row=i, column=2, value=f'=_xll.BDP("AAPL US Equity","{field}")')
```

```python
# Full filing list (with date override)
ws["A3"] = ArrayFormula(
    "A3:E200",                                                              # date | type | description | URL | filer
    '=_xll.BDS("AAPL US Equity","RR_LIST_OF_FILINGS_WITH_DATES",'
    '"RR_START_DT=20200101","RR_END_DT=20241231")'
)
```

The columns in `RR_LIST_OF_FILINGS_WITH_DATES` (exact set varies by Bloomberg add-in version, common columns):

| Col | Content |
|---|---|
| 1 | Filing date |
| 2 | Document type (10-K / 10-Q / 8-K / DEF 14A / S-1 / 4 / etc.) |
| 3 | Description |
| 4 | Filing URL (Bloomberg-hosted or SEC-EDGAR direct link) |
| 5 | Filer / agent name (if applicable) |

### 2.2 International regulatory filings

Outside the US, the same `RR_*` family resolves to local equivalents:

| Region | Filing types covered |
|---|---|
| UK | Annual reports, half-yearly reports, FCA filings |
| EU | Annual / half-yearly / interim reports per ESMA |
| Japan | TDnet filings, Yuho (annual securities report), Hanki (semi-annual) |
| Hong Kong | HKEX disclosures |
| Canada | SEDAR filings |
| China | Shanghai / Shenzhen exchange disclosures |

The same `RR_LIST_OF_FILINGS_WITH_DATES` field works — Bloomberg federates the discovery layer across regulatory regimes. The document-type column will return local codes (e.g. "AR" for UK annual report, "Yuho" for Japanese).

### 2.3 Document URL vs full text

`RR_FILING_DOC_URL` returns a URL. Bloomberg does not surface the full filing **text** through DAPI — the user has to click through. For programmatic text-extraction work, the user wants SEC EDGAR's free API or a vendor like AlphaSense.

---

## 3. Dividend history

### 3.1 The canonical bulk-history field

| Field | Returns | Date filter |
|---|---|---|
| `DVD_HIST_ALL` | Full dividend history (ordinary + special + capital gains) | `DVD_START_DT` / `DVD_END_DT` overrides |
| `DVD_HIST` | Ordinary dividends only | Same |
| `DVD_HIST_GROSS` | Pre-tax dividends | Same |

```python
ws["A3"] = ArrayFormula(
    "A3:I40",
    '=_xll.BDS("AAPL US Equity","DVD_HIST_ALL",'
    '"DVD_START_DT=20180101","DVD_END_DT=20241231")'
)
```

Columns returned (`DVD_HIST_ALL`):

| Col | Content |
|---|---|
| 1 | Declared date |
| 2 | Ex-dividend date |
| 3 | Record date |
| 4 | Payable date |
| 5 | Dividend amount (per share, in reporting currency) |
| 6 | Dividend frequency code (`Q`, `S`, `A`, `M`, `IR` — irregular) |
| 7 | Dividend type (`Regular Cash`, `Special Cash`, `Stock`, `Spinoff`, `Liquidation`, `Capital Gain`, etc.) |
| 8 | Currency |
| 9 | Footnote / amendment text |

To filter on `Special Cash` only, the user reads back the BDS array into Excel and applies a normal `FILTER()` formula or AutoFilter — Bloomberg's add-in doesn't accept a `DVD_TYPE=Special` server-side filter.

### 3.2 Single-cell dividend fields (`BDP`)

| Field | Returns |
|---|---|
| `DVD_HIST_LAST_DPS_GROSS` | Most recent dividend per share (gross) |
| `DVD_HIST_LAST_DPS_NET` | Most recent dividend per share (net) |
| `DVD_HIST_LAST_PAY_DT` | Most recent payment date |
| `DVD_HIST_LAST_EX_DT` | Most recent ex-dividend date |
| `DVD_HIST_NEXT_DPS_GROSS` | Next announced dividend per share |
| `DVD_HIST_NEXT_EX_DT` | Next ex-dividend date |
| `DVD_HIST_NEXT_PAY_DT` | Next payment date |
| `DVD_PAYOUT_RATIO` | Trailing dividend / EPS |
| `EQY_DVD_YLD_IND` | Indicated yield (annualised) |
| `EQY_DVD_YLD_5YR_AVG` | 5Y average yield |

### 3.3 Dividend-frequency conventions

The frequency field returns single-letter codes that map to:

| Code | Frequency |
|---|---|
| `M` | Monthly |
| `Q` | Quarterly |
| `S` | Semi-annual |
| `A` | Annual |
| `B` | Biennial |
| `IR` | Irregular |
| `D` | Discontinued |
| `SP` | Special (one-off, paid alongside regular) |

PRISM should annotate the workbook with the frequency code legend so users don't have to guess.

---

## 4. Corporate actions (splits, spinoffs, IPOs, buybacks)

### 4.1 Stock splits

| Field | Returns |
|---|---|
| `EQY_SPLIT_DT_HIST` | List of historical split dates | `BDS` |
| `EQY_SPLIT_DT_NEXT` | Next announced split date | `BDP` |
| `EQY_SPLIT_RATIO` | Split ratio (e.g. 2.0 for 2-for-1, 0.5 for 1-for-2 reverse) | `BDS` history |
| `EQY_SPLIT_FACTOR_HIST` | Cumulative split factor history | `BDS` |

```python
ws["A3"] = ArrayFormula(
    "A3:C20",
    '=_xll.BDS("AAPL US Equity","EQY_SPLIT_FACTOR_HIST")'
)
```

Columns: ex-date, ratio (e.g. 4.0 means 4-for-1), notes.

### 4.2 IPOs and spinoffs

| Field | Returns |
|---|---|
| `IPO_DT` | IPO date | `BDP` |
| `IPO_PX` | IPO offering price | `BDP` |
| `IPO_AMT_OFFERED_USD` | IPO amount raised | `BDP` |
| `IPO_FIRST_TRADE_DT` | First trading date | `BDP` |
| `EQY_INIT_PO_DT` | Initial public offering date (alias) | `BDP` |
| `SPIN_OFF_DT_NEXT` | Next announced spinoff date | `BDP` |
| `SPIN_OFF_LIST_HIST` | List of historical spinoffs | `BDS` |

### 4.3 Buybacks / share repurchases

| Field | Returns |
|---|---|
| `EQY_SHARE_REPURCHASE_HIST` | Historical repurchase events | `BDS` |
| `EQY_BUYBACK_AUTH_HIST` | Buyback authorisations | `BDS` |
| `BUY_BACK_RATIO_TR12M` | Trailing 12-month buyback yield | `BDP` |
| `CFF_PURCHASE_COMMON_PREFERRED_STOCK` | Cash spent on buybacks (cash-flow line) | `BDP` with `BEST_FPERIOD_OVERRIDE` |
| `BUYBACK_PLAN_TARGET_AMT` | Authorised buyback amount | `BDP` |
| `BUYBACK_PLAN_ANNOUNCE_DT` | Date the buyback plan was announced | `BDP` |

### 4.4 Other event tickers worth knowing

| Event | Field | Notes |
|---|---|---|
| Bankruptcy filing | `BANK_PRO_DT` | Bankruptcy proceeding date if applicable |
| Delisting | `EQY_DELIST_DT` | Delisting date |
| Name change | `LAST_NAME_CHG_DT` | Historical name change |
| Index addition / deletion | `INDX_ADD_DEL_HIST` | `BDS` returning index membership changes |

---

## 5. M&A status fields

| Field | Returns |
|---|---|
| `LAST_TRADE_ANNOUNCED_DEAL_TYPE` | Type of any announced deal involving the company (e.g. "Acquirer", "Target") |
| `M_AND_A_TARGET_NAME` | Target name in announced deal |
| `M_AND_A_ACQUIRER_NAME` | Acquirer name |
| `M_AND_A_ANNOUNCE_DT` | Announcement date |
| `M_AND_A_COMPLETE_DT` | Expected / actual completion date |
| `M_AND_A_DEAL_VAL_USD` | Deal value in USD |
| `M_AND_A_DEAL_STATUS` | Pending / Completed / Withdrawn / Terminated |
| `M_AND_A_OFFER_PER_SHARE` | Offer price per share |
| `MA_HIST` | List of historical M&A events involving this company | `BDS` |

```python
ws["A1"] = '=_xll.BDP("VMW US Equity","M_AND_A_TARGET_NAME")'             # if VMW is target
ws["A2"] = '=_xll.BDP("VMW US Equity","M_AND_A_ACQUIRER_NAME")'
ws["A3"] = '=_xll.BDP("VMW US Equity","M_AND_A_DEAL_VAL_USD")'
ws["A4"] = '=_xll.BDP("VMW US Equity","M_AND_A_DEAL_STATUS")'
```

For deal-search work (e.g. "all completed M&A in Tech in 2024"), the user goes to `MA<GO>` on the terminal. Bloomberg does not expose a `BQL` deal-universe builder for Excel.

---

## 6. BQL equivalents

BQL exposes the same earnings + dividend + filing surface in function form. Field names are lowercase and parenthesised.

### 6.1 Earnings in BQL

| DAPI field | BQL function | Notes |
|---|---|---|
| `BEST_EPS` (forward consensus) | `is_eps(fa_period_offset=1, fa_act_est_data=E, est_source=BST)` | Next-period Bloomberg standard estimate |
| `IS_DILUTED_EPS` (actual) | `is_eps(fa_period_offset=0)` | LTM actual |
| `EARN_ANN_DT_NEXT` | `earnings_announcement_date()` | Next |
| `ERN_ANN_DT_TIME_HIST_WITH_EPS` | Use `bql.bql("get(is_eps(fa_period_type=Q, fa_period_offset=range(0,-12), fa_act_est_data=A)) for(['AAPL US Equity'])")` | 12 trailing quarters of actual EPS |

```excel
=_xll.BQL.Query("get(name(), is_eps(fa_period_type=Q, fa_period_offset=range(0,-12))) for(['AAPL US Equity'])")
```

`fa_period_offset=range(0,-12)` walks back through the last 12 fiscal quarters; `range(0,12)` walks forward 12 estimated quarters. Combine `A` and `E` data items in one query to get actuals vs estimates side-by-side.

### 6.2 Dividends in BQL

```
get(dvd_amount(dates=range(-5Y, 0D)), dvd_ex_dt(dates=range(-5Y, 0D)))
for(['AAPL US Equity'])
```

Returns long-form table of dividend payments over the last 5 years.

### 6.3 Filings — BQL does NOT cover them

There is no BQL `filings()` function. The `RR_*` family is DAPI-only. For multi-company filing-list pulls, the right pattern is N parallel `BDS` calls (loop over the ticker list in openpyxl, one BDS array per ticker on a dedicated `_filings_<ticker>` fetch sheet).

---

## 7. Canonical pattern — pull filings + earnings for one company

**The case study.** PRISM gets asked: "give me a workbook with Apple's last 8 earnings reports (including beat/miss vs consensus) AND all 10-Q / 10-K filings for the last 5 years, with clickable URLs to the documents."

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
wb.remove(wb["Sheet"])

TICKER = "AAPL US Equity"

ws_earn  = wb.create_sheet("Earnings")
ws_fil   = wb.create_sheet("Filings")
ws_div   = wb.create_sheet("Dividends")
ws_data  = wb.create_sheet("_data")
ws_data.sheet_state = "hidden"

# ───────── EARNINGS history (Sheet 1) ─────────
ws_data["A1"] = ArrayFormula(
    "A1:F40",                                                               # 10Y quarterly + buffer
    f'=_xll.BDS("{TICKER}","ERN_ANN_DT_TIME_HIST_WITH_EPS")'
)

# Headers on user-facing sheet
hdrs = ["Period", "Date", "Time", "Actual EPS", "Estimated EPS",
        "Surprise ($)", "Surprise (%)", "Beat/Miss", "Comparable EPS", "YoY Δ"]
for c, h in enumerate(hdrs, start=1):
    ws_earn.cell(row=1, column=c, value=h)

# Project from _data + compute downstream
for r in range(2, 30):
    src = r - 1
    ws_earn.cell(row=r, column=1, value=f'=IFERROR(INDEX(_data!A:A,{src}),"")')      # Period
    ws_earn.cell(row=r, column=2, value=f'=IFERROR(INDEX(_data!B:B,{src}),"")')      # Date
    ws_earn.cell(row=r, column=3, value=f'=IFERROR(INDEX(_data!C:C,{src}),"")')      # Time
    ws_earn.cell(row=r, column=4, value=f'=IFERROR(INDEX(_data!D:D,{src}),"")')      # Actual
    ws_earn.cell(row=r, column=5, value=f'=IFERROR(INDEX(_data!F:F,{src}),"")')      # Estimated
    ws_earn.cell(row=r, column=6, value=f'=IF(OR(D{r}="",E{r}=""),"",D{r}-E{r})')   # Surprise $
    ws_earn.cell(row=r, column=7,
                 value=f'=IF(OR(D{r}="",E{r}="",E{r}=0),"",(D{r}-E{r})/ABS(E{r}))')
    ws_earn.cell(row=r, column=8,
                 value=f'=IF(D{r}="","",IF(D{r}>E{r}*1.02,"Beat",IF(D{r}<E{r}*0.98,"Miss","Inline")))')
    ws_earn.cell(row=r, column=9, value=f'=IFERROR(INDEX(_data!E:E,{src}),"")')      # Comparable
    ws_earn.cell(row=r, column=10,
                 value=f'=IF(OR(D{r}="",I{r}="",I{r}=0),"",(D{r}-I{r})/ABS(I{r}))')

# ───────── FILINGS list (Sheet 2) ─────────
ws_data["H1"] = ArrayFormula(
    "H1:L200",
    f'=_xll.BDS("{TICKER}","RR_LIST_OF_FILINGS_WITH_DATES",'
    f'"RR_START_DT=20200101","RR_END_DT=20241231")'
)

fil_hdrs = ["Filing Date", "Type", "Description", "URL", "Filer"]
for c, h in enumerate(fil_hdrs, start=1):
    ws_fil.cell(row=1, column=c, value=h)

for r in range(2, 200):
    src = r - 1
    ws_fil.cell(row=r, column=1, value=f'=IFERROR(INDEX(_data!H:H,{src}),"")')
    ws_fil.cell(row=r, column=2, value=f'=IFERROR(INDEX(_data!I:I,{src}),"")')
    ws_fil.cell(row=r, column=3, value=f'=IFERROR(INDEX(_data!J:J,{src}),"")')
    ws_fil.cell(row=r, column=4,
                value=f'=IFERROR(HYPERLINK(INDEX(_data!K:K,{src}),"Open"),"")')
    ws_fil.cell(row=r, column=5, value=f'=IFERROR(INDEX(_data!L:L,{src}),"")')

# Filter to 10-K / 10-Q only (user adds an AutoFilter on column B after open)
ws_fil["G1"] = "Tip: click Data → AutoFilter on row 1, then filter Type to 10-K / 10-Q."

# ───────── DIVIDENDS history (Sheet 3) ─────────
ws_data["N1"] = ArrayFormula(
    "N1:V40",
    f'=_xll.BDS("{TICKER}","DVD_HIST_ALL",'
    f'"DVD_START_DT=20200101","DVD_END_DT=20241231")'
)

div_hdrs = ["Declared", "Ex-Date", "Record", "Payable", "Amount", "Frequency", "Type", "Currency", "Notes"]
for c, h in enumerate(div_hdrs, start=1):
    ws_div.cell(row=1, column=c, value=h)

for r in range(2, 40):
    src = r - 1
    for c, col_letter in enumerate("NOPQRSTUV", start=1):
        ws_div.cell(row=r, column=c, value=f'=IFERROR(INDEX(_data!{col_letter}:{col_letter},{src}),"")')

# ───────── Single-cell summary (header on Earnings sheet, row 31+) ─────────
ws_earn["A31"] = "Summary (BDPs)"
ws_earn["A32"] = "Next earnings date"
ws_earn["B32"] = f'=_xll.BDP("{TICKER}","EARN_ANN_DT_NEXT")'
ws_earn["A33"] = "Next earnings period"
ws_earn["B33"] = f'=_xll.BDP("{TICKER}","EARN_PERIOD_NEXT_RPT_DT")'
ws_earn["A34"] = "Latest 10-K date"
ws_earn["B34"] = f'=_xll.BDP("{TICKER}","RR_LATEST_10K_DT")'
ws_earn["A35"] = "Latest 10-Q date"
ws_earn["B35"] = f'=_xll.BDP("{TICKER}","RR_LATEST_10Q_DT")'
ws_earn["A36"] = "Latest 8-K date"
ws_earn["B36"] = f'=_xll.BDP("{TICKER}","RR_LATEST_8K_DT")'
ws_earn["A37"] = "Indicated dividend yield"
ws_earn["B37"] = f'=_xll.BDP("{TICKER}","EQY_DVD_YLD_IND")'
ws_earn["A38"] = "Forward EPS (1BF)"
ws_earn["B38"] = f'=_xll.BDP("{TICKER}","BEST_EPS","BEST_FPERIOD_OVERRIDE","1BF")'

wb.save("aapl_calendar.xlsx")
```

What this gives the user after they open + refresh:

- **Earnings tab:** 12 trailing quarters with actual EPS, estimated EPS, surprise (`$` and `%`), beat / miss flag, year-over-year change, plus a single-cell "next earnings + latest filings + dividend yield + forward EPS" summary at the bottom.
- **Filings tab:** all SEC filings 2020–present with clickable URL hyperlinks. The user filters to 10-K / 10-Q with Excel's AutoFilter.
- **Dividends tab:** full ordinary + special dividend history with frequency, type, amount.
- **Hidden `_data` sheet:** the source `BDS` arrays. The user never edits this sheet so the array-formula locks don't get in the way.

### 7.1 Why the `_data` + view split here matters

Three independent `ArrayFormula` blocks (earnings, filings, dividends) all live on the hidden `_data` sheet. Each is sized generously (40 / 200 / 40 rows) — that's fine because nobody edits `_data`. The user-facing tabs are pure `INDEX` projections with `IFERROR` guards, so:

- Rows beyond the populated range show empty cells, not `#N/A`.
- The user can sort, filter, paste annotations, insert summary rows — none of the "can't change part of an array" errors.
- The hidden sheet stays out of sight (`sheet_state = "hidden"`).

### 7.2 Variations

- **N companies, side-by-side earnings comparison:** loop the per-company block over a ticker list, one tab per company (or one tab with N adjacent column blocks if all on the same calendar).
- **Sector earnings calendar:** combine `INDX_MEMBERS` (hub §7.3) for the sector index with the per-company `EARN_ANN_DT_NEXT` field. The output is a sortable "who reports when" calendar.
- **Filings-only inheritance:** drop the earnings + dividend tabs; pull `RR_FILINGS_BY_DATE` against a wider date window and group by `RR_FILING_DOCUMENT_TYPE`.

---

## 8. Anti-patterns specific to event work

| Mistake | Symptom | Fix |
|---|---|---|
| Pulling `EARN_ANN_DT_NEXT` for a non-trading-status security | Returns blank | Confirm the ticker is currently listed via `MARKET_STATUS` first |
| Using `BDH` on `RR_LIST_OF_FILINGS_WITH_DATES` | Doesn't work — RR_* fields are BDS-only | Use `BDS` with `RR_START_DT` / `RR_END_DT` overrides |
| Assuming `BEST_EPS` is the actual forward EPS at the time of the historical earnings beat | `BEST_EPS` is point-in-time at the BDP call; for historical-as-of forward estimates, use BQL with `est_source` + dated request | If serious accuracy matters: PIT Estimates dataset (Bloomberg Data License product) |
| Mixing `IS_DILUTED_EPS` (actual) and `BEST_EPS` (estimate) without specifying `fa_act_est_data` | The two have different "as-of" semantics | In BQL: pass `fa_act_est_data=A` for actuals, `=E` for estimates explicitly |
| Sorting earnings tab without copy-paste-values | The `IFERROR(INDEX(...))` formulas re-evaluate against new positions | Either don't sort the projected view (it's auto-sorted by the BDS) or copy-paste-values before sorting |
| Using `DVD_HIST` and missing special dividends | `DVD_HIST` returns only ordinary; `DVD_HIST_ALL` returns ordinary + special + capital gains + stock | Always default to `DVD_HIST_ALL` unless the user explicitly wants ordinary-only |
| Pulling M&A status without filtering by status | `LAST_TRADE_ANNOUNCED_DEAL_TYPE` returns even for completed-long-ago deals | Add `M_AND_A_DEAL_STATUS` to the row, filter user-side |
| Treating `RR_FILING_DOC_URL` as opening the full text | The URL opens Bloomberg's hosted viewer or EDGAR; PRISM doesn't have text extraction | Tell the user the workbook delivers links, not document text |

---

## 9. Quick reference

```
─────────────────────────────────────────────────────────────────────
  EARNINGS — KEY FIELDS
─────────────────────────────────────────────────────────────────────
  Next datetime             EARN_ANN_DT_NEXT, ERN_ANN_TIME_OF_DAY
  Last 12Q history          BDS("<t>","ERN_ANN_DT_TIME_HIST_WITH_EPS")
                            columns: period | date | time | actual | comparable | estimated
  Forward consensus EPS     BDP(..., "BEST_EPS",
                                "BEST_FPERIOD_OVERRIDE","1BF")
  BQL equivalent            get(is_eps(fa_period_type=Q,
                                         fa_period_offset=range(0,-12)))
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  FILINGS — KEY FIELDS (RR_* family, BDS only)
─────────────────────────────────────────────────────────────────────
  Date-filtered list        BDS("<t>","RR_LIST_OF_FILINGS_WITH_DATES",
                                "RR_START_DT=20200101","RR_END_DT=20241231")
  Latest by type            RR_LATEST_10K_DT / RR_LATEST_10Q_DT /
                            RR_LATEST_8K_DT
  Document URL              RR_FILING_DOC_URL (one URL per row)
  Document type             RR_FILING_DOCUMENT_TYPE
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  EARNINGS TRANSCRIPTS — EVT FAMILY (install-dependent names)
─────────────────────────────────────────────────────────────────────
  Event list (BDS)          EVT_LIST_HIST  (verify via FLDS<GO>)
  Event type                EVT_BBG_EVT_TYPE
  Content available flags   EVT_CONTENT_AVAILABILITY_FLAGS
  Document URL              EVT_DOC_URL
  Next event datetime       EVT_NEXT_ANNOUNCE_DT_TIME
  TRANSCRIPT TEXT:          NOT exposed to Excel — terminal-gated.
                            PRISM ships the URL; user clicks through.
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  DIVIDENDS — KEY FIELDS
─────────────────────────────────────────────────────────────────────
  Full history              BDS("<t>","DVD_HIST_ALL",
                                "DVD_START_DT=...","DVD_END_DT=...")
                            columns: declared | ex | record | payable
                                     | amount | freq | type | ccy | notes
  Single-cell latest        DVD_HIST_LAST_DPS_GROSS,
                            DVD_HIST_LAST_EX_DT
  Indicated yield           EQY_DVD_YLD_IND
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  CORPORATE ACTIONS / M&A — KEY FIELDS
─────────────────────────────────────────────────────────────────────
  Stock splits              EQY_SPLIT_FACTOR_HIST (BDS)
  IPO                       IPO_DT, IPO_PX, IPO_AMT_OFFERED_USD
  Buybacks                  EQY_SHARE_REPURCHASE_HIST (BDS),
                            BUYBACK_PLAN_ANNOUNCE_DT,
                            BUYBACK_PLAN_TARGET_AMT
  M&A status                M_AND_A_DEAL_STATUS, M_AND_A_DEAL_VAL_USD,
                            M_AND_A_TARGET_NAME, M_AND_A_ACQUIRER_NAME
─────────────────────────────────────────────────────────────────────
```
