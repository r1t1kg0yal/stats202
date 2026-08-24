"""Headless-Chrome screenshot driver shared by the chart and dashboard
PNG exporters in ``rendering``."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence, Union


def find_chrome() -> str:
    """Locate the Chrome/Chromium binary. Raises RuntimeError if not found.

    Resolution order:
      1. $CHROME_BIN env var (absolute path)
      2. /Applications/Google Chrome.app/Contents/MacOS/Google Chrome
      3. PATH lookup for google-chrome / chromium / chromium-browser / chrome
    """
    env = os.environ.get("CHROME_BIN")
    if env:
        p = Path(env).expanduser()
        if p.is_file():
            return str(p)
        raise RuntimeError(
            f"CHROME_BIN={env!r} is set but the file does not exist."
        )
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).is_file():
        return mac
    for candidate in ("google-chrome", "chromium", "chromium-browser",
                       "chrome", "Chromium"):
        path = shutil.which(candidate)
        if path:
            return path
    raise RuntimeError(
        "PNG export needs a Chrome/Chromium binary. Install Google Chrome "
        "or set the CHROME_BIN environment variable to the binary path."
    )


def render_via_chrome(
    chrome: str,
    html_path: Union[str, Path],
    output_path: Path,
    *,
    flags: Sequence[str],
    width: int,
    height: int,
    scale: int,
    virtual_time_ms: int,
    timeout_s: float,
    verbose: bool = False,
) -> Path:
    """Screenshot ``html_path`` to ``output_path`` with headless Chrome.

    ``flags`` carries the caller-specific switches (sandbox, scrollbars,
    local-file access) that sit between the fixed headless preamble and
    the fixed geometry/screenshot tail.
    """
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        *flags,
        f"--window-size={int(width)},{int(height)}",
        f"--force-device-scale-factor={int(scale)}",
        f"--virtual-time-budget={int(virtual_time_ms)}",
        "--run-all-compositor-stages-before-draw",
        f"--screenshot={output_path}",
        f"file://{html_path}",
    ]
    if verbose:
        print("  [png_export] " + " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True,
                          timeout=timeout_s)
    if verbose:
        if res.stdout:
            print(res.stdout.strip())
        if res.stderr:
            print(res.stderr.strip(), file=sys.stderr)
    if res.returncode != 0:
        raise RuntimeError(
            f"headless Chrome failed (exit {res.returncode}): "
            f"{(res.stderr or res.stdout).strip()}"
        )
    if not output_path.is_file():
        raise RuntimeError(
            f"Chrome did not write PNG to {output_path}. stderr: "
            f"{res.stderr.strip()}"
        )
    return output_path
