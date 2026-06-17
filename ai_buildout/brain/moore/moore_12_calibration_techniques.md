# MOORE PART 12: CALIBRATION & VALIDATION TECHNIQUES

## Steady-State Calibration Strategy

```
╔═══════════════════════════════════════════════════════════════╗
║  STEADY STATE: All ratios constant (not all variables!)     ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Definition:  d(Stock/Y)/dt = 0  for all stocks              ║
║                                                               ║
║  Implies:     Ṡ/S = Ẏ/Y  for all stocks S                   ║
║                                                               ║
║  NOT equilibrium! Variables still growing, but proportionally║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

    CALIBRATION PROCEDURE:
    ═════════════════════
    
    STEP 1: Set target growth rate
    ───────────────────────────────
    
        ẏ = 0.03  (3% real growth)
        π = 0.02  (2% inflation)
        ẏ_nominal = ẏ + π = 0.05  (5% nominal growth)
        
        
    STEP 2: Set target stock/flow ratios
    ────────────────────────────────────
    
        k = K/Y = 3.0  (capital-output)
        d = D/Y = 1.5  (debt-GDP)
        m = M/Y = 0.6  (money-GDP)
        
        
    STEP 3: Derive implied flow ratios
    ──────────────────────────────────
    
    From K̇/K = ẏ and K/Y = k:
    
        I/K = ẏ + δ
        
        ∴ I/Y = (ẏ + δ)·k
        
    If δ = 0.05, ẏ = 0.03, k = 3:
    
        I/Y = (0.03 + 0.05)·3 = 0.24
        
        
    From Ḋ/D = ẏ_nominal and D/Y = d:
    
        ΔD/Y = ẏ_nominal·d
        
    If ẏ_nominal = 0.05, d = 1.5:
    
        ΔD/Y = 0.05·1.5 = 0.075
        
        
    From Ṁ/M = ẏ_nominal and M/Y = m:
    
        ΔM/Y = ẏ_nominal·m
        
    If ẏ_nominal = 0.05, m = 0.6:
    
        ΔM/Y = 0.05·0.6 = 0.03
        
        
    STEP 4: Set behavioral parameters to achieve targets
    ────────────────────────────────────────────────────
    
    Investment function:
    
        I/Y = i_0 + γ_π·(π - π*) + γ_u·(u - u*)
        
    At steady state: π = π*, u = u*
    
        ∴ I/Y = i_0
        
        ∴ i_0 = 0.24  (from step 3)
        
        
    Consumption function:
    
        C/Y = 1 - I/Y - G/Y - (X-M)/Y
        
    If G/Y = 0.20, (X-M)/Y = 0:
    
        C/Y = 1 - 0.24 - 0.20 = 0.56
        
        ∴ C = 0.56·Y
        
    If C = α + c·Y_d and T/Y = 0.25:
    
        C/Y = α/Y + c·(1 - T/Y)
        0.56 = α/Y + c·0.75
        
    Choose c = 0.70 (MPC):
    
        α/Y = 0.56 - 0.70·0.75 = 0.035
        
        ∴ α = 0.035·Y_0
```

## Finding Steady State Numerically

```
    ITERATIVE STEADY-STATE SOLVER
    ═════════════════════════════
    
    Goal: Find parameters such that ratios stabilize
    
    
    ALGORITHM:
    ─────────
    
    [1] Initial guess for parameters θ
    
    [2] Run model for T periods (T = 200 years)
    
    [3] Compute ratios in final period:
    
        k_final = K_T/Y_T
        d_final = D_T/Y_T
        etc.
        
    [4] Compare to targets:
    
        error_k = k_final - k_target
        error_d = d_final - d_target
        
    [5] Adjust parameters:
    
        If k_final > k_target:
            → Reduce investment (lower i_0)
            
        If d_final > d_target:
            → Increase profit share (reduce wage share)
            → Or reduce borrowing propensity
            
    [6] Repeat until errors < tolerance
    
    
    Pseudo-code:
    
        θ = initial_guess
        
        for iteration in 1:max_iter:
            
            results = simulate(θ, T=200)
            
            k_final = results.K[-1] / results.Y[-1]
            d_final = results.D[-1] / results.Y[-1]
            
            error_k = k_final - k_target
            error_d = d_final - d_target
            
            if |error_k| < ε and |error_d| < ε:
                break  # Converged!
                
            # Adjust parameters
            θ['i_0'] -= η * error_k  # Gradient descent
            θ['wage_share'] -= η * error_d
            
        return θ  # Calibrated parameters
```

