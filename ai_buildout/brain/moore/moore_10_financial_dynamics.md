# MOORE PART 10: FINANCIAL DYNAMICS & DEBT ACCUMULATION

## Debt Dynamics: The Core Differential Equation

```
╔═══════════════════════════════════════════════════════════════╗
║  DEBT ACCUMULATION EQUATION                                  ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  dD/dt = I - Π + i·D                                         ║
║                                                               ║
║  where:                                                       ║
║    D = Stock of debt                                         ║
║    I = Investment spending                                    ║
║    Π = Profits (gross of interest)                           ║
║    i = Interest rate                                          ║
║    i·D = Interest payments                                    ║
║                                                               ║
║  Interpretation:                                             ║
║    Debt rises when: I + interest > Π                         ║
║    Debt falls when: Π > I + interest                         ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

    DEBT RATIO DYNAMICS
    ═══════════════════
    
    Define: d = D/Y  (debt-to-GDP ratio)
    
    Taking logs and differentiating:
    
        ḋ/d = Ḋ/D - Ẏ/Y
        
    Substituting Ḋ = I - Π + i·D:
    
        ḋ/d = (I - Π + i·D)/D - ẏ
        
            = (I - Π)/D + i - ẏ
            
    Multiply through by d:
    
        ḋ = d·[(I - Π)/D + i - ẏ]
        
        
    IN STEADY STATE (d constant):
    
        ḋ = 0
        
        ∴ (I - Π)/D + i = ẏ
        
        ∴ Debt service ratio must match growth:
        
            i·d = ẏ·d - (I - Π)/Y
            
            
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  If i·d > ẏ·d → Debt servicing exceeds growth  │
    │               → Unsustainable                    │
    │               → Deleveraging inevitable          │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Minsky's Financial Fragility

```
    THREE FINANCING REGIMES
    ═══════════════════════
    
    1. HEDGE FINANCE (Stable)
    ─────────────────────────
    
        Π > i·D + Amortization
        
        Cash flow covers:
        • Interest payments
        • Principal repayments
        • Still have profit left over
        
        Debt ratio stable or declining
        
        
    2. SPECULATIVE FINANCE (Fragile)
    ────────────────────────────────
    
        Π > i·D  BUT  Π < i·D + Amortization
        
        Cash flow covers interest,
        but must refinance principal
        
        Debt ratio stable if can roll over
        Vulnerable to rate increases
        
        
    3. PONZI FINANCE (Unsustainable)
    ────────────────────────────────
    
        Π < i·D
        
        Cash flow doesn't even cover interest!
        
        Must borrow to pay interest
        Debt ratio RISING
        
        Eventual default inevitable
        
        
    DYNAMICS:
    ────────
    
         Regime
         │
      3  │ Ponzi ──────────────── Crisis!
         │           ↗
      2  │ Spec ──↗              ↓
         │     ↗                  ↓ Deleveraging
      1  │ Hedge                  ↓
         │    ↑                   ↓
         │    └───────────────────┘
         └─────────────────────────────→ time
              Expansion        Crash   Recovery
              
              
    Transition dynamics:
    
        Low debt → Optimism → More borrowing
                → Debt rises → Fragility rises  
                → Eventually: Π < i·D
                → Crisis
```

## Debt-Deflation Dynamics (Fisher)

```
    FISHER'S DEBT-DEFLATION SPIRAL
    ══════════════════════════════
    
    [1] Debt high → Distress selling to repay
              ↓
    [2] Asset prices fall → Wealth ↓
              ↓
    [3] Collateral value ↓ → Credit contraction
              ↓
    [4] Spending ↓ → AD ↓
              ↓
    [5] Prices fall (P ↓)
              ↓
    [6] Real debt burden ↑ (D/P ↑)
              ↓
    [7] More distress selling
              ↓
        Back to [1] → SPIRAL
        
        
    Mathematical form:
    
        dD/dt = I - Π  (debt accumulation)
        dP/dt = (P*/P - 1)/τ_P  (price adjustment)
        
    If P falls:
        → Real debt D/P rises
        → Debt service (i·D/P) rises in real terms
        → Π net of interest falls
        → dD/dt rises
        → More unsustainable
        
        
    Self-reinforcing DEFLATION:
    
         P
         │
         │ ─────────────────
         │                  ╲
         │                   ╲
         │                    ╲
         │                     ╲  Accelerating
         │                      ╲ deflation
         │                       ↓
         └──────────────────────────→ t
