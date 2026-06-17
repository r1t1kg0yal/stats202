# Harvey Module 02: Expectations, Mental Models, and Bandwagons

> **Sources:** `pieces/Harvey_CurrenciesCapitalFlowsCrises.md`, `pieces/Harvey_FXDuringGreatRecession.md`  
> **Use:** Forecast-formation layer for Harvey FX analysis and the bridge to positioning/narrative brains.

---

## Core Claim

Exchange-rate expectations are causal. They are not noise around a known fundamental value. Agents forecast under fundamental uncertainty, using shared mental models, heuristics, conventions, and recent price action. Those forecasts drive portfolio flows; portfolio flows move exchange rates; exchange-rate moves feed back into the forecasts.

```
┌──────────────────────────────────────────────────────────────────────┐
│                    EXPECTATIONS ARE A PRICE INPUT                    │
├──────────────────────────────────────────────────────────────────────┤
│  New information                                                     │
│      ↓                                                               │
│  Filtered through shared mental model                                │
│      ↓                                                               │
│  Short-term forecast update                                          │
│      ↓                                                               │
│  Medium-term attractor: bullish / bearish / neutral                  │
│      ↓                                                               │
│  Portfolio flow                                                      │
│      ↓                                                               │
│  Exchange-rate move                                                  │
│      ↓                                                               │
│  Price action becomes new information                                │
└──────────────────────────────────────────────────────────────────────┘
```

## Mental Model Stack

Harvey's currency trader does not optimize from a complete model of the world. The trader uses a practical forecasting stack.

```
┌──────────────────────────────┐
│ BASE FACTORS                  │
│ rates, growth, liquidity,     │
│ asset returns, trade, policy  │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ INDICATORS                    │
│ data releases, price moves,   │
│ news, official statements     │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ SHORT-TERM FORECAST           │
│ fast-moving interpretation    │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│ MEDIUM-TERM ATTRACTOR         │
│ bullish / bearish / neutral   │
│ lens for future information   │
└──────────────────────────────┘
```

The attractor matters because it changes how evidence is weighted:

| Attractor | Market behavior |
|---|---|
| Bullish | Pro-currency news is magnified; adverse news is discounted |
| Bearish | Adverse news is magnified; supportive news is discounted |
| Neutral | News has more symmetric impact; price is more data-sensitive |

## Heuristic Biases

Harvey imports psychology into FX because agents lack objective probability distributions.

| Bias | Market expression |
|---|---|
| Availability | Dramatic recent events dominate forecast weight |
| Representativeness | Small samples are treated as regime evidence |
| Anchoring | Forecasts anchor to recent levels or recent changes |
| Animal spirits | Agents act despite inadequate knowledge |
| Convention | Shared market stories become self-validating until challenged |
| Credit/blame | Career incentives make crowd-following safer than solitary dissent |

These are not simple mistakes that disappear through arbitrage. If the whole market shares the bias, the bias becomes part of the price-forming mechanism.

## Bandwagon Loop

```
┌──────────────────────────────────────────────────────────────┐
│       R1: FX Bandwagon / Momentum Feedback                   │
│                                                              │
│   Currency appreciates                                       │
│       │                                                      │
│       ▼                                                      │
│   Recent price action becomes available evidence             │
│       │                                                      │
│       ▼                                                      │
│   Medium-term attractor turns more pro-currency              │
│       │                                                      │
│       ▼                                                      │
│   Portfolio inflows increase                                 │
│       │                                                      │
│       ▼                                                      │
│   Further currency appreciation ───────────────────────┐     │
│                                                        │     │
│       ┌────────────────────────────────────────────────┘     │
│       ▼                                                      │
│   Trend-following and confirming narratives strengthen        │
└──────────────────────────────────────────────────────────────┘

CONSTRAINT:
───────────
[Confidence in the trend] ──┤ [Position size] ──╳ [Bandwagon continuation]

BREAKS WHEN:
────────────
Contrary evidence accumulates
  → mental-model forecast and actual exchange rate diverge
  → confidence collapses
  → capital flow reverses
```

## Profit-Taking Whipsaw

Harvey's bandwagon is not a smooth trend. Traders fear losing paper gains, so even persistent trends are punctuated by reversals.

```
Sustained appreciation
  → paper profits
  → anxiety about reversal
  → profit taking
  → short interruption
  → trend resumes if attractor remains intact
```

This makes short-horizon FX look noisy even when the medium-term attractor is strong.

## Forecast Confidence

Confidence determines whether forecast differences become capital flows.

```
Expected return gap × confidence × liquidity = realized position pressure
```

The expected return gap can be large, but if confidence is weak the flow may be too small to close the gap. This is the expectation-formation bridge between the bandwagon model and UIP failure.

## Operational Translation

When applying Harvey:

1. Separate the raw factor from the interpreted factor. A rate hike matters through the mental model built around it.
2. Identify the medium-term attractor before scoring news. The same data point has different price impact under a bullish vs bearish lens.
3. Treat price action as an input to expectations, not only an output of fundamentals.
4. Watch for evidence that confirming news stops moving price; that can mean the attractor is exhausted.
5. Track confidence. Low-confidence forecasts create UIP deviations and incomplete arbitrage; high-confidence forecasts create bandwagons.

