# MOORE PART 11: SYSTEM DYNAMICS PATTERNS FOR SFC MODELS

## Stock-Flow Chains (The Building Blocks)

```
    BASIC STOCK-FLOW PATTERN
    ════════════════════════
    
         Inflow              Stock              Outflow
         ──────              ─────              ───────
         
    [Flow_in] ──→ ∫ ──→ [Stock] ──→ [Flow_out]
                  ↑        │
                  │        └──→ [÷τ] (time constant)
                  │
                [S_0] (initial condition)
                
                
    Differential equation:
    
        dS/dt = Flow_in - Flow_out
        
        
    Time constant formulation:
    
        Flow_out = S/τ
        
    where τ = time to exhaust stock at current outflow rate
    
    
    Example: Capital depreciation
    
        dK/dt = I - δ·K
        
        where δ = 1/τ_K = depreciation rate
              τ_K = average lifetime of capital
              
    If τ_K = 20 years → δ = 0.05 (5% per year)
```

## Co-Flow Pattern (Parallel Stocks)

```
    NOMINAL & REAL STOCK PAIRS
    ══════════════════════════
    
    Many stocks exist in both nominal and real terms:
    
    
        Nominal Capital:            Real Capital:
        ────────────────            ─────────────
        
    [I_nom] ──→ ∫ ──→ [K_nom]    [I_real] ──→ ∫ ──→ [K_real]
                 ↑                            ↑
               [K_0]                        [K_0/P_0]
               
               
    Linking equation:
    
        K_nom = P_I · K_real
        
    Or:
        K_real = K_nom / P_I
        
        
    Flows:
    
        I_nom = P_I · I_real
        I_real = I_nom / P_I
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Track NOMINAL in Godley tables                 │
    │  (financial accounting is nominal)              │
    │                                                  │
    │  Compute REAL for economic analysis             │
    │  (productivity, growth, ratios)                 │
    │                                                  │
    │  Both must be consistent:                       │
    │    Nom = P × Real                               │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## The Consumption-Wealth Nexus

```
    CONSUMPTION DYNAMICS (Multiple channels)
    ════════════════════════════════════════
    
    Full specification:
    
        C = C_auto + c_y·Y_d + c_w·NW_{-1} + c_Δw·ΔNW
        
    where:
        C_auto = Autonomous consumption (baseline)
        c_y = MPC out of current income (0.6-0.85)
        Y_d = Disposable income = Y - T
        c_w = MPC out of wealth (0.01-0.05 per year)
        NW_{-1} = Lagged net worth
        c_Δw = MPC out of wealth changes (0.05-0.15)
        ΔNW = Current period wealth change (capital gains)
        
        
    Wiring in Minsky:
    
        [C_auto] ────────────────────┐
                                     │
        [Y] ──→ [-] ←── [T] ──→ [Y_d] ──→ [×c_y] ──┐
                                                    │
        [NW_{-1}] ──→ [×c_w] ───────────────────────┤
                                                    │
        [ΔNW] ──→ [×c_Δw] ──────────────────────────┤
                                                    │
                                                    ↓
                                                  [+] ──→ [C]
                                                  
                                                  
    Wealth stock dynamics:
    
        dNW/dt = S = Y - T - C
        
        [Y] ─┐
             ├─→ [+] ──→ [-] ←── [C] ──→ [dNW/dt] ──→ ∫ ──→ [NW]
        [T] ─┘                                         ↑
                                                       │ NW_0
                                                       
    Creates feedback:
    
        Y ↑ → C ↑ (income effect)
           → NW ↑ (more saving)
           → C ↑ next period (wealth effect)
```

## The Investment-Capital-Output Chain

```
    CORE REAL-SIDE DYNAMICS
    ═══════════════════════
    
    [1] Investment determination:
    
        I = I_0 + γ_π·(π - π*) + γ_u·(u - u*) + ε
        
        Depends on:
        • π = Π/(P·K) = profit rate
        • u = Y/(K/ν) = capacity utilization
        • ε = animal spirits
        
        
    [2] Capital accumulation:
    
        dK/dt = I - δ·K
        
        
    [3] Output from capital:
    
        Y_potential = K/ν  (ν = capital-output ratio)
        
    Or with utilization:
    
        Y = u·(K/ν)
        
    where u ∈ [0, 1] determined by AD
    
    
    [4] Utilization feedback:
    
        u = Y^D/(K/ν)
        
    If u > u* (above target):
        → I ↑ (invest to expand capacity)
        → K ↑ over time
        → Y_potential ↑
        → u ↓ back toward u*
        
        
    COMPLETE LOOP:
    
    [ε] ────────────────────┐
                            ↓
    [π] ──→ [I function] ──→ [I] ──→ ∫ ──→ [K]
    [u] ──→                         -δK      │
              ↑                                ↓
              │                             [÷ν] ──→ [Y_pot]
              │                                │
              └── [Y^D ÷ Y_pot] ←────────────┘
                       u