## Validation Against Stylized Facts

```
    EMPIRICAL VALIDATION CHECKLIST
    ══════════════════════════════
    
    ┌────────────────────────────────────────────────────┐
    │ STEADY-STATE CHECKS                                │
    ├────────────────────────────────────────────────────┤
    │                                                    │
    │ □ Capital-output ratio: K/Y ∈ [2.5, 4.0]         │
    │ □ Investment share: I/Y ∈ [0.15, 0.30]           │
    │ □ Consumption share: C/Y ∈ [0.55, 0.75]          │
    │ □ Wage share: ω ∈ [0.55, 0.70]                   │
    │ □ Profit share: Π/Y ∈ [0.25, 0.45]               │
    │ □ Debt-GDP: d ∈ [1.0, 2.0]                       │
    │ □ Money-GDP: m ∈ [0.5, 1.0]                      │
    │                                                    │
    └────────────────────────────────────────────────────┘
    
    ┌────────────────────────────────────────────────────┐
    │ GROWTH RATES                                       │
    ├────────────────────────────────────────────────────┤
    │                                                    │
    │ □ GDP growth: ẏ ∈ [0.02, 0.05]                   │
    │ □ Productivity: Ȧ/A ∈ [0.01, 0.03]               │
    │ □ Wage growth: Ẇ/W ∈ [0.02, 0.06]                │
    │ □ Inflation: π ∈ [0.01, 0.04]                    │
    │ □ Money growth: Ṁ/M ≈ ẏ_nominal                  │
    │                                                    │
    └────────────────────────────────────────────────────┘
    
    ┌────────────────────────────────────────────────────┐
    │ CYCLE PROPERTIES (if oscillating)                 │
    ├────────────────────────────────────────────────────┤
    │                                                    │
    │ □ Business cycle period: 4-10 years               │
    │ □ GDP amplitude: ±3% to ±8%                       │
    │ □ Investment volatility: 2-5× GDP volatility      │
    │ □ No explosive growth (bounded)                    │
    │ □ No collapse to zero                              │
    │                                                    │
    └────────────────────────────────────────────────────┘
```

## Parameter Sensitivity Analysis

