"""Trusted-side chart tools.

A thin layer over the closure-safe render core in ``prism_mcp.chart_render``.
The core renders charts and tables and writes bare S3 handles; it is
import-closed so it can ship in the minimal secure-execution sandbox image.
This module installs the extensions the sandbox must not be able to reach on
its own -- presigned download URLs and the GS font root -- by registering them
on the core, and re-exports the full public API so every existing caller is
unaffected.

The sandbox never imports this module. It imports ``prism_mcp.chart_render``
directly, so neither is registered there and the core keeps the no-op defaults
it ships with. The studio is not among them: it needs nothing the sandbox
lacks, and both tiers load it through ``core.register_studio``.
"""

from prism_meta import REPO_ROOT as _repo_root

from prism_mcp.chart_render import core as _core
from prism_mcp.chart_render.core import *  # noqa: F403,F401 (public API re-export)

# Trusted-side only. The import below reaches something the sandbox image does
# not have -- boto3, the GS network stack -- which is exactly why the core
# cannot import it itself.
from prism_mcp.utils.download_links import generate_presigned_download_url as _presign

_core.register_trusted_extensions(
    presign=_presign,
    font_repo_root=_repo_root,
)
_core.register_studio()

__all__ = list(_core.__all__)
