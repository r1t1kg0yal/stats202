---
class: end-usage
topic: entrypoint-site-open-refresh
status: OPEN
created: 2026-07-16
depends_on:
  - staging/prompts/open/2026-07-16_django_light_refresh_presence_wire.md
prerequisite_payload:
  - jobs/hourly/refresh_dashboards.py  # must accept --open-interval / --interval daemon
  - prism-core/dashboards/refresh_runner.py  # --mode light|full
---

# PRISM patch prompt — Change 4: `entrypoint.py site` starts open-tab light refresh

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Django presence + light refresh POST are already wired. Browser logs show:

- `POST /api/dashboard/presence/` → 200 (heartbeat OK)
- `GET /api/dashboard/data/` → 304 / cache_hit (no new stamps)
- refreshes only with `trigger=manual`

Missing piece: nothing is calling
`jobs/hourly/refresh_dashboards.py --open-interval 60` while the site
runs. The user wants **`entrypoint.py site` to start that daemon by
default** alongside Django.

---

## Paste the following into PRISM

# Wire open-tab light refresh into `entrypoint.py site`

Implement Change 4 so that running:

```text
entrypoint.py site
```

starts **both**:

1. the Django site (existing behavior on `0.0.0.0:8501`), and
2. the open-tab light-refresh daemon:

```text
python <REPO_ROOT>/jobs/hourly/refresh_dashboards.py \
    --interval 900 \
    --open-interval 60
```

As you come into Frictions, document and let me know what those
Frictions are.

## Prerequisite check (do first)

1. Confirm `jobs/hourly/refresh_dashboards.py --help` shows
   `--interval` and `--open-interval`.
2. Confirm that file's daemon path calls
   `launch_clean_refresh(folder, mode="light")` for open folders and
   default/`full` for the cold walk.
3. If the installed `refresh_dashboards.py` lacks `--open-interval`,
   **stop** and report that the echarts payload drop is stale — do not
   invent a parallel scheduler inside `entrypoint.py`.

## Goal behavior

```text
entrypoint.py site
        │
        ├─► Popen Django runserver (existing _run_site)
        │
        └─► Popen refresh_dashboards --interval 900 --open-interval 60
                │
                ├─ every 60s: light-refresh TTL-fresh open tabs
                │             (reads secondary/dashboard_open_presence/index.json)
                └─ every 900s: full cold-HTML walk (unchanged contract)

Ctrl+C / site exit
        │
        └─► terminate BOTH children cleanly
```

Default = heartbeat/open-refresh **on**. Provide an opt-out flag so
legacy site-only runs remain possible.

---

## Change A — constants near `SITE_DEFAULT_PORT`

In `entrypoint.py`, next to `SITE_DEFAULT_PORT = 8501`, add:

```python
# Open-tab light refresh (Change 4). While `site` is up, dashboards with
# a fresh presence heartbeat get refresh_runner --mode light every N
# seconds. Full cold-HTML walk stays on the longer interval.
SITE_OPEN_REFRESH_INTERVAL_S = 60
SITE_FULL_REFRESH_INTERVAL_S = 900
```

---

## Change B — helper to spawn the refresh daemon

Add a helper in the same file as `_run_site` (adapt imports/`REPO_ROOT`
to whatever `entrypoint.py` already uses — `Path(__file__).resolve()`,
`prism_meta.REPO_ROOT`, etc.):

```python
def _refresh_dashboards_script():
    """Return absolute path to jobs/hourly/refresh_dashboards.py."""
    # Prefer the same REPO_ROOT resolution entrypoint already uses.
    # Example if REPO_ROOT is available:
    return os.path.join(str(REPO_ROOT), "jobs", "hourly", "refresh_dashboards.py")


def _run_open_refresh_daemon(
    open_interval_s=SITE_OPEN_REFRESH_INTERVAL_S,
    full_interval_s=SITE_FULL_REFRESH_INTERVAL_S,
):
    """Spawn the open-tab light + cold full refresh daemon. Returns Popen."""
    script = _refresh_dashboards_script()
    if not os.path.isfile(script):
        raise FileNotFoundError(
            f"refresh_dashboards.py not found at {script} — "
            "drop the staged echarts payload / jobs copy first"
        )
    cmd = [
        sys.executable,
        script,
        "--interval", str(int(full_interval_s)),
        "--open-interval", str(int(open_interval_s)),
    ]
    print(
        f"Starting open-tab dashboard refresh daemon: "
        f"open every {open_interval_s}s, full walk every {full_interval_s}s"
    )
    print(f"  cmd: {' '.join(cmd)}")
    # Inherit env (needs same S3 / kerberos / PYTHONPATH as site).
    return subprocess.Popen(cmd, env=os.environ.copy())
```

Do **not** use `shell=True`. Do **not** redirect away stdout/stderr —
operator should see open-walk banners in the same terminal (or follow
whatever logging pattern sibling entrypoint jobs already use; if site
already tees child logs, match that).

