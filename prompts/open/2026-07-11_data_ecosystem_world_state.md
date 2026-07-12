---
class: context-extraction
topic: data-ecosystem-world-state
status: READY
created: 2026-07-11
sequence: 5/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
  - staging/prompts/open/2026-07-11_dashboard_data_pull_contracts.md
  - staging/prompts/open/2026-07-11_sandbox_storage_execution.md
reply_folded_into:
  - prism/api-clients.md
  - prism/gs-proxy.md
  - prism/data-functions.md
  - prism/world-state.md
  - prism/architecture.md
  - prism/codebase-tree.md
  - prism/README.md
---

# Context-extraction prompt — data ecosystem and world state

**Why this exists (staging-only note; do not paste this section into
PRISM):**

The local data documentation is historical and internally inconsistent after
the `prism-main` / `prism-core` split. It still describes 17 clients under
`ai_development/mcp/clients/`, a 13-module package export hub, 10 sandbox
client injections, seven world-state modules, and pre-split utility/context
paths. The staging roster now places clients and the GS proxy in parent-tree
`core/mcp/`, while data helpers and L2 context appear to live in the
`prism-core` submodule. Counts, paths, exports, injection, registry mappings,
transport choices, ingestion producers, and world-state freshness therefore
need one source-backed current pass.

This is sequence 5 of 7. The dashboard architecture prompt already covers
dashboard-specific helper injection, persisted-script namespaces, refresh
runner mechanics, registry/status schemas, and portal endpoints. This prompt
must use that answer as a boundary and inspect the data ecosystem itself,
without repeating dashboard compiler or refresh mechanics.

The reply should be folded only into the files listed in
`reply_folded_into`, after its evidence and contradiction ledger have been
reviewed.

---

## Paste the following into PRISM

# Data ecosystem and world-state architecture refresh (read-only)

You are being asked to inspect the current PRISM checkout and return a
source-backed map of its data ecosystem and world-state surfaces after the
`prism-main` / `prism-core` split. This is a pure read-only
context-extraction request. Do not answer from memory or from a prior
conversation.

The dashboard subsystem was separately inspected in
`2026-07-11_dashboard_architecture_validation.md`. Do not repeat dashboard
compiler, refresh-runner, registry/status, portal-route, or persisted-script
namespace details. Where a data contract touches dashboards, identify only
the shared data helper/client boundary and cite the earlier dashboard
inspection as an already-covered consumer.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- invoke any external API client, data pull, scraper, crawler, ingestion job,
  world-state refresh, scheduler, report process, or dashboard process;
- issue outbound HTTP requests, Kerberos/SPNEGO handshakes, proxy CONNECTs,
  or requests to direct-public hosts;
- run `entrypoint.py`, any file under `jobs/`, or any module's `main()`;
- write, copy, move, or delete S3 objects, cached context, indexes, session
  artifacts, world-state snapshots, manifests, logs, or status files;
- send email, create a ticket, start a subprocess, or install/upgrade a
  package;
- enumerate user-private S3 objects or expose credentials, tokens, cookies,
  ticket-cache contents, API keys, account identifiers, or user data values.

Read repository source, static configuration, deployment wiring, and
redacted existing schemas only. A short introspection script may print file
paths, line counts, byte counts, import locations, signatures, AST-derived
symbol names, or already-loaded constant shapes only when it cannot mutate
state or trigger import-time network/job behavior. Prefer AST/source
inspection over importing modules with side effects.

## Source-first method and reply protocol

1. Start from the current checkout, source tree, package files, registry,
   loader/assembler, sandbox injection source, jobs, and deployment
   configuration. Treat prose docs and prior answers only as claims to test.
2. Mirror every numbered section and subsection below. Do not add unrelated
   architecture commentary.
3. Cite every source-backed claim with the exact current repository path and
   inclusive line range. Use `path:line-line`; do not cite a directory,
   filename without lines, or prior conversation as evidence.
4. When a repository search is requested, state the exact roots and literal
   or regex patterns searched, then return every relevant match as
   `path:line:source`. If a root does not exist, say so. If search coverage is
   incomplete, mark it `INCOMPLETE` and explain why.
