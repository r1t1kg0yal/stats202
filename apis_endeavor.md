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

### Session 3 — apis/ layout scaffolding

```
Motivation
  All design decisions (D4-D12) locked in this session before the
  handoff. Session 3 itself is the SCAFFOLDING work — turning the
  decisions into actual on-disk structure that Session 4 can fill in.

Deliverables
  □ Empty directory scaffolding for the locked layout:
      GS/data/apis/ai_development/mcp/   (D5 — for stub mirror;
                                          empty .py file with TODO
                                          stub or placeholder)
      GS/data/apis/dev/                  (D6 — for shared harness;
                                          stub _harness.py with
                                          sys.path setup)
      GS/data/apis/<src>/                (existing — keep)
      GS/data/apis/<src>/<src>-payload/  (D4 — empty per source,
                                          .gitkeep or README)
      GS/data/apis/<src>/dev/            (D6 — empty per source)
      GS/data/apis/<src>/dev/archive/_pre_payload/
                                         (D8 — for archived files)

  □ Initial sys.path setup written into GS/data/apis/dev/_harness.py
    so demos can resolve both `ai_development.mcp.gs_app_proxy
    _negotiate` (the stub mirror) and `<src>` (whatever client they
    're testing).

  □ Updated GS/data/apis/README.md with a "Payload model (in
    flight)" section pointing at staging/apis_endeavor.md and
    sketching the per-source folder structure.

  □ A scaffolding-only commit. NO actual stub mirror code (Session
    4) and NO actual client rebuilds (Session 5+).

Acceptance
  - Every directory in D4/D5/D6/D8 exists on disk with at least a
    .gitkeep / README so it survives git operations
  - GS/data/apis/dev/_harness.py imports cleanly (even if the stub
    mirror file is empty — Session 4 fills it in)
  - Existing GS/data/apis/<src>/<src>.py + SKILL.md files remain
    untouched (Session 5/6 archives them as part of the per-source
    rebuild)

Carries forward
  - Skeleton on disk that Session 4 writes the stub mirror into
  - Clear per-source landing zones for Sessions 5+
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
   2     [x]      2026-05-01   PRISM round-trip complete. Reply at
                                papers/converted/Scan May 1, 2026 at
                                10.45 PM.md (417 lines). Folded into:
                                  - prism/_reference/g_a_p_n.py
                                    (F8/F9/F10 cleared)
                                  - prism/gs-proxy.md (§3.2 sandbox-
                                    interaction; §5.3 _USE_GS_PROXY tri-
                                    modal; §7 full transport policy
                                    rewrite for all 17 clients including
                                    the §7.3 "direct" group; §11 cleared
                                    + F19/F20 opened)
                                  - prism/api-clients.md (§4 full
                                    rewrite covering init.py membership,
                                    sandbox injection, pull_nyfed_data
                                    function-injection exception, 4
                                    clients absent from __init__.py, 7
                                    clients not injected; §6 unmapped
                                    clients confirmed; §7 bundles
                                    confirmed standalone vs bundled;
                                    §10 _USE_GS_PROXY tri-modal; §11
                                    cleared + F19/F20/F21 opened)
                                  - prism/code-sandbox.md (§2.5 +
                                    §2.14 cleanup; pull_nyfed_data
                                    note)
                                  - prism/codebase-tree.md (§3.4
                                    expanded with mcp/ top-level files
                                    inc. config.py)
                                  - prism/_changelog.md (Session 2
                                    entry; F8/F9/F10/F11/F12/F14/F15/
                                    F16/F17/F18 RESOLVED; F7/F13
                                    PARTIAL; F19/F20/F21 NEW; C38-C42
                                    contradictions resolved)
                                Active prompt at staging/prompts.md was
                                copied to staging/prompts_archive/
                                2026-05-01_apis_endeavor_session_2.md
                                with frontmatter; staging/prompts.md
                                now reset to "no active prompt"
                                holding-pattern note.
   3     [ ]      —            READY TO START in fresh Cursor session.
                                Handoff prompt at:
                                  staging/handoffs/session_3.md
                                All design decisions (D4-D12) locked
                                this session. Session 3 deliverable
                                is now SCAFFOLDING (directory tree +
                                stub _harness.py + README touch-up),
                                not design. See "Lessons from
                                Sessions 1+2" below for the
                                load-bearing context the next session
                                inherits.
   4     [ ]
   5     [ ]
   6     [ ]
   7     [ ]
   8     [ ]
```

