#!/usr/bin/env python3
"""refresh_dashboards.py -- hourly cron entry point for dashboard refresh.

Walks ``UserRegistry``, reads each user's ``dashboards_registry.json``,
and spawns ``refresh_runner.py`` as a subprocess for each dashboard
that is enabled and due. Per-dashboard isolation: a slow pull on one
dashboard cannot block any other dashboard's refresh. After the
subprocess pass, calls ``UserManifestManager.update_dashboard_pointer``
once per kerberos that had at least one successful refresh, so the
manifest pointer block (count / active_count / last_refreshed)
doesn't drift across hourly ticks (per
``prism/dashboard-refresh.md`` \u00a77).

Called from PRISM ``entrypoint.py``'s ``fifteen_minute_context_generator``.
The function name preserves the legacy entry point so the
PRISM-side cron loop doesn't need to change.

Frequency thresholds (matches the contract in
``prism/dashboard-refresh.md`` \u00a75.3 so existing registry entries don't
need migration):

    refresh_frequency       elapsed_hours required
    --------------------    ------------------------
    "hourly"                >= 1
    "daily"                 >= 20    (default)
    "weekly"                >= 160
    "manual"                never (cron skips; only [Refresh] button triggers)

PRISM-side imports only; no fallbacks. Single canonical resolution
path for the runner script, the user registry, the user manifest
manager, and s3_manager.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone

from ai_development.core.common import UserRegistry
from ai_development.core.s3_bucket_manager import s3_manager
from ai_development.core.user_manifest import UserManifestManager
from ai_development.dashboards import refresh_runner as _refresh_runner_module


# Path on disk of the single-dashboard runner. Spawned per due
# dashboard. Resolved once via the canonical Python import (no
# repo-root walking, no fallback paths).
_REFRESH_RUNNER_PATH = _refresh_runner_module.__file__


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_due(entry: dict) -> bool:
    """Return True if ``entry`` (one item from registry["dashboards"])
    should be refreshed now. False for ``refresh_enabled=False`` entries
    and for any frequency that hasn't elapsed yet."""
    if not entry.get("refresh_enabled", True):
        return False
    freq = entry.get("refresh_frequency", "daily")
    if freq == "manual":
        return False
    last = entry.get("last_refreshed")
    if not last:
        return True
    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    elapsed_hours = (_utcnow() - last_dt).total_seconds() / 3600.0
    if freq == "hourly":
        return elapsed_hours >= 1
    if freq == "weekly":
        return elapsed_hours >= 160
    return elapsed_hours >= 20


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
    BLOCK until it exits. Per-dashboard subprocess: a slow / hung pull
    on one dashboard cannot stall the rest of the cron pass.

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
            f"{_utcnow().strftime('%Y%m%d_%H%M%S')}.log"
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


def main() -> int:
    """Walk every user, refresh every due dashboard via subprocess.

    Per-dashboard isolation: each refresh runs in its own
    ``refresh_runner.py`` subprocess so a stuck pull on dashboard A
    cannot block dashboards B / C / D. Spawn-time failures on one
    dashboard are caught and recorded; the cron continues.
    """
    started = _utcnow()
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
            if not _is_due(entry):
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
    # update is the cron's responsibility (§7).
    _update_user_manifests(success_kerberos)

    completed = _utcnow()
    elapsed = (completed - started).total_seconds()
    successes = sum(1 for r in results if r["returncode"] == 0)
    failures = sum(1 for r in results if r["returncode"] != 0)
    print(
        f"[refresh_dashboards] done elapsed={elapsed:.1f}s "
        f"refreshed={len(results)} (success={successes} fail={failures}) "
        f"skipped={disabled_count + not_due_count} "
        f"(disabled={disabled_count} not_due={not_due_count}) "
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


if __name__ == "__main__":
    sys.exit(main())
