# Handoff prompt — APIs endeavor Session 3 (scaffolding)

> Paste this whole file at the start of a fresh Cursor session to
> pick up from here.

You are taking over Session 3 of the **APIs endeavor**, a multi-
session staging-side rewrite of the `mcp/clients/*.py` files in PRISM
into a plug-and-play drag-and-drop model that mirrors the
`GS/viz/altair/altair-payload/` and `GS/viz/echarts/echarts-payload/`
patterns. Sessions 1 and 2 are complete. All design decisions are
LOCKED. Your job is the SCAFFOLDING — turning the locked decisions
into actual on-disk structure that Session 4 will fill in.

---

## 1. Read these files before doing anything

Read in this order. The total reading budget is ~3500 lines —
substantial but each file is dense and load-bearing. Do not skim.

```
ORIENTATION
  .cursor/rules/prism.mdc                       always-on; the
                                                  always-applied
                                                  workspace rule
                                                  (already in your
                                                  context)
  .cursor/rules/viz-platforms.mdc               the gold-standard
                                                  drag-and-drop
                                                  contract you are
                                                  mirroring
  prism/README.md                               prism/ catalog +
                                                  routing table

THE ENDEAVOR
  staging/apis_endeavor.md                      THE master plan.
                                                  Read in full —
                                                  especially:
                                                  - "Locked decisions"
                                                    (D1-D12)
                                                  - "Lessons from
                                                    Sessions 1+2"
                                                    (L1-L7)
                                                  - "Session 3"
                                                    deliverables /
                                                    acceptance

PRISM-SIDE TRUTH (so you understand what the staging payloads ship to)
  prism/gs-proxy.md                             the GS outbound
                                                  HTTPS transport
                                                  layer your stub
                                                  mirror replicates
                                                  (full read; this is
                                                  what Session 4
                                                  builds against)
  prism/api-clients.md                          the 17-client layer
                                                  (sandbox injection
                                                  asymmetry; pull_
                                                  nyfed_data
                                                  exception; bucket
                                                  taxonomy)
  prism/_reference/gs_app_proxy_negotiate.py    documentary
                                                  reconstruction of
                                                  PRISM's actual
                                                  source. Use as the
                                                  signature spec for
                                                  the staging stub
                                                  mirror (Session 4
                                                  uses this directly,
                                                  but you should know
                                                  it exists)

STAGING SIDE — CURRENT STATE OF GS/data/apis/
  GS/data/apis/README.md                        24-source inventory +
                                                  status table — you
                                                  will lightly edit
                                                  this to add a
                                                  "Payload model (in
                                                  flight)" section
  GS/data/apis/treasury/                        canonical Bucket A
                                                  example (will be
                                                  Session 5's first
                                                  rebuild target)
  GS/data/apis/treasurydirect/                  canonical Bucket B
                                                  example (Session 6)
  GS/data/apis/bis/                             second Bucket B
                                                  example
  GS/data/apis/cftc/                            canonical Bucket C
                                                  (direct, no proxy)
                                                  example

VIZ PRECEDENT — the pattern you are mirroring
  GS/viz/altair/                                directory tree to
                                                  imitate at the apis
                                                  level
  GS/viz/altair/ai_development/                 stub mirror layout
                                                  example
  GS/viz/altair/dev/                            shared dev infra
                                                  example
  GS/viz/altair/altair-payload/                 the byte-identical
                                                  drag-and-drop unit
                                                  example
  GS/viz/altair/dev/demos/_harness.py           sys.path setup
                                                  example you'll
                                                  pattern your apis
                                                  _harness.py off of

CONVENTIONS
  prism/_prompting-guide.md                     PRISM-side primer on
                                                  prompt classes (you
                                                  WON'T need to write
                                                  any PRISM prompts
                                                  for Session 3, but
                                                  good to know)
```

---

## 2. What was done in Sessions 1 and 2

