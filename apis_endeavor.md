# APIs Endeavor — Multi-Session Plan

This file is the cross-session handoff artifact for the work of moving
external API client development out of the PRISM codebase and into this
staging repo, mirroring the `GS/viz/altair/` and `GS/viz/echarts/`
plug-and-play model.

Anyone (Cursor or human) opening a fresh session in this series should
read this file FIRST.

```
╔════════════════════════════════════════════════════════════════════════╗
║ THE ONE-SENTENCE GOAL                                                  ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║ Make GS/data/apis/<source>-payload/ a drag-and-drop unit into PRISM,   ║
║ exactly the way GS/viz/altair/altair-payload/ already is — with a      ║
║ local stub mirror that lets the byte-identical payload run here for    ║
║ development, demo, and QC, without requiring GS network / Kerberos.    ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
```

## Mission

Today, every external API client (treasury, treasurydirect, fdic, bis,
ofr, openfigi, sec_edgar, prediction_markets, ...) lives in two places
that are out of sync:

```
PRISM side                            staging side (this repo)
ai_development/mcp/clients/           GS/data/apis/<source>/
    treasury_client.py                    treasury.py
    treasury_direct_client.py             ...
    bis_client.py
    fdic_client.py
    ...                               GS/data/apis/<source>/SKILL.md
                                          (analogous to the L2 markdown
ai_development/mcp/                        modules PRISM consumes)
    gs_app_proxy_negotiate.py
                                      No connection to gs_app_proxy_negotiate
ai_development/context/modules/        — staging clients use vanilla
    static/data_guides/<src>_guide.md   `requests` directly because we
    static/instruments/treasury_api.md   don't have GS auth here.
    static/tools/<src>_guide.md
```

The staging-side files are useful for offline experimentation but they
will never run inside PRISM as-is — they bypass the proxy/Kerberos
layer entirely. So work done here doesn't move PRISM forward, and work
done in PRISM is hard to develop / test (no browser, no IDE vision, no
demo harness, no fast iteration).

The fix is the viz pattern: build the PRISM-bound files HERE, ship them
unchanged, with a local stub mirror that makes them runnable in this
repo. The two sides become identical files in two folders, plus a thin
local infrastructure layer that doesn't ship.

## The drag-and-drop contract (target end-state)

Mirrors `.cursor/rules/viz-platforms.mdc` exactly:

```
┌────────────────────────────────────────────────────────────────────┐
│ Source (this repo)                          PRISM destination       │
├────────────────────────────────────────────────────────────────────┤
│ GS/data/apis/<src>/<src>-payload/<src>_client.py                    │
│                              ──────►   ai_development/mcp/clients/  │
│                                                                     │
│ GS/data/apis/<src>/<src>-payload/<src>_guide.md                     │
│                              ──────►   context/modules/static/      │
│                                          data_guides/ (or           │
│                                          instruments/ or tools/)    │
│                                                                     │
│ + a one-time PRISM-side wiring change to register the new module    │
│   in registry.py (one line per source)                              │
└────────────────────────────────────────────────────────────────────┘

Staging-only (never ships):

  GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py
                          stub mirror — same signatures as PRISM,
                          but bodies that fall through to vanilla
                          `requests` so payload runs locally

  GS/data/apis/ai_development/mcp/clients/__init__.py
                          (if PRISM has a non-trivial export hub)

  GS/data/apis/dev/
                          demo harness, sys.path patching, smoke
                          tests — analogous to GS/viz/altair/dev/
```

The two-sided invariant from viz-platforms.mdc applies verbatim:

1. Payload files are byte-identical between staging and PRISM. Once
   installed in PRISM, never edited there.
2. The staging repo carries whatever local infrastructure is needed
   to make those exact same files runnable here. That infrastructure
   is staging-only and never ships.

## File references (anchors for any session in this series)