5. Paste only the bounded blocks explicitly requested: import/export blocks,
   namespace entries, registry rows, loader mappings, transport APIs, path
   constants, and scheduler call sites. Do not paste whole large files,
   whole client bodies, generated context bodies, data payloads, or secrets.
6. A requested function/class block runs from its declaration through its
   syntactic end, including decorators and immediately relevant imports.
   If it exceeds 200 lines, provide its signature plus the exact bounded
   branches requested, with line ranges; never use `...` inside a purported
   verbatim block.
7. Redact secrets, tokens, cookies, credentials, ticket-cache contents,
   internal host credentials, API keys, and user data values. Preserve key
   names, types, module names, public hostnames, paths, signatures, control
   flow, and redacted schema shape.
8. Use only these verdicts wherever a verdict is requested:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. If sources conflict, show both exact citations and use `CONTRADICTS` or
   `UNKNOWN`; do not silently choose one. Executed/deployed configuration
   outranks comments, and executable source outranks historical prose, but
   preserve the conflict.
10. Separate current behavior from forward proposals. A proposal may be
    reported only when a current source labels it as proposed/disabled or
    when exhaustive source search returns `NOT_PRESENT`. Never present a
    local historical proposal as live PRISM behavior.
11. Do not include a `## Frictions` section. This is context extraction, not
    end-usage testing.

## Required search roots and patterns

Search both checkout roots. Begin with these candidate roots, but first
resolve their actual current locations:

```text
prism-main/
prism-main/core/
prism-main/core/mcp/
prism-main/core/mcp/clients/
prism-main/jobs/
prism-main/entrypoint.py
prism-main/prism-core/
prism-main/prism-core/prism_mcp/
prism-main/prism-core/context/
```

Also search any package/deployment roots discovered through `pyproject.toml`,
`setup.py`, `setup.cfg`, service files, shell launchers, Docker files, or
entrypoint configuration.

At minimum, report searches for these patterns:

```text
clients
__all__
exec_namespace
execute_analysis_script
_client
pull_*_data
save_artifact
MODULE_REGISTRY
bundle
world_state
market_dashboard
news_snapshot
calendars
auction_schedule
prediction_markets_snapshot
world_timeline
earnings_calendar
session_and_auth
manual_https_request
KerberosProxyAuthAdapter
get_spnego_token
KRB5CCNAME
Proxy-Authorization
requests.Session
grep_s3
glob_s3
get_s3_files
context_cache
entrypoint
cron
schedule
```

Do not limit searches to the historical paths above. Search import strings,
dynamic imports, package re-exports, registry/config literals, launcher
argv, and renamed modules across both roots.

## 0. Freshness and checkout identity

Return a concise identity block:

```text
INSPECTION_UTC:
PRISM_MAIN_ROOT:
PRISM_MAIN_HEAD:
PRISM_CORE_ROOT:
PRISM_CORE_CHECKED_OUT_SHA:
PRISM_CORE_RECORDED_SHA:
SUBMODULE_MATCH: YES/NO/UNKNOWN
```

State the command/source used for each value. If Git metadata is unavailable,
return `UNKNOWN`; do not infer identity from a path or deployment label.
Do not repeat the longer dashboard environment dump.

Then return the current absolute and repository-relative locations of:

- the external-client package;
- the GS proxy/transport module;
- the script-execution/sandbox injection module;
- data helper implementations and backend classes;
- context registry, assembler, loader, static modules, runtime modules, and
  cached-context root;
- jobs root and scheduler/entrypoint configuration.

## 1. Current external API client inventory

### 1.1 Physical inventory

Programmatically enumerate every Python module in the active external-client
package, excluding caches and generated bytecode. Include package markers,
shared utilities, base classes, and files without a `_client.py` suffix.

Return one row per file:

| Current path | Module name | Bytes | Lines | Public functions | Public classes | Imported by active code | Status |
|---|---|---:|---:|---|---|---|---|

`Status` must be one of the fixed verdicts. Use `CONFIRMED` when the file is
part of the active client package, `NOT_PRESENT` for a specifically checked
historical file that no longer exists, and `UNKNOWN` only when package
ownership cannot be resolved.

For `Public functions` and `Public classes`, list every top-level non-private
symbol and its exact signature, derived from source/AST without importing the
module. Do not paste method bodies or docstrings. If a module intentionally
exports a private-looking name through `__all__`, include it and mark it
`explicit export`.

