# Handoff prompt — APIs endeavor Session 4 (stub mirror + harness)

> Paste this whole file at the start of a fresh Cursor session to
> pick up from here.

You are taking over Session 4 of the **APIs endeavor**, a multi-
session staging-side rewrite of the `mcp/clients/*.py` files in
PRISM into a plug-and-play drag-and-drop model. Sessions 1-3 are
complete. The directory tree is scaffolded. Your job is to fill in
the bodies of the two placeholder files Session 3 left for you,
plus write 1-2 smoke demos that prove the stubs actually work.

---

## 1. Read these files before doing anything

Read in this order. Total budget is roughly the same as Session 3
— substantial but each file is dense.

```
ORIENTATION
  .cursor/rules/prism.mdc                       always-on; the
                                                  always-applied
                                                  workspace rule
  .cursor/rules/viz-platforms.mdc               the gold-standard
                                                  drag-and-drop
                                                  contract; the
                                                  stub-mirror parity
                                                  invariant section
                                                  is the spec for
                                                  this session
  prism/README.md                               prism/ catalog +
                                                  routing table

THE ENDEAVOR
  staging/apis_endeavor.md                      Master plan. Read in
                                                  full, especially:
                                                  - "Locked decisions"
                                                    (D1-D13)
                                                  - "Lessons from
                                                    Sessions 1+2"
                                                    (L1-L8)
                                                  - "Session 4"
                                                    deliverables /
                                                    acceptance

PRISM-SIDE TRUTH (the signature spec)
  prism/_reference/gs_app_proxy_negotiate.py    THE source file you
                                                  are mirroring.
                                                  Read in full —
                                                  signatures must be
                                                  byte-identical.
  prism/gs-proxy.md                             behaviour spec —
                                                  especially:
                                                  - section 5.3
                                                    (_USE_GS_PROXY
                                                    tri-modal)
                                                  - section 7
                                                    (per-host
                                                    transport policy)
                                                  - section 8 (header
                                                    contamination —
                                                    why manual
                                                    CONNECT exists)
                                                  - section 9 (edge
                                                    cases your stub
                                                    can ignore but
                                                    PRISM handles)
  prism/api-clients.md                          per-client transport
                                                  table — useful to
                                                  know which clients
                                                  call session_and_
                                                  auth() vs
                                                  manual_https_
                                                  request()

STAGING SIDE — WHAT SESSION 3 LEFT YOU
  GS/data/apis/ai_development/mcp/              placeholder file
      gs_app_proxy_negotiate.py                   that raises
                                                  NotImplementedError
                                                  on import. You
                                                  REPLACE this with
                                                  real bodies.
  GS/data/apis/dev/_harness.py                  placeholder with
                                                  minimal sys.path
                                                  setup + warning.
                                                  You finalize this.
  GS/data/apis/dev/notes.md                     project-wide notes
                                                  (reference, light
                                                  edits if relevant)

VIZ PRECEDENT (the pattern you mirror)
  GS/viz/altair/ai_development/                 stub-mirror layout
                                                  example
  GS/viz/altair/dev/demos/_harness.py           shared sys.path
                                                  setup pattern
                                                  (already-real,
                                                  full body)
```

---

## 2. What was done in Sessions 1-3

```
┌─ SESSION 1 (prism/ uplift) ────────────────────────────────────────┐
│ Folded OCR scan into curated prism/ docs:                          │
│   prism/gs-proxy.md, prism/api-clients.md, prism/_reference/       │
│   gs_app_proxy_negotiate.py. Cross-references in architecture.md / │
│   code-sandbox.md / codebase-tree.md / data-functions.md / README. │
└────────────────────────────────────────────────────────────────────┘

┌─ SESSION 2 (PRISM round-trip) ─────────────────────────────────────┐
│ Resolved F8-F18 via PRISM context-extraction prompt. Three         │
│ structural findings in "Lessons from Sessions 1+2":                │
│   L1. Three transport buckets (A/B/C), not two                     │
│   L2. _USE_GS_PROXY is tri-modal; stub falls through transparently │
│   L3. mcp/clients/__init__.py != script_exec_tools injection       │
│   L4. newyorkfed_client is the function-injection exception        │
│   L5-L7. minor                                                     │
└────────────────────────────────────────────────────────────────────┘

┌─ SESSION 3 (scaffolding + redesign) ───────────────────────────────┐
│ Mid-session redesign of D4/D6/D7/D8: per-source <src>-payload/     │
│ folders -> ONE unified apis-payload/ at apis root with FLAT        │
│ clients/ + modules/ subfolders mirroring PRISM's destination       │
│ directories. D13 added (success-criterion drag-and-drop loop). L8  │
│ added (only treasury+treasury_direct shares an L2; other adjacent  │
│ pairs rejected).                                                   │
│                                                                    │
│ On disk:                                                           │
│   GS/data/apis/apis-payload/clients/.gitkeep                       │
│   GS/data/apis/apis-payload/modules/.gitkeep                       │
│   GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py        │
│     (placeholder, raises NotImplementedError)                      │
│   GS/data/apis/dev/_harness.py (placeholder, warns + minimal       │
│     sys.path insert)                                               │
│   GS/data/apis/dev/{demos,output,archive/_pre_payload}/.gitkeep    │
│   GS/data/apis/dev/notes.md                                        │
│                                                                    │
│ Cleanup detour: archived 4 repo-root cli_*.py files +              │
│ project-clis.mdc rule.                                             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. What you will do in Session 4

This is BUILD WORK — the load-bearing staging-only piece that
makes the whole endeavor possible. Two real bodies + 1-2 smoke
demos. No payload work yet (Session 5 is the first reference
rebuild).

### 3.1 Replace the stub mirror placeholder

`GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py` is
currently a placeholder that raises `NotImplementedError` on
import. Replace it with the real stub mirror.

Public surface MUST match `prism/_reference/gs_app_proxy_negotiate.py`
byte-for-byte (the stub-mirror parity invariant from
`.cursor/rules/viz-platforms.mdc`):

```
def get_spnego_token(target_principal: str) -> str: ...

class KerberosProxyAuthAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, proxy_address: str, target_principal: str,
                 *args, **kwargs): ...

def session_and_auth() -> Tuple[requests.Session, Optional[Any]]: ...

def manual_https_request(
    method: str,
    host: str,
    path: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    data: Optional[Union[bytes, str, Dict[str, Any]]] = None,
    timeout: float = 30.0,
) -> Tuple[Any, str]: ...
```

(verify exact signatures against `prism/_reference/`.)

Bodies fall through to vanilla `requests` (no GS network, no
Kerberos):

```
session_and_auth()    -> returns (requests.Session(), None)

manual_https_request(method, host, path, **kwargs)
    -> calls requests.request(method, f"https://{host}{path}", **kwargs)
       returns (parsed_data, status_string) in the same shape PRISM's
       tunnel returns:
           parsed_data    = response.json() if json content-type else
                            response.text or response.content
           status_string  = f"HTTP/1.1 {response.status_code} {reason}"

get_spnego_token(target_principal)
    -> staging stub never produces a real SPNEGO token; return a
       deterministic placeholder string (e.g.
       "stub-spnego-token-for-{target_principal}") so any caller that
       *uses* the token in an Authorization header sees something
       traceable in tcpdump / mock servers. The actual auth is bypassed
       because vanilla requests doesn't go through a Kerberos proxy.

KerberosProxyAuthAdapter
    -> instantiable but functionally a no-op; wrap requests.adapters.
       HTTPAdapter without the SPNEGO injection. Tests should never
       exercise this through a real proxy in staging.
```

CRITICAL constraints (per the parity invariant):

1. Stubs follow PRISM, not the other way around. If the body shape
   here doesn't match what PRISM does, fix the stub, never PRISM.

2. Stubs MUST NOT be more permissive than PRISM. If PRISM rejects
   an unknown kwarg with TypeError, the stub must too.

3. Stubs MAY be stricter than PRISM (raise on signature drift loudly).

4. The stub satisfies all three `_USE_GS_PROXY` patterns
   transparently per L2 — no client-side code change required.

### 3.2 Finalize the dev harness

`GS/data/apis/dev/_harness.py` currently has a minimal sys.path
insert + warning. Replace the warning (now obsolete since the stub
is real) with a richer setup_sys_path() that:

1. Inserts `GS/data/apis/` at sys.path[0] (so
   `from ai_development.mcp.gs_app_proxy_negotiate import ...`
   resolves to the local stub).
2. Optionally inserts `GS/data/apis/apis-payload/clients/` at
   sys.path[1] so demos can `import treasury_client` directly
   (this matches how PRISM-side demos import `treasury_client`
   without the `mcp.clients.` prefix).
3. Returns the apis_root Path for callers that want it.

Pattern is borrowed from `GS/viz/altair/dev/demos/_harness.py` —
read that file first to mirror the existing convention.

### 3.3 Write 1-2 smoke demos

Each demo proves the stub works end-to-end without touching any
real client. Place under `GS/data/apis/dev/demos/`:

```
00_smoke_session_and_auth.py
  - calls setup_sys_path() from the harness
  - imports session_and_auth from the stub
  - asserts return type is (requests.Session, None)
  - performs one trivial GET against a public endpoint (e.g.
    https://api.fiscaldata.treasury.gov/services/api/fiscal_service/
    debt_to_penny?limit=1) using the returned session
  - prints status + first row, exits 0 on success
  - has both an interactive CLI (run with no args = run the smoke)
    and a --help / argparse surface per the workspace rule

00_smoke_manual_https_request.py
  - calls setup_sys_path() from the harness
  - imports manual_https_request from the stub
  - calls it with a TreasuryDirect endpoint (the canonical Bucket B
    target):
      manual_https_request(
          "GET",
          "www.treasurydirect.gov",
          "/TA_WS/securities/announced?format=json&type=Bill",
          timeout=10.0,
      )
  - asserts return is a 2-tuple (parsed, status_string)
  - asserts status_string starts with "HTTP/1.1 2"
  - prints first 100 chars of parsed
  - same CLI shape as above
