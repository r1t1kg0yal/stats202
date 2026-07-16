---
class: end-usage
topic: entrypoint-site-open-refresh
status: SUPERSEDED
created: 2026-07-16
superseded_on: 2026-07-16
superseded_by: staging/prompts/archive/2026-07-16_django_entrypoint_refresh_visibility.md
depends_on:
  - staging/prompts/archive/2026-07-16_django_light_refresh_presence_wire.md
prerequisite_payload:
  - jobs/hourly/refresh_dashboards.py  # --open-interval alone = open-only daemon
  - prism-core/dashboards/refresh_runner.py  # --mode light|full
---

# PRISM patch prompt — Change 4: `entrypoint.py site` starts **open-only** light refresh

**SUPERSEDED 2026-07-16.** Afternoon visibility extraction confirmed
`entrypoint.py site` already spawns
`refresh_dashboards.py --open-interval N` with no `--interval`, plus
`--no-open-refresh` / `--open-interval` flags. Do not re-apply this
patch. Retained for audit only.

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Presence + light Refresh button already work. Logs show presence `200`
and data `304`/`cache_hit` — nothing is light-refreshing open tabs
automatically.

**Requirement (user):** `entrypoint.py site` must refresh **only
dashboards that are actively open**. It must **not** walk the whole
registry / run the cold full refresh. Full walks stay on the existing
15-minute one-shot (or whatever already owns that).

Staged CLI contract (re-drop `jobs/hourly/refresh_dashboards.py` if
needed):

```text
# OPEN-ONLY daemon (what site must spawn)
python jobs/hourly/refresh_dashboards.py --open-interval 60

# FULL walk daemon (do NOT use from site)
python jobs/hourly/refresh_dashboards.py --interval 900

# BOTH (also do NOT use from site)
python jobs/hourly/refresh_dashboards.py --interval 900 --open-interval 60
```

`--open-interval` alone = open-only (no full walk).

---

## Paste the following into PRISM

# Wire open-only tab light refresh into `entrypoint.py site`

Implement Change 4 so that:

```text
entrypoint.py site
```

starts **both**:

1. the Django site (existing `_run_site` / port 8501), and
2. an **open-only** refresh daemon — **no full registry walk**:

```text
python <REPO_ROOT>/jobs/hourly/refresh_dashboards.py --open-interval 60
```

That daemon must:

- read `secondary/dashboard_open_presence/index.json` (TTL-fresh entries)
- spawn `refresh_runner.py --mode light` **only** for those folders
- **never** call the full `_walk_once` / due-registry walk

As you come into Frictions, document and let me know what those
Frictions are.

## Prerequisite check (do first)

1. `jobs/hourly/refresh_dashboards.py --help` shows `--open-interval`.
2. Running with **only** `--open-interval 60` (no `--interval`) starts a
   daemon whose banner says full-interval is off / open-only — not a
   full walk every 900s. If `--open-interval` alone still implies a
   full walk, **stop** and report the payload is stale (staging fixed
   this: open-interval alone = open-only).
3. Do not invent a custom scheduler inside `entrypoint.py` that lists
   all users/dashboards.

## Goal behavior

```text
entrypoint.py site
        │
        ├─► Popen Django runserver          (existing)
        │
        └─► Popen refresh_dashboards --open-interval 60
                │
                └─ every 60s: light-refresh ONLY presence-fresh folders
                   (no UserRegistry full walk, no cold HTML compile)

Ctrl+C
        └─► terminate BOTH children
```

Cold / full refresh remains whoever already owns it
(`fifteen_minute_context_generator` / one-shot `refresh_dashboards.main()`).
**Do not** attach a full walk to `site`.

Default for `site` = open-refresh **on**. Opt-out via
`--no-open-refresh`.

---

## Change A — constant near `SITE_DEFAULT_PORT`

```python
# Open-tab light refresh only (Change 4). While `site` is up, folders
# with a fresh presence heartbeat get refresh_runner --mode light.
# Does NOT walk the full registry — cold HTML stays on the 15-minute job.
SITE_OPEN_REFRESH_INTERVAL_S = 60
```

Do **not** add a `SITE_FULL_REFRESH_INTERVAL_S` used by `site`.

---