```
┌─ SESSION 1 (prism/ uplift) ────────────────────────────────────────┐
│                                                                    │
│ Folded the OCR scan at                                             │
│   papers/converted/Scan May 1, 2026 at 9.33 PM.md                  │
│ into curated prism/ docs:                                          │
│   - prism/gs-proxy.md (NEW)                                        │
│   - prism/api-clients.md (NEW)                                     │
│   - prism/_reference/gs_app_proxy_negotiate.py (NEW;               │
│     reconstructed source, AST-clean)                               │
│   - architecture.md / code-sandbox.md / codebase-tree.md /         │
│     data-functions.md / README.md cross-references                 │
│   - .cursor/rules/prism.mdc light update                           │
│ Left F8-F18 as WARN sentinels for Session 2.                       │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ SESSION 2 (PRISM round-trip) ─────────────────────────────────────┐
│                                                                    │
│ Generated context-extraction prompt at staging/prompts.md          │
│ (now archived to staging/prompts_archive/2026-05-01_apis           │
│ _endeavor_session_2.md). User pasted into PRISM, returned reply    │
│ at papers/converted/Scan May 1, 2026 at 10.45 PM.md.               │
│                                                                    │
│ Folded reply into prism/ docs. F8-F18 mostly RESOLVED, with        │
│ three structural surprises that materially reshape the endeavor:   │
│                                                                    │
│   L1. THREE transport buckets (not two):                           │
│         A — standard requests (6 clients)                          │
│         B — manual CONNECT tunnel (5 clients)                      │
│         C — DIRECT requests, no GS proxy at all (6 clients)        │
│       Plus newyorkfed which is half-injected                       │
│       (only pull_nyfed_data exposed).                              │
│                                                                    │
│   L2. _USE_GS_PROXY is TRI-MODAL across clients (hardcoded /       │
│       import-availability / no flag at all). Stub mirror's         │
│       vanilla-requests bodies satisfy ALL three transparently.     │
│                                                                    │
│   L3. mcp/clients/__init__.py membership ≠ script_exec_tools.py    │
│       injection membership. PRISM-side wiring step on copy-in is   │
│       3 lines + 1 registry entry.                                  │
│                                                                    │
│ New open items: F19 (openfigi import discrepancy), F20 (PRISM      │
│ declined verbatim source pastes — structural verification only),   │
│ F21 (per-client signature inventories declined too).               │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ SESSION 3 PREP (this most-recent session) ────────────────────────┐
│                                                                    │
│ All design decisions D4-D12 LOCKED via direct multi-choice with    │
│ the user. Updated staging/apis_endeavor.md "Locked decisions"      │
│ section in full. This handoff written.                             │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. The locked decisions you must execute against

Full rationale per decision in `staging/apis_endeavor.md` "Locked
decisions" section. Headlines:

```
D4  Per-source <src>-payload/ folders inside GS/data/apis/<src>/
    (mirrors GS/viz/altair/altair-payload/ INSIDE GS/viz/altair/).

D5  Stub mirror at:
      GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py
    Single file. Import line that resolves in BOTH staging and PRISM:
      from ai_development.mcp.gs_app_proxy_negotiate import session_and_auth

D6  Demo / dev infrastructure:
      GS/data/apis/dev/_harness.py        ← shared sys.path setup
      GS/data/apis/<src>/dev/             ← per-source demos / output
                                            / notes / archive
    Mirrors altair (GS/viz/altair/dev/demos/_harness.py shared +
    per-demo files).

D7  Skill-module filename inside payload matches PRISM's exact
    destination filename per pillar:
      data_guides → <src>_guide.md  (e.g. fdic_guide.md, fred_guide.md)
      instruments → <src>_api.md    (e.g. treasury_api.md)
      tools       → <src>_guide.md  (e.g. openfigi_guide.md)
    Drag-and-drop is byte-identical including filename.
    NO universal SKILL.md in the payload. Existing SKILL.md files
    move to dev/archive/_pre_payload/ on migration (D8).

D8  Existing GS/data/apis/<src>/<src>.py + SKILL.md migrate to:
      GS/data/apis/<src>/dev/archive/_pre_payload/
    Per-source archive, mirrors viz.