```
    SYSTEMATIC PARAMETER EXPLORATION
    ════════════════════════════════
    
    For each parameter θ_i:
    
    [1] Baseline: θ_i = θ_i,base
    
    [2] Vary: θ_i ∈ [θ_min, θ_max]  (11 points)
    
    [3] For each value:
        • Run simulation T periods
        • Record KPIs
        • Compute steady-state or cycle statistics
        
    [4] Plot response curves: θ_i → KPI
    
    
    Example: Phillips curve slope sensitivity
    ──────────────────────────────────────────
    
    Parameter: φ (wage response to employment)
    Range: [0.1, 1.0]
    
    
    Response curves:
    
         Wage share (steady state)
         │
      70%│                              ╱
         │                          ╱
         │                      ╱
      65%│                  ╱
         │              ╱
      60%│          ╱
         │      ╱
      55%│──────
         └────────────────────────────→ φ
           0.1  0.3  0.5  0.7  0.9
           
           
         Cycle amplitude
         │
      15%│                              ╱
         │                          ╱
      10%│                      ╱
         │                  ╱
       5%│              ╱
         │          ╱
       0%│──────╱
         └────────────────────────────→ φ
           0.1  0.3  0.5  0.7  0.9
           
           
    Interpretation:
    
        Higher φ → Higher wage share (labor stronger)
                → Larger cycles (less damping)
                
                
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Sensitivity analysis reveals:                  │
    │    • Which parameters matter most               │
    │    • Robustness of results                      │
    │    • Parameter interaction effects              │
    │    • Plausible parameter ranges                 │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Shock Response Analysis

```
    IMPULSE RESPONSE FUNCTIONS
    ══════════════════════════
    
    Protocol:
    ────────
    
    [1] Run to steady state (t = 0 to t = T_steady)
    
    [2] At t = T_steady, apply shock:
    
        Δθ = +10% (or -10%, +25%, etc.)
        
    [3] Continue simulation for T_response periods
    
    [4] Record deviations from baseline:
    
        δX(t) = X_shock(t) - X_baseline(t)
        
        
    Metrics:
    ───────
    
    Impact multiplier:
        M = δX(∞) / Δθ
        
    Peak response:
        δX_max and time of peak t_peak
        
    Half-life:
        t_{1/2} where |δX(t_{1/2})| = 0.5·|δX(∞)|
        
    Oscillation:
        Present/absent, period if present
        
        
    Example: Productivity shock (+10% to α_A)
    ──────────────────────────────────────────
    
         δY (% deviation)
         │
       0%├────────────────────────────
         │╲
         │ ╲
      -2%│  ╲
         │   ╲__________
      -4%│              ────────  New SS
         │
         └────────────────────────────→ t
            0   5   10  15  20  years
            ↑
          Shock
          
    Impact: -4% (higher productivity → less employment → less AD)
    Half-life: ~5 years
    No oscillation (monotonic adjustment)
```

## Multi-Parameter Calibration (Optimization)

```
    OBJECTIVE FUNCTION APPROACH
    ═══════════════════════════
    
    Define loss function:
    
        L(θ) = Σ_i w_i·(r_i(θ) - r_i,target)²
        
    where:
        θ = parameter vector
        r_i = i-th ratio (K/Y, D/Y, etc.)
        w_i = weight on i-th ratio
        
        
    Minimize:
    
        θ* = argmin_θ L(θ)
        
        
    Methods:
    ───────
    
    1. GRID SEARCH (Exhaustive)
       
       For each combination of θ values:
           Simulate
           Compute L(θ)
           
       Choose θ with minimum L
       
       Pros: Guaranteed to find global min (if grid fine enough)
       Cons: Exponential in # parameters
       
       
    2. GRADIENT DESCENT (Local)
    
       θ_{k+1} = θ_k - η·∇L(θ_k)
       
       where η = learning rate
       
       Pros: Fast for smooth L
       Cons: Can get stuck in local minima
       
       
    3. NELDER-MEAD (Simplex)
    
       Downhill simplex method
       Doesn't require derivatives
       
       Pros: Robust, derivative-free
       Cons: Slow for high dimensions
       
       
    4. GENETIC ALGORITHM (Global)
    
       Evolutionary search
       Population of θ vectors
       Selection, crossover, mutation
       
       Pros: Global search, handles discontinuities
       Cons: Many function evaluations
```

## Moment Matching

```
    CALIBRATE TO MATCH EMPIRICAL MOMENTS
    ════════════════════════════════════
    
    Empirical data provides moments:
    
        μ_Y = E[Y] = mean of GDP
        σ_Y = std[Y] = volatility of GDP
        ρ_Y(k) = autocorrelation of Y at lag k
        
        
    Model produces moments:
    
        Run simulation, compute:
        
        μ̂_Y = (1/T)·Σ Y_t
        σ̂_Y = sqrt((1/T)·Σ(Y_t - μ̂_Y)²)
        ρ̂_Y(k) = corr(Y_t, Y_{t-k})
        
        
    Match moments:
    
        Minimize: Σ (moment_empirical - moment_model)²
        
        
    Example: Business cycle properties
    ───────────────────────────────────
    
    Empirical (US data 1950-2020):
    
        σ_Y = 0.025  (2.5% std dev around trend)
        σ_I = 0.08   (8% std dev)
        σ_I/σ_Y = 3.2  (investment 3.2× more volatile)
        ρ_Y(1) = 0.85  (high persistence)
        
        
    Model parameters must produce similar moments
    
    Adjust:
        γ_π, γ_u in investment function
        c in consumption function
        φ in Phillips curve
        
    Until:
        σ̂_I/σ̂_Y ≈ 3.2
        ρ̂_Y(1) ≈ 0.85
