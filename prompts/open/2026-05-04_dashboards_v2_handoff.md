---
session: dashboards v2 architecture redesign — consolidated PRISM-side change set (the handoff prompt)
sent: 2026-05-04
reply: (paste reply confirming the diff has been applied; reply lands at projects/echarts/dev/scans/2026-05-04_dashboards_v2_handoff_reply.md)
reply_folded_into:
  - prism/dashboard-refresh.md (§3 spawning + §5 runner walkthrough — point at new dashboards/ paths; drop the namespace-injection / partial-wired explanations now obsolete)
  - prism/architecture.md §6 (dashboards subsystem — co-located runners + engine)
  - prism/codebase-tree.md (file map — refresh_runner.py + refresh_dashboards.py move from jobs/ to dashboards/)
  - prism/_changelog.md (one-line entry per the curation policy)
  - staging/README.md echarts row (bump to v2 with new payload contents)
status: OPEN — DEPENDS on the two precursor prompts (engine-imports + runner-relocate replies) being received first
---

Title: dashboards v2 — consolidated PRISM-side change set (relocate runners, drop namespace injection, install the new payload)

This is the handoff prompt for the dashboards v2 architecture redesign. It assumes:

1. The `2026-05-04_dashboards_v2_engine_imports.md` reply confirmed every helper accepts `s3_manager` as an explicit kwarg and is directly importable from a stable PRISM-side module path.
2. The `2026-05-04_dashboards_v2_runner_relocate.md` reply enumerated every call site that today imports from `ai_development.jobs.refresh_runner` / `ai_development.jobs.hourly.refresh_dashboards`.

Apply the changes below in the listed order. Each step is independent enough to verify on its own; the sequence keeps the live system runnable between steps (no orphaned import). The new payload files are in the staging repo at `projects/echarts/echarts-payload/`; copy them into PRISM at the destinations called out below.

---

## 1. Drop the new echarts payload into `ai_development/dashboards/`

Copy the contents of `staging/echarts-payload/` (drop the staging copy; the canonical lives at `projects/echarts/echarts-payload/`) into PRISM at `ai_development/dashboards/`. The byte-identical-payload contract holds. Files (and what each does):

| File | Status | Role |
|---|---|---|
| `__init__.py` | UPDATED (re-exports new helpers) | `from ai_development.dashboards import build_dashboard, run_pull, refresh_dashboard, ...` |
| `echart_dashboard.py` | UPDATED (added `run_pull` / `build_dashboard` / `refresh_dashboard` + `_resolve_s3_manager` + `_exec_dashboard_script` near the bottom; `__all__` extended) | Engine + the three new folder-operation entry points |
| `echart_studio.py` | UNCHANGED | Internal single-chart builder |
| `config.py` | UNCHANGED | Brand tokens + theme + palettes |
| `rendering.py` | UNCHANGED | Editor HTML + dashboard HTML + headless-PNG export |
| `refresh_runner.py` | NEW (was at `ai_development/jobs/refresh_runner.py`) | Single-dashboard refresh CLI: `python -m ai_development.dashboards.refresh_runner --folder users/<k>/dashboards/<id> [--log-path <log>]`. Phase tracker tags each error with `script: scripts/pull_data.py::<pull_name>` / `scripts/build.py` / `<registry>` so the §8.1 modal's script pill populates. Heuristic exception classifier maps to `data_pull_empty` / `network_error` / `data_schema_error` / `compile_failed` / `missing_artifact` / `<exception class>`. Status JSON timestamps Z-suffixed to match existing registry entries. |
| `refresh_dashboards.py` | NEW (was at `ai_development/jobs/hourly/refresh_dashboards.py`) | Hourly cron entry point: walks `UserRegistry`, per due dashboard spawns `refresh_runner.py --folder X --log-path Y` subprocess. Spawn-time failures are caught per-dashboard so one bad spawn cannot crash the cron pass. After every successful refresh, calls `UserManifestManager.update_dashboard_pointer(kerberos)` once per affected user (per `prism/dashboard-refresh.md` §7) so the manifest pointer block stays current across hourly ticks -- the on-demand `[Refresh]` path remains intentionally pointer-stale per §5.7. Cron summary distinguishes `disabled=N` vs `not_due=N` skip categories. |

