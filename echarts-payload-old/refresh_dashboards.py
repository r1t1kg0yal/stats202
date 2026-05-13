#!/usr/bin/env python3
"""refresh_dashboards.py -- cron / daemon entry point for dashboard refresh.

Walks ``UserRegistry``, reads each user's ``dashboards_registry.json``,
and spawns ``refresh_runner.py`` as a subprocess for each dashboard
that is enabled and due. Per-dashboard subprocess isolation:
a failure / hang in one dashboard's refresh cannot CORRUPT another
dashboard's state -- each refresh runs in its own Python interpreter
with its own filesystem locks and S3 client. The cron walks dashboards
SEQUENTIALLY (``proc.wait()`` blocks per dashboard); a slow Haver pull
on dashboard A delays dashboard B on the same cron tick but does not
crash it. ``_is_due`` thresholds keep tick volume small in steady
state -- most ticks are no-ops because few dashboards cross their
threshold simultaneously.

After the subprocess pass, calls ``UserManifestManager.update_dashboard_pointer``
once per kerberos that had at least one successful refresh, so the
manifest pointer block (count / active_count / last_refreshed)
doesn't drift across cron ticks (per
``prism/dashboard-refresh.md`` \u00a77).

Two operating modes:

1. **One-shot** (default): ``main()`` (no args) does a single walk
   and exits. Preserves the legacy entrypoint.py contract -- PRISM's
   ``fifteen_minute_context_generator`` calls ``main()`` every 5
   minutes and the walk takes ~10s for 100 users.

2. **Daemon** (``--interval N``): ``python -m refresh_dashboards
   --interval 30`` loops forever, walking every ``N`` seconds. Use
   this when the legacy 5-minute context cycle is too coarse for
   sub-5-minute dashboard cadences. The walk itself is cheap (~10s
   for 100 users); the expensive spawns are gated by ``_is_due`` so
   most ticks are skip-only.

Frequency contract (``dashboards_time.parse_freq``; matches the contract in
``prism/dashboard-refresh.md`` \u00a75.3 so existing registry entries don't
need migration):

    refresh_frequency       elapsed required          notes
    --------------------    ----------------------    --------------------------
    "60s" / "5m" / "1h"     duration string           PRISM-authored per dash
    "1d" / "1w"             (case-insensitive)
    "hourly"                >= 1h                     legacy enum, back-compat
    "daily"                 >= 20h (default)
    "weekly"                >= 160h
    "manual"                never (cron skips)        only [Refresh] triggers

Cadence floor: ``effective_refresh = max(walk_interval, refresh_frequency)``.
A "60s" dashboard with the daemon walking every 30s lands within ~60-90s
of every tick; with the legacy one-shot path at 5min, "60s" effectively
becomes "every 5 minutes". Pick ``--interval`` to match the SHORTEST
``refresh_frequency`` in the registry.

PRISM-side imports only; no fallbacks. Single canonical resolution
path for the runner script, the user registry, the user manifest
manager, and s3_manager.
"""

from __future__ import annotations

import argparse
import json
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


# Failure cooldown bounds. A failing dashboard waits at least
# _COOLDOWN_FLOOR after each error before retry; the cooldown grows
# exponentially with consecutive failures and is capped at _COOLDOWN_CEIL.
# These are operational knobs (engineering judgement, not user config) --
# tuned so a 60s intraday dashboard backs off to 5/10/20/40/60min after
# successive failures rather than spamming the daemon every 30s.
_COOLDOWN_FLOOR = timedelta(seconds=60)
_COOLDOWN_CEIL = timedelta(hours=1)
_COOLDOWN_BASE_MULTIPLIER = 5


# Path on disk of the single-dashboard runner. Spawned per due
# dashboard. Resolved once via the canonical Python import (no
# repo-root walking, no fallback paths).
_REFRESH_RUNNER_PATH = _refresh_runner_module.__file__


