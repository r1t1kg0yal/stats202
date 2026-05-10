---
session: BoltWeb pricing engine — capability surface + access mechanism + integration with sandbox / dashboards
sent: 2026-05-09
reply: scans/prism/2026-05-09_boltweb_pricing_engine_reply.md
reply_folded_into:
  - NOT YET FOLDED — reply received, filing complete, analysis-pending. Likely
    new prism/pricing-engine.md (or prism/gs-quant.md) covering the gs_quant
    + gs_quant_internal + BoltWeb routing-prefix surface end-to-end. Plus
    light updates to api-clients.md / code-sandbox.md / dashboard-refresh.md /
    competitive-spec.md per the original prompt frontmatter.
status: USED — reply received and filed at scans/prism/. Section 4 (computation
  surface) returned empty body; Section 6 (output contract) returned only one
  table row. The §4 gap can be back-filled either by a targeted re-prompt or
  by inferring from spoke Section 9 (BoltWeb is transport+routing only; the
  pricing primitives live behind the server-side valuation engine and are NOT
  exposed at PRISM's Python namespace).
key_findings:
  - BoltWeb itself is tiny — 3 modules / ~8 KB / 5 public symbols
    (valuation, capture_market_ref, BotnationApi, botnation_to_portfolio,
    PlexApi). The actual pricing engine is gs_quant + gs_quant_internal
    behind it; BoltWeb is the routing prefix into one valuation backend.
  - PRISM has NO first-party wrapper. gs_quant_internal is vendored on
    sys.path; scripts import directly via `from gs_quant_internal.boltweb
    import ...`. No mcp/clients/, no mcp/utils/, no _USE_GS_PROXY pattern.
  - Auth via gs_quant_auth's KerberosSessionMixin/MQLoginMixin; PRISM
    runs as service account pmacros2.
  - NEITHER the execute_analysis_script sandbox NOR the dashboard refresh
    runner pre-injects BoltWeb / gs_quant. Same status as alt-data clients
    per dashboard-refresh.md §5.5: importable, not pre-wired. A pull_data.py
    must initialise GsSession itself (boilerplate from hub Section 1).
  - Working pricing paths: vanilla rates swaps + swaptions + caps +
    Bermudans, USTs (via GovtBondBuilder/CUSIP), CDS single-name + index,
    MBS TBA, EqAutoCallable + EqPortfolioSwap, FX vanilla options +
    binaries + autocallables + TARFs, commodity swaps + forwards.
  - Broken / missing paths: bond futures, cash IG/HY corporate bond live
    PV/DV01 (TSDB EOD duration fallback only), CMOs / MBS prepay, EqOption
    PV/Greeks (probe-before-rely), COMMOD MDAPI coordinates, RiskCube /
    InquiryCube (NOT PERMISSIONED for pmacros2), XVA primitives.
  - Risk: PV + Greeks work for the working classes (.calc(IRDelta), etc.).
    Scenarios via CarryScenario / CurveScenario /
    MarketDataShockBasedScenario. No XVA exposed.
  - NLP trade-parsing via botnation_to_portfolio(message) is a genuine
    differentiator with no Bloomberg-widget analogue — open-ended catalog
    (700+ TDAPI builders) that maps "5y USD SOFR swap 10mm pay fixed"
    directly to a priced Portfolio.
  - Output: FloatWithInfo for scalars; PortfolioRiskResult for batched
    Portfolio.calc([...]). ErrorValue is the soft-failure surface — must
    always isinstance(result, ErrorValue) check.
  - Latency: ~0.5s per priced builder; 0.38–1.59s for Botnation parse.
    Cold-start materially slower. 10–50 calls per turn = 5–25s feasible
    inline; Portfolio batch is the optimisation.
  - Entitlement gate: pmacros2 can WRITE Portfolio.save_as_quote() but
    generally CANNOT READ Portfolio.from_quote(other_user_quote_id) due to
    per-quote ACL on Marquee. Significant for cross-user / community
    dashboard workflows.
  - Confirmed: BoltWeb + gs_quant + gs_quant_internal is the COMPLETE
    pricing surface PRISM has. No slang / Athena / CalQ / CRiSK / Finch /
    SecDB siblings.
  - Existing skill: gs_quant_spoke_boltweb.md (32 KB) covers the WRITE
    path and entitlement story. Does NOT cross-link to widget_tool.md or
    dashboard-refresh.md.
---

Title: BoltWeb pricing engine — capability surface, access mechanism, sandbox integration, hard limits

I'm scoping how the dashboards authoring layer (`projects/echarts/`,
specifically `widget: tool` per `dashboards/widget_tool.md`) can host
genuinely useful pricing tools — Bloomberg-equivalents like SWPM, CDSW,
OVME, MARS, DLIB, etc. The dashboards system today ships only
`compute_js` for the tool widget, which fits closed-form math (BSM,
bond YTM, Taylor rule, DCF) but is structurally locked out of curve
calibration, vol-surface fits, Monte Carlo, PDE/lattice, XVA, MBS prepay,
and similar. The Phase 4 `compute_python` server-side compute backend is
the placeholder for that gap.

