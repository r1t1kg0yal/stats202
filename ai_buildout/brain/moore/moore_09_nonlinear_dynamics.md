# MOORE PART 9: NONLINEAR DYNAMICS & COMPLEXITY IN SFC MODELS

## Why Nonlinearity Matters

```
╔═══════════════════════════════════════════════════════════════╗
║  LINEAR SYSTEMS (Too restrictive)                            ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Form: ẋ = Ax + Bu                                           ║
║                                                               ║
║  Properties:                                                  ║
║    • Superposition: f(x₁) + f(x₂) = f(x₁ + x₂)             ║
║    • Proportionality: f(αx) = α·f(x)                        ║
║    • Closed-form solutions exist                             ║
║    • Stable or unstable (no chaos)                           ║
║                                                               ║
║  Problem: REAL ECONOMIES ARE NONLINEAR                       ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

╔═══════════════════════════════════════════════════════════════╗
║  NONLINEAR SYSTEMS (Necessary for realism)                   ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Form: ẋ = f(x, y, z, ...)  where f is nonlinear            ║
║                                                               ║
║  Properties:                                                  ║
║    • No superposition                                         ║
║    • Emergent behaviors (chaos, bifurcations)                ║
║    • Sensitive to initial conditions                         ║
║    • No closed-form solutions (simulation required)          ║
║    • Can have multiple equilibria, limit cycles              ║
║                                                               ║
║  Types of nonlinearity in economics:                         ║
║    • Multiplication of variables: e·ω (Goodwin model)       ║
║    • Ratios: D/Y, Π/K                                        ║
║    • Saturations: min(), max()                               ║
║    • Thresholds: if-then logic                               ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

## Sources of Nonlinearity in SFC Models

```
    TYPE 1: MULTIPLICATIVE INTERACTIONS
    ═══════════════════════════════════
    
    Goodwin Model (employment × wage share):
    
        dω/dt = ω · [φ(e) - (α+β)]
        de/dt = e · [-(α+β) + (I/Y)·(Y/K) - δ]
        
    where I/Y depends on both π (profit rate) and ω (wage share):
    
        π = (1-ω)·(Y/K)  (nonlinear: involves product)
        
        I/Y = f(π) = f((1-ω)·(Y/K))
        
        ∴ de/dt involves e·ω interaction → NONLINEAR
        
        
    Result: Perpetual cycles (predator-prey dynamics)
    
        ω
         │         ╱──→╲
         │       ╱      ╲
      70%│      ↑        ↓
         │       ╲      ╱
         │         ╲←──╱
      55%│
         └───────────────────→ e
               60%      90%
               
    No equilibrium! Endless cycling
    
    
    TYPE 2: RATIO DYNAMICS
    ══════════════════════
    
    Debt-GDP ratio:
    
        d = D/Y
        
        ḋ/d = Ḋ/D - Ẏ/Y
        
    If Ḋ/D > Ẏ/Y → d rises (debt grows faster than income)
    If Ḋ/D < Ẏ/Y → d falls
    
    Minsky instability: Debt can grow faster than income
    
        ḋ = d·[(I - Π)/D - ẏ]
        
    If investment debt-financed and Π < I:
        → d rises
        → Interest burden (i·D) rises
        → Π - i·D falls
        → More debt needed
        → d rises faster
        → EXPLOSIVE!
        
        
    TYPE 3: SATURATION FUNCTIONS
    ════════════════════════════
    
    Phillips curve with bounds:
    
        φ(e) = φ_max / (1 + exp(-λ·(e - e_0)))
        
        e → 0:   φ → 0 (wage deflation limited)
        e → 1:   φ → φ_max (wage growth saturates)
        
        
    TYPE 4: THRESHOLD EFFECTS
    ═════════════════════════
    
    Investment response to profit rate:
    
        I/Y = { i_min           if π < π_min
              { i_0 + β·(π-π*)  if π_min ≤ π ≤ π_max  
              { i_max           if π > π_max
              
    Creates piecewise-linear dynamics
    
    
    TYPE 5: SWITCH FUNCTIONS
    ════════════════════════
    
    Policy rule:
    
        G = { G_high  if u < u*  (recession)
            { G_low   if u ≥ u*  (boom)
            
    Discontinuous switch creates complex dynamics
```

## Phase Diagrams & State Space

```
    2D PHASE PORTRAIT (Goodwin Model)
    ═════════════════════════════════
    
    State variables: (e, ω)
    
    Isoclines (where ė = 0, ω̇ = 0):
    
        ė = 0:  Vertical line at e = e*
        ω̇ = 0:  Horizontal line at ω = ω*
        
        
    Phase portrait:
    
        ω
         │
         │   IV    │    I
         │  (ω̇<0, │ (ω̇>0,
         │   ė<0) │  ė>0)
         ├─────────┼─────────
      ω* │         │×  
         │         │(e*,ω*)
         ├─────────┼─────────
         │  III    │   II
         │  (ω̇<0, │ (ω̇>0,
         │   ė>0) │  ė<0)
         │         │
         └─────────┴──────────→ e
                  e*
                  
    Trajectory: Counterclockwise cycles around (e*, ω*)
    
    
    Vector field:
    
        At each point (e, ω):
        Arrow shows (ė, ω̇) direction
        
        ↗ (both positive)
        → (e positive, ω zero)
        ↘ (e positive, ω negative)
        etc.
```

## Bifurcation Analysis

```
    PARAMETER-DEPENDENT DYNAMICS
    ════════════════════════════
    
    As parameter θ varies, system behavior changes qualitatively
    
    
    Example: Investment sensitivity to profit rate
    ──────────────────────────────────────────────
    
    I/Y = γ·(π - π*)
    
    As γ increases:
    
    
    γ < γ₁:  Stable spiral
         ↓   (damped oscillations → equilibrium)
         
         
    γ = γ₁:  BIFURCATION POINT
         ↓   (Hopf bifurcation)
         
         
    γ₁ < γ < γ₂:  Limit cycle
         ↓         (perpetual oscillation)
         
         
    γ = γ₂:  BIFURCATION POINT
         ↓   (Period-doubling)
         
         
    γ > γ₂:  Chaos
             (bounded but aperiodic)
             
             
    Bifurcation diagram:
    
        Amplitude
         │                        ╱ ╲
         │                    ╱ ╲   ╲ ╱ (chaos)
         │                ╱ ╲           ╲
         │            ╱ ╲                 ╲
         │        ╱ ╲                       ╲
         │    ╱ ╲                             ╲
         │───────────────────────────────────────→ γ
           0  γ₁            γ₂
           
    Stable  Cycles  Period-doubling  Chaos
```

## Goodwin-Minsky Integration

```
    EXTENDING GOODWIN WITH DEBT DYNAMICS
    ════════════════════════════════════
    
    Goodwin (2D): employment-wage cycles
    
        ė = e·[...]
        ω̇ = ω·[...]
        
        
    Minsky extension (3D): Add debt ratio
    
        ḋ = d·[(I-Π)/D - ẏ]
        
        
    Full system:
    
        [1] de/dt = e·[ẏ - (α+β)]
        
        [2] dω/dt = ω·[φ(e) - (α+β)]
        
        [3] dd/dt = d·[(I-Π)/D - ẏ]
        
    where:
        ẏ = (I/Y)·(Y/K) - δ
        I/Y = f(π, d)  (depends on profit AND debt)
        π = (1-ω)·(Y/K)
        Π = (1-ω-i·d)·Y  (profit after interest)
        
        
    Dynamics:
    ────────
    
    Phase 1: Stable growth (low d)
    Phase 2: Debt builds up (d rises)
    Phase 3: Minsky moment (d → d_critical)
    Phase 4: Crisis & deleveraging (d falls sharply)
    
    
    3D trajectory:
    
         d
         │    ╱╲
         │   ╱  ╲     Crisis!
         │  ╱    ╲   
         │ ╱      ╲╱  (crash)
         │╱
         └──────────────→ ω
          ╱           e
         
    System spirals up in d until crisis
```

## Chaotic Dynamics (Keen's Model)

```
    CONDITIONS FOR CHAOS IN ECONOMIC MODELS
    ═══════════════════════════════════════
    
    Keen (1995) extended Goodwin-Minsky to show chaos:
    
    Requirements:
    ─────────────
    
    1. At least 3 state variables (e, ω, d)
    2. Nonlinear interactions (products, ratios)
    3. Positive feedback (debt-investment)
    4. Negative feedback (employment-wages)
    
    
    Result: Bounded but aperiodic behavior
    
        d(t)
         │
         │  ×
         │   ×      ×
         │     ×  ×   × ×
         │ ×    ×       ×  ×
         │                  × ×
         │  ×   ×                ×
         └─────────────────────────────→ t
         
         Never repeats, but stays in range [d_min, d_max]
         
         
    Sensitive dependence:
    
        Two runs, d(0) = 1.500 vs d(0) = 1.501
        
        Initially identical, diverge exponentially after ~20 periods
        
        
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  IMPLICATION: Long-run prediction impossible    │
    │                                                  │
    │  BUT: Can understand the attractor               │
    │       (Range of possible behaviors)             │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Hysteresis & Path Dependence

```
    HISTORY MATTERS
    ═══════════════
    
    Hysteresis: Current state depends on past path
    
    
    Example: Unemployment Hysteresis
    ────────────────────────────────
    
    Recession occurs → U rises → Skills atrophy
                                 → Long-term unemployed
                                 → Effective labor force ↓
                                 → NAIRU rises
                                 
    Even after recession ends, U stays high!
    
    
        U
         │     Recession
         │        ↓
      10%│    ┌───────┐
         │    │       │
         │    │       └──────────  ← Stays high (hysteresis)
       6%├────┘
         │
       4%│
         └────────────────────────→ t
         
         Before      During    After
         
         
    Mathematical form:
    
        NAIRU_t = NAIRU_{t-1} + h·(U_{t-1} - NAIRU_{t-1})
        
        If U > NAIRU for extended period
        → NAIRU rises
        
        (Skills deteriorate, workers discouraged)
        
        
    Implementation in model:
    
        [U] ─→ [-] ←─ [NAIRU] ─→ [×h] ─→ [dNAIRU/dt] ─→ ∫ ─→ [NAIRU]
                                   ↑                           │
                                   └───────────────────────────┘
                                   
    Path-dependent: Future NAIRU depends on past U
```

## Multiple Equilibria & Regime Switching

```
    MULTIPLE ATTRACTORS
    ═══════════════════
    
    Many SFC models have multiple equilibria:
    
    
    Example: High-employment vs Low-employment
    ──────────────────────────────────────────
    
    Investment function:
    
        I/Y = i_0 + β·(π - π*)
        
    Profit rate:
        π = f(Y, ω)
        
    Can have two stable equilibria:
    
    
         Y
         │
         │      ╱
         │    ╱ 
      Y_H├───×────────  High equilibrium (stable)
         │  ╱│╲
         │╱  │  ╲
         │   │    ╲
         │   │      ╲
      Y_L├───┼───────×  Low equilibrium (stable)
         │   │      ╱
         │   │    ╱
         │   × (unstable)
         │
         └───────────────→ I/Y
         
         
    Starting from Y₀:
    
        If Y₀ > Y_unstable → converge to Y_H
        If Y₀ < Y_unstable → converge to Y_L
        
    "Poverty trap" = stuck at Y_L
    
    Need BIG push to escape to Y_H
    
    
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Policy implication:                            │
    │    Small stimulus → return to Y_L (ineffective) │
    │    Large stimulus → jump to Y_H (effective)     │
    │                                                  │
    │  History determines which equilibrium!          │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Limit Cycles (Sustained Oscillations)

```
    PREDATOR-PREY DYNAMICS IN ECONOMICS
    ═══════════════════════════════════
    
    Goodwin employment-wage cycle:
    
        ė = e·[ẏ - (α+β)]
        ω̇ = ω·[φ(e) - (α+β)]
        
    Has limit cycle: Perpetual oscillation
    
    
         ω (wage share)
         │
         │      2 →→→ 1
         │     ↓       ↑
      70%│    ↓         ↑
         │   ↓           ↑
         │  3             0
      60%│   ↓         ↑
         │    ↓       ↑
         │     4 ←←← 5
      55%│
         └────────────────────→ e
              70%    85%
              
    Quadrants:
    
    0→1: e high → wages rise (ω↑)
    1→2: ω high → profits low → investment low → e falls
    2→3: e low → wages fall (ω↓)
    3→4: ω low → profits high → investment high → e rises
    4→0: Cycle repeats
    
    
    Period ≈ 15-25 years (empirically)
    
    
    Amplitude depends on:
        φ = Phillips curve slope
        I(π) = Investment sensitivity
```

## Catastrophe Theory: Sudden Transitions

```
    FOLD CATASTROPHE (Minsky Moment)
    ════════════════════════════════
    
    System has equilibria that appear/disappear
    
    
    Control parameter: Debt ratio d
    
    
    Equilibrium output as function of d:
    
         Y*
         │     Stable branch
         │  ─────────────
         │             ╲
         │              ╲ Unstable
         │               ╲
         │                ╲
         │                 ╲
         │                  └─── Fold point
         └──────────────────────────→ d
                              d_crit
                              
                              
    As d increases:
    
        d < d_crit:  System stable at high Y
        d = d_crit:  CATASTROPHE (fold bifurcation)
        d > d_crit:  No equilibrium! System crashes
        
        
    Time dynamics:
    
         Y
         │
         │  ────────────────
         │                  ╲
         │                   ╲
         │                    ╲
         │                     ╲  Sudden
         │                      ╲ collapse
         │                       ↓
         │                        ────────
         └──────────────────────────────────→ t
                               t_crisis
                               
                               
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Crisis is ENDOGENOUS                           │
    │  Emerges from system dynamics                   │
    │  Not "exogenous shock"                          │
    │                                                  │
    │  Debt accumulation → Fragility → Crash          │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Discrete-Time vs Continuous-Time

```
    TWO FORMULATIONS
    ════════════════
    
    DISCRETE TIME (Difference equations):
    ─────────────────────────────────────
    
        Y_{t+1} = f(Y_t, K_t, ...)
        K_{t+1} = K_t + I_t - δ·K_t
        
    Pros: Natural for annual/quarterly data
    Cons: Step size Δt = 1 (period), not flexible
          Can create spurious oscillations
          
          
    CONTINUOUS TIME (Differential equations):
    ─────────────────────────────────────────
    
        dY/dt = f(Y, K, ...)
        dK/dt = I - δ·K
        
    Pros: Flexible Δt, smooth dynamics
          Minsky uses this!
    Cons: Must choose integration method
    
    
    CONVERSION:
    ──────────
    
    Discrete → Continuous (approximation):
    
        Y_{t+1} - Y_t ≈ dY/dt · Δt
        
        ∴ dY/dt ≈ (Y_{t+1} - Y_t)/Δt
        
        
    Continuous → Discrete:
    
        Integrate: Y_{t+1} = Y_t + ∫_t^{t+Δt} f(Y,K,...) dτ
```

## Stochastic Extensions

```
    ADDING RANDOMNESS (Carefully!)
    ══════════════════════════════
    
    Deterministic core + stochastic shocks:
    
        dX/dt = f(X) + σ·η(t)
        
    where:
        f(X) = deterministic dynamics
        σ = shock volatility
        η(t) = random noise
        
        
    Types of noise:
    ───────────────
    
    1. WHITE NOISE
       η(t) ~ N(0,1), uncorrelated
       
       Example: ε_t ~ N(0, σ_ε)  (animal spirits shock)
       
       
    2. COLORED NOISE (autocorrelated)
       η_t = ρ·η_{t-1} + ε_t
       
       Example: Persistent confidence shifts
       
       
    3. JUMP PROCESS
       η(t) = 0 most of time
       η(t) = large with small probability
       
       Example: Sudden regime shifts, crises
       
       
    CAUTION:
    ───────
    
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  Moore emphasizes:                              │
    │    Endogenous dynamics >> Random shocks         │
    │                                                  │
    │  Don't use shocks to "explain" cycles           │
    │  Cycles should emerge from structure            │
    │                                                  │
    │  Use shocks only to:                            │
    │    • Test robustness                            │
    │    • Model truly random events (weather, etc.)  │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Dimensionality & Complexity

```
    STATE SPACE DIMENSIONALITY
    ══════════════════════════
    
    N = number of stock variables
    
    
    N = 1:  Simple dynamics
            • Monotonic approach to equilibrium
            • Exponential growth/decay
            • No oscillations possible
            
            
    N = 2:  Richer dynamics
            • Spirals, cycles possible
            • Poincaré-Bendixson: Either equilibrium or limit cycle
            • No chaos
            
    Example: Goodwin (e, ω)
    
    
    N = 3:  Chaos possible
            • Strange attractors
            • Sensitive dependence
            • Bounded but aperiodic
            
    Example: Keen's Goodwin-Minsky (e, ω, d)
    
    
    N ≥ 4:  High-dimensional dynamics
            • Multiple timescales
            • Complex attractors
            • Very difficult to visualize
            
    Typical SFC model: N = 10-30 state variables
    
    
    ┌──────────────────────────────────────────────────┐
    │                                                  │
    │  As N increases:                                │
    │    • Richer dynamics possible                   │
    │    • More difficult to analyze                  │
    │    • More parameters to calibrate               │
    │    • Simulation essential                        │
    │                                                  │
    └──────────────────────────────────────────────────┘
```

## Practical Nonlinear Techniques

```
    TECHNIQUE 1: Smoothing Discontinuities
    ══════════════════════════════════════
    
    Instead of: Y = { Y₁  if X < X*
                    { Y₂  if X ≥ X*
                    
    Use smooth approximation:
    
        Y = Y₁ + (Y₂-Y₁)/(1 + e^{-k(X-X*)})
        
    where k = steepness (large k ≈ sharp transition)
    
    
    TECHNIQUE 2: Avoiding Division by Zero
    ══════════════════════════════════════
    
    Instead of: r = Π/K  (undefined if K=0)
    
    Use: r = Π/(K + ε)  where ε = 1e-10
    
    Or: r = Π/max(K, K_min)  where K_min = 0.01
    
    
    TECHNIQUE 3: Soft Constraints
    ═════════════════════════════
    
    Instead of: u = min(Y/K_cap, 1)  (hard ceiling)
    
    Use penalty function:
    
        Cost(u) = { 0              if u < u_max
                  { α·(u-u_max)²   if u ≥ u_max
                  
    Firms avoid going above u_max due to rising costs
    
    
    TECHNIQUE 4: Regime Blending
    ════════════════════════════
    
    Instead of switching: Switch(condition)
    
    Use weight function:
    
        Y = w(X)·Y_regime1 + (1-w(X))·Y_regime2
        
    where w(X) = 1/(1 + e^{-k(X-X*)})  ∈ [0,1]
    
    Smoothly blend between regimes
```

## Summary: Nonlinear SFC Modeling

```
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║  NONLINEAR DYNAMICS IN SFC MODELS                            ║
║                                                               ║
║  ─────────────────────────────────────────────────────────── ║
║                                                               ║
║  Sources of nonlinearity:                                    ║
║    1. Products of variables (e·ω, π·K)                      ║
║    2. Ratios (D/Y, Π/K, W/P)                                ║
║    3. Saturation functions (logistic, tanh)                  ║
║    4. Thresholds and switches                                ║
║                                                               ║
║  Resulting behaviors:                                         ║
║    • Limit cycles (Goodwin)                                  ║
║    • Chaos (Keen extension)                                  ║
║    • Bifurcations (parameter-dependent regime change)        ║
║    • Hysteresis (path dependence)                            ║
║    • Multiple equilibria                                      ║
║    • Catastrophes (Minsky moments)                           ║
║                                                               ║
║  Analysis tools:                                             ║
║    • Phase diagrams (2D, 3D)                                ║
║    • Bifurcation analysis                                    ║
║    • Lyapunov exponents (chaos detection)                    ║
║    • Basin of attraction mapping                             ║
║                                                               ║
║  Practical techniques:                                        ║
║    • Smooth approximations to discontinuities                ║
║    • Bounds to prevent explosions                            ║
║    • Multiple timescales                                      ║
║    • Adaptive integration                                     ║
║                                                               ║
║  Moore's insight: Complex endogenous dynamics                ║
║                   more important than random shocks          ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```