```

## Interest Rate Channels

```
    HOW BR AFFECTS THE ECONOMY (Transmission mechanisms)
    ════════════════════════════════════════════════════
    
    Central Bank sets BR
         │
         ├──→ [1] DIRECT CREDIT CHANNEL
         │         ↓
         │    Lending rate = BR + markup
         │         ↓
         │    Cost of borrowing ↑
         │         ↓
         │    I ↓, C_durables ↓
         │         ↓
         │    AD ↓
         │
         │
         ├──→ [2] ASSET PRICE CHANNEL
         │         ↓
         │    Discount rate for assets ↑
         │         ↓
         │    Bond prices ↓, Stock prices ↓
         │         ↓
         │    Wealth ↓
         │         ↓
         │    C ↓ (wealth effect)
         │         ↓
         │    AD ↓
         │
         │
         ├──→ [3] EXCHANGE RATE CHANNEL
         │         ↓
         │    Higher domestic rates → Capital inflow
         │         ↓
         │    Exchange rate appreciates
         │         ↓
         │    Exports ↓, Imports ↑
         │         ↓
         │    AD ↓
         │
         │
         └──→ [4] EXPECTATIONS CHANNEL
                   ↓
              Higher BR signals "CB fighting inflation"
                   ↓
              Inflation expectations ↓
                   ↓
              Real wage expectations ↑
                   ↓
              Wage demands ↓
                   ↓
              Cost pressures ↓
                   
                   
    Total effect: ΔY/ΔBR < 0  (contractionary)
    
    Lag structure: Effects spread over 1-2 years
```

## Term Structure of Interest Rates

```
    EXPECTATIONS THEORY OF YIELD CURVE
    ══════════════════════════════════
    
    Long rate = Expected average of future short rates
    
        i_L(t) = [i_S(t) + E_t(i_S(t+1)) + E_t(i_S(t+2)) + ...]/N
        
               + term premium
               
               
    If CB credibly commits to BR path:
    
        BR(t+k) = BR* for all k
        
    Then:
    
        i_L ≈ BR* + term premium
        
        
    Implementation:
    ───────────────
    
    Simple: Assume flat term structure
    
        i_L = BR + spread
        
    where spread ≈ 1-2% (historical average)
    
    
    Advanced: Model expectations
    
        E_t(BR_{t+k}) = BR_t + β·(BR_target - BR_t)
        
    (Expect mean reversion to target)
    
        i_L = Σ_k w_k·E_t(BR_{t+k})
        
    where w_k = weights (sum to 1)
