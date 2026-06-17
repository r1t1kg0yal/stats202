# MOORE PART 8: STOCK-FLOW CONSISTENT ARCHITECTURE

## The Core SFC Principle

```
╔═══════════════════════════════════════════════════════════════╗
║  EVERY FLOW COMES FROM SOMEWHERE AND GOES SOMEWHERE          ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Stocks (S):  Accumulated quantities                         ║
║    • Capital: K_t = K_0 + ∫(I - δK) dt                      ║
║    • Debt:    D_t = D_0 + ∫(ΔD) dt                          ║
║    • Money:   M_t = M_0 + ∫(ΔM) dt                          ║
║                                                               ║
║  Flows (F):  Rates of change                                 ║
║    • Investment: I_t = dK/dt + δK                           ║
║    • Borrowing: ΔD_t = dD/dt                                ║
║    • Money creation: ΔM_t = dM/dt                           ║
║                                                               ║
║  CONSISTENCY REQUIREMENT:                                     ║
║    Sum of all flows into stock = Sum of all flows out       ║
║    + Change in stock                                          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## The Transaction Matrix (Godley Tables)

```
    ANATOMY OF A GODLEY TABLE
    ═════════════════════════
    
    Columns: Balance sheet items (stocks)
    Rows:    Transactions (flows)
    Entries: Changes in stocks from each transaction
    
    
    Example: Simple Firm-Household-Bank Model
    ──────────────────────────────────────────
    
                    FIRMS                 HOUSEHOLDS           BANKS
                    ─────                 ──────────           ─────
                    Assets │ Liab │ NW    Assets │ Liab │ NW  Assets │ Liab │ NW
    ────────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    1. Prod & Sales        │      │               │      │             │      │
       GDP flows     +Y    │      │        -Y     │      │             │      │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    2. Consumption         │      │               │      │             │      │
       HH consume    -C    │      │        +C     │      │             │      │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    3. Investment          │      │               │      │             │      │
       Firms invest  +I    │      │               │      │             │      │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    4. Wages               │      │               │      │             │      │
       Wage bill     -WL   │      │        +WL    │      │             │      │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    5. Bank Loans          │      │               │      │             │      │
       Firms borrow       │ +ΔL  │               │      │        +ΔL  │ +ΔM │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
    6. Deposits            │      │               │      │             │      │
       HH accumulate +ΔM  │      │        +ΔM    │      │             │ +ΔM │
       ────────────────────┼──────┼────────────────┼──────┼──────────────┼──────┼────
                          │      │               │      │             │      │
    ROW SUM (must = 0):    0      0               0      0             0      0
    
    
    CHECKS:
    ───────
    
    □ Every row sums to zero (flow conservation)
    □ A - L - E = 0 for each sector
    □ ΔAssets - ΔLiabilities - ΔNW = 0 each sector
    □ One sector's asset = Another's liability (financial assets)
```

## The Three-Layer Architecture

```
    SFC MODEL STRUCTURE (Godley-Lavoie Framework)
    ═════════════════════════════════════════════
    
    LAYER 1: BALANCE SHEETS (Stocks, at point in time)
    ──────────────────────────────────────────────────
    
    For each sector s:
    
        A_s = L_s + NW_s
        
        ┌─────────────┬─────────────┬──────────┐
        │ Assets      │ Liabilities │ Net Worth│
        ├─────────────┼─────────────┼──────────┤
        │ K (capital) │ Loans       │          │
        │ M (deposits)│ Deposits    │ NW       │
        │ B (bonds)   │ Bonds       │          │
        └─────────────┴─────────────┴──────────┘
        
        A_s - L_s - NW_s = 0  ✓
        
    Global: Σ_s (Financial Assets) = Σ_s (Financial Liabilities)
            (Real assets are net worth)
    
    
    LAYER 2: TRANSACTION FLOWS (Changes in stocks over period)
    ───────────────────────────────────────────────────────────
    
    For each sector s:
    
        ΔNW_s = ΔA_s - ΔL_s
        
        Each transaction creates flows:
        
        ┌──────────────────┬─────┬──────┬────┐
        │ Transaction      │ ΔA  │ ΔL   │ ΔNW│
        ├──────────────────┼─────┼──────┼────┤
        │ Wage payment     │ -WL │      │-WL │
        │ Consumption      │ -C  │      │-C  │
        │ Investment       │ +I  │      │+I  │
        │ Bank borrowing   │ +ΔM │ +ΔL  │  0 │
        └──────────────────┴─────┴──────┴────┘
        
        Row sum = 0 each transaction
        
    
    LAYER 3: BEHAVIORAL EQUATIONS (Determine flow magnitudes)
    ──────────────────────────────────────────────────────────
    
    For each flow f:
    
        f = g(stocks, other flows, parameters, expectations)
        
        Examples:
        
        C = α·Y_d  (consumption function)
        I = f(π, u, BR, ε_animal_spirits)  (investment)
        ΔL = ΔW·L + ΔInventories  (loan demand)
        W_growth = φ(e)  (Phillips curve)
