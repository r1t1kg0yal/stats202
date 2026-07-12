---
class: context-extraction
topic: dashboard-architecture-validation
status: PARTIALLY_ANSWERED
created: 2026-07-11
reply: live PRISM read-only response received 2026-07-11
unresolved:
  - section 10.2 XLSX/html2canvas production CDN behavior
  - prism-main recorded submodule commit versus checked-out prism-core commit
reply_folded_into:
  - .cursor/rules/viz-platforms.mdc
  - .cursor/rules/prism.mdc
  - projects/echarts/README.md
  - projects/echarts/dev/packages.md
  - projects/echarts/dev/notes.md
  - projects/echarts/echarts-payload/__init__.py
  - projects/echarts/echarts-payload/echart_studio.py
  - projects/echarts/echarts-payload/refresh_runner.py
  - projects/echarts/echarts-payload/dashboards_hub.md
  - projects/echarts/echarts-payload/dashboards/build.md
  - projects/echarts/dev/goldens/context_post_rewrite.json
  - staging/README.md
  - prism/README.md
  - prism/codebase-tree.md
  - prism/code-sandbox.md
  - prism/architecture.md
  - prism/dashboard-refresh.md
  - prism/dashboards-portal.md
  - prism/mcp-tools.md
  - prism/_prompting-guide.md
  - prism/_changelog.md
---

# Context-extraction prompt — dashboard subsystem architecture validation

**Why this exists (staging-side note; do not paste this section into
PRISM):**

Before continuing ECharts/dashboard development, we need one current,
source-backed map of every PRISM boundary the payload depends on. Local
documentation is not internally consistent after the `prism-main` /
`prism-core` split:

- the canonical payload and tests enforce 8 Python files, a router, a kernel,
  and 9 context spokes;
- `.cursor/rules/viz-platforms.mdc` still describes 7 spokes in one section;
- `staging/README.md` still describes 6 staging-only test-prompt files rather
  than the 8 currently enforced;
- `.cursor/rules/prism.mdc` and several `prism/` references retain retired
  `ai_development/...` paths;
- `projects/echarts/dev/packages.md` says ECharts is CDN-loaded, while the
  current payload inlines a repository asset into dashboard HTML;
- payload prose says both “no namespace injection” and that persisted scripts
  receive injected helpers on execution.

This prompt is deliberately broader than the July old-versus-production
reconciliation. It validates the full live boundary: source layout, imports,
callers, sandbox injection, L2 context loading, Django routes, S3/registry
contracts, refresh subprocesses, cron wiring, assets, and runtime
dependencies. The reply should be folded into the files listed in
`reply_folded_into` only after the evidence has been reviewed.

---

## Paste the following into PRISM

# Dashboard subsystem architecture validation (read-only)

You are being asked to introspect the current dashboard subsystem after the
`prism-main` / `prism-core` split. This is a pure read-only
context-extraction request.

Use `list_ai_repo`, `execute_analysis_script`, repository search, and direct
source reads as needed. Do not answer from memory.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- run `refresh_runner.py`, `refresh_dashboards.py`, `compile_dashboard`,
  `build_dashboard`, `refresh_dashboard`, `run_pull`, or any other dashboard
  build/refresh entry point;
- issue POST/PUT/PATCH/DELETE requests to dashboard endpoints;
- write, copy, move, or delete S3 objects;
- update `dashboards_registry.json`, `refresh_status.json`, a user manifest,
  a completion marker, or a log object;
- create a dashboard, session artifact, ticket, or background process;
- install, upgrade, or import-test a missing package by changing the
  environment.

Read existing source and metadata only. A short introspection script that
prints paths, versions, signatures, hashes, `sys.path`, or the shape of an
already-loaded object is permitted only if it performs no writes and invokes
none of the entry points prohibited above.

## Reply protocol

1. Mirror every numbered section and subsection below.
2. Cite the exact current path and line range for every source-backed claim.
3. Where source is requested, paste the complete bounded block verbatim in a
   fenced code block. Do not use `...`, reconstructed snippets, or prose
   placeholders inside a requested block.
4. Where a repository search is requested, state the searched roots and
   patterns, then return every match as `path:line:source`. If a search is
   incomplete, mark it `INCOMPLETE` and explain why.