```

## Portfolio Stock-Flow Model

```
    HOUSEHOLD PORTFOLIO DYNAMICS
    ════════════════════════════
    
    Wealth allocation across assets:
    
        NW = M + B_S + B_L + E
        
    where:
        M = Money (deposits)
        B_S = Short-term bonds
        B_L = Long-term bonds
        E = Equities
        
        
    FLOW OF FUNDS (Period t):
    ────────────────────────
    
    New wealth: ΔNW = S = Y - T - C
    
    Rebalancing existing wealth:
    
        ΔM_rebal = -(M - m*·NW)/τ_M
        ΔB_S_rebal = -(B_S - b_S*·NW)/τ_B
        ΔB_L_rebal = -(B_L - b_L*·NW)/τ_B
        ΔE_rebal = -(E - e*·NW)/τ_E
        
    Allocating new wealth:
    
        ΔM_new = m*·ΔNW
        ΔB_S_new = b_S*·ΔNW
        ΔB_L_new = b_L*·ΔNW
        ΔE_new = e*·ΔNW
        
    Total changes:
    
        ΔM = ΔM_rebal + ΔM_new
        ΔB_S = ΔB_S_rebal + ΔB_S_new
        etc.
        
        
    Desired shares depend on rates of return:
    
        m* = f(i_M, i_S, i_L, r_E, σ_E)
        b_S* = g(i_M, i_S, i_L, r_E, σ_E)
        ...
        
    where:
        i_M = interest on deposits
        i_S, i_L = bond yields
        r_E = expected return on equities
        σ_E = risk (volatility)
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Higher rates → shift to bonds                  │
    │  Higher risk → shift to safe assets             │
    │  New wealth allocated according to preferences  │
    │  Existing wealth gradually rebalanced           │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Bank Balance Sheet Dynamics

```
    COMMERCIAL BANK SECTOR
    ══════════════════════
    
    ASSETS:                         LIABILITIES:
    ───────                         ────────────
    Reserves (R)                    Deposits (M)
    Loans (L)                       Net Worth (NW_B)
    Securities (B_B)
    
    
    Balance sheet identity:
    
        R + L + B_B = M + NW_B
        
        
    DYNAMICS:
    ────────
    
    Loan creation:
    
        dL/dt = New loans - Repayments
              = L_demand·(credit_limit - L)/L_limit
                - L/τ_repay
                
                
    Deposit creation:
    
        dM/dt = dL/dt  (loans create deposits)
        
        
    Reserve requirement:
    
        R_required = r·M  (r = reserve ratio)
        
        R_actual supplied by CB at BR
        
        
    Bank profits:
    
        Π_B = i_L·L + i_B·B_B - i_M·M - Costs
        
        
    Net worth dynamics:
    
        dNW_B/dt = Π_B - Dividends
        
        
    Capital adequacy:
    
        NW_B/L ≥ κ  (minimum capital ratio)
        
        If binding → Credit rationing tightens
        
            L_supply = min(L_demand, κ·NW_B)
```

## Debt Sustainability Analysis

```
    WHEN IS DEBT SUSTAINABLE?
    ═════════════════════════
    
    Debt dynamics:
    
        ḋ = d·(r_D - ẏ) + (I - Π)/Y
        
    where:
        d = D/Y
        r_D = Ḋ/D = debt growth rate
        ẏ = Ẏ/Y = income growth rate
        
        
    STABILITY CONDITION:
    ───────────────────
    
    For d to be stable (ḋ = 0):
    
        r_D = ẏ - (I - Π)/(D)
        
    Define primary surplus ratio: s = (Π - I)/Y
    
    Then:
        r_D = ẏ + s/d
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Debt sustainable if:                           │
    │                                                  │
    │    Debt growth ≤ Income growth                  │
    │    + Primary surplus contribution               │
    │                                                  │
    │  If i·d > ẏ·d:                                  │
    │    Interest burden exceeds growth capacity      │
    │    → Unsustainable                              │
    │    → Deleveraging required                      │
    │                                                  │
    └──────────────────────────────────────────────────┘
    
    
    EXAMPLE:
    ────────
    
    d = 1.5  (debt = 150% of GDP)
    i = 0.05  (5% interest)
    ẏ = 0.03  (3% growth)
    
    Interest burden: i·d = 0.05·1.5 = 0.075 = 7.5% of GDP
    Growth capacity: ẏ·d = 0.03·1.5 = 0.045 = 4.5% of GDP
    
    Gap: 7.5% - 4.5% = 3% of GDP
    
    ∴ Need primary surplus of 3% of GDP to stabilize
    
    If primary balance = 0:
        → ḋ > 0
        → d rising
        → UNSUSTAINABLE
```

