"""Trusted-side chart tools.

A thin layer over the closure-safe render core in ``prism_mcp.chart_render``.
The core renders charts and tables and writes bare S3 handles; it is
import-closed so it can ship in the minimal secure-execution sandbox image.
This module installs the extensions the sandbox must not be able to reach on
its own -- presigned download URLs, render-failure alerting, and the GS font
root -- by registering them on the core, and re-exports the full public API
so every existing caller is unaffected.

The studio is not one of those extensions. It is stdlib-only and ships inside
``prism_mcp.chart_render`` itself, so this module registers it through the
core's own ``register_studio`` -- the same call a sandboxed render makes.

The sandbox never imports this module. It imports ``prism_mcp.chart_render``
directly, so nothing here runs, the extensions are never registered, and the
core keeps the import-closed no-op defaults it ships with.
"""

from prism_meta import REPO_ROOT as _repo_root

from prism_mcp.chart_render import core as _core
from prism_mcp.chart_render.core import *  # noqa: F403,F401 (public API re-export)

# Trusted-side only. Every import below reaches something the sandbox image does
# not have -- boto3, the GS network stack -- which is exactly why the core
# cannot import them itself.
from prism_mcp.utils.download_links import generate_presigned_download_url as _presign
from prism_mcp.utils.error_handler import send_error_email as _send_error

_core.register_trusted_extensions(
    presign=_presign,
    send_error=_send_error,
    font_repo_root=_repo_root,
)
_core.register_studio()

__all__ = list(_core.__all__)