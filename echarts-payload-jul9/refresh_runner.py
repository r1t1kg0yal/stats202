#!/usr/bin/env python3
"""refresh_runner.py -- single-dashboard refresh CLI.

Spawned by the Django Refresh button handler (POST
``/api/dashboard/refresh/``) and by the hourly cron
(``refresh_dashboards.py``). Runs ``run_pull`` for every ``PULLS``
entry, then ``build_dashboard`` for the named folder, then writes
``<folder>/refresh_status.json`` with the outcome.

Usage::

    python -m dashboards.refresh_runner \
        --folder    users/<kerberos>/dashboards/<name> \
        --log-path  subprocess_logs/YYYY/MM/DD/.../run.log   # optional S3 key

Status JSON shape (matches the polling endpoint contract documented in
``prism/dashboard-refresh.md`` \u00a78.1 so the in-browser failure modal
renders all fields, including the per-error ``script`` +
``classification`` pills and the ``log_path`` PRISM-triage field)::

    {
        "status":          "running" | "success" | "error",
        "started_at":      "2026-05-04T21:30:11.123456+00:00",
        "completed_at":    "2026-05-04T21:30:55.789012+00:00",  # final only
        "elapsed_seconds": 44.67,                                # final only
        "pid":             12345,
        "log_path":        "subprocess_logs/.../run.log",        # if --log-path
        "errors":          [{"script": "scripts/pull_data.py",
                              "classification": "data_pull_empty",
                              "message":   "...",
                              "traceback": "..."}],              # final only
    }

Subprocess log streaming: stdout/stderr drains to S3 keys under
``subprocess_logs/YYYY/MM/DD/...`` via ``S3LogStreamer`` (one daemon
thread per spawn). No ``/tmp/`` fallback -- the legacy filesystem path
has been retired. The S3 log key is passed in via ``--log-path`` so it
lands verbatim in ``refresh_status.json`` for triage UX.

The spawner sets ``PRISM_SUBPROCESS_S3_FOLDER_KEY`` in the subprocess
environment so ``register_completion_marker()`` (called at the top of
``main()``) writes ``completion.json`` next to the streamed log,
letting a reader distinguish "still running" / "finished cleanly" /
"finished with error" / "parent died" by inspecting the S3 folder.
The marker is a no-op when the env var is absent (e.g. direct CLI
invocation outside the spawner), so ``python refresh_runner.py
--folder ...`` for ad-hoc / staging runs stays clean.

PRISM-side imports only; no fallbacks. Single canonical resolution
path for the engine, the user manifest, and ``s3_manager``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from typing import Any, Optional

import sys, os
print('=' * 80, flush=True)
print(f'[REFRESH_RUNNER] PID={os.getpid()}', flush=True)
print(f'[REFRESH_RUNNER] sys.executable={sys.executable}', flush=True)
print(f'[REFRESH_RUNNER] sys.prefix={sys.prefix}', flush=True)
print(f'[REFRESH_RUNNER] sys.path:', flush=True)
for p in sys.path:
    print(f'[REFRESH_RUNNER]   {p}', flush=True)
print(f'[REFRESH_RUNNER] os.environ PYTHONPATH={os.environ.get("PYTHONPATH","<unset>")}', flush=True)
print(f'[REFRESH_RUNNER] os.environ PYTHONHOME={os.environ.get("PYTHONHOME","<unset>")}', flush=True)

import importlib.util

# Check if the submodule exists
spec_csvs = importlib.util.find_spec("pandas.io.formats.csvs")
spec_string = importlib.util.find_spec("pandas.io.formats.string")

print("[REFRESH_RUNNER] csvs exists:", spec_csvs is not None)
print("[REFRESH_RUNNER] string exists:", spec_string is not None)
import importlib.util

# Check if the submodule exists
spec_csvs = importlib.util.find_spec("pandas.io.formats.csvs")
spec_string = importlib.util.find_spec("pandas.io.formats.string")

print("[REFRESH_RUNNER] csvs exists:", spec_csvs is not None)
print("[REFRESH_RUNNER] string exists:", spec_string is not None)

print('=' * 80, flush=True)

from core.s3_bucket_manager import s3_manager
from dashboards import build_dashboard, run_pull
from dashboards.dashboards_time import (
    format_iso, freq_delta, parse_iso, utcnow,
)
from prism_mcp.utils.subprocess_completion import (
    register_completion_marker,
)
from prism_mcp.utils.data_functions import (
    pull_market_data, pull_haver_data, pull_plottool_data,
    pull_fred_data, save_artifact,
)


def _build_exec_namespace() -> dict:
    """Canonical exec namespace for user-authored pull_data.py and build.py
    scripts. Mirrors what the in-session sandbox pre-injects (s3_manager,
    pull_market_data, pull_haver_data, pull_plottool_data, pull_fred_data,
    save_artifact) so scripts authored in the sandbox are portable to the
    clean subprocess interpreter the refresh runner uses.

    Without this, user pull_data.py scripts that omit explicit imports raise
    NameError on the first refresh_runner tick (see ticket signature
    refresh_runner:pull_data.py:NameError:pull_market_data, recurring across
    9+ tickets as of 2026-05-16)."""
    return {
        '__name__': '__main__',
        '__builtins__': __builtins__,
        's3_manager': s3_manager,
        'pull_market_data': pull_market_data,
        'pull_haver_data': pull_haver_data,
        'pull_plottool_data': pull_plottool_data,
        'pull_fred_data': pull_fred_data,
        'save_artifact': save_artifact,
    }


# Phase tags used in the per-error ``script`` field so the \u00a78.1 modal +
# Copy-for-PRISM markdown surface "which phase blew up" without the
# runner having to re-introspect the traceback.
_PHASE_PULL_PREFIX = "scripts/pull_data.py"
_PHASE_PULL_LOAD = "scripts/pull_data.py::<load>"
_PHASE_BUILD = "scripts/build.py"
_PHASE_REGISTRY = "<registry>"


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


def _read_status(folder: str) -> Optional[dict]:
    """Read ``refresh_status.json`` for ``folder``. Returns ``None`` if
    the file is missing, unreadable, or malformed. Used at the start of
    ``run()`` to capture the previous ``consecutive_failures`` count so
    the cooldown logic in ``refresh_dashboards`` can back off failing
    dashboards instead of hot-spinning every tick."""
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


def _parse_folder(folder: str) -> tuple:
    """Return ``(folder, kerberos, dashboard_id)`` parsed from a canonical
    folder path ``users/<kerberos>/dashboards/<id>``. Raises if the
    shape doesn't match -- single canonical path, no normalisation
    magic."""
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
    """Map an exception to a \u00a75.6 classification string for the modal's
    classification pill. Heuristic-based; falls back to the exception's
    class name when no pattern matches."""
    msg = str(exc).lower()
    name = type(exc).__name__
    if "no data" in msg or ("empty" in msg and "dataframe" in msg):
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
    ``last_refreshed`` matches ``metadata.time.refresh_cycle_at``
    byte-for-byte (single source of truth for "when did this cycle
    start"). Raises if the entry isn't there."""
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
    """Read ``PULLS`` keys from ``<folder>/scripts/pull_data.py`` without
    running them. Used by the runner to drive ``run_pull(folder, name)``
    per pull so a per-pull failure surfaces the failing pull's name in
    the ``script`` field of the \u00a78.1 ``errors[]`` entry."""
    src = s3_manager.get(f"{folder}/scripts/pull_data.py").decode("utf-8")
    ns: dict = {"__name__": "_runner_introspect", "__builtins__": __builtins__}

    # DEBUG: dump exec namespace and check what pull_data.py expects
    print(f"[_LIST_PULLS] folder={folder}", flush=True)
    print(f"[_LIST_PULLS] script length={len(src)} chars", flush=True)
    print(f"[_LIST_PULLS] first 500 chars:\n{src[:500]}", flush=True)
    print(f"[_LIST_PULLS] namespace keys before exec: {list(ns.keys())}", flush=True)
    # Look for the call sites that will fail
    import re as _re
    bad_refs = _re.findall(
        r'\b(pull_market_data|pull_haver_data|pull_plottool_data|pull_fred_data|s3_manager|make_chart)\b', src)
    print(f"[_LIST_PULLS] script references injected names: {set(bad_refs)}", flush=True)
    print(f"[_LIST_PULLS] These MUST be imported at the top of pull_data.py for refresh to work", flush=True)
    import importlib.util

    # Check if the submodule exists
    spec_csvs = importlib.util.find_spec("pandas.io.formats.csvs")
    spec_string = importlib.util.find_spec("pandas.io.formats.string")

    print("[_LIST_PULLS] csvs exists:", spec_csvs is not None)
    print("[_LIST_PULLS] string exists:", spec_string is not None)

    ns: dict = _build_exec_namespace()
    ns["__name__"] = "_runner_introspect"
    exec(compile(src, f"{folder}/scripts/pull_data.py", "exec"), ns)
    pulls = ns.get("PULLS")
    if not isinstance(pulls, dict):
        raise RuntimeError(
            f"refresh_runner: {folder}/scripts/pull_data.py must define a "
            f"module-level PULLS dict (got {type(pulls).__name__})"
        )
    return list(pulls)


