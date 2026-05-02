# PRISM context-extraction prompt — `prism/` clarity sweep

This is a **CONTEXT-EXTRACTION PROMPT**, not an end-usage prompt. No
real artefact to build. No Frictions section needed. The goal is to
introspect specific PRISM internals and resolve a list of
contradictions / unclear designs / undocumented architecture that
have accumulated in `prism/` (the staging-side curated SSOT).

Reply by section number. Quote source verbatim wherever possible
(file path + line range + fenced block). Where verbatim isn't
practical, give a STRUCTURED answer (tables, named fields,
explicit lists). Where the question is forward-looking, give a
DESIGN-INTENT answer (current state + intent + blocker if any).

If a section can't be resolved (file missing, symbol unstable,
permission), add it to a `## Could not resolve` block at the end
with what you tried and what blocked it. Do not fabricate.

If the introspection naturally surfaces follow-on facts that
contradict something this prompt assumed, FLAG THEM EXPLICITLY in
that section's reply with `> NOTE: assumption mismatch — ...`.
Drift in either direction is signal.

---

# TIER 1 — load-bearing architecture / true contradictions

## §1. The L1 docstrings (the LLM's actual operating instructions)

`prism/` documents fragments of these but never the verbatim full
bodies. They are the most-loaded strings in PRISM (visible on
EVERY conversation before any tool call), so this is the highest-
value section.

For EACH of the three L1 tools below, paste the verbatim function
docstring (everything between the triple quotes), the file path,
and any module-level constants the docstring relies on (e.g.
specialization-bundle dicts, world_state schema):

1. **`get_context()`** in `mcp/tools/context_tool.py` — the L2
   routing table; carries Rule 1 / Rule 3 (one-shot per user
   message), the module catalog, the specialization-bundle
   semantics, and the `world_state` / `observation_domains` /
   `user_signal_hint` parameter docs.

2. **`global_context()`** in `mcp/tools/global_tools.py` — the L1
   system prompt itself.

3. **`data_context()`** (path TBD — likely `mcp/tools/` somewhere) —
   the data-source decision tree referenced from
   `prism/architecture.md` §6.

For each, also state:
- `async def` or plain `def`?
- Decorators applied (e.g. `@mcp.tool`, custom)?
- Return type annotation?
- Total character / line count of the docstring?

If any of these three tools doesn't exist by that name, say so
and point to the actual mechanism that plays the same role.

## §2. L1 vs L2 vs Tier-1-of-L2 — concrete taxonomy

`prism/` uses these terms in adjacent paragraphs and they're easy
to conflate. Resolve:

(a) Define each layer with one sentence + the file/folder where
    that layer's content actually lives:

| Layer | One-sentence definition | Where the content lives |
|-------|-------------------------|--------------------------|
| L1 system prompt | ? | `mcp/tools/global_tools.py`? |
| L1 tool registry / docstrings | ? | `mcp/tools/*.py` docstrings + MCP tool registration? |
| L2 always-loaded (Tier 1 of L2) | ? | `context/modules/static/*.md` + Tier 1 list? |
| L2 on-demand (Tier 2 of L2) | ? | Same folder, different tier flag? |
| L3 code execution | ? | `execute_analysis_script` namespace |
| L4 S3 / indexes | ? | `grep_s3` / `get_s3_files` indexes |

(b) On a fresh user-message turn (kerberos provided, no
    specialization), what does the LLM literally see in its
    context window AT t=0 (before it has called anything)? List
    the ordered concatenation of strings (system prompt, tool
    docstrings, anything else).

(c) After the LLM calls `get_context(...)` exactly once on that
    turn, what gets ADDED to the context window? List the
    `<CONTEXT_START>` block's source modules in load order for
    the default `end_user` specialization with no `world_state`
    flags and no `include_modules`.

(d) Are L1 tool docstrings and L2 Tier-1 modules ever the same
    string in two places (i.e. does the L1 `get_context`
    docstring duplicate any of the same content that lives in a
    Tier-1 markdown module)? If yes, which content overlaps?

## §3. Module pillars vs directory structure — the mapping

`prism/architecture.md` §3.3 lists module **pillars**:
`navigation`, `world_state`, `user`, `tools`, `behavioral`,
`skills`, `reports`.

`prism/codebase-tree.md` §2 lists `context/modules/static/`
**subdirectories**: `core/`, `data_guides/`, `instruments/`,
`tools/`, `developer/`, `observatory/`, `reports/`, `email/`,
`claude_skills/`, `people/`, `reference_data/`.