```

## The Fundamental Equation Structure

```
    DIFFERENTIAL EQUATIONS (Continuous Time)
    ════════════════════════════════════════
    
    For each stock S_i:
    
        dS_i/dt = Σ Inflows_i - Σ Outflows_i
        
        
    Example: Capital stock
    
        dK/dt = I - δK
        
        where:
            I = Gross investment (inflow)
            δK = Depreciation (outflow)
            
            
    In Minsky: Use integral blocks
    
        [I - δK] ──→ ∫ ──→ [K]
                     ↑
                     │ K_0 (initial condition)
                     
                     
    INTEGRATION:
    
        K(t) = K_0 + ∫_0^t (I(τ) - δ·K(τ)) dτ
```

## Stock-Flow Norms (Godley's Ratios)

```
╔═══════════════════════════════════════════════════════════════╗
║  TYPICAL STOCK-FLOW RATIOS (Steady State)                   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Capital-Output Ratio:                                       ║
║    K/Y ≈ 3.0    (capital stock ≈ 3× annual output)          ║
║                                                               ║
║  Debt-GDP Ratio:                                             ║
║    D/Y ≈ 1.5    (private debt ≈ 150% of GDP)                ║
║                                                               ║
║  Money-GDP Ratio:                                            ║
║    M/Y ≈ 0.6    (money supply ≈ 60% of GDP)                 ║
║                                                               ║
║  Investment-GDP:                                              ║
║    I/Y ≈ 0.20   (investment ≈ 20% of GDP)                   ║
║                                                               ║
║  Government Debt-GDP:                                         ║
║    B_g/Y ≈ 0.8  (govt debt ≈ 80% of GDP)                    ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

    FLOW CONSISTENCY CHECKS:
    ════════════════════════
    
    In steady state (stocks/GDP constant):
    
    If K/Y = k (constant), then:
    
        d(K/Y)/dt = 0
        
        ∴ K̇/K = Ẏ/Y
        
        ∴ (I - δK)/K = ẏ
        
        ∴ I/K = ẏ + δ
        
        ∴ I/Y = (ẏ + δ)·(K/Y) = (ẏ + δ)·k
        
        
    Example: If k = 3, ẏ = 3%, δ = 5%
    
        I/Y = (0.03 + 0.05)·3 = 0.24 = 24%
        
        
    This is ACCOUNTING, not theory
    Ratios must be internally consistent!
```

## Matrix Representation

```
    GODLEY'S TRANSACTION MATRIX (General Form)
    ══════════════════════════════════════════
    
              │ Sector 1      │ Sector 2      │ ... │ Sector N      │ Σ
              │ A │ L │ NW    │ A │ L │ NW    │     │ A │ L │ NW    │
    ──────────┼───┼───┼───────┼───┼───┼───────┼─────┼───┼───┼───────┼───
    Flow 1    │   │   │       │   │   │       │     │   │   │       │ 0
    Flow 2    │   │   │       │   │   │       │     │   │   │       │ 0
    ...       │   │   │       │   │   │       │     │   │   │       │
    Flow m    │   │   │       │   │   │       │     │   │   │       │ 0
    ──────────┼───┼───┼───────┼───┼───┼───────┼─────┼───┼───┼───────┼───
    Σ         │ΔA│ΔL │ ΔNW   │ΔA│ΔL │ ΔNW   │     │ΔA│ΔL │ ΔNW   │ 0
              │   │   │= 0    │   │   │= 0    │     │   │   │= 0    │
              
              
    CLOSURE REQUIREMENTS:
    ────────────────────
    
    Horizontal (each row):     Σ_j (entry_ij) = 0
    Vertical (each sector):    ΔA - ΔL - ΔNW = 0
    Global (all fin. assets):  Σ_s ΔA_fin = Σ_s ΔL_fin
    
    
    IMPLEMENTATION:
    ──────────────
    
    In Minsky:
    
    1. Create Godley table for each sector
    2. Name columns (stock variables)
    3. Add rows (transactions)
    4. Enter flow expressions
    5. Check A-L-E column = 0 for each row
    6. Copy flow variables to canvas
    7. Wire behavioral equations
