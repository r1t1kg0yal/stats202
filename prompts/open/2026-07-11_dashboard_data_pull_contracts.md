---
class: context-extraction
topic: dashboard-data-pull-contracts
status: FOLDED
created: 2026-07-11
reply_received: 2026-07-11
reply_source: cursor-chat screenshots (4 images, captured 2026-07-11 23:09 ET)
folded_on: 2026-07-11
sequence: 1/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
reply_folded_into:
  - prism/data-functions.md
  - prism/code-sandbox.md
  - prism/dashboard-refresh.md
  - prism/architecture.md
  - projects/echarts/echarts-payload/dashboards.md
  - projects/echarts/echarts-payload/dashboards_hub.md
  - projects/echarts/echarts-payload/dashboards/build.md
  - projects/echarts/echarts-payload/dashboards/pipelines.md
---

# Context-extraction prompt — dashboard data-pull contracts

**Why this exists (staging-only note; do not paste this section into
PRISM):**

The broad dashboard architecture validation established the installed
package, runner, context, portal, registry, and process topology. This
follow-up deliberately does not repeat that global inventory, import map,
route audit, asset audit, or portal audit. It closes the narrower contract
that remains load-bearing for dashboard authorship: every live data helper
and client path, the wrappers and namespaces through which each is called,
what each call returns and persists, and whether initial build and clean
refresh execute the same persisted scripts with the same behavior.

Fold the reply only into the paths listed in `reply_folded_into`, after
review. For the ECharts context payload, change only the four listed owners
and only where the reply proves a PRISM authoring decision; engine-internal
detail belongs in the `prism/` reference files.

---

## Paste the following into PRISM

# Dashboard data-pull contracts (read-only)

Inspect the current live implementation. This is a source-first,
read-only context-extraction request. Do not answer from memory, prior
conversation, staging prose, generated API documentation, or a previously
captured reply. Treat current executable source as primary; use active
runtime context only to determine what PRISM is taught. Where sources
disagree, preserve the disagreement.

The prior dashboard architecture validation already covered the global
installed inventory, package import topology, public export inventory,
Django/portal routes, static assets, registry/status schemas, and broad
inbound/outbound graphs. Do not reproduce those sections. Read only the
bounded source needed to resolve the data-pull contract below.

Use `list_ai_repo`, repository search, direct source reads, and narrowly
scoped read-only introspection through `execute_analysis_script` as needed.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- execute a live data pull or client network request;
- invoke `run_pull`, `build_dashboard`, `refresh_dashboard`,
  `compile_dashboard`, `refresh_runner.py`, or
  `jobs/hourly/refresh_dashboards.py`;
- execute a persisted dashboard script, `PULLS` entry, or `TRANSFORMS`;
- create or alter a session, dashboard, registry, manifest, status file,
  completion marker, log object, cache, local file, or S3 object;
- issue POST/PUT/PATCH/DELETE requests;
- install, upgrade, reload, or monkey-patch packages;
- enumerate or quote user data values, vendor identifiers from user scripts,
  credentials, or proprietary payloads.

Permitted introspection is limited to imports, definitions, signatures,
wrapper objects, registry/config entries, AST-derived symbol names, and
existing metadata schemas. If importing a module has a write, network,
registration, or job-launch side effect, do not import it; inspect its
source statically and mark runtime identity `UNKNOWN`.

## Reply protocol

1. Mirror every numbered section and subsection below.
2. Cite an exact current repository path and line range for every
   source-backed claim. Use the checked-out path, not a retired
   `ai_development/...` alias unless that alias is itself found live.
3. For every requested source block, paste a complete bounded block
   verbatim in a fenced code block. Never use `...`, reconstructed code,
   or prose placeholders inside a requested block.
4. Never paste an entire large file. A bounded block means one complete
   definition, one import/injection block, one registry entry, or one
   contiguous call-site block. If a definition is over 150 lines, return
   its signature plus only the complete relevant branches, each with exact
   line ranges.
