# 09 · Synthesis — The Whole Brain as One System

> Every chapter is a loop. The brain is a small set of feedback loops fighting
> over which one dominates. This doc draws them as one diagram, catalogs them,
> and maps each onto the system-dynamics toy model that will encode it.

---

## 1. The unified causal-loop diagram

```
                    ╔════════════ R1 · THE GREASE ENGINE (reinforcing) ════════════╗
                    ║                                                              ║
        collateral ─╫─► b/s capacity ─► money creation ─► asset supply ─┐         ║
         supply ▲   ║      ▲             (new A–L pairs)                 │         ║
                │   ║      │                                            │         ║
                └───╫──────┴──── asset yields ↑ ─► risk-taking ↑ ───────┘         ║
                    ║         "RISK CROWDS IN RISK"  (assets beget assets)        ║
                    ╚══════════════════════════════════════════════════════════════╝
       HARD MONEY = R1 CAPPED (no printer) ⇒ only the balancers run ⇒ deflation default
       ELASTIC MONEY = R1 dominates ⇒ self-reinforcing monetary inflation (1950s–2008)

   ┌─ B1 · FRICTION self-correct ─┐  ┌─ B2 · DISSAVING speed-bumps ─┐  ┌─ Rsign · RATES⇄NGDP ─┐
   │ price↑ (non-monetary)        │  │ spend↑ via dissaving         │  │ rates↑ = price we pay │
   │  → real demand↓ → Q↓         │  │  → savings↓ to a FLOOR       │  │   each other ↑        │
   │  → promises break → M↓       │  │  → players hit floors        │  │  →[if b/s execute]    │
   │  → price↓     (TRANSITORY)   │  │  → dissave capacity↓         │  │    flow↑, velocity↑,  │
   │                              │  │  → spending↓  (TRANSITORY)   │  │    cheap insurance →  │
   │  asset yields DON'T rise     │  │ + saving is mean-reverting   │  │    risk↑ → NGDP↑ →    │
   └──────────────────────────────┘  └──────────────────────────────┘  │    rates↑    (R!)     │
                                                                        └───────────────────────┘
        consensus draws the last loop BALANCING (rates↑→activity↓).
        the brain draws it REINFORCING. Sign(coupling) is the whole argument.
```

## 2. The stock-flow seesaw (the conserved-quantity constraint)

```
        ┌──────────────────── STOCK ⇆ FLOW ────────────────────┐
        │   STOCK (valuation·wealth·saving)   FLOW (income·spend) │
        │            ╲                            ╱              │
        │             ╲_____________ △ __________╱               │
        │   rate cuts / QE  → tilt STOCK = DEFLATION             │
        │   rate hikes / issuance → tilt FLOW = INFLATION        │
        │   only NEW MONEY (R1) adds to BOTH pans simultaneously │
        └────────────────────────────────────────────────────────┘
```

## 3. The policy-inversion spectrum

```
   LESS risk / LESS money (deflation)        MORE risk / MORE money (inflation)
   ◄══════════════════════════════════════════════════════════════════════►
      Deficit REDUCTION                          Deficit EXPANSION
      QE                                         QT
      Rate CUTS                                  Rate HIKES
      HIGH asset prices (low yields)             CHEAP assets (high yields)

   the Fed acts CYCLICALLY (risk-additive). The FISCAL authority is the true
   counter-cyclical force (austerity when risk is abundant; expand when scarce).
```

## 4. The loops catalog — mental model → loop → expected behavior

```
  MENTAL MODEL (ch)        LOOP        DOMINANT DYNAMIC        SHOULD PRODUCE
  ─────────────────────────────────────────────────────────────────────────────
  Collateral engine (01)   R1          crowd-in reinforcing    runaway expansion
                                                                vs capped → deflation
  Income/velocity (02)     B2          savings-floor balancer  damped → transitory
                                                                (settles the Bob debate)
  Reserves (03)            n/a         swap, not a loop         no change to R1
  Three balance sheets(04) R1 + shock  hidden-leg collapse      regime collapse →
                                                                post-cyclical
  Stock-flow (05)          constraint  conserved seesaw         reallocation ≠ creation
  QE (06)                  B (insurance) area-under-curve ↓     low yields shrink risk
  Rate hikes (07)          Rsign       rates⇄NGDP coupling      +corr; hikes stimulative
  Volcker / FDNE (08)      observer    regime / signaling       "control" = appearance
```

## 5. Bridge to the system-dynamics models

> Decisions already made: substrate = a Godley-table SFC core that compiles to
> ODEs (solved with scipy, in the `pk_model.py` style — see
> [../../converted/tykeynes/pk_model.py](../../converted/tykeynes/pk_model.py)).
> First model = the collateral crowd-in engine. Lineage corpus:
> [../../converted/sfc/papers/](../../converted/sfc/papers/) (Keen, Godley, shadow-banking SFC).

```
   build order (each toy model encodes one loop above):
     1  COLLATERAL ENGINE      (R1)  elastic vs hard money; self-reinforcing vs deflation
     2  4-PLAYER DISSAVING     (B2)  the numbered step-table; transitory by savings floor
     3  THREE BALANCE SHEETS   (R1+shock) with a LATENT M_unobservable the in-sim
                                      "policymaker" cannot observe (reproduce 2008 → post-cyclical)
     4  STOCK-FLOW SEESAW       (constraint) conserved pool; QE/cuts vs issuance/hikes
     5  RATES⇄NGDP             (Rsign) toggle the coupling sign; reproduce +Δrates/Δcredit corr
     6  QE / INSURANCE          (B)  area-under-curve; 6% vs 2% bond payout budget
     7  VOLCKER / FDNE          (observer) rates-as-conditions vs rates-as-policy
```

### Where the brain is novel vs the Keen/Minsky lineage

```
   INHERITED                              ORIGINAL EXTENSIONS
   ─────────────────────────────────     ───────────────────────────────────────
   endogenous money (banks create)        COLLATERAL/b-s SPACE is the binding
   Godley double-entry / SFC               constraint (not the debt/GDP ratio)
   Minsky rising-fragility                a HIDDEN STATE: true money = observable +
   Goodwin/Keen limit cycles &             UNOBSERVABLE; the sim knows it, the
   debt-deflation breakdown                in-sim policymaker only sees a proxy
                                          POLICY SIGN-FLIPS (hikes=ease, QE=tighten)
                                          RATES⇄NGDP mutually reinforcing
```

## 6. Open threads (the unfinished edges — flagged, not asserted)

```
   from ch.07 (the rough chapter) and cross-chapter:
     ▸ the MPC rebuttal is stubbed ("every dollar is already allocated to spending")
     ▸ "rates⇄NGDP are binary black holes" wants a dedicated "Bonds/Curves are
       inflation" piece that isn't in the current 8
     ▸ "risk crowd-in" is spread across ch.04/05/07 with no single home
     ▸ Bridgewater rebuttal + 1930s liquidity-preference example not yet integrated
   epistemics worth naming (where the framework's weight rests):
     ▸ the UNOBSERVABILITY SHIELD — "we can't measure true money, so reason from
       mechanics" — explains anomalies but is hard to falsify directly
     ▸ the CROWD-IN claim replacing crowd-out carries every policy inversion
```

---

Back to: [README.md](README.md) · [00_overview.md](00_overview.md)
