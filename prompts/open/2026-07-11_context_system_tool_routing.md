---
class: context-extraction
topic: context-system-tool-routing
status: READY
created: 2026-07-11
sequence: 3/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
  - staging/prompts/open/2026-07-11_dashboard_data_pull_contracts.md
  - staging/prompts/open/2026-07-11_user_ontology_dashboards.md
reply_folded_into:
  - prism/architecture.md
  - prism/mcp-tools.md
  - prism/codebase-tree.md
  - prism/README.md
  - prism/_prompting-guide.md
---

# Context-extraction prompt - context system and tool routing

**Staging note (do not paste this section into PRISM):**

This prompt refreshes the full context-loading and L1 tool-routing
architecture after the `prism-main` / `prism-core` split. The local
`prism/` references are historical outside the dashboard-specific material
refreshed on 2026-07-11. The prior dashboard architecture prompt already
audits the dashboard package, persisted-script namespaces, portal, refresh,
assets, and deployment wiring in depth. This prompt uses the dashboard
router/kernel/spoke topology only as one bounded test of generic context and
repository-routing behavior.

The reply should be reviewed and folded only into the paths listed in
`reply_folded_into`.

---

## Paste the following into PRISM

# Context system and L1 tool-routing architecture refresh (read-only)

This is a pure read-only context-extraction request. Introspect the current
checked-out source. Do not answer from memory, an earlier conversation,
generated documentation, or a presumed pre-split `ai_development/` layout.

The goal is a current, source-backed map of:

- the split-checkout file graph;
- context registry, assembler, loader, and content types;
- exact Tier 1 and Tier 2 catalogs;
- specialization bundles, trigger-driven includes, exclusions, composites,
  and de-duplication;
- runtime user and world-state injection;
- `get_context` one-shot behavior;
- `list_ai_repo` root/path resolution, modes, limits, and warnings;
- registered module IDs versus ordinary on-demand repository files;
- context-budget instrumentation;
- the complete current L1 tool registry, signatures, and docstrings.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository file;
- write, copy, move, or delete S3 objects;
- create or modify a session artifact, context cache, index, ticket, report,
  observation, dashboard, completion marker, or background process;
- call a context runtime generator if it has writes, outbound requests, or
  other side effects;
- rebuild context caches or indexes;
- invoke POST, PUT, PATCH, or DELETE endpoints;
- install, upgrade, or reconfigure packages;
- alter environment variables, `sys.path`, Git state, or the checked-out
  submodule;
- print secrets, credentials, tokens, cookies, private user-memory values, or
  private document contents.

Use `list_ai_repo`, repository search, direct source reads, and read-only
`execute_analysis_script` introspection as needed. A script may print paths,
signatures, docstrings, registry metadata, hashes, types, and already-loaded
configuration only when it performs no writes and triggers no runtime
generator with side effects.

## Source-first method and reply protocol

1. Mirror every numbered section and subsection below.
2. Start each section with the source paths inspected. Distinguish source
   evidence from runtime introspection and from active documentation.
3. Cite every source-backed claim as
   `repository-relative/path.py:START-END`. Add an absolute path only where
   this prompt explicitly asks for one.
4. When a bounded source block is requested, paste it verbatim in a fenced
   code block. Do not use `...`, reconstructed code, omitted branches, or
   prose placeholders inside that block.
5. Do not paste an entire large file. A bounded block means one complete
   function, class, registry row, constant, import/registration block, or
   docstring. If the requested symbol itself exceeds 250 lines, report its
   exact line range and SHA-256, paste its signature plus complete docstring,
   and list its internal section headings and directly called helpers.
6. For every repository search, state:
   - every root searched;
   - every literal and regex pattern used;
   - exclusions;
   - match count;
   - every executable/configuration match as `path:line:source`.
   If any root could not be searched, say so in `## Could not resolve`.
7. Redact secret values and private user data. Preserve key names, value
   types, source paths, module IDs, control flow, and default behavior.
8. Where a verdict is requested, use only:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. Do not silently reconcile conflicting sources. Show both citations and
   use the fixed verdict vocabulary.
10. Keep current implemented behavior separate from comments, TODOs,
    proposals, migration notes, dead code, and historical compatibility
    paths.

## 0. Freshness and checkout identity

Return a concise identity block:

```text
INSPECTED_AT_UTC:
PRISM_MAIN_ROOT:
PRISM_MAIN_HEAD:
PRISM_CORE_ROOT:
PRISM_CORE_CHECKED_OUT_SHA:
PRISM_CORE_RECORDED_SHA:
CHECKED_OUT_MATCHES_RECORDED:
PYTHON_EXECUTABLE:
```

For each SHA, state the read-only command or metadata source used. If Git
metadata is unavailable, use `UNKNOWN`; do not infer identity from a folder
name, deployment label, or prior answer.

Give repository-relative and absolute roots for `prism-main` and
`prism-core`. State which root owns each top-level package currently relevant
to this prompt:

```text
core
jobs
prism_meta
web
prism_mcp
context
dashboards
```

## 1. Canonical current file graph

### 1.1 Root anchors and package resolution

Paste the complete bounded definitions that establish:

- `prism_meta.REPO_ROOT`;
- the `prism-main` root;
- the `prism-core` root;
- package/import path setup for `core`, `prism_mcp`, and `context`;
- any launcher, entrypoint, service, settings, `.pth`, editable-install, or
  `PYTHONPATH` configuration required for those imports.

Run a read-only process and return unshortened output for:

```python
import os
import sys
import core
import prism_meta
import prism_mcp

print("cwd", os.getcwd())
print("python", sys.executable)
print("sys_version", sys.version)
print("sys_path", list(enumerate(sys.path)))
print("core", getattr(core, "__file__", None))
print("prism_meta", getattr(prism_meta, "__file__", None))
print("prism_mcp", getattr(prism_mcp, "__file__", None))
print("repo_root", getattr(prism_meta, "REPO_ROOT", None))
```

Do not mutate `sys.path` for this inspection.

### 1.2 Context and tool file graph

Starting at both checkout roots, exhaustively locate current executable or
LLM-consumed files matching these names and concepts:

```text
context_tool.py
global_tools.py
registry.py
assembler.py
loader.py
context_baton.py
output_limits.py
developer_tools.py
subprocess_tools.py
server.py
MODULE_REGISTRY
SPECIALIZATION
specialization
include_modules
exclude_modules
content_type
list_ai_repo
RepositoryExplorer
get_context
global_context
```

Search roots:

```text
<prism-main root>
<prism-core root>
```

Exclude only `.git/`, caches, generated bytecode, virtual environments,
`node_modules/`, and build artifacts. Do not exclude active Markdown context,
active service configuration, or tests.

Return a canonical graph:

| Current path | Checkout owner | Kind | Defines | Direct callers/importers | Runtime/LLM consumed |
|---|---|---|---|---|---|

`Kind` must be one of `Python source`, `static context`, `runtime context`,
`cache/config`, `test`, `active documentation`, or `historical/archive`.

Then provide edges in this exact form:

```text
caller_path:symbol -> callee_path:symbol
```

Include the context-tool entry, registry, assembler, loader, runtime
generators, cached content loader, baton instrumentation, MCP server tool
registration, and repository explorer. This is the canonical current file
graph requested by this prompt.

### 1.3 Retired path and compatibility search

Search both roots for active executable/configuration references to:

```text
ai_development
ai_development/context
ai_development/mcp
prism-core/context
prism_mcp
context/modules
```

Return:

| Referencing path/lines | Reference | Active runtime effect | Compatibility alias | Current target | Verdict |
|---|---|---|---|---|---|

Do not classify comments, archives, or old documentation as runtime aliases.

## 2. Context registry schema and ownership

### 2.1 Registry definitions

Paste verbatim:

- imports and constants directly required by the module-definition type;
- the complete module-definition dataclass, TypedDict, Pydantic model, dict
  schema, or equivalent;
- the complete `MODULE_REGISTRY` declaration header;
- helper functions that resolve a module ID or validate registry entries;
- constants/enums for tier, pillar, content type, specialization, and bundle
  fields.

Return every actual registry field:

| Field | Type | Required | Default | Meaning | Reader(s) |
|---|---|---|---|---|---|

Do not infer fields from one sample row.

### 2.2 Registry source of truth

Answer with evidence:

1. Is there one registry, multiple merged registries, generated registry
   content, plugin discovery, or runtime registration?
2. Does any active code mutate the registry after import?
3. Are module descriptions duplicated in the `get_context` docstring,
   generated from the registry, or maintained independently?
4. What validation detects missing files, duplicate IDs, invalid bundles,
   invalid composites, or tier/content-type mismatches?
