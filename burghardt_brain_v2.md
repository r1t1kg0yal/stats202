# Analyst Brain: Burghardt & Belton

> **Template:** v2
> **Analyst:** Galen Burghardt & Terrence Belton
> **Source:** *The Treasury Bond Basis: An In-Depth Analysis for Hedgers, Speculators, and Arbitrageurs* (3rd ed., 2005)
> **Domain:** Treasury Futures / Bond Basis / Delivery Options / CTD Mechanics / Basis Trading / Hedging / Volatility Arbitrage / Global Govt Bond Futures

---

## Core Thesis

Treasury bond futures are not simple forward contracts -- they are forward contracts with a bundle of real options embedded in the delivery mechanism, all held by the short. The cash-futures basis decomposes exactly into carry plus delivery option value (BNOC), and this decomposition is the master key to everything: hedging, trading, arbitrage, and valuation. The conversion factor system, designed to equalize deliverable bonds, instead creates a rich option structure because it only achieves true equalization at a single yield (6%). Away from that yield, one bond becomes cheapest to deliver, the others become expensive, and the gap between them is the source of all optionality. Most participants misunderstand the basis because they treat futures as a forward on "bonds" generically, when in reality futures track the minimum of a set of converted bond prices -- a fundamentally option-like payoff. The entire basis trading ecosystem flows from this single structural fact.

---

## Axioms

| ID | Axiom | Therefore... |
|----|-------|-------------|
| A1 | Basis ≡ Carry + BNOC, always, by construction | Every basis observation decomposes into two independent components: the cost of holding the bond (carry) and the market price of the short's delivery options (BNOC). Analyzing the basis means analyzing these two channels separately. |
| A2 | Conversion factors equalize deliverable bonds only at 6% yield; deviations from 6% create a strict ordering | At yields above 6%, high-duration bonds are cheapest; below 6%, low-duration bonds are cheapest. The sensitivity of this ordering to yield changes is the source of the switch option. |
| A3 | The short holds three classes of real options: quality (switch), end-of-month, and timing; the long holds none | These options have positive value, so the futures price is depressed below the CTD's forward price by the aggregate option premium. The short never pays for these options; they are embedded in the contract design. |
| A4 | CTD selection obeys two orthogonal rules: duration (yield level effect) and yield (yield spread effect) | The duration rule determines CTD given uniform yields; the yield rule determines CTD given uniform duration. In practice both operate simultaneously, and yield spread changes can override yield level effects. |
| A5 | The CTD's BNOC is pure delivery option value; every other bond's BNOC = option value + expensiveness premium | Non-CTD bonds are analogous to in-the-money options (intrinsic + time value). The CTD is at-the-money (time value only). Only the CTD's BNOC directly measures what the market charges for optionality. |
| A6 | Spot yields and term repo rates are independent over short horizons | Forward prices are functions of both, but through mechanically distinct channels. Spot DV01 is ~50x larger than repo DV01. A complete hedge requires offsetting both exposures separately. |
| A7 | Systematic yield spread behavior -- curve flattens as yields rise, steepens as yields fall -- dampens switch option value | This is equivalent to the crossover yield moving away from the current yield as yields move, i.e., a moving strike. It makes CTD switches harder to trigger than a parallel-shift model implies. |
| A8 | When open interest exceeds deliverable supply of the CTD, arbitrage relationships break and BNOC can go negative | Negative BNOC is not a free lunch -- it prices the probability of delivery failure. The basis market transitions from an options market to a supply-constraint market. |
| A9 | Buying the basis is buying volatility; selling the basis is selling volatility | The basis market is a synthetic options market that trades alongside the exchange-listed options market. When the two markets disagree on volatility pricing, arbitrage opportunities exist. |

---

## Mental Models

### M1: Basis Decomposition Machine