D9  PRISM-side wiring on copy-in (3 lines + 1 registry entry):
      mcp/clients/__init__.py:        from . import <src>_client
      mcp/tools/script_exec_tools.py:
        in import block:              <src>_client as _<src>_client,
        in namespace dict:            "<src>_client": _<src>_client,
      context/registry.py:            new MODULE_REGISTRY entry per
                                      D7's filename
    Encoded in Session 7's .cursor/rules/api-clients.mdc rule.

D10 Migration order:
      Session 5 = treasury        (Bucket A)
      Session 6 = treasurydirect  (Bucket B)
      Session 7 = api-clients.mdc rule
      Session 8 = first batch (fdic → bis → ofr → ...)

D11 Six L2-orphaned clients (cftc, congress, federal_register,
    usitc, ofac, wikipedia) get a NEW <src>_guide.md as part of
    their migration. Net new contribution to PRISM. ofac is
    flagged (might be intentionally retired — ask the user before
    writing the L2 module for it).

D12 Bucket C clients get same payload formality as A/B. Just no
    stub-mirror smoke test required (their migrations don't
    exercise gs_app_proxy_negotiate).
```

---

## 4. What you will do in Session 3 (your deliverables)

This is SCAFFOLDING WORK ONLY. No actual stub mirror code (Session 4
writes that). No actual client rebuilds (Session 5+). You are
creating the empty-but-correct directory tree that Session 4
populates.

### 4.1 Create the directory tree

```
GS/data/apis/
├── README.md                                           ← LIGHT EDIT
├── ai_development/                                     ← NEW
│   └── mcp/
│       └── gs_app_proxy_negotiate.py                   ← stub file
│                                                          (placeholder
│                                                          for Session
│                                                          4; see §4.2)
├── dev/                                                ← NEW
│   └── _harness.py                                     ← scaffolding
│                                                          for sys.path
│                                                          setup; see
│                                                          §4.3
├── treasury/                                           ← existing
│   ├── treasury.py                                       (untouched —
│   ├── SKILL.md                                          archive happens
│   ├── examples/                                         in Session 5)
│   ├── archive/
│   ├── data/
│   ├── metadata/
│   ├── treasury-payload/                               ← NEW (empty,
│   │   └── .gitkeep                                       Session 5
│   │                                                      fills it in)
│   └── dev/                                            ← NEW
│       ├── demos/
│       │   └── .gitkeep
│       ├── output/
│       │   └── .gitkeep
│       ├── archive/
│       │   └── _pre_payload/
│       │       └── .gitkeep
│       └── notes.md                                    ← scaffolding
│                                                          (empty header
│                                                          + open-items
│                                                          template)
├── treasurydirect/                                     ← same pattern
│   ├── (existing files untouched)
│   ├── treasurydirect-payload/                         ← NEW
│   │   └── .gitkeep
│   └── dev/                                            ← NEW
│       ├── demos/.gitkeep
│       ├── output/.gitkeep
│       ├── archive/_pre_payload/.gitkeep
│       └── notes.md
├── ... (all 24 existing source folders get the same -payload/ +
       dev/ skeleton)