---

## Change C — evolve `_run_site` to supervise both processes

Current shape (from live read):

```python
def _run_site(port, on_started=None):
    ...
    proc = subprocess.Popen(cmd, env=env)
    if on_started is not None:
        on_started()
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        ...
```

**Replace the wait/shutdown section** so `_run_site` also starts the
refresh daemon by default:

```python
def _run_site(port, on_started=None, open_refresh=True):
    ...
    # existing Django Popen → proc
    proc = subprocess.Popen(cmd, env=env)

    refresh_proc = None
    if open_refresh:
        try:
            refresh_proc = _run_open_refresh_daemon()
        except Exception as exc:
            # Site can still serve HTML/data; open-tab auto pull is dead.
            print(
                f"WARN open-refresh daemon failed to start: "
                f"{type(exc).__name__}: {exc}"
            )
            refresh_proc = None

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
        # Wait on the site process; if refresh daemon dies early, log once
        # but keep the site up (presence still works; only auto-pull dies).
        while True:
            site_rc = proc.poll()
            if site_rc is not None:
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

Add `import time` at module top if not already present.

Keep the existing `REPORT_API_URL` / `run.py runserver --noreload`
construction **unchanged**.

---

## Change D — `site` CLI defaults open-refresh ON

Current:

```python
@cli.command("site")
def site():
    """Run web/prism_site Django app on 0.0.0.0:8501. ..."""
    _run_site(SITE_DEFAULT_PORT)
```

**Change to** (match whatever click/typer/argparse style this file uses
for other commands — prefer the local idiom):

### If the CLI is click-style

```python
@cli.command("site")
@click.option(
    "--no-open-refresh",
    is_flag=True,
    default=False,
    help="Do not start the open-tab light-refresh daemon.",
)
@click.option(
    "--open-interval",
    type=int,
    default=SITE_OPEN_REFRESH_INTERVAL_S,
    show_default=True,
    help="Seconds between open-tab light refreshes.",
)
def site(no_open_refresh, open_interval):
    """Run the Django portal and (by default) the open-tab refresh daemon.

    Open dashboards heartbeat POST /api/dashboard/presence/; this daemon
    light-refreshes those folders every --open-interval seconds so the
    browser poll of /api/dashboard/data/ sees new last_refreshed stamps
    without a manual Refresh click.
    """
    # Allow overriding the module default for this run only.
    global SITE_OPEN_REFRESH_INTERVAL_S
    SITE_OPEN_REFRESH_INTERVAL_S = int(open_interval)
    _run_site(SITE_DEFAULT_PORT, open_refresh=not no_open_refresh)
```

### If the CLI is a custom decorator without click options

Add a parallel flag the way sibling commands do. Minimum requirement:

- `entrypoint.py site` → `open_refresh=True` (default)
- Some explicit opt-out (`--no-open-refresh` or `site_no_refresh`) exists
  and is documented in the command docstring

Also update the `site` docstring to mention the daemon explicitly.

---

## Change E — do NOT change

| Surface | Why |
|---|---|
| `fifteen_minute_context_generator` one-shot `refresh_dashboards.main()` | Keep as the production cold walk if still registered; `site`'s daemon is additive for interactive sessions |
| `refresh_dashboard_api` / presence view | Already wired in Change 1–3 |
| Default runner mode for the cold walk | Must remain `full` |

If both the 15-minute one-shot **and** the site daemon run full walks,
that is acceptable (overlapping full walks are gated by
`refresh_status` / due logic). Do not disable the 15-minute job in this
pass unless you hit a concrete lock conflict — then report under
Frictions.

---

## Verification

After editing, run:

```text
entrypoint.py site
```

Expected startup prints (approximate):

```text
Starting open-tab dashboard refresh daemon: open every 60s, full walk every 900s
  cmd: .../python .../jobs/hourly/refresh_dashboards.py --interval 900 --open-interval 60
... django site URL ...
```

Then with an owned dashboard tab open (`smoke_intraday_yields` is fine):

1. Django log keeps showing `POST /api/dashboard/presence/` → 200.
2. Within ~60–90s, refresh daemon stdout shows an **open-walk** banner
   and a light refresh for that folder (not only `trigger=manual` in
   Django).
3. Django log then shows `GET /api/dashboard/data/` → **200** (not only
   304/cache_hit), and the page pill/values update with **no** Refresh
   click and **no** full reload.
4. `entrypoint.py site --no-open-refresh` starts Django only (no daemon
   cmd print); data stays 304 until manual Refresh.

Report pass/fail for each of 1–4.

---

## Reply format

1. Prerequisite check  
2. Exact files touched (`entrypoint.py` path + any tiny helper moves)  
3. Final `site` / `_run_site` signatures  
4. Verification 1–4  
5. **## Frictions**