```

## Employment-Wage-Price Nexus

```
    THE DISTRIBUTIONAL DYNAMICS
    ═══════════════════════════
    
    [1] Output determines labor demand:
    
        L_d = Y/A
        
    where A = labor productivity
    
    
    [2] Employment rate:
    
        e = L/N
        
    where N = labor force
    
    
    [3] Wage dynamics (Phillips curve):
    
        dW/dt = W·φ(e)
        
    where φ(e) = wage response function
    
    
    [4] Productivity (Verdoorn law):
    
        dA/dt = α_A·A + β·(Ẏ/Y)·A
        
    Autonomous growth + output-induced
    
    
    [5] Price level (markup):
    
        P = (1+μ)·(W/A)
        
        
    [6] Real wage:
    
        ω = W/P = 1/(1+μ)·A
        
        
    WIRING:
    ──────
    
    [Y] ──→ [÷A] ──→ [L] ──→ [÷N] ──→ [e]
                      ↑              ↓
                      │           [φ(e)] ──→ [×W] ──→ [dW/dt] ──→ ∫ ──→ [W]
                      │                                             ↑
    [A] ──────────────┘                                            │ W_0
      │
      ↓
    [W÷A] ──→ [×(1+μ)] ──→ [P]
    
    
    Feedbacks:
    
    Y ↑ → L ↑ → e ↑ → W ↑ → P ↑  (cost-push inflation)
    
    Y ↑ → A ↑ → W/A ↓ → P ↓  (productivity dampens inflation)
```

## Adaptive Expectations Pattern

```
    ERROR-CORRECTION MECHANISM
    ══════════════════════════
    
    General form:
    
        dX^e/dt = (X - X^e)/τ_adapt
        
    Expected X adjusts to actual X with lag τ
    
    
    Example: Expected inflation
    
        dπ^e/dt = (π - π^e)/τ_π
        
        
    If τ_π = 2 years:
        Expectations adjust with 2-year lag
        
    After shock:
        Half of error corrected in ~1.4 years
        90% corrected in ~4.6 years
        
        
    Implementation:
    
        [π] ──→ [-] ←── [π^e] ──→ [÷τ] ──→ [dπ^e/dt] ──→ ∫ ──→ [π^e]
                                                           ↑        │
                                                           │        │
                                                          [π_0] ←───┘
                                                          
                                                          
    USE IN MODEL:
    
    Wage bargaining based on expected inflation:
    
        Ẇ/W = φ(e) + π^e
        
    Workers try to maintain real wages
    If π^e lags π → real wage erosion
```

## The Multiplier-Accelerator Pattern

```
    INTERACTION OF CONSUMPTION & INVESTMENT
    ═══════════════════════════════════════
    
    Consumption responds to income (Multiplier):
    
        C = C_0 + c·Y
        
        
    Investment responds to output growth (Accelerator):
    
        I = I_0 + v·(Y - Y_{-1})/Δt
        
    where v = accelerator coefficient
    
    
    Combined:
    
        Y = C + I
          = C_0 + c·Y + I_0 + v·(Y - Y_{-1})/Δt
          
        
    Solving for Y:
    
        Y = [C_0 + I_0 + (v/Δt)·Y_{-1}]/(1 - c + v/Δt)
        
        
    Second-order dynamics:
    
        Y_{t+1} = α·Y_t + β·Y_{t-1} + γ
        
    where α, β depend on c, v
    
    
    STABILITY DEPENDS ON PARAMETERS:
    
    Small v: Damped oscillations → stable
    Medium v: Persistent cycles
    Large v: Explosive oscillations
    
    
         Y
         │        ╱╲      ╱╲
         │      ╱    ╲  ╱    ╲     Stable (small v)
         │    ╱        ╲        ╲
         │──────────────────────────────
         │
         │    ╱╲        ╱╲        ╱╲
         │  ╱    ╲    ╱    ╲    ╱    ╲  Cycles (medium v)
         │╱        ╲╱        ╲╱
         │──────────────────────────────
         │                ╱ ╲
         │              ╱     ╲  ╱      Explosive (large v)
         │            ╱         ╲
         └──────────────────────────────→ t