## Credit Rationing Dynamics

```
    BORROWING CONSTRAINTS
    ═════════════════════
    
    Banks set credit ceiling based on borrower's "3 Cs":
    
    
    1. CREDIT (Income):
       ───────────────
       Max_L = κ_Y·Y  (some multiple of income)
       
       Typical: κ_Y = 3-5
       
       
    2. COLLATERAL (Wealth):
       ──────────────────────
       Max_L = κ_W·W  (loan-to-value ratio)
       
       Typical: κ_W = 0.7-0.9  (70-90% LTV)
       
       
    3. CHARACTER (History):
       ────────────────────
       If default history: Max_L = 0
       If good history: Ceiling increased
       
       
    EFFECTIVE CEILING:
    ─────────────────
    
        L_max = min(κ_Y·Y, κ_W·W, L_history)
        
        
    CREDIT UTILIZATION:
    ──────────────────
    
        L_actual/L_max = utilization
        
    Typically 40-60% in normal times
    
    In boom: utilization → 80%+ (near ceiling)
    In bust: utilization → 20%- (under-borrowed)
    
    
    IMPLEMENTATION:
    ──────────────
    
        Demand: L_desired = working capital needs
        
        Supply: L_granted = min(L_desired, L_max)
        
        Rationing: If L_desired > L_max
                   → Investment constrained
                   → I_actual < I_desired
                   
        [I_desired] ─┐
                     ├─→ [min] ─→ [I_actual]
        [I_max] ────┘      ↑
                           │
        where I_max = (Π + L_max - L_current)/Δt
```

## Endogenous Leverage Cycles

```
    PRO-CYCLICAL LEVERAGE
    ═════════════════════
    
    Boom phase:
    ───────────
    
    Asset prices ↑ → Collateral value ↑
                  → L_max ↑
                  → More borrowing possible
                  → More investment
                  → AD ↑
                  → Asset prices ↑ further
                  → POSITIVE FEEDBACK
                  
                  
    Bust phase:
    ──────────
    
    Asset prices ↓ → Collateral value ↓
                  → L_max ↓
                  → Forced deleveraging
                  → Asset sales
                  → AD ↓
                  → Asset prices ↓ further
                  → NEGATIVE FEEDBACK
                  
                  
    LEVERAGE RATIO DYNAMICS:
    ───────────────────────
    
        λ = D/(P_asset·Q_asset)  (debt-to-asset-value)
        
        dλ/dt = λ·(Ḋ/D - Ṗ/P - Q̇/Q)
        
        
    In boom: Ṗ/P > 0, Q̇/Q > 0
            → λ falls (leverage looks safe)
            → Borrow more
            
    In bust: Ṗ/P < 0, Q̇/Q < 0
            → λ rises (leverage looks dangerous)
            → Forced deleveraging
            
            
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Leverage is PRO-CYCLICAL                       │
    │    Boom: Looks safe, actually building fragility│
    │    Bust: Looks dangerous, forced selling        │
    │                                                  │
    │  Creates boom-bust cycles endogenously          │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## The Monetary Circuit: Temporal Structure

```
    COMPLETE CIRCUIT DYNAMICS
    ═════════════════════════
    
    Phase 1: PRODUCTION PLANNING (t=0)
    ──────────────────────────────────
    
    Firms decide production: Y_plan
         ↓
    Need working capital: WC = W·L + Materials
         ↓
    Borrow from banks: ΔL = WC
         ║
         ║ (creates deposits)
         ↓
    +ΔM (money created)
    
    
    Phase 2: PRODUCTION (t=0 to t=T_prod)
    ──────────────────────────────────────
    
    Firms pay wages: W·L
         ↓
    Workers receive deposits
         ↓
    Firms buy materials: Materials
         ↓
    Suppliers receive deposits
         ↓
    Production occurs
         ↓
    Inventories accumulate
    
    
    Phase 3: SALES (t=T_prod to t=T_sales)
    ───────────────────────────────────────
    
    Goods sold: Revenue = P·Y
         ↓
    Firms receive deposits
         ↓
    Inventories decumulate
    
    
    Phase 4: CIRCUIT CLOSURE (t=T_sales)
    ────────────────────────────────────
    
    Firms repay loans: -ΔL
         ║
         ║ (destroys deposits)
         ↓
    -ΔM (money destroyed)
    
    Net change in M = 0 (circuit closed)
    
    
    BUT: In growing economy, circuit DOESN'T fully close
    
        New loans > Repayments
        ∴ ΔM > 0  (secular money growth)
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Money created for production                   │
    │  Destroyed when sales complete                  │
    │                                                  │
    │  Net growth in M = Net growth in activity       │
    │                                                  │
    │  M accommodates circuit, doesn't drive it       │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Profit Equation (Kalecki-Levy)