The two new runner files use **real Python imports** with **no fallbacks** — `from ai_development.dashboards import refresh_dashboard`, `from ai_development.core.s3_bucket_manager import s3_manager`, `from ai_development.core.common import UserRegistry`. The old `try: import ai_development.jobs.refresh_runner / except: ...` fallback pattern is gone.

The new `refresh_dashboards.py` does NOT carry: `_build_exec_namespace`, `_normalize_script`, `_sort_scripts_by_dependency`, the headless `ChartResult` / `ChartSpec` / `make_chart_headless` / `make_multipack_headless` stubs, the `OBSERVATORY_DASHBOARD_IDS` Phase 1 split, the `try/except` import fallbacks. All of that is obsolete under the v2 model: scripts use real imports; the runner just calls `refresh_dashboard(folder)` per due dashboard.

## 2. Delete the old runner files at `ai_development/jobs/`

After step 1 is in place, delete:

- `ai_development/jobs/refresh_runner.py`
- `ai_development/jobs/hourly/refresh_dashboards.py`

If `ai_development/jobs/hourly/` becomes empty, delete that directory too. If `ai_development/jobs/` carries only the `refresh_runner.py` we just deleted, delete the directory. (Confirm via `list_ai_repo` before deleting; the runner-relocate reply should have enumerated everything in `jobs/`.)

## 3. Update `mysite/news/views.py refresh_dashboard_api`

The current Popen invocation walks `os.path.dirname(...)` four levels up from `__file__` and joins with `"ai_development/jobs/refresh_runner.py"`. Replace that with:

```python
import ai_development.dashboards.refresh_runner as _rr
refresh_runner_path = _rr.__file__
```

This single-line change is the canonical resolution path — no string-based path walking, no fallback. The Popen call gets one new arg (`--log-path`) so the runner can stamp the log path into `refresh_status.json` for the §8.1 modal's PRISM-triage block:

```python
proc = subprocess.Popen(
    [sys.executable, refresh_runner_path,
     '--folder',   dashboard_folder.rstrip('/'),
     '--log-path', log_file.name],          # NEW under v2
    start_new_session=True,
    stdout=log_file,
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
    cwd=repo_root,
    env=os.environ.copy(),
)
```

Note the argument shape under v2:
- The old runner took `--kerberos` / `--dashboard-id` / `--dashboard-folder` (three args). The new runner takes `--folder` (single arg; the runner parses kerberos + id from the canonical `users/<k>/dashboards/<id>` shape).
- The new optional `--log-path` is the same path Django is already streaming the subprocess's stdout/stderr to (`/tmp/dashboard_refresh/<k>_<id>_<ts>.log`). Passing it through means `refresh_status.json` carries `log_path` verbatim, which the §8.1 failure modal surfaces in its Copy-for-PRISM markdown so PRISM can grep server logs by PID + log path without round-tripping back to Django.

The runner status JSON shape under v2 also enriches the `errors[]` dict to match the §8.1 contract verbatim — each entry carries `script` (which phase failed: `scripts/pull_data.py::<pull_name>`, `scripts/build.py`, or `<registry>`), `classification` (heuristic mapping of the exception to `data_pull_empty` / `network_error` / `data_schema_error` / `compile_failed` / etc.), `message`, and `traceback`. The browser modal already accepts both the legacy string-list shape and the dict shape (per §8.1) so the wire-protocol stays compatible; the only change is that the modal's `script: …` and `classification: …` pills now actually populate.

## 4. Update the hourly cron entrypoint

Wherever `entrypoint.py` (or whatever module hosts `fifteen_minute_context_generator`) imports the hourly cron, change:

```python
# OLD
from ai_development.jobs.hourly.refresh_dashboards import main as refresh_main
refresh_main()
```

to:

```python
# NEW
from ai_development.dashboards.refresh_dashboards import main as refresh_main
refresh_main()
```

The function signature (`main()` returning `int`) is preserved.

## 5. (Optional) Drop dashboard-script namespace injection from `script_exec_tools.py`

The `execute_analysis_script` sandbox today injects `pd` / `np` / `s3_manager` / `pull_*_data` / `compile_dashboard` / `populate_template` / `manifest_template` / `validate_manifest` / etc. into the namespace as bare names. Under v2, the **persisted** `pull_data.py` and `build.py` use real Python imports for everything (no namespace dependency). The in-session ephemeral code that PRISM writes BEFORE persisting still uses bare names (per dashboards.md §1) — that's intentional.