```

So for each of the 24 existing source folders under `GS/data/apis/`,
you add:
- `<src>/<src>-payload/.gitkeep`
- `<src>/dev/demos/.gitkeep`
- `<src>/dev/output/.gitkeep`
- `<src>/dev/archive/_pre_payload/.gitkeep`
- `<src>/dev/notes.md` (scaffolded — see §4.4)

The 24 sources to do this for (from `GS/data/apis/README.md`):
`bis`, `cftc`, `congress`, `data`, `defeatbeta`, `dtcc`, `eia`,
`electricity`, `fdic`, `federal_register`, `fred`, `gdelt`, `nyfed`,
`ofac`, `ofr`, `openfigi`, `prediction_markets`, `rss`, `sec_edgar`,
`substack`, `tariffs`, `tic`, `treasury`, `treasurydirect`,
`usaspending`, `wikipedia`.

(Note: `data/` and `defeatbeta/` are not in the 17-client PRISM
inventory — they are staging-only directories. Skip them or include
them with a comment, your call. The PRISM-bound 17 are: bis, cftc,
congress, fdic, federal_register, fred, newyorkfed (= nyfed
directory), ofac, ofr, openfigi, prediction_markets, sec_edgar,
substack, treasury, treasury_direct (= treasurydirect directory),
usitc, wikipedia. The other 7 staging directories are extra.)

### 4.2 The stub mirror placeholder

`GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py` should be
a PLACEHOLDER that Session 4 will replace. Suggested content:

```python
"""
Staging stub mirror for PRISM's gs_app_proxy_negotiate.py.

This is the LOCAL replacement that lets <src>-payload/<src>_client.py
files import `from ai_development.mcp.gs_app_proxy_negotiate import
session_and_auth, manual_https_request` and have it resolve in this
staging repo (which has no GS network / no Kerberos).

The same import line resolves in PRISM to the REAL Kerberos /
SPNEGO / proxy implementation. The signature contract MUST match
PRISM verbatim — see prism/_reference/gs_app_proxy_negotiate.py for
the spec.

This file is staging-only and never ships to PRISM.

Status: PLACEHOLDER (Session 3 scaffolding). Session 4 of the APIs
endeavor will fill in the actual stub bodies (vanilla `requests`
fallthroughs that satisfy all three _USE_GS_PROXY patterns
documented in prism/gs-proxy.md §5.3).

Until Session 4: importing from this module raises NotImplementedError
loudly so any premature use surfaces immediately.
"""

raise NotImplementedError(
    "Stub mirror not yet implemented. Session 4 of the APIs endeavor "
    "(see staging/apis_endeavor.md) writes the actual stub bodies. "
    "Until then, do not import from this module."
)
```

The `raise` at module-load time means `from ai_development.mcp.gs_app
_proxy_negotiate import ...` fails LOUDLY (which is the right
behaviour per the viz "stub mirror parity invariant" — strict stubs
fail loud, not silent).

### 4.3 The shared dev harness

`GS/data/apis/dev/_harness.py` — minimal scaffolding for sys.path
setup that Session 4+ demos will import. Suggested skeleton:

```python
"""
Shared sys.path harness for staging-side apis demos.

Any per-source demo at GS/data/apis/<src>/dev/demos/*.py can import
this to set up the local stub-mirror path:

    from GS.data.apis.dev._harness import setup_sys_path
    setup_sys_path()

After that, payload imports like:
    from ai_development.mcp.gs_app_proxy_negotiate import session_and_auth
resolve to GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py
(the local stub mirror), exactly as they would resolve to PRISM's
real module on the PRISM side.

Status: PLACEHOLDER (Session 3 scaffolding). Session 4 fills in the
actual setup_sys_path() body once the stub mirror is written. For
now this module exposes the function name so demos can import it
without breaking, but the body is a no-op + warning.
"""

import sys
import warnings
from pathlib import Path


def setup_sys_path() -> None:
    """Insert GS/data/apis/ at sys.path[0] so `ai_development.*`
    imports resolve to the local stub mirror.

    Session 3 scaffolding: this is a no-op + warning.
    Session 4 will replace with the actual sys.path mutation.
    """
    apis_root = Path(__file__).resolve().parent.parent  # GS/data/apis/
    if str(apis_root) not in sys.path:
        sys.path.insert(0, str(apis_root))
    warnings.warn(
        "GS/data/apis/dev/_harness.py is a Session 3 scaffolding "
        "placeholder. Stub mirror at ai_development/mcp/g_a_p_n.py "
        "will raise NotImplementedError until Session 4. "
        "See staging/apis_endeavor.md.",
        stacklevel=2,
    )
```

Pattern is borrowed from `GS/viz/altair/dev/demos/_harness.py` — go
read that file first to mirror the existing convention.

### 4.4 The per-source notes.md scaffolding

For each `GS/data/apis/<src>/dev/notes.md`, write a minimal stub:

```markdown
# notes.md — <src> staging notes

