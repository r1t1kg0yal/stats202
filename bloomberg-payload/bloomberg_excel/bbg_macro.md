# Macro releases, surveys, surprises, central banks

Spoke fetched on demand from the Bloomberg Excel hub. Covers the macro-data surface: ECO release index tickers, Bloomberg's economist-survey field family, the Citi / Bloomberg surprise indices, central-bank meeting fields, OIS-implied policy paths (WIRP-style), CFTC COT positioning, and nowcasts.

For openpyxl mechanics, the BQL grammar, and override flags, see the hub (`bloomberg_excel.md`).

---

## 1. ECO release index tickers — the things you actually pull

Every economic release on the Bloomberg calendar (`ECO<GO>`) has an `<...> Index` ticker. PRISM uses the ticker to address survey + actual data via DAPI / BQL. Memorise the patterns; the catalog is enormous.

### 1.1 US headline releases

| Indicator | Ticker | Source | Released |
|---|---|---|---|
| CPI YoY | `CPI YOY Index` | BLS | Mid-month |
| Core CPI YoY | `CPI XYOY Index` | BLS | Mid-month |
| CPI MoM | `CPI CHNG Index` | BLS | Mid-month |
| Core CPI MoM | `CPI XCHG Index` | BLS | Mid-month |
| PCE Core YoY | `PCE CYOY Index` | BEA | End-month |
| PCE Headline YoY | `PCE DEFY Index` | BEA | End-month |
| Nonfarm Payrolls (Net Change) | `NFP TCH Index` | BLS | First Friday |
| NFP Private Payrolls | `NFP PCH Index` | BLS | First Friday |
| Unemployment Rate | `USURTOT Index` | BLS | First Friday |
| Average Hourly Earnings YoY | `AHE YOY% Index` | BLS | First Friday |
| Initial Jobless Claims | `INJCJC Index` | DOL | Thursday |
| Continuing Claims | `INJCSP Index` | DOL | Thursday |
| ADP Employment Change | `ADP CHNG Index` | ADP | Wednesday before NFP |
| JOLTS Job Openings | `JOLTTOTL Index` | BLS | Monthly |
| GDP QoQ Annualized (Advance / 2nd / Final) | `GDP CQOQ Index` | BEA | Last Thursday of month after quarter-end |
| Retail Sales MoM (Advance) | `RSTAMOM Index` | Census | Mid-month |
| Retail Sales ex-Auto MoM | `RSTAXAG% Index` | Census | Mid-month |
| ISM Manufacturing PMI | `NAPMPMI Index` | ISM | First business day |
| ISM Services PMI | `NAPMNMI Index` | ISM | Third business day |
| ISM Manufacturing Prices Paid | `NAPMPRIC Index` | ISM | First business day |
| Existing Home Sales (SAAR) | `ETSLTOTL Index` | NAR | Mid-month |
| New Home Sales (SAAR) | `NHSLTOT Index` | Census | End-month |
| Building Permits | `NHSPATOT Index` | Census | Mid-month |
| Industrial Production MoM | `IP YOY Index` (YoY) / `IP CHNG Index` (MoM) | Fed | Mid-month |
| Capacity Utilization | `CPTICHNG Index` | Fed | Mid-month |
| Durable Goods Orders MoM | `DGNOCHNG Index` | Census | End-month |
| Trade Balance | `USTBTOT Index` | BEA / Census | First week |
| Univ. of Michigan Sentiment (Final) | `CONSSENT Index` | UMich | End-month |
| Conference Board Consumer Confidence | `CONCCONF Index` | Conf. Board | End-month |
| PPI MoM | `PPI CHNG Index` | BLS | Mid-month |
| Empire Manufacturing | `EMPRGBCI Index` | NY Fed | Mid-month |
| Philadelphia Fed Manufacturing | `OUTFGAF Index` | Philly Fed | 3rd Thursday |
| Chicago PMI | `CHPMINDX Index` | ISM-Chicago | Last business day |

### 1.2 Major non-US releases