## Lessons from Sessions 1+2 (carry into Session 3+)

These are the structural findings that materially change the
plug-and-play model from what we sketched in Session 1. Read these
BEFORE starting Session 3 design — they reshape some defaults.

### L1. PRISM's clients fall into three transport buckets, not two

Original assumption: every client uses `gs_app_proxy_negotiate.py`
via either `session_and_auth()` or `manual_https_request()`.

Actual finding (Session 2):

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Bucket A — STANDARD requests + Kerberos proxy adapter                   │
│   session_and_auth()                                                    │
│   Clients: fdic, treasury, fred, newyorkfed, wikipedia (try/fallback),  │
│            prediction_markets (Kalshi + Gamma)                          │
│   = 6 clients                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Bucket B — MANUAL CONNECT tunnel                                        │
│   manual_https_request()                                                │
│   Clients: bis, treasury_direct, sec_edgar, ofr, substack (with direct  │
│            fallback), prediction_markets (CLOB + Data)                  │
│   = 5 clients                                                           │
├─────────────────────────────────────────────────────────────────────────┤
│ Bucket C — DIRECT requests (no GS proxy at all)                         │
│   plain requests.Session()                                              │
│   Clients: cftc, congress, federal_register, usitc, ofac, openfigi      │
│   = 6 clients                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                                     +
                          newyorkfed_client (special — see L4)
```

Implication for Session 3+:

- **Bucket A and B** clients NEED the staging stub mirror for
  `gs_app_proxy_negotiate.py` to run locally. The stub's bodies are
  vanilla `requests`; the public signature matches PRISM. (Session 4.)

- **Bucket C** clients DO NOT NEED the stub mirror at all. They
  already use vanilla `requests`. The staging payload model for these
  six is the SIMPLEST possible — copy the file across, no transport
  dependency to mock. They can be migrated FIRST or LAST; either
  works.

- This means Session 4's stub mirror only has to support 11 clients,
  not 17. The remaining 6 are zero-effort migrations.

### L2. `_USE_GS_PROXY` is tri-modal, but irrelevant for staging

Three patterns coexist in PRISM:
- Hardcoded `True` (fdic_client)
- Import-availability driven (bis_client, substack_client)
- No flag at all (treasury_client)

Implication for Session 3+:

The staging stub mirror's `session_and_auth()` and
`manual_https_request()` simply fall through to vanilla `requests`.
This works for ALL three patterns transparently:

```
fdic_client (_USE_GS_PROXY = True)
  → session_and_auth() called
  → stub mirror returns (requests.Session(), None)
  → session.get(url, auth=None, timeout=30) works fine

bis_client (_USE_GS_PROXY = True if import succeeds)
  → import succeeds (stub mirror exists)
  → manual_https_request(...) called
  → stub mirror does requests.request(method, f"https://{host}{path}", ...)
    and wraps in (parsed_data, "HTTP/1.1 200 ") shape
  → works

treasury_client (no flag)
  → session_and_auth() called directly
  → same as fdic