5. Do not paste entire large files. Return only the requested import blocks,
   functions, registry entries, schemas, and call sites.
6. Redact secrets, tokens, cookies, and user data values. Preserve key names,
   types, paths, import names, and control flow.
7. Use only these verdicts where a verdict is requested:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
8. If evidence conflicts, show both sources and classify the conflict. Do not
   silently choose one.

## 0. Freshness and checkout identity

### 0.1 Checkout identity

Return:

- current `prism-main` HEAD SHA;
- current `prism-core` submodule SHA;
- the submodule SHA recorded by `prism-main`;
- whether the checked-out `prism-core` SHA matches the recorded SHA;
- repository-relative and absolute paths for both roots;
- current UTC timestamp of the inspection.

State exactly how each value was obtained. If Git metadata is not readable,
return `UNKNOWN`; do not infer a SHA from a filename, deployment label, or
prior conversation.

### 0.2 Root anchors

Paste verbatim:

- the complete current `prism_meta/__init__.py` if it is 100 lines or fewer,
  otherwise the complete `REPO_ROOT` definition and its imports;
- the source that places `prism-main`, `prism-core`, and the dashboard module
  directory on `sys.path` or `PYTHONPATH`;
- any launcher, settings, package, or entrypoint configuration that performs
  that setup.

Then run a read-only introspection and paste the output:

```python
import os
import sys
import core
import dashboards
import prism_mcp
import prism_meta

print("cwd", os.getcwd())
print("python", sys.executable)
print("sys_version", sys.version)
print("sys_path", list(enumerate(sys.path)))
print("core", getattr(core, "__file__", None))
print("dashboards", getattr(dashboards, "__file__", None))
print("prism_mcp", getattr(prism_mcp, "__file__", None))
print("prism_meta", getattr(prism_meta, "__file__", None))
print("repo_root", prism_meta.REPO_ROOT)
print("repo_root_type", type(prism_meta.REPO_ROOT).__name__)
```

Do not normalize or shorten the printed paths.

## 1. Installed payload inventory and parity

### 1.1 Expected staging source

The canonical staging source currently has this exact inventory:

| Staging-relative path | Bytes | Lines | SHA-256 |
|---|---:|---:|---|
| `__init__.py` | 4,963 | 110 | `b7848948e69f1b1e5ab88cc07ddd8e26493d88ffad5957f5cb4c08bc9e5a2ef3` |
| `config.py` | 25,707 | 664 | `5a1e7560fd1a7786cfc448b365106e86b685036e761b760d02ba454b84b2c053` |
| `dashboards_time.py` | 8,201 | 211 | `ae7c3f003dfd0079be5d3f843716958313e90abc26aeebb3ae4e8565a3e4b6b7` |
| `echart_dashboard.py` | 582,564 | 13,754 | `9ee286098f5f4287789a10ea2545954f7f4c3e169e7222e5923156d1236c90bb` |
| `echart_studio.py` | 286,038 | 6,877 | `79a41591f83abe679556af876576d683b6eb8eb9f94789cb917122c2639e25fa` |
| `rendering.py` | 645,794 | 16,263 | `3231e0a7421da44f75152fd93cdec058a1315a52350f68175f1439ffdc960e94` |
| `refresh_runner.py` | 22,938 | 552 | `a2b958f8962b66af91e02ded2183ff32350ac8b016d6f31e440bccb77bfb23b0` |
| `refresh_dashboards.py` | 29,032 | 720 | `b43085294146f3b63c7461b032361ec2bf5c58e81f950ceb909cf64f06d22147` |
| `dashboards.md` | 10,580 | 134 | `7cb78399944cb58c2bbc18514b1814d35cee725f27cf104ffe974f093f8a9449` |
| `dashboards_hub.md` | 11,676 | 230 | `9c591ec685b2a6486e54db1f9e8a64b69581a3c430182e1bc09215392ff6075f` |
| `dashboards/build.md` | 13,073 | 347 | `6dee8499786f0f79f42f94446a726c091d07802578ded03c1999a651cab4d255` |
| `dashboards/charts.md` | 14,929 | 351 | `96f4ceaaf1aa63fa48fb764c89f126b290d24ffbb9a619e7c5e8a97c249c457d` |
| `dashboards/diagnose.md` | 12,917 | 197 | `0b9dd5731f9b7e9317345c1b0a7ab98afd082ede4a161b24cee306968909baf9` |
| `dashboards/filters.md` | 11,107 | 338 | `3c883550d3595d18c3b219afaf4e618fd9ae49a86c8d322aa3c8cb63a075d4f8` |
| `dashboards/pipelines.md` | 11,482 | 269 | `d5df7469abe0136b1089ec13442033de46b43f11d136325b8a4e35f648017e19` |
| `dashboards/recipes.md` | 15,259 | 411 | `a276b96744beaf0e3aa321507670d77ee6ab0b611e0885f4c08611230d29257f` |
| `dashboards/template_crud.md` | 13,664 | 354 | `114904d4c520944a27b9d8d8d52d9a7d36591e7efd7c3e13847a027fe22ac634` |
| `dashboards/widget_tool.md` | 14,222 | 346 | `7c0ebd895266cd0cc1ef6e47925e9c7ee8747ce30389da55a9d1d3517dac8ad2` |
| `dashboards/widgets.md` | 9,775 | 301 | `50f2f9d5835b100685fc9d5efe231fabeca56a0ce7f2b26cfe5290b6eb4e79b0` |