Explicitly answer:

1. What is the exact current client count, excluding `__init__.py` and shared
   utility/base files?
2. Which historical 17 client names still exist, which moved, which were
   renamed, and which are absent?
3. Which clients were added after the historical 17-client inventory?
4. Does a live module still use the exceptional name `congress.py`, or has it
   moved/renamed?
5. Are there client implementations outside the primary package that expose
   comparable external-API behavior?

### 1.2 Package exports

Paste the complete bounded import and `__all__` blocks from every active
client-package `__init__.py`. If exports are generated dynamically, paste the
complete generating block instead.

Return:

| Client module | Physical file | Imported by package | In `__all__` | Lazy/dynamic export | Import path that works by source semantics | Verdict |
|---|---|---:|---:|---:|---|---|

Search for all package-level re-export hubs, compatibility aliases, and
retired `ai_development.mcp.clients` imports. State whether omissions from
`__all__` affect explicit submodule imports in the current package layout.

### 1.3 Active consumers

Search both roots for static imports, `importlib`/dynamic imports, string
module paths, sandbox namespace entries, job imports, world-state producers,
report/observation imports, and tests/diagnostics that consume client
modules.

Return:

| Client | Consumer path/lines | Import or lookup shape | Runtime surface | Active/config/test/doc | Verdict |
|---|---|---|---|---|---|

Do not count comments or historical docs as runtime consumers. End with:

```text
CLIENT_PHYSICAL_INVENTORY_COMPLETE: YES/NO
CLIENT_CONSUMER_SEARCH_COMPLETE: YES/NO
```

## 2. Sandbox export and injection status

### 2.1 Import and namespace blocks

From the current `execute_analysis_script` implementation, paste only:

- the complete external-client import block;
- the complete data-helper import block;
- the client/data-helper entries in the execution namespace;
- any wrapper/partial/alias construction applied to those entries;
- any allowlist/denylist or sanitization that changes availability.

Return one row for every physical client:

| Client module | Package-exported | Imported by sandbox module | Injected name(s) | Injected as module/function/wrapper | Explicit import still possible | Verdict |
|---|---:|---:|---|---|---:|---|

Include helper functions sourced from clients, such as
`pull_nyfed_data`, even if the containing client module is not injected.
Identify duplicate names, compatibility aliases, and names shadowed later in
namespace construction.

### 2.2 Namespace closure

Search for every other code-execution namespace builder, including report
workers, observation workers, scheduled processes, email analysis, persisted
scripts, and developer/eval harnesses. Do not repeat the already-inspected
dashboard runner namespace.

Return:

| Namespace builder | Process/interface | Client names | Pull/save/search names | Same as chat sandbox | Evidence |
|---|---|---|---|---|---|

Answer:

1. Is the ordinary chat/MCP sandbox the only general data-client namespace?
2. Do report or observation workers receive the same client modules and data
   helpers, a subset, or an independently constructed namespace?
3. Does any active source still require an `ai_development.*` import?
4. Is client injection explicit, generated from package exports, or discovered
   from the filesystem?

End with:

```text
CLIENT_INJECTION_MAP_COMPLETE: YES/NO
DATA_NAMESPACE_BUILDERS_COMPLETE: YES/NO
```

## 3. Client-to-L2 registry mappings and bundles

### 3.1 Registry rows

Search the live registry and any split registry/config files for every client
name, injected alias, source name, and likely guide key. For each mapping,
paste the complete bounded registry row, preserving all fields but redacting
user-specific values if any.

Return:

| Client | Injected name | Registry key | Tier | Pillar/category | Content type | Source path | Trigger description present | Bundle/specialization | Verdict |
|---|---|---|---:|---|---|---|---:|---|---|

For clients with no row, report the exact searches and use `NOT_PRESENT`.
Do not infer a mapping merely because a similarly named markdown file exists.

### 3.2 L2 file and loader validation

For every registry source path above:

- verify the file exists at the resolved current path;
- report bytes and lines;
- identify the loader branch used (`static`, `runtime`, `cached`,
  `composite`, or another current type);
- verify whether the key is callable through `include_modules`;
- identify any bundle expansion and deduplication behavior.

Do not paste guide bodies. Return:

| Registry key | Resolved file/path | Exists | Loader branch | Bundle members | Auto-load trigger | Orphan/drift condition | Verdict |
|---|---|---:|---|---|---|---|---|

### 3.3 Reverse coverage

Enumerate client-related L2 guides with no live client mapping and live
clients with no L2 guide. Distinguish:

```text
client + injected + mapped
client + injected + unmapped
client + not injected + mapped
client + not injected + unmapped
guide + no current client
```

Explicitly verify the historical shared/bundled claims:

- Treasury Fiscal Data and TreasuryDirect share one guide;
- the Treasury guide bundles an IR instrument guide;
- prediction-markets guidance bundles chart/snapshot context;
- other historical client guides were standalone.

Use source, not the local list, to determine the current keys and members.
End with:

```text
CLIENT_L2_BIJECTION_COMPLETE: YES/NO
BUNDLE_GRAPH_COMPLETE: YES/NO
```

## 4. Live GS proxy and outbound transport APIs

### 4.1 Module location and public surface

Locate every active GS proxy/transport module and compatibility shim. Paste
only:

- the imports and constants required to define proxy/ticket behavior;
- the complete signatures and docstrings of public transport functions;
- the complete `KRB5CCNAME` bootstrap block, if present;
- the complete public adapter class declaration and method signatures;
- any active central host-policy registry or normalized response type.

Return:

| Symbol | Current path/lines | Signature/type | Called by | Import-time side effect | Verdict |
|---|---|---|---|---|---|

At minimum, search for:

```text
get_spnego_token
KerberosProxyAuthAdapter
session_and_auth
manual_https_request
request_json
HOST_TRANSPORT_POLICY
TransportResponse
KRB5CCNAME
PROXY_HOST
PROXY_PORT
```

Do not generate a ticket or call any symbol.

### 4.2 KRB5 and SPNEGO behavior

Using current executable source, answer with citations:

1. When and how is `KRB5CCNAME` discovered, set, validated, refreshed, or left
   untouched?
2. Is ticket-cache bootstrap import-time, call-time, launcher-time, or absent?
3. What service principal and GSSAPI flags are used?
4. Is SPNEGO one-shot or multi-leg, and which code handles 407 responses?
5. Which exceptions are caught versus propagated?
6. Does the sandbox/job/report environment alter or simply inherit
   Kerberos-related environment variables?
7. Are auth headers attached to CONNECT only, to target requests, or both?

Paste only the exact bounded branches that answer those questions.

### 4.3 Standard, manual, and direct contracts

Return exact source-backed contracts for each active mode:

| Mode | Entry point | Inputs | Return shape | Timeout behavior | TLS/CA/SNI | Header behavior | Connection lifecycle | Verdict |
|---|---|---|---|---|---|---|---|---|

For manual CONNECT, verify from source:

- supported methods and body encoding;
- query-string encoding;
- CONNECT status parsing;
- response status representation;
- JSON/text fallback;
- chunked transfer decoding;
- socket/SSL cleanup;
- certifi and SNI behavior.

For standard proxied requests, verify adapter mounting, proxy configuration,
auth object creation, session caching, and target/proxy header behavior.

For direct requests, identify whether direct access is an intentional policy,
an import fallback, a local-only branch, or merely historical.

### 4.4 Forward proposals are not current behavior

Search active executable/config source for:

```text
HOST_TRANSPORT_POLICY
request_json
TransportResponse
ThreadSafeSessionPool
TIMEOUT_CONFIGS
RateLimiter
TRANSPORT_REQUESTS_PROXY
TRANSPORT_MANUAL_CONNECT
TRANSPORT_DIRECT
```

Return:

| Proposed/possible symbol | Active executable definition | Active caller | Documentation-only occurrence | Verdict |
|---|---|---|---|---|

Use `NOT_PRESENT` when exhaustive active-source search finds no live
definition/caller. Do not recommend implementing any proposal.

## 5. Per-client and per-host transport matrix

Inspect every client request helper and every hostname/base URL constant.
Return one row per distinct client-host pair:

| Client | Host/base URL | Request helper path/lines | Transport entry point | Standard/manual/direct/conditional | Proxy flag or selection mechanism | Direct fallback | Auth/API-key headers | Timeout/retry/rate limit | Verdict |
|---|---|---|---|---|---|---|---|---|---|