The user has told me PRISM already has access to **BoltWeb**, a GS
pricing engine that handles "a lot of the pricing stuff". This
round-trip exists to figure out exactly which Phase-4-class problems
BoltWeb already solves for PRISM, what its access mechanism looks like,
and where the hard edges are — so the staging side can decide how much
of the gap is a "wire BoltWeb into the sandbox / refresh runner / tool
widget compute_python field" problem vs how much is genuinely new
engineering.

Use `list_ai_repo` and `execute_analysis_script` to introspect. Reply
with verbatim source pasted in fenced code blocks, exact paths, and
exact docstrings. Mirror the section structure below — each numbered
section in your reply answers the same-numbered section here.
Verbatim, no paraphrase, no summary.

If a fact requires reading a file too large to paste in full, paste the
relevant section verbatim and cite the file path + line range so I can
reconcile.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and
what blocked it (file missing, permission denied, symbol ambiguous).
This is NOT a frictions report — it is a minimal coverage note.

---

## 1. Where does BoltWeb live in PRISM?

This is the structural prerequisite for everything else. I need to know
exactly which files PRISM imports from when "BoltWeb" is invoked, what
the public Python surface is, and whether it follows the existing
client / utility / tool patterns in `ai_development/`.

1.1 Search `ai_development/` for any module whose name contains
    `boltweb`, `bolt_web`, `bolt-web`, `bolt`, or any obvious
    abbreviation. List every file found with full path + size + a
    one-sentence description of what's in it. If there's a single
    canonical entry point, name it.

1.2 Is BoltWeb accessed through:
    (a) a client at `mcp/clients/boltweb_client.py` (the
        `prism/api-clients.md` pattern),
    (b) a utility at `mcp/utils/<x>.py` (the `pull_haver_data` /
        `pull_market_data` / `pull_plottool_data` pattern in
        `mcp/utils/data_functions.py`),
    (c) a tool at `mcp/tools/<x>.py`,
    (d) a top-level helper at `mcp/<x>.py` analogous to
        `mcp/gs_app_proxy_negotiate.py`,
    (e) a Python package vendored under `ai_development/` (e.g.
        `ai_development/boltweb/...` with its own internal
        modules), or
    (f) something else entirely (a wrapper around an external `pip`
        package, a GS-internal module path like `risk_calc.boltweb`,
        a sibling repo on `sys.path`)?

    Confirm which, and paste the canonical import line(s) PRISM
    actually uses today.

1.3 Paste the verbatim public surface of the canonical entry-point
    module (top-level functions + classes + their docstrings —
    bodies omitted unless short). Use
    `list_ai_repo(file_paths=[<path>], mode="signatures")` if the
    module is large.

1.4 Is there a registry entry in
    `ai_development/context/registry.py` (`MODULE_REGISTRY`) for a
    BoltWeb skill / guide / tool-doc? If yes, paste the verbatim
    entry. If no, say so plainly.

