#!/usr/bin/env python3
"""refresh_dashboards.py -- cron / daemon entry point for dashboard refresh.

Walks ``UserRegistry``, reads each user's ``dashboards_registry.json``,
and spawns ``refresh_runner.py`` as a subprocess for each dashboard
that is enabled and due. Per-dashboard subprocess isolation: a failure
/ hang in one dashboard's refresh cannot CORRUPT another dashboard's
state -- each refresh runs in its own Python interpreter with its own
filesystem locks and S3 client. The cron walks dashboards SEQUENTIALLY
(``proc.wait()`` blocks per dashboard); a slow Haver pull on dashboard
A delays dashboard B on the same cron tick but does not crash it.
``_is_due`` thresholds keep tick volume small in steady state -- most
ticks are no-ops because few dashboards cross their threshold
simultaneously.

After the subprocess pass, calls
``UserManifestManager.update_dashboard_pointer`` once per kerberos
that had at least one successful refresh, so the manifest pointer
block (count / active_count / last_refreshed) doesn't drift across
cron ticks (per ``prism/dashboard-refresh.md`` \u00a77).

Subprocess log streaming
------------------------

Stdout/stderr drains to S3 keys under ``subprocess_logs/YYYY/MM/DD/...``
via ``S3LogStreamer`` (one daemon thread per spawn). No ``/tmp/``
fallback -- the legacy filesystem path has been retired. The S3 log
key is passed to ``refresh_runner.py`` via ``--log-path`` so it lands
verbatim in ``refresh_status.json`` for triage UX.

The spawner sets ``PRISM_SUBPROCESS_S3_FOLDER_KEY`` in the subprocess
environment so the runner's ``register_completion_marker()`` call
writes ``completion.json`` next to the streamed log. A reader can then
distinguish "still running" / "finished cleanly" / "finished with
error" / "parent died" by inspecting the S3 folder.

Two operating modes:

1. **One-shot** (default): ``main()`` (no args) does a single walk and
   exits. Preserves the legacy entrypoint.py contract -- PRISM's
   ``fifteen_minute_context_generator`` calls ``main()`` every 5
   minutes and the walk takes ~10s for 100 users.

2. **Daemon** (``--interval N``): ``python -m refresh_dashboards
   --interval 30`` loops forever, walking every ``N`` seconds. Use
   this when the legacy 5-minute context cycle is too coarse for
   sub-5-minute dashboard cadences. The walk itself is cheap (~10s
   for 100 users); the expensive spawns are gated by ``_is_due`` so
   most ticks are skip-only.

Frequency contract (``dashboards_time.parse_freq``; matches the
contract in ``prism/dashboard-refresh.md`` \u00a75.3 so existing registry
entries don't need migration):

    refresh_frequency       elapsed required          notes
    --------------------    ----------------------    --------------------------
    "60s" / "5m" / "1h"     duration string           PRISM-authored per dash
    "1d" / "1w"             (case-insensitive)
    "hourly"                >= 1h                     legacy enum, back-compat
    "daily"                 >= 20h (default)
    "weekly"                >= 160h
    "manual"                never (cron skips)        only [Refresh] triggers

Cadence floor: ``effective_refresh = max(walk_interval,
refresh_frequency)``. A "60s" dashboard with the daemon walking every
30s lands within ~60-90s of every tick; with the legacy one-shot path
at 5min, "60s" effectively becomes "every 5 minutes". Pick
``--interval`` to match the SHORTEST ``refresh_frequency`` in the
registry.

PRISM-side imports only; no fallbacks. Single canonical resolution
path for the runner script, the user registry, the user manifest
manager, ``s3_manager``, and the subprocess log streamer.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback

from datetime import timedelta
from typing import List, Optional

from ai_development.core.common import UserRegistry
from ai_development.core.s3_bucket_manager import s3_manager
from ai_development.core.user_manifest import UserManifestManager
from ai_development.dashboards import refresh_runner as _refresh_runner_module
from ai_development.dashboards.dashboards_time import (
    parse_freq, parse_iso, utcnow,
)
from ai_development.mcp.utils.s3_log_streamer import (
    S3LogPathBuilder, S3LogStreamer,
)


# Failure cooldown bounds. A failing dashboard waits at least
# _COOLDOWN_FLOOR after each error before retry; the cooldown grows
# exponentially with consecutive failures and is capped at
# _COOLDOWN_CEIL. These are operational knobs (engineering judgement,
# not user config) -- tuned so a 60s intraday dashboard backs off to
# 5/10/20/40/60min after successive failures rather than spamming the
# daemon every 30s.
_COOLDOWN_FLOOR = timedelta(seconds=60)
_COOLDOWN_CEIL = timedelta(hours=1)
_COOLDOWN_BASE_MULTIPLIER = 5


# Path on disk of the single-dashboard runner. Spawned per due
# dashboard. Resolved once via the canonical Python import (no
# repo-root walking, no fallback paths).
_REFRESH_RUNNER_PATH = _refresh_runner_module.__file__

# Subprocess-kind tag passed to S3LogPathBuilder; partitions the
# subprocess_logs/ key namespace from non-dashboard subprocesses
# (e.g. ad-hoc jobs scripts).
_SPAWN_KIND = "dashboard_refresh"

# ============================================================================
# small print helpers (HIERARCHICAL output: banner per walk + indented
# per-dashboard lines + indented sub-events for spawn / done / cooldown)
# ============================================================================

def _banner(text: str) -> None:
    """Print a phase-block banner: ``====== text ======``. Plain ASCII;
    the streamed bytes go to the parent cron's stdout (and onward to
    the S3 log key when the cron is itself spawned by a higher-level
    job)."""
    print(f"====== {text} ======", flush=True)


def _line(text: str) -> None:
    """Indent-2 dashboard summary line."""
    print(f"  {text}", flush=True)


def _sub(text: str) -> None:
    """Indent-4 sub-event line (under a dashboard summary)."""
    print(f"    {text}", flush=True)


def _human_duration(td: timedelta) -> str:
    """Compact human-readable duration. Examples: ``8s``, ``2m13s``,
    ``1h4m``, ``3d``, ``2d12h``. Total seconds rounded to int; <1s
    rounds up to 1s so the shortest outputs are still meaningful."""
    total = int(td.total_seconds())
    if total < 1:
        total = 1
    if total < 60:
        return f"{total}s"
    if total < 3600:
        m, s = divmod(total, 60)
        return f"{m}m" if s == 0 else f"{m}m{s}s"
    if total < 86400:
        h, rem = divmod(total, 3600)
        m = rem // 60
        return f"{h}h" if m == 0 else f"{h}h{m}m"
    d, rem = divmod(total, 86400)
    h = rem // 3600
    return f"{d}d" if h == 0 else f"{d}d{h}h"


def _last_age(entry: dict) -> str:
    """Human-readable age of the entry's ``last_refreshed`` field, or
    ``"never"`` when the field is missing / unparseable."""
    last = parse_iso(entry.get("last_refreshed"))
    if last is None:
        return "never"
    return _human_duration(utcnow() - last)


# ============================================================================
# refresh-status + cooldown helpers
# ============================================================================

def _read_refresh_status(folder: str) -> Optional[dict]:
    """Read ``<folder>/refresh_status.json``. Returns ``None`` on
    missing / unreadable / malformed input -- callers treat ``None`` as
    "no prior status known" (no cooldown applied). Used by ``_is_due``
    to back off failing dashboards instead of hot-spinning every tick."""
    try:
        raw = s3_manager.get(f"{folder}/refresh_status.json")
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _failure_cooldown(refresh_delta: timedelta,
                       consecutive_failures: int) -> timedelta:
    """Return the cooldown a failing dashboard must wait before retry.

    Exponential backoff keyed off ``consecutive_failures``. Base
    cooldown is ``max(refresh_delta * 5, 60s)`` (so an "hourly"
    dashboard gets a 5h-floored base which immediately caps at 1h).
    Each additional consecutive failure doubles the cooldown, up to
    the 1-hour ceiling.

    For ``refresh_frequency = "60s"`` (base = 5min):
        n=1: 5min, n=2: 10min, n=3: 20min, n=4: 40min, n>=5: 1h (cap)

    For ``refresh_frequency = "1h"`` or longer: always 1h (cap).
    """
    n = max(1, int(consecutive_failures))
    base = max(refresh_delta * _COOLDOWN_BASE_MULTIPLIER, _COOLDOWN_FLOOR)
    factor = 2 ** min(n - 1, 8)
    cooldown = base * factor
    return min(cooldown, _COOLDOWN_CEIL)


def _is_due(entry: dict, *, status: Optional[dict] = None) -> bool:
    """Return ``True`` if ``entry`` (one item from
    ``registry["dashboards"]``) should be refreshed now.

    Routes through the canonical ``dashboards_time.parse_freq`` so the
    threshold parsing is defined in one place. Accepts the full
    duration-string vocabulary (``"60s"`` / ``"5m"`` / ``"1h"`` /
    ``"1d"`` / ``"1w"``) plus the legacy enum (``"hourly"`` /
    ``"daily"`` / ``"weekly"``). ``"daily"`` means ">=20 hours elapsed
    since last refresh", not "calendar-day boundary" -- preserved
    verbatim from the legacy behaviour so existing registry entries
    don't need migration.

    Unknown frequencies fall back to ``daily`` for back-compat with
    typo'd entries; ``"manual"`` (case-insensitive) explicitly opts
    out of auto-refresh.

    Failure cooldown: if ``status`` (refresh_status.json contents)
    shows a recent error / partial outcome, the dashboard is held off
    for an exponential backoff window keyed off
    ``consecutive_failures``. This is what stops a chronically-failing
    dashboard from spawning a failing subprocess every cron tick
    (which would spam logs and starve healthy dashboards' refresh
    windows). The cooldown applies BEFORE the normal due-check.
    """
    if not entry.get("refresh_enabled", True):
        return False
    freq = entry.get("refresh_frequency", "daily")
    if isinstance(freq, str) and freq.strip().lower() == "manual":
        return False
    delta = parse_freq(freq) or parse_freq("daily")

    # Failure cooldown: if the prior run failed, wait out the backoff
    # before retrying. consecutive_failures is stamped by refresh_runner
    # on every error / partial outcome and reset to 0 on success.
    if status and status.get("status") in ("error", "partial"):
        completed = parse_iso(status.get("completed_at"))
        if completed is not None:
            n = status.get("consecutive_failures", 1) or 1
            cooldown = _failure_cooldown(delta, n)
            elapsed = utcnow() - completed
            if elapsed < cooldown:
                return False

    last = parse_iso(entry.get("last_refreshed"))
    if last is None:
        return True
    return (utcnow() - last) >= delta


def _user_registry_entries(kerberos: str) -> list:
    """Return the list of dashboard entries for kerberos, or ``[]`` if
    the user has no registry, the registry is unreadable, or the JSON
    is malformed. Wrapped in try/except so a single corrupt registry
    cannot crash the whole cron pass."""
    registry_path = f"users/{kerberos}/dashboards/dashboards_registry.json"
    try:
        raw = s3_manager.get(registry_path)
    except Exception:
        return []
    if not raw:
        return []
    try:
        registry = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return []
    entries = registry.get("dashboards", [])
    return entries if isinstance(entries, list) else []


# ============================================================================
# subprocess spawn (S3 log streaming)
# ============================================================================

def _spawn_runner(folder: str) -> dict:
    """Spawn ``refresh_runner.py --folder <folder> --log-path <s3_log_key>``
    and BLOCK until it exits. Per-dashboard subprocess isolation: a
    failure or hang in one dashboard's refresh cannot CORRUPT another
    dashboard's state. The cron walks dashboards SEQUENTIALLY --
    ``proc.wait()`` blocks on each spawn, so a slow Haver pull on
    dashboard A delays dashboard B on the same cron tick but does not
    crash it.

    Stdout/stderr drains to an S3 key via ``S3LogStreamer`` (one daemon
    thread per spawn). The S3 log key is passed to ``refresh_runner.py``
    via ``--log-path`` so the runner records it verbatim into
    ``refresh_status.json``. The runner's ``register_completion_marker()``
    call writes ``completion.json`` so a reader can distinguish
    still-running / clean-exit / error-exit / parent-died. NO ``/tmp/``
    fallback -- all subprocess logs live in S3 under
    ``subprocess_logs/YYYY/MM/DD/...``.

    Returns ``{folder, returncode, elapsed_seconds, log_path,
    s3_log_key, s3_folder_key}`` on a successful spawn, or the same
    shape with ``returncode: -1`` and an ``error`` field if the spawn
    itself failed.
    """
    spawn_ts = utcnow()
    slug = folder.replace("/", "_")
    folder_key, log_key, metadata_key, _completion_key = S3LogPathBuilder.build(
        kind=_SPAWN_KIND,
        session_description=slug,
        ts=spawn_ts,
    )

    # Option A -- dual-write: the dashboard FOLDER itself is the auditable
    # session-side destination. A user inspecting
    # users/<kerb>/dashboards/<name>/ should see the refresh subprocess
    # log right next to dashboard.html / refresh_status.json instead of
    # having to chase a centralized subprocess_logs/ key.
    (session_folder_key,
     session_log_key,
     session_metadata_key,
     _session_completion_key) = S3LogPathBuilder.build_session_side(
         session_path=folder,
         kind=_SPAWN_KIND,
         ts=spawn_ts,
     )

    env = os.environ.copy()
    env["PRISM_SUBPROCESS_S3_FOLDER_KEY"] = folder_key
    env["PRISM_SUBPROCESS_SESSION_FOLDER_KEY"] = session_folder_key

    header = (
        f"=== refresh_runner spawn ===\n"
        f"folder: {folder}\n"
        f"started: {spawn_ts.isoformat()}\n"
        f"s3_log_key: {log_key}\n"
        + "=" * 60 + "\n"
    ).encode("utf-8")

    pipe_r, pipe_w = os.pipe()
    streamer: Optional[S3LogStreamer] = None
    try:
        started = time.time()
        proc = subprocess.Popen(
            [sys.executable, _REFRESH_RUNNER_PATH,
             "--folder", folder, "--log-path", log_key],
            stdout=pipe_w, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        # Parent closes its copy of the write end so the streamer's
        # daemon thread sees EOF as soon as the subprocess exits and
        # closes its (only remaining) copy.
        os.close(pipe_w)
        pipe_w = -1

        # Dual-write: session-side key FIRST (canonical/auditable),
        # centralized key SECOND (dev-team triage convenience). The
        # streamer's _flush() PUTs the same bytes to every key in the
        # list with per-key failure isolation.
        streamer = S3LogStreamer(
            fd=pipe_r,
            s3_log_key=[session_log_key, log_key],
            header=header,
        )
        streamer.start()
        # streamer's daemon thread now owns pipe_r -- it closes the fd
        # on EOF / error. We mark it as -1 so the finally block doesn't
        # double-close.
        pipe_r = -1

        # Best-effort metadata sidecar. Dual-written to BOTH the
        # centralized and session-side folders so a reader inspecting
        # either copy can cross-reference the other. Per-key failures
        # are isolated.
        metadata_blob = {
            "pid":            proc.pid,
            "started_at":     spawn_ts.isoformat(),
            "folder":         folder,
            "s3_log_key":     log_key,
            "s3_folder_key":  folder_key,
            "session_s3_log_key":      session_log_key,
            "session_s3_folder_key":   session_folder_key,
            "session_s3_metadata_key": session_metadata_key,
            "kind":           _SPAWN_KIND,
        }
        for _md_key in (metadata_key, session_metadata_key):
            try:
                s3_manager.put(metadata_blob, _md_key)
            except Exception as meta_err:
                print(
                    f"WARN metadata sidecar write failed "
                    f"{_md_key}: {meta_err}",
                    file=sys.stderr, flush=True,
                )

        rc = proc.wait()
        elapsed = round(time.time() - started, 2)
        return {
            "folder":          folder,
            "returncode":      rc,
            "elapsed_seconds": elapsed,
            "log_path":        session_log_key,  # session-side is canonical
            "s3_log_key":      log_key,
            "s3_folder_key":   folder_key,
            "session_s3_log_key":      session_log_key,
            "session_s3_folder_key":   session_folder_key,
            "pid":             proc.pid,
        }
    except BaseException as exc:
        # Spawn-time failure (executable missing, OS pipe failure,
        # permission denied, etc.). Record the failure and keep walking;
        # one bad dashboard cannot crash the whole cron pass.
        print(
            f"SPAWN FAIL {folder}: {type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        return {
            "folder":          folder,
            "returncode":      -1,  # sentinel for spawn-time failure
            "elapsed_seconds": 0.0,
            "log_path":        session_log_key,
            "s3_log_key":      log_key,
            "s3_folder_key":   folder_key,
            "session_s3_log_key":      session_log_key,
            "session_s3_folder_key":   session_folder_key,
            "pid":             None,
            "error":           f"{type(exc).__name__}: {exc}",
        }
    finally:
        # Close any pipe ends we still own. After streamer.start() the
        # daemon thread owns pipe_r (and we set it to -1 above so this
        # block skips it).
        for fd in (pipe_r, pipe_w):
            if fd != -1:
                try:
                    os.close(fd)
                except OSError:
                    pass


def _update_user_manifests(successful_kerberos: set) -> List[tuple]:
    """Refresh the manifest pointer block for every kerberos that had
    at least one successful dashboard refresh this tick. Best-effort:
    a single user-manifest failure logs but does not block the rest of
    the pass. Per ``prism/dashboard-refresh.md`` \u00a77.

    Returns ``[(kerberos, ok: bool, error_str: Optional[str]), ...]``
    so the caller can render per-user pointer-update lines.
    """
    results: List[tuple] = []
    for kerberos in sorted(successful_kerberos):
        try:
            UserManifestManager.update_dashboard_pointer(kerberos)
            results.append((kerberos, True, None))
        except BaseException as exc:
            results.append((kerberos, False, f"{type(exc).__name__}: {exc}"))
    return results


# ============================================================================
# walk + daemon
# ============================================================================

def _walk_once(*, walk_id: int = 1) -> int:
    """Single walk over every user's registry. Spawn ``refresh_runner.py``
    per due dashboard. Returns 0 if every spawn succeeded, 1 if any
    failed.

    Per-dashboard subprocess isolation: each refresh runs in its own
    ``refresh_runner.py`` subprocess so a failure on dashboard A
    cannot CORRUPT state on dashboards B / C / D. The walk is
    SEQUENTIAL (``proc.wait()`` blocks per dashboard); a slow pull on
    A delays B / C / D on the same cron tick but does not crash them.
    Spawn-time failures on one dashboard are caught and recorded; the
    cron continues to the next dashboard.
    """
    started = utcnow()
    started_perf = time.perf_counter()

    all_kerberos = sorted(UserRegistry.instance().get_all_kerberos_ids())

    _banner(
        f"refresh_dashboards walk #{walk_id} starting "
        f"{started.isoformat()} ({len(all_kerberos)} users)"
    )

    results: list = []
    success_kerberos: set = set()
    disabled_count = 0
    not_due_count = 0
    cooldown_count = 0

    for kerberos in all_kerberos:
        entries = _user_registry_entries(kerberos)
        for entry in entries:
            dashboard_id = entry.get("id", "?")
            folder = entry.get("folder") or (
                f"users/{kerberos}/dashboards/{dashboard_id}"
            )
            freq = entry.get("refresh_frequency", "daily")
            last_age = _last_age(entry)
            short_id = f"{kerberos}/{dashboard_id}"

            if not entry.get("refresh_enabled", True):
                disabled_count += 1
                _line(
                    f"{short_id}  freq={freq}  "
                    f"last={last_age}  -> SKIP disabled"
                )
                continue

            status = _read_refresh_status(folder)
            if not _is_due(entry, status=status):
                # Differentiate cooldown skips from ordinary not-due so
                # operators can tell at a glance whether a dashboard is
                # healthy-but-not-due vs failing-and-backed-off.
                if status and status.get("status") in ("error", "partial"):
                    completed = parse_iso(status.get("completed_at"))
                    delta = (parse_freq(freq) or parse_freq("daily"))
                    n = status.get("consecutive_failures", 1) or 1
                    cooldown = _failure_cooldown(delta, n)
                    if completed is not None and (utcnow() - completed) < cooldown:
                        elapsed = (utcnow() - completed)
                        remaining = cooldown - elapsed
                        _line(
                            f"{short_id}  freq={freq}  "
                            f"last_error={_human_duration(elapsed)}  "
                            f"-> COOLDOWN n={n} "
                            f"retry_in={_human_duration(remaining)}"
                        )
                        cooldown_count += 1
                        continue
                _line(
                    f"{short_id}  freq={freq}  "
                    f"last={last_age}  -> SKIP not_due"
                )
                not_due_count += 1
                continue

            _line(
                f"{short_id}  freq={freq}  "
                f"last={last_age}  -> SPAWN"
            )
            r = _spawn_runner(folder)
            results.append(r)
            log_key = r.get("s3_log_key") or r.get("log_path") or "<unknown>"
            pid = r.get("pid")
            pid_str = f"pid={pid}" if pid is not None else "pid=?"
            _sub(f"\u21aa {log_key}  {pid_str}")
            rc = r.get("returncode", -1)
            elapsed_s = r.get("elapsed_seconds", 0.0) or 0.0
            if rc == 0:
                _sub(
                    f"\u2713 ok  rc={rc}  "
                    f"elapsed={elapsed_s:.2f}s"
                )
                success_kerberos.add(kerberos)
            else:
                err = r.get("error") or f"rc={rc}"
                _sub(
                    f"\u2717 fail  rc={rc}  "
                    f"elapsed={elapsed_s:.2f}s  ({err})"
                )

    # Refresh user-manifest pointer blocks for users whose registry
    # was mutated by a successful subprocess this tick. The runner
    # only touches the registry; the manifest pointer (aggregate
    # metadata) update is the cron's responsibility (per
    # dashboard-refresh.md \u00a77).
    pointer_results = _update_user_manifests(success_kerberos)
    pointer_failures = [r for r in pointer_results if not r[1]]
    if pointer_results:
        _line(
            f"manifest pointers refreshed: {len(pointer_results)} user(s) "
            f"({len(pointer_results) - len(pointer_failures)} ok, "
            f"{len(pointer_failures)} fail)"
        )
        for kerberos, _ok, err in pointer_failures:
            _sub(f"\u2717 {kerberos}: {err}")

    elapsed = time.perf_counter() - started_perf
    successes = sum(1 for r in results if r["returncode"] == 0)
    failures = sum(1 for r in results if r["returncode"] != 0)
    skipped = disabled_count + not_due_count + cooldown_count

    _banner(
        f"walk #{walk_id} done -- elapsed={elapsed:.2f}s  "
        f"refreshed={len(results)} (ok={successes} fail={failures})  "
        f"skipped={skipped} (disabled={disabled_count} "
        f"not_due={not_due_count} cooldown={cooldown_count})  "
        f"manifests={len(pointer_results)}"
    )
    return 0 if failures == 0 else 1


def _daemon(interval_seconds: int) -> int:
    """Loop forever, walking the registry every ``interval_seconds``.

    Each tick = one ``_walk_once`` pass with a monotonic walk counter.
    Walk time is reckoned into the sleep so the effective wall-clock
    cadence is constant: a 12s walk followed by an 18s sleep, not 30s
    of sleep on top of the walk.

    Walk-time exceptions are caught and logged but the daemon survives
    (subprocess failures inside ``_walk_once`` are already handled by
    ``_spawn_runner``; this branch covers genuinely-unexpected crashes
    like an S3 listing failure or a UserRegistry race).
    KeyboardInterrupt exits cleanly with rc=0.

    Cadence floor: a dashboard with ``refresh_frequency = "60s"`` and
    a daemon walking every 30s sees effective cadence ~60-90s (60s
    threshold + up to 30s walk granularity + ~11s spawn). Pick
    ``--interval`` to match the SHORTEST refresh_frequency you have
    registered; walking faster than that just wastes CPU.
    """
    if interval_seconds <= 0:
        print(
            f"refresh_dashboards: --interval must be > 0; got "
            f"{interval_seconds}",
            file=sys.stderr, flush=True,
        )
        return 2

    _banner(
        f"refresh_dashboards daemon mode -- interval={interval_seconds}s"
    )

    walk_id = 0
    try:
        while True:
            walk_id += 1
            tick_started = time.time()
            try:
                _walk_once(walk_id=walk_id)
            except BaseException as exc:
                print(
                    f"WALK CRASHED #{walk_id}: "
                    f"{type(exc).__name__}: {exc}",
                    file=sys.stderr, flush=True,
                )
                print(traceback.format_exc(),
                      file=sys.stderr, flush=True)
            tick_elapsed = time.time() - tick_started
            sleep_for = max(0.0, float(interval_seconds) - tick_elapsed)
            if sleep_for > 0:
                time.sleep(sleep_for)
    except KeyboardInterrupt:
        _banner(
            f"refresh_dashboards daemon interrupted "
            f"after walk #{walk_id}"
        )
        return 0


# ============================================================================
# CLI
# ============================================================================

def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="refresh_dashboards",
        description=(
            "Walk the dashboards registry and refresh every due "
            "dashboard via per-dashboard subprocess. Default: one "
            "walk + exit (legacy entrypoint.py contract). With "
            "--interval N: run as a daemon, walking every N seconds "
            "forever."
        ),
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Daemon mode: walk the registry every N seconds. "
            "Recommended N=30 for registries containing sub-minute "
            "refresh_frequency dashboards. Effective per-dashboard "
            "cadence = max(N, refresh_frequency); pick N <= the "
            "shortest refresh_frequency in the registry."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. Two callable shapes:

    1. ``main()`` (no args) -- single walk and exit. Preserves the
       legacy ``entrypoint.py`` contract; PRISM's
       ``fifteen_minute_context_generator`` calls this with no args.
    2. ``main(argv)`` (CLI args list) -- argparse-driven. With
       ``--interval N`` runs as a daemon, otherwise one-shot.

    Splitting on ``argv is None`` instead of ``sys.argv`` so the
    Python-level call from entrypoint.py never picks up stray CLI
    args intended for the parent process.
    """
    if argv is None:
        return _walk_once()
    args = _parse_args(argv)
    if args.interval is None:
        return _walk_once()
    return _daemon(args.interval)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
