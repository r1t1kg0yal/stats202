---
session: dashboards v2 architecture redesign — engine import-path verification
sent: 2026-05-04
reply: (paste reply markdown into projects/echarts/dev/scans/2026-05-04_dashboards_v2_engine_imports_reply.md)
reply_folded_into:
  - projects/echarts/echarts-payload/dashboards.md (Rule 5 + §6 cheat sheet — confirm/correct the s3_manager kwarg signature for every pull primitive)
  - projects/echarts/echarts-payload/dashboards/recipes.md (transforms hook examples — confirm the canonical alt-data client import paths)
  - projects/echarts/echarts-payload/dashboards/pipelines.md (§2 pipeline cataloging table — confirm save_artifact signature and import path)
  - projects/echarts/echarts-payload/dashboards/widget_tool.md (no change expected; cross-check that compute_js authoring is unaffected by the new pull/build shape)
  - prism/data-functions.md (if any signature changed: bump _as of and re-cite)
  - prism/api-clients.md (confirm registry-key → client-module → import-path mapping)
status: OPEN
---

Title: dashboards v2 — verify engine import paths so the new pull_data.py / build.py shape works without namespace injection

The Cursor staging side just landed a v2 of the echarts dashboards architecture. The big change: PRISM-authored `scripts/pull_data.py` and `scripts/build.py` now use **real Python imports** for their helpers (no namespace injection at exec time). The new payload entry points (`run_pull(folder, name)`, `build_dashboard(folder)`, `refresh_dashboard(folder)`) exec those scripts against `__builtins__` only — no `s3_manager` / `pull_*_data` / `compile_dashboard` is injected. Each script imports what it needs.

For this to work in PRISM, every helper a `pull_data.py` or `build.py` might need must be importable from a stable PRISM-side module path AND must accept `s3_manager` as an explicit kwarg (so the script can pass the canonical singleton). This prompt is the verification round-trip.

Use `execute_analysis_script` (`inspect.signature`, `inspect.getsourcefile`, `import` checks) and `list_ai_repo` to introspect. Reply with verbatim signatures + exact file paths in fenced code blocks. Mirror the section structure below.

---

## 1. Pull primitives — signatures + s3_manager kwarg

For each of the four pull primitives below, paste:

- The verbatim function signature (`inspect.signature(fn)`)
- The source-file path (`inspect.getsourcefile(fn)`)
- The full module path PRISM-authored code should import from

Specifically: confirm each accepts an `s3_manager` keyword argument explicitly (i.e. PRISM-authored code can do `pull_haver_data(codes=[...], name='cpi', output_path=..., s3_manager=s3_manager)`).

```
1.1  pull_haver_data
1.2  pull_market_data
1.3  pull_plottool_data
1.4  pull_fred_data
```

If any does NOT currently accept `s3_manager` as an explicit kwarg, flag it — the v2 dashboards skill assumes it does. The fallback today (`functools.partial(fn, s3_manager=s3_mgr)` inside `_build_exec_namespace`) is what we're trying to delete; that injection-pattern only works because the script was exec'd into a custom namespace.

## 2. `save_artifact` — signature + s3_manager kwarg

Same shape as §1: paste the verbatim signature, source-file path, module path. Confirm `s3_manager` is an explicit kwarg. The v2 skill examples use:

```python
save_artifact(records, name='gs_bank',
              output_path=f'{SESSION_PATH}/data',
              s3_manager=s3_manager)
```

## 3. Alt-data client modules — direct importability

For each alt-data client below, paste:

- The full module path (e.g. `ai_development.mcp.clients.fdic_client`)
- The exported singleton or class name (e.g. `fdic_client` or `FDICClient`)
- A 1-line example of how a `pull_data.py` would import it

```
3.1  fdic_client
3.2  sec_edgar_client
3.3  bis_client
3.4  treasury_client
3.5  treasury_direct_client
3.6  prediction_markets_client
3.7  openfigi_client
3.8  substack_client
3.9  wikipedia_client
3.10 nyfed_client
3.11 coalition / inquiry helpers (paste their actual import path; the
     names "Coalition" and "Inquiry" come from the L2 module; the
     callable / class entry point may be different)
```

For each, also confirm whether it requires explicit `s3_manager` wiring at construction time, or whether the singleton already binds the canonical s3_manager internally.

## 4. `s3_manager` itself — canonical import path

Paste the full module path PRISM-authored code should use to import the canonical S3 manager singleton. The v2 skill assumes:

```python
from ai_development.core.s3_bucket_manager import s3_manager
```

Confirm this is the canonical path. If it has moved (e.g. to `ai_development.core.s3` or some other location), paste the new path + the date the move happened.

## 5. `compile_dashboard` family — sandbox-injected vs directly importable

Today the engine entry points (`compile_dashboard`, `populate_template`, `manifest_template`, `validate_manifest`, `df_to_source`, `chart_data_diagnostics`) are injected into the `execute_analysis_script` sandbox namespace. Under v2, the new `build_dashboard(folder)` calls them internally; PRISM rarely calls them directly anymore. But for completeness, confirm each is also importable via:

```python
from ai_development.dashboards import (
    compile_dashboard, populate_template, manifest_template,
    validate_manifest, df_to_source, chart_data_diagnostics,
    load_manifest, save_manifest,
)
```

This matters for the new helpers themselves (`run_pull` / `build_dashboard` / `refresh_dashboard` import these primitives via `from echart_dashboard import ...` inside the same package).

## 6. `update_user_manifest` wrapper — import path

Confirm PRISM-authored Tool 3 code can call `update_user_manifest(KERBEROS, artifact_type='dashboard')` either via the sandbox namespace OR via `from ai_development.mcp.utils.data_functions import update_user_manifest` (paste whichever is canonical). The v2 skill's Tool 3 walkthrough assumes one of the two paths is stable.

## 7. Sandbox namespace under v2 — what changes?

The current `execute_analysis_script` namespace injects `pull_*_data`, `save_artifact`, `s3_manager`, `compile_dashboard`, `populate_template`, etc. as bare names. Under v2, PRISM-authored `pull_data.py` and `build.py` use real imports for everything. Question: does the SANDBOX-injected namespace need to change?

Specifically:

- Does the sandbox still inject these bare names for the in-session ephemeral code that PRISM writes BEFORE persisting `pull_data.py` / `build.py`? (Recipe 1 Tool 1 / Tool 2 still uses bare names like `pd`, `np`, `s3_manager` in the ephemeral script that authors + persists the scripts.)
- Or should the sandbox start nudging PRISM to use real imports too?

The v2 hub keeps the sandbox-injected names for ephemeral session code (per §1 of dashboards.md). The change is only in the persisted scripts. Confirm this distinction is clean — there's no PRISM-side enforcement that REQUIRES persisted scripts to use real imports today; the v2 skill TEACHES it via the templates, but a non-conforming `pull_data.py` would still work in the sandbox (wrong) and fail in the runner (right).

If you'd like to enforce the real-import pattern at the runner level (refuse to exec a `pull_data.py` that doesn't define `PULLS = {...}` at module level), that's a one-liner in `_exec_dashboard_script`; we can add it in a follow-up.

---

If part of this cannot be answered, add `## Could not resolve` at the end listing what you tried + what blocked it (file missing, function moved, import raised). This is NOT a frictions report — it's a coverage note.
