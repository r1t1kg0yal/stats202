# Harvey Module 05: Domestic Investment Cycle

> **Sources:** `pieces/Harvey_UsingtheGeneralTheorytoExplaintheUSBusinessCycle.md`, `pieces/Harvey_SystemDynamcicsTradeModel.md`, `pieces/Harvey_ModelingFinancialCrises.md`  
> **Use:** Domestic macro layer for investment-led expansions, endogenous recessions, and real-financial crisis triggers.

---

## Core Claim

Investment is the unstable driver of the business cycle. The expansion creates the conditions for its own reversal because expected profits rise with animal spirits while realized profits eventually moderate as the stock of physical capital grows, capital costs rise, and investment opportunities become less attractive. Recession begins when optimistic forecasts are disappointed.

```
┌──────────────────────────────────────────────────────────────────────┐
│                   HARVEY / KEYNES TRADE CYCLE                        │
├──────────────────────────────────────────────────────────────────────┤
│  Recession memories fade                                             │
│      ↓                                                               │
│  Animal spirits recover                                              │
│      ↓                                                               │
│  Expected profit from investment rises                               │
│      ↓                                                               │
│  Investment rises                                                    │
│      ↓                                                               │
│  GDP / sales / realized profits rise                                 │
│      ↓                                                               │
│  Optimism strengthens                                                │
│      ↓                                                               │
│  Capital stock and costs rise                                        │
│      ↓                                                               │
│  Realized profit from new investment moderates                       │
│      ↓                                                               │
│  Expected profits are disappointed                                   │
│      ↓                                                               │
│  Investment collapses                                                │
└──────────────────────────────────────────────────────────────────────┘
```

## Why Investment Is Central

Harvey's reading of Keynes' Chapter 22 puts investment at the center because consumption is too stable to generate the cycle by itself. Investment is forward-looking, debt-financed, and dependent on profit expectations formed under uncertainty.

| Variable | Role |
|---|---|
| Consumption share | Tends to fall as income rises; cannot carry expansion alone |
| Interest rates | Secondary and inconsistent; can complicate but usually do not initiate |
| Capital-goods prices | Rise as bottlenecks appear, reducing investment incentive |
| Expected profits | Primary driver of investment decisions |
| Realized profits | Validation test for prior forecasts |
| Capital stock | Accumulates faster than depreciation/tastes/technology create new opportunities |

## Capital Saturation Loop

```
┌──────────────────────────────────────────────────────────────┐
│       B1: Capital Saturation Balancing Loop                  │
│                                                              │
│   Expected profit from investment rises                      │
│       │                                                      │
│       ▼                                                      │
│   Investment rises                                           │
│       │                                                      │
│       ▼                                                      │
│   Stock of physical capital rises                            │
│       │                                                      │
│       ▼                                                      │
│   Remaining high-return projects decline                     │
│       │                                                      │
│       ▼                                                      │
│   Realized profit from new investment moderates              │
│       │                                                      │
│       ▼                                                      │
│   Expected profit from investment falls ───────────────┐     │
│                                                        │     │
│       ┌────────────────────────────────────────────────┘     │
│       ▼                                                      │
│   Investment falls                                           │
└──────────────────────────────────────────────────────────────┘

BREAKS WHEN:
────────────
Expected profits remain high while realized profits moderate
  → disappointment becomes undeniable
  → optimism flips into pessimism
  → investment collapses
```

This is not a claim that the economy reaches full satiation of capital needs. Keynes' point is narrower: the profit motive can collapse before full-employment capital needs are met because investors no longer believe incremental projects will validate prior expectations.

## Realized vs Expected Profits

```
Expansion start:
  realized profit > depressed expectations
  → pleasant surprise
  → optimism rises

Late expansion:
  realized profit may still be acceptable in absolute terms
  but realized profit < optimistic expectations
  → disappointment
  → investment reversal
```

The gap matters more than the level. A profit outcome that would have looked good in recession can trigger panic if it disappoints boom-time forecasts.

## System Dynamics Interpretation

Harvey uses system dynamics because the trade cycle is a historical-time feedback system, not a static equilibrium problem.

```
Stocks:
  [capital stock]
  [debt commitments]
  [confidence / memory of crisis]

Flows:
  (investment)
  (depreciation)
  (loan creation / repayment)

Auxiliaries:
  expected profit
  realized profit
  interest rate pressure
  capital-goods costs
```

The model is iterative and path dependent:

```
past investment → current capital stock → current expected return
past profits    → current confidence    → current investment
past crisis     → current caution       → current margins of safety
```

## Financial Amplifier

The real investment cycle becomes a financial crisis mechanism when optimistic investment expectations are financed by debt.

```
Investment boom
  → credit expansion
  → debt commitments rise
  → realized profits initially validate debt
  → lenders/borrowers lower margins of safety
  → speculative/Ponzi finance increases
  → realized profits disappoint
  → refinancing fails
  → defaults / fire sales / credit contraction
```

This is the domestic analog of the open-economy fragility tension in Module 03.

## Empirical Pattern Harvey Tests

In the U.S. business-cycle paper, Harvey tests whether late expansions show the Keynesian pattern:

| Indicator | Expected late-expansion behavior |
|---|---|
| Consumption / GDP | Declines or becomes less supportive |
| Investment growth | Moderates |
| Capital-goods price inflation | Rises |
| Interest rates | Often rise, but secondary |
| Realized profit growth | Moderates or turns negative |
| Business optimism | Remains positive enough to create disappointment |

The key empirical signature is not "investment is low." It is "investment and realized profits decelerate while optimism has not yet capitulated."

## Operational Checklist

For a capex boom or domestic cycle:

1. Identify whether investment is driving the expansion or merely following demand.
2. Track realized profit growth against expected profit narratives.
3. Watch capital stock/capacity relative to demand, not just current spending.
4. Track capital-goods cost pressure and financing demand.
5. Ask whether the boom's own investment is reducing future expected returns.
6. If debt financed, add the Minsky validation layer: can cash flows service the commitments created during the boom?

