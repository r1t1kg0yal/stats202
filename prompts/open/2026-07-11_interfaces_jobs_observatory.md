---
class: context-extraction
topic: interfaces-jobs-observatory
status: PARTIALLY_FOLDED
created: 2026-07-11
reply_received: 2026-07-11
reply_source: cursor-chat screenshots (16 images, captured 2026-07-11 22:55-22:57 ET)
folded_on: 2026-07-11
unresolved:
  - external procmon/scheduler activation configuration for long-running CLIs and cadence groups
  - exact live vision model identifier, public signatures, request configuration, and installed QUALITY_CHECK_PROMPT body
  - per-developer-loop mutation policies and production guards
sequence: 6/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
  - staging/prompts/open/2026-07-11_data_ecosystem_world_state.md
reply_folded_into:
  - prism/architecture.md
  - prism/codebase-tree.md
  - prism/security.md
  - prism/vision-qc.md
  - prism/competitive-spec.md
  - prism/mcp-tools.md
  - prism/README.md
---

# Context-extraction prompt — interfaces, jobs, Observatory, and remaining architecture

**Why this exists (staging-only note; do not paste this section into
PRISM):**

Most local architecture sections outside the dashboard subsystem were last
introspected in April or May 2026 and still use the retired
`ai_development/` layout. The current implementation of Teams/GS.AI/chat,
MCP, email, reports, Django portals, the Observatory, report and observation
workers, non-dashboard jobs, security/status context, vision/PDF/QC,
developer loops, evals, and design principles has not been reconciled with
the split `prism-main` / `prism-core` checkout.

This is sequence 6 of 7. It depends on the dashboard architecture validation
and the data-ecosystem/world-state refresh. Those prompts own dashboard
mechanics and data/client/transport/world-state mechanics respectively. This
prompt should identify cross-system edges to those surfaces but must not
re-extract their detailed contracts.

The competitive-positioning request is intentionally narrow: locate PRISM's
current internal source and ownership. Internal claims are not external
evidence about competitors, and PRISM must not research, browse, or update
competitor facts. Any fold into `prism/competitive-spec.md` is limited to
source/ownership/freshness framing.

The reply should be folded only into the files listed in
`reply_folded_into`, after its evidence and contradiction ledger have been
reviewed.

---

## Paste the following into PRISM

# Remaining architecture refresh: interfaces, jobs, Observatory, security, and vision (read-only)

You are being asked to inspect all current PRISM architecture surfaces not
owned by the dashboard-specific and data-ecosystem prompts. This is a pure
read-only context-extraction request. Use the live checkout and source first;
do not answer from memory or prior conversation.

Two dependent inspections define hard scope boundaries:

```text
dashboard architecture validation
    owns dashboard compiler/package, dashboard context topology,
    dashboard portal/detail/refresh routes, runner, registry/status,
    assets, and persisted-script namespaces

data ecosystem and world-state refresh
    owns external clients, GS proxy/Kerberos transport, data helpers,
    source-routing ontology, S3-vs-client-vs-pull decisions,
    world-state modules, and their ingestion producers
```

Do not repeat those inventories. Report only the interface, worker, job,
security, vision, development, evaluation, and ownership edges needed to
complete the system graph.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- invoke chat/Teams/email/report/observation/Observatory worker entry points;
- send or receive email, create a report/observation/ticket, publish an
  artifact, or enqueue work;
- run `entrypoint.py`, any scheduler, job, dev loop, eval, report workflow,
  ingestion process, snapshot process, or web server;
- issue POST/PUT/PATCH/DELETE requests to Django/MCP/LLM/vision services;
- call external APIs, upload images/documents, open PDFs through production
  services, or trigger Gemini/Claude/GS.AI inference;
- write, copy, move, or delete S3 objects, indexes, snapshots, sessions,
  thread state, manifests, locks, logs, cached context, or deployment state;
- start subprocesses/background processes or install/upgrade packages;
- enumerate user-private content or reveal prompts, credentials, tokens,
  cookies, API keys, Kerberos ticket material, email bodies, report bodies,
  observation contents, or user data values.

Read source, static configuration, route maps, service/deployment files,
registry metadata, and redacted existing schema shapes only. A short
introspection script may print paths, line/byte counts, signatures, AST
symbols, import locations, package versions, or already-loaded constants only
when it cannot mutate state or trigger import-time network/job behavior.
Prefer AST/source inspection over importing side-effectful modules.

## Source-first method and reply protocol

1. Establish the active checkout, executable entry points, route/tool
   registration, scheduler/deployment configuration, and worker source before
   consulting comments or prose docs. Treat prior architecture descriptions
   only as claims to test.
2. Mirror every numbered section and subsection below. Return only the
   requested blocks and tables.
3. Cite every source-backed claim with the exact current path and inclusive
   line range in `path:line-line` form. A directory, filename without lines,
   or prior answer is not evidence.
4. For every requested search, state exact roots and literal/regex patterns,
   then return every relevant match as `path:line:source`. Mark incomplete
   coverage `INCOMPLETE` and explain why.
5. Paste only bounded source blocks explicitly requested: registration,
   entrypoint, route, dispatch, worker orchestration, storage path, context
   registry/loader, security protocol, and vision/PDF call-site blocks. Do not
   paste entire large files, system prompts, user content, report prompts,
   observation bodies, email bodies, or data payloads.
6. A requested function/class block includes decorators and runs through its
   syntactic end. If it exceeds 200 lines, provide the signature plus the
   exact bounded branches requested, each with source ranges. Never use `...`
   inside a block described as verbatim.
