---
class: context-extraction
topic: sandbox-storage-execution
status: READY
created: 2026-07-11
sequence: 4/7
depends_on:
  - staging/prompts/open/2026-07-11_context_system_tool_routing.md
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
reply_folded_into:
  - prism/code-sandbox.md
  - prism/mcp-utils.md
  - prism/gateway.md
  - prism/boolean-sanitization.md
  - prism/session-hygiene.md
  - prism/security.md
  - prism/architecture.md
---

# Context-extraction prompt - sandbox, storage, and execution

**Staging note (do not paste this section into PRISM):**

This prompt refreshes `execute_analysis_script` and the adjacent execution,
storage, gateway, sanitization, session, and helper boundaries after the
`prism-main` / `prism-core` split. Local references outside the bounded
dashboard refresh performed on 2026-07-11 are historical. The earlier
dashboard architecture prompt already asks for the complete
dashboard-specific sandbox and persisted-script namespace audit. This prompt
uses dashboard execution only as a narrow cross-check of generic sandbox
principles; it does not repeat the compiler, portal, refresh, asset, or
deployment audit.

The reply should be reviewed and folded only into the paths listed in
`reply_folded_into`.

---

## Paste the following into PRISM

# Sandbox, storage, and execution architecture refresh (read-only)

This is a pure read-only context-extraction request. Introspect the current
checked-out source and currently importable runtime. Do not answer from
memory, previous conversations, local historical documentation, or presumed
pre-split `ai_development/` paths.

Refresh the current implementation of:

- `execute_analysis_script` signature and lifecycle;
- namespace construction by category;
- wrappers, partials, decorators, and validators;
- process, working-directory, `sys.path`, and import behavior;
- S3 singletons, proxies, wrappers, public methods, returns, and errors;
- session path construction and script-defined `SESSION_PATH`;
- artifact tracking and download-link generation;
- stdout, stderr, exception, email, and ticket behavior;
- preprocessing and AST checks;
- gateway parse/route behavior;
- gateway, Python, JavaScript, and S3 boolean/null sanitization boundaries;
- session hygiene;
- subprocess and raw-singleton bypasses;
- active adjacent `prism_mcp.utils` contracts.

Separate implemented current behavior from proposals, comments, TODOs,
known gaps, dead code, and historical compatibility paths.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify repository files;
- execute user analysis code, saved scripts, dashboard scripts, report
  workers, jobs, subprocesses, or refresh entry points;
- write, copy, move, delete, or sanitize an S3 object;
- generate a presigned URL if doing so copies data or changes storage;
- create a session, context artifact, script artifact, result file, chart,
  dashboard, report, observation, ticket, completion marker, log object, or
  background process;
- send an email or invoke `send_error_email`;
- invoke POST, PUT, PATCH, or DELETE endpoints;
- trigger an intentional error merely to observe email/ticket behavior;
- install, upgrade, or reconfigure packages;
- mutate environment variables, `sys.path`, Git state, singleton state, or
  the checked-out submodule;
- print secrets, security-node values, credentials, access keys, tokens,
  cookies, email addresses, private user values, or private S3 contents.

Use `list_ai_repo`, repository search, direct source reads, `inspect`,
`ast`, and read-only process introspection. You may inspect signatures,
docstrings, source paths, class/type identity, constants, and already-loaded
objects only when doing so has no writes or outbound side effects. Prefer
source inspection whenever property access could initialize a singleton.

## Source-first method and reply protocol

1. Mirror every numbered section and subsection below.
2. Begin each section with source paths inspected. Distinguish source,
   read-only runtime introspection, active documentation, and historical
   comments.
3. Cite every source-backed claim as
   `repository-relative/path.py:START-END`. Add absolute paths only where
   explicitly requested.
4. Paste requested bounded source blocks verbatim in fenced code blocks.
   Never use `...`, reconstructed code, omitted branches, or prose
   placeholders inside a requested block.
5. Do not paste entire large files. A bounded block is one complete function,
   class, method, signature/docstring, constant block, namespace literal,
   import block, error branch, or call site. If a requested symbol exceeds
   250 lines, report exact line range and SHA-256, then paste its signature,
   complete docstring, and only the complete directly relevant internal
   branches named by this prompt.
6. For every repository search, state:
   - all roots searched;
   - every literal and regex pattern;
   - exclusions;
   - match count;
   - every executable/configuration match as `path:line:source`.
   If any root is unavailable, record it in `## Could not resolve`.
7. Redact values, not structure. Preserve key names, value types, signatures,
   defaults, control flow, paths, exception types, and return shapes.
8. Where a verdict is requested, use only:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. Do not silently reconcile conflicting evidence. Show both sources and
   classify the conflict with the fixed vocabulary.
10. Do not run code paths merely to prove behavior already visible in source.

## 0. Freshness and checkout identity

Return only this concise identity block plus one citation per line:

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

Give absolute and repository-relative roots. If Git metadata is unreadable,
use `UNKNOWN`; do not infer identity.

