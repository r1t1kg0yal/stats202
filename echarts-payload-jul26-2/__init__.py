"""
dashboards -- ECharts dashboard compiler + folder operations.

Scope: dashboards only. ``compile_dashboard`` lowers a JSON manifest into
an interactive HTML dashboard. ECharts is NOT the path PRISM uses for
one-off charts in chat / email / report -- that surface lives in Altair
(``prism_mcp.utils.chart_functions``). The two engines must
not converge: do not surface ``make_echart`` or ``EChartResult`` from
this package as part of the PRISM-injected runtime namespace; they are
internal substrate for ``compile_dashboard``'s lowering pipeline only.
Multi-panel composition is a manifest concern (rows / cols / tabs in
the dashboard layout), not a separate one-off composite-canvas API --
those n-pack composite helpers belong to Altair's static-PNG surface.

Public surface PRISM imports:

    # Folder, inspection, transaction, and version operations.
    from dashboards import (
        run_pull,                  # run ONE pull from PULLS (in-process)
        review_dashboard,          # compile bounded panel receipt, no publish
        acknowledge_dashboard_review,  # bind rationale to exact signature
        publish_dashboard,         # review -> ack(if needed) -> build; rationale optional when publish-ready
        build_dashboard,           # template + CSVs + transforms -> compile
        build_dashboard_data_only, # datasets/time only; skip HTML
        refresh_dashboard,         # all PULLS + build_dashboard (full)
        light_refresh,             # all PULLS + build_dashboard_data_only
        launch_clean_refresh,      # isolated runner + S3 logs/status
        record_open_presence,      # open-tab heartbeat writer
        list_open_dashboards,      # TTL-fresh open folders
        inspect_dashboard,
        describe_dashboard,        # compact product floorplan for sync
        apply_manifest_operations,
        apply_persisted_script_operations,
        synchronize_refresh_frequency,
        list_dashboard_versions,   # timestamped definition summaries
        restore_dashboard_version, # older definition + current data
        read_dashboard_user_input, # read persisted notes/checklists/files
    )

    # Compile primitives and retained builder compatibility surface.
    from dashboards import (
        compile_dashboard,         # JSON manifest -> dashboard HTML + JSON
        render_dashboard,
        validate_manifest,         # dry-run structural validator
        prepare_manifest,
        manifest_template,         # strip data -> reusable template
        populate_template,         # template + fresh DataFrames -> manifest
        df_to_source,              # DataFrame -> canonical list-of-lists
        match_targets,
        load_manifest, save_manifest,
        Dashboard, Tab, ChartRef, KPIRef, TableRef,
    )

``chart_data_diagnostics``, the manifest/result/diagnostic types, and the
canonical ISO/refresh-frequency helpers are exported from the same package.
The builder classes and lower-level render/prepare helpers remain public for
installed-call-site compatibility; new PRISM authoring should prefer the
folder operations and high-level compile path above.

Sibling scripts (also part of the payload):

    refresh_runner.py    single-dashboard CLI invoked by the Django
                          [Refresh] button via subprocess.Popen.
                          --mode light|full (default full).
    refresh_dashboards.py
                          scheduled entry point. Full walk for cold HTML;
                          --open-interval N light-refreshes open tabs.

Internal-only modules (still drag-and-drop installed, not part of the
public surface):

    config.py            brand tokens + theme + palettes + dimensions
    echart_studio.py     single-chart builder (used internally by the
                          dashboard compiler when lowering each
                          ``widget: chart`` in the manifest)
    rendering.py         editor HTML + dashboard HTML + headless-Chrome
                          PNG export (driven by ``compile_dashboard``)
    dashboard_share.py   in-browser share fetch/ACL client
                          (``SHARE_CONTROLLER_JS``); CSS/HTML chrome
                          stays in ``rendering.py``
    dashboard_user_input.py
                          in-browser persisted-input API client
                          (``USER_INPUT_CONTROLLER_JS``)

Design: the manifest.json is the source of truth. ``compile_dashboard``
takes that JSON (dict, path, or JSON string), validates, lowers each
``widget: chart`` through the internal builders, and emits manifest +
interactive HTML. ``build_dashboard(folder)`` wraps that lifecycle for
the standard "load template + CSVs + transforms -> compile + write to
S3" recipe so PRISM doesn't reinvent it per dashboard.

DataFrame contract: PRISM emits Python that builds DataFrames from real
data functions (``pull_plottool_data``, ``pull_haver_data``, FRED, etc.)
and stores them as dataset values. Literal numbers never appear in the
JSON emitted by PRISM. Three accepted shapes for a dataset entry, all
normalised to the same on-disk form by the compiler:

    manifest["datasets"]["rates"] = df_rates                    # shorthand
    manifest["datasets"]["rates"] = {"source": df_rates}        # explicit
    manifest["datasets"]["rates"] = {"source": df_to_source(df_rates)}

Python runtime dependencies are stdlib + pandas + numpy. Persisted
dashboard scripts execute through one canonical namespace in both
in-process folder operations and clean refresh discovery. It exposes
``s3_manager``, the supported pull helpers, ``pull_nyfed_data``,
``save_artifact``, ``pd``, and ``np``.

The emitted HTML inlines ECharts (~1MB) read from the
local `web/backend_django/news/static/js/echarts.js` mirror. Code retains
a legacy `mysite/news/static/js/echarts.js` candidate, but that asset is
absent from the 2026-07-11 production checkout. The dashboard is portable:
core charts render identically when served by Django, opened from a file://
path, or streamed from S3 via a presigned URL. Optional Excel and
whole-dashboard PNG actions still require their jsDelivr XLSX/html2canvas
dependencies.
"""