The eight staging-only prompt files are:

```text
charts_test.md
diagnose_test.md
filters_test.md
pipelines_test.md
recipes_test.md
template_crud_test.md
widget_tool_test.md
widgets_test.md
```

They must not be present in the production context tree.

### 1.2 Production inventory

Programmatically enumerate:

- `prism-core/dashboards/`;
- `jobs/hourly/` entries related to dashboards;
- `prism-core/context/modules/static/tools/` entries whose names begin with
  `dashboards`;
- `prism-core/context/modules/static/tools/dashboards/`.

Exclude caches and generated bytecode. Return one row per relevant file:

| Production path | Kind | Bytes | Lines | SHA-256 | Expected staging path | Parity |
|---|---|---:|---:|---|---|---|

`Kind` must be one of `executed Python`, `LLM context`, `reference data`, or
`unexpected`. `Parity` must be one of `BYTE_IDENTICAL`, `DIFFERS`,
`PRODUCTION_ONLY`, `STAGING_ONLY`.

Explicitly answer:

1. Are all 8 Python payload files installed at the expected destinations?
2. Is `refresh_dashboards.py` installed only under `jobs/hourly/`, or is
   another executable copy present?
3. Are the router, kernel, and all 9 spokes installed?
4. Are any of the 8 staging-only test-prompt files installed?
5. Are there production-only dashboard Python, Markdown, JSON, YAML, or
   configuration files not represented above?
6. Do the current installed bytes match this staging baseline?

Do not return a full diff. For every `DIFFERS` row, report only:

- whether the delta touches executable Python, emitted HTML/JS/CSS, LLM
  semantics, or inert comments/docstrings/whitespace;
- the names of changed functions/classes/headings;
- whether the difference can change runtime or PRISM authoring behavior.

## 2. Dashboard package import mechanics

### 2.1 Per-file import map

For each of the eight Python payload files, return:

| File | Top-level imports | Lazy imports | Repo-local imports | External packages | `sys.path` mutation |
|---|---|---|---|---|---|

For `Top-level imports`, paste the complete import block from after
`from __future__` through the first function/class/constant that ends the
import region. For lazy imports, list every import nested in a function with
its path and line. Distinguish:

- standard library;
- `core.*`;
- `dashboards.*`;
- bare sibling imports such as `from rendering import ...`,
  `from config import ...`, and `from dashboards_time import ...`;
- `prism_mcp.*`;
- `prism_meta`;
- third-party Python packages.

### 2.2 Bare sibling resolution

Paste every payload block that mutates `sys.path`. Then answer with evidence:

1. Is `prism-core/dashboards/` itself on `sys.path` in the main process?
2. Is it on `sys.path` in the clean refresh subprocess?
3. Is it on `sys.path` in the hourly job process?
4. Which source is responsible in each process?
5. Why do bare sibling imports resolve when
   `dashboards.echart_dashboard` is imported as a package module?