State which root currently owns:

```text
core
jobs
prism_meta
web
prism_mcp
prism_mcp/tools/script_exec_tools.py
prism_mcp/utils
```

## 1. Canonical execution-boundary file graph

### 1.1 Exhaustive source discovery

Search both checkout roots for active definitions and call sites matching:

```text
execute_analysis_script
execute_with_timeout
preprocess_script_code
coerce_gateway_nulls
_fix_javascript_booleans
sanitize_python_script_booleans
sanitize_html_booleans
S3ManagerWrapper
S3BucketManager
s3_manager
s3_manager_personal
s3_manager_unsecured
SESSION_PATH
session.base_path
generate_presigned_download_url
generate_download_links_for_sandbox
send_error_email
submit_ticket
format_llm_friendly_error
redirect_stdout
redirect_stderr
script_path
search_replace
```

Search roots:

```text
<prism-main root>
<prism-core root>
```

Exclude only `.git/`, caches, generated bytecode, virtual environments,
`node_modules/`, and build artifacts. Include active tests, static context,
service/entrypoint configuration, and direct subprocess callers.

Return:

| Current path | Checkout owner | Kind | Defines/uses | Direct caller/importer | Process boundary |
|---|---|---|---|---|---|

`Kind` must be one of `Python source`, `static context`, `test`,
`configuration`, `active documentation`, or `historical/archive`.

Then return executable edges:

```text
caller_path:symbol -> callee_path:symbol
```

The graph must include tool registration, preprocessing, namespace building,
execution, session storage, wrapper/singleton storage, artifact collection,
download links, error handling, and any raw-singleton subprocess path.

### 1.2 Old-path compatibility

Search active executable/configuration source for:

```text
ai_development.mcp.tools.script_exec_tools
ai_development.mcp.utils
ai_development.core.s3_bucket_manager
prism_mcp.tools.script_exec_tools
prism_mcp.utils
core.s3_bucket_manager
```

Return:

| Reference path/line | Import/reference | Resolved module path | Active alias/compatibility | Verdict |
|---|---|---|---|---|

Do not treat archived prose as an active alias.

## 2. Exact `execute_analysis_script` contract

### 2.1 Registration, signature, and docstring

Paste verbatim:

- the MCP registration/decorator block;
- complete current function signature;
- complete current docstring;
- imports/constants immediately required to interpret its parameters;
- tool-entry gateway-coercion block.

Return every parameter:

| Parameter | Annotation | Default | Accepted forms | Coercion | Mutually exclusive with | Runtime effect |
|---|---|---|---|---|---|---|

Include `script_code`, `script_path`, `search_replace`, data/session/user
arguments, timeout controls, and every current parameter found. Do not limit
the table to historical parameters.

### 2.2 Return contract

Trace every return statement and exception escape:

| Branch | Trigger | Returned type | Exact shape/fields | Includes stdout | Includes stderr | Includes links | Raises |
|---|---|---|---|---|---|---|---|

Paste each complete bounded return/error branch. State whether MCP
serialization changes the Python return value before the LLM receives it.

### 2.3 Input mode precedence

Paste the complete logic that chooses among:

```text
inline script_code
existing script_path
search_replace against a saved script
any other current mode
```

Answer:

1. Which combinations are valid?
2. Which value wins if multiple modes are supplied?
3. How are string `"null"`, empty string, `None`, `True`, and `False`
   normalized before mode selection?
4. Does `script_path` read from S3, local disk, repository, or multiple
   locations?
5. Does `search_replace` modify persisted source, only in-memory source, or
   both?
6. What evidence files are written for each mode?

Use source inspection only; do not invoke a mode.

## 3. Full execution lifecycle

### 3.1 Ordered control flow

Return a numbered lifecycle from tool entry to MCP response. Every step must
name the exact function/method and cite source. Include:

1. gateway kwarg coercion;
2. user/session identity normalization;
3. session initialization/adoption;
4. source loading or search/replace;
5. source preprocessing;
6. syntax/AST/security checks;
7. script and result evidence-path construction;
8. namespace construction;
9. stdout/stderr capture;
10. timeout/thread/process execution;
11. exception formatting;
12. artifact collection;
13. chart/image post-processing, if still generic to the tool;
14. download-link construction;
15. result persistence;
16. email/ticket side effects;
17. final return serialization.

Do not add a step unless current source implements it.

### 3.2 Complete bounded orchestrator blocks

Paste the complete bounded blocks for:

- session initialization and early failure;
- source loading/preparation;
- preprocessing/check invocation;
- namespace construction call;
- `execute_with_timeout` call and result handling;
- success persistence and final return;
- timeout branch;
- script-exception branch;
- outer catch-all.

If these branches are inside one function longer than 250 lines, paste each
complete branch with its enclosing condition/try/except header and exact line
range rather than the whole function.

### 3.3 Implemented behavior versus proposals

Return:

| Claim/comment/TODO | Source | Implemented call path exists | Tests exist | Current classification |
|---|---|---|---|---|