```

## Cross-Validation Procedure

```
    SPLIT-SAMPLE VALIDATION
    ═══════════════════════
    
    Data: 1950-2020 (70 years)
    
    Split:
        Training: 1950-1990 (40 years)
        Test:     1990-2020 (30 years)
        
        
    Procedure:
    ─────────
    
    [1] Calibrate parameters using 1950-1990 data
    
        θ* = calibrate(data_1950_1990)
        
    [2] Simulate 1990-2020 using θ*
    
        Y_sim = simulate(θ*, T=30, Y_0=Y_1990)
        
    [3] Compare to actual 1990-2020:
    
        RMSE = sqrt(mean((Y_sim - Y_actual)²))
        
        Correlation = corr(Y_sim, Y_actual)
        
    [4] If poor fit:
        → Model misspecified
        → Structural break occurred
        → Parameters not stable
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Don't expect perfect fit (Moore's point!)      │
    │                                                  │
    │  Goal: Capture qualitative patterns             │
    │    • Growth rate range                          │
    │    • Cycle characteristics                      │
    │    • Crisis dynamics                            │
    │                                                  │
    │  Not: Precise quantitative prediction           │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Scenario Analysis Framework

```
    EXPLORING ALTERNATIVE FUTURES
    ═════════════════════════════
    
    Instead of "forecasting", analyze scenarios:
    
    
    SCENARIO 1: High investment (optimistic)
    ────────────────────────────────────────
    
        ε = +0.05  (animal spirits boost)
        BR = 0.02  (low rates)
        
        Result:
            ẏ ≈ 4%
            u ≈ 85%
            d rises to 1.8
            
            
    SCENARIO 2: Baseline (moderate)
    ───────────────────────────────
    
        ε = 0
        BR = 0.03
        
        Result:
            ẏ ≈ 3%
            u ≈ 78%
            d stable at 1.5
            
            
    SCENARIO 3: Austerity (pessimistic)
    ───────────────────────────────────
    
        ε = -0.03  (animal spirits depressed)
        BR = 0.05  (high rates)
        G/Y reduced from 0.20 to 0.15 (fiscal consolidation)
        
        Result:
            ẏ ≈ 1%
            u ≈ 70%
            d falls but Y falls more (d/Y may rise!)
            
            
    Compare scenarios:
    ─────────────────
    
         Y (level)
         │     Scenario 1 (high I)
         │    ╱╱
         │   ╱
         │  ╱  Scenario 2 (baseline)
         │ ╱
         │╱  Scenario 3 (austerity)
         └─────────────────────────────→ t
           0    10    20    30   years
           
           
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Scenarios show RANGE of possibilities          │
    │  Not "the forecast"                             │
    │                                                  │
    │  Conditional: "If policy X, then likely Y"      │
    │  Not deterministic: "Will be Y"                 │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Diagnostic Ratios for Model Health

```
    RUN-TIME DIAGNOSTICS
    ════════════════════
    
    Compute each period, flag if out of range:
    
    
    ┌────────────────────────────────────────────────────┐
    │ RATIO CHECKS                                       │
    ├────────────────────────────────────────────────────┤
    │                                                    │
    │ Capacity utilization:                              │
    │   u = Y/(K/ν)                                      │
    │   FLAG if u > 1.0  (over capacity!)               │
    │   FLAG if u < 0.5  (severe recession)             │
    │                                                    │
    │ Employment rate:                                   │
    │   e = L/N                                          │
    │   FLAG if e > 1.0  (impossible!)                  │
    │   FLAG if e < 0.4  (depression)                   │
    │                                                    │
    │ Debt service ratio:                                │
    │   DSR = i·D/Y                                      │
    │   FLAG if DSR > 0.20  (20% to interest)           │
    │                                                    │
    │ Debt-GDP:                                          │
    │   d = D/Y                                          │
    │   FLAG if d > 3.0  (300% of GDP)                  │
    │                                                    │
    │ Profit share:                                      │
    │   Π/Y                                              │
    │   FLAG if Π/Y < 0.1  (profit squeeze)             │
    │   FLAG if Π/Y > 0.6  (excessive)                  │
    │                                                    │
    └────────────────────────────────────────────────────┘
    
    
    Implementation:
    
        if u[t] > 1.0:
            print(f"WARNING: Over capacity at t={t}, u={u[t]}")
            # Either: stop simulation
            # Or: enforce bound: u = min(u, 1.0)