from __future__ import annotations

from dashboards.echart_dashboard import (  # noqa: E402,F401
    # Folder operations.
    run_pull,
    build_dashboard,
    build_dashboard_data_only,
    publish_dashboard,
    refresh_dashboard,
    light_refresh,
    record_open_presence,
    list_open_dashboards,
    OPEN_PRESENCE_INDEX_KEY,
    OPEN_PRESENCE_TTL_SECONDS,
    review_dashboard,
    acknowledge_dashboard_review,
    launch_clean_refresh,
    # Compile primitives.
    compile_dashboard,
    render_dashboard,
    validate_manifest,
    prepare_manifest,
    manifest_template,
    populate_template,
    df_to_source,
    match_targets,
    load_manifest,
    save_manifest,
    chart_data_diagnostics,
    # Folder / registry / template transactions.
    audit_dashboard_layout,
    apply_manifest_operations,
    apply_persisted_script_operations,
    synchronize_refresh_frequency,
    sync_refresh_frequency,
    inspect_dashboard,
    describe_dashboard,
    list_dashboard_versions,
    restore_dashboard_version,
    read_dashboard_user_input,
    # Python builder sugar retained for installed-call-site compatibility.
    Dashboard,
    Tab,
    ChartRef,
    KPIRef,
    TableRef,
    MarkdownRef,
    NoteRef,
    DividerRef,
    GlobalFilter,
    Link,
    # Result / diagnostic / error types.
    Manifest,
    DashboardResult,
    DashboardReview,
    PanelReceipt,
    Diagnostic,
    RefreshAttachmentError,
    DashboardReviewRequired,
    DashboardVersionRestoreError,
    # Package metadata / private qualification contract.
    _AUDIT_REQUIRED_PATHS,
    ENGINE_VERSION,
)
from dashboards.dashboards_time import (  # noqa: E402,F401
    utcnow,
    parse_iso,
    format_iso,
    parse_freq,
    freq_delta,
    is_stale,
    UTC,
    ET,
    REFRESH_FREQ_DELTAS,
)

__version__ = ENGINE_VERSION

# Retained for the installed PRISM callers shown in the production snapshot.
# New callers should use the public ``audit_dashboard_layout`` name.
_audit_dashboard_layout = audit_dashboard_layout

__all__ = [
    "__version__",
    # Folder operations.
    "run_pull",
    "build_dashboard",
    "build_dashboard_data_only",
    "publish_dashboard",
    "refresh_dashboard",
    "light_refresh",
    "record_open_presence",
    "list_open_dashboards",
    "OPEN_PRESENCE_INDEX_KEY",
    "OPEN_PRESENCE_TTL_SECONDS",
    "review_dashboard",
    "acknowledge_dashboard_review",
    "launch_clean_refresh",
    # Compile primitives.
    "compile_dashboard",
    "render_dashboard",
    "validate_manifest",
    "prepare_manifest",
    "manifest_template",
    "populate_template",
    "df_to_source",
    "match_targets",
    "load_manifest",
    "save_manifest",
    "chart_data_diagnostics",
    # Folder / registry / template transactions.
    "audit_dashboard_layout",
    "apply_manifest_operations",
    "apply_persisted_script_operations",
    "synchronize_refresh_frequency",
    "sync_refresh_frequency",
    "inspect_dashboard",
    "describe_dashboard",
    "list_dashboard_versions",
    "restore_dashboard_version",
    "read_dashboard_user_input",
    # Python builder sugar.
    "Dashboard",
    "Tab",
    "ChartRef",
    "KPIRef",
    "TableRef",
    "MarkdownRef",
    "NoteRef",
    "DividerRef",
    "GlobalFilter",
    "Link",
    # Result / diagnostic / error types.
    "Manifest",
    "DashboardResult",
    "DashboardReview",
    "PanelReceipt",
    "Diagnostic",
    "RefreshAttachmentError",
    "DashboardReviewRequired",
    "DashboardVersionRestoreError",
    # Time helpers.
    "utcnow",
    "parse_iso",
    "format_iso",
    "parse_freq",
    "freq_delta",
    "is_stale",
    "UTC",
    "ET",
    "REFRESH_FREQ_DELTAS",
]