`Current classification` must be one of:

```text
CURRENT_BEHAVIOR
PROPOSAL
KNOWN_GAP
DEAD_OR_UNREACHABLE
UNKNOWN
```

This classification is descriptive, not the formal verdict vocabulary.

## 4. Namespace construction by category

### 4.1 Namespace builder and base globals

Paste the complete function(s) that construct the execution namespace,
including imports immediately required to understand the literal. If the
namespace literal exceeds 250 lines, paste it in complete category blocks
without omitting any key.

Return one row for every injected name:

| Injected name | Category | Runtime object/type | Imported/defined from | Wrapping/partial | Pre-bound arguments | Publicly documented |
|---|---|---|---|---|---|---|

Use these categories where applicable, adding source-defined categories only
when necessary:

```text
core libraries
S3/session
data retrieval
external API clients
charts
dashboards
memory
cabinet/user state
reports/observations/tickets
news/search
vision/PDF
Pure/Alloy
inquiry
coalition
files/downloads
utilities
constants/types
other
```

Print:

```text
INJECTED_NAME_COUNT:
INJECTED_NAMES_SORTED:
```

### 4.2 Namespace exclusions and shadowing

Search imported symbols used during namespace construction and identify:

- imported but not injected names;
- injected aliases;
- injected names that shadow an imported symbol;
- duplicate dict keys;
- names removed by preprocessing;
- helpers documented in L2 but absent at runtime;
- runtime names absent from L2 documentation.

Return:

| Name | Imported | Injected | Documented | Shadow/alias source | Runtime consequence | Verdict |
|---|---|---|---|---|---|---|

### 4.3 Wrapper, partial, decorator, and validator chain

For every non-bare injected callable, return the exact wrapping chain:

```text
sandbox_name -> outer_wrapper -> partial/decorator -> underlying_callable
```

Paste complete bounded definitions for generic wrappers/validators used by
multiple injected names. Include:

```text
_wrap_chart_func
validate_params
timing wrappers
functools.partial bindings
session/user/S3 injection wrappers
error-enrichment wrappers
```

Add or remove names based on current source.

Return:

| Sandbox name(s) | User-visible signature | Hidden/pre-bound params | Override allowed | Wrapper error behavior | Evidence |
|---|---|---|---|---|---|

### 4.4 API-client injection

Return every injected client module/function and every client imported but
not injected:

| Sandbox name | Source module | Module or function | Injected | Explicit import required | Current guide/module ID |
|---|---|---|---|---|---|

Do not audit each client's HTTP transport here. The question is namespace
exposure only.

## 5. Process, timeout, and import behavior

### 5.1 Execution primitive

Paste the complete current `execute_with_timeout` implementation and its
direct caller. Return:

| Property | Current fact | Source |
|---|---|---|
| Thread/process/subprocess | | |
| Timeout value and source | | |
| Timeout cancellation mechanism | | |
| Whether timed-out code can continue running | | |
| Namespace shared with caller | | |
| stdout capture object | | |
| stderr capture object | | |
| exception transport | | |
| completed flag semantics | | |

Explicitly determine whether timeout is a hard kill, cooperative stop, join
timeout, process termination, or another mechanism.

### 5.2 Working directory and environment

Paste source that sets or assumes:

```text
cwd
PYTHONPATH
PYTHONHOME
PATH
sys.path
module roots
```

Run one read-only process that imports no storage singleton and prints:

```python
import os
import sys

print("cwd", os.getcwd())
print("python", sys.executable)
print("sys_path", list(enumerate(sys.path)))
print("PYTHONPATH_present", "PYTHONPATH" in os.environ)
print("PYTHONHOME_present", "PYTHONHOME" in os.environ)
```

Do not print environment values that may contain private paths or secrets
beyond the explicit `cwd`, executable, and `sys.path` requested.

### 5.3 Import policy inside scripts

Trace:

- redundant-import removal;
- allowed standard-library and third-party imports;
- imports of injected helpers;
- imports from `core`, `prism_mcp`, and `dashboards`;
- local/repository file imports;
- dynamic import handling;
- any allowlist, denylist, or AST restriction.

Return:

| Import pattern | Allowed | Removed/rejected | Resolution root | Error surfaced as | Source |
|---|---|---|---|---|---|

Do not infer a sandbox restriction from documentation alone.

### 5.4 Split-checkout import graph

Return current package ownership and importability:

| Package/module | Checkout owner | Resolved `__file__` | Root on `sys.path` | Imported by sandbox |
|---|---|---|---|---|

Include `core`, `jobs`, `prism_meta`, `web`, `prism_mcp`, and `dashboards`.
Use source/path introspection only; do not import a module whose import has
known side effects.

## 6. Session base path and `SESSION_PATH`

### 6.1 Session object and base-path construction

Paste:

- session class/dataclass definition;
- base-path construction/normalization;
- session creation/adoption logic;
- exact caller in `execute_analysis_script`;
- script/result/context evidence-path builders.