| Region | Indicator | Ticker |
|---|---|---|
| Eurozone | CPI YoY (Flash) | `ECCPEMUY Index` |
| Eurozone | Core CPI YoY | `CPEXEMUY Index` |
| Eurozone | GDP QoQ | `EUGNEMUQ Index` |
| Eurozone | Unemployment Rate | `UMRTEMU Index` |
| Eurozone | Manufacturing PMI (Final) | `MPMIEZMA Index` |
| Eurozone | Services PMI (Final) | `MPMIEZSA Index` |
| Eurozone | Composite PMI | `MPMIEZCA Index` |
| Germany | IFO Business Climate | `GRIFPBUS Index` |
| Germany | ZEW Survey Expectations | `GRZEWI Index` |
| Germany | CPI YoY | `GRCP20YY Index` |
| UK | CPI YoY | `UKRPCJYR Index` |
| UK | GDP QoQ | `UKGRABIQ Index` |
| Japan | CPI YoY (Nationwide ex-Fresh Food) | `JNCPIXFY Index` |
| Japan | GDP QoQ Annualized | `JGDPNSAQ Index` |
| Japan | Tankan Large Mfg DI | `JNTSMFG Index` |
| China | CPI YoY | `CNCPIYOY Index` |
| China | GDP YoY | `CHGDPY% Index` |
| China | Manufacturing PMI (NBS official) | `CPMINDX Index` |
| China | Manufacturing PMI (Caixin) | `EHPMICN Index` |

### 1.3 Anatomy of a release ticker

Some patterns to recognise (saves field-search lookups):

- `<region>CPI<...> Index` — CPI variants by region (suffix `YY` / `MM` / `XX` / `Q` for transform)
- `<region>GDP<...> Index` — GDP variants by region
- `<region>PMI<...> Index` — PMI variants
- `MPMI<region><MA|SA|CA> Index` — Markit/S&P Global PMIs (Mfg / Services / Composite)
- Suffix `% Index` on a magnitude indicator = percent change (`RSTAMOM Index` = retail sales MoM %)
- Two-letter country prefix (`UK`, `GR`, `FR`, `IT`, `ES`, `JN`, `CN`, `IN`, `BZ`, `MX`) for non-US country-level releases

When in doubt, the user runs `ECO<GO>`, navigates to the release, and reads the bottom-left ticker — that's what PRISM should consume.

---

## 2. Survey + actual fields — the meat

The Bloomberg ECO calendar carries **two parallel time series** per release:

1. The **economist survey** (BN Survey) — collected from ~80 sell-side / buy-side economists ahead of each release. Bloomberg publishes the median, mean, high, low, count, and standard deviation.
2. The **actual release** — what came out.

The surprise is `ACTUAL_RELEASE - BN_SURVEY_MEDIAN` (typical convention; some users normalise by `FORECAST_STANDARD_DEVIATION` to get a z-score).

### 2.1 Field catalog

| Field | Returns | Used with |
|---|---|---|
| `ACTUAL_RELEASE` | Released value of the indicator | `BDP` (latest) / `BDH` (history) on the release index ticker |
| `BN_SURVEY_MEDIAN` | Median economist forecast | Same |
| `BN_SURVEY_AVERAGE` | Mean economist forecast | Same |
| `BN_SURVEY_HIGH` | Highest forecast | Same |
| `BN_SURVEY_LOW` | Lowest forecast | Same |
| `BN_SURVEY_NUMBER_OBSERVATIONS` | Count of economists in the survey | Same |
| `FORECAST_STANDARD_DEVIATION` | Cross-sectional stdev of forecasts | Same |
| `ECO_RELEASE_DT` | Date of the next scheduled release | `BDP` |
| `ECO_RELEASE_TIME` | Time of the next scheduled release (typically `08:30:00`) | `BDP` |
| `ECO_FUTURE_RELEASE_DATE_LIST` | List of all upcoming scheduled release dates for this indicator | `BDS` |
| `ECO_RELEASE_DT_LIST` | List of historical release dates | `BDS` |
| `ECO_RELEASE_PERIOD` | The period covered (e.g. "Aug" for the Aug release of NFP) | `BDP` |
| `ECO_REL_FREQ` | Release frequency (M, Q, W, etc.) | `BDP` |
| `ECO_FORECASTERS_NAMES` | Names of contributing forecasters | `BDS` (rarely used) |
| `ECO_REVISION_FLAG` | Whether the latest release is a revision | `BDP` |

