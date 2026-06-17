# MOORE: HETERODOX MACROECONOMIC MODELING FRAMEWORK

## Overview

Basil Moore's "Shaking the Invisible Hand" provides the theoretical foundation for Post-Keynesian/heterodox stock-flow consistent (SFC) macroeconomic modeling. This is the framework that distinguishes SFC modeling from mainstream DSGE approaches.

## Core Theoretical Pillars

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║                    MOORE'S FRAMEWORK                          ║
║                                                               ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 1. COMPLEXITY vs EQUILIBRIUM                            │ ║
║  │    Economies are complex adaptive systems                │ ║
║  │    → No equilibrium, process analysis only               │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 2. ENDOGENOUS MONEY, EXOGENOUS INTEREST RATES           │ ║
║  │    Money created by credit, CB sets BR                   │ ║
║  │    → Reverse causation: Y → M, not M → Y                │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 3. SAVING ≡ INVESTMENT (Identity)                       │ ║
║  │    S is accounting record of I, not independent         │ ║
║  │    → I creates S, not S enables I                        │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 4. MARKUP PRICING, HORIZONTAL AS                        │ ║
║  │    Prices = markup over costs, sticky                    │ ║
║  │    → Output demand-determined                             │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 5. SECTORAL BALANCES & SFC                              │ ║
║  │    (S-I)+(G-T)+(M-X)≡0, stock-flow consistency          │ ║
║  │    → Govt deficit = Private surplus                      │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 6. DEMAND-LED GROWTH                                    │ ║
║  │    Investment drives growth, AD always matters          │ ║
║  │    → No SR/LR dichotomy                                  │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                          ↓                                    ║
║  ┌─────────────────────────────────────────────────────────┐ ║
║  │ 7. REJECTION OF MAINSTREAM AXIOMS                       │ ║
║  │    Ergodicity, neutrality, gross substitution all false │ ║
║  │    → Need new paradigm                                   │ ║
║  └─────────────────────────────────────────────────────────┘ ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## The Documents

### Part 1: Complexity vs Equilibrium
**File:** `moore_01_complexity_vs_equilibrium.md`

**Key points:**
- Economies are complex adaptive systems (CAS)
- Sensitive dependence on initial conditions
- No equilibrium exists or is approached
- Unit roots in all macro time series
- Process analysis replaces equilibrium analysis
- Prediction impossible, understanding possible

**When to reference:** Understanding WHY equilibrium analysis fails, WHY we must use dynamic simulation

### Part 2: Endogenous Money & Exogenous Interest Rates
**File:** `moore_02_endogenous_money.md`

**Key points:**
- Money multiplier theory is backwards
- Loans create deposits (not reserves create deposits)
- CB sets Bank Rate, not money supply
- Working capital finance drives money creation
- Horizontalism vs Verticalism
- Money accommodates activity, doesn't cause it

**When to reference:** Modeling monetary sector, understanding credit creation, setting interest rates in models

### Part 3: Saving ≡ Investment
**File:** `moore_03_saving_equals_investment.md`

**Key points:**
- S ≡ I as accounting identity (always)
- Most saving is non-volitional (convenience lending + capital gains)
- Investment creates its own saving
- No "Keynesian multiplier" (multiplier = 1)
- Loanable funds theory refuted
- Direction: I → S, not S → I

**When to reference:** Understanding consumption/investment dynamics, explaining how deficit spending is financed, avoiding loanable funds errors

### Part 4: Markup Pricing & Horizontal AS
**File:** `moore_04_markup_pricing.md`

**Key points:**
- Prices = (1+μ)·(W/A)
- Flat marginal cost curves (empirically verified)
- Prices sticky (median: 1 year)
- Prices respond to costs, not demand
- Output responds to demand, not costs
- AS curve is horizontal (as stylized fact)

**When to reference:** Price dynamics, inflation modeling, understanding why output is demand-determined

