---
session: refresh_dashboards daemon install -- wire the v2 daemon mode as its own continuously-running worker (decoupled from the legacy multi-task generator sequence)
sent: 2026-05-12
class: implementation-directive (NOT context-extraction; NOT end-usage)
preconditions:
  - The echarts v2 dashboards payload has already landed via drag-and-drop. Specifically `ai_development/dashboards/refresh_dashboards.py` is the v2 file (top-of-file docstring describes "Two operating modes: 1. One-shot (default) ... 2. Daemon (--interval N)"; argparse exposes `--interval N`; `_daemon(interval_seconds)` is the forever-loop body; `_walk_once()` is the single-pass walker that legacy entrypoint.py contract calls with `main()` no-args). `ai_development/dashboards/refresh_runner.py` exists at the v2 path (NOT the legacy `ai_development/jobs/refresh_runner.py`). `ai_development/dashboards/dashboards_time.py` exists with `parse_freq` accepting both legacy enum ("hourly"/"daily"/"weekly"/"manual") and duration-string syntax ("60s"/"5m"/"1h"/"1d"/"1w"). The dashboards registries already carry per-dashboard `refresh_frequency` strings in either dialect.
files_to_modify:
  - ai_development/entrypoint.py (REMOVE the `refresh_dashboards.main()` call from the legacy multi-task generator sequence; ADD a new always-on daemon launcher that invokes `refresh_dashboards.main(['--interval', '30'])` in its own continuously-running worker at PRISM boot)
reply_folded_into:
  - confirmation back to staging once the daemon is wired and stable; staging will then update `prism/dashboard-refresh.md` §5.1 (the "Cron cadence (entrypoint)" paragraph that today says "main() is invoked from entrypoint.py's fifteen_minute_context_generator() loop") to describe the new daemon-as-its-own-worker shape; staging/README.md echarts row also closes one follow-up pointer.
status: pending
---

Title: install refresh_dashboards as its own continuously-running daemon worker, decoupled from the legacy multi-task generator

The echarts v2 payload landed earlier today shipped a `--interval N`
daemon mode on `refresh_dashboards.py` precisely so dashboards with
sub-5-minute `refresh_frequency` (e.g. `"60s"`, `"2m"`, `"5m"`) can
actually be refreshed at the authored cadence. The mode IS already
in PRISM (per the file landed in `ai_development/dashboards/`), but
it isn't being USED -- `entrypoint.py` still calls
`refresh_dashboards.main()` (no args, one-shot) from inside its
legacy multi-task generator sequence. The walk cadence is therefore
gated by whatever the slowest job in that sequence happens to be on
a given tick, which is empirically ~30 minutes today. A `"60s"`
dashboard ends up with `effective_cadence = max(30m, 60s) = 30m`,
which is what's currently being observed in the wild (chrome's
`pollLiveData()` returning HTTP 304 every minute for ~30 minutes
between actual data updates).

The fix is structural: refresh_dashboards belongs in **its own
continuously-running worker**, NOT in the multi-task generator
sequence. The legacy one-shot entry point stops being called from
entrypoint.py at all; instead, entrypoint.py starts the daemon mode
ONCE at PRISM boot and the daemon's internal forever-loop handles
walk cadence on its own.

```
                  BEFORE (current)
                  ──────────────────────────────────────────
                  entrypoint.py
                    fifteen_minute_context_generator() loop:
                      ┌─ job_a()
                      │  job_b()
                      │  ...
                      │  refresh_dashboards.main()      ← one-shot walk
                      │  ...                              gated by every
                      │  job_z()                          OTHER job above
                      └─ sleep(300)
                    repeat

                  Net: dashboards walk every ~30 min in practice
                       even though sleep(300)==5min by design,
                       because cumulative job duration overruns
                       the sleep window.

                  AFTER (target)
                  ──────────────────────────────────────────
                  entrypoint.py boot:

                      worker_1  fifteen_minute_context_generator()
                                  (whatever this does, minus the
                                   refresh_dashboards.main() call)
                                  sleep(300) -> loop

                      worker_2  refresh_dashboards.main(
                                  ['--interval', '30']
                                )
                                  ─► _daemon(30) forever-loop:
                                     - _walk_once()  (~10s for 100 users)
                                     - sleep(30 - walk_time)
                                     - repeat

                  Net: dashboards walk every ~30s independent of
                       any other job's duration. "60s" dashboards
                       see effective cadence ~60-90s. "5m" dashboards
                       see ~5min. "daily" dashboards see ~20h.
                       The walk is cheap; the cost is per-dashboard
                       refresh_runner.py spawn time, gated by _is_due.
```