```
The OCR scan that started this endeavor
├── papers/converted/Scan May 1, 2026 at 9.33 PM.md   (~3970 lines)
│   ├── §1 (lines 1-750)    treasury_api.md content (current PRISM L2
│   │                       module — already deployed)
│   ├── §2 (lines 750-1130) gs_app_proxy_negotiate.py FULL SOURCE
│   ├── §3 (1130-2050)      Walkthrough: 2 transport patterns +
│   │                       per-client analysis
│   ├── §4 (2050-3550)      Deep-dive companion: Kerberos, SSL, chunked,
│   │                       errors, pooling, timeouts, rate limits,
│   │                       diagnostics, recipes, anti-patterns
│   └── §5 (3550-3970)      Client architecture: 17 clients, 3-layer
│                           pipeline, registry mapping, sandbox
│                           injection

The plug-and-play SSOT (read this rule before doing payload work)
├── .cursor/rules/viz-platforms.mdc
│   ├── two-sided contract
│   ├── stub-mirror parity invariant
│   ├── what NOT to do
│   └── intentional asymmetries

The orientation rule (always-on)
├── .cursor/rules/prism.mdc
│   ├── repo purpose, prism/ catalog
│   └── design principles

PRISM SSOT (curated; the place new docs land in Session 1)
├── prism/
│   ├── README.md            (catalog, routing, curation policy)
│   ├── architecture.md      (will get a new §11 in Session 1)
│   ├── code-sandbox.md      (will get client-injection note)
│   ├── codebase-tree.md     (will get mcp/clients/ + mcp/g_a_p_n.py)
│   ├── data-functions.md    (will get a §0 disclaimer)
│   ├── mcp-tools.md         (no change expected)
│   ├── mcp-utils.md         (no change expected)
│   ├── _changelog.md        (one entry per session)
│   ├── _prompting-guide.md  (PRISM-side primer, kept in sync)
│   └── archive/             (raw inputs that informed curation)
│
│ NEW in Session 1:
│   ├── gs-proxy.md          (the GS outbound HTTP transport layer)
│   ├── api-clients.md       (the external API client layer)
│   └── _reference/
│       └── gs_app_proxy_negotiate.py   (reconstructed PRISM-side
│                              source as documentary reference;
│                              real Kerberos imports kept as written)

Staging-side current state (the messy parallel — to be unified)
├── GS/data/apis/
│   ├── README.md             (24-source inventory + status table)
│   ├── treasury/
│   │   ├── treasury.py       (~1480 lines, vanilla requests)
│   │   └── SKILL.md
│   ├── treasurydirect/
│   │   ├── treasurydirect.py (~1316 lines, vanilla requests)
│   │   └── SKILL.md
│   ├── fdic/
│   │   ├── fdic.py
│   │   └── SKILL.md
│   ├── bis/
│   │   ├── bis.py
│   │   └── SKILL.md
│   └── ... (20 more)

Cross-session meta artifacts (this folder)
├── staging/
│   ├── apis_endeavor.md     (THIS FILE — multi-session plan + status)
│   └── prompts.md           (active context-extraction prompt to PRISM)
```

## Why a multi-session split

This work has natural seams. Treating it as one mega-session would
collapse them and lose the chance to course-correct between phases.
The seams are:

```
        Knowledge     ──►  Design     ──►  Build         ──►  Generalize
       (prism/ SSOT)       (decisions)     (one source)         (all sources)

Session  1   2              3                4    5    6        7    8
         │   │              │                │    │    │        │    │
         │   │              │                │    │    │        │    └─ migration
         │   │              │                │    │    │        │
         │   │              │                │    │    │        └──── codify rule
         │   │              │                │    │    │
         │   │              │                │    │    └────── treasurydirect
         │   │              │                │    │              (manual_connect)
         │   │              │                │    └────────── treasury
         │   │              │                │                  (requests_proxy)
         │   │              │                └─────────────── stub mirror + harness
         │   │              │
         │   │              └────────────── apis/ layout decisions
         │   │
         │   └─────────────── PRISM round-trip to resolve gaps
         │
         └───────────────── prism/ uplift (no info loss from OCR)
```