5. Which source is authoritative when docstring, registry, and filesystem
   inventory differ?

Search for all assignments, updates, decorators, registration calls, and
imports involving `MODULE_REGISTRY` or its current equivalent. Return every
active writer and reader.

## 3. Exact Tier 1 catalog

### 3.1 Strict Tier 1

Derive this catalog from current source, not local historical claims:

| Exact module ID | Pillar | Tier value | Content type | Current path/source | Inclusion rule | Size hint | Composite/components |
|---|---|---|---|---|---|---:|---|

Include every module loaded on every `get_context` call regardless of
specialization. State the exact source expression that establishes this set
and paste that bounded block verbatim.

Explicitly test the historical five-ID claim:

```text
core
parsing_issue
code_sandbox_context
session_hygiene
security_and_status
```

Do not assume the count remains five.

### 3.2 Conditionally always-on and generated/cached baseline

Return a separate row for every module effectively baseline-loaded by a
specialization, default parameter, kerberos presence, world-state default,
assembler rule, or bundle:

| Module ID | Trigger/default | Suppressed by | Content type | Source path | Implemented in | Verdict |
|---|---|---|---|---|---|---|

Explicitly resolve the current status of:

```text
macro_style_guide
observations_worldview
observations_summary
output_format_guide
directory_tree
search_indexes
user_context
```

Distinguish:

- unconditional Tier 1;
- specialization-default inclusion;
- parameter-triggered inclusion;
- runtime-generated content;
- cached content;
- ordinary optional Tier 2.

### 3.3 Render ordering and envelope

Paste the complete bounded code that determines:

- module ordering;
- `<CONTEXT_START>` and `<CONTEXT_END>` rendering;
- per-module delimiters/markers;
- duplicate removal;
- errors or placeholders for missing modules;
- returned metadata alongside the rendered string.

Return the exact final ordering algorithm in numbered steps.

## 4. Exact Tier 2 catalog and ordinary files

### 4.1 Exhaustive registered Tier 2 catalog

Return one row for every current registered non-Tier-1 module:

| Module ID | Pillar/domain | Content type | Current source/path | Description | Explicit trigger | Bundle | Composite members | Specialization(s) | Size hint |
|---|---|---|---|---|---|---|---|---|---:|

The table must be exhaustive. Group rows under the registry's current
domains, not a historical taxonomy. Preserve exact IDs and exact paths.

After the table, print:

```text
REGISTERED_TIER2_ROW_COUNT:
REGISTERED_TIER2_IDS_SORTED:
FILES_REFERENCED_BY_REGISTERED_TIER2_COUNT:
MISSING_REGISTERED_FILES_COUNT:
UNREFERENCED_ACTIVE_CONTEXT_FILES_COUNT:
```

For every missing registered file or unreferenced active context file, give
the exact path and explain whether it is ordinary on-demand content, dead,
generated, or unresolved.

### 4.2 Registered module IDs versus ordinary repository files

Define the distinction from source:

| Property | Registered module ID | Ordinary on-demand file |
|---|---|---|
| Addressed by | | |
| Valid in `include_modules` | | |
| Loaded by `get_context` | | |
| Read by `list_ai_repo` | | |
| Included in baton telemetry | | |
| Bundle/composite eligible | | |
| Validation owner | | |

Search active context Markdown for instructions that ask the LLM to fetch
another file via `list_ai_repo`. Return every such routing edge:

```text
registered_or_parent_file:line -> requested_short_path -> resolved_path
```

Do not paste the fetched file bodies.

## 5. Specializations, bundles, triggers, and de-duplication

### 5.1 Exact specialization catalog

Return every accepted `specialization` value:

| Specialization | Exact auto-includes | Exact suppressions/exclusions | Defaults changed | Source |
|---|---|---|---|---|

Explicitly resolve the historical set:

```text
end_user
orchestrator
report_planner
report_worker
report_writer
developer
```

Include values added, renamed, aliased, or removed.

Paste the complete bounded specialization mapping and the code that applies
it.

### 5.2 Parameter-triggered inclusion

Return every non-specialization inclusion trigger:

| Trigger parameter/state | Accepted shape/values | Included modules | Excluded modules | Ordering | Source |
|---|---|---|---|---|---|

Include at minimum:

```text
include_modules
exclude_modules
world_state
kerberos
bundle
script_categories
observation_domains
user_signal_hint
session
```