### Part 5: Sectoral Balances & Stock-Flow Consistency
**File:** `moore_05_sectoral_balances.md`

**Key points:**
- (S-I) + (G-T) + (M-X) ≡ 0
- Govt deficit = Private surplus (exactly)
- Consistent capital budgeting required
- Financial assets net to zero
- Every flow has source & destination
- Double-entry bookkeeping in Godley tables

**When to reference:** Multi-sector models, government finance, external sector, ensuring accounting closure

### Part 6: Demand-Led Growth
**File:** `moore_06_demand_led_growth.md`

**Key points:**
- No SR/LR dichotomy (LR is cumulative SR)
- Investment drives growth (K accumulation)
- Productivity endogenous (Verdoorn Law)
- No "natural rate" of unemployment
- Unit roots prove demand matters permanently
- Interest rates crucially important

**When to reference:** Growth dynamics, understanding long-run behavior, policy for raising growth

### Part 7: Critique of Mainstream
**File:** `moore_07_critique_of_mainstream.md`

**Key points:**
- DSGE fundamentally flawed (no money, no banks, assumes equilibrium)
- Representative agent fallacy
- Ergodicity assumption false
- Positivism inappropriate for complex systems
- Econometric data mining problems
- Rigor vs relevance false trade-off

**When to reference:** Understanding what's WRONG with mainstream, why we need alternative approach

### Part 8: SFC Architecture
**File:** `moore_08_sfc_architecture.md`

**Key points:**
- Three-layer structure (balance sheets, transactions, behaviors)
- Godley table mechanics and implementation
- Stock-flow integration methods (Euler, RK4)
- Temporal sequencing of computations
- Closure rules (demand vs supply)
- Nominal-real accounting
- Accounting closure checks

**When to reference:** Building model structure, implementing Godley tables, ensuring consistency

### Part 9: Nonlinear Dynamics
**File:** `moore_09_nonlinear_dynamics.md`