7. Redact secrets, tokens, cookies, credentials, ticket material, internal
   prompt text not explicitly requested, email addresses/contents, report or
   observation contents, and user values. Preserve key names, types, paths,
   package names, public route shapes, signatures, control flow, and redacted
   schema structure.
8. Use only these verdicts wherever a verdict is requested:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. When source/config conflicts, cite both and use `CONTRADICTS` or `UNKNOWN`.
   Deployment/service configuration outranks dormant CLI code for what is
   live; executable source outranks comments; preserve every conflict.
10. Distinguish active production code, callable-but-unwired code, tests/dev
    tools, documentation/context, archived/history, and forward proposals.
11. Do not include a `## Frictions` section. This is context extraction, not
    end-usage testing.

## Required search roots and patterns

Search both current checkout roots. Begin with these candidates, resolving
their actual locations before making claims:

```text
prism-main/
prism-main/core/
prism-main/jobs/
prism-main/prism_meta/
prism-main/web/
prism-main/entrypoint.py
prism-main/prism-core/
prism-main/prism-core/prism_mcp/
prism-main/prism-core/context/
prism-main/prism-core/dashboards/
```

Also discover and search any current roots for:

```text
email
report_generation
reports
observations
observatory
evals
dev
prompts
services
deployment
cron
workers
```

Follow `pyproject.toml`, `setup.py`, `setup.cfg`, Docker files, shell/service
launchers, CI/deployment manifests, and import paths to roots with different
names.

At minimum, report searches for:

```text
teams_server
prism_chatbot
mcp/server
FastMCP
register_tool
execute_analysis_script
get_context
generate_report
submit_report
submit_observation
edit_report
edit_observation
send_email
email_processing
thread_manager
parallel_processor
lock_manager
thread_archiver
observatory
observation
snapshot
prism_loop
report_commission
report_workflow
planner
worker
writer
entrypoint
cron
schedule
security_and_status
SECURITY ALERT
vision_functions
check_chart_quality
check_charts_quality
describe_images
imagify_pdf
pdf_reading
llm_loop
diagnostic_workflow
deterministic
llm_judge
competitive
competitor
design principle
progressive disclosure
artifact-first
```

Also search for active `ai_development.*` imports, paths, module strings, and
compatibility aliases across both roots.

## 0. Freshness and checkout identity

Return only this concise block:

```text
INSPECTION_UTC:
PRISM_MAIN_ROOT:
PRISM_MAIN_HEAD:
PRISM_CORE_ROOT:
PRISM_CORE_CHECKED_OUT_SHA:
PRISM_CORE_RECORDED_SHA:
SUBMODULE_MATCH: YES/NO/UNKNOWN
```

State the source/command used for each value. If Git metadata is unavailable,
return `UNKNOWN`; do not infer identity.

Then list the resolved current roots for:

- interface servers/adapters;
- MCP server/tools;
- Django project/apps;
- email pipeline;
- report generation/publishing;
- Observatory/observations;
- scheduled jobs and deployment wiring;
- security/status context;
- vision/PDF helpers;
- developer loops and evaluations;
- internal competitive-positioning material.

## 1. User-facing interfaces and entry points

### 1.1 Physical interface inventory

Enumerate every active user-facing or worker-facing PRISM interface, not just
the historical four. Include Teams/chat, GS.AI/MCP, email, reports, Django
portals/APIs, scheduled/on-demand process interfaces, and any current CLI or
service boundary source marks as production.

Return:

| Interface | Protocol/transport | Executable entry point | Deployment/service entry | Identity source | Request/input shape | Response/artifact shape | Shared backend | Verdict |
|---|---|---|---|---|---|---|---|---|

Classify each interface as:

```text
interactive user
asynchronous user
worker/internal
admin/developer
test/dev only
callable but unwired
```

Do not treat every Django route as a separate interface. Group routes by
portal/API surface and defer detailed route inventory to subsection 4.

### 1.2 Entry and dispatch blocks

For each active interface, paste only:

- service/application construction;
- route/message/event registration;
- top-level request/message handler signature;
- dispatch into the LLM/MCP/report/email backend;
- response delivery call;
- production launch configuration.

Do not paste prompt bodies or user content.

Return:

| Interface | Entry block path/lines | Dispatch target | In-process/subprocess/remote | Streaming | Artifact delivery | Error boundary |
|---|---|---|---|---:|---|---|

Explicitly answer:

1. Are Microsoft Teams, GS.AI/web chat, email, and report generation all live
   current interfaces?
2. Does each converge on the same MCP tool server, reuse only selected
   helpers, or have an independent LLM/tool orchestration path?
3. Which historical entry filenames moved or disappeared?
4. Are report generation and report portal separate interfaces?
5. Are any legacy chat/server entry points still importable but not deployed?

End with:

```text
INTERFACE_INVENTORY_COMPLETE: YES/NO
INTERFACE_DEPLOYMENT_WIRING_COMPLETE: YES/NO
```

## 2. MCP, chat, and tool flow

### 2.1 MCP server registration

Locate the active MCP server implementation and paste only:

- server/application construction;
- complete tool-registration import/registration blocks;
- auth/identity middleware hookup;
- transport/server launch block;
- any bundle or feature-flag filtering of tools.

Return one row per registered tool:

| Tool name | Definition path/lines | Registration path/lines | Interface availability | Auth/identity input | Mutating/read-only | Active/deprecated | Verdict |
|---|---|---|---|---|---:|---|---|

