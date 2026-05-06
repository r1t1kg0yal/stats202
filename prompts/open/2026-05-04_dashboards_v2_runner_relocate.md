---
session: dashboards v2 — verify call sites that import from ai_development.jobs.refresh_runner so the runner-file relocation handoff carries the right diff
sent: 2026-05-04
reply: (paste reply markdown into projects/echarts/dev/scans/2026-05-04_dashboards_v2_runner_relocate_reply.md)
reply_folded_into:
  - staging/prompts/open/2026-05-04_dashboards_v2_handoff.md (the consolidated handoff prompt — the verbatim views.py + entrypoint.py diffs land there)
  - prism/dashboard-refresh.md (§3 spawning section + §5 runner walkthrough — bump _as of, point at the new path)
  - projects/frontend/dev/scans/ (if views.py + dashboards portal need changes — flag for the frontend-side rewire)
status: OPEN
---

Title: dashboards v2 — locate every call site that imports / spawns ai_development.jobs.refresh_runner so the relocation handoff has a complete diff

Context: the Cursor staging side is bringing the dashboard refresh runner scripts into the echarts payload (`projects/echarts/echarts-payload/refresh_runner.py` + `refresh_dashboards.py`). The new payload destination is `ai_development/dashboards/refresh_runner.py` + `ai_development/dashboards/refresh_dashboards.py` — co-located with the engine. The current PRISM paths are `ai_development/jobs/refresh_runner.py` and `ai_development/jobs/hourly/refresh_dashboards.py`.

Before I draft the consolidated handoff prompt that lays out the relocation diff, I need to know **every place in PRISM that references the old paths** — by import, by string (subprocess paths), by docstring / comment. The handoff needs to update them all in lockstep with the move.

Use `list_ai_repo` (`mode="full"` on specific files; `mode="signatures"` on broader directories) to introspect. Reply with verbatim source pasted in fenced code blocks and exact paths. Mirror the section structure below.

---

## 1. Django side — the Refresh button handler

Paste the verbatim body of `refresh_dashboard_api` in `mysite/news/views.py`. Specifically I need to see:

- The line that resolves `refresh_runner_path` (today it walks `os.path.dirname(...)` four levels up from `__file__` and joins with `"ai_development/jobs/refresh_runner.py"`)
- The `subprocess.Popen([sys.executable, refresh_runner_path, ...])` invocation
- Any other reference to `ai_development.jobs` or `refresh_runner` in this file

Also paste the URL routes (`mysite/news/urls.py`) for `/api/dashboard/refresh/` and `/api/dashboard/refresh/status/` — confirm they map to `refresh_dashboard_api` + `refresh_status_api` respectively, with no other indirection.

## 2. Cron side — the hourly refresh entrypoint

Paste the verbatim body of `entrypoint.py`'s `fifteen_minute_context_generator` (or whatever function invokes the refresh). Specifically I need:

- The import line that pulls in `ai_development.jobs.hourly.refresh_dashboards` (or similar)
- The function call that runs the cron-side refresh (likely `refresh_dashboards.main()` or equivalent)
- Any other reference to `ai_development.jobs.hourly` or `refresh_dashboards` in this file

## 3. Other call sites — full search

Use `list_ai_repo` to grep across `ai_development/` for any other references to:

- `ai_development.jobs.refresh_runner`
- `ai_development.jobs.hourly.refresh_dashboards`
- The literal strings `"refresh_runner.py"` and `"refresh_dashboards.py"`
- Any module that does `from ai_development.jobs ...`

Paste each call-site verbatim with file path + line number. I need to know about every consumer so the handoff diff is exhaustive.

## 4. Internal cross-references between the two runner files

The current `refresh_runner.py` imports `_build_exec_namespace` and `_sort_scripts_by_dependency` from `ai_development.jobs.hourly.refresh_dashboards`. Paste the verbatim import line + a 3-line context window around it.

This matters because the v2 runner files DON'T have these helpers (the `_build_exec_namespace` model is replaced by real Python imports in the persisted scripts; `_sort_scripts_by_dependency` is moot under v2 since the runner just calls `refresh_dashboard(folder)` which runs PULLS in declared order then `build_dashboard`). So this internal import disappears entirely under v2.

## 5. The `_normalize_script` legacy compat layer

The current `refresh_dashboards.py` carries `_normalize_script(...)` that string-substitutes legacy generator paths into the new dashboards path (looking for `secondary/prism_observations/generators/<old_id>/workstation` and rewriting). Paste the verbatim function body + confirm whether any production dashboard still depends on this rewriting today (i.e. is there a registry entry whose persisted scripts contain those legacy paths?).

If no live dashboard depends on it, the helper goes away in v2. If some do, the handoff needs to call out that those scripts must be re-authored / migrated before the runner relocation.

## 6. Observatory dashboards Phase 1

The current `refresh_dashboards.py` `main()` has a Phase 1 / Phase 2 split. Phase 1 walks `OBSERVATORY_DASHBOARD_IDS = []` (empty as of the last scan; legacy dashboards retired). Confirm:

- Is `OBSERVATORY_DASHBOARD_IDS` still empty? Paste its current value verbatim.
- Are any Observatory dashboards refreshed via this Phase 1 loop today, or has the responsibility moved elsewhere?

If Phase 1 is dead, the v2 `refresh_dashboards.py` drops it entirely (the new file just walks `UserRegistry.get_all_kerberos_ids()` once and spawns `refresh_runner.py` per due dashboard — no Phase 1, no Phase 2 split, no Observatory legacy).

## 7. Documentation references

Search `prism/` (NOT just `ai_development/`) for any markdown that cites the old paths. Specifically `prism/dashboard-refresh.md` will need a §3 / §5 update to point at the new location. Paste any existing line in that file that references `ai_development/jobs/refresh_runner.py` or `ai_development/jobs/hourly/refresh_dashboards.py` so the handoff catches them.

---

If part of this cannot be answered, add `## Could not resolve` at the end. The handoff prompt I'm drafting next depends on this reply being complete — anything missing here becomes a blocker for the relocation move.