These are different taxonomies. Resolve:

(a) Paste a representative slice of `context/registry.py` —
    specifically 5-6 entries spanning multiple pillars (one each
    from `navigation`, `world_state`, `tools`, `behavioral`,
    `skills`, `reports`). Show the registry-key, `pillar`,
    `source` (file path), `tier`, and `bundle` fields.

(b) Build a mapping table: for EVERY pillar, list which
    `context/modules/static/<subdir>/` directory(ies) hold its
    modules. If a pillar spans multiple directories, say so.

(c) The reverse: for every subdirectory, which pillar(s) does
    it map to?

(d) Is there an authoritative spec anywhere (a docstring, a
    comment block in `registry.py`, a markdown doc) that
    documents the pillar-to-directory invariant? If yes, paste
    it. If no, confirm that.

## §4. Dashboard refresh runner namespace gap

`prism/dashboard-refresh.md` §5.5 documents that
`_build_exec_namespace` in `jobs/hourly/refresh_dashboards.py` is
**leaner** than `execute_analysis_script`'s sandbox namespace:

> `save_artifact()`, `pull_fred_data`, `pull_nyfed_data`,
> `pull_pure_data`, `pull_stacked_data`, and the alt-data client
> modules (`fdic_client`, `sec_edgar_client`, `bis_client`, …)
> are NOT in `_build_exec_namespace` as of 2026-04-27. They ARE
> in the `execute_analysis_script` sandbox.

This means a dashboard's `pull_data.py` that uses any of those
helpers builds cleanly at session-time but raises `NameError` on
hourly refresh.

Resolve:

(a) Paste the verbatim current `_build_exec_namespace` body from
    `ai_development/jobs/hourly/refresh_dashboards.py`. Include
    every name it puts into the namespace.

(b) Is the omission of `save_artifact` / `pull_fred_data` / the
    client modules **intentional** (e.g. headless-refresh-mode-
    only contract that excludes alt-data on purpose) or **drift**
    (intended to mirror the sandbox but the wrappers haven't
    been added yet)?

(c) If drift: is there a spec / endeavor / ticket scheduling the
    fix? When?

(d) The `make_chart` / multipack stubs (`make_chart_headless`,
    `ChartResult` with `success=False`, etc.) — are these
    permanent (charts are intentionally skipped on refresh
    because dashboards are JSON-manifest-driven) or are they
    placeholders that go away when chart-rendering becomes
    refresh-safe?

(e) The hourly refresh path uses `compile()` + `exec(compile,
    namespace)`; the on-demand `refresh_runner.py` uses plain
    `exec(content, namespace)`. Both call `_build_exec_namespace`
    — confirmed? Are there any other places that build a
    headless-style namespace separately?

## §5. Client layer asymmetries — fred / ofr / wikipedia / congress

`prism/api-clients.md` documents three structural oddities:

(a) `fred_client.py` and `ofr_client.py` HAVE registry entries
    (`fred_guide`, `ofr_guide` L2 modules) but are **NOT
    injected** into the sandbox namespace.

(b) `wikipedia_client.py` IS injected into the sandbox but has
    **no L2 module**.

(c) `congress.py` lacks the `_client.py` suffix that every other
    of the 17 modules uses.

For each:

(a/i) Is the fred / ofr non-injection drift (the module was
      supposed to be injected but never got added) or
      intentional (some other code path delivers the
      functionality)? If intentional, what is the alternative
      access path the LLM is supposed to use?

(a/ii) `pull_fred_data` IS in the sandbox namespace per
       `code-sandbox.md` §2.5 — paste its source from
       `ai_development/mcp/utils/data_functions.py` (or
       wherever it actually lives) and confirm it does NOT
       depend on `fred_client` being importable.

(b/i) Is wikipedia's missing L2 intentional (the LLM is
      supposed to discover it from the docstring of one of its
      methods?) or drift (an L2 was planned and never written)?

(c/i) `congress.py` naming — bug, in-flight rename, or
      intentional? Anything in the file body that explains?

(c/ii) Paste the first 20 lines of `mcp/clients/congress.py`
       to see what the public surface looks like.