Do not infer tool count from docs. Count live registration rows and identify
conditionally registered tools.

### 2.2 Chat request flow

Trace each interactive chat interface from inbound request/message to:

```text
identity resolution
  -> conversation/session state
  -> L1/global/tool context
  -> get_context/L2 assembly
  -> LLM/tool loop
  -> artifact/link handling
  -> stream/final response
  -> usage/audit persistence
```

Return:

| Stage | Teams path/lines | GS.AI/MCP path/lines | Django chat path/lines if any | Shared component | Divergence |
|---|---|---|---|---|---|

Paste only bounded orchestration/call-site blocks. Do not paste system prompt
or context-module bodies.

### 2.3 Context and tool-loading boundaries

Using current source, verify:

- where L1/global tool instructions are assembled;
- where `get_context` is registered and whether one-shot behavior is code
  enforced or instruction enforced;
- where L2 registry/assembler/loader are called;
- whether `list_ai_repo` still provides mid-session source reads and what
  roots it resolves after the split;
- where context-budget/overflow instrumentation runs;
- which interfaces/workers use the same context assembly path.

Return exact signatures and bounded call sites only. Fold detailed
data/world-state loading into the dependent sequence-5 answer; do not repeat
its module inventory.

### 2.4 Identity, sessions, and auditing

Return:

| Interface/process | Identity source | Session/conversation identifier | Storage/audit path | Usage tracker | Retention/archival owner | Evidence |
|---|---|---|---|---|---|---|

Redact values. Identify whether chat, email, report workers, and web requests
share the same session-folder/audit abstraction or write different state.

End with:

```text
MCP_TOOL_REGISTRY_COMPLETE: YES/NO
CHAT_REQUEST_FLOW_COMPLETE: YES/NO
CONTEXT_TOOL_BOUNDARY_COMPLETE: YES/NO
```

## 3. Email ingestion, threads, and delivery

### 3.1 Inbound and outbound architecture

Trace current email behavior from inbound acquisition to classification,
thread state, LLM/tool execution, response send, and archive.

Return:

| Stage | Implementation path/lines | Trigger/transport | Input schema | Lock/idempotency | Output/state written | Failure handling | Verdict |
|---|---|---|---|---|---|---|---|

Include inbound polling/webhook/job ownership, outbound SMTP/service
ownership, attachment handling, and production scheduler/service wiring.
Do not read or return actual email bodies or attachments.

### 3.2 Classification and thread semantics

Paste only:

- the classification enum/constants/schema;
- the dispatch branch for each classification;
- thread-key derivation;
- lock acquisition/release;
- thread load/update/archive decisions;
- reply-vs-silent behavior.

Return:

| Class/state | Trigger semantics | Reply behavior | Context retained | Thread transition | Archive behavior | Source evidence |
|---|---|---|---|---|---|---|

Explicitly verify whether the historical `Watch`, `Analysis`, and `Thread`
classes still exist and mean:

```text
Watch    -> CC'd/silent/read-only
Analysis -> perform work and reply
Thread   -> preserve context across messages
```

Do not infer classification meaning from names alone.

### 3.3 Concurrency and deduplication

Identify current ownership of:

- parallel processing;
- per-thread/message locks;
- duplicate detection/idempotency;
- retry/backoff;
- poison/failure handling;
- archival and stale-thread cleanup.

Return exact signatures and bounded decision branches, not whole classes.

### 3.4 Email-to-MCP/tool parity

Return:

| Capability | Interactive chat | Email analysis | Email thread | Difference source |
|---|---:|---:|---:|---|

Include L2 context, code execution, S3 search, report submission, observation
submission, chart/artifact attachment, and user identity. Use `UNKNOWN` when
the worker graph cannot prove parity.

End with:

```text
EMAIL_PIPELINE_COMPLETE: YES/NO
EMAIL_THREAD_STATE_COMPLETE: YES/NO
EMAIL_DEPLOYMENT_WIRING_COMPLETE: YES/NO
```

## 4. Django and portal surfaces outside dashboard mechanics

### 4.1 Project/app and route graph

Enumerate current Django project/app roots and route inclusions. Return every
non-dashboard PRISM surface grouped by function:

| Surface | URL prefix/pattern | App/root URLconf | View path/function | Methods | Auth decorator/middleware | Storage/backend | Verdict |
|---|---|---|---|---|---|---|---|

Cover report/observation portals, evals, usage/status/admin surfaces,
documents/white papers if present, chat endpoints if present, and any other
active PRISM portal.

For dashboard routes, return only one row:

```text
Dashboard portal and APIs -> already covered by
2026-07-11_dashboard_architecture_validation.md
```

Do not re-paste dashboard view blocks, URL details, sharing, refresh, or
storage schemas.

### 4.2 Django identity and authorization

Paste bounded source for:

- authenticated identity extraction;
- PRISM user allowlist/registry lookup;
- active/inactive handling;
- page/API authorization decorators or middleware;
- object-owner checks for reports/observations/documents where applicable.

Return:

| Surface | Viewer identity | Authorization source | Object owner/visibility rule | Cache/failure behavior | Evidence |
|---|---|---|---|---|---|

Redact user records and values.

### 4.3 Serving and artifact boundaries

For each portal, identify whether content comes from S3, filesystem, report
server, database, generated HTML, or another service. Return only schema/path
templates and call sites; do not enumerate or fetch private artifacts.

End with:

```text
DJANGO_ROUTE_GRAPH_COMPLETE: YES/NO
DJANGO_AUTH_BOUNDARY_COMPLETE: YES/NO
```