```

These are STAGING-SIDE smoke tests. They hit live external
endpoints (no GS auth required because TreasuryDirect / Treasury
Fiscal Data are both public). If you want to make them
network-free, mock with `responses` or `httpretty` — but a live
hit against a public API is the simplest proof and matches the
viz precedent.

### 3.4 Light edits to dev/notes.md

Update the "Status" section in `GS/data/apis/dev/notes.md` to
reflect that the stub mirror and harness are now real (not
placeholders). Drop the "Session 4 fills body" notes for both
files. Add a "Recent changes" entry at the bottom.

---

## 4. Non-goals for Session 4 (do NOT do these)

- Do NOT touch any `<src>/<src>.py` files. Per-source migrations
  are Sessions 5+.
- Do NOT write any payload files (`apis-payload/clients/*` or
  `apis-payload/modules/*`). Same reason.
- Do NOT modify `prism/` docs. The structural facts in
  `prism/gs-proxy.md` and `prism/_reference/` are the spec; Session
  4 implements against them, not re-derives.
- Do NOT write `.cursor/rules/api-clients.mdc`. That's Session 7,
  AFTER Sessions 5+6 produce two reference rebuilds that prove the
  pattern in practice.
- Do NOT extend the stub mirror beyond what
  `prism/_reference/gs_app_proxy_negotiate.py` exposes. Per L6,
  `mcp/utils/` has no shared cross-client helper layer in PRISM,
  so the stub mirror is a single file.
- Do NOT add the GS Kerberos imports (`requests_kerberos`,
  `gssapi`, `pykerberos`) at the top of the stub. Those are
  PRISM-side only. The local stub uses vanilla `requests` only.

---

## 5. Acceptance criteria for Session 4

```
□ GS/data/apis/ai_development/mcp/gs_app_proxy_negotiate.py
    - imports cleanly (no NotImplementedError on module load)
    - exposes session_and_auth, manual_https_request,
      KerberosProxyAuthAdapter, get_spnego_token with signatures
      byte-identical to prism/_reference/gs_app_proxy_negotiate.py
    - bodies use vanilla requests; no GS Kerberos imports

□ GS/data/apis/dev/_harness.py
    - setup_sys_path() body inserts apis_root + optionally
      apis-payload/clients/ on sys.path
    - no longer warns about being a placeholder
    - mirrors GS/viz/altair/dev/demos/_harness.py's shape

□ GS/data/apis/dev/demos/00_smoke_session_and_auth.py
    - runs to completion with no args
    - has full argparse surface
    - hits a public Treasury Fiscal Data endpoint successfully

□ GS/data/apis/dev/demos/00_smoke_manual_https_request.py
    - same as above but for TreasuryDirect (Bucket B canonical)

□ GS/data/apis/dev/notes.md updated:
    - Status section reflects post-Session-4 state
    - Recent changes entry added

□ staging/apis_endeavor.md status tracker:
    - Session 4 marked [x] complete
    - Session 5 marked [ ] ready, with handoff pointer

□ prism/_changelog.md:
    - new top entry, "2026-MM-DD — APIs endeavor Session 4
      (stub mirror + harness) complete"

□ Optional but recommended:
    Write staging/handoffs/session_5.md describing the treasury
    rebuild. The Session 5 shape is locked in apis_endeavor.md;
    just transcribe.
```

---

## 6. Reference: signatures from prism/_reference/

The full reconstructed source is in
`prism/_reference/gs_app_proxy_negotiate.py` (~460 lines). When you
read it, focus on the four public symbols — those are the only
contract the staging stub mirror has to satisfy:

```
get_spnego_token(target_principal: str) -> str

class KerberosProxyAuthAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, proxy_address, target_principal, *args, **kwargs)
    def send(self, request, **kwargs)

session_and_auth() -> Tuple[requests.Session, Optional[Any]]

manual_https_request(method, host, path, *, headers=None,
    params=None, data=None, timeout=30.0)
    -> Tuple[Any, str]
```

The signature spec is the WHAT. The PRISM-side BEHAVIOUR (what each
method does in production) is in `prism/gs-proxy.md`. Your stub
implementation only has to provide the WHAT — the BEHAVIOUR is
"vanilla requests fallthrough" because no GS network exists locally.

---

## 7. House rules (carried from the user's standing rules)

- **No emojis.**
- **Never delete files.** Move to archive/ instead.
- **All scripts run without arguments.** Smoke demos must launch
  by `python3 GS/data/apis/dev/demos/00_smoke_*.py` with no args
  AND have full argparse surfaces (`--help`, etc.).
- **Progress information.** Even though smoke demos are short,
  any user-visible CLI output should include status updates if
  the demo takes more than a few seconds.
- **No summary markdowns.** Don't write a "session_4_summary.md".
  Just update apis_endeavor.md status tracker + prism/_changelog.md.
- **Document updates in-place.** No "NEW" / "UPDATED" markers.
- **ASCII art is welcome** in markdown files but not required.

---

End of handoff. Start by reading `staging/apis_endeavor.md`
"Locked decisions" + "Lessons from Sessions 1+2" sections, then
`prism/_reference/gs_app_proxy_negotiate.py` in full, then begin
implementation per section 3 above.