### 2.2 Pulling the latest release vs. the history

**Latest release only:**

```python
ws["A1"] = '=_xll.BDP("CPI YOY Index","ACTUAL_RELEASE")'
ws["A2"] = '=_xll.BDP("CPI YOY Index","BN_SURVEY_MEDIAN")'
ws["A3"] = '=_xll.BDP("CPI YOY Index","ECO_RELEASE_DT")'                  # next release date
ws["A4"] = '=_xll.BDP("CPI YOY Index","ECO_RELEASE_PERIOD")'              # "Aug" etc.
```

**Full history of actuals — use `BDH` (the indicator IS a time series):**

```python
ws["A3"] = ArrayFormula(
    "A3:B255",                                                              # ~10Y monthly + header
    '=_xll.BDH("CPI YOY Index","PX_LAST","-10Y","0D","Per=cm","Fill=N","Dts=S","Dir=V")'
)
```

For a release index, `PX_LAST` and `ACTUAL_RELEASE` return the same series — `PX_LAST` is the survivor-form, `ACTUAL_RELEASE` is the explicit name.

### 2.3 Full history of actuals + surveys (the case-study pattern below) requires BDH on survey fields too

```python
fields = "ACTUAL_RELEASE,BN_SURVEY_MEDIAN,BN_SURVEY_HIGH,BN_SURVEY_LOW,FORECAST_STANDARD_DEVIATION"
ws["A3"] = ArrayFormula(
    f"A3:F255",
    f'=_xll.BDH("CPI YOY Index","{fields}","-10Y","0D","Per=cm","Fill=N","Dts=S","Dir=V")'
)
```

This is the spine of every "surprise vs expectations" workbook.

---

## 3. Surprise indices

Citi's Economic Surprise Index family (`CESI*`) is a widely-watched composite: weighted standard-deviations of release-vs-survey surprises with a rolling 3-month decay window. Positive = data beating consensus on average; negative = missing.

### 3.1 Citi CESI tickers

| Ticker | Region |
|---|---|
| `CESIUSD Index` | United States |
| `CESIEUR Index` | Eurozone |
| `CESIGBP Index` | UK |
| `CESIJPY Index` | Japan |
| `CESICNY Index` | China |
| `CESICAD Index` | Canada |
| `CESIAUD Index` | Australia |
| `CESINZD Index` | New Zealand |
| `CESINOK Index` | Norway |
| `CESISEK Index` | Sweden |
| `CESICHF Index` | Switzerland |
| `CESIEM Index` | Emerging Markets composite |
| `CESILATAM Index` | Latin America composite |
| `CESIGL Index` (or `CESIWO Index` on some installs) | Global composite |

These behave like ordinary index tickers — pull with `PX_LAST` (current level) or `BDH` for history.

```python
ws["A3"] = ArrayFormula(
    "A3:B1827",                                                             # 5Y calendar-day
    '=_xll.BDH("CESIUSD Index","PX_LAST","-5Y","0D","Per=cd","Fill=P","Dts=S","Dir=V")'
)
```

### 3.2 Bloomberg's own surprise indices

Bloomberg publishes its own version under the `BES*` family (less commonly used externally but referenced internally on the terminal):

| Ticker | Region |
|---|---|
| `BESUSI Index` | US |
| `BESEUI Index` | Eurozone |
| `BESJPI Index` | Japan |
| `BESCHI Index` | China |

Default to Citi (CESI*) for cross-team reproducibility unless the user explicitly asks for Bloomberg's.

---

## 4. Central bank meeting fields

### 4.1 Policy rate tickers (the levels themselves)