## 5. Observatory architecture

### 5.1 Physical inventory and active processes

Enumerate every current source/config file whose primary ownership is
Observatory, observations, reports generated by the Observatory, or its
orchestrator.

Return:

| Current path | Component/process | Public entry point | Called by | Scheduled/on-demand | Reads | Writes | Active/test/doc | Verdict |
|---|---|---|---|---|---|---|---|---|

Identify compatibility aliases and historical files that moved. Do not return
observation/report contents.

### 5.2 Process graph

Build a source-backed graph from current code:

```text
screening/framework execution
  -> observation create/refresh/deprecate
  -> snapshot/materialized read model
  -> context/portal consumers

events/data releases/observation state
  -> orchestrator/scheduling
  -> report commission
  -> planner
  -> parallel workers
  -> writer
  -> publication
  -> observations emitted as report side effects, if current
```

For each edge cite the producer call site and consumer call site.

Return:

| From component | To component | Trigger/data passed | Process boundary | Storage handoff | Failure/retry behavior | Evidence |
|---|---|---|---|---|---|---|

### 5.3 Observation lifecycle and schemas

Locate current observation schema/enums and paste only:

- ID/domain/status/type enums or literal sets;
- required fields and validation;
- create/update/deprecate transitions;
- storage path construction;
- source/provenance fields;
- report linkage fields.

Return:

| Field/state | Type | Required | Writer(s) | Reader(s) | Transition/default | Evidence |
|---|---|---:|---|---|---|---|

Redact example values. Identify whether observations are markdown, JSON,
database rows, or multiple artifacts in current production.

### 5.4 Snapshot/materialized read model

Return exact current:

- snapshot producer entry point;
- scheduler/deployment registration;
- cadence;
- source observation enumeration;
- output schema keys with values redacted;
- storage path;
- atomicity/overwrite behavior;
- consumers in context, portals, reports, or APIs;
- stale/missing behavior.

Do not run the snapshot.

### 5.5 Framework/dashboard state

Determine whether Observatory analytical frameworks still maintain dashboard
folders as state. Return:

| Framework/state type | Config/schema owner | Storage path | Refresh/screen owner | End-user consumer | Verdict |
|---|---|---|---|---|---|

Do not re-inspect ECharts/dashboard compiler mechanics. Treat a dashboard as
an Observatory-owned state/artifact edge only.

End with:

```text
OBSERVATORY_COMPONENT_INVENTORY_COMPLETE: YES/NO
OBSERVATORY_PROCESS_GRAPH_COMPLETE: YES/NO
OBSERVATION_SCHEMA_COMPLETE: YES/NO
OBSERVATORY_SNAPSHOT_COMPLETE: YES/NO
```

## 6. Report and observation workers

### 6.1 Entry points and orchestration

Enumerate all active report-generation, report-publishing, and
observation-publishing entry points, including MCP tools, internal APIs,
scheduled commissions, and worker CLIs/services.

Return:

| Entry point/tool | Definition path/lines | Orchestrator/worker target | Async mechanism | Identity/context | Output | Active/deprecated | Verdict |
|---|---|---|---|---|---|---|---|---|

Distinguish at minimum:

```text
generate_report
submit_report
edit_report
submit_observation
edit_observation
scheduled/orchestrated report commission
legacy report workflow
current report workflow
```

Use source to determine which names still exist.

### 6.2 Planner/worker/writer topology

If the live workflow remains multi-stage, return:

| Stage | Implementation | Model/client | Input contract | Tool/context availability | Parallelism | Output handoff | Retry/failure |
|---|---|---|---|---|---|---|---|

Paste only orchestration and worker-construction blocks. Do not paste report
prompts or generated report content.

Explicitly verify:

1. Does the current workflow use Planner -> parallel Workers -> Writer?
2. Is it implemented with LangGraph, a custom orchestrator, subprocesses,
   queues, direct async calls, or another mechanism?
3. How many LLM calls are fixed versus data-dependent?
4. Which specialization/context bundle does each stage receive?
5. Do workers use the ordinary MCP server/tools or an independently assembled
   tool set?
6. Which publication pipeline produces PDF, HTML, markdown, or portal entries?
7. Are observations still emitted as report side effects?

### 6.3 Storage and publication

Return redacted schema/path templates for report commission, worker outputs,
draft/final report artifacts, publication metadata, PDFs/HTML, and linked
observations. Identify writer and reader call sites and retention/versioning.

### 6.4 Legacy versus live

Search for `report_generation/`, `report_workflow`, `report_server`,
`report_portal`, LangGraph imports, and replacement modules. Return:

| Historical/current component | Exists | Imported/called | Deployment registered | Current owner/replacement | Verdict | Evidence |
|---|---:|---:|---:|---|---|---|

End with:

```text
REPORT_ENTRYPOINTS_COMPLETE: YES/NO
REPORT_WORKER_TOPOLOGY_COMPLETE: YES/NO
REPORT_STORAGE_PUBLICATION_COMPLETE: YES/NO
```

## 7. Jobs, cadence, and deployment wiring

### 7.1 Complete non-dashboard job inventory

Enumerate every active scheduled or continuously running job outside the
dashboard refresh job. Do not rely on folder names for cadence.

Return one row per job:

| Job path/module | Domain/purpose | Scheduler/service registration | Exact command | Live cadence | One-shot/daemon | Inputs | Outputs | Lock/retry/failure isolation | Consumers | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|

Group the final table by actual cadence, not directory.