```

## Inventory Dynamics Pattern

```
    INVENTORY BUFFER STOCK
    ══════════════════════
    
    Firms target inventory-sales ratio:
    
        i* = I_inv*/S  (desired ratio, e.g., 0.15)
        
        
    Actual ratio:
    
        i = I_inv/S
        
        
    Production adjusts to restore target:
    
        Y_prod = S + (i* - i)·S/τ_inv
        
               = S·[1 + (i* - i)/τ_inv]
               
               
    Inventory accumulation:
    
        dI_inv/dt = Y_prod - S
        
        
    Wiring:
    
        [S] ────────┬────────────────────┐
                    │                    ↓
                    ↓                  [+] ──→ [Y_prod]
                  [÷] ──→ [i=I_inv/S]  ↑
                    ↑        │          │
        [I_inv] ───┘        ↓          │
                          [-] ←── [i*] │
                            │           │
                            ↓           │
                          [÷τ_inv] ────┘
                          
        [Y_prod] ─┐
                  ├─→ [-] ──→ [dI_inv/dt] ──→ ∫ ──→ [I_inv]
        [S] ──────┘                           ↑
                                             [I_inv,0]
                                             
                                             
    Creates first-order lag:
    
        If S surges, I_inv falls below target
        → Y_prod increases to rebuild inventories
        → I_inv gradually restored
```

## Lagged Adjustment Pattern

```
    PARTIAL ADJUSTMENT (First-order lag)
    ════════════════════════════════════
    
    Variable X adjusts gradually toward target X*:
    
        dX/dt = (X* - X)/τ
        
        
    Solution:
    
        X(t) = X* + (X_0 - X*)·e^{-t/τ}
        
        
    Properties:
    
        After τ: Gap closed by (1-1/e) ≈ 63%
        After 2τ: Gap closed by (1-1/e²) ≈ 86%
        After 3τ: Gap closed by (1-1/e³) ≈ 95%
        
        
    Half-life: t_{1/2} = τ·ln(2) ≈ 0.69τ
    
    
    Examples:
    ────────
    
    Price adjustment:
        dP/dt = (P* - P)/τ_P
        
        where P* = (1+μ)·(W/A) = target price
              τ_P ≈ 0.5-1 year (pricing period)
              
              
    Consumption adjustment:
        dC/dt = (C* - C)/τ_C
        
        where C* = c·Y_d = target consumption
              τ_C ≈ 0.25 year (quarterly adjustment)
              
              
    Investment adjustment:
        dI/dt = (I* - I)/τ_I
        
        where I* = f(π, u) = desired investment
              τ_I ≈ 1-2 years (planning lag)
```

## Distribution Dynamics

```
    WAGE SHARE & PROFIT SHARE
    ═════════════════════════
    
    Definitions:
    
        ω = (W·L)/Y = Labor's share
        Π_share = Π/Y = 1 - ω = Capital's share
        
        
    Dynamics:
    
        ω̇/ω = (Ẇ/W + L̇/L) - Ẏ/Y
        
             = (Ẇ/W) - (Ẏ/Y - L̇/L)
             
             = (Ẇ/W) - (Ȧ/A)  (if Ẏ/Y = Ȧ/A + L̇/L)
             
             
    Steady state (ω̇ = 0):
    
        Ẇ/W = Ȧ/A
        
    Wages must track productivity for stable distribution
    
    
    If Ẇ/W > Ȧ/A:
        → ω ↑ (labor share rising)
        → Π_share ↓ (profit squeeze)
        → Investment may fall
        → Potential conflict
        
        
    IMPLEMENTATION:
    ──────────────
    
    Can model ω directly:
    
        dω/dt = ω·[(Ẇ/W) - (Ẏ/Y - L̇/L)]
        
        [Ẇ/W] ─┐
               ├─→ [-] ←── [Ẏ/Y - L̇/L] ──→ [×ω] ──→ [dω/dt] ──→ ∫ ──→ [ω]
               │                                                   ↑
               │                                                  [ω_0]
               │                                                   
               
    Or derive from stocks:
    
        ω = (W·L)/Y
        
        [W] ─┐
             ├─→ [×] ──→ [÷Y] ──→ [ω]
        [L] ─┘