(d) The seven NOT-injected list (`cftc`, `congress`,
    `federal_register`, `fred`, `ofac`, `ofr`, `usitc`) — is
    there a single decision (e.g. "these were curated out
    deliberately because they're noisy / unfinished") or is it
    seven independent code-drift cases?

## §6. Registry schema contradiction — `schema_version` / `owner_kerberos` / `history_retention_days`

`prism/dashboard-refresh.md` §6.1 says, of
`users/{kerberos}/dashboards/dashboards_registry.json`:

> `schema_version` and `owner_kerberos` are NOT part of the
> current schema. Earlier versions of this file claimed they
> were; they are not present in any live registry as of
> 2026-04-27.

But `prism/dashboards-portal.md` §2.2 shows that
`secondary/prism_observations/dashboards/dashboards_registry.json`
DOES carry both `schema_version: "1.0"` and `owner_kerberos:
"system"`.

And `history_retention_days` is documented as
"planned-but-unimplemented" for user registries but actually
present in the Observatory registry.

Resolve:

(a) Paste the actual current top-level shape of:
    - `users/goyalri/dashboards/dashboards_registry.json` (or any
      live user registry — anonymise if needed)
    - `secondary/prism_observations/dashboards/dashboards_registry.json`

(b) Are user and Observatory registries supposed to share a
    schema (and Observatory just drifted ahead) or are they
    intentionally separate schemas? If separate, where is each
    schema defined / enforced?

(c) `history_retention_days` — is the field actually honoured
    anywhere (any code that reads it and acts on it)? Or is it
    inert metadata in the Observatory registry?

(d) The hand-rolled-by-Tool-3 registry-write pattern documented
    in `dashboard-refresh.md` §6.3 — is there a plan to ship a
    canonical `register_dashboard()` helper, and if so, will it
    enforce a schema (Pydantic / dataclass / jsonschema)?

## §7. Cross-user enforcement intent (`/api/dashboard/refresh/`)

`prism/dashboard-refresh.md` §2.4 documents that
`refresh_dashboard_api` does NOT enforce viewer == owner:

> User A's browser, with A's GSSSO cookie set, can POST
> `{"kerberos": "B", "dashboard_id": "..."}` and trigger a
> refresh of B's dashboard.

The UI hides the [Refresh] button for non-authors via
`PRISM_VIEWER === PRISM_DASHBOARD_AUTHOR` (`dashboards-portal.md`
§6.5), but a hand-crafted POST slips through.

Resolve:

(a) Paste the current verbatim `refresh_dashboard_api` body
    from `ai_development/mysite/news/views.py`. Confirm
    whether the viewer-owner check is still absent.

(b) Is leaving this gap **intentional** (e.g. PRISM-as-a-service
    might cross-trigger refreshes for shared dashboards in some
    automation use-case) or **a known security item awaiting a
    fix**?

(c) If "awaiting a fix" — what's the design? `if data.get(
    "kerberos") != caller: return 403`? Or something more
    flexible (e.g. allow if the target's `shared: true` and
    `caller in <some allowlist>`)?

(d) Same question for `refresh_status_api` — is the
    viewer-implicit S3 path (always `users/{viewer}/...`) the
    intended long-term shape, or is the design intent to grow an
    explicit `?author=` parameter for community polling?

## §8. Vision QC retirement — what's blocking step 3

`prism/vision-qc.md` §8 lists 5 retirement steps:

| Step | Status (per `prism/`) |
|------|------------------------|
| Engine-internal QC stop calling `_check_chart_quality_safe` from inside `make_chart` | "done in staging; ships on next drag-and-drop" |
| Vision-driven annotation auto-generator removed from `chart_functions.py` | Same |
| Post-exec QC: `_check_charts_quality_injected` removed from `script_exec_tools.py` | "not started — requires PRISM-side change" |
| `check_chart_quality` / `check_charts_quality_parallel` become no-ops | "not started" |
| `describe_images` continues for genuine description tasks | unchanged |

Resolve:

(a) Confirm: is `_check_charts_quality_injected` still being
    called by `script_exec_tools.py` after every successful
    `execute_analysis_script` run? Paste the call site and the
    full `_check_charts_quality_injected` body if it's still
    live.

(b) What is blocking step 3? Specifically: is there a
    construction-time replacement (the "constructive
    guardrails inside `make_chart`" referenced in
    `vision-qc.md` §8) that hasn't shipped on the staging side
    yet, OR is the post-exec QC providing real value PRISM
    relies on?

(c) `_check_chart_quality_safe` is documented as dead code
    (`code-sandbox.md` §2.3 — "Defined but never called in
    current `chart_functions.py`"). Is the staging side's
    chart_functions.py the version PRISM is actually running, or
    is there drift? If drift: paste the current PRISM-side
    `chart_functions.py` size + the line numbers where
    `_check_chart_quality_safe` is defined and the line numbers
    where it is (or is not) called.

(d) Is there a staging→PRISM drag-and-drop currently scheduled
    that would land steps 1+2? (Doesn't have to be a precise
    date — week-of-X granularity is fine.)

# TIER 2 — design intent / forward-looking

## §9. The `__dynamic__` decorator placeholder

`prism/dashboards-portal.md` §3 documents:

> `@require_page_access('__dynamic__')` is a placeholder — the
> real per-dashboard access check is hand-rolled inside
> `dashboard_detail` via `check_page_access(kerberos,
> dashboard_id)`. The decorator runs first and short-circuits
> ('__dynamic__' is not a key in `PAGE_ACCESS_RULES`, so
> `check_page_access` falls through the "no restriction"
> branch).

(a) Why does the decorator exist if it's a placeholder? Was
    it intended to be replaced with a real check and the
    refactor stalled, or is the no-op-with-inner-check pattern
    the actual design?

(b) Is there a plan to either remove the placeholder or wire it
    to do something real?

(c) Any other view in `mysite/news/views.py` that uses
    `'__dynamic__'` the same way?

## §10. `OBSERVATORY_DASHBOARD_IDS = []` — five legacy dashboards

`prism/dashboards-portal.md` §2.2 documents:

> Five dashboards at `secondary/prism_observations/dashboards/`,
> 2 of them with missing `scripts/` folders. Phase 1 of the
> hourly runner is a no-op because `OBSERVATORY_DASHBOARD_IDS =
> []` is empty.

(a) Are these five dashboards being kept as-is (legacy
    artefacts the portal still serves but nothing refreshes), or
    are they slated for migration to the user-dashboard model
    (re-author with current SSOT, move to a `_prism_examples`-
    style system kerberos, or similar)?

(b) `leading_indicators` and `macro_lead_lags` have missing
    scripts. Are they pre-broken, mid-migration, or are the
    scripts gone for a different reason?

(c) The `_prism_examples` system-kerberos pattern referenced in
    `architecture.md` §10.5 — is anyone planning to use it for
    the Observatory dashboards, or for new curated examples?

## §11. `update_dashboard_pointer` not called from on-demand refresh

`prism/dashboard-refresh.md` §5.7 documents:

> `refresh_runner.py` (the on-demand spawned subprocess) does
> NOT call `UserManifestManager.update_dashboard_pointer`. That's
> only invoked from the hourly runner's `refresh_user_dashboards`.
> On-demand [Refresh] clicks update the registry but leave the
> manifest pointer slightly stale until the next hourly tick.
> This is intentional and harmless.

(a) Confirm "intentional" vs "lazy / overlooked". If
    intentional, what's the rationale?

(b) The manifest pointer's `last_refreshed` field — is anyone
    actually reading that pointer (vs reading the registry
    directly)? If nothing reads it for hot paths, the staleness
    is structurally fine; if something does, this is a soft bug.

## §12. The `s3_manager_unsecured` legacy bucket

`prism/code-sandbox.md` §5.1:

> `s3_manager_unsecured` — Bucket: `usratestai`. Role: Legacy.
> Marked TODO:remove.
> Used only by `generate_presigned_download_url` to copy from
> the secured bucket → unsecured bucket so the wider GS network
> can reach the URL.

(a) Is the "TODO:remove" being actioned? What replaces the copy-
    to-unsecured-bucket trick for presigned URLs (e.g. moving
    presigned URL generation to a different reachable bucket)?

(b) What's the timeline (week-of-X) and what's blocking?

## §13. `pull_fred_data` status — sandbox vs refresh runner vs L2

Three docs disagree on `pull_fred_data`'s readiness:

- `prism/code-sandbox.md` §2.5 lists it in the sandbox namespace
  (timed + partial wrapper, `output_path` aware).
- `prism/dashboard-refresh.md` §5.5 says: "Dashboards that stick
  to the four pull primitives (`pull_haver_data`,
  `pull_market_data`, `pull_plottool_data` — plus
  `pull_fred_data` once it is added) refresh cleanly with no
  caveat." (Implies `pull_fred_data` is forthcoming for the
  refresh-runner namespace.)
- `prism/api-clients.md` §6.1 says `fred_client.py` maps to
  `fred_guide` L2 module — but `code-sandbox.md` §2.14 says
  `fred_client` is NOT injected.

(a) Is `pull_fred_data` actually in `_build_exec_namespace`
    today (2026-05-XX)? If yes, the dashboard-refresh doc is
    stale. If no, when does it land?

(b) Is the underlying `fred_client` module supposed to be in
    the sandbox namespace, or is `pull_fred_data` the only
    fred-touching name the LLM ever sees?

# TIER 3 — minor inconsistencies (one-line acks fine)

For each of these, a one-line confirm/deny + a one-line "intent" is
enough. No verbatim source needed unless trivial.

## §14. The QC prompt's "FIVE categories" header

`vision-qc.md` §3 paste of `QUALITY_CHECK_PROMPT` says
"evaluate the chart across FIVE categories" but enumerates SIX
(the 6th is annotation placement validity).

Is this still in the live prompt? Cosmetic fix planned, or stays?

## §15. `wikipedia_client` imported despite not in `__all__`

`api-clients.md` §4.1 documents that `wikipedia_client` is
imported by `script_exec_tools.py` from
`ai_development.mcp.clients` even though it's NOT in that
package's `__init__.py`'s `__all__`. Submodule fallback works,
but it's intent-asymmetric.

Bug, drift, or intentional?

## §16. `describe_image` (singular) shim

`mcp-utils.md` §4.1 says:

> The injected name in the sandbox namespace is `describe_images`
> (plural) — there is no singular `describe_image` injected. The
> local stub at `projects/altair/ai_development/mcp/utils/
> vision_functions.py` exposes a `describe_image` (singular) shim
> for legacy callers; that shim does not exist in PRISM.

Is there any PRISM code path that still calls `describe_image`
(singular)? If yes, what triggers the shim?

## §17. `validate_dashboard_spec` legacy alias

`dashboard-refresh.md` §5.5 documents that
`_build_exec_namespace` registers both `validate_manifest` and
`validate_dashboard_spec` as the same callable.

(a) Anything currently still calling `validate_dashboard_spec`?
    If no, is the alias scheduled for removal?

## §18. `chart_functions_helper.py` (resolved sentinel)

`codebase-tree.md` §3.5 has:

> RESOLVED 2026-04-26: `chart_functions_helper.py` (mentioned
> in earlier docs as the interactive companion) is gone. Its
> role moved to `chart_functions_studio.py`.

Confirm `chart_functions_helper.py` no longer exists in PRISM
(`mcp/utils/`).

## §19. F19 — `openfigi_client.py` transport

Open in `gs-proxy.md` §11.2 / `api-clients.md` §11.2.

Two earlier scans disagreed on whether `openfigi_client.py`
imports from `gs_app_proxy_negotiate.py`. The §5 file-body
inspection said NO; the §9 shared-helper grep said YES.

Resolve: paste the current top-of-file imports from
`mcp/clients/openfigi_client.py`. Does it import
`session_and_auth` or `manual_https_request`? If neither, is
that intentional (openfigi works direct via vanilla `requests`)?

## §20. F20 / F21 — verbatim source policy

`gs-proxy.md` §11.2 / `api-clients.md` §11.2 carry these as
"PRISM declined to paste verbatim source on policy grounds".

(a) Is the policy still binding for `mcp/gs_app_proxy_negotiate.py`
    and `mcp/clients/<src>_client.py` files? Or has it
    softened?

(b) If still binding: is `list_ai_repo(file_paths=[...],
    mode="full")` from a PRISM session — run by the user, with
    the raw output captured — the only path?

(c) Is there a different in-band tool (e.g. `read_internal_repo`,
    a developer-mode flag, or a `signatures-only` mode that's
    less restricted) that gets us byte fidelity for these files?

---

# Reply structure

Reply with one heading per section number (`## §1.`, `## §2.`,
…). Inside each, structure freely — tables, fenced code blocks,
short prose — but cite file paths and line ranges for verbatim
quotes. Where a section has sub-questions (§1, §3, §4, etc.),
answer each sub-letter (a, b, c, …) explicitly so they're easy
to fold back into `prism/`.

For sections where you cannot answer (policy decline, file
missing, symbol unstable), say so by section number in a final
`## Could not resolve` block. Do not skip a section silently.

If at any point your introspection produces a fact that
contradicts what this prompt assumed, FLAG IT in that section's
reply with `> NOTE: prompt assumption mismatch — <what>` so the
contradictions get a sentinel-style call-out.

No paraphrasing where source-pasting is asked for. No
summarising where the question is structural.