The sequence-5 prompt owns data/world-state producer internals. For those
jobs, include only deployment registration and cross-reference the dependent
answer for input/output mechanics. This section must additionally cover
Observatory, reports, email, cleanup, usage, eval, and other architecture
jobs not owned there.

### 7.2 Scheduler and entrypoint source

Paste only:

- root scheduler/entrypoint registration tables;
- cron/interval expressions;
- subprocess/command construction;
- service/container launch configuration;
- global exception isolation and logging setup;
- environment/cwd/interpreter setup.

Return:

| Scheduler owner | Registration source | Process launched | Cadence | Interpreter/cwd/env | Concurrent/sequential | Restart policy | Verdict |
|---|---|---|---|---|---|---|---|

### 7.3 Alternative deployment wiring

Search for jobs activated outside the root entrypoint:

```text
crontab/cron expressions
systemd/service files
Docker/Kubernetes/ECS manifests
CI schedules
supervisors
queue workers
web-process startup hooks
external scheduler configuration referenced by source
```

Do not infer external infrastructure that is not represented in the
checkout. Use `UNKNOWN` when code names an external scheduler but its
configuration is not readable.

### 7.4 Cadence contradictions

Return:

| Job | Folder-implied cadence | Actual deployed cadence | Code default cadence | On-demand path | Verdict | Evidence |
|---|---|---|---|---|---|---|

Explicitly test the historical lists of minutely, hourly, and daily jobs and
identify moved, renamed, added, retired, or unwired files.

End with:

```text
NON_DASHBOARD_JOB_INVENTORY_COMPLETE: YES/NO
SCHEDULER_REGISTRATION_COMPLETE: YES/NO
DEPLOYMENT_ACTIVATION_COMPLETE: YES/NO
CADENCE_RECONCILIATION_COMPLETE: YES/NO
```

## 8. Security and platform-status L2 context

### 8.1 Registration and loading

Locate the current security/status context surface. Return:

| Registry key | Tier | Pillar/category | Content type | Source path | Auto-load rule | Specialization exceptions | Loader | Verdict |
|---|---:|---|---|---|---|---|---|---|

Verify whether security and platform status still share one strict Tier-1
module, were split, renamed, or moved. Paste the complete bounded registry
row(s) and assembler auto-load decision, not the whole context body.

### 8.2 Security policy and executable enforcement

From the live L2 content and executable code, build:

| Threat/policy | Taught in context | Enforced in code/middleware | Severity/action | Alert owner | Evidence | Verdict |
|---|---:|---:|---|---|---|---|

Do not reproduce sensitive system prompts or operational secrets. It is
permitted to report category names, severity labels, control flow, and
redacted alert schema.

Explicitly verify:

1. Which historical threat categories remain?
2. Is neutral deflection instruction-only or code-enforced?
3. Does suspicious activity still trigger an alert email, and through which
   function/configuration?
4. Is the recipient hardcoded, configured, or removed? Redact its value.
5. What distinguishes developer-mode exploration from prohibited bulk
   exfiltration?
6. What authorization/entitlement controls exist outside the L2 instruction?

Do not trigger an alert.

### 8.3 Platform status and limitations

Return current source-backed status claims for:

- arbitrary internet/web browsing;
- approved external API integrations;
- S3 access boundaries;
- supported chart/dashboard/report/PDF surfaces;
- known platform limitations and user-facing escalation language.

Distinguish:

```text
no arbitrary web browsing
approved API integrations can make outbound requests
workers/jobs may ingest public data
developer tools can read repository source
```

Do not treat these as contradictory unless current source actually conflicts.
The dashboard and data prompts own their detailed capability lists.

### 8.4 Drift between context and implementation

Search every capability/limitation named in the security/status module
against current executable source. Return:

| Context claim | Implementation evidence | Current/stale | Verdict | Required local target |
|---|---|---|---|---|

End with:

```text
SECURITY_STATUS_REGISTRATION_COMPLETE: YES/NO
SECURITY_POLICY_MAPPING_COMPLETE: YES/NO
PLATFORM_STATUS_DRIFT_CHECK_COMPLETE: YES/NO
```

## 9. Vision, PDF, and QC implementation status

### 9.1 Physical inventory and public surface

Locate current modules for chart/image vision, PDF reading/imagification, PDF
generation, multimodal uploads, and post-execution QC.

Return:

| Module/path | Public symbol | Exact signature | Injected/tool name | Active caller(s) | External service/model config | Active/dead/deprecated | Verdict |
|---|---|---|---|---|---|---|---|

At minimum search for:

```text
check_chart_quality
check_charts_quality_parallel
_check_charts_quality_injected
_check_chart_quality_safe
describe_images
imagify_pdf
pdf_reading_functions
submit_report
latex_compiler
QUALITY_CHECK_PROMPT
DEFAULT_VISION_PROMPT
document_id
questionContext
```

Redact credentials and internal headers. Model/application/environment names
may be reported when present as non-secret configuration.

### 9.2 Automatic chart QC call graph

Trace all automatic and explicit paths:

```text
chart render/save
  -> automatic engine-internal QC, if any
  -> automatic post-exec sweep, if any
  -> explicit sandbox/tool QC, if any
  -> stdout/result/artifact behavior
```

Return:

| Path | Trigger | Call site | Number of model calls | Blocks delivery | Fail-open/closed | Result schema | Consumer | Verdict |
|---|---|---|---:|---:|---|---|---|---|