Two concrete edits inside `ai_development/entrypoint.py`:

  1. **Remove the `refresh_dashboards.main()` call** from
     `fifteen_minute_context_generator()` (or whichever function in
     entrypoint.py currently calls it from inside a sleep-and-loop
     cycle). If the existing call site has any pre-call logging
     (`[15MIN] Dashboard refresh starting` / etc.), remove that too.
     If it has surrounding try/except scaffolding specific to that
     one call, remove that too.

  2. **Add a new always-on daemon launcher** that starts at PRISM
     boot (the same place entrypoint.py boots its other worker
     threads / processes -- match the existing convention).
     Recommended shape -- a subprocess.Popen with
     `start_new_session=True` so the daemon survives parent
     stdin/stdout shutdowns:

     ```python
     # --- dashboard refresh daemon ---
     # The v2 refresh_dashboards.py supports a --interval N mode that
     # loops forever, walking the registry every N seconds. We run
     # this as its own dedicated subprocess (decoupled from the
     # multi-task generator) so the dashboard walk cadence is NOT
     # gated by the duration of other jobs in the multi-task cycle.
     # Without this, dashboards with sub-5-minute refresh_frequency
     # silently degrade to whatever the multi-task cycle wall-clock
     # ends up being (~30 minutes in practice today).
     import subprocess as _subprocess
     import sys as _sys
     _refresh_dashboards_daemon = _subprocess.Popen(
         [_sys.executable, "-m",
          "ai_development.dashboards.refresh_dashboards",
          "--interval", "30"],
         start_new_session=True,
         stdout=_subprocess.DEVNULL,
         stderr=_subprocess.DEVNULL,
         stdin=_subprocess.DEVNULL,
     )
     ```

     Or, if entrypoint.py boots workers as threads rather than
     subprocesses, the equivalent thread shape:

     ```python
     import threading as _threading
     from ai_development.dashboards import refresh_dashboards as _rd
     _refresh_dashboards_thread = _threading.Thread(
         target=lambda: _rd.main(["--interval", "30"]),
         daemon=True,
         name="refresh_dashboards_daemon",
     )
     _refresh_dashboards_thread.start()
     ```

     Pick whichever shape matches entrypoint.py's existing worker
     conventions (subprocess vs thread). Subprocess is the
     stronger isolation; thread is cheaper. If unsure, default
     subprocess -- the daemon's forever-loop is non-trivial state
     to keep inside the parent Python interpreter, and a daemon
     crash (e.g. an UnhandledExceptionError in `_walk_once`) is
     easier to recover from when it's its own process.

A subtle correctness consideration -- the daemon's `_walk_once()`
spawns `refresh_runner.py` per due dashboard via Popen + wait. The
on-demand `[Refresh]` button in views.py ALSO spawns
`refresh_runner.py` for the same single dashboard. Both paths write
to the same `refresh_status.json` and the same `dashboards_registry.json`.
The existing three-tier conflict detection in `refresh_dashboard_api`
(`prism/dashboard-refresh.md` §4) handles this concurrency cleanly:
if a daemon-spawned refresh is already running for a given
dashboard, the on-demand POST sees `status == "running"` with a live
PID and returns HTTP 409 `already_refreshing`. So the daemon and
the [Refresh] button coexist safely.

Reply with:

  - a single `## Confirmation` block listing the entrypoint.py
    file:line ranges actually edited, the daemon launch shape
    chosen (subprocess vs thread), the line where the daemon
    launcher is invoked at boot, and the line(s) where the legacy
    `refresh_dashboards.main()` call was removed.
  - a `## Boot log evidence` block quoting (verbatim) the first
    couple of lines of PRISM's startup log AFTER the change,
    proving the daemon process / thread is running. Specifically,
    the daemon's `[refresh_dashboards] daemon mode interval=30s`
    line (emitted by `_daemon` on entry) should appear in stdout
    or in `/tmp/dashboard_refresh/...` log shortly after boot.
  - a `## Frictions` section IF anything in this spec did not apply
    cleanly (e.g. entrypoint.py's worker bootstrap pattern doesn't
    match either the subprocess or thread shape above, or the
    multi-task generator's structure has dependencies on
    refresh_dashboards.main() being called inline, or PRISM has
    other consumers of `refresh_dashboards.main()` that need
    co-migration). No friction = no section.

This is an **implementation directive**, not a context-extraction
prompt. Do not paste back signatures or docstrings unless they're
load-bearing for a friction note. Edit the file, confirm what
changed, surface any frictions.

---

## 1. Why this is the right architecture