```

## Growth Accounting Decomposition

```
    SOURCES OF GROWTH ANALYSIS
    ══════════════════════════
    
    Production function approach:
    
        Y = A·F(K, L)
        
    Taking logs and differentiating:
    
        Ẏ/Y = Ȧ/A + α·K̇/K + (1-α)·L̇/L
        
    where α = capital's share
    
    
    Decompose observed ẏ into:
    
        ẏ = [Ȧ/A] + [α·K̇/K] + [(1-α)·L̇/L]
            ↑          ↑            ↑
           TFP      Capital     Labor
          growth  contribution contribution
          
          
    Example calculation:
    
        ẏ = 3.0%
        Ȧ/A = 1.5%  (productivity growth)
        K̇/K = 4.0%  (capital growth)
        L̇/L = 1.0%  (employment growth)
        α = 0.33
        
        Check: 1.5% + 0.33·4.0% + 0.67·1.0%
             = 1.5% + 1.32% + 0.67%
             = 3.49% ≈ 3.0% ✓
             
             
    Decomposition:
    
        TFP:     1.5% / 3.0% = 50%
        Capital: 1.32% / 3.0% = 44%
        Labor:   0.67% / 3.0% = 6%
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Growth accounting shows:                       │
    │    • Relative importance of factors             │
    │    • Where growth comes from                    │
    │    • What policy can affect                     │
    │                                                  │
    │  In Moore framework:                            │
    │    All three (A, K, L) respond to demand       │
    │    ∴ Growth is demand-led                       │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Comparative Dynamics (Not Statics!)

```
    POLICY EXPERIMENTS
    ══════════════════
    
    Instead of comparative STATICS (equilibrium shift):
    Use comparative DYNAMICS (trajectory shift)
    
    
    Experiment: Effect of interest rate cut
    ────────────────────────────────────────
    
    Baseline:  BR = 0.04 (4%)
    Policy:    BR = 0.02 (2%)
    
    
    Run both:
    
         Y (level)
         │
         │     Policy (BR=2%)
         │    ╱╱
         │   ╱
         │  ╱  Baseline (BR=4%)
         │ ╱
         │╱
         └─────────────────────────────→ t
           0    5    10   15   20  years
           ↑
         Policy
         change
         
         
    Compare TRAJECTORIES:
    
        ΔY(t) = Y_policy(t) - Y_baseline(t)
        
         ΔY
         │
      10%│              ╱────────  Long-run effect
         │            ╱
       5%│          ╱
         │        ╱
       0%├────╱──
         └─────────────────────────────→ t
           0    5    10   15   20
           
           
    Cumulative effect:
    
        Cumulative_gain = ∫ ΔY(t) dt
        
        = Additional output over 20 years
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Process analysis focuses on:                   │
    │    • Transition path (not just endpoints)       │
    │    • Adjustment speed                           │
    │    • Cumulative effects                         │
    │    • Dynamic interactions                        │
    │                                                  │
    │  More informative than static comparison!       │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Identifying Instability Sources

```
    DEBUGGING EXPLOSIVE BEHAVIOR
    ════════════════════════════
    
    If model explodes (variables → ∞):
    
    
    CHECK 1: Eigenvalues
    ───────────────────
    
    Compute Jacobian at steady state
    Get eigenvalues λ_i
    
    If any Re(λ_i) > 0 significantly:
        → Structurally unstable
        → May be intentional (Minsky) or bug
        
        
    CHECK 2: Positive feedbacks
    ──────────────────────────
    
    Trace loops:
    
    Example: Debt-investment loop
    
        D ↑ → Interest burden ↑ → Need more borrowing
           → D ↑ faster → EXPLOSIVE
           
    If no counteracting negative feedback:
        → Unsustainable
        
    Fix: Add constraints
        • Credit ceiling
        • Investment limited by profit
        • Forced deleveraging when d > d_max
        
        
    CHECK 3: Parameter values
    ────────────────────────
    
    Are parameters in reasonable ranges?
    
    Common errors:
    • Growth rates in decimal not percent (α=0.03 not α=3)
    • Time constants too small (τ=0.01 not τ=1)
    • Multiplicative factors too large
    
    
    CHECK 4: Time step
    ─────────────────
    
    If Δt too large relative to fastest dynamics:
        → Numerical instability
        
    Rule: Δt < 0.1·τ_min
    
    If τ_min = 0.1 year → need Δt < 0.01 year
