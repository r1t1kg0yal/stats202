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
from typing import Optional

from ai_development.core.s3_bucket_manager import s3_manager
from ai_development.dashboards import build_dashboard, run_pull
from ai_development.dashboards.dashboards_time import (
    format_iso, freq_delta, parse_iso, utcnow,
)


# Phase tags used in the per-error `script` field so the §8.1 modal +
# Copy-for-PRISM markdown surface "which phase blew up" without the
# runner having to re-introspect the traceback.
_PHASE_PULL_PREFIX = "scripts/pull_data.py"
_PHASE_PULL_LOAD   = "scripts/pull_data.py::<load>"  # module-level imports + PULLS dict literal
_PHASE_BUILD       = "scripts/build.py"
_PHASE_PARSE       = "<argparse>"


def _utcnow_iso() -> str:
    """ISO-8601 UTC for status / registry stamps. Routes through the
    canonical ``dashboards_time`` module (``+00:00`` emit; ``parse_iso``
    accepts both ``+00:00`` and legacy ``Z``-suffix registry entries
    transparently)."""
    return format_iso(utcnow())


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


def _read_registry_entry(kerberos: str, dashboard_id: str) -> dict:
    """Read the dashboard entry from
    ``users/<kerberos>/dashboards/dashboards_registry.json``. Raises if
    the entry isn't there -- a missing registry entry means Django
    allowed a refresh on an unregistered dashboard (a bug upstream that
    should surface, not be papered over). Used at the start of
    ``run()`` to fetch ``refresh_frequency`` for ``next_refresh_at``
    computation."""
    registry_path = f"users/{kerberos}/dashboards/dashboards_registry.json"
    raw = s3_manager.get(registry_path)
    registry = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    for dash in registry.get("dashboards", []):
        if dash.get("id") == dashboard_id:
            return dash
    raise RuntimeError(
        f"refresh_runner: dashboard {dashboard_id!r} not in "
        f"{registry_path}; runner cannot read entry"
    )


def _update_registry(kerberos: str, dashboard_id: str, status: str,
                       *, refreshed_at: str) -> None:
    """Stamp ``last_refreshed`` + ``last_refresh_status`` on the dashboard
    entry. ``refreshed_at`` is supplied by ``run()`` so the registry's
    ``last_refreshed`` matches ``metadata.time.refresh_cycle_at`` byte-for-
    byte (single source of truth for "when did this cycle start").
    Raises if the entry isn't there."""
    registry_path = f"users/{kerberos}/dashboards/dashboards_registry.json"
    raw = s3_manager.get(registry_path)
    registry = json.loads(raw.rstrip(b"\x00").decode("utf-8"))
    matched = False
    for dash in registry.get("dashboards", []):
        if dash.get("id") == dashboard_id:
            dash["last_refreshed"] = refreshed_at
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
    failing_phase = _PHASE_PULL_LOAD  # default attribution if module-level load blows up

    # Cycle anchor — single utcnow() that flows into:
    #   - metadata.time.refresh_cycle_at (via build_dashboard kwarg)
    #   - registry.dashboards[].last_refreshed (via _update_registry)
    # so the chrome pill and the registry agree on "when did this
    # cycle's data land" to the same byte. Captured here, not inside
    # build_dashboard, so the value survives a build-phase failure
    # (we still want the cycle anchor stamped on the status row).
    cycle_dt = utcnow()
    cycle_iso = format_iso(cycle_dt)

    # next_refresh_at is best-effort: requires the registry entry's
    # refresh_frequency. If the registry read fails (deleted entry,
    # corrupt JSON), proceed without it -- the build still runs, the
    # pill just won't carry a "next refresh in N minutes" hint.
    next_refresh_iso: Optional[str] = None
    try:
        entry = _read_registry_entry(kerberos, dashboard_id)
        delta = freq_delta(entry.get("refresh_frequency", "daily"))
        if delta is not None:
            next_refresh_iso = format_iso(cycle_dt + delta)
    except Exception as exc:
        # Non-fatal: log and continue with next_refresh_at=None.
        print(
            f"[refresh_runner] registry read FAILED (non-fatal): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )

    try:
        # Phase 1: enumerate pulls + run each via the engine entry point.
        # _list_pulls execs pull_data.py at module level (imports + PULLS
        # dict literal) so an import failure / syntax error here surfaces
        # under _PHASE_PULL_LOAD before any pull runs. Once we have the
        # pull names, each iteration retags failing_phase to the specific
        # pull about to run.
        pull_names = _list_pulls(folder)
        for name in pull_names:
            failing_phase = f"{_PHASE_PULL_PREFIX}::{name}"
            run_pull(folder, name, s3_manager=s3_manager)

        # Phase 2: build (template + CSVs + transforms -> compile + write).
        # Pass cycle_iso so build_dashboard stamps metadata.time.refresh_
        # cycle_at; the chrome pill renders "refreshed <ET wall time>"
        # off this value. next_refresh_iso is optional ("next refresh
        # in N minutes" UX is future; the field is observability-only
        # today).
        failing_phase = _PHASE_BUILD
        build_dashboard(
            folder, s3_manager=s3_manager,
            refresh_cycle_at=cycle_iso,
            next_refresh_at=next_refresh_iso,
        )

        # Phase 3: registry stamp -- last_refreshed matches the cycle
        # anchor passed into build_dashboard byte-for-byte.
        failing_phase = "<registry>"
        _update_registry(kerberos, dashboard_id, "success",
                          refreshed_at=cycle_iso)
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
    started_dt = parse_iso(started_at)
    completed_dt = parse_iso(completed_at)
    elapsed = (
        (completed_dt - started_dt).total_seconds()
        if started_dt and completed_dt else 0.0
    )

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