Requirements:

- Follow helper aliases and lazy imports to the actual wire path.
- Distinguish multiple hosts within one client, especially prediction-market
  or artifact/scraping clients.
- Distinguish standard GS proxy, manual CONNECT, direct `requests`, and
  conditional/import-availability behavior.
- Report whether a module-level session/auth object is cached and whether the
  cache is process-global, thread-local, or per call.
- Redact API-key values while preserving header names and configuration
  sources.
- Do not label an unproxied branch a fallback unless executable control flow
  can reach it.
- If no outbound host is statically recoverable, report the URL construction
  source and use `UNKNOWN`.

Then answer:

1. Does every external client use the GS proxy?
2. Is transport policy centralized or encoded per client/host?
3. Which clients import both standard and manual helpers?
4. Which clients bypass the GS proxy entirely in current production source?
5. Which transport claims in historical docs are contradicted by current
   source?

End with:

```text
CLIENT_HOST_TRANSPORT_MATRIX_COMPLETE: YES/NO
```

## 6. Unified data-access routing graph

### 6.1 Active mechanism inventory

Build a current, source-backed graph of every mechanism by which PRISM obtains
or discovers data. At minimum distinguish:

```text
curated pull helpers
external API clients
save_artifact / persistence helpers
S3 indexed search and direct S3 reads
cached context
runtime/push world-state modules
scheduled ingestion producers
GS/internal Python libraries or backends
```

Return:

| Mechanism | Public/injected entry point | Implementation path | Source/backend | Returns | Persists automatically | Freshness model | Discovery step | L2 guidance | Primary consumer |
|---|---|---|---|---|---:|---|---|---|---|

This table must include every current `pull_*_data` helper exposed to the
ordinary sandbox, not only Haver/Market/PlotTool. It must also include
`save_artifact`, `grep_s3`, `glob_s3`, `get_s3_files`, and any current
cached-context/world-state access surface.

### 6.2 Pull-helper contracts

For each exposed `pull_*_data` helper:

- return its exact signature;
- identify its implementation and backend class/client;
- identify wrapper/partial arguments pre-bound by injection;
- state its return type/shape from source;
- state automatic files/sidecars/attrs/stdout effects;
- identify `name`, `output_path`, session-path, and S3 semantics where
  applicable;
- identify its current L2 module(s).

Do not paste implementations. Return one compact row per helper and paste only
the namespace wrapper construction needed to prove pre-bound arguments.

Explicitly resolve:

- whether `pull_market_data` still returns an EOD/intraday tuple;
- whether `pull_plottool_data` and GS market data share a TSDB backend;
- where `pull_nyfed_data` now comes from;
- whether FRED, Pure/Lipper, LSEG news, stacked data, or newer helpers follow
  the same persistence contract;
- whether `SESSION_PATH` is injected, script-defined, or wrapper-bound in the
  current checkout.

### 6.3 `save_artifact` and persistence boundary

Return the exact current signature, type dispatch, extension rules, path
construction, overwrite behavior, return value, and namespace wrapper for
`save_artifact`.

Answer:

1. Which input types are accepted?
2. Which types become CSV versus JSON or another format?
3. Does `output_path` replace or append to `source_dir`?
4. Is persistence idempotent for repeated names?
5. Which data clients/helpers call it internally, and which leave persistence
   to LLM-authored code?
6. Is it the intended persistence bridge for every non-auto-saving client, or
   are there newer dedicated persistence APIs?

### 6.4 S3 search, cached context, and push state

For S3 discovery/search, return exact signatures and index/config ownership
for `grep_s3`, `glob_s3`, `get_s3_files`, and any successor names. Identify
which active job builds each search index and its cadence.

For cached context, identify:

- registry content type and loader branch;
- physical/S3 cache path construction;
- producer job or refresh owner;
- stale/missing behavior;
- provenance metadata retained in the cached artifact.

For push/runtime world state, do not collapse it into S3 search. Identify the
producer, storage/cache, loader, and freshness gate separately.

### 6.5 Decision boundary

Return a source-backed decision table:

| User need/data shape | Discovery mechanism | Retrieval mechanism | Persistence mechanism | World-state shortcut | Required L2 context | Disambiguation/source-priority rule |
|---|---|---|---|---|---|---|