| CB | Ticker | Field for the rate |
|---|---|---|
| Fed Funds Target Upper Bound | `FDTR Index` | `PX_LAST` |
| Fed Funds Effective Rate | `FEDL01 Index` | `PX_LAST` |
| SOFR (Secured Overnight Financing Rate) | `SOFRRATE Index` | `PX_LAST` |
| ECB Deposit Facility Rate | `EURR002W Index` (Main Refi) / `EUDR Index` (Depo) | `PX_LAST` |
| BoE Bank Rate | `UKBRBASE Index` | `PX_LAST` |
| BoJ Policy Rate | `BOJDPBAL Index` | `PX_LAST` |
| RBA Cash Rate Target | `RBATCTR Index` | `PX_LAST` |
| BoC Overnight Rate | `CABROVER Index` | `PX_LAST` |
| SNB Policy Rate | `SZRTSL Index` | `PX_LAST` |
| PBoC LPR 1Y | `CHLR12M Index` | `PX_LAST` |
| PBoC LPR 5Y | `CHLR5YR Index` | `PX_LAST` |
| Banxico Overnight Rate | `MXONBR Index` | `PX_LAST` |
| BCB Selic Target | `BZSTSETA Index` | `PX_LAST` |

### 4.2 Meeting calendars (when does the FOMC / ECB / etc. next meet)

| Field | What | Used with |
|---|---|---|
| `MEETING_DATE` | Next scheduled meeting date for the relevant CB | `BDP` |
| `CENTRAL_BANK_MEETING_DATES` | List of meeting dates (forward + recent) | `BDS` |
| `INTEREST_RATE_DECISION` | The decision (rate change in bp) at a given meeting | `BDH` over time |

```python
ws["B1"] = '=_xll.BDP("FDTR Index","MEETING_DATE")'                       # next FOMC
ws["A1"] = ArrayFormula(
    "A1:B30",
    '=_xll.BDS("FDTR Index","CENTRAL_BANK_MEETING_DATES")'
)
```

### 4.3 WIRP / implied-policy-rate paths

`WIRP<GO>` is the Bloomberg terminal page that consolidates Fed Funds futures and OIS pricing into an implied path of policy rate changes. The underlying data is the **price of OIS swaps** at successive meeting dates and Fed Funds futures.

For Excel work, the canonical path is:

1. Pull OIS-implied rate at each upcoming meeting date (`FEDS<MeetingDateCode> Index` family) — Bloomberg publishes one ticker per scheduled FOMC date with the OIS-implied rate.
2. Compute the cumulative implied change vs. current `FDTR Index` level.