If a parameter affects generation inputs but not module selection, say so
with `NOT_PRESENT` for module-selection behavior.

### 5.3 Bundle expansion

Return every registry bundle edge:

```text
module_id -> bundled_module_id
```

Paste the complete bundle-expansion helper. State whether expansion is
recursive, whether cycles are detected, and whether explicit exclusion wins
over bundle inclusion.

### 5.4 Composite expansion and de-duplication

Return every composite module and its exact ordered members:

| Composite ID | Members in order | Composite source/path | Components removed from final list | Source |
|---|---|---|---|---|

Paste the complete composite-expansion and de-duplication logic. Answer:

1. At what stage does composite expansion happen?
2. Are nested composites supported?
3. Are duplicate IDs removed before or after load?
4. If both a composite and one of its members are explicitly requested, what
   renders?
5. What wins among strict Tier 1, specialization includes, bundles,
   `include_modules`, and `exclude_modules`?
6. Is ordering stable and deterministic?
7. What happens on an unknown module ID?

Give one source-backed worked example for each distinct branch. Do not run a
generator with side effects.

### 5.5 Trigger phrases that live only in L1 documentation

Compare executable assembler rules with routing instructions in the current
`get_context` docstring. Return every module whose trigger is documented for
LLM judgment but not code-enforced:

| Module ID | Exact docstring trigger | Code-enforced | Specialization-included | Registry row | Verdict |
|---|---|---|---|---|---|

Explicitly inspect:

```text
coalition
inquiry
prediction_markets_skill
```

## 6. Content loaders and runtime injection

### 6.1 Content-type dispatch

Return every accepted content type from source:

| Content type | Registry representation | Loader function | Storage location | Call signature | Failure behavior | Cached |
|---|---|---|---|---|---|---|

Explicitly determine whether these names still exist and what they mean:

```text
static
runtime
cached
dynamic
composite
```

Paste the complete bounded dispatch function(s), including imports needed to
understand dispatch.

### 6.2 Static modules

Show exact path resolution from registry row to file read. State encoding,
missing-file behavior, marker insertion, and whether file bodies are cached
in-process.

### 6.3 Runtime modules

Paste the runtime-module import and invocation code. Return:

| Runtime module ID | Python path | Callable | Exact signature | Inputs passed by assembler | External reads | Possible writes |
|---|---|---|---|---|---|---|

Do not execute a generator with possible writes or outbound calls. Source
inspection is sufficient.

### 6.4 Cached/dynamic modules

Paste the cache-key/path construction and cache-read behavior. State:

- storage manager used;
- exact key pattern;
- byte decoding;
- cache miss behavior;
- stale-cache behavior, if any;
- whether generation is synchronous, background, or outside
  `get_context`;
- whether cached bytes count toward baton instrumentation.

### 6.5 User-context injection

Trace the current `kerberos` path from `get_context` parameter to rendered
context:

```text
tool kwarg -> assembler -> registry/loader -> runtime generator -> output
```

Return key names and value types, but redact all user values. State exactly
which user stores may be read and whether missing/unknown kerberos is
fail-open, fail-closed, omitted, or erroring.

### 6.6 World-state injection

Return every accepted `world_state` key and alias:

| Input key/alias | Canonical module ID | Default | Runtime/static/cached | Generator/source | Invalid-value behavior |
|---|---|---|---|---|---|

Paste the complete normalization/mapping block. State whether unknown keys
are ignored, warned, or rejected.

## 7. `get_context` L1 contract and one-shot behavior

### 7.1 Registration, exact signature, and exact docstring

Paste verbatim:

- MCP registration/decorator block;
- complete current `get_context` signature;
- complete current docstring;
- kwarg coercion/normalization immediately at entry;
- the call into the assembler;
- the final response wrapper.

Do not paste unrelated implementation.

Return:

| Parameter | Annotation | Default | Normalization | Selection effect | Generator input effect |
|---|---|---|---|---|---|

Include every parameter, not only the historically documented ones.

### 7.2 One-shot semantics

Search source and active L1/L2 context for:

```text
ONCE PER USER MESSAGE
NEVER CALL TWICE
one allotted
CONTEXT_START
get_context(
call count
already called
```

Return every enforcement or instruction site. Answer separately:

| Question | Implemented fact | Evidence | Verdict |
|---|---|---|---|
| Is there a process/session/turn code guard? | | | |
| Does a second call raise, warn, return context, or do something else? | | | |
| Is one-shot behavior an LLM convention only? | | | |
| Is the unit one user message, one turn, one conversation, or one process? | | | |
| Can `include_modules` fetch content after the initial render? | | | |

### 7.3 Session parameter interaction

Trace `session` through normalization, session creation/adoption, returned
session path, and context evidence files. Do not write a session. Use source
inspection only. Keep this subsection limited to `get_context`; the adjacent
execution/storage lifecycle belongs to the next prompt in this sequence.

## 8. `list_ai_repo` and `RepositoryExplorer`

### 8.1 Registration, exact signature, and exact docstring

Paste verbatim:

- MCP registration/decorator block;
- complete current `list_ai_repo` signature;
- complete current docstring;
- the bounded preprocessing/dispatch function;
- the `RepositoryExplorer` class methods called by each mode.

Return every parameter:

| Parameter | Annotation | Default | Accepted values | Normalization | Failure behavior |
|---|---|---|---|---|---|

### 8.2 Root resolution after the split

Paste the complete root-resolution functions and every special-case branch
for:

```text
prism-main
prism-core
context
entrypoint.py
macro
filename-only lookup
directory paths
absolute paths
parent traversal
```

Return read-only resolution results for:

```text
context/modules/static/tools/
tools/dashboards.md
dashboards.md
dashboards_hub.md
dashboards/widgets.md
prism_mcp/tools/context_tool.py
core/common.py
entrypoint.py
```

For each input, report resolved path, ambiguity count, and whether the result
is file, directory, missing, or rejected. Do not paste file bodies.

### 8.3 Modes and extraction behavior

For every accepted mode, return:

| Mode | Input kinds | Implementation helper | Output shape | Python-only | Depth behavior | Error/fallback |
|---|---|---|---|---|---|---|

Explicitly validate:

```text
list
signatures
specific
full
```

Identify any additional accepted aliases or modes. Paste complete bounded
helpers for signature extraction, specific-element extraction, recursive
listing, and file-list formatting.

### 8.4 Limits, warnings, and security boundaries

Locate and paste the constants and checks for:

- file-size warning threshold;
- hard response or per-file limits;
- maximum recursion depth;
- default/floored signature depth;
- extension defaults;
- excluded directories;
- binary-file handling;
- path traversal / absolute-path rejection;
- secret-file filtering;
- maximum file count;
- output truncation;
- timeouts.

Return:

| Boundary | Exact value | Warning or block | Applied in mode(s) | Source |
|---|---:|---|---|---|

If a boundary is absent, use `NOT_PRESENT`; do not infer safety from no
observed failure.

### 8.5 Mid-session read contract

Answer with source and current docstring evidence:

1. Is there any separate repository-read tool?
2. Is `mode="full"` the canonical body-read path?
3. Can ordinary context files be fetched by short path?
4. How are duplicate basenames resolved?
5. Are repository reads included in context-budget baton telemetry?
6. Are there documented or enforced limits on number of calls per turn?

## 9. Context-budget instrumentation

### 9.1 Baton source and data flow

Paste verbatim:

- baton imports in the context tool;
- baton constants and report type definitions;
- `compute_initial_baton` and `compute_baton_dashboard` signatures and
  docstrings;
- overflow decision and email call site;
- assembler return carrying per-module sizes;
- response rendering of baton telemetry.

Return:

| Measurement | Unit | Scope | Computed before/after load | Includes markers | Includes ordinary repo reads |
|---|---|---|---|---|---|

### 9.2 Threshold and overflow behavior

State exact thresholds, recipient/configuration source with values redacted,
whether overflow blocks or warns, and whether email failure affects context
delivery. Distinguish character counts, bytes, estimated tokens, and actual
model tokens.

### 9.3 Uninstrumented surfaces

Identify, from source, context entering the model outside the baton:

- L1 tool schemas/docstrings;
- system instructions;
- mid-session `list_ai_repo` results;
- tool results;
- runtime interface wrappers;
- any other active surface found.

Do not estimate sizes unless source computes them. Mark unavailable
measurements `UNKNOWN`.

## 10. Complete current L1 tool registry

### 10.1 Registration mechanism

Paste the complete bounded MCP tool-registration/import block(s). Explain
whether tools are registered by decorators, explicit lists, server
inspection, plugin discovery, or multiple mechanisms.