```

## Practical Calibration Workflow

```
    STAGE-BY-STAGE CALIBRATION
    ══════════════════════════
    
    Don't calibrate everything at once!
    
    
    Stage 1: Capital accumulation only
    ──────────────────────────────────
    
    Variables: K, Y
    Parameters: i_0, δ, ν
    
    Target: K/Y = 3.0
    
    Calibrate:
        Choose i_0, δ such that K/Y → 3.0
        
        
    Stage 2: Add productivity
    ─────────────────────────
    
    New variables: A
    New parameters: α_A
    
    Target: Ȧ/A = 0.02
    
    Calibrate:
        Choose α_A = 0.02
        Verify: K/Y still ≈ 3.0 (may need to adjust i_0)
        
        
    Stage 3: Add employment
    ───────────────────────
    
    New variables: L, N, e
    New parameters: β_N
    
    Target: e = 0.75
    
    Calibrate:
        Choose β_N such that L/N → 0.75
        Verify: Previous ratios still hold
        
        
    Continue...
    ──────────
    
    Each stage:
    • Add one new component
    • Calibrate new parameters
    • Verify previous calibration still holds
    • If not, re-calibrate
    
    
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Progressive calibration:                       │
    │    • Easier than calibrating all at once        │
    │    • Understand each component's role           │
    │    • Catch errors early                         │
    │    • Build intuition                            │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Dimensionless Formulation

```
    NORMALIZE TO REMOVE SCALE DEPENDENCE
    ════════════════════════════════════
    
    Instead of levels, use ratios:
    
    
    Dimensional variables:          Dimensionless variables:
    ──────────────────────          ────────────────────────
    
    K (capital stock)        →      k = K/Y
    D (debt stock)           →      d = D/Y
    M (money stock)          →      m = M/Y
    I (investment)           →      i = I/Y
    C (consumption)          →      c = C/Y
    
    
    System in normalized form:
    
        dk/dt = [i - (ẏ+δ)·k]
        dd/dt = [(I-Π)/Y - ẏ·d]
        
        
    Advantages:
    ──────────
    
    1. Scale-independent (works for any economy size)
    2. Parameters interpretable (elasticities)
    3. Steady state obvious (dk/dt = 0 → i = (ẏ+δ)·k)
    4. Easier to calibrate
    
    
    Example: Goodwin model in normalized form
    ──────────────────────────────────────────
    
        State: (e, ω)  both ∈ [0,1]
        
        de/dt = e·[ẏ - (α+β)]
        dω/dt = ω·[φ(e) - (α+β)]
        
        No dimensional constants!
        
        
    Implementation:
    
        Work with ratios throughout
        Reconstruct levels only for plotting:
        
            Y(t) = Y_0·exp(∫ ẏ dt)
            K(t) = k(t)·Y(t)
            D(t) = d(t)·Y(t)
```

## Handling Initial Conditions