Cover macro time series, market EOD/intraday, PlotTool expressions, GS
proprietary analytics, single-stock fundamentals, funds/flows, Treasury
auctions/fiscal data, NY Fed, BIS, FDIC, SEC filings/XBRL, identifiers,
prediction markets, news push/pull/archive, Fed/GS research text, earnings,
and any current sources absent from that list.

Use current L1 routing docstrings, registry, and executable paths as evidence.
Do not preserve a local row that no longer exists in live source.

## 7. Discovery-before-query and source disambiguation

Locate current L1/L2 instructions and executable discovery helpers governing
source choice. Paste only the bounded decision/routing blocks from:

- the current data-routing L1 tool/docstring;
- relevant registry descriptions;
- discovery helper signatures;
- source-specific L2 instructions where they impose a mandatory pre-query
  step.

Return:

| Source/domain | Mandatory discovery first | Discovery function | Query function/client | Source selection rule | Alternative/fallback allowed | Evidence |
|---|---:|---|---|---|---:|---|

Explicitly verify:

1. Is `explore_haver()` mandatory before every Haver pull, and is it a
   separate execution?
2. What discovery is required before TSDB coordinate/PlotTool queries?
3. Which clients expose endpoint/schema/universe discovery before a data
   query?
4. Which sources require universe-first selection rather than guessing an
   identifier, series, endpoint, security type, or field?
5. What current rules disambiguate Haver versus market data versus PlotTool,
   push news versus pull news versus archive search, TreasuryDirect versus
   Fiscal Data, and cached world state versus a fresh API call?
6. What source-priority or fallback rules are executable policy, and which are
   LLM guidance only?
7. Does live guidance still state that all retrieval goes through code
   execution, and how does that coexist with world-state context and S3 tools?

Do not invoke discovery/query functions; inspect source and guidance only.

## 8. Current world-state runtime and loader graph

### 8.1 Inventory and registration

Enumerate every active module classified as world state by the live registry,
assembler, loader, L1 routing docstring, or specialization bundle. Do not
assume the historical count is seven.

Return:

| Registry/module ID | Pillar/category | Content type | Source path | Loader/generator | `world_state` key(s) | Specialization auto-include | Bundle | Bytes/lines | Verdict |
|---|---|---|---|---|---|---|---|---:|---|

Include world-state-adjacent observation summaries only when source shows
they are auto-included or routed with this cluster; label their distinct
ownership.

Paste the complete bounded assembler mapping from `world_state` keys/aliases
to module IDs and the relevant specialization auto-include rows. Do not paste
generated module bodies.

### 8.2 Per-module producer, storage, cadence, and provenance

For every world-state module, trace the full path:

```text
upstream source
  -> ingestion/refresh producer
  -> stored/cache artifact
  -> runtime generator/loader
  -> get_context key/alias/specialization
  -> rendered provenance/freshness warning
```

Return:

| Module | Upstream source(s) | Producer path | Live cadence/trigger | Storage/cache path | Generator/loader | Freshness gate | Stale/missing behavior | Provenance shown to LLM | Verdict |
|---|---|---|---|---|---|---|---|---|---|

If a module performs a live API call rather than consuming a scheduled
artifact, identify the exact call path but do not invoke it. If cadence exists
only in prose and not deployment wiring, use `UNKNOWN`.

### 8.3 Alias and bundle semantics

Verify every accepted `world_state` key, including historical aliases and
newer keys. Return:

| Input key | Canonical module | Alias/direct/deprecated | Filter parameters consumed | Bundle expansion | Unknown-key behavior | Verdict |
|---|---|---|---|---|---|---|

Explicitly test the local assumptions that:

- `markets` aliases `market_dashboard`;
- `news` aliases `news_snapshot`;
- `prediction_markets` maps to `prediction_markets_snapshot`;
- `timeline` maps to `world_timeline`;
- `earnings` maps to `earnings_calendar`;
- `auction_schedule` bundles Treasury guidance;
- prediction-market snapshot and analytical skill are separate modules;
- an end-user specialization auto-includes some world state even when flags
  are omitted.

Use source inspection only. Do not call `get_context`.

### 8.4 Runtime module contracts

For each runtime generator, return:

- exact `generate(...)` signature;
- configuration/environment inputs;
- files/S3 keys read;
- network/data helper calls reachable during generation;
- output type and wrapper/markup;
- explicit freshness/provenance fields;
- exception and stale-cache behavior.

Paste only signatures and the bounded source branches responsible for
read/load/freshness/fallback decisions, not full generated content.

End with:

```text
WORLD_STATE_INVENTORY_COMPLETE: YES/NO
WORLD_STATE_PRODUCER_GRAPH_COMPLETE: YES/NO
WORLD_STATE_ALIAS_MAP_COMPLETE: YES/NO
```

## 9. Scheduled ingestion producers

Enumerate active scheduled jobs that produce data consumed by:

- pull helpers or their caches;
- S3 search indexes;
- runtime/cached context;
- world-state modules;
- client-backed snapshots;
- Observatory/report inputs only where they are data producers shared with
  the surfaces above.

Do not repeat the dashboard refresh job.

Return:

| Job/producer path | Scheduler registration path/lines | Command/module | Cadence | One-shot/daemon | Inputs/source | Output path/artifact | Consumer(s) | Retry/lock/failure behavior | Verdict |
|---|---|---|---|---|---|---|---|---|---|

Paste only each scheduler/entrypoint registration and the producer's output
path construction. Do not paste whole job files.

Explicitly answer:

1. Is `entrypoint.py` still the active owner for all minutely/hourly/daily
   schedules?
2. Are there services, cron manifests, containers, or external schedulers
   outside `entrypoint.py`?
3. Which folder names disagree with actual cadence?
4. Which producers are invoked on demand as well as scheduled?
5. Which jobs in the historical minutely/hourly/daily lists moved, were
   renamed, or are no longer deployed?
6. How are freshness timestamps and provenance carried from producer to
   world-state/context consumer?

End with:

```text
INGESTION_DEPLOYMENT_GRAPH_COMPLETE: YES/NO
```

## 10. Current package and path graph

Return one canonical path graph for the data ecosystem:

```text
prism-main/
  <parent-owned client/transport/jobs/core paths>
  prism-core/
    <submodule-owned MCP/context/data-helper paths>
```

Annotate each node with its import package (`core.*`, `prism_mcp.*`,
`context.*`, or another current package), owner checkout, and active consumer.

Then return:

| Historical path/claim | Current target | Compatibility alias exists | Executed/read at runtime | Verdict | Evidence |
|---|---|---:|---:|---|---|

Include at minimum:

```text
ai_development/mcp/clients/
ai_development/mcp/gs_app_proxy_negotiate.py
ai_development/mcp/tools/script_exec_tools.py
ai_development/mcp/utils/data_functions.py
ai_development/mcp/utils/gs_data_sources.py
ai_development/context/registry.py
ai_development/context/modules/runtime/
context/modules/static/data_guides/
context/modules/static/instruments/
context/modules/static/tools/
jobs/minutely/
jobs/hourly/
jobs/daily/
```

Search executable imports and deployment config for active
`ai_development.*` references. Distinguish runtime compatibility aliases from
archived docs/comments.

## 11. Data-ecosystem contradiction ledger

Resolve every local historical assumption below from current source. Use only
the fixed verdict vocabulary.

