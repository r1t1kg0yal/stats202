"""Trusted-side chart tools.

A thin layer over the closure-safe render core in ``prism_mcp.chart_render``.
The core renders charts and tables and writes bare S3 handles; it is
import-closed so it can ship in the minimal secure-execution sandbox image.
This module installs the extensions the sandbox must not be able to reach on
its own -- presigned download URLs, the interactive studio editor, vision
quality-check, render-failure alerting, and the GS font root -- by registering
them on the core, and re-exports the full public API so every existing caller
is unaffected.

The sandbox never imports this module. It imports ``prism_mcp.chart_render``
directly, so nothing here runs, the extensions are never registered, and the
core keeps the import-closed no-op defaults it ships with.
"""

from prism_meta import REPO_ROOT as _repo_root

from prism_mcp.chart_render import core as _core
from prism_mcp.chart_render.core import *  # noqa: F403,F401 (public API re-export)

# Trusted-side only. Every import below reaches something the sandbox image does
# not have -- boto3, the GS network stack, the studio's browser assets -- which
# is exactly why the core cannot import them itself.
from prism_mcp.utils.download_links import generate_presigned_download_url as _presign
from prism_mcp.utils.vision_functions import check_chart_quality as _chart_quality
from prism_mcp.utils.error_handler import send_error_email as _send_error
from prism_mcp.utils import chart_functions_studio as _chart_studio
from prism_mcp.utils.chart_functions_studio import (
    DIMENSION_PRESETS as _studio_dimension_presets,
    _compute_chart_id,
)
from prism_mcp.utils import chart_functions_studio_tables as _table_studio

_core.register_trusted_extensions(
    presign=_presign,
    chart_quality=_chart_quality,
    send_error=_send_error,
    chart_studio=_chart_studio,
    table_studio=_table_studio,
    studio_dimension_presets=_studio_dimension_presets,
    compute_chart_id=_compute_chart_id,
    font_repo_root=_repo_root,
)

__all__ = list(_core.__all__)