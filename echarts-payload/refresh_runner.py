#!/usr/bin/env python3
"""refresh_runner.py -- single-dashboard refresh CLI.

Spawned by the Django Refresh button handler (POST /api/dashboard/refresh/)
and by the hourly cron (``refresh_dashboards.py``). Runs ``run_pull``
for every ``PULLS`` entry, then ``build_dashboard`` for the named folder,
then writes ``<folder>/refresh_status.json`` with the outcome.

Usage::

    python -m ai_development.dashboards.refresh_runner \
        --folder    users/<kerberos>/dashboards/<name> \
        --log-path  /tmp/dashboard_refresh/<slug>_<UTC>.log   # optional

Status JSON shape (matches the polling endpoint contract documented in
``prism/dashboard-refresh.md`` \u00a78.1 so the in-browser failure modal renders
all fields, including the per-error ``script`` + ``classification`` pills
and the ``log_path`` PRISM-triage field)::

    {
        "status":          "running" | "success" | "error",
        "started_at":      "2026-05-04T21:30:11.123456Z",
        "completed_at":    "2026-05-04T21:30:55.789012Z",  # final only
        "elapsed_seconds": 44.67,                            # final only
        "pid":             12345,
        "log_path":        "/tmp/dashboard_refresh/...",     # if --log-path
        "errors":          [{"script": "scripts/pull_data.py",
                              "classification": "data_pull_empty",
                              "message":   "...",
                              "traceback": "..."}],          # final only
    }

PRISM-side imports only; no fallbacks. Single canonical resolution path
for the engine, the user manifest, and s3_manager.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional

from ai_development.core.s3_bucket_manager import s3_manager
from ai_development.dashboards import build_dashboard, run_pull


# Phase tags used in the per-error `script` field so the §8.1 modal +
# Copy-for-PRISM markdown surface "which phase blew up" without the
# runner having to re-introspect the traceback.
_PHASE_PULL_PREFIX = "scripts/pull_data.py"
_PHASE_BUILD       = "scripts/build.py"
_PHASE_PARSE       = "<argparse>"


def _utcnow_iso() -> str:
    """ISO-8601 UTC with `Z` suffix to match existing registry entries
    (per `prism/dashboard-refresh.md` \u00a76.2). Sub-microsecond precision."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _put_status(folder: str, payload: dict) -> None:
    s3_manager.put(
        json.dumps(payload, indent=2).encode("utf-8"),
        f"{folder}/refresh_status.json",
    )


def _parse_folder(folder: str) -> tuple:
    """Return (folder, kerberos, dashboard_id) parsed from a canonical
    folder path ``users/<kerberos>/dashboards/<id>``. Raises if the
    shape doesn't match -- single canonical path, no normalisation magic."""
    folder = folder.rstrip("/")
    parts = folder.split("/")
    if (len(parts) != 4
            or parts[0] != "users"
            or parts[2] != "dashboards"):
        raise ValueError(
            f"refresh_runner: --folder must match "
            f"'users/<kerberos>/dashboards/<id>' (got {folder!r})"
        )
    return folder, parts[1], parts[3]


def _classify_exception(exc: BaseException) -> str:
    """Map an exception to a §5.6 classification string for the modal's
    classification pill. Heuristic-based; falls back to the exception's
    class name when no pattern matches."""
    msg = str(exc).lower()
    name = type(exc).__name__
    if "no data" in msg or "empty" in msg and "dataframe" in msg:
        return "data_pull_empty"
    if name in ("ConnectionError", "Timeout", "TimeoutError",
                  "ConnectionResetError", "ConnectionAbortedError"):
        return "network_error"
    if "connection" in msg or "timeout" in msg or "timed out" in msg:
        return "network_error"
    if name in ("KeyError", "AttributeError"):
        return "data_schema_error"
    if name == "FileNotFoundError" or "filenotfounderror" in msg:
        return "missing_artifact"
    if "compile" in msg and "fail" in msg:
        return "compile_failed"
    return name or "unknown"


def _update_registry(kerberos: str, dashboard_id: str, status: str) -> None:
    """Stamp ``last_refreshed`` + ``last_refresh_status`` on the dashboard
    entry in ``users/<kerberos>/dashboards/dashboards_registry.json``.
    Raises if the entry isn't there -- a missing registry entry means
    Django allowed a refresh on an unregistered dashboard (a bug
    upstream that should surface, not be papered over)."""
    registry_path = f"users/{kerberos}/dashboards/dashboards_registry.json"
    raw = s3_manager.get(registry_path)
    registry = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    matched = False
    for dash in registry.get("dashboards", []):
        if dash.get("id") == dashboard_id:
            dash["last_refreshed"] = _utcnow_iso()
            dash["last_refresh_status"] = status
            matched = True
            break
    if not matched:
        raise RuntimeError(
            f"refresh_runner: dashboard {dashboard_id!r} not in "
            f"{registry_path}; runner cannot stamp status"
        )
    registry["last_updated"] = _utcnow_iso()
    s3_manager.put(
        json.dumps(registry, indent=2).encode("utf-8"),
        registry_path,
    )