1.5 Is there an L2 skill / context module for BoltWeb under
    `ai_development/context/modules/static/` (e.g.
    `boltweb_guide.md`, `pricing_engine.md`, `tools/boltweb.md`,
    `instruments/<x>.md`)? List every file whose role is to teach
    PRISM how to use BoltWeb, and paste the H1 + first paragraph of
    each.

---

## 2. Authentication + transport

BoltWeb is presumably GS-internal, so the transport choice — standard
requests through the GS proxy (`session_and_auth()`) vs manual CONNECT
tunnel (`manual_https_request()`) vs a non-HTTP RPC layer vs an
in-process Python library — determines how the sandbox + dashboards
refresh runner reach it.

2.1 What transport does BoltWeb use under the hood? Paste the verbatim
    line(s) where the BoltWeb module makes its outbound call(s) — HTTP,
    a Python RPC, a thrift / gRPC call, a shared-memory queue, a
    direct database read. If HTTP, name the transport function it
    calls and paste the imports.

2.2 Is the `_USE_GS_PROXY` flag (see `prism/gs-proxy.md` §5.3 for the
    tri-modal pattern across other clients) present in the BoltWeb
    module? Hardcoded `True`? Env-driven? Network-probe? Paste the
    verbatim line.

2.3 What auth does BoltWeb require — SPNEGO/Kerberos via
    `KerberosProxyAuthAdapter`, a service-account token, an OAuth
    bearer, none (in-process)? Paste any auth-construction code
    verbatim.

2.4 What endpoint(s) does it talk to (host + base path)? If multiple
    environments exist (prod / qa / dev / staging) name them all and
    say which one PRISM points at by default.

2.5 Are there any `os.environ` requirements (e.g.
    `BOLTWEB_USERNAME`, `KRB5CCNAME`, `BOLTWEB_API_KEY`,
    `GS_PROD_TOKEN`)? List every env-var lookup in the module.

---

## 3. Asset-class coverage matrix

This is the load-bearing capability question. I want a complete map of
what BoltWeb can and cannot price. Where the answer "depends on the
sub-product", break it out.

For each asset class below, fill in the four columns:

```
[asset class] | [products supported] | [products NOT supported] |
              | [pricing models / methods]                       |
```

Where "pricing models / methods" lists the actual numerical machinery
exposed (closed-form, lattice/binomial/trinomial, finite-difference /
PDE, Monte Carlo, curve bootstrap, vol-surface fit, etc.). Cite where
in the BoltWeb code/docstrings/skill these are defined; do not
fabricate.

3.1 **Rates** — govts, swaps (vanilla / OIS / XCCY / MTN / cap-floor /
    swaptions / callable / Bermudan), basis swaps, repo, FRAs, futures.

3.2 **Credit** — cash bonds (corp / sovereign / muni), single-name CDS,
    index CDS (CDX, iTraxx), CLNs, options on CDS, recovery products,
    capital-structure arbitrage payoffs.

3.3 **MBS / Securitized** — TBA, pools (agency + non-agency), CMOs
    (with waterfall), ABS, CLOs, RMBS, prepayment models (PSA stack,
    proprietary).

3.4 **Equity derivatives** — listed options (vanilla American /
    European), exotic options (barrier / Asian / digital / lookback /
    cliquet / autocallable / variance swap), structured equity
    notes, dispersion / correlation products.

3.5 **FX** — spot, forwards, NDFs, vanilla options, exotic options
    (barrier / Asian / TARN / digital / dual-digital), G10 + EM
    coverage scope.

3.6 **Commodities** — futures, swaps, options on futures, calendar
    spreads, structured energy / metal products.

3.7 **Cross-asset / hybrid** — equity-linked notes with rate
    components, FX-linked credit, multi-asset baskets, callable
    multi-leg structured notes.

3.8 **Custom term-sheets** — can a user-supplied payoff (Python
    function, JSON tree, FpML XML) be priced? If yes, what's the
    contract for declaring such payoffs? If no, name the formal
    payoff catalog BoltWeb operates on and list its size.

