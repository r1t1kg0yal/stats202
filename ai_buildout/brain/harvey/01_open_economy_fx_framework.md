# Harvey Module 01: Open-Economy FX Framework

> **Sources:** `pieces/Harvey_CurrenciesCapitalFlowsCrises.md`, `pieces/Harvey_ExchangeRatesTrade.md`, `pieces/Harvey_DeviationsFromUIP.md`  
> **Use:** Core Harvey map for exchange-rate determination, current-account diagnostics, and UIP failures.

---

## Core Claim

Exchange rates are set in the market for financial capital, not in the market for goods and services. The actual exchange rate can diverge from the balanced-trade exchange rate indefinitely because portfolio capital flows are autonomous, expectation-driven, and many times larger than trade flows. Trade adjusts to the currency price financial markets produce; the currency price does not automatically move to restore balanced trade.

```
┌──────────────────────────────────────────────────────────────────────┐
│                      HARVEY FX CAUSAL ORDER                          │
├──────────────────────────────────────────────────────────────────────┤
│  Financial expected return                                           │
│    = interest/asset return - carrying cost + liquidity premium       │
│      + expected currency appreciation                                │
│                                                                      │
│        ↓                                                             │
│  Portfolio capital flows                                             │
│        ↓                                                             │
│  Actual exchange rate (AER)                                          │
│        ↓                                                             │
│  Trade balance at that AER                                           │
│                                                                      │
│  Balanced-trade exchange rate (BTER) is a reference line, not        │
│  an attractor.                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## The Two Exchange Rates

| Object | Meaning | Harvey status |
|---|---|---|
| AER | Actual exchange rate produced by portfolio allocation | Causal market price |
| BTER | Exchange rate that would balance exports and imports at a given income level | Accounting/reference price |

```
Trade balance = f(AER, domestic income, foreign income, relative prices)

But:

AER = f(portfolio capital flows)
portfolio capital flows = f(expected relative returns, confidence, liquidity)

Therefore:

AER can sit left or right of BTER for long periods.
Current account deficits/surpluses are outcomes, not self-correcting errors.
```

## Open-Economy Z-D Skeleton

Harvey embeds FX inside Keynes' nominal effective-demand framework. Firms and households transact in money prices, so nominal income and nominal sales matter directly.

```
┌───────────────────────────────┐
│        DOMESTIC MACRO          │
├───────────────────────────────┤
│ Z = required sales to employ N │
│ D = actual nominal demand      │
│ D = C(N) + I(r, profit_e) + NX │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│      CURRENT ACCOUNT BLOCK     │
├───────────────────────────────┤
│ Exports  ↑ when AER depreciates│
│ Imports  ↑ when income rises   │
│ BTFX = AER needed for X = M    │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│        FX CAPITAL BLOCK        │
├───────────────────────────────┤
│ Net portfolio inflows set AER  │
│ AER then tells importers/exporters│
│ what price they must use       │
└───────────────────────────────┘
```

Key implication: full employment and balanced trade are not built into the system. They are special outcomes that require the financial-capital price of currency to happen to match the real-side trade price.

## Portfolio Return Equation

Harvey adapts Keynes' asset-return logic to currencies:

```
expected return on currency asset
  = own return
  - carrying cost
  + liquidity premium
  + expected appreciation
```

For strategy work, translate this into five buckets:

| Bucket | What to watch |
|---|---|
| Interest return | Rate differentials, expected policy path, carry |
| Asset return | Equity/bond/credit expected return in the currency zone |
| Carrying cost | Capital controls, transaction frictions, balance-sheet cost |
| Liquidity premium | Reserve-currency status, convertibility, market depth, safety bid |
| Expected appreciation | Mental-model forecast, trend, narrative, positioning |

```
Higher expected return on USD assets
  → net demand for USD assets
  → portfolio inflow
  → USD appreciation

Lower expected return or lower confidence in USD forecast
  → net outflow / lower inflow
  → USD depreciation
```

## UIP Failure

Uncovered interest parity fails because the adjustment mechanism assumes more confidence than agents actually possess. Investors may see a return gap but lack enough conviction, liquidity, or mandate capacity to close it.

```
TEXTBOOK UIP:
─────────────
Return gap appears
  → arbitrage capital flows
  → rates/spot/expected spot adjust
  → return gap closes

HARVEY:
───────
Return gap appears
  → agents ask "do I trust the forecast enough?"
  → confidence gap prevents full position size
  → return gap persists inside a tolerance band
```

The confidence gap is not the same as a risk premium. A risk premium must compensate for a specific risk. A confidence gap means agents simply do not know enough to force equality and may allow either side of UIP to appear rich for long periods.

## Decision Rules

| Question | Harvey answer |
|---|---|
| Should FX converge to balanced trade? | No. BTER is a diagnostic, not an attractor. |
| Are trade flows irrelevant? | Not irrelevant, but usually second-order for currency pricing. They can affect expectations. |
| Do interest differentials matter? | Yes, especially among advanced economies, but through portfolio return and expectations, not mechanical UIP. |
| Can higher rates coincide with expected appreciation? | Yes. That is normal when capital inflows and bullish expectations dominate. |
| What is the first object to model? | Expected portfolio return and the mental model behind it. |

## Operational Checklist

When applying Harvey to a currency pair:

1. Identify the AER and a rough BTER/current-account pressure.
2. Decompose relative expected return into rates, asset returns, carrying costs, liquidity premia, and expected appreciation.
3. Ask whether trade data is directly moving portfolios or merely entering the mental model.
4. Treat UIP deviations as possible information about confidence and positioning, not as immediate arbitrage signals.
5. Look for a gap between what the currency is doing and what the mental model would justify; that gap feeds crisis analysis in Module 03.