```
╔═══════════════════════════════════════════════════════════════╗
║  KALECKI'S PROFIT EQUATION                                   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Π = I + Dividends + Govt_Deficit - Household_Saving         ║
║                                                               ║
║  Or simplified (closed economy):                             ║
║                                                               ║
║  Π = I + (G - T)                                             ║
║                                                               ║
║  "Capitalists earn what they spend,                          ║
║   Workers spend what they earn"                              ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

    DERIVATION:
    ──────────
    
    Y = W·L + Π  (income distribution)
    Y = C + I + G  (output)
    
    ∴ W·L + Π = C + I + G
    
    Assume: Workers consume all wages
            C_workers = W·L
            C_capitalists = C - W·L
            
    ∴ Π = C_cap + I + (G - T)
    
    If C_cap ≈ 0 (capitalists save, don't consume):
    
        Π ≈ I + (G - T)
        
        
    IMPLICATION:
    ───────────
    
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Profits determined by SPENDING, not production │
    │                                                  │
    │  High investment → High profits                 │
    │  Govt deficits → High profits                   │
    │                                                  │
    │  "Profits are what firms spend on investment    │
    │   plus what govt spends in deficit"             │
    │                                                  │
    │  Causation: I → Π, not Π → I                    │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Financial Fragility Index

```
    MEASURING SYSTEM FRAGILITY
    ══════════════════════════
    
    Composite indicator of financial vulnerability:
    
    
    Component 1: Debt Service Ratio
    ────────────────────────────────
    
        DSR = (i·D)/Y
        
        Fragile if DSR > 0.15  (15% of income to interest)
        
        
    Component 2: Debt-to-Income
    ───────────────────────────
    
        d = D/Y
        
        Fragile if d > 2.0  (debt > 200% of income)
        
        
    Component 3: Ponzi Share
    ────────────────────────
    
        Ponzi_share = (Firms where Π < i·D) / Total firms
        
        Fragile if Ponzi_share > 0.20  (20% Ponzi)
        
        
    Component 4: Asset Price Deviation
    ──────────────────────────────────
    
        Q_asset/Q_fundamental
        
        Fragile if > 1.5  (50% overvalued)
        
        
    COMPOSITE FRAGILITY INDEX:
    ─────────────────────────
    
        F = w_1·(DSR/0.15) + w_2·(d/2.0) 
          + w_3·(Ponzi/0.20) + w_4·(Q/Q_f)/1.5
          
    where w_i = weights (sum to 1)
    
    
    F > 1.0 → System fragile, crisis risk high
    
    
    USE IN MODEL:
    ────────────
    
    Probability of crisis = σ(F - 1)
    
    where σ = logistic function
    
    Or: Trigger deleveraging when F > F_critical