## Session-by-session plan

Each session has: **motivation**, **deliverables**, **acceptance**,
**what carries forward**.

---

### Session 1 — prism/ uplift (this session)

```
Motivation
  The OCR scan introduced two architectural domains prism/ doesn't
  document: the GS outbound transport layer (gs_app_proxy_negotiate.py)
  and the external API client layer (mcp/clients/* + registry mapping).
  Without these documented, every later session will re-derive PRISM's
  shape and get drift.

Deliverables
  □ prism/gs-proxy.md (NEW)
      - Reconstructed source of gs_app_proxy_negotiate.py
      - Per-section behaviour: SPNEGO, KerberosProxyAuthAdapter,
        session_and_auth, manual_https_request
      - Per-host transport policy table (what exists today)
      - Why TreasuryDirect/BIS need manual CONNECT
      - Edge cases (KRB5CCNAME bootstrap, SSL/SNI/certifi, chunked
        encoding SEC quirk)
      - Forward-direction-of-travel (request_json abstraction) clearly
        labelled PROPOSAL not current state
  □ prism/api-clients.md (NEW)
      - 17-client inventory
      - 3-layer architecture (client / injection / skill)
      - Sandbox injection in script_exec_tools.py
      - Registry entry shape + fdic_guide example verbatim
      - Client → registry key → skill module file map
      - End-to-end query flow example
      - Per-client transport mode (cross-ref gs-proxy.md §5)
  □ prism/_reference/gs_app_proxy_negotiate.py (NEW)
      - Clean reconstruction of the PRISM-side source as a literal
        .py file for documentary reference
      - Real Kerberos imports preserved (not the local stub)
      - This is the "what PRISM has" file. The local stub mirror
        with vanilla-requests bodies comes in Session 4.
  □ prism/architecture.md (UPDATE)
      - Add §11 "External API client layer" (orientation only,
        delegates to gs-proxy.md + api-clients.md)
      - Update §4 (Code execution sandbox) to note clients are
        auto-injected
  □ prism/code-sandbox.md (UPDATE)
      - §2.x add auto-injected client module names list
  □ prism/codebase-tree.md (UPDATE)
      - Add mcp/clients/, mcp/gs_app_proxy_negotiate.py,
        context/modules/static/{data_guides,instruments,tools}/
  □ prism/data-functions.md (UPDATE)
      - Add §0 disclaimer about three retrieval mechanisms
  □ prism/README.md (UPDATE)
      - Catalog gets gs-proxy.md + api-clients.md
      - Routing table gets ~6 new entries
  □ prism/_changelog.md (UPDATE)
      - One entry for Session 1
      - Open-items table (F-numbers) for every WARN sentinel left
        for Session 2 to resolve
  □ .cursor/rules/prism.mdc (LIGHT UPDATE)
      - Quote the viz-platforms drag-and-drop contract as the
        canonical pattern
      - Signal that GS/data/apis/ is the next domain
      - Do NOT write a new rule yet
  □ staging/apis_endeavor.md (this file — committed first)

Acceptance
  - Every fact in new docs has _as of 2026-05-01; sources: scan
    2026-05-01 21:33 (line N-M)_ stamp
  - Every uncertainty is flagged as WARN unverified with an
    F-number for Session 2 to pick up
  - The OCR scan stays where it is — papers/converted/. We do NOT
    move it to prism/archive/ unless explicitly asked.
  - Forward-looking proposals (request_json, TransportResponse,
    rate limiter) are clearly separated from current PRISM state

Carries forward
  - List of WARN sentinels → Session 2's context-extraction prompt
  - Reconstructed gs_app_proxy_negotiate.py → Session 4's stub
    mirror starting point
```

---

### Session 2 — Resolve gaps via PRISM round-trip