`refresh_dashboards.py`'s docstring is explicit about the two
modes and the cadence floor (lines 22-53 of the v2 file):

```
Two operating modes:

1. **One-shot** (default): main() (no args) does a single walk and
   exits. Preserves the legacy entrypoint.py contract -- PRISM's
   fifteen_minute_context_generator calls main() every 5 minutes
   and the walk takes ~10s for 100 users.

2. **Daemon** (--interval N): python -m refresh_dashboards
   --interval 30 loops forever, walking every N seconds. Use this
   when the legacy 5-minute context cycle is too coarse for
   sub-5-minute dashboard cadences. The walk itself is cheap
   (~10s for 100 users); the expensive spawns are gated by _is_due
   so most ticks are skip-only.

Cadence floor: effective_refresh = max(walk_interval, refresh_frequency).
A "60s" dashboard with the daemon walking every 30s lands within
~60-90s of every tick; with the legacy one-shot path at 5min, "60s"
effectively becomes "every 5 minutes". Pick --interval to match the
SHORTEST refresh_frequency in the registry.
```

The one-shot path was always a back-compat shim for the legacy
contract. The intended steady-state shape was always daemon mode;
moving entrypoint.py over is the clean cutover.

After the change, the legacy one-shot entry point (`main()` with
no args) is still kept in the file for two reasons:

  - hand-invoked debugging (`python -m ai_development.dashboards.refresh_dashboards`
    on a developer box does one walk and exits, useful for testing)
  - eventual decommission needs to be done in one cleanup pass
    after the daemon proves stable in production for a couple weeks

So no code is removed from `refresh_dashboards.py` itself. The
ONLY change is in `entrypoint.py`.

---

## 2. Where in entrypoint.py the call site is today

The legacy call site is described in `prism/dashboard-refresh.md` §5.1:

```
Cron cadence (entrypoint). main() is invoked from
entrypoint.py's fifteen_minute_context_generator() loop. Despite
the function name, the actual time.sleep(15 * 20) between cycles is
300 s (5 minutes), not 15 minutes. So _should_refresh()'s
>=1h / >=20h / >=160h thresholds (§5.3) are evaluated every
~5 minutes against the registry's last_refreshed field. The
function is wrapped in a try/except that prints
[15MIN] Dashboard refresh completed / [15MIN][ERROR] Dashboard
refresh failed: <e> -- a runtime exception in the runner does not
crash the parent loop.
```