Return:

| Input form | Accepted | Normalized path | New folder semantics | Reuse semantics | Error behavior |
|---|---|---|---|---|---|

Include a bare slug, a full `sessions/...` path, an external
`threads/.../artifacts` path, empty string, `None`, and malformed traversal.

### 6.2 Is `SESSION_PATH` injected?

Search active executable source and active L1/L2 context for:

```text
"SESSION_PATH"
'SESSION_PATH'
SESSION_PATH =
session.base_path
namespace
exec_namespace
```

Return every executable assignment/injection and every instruction to the
LLM. Answer:

| Question | Current fact | Evidence | Verdict |
|---|---|---|---|
| Is `SESSION_PATH` a namespace key? | | | |
| Must emitted inline code define it literally? | | | |
| Does a wrapper independently capture `session.base_path`? | | | |
| Can the script literal and wrapper closure diverge? | | | |
| What happens if the script omits it but never references it? | | | |
| What happens if the script references it without defining it? | | | |

### 6.3 Continuity and hygiene

Trace the exact source/docstring rules for:

- one conversation to one session folder;
- first-turn slug versus subsequent full path;
- inspect before pull;
- mandatory `name=` on data pulls;
- reusing files instead of re-pulling;
- editing a failed saved script rather than creating retries;
- evidence left by each execution call.

For each rule, distinguish code enforcement from LLM instruction:

| Rule | Code-enforced | L1/L2 instructed | Violation behavior | Evidence |
|---|---|---|---|---|

Do not create a session to test these rules.

## 7. S3 managers, singletons, proxies, and wrappers

### 7.1 Complete singleton inventory

Search both roots for every module-level `S3BucketManager` construction,
lazy getter, proxy, and exported manager.

Return:

| Exported name | Defining path | Concrete/proxy/wrapper | Bucket role | Security source | Lazy | Sandbox-visible | Direct subprocess users |
|---|---|---|---|---|---|---|---|

Redact bucket names only if policy requires it; otherwise preserve
non-secret bucket identifiers. Always redact credentials, endpoints with
tokens, passwords, and security values.

Explicitly resolve:

```text
s3_manager
s3_manager_personal
s3_manager_unsecured
```

### 7.2 `S3BucketManager` public surface

Paste the class signature and every public method signature/docstring.
Paste complete method bodies only for `get`, `put`, `exists`, `show_all`,
`list`, and `move` if each is 100 lines or fewer; otherwise paste the
complete directly relevant branches.

Return:

| Method/property | Exact signature | Accepted inputs | Return type/shape | Side effects | Exceptions/retries | Encoding |
|---|---|---|---|---|---|---|

Include all current public methods/properties, not only historical ones.

For polymorphic `put`, provide one row per accepted object type and exact
extension/serialization behavior. Determine whether successful `put`
returns `None`, the path, a response object, or multiple possible shapes.

### 7.3 Singleton/proxy initialization

Paste complete lazy getters and proxy classes. State:

- initialization trigger;
- cache lifetime;
- thread safety;
- failure caching/retry behavior;
- reset path, if any;
- whether property/introspection access initializes the singleton;
- which raw manager is imported by subprocess/jobs.

### 7.4 `S3ManagerWrapper`

Paste the complete wrapper class if 250 lines or fewer. Otherwise paste:

- constructor;
- every public method/property;
- artifact-tracking state;
- `.py` sanitization branch;
- delegation behavior.

Return:

| Wrapper member | Underlying member | Added behavior | Return preserved | Errors changed | Artifact tracked |
|---|---|---|---|---|---|

Explicitly answer:

1. Is there `__getattr__` forwarding?
2. Which raw-manager methods are inaccessible through the wrapper?
3. Does `put` preserve the raw return?
4. How are chart versus data artifacts classified?
5. What path prefix validation exists?
6. Does `.py` auto-sanitization fail open or fail closed?
7. Does wrapper `s3_client` expose a bypass around tracking/sanitization?

### 7.5 Personal and unsecured surfaces

State whether personal and unsecured managers are raw, proxied, or wrapped
in the sandbox. Identify every execution-tool call that uses them and every
operation allowed. Do not enumerate user objects.

## 8. Artifact tracking and download links

### 8.1 Artifact registry

Paste the wrapper state and methods that record artifacts, plus the
post-execution code that consumes them.

Return:

| Artifact category | Recorded on | Path filter | Deduplication | Ordering | Consumed by |
|---|---|---|---|---|---|

Determine whether artifacts written through raw `s3_client`, a raw
singleton, direct boto client, subprocess, or personal manager are visible
to the execution tool's tracker.

### 8.2 Download-link utility surface

From the current download-link module, return every public function,
dataclass, and constant:

| Symbol | Exact signature/fields | Return | Storage reads/writes | Raises or fail-safe | Active caller(s) |
|---|---|---|---|---|---|

Paste complete signatures and docstrings. Paste the bounded implementation
for the function used by `execute_analysis_script`.