def _list_pulls(folder: str) -> list:
    """Read PULLS keys from <folder>/scripts/pull_data.py without running
    them. Used by the runner to drive run_pull(folder, name) per pull
    so a per-pull failure surfaces the failing pull's name in the
    `script` field of the §8.1 errors[] entry."""
    src = s3_manager.get(f"{folder}/scripts/pull_data.py").decode("utf-8")
    ns: dict = {"__name__": "_runner_introspect", "__builtins__": __builtins__}
    exec(compile(src, f"{folder}/scripts/pull_data.py", "exec"), ns)
    pulls = ns.get("PULLS")
    if not isinstance(pulls, dict):
        raise RuntimeError(
            f"refresh_runner: {folder}/scripts/pull_data.py must define a "
            f"module-level PULLS dict (got {type(pulls).__name__})"
        )
    return list(pulls)


def run(folder: str, log_path: Optional[str] = None) -> int:
    """Refresh the dashboard at ``folder``. Returns process exit code
    (``0`` on success, ``1`` on any failure). The refresh-status JSON
    is the load-bearing observability surface; this function's exit
    code is the secondary signal Django reads.

    ``log_path`` is the filesystem path of the log file the spawner is
    streaming this subprocess's stdout/stderr to. Surfaced verbatim
    into refresh_status.json for PRISM-side triage (§8.1)."""
    folder, kerberos, dashboard_id = _parse_folder(folder)

    started_at = _utcnow_iso()
    pid = os.getpid()
    print(
        f"[refresh_runner] folder={folder} kerberos={kerberos} "
        f"dashboard_id={dashboard_id} pid={pid} started_at={started_at}",
        flush=True,
    )

    running_payload: dict = {"status": "running", "started_at": started_at,
                              "pid": pid}
    if log_path:
        running_payload["log_path"] = log_path
    _put_status(folder, running_payload)

    final_status = "error"
    errors: list = []
    failing_phase = _PHASE_PULL_PREFIX  # default attribution if pre-pull blows up

    try:
        # Phase 1: enumerate pulls + run each via the engine entry point
        pull_names = _list_pulls(folder)
        for name in pull_names:
            failing_phase = f"{_PHASE_PULL_PREFIX}::{name}"
            run_pull(folder, name, s3_manager=s3_manager)

        # Phase 2: build (template + CSVs + transforms -> compile + write)
        failing_phase = _PHASE_BUILD
        build_dashboard(folder, s3_manager=s3_manager)

        # Phase 3: registry stamp
        failing_phase = "<registry>"
        _update_registry(kerberos, dashboard_id, "success")
        final_status = "success"
    except BaseException as exc:
        tb = traceback.format_exc()
        errors.append({
            "script":         failing_phase,
            "classification": _classify_exception(exc),
            "message":        str(exc),
            "traceback":      tb,
        })
        print(
            f"[refresh_runner] FAILED in {failing_phase}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        print(tb, file=sys.stderr, flush=True)

    completed_at = _utcnow_iso()
    started_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
    completed_dt = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
    elapsed = (completed_dt - started_dt).total_seconds()

    final_payload = {
        "status":          final_status,
        "started_at":      started_at,
        "completed_at":    completed_at,
        "elapsed_seconds": round(elapsed, 2),
        "pid":             pid,
        "errors":          errors,
    }
    if log_path:
        final_payload["log_path"] = log_path
    _put_status(folder, final_payload)

    print(
        f"[refresh_runner] done status={final_status} "
        f"elapsed={elapsed:.1f}s errors={len(errors)}",
        flush=True,
    )
    return 0 if final_status == "success" else 1


def main(argv: list = None) -> int:
    parser = argparse.ArgumentParser(
        description="Single-dashboard refresh runner. Spawned by the Django "
                    "Refresh button + the hourly cron.",
    )
    parser.add_argument(
        "--folder", required=True,
        help="Dashboard folder S3 path, e.g. users/<kerberos>/dashboards/<id>",
    )
    parser.add_argument(
        "--log-path", default=None,
        help="Filesystem path the spawner is streaming this subprocess's "
              "stdout/stderr to. Recorded verbatim in refresh_status.json "
              "for PRISM-side triage (§8.1).",
    )
    args = parser.parse_args(argv)
    return run(args.folder, log_path=args.log_path)


if __name__ == "__main__":
    sys.exit(main())