```

## Debt-Driven Boom-Bust Cycle

```
    ENDOGENOUS CYCLE MECHANISM
    ══════════════════════════
    
    [1] EXPANSION PHASE
        ───────────────
        
        Optimism high → I ↑
                      → Borrowing ↑ (dD/dt > 0)
                      → AD ↑
                      → Y ↑, Π ↑
                      → Asset prices ↑
                      → Collateral ↑
                      → More borrowing possible
                      → (Loop back)
                      
        Debt grows but so does income
        d = D/Y may be stable or rising slowly
        
        
    [2] BOOM PEAK
        ─────────
        
        d reaches high level
        Interest burden i·d large
        Π growth slowing
        
        Fragility F → 1.0
        
        
    [3] MINSKY MOMENT
        ─────────────
        
        Small shock (CB raises BR, or demand dip)
              ↓
        Profits fall slightly
              ↓
        Some firms: Π < i·D (enter Ponzi)
              ↓
        Credit rating downgrades
              ↓
        Credit rationing tightens
              ↓
        Investment falls (I ↓)
              ↓
        AD ↓ → Y ↓ → Π ↓ further
              ↓
        Asset prices fall
              ↓
        Collateral ↓ → Forced deleveraging
              ↓
        CRISIS STARTS
        
        
    [4] CRISIS & DELEVERAGING
        ─────────────────────
        
        Distress selling → Asset prices crash
                        → Wealth destruction
                        → C ↓
                        → AD ↓ further
                        → Bankruptcies
                        → Bad debts
                        → Bank failures
                        → Credit crunch
                        → I ↓ dramatically
                        → Deep recession
                        
        d may rise initially (Y falls faster than D)
        Then falls as deleveraging proceeds
        
        
    [5] RECOVERY
        ────────
        
        d back to low level
        Balance sheets repaired
        Optimism gradually returns
        I starts to rise
        → Back to [1]
        
        
    Full cycle: 15-30 years (Minsky cycle)
```

## Modeling Financial Accelerator

```
    CREDIT AVAILABILITY MECHANISM
    ═════════════════════════════
    
    Investment depends on:
    • Internal finance (Π)
    • External finance (ΔL)
    
        I = min(I_desired, Π + ΔL_available)
        
        
    ΔL_available depends on:
    
        ΔL_available = (L_max - L)/τ
        
    where L_max depends on:
    
        L_max = κ·(NW_firm + Collateral)
        
        
    Collateral value:
    
        Collateral = P_asset·Q_asset
        
        
    FEEDBACK LOOP:
    ─────────────
    
    P_asset ↑ → L_max ↑ → I ↑ → AD ↑ → Y ↑
                                      → Π ↑
                                      → Firm NW ↑
                                      → L_max ↑
                                      → (amplification)
                                      
    P_asset ↓ → L_max ↓ → I ↓ → AD ↓ → Y ↓
                                      → Π ↓
                                      → Firm NW ↓
                                      → L_max ↓
                                      → (amplification)
                                      
                                      
    Implementation:
    
        [P_asset] ─┐
                   ├─→ [×] ─→ [Collateral]
        [Q_asset] ─┘      │
                          ↓
        [NW_firm] ─→ [+] ←┘
                     │
                     ↓
                   [×κ] ─→ [L_max]
                     │
                     ↓
        [I_desired] ─────→ [min] ─→ [I_actual]
                          ↑
        [Π + ΔL_avail] ──┘
```

## Interest Rate Risk (Duration Mismatch)

```
    BANK BALANCE SHEET RISK
    ═══════════════════════
    
    Assets:                  Liabilities:
    ───────                  ────────────
    Long-term loans (L_LT)   Short-term deposits (M)
    
    Maturity mismatch!
    
    
    If BR rises:
    ────────────
    
    Cost of deposits ↑ (immediately)
    Revenue from loans unchanged (locked in)
         ↓
    Profit margin ↓
         ↓
    Bank NW ↓
         ↓
    If severe: Bank capital ratio falls below minimum
              → Bank must shrink lending
              → Credit crunch
              
              
    DYNAMICS:
    ────────
    
        Π_B = i_L·L - i_M·M - Costs
        
        i_M = BR - markdown  (adjusts quickly)
        i_L = BR_past + markup  (fixed when loan made)
        
        
    If BR rises by Δi:
    
        ΔΠ_B ≈ -M·Δi  (immediate loss)
        
        
    Over time, as loans roll over:
    
        i_L rises gradually to new BR + markup
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Rapid BR increases hurt banks                  │
    │  → Credit supply contracts                      │
    │  → Amplifies recession                          │
    │                                                  │
    │  "Credit crunch" = endogenous response to       │
    │  monetary tightening                             │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Practical Debt Modeling Patterns