Search both checkout roots for every active MCP tool registration pattern,
including:

```text
@mcp.tool
@server.tool
register_tool
add_tool
Tool(
FastMCP
list_tools
```

Adapt patterns to actual source after the first match, and report all
patterns searched.

### 10.2 Exhaustive tool inventory

Return one row per currently exposed L1 tool:

| Exposed tool name | Defining path:line | Python symbol | Async | Exact signature | Registration site | Domain | Mutation-capable |
|---|---|---|---|---|---|---|---|

`Mutation-capable` is `YES` or `NO`, based on implementation behavior, not
name. Include aliases and conditionally registered tools. Exclude imported
helpers that are not exposed tools.

Print:

```text
L1_EXPOSED_TOOL_COUNT:
L1_EXPOSED_TOOL_NAMES_SORTED:
```

### 10.3 Current signatures and docstrings

For every exposed L1 tool in section 10.2, paste one bounded verbatim block
containing only:

- registration decorators immediately attached to the tool;
- the complete function signature;
- the complete current docstring.

Do not paste function bodies. If a tool has no docstring, state
`NOT_PRESENT` and cite its definition. Preserve exact whitespace and wording
inside every docstring.

Then return:

| Tool | Docstring routes to L2 module IDs | Docstring names ordinary files | Docstring references another tool | Stale path candidate |
|---|---|---|---|---|

### 10.4 L1 versus L2 routing ownership

Identify every L1 docstring that acts as a routing table. For every module ID
mentioned in a tool docstring, verify it exists in the current registry. For
every ordinary file path mentioned, verify it resolves through
`list_ai_repo`.

Return every mismatch:

| Tool/docstring line | Referenced ID/path | Registry/filesystem state | Runtime consequence | Verdict |
|---|---|---|---|---|

## 11. Dashboard router/kernel/spokes as a focused routing example

Do not repeat the prior dashboard architecture audit. Do not inspect the
dashboard compiler, persisted-script namespaces, Django routes, refresh
runner, assets, registry/status schemas, or deployment wiring here.

Use only the context registry, context files, and repository resolver to
validate this generic routing example:

```text
registered module ID: dashboards
router file: tools/dashboards.md
ordinary kernel file: tools/dashboards_hub.md
ordinary spokes: tools/dashboards/*.md
```

Return:

| Layer | Exact ID/path | Registry row | Valid in `include_modules` | Retrieval mechanism | Baton-covered |
|---|---|---|---|---|---|

Paste only:

- the `dashboards` registry row;
- the router's bounded on-demand file-routing menu;
- the exact resolver branch used by those short paths.

List the current kernel and spoke paths without pasting their bodies. State
whether any kernel/spoke is independently registered. This section exists
only to prove the generic distinction in section 4.2.

## 12. Diff against local historical claims

The local historical references currently claim, among other things:

1. Context follows
   `context_tool.py -> registry.py -> assembler.py -> loader.py`.
2. Strict Tier 1 has five modules:
   `core`, `parsing_issue`, `code_sandbox_context`, `session_hygiene`,
   `security_and_status`.
3. Four modules are conditionally always-on:
   `macro_style_guide`, `observations_worldview`,
   `observations_summary`, `output_format_guide`.
4. `directory_tree` is runtime, `search_indexes` is cached, and
   `user_context` is runtime when kerberos is supplied.
5. Registered content types are `static`, `runtime`, `cached`, and
   `composite`.
6. Specializations include `end_user`, `orchestrator`, `report_planner`,
   `report_worker`, `report_writer`, and `developer`.
7. Explicit includes, world-state flags, kerberos, bundles, and composites
   are combined before final de-duplication.
8. `get_context` is once per user message by LLM convention, without a code
   guard.
9. `include_modules` is not a mid-session fetch primitive.
10. `list_ai_repo` supports `list`, `signatures`, `specific`, and `full`.
11. Large files are warned at 20 KiB but not blocked.
12. Baton telemetry covers L2 modules but not mid-session repository reads.
13. The split checkout replaced the old monolithic
    `ai_development/...` physical layout.
14. Only the dashboard router is a registered module; its kernel and spokes
    are ordinary files.

Return a concise source-backed diff:

| Claim | Current fact | Changed/unchanged | Evidence | Verdict |
|---|---|---|---|---|

`Changed/unchanged` may contain only `CHANGED`, `UNCHANGED`, or `UNKNOWN`;
the formal verdict remains one of the four fixed verdict values.