```
Motivation
  Session 1 will inevitably leave gaps. Resolve them in one
  consolidated PRISM context-extraction round-trip rather than
  letting fabrication creep in during Sessions 3-7.

Deliverables
  □ staging/prompts.md (REPLACE/APPEND)
      - One context-extraction prompt covering every WARN sentinel
        from Session 1's _changelog open-items table
      - Likely sections:
        * Verbatim mcp/clients/__init__.py
        * Verbatim script_exec_tools.py client-injection block
        * _USE_GS_PROXY mechanism
        * Full registry entries for every client-mapped module
        * FiscalDataError + sibling exception classes
        * Any mcp/utils/ shared client helpers
        * KRB5CCNAME inheritance through script_exec_tools
  □ User pastes prompt into PRISM, returns reply (likely as a new
    OCR scan in papers/converted/ or pasted directly into chat)
  □ prism/* updates folding the reply in-place, removing all WARN
    sentinels addressed
  □ prism/_changelog.md updated with Session 2 entry +
    F-number resolutions

Acceptance
  - Zero WARN sentinels remaining in prism/gs-proxy.md and
    prism/api-clients.md
  - prism/_reference/gs_app_proxy_negotiate.py is verified
    byte-faithful to PRISM's actual source (caveat: minor
    OCR-noise corrections are fine; structural changes are not)

Carries forward
  - prism/ now stable enough that Sessions 3-7 can rely on it
  - Any new gaps surfaced during the round-trip get re-queued
```

---

### Session 3 — apis/ layout design

```
Motivation
  Before writing code, decide the directory shape, the stub-mirror
  location, the demo harness shape, and the rule structure. Doing
  this implicitly during Session 4 leads to thrashing.

Deliverables
  □ Decisions documented in this file (apis_endeavor.md):
      * Per-source <source>-payload/ folder (mirroring
        altair-payload/) vs flat layout
      * Stub mirror at GS/data/apis/ai_development/ vs
        GS/data/apis/_shared/ai_development/
      * Where the dev harness lives (GS/data/apis/dev/ vs
        per-source GS/data/apis/<src>/dev/)
      * Whether SKILL.md becomes <src>_guide.md (matching PRISM's
        actual filename) or stays SKILL.md (with a wiring step
        that renames-on-copy)
      * Naming: treasury_client.py vs treasury.py for the payload
        file (PRISM uses *_client.py)
  □ Empty directory scaffolding committed for the chosen layout
    (with .gitkeep or trivial README) so Session 4 has a clear
    landing zone
  □ Updated GS/data/apis/README.md with a "Future layout" section
    foreshadowing the migration

Acceptance
  - Decisions are written down with rationale, not just made
  - Layout is consistent with viz-platforms.mdc patterns where
    possible (cite specific viz precedents)
  - User has signed off on the layout before Session 4 starts

Carries forward
  - Concrete paths for Session 4 to write into
```

---

### Session 4 — Stub mirror + dev harness

```
Motivation
  Build the local infrastructure layer — the analog of
  GS/viz/altair/ai_development/ — so the same payload files run
  here without a GS network connection. This is the load-bearing
  staging-only piece.

Deliverables
  □ GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py
      - Same public surface as PRISM (get_spnego_token,
        KerberosProxyAuthAdapter, session_and_auth,
        manual_https_request)
      - Bodies that fall through to vanilla requests:
        * session_and_auth() returns (requests.Session(), None)
        * manual_https_request() does requests.request() under the
          hood and returns (parsed_json, status_string) in the same
          shape as PRISM's tunnel return
      - Stricter signatures than PRISM where possible (per the viz
        stub-mirror parity invariant — strict stubs fail loud)
  □ GS/data/apis/ai_development/mcp/clients/__init__.py (if PRISM
    has a non-trivial one)
  □ GS/data/apis/ai_development/mcp/utils/* (if Session 2 surfaces
    shared helpers used by the clients)
  □ GS/data/apis/dev/_harness.py with sys.path setup, mirroring
    GS/viz/altair/dev/demos/_harness.py
  □ 1-2 trivial smoke demos that just import the stub and call
    session_and_auth() / manual_https_request() to confirm the
    stub works end-to-end
  □ GS/data/apis/dev/notes.md scaffolded (tracking open items,
    known gotchas — analog to GS/viz/altair/dev/notes.md)

Acceptance
  - Smoke demos pass without GS network
  - Signatures are byte-identical to what
    prism/_reference/gs_app_proxy_negotiate.py declares
  - Stub fails loud, not silent, on signature drift (raise
    TypeError on unknown kwargs etc.)

Carries forward
  - Working stub mirror that Sessions 5+ write payload code against
```