**In one sentence:** The master identity that decomposes every observable basis into carry (deterministic, decays linearly to zero) and BNOC (stochastic, represents the market's option premium).

**Diagram:**

    MASTER IDENTITY:
    ────────────────

    [Basis] ≡ [Carry] + [BNOC]
        │          │         │
        │          │         └── Market price of short's delivery options
        │          │             (stochastic, option-like decay)
        │          │
        │          └── Coupon income - financing cost
        │              (deterministic, linear time decay)
        │
        └── Cash Price - (Factor × Futures Price)
            (observable in market)


    CARRY CALCULATION:
    ──────────────────
    Carry = (C/2) × (Days/CouponPeriod) - (P + AI) × (RP/100) × (Days/360)
                    ▲                              ▲
                    │                              │
              coupon accrual                 financing cost
              (actual/actual)               (actual/360)

    {IF yield curve positive} → Carry > 0 → Basis > BNOC
    {IF yield curve inverted} → Carry < 0 → Basis < BNOC


    WITH INTERVENING COUPON (one coupon before delivery):
    ──────────────────────────────────────────────────────
    Coupon Income = (C/2) × [D1/DCOUP1 + D2/DCOUP2]
    Financing Cost = (P+AI) × RP × D1/360 + P × RP × D2/360
    (principal resets after coupon payment)


    IMPLIED REPO RATE (IRR):
    ────────────────────────

    No intervening coupon:
    IRR = [(Invoice Price / Purchase Price) - 1] × (360 / n)

    One intervening coupon (reinvestment at IRR assumed):
    IRR = [(Invoice Price + C/2 - Purchase Price) / (Purchase Price × n - C/2 × n2)] × 360
    where n = total days, n2 = days from coupon to delivery

    WORKED EXAMPLE (7-1/4% of 8/22, April 5 2001, Jun delivery):
    ─────────────────────────────────────────────────────────────
    Cash price: 119-28/32 = $119.875; AI: $1.0014; Full price: $120.8764
    Factor: 1.1481; Futures: 103-30/32 = $103.9375
    Invoice = 103.9375 × 1.1481 + 2.6837 = $122.0143
    IRR = (122.0143/120.8764 - 1) × (360/84) = 4.03%
    Term RP = 4.54%; Spread = 4.03 - 4.54 = -0.51% (delivery option cost)

    Equivalence: IRR > Term RP ⟺ BNOC < Theoretical DOV ⟺ Basis cheap ⟺ Futures rich


    OPTION-ADJUSTED BASIS (OAB):
    ────────────────────────────
    OAB = BNOC - Theoretical Delivery Option Value

    OAB > 0 → Basis rich, futures cheap → sell basis
    OAB < 0 → Basis cheap, futures rich → buy basis
    OAB = 0 → Fair value

    Market Futures - Fair Futures = -OAB / Factor

**Key relationships:**
- Basis ≡ Carry + BNOC (identity, always true)
- IRR = Term RP ⟺ BNOC = Theoretical DOV (fair value condition)
- Basis → 0 as time → delivery (carry decays, BNOC decays)
- BNOC ≥ 0 under normal conditions (options have non-negative value)
- BNOC < 0 signals supply squeeze (delivery failure pricing)

**Connects to:** M2 (BNOC depends on CTD stability), M4 (switch option is largest component of BNOC), M5 (end-of-month option prevents BNOC from hitting zero at expiry)

---

### M2: CTD Selection Engine

**In one sentence:** The cheapest-to-deliver bond is determined by the joint interaction of yield level (duration rule) and yield spread (yield rule), creating a map with discrete switching boundaries.

**Diagram:**

    CTD DETERMINATION (two orthogonal forces):
    ────────────────────────────────────────────

    YIELD LEVEL AXIS (Duration Rule):
    ──────────────────────────────────

                    Crossover Yield (~6%)
                          │
          ◄───────────────┼───────────────►
          Yields < 6%     │     Yields > 6%
                          │
          LOW duration     │     HIGH duration
          is CTD           │     is CTD
          (high coupon,    │     (low coupon,
           short maturity) │      long maturity)


    YIELD SPREAD AXIS (Yield Rule):
    ────────────────────────────────

    Given bonds of equal duration:
    HIGHEST yield bond = CTD (always)

    Given bonds at equal yield:
    Duration rule applies (above)


    COMBINED CTD MAP:
    ─────────────────

    Yield Level ──→ selects duration bucket
                         │
                         ▼
    Yield Spreads ──→ selects within bucket
                         │
                         ▼
                    [CTD Bond]


    THREE METHODS TO IDENTIFY CTD (ranked):
    ────────────────────────────────────────

    1. (IRR - own RP rate)  ← best: accounts for repo specials
           │
    2. max(IRR)             ← good: assumes uniform RP rates
           │
    3. min(BNOC)            ← weakest: ignores price-level effects

    WHY BNOC CAN MISLEAD (CTD ranking failure):
    ─────────────────────────────────────────────

    April 2001 example:
    7-5/8% of 11/22: IRR=4.06%, IRR-TermRP=-0.48%, BNOC=4.53  ← CTD by all 3
    8% of 11/21:     IRR=3.99%, IRR-TermRP=-0.55%, BNOC=5.30
    7-1/8% of 2/23:  IRR=3.99%, IRR-TermRP=-0.55%, BNOC=4.92

    IRR and IRR-TermRP rank 8% and 7-1/8% identically (tied 3rd/4th)
    But BNOC ranks them differently: 7-1/8% appears cheaper (4.92 < 5.30)
    Because: 8% has a HIGHER price → lower IRR for same BNOC → actually cheaper
    BNOC ignores price levels; IRR does not.

**Key relationships:**
- At exactly 6% yield: all conversion factors neutral → all bonds equally cheap → short is indifferent
- ↑Yields ⇒ CTD shifts toward higher duration (lower coupon, longer maturity)
- ↓Yields ⇒ CTD shifts toward lower duration (higher coupon, shorter maturity)
- ↑Yield of bond i (relative to others) ⇒ bond i more likely CTD
- Crossover yield = specific yield level at which CTD switches from bond A to bond B
- Two bonds with same BNOC but different prices: higher-priced bond is cheaper to deliver (IRR resolves this)

**Connects to:** M4 (what causes CTD switches), M6 (yield spreads modify crossover yields), M3 (distance from crossover determines option character)

---

### M3: Basis as Synthetic Option

**In one sentence:** Each bond's basis exhibits option-like behavior determined by its position in the deliverable set -- high-duration bonds are calls, low-duration bonds are puts, middle bonds are straddles.

**Diagram:**

    FUTURES PRICE GEOMETRY:
    ───────────────────────

    At expiry, futures = min(Converted Prices across all deliverable bonds)

    Before expiry, futures traces a smooth curve BELOW the min:

    Price/Factor
        │
        │    Bond A               Bond C
        │    (low dur)     Bond B     (high dur)
        │      \          (mid dur)     /
        │       \           │          /
        │        \          │         /
        │         ╲─────────┼────────╱  ← min of converted prices
        │          ╲        │       ╱
        │           ╲───────┼──────╱   ← futures (smooth, below min)
        │            ╲      │     ╱
        │gap = Basis/Factor │
        │                   │
        └───────────────────┼───────────────── Yield
                        Crossover


    OPTION CHARACTER BY POSITION:
    ─────────────────────────────

    ┌──────────────┬──────────┬───────────────────┬──────────────────┐
    │ Bond Type     │ Duration │ Basis Analog       │ Profits When     │
    ├──────────────┼──────────┼───────────────────┼──────────────────┤
    │ High-duration │ High     │ CALL on bonds      │ Yields fall      │
    │ Low-duration  │ Low      │ PUT on bonds       │ Yields rise      │
    │ Mid-duration  │ Middle   │ STRADDLE/STRANGLE  │ Yields move big  │
    │ CTD (any)     │ Varies   │ AT-THE-MONEY       │ Any large move   │
    │ Non-CTD       │ Varies   │ IN-THE-MONEY       │ Already has      │
    │               │          │                    │ intrinsic value  │
    └──────────────┴──────────┴───────────────────┴──────────────────┘


    WORKED CROSSOVER MAP (April 5 2001, Exhibit 2.6):
    ─────────────────────────────────────────────────

    Three competing bonds, yield of 7-5/8% as reference:

    8-7/8% of 8/17 (low dur) ──┤ 4.98% yield ├── 7-5/8% of 11/22 (mid)
                                                         │
    7-5/8% of 11/22 (mid)  ──┤ 6.13% yield ├── 5-1/2% of 8/28 (high dur)

    Current yield: 5.64% → firmly in 7-5/8% zone
    Distance to lower crossover: 66bp (5.64 - 4.98)
    Distance to upper crossover: 49bp (6.13 - 5.64)
    → Slightly closer to high-duration switch (upside for high-dur basis)

    At crossover yields, futures prices would be:
      At 4.98%: ~111-26/32
      At 5.64%: 103-30/32 (current)
      At 6.13%: ~97-20/32


    CONSEQUENCE FOR FUTURES CONVEXITY:
    ──────────────────────────────────

    {IF near crossover yield}:
        Futures exhibit NEGATIVE convexity
        (CTD switching causes futures to track whichever bond falls fastest)

    {IF far from crossover yield}:
        Futures exhibit POSITIVE convexity
        (tracks single CTD, inherits its natural convexity)

    CONSTRAINT:
    ───────────
    [Distance from crossover] ──┤ [Option time value] ──╳ [Gamma collapses when deeply ITM/OTM]

    BREAKS WHEN:
    ────────────
    [Yields move to crossover] → [CTD uncertainty spikes] → [BNOC jumps, negative convexity regime]

**Key relationships:**
- Basis ∝ distance from CTD status (monotonically)
- Long basis = long volatility (theta decay in quiet markets, gamma profit in moves)
- Short basis = short volatility (collects premium, bleeds on big moves)
- Futures negative convexity ∝ proximity to crossover yield

**Connects to:** M1 (BNOC = this option value), M4 (what triggers moves through crossover), M11 (vol arb exploits mispricing of these synthetics vs exchange options)

---

### M4: Switch Option Dynamics

**In one sentence:** The switch (quality) option -- the most valuable delivery option -- is driven by three forces: parallel yield shifts, systematic yield spread changes, and nonsystematic spread noise, with the first two partially canceling.

**Diagram:**

    THREE DRIVERS OF CTD SWITCHES:
    ──────────────────────────────

    1. PARALLEL YIELD SHIFT (dominant):
    ───────────────────────────────────

        ΔYield ──→ Duration effect ──→ CTD switch at crossover yield
                         │
                    ↑Yield ⇒ ↑Duration CTD
                    ↓Yield ⇒ ↓Duration CTD


    2. SYSTEMATIC SPREAD CHANGE (dampener):
    ────────────────────────────────────────

    ┌────────────────────────────────────────────────────────────┐
    │        ⟲ B1: Spread Dampener                              │
    │                                                            │
    │   ↑Yields                                                  │
    │       │                                                    │
    │       ▼                                                    │
    │   Curve flattens (~2-3bp per 10bp yield rise)              │
    │       │                                                    │
    │       ▼                                                    │
    │   Crossover yield rises (moves AWAY from current yield)    │
    │       │                                                    │
    │       ▼                                                    │
    │   CTD switch HARDER to trigger ──┤ Switch option value     │
    │                                                            │
    │   (Symmetric: ↓Yields → curve steepens → crossover falls  │
    │    → switch again harder to trigger)                       │
    └────────────────────────────────────────────────────────────┘

    Net effect: Actual crossover yield is FURTHER from current yield
    than a parallel-shift model predicts → switch option value LOWER


    3. NONSYSTEMATIC SPREAD CHANGE (amplifier):
    ─────────────────────────────────────────────

        Random spread shocks (buybacks, auctions, squeezes)
            │
            ▼
        Unexpected CTD switches
            │
            ▼
        ↑ Realized delivery option value (beyond model)


    INTERACTION:
    ────────────
    Parallel shift + systematic spread = partially cancel → net switch option
    Nonsystematic spread = additive → increases option value beyond net

    CONSTRAINT:
    ───────────
    [Yield spread regime stability] ──┤ [Switch option value] ──╳ [Death of gamma when spreads become fully directional]

    BREAKS WHEN:
    ────────────
    [Spread-yield correlation → ±1] → [Crossover yield moves to infinity] → [CTD permanently entrenched, gamma = 0]

**Key relationships:**
- Switch option value ∝ yield volatility × number of close CTD contenders
- Switch option value ∝⁻¹ |systematic spread correlation with yield|
- Switch option value ∝ nonsystematic spread volatility
- Crossover yield (actual) = Crossover yield (parallel) + f(systematic spread slope)

**Connects to:** M2 (what is CTD), M6 (the dampener in detail), M3 (option character at crossover)

---

### M5: End-of-Month Option

**In one sentence:** After futures trading expires but before last delivery, the invoice price is locked while cash prices keep moving, creating a strangle-like payoff driven by BPV differences (not duration) among deliverable bonds.

**Diagram:**

    TIMELINE:
    ─────────
    ··· Last Trading Day ···|··· 7 business days ···|··· Last Delivery Day
           Futures fixed    |   Cash prices move    |
           at settlement    |   Invoice price LOCKED |
                            |                       |
                            └── END-OF-MONTH WINDOW ─┘


    THE BPV vs DURATION PARADOX:
    ────────────────────────────

    BEFORE expiry:  CTD determined by DURATION (conversion-factor-weighted)
    AFTER expiry:   CTD determined by BPV (absolute $ sensitivity)

    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │   High-coupon bonds: HIGH BPV but LOW duration          │
    │   Low-coupon bonds:  LOW BPV but HIGH duration          │
    │                                                         │
    │   → A bond that is CTD BEFORE expiry (via duration)     │
    │     may NOT be CTD AFTER expiry (via BPV)               │
    │                                                         │
    └─────────────────────────────────────────────────────────┘


    PAYOFF STRUCTURE:
    ─────────────────

    Net delivery cost = Cash Price - (Factor × Final Futures) - Carry

    The short picks whichever bond minimizes this cost.

    Crossover yield change: Δy = BNOC_gap / BPV_gap

    P/L
     │
     │         ╱                    ╲
     │        ╱                      ╲
     │       ╱     (zero zone)        ╲
     ├──────╱────────────────────────╲──────
     │     ╱                          ╲
     │    ╱                            ╲
     └────────────────────────────────────── Δy
         -Δy*                      +Δy*
         (yields fall              (yields rise
          enough)                   enough)

    ← STRANGLE PAYOFF: zero in the middle, positive on tails →


    CONSTRAINT:
    ───────────
    [BNOC gap between bonds] ──┤ [Crossover Δy threshold] ──╳ [Option becomes deep OTM if gap too wide]

    BREAKS WHEN:
    ────────────
    [Only one bond close to CTD] → [BPV gap huge] → [Crossover Δy unreachable] → [Option worthless]

    WORKED EXAMPLE (Exhibit 3.9):
    ─────────────────────────────

    At last trading day, three bonds competing:
    ┌──────────────┬────────┬──────────┬──────────┬────────────────────────┐
    │ Bond          │ Yield  │ BNOC     │ BPV      │ Δy to become CTD       │
    │               │        │ (32nds)  │ (32nds)  │ (bp)                   │
    ├──────────────┼────────┼──────────┼──────────┼────────────────────────┤
    │ 6-1/4% 8/23   │ 5.649  │ 1.0      │ 4.25     │ -4.0 = 1.0/(4.50-4.25) │
    │ 7-1/4% 8/22   │ 5.639  │ 0.0 CTD  │ 4.50     │ 0 (IS the CTD)         │
    │ 8-3/4% 8/20   │ 5.602  │ 1.5      │ 4.70     │ +7.5 = 1.5/(4.70-4.50) │
    └──────────────┴────────┴──────────┴──────────┴────────────────────────┘

    If yields rise 10bp:
      7-1/4% falls 45/32 (10 × 4.50)
      8-3/4% falls 47/32 (10 × 4.70)
      Net: 8-3/4% is now 0.5/32 CHEAPER to deliver → swap, profit 0.5/32

    If yields fall 10bp:
      7-1/4% rises 45/32
      6-1/4% rises 42.5/32
      Net: 6-1/4% is now 1.5/32 CHEAPER → swap, profit 1.5/32

    Note asymmetry: downside crossover (-4bp) is closer than upside (+7.5bp)
    → strangle is skewed

**Key relationships:**
- End-of-month option value ∝ yield volatility × 1/(BNOC gap / BPV gap)
- Hedge ratio post-expiry jumps to 1:1 (from conversion-factor-weighted ratio)
- End-of-month option prevents CTD BNOC from reaching zero at expiration
- Option is exercisable repeatedly (multiple switching opportunities in 7 days)
- Last switch must occur by 2nd-to-last business day (delivery logistics)
- Cost of the option = CTD BNOC at last trading day close (can be zero)
- BPV difference of 0.20/32nds per bp between competing bonds is typical

**Connects to:** M1 (BNOC at expiry = end-of-month option value), M4 (switch option hands off to end-of-month at expiry)

---

### M6: Yield Spread Dampener

**In one sentence:** The systematic tendency for the deliverable curve to flatten as yields rise and steepen as yields fall acts as a moving strike on the switch option, reducing its value relative to a parallel-shift model.

**Diagram:**

    MECHANISM:
    ──────────

    ┌────────────────────────────────────────────────────────────────┐
    │        ⟲ B1: Spread Dampener Loop                             │
    │                                                                │
    │   ↑Yields (10bp)                                               │
    │       │                                                        │
    │       ▼                                                        │
    │   Curve flattens (~2-3bp)                                      │
    │       │                                                        │
    │       ▼                                                        │
    │   High-duration bonds cheapen LESS than parallel model says    │
    │       │                                                        │
    │       ▼                                                        │
    │   Crossover yield RISES (moves further away)                   │
    │       │                                                        │
    │       ▼                                                        │
    │   CTD switch DOES NOT OCCUR ──┤ Switch option value            │
    │                                                                │
    │   SYMMETRIC REVERSE:                                           │
    │   ↓Yields → curve steepens → low-dur bonds cheapen LESS       │
    │   → crossover yield FALLS → switch again harder → ──┤ value   │
    └────────────────────────────────────────────────────────────────┘

    EXTREME CASE: "DEATH OF GAMMA" (Era 6, 1991-1993)
    ──────────────────────────────────────────────────

    Spread-yield correlation approached -1.0:
      Every 10bp yield decline → 3bp steepening
      Crossover yield pushed lower and lower
      CTD (7-1/2% of '16) NEVER switched despite 100bp rally
      Average BNOC collapsed: 11 ticks → 2 ticks

    Specific numbers (Exhibit 8.7):
      Yield spread (7-1/2% of 11/16 vs on-the-run long bond):
        Normal (pre-1991): ~+15bp
        At trough (mid-1992): ~-20bp
        Swing: 35bp, fully correlated with yield decline
      Delivery history (Jun 91 - Jun 93): 7-1/2% of 11/16 delivered
        in EVERY SINGLE contract (Exhibit 8.8)
      Option premium (Exhibit 8.10): Mar 91 ~11 ticks → Dec 92 ~2 ticks

    Aftermath (Era 7, Jul 93 - 1994):
      Yield curve REVERSED: flattened during a rally
      Callable bonds became CTD for the last time
      12-1/2% (callable) BNOC fell 35/32nds below 11-1/4% in 6 weeks
      Proved that spread regime changes are abrupt, not gradual

    This is the "100-year flood" of spread regimes:
    Spread behavior moved from dampener to ELIMINATOR of gamma

    VISUAL:
    ───────

    Normal:     Crossover yield         Actual crossover
                    (parallel)              (with spreads)
                        │                       │
        ◄───────────────┼───────────────────────┼──► yield
                   close to                further away
                   current yield          from current yield

    Death of gamma:
                    Crossover              "Crossover"
                    (parallel)             (with spreads)
                        │                                       │
        ◄───────────────┼───────────────────────────────────────┼──► yield
                                   unreachable

**Key relationships:**
- Spread dampener magnitude ≈ 2-3bp curve change per 10bp yield change (empirical)
- ΔCrossover = f(yield beta spread, yield change)
- When spread-yield correlation → ±1: switch option → 0 ("death of gamma")
- When spread-yield correlation → 0: parallel-shift model is adequate
- Nonsystematic spread shocks partially offset the dampener

**Connects to:** M4 (this IS the systematic component of switch dynamics), M9 (dampener controls convexity regime)

---

### M7: Repo Specialness Spiral

**In one sentence:** When a bond is heavily shorted or in demand for delivery, its reverse repo rate collapses below general collateral, inflating its basis, attracting more shorts (who see it as "rich"), and potentially triggering a squeeze.

**Diagram:**

    ┌────────────────────────────────────────────────────────────┐
    │        ⟳ R2: Specialness Spiral                           │
    │                                                            │
    │   Bond becomes CTD or on-the-run                           │
    │       │                                                    │
    │       ▼                                                    │
    │   Hedging/delivery demand ↑                                │
    │       │                                                    │
    │       ▼                                                    │
    │   Short sellers must borrow bond in reverse repo           │
    │       │                                                    │
    │       ▼                                                    │
    │   Reverse RP rate collapses (below GC, toward 0%)          │
    │       │                                                    │
    │       ▼                                                    │
    │   Basis inflated (lower financing cost = higher carry)     │
    │       │                                                    │
    │       ▼                                                    │
    │   Bond APPEARS rich (high basis) ←─────── attracts more    │
    │       │                                    short sellers   │
    │       ▼                                        │           │
    │   More borrowing demand ───────────────────────┘           │
    │       │                                                    │
    │       ▼  (loop reinforces)                                 │
    │   RP rate → 0% → NEGATIVE → fail-to-deliver regime        │
    └────────────────────────────────────────────────────────────┘

    ON-THE-RUN CYCLE:
    ─────────────────

    Post-auction ──→ OTR richens ──→ short hedges accumulate
                                          │
                                          ▼
                                     Goes special in repo
                                          │
                                          ▼
                                     Basis widens further
                                          │
    Pre-next-auction ──→ OTR cheapens ──→ Shorts cover ──→ RP normalizes

    RP RATE HIERARCHY:
    ──────────────────
    Fed Funds ≥ GC Repo > Special Repo > 0% > Negative RP > Fail

    CONSTRAINT:
    ───────────
    [Available float of bond] ──┤ [RP rate] ──╳ [At zero/negative: fail-to-deliver regime]

    BREAKS WHEN:
    ────────────
    [Short interest > available float] → [RP rate → negative] → [Fails cascade] → M8 activates

**Key relationships:**
- Specialness ∝ short interest / available float
- Basis of special bond = Basis(GC) + Specialness premium
- True CTD = max(IRR - own RP rate), not max(IRR)
- RP-GC spread is a leading indicator of squeeze risk
- OTR cycle: ~3 month period, richening early, cheapening late

**Connects to:** M8 (specialness spiral feeds into supply squeeze), M1 (repo rate directly enters carry calculation)

---

### M8: Supply-Squeeze Cascade

**In one sentence:** When futures open interest exceeds the deliverable supply of the CTD, the arbitrage relationship breaks, BNOC goes negative, and the market transitions from option pricing to delivery-failure-probability pricing.

**Diagram:**

    PRECONDITIONS:
    ──────────────
    1. Open interest >> CTD float
    2. CTD firmly entrenched (large gap to 2nd CTD)
    3. Bull flattening or similar regime concentrating deliverables

    CASCADE:
    ────────

    ┌────────────────────────────────────────────────────────────────┐
    │        ⟳ R3: Squeeze Cascade                                  │
    │                                                                │
    │   ↑Open interest / ↓Deliverable supply                        │
    │       │                                                        │
    │       ▼                                                        │
    │   P(delivery failure) > 0                                      │
    │       │                                                        │
    │       ▼                                                        │
    │   Fair CTD BNOC = P(fail) × (CTD_BNOC - 2nd_CTD_BNOC)         │
    │       │                                                        │
    │       ▼                                                        │
    │   CTD BNOC goes NEGATIVE                                       │
    │       │                                                        │
    │       ▼                                                        │
    │   Shorts unable to deliver → forced to ROLL                    │
    │       │                                                        │
    │       ▼                                                        │
    │   Buy front / sell back → calendar spread WIDENS               │
    │       │                                                        │
    │       ▼                                                        │
    │   Front futures RISE relative to back → CTD richens further    │
    │       │                                                        │
    │       ▼                                                        │
    │   Non-CTD bases compressed (pulled toward CTD)                 │
    │       │                                                        │
    │       ▼                                                        │
    │   Effective deliverable supply SHRINKS further                  │
    │       (non-CTD too expensive to deliver)                       │
    │                                                                │
    │   LOOP CONTINUES until:                                        │
    │   • Exchange intervenes                                        │
    │   • Yield regime shifts (new CTD emerges)                      │
    │   • Enough shorts capitulate/roll                              │
    └────────────────────────────────────────────────────────────────┘

    FORMULAS:
    ─────────
    Fair CTD BNOC = P(fail) × (CTD_BNOC - 2nd_CTD_BNOC)
    Implied P(fail) = CTD_BNOC / (CTD_BNOC - 2nd_CTD_BNOC)

    CONSTRAINT:
    ───────────
    [CTD float] ──┤ [Deliverability] ──╳ [Negative BNOC regime when float < OI]

    BREAKS WHEN:
    ────────────
    [OI / CTD float > 1] → [Delivery failure probable] → [BNOC < 0] → [Calendar spread dislocation]

    HISTORICAL CASES:
    ─────────────────

    2005 10-YEAR CTD SQUEEZE:
    ├── OI reached 2.1mm contracts (50% YoY growth)
    ├── Bull flattening (Fed hiking + declining intermediate yields)
    ├── Shortest maturity firmly entrenched as CTD
    ├── Gap to 2nd CTD: ~1 point (32/32nds)
    ├── CTD RP rate: fell to NEGATIVE 15% overnight (4-7/8% of 2/12, May 2005)
    ├── CTD BNOC: went negative → implied ~10% failure probability
    └── Strategies: sell non-CTD basis, buy calendar spread, asset-swap CTD

    1986 9-1/4% OF 2/16 SQUEEZE (worst in US basis trading history):
    ├── Setup: appeared "obvious" to short old CTD vs when-issued new bond
    ├── Massive short position built by spreaders expecting normal pattern
    ├── Japanese institutions owned most of the 9-1/4% but REFUSED to lend
    │   (unfamiliar with RP transactions; would not set precedent)
    ├── RP rate → 0% → rumors of NEGATIVE reverse RP
    ├── Funds selling old cheap-to-deliver issues compounded the problem
    ├── Yield spread: widened from 25-40bp to >100bp
    ├── Basis: widened ~6 full points ($60,000 per $1mm face)
    └── Lesson: NO THEORETICAL LIMIT to loss on a short squeeze

    SQUEEZE WARNING SIGNALS:
    ────────────────────────
    1. Declining RP special rate (approaching GC, then 0%)
    2. Large short interest relative to tradable float
    3. Yield spread changes between CTD and similar issues
    4. Calendar spread widening beyond fair value

**Key relationships:**
- Negative BNOC ∝ P(delivery failure) × BNOC gap to 2nd CTD
- Calendar spread ∝ squeeze intensity (widens as shorts forced to roll)
- Non-CTD bases ∝⁻¹ squeeze intensity (compressed as CTD richens)
- No theoretical limit to squeeze magnitude (1986: basis widened ~6 points = $60k/$1mm)
- As non-CTD bases narrow toward zero, effective deliverable supply increases (2nd CTD becomes viable)
- Exchange rules explicitly prohibit manipulation intended to create squeezes

**Connects to:** M7 (specialness spiral feeds this), M1 (BNOC < 0 violates normal option pricing), M4 (regime shift needed to break squeeze)

---

### M9: Negative Convexity Transmission

**In one sentence:** The CTD-switching mechanism causes futures to track whichever bond is falling fastest, transmitting negative convexity to the futures contract in the neighborhood of crossover yields and positive convexity far from them.

**Diagram:**

    CONVEXITY PROFILE OF FUTURES:
    ─────────────────────────────

    Convexity
        │
        │   +++                                    +++
        │  ++                                        ++
        │ +     (positive: single CTD)        (positive)+
        ├─────────────────────────────────────────────────
        │              ---  ---
        │             -        -
        │            -          -
        │           - (negative: -
        │          -   crossover  -
        │         -    zone)       -
        │
        └──────────────────────────────────────────────── Yield
                         Crossover


    MECHANISM:
    ──────────

    Far from crossover:
        Futures tracks single CTD → inherits its positive convexity
        DV01 is stable and predictable

    Near crossover:
        Futures tracks min(converted prices) → as yields change,
        CTD switches → futures follows whichever bond lost more value
        → DV01 INCREASES as yields rise (negative convexity)

    For hedge ratios:
    ─────────────────

    Rule-of-thumb DV01:       Jumps discretely at crossover
    Option-adjusted DV01:     Transitions smoothly through crossover

    Below crossover: Rule-of-thumb UNDERSTATES futures DV01 → hedge ratio too high
    Above crossover: Rule-of-thumb OVERSTATES futures DV01 → hedge ratio too low
    At crossover:    Rule-of-thumb DISCONTINUOUS → hedge ratio meaningless

    COMPUTING OA-DV01 (Exhibit 5.8):
    ─────────────────────────────────

    1. Build theoretical futures price schedule: F(y) for y from y-200bp to y+200bp
    2. At each yield level, F(y) reflects the CTD at that yield + its DOV
    3. Numerical derivative: OA-DV01(y) = [F(y-Δy) - F(y+Δy)] / (2 × Δy)

    The result is a SMOOTH curve through crossover, not a discrete jump.

    Rule-of-thumb at crossover: jumps from DV01_lowdur/CF_low to DV01_highdur/CF_high
    OA-DV01 at crossover: weighted average, transitioning gradually

    PRACTICAL IMPACT ON HEDGE RATIOS:
    ──────────────────────────────────
    Below crossover: Rule-of-thumb HR = DV01_bond / (DV01_lowdur/CF_low) → TOO HIGH
    At crossover:    Rule-of-thumb HR is UNDEFINED (discontinuous)
    Above crossover: Rule-of-thumb HR = DV01_bond / (DV01_highdur/CF_high) → TOO LOW

    The error can be 5-15% of the hedge ratio near crossover yields.

    A futures HEDGE is like a long straddle (Exhibit 5.11):
    → If yields move significantly in either direction, the hedge
       outperforms because OA-DV01 captures the CTD switch benefit
       that rule-of-thumb misses.

**Key relationships:**
- Futures convexity = f(distance from crossover, number of close CTD contenders)
- Near crossover: ΔDV01/Δy > 0 (negative convexity)
- Far from crossover: ΔDV01/Δy < 0 (positive convexity, from underlying bond)
- Option-adjusted DV01 = numerical derivative of theoretical futures price schedule
- Hedge error from rule-of-thumb: 5-15% near crossover, negligible far from crossover
- A correctly hedged position (using OA-DV01) has residual long-vol exposure

**Connects to:** M4 (crossover location determines convexity regime), M6 (dampener shifts crossover, affecting convexity zone), M3 (this IS the geometric mechanism behind the option analogy)

---

### M10: Carry-Option Delivery Tension

**In one sentence:** The short faces a tension between delivering early (to stop negative carry bleeding) and waiting (to preserve option value), with the equilibrium depending on carry magnitude vs remaining option value.

**Diagram:**

    DELIVERY DECISION TREE:
    ───────────────────────

    {IF carry > 0}:
        Deliver LAST day (earn carry, preserve all options)
        Implied repo < Term repo by option value amount

    {IF carry < 0}:

        ┌─────────────────────────────────┐
        │  TENSION:                       │
        │                                 │
        │  |Negative carry| vs Remaining  │
        │  per day             DOV        │
        │                                 │
        │  {IF |neg carry| > DOV}:        │
        │      Deliver EARLY              │
        │      Futures = CTD Price/Factor │
        │                                 │
        │  {IF |neg carry| < DOV}:        │
        │      WAIT despite bleeding      │
        │      Preserve switch + EOM opt  │
        └─────────────────────────────────┘


    WILD CARD OPTION (minor):
    ─────────────────────────

    After 2pm futures close, cash continues trading.
    Short can "cover the tail" if prices move enough.

    Break-even: Price must move by Basis / (Factor - 1)

    {IF Factor > 1}: profitable on price DROP (high-coupon era)
    {IF Factor < 1}: profitable on price RISE (low-coupon era)

    Requires: (a) Factor significantly ≠ 1, (b) high intraday vol


    TIMING OPTION VALUE HIERARCHY:
    ──────────────────────────────

    Switch option >> End-of-month option >> Wild card > Carry option > Limit move option

**Key relationships:**
- Early delivery destroys remaining option value (irreversible)
- Negative carry must exceed ALL remaining options to justify early delivery
- Wild card value ∝ |Factor - 1| × intraday volatility
- Era 2 (1979-81): wild card dominated (high factors, extreme vol)
- Paradox: in Era 2, delivery shifted LATER despite MORE negative carry (wild card value > carry cost)

**Connects to:** M1 (carry component of the decomposition), M4 (switch option is what you sacrifice), M5 (EOM option is what you sacrifice)

---

### M11: Volatility Arbitrage Equilibrium

**In one sentence:** The basis market and the exchange options market independently price bond yield volatility, and when they disagree, cross-market arbitrage (buying cheap vol in one, selling rich vol in the other) pulls them toward equilibrium.

**Diagram:**

    TWO MARKETS PRICING THE SAME VOLATILITY:
    ──────────────────────────────────────────

    ┌──────────────────────┐     ┌──────────────────────┐
    │  BASIS MARKET         │     │  OPTIONS MARKET       │
    │  (synthetic options)  │     │  (exchange-listed)    │
    │                       │     │                       │
    │  BNOC = implied       │     │  Premium = implied    │
    │  delivery option      │     │  exchange option      │
    │  value (via OAB)      │     │  value                │
    │                       │     │                       │
    │  Vol_basis             │     │  Vol_options           │
    └───────────┬───────────┘     └───────────┬───────────┘
                │                              │
                └──────────┬───────────────────┘
                           │
                    {IF Vol_basis < Vol_options}:
                        Buy basis (long cheap synthetic vol)
                        Sell exchange options (short rich vol)

                    {IF Vol_basis > Vol_options}:
                        Sell basis (short rich synthetic vol)
                        Buy exchange options (long cheap vol)


    ┌───────────────────────────────────────────────────────────┐
    │        ⟲ B2: Vol Arbitrage Equilibrium                    │
    │                                                           │
    │   Basis cheap (OAB < 0)                                   │
    │       │                                                   │
    │       ▼                                                   │
    │   Arbs buy basis / sell options                            │
    │       │                                                   │
    │       ▼                                                   │
    │   Basis richens / options cheapen                          │
    │       │                                                   │
    │       ▼                                                   │
    │   OAB → 0 (equilibrium)                                   │
    │                                                           │
    │   (Reverse for OAB > 0)                                   │
    └───────────────────────────────────────────────────────────┘

    RESIDUAL RISKS (imperfect arb):
    ────────────────────────────────
    1. Yield spread changes (not captured by options)
    2. Imperfect P/L profile matching
    3. Horizon mismatch: bond options expire ~1 month before futures last trading
       → basis has higher vega than the options hedge

    OAB CALCULATION CHAIN (Exhibit 4.6, April 2001 bond futures):
    ─────────────────────────────────────────────────────────────

    CTD: 7-5/8% of 11/22
    ├── Actual BNOC: 4.53/32nds (= Basis 18.1 - Carry 13.6)
    ├── Theoretical DOV: 8.2/32nds (switch + EOM, from model)
    ├── Theoretical Basis: 13.6 + 8.2 = 21.8/32nds
    ├── OAB = 4.53 - 8.2 = -3.7/32nds → BASIS CHEAP, FUTURES RICH
    └── Futures mispricing = -(-3.7)/1.1936 = 3.1/32nds rich

    Non-CTD check (5-3/8% of 2/31):
    ├── BNOC: 97.02/32nds (huge: very expensive to deliver)
    ├── Of which ~8/32nds is DOV, ~89/32nds is expensiveness premium
    └── Consistent: all bonds yield same OAB up to model noise


    VALUATION GRID METHODOLOGY (Exhibit 4.3):
    ──────────────────────────────────────────

    Expected BNOC = Σ_i Σ_j p(yield_i) × p(spread_j) × BNOC(i,j)

    Example (3×3 grid, probabilities: 0.16/0.68/0.16 for tails/center):
    ├── Yield: -100bp / 0 / +100bp
    ├── Spread: steeper / beta / flatter (each relative to yield scenario)
    ├── BNOC matrix: 9 cells, each from CTD identification + EOM option
    └── E[BNOC] = 0.16×7.76 + 0.68×7.08 + 0.16×8.44 = 7.41/32nds

    σ_y starts from implied vol of futures options:
    σ_yield = (Yield × Modified Duration) × σ_price


    BACKTEST (297 trades, May 1989 - Aug 1990):
    ────────────────────────────────────────────

    ┌─────────────┬────────┬───────┬───────┬─────────┬──────────┐
    │ Contract     │ Trades │ Worst │ Best  │ Average │ Std Dev  │
    ├─────────────┼────────┼───────┼───────┼─────────┼──────────┤
    │ All          │ 297    │ -16.7 │ +29.2 │ +4.9    │ 8.6      │
    │ Sep-89       │ 20     │ -10.0 │ +18.4 │ +1.3    │ 6.9      │
    │ Dec-89       │ 77     │ -1.9  │ +16.8 │ +6.8    │ 4.7      │
    │ Mar-90       │ 78     │ -13.4 │ +18.7 │ -2.1    │ 5.9      │
    │ Jun-90       │ 65     │ -16.7 │ +23.5 │ +5.3    │ 9.2      │
    │ Sep-90       │ 57     │ -9.5  │ +29.2 │ +12.5   │ 8.2      │
    ├─────────────┼────────┼───────┼───────┼─────────┼──────────┤
    │ Unhedged     │ 297    │ -12.4 │ +53.8 │ +6.8    │ 13.4     │
    │ basis only   │        │       │       │         │          │
    └─────────────┴────────┴───────┴───────┴─────────┴──────────┘

    Key insight: unhedged basis trades had HIGHER avg return (6.8 vs 4.9)
    but MUCH higher std dev (13.4 vs 8.6). The options hedge
    sacrifices ~2 ticks of expected return to cut risk by 36%.

    At 20:1 leverage: avg return 22.1%, worst -1.9%, best 46.2%
    Max practical leverage: ~25:1 (exchange margin + RP constraints)

**Key relationships:**
- OAB = BNOC - Theoretical DOV (fair value gap)
- Vol arb profitable when |OAB| > ~3-5 ticks (threshold from backtest)
- OAB typically trades within ±5 ticks of zero; episodes beyond ±10 ticks are rare
- Options market is a better vol forecaster than basis market (empirical)
- Hedged arb: avg +4.9 ticks, std dev 8.6; unhedged: avg +6.8, std dev 13.4
- 20:1 leverage → ~22% avg return on capital
- Vol arb is a BALANCING loop that tends to keep OAB near zero over time

**Connects to:** M1 (OAB is the arb signal), M3 (bases ARE the synthetic options being traded), M4 (delivery options are what's being priced)

---

### M12: Synthetic Asset Construction

**In one sentence:** Combining long futures with a short-term cash investment creates a synthetic bond that outperforms the physical bond when futures trade cheap (positive premium), producing systematic yield enhancement.

**Diagram:**

    CONSTRUCTION:
    ─────────────

    [Physical Bond]  ≡  [Long Futures] + [Cash Investment to Delivery Date]
                            │                    │
                            │                    └── Amount = Bond's Full Price
                            │                        Earns: RP rate (or T-bill, ABS float)
                            │
                            └── Hedge ratio = Spot DV01 / Forward DV01
                                (≈ 0.99 contracts per bond, not 1.00)


    YIELD ENHANCEMENT SOURCE:
    ─────────────────────────

    Premium = Forward Price - Market Futures Price
            = BNOC × Factor  (approximately)

    When futures cheap (premium > 0):
        Synthetic bond yield = Physical bond yield + Premium effect

    Empirical (10yr note, Jun 1998 - Jun 2004):
        Synthetic outperformed in 19 of 21 quarters
        Average annualized pickup: ~61bp using GC repo


    FORWARD PRICE FORMULA (with intervening coupon):
    ────────────────────────────────────────────────

    F = (S+AI)[1 + R(d1/360)][1 + R(d2/360)] - (C/2)[1 + R(d2/360) + d2/184]
    where d1 = days to coupon, d2 = days from coupon to delivery


    SPOT AND REPO DV01 DECOMPOSITION:
    ──────────────────────────────────

    WORKED EXAMPLE (7-5/8% of 11/22, delivery Jun 29, 84 days):

    Spot DV01 (sensitivity to 1bp change in bond yield):
      dF/dy = [1 + 0.0454(84/360) + 0.0454²(39/360)(45/360)] × 145.45
            = 1.01062 × 145.45
            = $146.99 per $100k par
      (1.06% amplification of the spot DV01 by repo carry)

    Repo DV01 (sensitivity to 1bp change in term RP rate):
      dF/dR = [127,616 × (84/360 + 0.0454 × 39/360 × 45/360) - 3.8125 × 0.125]
              / 10,000
            = $2.88 per $100k par

    RATIO: Spot DV01 / Repo DV01 = 146.99 / 2.88 ≈ 51:1
    → Spot yield risk DOMINATES; repo risk is small but INDEPENDENT

    INDEPENDENCE (Exhibit 5.6, Jan 1988 - Oct 2003):
      R² of weekly Δ(5yr yield) vs Δ(1mo repo) = 0.0249
      R² of weekly Δ(10yr yield) vs Δ(1mo repo) = 0.0112
      R² of weekly Δ(30yr yield) vs Δ(1mo repo) = 0.0018
      → Essentially ZERO correlation at weekly frequency


    SYNTHETIC BOND CONSTRUCTION:
    ────────────────────────────

    Synthetic = [0.9895 Futures] + [$127,616 in 84-day term cash]
                     │                       │
                     │                       └── ΔValue from RP change
                     │                            OFFSETS ΔForward from RP
                     │
                     └── 0.9895 = SpotDV01 / ForwardDV01 = 145.45 / 146.99
                         (NOT 1.0: because futures P/L is immediate cash,
                          no discounting needed; forward gains/losses are deferred)

    Repo DV01 risk is hedged away by the cash leg → synthetic has purer duration exposure

**Key relationships:**
- Synthetic yield enhancement ∝ futures cheapness (OAB)
- Pickup = premium / factor, annualized
- 10yr note futures chronically cheap (mortgage hedger selling pressure)
- Repo DV01 risk is hedged away by the cash leg → synthetic has purer duration exposure
- Tax treatment differs: futures P/L is 60/40 short-term/long-term

**Connects to:** M1 (premium = BNOC × Factor), M11 (vol arb and synthetic assets both exploit cheapness), M9 (option-adjusted DV01 needed for correct hedge ratio)

---

### M13: Basis Trade P/L Accounting

**In one sentence:** The P/L of any basis trade decomposes exactly into two channels -- change in gross basis and carry -- and for the CTD, selling the basis nets precisely the negative of the change in BNOC.

**Diagram:**

    LONG BASIS P/L (buy bond, sell CF × futures):
    ──────────────────────────────────────────────

    ┌─────────────────────────────────────────────────────────────────┐
    │                                                                 │
    │  Leg 1: Bond P/L                                                │
    │    = (Sell Price - Buy Price) × $10M / $100                     │
    │    Loss/gain in 32nds × $3,125 per 32nd per $1M par            │
    │                                                                 │
    │  Leg 2: Futures P/L                                             │
    │    = (Sell Price - Buy Price) × #contracts × $31.25 per 32nd    │
    │    Sign flipped for short futures position                      │
    │                                                                 │
    │  Leg 3: Coupon income earned                                    │
    │    = Par × (Coupon/2) × (Days/CouponPeriod)                     │
    │                                                                 │
    │  Leg 4: RP interest paid                                        │
    │    = FullPrice × RPrate × (Days/360)                            │
    │    (Calculated on FULL price = clean + accrued)                  │
    │                                                                 │
    │  Total P/L = Leg1 + Leg2 + Leg3 + Leg4                         │
    └─────────────────────────────────────────────────────────────────┘


    ALTERNATIVE DECOMPOSITION (the trader's view):
    ───────────────────────────────────────────────

    Total P/L = ΔBasis_value + Carry_earned

    Where:
      ΔBasis_value = (Basis_close - Basis_open) × $3,125 per 32nd per $1M
      Carry_earned = Coupon income - RP interest

    For LONG basis:  profit when basis WIDENS
    For SHORT basis: profit when basis NARROWS


    THE CTD SELLER'S IDENTITY:
    ──────────────────────────

    Short CTD basis P/L = -Δ(BNOC)

    If BNOC falls from 10.1 to 0: seller nets +10.1/32nds
    If BNOC rises from 10.1 to 17: seller loses -6.9/32nds

    This identity holds because carry is deterministic and nets
    out of the alternative decomposition for the CTD.


    WORKED EXAMPLE: BUYING THE BASIS (Ch1):
    ────────────────────────────────────────

    Open 4/5/01: Buy $10M 7-1/2% of 11/16 at 120-20, sell 115 Jun futures at 103-30
    Close 4/19/01: Sell bonds at 116-21, buy 115 futures at 100-16
    (Basis narrowed: 40.4 → 39.7/32nds; market fell ~4 points)

    Leg 1 (Bonds):  (116-21 - 120-20) = -127/32 × $3,125 = ($396,875)
    Leg 2 (Futures): (103-30 - 100-16) = +110/32 × 115 × $31.25 = $395,313
    Leg 3 (Coupon):  $10M × (7.5%/2) × (14/181) = $29,006
    Leg 4 (RP paid): $12,356,700 × 4.5% × (14/360) = ($21,624)
    ──────────────────────────────────────────────────────────────
    Total: $5,819

    Alternative decomposition:
    ΔBasis = -0.7/32 × $3,125 = ($2,188) → lost on basis narrowing
    Carry  = $29,006 - $21,624 = $7,381 → earned positive carry
    Net    = $5,819 ← carry more than offset basis loss


    WORKED EXAMPLE: SELLING THE BASIS (Ch1):
    ─────────────────────────────────────────

    Open 4/5/01: Sell $10M 7-5/8% of 2/25 at 125-22.5, buy 120 Jun futures at 103-30
    Close 4/19/01: Buy bonds at 121-15, sell 120 futures at 100-16

    Bonds: +135.5/32 × $3,125 = $423,438
    Futures: -110/32 × 120 × $31.25 = ($412,500)
    Coupon PAID: ($29,489) ← short pays coupon
    Reverse RP EARNED: $22,182 ← at 4.50%

    At RRP = 4.50%: net P/L = $3,631
    At RRP = 4.25%: net P/L = $2,399 (lost $1,232 to lower RRP)
    At RRP = 1.00%: net P/L = ($13,622) ← SPECIALNESS KILLS THE TRADE


    ROUNDING FRICTION:
    ──────────────────
    Exact CF ratio: 1.2138 → 121.38 contracts per $10M
    Actual: 121 contracts (whole contracts only)
    Slippage: 0.38 contracts × ΔFutures × $31.25
    This creates small directional tilt in "delta-neutral" basis trades.

    Value of 1/32nd per $1M par: $312.50 (= $1,000,000 / 32 / 100)
    → Carry in 32nds = Carry in $ / $312.50

    CONSTRAINT:
    ───────────
    [Whole contract rounding] ──┤ [Perfect P/L tracking] → slippage ∝ |ΔFutures| × |CF - round(CF)|

**Key relationships:**
- Short basis P/L = -Δ(BNOC) for CTD (exact identity)
- Long basis P/L = +Δ(BNOC) for CTD
- Carry component is deterministic; BNOC component is stochastic
- Whatever position you take in the BOND is the position in the BASIS
- Empirical: CTD BNOC fell in 23/25 quarters (10yr, 1998-2004); avg gain 4.9/32nds from avg starting BNOC of 6.7/32nds

**Connects to:** M1 (the identity being exploited), M3 (BNOC behavior determines P/L profile)

---

### M14: RP / Reverse RP Asymmetry

**In one sentence:** The 10-25bp spread between repo (financing longs) and reverse repo (financing shorts) is a hidden asymmetric friction that systematically favors long basis positions and penalizes short basis positions.

**Diagram:**

    RATE HIERARCHY FOR BASIS TRADES:
    ────────────────────────────────

    RP rate (financing longs)      ≈ GC + 0-5bp
         │
         │   10-25bp spread (normal)
         │
    Reverse RP rate (financing shorts) ≈ GC - 10-25bp
         │
         │   Variable: can collapse to 0% or negative for specials
         │
    Special Reverse RP rate            ≈ 0% to negative


    IMPACT ON P/L:
    ──────────────

    LONG BASIS (buy bond, short futures):
      Finance at RP rate (higher)
      → Higher financing cost
      → Lower carry earned
      → P/L drag: FullPrice × 10-25bp × Days/360

    SHORT BASIS (short bond, long futures):
      Invest proceeds at Reverse RP rate (lower)
      → Lower interest earned
      → Carry worse than it appears
      → P/L drag: FullPrice × 10-25bp × Days/360

    BOTH sides pay the friction, but:
      Short basis has ADDITIONAL risk: reverse RP can collapse
      to special/negative rates if bond becomes scarce


    WORKED EXAMPLE (from source):
    ─────────────────────────────

    $10M of 7-5/8% of 2/25, short basis, 14 days:
      At reverse RP = 4.50%: RP income = $22,182
      At reverse RP = 4.25%: RP income = $20,950 → P/L $1,232 worse
      At reverse RP = 1.00%: RP income = $4,929  → trade LOSES $13,622 vs gain

    The specialness tail risk is UNBOUNDED for the short basis seller.

    CONSTRAINT:
    ───────────
    [Bond scarcity] ──┤ [Reverse RP rate] ──╳ [At 0%/negative: carry destruction overwhelms basis convergence]

**Key relationships:**
- RP-RRP spread ≈ 10-25bp under normal conditions
- Short basis carry drag = FullPrice × (RP - RRP) × Days/360
- Special rate can drive carry negative even when basis looks profitable
- A bond "on special" at 1% reverse RP can convert a profitable short basis into a large loss
- The RP/RRP asymmetry is WHY the CTD identification should use (IRR - own RP rate), not just IRR

**Connects to:** M7 (specialness makes this asymmetry extreme), M13 (carry leg of P/L directly affected), M1 (financing cost is half of carry)

---

### M15: Delivery Month Mechanics

**In one sentence:** The transition from trading to delivery introduces discrete mechanical steps -- covering the tail, refreshing, bonds-in-the-box -- each creating specific risks and frictions that shape basis trade management.

**Diagram:**

    THREE-DAY DELIVERY PROCESS (Chicago time):
    ───────────────────────────────────────────

    TENDER (POSITION) DAY:
    ├── 7:20am  Futures market opens
    ├── 2:00pm  Futures market closes
    └── 5-8pm   Delivery notice deadline (clearing member → exchange)
                 ↑ 3-6 hour gap = WILD CARD WINDOW

    NOTICE (INTENTION) DAY:
    ├── 7:20am  Clearing member advises long
    ├── 1:00pm  Short nominates SPECIFIC BOND to deliver
    │           ↑ ~17 hours after notice = one-day switch option
    └── 2:00pm  Long provides bank information

    DELIVERY DAY:
    ├── 9:00am  Short delivers bond to clearing member bank
    └── 1:00pm  Final deadline; failure penalties SEVERE


    COVERING THE TAIL:
    ──────────────────

    During trade: CF-weighted ratio (e.g., 124 futures per $10M if CF = 1.24)
    At delivery:  1:1 ratio (100 futures per $10M, always)

    The EXTRA 24 futures are the "tail" -- unhedged price risk.

    ┌──────────────────────────────────────────────────────────────┐
    │                                                              │
    │  {IF CF > 1}: extra SHORT futures → exposed to price RISE    │
    │  {IF CF < 1}: extra LONG futures → exposed to price FALL     │
    │                                                              │
    │  Cover the tail = reduce/add contracts to reach 1:1          │
    │  Timing: as close to final trading bell as possible          │
    │  Earlier = more timing risk; later = better execution risk   │
    │                                                              │
    └──────────────────────────────────────────────────────────────┘


    REFRESHING (short basis sellers only):
    ──────────────────────────────────────

    Problem: deliveries assigned to OLDEST longs first
    Solution: buy + sell same-month futures → old longs replaced with new
    Effect: pushes position to back of delivery queue
    Note: all open longs after last trading day must stand for delivery


    BONDS IN THE BOX:
    ─────────────────

    Failure-to-deliver penalties can include:
    • Exchange-imposed fines
    • Forced delivery of non-CTD bond (exchange chooses)

    Requirement: physical possession ≥ 2 days before delivery day
    → Cannot finance via normal repo for last 2 days
    → Must use triparty repo (custody at clearing member) or uncollateralized

    CONSTRAINT:
    ───────────
    [Triparty/uncoll. rate - normal RP rate] ──┤ [Carry] → last 2 days carry is worse

**Key relationships:**
- Tail = |CF - 1.0| × position size (in contracts)
- Cover-the-tail timing: last minutes of last trading day
- Refreshing available only during trading hours (not post-expiry)
- Bonds-in-the-box cost: ~2 days of above-market financing
- The 1:1 jump at expiry is the reason hedge ratios behave discretely

**Connects to:** M5 (post-expiry world where 1:1 applies), M10 (delivery timing decisions), M13 (P/L affected by tail management)

---

### M16: Calendar Spread Relative Value

**In one sentence:** The calendar spread (front minus back futures) has a theoretical fair value derived from carry and delivery option differences across contract months, and mispricings create opportunities for spread trades, enhanced basis trades, and lower-cost hedging.

**Diagram:**

    FAIR VALUE:
    ───────────

    Spread_fair = Futures_front_fair - Futures_back_fair

    Where:
      Futures_fair = (CTD Price - CTD Basis Fair Value) / CTD Factor

    Mispricing = Spread_actual - Spread_fair


    THREE USES OF CALENDAR SPREAD MISPRICINGS:
    ───────────────────────────────────────────

    1. OUTRIGHT SPREAD TRADE:
       Buy cheap spread / sell rich spread
       Risk: yield curve changes, no forced convergence at expiry

    2. ENHANCED BASIS TRADE (2-3/32nds pickup):
       Buy cheap calendar spread → take delivery at front expiry
       → results in long basis in deferred month at below-market cost
       Example: calendar spread 2.4/32nds cheap
       → buy spread, take delivery, own deferred basis at 2.4/32nds discount

    3. LOWER-COST HEDGING:
       Time the futures roll based on spread mispricing
       → roll when spread is cheap (buy front, sell back)
       → avoid rolling when spread is rich


    SEASONAL PATTERN AROUND FIRST NOTICE DAY:
    ──────────────────────────────────────────

    ┌──────────────────────────────────────────────────────┐
    │                                                      │
    │  Pre-first-notice:                                   │
    │    Longs unwilling to risk early delivery → SELL     │
    │    front, buy back → spread FALLS                    │
    │                                                      │
    │  Strategy for shorts:                                │
    │    BUY spread just before first notice day           │
    │    (cheapest entry)                                  │
    │                                                      │
    │  Strategy for longs rolling forward:                 │
    │    SELL spread early (before seasonal pressure)      │
    │                                                      │
    └──────────────────────────────────────────────────────┘

    EXAMPLE (April 2001, 10yr note):
    ─────────────────────────────────
    Actual Jun/Sep spread:     14.5/32nds
    Theoretical spread:        16.9/32nds
    Mispricing:               -2.4/32nds (spread cheap)
    → Enhanced basis: take delivery in June, own Sep basis 2.4/32nds cheaper

**Key relationships:**
- Calendar spread mispricing ≈ -OAB (same magnitude, opposite sign)
- Saying "futures are cheap" = "basis is rich" = "calendar spread is cheap"
- Seasonal pressure: spreads fall pre-first-notice, recover after
- Enhanced basis pickup: typically 2-3/32nds when mispricings exist
- Calendar spread widens during supply squeezes (shorts forced to roll)

**Connects to:** M8 (squeeze widens spread), M1 (fair value derived from basis fair value), M13 (rolling is an alternative to unwinding)

---

### M17: OTR Basis Cycle

**In one sentence:** On-the-run bonds follow a predictable quarterly cycle -- richening post-auction as short hedges accumulate and the bond goes special, then cheapening pre-next-auction as supply approaches -- creating a rhythmic basis trading opportunity with embedded negative carry.

**Diagram:**

    QUARTERLY OTR CYCLE (e.g., 5yr note):
    ──────────────────────────────────────

    Time ──→

    AUCTION                                NEXT AUCTION
      │                                         │
      ▼                                         ▼
      ├────── RICHEN PHASE ──────┤──── CHEAPEN PHASE ────┤
      │                          │                        │
      │  OTR yield FALLS vs      │  OTR yield RISES vs   │
      │  off-the-run (~5bp)      │  off-the-run (~5bp)   │
      │                          │                        │
      │  Drivers:                │  Drivers:              │
      │  • Short hedges grow     │  • Market expects      │
      │  • Issue goes special    │    new supply           │
      │  • Liquidity premium     │  • Hedges rolled off   │
      │    attracts demand       │  • Special dissipates  │


    TRADING RULES:
    ──────────────

    Early in quarter: BUY OTR basis
      → Benefits from OTR richening (yield spread narrows)
      → Long the basis of the most liquid issue

    Late in quarter: SELL OTR basis
      → Benefits from OTR cheapening (yield spread widens)
      → But WARNING: OTR trades SPECIAL in repo

    THE NEGATIVE CARRY TRAP:
    ────────────────────────

    Selling OTR basis = short a bond that finances at SPECIAL rates
    → Reverse RP income << GC rate
    → Trade has NEGATIVE carry even in positive-slope environment
    → Yield spread move must exceed negative carry to profit

    Example: OTR reverse RP at 2.0% vs GC at 4.5%
    Negative carry = FullPrice × 2.5% × Days/360
    On $10M of 5yr: ~$1,700/month drag

**Key relationships:**
- OTR richening: ~5bp in 1.5 months post-auction (empirical average, 2000-2002)
- OTR cheapening: ~5bp in 1.5 months pre-next-auction
- Selling OTR basis is ALWAYS negative carry (OTR trades special)
- The CTD for 5yr is usually the OLD 5yr → OTR basis trade = yield spread trade
- OTR basis is more liquid than CTD basis (better bid/ask)

**Connects to:** M7 (OTR specialness drives the cycle), M14 (RP/RRP asymmetry is extreme for OTR), M13 (carry drag from specialness enters P/L)

---

### M18: BNOC Scenario Grid

**In one sentence:** The practitioner's tool for evaluating basis trade risk/reward is a matrix of projected BNOCs across yield levels and curve slopes at futures expiration, revealing the full payoff surface and identifying the highest-risk scenarios.

**Diagram:**

    CONSTRUCTION:
    ─────────────

    1. Start with current yield distribution of deliverables
    2. Shock reference bond yield by -60bp to +60bp (10bp increments)
    3. Apply yield betas to compute non-parallel curve shifts
    4. Optionally: vary curve slope ±1.5 standard deviations
    5. For each cell: identify CTD, compute EOM option, solve for futures, calculate all BNOCs


    SCENARIO GRID (schematic, April 2001 bond futures):
    ───────────────────────────────────────────────────

                    ← Yields Fall                    Yields Rise →
                    -60   -40   -20    0    +20   +40   +60

    CTD (7-5/8%):   11+   5+    2+   1+    2+    5     24     ← BNOC at expiry
                                       *
    Key competing:
    8-1/8% (low D):  5    1+    0*   1     5     11+    20
    5-1/2% (high D): 72   50+   33+  18+   8     2     0+*

    * = cheapest to deliver in that scenario


    READING THE GRID:
    ─────────────────

    For a SHORT basis seller of the 7-5/8% at BNOC = 10.1:

    Yield unchanged:  10.1 → 1.5 = profit of 8.6/32nds
    Yields -60bp:     10.1 → 11.5 = loss of 1.4/32nds
    Yields +60bp:     10.1 → 24 = loss of 13.9/32nds (!!!)

    WORST CASE: yields +60bp WITH curve steepening = BNOC → 17/32nds
    (curve steepening in a selloff is the nightmare scenario)


    THE ASYMMETRIC RISK MAP:
    ────────────────────────

    For CTD basis SELLER:
    ┌────────────────────────────────────────────────────────┐
    │                                                        │
    │  Max profit: BNOC at inception (≈ 5-10/32nds)          │
    │  Earned slowly via time decay over ~3 months           │
    │                                                        │
    │  Max loss: UNLIMITED                                   │
    │  Realized suddenly via CTD switch                      │
    │                                                        │
    │  Win rate: High (~23/25 quarters in 10yr)              │
    │  But losses can dwarf accumulated gains                │
    │                                                        │
    │  → Classic short-vol payoff profile                    │
    └────────────────────────────────────────────────────────┘

    For CTD basis BUYER:
    ┌────────────────────────────────────────────────────────┐
    │                                                        │
    │  Max loss: BNOC at inception                           │
    │  Lost slowly via time decay if yields don't move       │
    │                                                        │
    │  Max gain: UNLIMITED                                   │
    │  Realized via CTD switch or squeeze                    │
    │                                                        │
    │  → Classic long-vol payoff profile                     │
    └────────────────────────────────────────────────────────┘

**Key relationships:**
- Grid uses yield betas (nonparallel shifts), not parallel shifts
- Worst case for short basis: curve steepening in a selloff (low probability but high impact)
- The grid reveals whether delivery options are overpriced (many scenarios where BNOC decays to near zero)
- Breakeven yield move = level at which BNOC at expiry equals BNOC at inception
- The 10yr contract's grid was persistently favorable for sellers (options far OTM) in 2000-2004

**Connects to:** M3 (the option payoff profile), M4 (yield shift and spread scenarios), M13 (ΔBNOC = seller's P/L)

---

### M19: Deliverable Supply Anatomy

**In one sentence:** The effective deliverable supply is not the total par outstanding but the unstripped, unencumbered float that can actually be mobilized for delivery, and this float erodes through stripping, central bank holdings, buy-and-hold portfolios, and secular issuance changes.

**Diagram:**

    SUPPLY LAYERS (per issue):
    ──────────────────────────

    [Total Par Outstanding]
         │
         ├── [Stripped Amount] ──── UNAVAILABLE for delivery
         │     (reconstitution possible but slow)
         │
         ├── [Central Bank Holdings] ──── UNAVAILABLE
         │     (Fed SOMA, foreign CBs)
         │
         ├── [Buy-and-Hold Portfolios] ──── MOSTLY unavailable
         │     (insurance, pensions; CAN be sold but won't be for basis)
         │
         └── [Tradable Float] ──── EFFECTIVE SUPPLY
               │
               └── Further reduced by:
                   • Repo market encumbrance (already lent)
                   • Delivery fails chain
                   • Japanese institutions (historically: won't lend in repo)


    SECULAR DRIFT:
    ──────────────

    As bonds age:
    • Duration drifts down → bond moves through CTD eligibility window
    • Stripping increases (long-dated zeros popular) → float shrinks
    • No new supply added (Treasury issues at different points on curve)

    As Treasury policy changes:
    • Buybacks (2000): removed older high-coupon bonds → reduced supply
    • 30yr suspension (Oct 2001): no new long bonds → existing bonds more precious
    • Coupon change (8% → 6%, 2000): re-centered deliverable set → supply broadened temporarily

    CTD MATURITY DRIFT (Era 8 example):
    ────────────────────────────────────
    The 11-1/4% of 2/15 was CTD from Jun 1995 to Dec 1999
    Maturity drifted: 19 years (1995) → 15 years (1999)
    → Contract became a ~15yr hedge, not a 30yr hedge
    → Usefulness for hedging 30yr exposure degraded
    → CBOT forced to change factor coupon from 8% to 6%

**Key relationships:**
- Effective supply = Total outstanding - Stripped - CB holdings - Encumbered
- Squeeze probability ∝ Open interest / Effective supply (not total outstanding)
- Stripped amount can increase or decrease (STRIPS arbitrage)
- New issuance effect on CTD is paradoxical: high yields → high-coupon new issue → low duration → NOT CTD when high-duration needed

**Connects to:** M8 (supply constraint is the trigger), M7 (float determines specialness threshold), M2 (secular drift changes CTD landscape)

---

### M20: Four Competing Hedge Ratios

**In one sentence:** When yield correlations are imperfect, four distinct hedge ratios -- conventional, yield beta, yield delta, and minimum variance -- diverge significantly, each optimizing a different objective, and the choice between them reflects a trade-off between expected P/L and P/L variance.

**Diagram:**

    FOUR RATIOS (hedging $100M 30yr with 5yr, correlation = 0.88):
    ──────────────────────────────────────────────────────────────

    ┌──────────────┬──────────────┬────────────┬───────────┬──────────────┐
    │ Hedge Type    │ Short 5yr    │ Daily StDev│ Net DV01  │ Net E[DV01]  │
    │               │ ($mm)        │ ($)        │ ($k)      │ ($k)         │
    ├──────────────┼──────────────┼────────────┼───────────┼──────────────┤
    │ Unhedged      │ 0            │ 770        │ 149.1     │ 149.1        │
    │ Min Variance  │ 240.7        │ 366 (MIN)  │ 43.9      │ 33.6         │
    │ Yield Beta    │ 273.6        │ 377        │ 29.5      │ 17.9         │
    │ Yield Delta   │ 310.9        │ 416        │ 13.2      │ 0 (ZERO)     │
    │ Conventional  │ 341.2        │ 463        │ 0 (ZERO)  │ -14.6        │
    └──────────────┴──────────────┴────────────┴───────────┴──────────────┘

    FORMULAS:
    ─────────

    Conventional:   HR = DV01_hedge / DV01_instrument
                    → Net DV01 = 0; but E[net DV01] ≠ 0 when ρ < 1

    Yield Beta:     HR = Conventional × (σ_hedge / σ_instrument)
                    → Adjusts for differing yield vols; overcorrects when ρ < 1

    Yield Delta:    HR = Conventional × (σ_hedge / (σ_instrument × ρ))
                    → Sets E[net DV01] = 0 via regression coefficient

    Min Variance:   HR = Conventional × (σ_hedge × ρ / σ_instrument)
                    → Minimizes day-to-day P/L variance; most bullish position


    KEY INSIGHT:
    ────────────

    When ρ = 1.0: ALL FOUR ARE IDENTICAL
    When ρ < 1.0: they diverge, sometimes dramatically

    Conventional:  zero DV01 but NEGATIVE expected DV01 (biased short)
    Min Variance:  positive net DV01 (biased long) but lowest day-to-day variance
    Yield Delta:   zero EXPECTED DV01 but nonzero actual DV01
    Yield Beta:    in between, overcorrects

    INSTABILITY WARNING:
    ────────────────────
    10yr yield beta ranged 0.46 (1993) to 2.88 (1991) across years
    → In 1993, using yield betas INCREASED hedging error
    → Betas work on average but can fail spectacularly in regime shifts

**Key relationships:**
- All four converge as ρ → 1.0
- Min variance < Yield beta < Yield delta < Conventional (in hedge size)
- Conventional is the most bearish; min variance is the most bullish
- Yield betas reduce tracking error std dev (19bp → 16bp) on average but are unstable
- For basis trades: use conversion factor ratio (not DV01) to track the defined basis

**Connects to:** M9 (option-adjusted DV01 is yet another ratio that supersedes these near crossover), M12 (synthetic construction uses spot DV01/forward DV01)

---

### Composed: Death of Gamma

**Chain:** M6 → M4 → M9

    [Spread-yield correlation → ±1] (M6)
        │
        ▼
    {GATE: systematic spreads fully directional}
        │
        ▼
    [Switch option value → 0] (M4)
        │
        ▼
    [CTD permanently entrenched] (M2)
        │
        ▼
    [Negative convexity zone vanishes] (M9)
        │
        ▼
    [BNOC collapses to carry + trivial EOM option]

**Narrative:** When yield spread behavior becomes fully correlated with yield level changes, the effective crossover yield moves to an unreachable distance, killing the switch option entirely. The CTD becomes permanently entrenched, the basis loses its option character, and gamma disappears from the futures contract. This occurred in 1991-1993 and represents the extreme of the spread dampener regime.

---

### Composed: Squeeze Cascade

**Chain:** M7 → M8

    [Bond goes special in repo] (M7)
        │
        ▼
    {GATE: OI > deliverable float}
        │
        ▼
    [RP rate → 0% → negative] (M7)
        │
        ▼
    [Delivery failure probable] (M8)
        │
        ▼
    [BNOC < 0, calendar spread blows out]

**Narrative:** The repo specialness spiral (M7) feeds the supply squeeze cascade (M8) when the physical supply constraint binds. Specialness is the early warning signal; negative BNOC is the confirmation that the market has transitioned from options pricing to failure-probability pricing.

---

### Composed: Synthetic Yield Enhancement Regime

**Chain:** M12 → M1 → M11

    [Futures chronically cheap (mortgage/dealer selling)] (M12)
        │
        ▼
    {GATE: OAB persistently < 0}
        │
        ▼
    [Premium > 0 → synthetic outperforms physical] (M12)
        │
        ▼
    [Vol arbs buy basis → basis richens slowly] (M11)
        │
        ▼
    [Premium narrows → enhancement decays]

**Narrative:** When structural selling pressure (mortgage hedgers, dealer short-basis positions) keeps futures cheap, portfolio managers earn systematic yield enhancement from synthetics. Vol arbitrageurs act as the balancing mechanism that slowly closes the gap, but structural flows can maintain the cheapness for extended periods.

---

## Causal Primitives

| ID | Primitive | Pattern | Used In |
|----|-----------|---------|---------|
| P1 | Moving Strike | Systematic force shifts the effective exercise threshold, making the option harder to trigger | M4, M6, M9 |
| P2 | Buffer Until Break | Stock (deliverable supply) absorbs flow (open interest) until physical constraint binds, then regime rupture | M7, M8 |
| P3 | Reflexivity | Price → behavior → price: bond richening attracts shorts, shorts create demand, demand causes further richening | M7 |
| P4 | Identity Constraint | Basis ≡ Carry + BNOC forces: any change in basis decomposes exactly into carry change + BNOC change; no third channel exists | M1 |
| P5 | Regime-Dependent Path | Which causal links are active depends on the structural state; the same yield change activates different mechanisms in different regimes | M4, M6, M10 |
| P6 | Minimum Envelope | Futures = min(converted prices) creates a convex hull below competing curves; distance from hull = option value | M3, M9 |
| P7 | Dampener Exhaustion | The spread dampener (B1) has finite capacity; when spread-yield correlation saturates, the dampener becomes a total gamma eliminator | M6, Composed: Death of Gamma |
| P8 | Paradox of Best Trade | The most "obviously attractive" short basis carries the greatest squeeze risk because crowd positioning is self-defeating | M7, M8 |
| P9 | Horizon Mismatch | Options and basis positions expire at different times, creating residual vega risk that prevents perfect arbitrage | M11 |
| P10 | Dual-Clock Independence | Spot yields (driven by macro) and repo rates (driven by money market/Fed) evolve on independent clocks with R-squared ≈ 0; forward prices respond to both through mechanically distinct channels | M1, M12 |
| P11 | Asymmetric Payoff Envelope | Selling the basis has capped upside (= BNOC) earned slowly and uncapped downside realized suddenly; buying the basis inverts this. Every basis trade is a volatility position with this signature. | M3, M13, M18 |
| P12 | Hidden Friction | The RP/RRP spread (10-25bp) is invisible in quoted basis levels but directly enters P/L; specialness can amplify this to hundreds of basis points. The "real" carry differs from the "screen" carry by this friction. | M14, M17 |
| P13 | Discrete Transition | The hedge ratio jumps from CF-weighted to 1:1 at expiry; the CTD metric shifts from duration to BPV; the options regime shifts from switch to end-of-month. These are not gradual -- they are mechanical phase changes. | M5, M15, M9 |
| P14 | Seasonal Rhythmic Pattern | The OTR cycle, the calendar spread seasonal around first notice, and the quarterly expiry convergence all create predictable time-based patterns exploitable by traders who understand the institutional flows driving them. | M16, M17 |
| P15 | Float Erosion | Effective deliverable supply is a melting ice cube: stripping, CB purchases, and buy-and-hold accumulation steadily reduce tradable float. Squeezes are the eventual consequence when new issuance doesn't replenish. | M19, M8 |
| P16 | Rounding Artifact | Conversion factors round maturity to nearest quarter; basis positions use whole contracts. Both create small but systematic biases that compound in large positions and are the source of "slippage" in basis P/L tracking. | M2, M13 |

---

## Regime Taxonomy

| State | Name | Description | Active Loops | Dominant Primitive |
|-------|------|-------------|--------------|-------------------|
| S1 | Firm CTD / Simple Carry | Yields far from crossover; single bond firmly CTD; BNOC small; basis ≈ carry | None active (quiescent) | P4 (identity) |
| S2 | Unstable CTD / Options Active | Yields near crossover; multiple close CTD contenders; BNOC large; negative convexity zone active | R1 (negative convexity), B1 (spread dampener) | P1 (moving strike), P6 (min envelope) |
| S3 | Gamma Death / Spread Entrenchment | Directional yield spreads prevent switching despite yield changes; CTD permanently entrenched; BNOC → near zero | B1 dominates (dampener saturated) | P7 (dampener exhaustion) |
| S4 | Supply Squeeze / Delivery Failure | OI > deliverable supply; BNOC < 0; calendar spread dislocated; arbitrage relationships broken | R2 (specialness spiral), R3 (squeeze cascade) | P2 (buffer until break), P8 (best trade paradox) |
| S5 | Inverted Carry / Wild Card | Negative carry; high conversion factors; intraday vol sufficient for wild card exercise; delivery timing becomes strategic | R2 (wild card loop) | P5 (regime-dependent path) |
| S6 | Chronic Futures Cheapness / Golden Age | Structural selling pressure (dealer short-basis, mortgage hedging) keeps futures persistently below fair value; OAB < 0 for extended periods; yield enhancement works reliably | B2 (vol arb equilibrium, but overwhelmed by structural flows) | P11 (asymmetric payoff), P14 (seasonal) |
| S7 | Single-Bond Contract / Dry Spell | One bond so firmly CTD that no realistic yield scenario produces a switch; contract degrades into a single-bond forward; delivery option value trivial; basis trading dies | None (all options deep OTM) | P7 (dampener exhaustion) |

### Transition Map

    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │   [S1: Firm CTD] ──{yields drift to crossover}──→ [S2]    │
    │        ▲                                           │       │
    │        │                                           │       │
    │   {yields move                              {spread-yield  │
    │    away from                                 correlation   │
    │    crossover}                                → ±1}         │
    │        │                                           │       │
    │        │                                           ▼       │
    │   [S1] ←──{correlation breaks / vol shock}── [S3: Death]   │
    │                                                            │
    │                                                            │
    │   [S1 or S2] ──{OI >> CTD float}──→ [S4: Squeeze]         │
    │                     ▲                      │               │
    │                     │                      │               │
    │              {supply restored /      {yield regime         │
    │               exchange intervention}  shift creates        │
    │                                       new CTD}             │
    │                     │                      │               │
    │                     └──────────────────────┘               │
    │                                                            │
    │                                                            │
    │   [Any] ──{curve inverts + vol high + factors >> 1}──→ [S5]│
    │              ▲                                         │   │
    │              │                                         │   │
    │              └───{curve normalizes / vol drops}────────┘   │
    │                                                            │
    └────────────────────────────────────────────────────────────┘

### Transition Logic

    S1 → S2:  {IF |yield - crossover| < threshold AND vol > minimum}
    S2 → S1:  {IF |yield - crossover| > threshold (yields move away)}
    S2 → S3:  {IF |corr(Δspread, Δyield)| → 1 for sustained period}
    S3 → S1:  {IF correlation regime breaks (exogenous shock)}
    S1/S2 → S4:  {IF OI / CTD_float > 1 AND BNOC_gap(CTD, 2nd) large}
    S4 → S1/S2:  {IF yield shift creates new CTD OR exchange intervenes OR sufficient roll-off}
    Any → S5:  {IF carry < 0 AND |conversion factor - 1| > threshold AND intraday vol > wild card break-even}
    S5 → S1:  {IF curve normalizes AND vol subsides}

---

## Doctrines

| # | Doctrine |
|---|----------|
| D1 | "The basis is carry plus option value" -- this decomposition is exact, exhaustive, and the starting point for every analysis |
| D2 | "The CTD's BNOC is pure option value; everyone else pays option value plus an expensiveness premium" -- only the CTD tells you what delivery options cost |
| D3 | "Buying the basis is buying volatility; selling the basis is selling volatility" -- basis trades are options trades in disguise |
| D4 | "If the basis is cheap, futures are rich" -- the two statements are mathematically equivalent with opposite sign, and the factor is the conversion factor |
| D5 | "The most obviously attractive short basis trade carries the greatest squeeze risk" -- because crowd positioning creates the very scarcity it seeks to exploit |
| D6 | "Yield betas are a correction factor, not a foundation" -- they reduce tracking error on average but are unstable across regimes and can increase error in specific years |
| D7 | "Spot yields and repo rates are independent forces on the forward price" -- a complete hedge must offset both, but repo DV01 is ~50x smaller than spot DV01 |
| D8 | "Negative net basis is not free money -- it prices delivery failure" -- the implied probability of failure is BNOC / (BNOC - 2nd_CTD_BNOC) |
| D9 | "Conversion factors are the source of all optionality" -- without the imperfect equalization, there would be no CTD, no switching, no options, no BNOC |
| D10 | "The end-of-month option runs on BPV, not duration" -- after the invoice price is locked, absolute dollar sensitivity determines the switch, creating a paradox where high-coupon bonds (high BPV, low duration) can become CTD post-expiry |
| D11 | "Systematic yield spread behavior is a dampener on the switch option -- it moves the strike" -- and in extremis it can kill gamma entirely |
| D12 | "The futures price traces the smooth curve below the minimum of converted prices" -- this geometric fact is the root of the option analogy, the negative convexity, and the entire basis ecosystem |
| D13 | "When two markets disagree on volatility, the arb is to buy cheap and sell rich" -- but horizon mismatch, spread risk, and imperfect replication leave residual risk |
| D14 | "Every bond in the deliverable set has a maturity date for its CTD status" -- as bonds age, their duration drifts, and regime changes can abruptly promote or demote them |
| D15 | "Basis seller's P/L equals the negative of the change in BNOC" -- this is exact for the CTD, and almost exact for non-CTD after accounting for the convergence target |
| D16 | "The 10-25bp RP/reverse RP spread is the hidden tax on every basis trade" -- it systematically degrades carry for both long and short basis, and specialness can turn it into a position-destroying force |
| D17 | "Cover the tail as close to the final bell as possible" -- the CF-to-1:1 hedge ratio jump at expiry creates unhedged price risk; minimize the window of exposure |
| D18 | "Selling the OTR basis is always a negative carry trade" -- the OTR trades special in repo, so the reverse RP income is insufficient to cover the coupon paid; the yield spread move must pay for the carry drag |
| D19 | "Refreshing buys time against unwanted delivery assignment" -- buying and selling same-month futures pushes your long to the back of the delivery queue, but all longs must stand after last trading day |
| D20 | "The scenario grid is the basis trader's decision tool" -- project BNOCs across yield levels and curve slopes to determine if delivery options are overpriced relative to the risk surface |
| D21 | "BNOC rankings can diverge from IRR rankings because BNOC ignores price levels" -- two bonds with identical BNOC but different prices have different implied repo rates; the higher-priced bond is actually cheaper to deliver |
| D22 | "Calendar spread mispricing equals option-adjusted basis with opposite sign" -- buying a cheap spread is equivalent to buying cheap futures, which is equivalent to buying a cheap basis |
| D23 | "The deliverable float is a melting ice cube" -- stripping, buybacks, and buy-and-hold accumulation irreversibly reduce effective supply; every delivery cycle draws from a smaller pool unless new issuance replenishes |
| D24 | "In a basis short sale, realized losses come in cash; missed-opportunity losses come in forgone yield" -- portfolio managers who sell basis out of portfolio bear opportunity cost, while outright shorts bear cash-flow cost; the latter is operationally more dangerous |
| D25 | "The four hedge ratios converge only when correlation equals one" -- conventional, yield beta, yield delta, and minimum variance produce the same number only under perfect correlation; with ρ = 0.88 they can differ by 40% |

---

## Source Index

### Canon (defines the framework)

| Source | Models Informed |
|--------|----------------|
| Ch 1: Basic Concepts (definitions, carry, IRR, BNOC, P/L accounting, RP vs RRP) | M1, M13, M14 |
| Ch 2: What Drives the Basis? (CTD rules, option analogy, BNOC scenario grid) | M2, M3, M18 |
| Ch 3: The Short's Strategic Delivery Options (switch, EOM, timing, delivery process) | M4, M5, M10, M15 |
| Ch 4: The Option-Adjusted Basis (OAB, fair value, valuation grid) | M1, M3, M11 |

### Structural (deepens a model)

| Source | Models Informed |
|--------|----------------|
| Ch 5: Approaches to Hedging (DV01s, spot vs repo, yield betas, OA-DV01s, four competing ratios) | M9, M12, M20 |
| Ch 7: Volatility Arbitrage (cross-market vol arb, performance) | M11 |
| Ch 8: Nine Eras (regime history, death of gamma, golden age, squeeze, dry spell) | M6, M7, M8, M10, M19, Regime Taxonomy (all states) |
| Ch 9: Non-Dollar Government Bond Futures (global contracts, design variations) | M2, M5, M19 (modified for non-USD) |
| Ch 10: Applications for Portfolio Managers (synthetics, duration management) | M12 |

### Applied (model in action on a specific case)

| Source | Models Informed |
|--------|----------------|
| Ch 6: Trading the Basis (CTD selling, non-CTD selling, hot-run, squeeze, calendar spreads, RP effects, delivery mechanics) | M3, M7, M8, M13, M14, M15, M16, M17, M18 |
| Ch 8 Era 2: Negative Yield Curve 1979-81 (wild card dominance) | M10, S5 |
| Ch 8 Era 4: Golden Age 1985-89 (chronic futures cheapness, dealer positioning) | M12, M11, S6 |
| Ch 8 Era 6: Death of Gamma 1991-93 (spread entrenchment) | M6, Composed: Death of Gamma, S3 |
| Ch 8 Era 8: Long Dry Spell 1995-99 (entrenched 11-1/4%) | M19, S7 |
| Ch 8 Era 9: 6% Factors 2000+ (rebirth of optionality) | S2, M4, M19 |
| Ch 6: 2005 10yr CTD Supply Squeeze (negative BNOC, forced rolls) | M8, M16, S4 |
| Ch 6: 1986 9-1/4% Short Squeeze (worst squeeze in history) | M7, M8, M14 |
| Ch 1/6: P/L worked examples (buy/sell basis, carry accounting, rounding) | M13, M14 |

### Reference (background / definitions)

- Appendix A: Conversion Factor Calculation
- Appendix B: Carry Calculation Formulas
- Appendix C: Global Government Bond Market Conventions
- Appendix D: German Federal Bond Details (Bund/Bobl/Schatz)
- Appendix E: Japanese Government Bond (JGB) Details
- Appendix F: UK Gilt Details
- Appendix G: Day Count Conventions and Yield Calculation Methods