For each of 3.1–3.8 also flag explicitly:

- Does BoltWeb compute **risk / sensitivities** (Greeks,
  DV01 / KRD / DV01-by-tenor, vega-by-tenor / vega-by-strike,
  cross-gamma, ...) for that asset class, or only NPV?
- Does it compute **scenarios / stress / VaR** for that asset class
  (e.g. parallel curve shock, parallel vol shock, basket loss)?
- Does it compute **XVA** (CVA / DVA / FVA / KVA / MVA) for that
  asset class?

If BoltWeb has a definitive "asset class catalog" or "supported
instruments" data structure / registry / enum, paste it verbatim
(this is the highest-information answer and short-circuits §3.1–3.8).

---

## 4. Computation surface — the numerical machinery

3.x covers product coverage. This section covers what BoltWeb does
*underneath* — the computational primitives PRISM can call directly
without going through a high-level pricing call.

4.1 **Curve bootstrapping / calibration** — does BoltWeb expose a
    primitive to bootstrap an OIS / SOFR / EONIA / multi-curve from
    market quotes (deposits, futures, FRAs, swaps)? Paste the public
    function signature(s) plus a one-line description.

4.2 **Vol surface construction** — SVI, SABR, Heston, local-vol,
    Bjerksund-Stensland, custom? Paste the public surface (the
    "calibrate-this-surface-from-this-quote-grid" primitive plus
    the "evaluate-vol-at-(K,T)" primitive).

4.3 **Monte Carlo engine** — is there a generic MC engine PRISM
    can drive directly (define payoff function → simulate → return
    distribution)? How are paths generated (sobol, halton,
    pseudo-random, antithetic, Brownian bridge)? Variance reduction
    techniques? Convergence diagnostics?

4.4 **PDE / lattice / FD** — is there a primitive PRISM can drive
    directly to solve a PDE / build a tree / FD-grid for a custom
    boundary condition? Or is this strictly internal to specific
    pricers (callable swaps, exotics, etc.)?

4.5 **Optimisation / solvers** — Newton / Brent / Levenberg-Marquardt
    / global optimisers? Are these GS-internal scipy wrappers or
    something custom?

4.6 **Calendar / day-count / fixings** — is there a canonical
    business-calendar / day-count / holidays / fixings utility
    PRISM should reuse instead of authoring its own?

4.7 **Sensitivity engines (AD vs bump)** — does BoltWeb compute
    sensitivities by automatic differentiation (forward / reverse
    AD), bump-and-revalue, analytic differentiation, or some mix
    per pricer?

If BoltWeb's primitives are NOT exposed to PRISM at this granularity
(only high-level pricing calls are), say so plainly and skip §4.1–4.7
— that itself is the answer.

---

## 5. Input contract — identifiers, term-sheets, overrides

5.1 What identifiers does BoltWeb accept for already-known
    instruments? CUSIP / ISIN / SEDOL / FIGI / RIC / Bloomberg
    ticker / GS internal ID / multiple? Paste the relevant lookup
    code if it exists.

5.2 What's the input contract for a single pricing call — Python dict,
    typed dataclass, JSON, proprietary class, FpML-style XML? Paste
    a realistic example (or a docstring example) verbatim.

5.3 Override knobs — can the caller pass a custom curve / vol surface
    / spot fixing / dividend assumption / interpolation method to
    override BoltWeb's defaults? Or is the call always
    market-environment-driven? Paste the override interface if
    one exists.

5.4 What conventions does BoltWeb apply by default (day-count, calendar,
    valuation date, holiday handling)? Are these per-instrument-class
    defaults, or a global session config? Paste the relevant config
    block / default constants verbatim.