```
    SETTING INITIAL VALUES
    ══════════════════════
    
    APPROACH 1: Start from steady state
    ───────────────────────────────────
    
    Compute steady-state values analytically
    
    Example:
    
        K_0/Y_0 = k* = (i_0)/(ẏ + δ)
        
    If Y_0 = 100, i_0 = 0.24, ẏ = 0.03, δ = 0.05:
    
        K_0 = 3.0·100 = 300
        
        
    APPROACH 2: Start from empirical data
    ─────────────────────────────────────
    
    Use actual economy values from specific year:
    
        Y_0 = GDP_2020 = $21 trillion
        K_0 = Capital stock_2020 = $63 trillion
        D_0 = Private debt_2020 = $32 trillion
        etc.
        
        
    APPROACH 3: Run-in period
    ─────────────────────────
    
    Start with arbitrary values
    Run for T_runin periods (discard)
    Use values at T_runin as "initial" conditions
    
        t ∈ [-100, 0]: Run-in (discard)
        t ∈ [0, 100]: Analysis period
        
    Avoids transient effects from arbitrary ICs
    
    
    CONSISTENCY REQUIREMENT:
    ───────────────────────
    
    Initial stocks must satisfy accounting:
    
        For each sector:
            A_0 = L_0 + NW_0  ✓
            
        Global:
            Σ Financial Assets = Σ Financial Liabilities  ✓
```

## Model Comparison Metrics

```
    COMPARING ALTERNATIVE MODELS
    ════════════════════════════
    
    Model A vs Model B:
    
    
    METRIC 1: Goodness-of-fit to data
    ─────────────────────────────────
    
        RMSE_A = sqrt(mean((Y_A - Y_actual)²))
        RMSE_B = sqrt(mean((Y_B - Y_actual)²))
        
        Lower RMSE = better fit
        
        
    METRIC 2: Moment matching
    ─────────────────────────
    
        For each moment m:
        
            error_A,m = |moment_A,m - moment_data,m|
            error_B,m = |moment_B,m - moment_data,m|
            
        Score = Σ w_m·error_m
        
        Lower score = better match
        
        
    METRIC 3: Qualitative behavior
    ──────────────────────────────
    
        Does model exhibit:
        □ Realistic cycles?
        □ Minsky moments?
        □ Reasonable responses to shocks?
        □ Stable calibration?
        
        Subjective assessment
        
        
    METRIC 4: Parsimony
    ───────────────────
    
        # of parameters in model
        
        Prefer simpler model if fits equally well
        
        
    METRIC 5: Economic coherence
    ────────────────────────────
    
        Are mechanisms realistic?
        Do equations make economic sense?
        Are parameters interpretable?
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Moore's criterion: UNDERSTANDING                │
    │                                                  │
    │  Not just statistical fit                       │
    │  But explanatory power + realism                │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Summary: Calibration Best Practices

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  CALIBRATION & VALIDATION WORKFLOW                           ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  STEP 1: Set targets (empirical steady-state ratios)         ║
║          K/Y, D/Y, M/Y, I/Y, C/Y, wage share, etc.          ║
║                                                               ║
║  STEP 2: Derive implied flow rates                           ║
║          From stock/flow consistency                          ║
║                                                               ║
║  STEP 3: Choose functional forms                             ║
║          Linear, logistic, time-constant, etc.               ║
║                                                               ║
║  STEP 4: Calibrate progressively                             ║
║          One component at a time, verify previous hold       ║
║                                                               ║
║  STEP 5: Check accounting closure                            ║
║          Every period: S≡I, sectoral balances, Godley rows  ║
║                                                               ║
║  STEP 6: Validate against stylized facts                     ║
║          Growth rates, volatilities, cycle properties        ║
║                                                               ║
║  STEP 7: Sensitivity analysis                                ║
║          Vary each parameter, map responses                   ║
║                                                               ║
║  STEP 8: Shock response analysis                             ║
║          Impulse responses, check plausibility               ║
║                                                               ║
║  STEP 9: Scenario analysis                                    ║
║          Alternative futures, not single forecast            ║
║                                                               ║
║  STEP 10: Diagnostic monitoring                              ║
║           Runtime checks, flag anomalies                      ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
