"""
ai_development/dashboards -- ECharts dashboard compiler + folder operations.

Scope: dashboards only. ``compile_dashboard`` lowers a JSON manifest into
an interactive HTML dashboard. ECharts is NOT the path PRISM uses for
one-off charts in chat / email / report -- that surface lives in Altair
(``ai_development/mcp/utils/chart_functions.py``). The two engines must
not converge: do not surface ``make_echart`` or ``EChartResult`` from
this package as part of the PRISM-injected runtime namespace; they are
internal substrate for ``compile_dashboard``'s lowering pipeline only.
Multi-panel composition is a manifest concern (rows / cols / tabs in
the dashboard layout), not a separate one-off composite-canvas API --
those n-pack composite helpers belong to Altair's static-PNG surface.

Public surface PRISM imports (real Python imports -- no namespace
injection at exec time):

    # Folder operations -- the three entry points for every dashboard op.
    # Operate on a dashboard folder (S3 path); call from PRISM ephemeral
    # code OR from refresh_runner.py.
    from ai_development.dashboards import (
        run_pull,                  # run ONE pull from PULLS (in-process)
        build_dashboard,           # template + CSVs + transforms -> compile
        refresh_dashboard,         # all PULLS + build_dashboard
    )

    # Compile primitives (used by build_dashboard internally; PRISM rarely
    # calls these directly under the new model).
    from ai_development.dashboards import (
        compile_dashboard,         # JSON manifest -> dashboard HTML + JSON
        validate_manifest,         # dry-run structural validator
        manifest_template,         # strip data -> reusable template
        populate_template,         # template + fresh DataFrames -> manifest
        df_to_source,              # DataFrame -> canonical list-of-lists
        load_manifest, save_manifest,
    )
    # chart_data_diagnostics is exposed via the same module for post-
    # compile linting (empty datasets, all-NaN columns, etc.).

Sibling scripts (also part of the payload):

    refresh_runner.py    single-dashboard CLI invoked by the Django
                          [Refresh] button via subprocess.Popen.
                          Runs refresh_dashboard(folder).
    refresh_dashboards.py
                          hourly cron entry point. Walks UserRegistry,
                          per-user reads dashboards_registry.json,
                          spawns refresh_runner.py per due dashboard.

Internal-only modules (still drag-and-drop installed, not part of the
public surface):

    config.py            brand tokens + theme + palettes + dimensions
    echart_studio.py     single-chart builder (used internally by the
                          dashboard compiler when lowering each
                          ``widget: chart`` in the manifest)
    rendering.py         editor HTML + dashboard HTML + headless-Chrome
                          PNG export (driven by ``compile_dashboard``)

Design: the manifest.json is the source of truth. ``compile_dashboard``
takes that JSON (dict, path, or JSON string), validates, lowers each
``widget: chart`` through the internal builders, and emits manifest +
interactive HTML. ``build_dashboard(folder)`` wraps that lifecycle for
the standard "load template + CSVs + transforms -> compile + write to
S3" recipe so PRISM doesn't reinvent it per dashboard.

DataFrame contract: PRISM emits Python that builds DataFrames from real
data functions (``pull_market_data``, ``pull_haver_data``, FRED, etc.)
and stores them as dataset values. Literal numbers never appear in the
JSON emitted by PRISM. Three accepted shapes for a dataset entry, all
normalised to the same on-disk form by the compiler:

    manifest["datasets"]["rates"] = df_rates                    # shorthand
    manifest["datasets"]["rates"] = {"source": df_rates}        # explicit
    manifest["datasets"]["rates"] = {"source": df_to_source(df_rates)}

Zero runtime deps beyond Python stdlib + pandas for DataFrame
conversion. The emitted HTML inlines ECharts (~1MB) read from the
local `ai_development/mysite/news/static/js/echarts.js` mirror so the
dashboard is portable: it renders identically when served by Django,
opened from a file:// path, or streamed from S3 via a presigned URL.
"""

from __future__ import annotations

__version__ = "0.4.0"

from ai_development.dashboards.echart_dashboard import (  # noqa: E402,F401
    run_pull,
    build_dashboard,
    refresh_dashboard,
    compile_dashboard,
    validate_manifest,
    manifest_template,
    populate_template,
    df_to_source,
    load_manifest,
    save_manifest,
    chart_data_diagnostics,
    Manifest,
    DashboardResult,
)


# -------------------------------------------------------------
# Folder sanctity audit (canonical 5-path check)
#
# The L2 dashboards module (context/modules/static/tools/dashboards_hub.md
# section 2.5) documents this helper as the canonical pre-edit /
# post-build audit. It must be importable from
# ``ai_development.dashboards`` so PRISM ephemeral scripts (Tool 2
# build wrap-up, Recipe 2 section C step 1, Recipe 3 section D step 1)
# can call it without inlining the body each time.

_AUDIT_REQUIRED_PATHS = [
    "manifest_template.json",
    "manifest.json",
    "dashboard.html",
    "scripts/pull_data.py",
    "scripts/build.py",
]


def _audit_dashboard_layout(folder, manifest=None, *, s3_manager=None):  # noqa: F401
    """Confirm the canonical 5 paths exist under ``<folder>``.

    Raises ``ValueError`` listing the missing path(s) if any are
    absent. Does NOT enforce exclusivity -- anything else under the
    folder is fine; use ``archive/<UTC>/`` for rogue files you want to
    keep around for reference.

    Parameters
    ----------
    folder : str
        Dashboard folder path on S3
        (e.g. ``users/<kerberos>/dashboards/<name>``).
    manifest : dict, optional
        Loaded manifest dict. Currently unused but accepted for
        forward-compat with the documented call signature
        ``_audit_dashboard_layout(folder, m)``.
    s3_manager : optional
        S3 manager instance. If omitted, falls back to the singleton
        from ``ai_development.core.s3_bucket_manager``.

    Raises
    ------
    ValueError
        If one or more of the canonical 5 paths is missing from
        ``<folder>``.
    """
    if s3_manager is None:
        from ai_development.core.s3_bucket_manager import s3_manager as _s3
        s3_manager = _s3

    folder = folder.rstrip("/")
    listing_raw = s3_manager.list(folder)

    # ``s3_manager.list()`` returns ``List[str]`` (full keys) in the
    # PRISM sandbox. Tolerate the AWS-SDK ``List[dict]`` shape too in
    # case a caller passes a custom client (the staging stub at
    # ``projects/echarts/ai_development/core/s3_bucket_manager.py``
    # returns ``[{"Key": ...}]`` for parity with the boto3 surface).
    listing = set()
    for entry in listing_raw:
        key = entry["Key"] if isinstance(entry, dict) else entry
        if not key:
            continue
        rel = key.replace(f"{folder}/", "", 1).lstrip("/")
        listing.add(rel)

    missing = [r for r in _AUDIT_REQUIRED_PATHS if r not in listing]
    if missing:
        raise ValueError(
            f"_audit_dashboard_layout: {folder} missing required path(s): "
            f"{missing}"
        )
    return True