```

## Temporal Structure: Stock-Flow Sequencing

```
    TIME STRUCTURE IN SFC MODELS
    ════════════════════════════
    
    Period t-1          Period t           Period t+1
    ──────────────────────────────────────────────────
    
    Stocks_{t-1}  →  Flows_t  →  Stocks_t  →  Flows_{t+1}
    (Given)          (Computed)   (Updated)    (Computed)
    
    
    WITHIN-PERIOD SEQUENCE:
    ──────────────────────
    
    [1] READ stocks from t-1:
        K_{t-1}, M_{t-1}, D_{t-1}, W_{t-1}, etc.
        
    [2] COMPUTE flows for period t:
        Based on behavioral equations
        
        Example:
        Y_t = (K_{t-1}/ν) · u_t
        C_t = α · Y_d,t
        I_t = f(π_{t-1}, u_t, BR_t)
        ΔL_t = I_t - Π_t  (if I > profits)
        ΔM_t = ΔL_t       (loans create deposits)
        
    [3] CHECK accounting:
        (S-I)_t + (G-T)_t + (M-X)_t = 0  ?
        All Godley rows sum to 0 ?
        
    [4] UPDATE stocks for t:
        K_t = K_{t-1} + I_t·Δt - δ·K_{t-1}·Δt
        M_t = M_{t-1} + ΔM_t·Δt
        D_t = D_{t-1} + ΔL_t·Δt
        W_t = W_{t-1} + Ẇ_t·Δt
        
    [5] ADVANCE to t+1
        t ← t + Δt
        Go to [1]
```

## Integration Methods for Stocks

```
    NUMERICAL INTEGRATION (Minsky uses Runge-Kutta)
    ═══════════════════════════════════════════════
    
    Basic form: S(t+Δt) = S(t) + ∫_t^{t+Δt} f(S,t) dt
    
    
    EULER METHOD (Simplest, first-order):
    ─────────────────────────────────────
    
        S_{t+1} = S_t + f(S_t, t)·Δt
        
        Pros: Simple, fast
        Cons: Unstable for stiff equations, large Δt
        
        
    HEUN METHOD (Second-order):
    ───────────────────────────
    
        k_1 = f(S_t, t)
        k_2 = f(S_t + k_1·Δt, t+Δt)
        
        S_{t+1} = S_t + (k_1 + k_2)/2 · Δt
        
        Pros: Better stability
        Cons: 2× computation per step
        
        
    RUNGE-KUTTA 4 (Fourth-order, Minsky default):
    ──────────────────────────────────────────────
    
        k_1 = f(S_t, t)
        k_2 = f(S_t + k_1·Δt/2, t+Δt/2)
        k_3 = f(S_t + k_2·Δt/2, t+Δt/2)
        k_4 = f(S_t + k_3·Δt, t+Δt)
        
        S_{t+1} = S_t + (k_1 + 2k_2 + 2k_3 + k_4)/6 · Δt
        
        Pros: Excellent accuracy, adaptive step size
        Cons: 4× computation per step
        
        
    CHOICE OF Δt:
    ────────────
    
    Annual models:  Δt = 0.1 year (36 days)
    Quarterly:      Δt = 0.01 year (3.6 days)
    Monthly:        Δt = 0.003 year (1 day)
    
    Rule: Δt should be 1/10 of fastest time constant