6. Would removing the payload-local `sys.path.insert` blocks break any
   current production execution path?

### 2.3 Public package surface

Paste the complete current `prism-core/dashboards/__init__.py`. Return a
second table:

| Exported name | Defined in | Imported by production caller(s) | Wrapped/injected | Stability role |
|---|---|---|---|---|

`Stability role` must be one of `public contract`, `internal but imported`,
`internal only`, or `unknown`.

Search specifically for all production consumers of:

```text
run_pull
build_dashboard
refresh_dashboard
compile_dashboard
validate_manifest
manifest_template
populate_template
df_to_source
load_manifest
save_manifest
chart_data_diagnostics
audit_dashboard_layout
apply_manifest_operations
inspect_dashboard
synchronize_refresh_frequency
sync_refresh_frequency
_AUDIT_REQUIRED_PATHS
Manifest
DashboardResult
make_echart
EChartResult
```

Confirm whether `make_echart` and `EChartResult` remain internal and absent
from every sandbox/injected public namespace.

## 3. Outbound dependency contracts

For every dependency below, provide:

1. exact production import path;
2. exact import statement(s) in dashboard code;
3. `inspect.signature` output for every called method/function;
4. every dashboard call site as `path:line:source`;
5. source-defined return type/shape;
6. whether the local staging contract stated below is correct.

### 3.1 S3 manager

Inspect the actual type of `core.s3_bucket_manager.s3_manager`:

```text
get(path: str)
put(data, path: str)
exists(path: str)
list(prefix: str = "")
move(...)
delete(...)
```

Include only `move` or `delete` if dashboard code calls them. State whether
`list()` returns `list[str]`, dictionaries containing `Key`, another shape,
or multiple shapes.

### 3.2 User registry and user manifest

Inspect:

```text
core.common.UserRegistry.__init__
core.common.UserRegistry.get_all_kerberos_ids
core.user_manifest.UserManifestManager.__init__
core.user_manifest.UserManifestManager.update_dashboard_pointer
```

Paste the complete dashboard-related call sites and state whether pointer
updates happen after on-demand refresh, hourly refresh, both, or neither.

### 3.3 Data helpers and external clients

Inspect every dashboard import/call of:

```text
prism_mcp.utils.data_functions.pull_market_data
prism_mcp.utils.data_functions.pull_haver_data
prism_mcp.utils.data_functions.pull_plottool_data
prism_mcp.utils.data_functions.pull_fred_data
prism_mcp.utils.data_functions.save_artifact
core.mcp.clients.newyorkfed_client.pull_nyfed_data
```

Return exact signatures and exact return contracts. Confirm the live module
path and call shape for `pull_nyfed_data`.

### 3.4 Completion and log streaming

Inspect:

```text
prism_mcp.utils.subprocess_completion.register_completion_marker
prism_mcp.utils.s3_log_streamer.S3LogPathBuilder.build
prism_mcp.utils.s3_log_streamer.S3LogPathBuilder.build_session_side
prism_mcp.utils.s3_log_streamer.S3LogStreamer.__init__
```

Paste complete dashboard call sites, signatures, return shapes, and the
environment variables each contract reads.

### 3.5 Dependency closure

Search all eight Python payload files for repo-local imports and output an
exhaustive dependency edge list:

```text
dashboard_file -> imported_module.symbol
```

End with:

```text
OUTBOUND_DEPENDENCY_LEDGER_COMPLETE: YES/NO
```

If `NO`, identify the missing import or unresolved symbol.

## 4. Inbound consumer graph

Search the entire `prism-main` root and `prism-core` submodule for:

```text
from dashboards
import dashboards
dashboards.
refresh_runner
refresh_dashboards
compile_dashboard
build_dashboard
refresh_dashboard
apply_manifest_operations
inspect_dashboard
```

Exclude the dashboard payload's own definitions, caches, generated artifacts,
and static documentation from the first result set. Return every executable
consumer:

| Caller path and lines | Imported/called symbol | Call shape | Process/interface | User-visible behavior affected |
|---|---|---|---|---|

Classify `Process/interface` as one of:

```text
execute_analysis_script sandbox
Django request
hourly job
report/email worker
background subprocess
test/diagnostic
other
```