---

### Session 5 — Reference rebuild #1: treasury (Fiscal Data API)

```
Motivation
  Treasury Fiscal Data is the simpler transport case
  (requests_proxy / standard requests path). Rebuilding it first
  proves the payload model with the easier transport so Session 6
  only has to validate the harder one (manual CONNECT).

Why treasury first (vs treasurydirect)
  - Standard requests_proxy is the default path — proving it works
    end-to-end establishes the baseline
  - PRISM-side treasury_client.py is well-understood from the OCR
    scan §1 (treasury_api.md is its sibling L2 module, deployed)
  - The 80+ endpoint registry already exists in
    GS/data/apis/treasury/treasury.py — we can reuse the catalog,
    we just rewrite the request-layer

Deliverables
  □ GS/data/apis/treasury/treasury-payload/treasury_client.py
      - PRISM-style: imports from ai_development.mcp.gs_app_proxy
        _negotiate (which resolves to the local stub here, to the
        real module in PRISM)
      - Module-level _SESSION cache (per the OCR scan's
        recommendation; see prism/api-clients.md §X for the
        "preserve session caching" guidance)
      - Same public surface as the existing PRISM treasury_client
        (get_endpoint, query, get_debt_to_penny, get_avg_interest
        _rates, ...)
      - FiscalDataError preserved
  □ GS/data/apis/treasury/treasury-payload/treasury_api.md
      - The PRISM-bound L2 module (the same content the OCR scan
        §1 documented as currently deployed in PRISM)
      - Light freshness pass — fix any OCR scrambles, dated
        2026-05-01
  □ Demo gallery: GS/data/apis/treasury/dev/demos/01_*.py through
    several scenarios (debt-to-penny pull, MSPD table 5, MTS
    table, FX reporting rates) — all running through the stub
    mirror
  □ Existing GS/data/apis/treasury/treasury.py and SKILL.md moved
    to GS/data/apis/treasury/dev/archive/_pre_payload/ (NEVER
    delete per user rule)

Acceptance
  - All demos pass against the stub mirror with no GS network
  - The same treasury_client.py file would (in principle) work
    inside PRISM — verified by inspecting the stub-vs-PRISM
    signature parity in prism/_reference/
  - SKILL.md → treasury_api.md rename is documented in the
    apis_endeavor.md decisions section

Carries forward
  - Established pattern other clients copy from
  - First "this would drag-and-drop into PRISM today" payload
```

---

### Session 6 — Reference rebuild #2: treasurydirect (manual CONNECT)

```
Motivation
  TreasuryDirect is the canonical example of the manual_https_
  request path (target rejects auth headers; CONNECT tunnel keeps
  target request clean). Rebuilding it validates that the stub
  mirror handles BOTH transport patterns.

Deliverables
  □ GS/data/apis/treasurydirect/treasurydirect-payload/
    treasury_direct_client.py
      - Imports manual_https_request from ai_development.mcp.gs
        _app_proxy_negotiate
      - Same public surface as PRISM's treasury_direct_client
        (TreasuryDirectScraper class, _fetch / _fetch_json,
        scrape_refunding_latest, fetch_auction_schedule_xml, ...)
      - MockResponse pattern preserved (or normalized response
        wrapper if Session 4 introduced one in the stub)
  □ Demo gallery: GS/data/apis/treasurydirect/dev/demos/*.py
      - Announced auctions
      - Auction results
      - CUSIP lookup
      - Quarterly refunding scrape
  □ Existing GS/data/apis/treasurydirect/treasurydirect.py and
    SKILL.md archived to dev/archive/_pre_payload/
  □ The treasury_api.md module (already covering both Fiscal Data
    AND TreasuryDirect) updated to reflect that both clients are
    now staging-owned

Acceptance
  - Both transport patterns proven against the local stub
  - manual_https_request stub correctly returns the
    (parsed_data, status_string) tuple in the same shape as PRISM

Carries forward
  - Two reference rebuilds = enough pattern to codify
```