## 13. Prompt-specific contradiction ledger

Complete every row:

| ID | Local assumption | Verdict | Current production fact | Exact evidence |
|---|---|---|---|---|
| C01 | `prism-main` and `prism-core` form the current split checkout. | | | |
| C02 | `prism-core` owns `prism_mcp` and the active context system. | | | |
| C03 | No active context/tool runtime requires the old monolithic `ai_development/` root. | | | |
| C04 | One authoritative registry owns registered context-module IDs. | | | |
| C05 | Registry descriptions and the `get_context` docstring are independently maintained. | | | |
| C06 | Strict Tier 1 is exactly the historical five-ID set. | | | |
| C07 | The historical conditionally-always-on four-ID set is current. | | | |
| C08 | The Tier 2 table in this reply exhausts all registered non-Tier-1 IDs. | | | |
| C09 | Active context files not in the registry are ordinary repository files, generated files, or dead/unresolved files. | | | |
| C10 | `static`, `runtime`, `cached`, and `composite` are the complete current content-type set. | | | |
| C11 | Specialization auto-includes, bundles, explicit includes, and exclusions have deterministic precedence. | | | |
| C12 | Composite members are de-duplicated from rendered context. | | | |
| C13 | Kerberos triggers runtime user-context injection. | | | |
| C14 | Every accepted world-state key maps to a current registry module. | | | |
| C15 | `get_context` has no code-enforced one-shot guard. | | | |
| C16 | `include_modules` cannot fetch a module after the initial context render. | | | |
| C17 | `list_ai_repo` is the canonical mid-session repository-read tool. | | | |
| C18 | `list_ai_repo` has exactly four modes. | | | |
| C19 | Its large-file threshold is a warning, not a hard block. | | | |
| C20 | Context baton instrumentation excludes `list_ai_repo` results. | | | |
| C21 | The L1 tool inventory and docstrings returned here are complete for the current checkout. | | | |
| C22 | Dashboard kernel/spokes are ordinary files, not valid `include_modules` IDs. | | | |
| C23 | The canonical file graph covers every active context/tool registration and loader path. | | | |

For every `CONTRADICTS` or `UNKNOWN` row, name the exact local fold target
that should remain untrusted pending reconciliation:

```text
prism/architecture.md
prism/mcp-tools.md
prism/codebase-tree.md
prism/README.md
prism/_prompting-guide.md
```

Do not propose or perform edits.

## 14. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
FRESHNESS_IDENTITY_COMPLETE:
CURRENT_FILE_GRAPH_COMPLETE:
SPLIT_PATH_RESOLUTION_COMPLETE:
REGISTRY_SCHEMA_COMPLETE:
TIER1_CATALOG_COMPLETE:
TIER2_CATALOG_COMPLETE:
ORDINARY_FILE_DISTINCTION_COMPLETE:
SPECIALIZATION_CATALOG_COMPLETE:
TRIGGER_PRECEDENCE_COMPLETE:
BUNDLE_EXPANSION_COMPLETE:
COMPOSITE_DEDUP_COMPLETE:
CONTENT_LOADERS_COMPLETE:
USER_CONTEXT_PATH_COMPLETE:
WORLD_STATE_PATH_COMPLETE:
GET_CONTEXT_CONTRACT_COMPLETE:
ONE_SHOT_BEHAVIOR_RESOLVED:
LIST_AI_REPO_CONTRACT_COMPLETE:
LIST_AI_REPO_LIMITS_COMPLETE:
BATON_INSTRUMENTATION_COMPLETE:
L1_TOOL_INVENTORY_COMPLETE:
L1_TOOL_DOCSTRINGS_COMPLETE:
DASHBOARD_ROUTING_EXAMPLE_COMPLETE:
HISTORICAL_DIFF_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
CONTEXT_TOOL_ROUTING_REFRESH_COMPLETE:
```

`CONTEXT_TOOL_ROUTING_REFRESH_COMPLETE` may be `YES` only when every
preceding item is `YES`. If it is `NO`, list only the unresolved
section/subsection numbers and the missing source, search root, or
permission.

## Could not resolve

Always end with this heading. If nothing is unresolved, write:

```text
None.
```

Otherwise list each unresolved item with:

```text
SECTION:
ATTEMPTED:
BLOCKER:
EVIDENCE_OR_PERMISSION_NEEDED:
```