Then return a second result set for non-executable references in active
configuration, registries, context modules, launch scripts, service files,
and deployment manifests.

Explicitly answer:

1. Is `script_exec_tools.py` the only sandbox consumer?
2. Which Django view(s) import or launch dashboard code?
3. Which job/entrypoint imports `refresh_dashboards`?
4. Do report, email, observatory, or portal services import the compiler?
5. Are there any dynamic imports, string module paths, `importlib` calls,
   subprocess argv entries, or service commands that ordinary import search
   misses?
6. Does any consumer still import an `ai_development.dashboards` path?

End with:

```text
INBOUND_CONSUMER_GRAPH_COMPLETE: YES/NO
```

## 5. Sandbox and persisted-script execution

### 5.1 `execute_analysis_script` dashboard namespace

From the current sandbox implementation, paste verbatim:

- dashboard imports;
- the entire dashboard-related namespace/injection block;
- wrappers, validators, partials, decorators, or aliases applied to dashboard
  functions;
- the code that establishes `sys.path` for the script process.

Return:

| Name | Imported from | Present in sandbox namespace | Wrapped as | Publicly documented |
|---|---|---|---|---|

### 5.2 In-process persisted-script namespace

From `echart_dashboard.py`, paste the complete function that builds and
executes the namespace for persisted `scripts/pull_data.py` and
`scripts/build.py`, including all imports immediately required by that
function.

### 5.3 Refresh-subprocess namespace

From `refresh_runner.py`, paste the complete namespace builder and the
complete bounded block that executes persisted scripts.

### 5.4 Namespace parity

Return one comparison table:

| Name | Sandbox | In-process folder operation | Refresh subprocess | Required explicit import in persisted script |
|---|---|---|---|---|

Include at least:

```text
s3_manager
pull_market_data
pull_haver_data
pull_plottool_data
pull_fred_data
pull_nyfed_data
save_artifact
pd
np
__builtins__
```

Resolve these questions:

1. Are persisted scripts required to import every helper they call?
2. If yes, why do execution paths inject helpers?
3. If no, why does the current router instruct authors to import every
   helper?
4. Are the in-process and refresh-subprocess namespaces behaviorally
   identical?
5. Can a script succeed during initial build but fail during refresh because
   a name exists in only one namespace?
6. Does either execution path intentionally retain
   `pull_market_data` after authoring guidance shifted toward
   `pull_plottool_data`?

Classify any mismatch as `intentional`, `defect`, or `unknown`, with source
evidence.

## 6. L2 context registration and loading

### 6.1 Registry ownership

Paste verbatim the active registry/config entries that register:

```text
dashboards.md
dashboards_hub.md
dashboards/build.md
dashboards/diagnose.md
dashboards/template_crud.md
dashboards/pipelines.md
dashboards/recipes.md
dashboards/charts.md
dashboards/widgets.md
dashboards/widget_tool.md
dashboards/filters.md
```

For each, return:

| Context ID or registry key | Production path | Always/on-demand | Bundle(s) | Trigger | Loader |
|---|---|---|---|---|---|

### 6.2 Loader and `list_ai_repo`

Paste the complete bounded source blocks that:

- map a context module identifier to a filesystem path;
- define the repository root used by `list_ai_repo`;
- resolve `file_paths=["dashboards_hub.md", "dashboards/widgets.md"]`;
- enforce any one-shot `get_context()` behavior;
- impose file-size warnings or limits.

Run read-only fetches for exactly:

```python
list_ai_repo(
    file_paths=["dashboards_hub.md", "dashboards/widgets.md"],
    mode="full",
)
```

and:

```python
list_ai_repo(
    file_paths=["dashboards/diagnose.md"],
    mode="full",
)
```

Do not paste the returned file bodies. Report only whether each path resolves,
the resolved production path, and byte count.

### 6.3 Router topology

Confirm the live context topology:

```text
dashboards.md       -> router
dashboards_hub.md   -> cross-cutting kernel
9 dashboards/*.md  -> ownership spokes
```

State whether any active production source still describes
`dashboards.md` as the full hub, lists only 6 or 7 spokes, or omits
`build.md`, `diagnose.md`, or `template_crud.md`.