```

## Utilization-Investment Feedback

```
    CAPACITY UTILIZATION AS SIGNAL
    ══════════════════════════════
    
    Utilization:
    
        u = Y/(K/ν)
        
    where K/ν = full capacity output
    
    
    Investment response:
    
        I = I_base + κ·(u - u*)·K
        
    where:
        κ = utilization sensitivity
        u* = target utilization (≈ 0.80)
        
        
    Dynamics:
    ────────
    
    High AD → Y ↑ → u ↑ → I ↑ → K ↑ → Y_pot ↑
                                    → u ↓ back toward u*
                                    
    Low AD → Y ↓ → u ↓ → I ↓ → K stagnates
                                    → u stays low
                                    
                                    
    Wiring:
    
        [Y] ──→ [÷] ←── [K÷ν] ──→ [u]
                                    │
                                    ↓
                              [-] ←── [u*]
                                │
                                ↓
                              [×κ×K] ──→ [I_response]
                                │
                                ↓
        [I_base] ──→ [+] ←──────┘
                     │
                     ↓
                   [I] ──→ [- δK] ──→ [dK/dt] ──→ ∫ ──→ [K]
                                                   ↑
                                                  [K_0]
                                                  
                                                  
    Creates negative feedback (stabilizing):
    
    u high → I ↑ → K ↑ → u ↓
    u low → I ↓ → K flat → u stays low
```

## Ratio Dynamics (Key Pattern)

```
    MODELING X/Y RATIOS
    ═══════════════════
    
    For ratio r = X/Y:
    
        ṙ/r = Ẋ/X - Ẏ/Y
        
    Multiply by r:
    
        ṙ = r·(Ẋ/X - Ẏ/Y)
        
        
    Example: Debt-GDP ratio d = D/Y
    
        ḋ = d·(Ḋ/D - Ẏ/Y)
        
        
    Implementation OPTIONS:
    ──────────────────────
    
    Option A: Track stocks separately, compute ratio
    
        D(t) from ∫(dD/dt)
        Y(t) computed
        d(t) = D(t)/Y(t)  (algebraic)
        
        
    Option B: Model ratio directly
    
        ḋ = d·(Ḋ/D - Ẏ/Y)
        
        [Ḋ/D] ─┐
               ├─→ [-] ──→ [×d] ──→ [ḋ] ──→ ∫ ──→ [d]
        [Ẏ/Y] ─┘                             ↑
                                            [d_0]
                                            
                                            
    Option B advantages:
    • Avoids division by Y (if Y could be zero)
    • Ratio is often the economically meaningful variable
    • Can track ratio stability directly
    
    
    Option B disadvantages:
    • Lose track of levels (D, Y separately)
    • Must reconstruct if needed: D = d·Y
```

## Bounded Growth Pattern

```
    LOGISTIC GROWTH (Natural saturation)
    ════════════════════════════════════
    
    Population with carrying capacity:
    
        dN/dt = r·N·(1 - N/N_max)
        
    where:
        r = intrinsic growth rate
        N_max = carrying capacity
        
        
    Solution:
    
        N(t) = N_max·N_0·e^{rt} / (N_max + N_0·(e^{rt} - 1))
        
        
    Properties:
    
        N << N_max: Exponential growth (dN/dt ≈ r·N)
        N → N_max: Growth slows (dN/dt → 0)
        N = N_max: Growth stops
        
        
         N
         │     ╱────────────  N_max (asymptote)
         │   ╱
         │  ╱
         │ ╱
         │╱   Inflection point (N = N_max/2)
         └─────────────────────→ t
         
         
    Economic applications:
    ─────────────────────
    
    Market saturation:
    
        S = S_max·(M/M_max)/(1 + M/M_max)
        
    Technology diffusion:
    
        A = A_max/(1 + e^{-r(t-t_0)})
        
    Debt capacity:
    
        D_max = κ·NW  (borrowing constraint)