### 8.3 Presigned-link lifecycle

Trace exact storage flow:

```text
tracked source path -> source manager -> copy/no-copy -> destination manager
-> presign -> optional metadata/verification -> serialized tool response
```

Answer:

1. Does generating a link copy data to another bucket?
2. Which manager creates the URL?
3. What is the default and maximum expiry?
4. What metadata is returned?
5. What happens when one artifact fails but others succeed?
6. Are URLs generated for every tracked artifact or selected extensions?
7. Are session-folder scans used in addition to in-memory tracking?

Use source inspection only. Do not generate a link.

### 8.4 Generic evidence persistence

Return exact key/path patterns for:

- saved script source;
- result Markdown/text;
- stdout/stderr;
- data artifacts;
- chart/image artifacts;
- error artifacts;
- context/session metadata.

State which writes are mandatory, conditional, or absent.

## 9. stdout, stderr, exceptions, email, and tickets

### 9.1 Stream capture

Paste stream initialization, redirection, extraction, truncation, and
response assembly. Return:

| Stream | Captured | Persisted | Returned | Truncated | Ordering | Thread-safe |
|---|---|---|---|---|---|---|

State whether output emitted before an exception is preserved.

### 9.2 Error classification and LLM-friendly formatting

Paste:

- `format_llm_friendly_error` signature/docstring and relevant complete
  branches;
- traceback/offending-line extraction;
- hint-key mapping;
- timeout diagnosis helper;
- error response assembly.

Return:

| Error class/branch | LLM response | Email | Ticket | Persisted evidence | Re-raised |
|---|---|---|---|---|---|

Include syntax/preprocess errors, validation errors, ordinary Python
exceptions, memory errors, timeouts, session initialization, data loading,
download-link failures, and outer catch-all.

### 9.3 `send_error_email`

Paste exact signature, complete docstring, configuration dataclass/constant
names, and the complete fail-safe exception branch. Redact recipients and
credentials.

Return every execution/storage call site:

| Call site | Stage/tool name | Parameters included | Trigger | Failure effect |
|---|---|---|---|---|

Determine whether timeout errors email and whether email failures can change
the tool result.

### 9.4 Ticket behavior

Search for automatic or manual ticket creation adjacent to execution errors:

```text
submit_ticket
create_ticket
ticket
incident
error signature
```

Return every executable call site. If `execute_analysis_script` never
creates a ticket automatically, use `NOT_PRESENT`. Distinguish an injected
`submit_ticket` helper available to user code from automatic error handling.

## 10. Preprocessing, AST checks, and security boundaries

### 10.1 Preprocessing pipeline

Paste the complete `preprocess_script_code` function and every helper it
calls, subject to the 250-line bounded-block rule. Return exact order:

| Order | Helper/check | Transforms or validates | Fail-open/closed | Error type | Idempotent |
|---:|---|---|---|---|---|

Include redundant-import removal, frequency-alias repair, boolean/null
repair, syntax parsing, and every current check.

### 10.2 Exhaustive checks

Search source and tests for all checks invoked before `exec`. Return:

| Check | Exact prohibited pattern | Detection mechanism | False-positive guard | Exception/message | Test count |
|---|---|---|---|---|---:|

Explicitly inspect:

```text
raw matplotlib
local filesystem reads
local filesystem writes
full S3 listings
Excel hardcoded-value anti-patterns
subprocess/process launch
network calls
dynamic imports
eval/exec/compile
dunder access
credential/environment access
path traversal
```

If a category has no check, use `NOT_PRESENT`. Do not infer a security
boundary from the word "sandbox".

### 10.3 Enforcement scope and bypasses

For every check, state whether it applies to:

```text
inline script_code
script_path-loaded source
search_replace result
nested source strings written as .py
imported modules
subprocess-executed scripts
raw singleton writes
dashboard/report/job runners
```

Return all known bypasses proven by source or tests. Keep proposed fixes
separate.

### 10.4 Security-module overlap

Identify which execution restrictions are documented in the current strict
Tier 1 security/status context and which exist only in code. Return mismatches
without proposing edits.

## 11. Gateway parse and route boundary

### 11.1 Current response parsing

Locate the current gateway/interface code that receives raw model output.
Search both roots for:

```text
ast.literal_eval
literal_eval(
tool_answer
tool call
tool_calls
content blocks
.get("name")
.get('name')
```

Paste complete bounded parse/route functions. Return:

| Input shape | Parse result | Routed as | Failure behavior | Interface(s) |
|---|---|---|---|---|

Include plain text, dict literal, list of dicts, list containing strings,
quoted string, JSON code block, and vendor-native tool-call objects.

### 11.2 Start-with-letter and raw-structure claims

Determine from current implementation:

1. Must final text start with an ASCII letter?
2. Does starting with `{`, `[`, `"`, or a code fence enter a parser?
3. Does a successfully parsed non-tool structure crash, return, or fall
   through?
4. Are all interfaces governed by the same parser?
5. Are Unicode/em dash failures still implementation behavior or historical
   guidance?