5.5 Is "user-built term sheet" a first-class input, or is BoltWeb
    strictly catalog-driven (i.e. it can only price instruments
    BoltWeb's catalog already knows about)? If first-class, paste
    the term-sheet schema + a worked example.

---

## 6. Output contract — what comes back from a pricing call

6.1 What does the standard "price one instrument" call return?
    A scalar NPV? A dict with NPV + Greeks + cashflows? A typed
    `PricingResult` class? Paste a realistic example verbatim
    (output of a `dir(result)` or a `print(result)` if available).

6.2 Are there layered "report" objects that bundle NPV + risks +
    scenarios + cashflows + diagnostics into a single response,
    analogous to a Bloomberg `YAS` screen? Paste the public class
    + its main accessors.

6.3 Format — Python dict / pandas DataFrame / numpy array / nested
    dataclass? Are returns DataFrame-friendly out of the box (so
    `pull_data.py` can write CSV directly), or is there a coercion
    step PRISM has to do?

6.4 Are units / conventions encoded in the output (price in clean
    vs dirty, yield in pct vs bp, NPV in trade currency vs reporting
    currency, ...)? Paste any unit-handling code or convention
    constants.

6.5 Diagnostics — does the response carry calibration residuals,
    MC standard errors, optimiser iteration counts, warning lists?
    Paste the relevant fields.

---

## 7. Performance, latency, throughput

This is the practical question for whether PRISM can call BoltWeb
inline during a chat session, inside the dashboards refresh runner
(hourly), inside a `widget: tool`'s `compute_python` field (Phase 4 —
when that lands, if it lands), or only via batch / background paths.

7.1 What's the expected latency for the canonical "price one vanilla
    instrument" call (e.g. a 10y USD IR swap, a vanilla European
    BSM call, a 5y CDS)?

7.2 What's the expected latency for the canonical heavy call (e.g.
    a callable / Bermudan with a full lattice, a CDX index pricer
    with hazard-rate calibration, a vol-surface-calibrated equity
    barrier)?

7.3 Is there a batched / vectorised pricing entry point — price an
    array of instruments / strikes / tenors in one call? Paste the
    public surface if so.

7.4 Sync vs async / job-server pattern — does BoltWeb support
    "submit job, poll for result"? If yes, paste the submit + poll
    function signatures.

7.5 Rate limits / quotas — are there documented per-user / per-session
    QPS caps? Paste any rate-limit handling code (retry / backoff
    decorators).

7.6 Caching — does BoltWeb cache curves / vol surfaces / instrument
    metadata between calls in the same Python session, or is every
    call cold? Paste the caching layer if there is one.

---

## 8. Failure modes, error surface

8.1 What exception classes does BoltWeb raise (analogous to
    `FiscalDataError` in `treasury_client.py`)? Paste each verbatim
    class header line + a one-line description of when it fires.

8.2 Soft-failure paths — does BoltWeb ever return NaN / None / a
    `PricingResult` with `success=False` instead of raising? List
    each soft-failure surface and the typical cause.

8.3 What does "calibration failed" surface as — exception, sentinel
    value, partial result?

8.4 What does "instrument not found in catalog" surface as?

8.5 What does "transport error" / "auth error" / "network timeout"
    surface as? Are these wrapped into BoltWeb-specific exceptions
    or do they leak as raw `requests.exceptions.*` / `GSSError`?

---

## 9. Sandbox + refresh-runner injection — the integration question

This is the bridge between what BoltWeb can do (§3–§8) and what PRISM
+ the dashboards can actually use it for.

9.1 Is BoltWeb injected into the `execute_analysis_script` sandbox
    namespace today? Paste the relevant entries from
    `mcp/tools/script_exec_tools.py`'s exec_namespace dict (the
    one that already injects `pull_haver_data`, `pull_market_data`,
    `make_chart`, etc.). Confirm or deny each name PRISM might use
    inside an `execute_analysis_script` call to reach BoltWeb.

9.2 Is BoltWeb injected into `_build_exec_namespace` in
    `ai_development/jobs/hourly/refresh_dashboards.py` (the dashboard
    refresh runner)? Per the `prism/dashboard-refresh.md` §5.5 known
    gap, alt-data clients are NOT injected into the refresh-runner
    namespace today; a dashboard `pull_data.py` that imports them
    raises `NameError` at refresh time. Is BoltWeb in the same
    bucket (sandbox-only) or wired into the refresh runner too?

