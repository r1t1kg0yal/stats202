# Macro Stock-Flow Ratio Ontology

_as of 2026-05-10; sources: NIPA + Z.1 + DFA + H.8 + BIS (DSR + LBS + Credit-to-GDP) + FRED + IMF WEO/Fiscal Monitor + WID + UN + OECD + Godley-Lavoie 2007; v1 + v2 build covering ~190 top-level ratios across 20 themes_

A deduplicated catalog of analytically-loaded ratios built from the
master vocabulary of stocks and flows. Where the master vocabulary
answers "what are the things?", this file answers "what are the
**ratios** of those things — the lenses through which macro analysts
actually read the data?".

## What this is

~190 highest-priority macro stock-flow ratios for cross-asset / rates
/ macro analysis. Selection mixes desk-tracked metrics (P/E, credit
spreads, unemployment, debt/GDP) with structural fundamentals
(sectoral balances, top-1% wealth share, NIIP/GDP, Piketty β,
demographics, growth accounting). Each entry is tagged with its
**type** in the 2x2 of stock/flow combinations and its **sector**.

The build proceeds in tranches that first exhaust the **highest-level**
SFC / NIPA / national-accounting / global-macro surface before going
into market microstructure, sector granularity, or distributional
demographic cuts. The first 10 themes (v1, ~100 ratios) cover the
expenditure-side and desk-tracked surface; the second 10 (v2, ~91
ratios) cover the income side, wealth-to-income ratios, money + credit
aggregates, financial deepening, government finance composition,
global aggregates, demographics, growth accounting, SFC closure, and
within-sector composition.

## What this is not

A complete enumeration. Build pipeline: v1 + v2 = top ~190 highest-
level macro ratios, then v3+ progressively adds market microstructure
+ sector granularity + finer distributional cuts. The
`master_vocabulary.md` (sibling file in this folder, planned) is the
underlying inventory of stocks and flows that every ratio composes
from.

## The 2x2 of ratio types

```
                         DENOMINATOR
              ┌─────────────────────┬─────────────────────┐
              │       STOCK         │        FLOW         │
              ├─────────────────────┼─────────────────────┤
    STOCK     │  STOCK / STOCK      │  STOCK / FLOW       │
              │  ─────────────────  │  ─────────────────  │
              │  equity / assets    │  debt-to-GDP        │
N             │  CET1 / RWA         │  wealth-to-income   │
U             │  liquid / total     │  reserves / imports │
M   ──────────┼─────────────────────┼─────────────────────┤
E    FLOW     │  FLOW / STOCK       │  FLOW / FLOW        │
R             │  ─────────────────  │  ─────────────────  │
A             │  GROWTH RATES       │  saving rate S/Y    │
T             │  ROE, ROA, NIM      │  labor share        │
O             │  charge-offs/loans  │  exports / GDP      │
R             │  D&A / cap stock    │  ICR (EBIT / INT)   │
              └─────────────────────┴─────────────────────┘
```

Growth rates are FLOW/STOCK because Δstock IS the period's flow:
`(X_t − X_{t-1}) / X_{t-1}` is a flow (Δstock) over a stock. When the
underlying X is itself a flow (e.g. real GDP yoy), the growth rate is
a FLOW/FLOW. Both cases are tagged `growth` below for clarity, with
the underlying type noted in body where it matters.

## Per-entry shape

```
### <name>
**`<formula>`** · <type> · <sector> · <units>

<2-3 sentences: what the ratio tells you, key context, variants if useful.>
```

| Tag class | Allowed values |
|---|---|
| `<type>` | stock/stock · stock/flow · flow/flow · flow/stock · growth |
| `<sector>` | aggregate · households · nfc · banks · government · external · market |
| `<units>` | percent · ratio · multiple · index · bps · level |

## Themes

```
EXPENDITURE-SIDE + DESK-TRACKED  (v1 batch)
 1. Aggregate output composition  ........  10 ratios
 2. Sectoral balances  ....................   7 ratios
 3. Leverage  .............................  12 ratios
 4. Valuation  ............................  10 ratios
 5. Distribution / inequality  ............  10 ratios
 6. Growth rates  .........................  10 ratios
 7. Returns  ..............................   7 ratios
 8. Real-side / labor  ....................  12 ratios
 9. Monetary / banking  ...................  12 ratios
10. External  .............................  10 ratios

INCOME-SIDE + STRUCTURAL  (v2 batch)
11. NIPA income approach  .................  13 ratios
12. Wealth-to-income (Piketty universe)  ..  10 ratios
13. Money + credit aggregates / GDP  ......   8 ratios
14. Financial market deepening  ...........  10 ratios
15. Government finance composition  .......   7 ratios
16. Global macro / world aggregates  ......  10 ratios
17. Demographics  .........................   7 ratios
18. Growth accounting  ....................  10 ratios
19. SFC closure variables (G&L direct)  ...   8 ratios
20. Sectoral balance sheet composition  ...   8 ratios
                                          ─────────────
                                          191 ratios
```

---

## 1. Aggregate output composition

The major spending and saving fractions of GDP. Anchors of
sectoral-balance and growth-accounting analysis. All flow/flow —
period flow numerator, period flow denominator (typically GDP, or
disposable income for the personal saving rate).

### Investment rate (gross)
**`I / Y`** · flow/flow · aggregate · percent

Gross private domestic investment as a share of GDP. US runs ~17–20%
in steady state; structural drift down from ~25% peaks in the 1970s
reflects the services-shift and rising IP/intangible share.
Pro-cyclical — falls 5–8 ppts in recessions. NIPA Table 1.1.5.

### Gross national saving rate
**`S_gross / Y`** · flow/flow · aggregate · percent

National saving (HH + NFC + govt + foreign-attributed) as a share of
GDP. By the sectoral-balance identity, equals gross investment ±
foreign borrowing/lending. US gross saving ~17–19%; the (S − I) gap
is the current-account deficit. Compare to net national saving (after
depreciation) which is currently ~3% — historically low.

### Personal saving rate
**`(DPI − Outlays) / DPI`** · flow/flow · households · percent

Households saving rate out of disposable personal income. Volatile —
spiked to ~33% during 2020 transfers, dropped near zero post-recovery.
"Excess saving" depletion vs. pre-pandemic trend is a workhorse
narrative for reading consumer demand. NIPA Table 2.1.

### Personal consumption share
**`PCE / Y`** · flow/flow · aggregate · percent

PCE share of GDP. US runs ~68%; secular drift up from ~62% in the
1960s. Goods/services split (~30/70) and durables share are the
deeper cuts. This ratio is the asymmetric sister to the saving rate.

### Government spending share
**`G / Y`** · flow/flow · government · percent

Federal + state + local consumption + gross investment, as a share of
GDP. US runs ~17–18% (federal ~7%, S&L ~11%). Note: this is the NIPA
G — a flow that enters GDP — distinct from total federal **outlays**
(~24% of GDP) which include transfers (transfers are not in GDP).

### Federal revenue share
**`T_federal / Y`** · flow/flow · government · percent

Federal current receipts as a share of GDP. US runs ~17–18% in
expansion, 14–15% in recession. The cyclical sensitivity is itself a
key fiscal-impulse signal. Variants: total tax revenue (incl. state &
local) ~30%; primary balance = revenue minus non-interest outlays.

### Net exports share
**`(X − M) / Y`** · flow/flow · external · percent

Net exports as a share of GDP. US runs −3% to −5% (persistent
deficit). The mirror of the foreign-sector financial balance — a
negative NX/GDP means foreigners are net sellers of goods to the US
in exchange for US financial claims (the savings glut perspective).

### Imports share
**`M / Y`** · flow/flow · external · percent

Import propensity. US runs ~15%. Compare to small open economies
where M/Y can exceed 50%. Cyclically pro-domestic-demand: rises with
US growth, falls with USD strength + offshore demand. The marginal
propensity to import (ΔM/ΔY) is the cyclical-leakage parameter in
Keynesian multiplier accounting.

### Exports share
**`X / Y`** · flow/flow · external · percent

US runs ~10–11% (low for a G7). Tracks REER inversely with a 6–18
month lag. Goods/services split is ~70/30, with services exports
disproportionately weighted toward financial / IP / royalty services.

### Inventory investment / GDP
**`Δ Inventories / Y`** · flow/flow · nfc · percent

Inventory accumulation as a share of GDP. Tiny in level (±0.5%) but
loud in cycles — the swing factor in quarterly real GDP prints.
Inventory drawdowns of 1–2% (annualized) are recession signatures;
restocking flips can add 1.5%+ to a quarter. Watch I/S ratio
alongside.

---

## 2. Sectoral balances

The closure identities of the macroeconomy. By construction:
`(S − I)_priv + (T − G)_gov + (M − X)_ext = 0`. Reading the world
through these three numbers is the foundation of MMT-style
analysis and most central-bank flow-of-funds work.

### Household financial balance / GDP
**`(S_HH − I_HH^res) / Y`** · flow/flow · households · percent

Household sector net lending as a share of GDP. Personal saving minus
residential investment; positive means households are accumulating
financial assets (or paying down debt). US runs +2 to +6% in
expansion, +8 to +10% in recessions (saving spike). The HH balance
is the consumer side of "are households extending or retracting?".

### NFC financial balance / GDP
**`(S_NFC − I_NFC) / Y`** · flow/flow · nfc · percent

NFC retained earnings minus capex (also called the corporate financing
gap, with sign flipped). Positive = NFCs are net savers (post-2000
US); negative = NFCs are funding capex with external finance. Modern
US NFCs are typically slight net savers — the buyback-funded balance
sheet structure.

### Total private domestic balance / GDP
**`(S_HH − I_HH^res) + (S_NFC − I_NFC)`** · flow/flow · aggregate · percent

Sum of HH + NFC financial balances. The "private" side of the
sectoral-balance identity. Equals `−(govt deficit + external balance)
/ Y` exactly. Tracking this against the (negated) sum of govt + ROW
balances is the cleanest sectoral-balance check.