5. For each search, state all searched roots, exact literal/regex/glob
   patterns, exclusions, and whether the search completed. Return each
   relevant match as `path:line:source`.
6. For runtime signatures, report both `inspect.signature(exposed_object)`
   and `inspect.signature(inspect.unwrap(exposed_object))` when safe.
   Identify `functools.partial` keywords and wrapper layers separately.
7. Redact secrets, tokens, cookies, credentials, personal data, user values,
   proprietary series identifiers, and live dataset contents. Preserve key
   names, types, import names, callable names, path grammar, control flow,
   and schemas. Use `<REDACTED>` only for values, never for field names.
8. Use only these verdicts where a verdict is requested:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. If evidence conflicts, show both sources with paths and line ranges.
   Do not silently select one or resolve executable behavior from prose.

## 0. Checkout identity and inspection time

Return only:

| Item | Value | How obtained |
|---|---|---|
| `prism-main` HEAD SHA | | |
| checked-out `prism-core` SHA | | |
| `prism-core` SHA recorded by `prism-main` | | |
| checked-out/recorded match | `CONFIRMED` / `CONTRADICTS` / `UNKNOWN` | |
| `prism-main` absolute root | | |
| `prism-core` absolute root | | |
| inspection timestamp in UTC | | |

Do not repeat package inventories or parity tables. If Git metadata is
unavailable, use `UNKNOWN`; do not infer identity from paths or deployment
labels.

## 1. Exhaustive live data-surface discovery

### 1.1 Search roots and patterns

Search all active executable and LLM-consumed locations under both checkout
roots. At minimum include:

```text
prism-main/core/
prism-main/jobs/
prism-main/web/
prism-main/entrypoint.py
prism-main/prism-core/prism_mcp/
prism-main/prism-core/dashboards/
prism-main/prism-core/context/
```

Search definitions, imports, exports, namespace keys, registry entries,
aliases, wrappers, partials, and calls with these patterns:

```text
\bdef\s+pull_[A-Za-z0-9_]*data\b
\b(?:async\s+def|def)\s+pull_[A-Za-z0-9_]+\b
\bpull_[A-Za-z0-9_]*data\b
\bpull_haver_data\b
\bpull_market_data\b
\bpull_plottool_data\b
\bpull_fred_data\b
\bpull_nyfed_data\b
\bsave_artifact\b
\bPULLS\b
\bTRANSFORMS\b
\brun_pull\b
\b_build_exec_namespace\b
\b_exec_dashboard_script\b
\bfunctools\.partial\b
\bpartial\b
["'][A-Za-z0-9_]+_client["']
from\s+(?:core|prism_mcp)\.[^\n]*clients
```

Also search active dashboard context for the exact same callable names:

```text
prism-main/prism-core/context/modules/static/tools/dashboards.md
prism-main/prism-core/context/modules/static/tools/dashboards_hub.md
prism-main/prism-core/context/modules/static/tools/dashboards/*.md
prism-main/prism-core/context/modules/static/data_guides/*.md
prism-main/prism-core/context/modules/static/instruments/*.md
prism-main/prism-core/context/modules/static/tools/*.md
```

Exclude `.git/`, caches, bytecode, generated documentation, archived trees,
test fixtures, logs, session outputs, vendored packages, and staging-only
test prompts. Report any requested root that does not exist.

### 1.2 Data-surface inventory

Return one row for every live `pull_*` helper found, whether or not its name
ends in `_data`, plus `save_artifact` and every client module exposed to
dashboard scripts:

| Exposed name | Definition path:lines | Backend/client path | Sandbox exposure | In-process dashboard namespace | Clean runner discovery namespace | Persisted-script import path | Dashboard usage evidence | Current authoring-context owner |
|---|---|---|---|---|---|---|---|---|

Include at least:

```text
pull_haver_data
pull_market_data
pull_plottool_data
pull_fred_data
pull_nyfed_data
save_artifact
```