Open items, recent fixes, and gotchas for the `<src>` API client
during the APIs endeavor migration. Mirrors GS/viz/altair/dev/notes.md
in shape.

## Status

Pre-payload. The existing `<src>/<src>.py` + `SKILL.md` are the
current source of truth and are untouched. The migration to the
`<src>-payload/` model is scheduled per
`staging/apis_endeavor.md` (Session 5+ for treasury / treasurydirect;
Session 8 first-batch for the rest).

Transport bucket: TBD per `prism/api-clients.md` §9 / `prism/gs-proxy.md` §7.
                  (Update this row when the migration starts.)

## Open items

(none yet)
```

That's it. Don't try to fill in the transport bucket per source — let
Session 5/6/8 do that as part of the migration.

### 4.5 The README touch-up

Edit `GS/data/apis/README.md` — add a single new section (don't
restructure the existing inventory / status / usage tables):

```markdown
## Payload model (in flight — APIs endeavor)

A multi-session staging-side rewrite is moving each source from
the current vanilla-`requests` implementation to a plug-and-drop
model that mirrors `GS/viz/altair/altair-payload/`.

The target shape per source:

    GS/data/apis/<src>/
    ├── <src>.py               ← current implementation (will move
    ├── SKILL.md                  to dev/archive/_pre_payload/ on
    │                             migration)
    ├── <src>-payload/         ← NEW: the byte-identical drag-and-drop
    │   ├── <src>_client.py       unit. Lifts straight into PRISM at
    │   └── <src>_guide.md        ai_development/mcp/clients/ +
    │      (or _api.md per           context/modules/static/{pillar}/
    │       pillar — see D7)
    └── dev/                   ← NEW: staging-only dev infra
        ├── demos/                  (does not ship)
        ├── output/
        ├── archive/_pre_payload/
        └── notes.md

Plus a single staging-side stub mirror at
`GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py` that lets
the payload's `from ai_development.mcp.gs_app_proxy_negotiate import
...` lines resolve here without GS network / Kerberos.

The full plan is at `staging/apis_endeavor.md` (the canonical doc).
The locked design decisions (D4-D12) are in that doc's "Locked
decisions" section. The Session 3 handoff (this scaffolding) is at
`staging/handoffs/session_3.md`.

| Status table column | What "Done" / "Yes" means |
|----|----|
| `Code` | Existing pre-payload implementation exists. |
| `SKILL.md` | Existing pre-payload skill module exists. |
| `Wired?` | Existing implementation is wired into PRISM via the older mechanism (one of `mcp/clients/`, `pull_*_data` injection). NOT the new payload model. |

A new column will be added to the status table once the first source
finishes payload migration (Session 5).
```

---

## 5. Non-goals for Session 3 (do NOT do these)

- Do NOT write actual stub-mirror code in `gs_app_proxy_negotiate.py`.
  The placeholder `raise NotImplementedError(...)` is correct; Session
  4 fills in the real body.
- Do NOT touch any existing `<src>/<src>.py` files. They are
  untouched until the per-source migration session (5+) archives
  them per D8.
- Do NOT touch any existing `<src>/SKILL.md` files. Same reason.
- Do NOT write any `<src>_guide.md` / `<src>_api.md` skill modules.
  Those come in Session 5+ as part of each per-source migration.
- Do NOT modify `prism/` docs. The structural facts in `prism/gs
  -proxy.md` and `prism/api-clients.md` are the spec; Session 3
  doesn't re-derive them.
- Do NOT write `.cursor/rules/api-clients.mdc`. That's Session 7,
  AFTER the first two reference rebuilds prove the pattern.
- Do NOT migrate any clients. Just scaffold.

---

## 6. Acceptance criteria for Session 3