```
    PATTERN 1: Simple Debt Accumulation
    ═══════════════════════════════════
    
        dD/dt = ΔBorrowing - Repayment
              = I - Π  (if I deficit-financed)
              
        [I] ─┐
             ├─→ [-] ─→ [dD/dt] ─→ ∫ ─→ [D]
        [Π] ─┘                     ↑
                                   │ D_0
                                   
                                   
    PATTERN 2: With Amortization
    ════════════════════════════
    
        dD/dt = New_borrowing - Amortization
        
        Amortization = D/τ_amort
        
        where τ_amort = amortization period (e.g., 20 years)
        
        [New_L] ─┐
                 ├─→ [-] ─→ [dD/dt] ─→ ∫ ─→ [D]
        [D/τ] ──┘                          │
                                           └─→ [÷τ]
                                           
                                           
    PATTERN 3: Interest Burden
    ══════════════════════════
    
        Interest = i·D
        
        Net profit after interest:
        
            Π_net = Π_gross - i·D
            
        If Π_net < 0 → Ponzi finance
        
        [Π_gross] ─┐
                   ├─→ [-] ─→ [Π_net]
        [i×D] ────┘
        
        
    PATTERN 4: Debt Sustainability Check
    ════════════════════════════════════
    
        Sustainable = (i·d < ẏ·d)
        
        If not sustainable:
            → Trigger deleveraging
            → Reduce investment
            → Force repayment
            
        [i×d] ─┐
               ├─→ [-] ─→ [Margin] ─→ [if <0] ─→ [Crisis!]
        [ẏ×d] ─┘
```

## Summary: Financial Dynamics Architecture

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  FINANCIAL SECTOR MODELING (Moore/Minsky Framework)          ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  1. DEBT ACCUMULATION:                                       ║
║     dD/dt = I - Π + i·D  (or variants with amortization)    ║
║                                                               ║
║  2. DEBT RATIO DYNAMICS:                                     ║
║     ḋ = d·[(I-Π)/D + i - ẏ]                                 ║
║     Unstable if i·d > ẏ·d                                   ║
║                                                               ║
║  3. MINSKY REGIMES:                                          ║
║     Hedge → Speculative → Ponzi → Crisis                    ║
║                                                               ║
║  4. CREDIT RATIONING:                                        ║
║     L_max = f(Income, Collateral, History)                   ║
║     Actual credit ≤ L_max                                    ║
║                                                               ║
║  5. PRO-CYCLICAL LEVERAGE:                                   ║
║     Boom: Easy credit → borrowing ↑ → fragility ↑           ║
║     Bust: Tight credit → deleveraging → crisis deepens      ║
║                                                               ║
║  6. MONETARY CIRCUIT:                                        ║
║     Loans finance production → Deposits created              ║
║     Sales complete → Loans repaid → Deposits destroyed       ║
║     Net: M grows with nominal activity                       ║
║                                                               ║
║  7. INTEREST RATE TRANSMISSION:                              ║
║     BR → Lending rates → Investment → AD                     ║
║         → Asset prices → Wealth → Consumption                ║
║                                                               ║
║  8. PROFIT DETERMINATION:                                    ║
║     Π = I + (G-T)  (Kalecki)                                ║
║     Spending determines profits                               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
