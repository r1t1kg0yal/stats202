"""Clean-process refresh spawn: the engine-side wrapper that runs
``refresh_runner`` in its own interpreter and streams its output to S3."""

from __future__ import annotations

import json
from typing import Any, Dict


def launch_clean_refresh(
    folder: str,
    *,
    mode: str = "full",
) -> Dict[str, Any]:
    """Run the canonical refresh subprocess and return its structured result.

    This is the public authoring wrapper for clean-process verification.
    Callers provide dashboard intent (the canonical folder); the engine owns
    runner resolution, environment markers, S3 log streaming, metadata, wait,
    status collection, and failure propagation.

    ``mode`` is ``"full"`` (pull + compile + HTML; default, cron / Tool 4)
    or ``"light"`` (pull + manifest datasets only; Refresh button /
    open-tab cadence).
    """
    import os
    import subprocess
    import sys
    import time

    from dashboards import refresh_runner as runner_module
    from dashboards_time import utcnow
    # Qualified: the bare name is a second module object with its own
    # exception classes, so RefreshAttachmentError would escape callers'
    # ``except dashboards.RefreshAttachmentError``.
    from dashboards.echart_dashboard import (
        _audit_refresh_attachment,
        _canonical_dashboard_identity,
        _resolve_s3_manager,
    )
    from prism_mcp.utils.s3_log_streamer import (
        S3LogPathBuilder, S3LogStreamer,
    )

    canonical, _kerberos, _dashboard_id = _canonical_dashboard_identity(
        folder
    )
    s3 = _resolve_s3_manager(None)
    _audit_refresh_attachment(canonical, s3_manager=s3, strict=True)
    spawn_ts = utcnow()
    slug = canonical.replace("/", "_")
    # Logs go to the centralized subprocess tree only. A session-side copy
    # (S3LogPathBuilder.build_session_side) would root a per-cycle folder
    # inside the dashboard folder itself, where nothing reads it and the S3
    # cleaner cannot reach it -- `users/` is on the cleaner's allowlist, so
    # only the centralized copy is subject to SUBPROCESS_LOGS_TTL_DAYS.
    folder_key, log_key, metadata_key, _completion_key = (
        S3LogPathBuilder.build(
            kind="dashboard_refresh",
            session_description=slug,
            ts=spawn_ts,
        )
    )
    mode_norm = (mode or "full").strip().lower()
    if mode_norm not in ("full", "light"):
        raise ValueError(
            f"launch_clean_refresh: mode must be 'full' or 'light' "
            f"(got {mode!r})"
        )
    env = os.environ.copy()
    env["PRISM_SUBPROCESS_S3_FOLDER_KEY"] = folder_key
    header = (
        "=== refresh_runner spawn ===\n"
        f"folder: {canonical}\n"
        f"mode: {mode_norm}\n"
        f"started: {spawn_ts.isoformat()}\n"
        f"s3_log_key: {log_key}\n"
        + "=" * 60 + "\n"
    ).encode("utf-8")
    pipe_r, pipe_w = os.pipe()
    streamer = None
    process = None
    try:
        started = time.time()
        process = subprocess.Popen(
            [
                sys.executable,
                runner_module.__file__,
                "--folder", canonical,
                "--log-path", log_key,
                "--mode", mode_norm,
            ],
            stdout=pipe_w,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
        )
        os.close(pipe_w)
        pipe_w = -1
        streamer = S3LogStreamer(
            fd=pipe_r,
            s3_log_key=log_key,
            header=header,
        )
        streamer.start()
        pipe_r = -1
        metadata_blob = {
            "pid": process.pid,
            "started_at": spawn_ts.isoformat(),
            "folder": canonical,
            "mode": mode_norm,
            "s3_log_key": log_key,
            "s3_folder_key": folder_key,
            "kind": "dashboard_refresh",
        }
        s3.put(metadata_blob, metadata_key)
        returncode = process.wait()
        elapsed = round(time.time() - started, 2)
        status_path = f"{canonical}/refresh_status.json"
        status = None
        if s3.exists(status_path):
            status = json.loads(
                bytes(s3.get(status_path)).rstrip(b"\x00").decode("utf-8")
            )
        result = {
            "folder": canonical,
            "returncode": returncode,
            "elapsed_seconds": elapsed,
            "log_path": log_key,
            "s3_log_key": log_key,
            "s3_folder_key": folder_key,
            "pid": process.pid,
            "status": status,
        }
        review_required = (
            isinstance(status, dict)
            and status.get("status") == "review_required"
        )
        if returncode != 0 and not review_required:
            raise RuntimeError(
                f"clean refresh failed with returncode {returncode}; "
                f"log_path={log_key}; status={status!r}"
            )
        return result
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait()
        raise
    finally:
        for fd in (pipe_r, pipe_w):
            if fd != -1:
                try:
                    os.close(fd)
                except OSError:
                    pass