```

## Multi-Sector Flow Coordination

```
    THREE-SECTOR FLOW CONSISTENCY
    ═════════════════════════════
    
    Sectors: Households (H), Firms (F), Banks (B)
    
    
    HOUSEHOLD flows:
    ────────────────
    
    Income:   Y_H = W·L + Div + i_M·M_H
    Spending: C + ΔM_H + ΔB_H
    
    Budget: Y_H = C + ΔM_H + ΔB_H
    
    
    FIRM flows:
    ───────────
    
    Revenue:  P·Y
    Costs:    W·L + i·D_F
    Investment: I
    Borrowing: ΔL
    
    Budget: P·Y + ΔL = W·L + i·D_F + I + Div
    
    
    BANK flows:
    ──────────
    
    Revenue:  i_L·L + i_B·B_B
    Costs:    i_M·M
    
    Budget: i_L·L + i_B·B_B = i_M·M + Π_B
    
    
    CONSISTENCY REQUIREMENT:
    ───────────────────────
    
    Σ_sectors (Sources - Uses) = 0
    
    Check each period:
    
        (Y_H - C - ΔM_H - ΔB_H)        [HH budget]
      + (P·Y + ΔL - W·L - i·D_F - I - Div)  [Firm budget]
      + (i_L·L + i_B·B_B - i_M·M - Π_B)    [Bank budget]
      = 0  ✓
      
      
    In Minsky: Use multiple Godley tables
               One per sector
               Cross-check flows match
```

## Time Delay Patterns

```
    DISTRIBUTED LAGS
    ════════════════
    
    Effect of X on Y occurs over multiple periods:
    
        Y_t = α_0·X_t + α_1·X_{t-1} + α_2·X_{t-2} + ...
        
        
    Example: Investment affects output with lag
    
        Y_t = f(K_t) where K_t = ∫(I - δK) dt
        
    I at time τ affects Y at all times t > τ
    
    
    IMPLEMENTATION: Pipeline of delayed stocks
    
        [I] ──→ [÷n] ──→ ∫ ──→ [K_1] ──→ [÷τ] ──┐
                         ↑                       │
                        [0]                      ↓
                                        ∫ ──→ [K_2] ──→ [÷τ] ──┐
                                        ↑                       │
                                       [0]                      ↓
                                                       ∫ ──→ [K_3] ...
                                                       ↑
                                                      [0]
                                                      
        [K_total] = [K_1] + [K_2] + [K_3] + ...
        
        
    Simpler: Use single stock with time constant
    
        dK/dt = (I - δK)
        
    Effective delay ≈ 1/δ