## Change B — spawn helper (open-only argv)

```python
def _refresh_dashboards_script():
    return os.path.join(
        str(REPO_ROOT), "jobs", "hourly", "refresh_dashboards.py"
    )


def _run_open_refresh_daemon(open_interval_s=SITE_OPEN_REFRESH_INTERVAL_S):
    """Open-tab light refresh only. Returns Popen."""
    script = _refresh_dashboards_script()
    if not os.path.isfile(script):
        raise FileNotFoundError(
            f"refresh_dashboards.py not found at {script}"
        )
    cmd = [
        sys.executable,
        script,
        "--open-interval", str(int(open_interval_s)),
        # Intentionally NO --interval: open-only daemon.
    ]
    print(
        f"Starting open-tab light-refresh daemon "
        f"(open dashboards only, every {open_interval_s}s)"
    )
    print(f"  cmd: {' '.join(cmd)}")
    return subprocess.Popen(cmd, env=os.environ.copy())
```

Hard rule: the argv list must **not** contain `--interval`.

---

## Change C — `_run_site` supervises site + open daemon

Evolve the existing `_run_site` wait/shutdown to also start the open
daemon by default (same pattern as before: `open_refresh=True` kwarg,
terminate both on Ctrl+C, warn-but-continue if daemon fails to start).

Keep Django `run.py runserver --noreload` construction unchanged.

Sketch:

```python
def _run_site(port, on_started=None, open_refresh=True):
    ...
    proc = subprocess.Popen(cmd, env=env)  # django — unchanged

    refresh_proc = None
    if open_refresh:
        try:
            refresh_proc = _run_open_refresh_daemon()
        except Exception as exc:
            print(
                f"WARN open-refresh daemon failed to start: "
                f"{type(exc).__name__}: {exc}"
            )

    if on_started is not None:
        on_started()

    def _stop_child(child, name):
        if child is None or child.poll() is not None:
            return
        child.terminate()
        try:
            child.wait(timeout=10)
        except Exception:
            child.kill()
            child.wait()
        print(f"Stopped {name}")

    try:
        while True:
            if proc.poll() is not None:
                break
            if refresh_proc is not None and refresh_proc.poll() is not None:
                print(
                    f"WARN open-refresh daemon exited early "
                    f"rc={refresh_proc.returncode}"
                )
                refresh_proc = None
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_child(refresh_proc, "open-refresh daemon")
        _stop_child(proc, "django site")
```

Add `import time` if missing.

---

## Change D — `site` CLI defaults open-refresh ON

Match local click/typer style. Minimum:

```text
entrypoint.py site                  → open_refresh=True
entrypoint.py site --no-open-refresh → Django only
entrypoint.py site --open-interval 30 → override cadence (still open-only)
```

Docstring must say explicitly: **open dashboards only; no full registry
walk.**

---

## Change E — do NOT change

| Surface | Why |
|---|---|
| 15-minute / hourly full `refresh_dashboards.main()` | Keeps cold HTML for everyone |
| `refresh_dashboard_api` / presence view | Already wired |
| Spawning `--interval` from `site` | Forbidden in this pass |

---

## Verification

```text
entrypoint.py site
```

Startup must print a cmd that is **exactly** open-only, e.g.:

```text
.../python .../jobs/hourly/refresh_dashboards.py --open-interval 60
```

Fail verification if the cmd includes `--interval`.

With `smoke_intraday_yields` (or any owned dash) open:

1. `POST /api/dashboard/presence/` → 200 continues.
2. Within ~60–90s, daemon shows an **open-walk** for that folder only
   (not a multi-user full walk banner listing every kerberos).
3. `GET /api/dashboard/data/` → **200** (not only 304), pill/values
   update with no Refresh click.
4. Close the tab / stop heartbeats → within ~2–3 minutes that folder
   drops out of open walks (TTL expiry); no full-registry activity
   appears in the daemon output.
5. `entrypoint.py site --no-open-refresh` → no daemon cmd.

Report pass/fail for 1–5.

---

## Reply format

1. Prerequisite check (confirm open-interval-alone = open-only)  
2. Files touched  
3. Exact spawn argv used by `site`  
4. Verification 1–5  
5. **## Frictions**