```

No client code change required. The stub mirror is the entire
abstraction.

### L3. `mcp/clients/__init__.py` membership ≠ sandbox injection membership

Two separate gates:

| Surface | What it is | Membership |
|---------|------------|-----------|
| `mcp/clients/__init__.py` `__all__` | Package-level export list | 13 modules; ofac commented out; ofr/usitc/wikipedia absent |
| `script_exec_tools.py` injection | Sandbox-namespace exposure | 10 modules; pull_nyfed_data injected as a function |

Implication for Session 3+:

- The PRISM-bound payload includes the client `*_client.py` file. It
  does NOT include the changes to `__init__.py` or
  `script_exec_tools.py` — those are PRISM-side wiring done by the
  user when the payload lands.

- The user's "wiring step" when copying a payload into PRISM is
  therefore three lines (potentially):
  1. Add `from . import <new>_client` to `mcp/clients/__init__.py`
  2. Add `<new>_client as _<new>_client` to the
     `script_exec_tools.py` import block
  3. Add `"<new>_client": _<new>_client,` to the namespace dict
     literal

- The wiring step is documented in
  `.cursor/rules/api-clients.mdc` (Session 7) as part of the
  drag-and-drop contract.

### L4. `newyorkfed_client` is the function-injection exception

The newyorkfed client is NOT exposed as a module in the sandbox.
Only `pull_nyfed_data` (one specific function) is injected,
alongside `pull_haver_data` etc. in the data-retrieval block.

Implication for Session 3+:

- For most rebuilds, `<src>-payload/<src>_client.py` is the unit. For
  `newyorkfed`, the payload still ships `newyorkfed_client.py` (the
  full module), but the injection wiring is one-function only.

- This is a precedent worth keeping in mind for any future client
  whose primary surface is "one main pull function" rather than
  "many discoverable methods" — the function-injection pattern is
  the right shape for those.

### L5. PRISM declines verbatim source pastes

Operational constraint, not a bug.

Implication for Session 3+:

- The `prism/_reference/gs_app_proxy_negotiate.py` reconstruction is
  structurally verified (decorators, nesting, f-strings, dead-import
  status) but NOT byte-for-byte. For the staging stub mirror, this
  is sufficient — signatures and semantics are what matter, not
  byte-fidelity.

- For per-client public-method inventories (F21), the working model
  is: each Session 5+ rebuild authors its SKILL.md as the
  per-client surface-of-record, sourced from the client's actual
  exports as we work through it. We do NOT need PRISM to dump
  signature inventories.

- If a future ambiguity REQUIRES verbatim PRISM source, the user
  can run `list_ai_repo` themselves in a PRISM session and paste
  the raw output back as a scan. (Same pattern as the original
  reconstruction inputs.)

### L6. `mcp/utils/` has no shared cross-client helper layer

No `request_json` wrapper, no shared pagination helper, no shared
retry decorator, no shared rate limiter. Every client is bespoke.
The only repeated multi-client import is
`ai_development.mcp.gs_app_proxy_negotiate` itself.

Implication for Session 3+:

- The staging stub mirror at
  `GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py` is the
  ONLY transport file we need to mock. There is no `mcp/utils/`
  helper to also stub.

- If the staging-side rebuilds find themselves wanting a shared
  helper (e.g. all clients would benefit from a unified
  `request_json` wrapper per the §10 proposals in `gs-proxy.md`),
  that work is a SEPARATE PRISM-side proposal — it doesn't belong
  in the staging stub mirror, which by the parity invariant must
  match PRISM, not extend it.

### L7. Six clients are L2-orphaned (no skill module at all)

`cftc_client`, `congress`, `federal_register_client`,
`usitc_client`, `wikipedia_client`, `ofac_client` have no
`MODULE_REGISTRY` entry. The LLM has no L2 guide for them and (in
4 of 6 cases) doesn't even have them in the sandbox namespace.

Implication for Session 3+:

- These six clients are EFFECTIVELY DEAD from PRISM's perspective.
  The migration priority for them should be LOW, but the migration
  itself is TRIVIAL (Bucket C — direct, no transport stub
  dependency).

- A staging payload rebuild for any of them is incomplete WITHOUT a
  matching `<src>_guide.md` skill module. We should write the
  skill module FIRST (since "context over code" is the design
  principle), and then either include the wiring step in the
  payload or let the user add it manually.

---

## Locked decisions (carried into Session 3+)

All decisions D1-D10 are now locked. D1-D3 came from Session 1; D4-D10
were decided 2026-05-01 (post-Session 2 fold) before the Session 3
handoff was written. The Session 3 work below executes against these.

```
ID    Decision                                                Decided
───   ─────────────────────────────────────────────────────  ─────────
D1    prism/_reference/gs_app_proxy_negotiate.py = the       Session 1
      "what PRISM has" reference (real Kerberos imports
      preserved); SEPARATE local stub at GS/data/apis/
      ai_development/mcp/ comes in Session 4 with vanilla-
      requests bodies.
D2    OCR cleanup is aggressive: clean up null/true/false   Session 1
      → None/True/False, fix indentation, reconstruct
      broken code blocks.
D3    Cadence: work straight through, show user each file   Session 1
      as it's written, no preview-then-fill pattern.
D4    apis/ layout = per-source <source>-payload/ folder    Session 3
      INSIDE GS/data/apis/<source>/ (i.e.                    locked
      GS/data/apis/treasury/treasury-payload/, mirroring
      GS/viz/altair/altair-payload/). Each <src>-payload/
      is the byte-identical drag-and-drop unit.
D5    Stub mirror at:                                       Session 3
                                                            (Q1 = A)
        GS/data/apis/ai_development/mcp/
            gs_app_proxy_negotiate.py

      Mirrors PRISM's exact path. Drag-and-drop import
      line `from ai_development.mcp.gs_app_proxy_negotiate
      import session_and_auth` resolves in BOTH staging
      (via sys.path containing GS/data/apis/) and PRISM
      (native path), with no per-side branching. Single
      file (no other shared utils per L6).