def _count_widgets(layout: Any) -> int:
    """Count widget cells in a manifest ``layout`` block. Handles both
    the ``grid`` (``rows[][]``) and ``tabs`` (``tabs[].rows[][]``) kinds.
    Used purely for the [PHASE 2/3] one-line summary so an operator can
    tell at a glance how many widgets the build emitted."""
    if not isinstance(layout, dict):
        return 0
    rows: list = []
    if layout.get("kind") == "tabs":
        for tab in layout.get("tabs", []):
            if isinstance(tab, dict):
                rows.extend(tab.get("rows", []))
    else:
        rows = list(layout.get("rows", []))
    n = 0
    for row in rows:
        if isinstance(row, list):
            for cell in row:
                if isinstance(cell, dict) and "widget" in cell:
                    n += 1
    return n


def _banner(text: str) -> None:
    """Print a phase-block banner: ``====== text ======``. Plain ASCII;
    no ANSI -- the streamed bytes land in the S3 log key and any color
    codes there would be noise when read back via boto."""
    print(f"====== {text} ======", flush=True)


def run(folder: str, log_path: Optional[str] = None) -> int:
    """Refresh the dashboard at ``folder``. Returns process exit code
    (``0`` on success, ``1`` on any failure). The refresh-status JSON
    is the load-bearing observability surface; this function's exit
    code is the secondary signal Django reads.

    ``log_path`` is the S3 key the spawner is streaming this
    subprocess's stdout/stderr to via ``S3LogStreamer``. Surfaced
    verbatim into ``refresh_status.json`` for PRISM-side triage
    (\u00a78.1)."""
    folder, kerberos, dashboard_id = _parse_folder(folder)

    started_at = _utcnow_iso()
    pid = os.getpid()
    started_perf = time.perf_counter()

    _banner(f"refresh_runner {folder} -- pid={pid}")
    print(f"started_at={started_at}", flush=True)
    if log_path:
        print(f"log_path={log_path}", flush=True)

    # Capture the prior status BEFORE we overwrite it with "running" --
    # consecutive_failures is the count of consecutive error / partial
    # outcomes ending with the PREVIOUS run. Used to extend the failure
    # cooldown via exponential backoff on the next cron walk
    # (refresh_dashboards._failure_cooldown reads this field).
    prior_status = _read_status(folder)
    prior_failure_count = 0
    if prior_status and prior_status.get("status") in ("error", "partial"):
        try:
            prior_failure_count = int(
                prior_status.get("consecutive_failures", 0)
            )
        except (TypeError, ValueError):
            prior_failure_count = 0
        prior_failure_count = max(0, prior_failure_count)

    running_payload: dict = {"status": "running", "started_at": started_at,
                              "pid": pid}
    if log_path:
        running_payload["log_path"] = log_path
    _put_status(folder, running_payload)

    final_status = "error"
    errors: list = []
    failing_phase = _PHASE_PULL_LOAD  # default attribution if module-level load blows up

    # Cycle anchor -- single utcnow() that flows into:
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
        # Non-fatal: log to stderr (which the spawner merges into the
        # same S3 log key via subprocess.STDOUT) and continue with
        # next_refresh_at=None.
        print(
            f"WARN registry read failed (non-fatal): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )

    try:
        # PHASE 1: enumerate pulls + run each via the engine entry
        # point. _list_pulls execs pull_data.py at module level
        # (imports + PULLS dict literal) so an import failure / syntax
        # error here surfaces under _PHASE_PULL_LOAD before any pull
        # runs. Once we have the pull names, each iteration retags
        # failing_phase to the specific pull about to run.
        pull_names = _list_pulls(folder)
        print(f"[PHASE 1/3] pulls ({len(pull_names)} found)", flush=True)
        for name in pull_names:
            failing_phase = f"{_PHASE_PULL_PREFIX}::{name}"
            t0 = time.perf_counter()
            run_pull(folder, name, s3_manager=s3_manager)
            print(
                f"    pull {name}  \u2713  {time.perf_counter() - t0:.2f}s",
                flush=True,
            )

        # PHASE 2: build (template + CSVs + transforms -> compile +
        # write). Pass cycle_iso so build_dashboard stamps
        # metadata.time.refresh_cycle_at; the chrome pill renders
        # "refreshed <ET wall time>" off this value. next_refresh_iso
        # is optional ("next refresh in N minutes" UX is future; the
        # field is observability-only today).
        failing_phase = _PHASE_BUILD
        print(f"[PHASE 2/3] build", flush=True)
        t0 = time.perf_counter()
        manifest = build_dashboard(
            folder, s3_manager=s3_manager,
            refresh_cycle_at=cycle_iso,
            next_refresh_at=next_refresh_iso,
        )
        build_dt = time.perf_counter() - t0
        if isinstance(manifest, dict):
            widgets = _count_widgets(manifest.get("layout", {}))
            datasets_n = len(manifest.get("datasets", {}) or {})
        else:
            widgets = 0
            datasets_n = 0
        print(
            f"    build_dashboard  \u2713  {build_dt:.2f}s  "
            f"widgets={widgets} datasets={datasets_n}",
            flush=True,
        )

        # PHASE 3: registry stamp -- last_refreshed matches the cycle
        # anchor passed into build_dashboard byte-for-byte.
        failing_phase = _PHASE_REGISTRY
        print(f"[PHASE 3/3] registry stamp", flush=True)
        _update_registry(kerberos, dashboard_id, "success",
                          refreshed_at=cycle_iso)
        print(
            f"    last_refreshed={cycle_iso}  \u2713",
            flush=True,
        )
        final_status = "success"
    except BaseException as exc:
        tb = traceback.format_exc()
        klass = _classify_exception(exc)
        errors.append({
            "script":         failing_phase,
            "classification": klass,
            "message":        str(exc),
            "traceback":      tb,
        })
        # Concise failure marker on stdout so the structured log carries
        # the failure phase + classification inline; full traceback to
        # stderr (which the spawner merges into the same log key via
        # subprocess.STDOUT). Any phase header for the phase that blew
        # up has already been printed; the per-event line for that
        # phase has NOT (because we raised before reaching it).
        print(
            f"    [FAIL @ {failing_phase}]  {klass}: {exc}",
            flush=True,
        )
        print(
            f"FAIL phase={failing_phase} class={klass}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr, flush=True,
        )
        print(tb, file=sys.stderr, flush=True)

    completed_at = _utcnow_iso()
    elapsed = time.perf_counter() - started_perf

    # consecutive_failures: resets to 0 on success, increments on
    # error / partial. Consumed by refresh_dashboards._is_due to apply
    # exponential cooldown so a chronically-failing dashboard stops
    # spamming the cron every tick.
    if final_status == "success":
        consecutive_failures = 0
    else:
        consecutive_failures = prior_failure_count + 1

    final_payload = {
        "status":               final_status,
        "started_at":           started_at,
        "completed_at":         completed_at,
        "elapsed_seconds":      round(elapsed, 2),
        "pid":                  pid,
        "errors":               errors,
        "consecutive_failures": consecutive_failures,
    }
    if log_path:
        final_payload["log_path"] = log_path
    _put_status(folder, final_payload)

    _banner(
        f"runner done -- status={final_status}  "
        f"elapsed={elapsed:.2f}s  errors={len(errors)}"
    )
    return 0 if final_status == "success" else 1


def main(argv: Optional[list] = None) -> int:
    # Phase 3 of the subprocess_s3_log migration: register a completion
    # marker so a reader can distinguish "still running" / "finished
    # cleanly" / "finished with error" / "parent died" by inspecting
    # the S3 folder. No-ops cleanly when PRISM_SUBPROCESS_S3_FOLDER_KEY
    # is absent (e.g. direct CLI invocation outside the spawner -- the
    # ad-hoc / staging path).
    register_completion_marker()

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
        help="S3 key the spawner is streaming this subprocess's "
              "stdout/stderr to (via S3LogStreamer). Recorded verbatim in "
              "refresh_status.json for PRISM-side triage (\u00a78.1). Legacy "
              "/tmp/ paths are no longer accepted -- all subprocess logs "
              "live under subprocess_logs/YYYY/MM/DD/...; the local "
              "staging stub writes to <sandbox>/_logs/<flat-key> instead.",
    )
    args = parser.parse_args(argv)
    return run(args.folder, log_path=args.log_path)


if __name__ == "__main__":
    sys.exit(main())