6. Is ASCII-only an enforced check, a parser side effect, or an LLM rule?

Return fixed-vocabulary verdicts with exact citations.

### 11.3 Iteration limits

Paste the current tool-loop limit and stop conditions. State whether the
historical maximum of 20 iterations remains current and whether it varies by
interface/model.

### 11.4 Naive replacement

Search for all global replacements of:

```text
None
True
False
null
true
false
```

Paste every executable replacement block in the gateway path. Show whether
the historical no-op-looking replacement still exists, changed, or is
absent. Distinguish replacement before parsing, after parsing, tool-argument
serialization, and final-answer routing.

## 12. Boolean/null sanitization vectors

### 12.1 Current vector inventory

Build the table from current source:

| Vector | Boundary | Corruption/input | Automatic/explicit | Current fixer | Entry/call site | Scope | Known bypass |
|---|---|---|---|---|---|---|---|

Explicitly validate:

```text
A: gateway kwargs -> coerce_gateway_nulls
B: inline script source -> _fix_javascript_booleans
C: sandbox .py S3 writes -> S3ManagerWrapper.put sanitization
D: HTML script blocks -> sanitize_html_booleans
```

Add any current vector not represented above. If one no longer exists, use
`NOT_PRESENT`.

### 12.2 Vector A - gateway kwargs

Paste complete `coerce_gateway_nulls` and every active MCP tool-entry call
site. Return:

| Input token/container | Output | Recursion depth | Key-dependent | Substring-safe | Evidence |
|---|---|---:|---|---|---|

Include exact handling for:

```text
"null"
"None"
"none"
"NULL"
"true"
"false"
""
"yes"
"no"
"0"
bytes
list
tuple
dict
nested list
```

Return all tools with optional parameters that do not call the fixer.

### 12.3 Vector B - inline script source

Paste complete `_fix_javascript_booleans` and its direct helpers. Separate
tokenize and AST/f-string passes. Return:

| Source construct | Rewritten | Result | Failure behavior | Test evidence |
|---|---|---|---|---|

Include identifiers, strings, comments, f-string interpolation, nested
f-strings, format specs, conversions, walrus expressions, ternaries,
attributes, longer identifiers, syntax errors, and repeated passes.

### 12.4 Vector C - `.py` writes

Paste the complete wrapper `.py` branch and the called sanitizer. Answer:

1. Which input object types are decoded/sanitized?
2. Is extension matching case-sensitive?
3. Are compressed, extensionless, or query-suffixed paths covered?
4. Is sanitation failure fail-open?
5. Is source re-encoded identically?
6. Is the sanitizer run before artifact tracking and raw `put`?
7. Which paths bypass the wrapper?

### 12.5 Vector D - HTML/JavaScript

Paste the complete `sanitize_html_booleans` implementation and every active
caller. Return:

| HTML/JS construct | Rewritten | Scope guard | Known over-rewrite | Active caller |
|---|---|---|---|---|

Determine whether it is still explicit, has become automatic, or is unused.
Do not repeat dashboard rendering internals.

### 12.6 JavaScript/Python boundary search

Search active Python, HTML-template, and emitted-JavaScript source for:

```text
repr(
json.dumps(
True
False
None
null
true
false
<script
sanitize_html_booleans
```

Return only executable/template boundary sites where Python values become
JavaScript or JSON:

| Producer path/line | Serialization method | Consumer | Sanitizer | Current risk | Verdict |
|---|---|---|---|---|---|

### 12.7 Raw-singleton and subprocess bypasses

Exhaustively search both roots for direct imports/use of raw `s3_manager`
outside the sandbox wrapper. For every `.py` or `.html` write path, return:

| Writer path/symbol | Process | Manager object | Extension(s) | Sanitized | Wrapper bypass | Evidence |
|---|---|---|---|---|---|---|

Explicitly cover cron/jobs, reports, tickets, dashboard refresh, email, and
developer/subprocess tools. This is source mapping only; do not run them.

## 13. Adjacent active `prism_mcp.utils` contracts

### 13.1 Scope from actual imports/callers

Starting from `script_exec_tools.py`, its direct wrappers, storage/artifact
path, and error path, enumerate every imported `prism_mcp.utils` module and
symbol. Also include active utility symbols imported by the current chart
payload boundary only where `script_exec_tools.py` imports or wraps them.

Return:

| Utility module | Symbol | Exact signature/type | Direct caller | Namespace-injected | Still active |
|---|---|---|---|---|---|

Do not catalog unrelated utility modules merely because they exist.

### 13.2 Signatures and return/error contracts

For every active symbol in section 13.1, paste exact signature and complete
docstring. Return:

| Symbol | Return type/shape | Side effects | Raises/fail-safe | Hidden singleton/global | Source |
|---|---|---|---|---|---|

At minimum, inspect current active contracts in:

```text
error_handler.py
download_links.py
param_validator.py
code_preprocess_utils.py
unit_helper_functions.py
vision_functions.py
chart_functions_studio.py
output_limits.py
```

