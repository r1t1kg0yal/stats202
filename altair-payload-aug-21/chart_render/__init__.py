"""Closure-safe chart render core.

This package holds the chart / table rendering primitives that the
secure-execution sandbox needs. It imports only the DS stack (pandas / numpy /
matplotlib / altair / vl-convert / PIL) and the standard library -- never
``core``, ``prism_mcp.utils``, boto3 or the network -- so it can drop into the
minimal sandbox image and be consumed unchanged by the trusted-side chart tools.

The rendering API lives in ``core`` and is star-exported here, so the sandbox
can ``from prism_mcp.chart_render import make_chart, make_table``. Trusted-side
extensions (presigned URLs, the studio editor) are bolted on top by
``prism_mcp.utils.chart_functions`` via ``core.register_trusted_extensions``.
"""

from prism_mcp.chart_render.core import *  # noqa: F403,F401 (public API re-export)
from prism_mcp.chart_render import core as _core

__all__ = list(_core.__all__)