---

### Session 7 — Codify the pattern as .cursor/rules/api-clients.mdc

```
Motivation
  Sessions 5-6 will surface the actual conventions (file naming,
  import shape, rename-on-copy step, demo harness shape, what's
  drag-and-drop vs staging-only). Codify them as a rule so future
  agents follow the pattern automatically.

Deliverables
  □ .cursor/rules/api-clients.mdc, parallel to viz-platforms.mdc:
      * The drag-and-drop contract for apis/
      * Stub-mirror parity invariant (with the gs_app_proxy
        _negotiate stub as the worked example)
      * What NOT to do
      * Intentional asymmetries vs the viz pattern (if any)
      * Globs: GS/data/apis/**
  □ GS/data/apis/README.md updated:
      * Status table now reflects payload model
      * "How to add a new API" section pointing at the rule
  □ Any prism/* drift surfaced during builds folded back in
  □ prism/_changelog.md entry

Acceptance
  - The rule is detailed enough that a fresh Cursor session can
    add a new API client without re-deriving the pattern
  - viz-platforms.mdc and api-clients.mdc don't contradict each
    other; differences are intentional and documented

Carries forward
  - Self-serve rule for Sessions 8+ migration work
```

---

### Session 8 — Migration playbook + first batch

```
Motivation
  17 clients exist on PRISM side, ~24 sources exist on staging
  side. Treasury + TreasuryDirect = 2 done. Need a systematic way
  to convert the remaining ones.

Deliverables
  □ Migration priority list (in this file), ranked by:
      * Strategic value (FDIC, BIS, OFR, openfigi, sec_edgar,
        prediction_markets are likely top tier)
      * Transport difficulty (standard requests_proxy = easier)
      * Existing PRISM-side maturity
  □ Per-API checklist (template):
      [ ] Read PRISM-side <src>_client.py via list_ai_repo
          (delegate to PRISM round-trip if needed)
      [ ] Build <src>-payload/<src>_client.py
      [ ] Build <src>-payload/<src>_guide.md (or _api.md)
      [ ] 3-5 demos in dev/demos/
      [ ] Archive existing <src>/<src>.py + SKILL.md
      [ ] Verify stub-mirror parity
      [ ] Update GS/data/apis/README.md status table
  □ Execute the checklist for the next 1-3 highest-priority APIs
    as a "rep" to validate the playbook

Acceptance
  - Playbook is concrete enough that subsequent sessions
    (Session 9+) are largely mechanical
  - Each migrated API has the same shape as treasury and
    treasurydirect

Carries forward
  - The migration becomes a repeatable per-source operation that
    no longer requires this multi-session planning artifact
```

---

## Status tracker

Update this table at the END of each session. Use `[ ]`, `[~]`
(in progress), `[x]` (complete), `[!]` (blocked).