Generic forms that resolve to OIS-implied yields at future Fed meetings (you'll see them as inputs to WIRP):

| Pattern | Meaning |
|---|---|
| `FEDS<MMM><YY> Index` | OIS-implied effective rate after the FOMC meeting in the named month (e.g. `FEDSDEC25 Index`) — exact ticker shape varies by install version; verify with `FEDS<GO>` |
| `<currency>SO<tenor> Curncy` | OIS swap rate at a given tenor (`USSO1 Curncy` = 1Y USD OIS, `USSO2 Curncy` = 2Y) |
| `FF1 Comdty`, `FF2 Comdty` | Fed Funds futures front / second contract (the legacy CME-derived path) |

CME's FedWatch Tool uses Fed Funds futures (`FF*`); WIRP and most professional desks use OIS. Both are valid; pick by what the user asks for.

Field for fed-funds-futures implied probabilities (less commonly used in Excel):

```python
ws["A1"] = '=_xll.BDP("FF1 Comdty","FUT_PRICE_PER_FED_FUNDS_RATE")'
```

---

## 5. CFTC Commitments of Traders (COT)

Weekly positioning data from CFTC, aggregated by Bloomberg into per-future-contract fields. Most COT fields live on commodity / futures tickers — see `bbg_commodities.md` for the futures-specific catalog. For broad-market macro signals, use the futures aggregates:

| Field | Returns |
|---|---|
| `COT_NON_COMMERCIAL_LONG` | Speculator long contracts |
| `COT_NON_COMMERCIAL_SHORT` | Speculator short contracts |
| `COT_NON_COMMERCIAL_NET` | Net speculator position |
| `COT_COMMERCIAL_LONG` / `COT_COMMERCIAL_SHORT` / `COT_COMMERCIAL_NET` | Hedger positions |
| `COT_OPEN_INTEREST` | Total open interest |
| `COT_NUM_TRADERS_LARGE` | Number of large traders |
| `COT_PCT_OPEN_INTEREST_NC_LONG` | Speculator longs as % of OI |

Common macro-relevant futures + their tickers:

| Future | Ticker | Macro signal |
|---|---|---|
| S&P 500 E-Mini | `ES1 Index` | Equity positioning |
| US 10Y Treasury | `TY1 Comdty` | Rates positioning |
| US 2Y Treasury | `TU1 Comdty` | Front-end rates |
| US Ultra Bond | `UB1 Comdty` | Long-duration positioning |
| Euro FX | `EC1 Curncy` | EUR positioning |
| Japanese Yen | `JY1 Curncy` | JPY positioning |
| Gold | `GC1 Comdty` | Inflation hedge / risk-off |
| Crude Oil | `CL1 Comdty` | Energy / growth |
| Copper | `HG1 Comdty` | Industrial activity |
| Soybeans | `S 1 Comdty` (note the space) | Agri |

```python
ws["A3"] = ArrayFormula(
    "A3:E261",                                                              # 5Y weekly
    '=_xll.BDH("TY1 Comdty",'
    '"COT_NON_COMMERCIAL_LONG,COT_NON_COMMERCIAL_SHORT,COT_NON_COMMERCIAL_NET,COT_OPEN_INTEREST",'
    '"-5Y","0D","Per=cw","Fill=N","Dts=S","Dir=V")'
)
```

---

## 6. Nowcasts and high-frequency growth proxies

| Index | Ticker | What |
|---|---|---|
| Atlanta Fed GDPNow | `BNECNGUS Index` (Bloomberg-published proxy) or terminal page `GDPN<GO>` | Real-time US GDP estimate |
| NY Fed Nowcast | `NYFNWUS Index` | Real-time US GDP estimate |
| Bloomberg Economic Surprise Indices | `BES*` family (see §3.2) | Surprise composites |
| ADS Business Conditions Index (Philly Fed) | `ADSPHIL Index` | Daily business conditions composite |
| Chicago Fed National Activity Index | `CFNAI Index` | Monthly composite |
| Goldman Sachs Financial Conditions | `GSUSFCI Index` | Cross-asset financial conditions |
| Bloomberg US Financial Conditions | `BFCIUS Index` | Bloomberg-published financial conditions |
| Bloomberg Eurozone Financial Conditions | `BFCIEU Index` | Same for EUR |

Pull as ordinary indices via `BDH("BNECNGUS Index","PX_LAST", ...)`.

---

## 7. Canonical pattern — macro release surprise vs expectations history

**The case study.** PRISM gets asked: "pull full history of CPI surprise vs Bloomberg consensus, monthly, back 10Y, including the spread between high and low forecasts." This pattern generalises to any ECO indicator.

### 7.1 The minimal BDH workbook

```python
from openpyxl import Workbook
from openpyxl.worksheet.formula import ArrayFormula

wb = Workbook()
ws = wb.active
ws.title = "CPI_Surprise"

INDICATOR = "CPI YOY Index"                                                 # swap for any ECO ticker
WINDOW    = "-10Y"
N_ROWS    = 121                                                             # 10Y monthly + header

ws["A1"] = f"{INDICATOR} — actual, survey, surprise (10Y monthly)"

fields = ",".join([
    "ACTUAL_RELEASE",
    "BN_SURVEY_MEDIAN",
    "BN_SURVEY_HIGH",
    "BN_SURVEY_LOW",
    "FORECAST_STANDARD_DEVIATION",
])

ws["A3"] = ArrayFormula(
    f"A3:F{2 + N_ROWS}",                                                    # date + 5 fields = 6 cols
    f'=_xll.BDH("{INDICATOR}","{fields}","{WINDOW}","0D",'
    f'"Per=cm","Fill=N","Dts=S","Dir=V")'
)

ws["H1"] = "Computed columns (computed in Excel — refresh after BDH populates):"
ws["H3"] = "Date";       ws["I3"] = "Surprise (act-med)";  ws["J3"] = "Z-score"
for r in range(4, 4 + N_ROWS):
    ws.cell(row=r, column=8, value=f"=A{r}")
    ws.cell(row=r, column=9, value=f'=IF(OR(B{r}="",C{r}=""),"",B{r}-C{r})')
    ws.cell(row=r, column=10, value=f'=IF(OR(I{r}="",F{r}="",F{r}=0),"",I{r}/F{r})')

wb.save("cpi_surprise.xlsx")
```

After the user opens the workbook and the Bloomberg add-in refreshes:

- Columns `A:F` carry the BDH output (date + 5 fields). Each row is one release period.
- Columns `H:J` are downstream Excel arithmetic: the surprise is `actual - median`; the z-score normalises by the cross-economist standard deviation.

### 7.2 The richer BQL alternative (server-side computation, multiple indicators)

When the user wants the surprise across many indicators at once (e.g. "give me the surprise on CPI, Core CPI, NFP, and ISM Manufacturing for the last 5Y"), BQL is the right tool. One server call returns a long table.

```python
INDICATORS = [
    "CPI YOY Index",
    "CPI XYOY Index",
    "NFP TCH Index",
    "NAPMPMI Index",
]

bql = (
    "let("
    "#act=actual_release(dates=range(-5Y, 0D), fill=PREV);"
    "#med=bn_survey_median(dates=range(-5Y, 0D), fill=PREV);"
    "#stdev=forecast_standard_deviation(dates=range(-5Y, 0D), fill=PREV);"
    "#surp=#act - #med;"
    "#z=#surp / #stdev;"
    ")"
    "get(name(), #act, #med, #surp, #z) "
    f"for([{','.join(repr(t).replace(chr(39), chr(34)) for t in INDICATORS)}])"
)

ws["A1"] = ArrayFormula(
    "A1:F2500",                                                             # generously, on a _query sheet
    f'=_xll.BQL.Query("{bql}")'
)
```

Apply the dedicated-fetch-sheet pattern (hub §7.4) so the user can view / sort / annotate without hitting the array-lock error.

### 7.3 Field-availability and history caveats

- **Survey history starts when Bloomberg began collecting the survey.** For most US headline series, that's ~1997 onwards. For exotic / smaller-economy series, it may be much shorter or non-existent.
- **`BN_SURVEY_MEDIAN` returns the snapshot at release time**, not the survey as it stood 2 weeks before. If the user wants "intraday revision of forecasts before the release", that's the Point-in-Time (PIT) Releases & Surveys dataset (a separate Bloomberg Data License product) — not addressable through ECO Index DAPI fields.
- **`FORECAST_STANDARD_DEVIATION` can be `#N/A` for thinly-surveyed releases**. Always guard the z-score column with `IF(OR(I{r}="",F{r}="",F{r}=0),"",...)`.
- **Revisions:** the released value can be revised in subsequent months (e.g. NFP is routinely revised by ±50K). `ACTUAL_RELEASE` returns the most recent point-in-time value, NOT the original print. For original-print historical backtesting, the PIT dataset is the right product.

---

## 8. BQL macro deep dives

### 8.1 Field names in BQL

BQL exposes the same survey fields as DAPI, in lowercase function form:

| DAPI field | BQL function |
|---|---|
| `ACTUAL_RELEASE` | `actual_release(dates=...)` |
| `BN_SURVEY_MEDIAN` | `bn_survey_median(dates=...)` |
| `BN_SURVEY_HIGH` / `BN_SURVEY_LOW` | `bn_survey_high(dates=...)` / `bn_survey_low(dates=...)` |
| `FORECAST_STANDARD_DEVIATION` | `forecast_standard_deviation(dates=...)` |
| `ECO_RELEASE_DT` | `eco_release_dt()` |
| `ECO_FUTURE_RELEASE_DATE_LIST` | `eco_future_release_date_list()` |

The single-data-point form (e.g. "latest released CPI YoY"):

```
get(actual_release) for(['CPI YOY Index'])
```

### 8.2 Group + aggregate (cross-indicator surprise composite)

```
let(
  #surp = (actual_release(dates=range(-5Y, 0D), fill=PREV) - bn_survey_median(dates=range(-5Y, 0D), fill=PREV))
        / forecast_standard_deviation(dates=range(-5Y, 0D), fill=PREV);
  #avg_surp = avg(group(#surp, name()));
)
get(#avg_surp)
for(['CPI YOY Index', 'NFP TCH Index', 'NAPMPMI Index', 'USURTOT Index'])
with(fill=PREV)
```

This returns the per-indicator average surprise over the last 5Y — a simple cross-section of who has been beating / missing more.

### 8.3 Filtering ECO indicators by upcoming-release window

```
filter(
  ['CPI YOY Index', 'NFP TCH Index', 'GDP CQOQ Index', 'RSTAMOM Index'],
  eco_release_dt() <= 7D
)
```

Returns just the indicators with a release scheduled in the next 7 days. Useful for "what's on the calendar this week" widgets.

---

## 9. Anti-patterns specific to macro work

| Mistake | Symptom | Fix |
|---|---|---|
| Using `BDP("CPI YOY Index","PX_LAST")` and expecting the survey median | Returns actual, not survey | Use `BDP(...,"BN_SURVEY_MEDIAN")` explicitly |
| Pulling actuals at daily frequency | Returns NaN forward-filled to whatever release date the periodicity straddles | Match the periodicity to the release cadence: `Per=cm` for monthly releases, `Per=cw` for weekly (initial claims) |
| Subtracting actual from survey without revision-awareness | Backtest leak: original-print data is what economists were surprised by, not the revised series | Disclose to the user that revisions make backtests imperfect; PIT dataset is the right product for serious work |
| Pulling `ACTUAL_RELEASE` over `-10Y` and assuming the entire history is present | Some indicators (e.g. ISM Services pre-2008 was "non-manufacturing") have data discontinuities | When the BDH returns sparse data, check the index ticker description (`BDP(..., "SECURITY_DES")`) for whether the series was re-classified |
| Cross-indicator z-score composite without weighting | All indicators count equally — JOLTS gets the same weight as NFP | If the user wants Citi-style weighting, point to `CESIUSD Index` as the canonical composite (Citi handles the weighting) |
| Treating Fed Funds futures (`FF1 Comdty`) and OIS-implied (`USSO*`) as equivalent | They diverge during market stress (basis blows out) | Use OIS (USSO) for clean policy expectations; FF futures for the CME-derived "FedWatch" framing the user may be reading in financial press |

---

## 10. Quick reference

```
─────────────────────────────────────────────────────────────────────
  ECO RELEASE INDEX → SURVEY + ACTUAL FIELDS
─────────────────────────────────────────────────────────────────────
  Pattern:          BDH("<release> Index","ACTUAL_RELEASE,BN_SURVEY_MEDIAN,...",-NY,0D,"Per=cm")
  Surprise:         ACTUAL_RELEASE - BN_SURVEY_MEDIAN
  Z-score:          (ACTUAL_RELEASE - BN_SURVEY_MEDIAN) / FORECAST_STANDARD_DEVIATION
  Next release dt:  BDP("<release> Index","ECO_RELEASE_DT")
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  COMPOSITE SURPRISE INDICES (Citi)
─────────────────────────────────────────────────────────────────────
  US:               CESIUSD Index
  Eurozone:         CESIEUR Index
  UK:               CESIGBP Index
  Japan:            CESIJPY Index
  China:            CESICNY Index
  Emerging Mkts:    CESIEM Index
  Global:           CESIGL Index
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  CENTRAL BANK POLICY RATES
─────────────────────────────────────────────────────────────────────
  Fed Funds Target (upper)    FDTR Index
  Fed Effective                FEDL01 Index
  SOFR                         SOFRRATE Index
  ECB Main Refi                EURR002W Index
  ECB Deposit                  EUDR Index
  BoE Bank Rate                UKBRBASE Index
  BoJ Policy                   BOJDPBAL Index
  RBA Cash Rate                RBATCTR Index
  BoC Overnight                CABROVER Index
─────────────────────────────────────────────────────────────────────
```

```
─────────────────────────────────────────────────────────────────────
  OIS / FED FUNDS FUTURES — IMPLIED POLICY PATH
─────────────────────────────────────────────────────────────────────
  USD OIS curve points:        USSO1 Curncy  ... USSO5 Curncy
  Fed Funds futures front:     FF1 Comdty, FF2 Comdty, ...
  Implied at next FOMC:        Compute from OIS forward or use FEDS<MMM><YY> Index
                               (varies by install — verify with FEDS<GO>)
─────────────────────────────────────────────────────────────────────
```