### Government deficit / GDP
**`(G + Tr − T) / Y`** · flow/flow · government · percent

Federal + state + local fiscal deficit as a share of GDP. The
"government balance" line in sectoral-balance accounting (with sign
flipped: deficit = negative balance). Headline US deficit ~5–7% of
GDP today; compare to 1.5–3% pre-2008 expansion norms. CBO baseline
projections ~6%+ for the next decade absent legislation.

### Primary deficit / GDP
**`(G + Tr_non-int − T) / Y`** · flow/flow · government · percent

Government deficit excluding net interest payments. Removes the
"mechanical" debt-service component from the deficit, isolating
discretionary + automatic-stabilizer fiscal stance. Sustainability
math: stable debt/GDP requires primary surplus > (r − g) × debt/GDP.
US primary deficit ~3% with debt/GDP near 100% and (r − g) ≈ 0 is the
modern fiscal sustainability anchor.

### Foreign-sector balance / GDP
**`(M − X − Y_net) / Y ≈ −CA / Y`** · flow/flow · external · percent

Rest-of-world's financial balance against the domestic economy. The
mirror of the current account: a US current-account deficit
(negative CA) appears as a positive foreign-sector balance — ROW
accumulates financial claims on the US. The "exorbitant privilege"
of US deficit financing operates here.

### Cyclically adjusted primary balance / GDP
**`CAPB / Y_potential`** · flow/flow · government · percent

Primary balance scaled by potential GDP, with cyclical components of
revenue + outlays stripped out. The IMF / OECD / CBO benchmark for
"structural fiscal stance". A 1ppt year-on-year tightening in CAPB is
"fiscal consolidation"; the inverse is "fiscal stimulus". Useful
because the headline deficit moves automatically with the cycle.

---

## 3. Leverage

Indebtedness ratios across sectors. Mostly stock/flow (debt is a
stock; income/output is a flow). Compositional ratios within debt
(debt/equity) are stock/stock. The leverage cycle — borrow, build,
deleverage — is the central narrative of business-cycle macro since
2000.

### Gross public debt / GDP
**`Debt_gov^gross / Y`** · stock/flow · government · percent

Total debt outstanding (federal + state + local + agency, gross of
intragovernmental holdings) divided by annual GDP. US ~120% gross
today (federal ~100%; state & local ~20%). Gross is louder than
"held-by-public" because intragovernmental Treasury holdings (Social
Security trust fund etc.) are owed but already-internalized.

### Public debt held by public / GDP
**`Debt_gov^held-by-public / Y`** · stock/flow · government · percent

Federal debt actually owed to non-government creditors (~99% of GDP
in 2026). The economically-meaningful number for fiscal-sustainability
math; intragovernmental debt is a legal artifact. The CBO's
projection horizon is in this measure.

### Household debt / DPI
**`Debt_HH / DPI`** · stock/flow · households · percent

Aggregate household leverage relative to disposable personal income.
US ~95% today, down from peak ~135% in 2008. The deleveraging arc
post-GFC is the single most important macro stock-flow story of the
2010s. Includes mortgage + consumer credit + student loans.

### Household debt / GDP
**`Debt_HH / Y`** · stock/flow · households · percent

US ~70% (vs. ~95% peak). The GDP-scaled version of the same story.
Useful for cross-country comparisons where disposable-income
definitions differ. Norway, Sweden, Australia, Canada all run >100%
HH debt / GDP today and dominate the BIS warning list.

### Mortgage debt / DPI
**`Debt_HH^mortgage / DPI`** · stock/flow · households · percent

Mortgage-debt-only version of HH leverage. US ~65% of DPI today, down
from ~100% peak. The post-GFC retreat is largely mortgage-driven —
non-mortgage HH leverage is roughly flat across the cycle.

### Consumer credit / DPI
**`Debt_HH^consumer / DPI`** · stock/flow · households · percent

Non-mortgage HH leverage (credit card + auto + student + personal
loans). US ~25% of DPI. Less cyclical than mortgage; the
deleveraging hangover after 2008 was about housing finance, not
credit cards. Student loans dominate the secular drift up.

### NFC debt / GDP
**`Debt_NFC / Y`** · stock/flow · nfc · percent

Aggregate corporate leverage. US ~75% of GDP, near historical highs
(prior peak ~70% in 2007). Composition shift: bonds replaced loans
post-2008 (corporate-bond market grew ~50%; bank C&I share fell from
~70% to ~50% of NFC debt).

### NFC net debt / EBITDA
**`(Debt_NFC − Cash_NFC) / EBITDA_NFC`** · stock/flow · nfc · multiple

The credit-analyst's preferred leverage measure. Removes the
balance-sheet cash buffer from the gross debt number. Investment
grade target ~3x; below-investment-grade typically 4–6x; distressed
>7x. Aggregate US NFC ~2.5x; rising on M&A waves, falling on
deleveraging cycles.

### NFC debt / market equity (D/E)
**`Debt_NFC / MktCap_NFC`** · stock/stock · nfc · ratio

Market-value version of corporate leverage. Procyclical inverse —
falls when stocks rally (denominator inflates), rises in selloffs.
Aggregate US NFC ~30–50% across the cycle. Compare to book D/E
(~75–100%) which is much less cyclical.

### Bank loan-to-deposit ratio
**`L_banks / D_banks`** · stock/stock · banks · percent

Loans as a share of deposit funding. US commercial banks ~65% post
QE (deposits inflated by reserves); pre-2008 norm ~95%. Higher = more
loan-driven balance sheet (less liquidity buffer). H.8 weekly. Small
banks consistently run higher LDR than large banks (~80% vs. ~60%).

### Interest coverage ratio (ICR)
**`EBIT / Interest expense`** · flow/flow · nfc · multiple

NFC operating earnings vs. interest burden. Covenant-floor levels
typically 2–3x; <1x is technical default territory. Aggregate US NFC
~5–8x today; stress-tested to current rates would compress materially
on rolled debt. Small-cap and HY ICR has been the credit-cycle leading
indicator since 2022.

### BIS household debt service ratio (DSR)
**`(Interest + Amortization)_HH / DPI`** · flow/flow · households · percent

Quarterly debt service (interest + principal) as a share of household
income. The BIS-published version uses standardized maturity
assumptions. US runs ~10% today, range 9.5–13% pre-GFC. Rising
mortgage rates feed in slowly because most mortgages are 30y fixed —
ARM-heavy economies (UK, AU) saw faster transmission post-2022.

---

## 4. Valuation

Asset-pricing ratios. Most are stock/flow (price is a stock; earnings
or rent is a flow). Spreads are flow/flow. The eternal valuation
question: are we cheap or rich vs. history? — these ratios are the
denominators of that conversation.

### S&P 500 P/E (trailing)
**`P / E_{TTM}`** · stock/flow · market · multiple

Index-level price divided by trailing-twelve-month earnings per
share. Long-run mean ~16x; range 8x (1980 trough) to 30x (1999 peak).
Sector composition matters — tech-heavy index supports higher P/E
than the 1980s industrial composition. Watch denominator quality
during recessions (earnings collapse, P/E spikes mechanically).

### CAPE (Shiller)
**`P / E_10y-real-avg`** · stock/flow · market · multiple

Cyclically-adjusted P/E using real 10-year-average earnings. Smooths
the denominator-volatility problem that makes trailing P/E noisy at
turning points. Shiller's preferred valuation metric. US CAPE ~33
today vs. long-run mean ~17 — at the 90th+ historical percentile.

### S&P 500 dividend yield
**`Div_TTM / P`** · flow/stock · market · percent

Trailing dividend yield. US ~1.4% today vs. long-run mean ~3.5%. The
collapse since 1990 reflects the buyback shift — total cash return
(dividends + buybacks) yields ~4–5%, more comparable to historical
dividend levels. Inverse of dividend yield = the implicit P/D
multiple.

### S&P 500 earnings yield
**`E_{TTM} / P`** · flow/stock · market · percent

Trailing-twelve earnings divided by index level — the inverse of P/E,
expressed as a yield. Useful for direct comparison to bond yields:
the gap (E/P − Treasury yield) is the equity risk premium proxy. US
~5% today vs. ~5% Treasury — gap near zero, historically tight.

### S&P 500 price-to-book
**`P / Book Equity`** · stock/stock · market · multiple

Market-equity over book-equity. US ~4.5x today, up from ~3x long-run
mean. The drift partly reflects intangibles under-counted on the
book side (R&D, brand, software treated as expenses). Sector mix
matters — tech-heavy P/B looks stretched but reflects accounting
treatment of IP capital.

### Tobin's Q (NFC)
**`Mkt value of NFC / Replacement cost of NFC capital stock`** · stock/stock · nfc · ratio

Sector-aggregate version of P/B. Q > 1 implies firms can profitably
issue equity to fund new capital; Q < 1 implies replacement cost
exceeds market valuation (cheaper to buy a competitor than build).
Z.1 publishes a quarterly NFC Q-ratio. US has run Q > 1 since the
late 1990s; pre-1995 norm was Q ≈ 0.8. Not a clean buy/sell signal
in practice — Q has stayed elevated for decades.

### Equity risk premium (ERP)
**`E/P − r_{10y, real}`** · flow/flow · market · percent

The implied compensation for holding stocks vs. real Treasuries.
Multiple definitions exist (Damodaran's implied ERP, Gordon-growth
ERP, dividend discount versions). Earnings-yield-minus-real-yield is
the simplest. US runs ~3–5% historically; today ~2% (compressed by
high real yields + elevated valuations).

### IG credit spread (option-adjusted)
**`Yield_{IG} − Yield_{UST, duration-matched}`** · flow/flow · market · bps

Investment-grade corporate spread over duration-matched Treasuries.
Bloomberg US Corporate Index OAS. Range ~80 (2007 tights, 2021
post-stimulus tights) to ~600 (2008 peak). Today ~80–100 — historically
tight. The cleanest single barometer of corporate credit conditions.

### HY credit spread (option-adjusted)
**`Yield_{HY} − Yield_{UST, duration-matched}`** · flow/flow · market · bps