```
Session  Status   Date         Notes
───────  ──────   ──────       ───────────────────────────────────────
   1     [x]      2026-05-01   prism/ uplift complete:
                                - prism/gs-proxy.md (NEW)
                                - prism/api-clients.md (NEW)
                                - prism/_reference/gs_app_proxy_negotiate.py (NEW;
                                  AST-clean reconstruction; F8/F9/F10 flagged)
                                - architecture.md / code-sandbox.md /
                                  codebase-tree.md / data-functions.md /
                                  README.md cross-references folded in
                                - _changelog.md entry + 11 F-numbers logged
                                  (F8-F18) for Session 2 to resolve
                                - .cursor/rules/prism.mdc light update
                                  framing the drag-and-drop contract as
                                  canonical and signalling apis/ is next
   2     [~]      2026-05-01   Prompt drafted at staging/prompts.md.
                                Old "list_ai_repo spoke fetching" prompt
                                moved to staging/prompts_archive/ before
                                overwrite. The new prompt has 12 sections
                                resolving F7-F18 in one consolidated
                                round-trip:
                                  §1  full gs_app_proxy_negotiate.py
                                      (resolves F8/F9/F10 + verifies the
                                      reconstructed _reference/ copy)
                                  §2  full mcp/clients/__init__.py (F14)
                                  §3  script_exec_tools.py client-injection
                                      block + 7-client gap explanation +
                                      KRB5CCNAME inheritance (F15)
                                  §4  _USE_GS_PROXY mechanism per client (F11)
                                  §5  per-client transport choice for the
                                      11 unverified clients (F12)
                                  §6  per-client public-method inventory
                                      (F13)
                                  §7  full MODULE_REGISTRY entries for
                                      every client-mapped module (F16/F17/F18)
                                  §8  sibling exception classes per client
                                      (extension to F13)
                                  §9  shared mcp/utils/ helpers across
                                      clients (extension)
                                  §10 KRB5CCNAME / sandbox process behaviour
                                  §11 verbatim list_ai_repo def from
                                      developer_tools.py (carry-over F7)
                                  §12 sanity / coverage (any missing
                                      clients, any superseding transport
                                      module)
                                AWAITING: user pastes into PRISM, returns
                                reply. Then fold into prism/* and clear
                                sentinels.
   3     [ ]
   4     [ ]
   5     [ ]
   6     [ ]
   7     [ ]
   8     [ ]
```

## Open decisions (TBD as work progresses)

```
ID    Decision                                           Decided in
───   ─────────────────────────────────────────────────  ───────────
D1    prism/_reference/gs_app_proxy_negotiate.py = the   Session 1
      "what PRISM has" reference (real Kerberos imports     (yes)
      preserved); SEPARATE local stub at
      apis/ai_development/ comes in Session 4 with
      vanilla-requests bodies
D2    OCR cleanup is aggressive: clean up null/true/      Session 1
      false → None/True/False, fix indentation,             (yes)
      reconstruct broken code blocks
D3    Cadence: work straight through, show user each       Session 1
      file as it's written, no preview-then-fill              (yes)
      pattern
D4    apis/ layout: per-source <source>-payload/ folder  Session 3
      vs flat (likely per-source by analogy with viz)
D5    Stub mirror location: GS/data/apis/ai_development  Session 3
      /mcp/ vs GS/data/apis/_shared/ai_development/mcp/
D6    Demo harness location: GS/data/apis/dev/ vs        Session 3
      per-source GS/data/apis/<src>/dev/
D7    SKILL.md rename: leave as SKILL.md (rename on      Session 3
      copy) vs <src>_guide.md / <src>_api.md (matching
      PRISM's actual filenames)
D8    Where existing <src>/<src>.py + SKILL.md go        Session 3
      after migration: dev/archive/_pre_payload/ (per
      user "no delete" rule)
```

## Hard rules carried across sessions

- **Never delete files** (user rule). Move to archive/ instead.
  Temporary test scripts are the only exception.
- **Never invent PRISM facts** (prism/ curation policy). If a fact
  isn't in prism/ or in a verified source, generate a context-
  extraction prompt instead.
- **Never write summary markdowns** of completed work (user rule).
  Update apis_endeavor.md status tracker only.
- **No emojis** (user rule).
- **Interactive CLI for any new script** (user rule). Running
  without arguments must launch a menu; full argparse mode must
  also exist.
- **Plug-and-play invariant**: payload files are byte-identical
  between staging and PRISM. The stub mirror is the only place
  staging diverges from PRISM, and only in the body, never the
  signature.