The inventory must also include every additional live `pull_*` helper
found, including helpers such as Pure/Lipper, stacked data, news, or other
sources if they are callable from the sandbox or a persisted dashboard
script. Do not assume the current curated list is complete.

Classify `Dashboard usage evidence` as one or more of:

```text
engine namespace
authoring context
active executable caller
persisted dashboard AST
none found
```

### 1.3 Persisted-dashboard symbol census

Without returning script bodies or argument values, perform a read-only
AST census over existing canonical persisted pull scripts discoverable at:

```text
users/*/dashboards/*/scripts/pull_data.py
```

Return only aggregate counts and redacted symbol-level rows:

| Imported module/symbol | Called attribute/symbol | Number of scripts | Number of owners | Parse failures |
|---|---|---:|---:|---:|

Do not return kerberos IDs, dashboard IDs, literal arguments, series codes,
URLs, or source data. If no safe metadata-only enumeration mechanism
exists, mark this subsection `UNKNOWN` rather than reading user values.

## 2. Exact helper, backend, and wrapper contracts

### 2.1 Contract packet for every inventory row

For each helper in section 1.2, return a compact packet containing:

1. exact definition path and line range;
2. exact import/export path;
3. source declaration signature;
4. safe runtime exposed signature and unwrapped signature;
5. wrapper/partial/decorator chain in call order;
6. pre-bound or overwritten arguments and whether callers may override;
7. required caller-supplied arguments and defaults;
8. backend class/function/client invoked, with its exact call site;
9. exact success return type and shape;
10. empty/no-data return behavior;
11. persistence side effects and written key grammar;
12. metadata, attrs, fingerprint, stdout, or provenance side effects;
13. exception normalization, retries, timeout, and cancellation behavior.

Paste only:

- the complete definition header and docstring;
- the complete wrapper/partial construction block;
- the complete backend-dispatch branch;
- the complete output-path/name/write/return branches.

Do not paste unrelated normalization tables, vendor catalogs, or entire
large helper implementations.

### 2.2 Required deep checks

For `pull_haver_data`, `pull_market_data`, `pull_plottool_data`,
`pull_fred_data`, `pull_nyfed_data`, and `save_artifact`, explicitly
resolve:

- whether `session_path` and `s3_manager` are accepted by the source
  definition, required internally, pre-bound in each namespace, removed
  from the public signature, or caller-overridable;
- whether `output_path` is a directory prefix or a file path;
- whether a trailing slash is normalized, rejected, or preserved;
- whether `name` is required, defaulted, randomized, sanitized, or allowed
  to contain a suffix/extension/path separator;
- exact filename and metadata-sidecar suffix rules for every mode;
- overwrite/idempotency semantics on repeated name/path;
- return value versus persisted value, including DataFrame index/columns,
  tuple members, `df.attrs`, and returned S3 path;
- no-data, partial-data, malformed-code, backend-timeout, and S3-write
  failure behavior;
- timestamp fields in returned data, sidecars, fingerprints, status, or
  attrs, and which clock/timezone/source produces each;
- whether the helper prints a fingerprint and whether refresh captures it.

For `pull_market_data`, distinguish `eod`, `iday`, `intraday`, and `both`
exactly as implemented; do not normalize tokens in prose. For
`pull_nyfed_data`, resolve whether it auto-persists or requires
`save_artifact`, and whether the exposed object is a direct function,
wrapper, client attribute, or alias.

### 2.3 Backend classes

Trace each curated helper through every backend used in its live path,
including data-source factories and EOD/intraday branches. Return:

| Helper | Backend class/function | Constructor/factory signature | Called method signature | Return before wrapper normalization | Cache/retry/timeout behavior |
|---|---|---|---|---|---|

Paste only complete constructor/factory and called-method headers plus the
bounded dispatch/caching/timeout branches. Do not inventory unrelated
backend methods.