High-yield spread over Treasuries. Bloomberg US HY Index OAS. Range
~250 (2007 tights) to ~1900 (2008 peak), ~1100 (March 2020). Today
~300 — toward historical lows. The HY/IG ratio is itself a useful
risk-on/risk-off gauge.

### Cap rate (commercial real estate)
**`NOI / Property value`** · flow/stock · nfc · percent

Net operating income over current property value — the real-estate
analog of dividend yield. US office cap rate ~7%; multifamily ~5%;
industrial ~5–6%. Cap rate compression (denominator inflation) was
the post-GFC story; the post-2022 reversal has been most violent in
office (cap rates +200bps).

---

## 5. Distribution / inequality

Distributional shares of stocks and flows across population groups.
Mostly stock/stock (group's wealth / total wealth) or flow/flow
(group's income / total income). The DFA (Distributional Financial
Accounts) at the Fed is the canonical US source.

### Top 1% wealth share
**`NW_{P99-100} / NW_total`** · stock/stock · households · percent

Share of household net worth held by the top 1% of the wealth
distribution. US ~31% today (DFA Q4 2025); range 22% (early 1990s)
to 32%+ (late 2010s). The single most-cited inequality statistic in
US macro.

### Top 0.1% wealth share
**`NW_{P99.9-100} / NW_total`** · stock/stock · households · percent

Share held by the top 0.1%. US ~13% today (DFA). The top 0.1% has
roughly tripled its share since 1980 — far steeper than the top 1%
arc. SCF + DFA are the only public sources granular enough to
estimate this reliably.

### Bottom 50% wealth share
**`NW_{P0-50} / NW_total`** · stock/stock · households · percent

Share held by the bottom half. US ~3% today (DFA). The bottom 50%
has owned 0–4% of net worth across the entire DFA history (1989-).
Wealth concentration at the top is the primary story; the bottom is
roughly flat on this measure.

### Top 10% income share
**`Y_{P90-100} / Y_total`** · flow/flow · households · percent

Share of pre-tax national income captured by the top 10%. World
Inequality Database series. US ~46% today vs. ~33% in 1980. The
"hockey stick" of US inequality lives in the 1980-2010 window;
plateau since.

### Top 1% income share (pre-tax)
**`Y_{P99-100} / Y_total`** · flow/flow · households · percent

WID + Piketty-Saez series. US ~19% today vs. ~10% in 1980. This is
the income mirror of the top-1% wealth share — both have roughly
doubled. The post-tax version (~14%) shows the (modest) progressivity
of the US tax system.

### Gini coefficient (income, post-tax)
**`Gini(Y^{post-tax})`** · ratio · households · ratio

Standard inequality scalar — 0 = perfect equality, 1 = one person
takes all. US post-tax Gini ~0.40 today, up from ~0.34 in 1980.
European OECD median ~0.30. The coefficient compresses the full
distribution into one number — useful for cross-country comparison,
loses detail relative to share statistics.

### Gini coefficient (wealth)
**`Gini(NW)`** · ratio · households · ratio

Wealth Gini. US ~0.85 today (vs. ~0.40 income Gini — wealth always
concentrated more than income). Cross-country wealth Ginis range
~0.55 (Slovakia) to ~0.90 (US, Brazil). Hard to estimate cleanly —
wealth survey nonresponse is concentrated at the top.

### P90/P50 wage ratio
**`W_{P90} / W_{P50}`** · flow/flow · households · ratio

Top-decile wage divided by median wage. US ~2.4x today, up from
~1.7x in 1980. The "polarization" story — the gap between the top
decile and the median grew far faster than the gap between the
median and the bottom decile (P50/P10 ~2.0x, roughly flat since
1990).

### Mean / median wealth multiple
**`mean(NW) / median(NW)`** · stock/stock · households · multiple

Mean is pulled up by the right-tail; the multiple is a one-number
proxy for tail-heaviness. US mean wealth ~$1M, median ~$190K → mean/
median ~5.3x. Compare to ~3x in the 1960s. A higher-mean-than-median
multiple is the wealth-distribution analog of skewness.

### Homeownership rate
**`Owner-occupied units / Total occupied units`** · stock/stock · households · percent

Share of households that own their home. US ~66% today (range 63%
in 1965 → 69% in 2004 → 63% in 2016 → 66% today). Strongly
age-correlated; concerns about declining ownership concentrate among
under-35 cohorts post-2008.

---

## 6. Growth rates

Period-over-period changes in stocks and flows. All are flow/stock or
flow/flow depending on whether the underlying X is itself a stock or
flow. The most-tracked macro statistics in the world.

### Real GDP growth (qoq SAAR)
**`(Y_t / Y_{t-1})^4 − 1`** · growth · aggregate · percent (annualized)

Quarterly real GDP growth, annualized. The headline "GDP print" in
the US. NIPA Q1 advance, Q2 second, Q3 third estimates. Trend US ~2%;
recessions print 1–2 negative quarters in a row; expansions average
~2.3%. The Atlanta Fed GDPNow + NY Fed Nowcast are the workhorse
real-time trackers.

### Real GDP growth (yoy)
**`Y_t / Y_{t-4} − 1`** · growth · aggregate · percent

Year-over-year real GDP growth. Smoother than qoq SAAR — averages
across 4 quarters. Trend ~2%; recession troughs −2% to −4%; expansion
peaks ~4%. Useful for cross-country comparisons (most non-US series
publish yoy, not annualized qoq).

### Headline CPI inflation (yoy)
**`CPI_t / CPI_{t-12} − 1`** · growth · aggregate · percent

Consumer Price Index, all-items, year-over-year. Includes food + energy
volatility. BLS monthly; the "inflation print" that hits policy +
markets the hardest. Pre-2021 US ~1.5–2%; 2022 peak 9.1%; today ~3%.

### Core CPI inflation (yoy)
**`CPI_{ex-food-energy, t} / CPI_{ex-food-energy, t-12} − 1`** · growth · aggregate · percent

Core CPI excludes food + energy. The Fed's primary read for the
"trend" inflation signal stripped of supply-shock volatility. Today
~3.5%; recent run-up dominated by services-ex-shelter (BLS calls this
"supercore"; Fed-cited).

### Core PCE inflation (yoy)
**`PCE_{core, t} / PCE_{core, t-12} − 1`** · growth · aggregate · percent

Core Personal Consumption Expenditures price index, year-over-year.
The Fed's actual statutory inflation target (2% PCE core, since
2012). Lower-weight on shelter than CPI; tracks ~30bps below core CPI
on average. BEA monthly with NIPA Personal Income & Outlays release.

### Wage growth (AHE production+nonsup, yoy)
**`AHE_t / AHE_{t-12} − 1`** · growth · households · percent

Average Hourly Earnings, production + nonsupervisory workers, yoy.
The wage tracker most cited in real-time labor market commentary.
Less subject to compositional bias than the all-employees AHE.
Trend ~3–3.5%; today ~4%. Compare to ECI (Employment Cost Index)
quarterly, which controls for composition.

### M2 growth (yoy)
**`M2_t / M2_{t-12} − 1`** · growth · aggregate · percent

Broad money growth. US ~1% today; peaked at 27% during 2021
stimulus; fell as low as −5% during 2023 deposit migration (the
fastest contraction since the 1930s). Money-growth-as-leading-
inflation-indicator has been resurrected in the post-2020 era.

### Bank credit growth (yoy)
**`BankCredit_t / BankCredit_{t-12} − 1`** · growth · banks · percent

H.8 commercial bank credit (loans + securities), year-over-year. US
~2–3% today. Cyclical: ~6–10% in expansion, contracting in recession.
The C&I component is the standard credit-cycle leading indicator;
real estate is more lagging.

### Case-Shiller house prices (yoy)
**`HPI_t / HPI_{t-12} − 1`** · growth · households · percent