Use `NOT_PRESENT` for a file/symbol no longer used by this execution
boundary.

### 13.3 Historical five-module claim

The local `prism/mcp-utils.md` historically scopes itself to:

```text
error_handler.py
download_links.py
unit_helper_functions.py
vision_functions.py
chart_functions_studio.py
```

Return a diff showing which remain active, which signatures changed, and
which additional utility modules are now load-bearing for execution/storage.
Do not broaden the proposed documentation scope beyond evidence from direct
imports/callers.

## 14. Generic execution validation using dashboard paths

Do not repeat the dashboard-specific namespace audit from the prior prompt.
Do not inspect the dashboard compiler API, portal, refresh orchestration,
assets, registry/status schemas, or deployment wiring.

Use current dashboard-related code only to test these generic claims:

1. Top-level `execute_analysis_script` has one dashboard injection block.
2. Injected dashboard callables use the same generic namespace, session,
   artifact, stream, and error lifecycle as other sandbox callables.
3. Persisted dashboard scripts and clean refresh subprocesses are separate
   execution boundaries and may bypass top-level wrapper, AST, artifact, or
   sanitizer behavior.
4. Raw S3 manager use outside `execute_analysis_script` is not covered by
   `S3ManagerWrapper`.

Return:

| Generic principle | Top-level sandbox | Persisted/in-process path | Clean subprocess path | Verdict | Evidence |
|---|---|---|---|---|---|

Paste only the top-level dashboard namespace block and the minimal complete
call sites proving whether separate execution paths use the wrapper/raw
manager. Refer unresolved dashboard-specific detail back to the earlier
audit; do not duplicate it.

## 15. Current behavior, proposals, and known gaps

Return three strictly separated tables.

### 15.1 Current implemented behavior

| Behavior | Executable source | Active caller | Test coverage |
|---|---|---|---|

Include only behavior reachable in the current checkout.

### 15.2 Proposals/TODOs not implemented

| Proposal/TODO | Source/comment | Missing implementation evidence | Superseded |
|---|---|---|---|

Do not phrase a proposal as current behavior.

### 15.3 Known gaps and bypasses

| Gap | Proven affected path | Current consequence | Existing test | Proposed fix, if source states one |
|---|---|---|---|---|

At minimum, resolve the historical candidates:

```text
wrapper-level .py sanitization integration test
HTML sanitization explicit-only
raw singleton/subprocess bypass
edit_ai_repo sanitization residuals
timeout thread continuing after join
wrapper s3_client bypass
namespace/documentation drift
SESSION_PATH literal versus closure divergence
```

If a candidate is fixed or absent, use the formal verdict
`CONTRADICTS` or `NOT_PRESENT` in an adjacent verdict column.

## 16. Diff against local historical claims

The local historical references currently claim:

1. `execute_analysis_script` is the sole MCP Python-execution tool.
2. It executes via `exec` in a prebuilt namespace of roughly 110 names.
3. Timeout is approximately 60 seconds and uses a thread/join wrapper.
4. `SESSION_PATH` is not injected; emitted scripts define the literal path.
5. A closure-captured `session.base_path` is still injected into wrapped
   helpers.
6. Three S3 singletons exist: general, personal, and legacy unsecured.
7. Sandbox `s3_manager` is an explicit wrapper without `__getattr__`.
8. Raw `S3BucketManager.get` returns bytes and successful `put` returns
   `None`.
9. Wrapper `put` tracks artifacts and auto-sanitizes `.py` source.
10. Download links may copy from secured/general storage to legacy unsecured
    storage before presigning.
11. stdout and stderr are captured around `exec`.
12. ordinary execution errors email; timeout does not.
13. preprocessing blocks raw matplotlib, local file operations, full S3
    listings, and Excel anti-patterns.
14. gateway parsing uses `ast.literal_eval` and creates a start-with-letter
    final-response constraint.
15. boolean/null handling has four vectors A-D, with A-C automatic and D
    explicit.
16. subprocess writers using raw singletons bypass wrapper sanitization and
    artifact tracking.
17. the historical `mcp-utils.md` five-module scope does not include every
    utility now load-bearing for execution.

Return:

| Claim | Current fact | Changed/unchanged | Evidence | Verdict |
|---|---|---|---|---|

`Changed/unchanged` may contain only `CHANGED`, `UNCHANGED`, or `UNKNOWN`;
the formal verdict remains one of the four fixed verdict values.

## 17. Prompt-specific contradiction ledger

Complete every row:

| ID | Local assumption | Verdict | Current production fact | Exact evidence |
|---|---|---|---|---|
| C01 | The active tool lives at `prism-core/prism_mcp/tools/script_exec_tools.py`. | | | |
| C02 | `execute_analysis_script` is the sole L1 Python execution surface. | | | |
| C03 | The exact signature/docstring returned here matches current MCP registration. | | | |
| C04 | All input modes pass through the same preprocessing and checks. | | | |
| C05 | Timeout uses a thread/join and is not a hard process kill. | | | |
| C06 | A timed-out target cannot mutate storage after the tool returns. | | | |
| C07 | The namespace inventory returned here is exhaustive. | | | |
| C08 | Every injected wrapped callable has its hidden parameters documented. | | | |
| C09 | `SESSION_PATH` is not a namespace key. | | | |
| C10 | Scripts define `SESSION_PATH` from the path returned/adopted by context/session state. | | | |
| C11 | Wrapper closures use the same `session.base_path` independently of the script literal. | | | |
| C12 | One-conversation/one-session is code-enforced rather than instruction-only. | | | |
| C13 | Exactly three exported S3 manager roles remain current. | | | |
| C14 | Sandbox general storage is wrapped; personal storage exposure is separately defined. | | | |
| C15 | `S3ManagerWrapper` has no general `__getattr__` forwarding. | | | |
| C16 | Raw `S3BucketManager.get` always returns bytes. | | | |
| C17 | Successful raw/wrapped `put` returns `None`. | | | |
| C18 | All sandbox-originated artifacts are tracked. | | | |
| C19 | Download-link generation has storage side effects. | | | |
| C20 | stdout and stderr emitted before an exception are retained. | | | |
| C21 | Timeouts do not call `send_error_email`. | | | |
| C22 | `execute_analysis_script` never auto-creates a ticket. | | | |
| C23 | Pre-execution checks cover every category listed in section 10.2. | | | |
| C24 | The gateway still uses `ast.literal_eval` in the active route. | | | |
| C25 | Start-with-letter and ASCII-only guidance reflects current implementation. | | | |
| C26 | Vector A covers every MCP tool with optional parameters. | | | |
| C27 | Vector B handles bare tokens and f-string interpolations without rewriting strings/comments. | | | |
| C28 | Vector C applies only to sandbox wrapper `.py` writes. | | | |
| C29 | Vector D remains explicit rather than automatic. | | | |
| C30 | Raw singleton and subprocess writes bypass wrapper tracking/sanitization. | | | |
| C31 | The active `prism_mcp.utils` table in this reply covers every direct execution/storage dependency. | | | |
| C32 | Dashboard-adjacent paths validate the generic separation between top-level sandbox and subprocess execution. | | | |
| C33 | Current behavior, proposals, and known gaps are fully separated in this reply. | | | |

For every `CONTRADICTS` or `UNKNOWN` row, name the exact local fold target
that should remain untrusted pending reconciliation:

```text
prism/code-sandbox.md
prism/mcp-utils.md
prism/gateway.md
prism/boolean-sanitization.md
prism/session-hygiene.md
prism/security.md
prism/architecture.md
```

Do not propose or perform edits.

## 18. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
FRESHNESS_IDENTITY_COMPLETE:
EXECUTION_FILE_GRAPH_COMPLETE:
TOOL_SIGNATURE_COMPLETE:
RETURN_CONTRACT_COMPLETE:
INPUT_MODE_PRECEDENCE_COMPLETE:
EXECUTION_LIFECYCLE_COMPLETE:
NAMESPACE_INVENTORY_COMPLETE:
WRAPPER_CHAINS_COMPLETE:
PROCESS_TIMEOUT_BEHAVIOR_COMPLETE:
IMPORT_BEHAVIOR_COMPLETE:
SESSION_BASE_PATH_COMPLETE:
SESSION_PATH_SEMANTICS_COMPLETE:
SESSION_HYGIENE_ENFORCEMENT_COMPLETE:
S3_SINGLETON_INVENTORY_COMPLETE:
S3_PUBLIC_CONTRACTS_COMPLETE:
S3_WRAPPER_CONTRACT_COMPLETE:
ARTIFACT_TRACKING_COMPLETE:
DOWNLOAD_LINK_LIFECYCLE_COMPLETE:
STREAM_CAPTURE_COMPLETE:
ERROR_EMAIL_TICKET_BEHAVIOR_COMPLETE:
PREPROCESS_PIPELINE_COMPLETE:
AST_SECURITY_CHECKS_COMPLETE:
GATEWAY_PARSE_ROUTE_COMPLETE:
BOOLEAN_VECTOR_A_COMPLETE:
BOOLEAN_VECTOR_B_COMPLETE:
BOOLEAN_VECTOR_C_COMPLETE:
BOOLEAN_VECTOR_D_COMPLETE:
RAW_SINGLETON_BYPASSES_COMPLETE:
ACTIVE_MCP_UTILS_COMPLETE:
DASHBOARD_GENERIC_VALIDATION_COMPLETE:
CURRENT_VS_PROPOSALS_SEPARATED:
HISTORICAL_DIFF_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
SANDBOX_STORAGE_EXECUTION_REFRESH_COMPLETE:
```

`SANDBOX_STORAGE_EXECUTION_REFRESH_COMPLETE` may be `YES` only when every
preceding item is `YES`. If it is `NO`, list only unresolved
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