def _read_refresh_status(folder: str) -> Optional[dict]:
    """Read ``<folder>/refresh_status.json``. Returns ``None`` on missing
    / unreadable / malformed input -- callers treat None as "no prior
    status known" (no cooldown applied). Used by ``_is_due`` to back off
    failing dashboards instead of hot-spinning every tick."""
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

    Exponential backoff keyed off ``consecutive_failures``. Base cooldown
    is ``max(refresh_delta * 5, 60s)`` (so an "hourly" dashboard gets
    a 5h-floored base which immediately caps at 1h). Each additional
    consecutive failure doubles the cooldown, up to the 1-hour ceiling.

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
    typo'd entries; ``"manual"`` (case-insensitive) explicitly opts out
    of auto-refresh.

    Failure cooldown: if ``status`` (refresh_status.json contents) shows
    a recent error / partial outcome, the dashboard is held off for an
    exponential backoff window keyed off ``consecutive_failures``. This
    is what stops a chronically-failing dashboard from spawning a
    failing subprocess every cron tick (which would spam logs and starve
    healthy dashboards' refresh windows). The cooldown applies BEFORE
    the normal due-check.
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
    """Return the list of dashboard entries for kerberos, or [] if the
    user has no registry, the registry is unreadable, or the JSON is
    malformed. Wrapped in try/except so a single corrupt registry
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


def _spawn_runner(folder: str, log_root: str = "/tmp/dashboard_refresh") -> dict:
    """Spawn ``refresh_runner.py --folder <folder> --log-path <log>`` and
    BLOCK until it exits. Per-dashboard subprocess isolation: a failure
    or hang in one dashboard's refresh cannot CORRUPT another dashboard's
    state. The cron walks dashboards SEQUENTIALLY -- ``proc.wait()`` blocks
    on each spawn, so a slow Haver pull on dashboard A delays dashboard B
    on the same cron tick but does not crash it.

    Returns ``{folder, returncode, elapsed_seconds, log_path}`` on a
    successful spawn, or ``{folder, returncode: -1, error, log_path}``
    if the spawn itself failed. The log path is passed through to the
    runner so it lands verbatim in refresh_status.json (\u00a78.1).
    """
    import os
    try:
        os.makedirs(log_root, exist_ok=True)
        slug = folder.replace("/", "_")
        log_path = (
            f"{log_root}/{slug}_"
            f"{utcnow().strftime('%Y%m%d_%H%M%S')}.log"
        )
        started = time.time()
        with open(log_path, "wb") as log_fh:
            proc = subprocess.Popen(
                [sys.executable, _REFRESH_RUNNER_PATH,
                 "--folder", folder, "--log-path", log_path],
                stdout=log_fh, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
            rc = proc.wait()
        elapsed = round(time.time() - started, 2)
        return {
            "folder":          folder,
            "returncode":      rc,
            "elapsed_seconds": elapsed,
            "log_path":        log_path,
        }
    except BaseException as exc:
        # Spawn-time failure (executable missing, OSError on log file,
        # permission denied, etc.). Record the failure and keep walking;
        # one bad dashboard cannot crash the whole cron pass.
        print(
            f"[refresh_dashboards] SPAWN FAILED for {folder}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        return {
            "folder":          folder,
            "returncode":      -1,  # sentinel for spawn-time failure
            "elapsed_seconds": 0.0,
            "log_path":        None,
            "error":           f"{type(exc).__name__}: {exc}",
        }


def _update_user_manifests(successful_kerberos: set) -> None:
    """Refresh the manifest pointer block for every kerberos that had
    at least one successful dashboard refresh this tick. Best-effort:
    a single user-manifest failure logs a warning and continues so the
    rest of the pass is not blocked. Per `prism/dashboard-refresh.md` \u00a77."""
    for kerberos in sorted(successful_kerberos):
        try:
            UserManifestManager.update_dashboard_pointer(kerberos)
        except BaseException as exc:
            print(
                f"[refresh_dashboards] manifest pointer update FAILED for "
                f"{kerberos}: {type(exc).__name__}: {exc}",
                file=sys.stderr, flush=True,
            )


def _walk_once() -> int:
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
    print(
        f"[refresh_dashboards] starting at {started.isoformat()}",
        flush=True,
    )

    all_kerberos = sorted(UserRegistry.instance().get_all_kerberos_ids())
    print(
        f"[refresh_dashboards] walking {len(all_kerberos)} user(s)",
        flush=True,
    )

    results: list = []
    success_kerberos: set = set()
    disabled_count = 0
    not_due_count = 0
    cooldown_count = 0
    for kerberos in all_kerberos:
        entries = _user_registry_entries(kerberos)
        for entry in entries:
            dashboard_id = entry.get("id")
            folder = entry.get("folder") or (
                f"users/{kerberos}/dashboards/{dashboard_id}"
            )
            if not entry.get("refresh_enabled", True):
                disabled_count += 1
                continue
            status = _read_refresh_status(folder)
            if not _is_due(entry, status=status):
                # Differentiate cooldown skips from ordinary not-due so
                # operators can tell at a glance whether a dashboard is
                # healthy-but-not-due vs failing-and-backed-off.
                if status and status.get("status") in ("error", "partial"):
                    completed = parse_iso(status.get("completed_at"))
                    delta = (parse_freq(entry.get("refresh_frequency", "daily"))
                              or parse_freq("daily"))
                    n = status.get("consecutive_failures", 1) or 1
                    cooldown = _failure_cooldown(delta, n)
                    if completed is not None and (utcnow() - completed) < cooldown:
                        elapsed = (utcnow() - completed).total_seconds()
                        remaining = max(0, cooldown.total_seconds() - elapsed)
                        print(
                            f"[refresh_dashboards] COOLDOWN {folder} "
                            f"(consecutive_failures={n}, "
                            f"last_error={int(elapsed)}s ago, "
                            f"retry_in={int(remaining)}s)",
                            flush=True,
                        )
                        cooldown_count += 1
                        continue
                not_due_count += 1
                continue
            print(
                f"[refresh_dashboards] -> {folder}",
                flush=True,
            )
            r = _spawn_runner(folder)
            results.append(r)
            if r["returncode"] == 0:
                success_kerberos.add(kerberos)

    # Refresh user-manifest pointer blocks for users whose registry was
    # mutated by a successful subprocess this tick. The runner only
    # touches the registry; the manifest pointer (aggregate metadata)
    # update is the cron's responsibility (per dashboard-refresh.md).
    _update_user_manifests(success_kerberos)

    completed = utcnow()
    elapsed = (completed - started).total_seconds()
    successes = sum(1 for r in results if r["returncode"] == 0)
    failures = sum(1 for r in results if r["returncode"] != 0)
    print(
        f"[refresh_dashboards] done elapsed={elapsed:.1f}s "
        f"refreshed={len(results)} (success={successes} fail={failures}) "
        f"skipped={disabled_count + not_due_count + cooldown_count} "
        f"(disabled={disabled_count} not_due={not_due_count} "
        f"cooldown={cooldown_count}) "
        f"manifests_refreshed={len(success_kerberos)}",
        flush=True,
    )
    for r in results:
        if r["returncode"] != 0:
            log_hint = r.get("log_path") or r.get("error", "<spawn failed>")
            print(
                f"[refresh_dashboards] FAILED {r['folder']} "
                f"rc={r['returncode']} log={log_hint}",
                flush=True,
            )
    return 0 if failures == 0 else 1


def _daemon(interval_seconds: int) -> int:
    """Loop forever, walking the registry every ``interval_seconds``.

    Each tick = one ``_walk_once`` pass. Walk time is reckoned into the
    sleep so the effective wall-clock cadence is constant: a 12s walk
    followed by an 18s sleep, not 30s of sleep on top of the walk.

    Walk-time exceptions are caught and logged but the daemon survives
    (subprocess failures inside ``_walk_once`` are already handled by
    ``_spawn_runner``; this branch covers genuinely-unexpected crashes
    like an S3 listing failure or a UserRegistry race). KeyboardInterrupt
    exits cleanly with rc=0.

    Cadence floor: a dashboard with ``refresh_frequency = "60s"`` and
    a daemon walking every 30s sees effective cadence ~60-90s (60s
    threshold + up to 30s walk granularity + ~11s spawn). Pick
    ``--interval`` to match the SHORTEST refresh_frequency you have
    registered; walking faster than that just wastes CPU.
    """
    if interval_seconds <= 0:
        print(
            f"[refresh_dashboards] --interval must be > 0; got "
            f"{interval_seconds}",
            file=sys.stderr, flush=True,
        )
        return 2
    print(
        f"[refresh_dashboards] daemon mode interval={interval_seconds}s",
        flush=True,
    )
    try:
        while True:
            tick_started = time.time()
            try:
                _walk_once()
            except BaseException as exc:
                print(
                    f"[refresh_dashboards] WALK CRASHED: "
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
        print(
            "[refresh_dashboards] daemon interrupted, exiting",
            flush=True,
        )
        return 0


def _parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="refresh_dashboards",
        description=(
            "Walk the dashboards registry and refresh every due "
            "dashboard via per-dashboard subprocess. Default: one walk + "
            "exit (legacy entrypoint.py contract). With --interval N: "
            "run as a daemon, walking every N seconds forever."
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
    Python-level call from entrypoint.py never picks up stray CLI args
    intended for the parent process.
    """
    if argv is None:
        return _walk_once()
    args = _parse_args(argv)
    if args.interval is None:
        return _walk_once()
    return _daemon(args.interval)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