## 3. Dashboard-relevant client modules

### 3.1 Exposure and importability

For every `*_client` module exposed in the initial sandbox, imported by
active dashboard source/context, or found in the redacted AST census,
return:

| Sandbox/persisted name | Exact module path | Exposure mechanism | Available initially | Available in-process | Available in clean refresh discovery | Required persisted import | Dashboard-used methods |
|---|---|---|---|---|---|---|---|

Do not claim that all sandbox clients are dashboard-used. Separate
technical availability from evidenced use.

### 3.2 Dashboard-used method contracts

For each evidenced dashboard-used method, return its exact signature,
return type/shape, network timeout/retry policy, error behavior, and whether
it persists automatically or must flow through `save_artifact`. Paste only
the complete method header/docstring and bounded return/error branches.

For client methods not evidenced in dashboard code/context, list the module
only; do not reproduce its full API.

### 3.3 Client-to-artifact path

Trace the exact supported path:

```text
client method
  → returned object
  → save_artifact or explicit S3 write
  → flat data/ object
  → build_dashboard loader
```

State which return shapes `save_artifact` accepts, extension selection,
encoding, index handling, metadata/provenance preservation or loss, and
what happens for empty lists, nested dictionaries, generators, scalars,
and objects with `to_frame()`.

## 4. Three execution namespaces

### 4.1 Initial `execute_analysis_script` namespace

From the current sandbox implementation, paste the complete bounded blocks
that:

- import data helpers and client modules;
- construct timed wrappers, partials, aliases, or validators;
- place data helpers and clients into the execution namespace;
- set the sandbox timeout and execute the script.

Return exact exposed and unwrapped signatures. Distinguish the raw S3
singleton from any sandbox wrapper.

### 4.2 In-process persisted-script path

From the dashboard engine, paste:

- the complete `_exec_dashboard_script` definition;
- the complete `run_pull` definition;
- any immediately called loader needed to explain script retrieval,
  compile/exec behavior, namespace reuse, and named `PULLS` selection.

Resolve whether executing enough of `pull_data.py` to obtain `PULLS`
already runs module-level work, whether the namespace persists between
pulls, and whether `run_pull` invokes only the selected zero-argument
callable.

### 4.3 Clean refresh subprocess discovery

From the live runner, paste:

- the complete `_build_exec_namespace` definition;
- the complete bounded block that loads/executes `pull_data.py` to discover
  `PULLS`;
- the loop/call site that delegates each name to `run_pull`;
- timeout, error capture, phase labeling, and continuation/abort behavior.

Do not repeat the runner CLI, scheduler, status schema, or portal launch
path already covered by the architecture validation.

### 4.4 Namespace parity matrix

Return:

| Name | Initial sandbox | In-process persisted script | Clean runner discovery | Wrapper/partial in each | Explicit persisted import required | Behavioral mismatch |
|---|---|---|---|---|---|---|

Include every inventory row from sections 1.2 and 3.1, plus:

```text
s3_manager
pd
np
io
json
datetime
timezone
SESSION_PATH
__builtins__
```

For `Behavioral mismatch`, use only `CONFIRMED`, `CONTRADICTS`,
`UNKNOWN`, or `NOT_PRESENT`, followed by one sentence of evidence.

Resolve whether explicit imports are merely style, are required for clean
refresh, or are required in every path. Identify any script that can pass
initial authoring or `run_pull` but fail during runner discovery solely
because the namespaces differ.

## 5. End-to-end persisted data flow

Trace one abstract pull through live source without invoking it:

```text
persisted scripts/pull_data.py
  → module-level PULLS discovery
  → run_pull(folder, pull_name)
  → helper/backend/client call
  → flat data/ CSV or JSON
  → metadata sidecar / attrs / fingerprint / provenance
  → build_dashboard CSV/JSON discovery and parsing
  → scripts/build.py TRANSFORMS
  → manifest_template dataset slots
  → populate/compile
  → manifest.json + dashboard.html
  → refresh result/status/registry timestamps
```