```
□ All 24 source folders under GS/data/apis/ have an empty
  <src>-payload/ subfolder with .gitkeep
□ All 24 source folders have a dev/ subfolder with demos/, output/,
  archive/_pre_payload/ (each with .gitkeep) and a scaffolded
  notes.md per §4.4
□ GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py exists
  with the §4.2 placeholder body (raises NotImplementedError on
  import)
□ GS/data/apis/dev/_harness.py exists with the §4.3 placeholder
  body (warns + does sys.path setup but not the actual stub-mirror
  path-manipulation magic Session 4 needs)
□ GS/data/apis/README.md has the §4.5 "Payload model (in flight)"
  section appended
□ Existing <src>/<src>.py + SKILL.md files are UNTOUCHED in every
  source folder
□ staging/apis_endeavor.md status tracker updated:
    Session 3 marked [x] complete with one-line note
    Session 4 marked [ ] ready
□ prism/_changelog.md gets a one-line "Session 3 (scaffolding)
  complete" entry (no actual prism/ doc edits — this is staging
  organizational work)
□ Run `python3 -c "import sys; sys.path.insert(0, 'GS/data/apis'); \
                  from GS.data.apis.dev._harness import setup_sys_path"`
  and confirm it imports cleanly (the warning fires but no
  exception)
□ Run `python3 -c "import sys; sys.path.insert(0, 'GS/data/apis'); \
                  from ai_development.mcp.gs_app_proxy_negotiate import \
                  session_and_auth"` and confirm it raises
  NotImplementedError loudly (proves the strict-stub invariant)
```

---

## 7. After you finish Session 3

Update `staging/apis_endeavor.md`:
- Status tracker: Session 3 → `[x]` with the scaffolding summary
- Status tracker: Session 4 → `[ ]` ready, with one-line note
  pointing the next handoff at the same staging/apis_endeavor.md
- "Open decisions" — no changes; D4-D12 are already locked
- Maybe add a "Lessons from Session 3" if you found anything
  surprising while scaffolding (unlikely — this is mechanical work)

Update `prism/_changelog.md`:
- New top entry, one paragraph max, "2026-MM-DD — APIs endeavor
  Session 3 (scaffolding) complete"

Optionally write `staging/handoffs/session_4.md` as the next
handoff (the structure of Session 4 is already known — write the
real stub mirror body in `ai_development/mcp/gs_app_proxy_negotiate
.py` per `prism/_reference/gs_app_proxy_negotiate.py` signatures,
fill in `dev/_harness.py`'s setup_sys_path() body, write 1-2
trivial smoke demos that prove the stub mirror works).

---

## 8. Reference: the locked layout in one diagram

```
GS/data/apis/                    ← apis root
│
├── README.md                    ← inventory + new "Payload model" section
│
├── ai_development/              ← STAGING STUB MIRROR (never ships)
│   └── mcp/
│       └── gs_app_proxy_negotiate.py
│           (placeholder Session 3 → real stub Session 4)
│
├── dev/                         ← SHARED dev infrastructure (never ships)
│   └── _harness.py              (sys.path setup helper)
│
├── treasury/                    ← per-source folder (24 of these)
│   ├── treasury.py              ← existing (UNTOUCHED until Session 5)
│   ├── SKILL.md                 ← existing (UNTOUCHED until Session 5)
│   ├── examples/                ← existing
│   ├── archive/                 ← existing
│   ├── data/                    ← existing
│   ├── metadata/                ← existing (treasury-only)
│   │
│   ├── treasury-payload/        ← NEW (Session 3 scaffolding)
│   │   └── .gitkeep
│   │   (Session 5 will fill with treasury_client.py + treasury_api.md)
│   │
│   └── dev/                     ← NEW (Session 3 scaffolding)
│       ├── demos/.gitkeep
│       ├── output/.gitkeep
│       ├── archive/
│       │   └── _pre_payload/.gitkeep
│       │       (Session 5 will move treasury.py + SKILL.md here)
│       └── notes.md             ← NEW (scaffolded stub)
│
├── treasurydirect/              ← same pattern, Session 6 target
├── fdic/                        ← same pattern
├── bis/                         ← same pattern
├── ... (20 more)
│
└── (everything else under GS/data/apis/, unchanged)
```