```

## Regime-Dependent Dynamics

```
    SWITCHING BETWEEN STATES
    ════════════════════════
    
    System behavior depends on regime:
    
    
    Example: Central bank reaction function
    
        BR = { BR_low    if π < π_target - ε
             { BR_normal if |π - π_target| ≤ ε
             { BR_high   if π > π_target + ε
             
             
    Or smooth version (Taylor rule):
    
        BR = BR* + α_π·(π - π*) + α_u·(u - u*)
        
    where:
        α_π = response to inflation (≈ 0.5)
        α_u = response to utilization (≈ 0.5)
        
        
    Investment regime-switching:
    
        Normal times: I = f(π, u)
        
        Credit crunch: I = min(f(π, u), I_constrained)
        
        where I_constrained = Π + ΔL_max
        
        
    Wiring with switch:
    
        [π < π_crisis] ──→ [Switch] ──→ [Regime]
                             │
                             ├─ 0: Normal
                             └─ 1: Crisis
                             
        [I_normal] ─┐          
                    ├─→ [Switch output] ──→ [I]
        [I_crisis] ─┘         ↑
                              │
                         [Regime] (control)
```

## Expectation Formation Mechanisms

```
    PATTERN 1: Extrapolative
    ════════════════════════
    
        X^e_t = X_{t-1} + θ·(X_{t-1} - X_{t-2})
        
    Recent trend continues
    
    
    PATTERN 2: Regressive
    ═════════════════════
    
        X^e_t = X_normal + β·(X_{t-1} - X_normal)
        
    Mean reversion toward normal
    
    
    PATTERN 3: Adaptive
    ═══════════════════
    
        X^e_t = X^e_{t-1} + γ·(X_{t-1} - X^e_{t-1})
        
    Error correction
    
    
    PATTERN 4: Heterogeneous
    ════════════════════════
    
        X^e_total = w_1·X^e_extrap + w_2·X^e_regress
        
    Different agents use different rules
    
    
    PATTERN 5: State-dependent
    ══════════════════════════
    
        Weight on extrapolation depends on state:
        
        w_extrap = f(Confidence)
        
        High confidence → More extrapolation (momentum)
        Low confidence → More regression (mean reversion)
```

## Disequilibrium Adjustment Pattern

```
    QUANTITY-PRICE ADJUSTMENT
    ═════════════════════════
    
    Market has excess demand: Y^D > Y^S
    
    
    Fast adjustment (days): Prices flex
    
        dP/dt = κ_P·(Y^D - Y^S)/Y^S
        
        
    Slow adjustment (months): Quantities adjust
    
        dY/dt = κ_Y·(Y^D - Y^S)
        
        
    Fix-price markets: κ_P ≈ 0, κ_Y > 0
        → Quantity adjusts, price fixed
        
    Flex-price markets: κ_P >> κ_Y
        → Price adjusts quickly, quantity follows
        
        
    In SFC models:
    
        Fix-price (95% of GDP):  Y = Y^D  (at given P)
        Flex-price (5% of GDP):  P adjusts to clear
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Adjustment speed determines dynamics           │
    │                                                  │
    │  Fast price adjustment → Neoclassical           │
    │  Fast quantity adjustment → Keynesian           │
    │                                                  │
    │  Moore: Modern economies are Keynesian          │
    │         (quantity-adjusting, price-fixed)       │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Momentum & Feedback Strength

```
    POSITIVE VS NEGATIVE FEEDBACK BALANCE
    ═════════════════════════════════════
    
    System with both feedbacks:
    
        dX/dt = α·X - β·X²
        
    where:
        α·X = positive feedback (growth)
        -β·X² = negative feedback (saturation)
        
        
    Equilibrium: X* = α/β
    
    
    Stability:
    
        ∂(dX/dt)/∂X = α - 2β·X
        
        At X*: α - 2β·(α/β) = α - 2α = -α < 0
        
        ∴ Stable
        
        
    Dynamics depend on α/β:
    
         X
         │     ╱────────────  X* = α/β
         │   ╱
         │  ╱
         │ ╱
         │╱
         └─────────────────────→ t
         
    Fast approach if α, β large
    Slow approach if α, β small
    
    
    Economic example:
    ────────────────
    
    Investment-capital:
    
        dK/dt = I(K) - δ·K
        
    where I(K) = γ·(K/K*)^η - δ·K
    
    Positive feedback: More K → higher optimal I
    Negative feedback: Depreciation
```

## Summary: SD Patterns for SFC

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  ESSENTIAL SYSTEM DYNAMICS PATTERNS                          ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  1. STOCK-FLOW CHAINS                                        ║
║     Inflow → ∫ → Stock → Outflow                            ║
║     Time constants τ for realistic lags                      ║
║                                                               ║
║  2. CO-FLOWS (Nominal-Real pairs)                            ║
║     Track nominal in Godley, compute real for analysis      ║
║                                                               ║
║  3. PARTIAL ADJUSTMENT                                        ║
║     dX/dt = (X* - X)/τ                                       ║
║     First-order lags for all adjustments                     ║
║                                                               ║
║  4. BUFFER STOCKS                                             ║
║     Inventories, money balances, excess capacity             ║
║     Absorb short-run mismatches                              ║
║                                                               ║
║  5. RATIO DYNAMICS                                            ║
║     ṙ = r·(Ẋ/X - Ẏ/Y) for all ratios r = X/Y               ║
║                                                               ║
║  6. FEEDBACK LOOPS                                            ║
║     Positive (growth/collapse) + Negative (cycles)           ║
║     Map and balance carefully                                 ║
║                                                               ║
║  7. MULTI-SECTOR COORDINATION                                 ║
║     Flows match across Godley tables                         ║
║     Accounting checks every period                            ║
║                                                               ║
║  8. REGIME SWITCHING                                          ║
║     State-dependent dynamics (normal/crisis)                  ║
║     Smooth or discrete transitions                            ║
║                                                               ║
║  9. EXPECTATION FORMATION                                     ║
║     Adaptive, extrapolative, or hybrid                       ║
║     Lagged adjustment to actual                               ║
║                                                               ║
║  10. BOUNDED RESPONSES                                        ║
║      Logistic, tanh, min/max for realistic limits           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