If the engine-imports reply confirmed every name is also importable, you can incrementally start nudging PRISM toward real imports in ephemeral code too — but that's a downstream cleanup, not load-bearing for v2. The v2 hub dashboard.md skill teaches the new pattern via the recipe templates; PRISM picks it up via the templates without enforcement.

The one thing that COULD shift: the `_build_exec_namespace` machinery in `refresh_dashboards.py` (which the v2 file no longer carries) used to be the documentation for "what the runner injects into scripts". Under v2, that injection model is gone — scripts use real imports. So if any other code path uses `_build_exec_namespace` (search for callers), point it at the corresponding real-import shape.

## 6. Re-cite the `prism/dashboard-refresh.md` doc

Update `prism/dashboard-refresh.md` to reflect:

- §3 (spawning the runner): the canonical `import ai_development.dashboards.refresh_runner as _rr; refresh_runner_path = _rr.__file__` pattern; the new `--folder` single-arg shape
- §5 (runner walkthrough): the v2 runner just calls `refresh_dashboard(folder)`; no `_build_exec_namespace`, no `_sort_scripts_by_dependency`, no per-script exec loop. The `_should_refresh` / `refresh_all_user_dashboards` / `refresh_user_dashboards` / `refresh_single_user_dashboard` helpers are subsumed by the new `refresh_dashboards.py main()` (which just walks the registry once and spawns subprocess per due entry)
- §5.5 (the `_build_exec_namespace` table): delete entirely. The injected namespace is `__builtins__` only; scripts import everything they need
- §5.7 (`refresh_runner.py` body): rewrite to the new shape — single `--folder` arg, calls `refresh_dashboard(folder)`, writes status JSON, no fallback imports

Bump the `_as of` stamp; add a `_changelog.md` entry per the curation policy.

## 7. Re-cite `prism/architecture.md` §6 + `prism/codebase-tree.md`

`architecture.md` §6 (dashboards subsystem) should mention the co-located runners + the new `run_pull` / `build_dashboard` / `refresh_dashboard` entry points.

`codebase-tree.md` should reflect the file moves: `ai_development/dashboards/` gains `refresh_runner.py` + `refresh_dashboards.py`; `ai_development/jobs/` either shrinks or disappears entirely.

## 8. Verification

After steps 1-7, smoke-test end-to-end:

1. Pick a non-critical existing user dashboard. Click `[Refresh]` in the browser. Confirm `refresh_status.json` lands with `status: "success"` and the rebuilt `manifest.json` + `dashboard.html` reflect today's data.
2. Trigger the hourly cron manually (`python -c "from ai_development.dashboards.refresh_dashboards import main; main()"`). Confirm the per-dashboard subprocess spawn pattern works for at least one due dashboard.
3. Run a fresh build of a small test dashboard from a PRISM session using the new Recipe 1 (hub §B). Confirm Tools 1-4 complete cleanly with no namespace errors.

If any step fails, the failure surfaces immediately — there are no fallbacks to silently route around it. Report the failure verbatim.

---

## What this change buys

- **No more namespace-injection footguns.** Every "name X not in `_build_exec_namespace`" error class disappears. Scripts use real imports; the runner doesn't curate a namespace dict.
- **No more `subprocess.run(..., timeout=600, capture_output=True)` hangs.** The new runner uses `Popen` + log file + `wait()`. The browser's polling endpoint is the liveness check; no arbitrary 10-minute timeout that rejects legitimately slow pulls.
- **No more `try: import ai_development.jobs.refresh_runner / except: ...` fallback chains.** Single canonical import path; if the import fails, the user learns immediately.
- **One canonical recipe per user-ask shape** (hub §A.2 path-decision table) — PRISM stops reinventing build / edit / refresh orchestration per session.
- **Per-dashboard subprocess isolation in the cron.** A slow Haver pull on one dashboard cannot stall any other dashboard's refresh.
- **Folder-as-workspace model is consistent across browser-Refresh, cron, and PRISM in-session.** Same three engine entry points (`run_pull`, `build_dashboard`, `refresh_dashboard`) carry every operation.

If you'd like to defer steps 5-7 to a follow-up turn (so the runner relocation in steps 1-4 lands first as a clean diff), that's fine — the steps are independent.