PRISM-side mapping (what each payload file lifts to, for context):

```
STAGING                                         PRISM
─────────────────────────────────────────────  ──────────────────────────
GS/data/apis/<src>/<src>-payload/              ai_development/mcp/clients/
    <src>_client.py             ──────────►        <src>_client.py
    <src>_guide.md              ──────────►    context/modules/static/
                                                   {pillar}/<src>_guide.md
                                                   (or _api.md per D7)
+ PRISM-side wiring step (3 lines + 1 registry entry — see D9)
```

---

## 9. Key files at a glance (paths to keep handy while you work)

```
HANDOFF / PLANNING                                  HEAVY-READ FOR
                                                    UNDERSTANDING
── staging/apis_endeavor.md                         (full)
── staging/handoffs/session_3.md (this file)
── staging/prompts.md (no active prompt right now)
── staging/prompts_archive/2026-05-01_apis
       _endeavor_session_2.md (the round-trip
       that informed the L1-L7 lessons)

PRISM-SIDE TRUTH                                    BUDGET
── prism/README.md                                  ~150 lines
── prism/architecture.md §6.3 (client modules path) ~50 lines
── prism/code-sandbox.md §2.5 + §2.14               ~80 lines
── prism/codebase-tree.md §3.3 + §3.4               ~50 lines
── prism/gs-proxy.md (full)                         ~775 lines
── prism/api-clients.md (full)                      ~660 lines
── prism/_reference/gs_app_proxy_negotiate.py       ~460 lines
── .cursor/rules/prism.mdc                          ~110 lines
── .cursor/rules/viz-platforms.mdc                  ~310 lines

VIZ PRECEDENT (the pattern you mirror)
── GS/viz/altair/                                   listing only
── GS/viz/altair/ai_development/                    listing only
── GS/viz/altair/dev/demos/_harness.py              full (~50 lines)
── GS/viz/altair/dev/notes.md                       full (~480 lines —
                                                     for the notes.md
                                                     skeleton inspiration)

STAGING SIDE — CURRENT STATE
── GS/data/apis/README.md                           ~190 lines
── GS/data/apis/treasury/SKILL.md                   listing only (don't
                                                     migrate yet)
── GS/data/apis/treasury/treasury.py                listing only
```

---

## 10. House rules (carried from the user's standing rules)

- **No emojis.** None of the files you create should have emojis.
- **Never delete files.** Move to `archive/` instead. Temporary test
  scripts are the only exception.
- **All scripts must work without arguments.** If you write any
  `.py` file with a CLI surface, run-with-no-args must launch an
  interactive menu; full argparse mode must mirror it. (Probably
  not relevant for Session 3 since you're scaffolding, not coding.)
- **No summary markdowns.** Don't write a "session_3_summary.md" or
  similar. Just update `staging/apis_endeavor.md` status tracker
  and `prism/_changelog.md`.
- **No new HTML / CSS aesthetics.** (Not relevant for Session 3.)
- **ASCII art is welcome** in markdown files but not required.

---

End of handoff. Start by reading
`staging/apis_endeavor.md` "Locked decisions" + "Lessons from
Sessions 1+2" sections, then `prism/gs-proxy.md` §7 (transport
buckets), then begin scaffolding per §4 above.


Below are some additional things I was thinking about - these will be likely more unstructured.

1) The payload structure should be very similar across all the APIs - one context file, one *_client.py file.
2) I think we should continue keeping treasury_client and treasury_direct_client a single module.
3) Let's think about other cases where we should do strategic grouping of these - basically in cases where the modules are likely to be used together or are complementary.
4) It may take several iterations but the mark of success is that I drop in the client py file and the markdown context file, you give me a test prompt I ask Prism, I will include the "let me know if frictions" tag at the end, and Prism has no frictions. That's how we know the materials you delivered me are frictionless. It's ok if it takes a few times, once we have working drag and drop files then it's easy to iterate on the clients or their context without actually breaking the GS auth or other internals.