Do not invoke QC or paste the full long-form QC prompt. Return its current
constant location, hash/line count if useful, required output prefixes, and
the bounded response-parsing block.

Explicitly resolve:

1. Is engine-internal QC active, dead but defined, or absent?
2. Is a post-execution sweep active in live production?
3. Does it return only GOOD/BAD, or also an analyst-eye description?
4. Are descriptions printed to sandbox stdout?
5. Is the current behavior fail-open, and what must callers inspect besides
   `passed`?
6. Which statements in local `prism/vision-qc.md` describe staging intent
   rather than installed behavior?
7. Was vision-driven annotation generation removed from installed code or
   only from staging?

### 9.3 Image-description and PDF-read flow

Trace:

```text
PDF/input path
  -> page/image materialization
  -> S3/local bytes
  -> multimodal upload
  -> per-page/image calls
  -> ordering/aggregation
  -> returned description/artifacts
```

Return:

| Stage | Function/path | Input | Output | Parallelism | Persistence | Failure behavior | Evidence |
|---|---|---|---|---|---|---|---|

Do not read a real PDF or upload an image. Use source and test fixtures only.

### 9.4 PDF generation versus reading

Distinguish current implementations for:

- reading/understanding PDFs;
- rendering pages to images;
- generating report PDFs;
- serving/downloading PDFs.

Return the exact entry points, dependencies, process boundaries, and output
paths. Do not conflate Gemini vision with LaTeX/report compilation.

End with:

```text
VISION_PUBLIC_SURFACE_COMPLETE: YES/NO
CHART_QC_CALL_GRAPH_COMPLETE: YES/NO
VISION_ACTIVE_RETIRED_STATUS_COMPLETE: YES/NO
PDF_READ_FLOW_COMPLETE: YES/NO
PDF_GENERATION_FLOW_COMPLETE: YES/NO
```

## 10. Developer loops and evaluation infrastructure

### 10.1 Dev-loop inventory

Enumerate active autonomous/developer loop implementations and their
production/dev wiring.

Return:

| Loop/type | Implementation path | Entry point | Mutating/read-only policy | Persistent state path | Stop/approval boundary | Model/tool surface | Active/dev-only | Verdict |
|---|---|---|---|---|---|---|---|---|

Verify whether historical implementation/testing/debugging/investigator loop
types still exist and whether their mutation policies are code-enforced,
prompt-enforced, or merely documented.

Paste only loop registration/type definitions, state-path construction, and
the bounded dispatch/termination logic. Do not run a loop or paste its full
prompt.

### 10.2 Diagnostic infrastructure

Trace session diagnostics, context-budget diagnostics, bug/investigation
workflows, and any chart/dashboard/data-specific loops. Return:

| Diagnostic surface | Trigger/entry | Reads | Writes | Worker/model | Output | Production/dev | Evidence |
|---|---|---|---|---|---|---|---|

### 10.3 Eval inventory

Enumerate every current evaluation framework, suite, harness, portal, and
scheduled eval.

Return:

| Eval mode/suite | Path | Runner/entry point | Dataset/question source | Scoring/validator | Judge model if any | Persistence/reporting | Scheduled/on-demand | Verdict |
|---|---|---|---|---|---|---|---|---|

Explicitly verify:

1. Do deterministic and LLM-judge modes still exist?
2. Is there one `prism_test_harness.py` or a replacement/split harness?
3. Which evals exercise live tools versus mocks/fixtures?
4. Which evals are read-only and which write artifacts/state?
5. Is an eval portal active in Django?
6. Are any evals scheduled in production?
7. How are regressions, baselines, and pass/fail state stored?

Do not run evals.

### 10.4 Dev/eval deployment boundary

Return:

| Component | Importable in production | Exposed to end users | Deployment registered | Developer-only guard | Verdict | Evidence |
|---|---:|---:|---:|---|---|---|

End with:

```text
DEV_LOOP_INVENTORY_COMPLETE: YES/NO
DEV_LOOP_POLICY_COMPLETE: YES/NO
DIAGNOSTIC_INFRA_COMPLETE: YES/NO
EVAL_INFRA_COMPLETE: YES/NO
DEV_EVAL_DEPLOYMENT_BOUNDARY_COMPLETE: YES/NO
```

## 11. Current design principles as represented in source

Do not invent or philosophically reinterpret principles. Locate current
authoritative internal docs, L1/L2 context, code comments, tests, or
architecture metadata that explicitly names or operationalizes design
principles.

Search for the historical principles:

```text
RLM / Recursive Language Model
Progressive Disclosure
LLM-First Problem Solving
Context Over Code
Observations Mosaic
Verbalised Sampling
One-Shot Full Upgrade
Artifact-First
Extensibility
Auditability
Composability
Engines Absorb Friction
```

Return:

| Principle/name | Current authoritative source | Executable/test manifestation | Current wording/meaning | Active/historical/proposal | Verdict |
|---|---|---|---|---|---|

Requirements:

- Quote at most the bounded paragraph/table row that defines each principle.
- Distinguish a principle explicitly represented in live PRISM from a
  Cursor/staging doctrine not present in PRISM.
- Do not infer a named principle solely because code happens to resemble it.
- Identify contradictions between principles and current implementation only
  when both sides have direct evidence.
- Identify the current owner for updating architecture/design-principle docs.

Then return a compact current set:

```text
LIVE_EXPLICIT_PRINCIPLES:
  - <name>: <one source-backed sentence>

STAGING_OR_HISTORICAL_ONLY:
  - <name>: <why it is not live>
```

## 12. Internal competitive-positioning source and ownership