| ID | Local historical assumption to test | Verdict | Current production fact | Exact evidence |
|---|---|---|---|---|
| D01 | PRISM still has one `ai_development/` tree containing clients, MCP utilities, context, and jobs. | | | |
| D02 | External clients live at `mcp/clients/` in the same package tree as `script_exec_tools.py`. | | | |
| D03 | There are exactly 17 external API client modules. | | | |
| D04 | `congress.py` remains the only client without a `_client.py` suffix. | | | |
| D05 | The client package explicitly exports 13 modules; OFAC is commented and OFR/USITC/Wikipedia are absent. | | | |
| D06 | The ordinary sandbox injects exactly nine client modules plus the `pull_nyfed_data` function. | | | |
| D07 | Seven historical clients are absent from sandbox injection. | | | |
| D08 | New York Fed is exposed only as `pull_nyfed_data`, not as an injected module. | | | |
| D09 | Ten registry keys map eleven clients, with six historical clients unmapped. | | | |
| D10 | Treasury Fiscal Data and TreasuryDirect share one L2 guide and bundle IR guidance. | | | |
| D11 | Prediction-market guidance bundles chart context and a prediction-market snapshot. | | | |
| D12 | Every client depends on the GS proxy transport module. | | | |
| D13 | Transport selection remains per client/host, with no active central policy registry. | | | |
| D14 | The live proxy API consists of `get_spnego_token`, `KerberosProxyAuthAdapter`, `session_and_auth`, and `manual_https_request`. | | | |
| D15 | `KRB5CCNAME` discovery mutates the process environment at module import time and does not validate expiry. | | | |
| D16 | Manual CONNECT returns parsed data plus a string status line and uses a clean target request after proxy auth. | | | |
| D17 | Current data access is adequately described by only pull helpers, `save_artifact`, and external clients. | | | |
| D18 | `pull_market_data` returns `(eod_df, intraday_df)` and appends EOD/intraday filename suffixes. | | | |
| D19 | Haver exploration is the only universally mandatory discovery-before-query rule. | | | |
| D20 | The data-routing ontology still has the historical source rows and disambiguation priorities. | | | |
| D21 | World state contains exactly seven runtime modules with the historical aliases and cadences. | | | |
| D22 | `prediction_markets_snapshot` is auto-included for end users even without an explicit flag. | | | |
| D23 | `auction_schedule` performs a live API call and bundles Treasury guidance. | | | |
| D24 | Minutely/hourly/daily ingestion is activated by one root `entrypoint.py`. | | | |
| D25 | `HOST_TRANSPORT_POLICY`, `request_json`, and `TransportResponse` remain proposals rather than live APIs. | | | |
| D26 | Historical client counts, package membership, registry mappings, and transport tables are stale only because paths moved, not because membership changed. | | | |

For each `CONTRADICTS` or `UNKNOWN` row, name the exact local target document
that must remain untrusted:

```text
prism/api-clients.md
prism/gs-proxy.md
prism/data-functions.md
prism/world-state.md
prism/architecture.md
prism/codebase-tree.md
prism/README.md
```

Do not propose fixes in this section.

## 12. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
CHECKOUT_IDENTITY_COMPLETE:
CLIENT_PHYSICAL_INVENTORY_COMPLETE:
CLIENT_PACKAGE_EXPORTS_COMPLETE:
CLIENT_CONSUMER_SEARCH_COMPLETE:
CLIENT_INJECTION_MAP_COMPLETE:
DATA_NAMESPACE_BUILDERS_COMPLETE:
CLIENT_L2_BIJECTION_COMPLETE:
BUNDLE_GRAPH_COMPLETE:
LIVE_PROXY_API_COMPLETE:
KRB5_SPNEGO_BEHAVIOR_COMPLETE:
TRANSPORT_CONTRACTS_COMPLETE:
CLIENT_HOST_TRANSPORT_MATRIX_COMPLETE:
DATA_ACCESS_MECHANISM_GRAPH_COMPLETE:
PULL_HELPER_CONTRACTS_COMPLETE:
SAVE_ARTIFACT_CONTRACT_COMPLETE:
S3_CACHE_PUSH_BOUNDARIES_COMPLETE:
SOURCE_ROUTING_ONTOLOGY_COMPLETE:
DISCOVERY_BEFORE_QUERY_COMPLETE:
WORLD_STATE_INVENTORY_COMPLETE:
WORLD_STATE_PRODUCER_GRAPH_COMPLETE:
WORLD_STATE_ALIAS_MAP_COMPLETE:
INGESTION_DEPLOYMENT_GRAPH_COMPLETE:
CURRENT_PATH_GRAPH_COMPLETE:
FORWARD_PROPOSALS_SEPARATED:
CONTRADICTION_LEDGER_COMPLETE:
DATA_ECOSYSTEM_REFRESH_COMPLETE:
```

`DATA_ECOSYSTEM_REFRESH_COMPLETE` may be `YES` only when every preceding item
is `YES`. If it is `NO`, list only the unresolved section/subsection numbers
and the missing source, search coverage, or permission.

If any requested item cannot be answered, end with:

## Could not resolve

List each unresolved item as:

```text
- Section/subsection:
  Searched roots:
  Searched patterns:
  Blocker:
```

Do not include recommendations, speculative replacements, or a `Frictions`
section.