So the call site is:

  - **function**: `fifteen_minute_context_generator()` (or however
    it's renamed today)
  - **shape**: inside the sleep-and-loop body, between other jobs;
    wrapped in try/except with `[15MIN]` log prefix
  - **what to remove**: the `refresh_dashboards.main()` call plus
    its try/except scaffolding plus its `[15MIN]` logger lines

If the legacy call site has been renamed / moved / split since the
2026-04-26 scan documented it, fold those facts into the
`## Confirmation` block so staging can update
`prism/dashboard-refresh.md` §5.1 in lockstep.

---

## 3. Daemon shape decision -- subprocess vs thread

Both shapes work. Pick by matching entrypoint.py's existing worker
conventions:

| Concern | Subprocess (recommended) | Thread |
|---------|--------------------------|--------|
| Crash isolation | full -- daemon segfault / OOM doesn't take PRISM down | shared interpreter -- exception escapes the thread, daemon=True silently lets the thread die without restarting it |
| Restart on crash | external supervisor (or just leave restart to next PRISM boot; the impact of a missed walk window is at most one tick's worth of refreshes) | manual restart logic needed or just leave it dead and lose dashboard refresh until next PRISM boot |
| Log surface | own stdout/stderr; entrypoint.py points them at /tmp/dashboard_refresh/ if it wants | mixed into PRISM's main log; daemon's verbose `[refresh_dashboards] -> users/x/dashboards/y` lines pollute the parent's stream |
| Memory | ~50MB extra (Python interpreter + pandas) | zero |
| GIL contention | none (own interpreter) | minor -- daemon spends most of life in `proc.wait()` which releases GIL, but the inter-tick walk does touch pandas |
| Lifecycle | `Popen.terminate()` on shutdown; `start_new_session=True` lets it survive parent stdin closure if desired | `daemon=True` thread dies with PRISM process |

Default subprocess. The expected daemon footprint (one Python
interpreter + the same pandas / boto3 / s3_manager stack PRISM
already has) is small relative to PRISM's overall process size.
The crash-isolation upside is meaningful.

---

## 4. What does NOT change

  - `refresh_dashboards.py` itself (file already has the daemon mode)
  - `refresh_runner.py` (still spawned per due dashboard by the daemon's `_walk_once`, same as today)
  - `views.py::refresh_dashboard_api` (the [Refresh] button still spawns refresh_runner.py directly; the three-tier conflict detection handles concurrency with the daemon's spawns)
  - `dashboards_registry.json` schema (the daemon reads + spawns; the spawned `refresh_runner.py` writes)
  - `refresh_status.json` schema (same)
  - User-manifest pointer update path (`_update_user_manifests` post-walk, unchanged)
  - Any of the chrome JS in `rendering.py` (the pollLiveData loop is agnostic to who advances `registry.last_refreshed`)
  - The other open prompt at `staging/prompts/open/2026-05-11_views_py_time_refresh_uplift.md` (independent workstream; coexists fine)

This is a minimal-surface change with one purpose: stop gating the
refresh walk cadence on the multi-task generator's wall clock.

---

## 5. Acceptance criteria

After this lands and PRISM has been running for at least one cycle:

  1. `/tmp/dashboard_refresh/` (or wherever entrypoint.py points the
     daemon's stdout) shows `[refresh_dashboards] starting at <ISO>`
     lines every ~30 seconds.
  2. For a dashboard authored with `refresh_frequency: "60s"`,
     consecutive `last_refreshed` values in
     `users/<kerberos>/dashboards/dashboards_registry.json`
     are 60-120 seconds apart (one walk-interval of jitter).
  3. The chrome's `pollLiveData()` returns HTTP 200 (not 304)
     within ~60-120 seconds of the data underlying the dashboard
     changing; the in-place data swap fires; no `location.reload()`.
  4. `[15MIN] Dashboard refresh completed` lines DO NOT appear in
     PRISM's main log anymore (because the multi-task generator no
     longer calls `refresh_dashboards.main()`).
  5. PRISM's main multi-task generator still ticks every ~5
     minutes through its OTHER jobs at their previous cadence.
     The dashboard daemon being decoupled does not change the
     pace of any other entrypoint.py work.

---

## 6. Anti-patterns -- do not do these

  1. **Do not** keep the multi-task generator's
     `refresh_dashboards.main()` call AND add the daemon. Two
     consumers walking the same registry will fight on
     `refresh_status.json` (one writes "running" while the other
     reads it; three-tier conflict detection will see ghost-lock
     scenarios). Pick one path; the daemon is the one.

  2. **Do not** route the daemon's stdout into a logger that
     bubbles up into Slack / pagerduty / etc. The daemon prints
     `[refresh_dashboards] -> users/...` and `[refresh_dashboards]
     done elapsed=...` lines every walk. Useful for triage, noisy
     in alerting. Default `subprocess.DEVNULL` if PRISM already
     captures the file at `/tmp/dashboard_refresh/...`; the
     spawned `refresh_runner.py` already writes its own log there.

  3. **Do not** change `--interval 30` to anything below 15s
     without verifying the walk itself stays under that bound. A
     30s interval gives the walk room to grow to ~25s in the
     worst case before ticks start backing up. With 100 users +
     2-3 dashboards each, walk time is ~10s steady-state; 30s
     interval has 20s of headroom.

  4. **Do not** edit `prism/dashboard-refresh.md` §5.1 to "match"
     the new architecture pre-emptively. That doc describes LIVE
     PRISM behaviour; staging will update it via the
     `reply_folded_into` confirmation loop AFTER this change lands.

  5. **Do not** assume entrypoint.py's worker conventions match
     either the subprocess or thread shape above without reading
     the file first. The `## Frictions` block exists exactly to
     surface a mismatch.

---

## 7. Cross-references

  - The v2 daemon mode docstring + cadence-floor math:
    `ai_development/dashboards/refresh_dashboards.py` (top docstring + lines 22-53)
  - The legacy call site (one-shot path described):
    `prism/dashboard-refresh.md` §5.1 "Cron cadence (entrypoint)"
  - Why minutely auto-refresh needs this fix:
    chrome's `pollLiveData` returns 304 forever while
    `registry.last_refreshed` doesn't advance; advancing it requires
    the daemon (or [Refresh] click) to walk + spawn refresh_runner.py
  - Three-tier conflict detection (handles daemon + on-demand
    spawns competing for the same dashboard):
    `prism/dashboard-refresh.md` §4
  - User-manifest pointer update (still cron-side; unchanged):
    `prism/dashboard-refresh.md` §7

---

## 8. Single-line summary for changelog

> entrypoint.py wired refresh_dashboards as a continuously-running
> daemon (`--interval 30`) decoupled from the multi-task generator
> sequence, eliminating the structural cap on per-dashboard refresh
> cadence imposed by other jobs' duration in the sequence