For every arrow, return:

| Stage | Owning function | Exact input contract | Exact output contract | Persisted path/schema | Failure boundary |
|---|---|---|---|---|---|

Paste the complete bounded source blocks that:

- enumerate and validate `PULLS`;
- build the flat-data path;
- discover data files and map stems to dataset keys;
- parse CSV and JSON, including index/date handling;
- load, validate, and execute ordered `TRANSFORMS`;
- require each transform's return shape;
- attach datasets to template slots;
- compile and persist final outputs;
- stamp generated data-domain, pull, build, and refresh timestamps;
- preserve or discard helper metadata sidecars and `df.attrs`.

Explicitly answer:

1. Are metadata sidecars loaded into the build or ignored?
2. Do `df.attrs` survive CSV persistence/reload?
3. Where does `field_provenance` originate, and is it derived from helper
   metadata or manually authored?
4. How are `_metadata`, `_eod`, `_intraday`, `.csv`, and `.json` stems
   classified?
5. Can a sidecar become an unintended manifest dataset?
6. Are JSON artifacts loadable as datasets, and with what normalization?
7. What exact collision behavior applies when two producers write the same
   stem?
8. Which timestamps represent source-data freshness versus execution time?

## 6. Build, refresh, error, and timeout differences

Return a comparison matrix:

| Property | Initial sandbox authoring | Direct in-process `run_pull` | `build_dashboard` | `refresh_dashboard` | Clean `refresh_runner` subprocess | Scheduled launch |
|---|---|---|---|---|---|---|
| interpreter/process | | | | | | |
| namespace source | | | | | | |
| helper wrapping/pre-binding | | | | | | |
| persisted-script imports required | | | | | | |
| timeout owner/value | | | | | | |
| network/client timeout | | | | | | |
| per-pull failure isolation | | | | | | |
| stdout/fingerprint capture | | | | | | |
| output overwrite behavior | | | | | | |
| build after partial pull failure | | | | | | |
| timestamp/freshness stamping | | | | | | |
| metadata/provenance retained | | | | | | |

Do not repeat scheduler cadence, route behavior, or full registry/status
schemas. Focus only on differences capable of changing data output or
failure behavior.

Resolve:

- whether the initial sandbox's approximately 60-second limit applies to
  `run_pull`, refresh subprocesses, client HTTP calls, or none of them;
- whether any helper/backend has an independent timeout;
- whether the runner continues to later pulls after one failure;
- whether a failed pull can leave a prior CSV in place and still permit a
  build from stale data;
- whether refresh writes atomically or overwrites each artifact in place;
- whether current freshness UI can distinguish stale retained data from a
  newly successful pull;
- whether `name` plus stable `output_path` is sufficient for idempotency
  across every helper/client path.

## 7. Active authoring-context alignment

Inspect only the active dashboard router, kernel, `build.md`, and
`pipelines.md`, plus the active Tier-1 sandbox context and directly relevant
data/client guides. Do not audit unrelated dashboard spokes.

Return:

| Context path:lines | Contract taught | Executable fact | Verdict | Required owner if correction is proven |
|---|---|---|---|---|

Check at minimum:

- the complete pull-helper/client inventory;
- exact imports required in persisted scripts;
- `SESSION_PATH`, `output_path`, and `s3_manager` requirements;
- market-data mode and filename suffix tokens;
- `save_artifact` supported types and JSON/CSV behavior;
- metadata sidecars, fingerprints, and field provenance;
- flat data-folder discovery;
- namespace parity across initial, in-process, and clean refresh paths;
- timeout guidance;
- generated freshness timestamps;
- clean-refresh success criteria.

Do not propose adding engine internals to authoring context. A context
correction is warranted only when the fact changes what PRISM imports,
calls, names, persists, verifies, or tells the user.

## 8. Canonical contract summary