S&P/Case-Shiller National Home Price Index, year-over-year. US ~3%
today; range −18% (2009 trough) to +20% (2022 peak). Repeat-sales
methodology (vs. FHFA's purchase-only series). The cleanest house-
price growth signal at national level.

### Nonfarm business productivity (yoy)
**`(Y/H)_t / (Y/H)_{t-4} − 1`** · growth · aggregate · percent

Output per hour worked, nonfarm business sector, year-over-year.
BLS quarterly Productivity & Costs release. Trend US ~1.5%; recent
run ~2% (post-2020 acceleration debated — composition? capital
deepening? AI premature?). Determines real-wage growth + Fed's
neutral-rate calculus.

---

## 7. Returns

Period income or capital gain divided by capital base. Mostly
flow/stock — return = (period flow) / (start-of-period stock). The
"yield" universe.

### Bank ROE
**`Net income_banks / Avg Equity_banks`** · flow/stock · banks · percent

Bank-sector return on equity. US large-bank ROE ~10–12% today;
pre-GFC norm 12–15%; capital-rule tightening cut steady-state ROE
~3ppts. Aggregate (FDIC) ~10%. Below cost-of-equity (~10%) for many
banks today — implied P/B compression.

### Bank ROA
**`Net income_banks / Avg Total assets_banks`** · flow/stock · banks · percent

Bank-sector return on assets. US ~1.0–1.2% today. Less leverage-
sensitive than ROE. Useful for cross-bank comparisons (large vs.
community) where capital structure differs. Pre-GFC norm ~1.3–1.5%.

### NFC sector ROE
**`Net income_NFC / Equity_NFC`** · flow/stock · nfc · percent

Sector-aggregate corporate return on equity. US ~12–14% today.
Buyback-funded equity reduction has propped up ROE structurally —
cleaner read is ROA or ROIC.

### NFC sector ROA
**`Net income_NFC / Total assets_NFC`** · flow/stock · nfc · percent

Sector-aggregate corporate return on assets. US ~6–7%. More stable
than ROE (no leverage / buyback distortion). The "earning power"
metric corporate-finance textbooks anchor on.

### 10y Treasury real yield (TIPS)
**`yield_{10y nominal} − BE inflation_{10y}`** · flow/stock · government · percent

10-year TIPS yield — the canonical risk-free real rate. Today ~2%;
range −1% (2020 lows) to +2% (post-2022 highs). The discount-rate
floor for everything that prices off "long real rates" — equity
multiples, real estate, infrastructure NPVs.

### Earnings yield gap (E/P − 10y real)
**`E/P − r_{10y, real}`** · flow/flow · market · percent

Forward earnings yield minus 10y TIPS — a real-rates-adjusted ERP
proxy. US ~3% today; long-run norm ~3–4%. The denominator switch
(real vs. nominal Treasury) materially changes the level — choose
explicitly. Damodaran's implied ERP is a more rigorous version.

### Free cash flow yield (FCF/P)
**`FCF_TTM / Mkt cap`** · flow/stock · market · percent

Free cash flow over market cap — earnings yield's cash-flow analog.
US S&P 500 FCF yield ~3.5%. Less manipulable than earnings (no
accruals games); preferred by quality-equity investors. The
spread vs. Treasury yield is the cash-payback ERP.

---

## 8. Real-side / labor

Quantities and rates in the labor and production system. Mostly
stock/stock (employed / population, unemployed / labor force —
compositional ratios of population groups). A few are flow/stock
(quits rate, capacity utilization) and a few flow/flow (labor share,
output gap).

### Unemployment rate (U-3)
**`Unemployed / Labor force`** · stock/stock · households · percent

Standard headline unemployment (BLS). US ~4% today; full-employment
estimates 3.5–4.5%; recession peaks 6–10%. The Phillips-curve-driver,
Sahm-rule trigger, and most-cited macro-real-side indicator.

### U-6 (broader unemployment)
**`(U + Marginally attached + PT-for-econ-reasons) / (LF + Marginally attached)`** · stock/stock · households · percent

Broader unemployment measure capturing discouraged workers and
involuntary part-time. U-6 ~7.5% today; runs ~3.5–4ppts above U-3
historically; gap widens in recoveries (slack hiding in part-time).

### Employment-to-population ratio
**`Employed / Civilian noninstitutional population`** · stock/stock · households · percent

Employed share of working-age + population. US ~60% today; peak
~64% in 2000; 2020 trough 51%. The "level of employment relative to
demographic supply" — bypasses the labor-force-participation issue
in the unemployment rate.

### Prime-age (25-54) employment-population
**`Employed_{25-54} / Population_{25-54}`** · stock/stock · households · percent

EPOP restricted to prime-age population — strips out demographic
aging + youth schooling effects. The labor-market state most
predictive of policy traction. US ~80–81% today; pre-COVID peak
~80.4%; recovery has been remarkably full.

### Labor force participation rate
**`Labor force / Civilian noninstitutional population`** · stock/stock · households · percent

Share of pop working or looking for work. US ~62.5% today; peak
~67% in 2000; secular decline reflects aging + (some) discouragement.
Prime-age LFPR (~83%) is the cyclically meaningful version —
headline is dominated by retirement boomers.

### Job openings rate (JOLTS)
**`Job openings / (Job openings + Employed)`** · stock/stock · aggregate · percent

Vacancies as a share of total employment positions (filled +
unfilled). US ~5% today; range 3% (2010s norm) to 7% (2022 peak).
The "labor demand" measure central to the Beveridge-curve framing
of post-2020 disinflation.

### Quits rate
**`Quits_t / Employed_t`** · flow/stock · households · percent

Voluntary separations as a share of employment, monthly. The tightest
real-time gauge of worker bargaining power. US ~2.0% today; 2022
peak 3.0%; recession troughs ~1.3%. "Great Resignation" 2021–22 lived
in this series.

### V/U ratio (vacancy-to-unemployed)
**`Job openings / Unemployed`** · stock/stock · aggregate · ratio

Tightness measure. US ~1.0 today; range 0.2 (recession) to 2.0
(2022 peak). The Beveridge-curve framing: V/U > 1 is "tight" labor
market; the Fed's preferred non-Phillips disinflation channel works
through V/U dropping while U holds (post-2022 "soft landing"
compatibility).

### Labor share
**`Compensation_total / GDI`** · flow/flow · aggregate · percent

Labor's share of national income. US ~57–60% today; secular drift
down from ~64% in 1970. The single most-cited distributional
macro statistic. Cross-country labor-share-fall is broadly
synchronized — partly composition (fall of manufacturing), partly
markup-driven, partly globalization.

### Capital share
**`(Operating surplus + Mixed income) / GDI`** · flow/flow · aggregate · percent

Mirror of labor share. US ~38% today, up from ~32% in 1970. Within
capital share, profit share + interest share + rental income split
matters — all three rose, but profits drove most of the secular
shift.

### Output gap
**`(Y − Y*) / Y*`** · flow/flow · aggregate · percent

Actual GDP minus potential GDP, as a percent of potential. CBO
estimates US near zero today (recovered from −10% in 2020). The
classical "slack" measure central to Phillips-curve modeling.
Y* itself is unobservable — model-dependent (CBO, IMF, BEA each
publish slightly different versions).

### Capacity utilization (industrial)
**`Output_industrial / Capacity_industrial`** · flow/stock · nfc · percent

Industrial Production / Industrial Capacity. Fed G.17 monthly. US
~78% today; range 64% (recession trough) to 85% (cyclical peak).
The narrow-but-real-time slack measure for the goods-producing
sector. Less useful in a services-dominant economy but still tracked.

---

## 9. Monetary / banking

Bank balance-sheet composition, capital ratios, asset quality, money
supply. Mostly stock/stock (bank ratios) or stock/flow (M2/GDP). The
H.8 weekly + Call Reports quarterly form the data backbone.

### CET1 ratio
**`CET1 capital / RWA`** · stock/stock · banks · percent

Common Equity Tier 1 capital as a share of risk-weighted assets.
The post-Basel III primary capital adequacy gauge. US large banks
~12–14% today; regulatory minimum 4.5% + 2.5% conservation buffer +
GSIB surcharge (1–4.5% depending on bank). Most actionable single
banking-stability indicator.

### Tier 1 leverage ratio
**`Tier 1 capital / Total assets`** · stock/stock · banks · percent

Non-risk-weighted leverage gauge. US large banks ~8–9% today;
regulatory minimum 4% (5% for SLR-relevant GSIBs). Less gameable
than CET1 (no RWA-density tweaks). The 2010s rise in supplementary
leverage exposure (SLR) made this the binding constraint for many
GSIBs at certain points.

### Bank net interest margin (NIM)
**`Net interest income / Avg earning assets`** · flow/stock · banks · percent

Bank-sector net interest margin. US large banks ~2.5–3.0% today;
range ~2.2% (2014–21 ZIRP era) to ~4% (1980s). The single most-
important bank P&L driver. Sensitivity to rate moves = "deposit
beta" — how much deposit-rate pass-through banks accept on Fed hikes.

### Allowance / gross loans (ACL coverage)
**`ACL / Gross loans`** · stock/stock · banks · percent

Allowance for credit losses as a share of gross loans. US ~1.3–1.6%
today (post-CECL norm); pre-CECL ~1.2%; GFC peak ~3.6%. Shocks
ahead-of-cycle pull this up; expansions grind it down. Recently, CRE
exposure stress has been visible primarily here.

### Net charge-off rate
**`Net charge-offs / Avg loans`** · flow/stock · banks · percent (annualized)

Annualized realized credit losses. US banks ~0.6% today; range 0.3%
(expansion lows) to 3% (2009 peak). Credit-card NCOs run ~3–5%; CRE
~0.1–1.5%; C&I ~0.3–1%. The realized-loss companion to provisioning.

### NPL ratio
**`Nonperforming loans / Total loans`** · stock/stock · banks · percent

Loans 90+ days delinquent + nonaccrual. US banks ~0.7% today; range
~0.6% (cycle lows) to ~5% (1991, 2009). Country comparison: Italy
peaked ~17% post-eurozone crisis; Japan never published a clean
post-1990 number due to forbearance.

### Cash assets / total bank assets
**`Cash + Reserves / Total assets`** · stock/stock · banks · percent

Liquidity buffer. US banks ~10% today (post-QE elevated); pre-QE
norm ~3%; deposits-flight stress brings this down (banks dropped
cash in March 2023 SVB episode). H.8 weekly.

### Loans / total bank assets
**`Loans / Total assets`** · stock/stock · banks · percent

Loan-intensity of the bank balance sheet. US banks ~52% today; pre-
QE norm ~58%; mid-1990s ~65%. Mirror of securities + cash. Smaller
banks lend-heavier (~65%) than money-centers (~40–50%).

### Uninsured deposit share
**`Uninsured deposits / Total deposits`** · stock/stock · banks · percent

Share of deposits above the FDIC $250K limit. US ~45% today (down
from ~50% pre-SVB); the SVB stress test exposed this — banks with
80%+ uninsured ratios faced the most run risk. Call Reports
quarterly.

### M2 / GDP (Marshallian K)
**`M2 / Y`** · stock/flow · aggregate · percent

Broad money relative to GDP. US ~75% today; range 50% (1995) to 90%
(2021 peak). The inverse of velocity. Surge during 2020-21 was a
definitional spike (transfer payments + reserve balances + deposit
inflows); modest decline since. Strict-monetarist framings lean
heavily on this ratio.

### Velocity of M2
**`Y / M2`** · flow/stock · aggregate · ratio

GDP per dollar of M2. US ~1.4 today; range ~1.1 (2021 trough) to
~2.1 (1997 peak). Secular decline since 2000; sharp drop 2020. The
secular fall is partly definitional (more financial deposits in M2),
partly real (lower turnover). Often overinterpreted.

### Reserves / total deposits
**`Reserves at Fed / Total deposits`** · stock/stock · banks · percent

Reserve-balance backing of deposits. US ~13% today (peak ~22% during
QE3); pre-2008 norm <2%. Post-2008 abundant-reserves regime: reserve
levels are a Fed balance-sheet decision, not a bank choice. The 2023
SVB episode showed minimum-reserve-comfort levels were not yet
binding (~3 trillion).

---

## 10. External

Cross-border stock-flow ratios. Current account = the consolidated
sectoral-balance against rest-of-world. NIIP = the cumulated stock
counterpart. REER + terms-of-trade = the price side.

### Current account / GDP
**`CA / Y`** · flow/flow · external · percent

Current-account balance as a share of GDP. US runs −2.5 to −4%
(persistent deficit). The mirror of (S − I) for the domestic economy
+ government — exact identity by sectoral balance. Global imbalances
debate centers on East-Asian + oil-exporter surpluses funding US
deficit.

### Goods trade balance / GDP
**`(X_goods − M_goods) / Y`** · flow/flow · external · percent

Goods-only trade balance, excluding services. US runs −4 to −5%; the
goods deficit is structurally larger than the services surplus
(+1.5%) — net is the −2.5 to −3.5% trade balance. The bilateral
goods deficit with China + Mexico dominates the goods line.

### NIIP / GDP
**`(Foreign assets − Foreign liabilities) / Y`** · stock/flow · external · percent

Net international investment position over GDP. US ~ −80% today —
the world's largest debtor in absolute terms. The cumulated
counterpart of decades of CA deficits, but valuation effects (USD
strength, US equity outperformance) have offset some accumulation.
US net income flows still positive despite negative NIIP — the
"exorbitant privilege".

### External debt / GDP
**`Gross foreign debt / Y`** · stock/flow · external · percent

Gross debt owed to foreigners. US ~95% (Treasury + other). For
emerging markets the equivalent (often also dollar-denominated) is
the workhorse vulnerability indicator — 60–80% is the IMF
"caution" zone. Argentina, Turkey have run >100% pre-crisis.

### Reserves / months of imports
**`Foreign reserves / (M_goods+services / 12)`** · stock/flow · external · multiple (months)

Months of import cover. IMF rule-of-thumb floor: 3 months. China ~14
months; emerging-market median ~6 months; reserve-adequacy stress
zones <3 months. US doesn't track this — USD-issuer doesn't need
reserves. The metric is most relevant for non-reserve-currency
issuers.

### Reserves / short-term external debt
**`Foreign reserves / Foreign debt_{maturing < 1y}`** · stock/stock · external · ratio

The Greenspan-Guidotti rule: ratio ≥ 1.0 = "adequate". The crisis
indicator. EM crises (1997 Asia, 2001 Argentina, 2018 Turkey) all
preceded by ratios falling below 1. China + Saudi Arabia run ratios
above 4; Turkey + Argentina are sub-1 today.

### REER (real effective exchange rate, level)
**`Σ w_i × (e_i × P_dom / P_i)`** · level · external · index

Trade-weighted real exchange rate index. JPMorgan, Fed, BIS each
publish slightly different baskets. US dollar broad REER ~120 today
(BIS); range 80 (2008 trough) to 130 (2002 peak). Reversion-to-mean
takes 5+ years; not a near-term FX trade signal but a long-run
valuation anchor.

### Terms of trade
**`P_X / P_M`** · flow/flow · external · index

Export prices over import prices. Improvement = your exports buy more
imports per unit. Commodity-exporter terms of trade rise with oil/
commodities; commodity-importer falls. US ~flat — diversified import/
export basket. Australia's terms of trade ran +50% in 2021 China
demand boom; the AUD strength was largely TOT-driven.

### Foreign holdings / Treasury marketable debt outstanding
**`UST_{foreign} / UST_{marketable, total}`** · stock/stock · external · percent

Foreign-held share of US Treasury market. ~30% today, down from
peak ~50% in 2008 — the 15-year decline is largely Fed-balance-sheet
absorption of the difference (held-share rose). Within "foreign",
official (central bank) vs. private has shifted away from official
since China's reserve-accumulation peak ~2014.

### FDI inflow / GDP
**`FDI_in / Y`** · flow/flow · external · percent

Foreign direct investment inflows as a share of GDP. US ~1% today;
EM inflows can run 3–5% (Chile, Vietnam). The structural-not-
financial leg of foreign capital — typically less reversal-prone
than portfolio flows. Mexico's FDI has grown sharply since 2022 on
nearshoring.

---

## 11. NIPA income approach

The income side of GDP. Where Theme 1 was the expenditure approach
(`C + I + G + (X − M)`), this is the income approach (compensation +
operating surplus + mixed income + net taxes). Same total, two
views — the NIPA Table 1.10 / Table 2.1 surfaces. Plus the gross-vs-
net (post-depreciation) saving / investment / income variants that
get short shrift in headline reporting.

### Compensation of employees / GDP
**`Compensation_total / Y`** · flow/flow · aggregate · percent

Total employee compensation (wages + supplements) as a share of GDP.
The NIPA labor-share variant. US ~52% today; secular drift down from
~58% in 1970. Differs slightly from "labor share" in Theme 8 (which
uses GDI denominator); the GDP version is more frequently cited in
NIPA-specific contexts.

### Net operating surplus / GDP
**`NOS / Y`** · flow/flow · aggregate · percent

Net operating surplus (after capital consumption) as a share of GDP —
the NIPA "corporate share" of national output. US ~14–16% today.
Net (post-D&A) is the cleaner read than gross since depreciation is
not income to anyone.

### Mixed income / GDP
**`Mixed income / Y`** · flow/flow · aggregate · percent

Income of unincorporated business (proprietors + partnerships +
unincorporated farms) — neither pure labor nor pure capital, mixed.
US ~9% today. Underweighted in modern macro discussion but a real
slice of the income distribution; tax-side often lumped with
personal income.

### Net taxes on production / GDP
**`(Taxes − Subsidies)_production / Y`** · flow/flow · aggregate · percent

Net indirect taxes (sales tax, property tax, customs, excise, less
subsidies) as a share of GDP. The "wedge" between GDP at market
prices and at factor cost. US ~8% (relatively low — VAT-heavy
economies run 15%+).

### Net national income / GDP
**`NNI / Y`** · flow/flow · aggregate · percent

Net national income = GDP − consumption of fixed capital + net
factor income from ROW. US ~83% (after ~16% depreciation, then
small positive net factor income tilt). The "net" headline most
economists quietly prefer over GDP for welfare comparisons.

### Personal income / GDP
**`PI / Y`** · flow/flow · aggregate · percent

Personal income as a share of GDP. US ~85%. The wedge between PI and
GDP captures: corporate profits not distributed (retained earnings),
employer payroll taxes (paid by firms, not received by HHs as
"income"), and net business income.

### Disposable personal income / GDP
**`DPI / Y`** · flow/flow · households · percent

Personal income minus current personal taxes. US ~73%. The post-tax
wedge — direct gauge of how much of the national pie households
actually have to spend or save.

### Total tax revenue / GDP
**`(T_federal + T_S&L) / Y`** · flow/flow · government · percent

Federal + state + local tax revenue. US ~28%; OECD average ~34%;
Nordics 40%+. The single most-cited "size of government" indicator
across countries. Differs from v1's federal-only revenue share by
including the substantial state-and-local layer (~10% of GDP).

### NFC profits before tax / GDP
**`Profits_pre-tax / Y`** · flow/flow · nfc · percent

Corporate profits before tax as a share of GDP, NIPA Table 6.16.
US ~12% today; cyclical range 8–13%. Variants: domestic vs total
(adds rest-of-world earnings); economic profits (with IVA + CCAdj)
vs book profits.

### NFC profits after tax / GDP
**`Profits_post-tax / Y`** · flow/flow · nfc · percent

After-tax corporate profits as a share of GDP. US ~10% today; the
post-2017 TCJA tax-cut step is visible in this series. Pre-2017 the
gap to pre-tax was ~2.5%; post-2017 ~1.5%.

### Net national saving rate
**`(GS_national − D&A) / Y`** · flow/flow · aggregate · percent

National saving net of capital consumption (depreciation), as a
share of GDP. US ~3% today — historically low; recent troughs near
zero. The "real" saving figure: gross national saving runs ~17–19%,
of which ~14% just maintains the existing capital stock. A different
signal from the gross-saving rate in v1 Theme 1.

### Net domestic investment / GDP
**`(GDI − D&A) / Y`** · flow/flow · aggregate · percent

Investment net of depreciation. US ~5% today. The "net adds" to the
capital stock per period — this drives Solow-style growth math.
Together with net national saving, the (S − I) gap shifts to NIPA-
net concepts (and tightens — both sides shrink by depreciation).

### Capital consumption / GDP
**`D&A_NIPA / Y`** · flow/flow · aggregate · percent

Consumption of fixed capital (depreciation + amortization) as a share
of GDP. US ~16%; structural drift up from ~10% in 1970 as
intangibles + IT capital depreciate faster. The wedge between gross
and net concepts across the NIPA system.

---

## 12. Wealth-to-income (Piketty universe)

Stock-to-flow ratios that measure the SIZE of wealth relative to the
flow of income that generates it. Piketty's β = K/Y is the anchor;
many variants. Slow-moving but huge structural anchors. Each ratio
is in years (a wealth stock divided by an annual income flow).

### Capital-output ratio (K/Y)
**`K / Y`** · stock/flow · aggregate · multiple (years)

The ratio of the productive capital stock to annual GDP — Solow's
steady-state β. US ~3.0x; OECD norms 2.5–4.0. Has drifted up since
1980 across most rich economies; the Piketty wealth-share narrative
builds from this. Different from total-private-wealth β below by
restricting K to reproducible productive capital.

### Total private wealth / GDP (β, Piketty)
**`Wealth_total^private / Y`** · stock/flow · aggregate · multiple (years)

Piketty's broader β. US ~5x today vs. ~3x in 1980. Includes housing,
financial wealth, business equity, durables. The "comeback of
capital" in *Capital in the Twenty-First Century* is largely this
2x climb. Cross-country: France ~6x, UK ~6x, Germany ~4x today.

### Household net worth / DPI
**`NW_HH / DPI`** · stock/flow · households · multiple (years)

Household-sector wealth-to-income. US ~7.5x today (Z.1 Q4 2025);
range ~5x (1990s) to 8x (current peak). The HH "lifecycle wealth"
benchmark. Cycles are huge — wealth/income at 8x in 2007, 6x in
2009, 7.5x in 2020, 8.5x in 2022 peak, 7.5x today.

### Household net worth / GDP
**`NW_HH / Y`** · stock/flow · households · multiple (years)

HH net worth scaled to GDP. US ~5.6x today (vs ~4.5x in 1990).
Cleaner cross-country comparison than HH/DPI (where DPI definitions
diverge). Z.1 + DFA quarterly.

### Net financial wealth (HH) / GDP
**`NFA_HH / Y`** · stock/flow · households · multiple (years)

Household financial assets minus liabilities, scaled to GDP. US
~3.5x today. Structurally different from total wealth — financial
wealth concentrates more at the top and is more cyclical (equity
markets drive most of it). Z.1 Table B.101.

### Total housing wealth / GDP
**`Real Estate_HH / Y`** · stock/flow · households · multiple (years)

Aggregate residential real estate (owner-occupied + rental + tenant)
divided by GDP. US ~1.7x today; range 1.2x (1990) to 2.0x (2006 peak,
2022 peak). The single largest household asset class in absolute
terms.

### Pension wealth / GDP
**`Pension entitlements / Y`** · stock/flow · aggregate · multiple (years)

DB + DC pension entitlements + IRAs as share of GDP. US ~1.5x today;
pre-1990 ~0.5x — financialization of retirement. Includes public +
private pension claims; excludes Social Security entitlements (a
separate flow obligation, sometimes added as memorandum).

### National net worth / GDP
**`NW_national / Y`** · stock/flow · aggregate · multiple (years)

Total national balance sheet (Z.1 Table B.1) — all sectors' net
worth summed = real-asset stock + net foreign assets. US ~6x today.
Differs from Piketty β by capturing real assets at market value
rather than reproducible-cost capital.

### Capital-labor ratio (K/L)
**`K / Hours worked` or `K / Employment`** · stock/flow · aggregate · level (varies)

Capital per worker (or per hour). The "capital deepening" metric —
rising K/L is the fundamental driver of labor productivity in Solow
growth. US K/L roughly doubled since 1970; per-hour capital up
materially since 2000. Decomposed in growth accounting (Theme 18).

### Productive capital stock / GDP
**`K_productive / Y`** · stock/flow · aggregate · multiple (years)

Tangible reproducible capital (structures + equipment + software,
typically excluding land + intangibles). US ~2.5x today. Cleaner for
international comparisons than total private wealth (which includes
land — variable definitions across countries).

---

## 13. Money + credit aggregates / GDP

Beyond v1's M2/GDP and velocity. Total credit aggregates (BIS),
monetary base, currency. The structural surface of monetary depth.

### Total credit to non-financial sector / GDP
**`Credit_NFS / Y`** · stock/flow · aggregate · percent

BIS broadest credit measure: HH + NFC + Government credit. US ~250%;
OECD median ~270%; China ~310%. The single broadest measure of "how
leveraged is this economy". BIS countercyclical capital buffer
trigger uses gap from this trend.

### Total credit to private non-financial sector / GDP
**`Credit_{HH+NFC} / Y`** · stock/flow · aggregate · percent

Same as above but excluding government — only private-sector
borrowing. US ~150%; the "private leverage" gauge. Used in BIS
early-warning models for banking crises (Drehmann–Borio–Tsatsaronis
gap measure).

### Bank credit / GDP
**`BankCredit / Y`** · stock/flow · banks · percent

US commercial bank credit (loans + securities) as a share of GDP.
~75% today; pre-QE norm ~60%. The H.8 weekly aggregate scaled to
GDP. Signal: bank-intermediated share of total credit. Has fallen
relative to total private credit as nonbank lending grew.

### Currency in circulation / GDP
**`Currency / Y`** · stock/flow · aggregate · percent

Physical currency and coin held outside banks as share of GDP. US
~9% (high — driven by foreign holdings of dollar bills, est. 50%+ of
US currency held abroad). Eurozone ~12%; Japan ~25% (cash-heavy
society).

### Monetary base / GDP
**`MB / Y`** · stock/flow · aggregate · percent

Currency + bank reserves at central bank, share of GDP. US ~22%
today (post-QE elevated); pre-QE ~6%. The "outside money" stock —
the central bank's liability matched against base-money assets.

### M1 / M2
**`M1 / M2`** · stock/stock · aggregate · ratio

Transactional-money share of broad money. US M1/M2 ratio jumped from
~25% (pre-2020) to ~85% (post-2020 redefinition that moved savings
deposits into M1). The pre-2020 series captured the "willingness to
spend" — now muddled by definitional change.

### Reserves at Fed / GDP
**`Reserves_Fed / Y`** · stock/flow · banks · percent

Bank reserves at the Fed scaled to GDP. US ~13% today (peak ~22%
during QE3); pre-2008 ~0.5%. Tracks the QE/QT cycle. The relevant
"abundance" benchmark for the ample-reserves regime — the Fed
targets a no-shortage equilibrium above an ill-defined floor.

### Credit-to-GDP gap (BIS)
**`Credit/GDP_t − HP-trend(Credit/GDP)_t`** · ratio · aggregate · percentage points

Deviation of credit/GDP from a one-sided HP-filter trend. The BIS
countercyclical-capital-buffer trigger threshold: above 2ppts implies
gradually adding capital buffer; above 10ppts implies max buffer. US
~−5ppts today (slack); China ran +25 in the 2010s; Spain ran +40
pre-2008.

---

## 14. Financial market deepening

Stock of major financial markets relative to GDP. Z.1-derived. The
"size" of the financial system at the highest level of aggregation.

### Total stock market cap / GDP (Buffett indicator)
**`MktCap_equity / Y`** · stock/flow · market · percent

US public-equity market cap divided by GDP. ~190% today; long-run
mean ~85%; range 35% (1980) to 200%+ (2021 peak). Buffett's
preferred valuation indicator at the aggregate level — though it has
been distorted by globalization (US firms with foreign operations
inflate the numerator relative to the domestic GDP denominator).

### Total bond market / GDP
**`Bonds_outstanding / Y`** · stock/flow · market · percent

All US fixed-income outstanding (Treasury + agency + corporate +
municipal + ABS) over GDP. ~225% today; up from ~150% in 2000.
Reflects the doubling of public debt + corporate-bond growth. SIFMA
aggregate.

### Treasury market / GDP
**`UST_marketable / Y`** · stock/flow · market · percent

Marketable Treasury debt outstanding scaled to GDP. ~100% today
(vs. ~30% in 2000). The "premier reserve asset" stock — also the
benchmark for fiscal capacity. Different from gross-public-debt-to-
GDP in v1 by restricting to marketable instruments.

### Corporate bond market / GDP
**`CorpBonds / Y`** · stock/flow · nfc · percent

Total corporate bond debt outstanding over GDP. US ~50%; up from
~30% in 2000. The post-2008 disintermediation — corporate-bond
market grew while bank C&I lending shrank as a share of NFC debt.

### Mortgage market / GDP
**`Mortgages_outstanding / Y`** · stock/flow · households · percent

Total residential + commercial mortgage debt as share of GDP. US
~85% today; peak ~100% (2007). The single biggest credit market in
most advanced economies.

### Bank assets / GDP
**`Banks_assets / Y`** · stock/flow · banks · percent

Commercial bank total assets scaled to GDP. US ~80%; eurozone ~270%;
Japan ~350%. The structural "bank-centricity" of the economy. US
banking is shallow vs Europe/Japan because capital markets do more
of the heavy lifting.

### Total financial sector assets / GDP
**`FinSector_assets / Y`** · stock/flow · aggregate · percent

All financial intermediaries' assets (Z.1 sum). US ~500% today;
1985 ~250%; secular climb reflects financialization. Includes
banking + insurance + pensions + funds + GSEs + ABS issuers.

### Pension assets / GDP
**`PensionAUM / Y`** · stock/flow · aggregate · percent

Total pension fund AUM (DB + DC + state/local + federal) scaled to
GDP. US ~150% today; pre-2000 ~70%. The largest investor class in US
capital markets by AUM.

### Mutual fund + ETF AUM / GDP
**`MFAUM + ETFAUM / Y`** · stock/flow · market · percent

US mutual fund + ETF assets under management over GDP. ~110% today;
pre-2000 ~50%; ETF share within this has gone from <1% to ~25% of
total. Tracks retail / institutional participation in markets.

### Fed balance sheet / GDP
**`Fed_assets / Y`** · stock/flow · government · percent

Federal Reserve total assets over GDP. US ~25% today; peak ~36%
(2022); pre-2008 ~6%. The QE/QT lever — direct measure of monetary
balance-sheet expansion. Forward path: Fed has guided "smaller but
abundant" reserves regime, implying steady-state ~20%.

---

## 15. Government finance composition

Beyond v1's debt/GDP and deficit/GDP. Interest burden, holders, and
maturity structure of government debt. The "shape" of fiscal
position rather than its level.

### Net interest expense / GDP
**`Interest_federal / Y`** · flow/flow · government · percent

Federal net interest expense as share of GDP. US ~3.2% today, up
from ~1.5% in 2020. Projected to climb above 5% by mid-2030s on CBO
baseline as low-rate debt rolls into higher-rate funding. The single
most-cited fiscal-sustainability gauge today.

### Net interest expense / federal revenue
**`Interest_federal / T_federal`** · flow/flow · government · percent

Interest as a share of federal tax revenue. US ~18% today; running
toward ~25% by 2030 on baseline. Captures debt-affordability — when
interest takes >20% of revenue, fiscal flexibility tightens
materially. The metric Reinhart-Rogoff and others highlight as the
political stress point.

### Federal outlays / GDP
**`Outlays_federal / Y`** · flow/flow · government · percent

Total federal spending scaled to GDP (transfers + interest + G).
US ~24% today vs. ~20% pre-2000. Includes transfers (which are NOT
in NIPA G — that's the wedge from v1's G/Y of ~7%). The "size of
federal" measure most commonly cited in budget discussions.

### Foreign-held federal debt / total federal debt
**`UST_foreign / Total federal debt`** · stock/stock · government · percent

Share of federal debt held by foreign creditors. US ~25% of gross
debt held by public; peak ~50% (2008). The "external dependence"
gauge for US fiscal position. Within "foreign", official (CB) vs.
private has shifted away from official since China's reserve-
accumulation peak ~2014.

### Fed-held UST / total marketable
**`UST_Fed / UST_marketable`** · stock/stock · government · percent

Share of marketable Treasuries on the Fed's balance sheet. ~20%
today; peak ~28% (2022); pre-QE ~15%. The "QE residual" — captures
how much fiscal financing the central bank is absorbing at the
margin. Close cousin of Fed-balance-sheet-to-GDP.

### Marketable / total federal debt
**`UST_marketable / Total federal debt`** · stock/stock · government · percent

Negotiable share of total federal debt. US ~80%; intragovernmental
holdings (Social Security trust fund, federal employee retirement)
make up the residual. Marketable is the economically-meaningful
denominator for most Treasury-market discussions.

### Average maturity of marketable debt
**`Σ (M_i × maturity_i) / Σ M_i`** · level · government · years

Weighted-average maturity of marketable Treasury debt outstanding.
US ~6 years today; declined from ~6.3 (2020) as Treasury increased
bill issuance. The longer the WAM, the slower rate increases pass
through to interest expense — directly relevant for the trajectory
of net-interest/GDP. Treasury QRA tracks against a vague "regular
and predictable" target.

---

## 16. Global macro / world aggregates

The world-level versions of US-centric ratios. IMF / BIS / WTO data.
Bilateral comparisons (China-US, EM-DM) where they're top-level for
cross-asset positioning.

### World trade / world GDP
**`(X_world + M_world) / 2 / Y_world`** · flow/flow · external · percent

Globalization gauge — total world trade as a share of world GDP.
~30% today; peak ~32% (2008); pre-1990 ~15%. The "trade-to-GDP"
plateau since 2008 has been the slowbalisation thesis evidence.
World Bank / WTO data.

### Sum of world CA imbalances / world GDP
**`Σ |CA_country| / 2 / Y_world`** · flow/flow · external · percent

The global savings-glut / imbalances intensity gauge — the absolute
sum of world current-account imbalances divided by 2 (each unit
appears once as surplus, once as deficit) over world GDP. ~1.5%
today (compressed from ~3% in 2008). Pre-2008 imbalances were the
canonical Bernanke "savings glut" topic.

### World FDI stock / world GDP
**`FDI_world / Y_world`** · stock/flow · external · percent

Aggregate inward FDI position relative to world GDP. ~45% today;
1990 ~10%. The financial-globalization trajectory at structural
level. Tracks slower than CA imbalances — cumulative measure.

### World portfolio investment / world GDP
**`Portfolio_world / Y_world`** · stock/flow · external · percent

Cross-border portfolio investment (equity + debt) as share of world
GDP. ~75% today; up from ~30% (1995). The "financial integration"
gauge. Reverses partially in crises (home bias re-emerges).

### World cross-border bank claims / world GDP
**`BIS_LBS_claims / Y_world`** · stock/flow · banks · percent

BIS Locational Banking Statistics — cross-border claims of BIS-
reporting banks. ~60% today; peak ~70% (2008); structural decline
since GFC as banks retrenched home. The "global bank balance sheet"
gauge.

### World public debt / world GDP
**`Σ Debt_gov_country / Y_world`** · stock/flow · government · percent

Global government debt scaled to world GDP. ~95% today; pre-2008
~60%; post-2020 surge to peak ~100%. IMF Fiscal Monitor publishes
this — useful for benchmarking individual-country debt levels
against the global trend.

### EM GDP / DM GDP
**`Y_EM / Y_DM`** · flow/flow · external · ratio

Emerging-market GDP relative to developed-market GDP. At PPP this
crossed 1.0x in 2007 and is now ~1.4x; at market exchange rates
~0.6x and slowly rising. The structural shift in the global economy.

### China GDP / US GDP
**`Y_China / Y_US`** · flow/flow · external · ratio

Bilateral relative size — at market rates ~70%; at PPP ~120% (China
overtook US ~2014 on PPP). Since 2010 the convergence has stalled at
market rates due to USD strength + China's slower growth + yuan
policy. Key cross-asset positioning anchor.

### World M2 / world GDP
**`Σ M2_country / Y_world`** · stock/flow · aggregate · percent

Global broad money relative to world GDP. ~110% today; significant
growth post-2008 + 2020. Tracks the "global liquidity" narrative.
Composition shifts (China weight growing) matter for interpretation
since China's M2/GDP runs ~210% — pulls the global number up.

### World reserves / world GDP
**`Reserves_world / Y_world`** · stock/flow · external · percent

Total foreign reserve assets globally / world GDP. ~14% today; peak
~16% (2014); secular climb 2000–2014, plateau since. The "hot-money
insurance" stock at world level. CB stockpiling has shifted from
China-driven to broader EM diversification.

---

## 17. Demographics

Population structure ratios. Slow-moving but huge structural drivers
of growth, fiscal trajectories, neutral interest rates, and rates
across the curve.

### Old-age dependency ratio
**`Pop_{65+} / Pop_{15-64}`** · stock/stock · aggregate · ratio

Population 65+ as a share of working-age population. US ~28% today;
range 18% (1990) to projected 40% (2060). Italy + Japan running 50%+;
China rising fast (~20% today, projected 50% by 2050). The structural
fiscal pressure on retirement systems lives here.

### Total dependency ratio
**`(Pop_{0-14} + Pop_{65+}) / Pop_{15-64}`** · stock/stock · aggregate · ratio

Total dependents (kids + elderly) per working-age person. US ~55%
today; projected ~70% by 2060. The full demographic burden — youth
dependency falling globally as TFR drops; old-age rising. Net effect
varies by country.

### Working-age population / total population
**`Pop_{15-64} / Pop_{total}`** · stock/stock · aggregate · percent

Productive-age share of population. US ~65%; secular decline from
~67% (2010 peak); projected ~58% by 2060. The mirror of dependency
ratios. The "demographic dividend" is having this number high and
rising; the developed world is past that window.

### Population growth rate
**`Pop_t / Pop_{t-1} − 1`** · growth · aggregate · percent

Annual population growth. US ~0.5% today; pre-2000 ~1%. Below 1% is
the OECD norm. Negative growth in Japan, Italy, Korea, China (as of
2022+). Below-replacement TFR plus aging cohorts → sustained
negative growth eventually.

### Net migration / population
**`(Immigration − Emigration) / Pop`** · flow/stock · aggregate · percent

Net migration rate. US ~0.3% today; varies sharply year-to-year.
The single most important growth-rate variable in advanced economies
where TFR is below replacement — without immigration, US population
growth would already be negative.

### Total fertility rate
**`Births per woman over reproductive lifetime`** · ratio · aggregate · ratio

Average lifetime births per woman. US ~1.6 today; replacement ~2.1.
Below replacement in nearly all advanced economies; Korea at 0.7
(world's lowest). Long-run determinant of working-age population
trajectory.

### Life expectancy at 65
**`E[death age | survived to 65] − 65`** · level · aggregate · years

Expected remaining lifespan at age 65. US ~19 today (~17 male, ~20
female); G7 average ~21. Slow trend up since 1950 (~13 then). Pension
system accounting depends critically on this — a 1-year increase
adds ~5% to NPV of obligations.

---

## 18. Growth accounting

The Solow decomposition of growth into capital deepening, labor
input, and TFP. The standard framework for thinking about long-run
growth sources. Mostly per-capita / per-hour ratios + contribution
shares.

### Real GDP per capita (level)
**`Y_real / Pop`** · flow/stock · aggregate · level (real $)

Standard cross-country welfare comparison. US ~$72K (2025) vs. OECD
median ~$55K. The "level" metric across countries — converges via
catch-up in EM, plateaus at the frontier in DM. PPP-adjusted version
controls for price-level differences.

### Real GDP per capita growth (yoy)
**`(Y_real/Pop)_t / (Y_real/Pop)_{t-4} − 1`** · growth · aggregate · percent

Per-capita growth — what you get from real GDP growth minus
population growth. US trend ~1.5%; below pre-2000 ~2%. The "living-
standards-improvement" rate. Below 1% in much of Europe since 2008.

### Real GDP per worker
**`Y_real / Employment`** · flow/stock · aggregate · level (real $)

Output per employed person — productivity by employment count. US
~$140K. Differs from per-hour by hours-per-worker (varies across
countries — Europe works fewer hours, so per-hour productivity is
higher than per-worker would suggest).

### Real GDP per hour worked
**`Y_real / Hours_worked`** · flow/flow · aggregate · level (real $/hr)

Labor productivity at hourly level. The cleanest cross-country
productivity comparison (controls for hours differences). US ~$75/hr;
Eurozone ~$65/hr; Japan ~$50/hr. The post-2020 US productivity
acceleration is a real anomaly.

### Total factor productivity growth
**`TFP_t / TFP_{t-1} − 1`** · growth · aggregate · percent

The Solow residual — the share of output growth not explained by
capital + labor inputs. US ~0.8% trend; range 0–2%; the post-2020
estimates are ~1.5%. The fundamental long-run driver of welfare
gains; capital deepening alone has diminishing returns. BLS
multifactor productivity series.

### Capital deepening contribution to growth
**`Δ(K/L) × capital share`** · flow/flow · aggregate · ppts of GDP growth

Annual contribution of K/L growth to labor productivity, weighted
by capital's share of income. US ~0.5–1ppt today. Has been
shrinking post-2008 (low investment cycle) — partly explains the
productivity slowdown of the 2010s.

### Labor input contribution to growth
**`Δ(Labor input) × labor share`** · flow/flow · aggregate · ppts of GDP growth

Annual contribution of total labor input growth (hours × quality)
to GDP. US ~0.5ppt today; pre-2008 ~1ppt. Reflects falling LFPR +
slower employment growth + composition shifts.

### Hours worked / population
**`Hours_total / Pop`** · stock/stock · aggregate · percent

Aggregate workforce intensity. US ~25% (annual hours per capita
~1300 / total hours-in-year × 1). Different across countries:
France ~20%; US ~25%; Korea ~30%. A "structural workforce
engagement" measure that complements LFPR.

### Manufacturing share of GDP
**`Y_manufacturing / Y`** · flow/flow · aggregate · percent

US ~10% today; pre-1990 ~20%; secular decline as services share
rose. The "deindustrialization" gauge. Different in Germany ~22%,
Korea ~28%, China ~28%. Among the most-debated structural
indicators in industrial policy debates.

### Services share of GDP
**`Y_services / Y`** · flow/flow · aggregate · percent

US ~80% today (services value-added share). Mirror of manufacturing
+ agriculture. Services-share-of-employment runs higher (~85%) than
services-share-of-output (~80%) because services are typically
lower productivity (Baumol's cost disease).

---

## 19. SFC closure variables (G&L direct)

Variables featured directly in the Godley-Lavoie SFC closure
identities. Some are levels rather than ratios, but they appear as
ratios in the model equations (price/unit-cost markup, real wage
W/P, inventory/sales σ, Tobin allocation shares).

### Real wage rate (W/P)
**`Wage_nominal / Price index`** · flow/flow · households · level (real $/hr)

Real hourly wage. US ~$28/hr in 2017 dollars (BLS production +
nonsupervisory). Levels matter as much as growth — real-wage
stagnation 1973–1995 was the canonical "decoupling from
productivity" story. Recovery 1995–2000 + post-2014 has narrowed
the gap.

### Markup ratio (P / unit cost)
**`Price / Marginal cost`** · ratio · nfc · ratio

Unit-output price relative to marginal/unit cost. Aggregate US has
risen from ~1.20 (1980) to ~1.45–1.55 (today) — De Loecker–Eeckhout
estimates. The "rise of market power" thesis lives in this number.
Highly contested measurement; results depend on cost definitions.

### Inventory-to-sales ratio (σ)
**`Inventories / Monthly sales`** · stock/flow · nfc · multiple (months)

The "G&L target" in the DIS model + standard NIPA tracker. US ~1.4
months today; range 1.2–1.7. Spikes during recessions (sales drop
faster than inventories adjust). The cyclical leading indicator most
referenced in recessionary debates.

### HH cash + deposits / HH wealth
**`(Cash + Deposits)_HH / NW_HH`** · stock/stock · households · percent

Household liquidity preference at portfolio level. US ~10% today;
pre-2020 ~9%; 2020 spike to ~12%. The G&L "Tobin row" — share of
HH wealth held in money form. Rises during uncertainty
(precautionary), falls in risk-on regimes.

### HH bonds / HH wealth
**`Bonds_HH / NW_HH`** · stock/stock · households · percent

Direct + intermediated bond holdings as share of HH wealth. US ~6%
today; range 5–10%. Includes Treasuries + corporates + munis +
agency. Lower than equity share because bonds are disproportionately
held in pensions (separately classified in NW composition).

### HH equities / HH wealth
**`Equities_HH / NW_HH`** · stock/stock · households · percent

Household direct + indirect equity holdings as share of net worth.
US ~30% today; pre-1995 ~15%; structural climb reflects
financialization + retirement-savings shift. Concentrated at top —
median HH has near-zero direct equity; top 1% holds ~50% of wealth
in equities.

### Average tax rate (θ)
**`T_HH_total / Y_HH_pretax`** · flow/flow · households · percent

The G&L exogenous tax rate parameter. US ~18% today (federal +
state + local on personal income). Cross-country range: 35%+ in
Nordics; 20% in US; 15% in many EM. Different from marginal rate
(top bracket — ~40%+ federal+state+local in US for high earners).

### Reserve requirement ratio (ρ)
**`Required reserves / Reservable deposits`** · ratio · banks · percent

The G&L compulsory reserve ratio. US ~0% today (eliminated March
2020); pre-2020 was ~10% on transaction deposits >$127M. Elsewhere:
China ~7% (post-2024 cuts); India ~4.5%. With abundant reserves the
ratio is largely defunct as a binding constraint in the US — the
Fed sets reserve targets via balance-sheet policy, not reserve
requirements.

---

## 20. Sectoral balance sheet composition

Within-sector composition shares — how a sector's balance sheet is
structured. Stock/stock ratios at the highest level of sectoral
breakdown. Distributional implications follow directly.

### HH real estate / HH net worth
**`Real Estate_HH / NW_HH`** · stock/stock · households · percent

Aggregate housing share of HH wealth. US ~30%; bottom 50% have ~50%+
of wealth in housing; top 1% have ~10%. The "housing equity" share
is the single most important wealth-distribution structural ratio —
explains why house-price moves have asymmetric wealth-effect
transmission.

### HH financial assets / HH net worth
**`FA_HH / NW_HH`** · stock/stock · households · percent

Mirror of real estate share (excluding consumer durables). US ~70%;
top 10% have ~80%+ in financial assets; bottom 50% ~20%. The
distributional split between housing-rich vs. financial-rich HHs
shapes the wealth-effect transmission of asset prices.

### HH equity / HH financial assets
**`Equities_HH / FA_HH`** · stock/stock · households · percent

Equity share of HH financial portfolio. US ~45%; pre-1995 ~25%.
Includes direct + mutual funds + ETF + retirement-account equity.
Cyclical: rises with equity rallies, falls in selloffs (composition
+ valuation). Captures the "risk-on" allocation.

### HH cash + deposits / HH financial assets
**`Liquid_HH / FA_HH`** · stock/stock · households · percent

Liquid share of HH financial portfolio. US ~13%; range 10–18%. Rises
in uncertainty regimes (2008, 2020). The "dry powder" allocation
households can rapidly redeploy.

### HH pension entitlements / HH net worth
**`Pension_HH / NW_HH`** · stock/stock · households · percent

Retirement-wealth share of total HH wealth. US ~15%; secular climb
from ~6% (1980). Reflects DC-plan growth + IRA expansion. The
"long-horizon" share — generally less liquid, more risk-bearing
than other wealth pools.

### HH durables / HH net worth
**`Durables_HH / NW_HH`** · stock/stock · households · percent

Consumer durables (vehicles + appliances) as share of HH net worth.
US ~5%. Slow-moving structural number. Sometimes treated as
intermediate consumption rather than wealth, depending on accounting
boundary; NIPA / Z.1 treat it as wealth for HH net-worth purposes.

### NFC retained earnings / NFC profits (retention ratio)
**`Retained earnings / Profits_post-tax`** · flow/flow · nfc · percent

Share of after-tax profits retained by corporations. US ~50% today;
pre-1990 ~70%. Mirror of payout ratio. The structural decline in
retention reflects the buyback shift — capital returned to
shareholders rather than reinvested.

### NFC dividends + buybacks / NFC profits (total payout ratio)
**`(Div + Buyback) / Profits_post-tax`** · flow/flow · nfc · percent

Total cash returned to shareholders as share of after-tax profits.
US ~90% today (vs. ~40% in 1980). The structural climb is the
"financialization of the firm" — corporations distribute most
earnings rather than retain. Cyclical — peaks at 110%+ near cycle
ends (debt-funded buybacks).

---

## Coverage notes — what's missing after v1+v2

After v1 (10 themes / ~100 ratios) and v2 (10 themes / ~91 ratios),
the highest-level NIPA / SFC / national-accounting / global-macro
surface is largely covered. The following are deferred to v3+
because they are either market microstructure (price/quote-side),
sector-granular (within-sector cuts), or distributional cuts by
demographic group rather than wealth/income percentile:

- **Volatility ratios**: VIX-implied vol / realized; vol-of-vol;
  cross-asset vol regimes; MOVE / VIX ratio (rates-equity vol)
- **Curve / spread structure**: 2s10s, 3m10y, swap spreads, IG/HY
  ratio, EM/DM spread, real / nominal curve, inflation-breakeven
  curve, term premium (model-derived)
- **Sector granularity**: per-industry value added shares (mfg
  subsectors, services subsectors, energy share, finance share);
  per-industry employment shares
- **Real-estate granular**: housing starts / completions; months of
  supply; rent / income; vacancy rates; price-to-rent; price-to-
  income (regional); cap-rate by property type
- **Tax granular**: payroll / income / corporate / excise / customs
  shares of total revenue; effective tax rates by quintile;
  tax-burden by income source (labor vs capital)
- **Distributional demographic**: shares by race / education / region;
  saving rates by quintile; debt-service ratios by quintile;
  wealth-to-income by group; intergenerational mobility metrics
- **Crypto / digital**: stablecoin market cap / total liquid USD;
  crypto total / global equity cap; on-chain transaction volume /
  GDP; CBDC adoption rates
- **Energy / commodity**: oil consumption / GDP; energy intensity
  (BTU/GDP); commodity terms-of-trade by sector; mineral self-
  sufficiency (production / consumption)
- **Climate / sustainability**: green bond issuance / total bond;
  ESG AUM share; carbon intensity (CO2/GDP); transition-risk
  exposure as share of bank assets
- **Banking granular**: deposit beta by bank size; branch density;
  fintech adoption / total payments; non-bank financial assets /
  bank assets (shadow-banking proportion)
- **Insurance**: P&C premiums / GDP, life premiums / GDP,
  reinsurance share, catastrophe-bond market / GDP
- **Income mobility**: intergenerational income elasticity;
  Great-Gatsby curve coordinates per country; regional income
  convergence indices
- **Time-use**: work / leisure / household-production hours per
  capita; informal-sector share of labor

Each block is candidate scope for a future tranche. The heuristic
remains: keep going broad before going deep. v3 will surface another
~100 entries from these buckets in the order the user prioritizes.