**Key points:**
- Sources of nonlinearity (products, ratios, saturations)
- Limit cycles (Goodwin predator-prey)
- Chaos (Keen's 3D extension)
- Bifurcations and regime changes
- Hysteresis and path dependence
- Multiple equilibria
- Phase diagram analysis

**When to reference:** Understanding complex dynamics, analyzing instability, Minsky moments

### Part 10: Financial Dynamics
**File:** `moore_10_financial_dynamics.md`

**Key points:**
- Debt accumulation equation: dD/dt = I - Π + i·D
- Debt ratio dynamics and sustainability
- Minsky's three regimes (Hedge, Speculative, Ponzi)
- Credit rationing and pro-cyclical leverage
- Monetary circuit (creation and destruction)
- Kalecki profit equation
- Financial accelerator mechanism

**When to reference:** Modeling debt, financial instability, credit cycles, Minsky moments

### Part 11: System Dynamics Patterns
**File:** `moore_11_system_dynamics_patterns.md`

**Key points:**
- Stock-flow chain patterns
- Co-flow patterns (nominal-real pairs)
- Lagged adjustment (first-order lags)
- Buffer stock dynamics
- Ratio dynamics formulation
- Multiplier-accelerator interaction
- Feedback loop architecture
- Time delay implementation

**When to reference:** Implementing specific dynamics, wiring models, creating realistic lags

### Part 12: Calibration Techniques
**File:** `moore_12_calibration_techniques.md`

**Key points:**
- Steady-state calibration from ratios
- Numerical steady-state finding
- Moment matching to data
- Parameter sensitivity analysis
- Impulse response functions
- Scenario analysis (not forecasting)
- Diagnostic ratio checks
- Progressive calibration strategy

**When to reference:** Calibrating models, validating results, sensitivity testing, debugging

## The Logical Flow

```
    HOW THE PIECES FIT TOGETHER
    ═══════════════════════════
    
    [1] Economies are COMPLEX (Part 1)
         │
         ├─→ ∴ No equilibrium analysis (Part 1)
         ├─→ ∴ Forecast impossible (Part 1)
         └─→ ∴ Need process analysis (Part 1)
         
         
    [2] Money is ENDOGENOUS (Part 2)
         │
         ├─→ ∴ Credit creates purchasing power (Part 2)
         ├─→ ∴ Investment not constrained by prior S (Part 3)
         └─→ ∴ I creates S via credit creation (Part 3)
         
         
    [3] Prices are STICKY, markup-based (Part 4)
         │
         ├─→ ∴ Output adjusts to demand (Part 4)
         ├─→ ∴ AS curve horizontal (Part 4)
         └─→ ∴ Economy is demand-constrained (Part 4)
         
         
    [4] Accounting IDENTITIES constrain (Part 5)
         │
         ├─→ ∴ Govt deficit = Private surplus (Part 5)
         ├─→ ∴ S ≡ I in all sectors (Part 5)
         └─→ ∴ Stock-flow consistency essential (Part 5)
         
         
    [5] Demand determines GROWTH (Part 6)
         │
         ├─→ ∴ Investment key to growth (Part 6)
         ├─→ ∴ No SR/LR dichotomy (Part 6)
         └─→ ∴ AD matters permanently (Part 6)
         
         
    [6] Mainstream is WRONG (Part 7)
         │
         ├─→ ∴ Reject GE analysis (Part 7)
         ├─→ ∴ Reject rational expectations (Part 7)
         └─→ ∴ Need new paradigm (Parts 1-6)
```

## How This Differs from DSGE

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ DSGE/Mainstream            │ Moore/Post-Keynesian         ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                            │                              ┃
┃ Equilibrium always         │ Perpetual disequilibrium     ┃
┃ Ergodic (calculable risk)  │ Non-ergodic (uncertainty)    ┃
┃ Rational expectations      │ Conventional expectations    ┃
┃ Representative agent       │ Heterogeneous agents         ┃
┃ Exogenous money            │ Endogenous money             ┃
┃ Endogenous interest rates  │ Exogenous interest rates     ┃
┃ Loanable funds             │ Credit creation              ┃
┃ S enables I                │ I creates S                  ┃
┃ Flexible prices            │ Sticky prices (markup)       ┃
┃ Supply-determined LR       │ Demand-led always            ┃
┃ Vertical LR Phillips Curve │ No vertical PC               ┃
┃ Natural rates exist        │ No natural rates             ┃
┃ SR/LR dichotomy            │ LR is cumulative SR          ┃
┃ Microfoundations essential │ Emergent macro properties    ┃
┃ Comparative statics        │ Dynamic simulation           ┃
┃ Closed-form solutions      │ Computer simulation          ┃
┃ Predict future             │ Understand processes         ┃
┃                            │                              ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Practical Modeling Implications

```
    WHAT THIS MEANS FOR YOUR MINSKY MODELS
    ══════════════════════════════════════
    
    ✓ DO:
    ─────
    
    □ Model in calendar time (date all variables)
    □ Use process analysis (ΔY_t → ΔY_{t+1})
    □ Include banks and credit creation explicitly
    □ Make money endogenous (loans create deposits)
    □ Set interest rates exogenously (CB policy)
    □ Use markup pricing (P = (1+μ)·ULC)
    □ Model AS as horizontal (quantity adjusts to demand)
    □ Ensure S ≡ I as identity (not equilibrium)
    □ Maintain sectoral balance identities
    □ Ensure stock-flow consistency (Godley tables)
    □ Make investment respond to expected AD
    □ Allow permanent effects of shocks (unit roots)
    □ Include animal spirits (non-measurable expectations)
    
    
    ✗ DON'T:
    ────────
    
    □ Solve for "equilibrium" positions
    □ Assume money is exogenous
    □ Use loanable funds (S finances I)
    □ Make saving a behavioral function
    □ Assume flexible prices clearing markets
    □ Use upward-sloping AS curve
    □ Separate "short run" and "long run" analysis
    □ Assume rational expectations
    □ Use representative agent
    □ Assume ergodicity
    □ Try to "predict" long-run outcomes
    □ Ignore accounting identities
```

## The Theoretical Architecture

```
    FOUNDATION LEVEL: Complexity & Uncertainty
    ══════════════════════════════════════════
    
    Economies = Complex Adaptive Systems
    Future = Fundamentally unknowable
    Distributions = Non-ergodic (change over time)
    Expectations = Animal spirits (not calculable)
    
              ↓ (Implies)
              
    METHODOLOGICAL LEVEL: Process Analysis
    ══════════════════════════════════════
    
    Historical time (not logical time)
    First differences (not levels)
    Ordinal forecasts (not cardinal)
    Simulation (not closed-form solution)
    Understanding (not prediction)
    
              ↓ (Applied to)
              
    MONETARY LEVEL: Endogenous Money
    ════════════════════════════════
    
    Loans create deposits
    Credit demand determines M
    CB sets BR (interest rate)
    Money accommodates activity
    
              ↓ (Finances)
              
    FLOW LEVEL: Investment & Demand
    ═══════════════════════════════
    
    I driven by expected AD (animal spirits)
    I financed by credit creation
    I creates S (identity, not equilibration)
    AD determines Y (output)
    
              ↓ (Determined by)
              
    PRICE LEVEL: Markup Pricing
    ═══════════════════════════
    
    P = (1+μ)·(W/A)
    π = Ẇ/W - Ȧ/A
    Prices sticky, cost-driven
    AS horizontal
    
              ↓ (Accumulates into)
              
    STOCK LEVEL: Capital & Growth
    ═════════════════════════════
    
    K̇ = I - δK
    Growth driven by I
    I driven by AD
    ∴ Growth is demand-led
    
              ↓ (Constrained by)
              
    ACCOUNTING LEVEL: Sectoral Balances
    ═══════════════════════════════════
    
    (S-I) + (G-T) + (M-X) ≡ 0
    Stock-flow consistency
    Godley tables
    Double-entry bookkeeping
```

## Contrast with Mainstream at Each Level

```
    LEVEL          │ MAINSTREAM           │ MOORE/POST-KEYNESIAN
    ───────────────┼──────────────────────┼─────────────────────
    Epistemology   │ Positivism           │ Realism
                   │ (prediction)         │ (understanding)
                   │                      │
    Ontology       │ Atomistic            │ Holistic
                   │ (micro→macro)        │ (emergent properties)
                   │                      │
    Method         │ Equilibrium          │ Process analysis
                   │ (comparative static) │ (dynamic simulation)
                   │                      │
    Time           │ Logical time         │ Historical time
                   │ (reversible)         │ (irreversible)
                   │                      │
    Money          │ Neutral veil         │ Credit creation
                   │ Exogenous M          │ Endogenous M
                   │                      │
    Interest rates │ Market-determined    │ CB policy instrument
                   │ (endogenous)         │ (exogenous)
                   │                      │
    Saving/Invest  │ Independent          │ Identity (S≡I)
                   │ S enables I          │ I creates S
                   │                      │
    Prices         │ Flexible             │ Sticky markup
                   │ Market-clearing      │ Cost-driven
                   │                      │
    Output         │ Supply-determined    │ Demand-determined
                   │ (capacity)           │ (AD)
                   │                      │
    Growth         │ Supply-side          │ Demand-led
                   │ (saving, tech)       │ (investment, AD)
                   │                      │
    Unemployment   │ Natural rate         │ Demand-deficiency
                   │ (structural)         │ (cyclical always)
                   │                      │
    Policy         │ Supply-side          │ Demand management
                   │ (deregulate)         │ (fiscal, BR)
```

## Reading Order for Learning

```
    FOR THEORETICAL FOUNDATIONS:
    ════════════════════════════
    
    1. Start with Part 1 (Complexity)
       → Understand WHY equilibrium is wrong
       
    2. Then Part 7 (Critique)
       → See what's wrong with mainstream
       
    3. Then Parts 2-6 in order
       → Build up the positive alternative
       
       
    FOR PRACTICAL MODELING:
    ═══════════════════════
    
    1. Part 8 (SFC Architecture)
       → Learn model structure, Godley tables
       
    2. Part 5 (Sectoral Balances)
       → Get accounting framework right
       
    3. Part 2 (Endogenous Money)
       → Model financial sector correctly
       
    4. Part 11 (System Dynamics Patterns)
       → Common modeling patterns
       
    5. Part 10 (Financial Dynamics)
       → Debt, credit, Minsky moments
       
    6. Part 9 (Nonlinear Dynamics)
       → Understand complex behaviors
       
    7. Part 12 (Calibration)
       → Calibrate and validate models
       
       
    FOR BUILDING YOUR FIRST MODEL:
    ══════════════════════════════
    
    1. Part 8 (SFC Architecture) - Structure
    2. Part 11 (SD Patterns) - Components
    3. Part 12 (Calibration) - Parameter setting
    4. Part 5 (Sectoral Balances) - Accounting checks
    5. Part 10 (Financial Dynamics) - If modeling finance
```

## Key Equations Summary

```
╔═══════════════════════════════════════════════════════════════╗
║  ESSENTIAL EQUATIONS FROM MOORE                              ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  MONETARY:                                                    ║
║    ΔM ≈ Δ(W·L) + Δ(Materials) + Δ(Inventories)             ║
║    BR = exogenous (CB sets)                                  ║
║    Lending rate = BR + markup                                 ║
║                                                               ║
║  SAVING-INVESTMENT:                                           ║
║    S ≡ I  (identity, always)                                 ║
║    S ≡ Y - C  (definition)                                   ║
║    Most S is non-volitional                                   ║
║                                                               ║
║  SECTORAL BALANCES:                                           ║
║    (S-I) + (G-T) + (M-X) ≡ 0                                ║
║    Private surplus = Govt deficit + Foreign surplus          ║
║                                                               ║
║  PRICING:                                                     ║
║    P = (1+μ)·(W/A)                                           ║
║    π = Ẇ/W - Ȧ/A  (when μ stable)                          ║
║                                                               ║
║  GROWTH:                                                      ║
║    ẏ = (I/Y)·(Y/K) - δ + Verdoorn effect                    ║
║    I/Y driven by expected AD                                 ║
║                                                               ║
║  UNIT ROOTS:                                                  ║
║    Y_t ≈ Y_{t-1} + ε_t  (ρ ≈ 1.0)                          ║
║    Best forecast: Y_{t+1} = Y_t                              ║
║                                                               ║
║  DEBT DYNAMICS:                                               ║
║    dD/dt = I - Π + i·D                                       ║
║    ḋ = d·[(I-Π)/D + i - ẏ]                                  ║
║    Sustainable if: i·d < ẏ·d                                ║
║                                                               ║
║  STOCK-FLOW INTEGRATION:                                      ║
║    S(t) = S_0 + ∫ f(S,t) dt                                 ║
║    Use RK4 for accuracy                                       ║
║                                                               ║
║  FIRST-ORDER LAGS:                                            ║
║    dX/dt = (X* - X)/τ                                        ║
║    Half-life = 0.69·τ                                        ║
║                                                               ║
║  RATIO DYNAMICS:                                              ║
║    ṙ = r·(Ẋ/X - Ẏ/Y)  for r = X/Y                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## Key Quotes (Moore's Greatest Hits)

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  "Complex adaptive systems can be simulated but never        ║
║   solved."                                                    ║
║                                                               ║
║  "The central message of this book is that members of the    ║
║   economics profession currently operate with a basically    ║
║   incorrect paradigm of the way modern banking systems       ║
║   operate."                                                   ║
║                                                               ║
║  "Changes in wages and employment largely determine the      ║
║   demand for bank loans, which in turn determine the rate    ║
║   of growth of the money supply. Central banks have no       ║
║   alternative but to accept this course of events."          ║
║                                                               ║
║  "Saving is the accounting record of investment."            ║
║                                                               ║
║  "In the real world banks extend credit, creating deposits   ║
║   in the process. And look for the reserves later."          ║
║   (quoting Fed official Alan Holmes)                          ║
║                                                               ║
║  "The supply of credit money is credit-driven and is         ║
║   horizontal as some markup on Bank Rate."                    ║
║                                                               ║
║  "There is no long run. The long run is merely a series of   ║
║   short runs." (quoting Abba Lerner)                         ║
║                                                               ║
║  "Inflation is always and everywhere a symptom of the        ║
║   struggle over the distribution of income."                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## For the Agent: Essential Mindset Shifts

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  MENTAL MODEL FOR SFC MODELER                               ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                             ┃
┃  When building models, ALWAYS ask:                         ┃
┃                                                             ┃
┃  1. "Does this assume equilibrium?"                        ┃
┃     If yes → REJECT, use process analysis                  ┃
┃                                                             ┃
┃  2. "Where does money come from?"                          ┃
┃     Answer must be: "Credit creation"                      ┃
┃     Not: "Exogenous M" or "Loanable funds"                ┃
┃                                                             ┃
┃  3. "Does S ≡ I hold as identity?"                         ┃
┃     Must be true ALWAYS, not just "in equilibrium"         ┃
┃                                                             ┃
┃  4. "Are sectoral balances consistent?"                    ┃
┃     (S-I)+(G-T)+(M-X) ≡ 0 must hold every period          ┃
┃                                                             ┃
┃  5. "How are prices determined?"                           ┃
┃     Answer: Markup over costs, sticky                      ┃
┃     Not: Market clearing, flexible                          ┃
┃                                                             ┃
┃  6. "What determines output?"                              ┃
┃     Answer: AD (demand-side)                               ┃
┃     Not: Production function (supply-side)                  ┃
┃                                                             ┃
┃  7. "What drives growth?"                                   ┃
┃     Answer: Investment (driven by AD expectations)         ┃
┃     Not: Saving rate or exogenous productivity             ┃
┃                                                             ┃
┃  8. "Can I predict long-run outcome?"                      ┃
┃     Answer: NO (complex system, path-dependent)            ┃
┃     But: Can understand dynamics and ordinal changes       ┃
┃                                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## The Moore Paradigm in One Diagram

```
                    HETERODOX MACRO PARADIGM
                    ════════════════════════
                    
                         [Animal Spirits]
                         (Expectations of
                          future AD)
                               │
                    ┌──────────┴──────────┐
                    ↓                     ↓
              [Investment]          [Consumption]
                    │                     │
                    ├─────────┬───────────┤
                    ↓         │           ↓
              Demand for      │      Aggregate
              bank credit     │      Demand (AD)
                    │         │           │
                    ↓         │           ↓
              Money supply    │      Output (Y)
              (endogenous)    │           │
                    │         │           ├─→ Employment
                    │         │           ├─→ Capacity use
                    │         │           └─→ Income (Y)
                    │         │
                    ↓         ↓
              [Capital      [Saving]
               Stock K]     (≡ Investment)
                    │
                    ├─→ Y_potential
                    └─→ Productivity (A)
                    
    
    Prices (P) determined separately:
    
    [Wage bargaining] → W
                        │
                        ↓
                   ULC = W/A
                        │
                        ↓ (markup)
                      P = (1+μ)·ULC
                        │
                        ↓
                   Inflation = Ẇ/W - Ȧ/A
                   
                   
    Central Bank policy:
    
    [CB] → BR → Lending rates → Investment
                              → AD
                              → Growth
                              
                              
    KEY FEEDBACKS:
    
    Y ↔ AD  (output responds to demand)
    I → K → Y_potential  (investment creates capacity)
    Y → A  (Verdoorn Law)
    AD → I  (accelerator)
    M accommodates all  (endogenous money)
```

## What Moore Enables You To Do

```
    WITH MOORE'S FRAMEWORK, YOU CAN:
    ════════════════════════════════
    
    ✓ Explain monetary phenomena correctly
      (credit creation, role of banks)
      
    ✓ Analyze financial instability
      (Minsky moments, debt dynamics)
      
    ✓ Understand why austerity fails
      (paradox of thrift, S≡I identity)
      
    ✓ Model realistic price dynamics
      (sticky prices, cost-driven inflation)
      
    ✓ Analyze demand-deficient unemployment
      (no natural rate, AD matters)
      
    ✓ Study growth as demand-led process
      (investment drives growth)
      
    ✓ Maintain accounting consistency
      (sectoral balances, SFC)
      
    ✓ Avoid equilibrium fallacies
      (process analysis instead)
      
    ✓ Model realistic agent behavior
      (bounded rationality, animal spirits)
      
    ✓ Simulate complex dynamics
      (nonlinear, path-dependent)
      
      
    WITHOUT MOORE, YOU'RE STUCK WITH:
    ════════════════════════════════
    
    ✗ Quantity theory confusion (M causes PY)
    ✗ Loanable funds errors (S enables I)
    ✗ Supply-side dogma (saving determines growth)
    ✗ Natural rate myths (NAIRU)
    ✗ Equilibrium fantasies (system never gets there)
    ✗ Representative agent fallacies
    ✗ Rational expectations impossibilities
    ✗ Mainstream policy failures
```

## Integration with Minsky Software

```
    MOORE THEORY → MINSKY IMPLEMENTATION
    ════════════════════════════════════
    
    Moore Concept              Minsky Implementation
    ─────────────              ─────────────────────
    
    Endogenous money     →     Godley tables with bank sector
                               Loans create deposits explicitly
                               
    S ≡ I identity       →     Balance sheets sum to zero
                               Stock-flow consistency enforced
                               
    Sectoral balances    →     Multi-table Godley structure
                               (S-I)+(G-T)+(M-X)≡0 checked
                               
    Markup pricing       →     P = (1+μ)·(W/A) equation
                               μ as parameter, stable
                               
    Horizontal AS        →     Y determined by AD
                               No capacity constraint until Q_max
                               
    Demand-led Y         →     I → K → Y_potential
                               Verdoorn effects
                               
    Process analysis     →     All variables dated
                               Integral blocks for stocks
                               No "equilibrium" solving
                               
    Interest rate policy →     BR as parameter (slider)
                               Banks markup over BR
                               
    Animal spirits       →     ε parameter in I function
                               Can shock exogenously
```

## Final Synthesis

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║              MOORE'S HETERODOX PARADIGM                       ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  Economics is a MONETARY PRODUCTION economy                  ║
║  where CREDIT enables deficit spending,                       ║
║  INVESTMENT creates saving and capacity,                      ║
║  DEMAND determines output and growth,                         ║
║  PRICES are sticky and cost-driven,                          ║
║  BANKS create money endogenously,                            ║
║  CENTRAL BANKS set interest rates,                            ║
║  ACCOUNTING identities constrain flows,                       ║
║  and the FUTURE is fundamentally uncertain                    ║
║  so EQUILIBRIUM never occurs and                             ║
║  PREDICTION is impossible but                                 ║
║  UNDERSTANDING is achievable through                          ║
║  PROCESS ANALYSIS and SIMULATION                             ║
║  of NONLINEAR DYNAMICS over CALENDAR TIME.                   ║
║                                                               ║
║  This is the foundation of Post-Keynesian                    ║
║  Stock-Flow Consistent macroeconomic modeling.               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