D6    Demo / dev infrastructure layout:                     Session 3
                                                            (Q2 =
        GS/data/apis/dev/                  ← shared          per-source
            _harness.py                       infra          + shared
            _conftest.py (?)                                 harness)
        GS/data/apis/<src>/dev/            ← per-source
            demos/                            demos +
            output/                           ad-hoc
            notes.md
            archive/_pre_payload/

      Each <src>-payload/ folder stays clean and isolated
      so it can be selected and copy-pasted to PRISM as a
      unit. The per-source dev/ holds everything that
      doesn't ship. The shared dev/ at apis root holds
      reusable harness infra (sys.path setup, stub-mirror
      path injection) that any per-source demo can import.
      Mirrors altair (which has dev/demos/_harness.py
      shared + per-demo files).
D7    SKILL.md filename: matches PRISM's exact destination   Session 3
      filename per pillar:                                   (Q3 = A)

        data_guides pillar: <src>_guide.md
          (e.g. fdic_guide.md, bis_data_guide.md,
           nyfed_guide.md, ofr_guide.md, substack_guide.md,
           prediction_markets_skill.md, fred_guide.md)
        instruments pillar: <src>_api.md
          (e.g. treasury_api.md)
        tools pillar:       <src>_guide.md
          (e.g. openfigi_guide.md, sec_edgar_guide.md)

      Drag-and-drop is byte-identical including filename;
      wiring step is just placing the file at the right
      static/{pillar}/ path. Universal SKILL.md is dropped
      to remove the rename step.

      During migration, existing GS/data/apis/<src>/SKILL.md
      gets archived to GS/data/apis/<src>/dev/archive/
      _pre_payload/SKILL.md (per D8).
D8    Existing <src>/<src>.py + SKILL.md migrate to:        Session 3
                                                            (Q4 = A)
        GS/data/apis/<src>/dev/archive/_pre_payload/
            <src>.py
            SKILL.md
            (anything else that lived in <src>/ and is
             not part of the new payload)

      Per-source archive (mirrors viz). Keeps everything
      related to one source in one folder tree.
D9    Wiring step on PRISM side when payload lands =        Session 7
      3 lines, encoded in .cursor/rules/api-clients.mdc      (rule)
      (Session 7):
        + mcp/clients/__init__.py:
          from . import <src>_client
        + mcp/tools/script_exec_tools.py imports:
          <src>_client as _<src>_client,
        + mcp/tools/script_exec_tools.py namespace dict:
          "<src>_client": _<src>_client,
      Plus PRISM-side context/registry.py addition for
      the new <src>_guide.md (one MODULE_REGISTRY entry).
D10   Migration order:                                      Session 3
                                                            (Q7 = A)
        Session 5 = treasury (Bucket A — proves
                    session_and_auth + the simpler stub)
        Session 6 = treasurydirect (Bucket B — proves
                    manual_https_request + manual stub)
        Session 7 = .cursor/rules/api-clients.mdc rule
                    written based on what 5+6 surfaced
        Session 8 = first batch of remaining migrations
                    using the now-codified rule
                    (priority: fdic → bis → ofr → ...
                    Bucket C migrations slot in as
                    quick wins per D11)
D11   Orphaned-client policy:                                Session 3
      Six clients have NO L2 module today (cftc, congress,   (Q5 = A)
      federal_register, usitc, ofac, wikipedia). Migration
      writes a NEW <src>_guide.md per client as a net new
      contribution to PRISM. The migration is incomplete
      without it (context-over-code). Each new skill module
      goes into the right pillar (likely all data_guides
      except sec_edgar/openfigi which are tools/).

      ofac is a special case: commented out of __init__.py,
      not injected. Migration STILL ships the payload but
      flags the L2-curation question to the user (write the
      skill module anyway? or accept the retired status?).
D12   Bucket C (6 direct clients — cftc, congress,          Session 3
      federal_register, usitc, ofac, openfigi):              (Q6 = A)

      Same payload formality as Buckets A+B. Each gets
      <src>-payload/<src>_client.py and <src>-payload/
      <src>_guide.md. Same dev/ structure. Same wiring
      step. The only difference: NO stub-mirror dependency
      to test (their migrations don't exercise
      gs_app_proxy_negotiate at all). The api-clients.mdc
      rule (Session 7) will note this as "Bucket C: no
      stub-mirror smoke test required."
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