This section is source-location and ownership introspection only.

Do not:

- browse the web or call external search/APIs;
- research any competitor;
- validate feature claims, scores, market share, product capabilities, or
  vendor comparisons;
- update the matrix from general knowledge;
- present an internal PRISM document as independent external evidence.

### 12.1 Locate current sources

Search for active files, context modules, reports, prompts, routes, jobs, or
owners containing competitive positioning. Include terms for known historical
vendors only as filename/content search keys, not as facts to investigate.

Return:

| Source path | Content type | Registered/served/generated | Owner/maintainer from source | Last-updated metadata | Inputs/citations recorded | Internal/external evidence status | Verdict |
|---|---|---|---|---|---|---|---|

### 12.2 Consumption and ownership graph

Return:

```text
authoritative internal positioning source
  -> generator/editor/owner
  -> registry/context/portal/report consumer
  -> derived copies or stale duplicates
```

For each edge cite source. Identify whether the current internal source is:

```text
LLM context
developer strategy doc
customer-facing collateral
generated report
archived historical material
not present
```

### 12.3 Evidence disclaimer

Return exactly:

```text
INTERNAL_POSITIONING_SOURCE_LOCATED: YES/NO
INTERNAL_SOURCE_IS_EXTERNAL_PROOF: NO
EXTERNAL_COMPETITOR_RESEARCH_PERFORMED: NO
```

If `INTERNAL_POSITIONING_SOURCE_LOCATED` is `NO`, report search coverage in
`## Could not resolve`; do not compensate with external research.

Any future fold into `prism/competitive-spec.md` must be limited to:

- current internal source path;
- ownership/maintainer;
- consumption path;
- freshness/citation limitations;
- explicit statement that internal self-scoring is not external proof.

Do not return revised competitive scores or capability claims.

## 13. Current architecture path graph

Return one canonical physical/package graph:

```text
prism-main/
  <interfaces, core, jobs, web, metadata, deployment>
  prism-core/
    <MCP, context, dashboards, other submodule packages>
```

Annotate each node with:

- checkout owner;
- Python import package;
- executable/service entry point;
- principal caller/consumer;
- active versus dev/test/history.

Then return:

| Historical path/claim | Current target | Compatibility alias exists | Active import/deployment use | Verdict | Evidence |
|---|---|---:|---:|---|---|

Include at minimum the historical surfaces:

```text
ai_development/core/
ai_development/mcp/
ai_development/context/
ai_development/email/
ai_development/jobs/
ai_development/mysite/
ai_development/report_generation/
ai_development/evals/
ai_development/prompts/
core/observations/
core/dev/
development/dev_loops/
secondary/prism_observations/
```

Search all active imports, string module paths, launcher commands, and
deployment config for `ai_development.*`. Distinguish comments/docs/archives
from executable compatibility.

### 13.1 End-to-end architecture edges

Return a source-backed edge list:

```text
interface_or_scheduler
  -> handler_or_worker
  -> context/tool/data boundary
  -> artifact/state store
  -> user/worker consumer
```

Provide one path for Teams/chat, GS.AI/MCP, email, report generation,
Observatory screening/snapshot, Django portal, scheduled jobs, dev loops, and
evals. Cross-reference rather than repeat the dashboard and data details
owned by dependent prompts.

End with:

```text
CURRENT_ARCHITECTURE_PATH_GRAPH_COMPLETE: YES/NO
END_TO_END_EDGE_GRAPH_COMPLETE: YES/NO
ACTIVE_AI_DEVELOPMENT_REFERENCE_SEARCH_COMPLETE: YES/NO
```

## 14. Remaining-architecture contradiction ledger

Resolve every local historical assumption below from current source. Use only
the fixed verdict vocabulary.

| ID | Local historical assumption to test | Verdict | Current production fact | Exact evidence |
|---|---|---|---|---|
| A01 | PRISM has exactly four user interfaces: Teams, GS.AI/web MCP, Email, and Report Generation. | | | |
| A02 | All user interfaces converge on one identical MCP tool layer. | | | |
| A03 | `core/teams_server.py`, `core/prism_chatbot.py`, `mcp/server.py`, `email/email_processing.py`, and `report_generation/` remain the live entry paths. | | | |
| A04 | The MCP server registers approximately 20 tools. | | | |
| A05 | `get_context` remains instruction-enforced one-shot rather than code-enforced one-shot. | | | |
| A06 | `list_ai_repo` remains the mid-session repository-read mechanism and resolves the current split roots correctly. | | | |
| A07 | Email still uses Watch, Analysis, and Thread behavioral classes with the historical semantics. | | | |
| A08 | Email concurrency is owned by `parallel_processor.py`, `lock_manager.py`, and `thread_archiver.py`. | | | |
| A09 | The current Django root is `web/backend_django/`, and old `mysite/` paths are retired. | | | |
| A10 | Observatory still consists of screening, snapshot materialization, and report scheduling as three principal processes. | | | |
| A11 | Observatory snapshots are materialized on a minutely cadence into a read-only JSON consumer surface. | | | |
| A12 | Observatory storage remains rooted under `secondary/prism_observations/` with config, snapshot, orchestrator state, dashboards, observations, and reports. | | | |
| A13 | Report generation remains Planner -> parallel Workers -> Writer -> PDF/HTML publication. | | | |
| A14 | Reports still emit observations as side effects. | | | |
| A15 | A root `entrypoint.py` is the production scheduler for all minutely/hourly/daily jobs. | | | |
| A16 | Historical job folder cadence accurately describes deployed cadence. | | | |
| A17 | `security_and_status` is one strict Tier-1 context module loaded on every conversation. | | | |
| A18 | Security vigilance is primarily LLM instruction with alert-email side effects rather than middleware enforcement. | | | |
| A19 | “PRISM has no internet access” means no arbitrary browsing, while approved clients/jobs can still make outbound requests. | | | |
| A20 | Engine-internal chart QC is retired, while a post-execution vision sweep remains active. | | | |
| A21 | The post-execution sweep returns GOOD/BAD plus an analyst-eye description and prints passing descriptions to stdout. | | | |
| A22 | Vision/QC failures are fail-open and do not block chart delivery. | | | |
| A23 | `describe_images` and `imagify_pdf` remain active, parallel multimodal reading surfaces. | | | |
| A24 | PDF reading and report PDF generation are separate pipelines. | | | |
| A25 | Dev loops still include implementation, testing, debugging, and investigator modes with different mutation policies. | | | |
| A26 | Dev-loop state remains under `development/dev_loops/{type}_{id}/state.md`. | | | |
| A27 | Evals still have deterministic and LLM-judge modes plus a monolithic `prism_test_harness.py`. | | | |
| A28 | The historical architecture principles remain explicitly represented in live PRISM docs/context/code. | | | |
| A29 | The local competitive matrix has a current live internal counterpart with identifiable ownership. | | | |
| A30 | Any internal competitive source is sufficient external proof of competitor capabilities. | | | |
| A31 | No active executable or deployment path still imports `ai_development.*`. | | | |
| A32 | The split-checkout path graph documented for dashboards generalizes unchanged to every other architecture surface. | | | |