## 7. Django and portal integration

### 7.1 Route inventory

Enumerate every current dashboard-related Django route. Include, at minimum,
routes for:

- dashboard HTML/detail serving;
- refresh start;
- refresh status polling;
- live dataset/data polling;
- sharing/community visibility;
- dashboard registry/listing;
- download or attachment behavior, if present.

Return:

| URL pattern | Name | View path/function | Methods | Reads | Writes | Dashboard symbol used |
|---|---|---|---|---|---|---|

Do not invoke the routes.

### 7.2 Refresh launch call site

Paste the complete Django view block that launches a dashboard refresh,
including:

- imports;
- authorization and folder validation;
- subprocess argv;
- working directory;
- environment construction;
- log-path construction;
- completion-marker keys;
- immediate response payload;
- error handling.

State whether it launches:

```text
python -m dashboards.refresh_runner
python <path>/refresh_runner.py
another command
```

and give the exact resolved command.

### 7.3 Polling contracts

Paste the complete bounded view blocks that read `refresh_status.json` and
live dataset files. Return the exact JSON response schemas and status-code
behavior. Show where the emitted dashboard JavaScript constructs these URLs.

### 7.4 Portal coupling

Identify every portal/template/static-JS assumption that depends on:

- dashboard folder shape;
- `dashboard_id`;
- author kerberos;
- registry fields;
- sharing fields;
- status schema;
- live data endpoint;
- cache headers or ETag behavior.

Return source paths and lines. Do not summarize portal behavior without a
corresponding source citation.

## 8. Refresh runner and scheduled job

### 8.1 Single-dashboard runner

Paste verbatim:

- `refresh_runner.py` CLI parser construction;
- `main()` and the call into the refresh phases;
- completion-marker registration;
- the phase sequence;
- final status write;
- the exact diagnostic print block at module import, if present.

Answer:

1. Is the current installed runner byte-identical to the staging hash in
   section 1?
2. Does production intentionally print `sys.executable`, `sys.prefix`,
   the complete `sys.path`, `PYTHONPATH`, `PYTHONHOME`, and duplicate
   `pandas.io.formats` checks at import time?
3. Is that block required for runtime behavior, temporary instrumentation,
   or unknown?

### 8.2 Hourly scheduler

Paste verbatim:

- the code/config/service entry that invokes
  `jobs/hourly/refresh_dashboards.py`;
- its command, cadence, working directory, environment, and interpreter;
- the per-dashboard `subprocess.Popen` call;
- due/disabled/cooldown selection;
- post-spawn user-manifest update;
- top-level exception isolation.

State whether production uses one-shot cron execution, daemon
`--interval`, another scheduler, or multiple modes.

### 8.3 Process-boundary parity

Return:

| Property | Django-spawned runner | Hourly-spawned runner | Direct CLI |
|---|---|---|---|
| Interpreter | | | |
| cwd | | | |
| `PYTHONPATH` | | | |
| dashboard folder on `sys.path` | | | |
| log path | | | |
| completion keys | | | |
| user identity source | | | |
| manifest pointer update | | | |

Flag any difference that can make the same dashboard refresh differently
across launch surfaces.

## 9. Persistence, registry, and status schemas

### 9.1 Canonical folder tree

From source, return the complete canonical dashboard folder tree and identify
which component owns each path:

```text
users/{kerberos}/dashboards/{dashboard_id}/
```

Include scripts, data, manifest template, materialized manifest, dashboard
HTML, refresh status, history/archive/transactions, and any metadata files
currently recognized by source.

### 9.2 Dashboard registry

Paste:

- the source that defines or writes a registry entry;
- the source that reads it in Django and the hourly job;
- one existing entry with values redacted but keys, types, nesting, and null
  behavior preserved.

Return a field table:

| Field | Type | Required | Writer(s) | Reader(s) | Default/back-compat behavior |
|---|---|---|---|---|---|

### 9.3 Refresh status

Do the same for `refresh_status.json`, including every top-level field and
every `errors[]` field. Identify which fields the dashboard JavaScript and
Django views assume.

### 9.4 User manifest

Paste the exact dashboard-pointer schema and the writer/reader call sites.
State whether dashboard compilation or refresh can leave the pointer stale,
and which path repairs it.