Produce four compact source-backed tables suitable for curation:

1. callable/import/signature/return contract;
2. persistence path/suffix/sidecar/idempotency contract;
3. namespace and pre-binding contract;
4. build-versus-refresh/error/timeout/freshness contract.

Each row must cite its defining executable source. Do not repeat source
blocks in this section.

## 9. Dashboard data-pull contradiction ledger

Resolve each assumption:

| ID | Assumption | Verdict | Current fact | Evidence |
|---|---|---|---|---|
| DPC01 | The live helper inventory is fully represented by the six named required helpers. | | | |
| DPC02 | Every dashboard-capable helper is available in all three execution namespaces. | | | |
| DPC03 | Persisted dashboard scripts must explicitly import every helper/client they call. | | | |
| DPC04 | `session_path` and `s3_manager` are pre-bound identically in all execution paths. | | | |
| DPC05 | `output_path` is always a directory prefix and all helpers preserve the same trailing-slash behavior. | | | |
| DPC06 | Stable `name` plus `output_path` makes every helper/client artifact idempotent. | | | |
| DPC07 | `pull_market_data` mode tokens and `_eod`/`_intraday` suffixes are documented exactly as implemented. | | | |
| DPC08 | All curated pull helpers return a DataFrame. | | | |
| DPC09 | `pull_nyfed_data` auto-persists dashboard-ready output. | | | |
| DPC10 | Client-returned data requires `save_artifact` or an explicit S3 write. | | | |
| DPC11 | Every pull helper writes a metadata sidecar and stamps `df.attrs`. | | | |
| DPC12 | Metadata sidecars and `df.attrs` flow automatically into manifest field provenance. | | | |
| DPC13 | The build loader cannot mistake metadata sidecars for datasets. | | | |
| DPC14 | JSON artifacts are first-class dashboard datasets. | | | |
| DPC15 | Fingerprint stdout is retained in clean-refresh logs. | | | |
| DPC16 | The initial sandbox timeout also bounds dashboard refresh pulls. | | | |
| DPC17 | A failed pull cannot leave stale prior data available to a subsequent build. | | | |
| DPC18 | Initial build and clean refresh have behaviorally identical namespaces and wrapper semantics. | | | |
| DPC19 | Source-data freshness and refresh execution time are represented by distinct timestamps. | | | |
| DPC20 | The router, kernel, build, and pipelines context owners match executable behavior. | | | |

For every `CONTRADICTS` or `UNKNOWN` row, identify the exact curated claim
that must remain untrusted. Do not turn the ledger into redesign advice.

## 10. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
CHECKOUT_IDENTITY_COMPLETE:
LIVE_PULL_SURFACE_ENUMERATED:
PERSISTED_SYMBOL_CENSUS_COMPLETE:
HELPER_SIGNATURES_COMPLETE:
BACKEND_CONTRACTS_COMPLETE:
CLIENT_CONTRACTS_COMPLETE:
WRAPPER_PREBINDING_RESOLVED:
THREE_NAMESPACE_PARITY_RESOLVED:
PULLS_RUN_PULL_FLOW_COMPLETE:
FLAT_PERSISTENCE_CONTRACT_COMPLETE:
METADATA_FINGERPRINT_PROVENANCE_RESOLVED:
TRANSFORMS_BUILD_FLOW_COMPLETE:
BUILD_REFRESH_DIFFERENCES_RESOLVED:
ERROR_TIMEOUT_IDEMPOTENCY_RESOLVED:
FRESHNESS_TIMESTAMPS_RESOLVED:
AUTHORING_CONTEXT_ALIGNMENT_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
DASHBOARD_DATA_PULL_CONTRACT_COMPLETE:
```

`DASHBOARD_DATA_PULL_CONTRACT_COMPLETE` may be `YES` only if every
preceding item is `YES`. If it is `NO`, list only the unresolved
section/subsection numbers and the missing source or permission.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and what
blocked it.