For A30, the only acceptable resolved verdict is `CONTRADICTS`: an internal
source is not independent external proof. If no internal source exists, A29
may be `NOT_PRESENT`, but A30 remains `CONTRADICTS` as an evidentiary rule.

For every `CONTRADICTS` or `UNKNOWN` row, name the exact local target that
must remain untrusted:

```text
prism/architecture.md
prism/codebase-tree.md
prism/security.md
prism/vision-qc.md
prism/competitive-spec.md
prism/mcp-tools.md
prism/README.md
```

Do not propose fixes or redesigns in this ledger.

## 15. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
CHECKOUT_IDENTITY_COMPLETE:
INTERFACE_INVENTORY_COMPLETE:
INTERFACE_DEPLOYMENT_WIRING_COMPLETE:
MCP_TOOL_REGISTRY_COMPLETE:
CHAT_REQUEST_FLOW_COMPLETE:
CONTEXT_TOOL_BOUNDARY_COMPLETE:
EMAIL_PIPELINE_COMPLETE:
EMAIL_THREAD_STATE_COMPLETE:
EMAIL_DEPLOYMENT_WIRING_COMPLETE:
DJANGO_ROUTE_GRAPH_COMPLETE:
DJANGO_AUTH_BOUNDARY_COMPLETE:
OBSERVATORY_COMPONENT_INVENTORY_COMPLETE:
OBSERVATORY_PROCESS_GRAPH_COMPLETE:
OBSERVATION_SCHEMA_COMPLETE:
OBSERVATORY_SNAPSHOT_COMPLETE:
REPORT_ENTRYPOINTS_COMPLETE:
REPORT_WORKER_TOPOLOGY_COMPLETE:
REPORT_STORAGE_PUBLICATION_COMPLETE:
NON_DASHBOARD_JOB_INVENTORY_COMPLETE:
SCHEDULER_REGISTRATION_COMPLETE:
DEPLOYMENT_ACTIVATION_COMPLETE:
CADENCE_RECONCILIATION_COMPLETE:
SECURITY_STATUS_REGISTRATION_COMPLETE:
SECURITY_POLICY_MAPPING_COMPLETE:
PLATFORM_STATUS_DRIFT_CHECK_COMPLETE:
VISION_PUBLIC_SURFACE_COMPLETE:
CHART_QC_CALL_GRAPH_COMPLETE:
VISION_ACTIVE_RETIRED_STATUS_COMPLETE:
PDF_READ_FLOW_COMPLETE:
PDF_GENERATION_FLOW_COMPLETE:
DEV_LOOP_INVENTORY_COMPLETE:
DEV_LOOP_POLICY_COMPLETE:
DIAGNOSTIC_INFRA_COMPLETE:
EVAL_INFRA_COMPLETE:
DEV_EVAL_DEPLOYMENT_BOUNDARY_COMPLETE:
LIVE_DESIGN_PRINCIPLES_COMPLETE:
INTERNAL_COMPETITIVE_SOURCE_OWNERSHIP_COMPLETE:
CURRENT_ARCHITECTURE_PATH_GRAPH_COMPLETE:
END_TO_END_EDGE_GRAPH_COMPLETE:
ACTIVE_AI_DEVELOPMENT_REFERENCE_SEARCH_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
REMAINING_ARCHITECTURE_REFRESH_COMPLETE:
```

`REMAINING_ARCHITECTURE_REFRESH_COMPLETE` may be `YES` only when every
preceding item is `YES`. If it is `NO`, list only unresolved
section/subsection numbers and the missing source, search coverage, or
permission.

If any requested item cannot be answered, end with:

## Could not resolve

List each unresolved item as:

```text
- Section/subsection:
  Searched roots:
  Searched patterns:
  Blocker:
```

Do not include recommendations, speculative replacements, revised competitor
claims, or a `Frictions` section.