```

## Behavioral Equation Patterns

```
    COMMON FUNCTIONAL FORMS IN SFC MODELS
    ═════════════════════════════════════
    
    1. LINEAR (Simple, baseline)
    ────────────────────────────
    
        Y = α + β·X
        
        Example: C = C_0 + c·Y_d
        
        Pros: Tractable, stable
        Cons: No saturation, can go negative
        
        
    2. PROPORTIONAL (Zero intercept)
    ────────────────────────────────
    
        Y = β·X
        
        Example: I = k·Y  (accelerator)
        
        Pros: Simple
        Cons: No autonomous component
        
        
    3. LOGISTIC (Bounded response)
    ──────────────────────────────
    
        Y = Y_max / (1 + e^{-k(X - X_0)})
        
        Example: e_response = 1/(1 + e^{-λ(Y-Y_0)})
        
        Pros: Natural bounds [0, Y_max]
        Cons: More parameters, needs calibration
        
        
    4. PIECEWISE LINEAR (Kinked)
    ────────────────────────────
    
        Y = { Y_1  if X < X*
            { Y_2  if X ≥ X*
            
        Example: Capacity constraint
        
            Y = min(Y_demand, Y_capacity)
            
        Pros: Captures regime changes
        Cons: Discontinuous derivatives
        
        
    5. EXPONENTIAL (Growth/decay)
    ─────────────────────────────
    
        Ẏ/Y = α  →  Y(t) = Y_0·e^{αt}
        
        Example: A(t) = A_0·e^{α_A·t}  (productivity)
        
        Pros: Natural for growth processes
        Cons: Unbounded, can explode
        
        
    6. TIME CONSTANT (First-order lag)
    ──────────────────────────────────
    
        dY/dt = (1/τ)·(Y* - Y)
        
        Example: P adjusts to P*
        
            dP/dt = (1/τ_P)·(P* - P)
            
        τ = time to close (1-1/e) ≈ 63% of gap
        
        Pros: Intuitive, realistic lags
        Cons: Need to calibrate τ
```

## Handling Expectations (Animal Spirits)

```
    MODELING NON-MEASURABLE EXPECTATIONS
    ════════════════════════════════════
    
    Problem: Animal spirits ε can't be measured
             But they drive investment!
             
             I = I_base(π, u, BR) + ε
             
             
    APPROACH 1: Exogenous Shocks
    ────────────────────────────
    
        ε(t) = 0  (baseline)
        ε(t) = ε_0  for t ∈ [t_shock, t_shock + duration]
        
        Test impulse responses to confidence shocks
        
        
    APPROACH 2: Adaptive/Extrapolative
    ──────────────────────────────────
    
        ε_t = f(ΔY_{t-1}, ΔY_{t-2}, ...)
        
        Example: ε_t = β·(Y_t - Y_{t-4})/Y_{t-4}
                 (extrapolate recent growth)
                 
        Pros: Endogenous expectations
        Cons: Can create instability
        
        
    APPROACH 3: Regime-Switching
    ────────────────────────────
    
        ε_t = { ε_boom   if indicator > threshold
              { ε_normal if threshold_low < indicator < threshold_high
              { ε_slump  if indicator < threshold_low
              
        Example: Switch based on capacity utilization
        
        
    APPROACH 4: Error-Correction
    ────────────────────────────
    
        ε_t = ε_{t-1} + γ·(Y_actual - Y_expected)
        
        Expectations adjust to errors
        
        
    RECOMMENDATION:
    
        Baseline: ε = 0
        Experiments: Shock ε exogenously
        Advanced: Adaptive once baseline works
```

## Feedback Loop Architecture

```
    IDENTIFYING AND MAPPING FEEDBACK LOOPS
    ══════════════════════════════════════
    
    POSITIVE (Reinforcing) Loops:
    ─────────────────────────────
    
        Y ↑ → I ↑ → K ↑ → Y_potential ↑ → Y ↑
        (Growth accelerator)
        
        Variables move in SAME direction around loop
        → Can cause exponential growth or collapse
        → Need counteracting negative loops for stability
        
        
    NEGATIVE (Balancing) Loops:
    ───────────────────────────
    
        Y ↑ → e ↑ → W ↑ → Costs ↑ → P ↑ → Y ↓
        (Inflation constraint)
        
        Variables move in OPPOSITE direction
        → Tend toward some value
        → Create oscillations (predator-prey)
        
        
    MAPPING PROCEDURE:
    ─────────────────
    
    1. List all stocks: K, M, D, W, P, A, N, ...
    
    2. For each stock, identify:
       • What flows affect it?
       • What does it affect?
       
    3. Build dependency graph:
    
        K → Y → Π → I → K  (positive loop)
        Y → e → W → P → Y  (negative loop)
        
    4. Classify loop polarity:
    
       Count negative links around loop
       Even # negatives → Positive loop
       Odd # negatives → Negative loop
       
    5. Predict behavior:
    
       Dominant positive loop → Growth/collapse
       Dominant negative loop → Cycles
       Balanced → Complex dynamics
```

## Time Scales and Separation

```
    MULTI-TIMESCALE DYNAMICS
    ════════════════════════
    
    Different variables adjust at different speeds:
    
    VERY FAST (days):
    ─────────────────
    • Financial asset prices (stocks, bonds, FX)
    • Interest rate expectations
    • Bank reserve positions
    
    τ ≈ days to weeks
    
    
    FAST (months):
    ──────────────
    • Production output (firms adjust to demand)
    • Inventory levels
    • Short-term borrowing
    
    τ ≈ 1-6 months
    
    
    MEDIUM (quarters to years):
    ───────────────────────────
    • Consumption spending
    • Employment hiring/firing
    • Prices (sticky, annual review)
    • Wages (annual bargaining)
    
    τ ≈ 1-2 years
    
    
    SLOW (years to decades):
    ────────────────────────
    • Capital stock (depreciation slow)
    • Technology/productivity
    • Institutions
    • Population
    
    τ ≈ 5-30 years
    
    
    MODELING IMPLICATION:
    ────────────────────
    
    When modeling annual frequency:
    • Treat fast variables as "instantaneous"
    • Treat medium variables as "adjusting"
    • Treat slow variables as "nearly fixed"
    
    Example:
    
        Stock prices: Assume jump to equilibrium (fast)
        Production: Model with lag τ ≈ 0.25 year
        Capital: Model with integral, τ_K = K/(I-δK) ≈ 20 years
```

## Stability Analysis for SFC Models

```
    LINEARIZATION AROUND STEADY STATE
    ═════════════════════════════════
    
    System: dS/dt = F(S)
    
    Steady state S*: F(S*) = 0
    
    Linearize: dΔS/dt ≈ J·ΔS
    
    where J = Jacobian matrix = ∂F_i/∂S_j evaluated at S*
    
    
    Example: 2D system (K, W)
    ─────────────────────────
    
        dK/dt = I(π(K,W)) - δK
        dW/dt = W·φ(e(K,W))
        
        
    Jacobian:
    
        J = [ ∂K̇/∂K    ∂K̇/∂W  ]
            [ ∂Ẇ/∂K    ∂Ẇ/∂W  ]
            
            
    Eigenvalues λ₁, λ₂:
    
        det(J - λI) = 0
        
        λ² - Tr(J)·λ + Det(J) = 0
        
        
    Stability:
    ─────────
    
    • Both Re(λ) < 0  → Stable (returns to S*)
    • Any Re(λ) > 0   → Unstable (moves away from S*)
    • Re(λ) = 0       → Marginal (cycles)
    
    
    For Minsky models:
    
    ∴ Check eigenvalues of Jacobian at steady state
      If unstable BUT bounded → Intentional (Minsky instability)
      If unstable AND unbounded → Bug (fix the model)
```

## Buffer Stock Dynamics

```
    BUFFER STOCKS vs FLOW VARIABLES
    ════════════════════════════════
    
    Buffer stocks absorb short-run mismatches:
    
    
    1. INVENTORIES (Production buffer)
    ──────────────────────────────────
    
        dI_inv/dt = Y - S
        
        where:
            Y = Production rate
            S = Sales rate
            
        Firms target: I_inv/S = i* (desired ratio)
        
        Actual: I_inv/S may deviate
        
        Adjustment: Y adjusts to restore i*
        
            Y = S·(1 + (i* - I_inv/S)/τ_inv)
            
            
    2. MONEY BALANCES (Liquidity buffer)
    ────────────────────────────────────
    
        Households target: M/Y = m* (desired ratio)
        
        Actual: M/Y may deviate (due to credit creation)
        
        Adjustment: Portfolio reallocation
        
            ΔBonds = (M - m*·Y)/τ_portfolio
            
        (Excess money → buy bonds over time)
        
        
    3. EXCESS CAPACITY (Production buffer)
    ──────────────────────────────────────
    
        Firms target: u = u* ≈ 0.80 (80% utilization)
        
        Actual: u = Y/Y_capacity may deviate
        
        Adjustment: Investment responds
        
            I = I_base + κ·(u - u*)·K
            
        (High utilization → invest to expand capacity)
```

## Closure Rules (How to Close the Model)

```
╔═══════════════════════════════════════════════════════════════╗
║  CLOSURE = SPECIFYING WHAT ADJUSTS                           ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  SFC models must specify adjustment mechanisms               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

    DEMAND CLOSURE (Post-Keynesian default):
    ════════════════════════════════════════
    
        Given: P, W (sticky, cost-determined)
               BR (CB policy)
               
        Adjusts: Y (output quantity)
                 
        Mechanism: Firms meet demand, adjust production
        
            Y^S = Y^D  (at given P)
            
            Firms are quantity-takers in product market
            
            
    ALTERNATIVE: SUPPLY CLOSURE (Classical/Neoclassical)
    ════════════════════════════════════════════════════
    
        Given: K, L, A (factors)
        
        Adjusts: P, W (prices clear markets)
        
        Mechanism: Y = F(K, L, A)  (production function)
                   P adjusts until Y^D = Y^S
                   
        (Moore rejects this for modern economies)
        
        
    HYBRID CLOSURES:
    ═══════════════
    
    • Short run: Demand closure
    • Capacity limit: min(Y^D, Y^capacity)
    • Flex-price sector: Supply closure
    • Fix-price sector: Demand closure
```

## Linking Real and Nominal

```
    NOMINAL-REAL ACCOUNTING
    ═══════════════════════
    
    All flows and stocks exist in NOMINAL terms
    "Real" variables are constructed by deflation
    
    
    Y_nominal = P · Y_real
    
    
    PRICE DEFLATORS:
    ───────────────
    
    For different purposes, different deflators:
    
    GDP deflator: P_GDP
        Y_real = Y_nominal / P_GDP
        
    CPI: P_C
        C_real = C_nominal / P_C
        
    Investment deflator: P_I
        I_real = I_nominal / P_I
        
        
    CAPITAL STOCK (Tricky!):
    ───────────────────────
    
    Nominal: K_nominal(t) = Σ_τ I_nominal(τ)·(1-δ)^{t-τ}
    
    Real: K_real(t) = Σ_τ I_real(τ)·(1-δ)^{t-τ}
                    = Σ_τ [I_nominal(τ)/P_I(τ)]·(1-δ)^{t-τ}
                    
    Issue: Different vintages bought at different prices!
    
    
    SOLUTION: Replacement cost valuation
    
        K_real(t) = K_nominal(t) / P_I(t)
        
        (Value existing capital at current prices)
        
        
    For SFC: Track NOMINAL values in Godley tables
             Convert to real for analysis/interpretation
```

## Calibration Strategy

```
    CALIBRATING SFC MODELS TO STEADY STATE
    ══════════════════════════════════════
    
    Goal: Find parameters such that stocks/GDP are constant
    
    
    METHOD 1: Analytical (if possible)
    ──────────────────────────────────
    
    Set all growth rates equal:
    
        K̇/K = Ẏ/Y = ṁ/M = Ḋ/D = ẏ
        
    Then solve:
    
        From I/K = ẏ + δ  and  I/Y = i
        → i = (ẏ + δ)·k  where k = K/Y
        
        From ΔM/M = ẏ_nominal  and  M/Y = m
        → Growth of M consistent with nominal growth
        
        From ΔD = I - Π  and  D/Y = d
        → Profit share must sustain debt ratio
        
        
    METHOD 2: Numerical (complex models)
    ────────────────────────────────────
    
    1. Start with guess for parameters
    
    2. Run model for T periods (T large, e.g., 200 years)
    
    3. Check: Are ratios stabilizing?
    
           K/Y_{t=150→200} ≈ constant?
           D/Y_{t=150→200} ≈ constant?
           
    4. If not, adjust parameters:
    
           If K/Y rising → reduce I/Y (lower investment function)
           If D/Y rising → raise profit share (reduce wage share)
           If M/Y rising → reduce credit demand
           
    5. Iterate until ratios stable
    
    6. THEN calibrate to match empirical values:
    
           Target: K/Y ≈ 3.0
           Achieved: K/Y ≈ 2.5
           → Scale investment function by 3.0/2.5
```

## Consistency Checks (Critical!)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃  ACCOUNTING CLOSURE VERIFICATION                            ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃                                                             ┃
┃  Run these checks EVERY time step:                         ┃
┃                                                             ┃
┃  1. SECTORAL BALANCE:                                      ┃
┃     |(S-I) + (G-T) + (M-X)| < ε  (ε = 1e-6)              ┃
┃                                                             ┃
┃  2. GODLEY ROW SUMS:                                       ┃
┃     |Σ_j entry_ij| < ε  for each row i                    ┃
┃                                                             ┃
┃  3. GODLEY COLUMN (A-L-E):                                 ┃
┃     |A_j - L_j - E_j| < ε  for each sector j              ┃
┃                                                             ┃
┃  4. FINANCIAL ASSET MATCHING:                              ┃
┃     |Σ Financial Assets - Σ Financial Liabilities| < ε    ┃
┃                                                             ┃
┃  5. GDP IDENTITY:                                           ┃
┃     |Y - (C + I + G + X - M)| < ε                         ┃
┃                                                             ┃
┃  6. INCOME IDENTITY:                                        ┃
┃     |Y - (W·L + Π + ...)| < ε                             ┃
┃                                                             ┃
┃  If ANY check fails → STOP, debug before proceeding        ┃
┃                                                             ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Typical Model Structure Template

```
    STANDARD SFC MODEL ARCHITECTURE
    ═══════════════════════════════
    
    ┌─────────────────────────────────────────────────┐
    │ PARAMETERS (Exogenous)                          │
    ├─────────────────────────────────────────────────┤
    │ α_A: Productivity growth                        │
    │ β_N: Population growth                          │
    │ δ: Depreciation rate                            │
    │ μ: Markup                                       │
    │ ν: Capital-output ratio                         │
    │ τ_*: Time constants                             │
    │ BR: Bank rate (CB policy)                       │
    └─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────────────────┐
    │ STOCKS (State variables, integrated)            │
    ├─────────────────────────────────────────────────┤
    │ K: Capital                                      │
    │ M: Money supply                                 │
    │ D: Debt                                         │
    │ W: Wage level                                   │
    │ P: Price level                                  │
    │ A: Productivity index                           │
    │ N: Labor force                                  │
    └─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────────────────┐
    │ FLOWS (Computed each period)                    │
    ├─────────────────────────────────────────────────┤
    │ Y: Output (from AD or K/ν)                      │
    │ C: Consumption (from Y_d, wealth)               │
    │ I: Investment (from π, u, BR, ε)                │
    │ L: Employment (from Y/A)                        │
    │ Π: Profits (from Y - W·L - ...)                 │
    └─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────────────────┐
    │ RATES OF CHANGE (Feed integral blocks)          │
    ├─────────────────────────────────────────────────┤
    │ dK/dt = I - δK                                  │
    │ dM/dt = ΔLoans                                  │
    │ dD/dt = I - Π (if deficit-financed)            │
    │ dW/dt = W·φ(e)  (Phillips curve)                │
    │ dA/dt = α_A·A                                   │
    └─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────────────────┐
    │ INTEGRATION (Minsky integral blocks)            │
    ├─────────────────────────────────────────────────┤
    │ K_t = ∫(dK/dt) dt                               │
    │ M_t = ∫(dM/dt) dt                               │
    │ etc.                                             │
    └─────────────────────────────────────────────────┘
              ↓
    ┌─────────────────────────────────────────────────┐
    │ ACCOUNTING CHECKS (Every period)                │
    ├─────────────────────────────────────────────────┤
    │ S ≡ I ?                                         │
    │ (S-I)+(G-T)+(M-X) ≡ 0 ?                        │
    │ Godley tables balance?                          │
    └─────────────────────────────────────────────────┘
```

## Common Architectural Patterns

```
    PATTERN 1: GOODS MARKET EQUILIBRIUM
    ═══════════════════════════════════
    
    At given P (sticky):
    
        Y^D = C + I + G + X - M
        
        Y^S = min(Y^D, Y_capacity)
        
        Y = Y^S
        
        
    Implementation in Minsky:
    
        [C] ─┐
        [I] ─┤
        [G] ─├─→ [+] ─→ [Y^D]
        [X] ─┤          │
        [M] ─┘          │
                        ├─→ [min] ─→ [Y]
                        │     ↑
        [Y_capacity] ───┘     │
                         (saturation)
                         
                         
    PATTERN 2: MONETARY CIRCUIT
    ═══════════════════════════
    
    Loan creation:
    
        ΔL = Demand for credit
           = ΔW·L + ΔMaterials + ΔI_inventory
           
        ΔM = ΔL  (loans create deposits)
        
        
    Loan repayment (circuit closes):
    
        Repay = (L - L_target)/τ_repay
        
        ΔL = New loans - Repay
        ΔM = ΔL
        
        
    Implementation:
    
        [W·L] ─┐
        [Mat] ─├─→ [+] ─→ [New Loans]
        [ΔInv]─┘          │
                          ├─→ [-] ─→ [ΔL] ─→ ∫ ─→ [L]
                          │    ↑              ║
        [Repay] ──────────┘                  ║
                                             ↓
                                          [ΔM] ─→ ∫ ─→ [M]
                                          
                                          
    PATTERN 3: PORTFOLIO ALLOCATION
    ═══════════════════════════════
    
    Households allocate wealth:
    
        NW = M + B + E  (money, bonds, equities)
        
    Desired shares: m*, b*, e*  (sum to 1)
    
    Actual allocation differs → gradual adjustment
    
        ΔM = (m*·NW - M)/τ_M + ΔNW·m*
        ΔB = (b*·NW - B)/τ_B + ΔNW·b*
        ΔE = (e*·NW - E)/τ_E + ΔNW·e*
        
        
    Implementation:
    
        [NW] ─→ [×m*] ─→ [-] ←─ [M] ─→ [÷τ_M] ─→ [ΔM_adj]
                         ↓                          │
        [ΔNW] ─→ [×m*] ─────────────────────────────┤
                                                     ↓
                                                  [+] ─→ [ΔM]
```

## Practical Implementation Patterns

```
    COMMON EQUATION STRUCTURES
    ══════════════════════════
    
    1. CONSUMPTION (Baseline + Propensity)
    ──────────────────────────────────────
    
        C = C_auto + c_y·Y_d + c_w·NW
        
        where:
            C_auto = autonomous consumption
            c_y = marginal propensity (0.6-0.9)
            c_w = wealth effect (0.01-0.05)
            Y_d = Disposable income
            NW = Net worth
            
            
    2. INVESTMENT (Profit + Accelerator)
    ────────────────────────────────────
    
        I = γ_0 + γ_π·(π - π*) + γ_u·(u - u*) + ε
        
        where:
            γ_0 = baseline investment
            γ_π = profit sensitivity
            π = profit rate = Π/(P·K)
            γ_u = utilization response
            u = Y/(K/ν) = capacity utilization
            ε = animal spirits
            
            
    3. WAGE DYNAMICS (Phillips Curve)
    ─────────────────────────────────
    
        Ẇ/W = Ω + φ(e - e*)
        
        where:
            Ω = autonomous wage push (union power, etc.)
            φ = Phillips slope (0.3-0.8)
            e = L/N = employment rate
            e* = reference employment
            
        Nonlinear form:
        
            φ(e) = φ_0·(e-e_min)/(e_max-e) - φ_1
            
            (Bounded, saturates at extremes)
            
            
    4. PRICING (Markup)
    ───────────────────
    
        P = (1+μ)·(W/A)
        
        Or dynamic:
        
            Ṗ/P = Ẇ/W - Ȧ/A
            
        where μ assumed stable
        
        
    5. CREDIT DEMAND
    ────────────────
    
        ΔL = κ_w·Δ(W·L) + κ_i·I + κ_inv·ΔInventories
        
        where κ's are credit coefficients (0.5-1.0)
        
        
    6. MONEY SUPPLY
    ───────────────
    
        ΔM = ΔL  (loans create deposits)
        
        Or more detailed:
        
            ΔM = ΔLoans + ΔBond_purchases_by_banks
                - ΔLoan_repayments
```

## Error Handling & Bounds

```
    PREVENTING NUMERICAL EXPLOSIONS
    ═══════════════════════════════
    
    1. NON-NEGATIVITY CONSTRAINTS
    ─────────────────────────────
    
        For stocks that can't be negative:
        
            K ≥ 0
            M ≥ 0
            N ≥ 0
            
        Implement with max():
        
            K_new = max(0, K_old + dK·Δt)
            
        Or prevent negative flows:
        
            Consumption = min(C_desired, Y_d + M/Δt)
            (Can't consume more than income + liquidating all money)
            
            
    2. RATIO BOUNDS
    ───────────────
    
        For ratios in [0,1]:
        
            u = Y/Y_cap must be in [0, 1]
            e = L/N must be in [0, 1]
            
        Implement:
        
            u_actual = max(0, min(1, u_computed))
            
            
    3. EXPLOSIVE DEBT PREVENTION
    ─────────────────────────────
    
        If D/Y → ∞, model will crash
        
        Add debt-servicing constraint:
        
            I_feasible = min(I_desired, 
                            Π + ΔL_max)
                            
        where ΔL_max based on debt sustainability:
        
            ΔL_max = (d_max·Y - D)/Δt
            
            
    4. DIVISION BY ZERO PROTECTION
    ──────────────────────────────
    
        π = Π/(P·K + ε_small)  (avoid π=∞ when K=0)
        
        where ε_small = 1e-10
```

## Summary: SFC Architecture Principles

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  ESSENTIAL SFC MODELING ARCHITECTURE                         ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  1. THREE LAYERS: Balance sheets, Transactions, Behaviors    ║
║                                                               ║
║  2. STOCKS via integral blocks (K, M, D, W, P, A)           ║
║                                                               ║
║  3. FLOWS from behavioral equations + accounting             ║
║                                                               ║
║  4. ACCOUNTING CLOSURE enforced every period                 ║
║     • Sectoral balances sum to zero                          ║
║     • Godley tables balance                                   ║
║     • S ≡ I as identity                                      ║
║                                                               ║
║  5. TIME CONSTANTS for realistic adjustment speeds           ║
║                                                               ║
║  6. BUFFER STOCKS (inventories, money, capacity)            ║
║                                                               ║
║  7. FEEDBACK LOOPS mapped and understood                     ║
║                                                               ║
║  8. CALIBRATION to steady-state stock/flow ratios           ║
║                                                               ║
║  9. BOUNDS to prevent explosions                             ║
║                                                               ║
║  10. CHECKS every time step for consistency                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