### 9.5 S3 semantics

For each dashboard path operation, identify:

- exact key construction;
- bytes/string encoding assumptions;
- existence/list semantics;
- atomicity or overwrite behavior;
- cache/ETag behavior;
- history/archive retention behavior.

Do not enumerate unrelated user objects.

## 10. Static assets and emitted runtime dependencies

### 10.1 ECharts asset

Paste the complete current `_get_echarts_js()` function and every call site.
Return:

- path candidates in exact order;
- current resolved absolute path;
- existence for each candidate;
- bytes, SHA-256, and identifiable ECharts version of the resolved file;
- behavior when no candidate exists;
- whether the legacy `mysite/news/static/js/echarts.js` path still exists;
- whether both paths are intentionally supported.

### 10.2 Other browser dependencies

Search emitted HTML/JavaScript for every external URL and library reference.
Return:

| Library/asset | Version | Inline/local/CDN | Used by | Required for core display or optional action | Offline behavior |
|---|---|---|---|---|---|

Include ECharts, XLSX, html2canvas, fonts, logos, and any other external
runtime asset found. Distinguish dashboard HTML from the headless PNG harness.

### 10.3 Python/runtime dependencies

Return actual runtime versions and provenance for:

```text
Python
pandas
numpy
zoneinfo/tzdata
Chrome/Chromium used by PNG export
```

Search the payload for every third-party import. For each dependency, state:

- import sites;
- feature requiring it;
- whether required in the main process, refresh subprocess, dev-only tools,
  or emitted browser runtime;
- where the production version is pinned or installed.

Explicitly resolve whether the production payload is accurately described as
“stdlib + pandas” or whether `numpy` is also a runtime dependency.

## 11. Configuration, environment, and deployment wiring

### 11.1 Environment variables

Return every environment variable read by the dashboard subsystem and its
direct dependencies:

| Variable | Reader path/line | Required/optional | Default | Process(es) | Secret |
|---|---|---|---|---|---|

Include subprocess folder/session keys, logo/static paths, Python path
variables, and any dashboard-specific settings.

### 11.2 Django settings and static roots

Paste the bounded settings/path configuration that makes the primary
ECharts asset and dashboard routes available. Identify the authoritative
production static root and any legacy root.

### 11.3 Job/deployment registration

Return every service, scheduler, manifest, entrypoint, or configuration file
that activates dashboard refresh or exposes dashboard routes. Include module
paths and commands verbatim.

### 11.4 Package boundaries

State, with source/config evidence:

1. Which files belong to `prism-main`.
2. Which files belong to the `prism-core` submodule.
3. Which package owns `core`, `dashboards`, `prism_mcp`, `prism_meta`, and
   `jobs`.
4. Which roots are editable installs versus raw paths on `sys.path`.
5. Whether any import depends on the checkout folder being named
   `prism-main` or `prism-core`.

## 12. Active documentation and reference graph

Search active source, context, developer documentation, and agent-facing
rules for references to:

```text
ai_development/dashboards
ai_development/jobs
ai_development/mysite
mysite/news/static/js/echarts.js
prism-core/dashboards
jobs/hourly/refresh_dashboards.py
dashboards_hub.md
dashboards/build.md
dashboards/diagnose.md
dashboards/template_crud.md
```

Return:

| Referencing path/lines | Referenced path or claim | Executed/read at runtime | Current/stale/unknown | Correct current target |
|---|---|---|---|---|

Distinguish:

- executable source or deployment configuration;
- LLM-consumed context;
- agent/developer documentation;
- archived/history-only material.

Do not classify an archived reference as an active compatibility problem.

## 13. Contradiction ledger

Resolve each local assumption using the evidence gathered above:

| ID | Local assumption | Verdict | Production fact | Evidence |
|---|---|---|---|---|
| C01 | Runtime is split between `prism-main` and a `prism-core` submodule. | | | |
| C02 | `prism-main` and `prism-core` are both import roots. | | | |
| C03 | `prism-core/dashboards/` itself is on `sys.path` for bare sibling imports. | | | |
| C04 | There is no active `ai_development.*` dashboard import alias. | | | |
| C05 | Seven Python modules live in `prism-core/dashboards/`; `refresh_dashboards.py` lives in parent `jobs/hourly/`. | | | |
| C06 | Production context is one router, one kernel, and nine spokes. | | | |
| C07 | Eight staging-only test-prompt files are absent from production. | | | |
| C08 | `dashboards.md` is the always-loaded router, not the full authoring hub. | | | |
| C09 | `dashboards_hub.md` and spokes resolve through `list_ai_repo` using the short paths shown in the router. | | | |
| C10 | The main dashboard HTML inlines a local `echarts.js`; it does not load ECharts from a CDN. | | | |
| C11 | XLSX and html2canvas may still use CDN URLs for optional browser actions. | | | |
| C12 | `numpy` is a production runtime dependency for compute/diagnostic paths. | | | |
| C13 | Persisted scripts receive injected helpers even though current prose says authors must import every helper. | | | |
| C14 | In-process and refresh-subprocess persisted-script namespaces are identical. | | | |
| C15 | `pull_nyfed_data` comes from `core.mcp.clients.newyorkfed_client`. | | | |
| C16 | `s3_manager.list()` returns `list[str]`. | | | |
| C17 | Django and cron launch the same `dashboards.refresh_runner` implementation. | | | |
| C18 | The refresh runner's import-time environment dump is present in live production. | | | |
| C19 | The primary static asset path is `web/backend_django/news/static/js/echarts.js`. | | | |
| C20 | `mysite/news/static/js/echarts.js` is only a legacy fallback. | | | |
| C21 | No production consumer imports `make_echart` or `EChartResult` as a public API. | | | |
| C22 | All executable consumers are covered by the inbound consumer graph. | | | |

For every `CONTRADICTS` or `UNKNOWN` row, state the exact local file/claim
that must remain untrusted until reconciled.

## 14. Compatibility boundary for future dashboard work

Based only on the verified source and consumer graph, return three lists.
Each item must cite its defining source and every known consumer.

### 14.1 Hard external contracts

List signatures, import paths, file destinations, JSON schemas, S3 keys,
route shapes, environment variables, and static paths whose change would
require coordinated PRISM changes.

### 14.2 Internal contracts enforced by the payload

List boundaries that may be changed within the payload only if all payload
callers, context files, and tests change together.

### 14.3 Implementation details with no external consumer

List only items proven by exhaustive search to have no external caller or
configuration dependency. Do not infer safety from a leading underscore
alone.

Then provide this matrix:

| Change surface | Can staging change alone? | Coordinated owner(s) | Verification required | Evidence |
|---|---|---|---|---|
| Python public export | | | | |
| Bare sibling import | | | | |
| `core.*` dependency call | | | | |
| Sandbox namespace | | | | |
| Persisted-script namespace | | | | |
| Context router/spoke path | | | | |
| Django route or response schema | | | | |
| Registry/status field | | | | |
| Refresh subprocess argv/env | | | | |
| Cron entrypoint | | | | |
| ECharts asset path | | | | |
| Emitted HTML/JS behavior | | | | |

This section is a source-backed compatibility classification, not a request
to modify code or propose a redesign.

## 15. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
FRESHNESS_IDENTITY_COMPLETE:
INSTALLED_INVENTORY_COMPLETE:
IMPORT_MAP_COMPLETE:
OUTBOUND_DEPENDENCY_LEDGER_COMPLETE:
INBOUND_CONSUMER_GRAPH_COMPLETE:
NAMESPACE_PARITY_RESOLVED:
CONTEXT_LOADING_RESOLVED:
DJANGO_PORTAL_WIRING_COMPLETE:
REFRESH_CRON_WIRING_COMPLETE:
PERSISTENCE_SCHEMAS_COMPLETE:
ASSET_DEPENDENCIES_COMPLETE:
DEPLOYMENT_WIRING_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
COMPATIBILITY_BOUNDARY_COMPLETE:
ARCHITECTURE_VALIDATION_COMPLETE:
```

`ARCHITECTURE_VALIDATION_COMPLETE` may be `YES` only if every preceding item
is `YES`. If it is `NO`, list only the unresolved section/subsection numbers
and the missing source or permission.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and what
blocked it.