9.3 If a dashboard's `pull_data.py` calls BoltWeb to compute prices
    for the dashboard's data layer, would that work today on the
    daily refresh path? Walk through the scenario.

9.4 If the dashboards system someday adds `compute_python` (the
    Phase 4 server-side compute backend documented in
    `projects/echarts/echarts-payload/dashboards/widget_tool.md` §5),
    is BoltWeb the natural backend, or is there a more direct
    primitive PRISM should reach for?

9.5 Latency sanity — given §7.1 and §9.1, can PRISM realistically
    call BoltWeb 10–50 times in a single user turn (e.g. to populate
    a curve term-structure matrix or a Greeks ladder), or is even
    a handful of calls per turn pushing the budget?

---

## 10. Worked examples — paste verbatim PRISM-side calls

If PRISM has used BoltWeb in past sessions, paste the verbatim Python
that was actually executed. Three classes I'm specifically looking for:

10.1 A vanilla rates pricing — a 10y USD swap (or a UST cashflow
     valuation) with NPV + DV01.

10.2 A vanilla equity-derivatives pricing — a BSM call / put with
     spot / strike / vol / rate / div input, NPV + Greeks output.

10.3 A vanilla credit pricing — a 5y single-name CDS or a CDX
     spread with NPV + DV01 + IR-DV01 (or whatever standard risks
     come back).

If past calls aren't preserved in S3 / chat history, fabricate a
canonical-shape example from the docstrings or the test files
adjacent to the BoltWeb module (e.g. `tests/test_boltweb*.py`,
`mcp/clients/test_boltweb_client.py`, etc.) and paste those test
inputs + expected outputs verbatim.

10.4 If there's a `mcp/clients/boltweb*` module or a
     `mcp/utils/<boltweb>.py`, paste the first 100 lines (imports +
     module docstring + first one or two function bodies). I want
     to see the call shape with my own eyes.

---

## 11. Hard non-capabilities — where BoltWeb stops

11.1 Asset classes / instrument types BoltWeb explicitly does NOT
     handle. Is there a "we don't price X" list documented anywhere
     (in docstrings, in skill markdown, in the issue tracker)?
     Paste it.

11.2 If a user asks PRISM to price something BoltWeb can't handle,
     is there a documented fallback path (e.g. "for variance swaps,
     use the QuantLib client at `mcp/clients/quantlib_client.py`")?

11.3 Are there any other GS-internal pricing engines on PRISM's
     namespace alongside BoltWeb (e.g. `slang`, `Athena`, `CalQ`,
     `CRiSK`, `Finch`, `SecDB`, anything ending in `_pricer.py`)?
     List them with one-line scope. Specifically check
     `ai_development/mcp/clients/`, `ai_development/mcp/utils/`,
     and `ai_development/mcp/`.

11.4 If BoltWeb is the sole pricing engine PRISM has access to,
     confirm that explicitly — I want to be sure I'm not missing
     a sibling.

---

## 12. Skill / context module status

12.1 List every file under
     `ai_development/context/modules/static/` (or any sibling
     `context/modules/<x>/`) whose role is to teach PRISM how to
     USE BoltWeb (vs documenting general pricing concepts). Paste
     the H1 + first paragraph of each.

12.2 If a BoltWeb skill exists, paste the verbatim "what this engine
     can / cannot do" section. If multiple BoltWeb-related skill
     files exist, list them and indicate which is the canonical
     entry point.

12.3 Trigger logic — when does BoltWeb's skill module get pulled
     into PRISM's context? Always-on (Tier 1)? Bundled with a
     specialisation? Keyword-triggered? Paste the relevant
     trigger / routing logic if it lives in code; describe the
     convention if it lives only in module frontmatter.

12.4 If NO skill module exists for BoltWeb today (just the
     underlying Python module), say so plainly. That's actionable
     signal — it means we'd need to author one in staging before
     the round-trip-verification loop closes.

---

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it.
