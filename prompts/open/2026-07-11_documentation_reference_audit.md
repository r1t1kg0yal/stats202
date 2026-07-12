---
class: context-extraction
topic: documentation-reference-audit
status: PARTIALLY_FOLDED
created: 2026-07-11
reply_received: 2026-07-11
reply_source: cursor-chat screenshots (18 images, captured 2026-07-11 22:49-22:51 ET)
folded_on: 2026-07-11
unresolved:
  - prompts 1-5 were absent from the PRISM session, so cross-prompt synthesis and conflict checks could not run
  - local prism/.cursor/rules/staging/projects corpus was absent from the PRISM checkout, so local-reference and staleness-notice audit could not run
  - production browser reachability and CSP/proxy policy for jsDelivr XLSX/html2canvas dependencies
  - semantic classification of the dirty echart_studio.py +14/-8 working-tree delta
  - exact path of the single committed file differing between recorded and checked-out prism-core histories
  - full active stale-reference completeness and corpus-reactivation governance decision
sequence: 7/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_data_pull_contracts.md
  - staging/prompts/open/2026-07-11_user_ontology_dashboards.md
  - staging/prompts/open/2026-07-11_context_system_tool_routing.md
  - staging/prompts/open/2026-07-11_sandbox_storage_execution.md
  - staging/prompts/open/2026-07-11_data_ecosystem_world_state.md
  - staging/prompts/open/2026-07-11_interfaces_jobs_observatory.md
reply_folded_into:
  - prism/README.md
  - prism/codebase-tree.md
  - prism/_prompting-guide.md
  - prism/_changelog.md
  - .cursor/rules/prism.mdc
  - .cursor/rules/prism-freshness.mdc
  - .cursor/rules/viz-platforms.mdc
  - staging/README.md
  - projects/echarts/README.md
---

# Context-extraction prompt — documentation and reference audit

**Why this exists (staging-only note; do not paste this section into
PRISM):**

This is the final synthesis prompt in the seven-prompt documentation
freshness sequence. It should be sent only after replies to prompts 1-6 are
available. It uses those source-backed replies as its evidence base, searches
the current checkout for stale references, closes the two residual dashboard
questions left by
`2026-07-11_dashboard_architecture_validation.md`, and produces the routing
and contradiction ledgers needed to curate the local documentation.

The pasteable body deliberately does not repeat the completed dashboard
architecture inventory. It requests no code or documentation changes.

---

## Paste the following into PRISM

# Documentation and reference audit (read-only final synthesis)

You are being asked to perform the final source-backed synthesis for a
seven-prompt PRISM documentation freshness campaign. This is a pure read-only
context-extraction request.

The replies to these six preceding prompts are the primary evidence base:

```text
1. 2026-07-11_dashboard_data_pull_contracts.md
2. 2026-07-11_user_ontology_dashboards.md
3. 2026-07-11_context_system_tool_routing.md
4. 2026-07-11_sandbox_storage_execution.md
5. 2026-07-11_data_ecosystem_world_state.md
6. 2026-07-11_interfaces_jobs_observatory.md
```

The partially answered
`2026-07-11_dashboard_architecture_validation.md` is also an input. Its broad
dashboard layout, imports, consumers, context topology, Django routes,
refresh pipeline, schemas, and static-asset inventory have already been
answered. Do not rerun that architecture audit. Reinspect source only where
needed to:

1. classify a current stale-reference match;
2. obtain a current path-and-line citation;
3. close the two explicitly unresolved dashboard items in section 8; or
4. resolve a conflict among the prior replies.

If one or more replies to prompts 1-6 are unavailable in this conversation,
identify the missing dependency in `## Could not resolve`. Do not recreate
the missing broad audit inside this prompt.

Use `list_ai_repo`, repository search, direct source reads, Git read-only
commands, and narrowly bounded read-only introspection as needed. Do not
answer from memory.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify, create, copy, move, rename, or delete any
  repository file;
- run `git checkout`, `git switch`, `git reset`, `git clean`, `git pull`,
  `git fetch`, `git merge`, `git rebase`, `git submodule update`, or any
  command that changes either checkout or its index;
- install, upgrade, remove, or reconfigure a package;
- run a dashboard build, pull, compile, refresh, scheduled job, report,
  ingestion job, email job, or deployment entry point;
- invoke POST, PUT, PATCH, or DELETE endpoints;
- write, copy, move, or delete S3 objects;
- update a user manifest, dashboard registry, refresh status, session,
  memory, cabinet object, completion marker, or log object;
- create a ticket, background task, subprocess worker, dashboard, report,
  chart, or other user artifact;
- print secrets, credentials, cookies, authorization headers, user content,
  or user-identifying values.

Permitted operations are read-only: source/configuration reads, repository
search, `git status`, `git rev-parse`, `git ls-tree`, `git submodule status`,
`git diff`, hashing existing bytes, `inspect.signature`, and a narrowly
scoped unauthenticated HTTP `HEAD` or minimal `GET` solely for the CDN
reachability check in section 8.1. The network probe must send no cookies,
credentials, bearer tokens, Kerberos material, user data, or repository
content.

Do not propose or perform code or documentation edits. A recommended local
fold target is routing metadata for later human curation, not an edit
request.

## Reply protocol

1. Mirror every numbered section and subsection below.
2. Begin with checkout identity and a source-evidence index. Present source
   evidence before conclusions.
3. Cite the exact current repository path and inclusive line range for every
   source-backed claim. Use `path:start-end`, not an approximate location.
4. When evidence comes from a reply to prompts 1-6, identify the prompt
   number, its reply section, and the underlying current source citation.
   A prompt number alone is not evidence.
5. Where a source block is requested, paste only the smallest complete
   bounded block needed to establish the claim. Do not paste an entire large
   file, use `...`, reconstruct omitted code, or exceed 120 source lines in
   one block.
6. For search results, state the exact roots, literal strings or regular
   expressions, file-type filters, and exclusions used. Return every match
   as `path:line:source`. If output is grouped, list every occurrence; do not
   collapse an unlisted tail into “and others”.
7. If a root or file class cannot be searched exhaustively, mark the search
   `INCOMPLETE`, identify the omitted scope, and do not claim absence.
8. Redact secret and user-data values as `<REDACTED>`, while preserving key
   names, types, nesting, code paths, URL hosts/paths, and control flow.
9. Keep production source facts separate from local-document claims and
   user governance decisions.
10. Do not include a `Frictions` section.

Use only these fixed vocabularies:

**Evidence verdict**

```text
CONFIRMED
CONTRADICTS
UNKNOWN
NOT_PRESENT
```

**Reference status**

```text
CURRENT
STALE_ACTIVE
HISTORY_ONLY
ARCHIVE_ONLY
UNKNOWN
```

**Surface class**

```text
RUNTIME
LLM_CONTEXT
AGENT_DOC
HISTORY
ARCHIVE
```

`HISTORY_ONLY` and `ARCHIVE_ONLY` are not active defects. A reference is
`STALE_ACTIVE` only when a current runtime, current LLM-consumed context
module, current configuration/deployment surface, or current agent/developer
instruction can still direct behavior toward a retired path or false claim.

## 0. Freshness and checkout identity

### 0.1 Inspection identity

Return:

- current UTC inspection timestamp;
- absolute and repository-relative roots for `prism-main` and
  `prism-core`;
- current `prism-main` HEAD SHA;
- checked-out `prism-core` HEAD SHA;
- `prism-core` gitlink SHA recorded by current `prism-main` HEAD;
- whether checked-out and recorded `prism-core` SHAs match;
- dirty/clean state of each checkout, without printing file contents;
- exact read-only commands or APIs used.

Use current Git metadata. Do not copy identity values from the prior
dashboard reply.

### 0.2 Dependency reply availability

Return:

| Prompt | Reply available | Current source citations present | Conflicts with another reply | Usable for synthesis |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |
| 4 | | | | |
| 5 | | | | |
| 6 | | | | |

If the checkout identity in a prior reply differs from section 0.1, mark
every affected fact `UNKNOWN` until it is narrowly rechecked against the
current checkout.

## 1. Source-evidence index

Before classifying documentation, build a compact evidence index from the
current source citations underlying prompts 1-6 and the targeted reads in
this prompt.

Return:

| Evidence ID | Topic | Current source path and lines | Source kind | Established fact | Prompt reply source |
|---|---|---|---|---|---|

`Source kind` must be one of:

```text
executed Python
LLM context
configuration
deployment
developer documentation
Git metadata
read-only runtime probe
```

At minimum, index evidence for:

- repository/package roots and import path setup;
- dashboard/data-pull execution paths;
- user ontology/context/manifest ownership;
- context registry, loader, bundles, and specialization rules;
- sandbox namespace and `SESSION_PATH` behavior;
- S3 managers/wrappers and persistence schemas;
- client inventory and transport ownership;
- world-state and ingestion ownership;
- interfaces, jobs, Observatory, email/reporting, security/status, vision
  QC, development/evaluation infrastructure, and design principles;
- ECharts/XLSX/html2canvas browser dependencies;
- current job paths and activation cadence;
- current user-list, user-manifest, dashboard-registry, and S3 schema
  locations.

Do not restate the full prior replies. One row may cover multiple local
claims only when the cited source block proves all of them.

## 2. Exhaustive reference search

### 2.1 Required search roots

Search all current text-bearing files under these roots:

```text
<prism-main>/
<prism-main>/core/
<prism-main>/jobs/
<prism-main>/prism_meta/
<prism-main>/web/
<prism-main>/prism-core/prism_mcp/
<prism-main>/prism-core/context/
<prism-main>/prism-core/dashboards/
```

The `<prism-main>/` root search must include current:

- Python source;
- LLM-consumed Markdown/context;
- README and developer documentation;
- agent-facing instructions;
- JSON, YAML, TOML, INI, shell, service, cron, Docker, CI, package, and
  deployment configuration;
- URL/router and Django settings/templates;
- registry and bundle declarations;
- checked-in job launchers and entry points.

Exclude only:

```text
.git/
__pycache__/
*.pyc
node_modules/
.venv/
venv/
binary files
generated user/session/dashboard artifacts
vendored minified assets, except when checking their source URL/version
```

Do not exclude a directory merely because its name contains `archive`,
`history`, `legacy`, or `deprecated`; those matches must be found and
classified as `HISTORY` or `ARCHIVE`.

### 2.2 Required literal strings and patterns

Search every root in section 2.1 for all of the following. Use both slash
paths and dotted import forms where applicable.

**Retired repository and package roots**

```text
ai_development/
ai_development.
/ai_development
GS/viz/
GS/data/apis/
GS/frontend/
GS/knowledge/docstrings/
from ai_development
import ai_development
```

Also derive the complete current top-level package/root set from Git and
package/deployment configuration. Search for any additional retired package
root named by current comments, compatibility maps, migration notes, or
deprecation blocks. List the newly discovered pattern before reporting its
matches.

**Old Django and static-asset paths**

```text
ai_development/mysite
ai_development.mysite
mysite/mysite/
mysite/news/
mysite/news/static/js/echarts.js
web/backend_django/news/static/js/echarts.js
STATICFILES_DIRS
STATIC_ROOT
REPORT_SERVER_BASE
```

**Dashboard topology and path claims**

```text
dashboards_echarts
dashboards.md
dashboards_hub.md
dashboard spokes
6 spokes
six spokes
7 spokes
seven spokes
9 spokes
nine spokes
full hub
sole registered
MODULE_REGISTRY
context/registry.py
context/loader.py
prism-core/dashboards
jobs/hourly/refresh_dashboards.py
jobs/refresh_runner.py
ai_development/jobs
ai_development/dashboards
```

Use case-insensitive regular expressions that also catch claims where a
number and `spoke`, `module`, `context file`, or `Python file` are separated
by up to 100 characters.

**Client inventory, context registries, and bundles**

```text
mcp/clients
core/mcp/clients
17 clients
20 clients
24 clients
35 clients
client modules
client guides
MODULE_REGISTRY
MODULE_SPECS
bundle
bundles
specialization
end_user
developer
report_worker
orchestrator
instruments_guide_ir
prediction_markets_skill
```

Use case-insensitive regular expressions that catch any integer within 100
characters of `client`, `guide`, `module`, `registry`, or `bundle`, not only
the seed counts above.

**Sandbox/session claims**

```text
SESSION_PATH
session_path
inject SESSION_PATH
SESSION_PATH injection
namespace injection
script_exec_tools.py
execute_analysis_script
S3ManagerWrapper
s3_manager
s3_manager_unsecured
s3_manager_personal
```

For every `SESSION_PATH` match, distinguish:

1. an LLM-authored literal defined by the script;
2. an injected namespace key;
3. a closure/partial-bound `session_path` argument;
4. an internal wrapper field;
5. historical prose.

Do not treat these as equivalent.

**ECharts and public-surface claims**

```text
make_echart
EChartResult
compile_dashboard
echarts.js
echarts.min.js
cdn
cdnjs
jsdelivr
unpkg
XLSX
xlsx
html2canvas
_get_echarts_js
```

Search imports, namespace literals, `__all__`, context modules, emitted
HTML/JavaScript strings, templates, and developer documentation. A
definition inside `prism-core/dashboards/` is not by itself public usage.

**Jobs, schedulers, and cadence**

```text
refresh_dashboards.py
refresh_runner.py
entrypoint.py
fifteen_minute
15-minute
15 minute
5-minute
5 minute
hourly
daily
weekly
time.sleep
300
900
cron
schedule
systemd
supervisor
celery
```

Classify prose names separately from the actual deployment activation
source. A function named `fifteen_minute_*` is not evidence of its cadence.

**S3 and user-schema claims**

```text
secondary/sod/prism_users_list.json
prism_users_list.json
UserRegistry
UserManifestManager
users/
manifest.json
dashboards_registry.json
refresh_status.json
schema_version
owner_kerberos
history_retention_days
refresh_enabled
shared_at
dashboard pointer
user_ontology
user_context
memory
cabinet
```

Search schema writers and readers, not only examples. Do not print live user
records or S3 values.

### 2.3 Match classification

Return every match in one table:

| Match ID | Referencing path and line | Matched text/claim | Surface class | Reference status | Runtime/read path | Current canonical target or fact | Evidence ID |
|---|---|---|---|---|---|---|---|

Classification rules:

- executable source, active configuration, deployment manifests, and active
  launch scripts are `RUNTIME`;
- context loaded or fetchable by the LLM is `LLM_CONTEXT`;
- current README, developer, operator, or agent instruction is `AGENT_DOC`;
- changelogs, migration narratives, and explicitly historical sections are
  `HISTORY`;
- files under an archive root or explicitly immutable archival artifact are
  `ARCHIVE`;
- do not classify an archive or history match as `STALE_ACTIVE`;
- a legacy fallback branch in executable code is `RUNTIME`; report whether
  the branch is reachable and intentionally supported before assigning its
  reference status.

End this section with:

```text
SEARCH_ROOTS_EXHAUSTIVE: YES/NO
SEARCH_PATTERNS_COMPLETE: YES/NO
ALL_MATCHES_CLASSIFIED: YES/NO
```

## 3. Active stale-reference findings

Filter section 2.3 to `STALE_ACTIVE` only. Return:

| Finding ID | Active surface | Stale path or claim | Behavior it can misdirect | Current production fact | Production evidence | Recommended local fold target |
|---|---|---|---|---|---|---|

`Recommended local fold target` must name one of the existing topical or
meta documents listed in section 5. Do not ask for or perform an edit.

Then return separate lists for:

```text
RUNTIME_STALE_REFERENCES
LLM_CONTEXT_STALE_REFERENCES
AGENT_DOC_STALE_REFERENCES
```

Each list must contain match IDs, or `NONE`.

## 4. Current canonical file graph

Produce a current canonical graph grounded in Git, package/deployment
configuration, import roots, registries, and actual consumers.

### 4.1 Repository/package graph

Use a tree that includes at least:

```text
prism-main/
├── core/
│   └── mcp/clients/
├── jobs/
├── prism_meta/
├── web/backend_django/
└── prism-core/                    gitlink/submodule
    ├── prism_mcp/
    │   ├── tools/
    │   └── utils/
    ├── context/
    │   ├── registry/loader/assembler owners
    │   └── modules/
    └── dashboards/
```

Adjust this shape to the current source; do not preserve a node merely
because it appears above. For every node, cite its current path and its
owning checkout.

### 4.2 Ownership and activation table

Return:

| Canonical node/file | Owning checkout/package | Activated or loaded by | Public/runtime role | Superseded path(s) | Evidence |
|---|---|---|---|---|---|

Cover:

- MCP tools and sandbox;
- data helper implementations;
- external clients and proxy transport;
- context registry/loader/assembler and static/runtime modules;
- dashboard compiler and refresh runners;
- Django routes/templates/static assets;
- jobs/deployment activation;
- user registry/manifest/ontology/context;
- S3/storage wrappers;
- Observatory, email, reporting, world-state, gateway, security, vision, and
  evaluation/development owners found in prompts 1-6.

Do not include speculative destinations. If an owner is not established by
source, use `UNKNOWN`.

## 5. Topic-to-owner routing for the local curated corpus

Return exactly one row for every topical document currently indexed by the
local `prism/README.md`:

```text
architecture.md
codebase-tree.md
code-sandbox.md
mcp-tools.md
mcp-utils.md
gs-proxy.md
api-clients.md
vision-qc.md
dashboard-refresh.md
dashboards-portal.md
data-functions.md
world-state.md
security.md
gateway.md
boolean-sanitization.md
session-hygiene.md
competitive-spec.md
```

Use:

| Local topical doc | Current production source owner(s) | LLM-context owner, if different | Evidence prompt(s) | Freshness coverage | Current canonical paths | Recommended fold destination |
|---|---|---|---|---|---|---|

`Freshness coverage` must be one of:

```text
FULL
PARTIAL
NONE
UNKNOWN
```

Requirements:

- every row must cite current production source or explicitly state
  `UNKNOWN`;
- distinguish an implementation owner from an LLM-context owner;
- `competitive-spec.md` must separate inspectable internal capability facts
  from external competitor claims that repository introspection cannot
  verify;
- if the user system/ontology evidence does not fit cleanly in an existing
  topical owner, report the gap without inventing a new filename;
- identify overlaps where two local topical docs claim the same production
  owner and state which one should own routing versus implementation detail;
- cover all 17 rows even when a topic has no current production analog.

End with:

```text
README_TOPICAL_DOCS_COVERED: 17/17
TOPIC_OWNER_ROUTING_COMPLETE: YES/NO
```

## 6. Local staleness-notice audit

Evaluate these local governance notices against source coverage, but do not
treat governance as a production-source fact:

| Local notice | Current local claim |
|---|---|
| `prism/README.md:3-31` | `prism/` is historical by default; only bounded dashboard sections were refreshed in July. |
| `.cursor/rules/prism.mdc:8-42` | `prism/` orientation is no longer load-bearing; old `ai_development` paths require translation. |
| `.cursor/rules/prism-freshness.mdc:8-28` | the freshness loop is not being applied to `prism/`. |
| `staging/README.md:3-17` | `prism/` references and the broader project roster are no longer current. |
| `prism/_changelog.md:16-33` | `prism/` was deprecated as a maintained SSOT on 2026-05-15. |

Return:

| Notice | Evidence verdict today | Which source-backed clauses remain true | Which clauses become false after prompts 1-6 and this audit are folded | Additional evidence needed | Governance decision needed |
|---|---|---|---|---|---|

Rules:

- evidence being available does not itself update a local document;
- a staleness clause remains true until the relevant evidence is reviewed
  and folded into the local owner;
- a source cannot decide whether the user wants to reactivate local
  maintenance;
- do not recommend removing a notice wholesale when only some topics are
  refreshed;
- identify the exact topic rows from section 5 that still prevent a
  corpus-wide current claim.

## 7. Source facts versus governance decision

Return two clearly separated subsections.

### 7.1 Source-backed readiness

Answer:

```text
ALL_17_TOPICS_HAVE_CURRENT_SOURCE_EVIDENCE: YES/NO
ALL_ACTIVE_STALE_REFERENCES_IDENTIFIED: YES/NO
ALL_ROUTING_OWNERS_IDENTIFIED: YES/NO
CORPUS_CAN_TRUTHFULLY_DROP_HISTORICAL_BY_DEFAULT_TODAY: YES/NO
```

For every `NO`, cite the blocking row or unresolved evidence.

### 7.2 User governance decision

Do not infer this from code, a changelog, or the existence of the prompt
campaign. Present this exact decision separately:

```text
USER DECISION REQUIRED
Reactivate local prism/ as maintained infrastructure documentation after
the campaign evidence is reviewed and folded in? YES/NO
```

Then provide:

- a source-backed recommendation;
- the operational meaning of `YES` for freshness stamps, contradiction
  handling, routing ownership, and future context-extraction replies;
- the operational meaning of `NO` for preserving historical notices while
  retaining bounded current overlays;
- the specific staleness-notice clauses from section 6 that become false
  only under `YES` and only after their topic evidence is folded in.

Do not report the governance choice as `CONFIRMED` or `CONTRADICTS`.

## 8. Close the two unresolved dashboard items

This section is the only dashboard-source follow-up. Do not repeat the prior
architecture sections.

### 8.1 XLSX and html2canvas production behavior

Search current emitted dashboard/editor HTML and JavaScript, ECharts
rendering source, Django/static configuration, security policy, and
deployment configuration for:

```text
XLSX
xlsx
html2canvas
cdn
cdnjs
jsdelivr
unpkg
script.src
createElement("script")
createElement('script')
Content-Security-Policy
CSP
connect-src
script-src
proxy
egress
offline
```

Return:

| Dependency | Exact URL/version | Source path and lines | Load timing | Feature/action using it | Core dashboard dependency | Production policy allows host | Read-only reachability result | Offline/blocked behavior |
|---|---|---|---|---|---|---|---|---|

Requirements:

- distinguish initial dashboard display from optional export/snapshot
  actions;
- show whether code loads each library eagerly, lazily, or only after a
  user action;
- paste the complete bounded loader and error-handling blocks;
- identify whether a local/inlined copy exists;
- identify CSP, proxy, allowlist, egress, or browser policy evidence;
- if permitted, perform one unauthenticated read-only `HEAD` or minimal
  `GET` per unique host from the production environment and report UTC
  timestamp, status, final host after redirects, content type, and whether
  the bytes look like the requested library;
- do not claim production reachability from a source URL alone;
- do not claim offline support unless the required bytes are local/inlined
  or a source-defined cache/service-worker path proves it;
- state the exact user-visible and console behavior when each optional
  dependency cannot load.

End with evidence verdicts for:

```text
ECHARTS_CORE_DISPLAY_IS_SELF_CONTAINED:
XLSX_IS_OPTIONAL:
HTML2CANVAS_IS_OPTIONAL:
XLSX_PRODUCTION_REACHABILITY:
HTML2CANVAS_PRODUCTION_REACHABILITY:
OPTIONAL_ACTION_OFFLINE_BEHAVIOR_DOCUMENTED:
```

Use only `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, or `NOT_PRESENT`.

### 8.2 Recorded versus checked-out `prism-core`

Using current Git metadata, return:

| Item | SHA/value | Exact read-only command/source | Verdict |
|---|---|---|---|
| `prism-main` HEAD | | | |
| recorded `prism-core` gitlink | | | |
| checked-out `prism-core` HEAD | | | |
| match | | | |

If the SHAs differ:

1. identify ahead/behind/divergence relationship if both objects are
   available locally;
2. report commit subjects and timestamps for the recorded and checked-out
   commits;
3. list changed dashboard/context files between the two commits without
   dumping full diffs;
4. classify whether the mismatch is a detached checkout state, local
   uncommitted work, a different committed checkout, an unavailable object,
   or `UNKNOWN`;
5. state which identity is activated by the running/imported production
   process, with source/runtime evidence rather than assumption;
6. state whether the earlier installed-byte parity comparison is valid.

Do not reconcile, check out, fetch, or update the submodule.

### 8.3 `echart_studio.py` delta classification

If both commit objects and file versions are available, compare:

```text
<recorded prism-core commit>:dashboards/echart_studio.py
<checked-out prism-core commit>:dashboards/echart_studio.py
current working-tree prism-core/dashboards/echart_studio.py
```

Return:

| Comparison | Bytes/lines/SHA-256 each side | Changed functions/classes/constants | Delta class | Can alter runtime behavior | Relationship to checkout mismatch |
|---|---|---|---|---|---|

`Delta class` must be one or more of:

```text
EXECUTABLE_LOGIC
PUBLIC_EXPORT
SERIALIZATION
EMITTED_OPTION
ERROR_BEHAVIOR
IMPORT_PATH
DOCSTRING_COMMENT
WHITESPACE_ONLY
UNKNOWN
```

Do not paste the full diff. Paste only the smallest complete changed blocks
needed to justify the classification, with current path/line citations.

If a prior prompt's staging baseline hash is available, compare its stated
hash separately. Label it `PRIOR_PROMPT_BASELINE`; do not imply that it is a
Git commit or current production identity.

End with:

```text
SUBMODULE_IDENTITY_RESOLVED: YES/NO
ECHART_STUDIO_DELTA_CLASSIFIED: YES/NO
INSTALLED_PARITY_CLAIM_CURRENTLY_VALID: YES/NO
```

## 9. Final contradiction ledger

Link each local claim to current production evidence and its future fold
owner. Do not request or perform an edit.

Seed the ledger with these claims and add every additional
`STALE_ACTIVE`, `CONTRADICTS`, or `UNKNOWN` claim found in sections 2-8:

| ID | Local claim/location |
|---|---|
| C01 | `prism/README.md:5-12` — most curated material is historical, with only bounded July dashboard sections refreshed. |
| C02 | `.cursor/rules/prism.mdc:33-42` — there is no current `ai_development/` tree; PRISM uses a `prism-main`/`prism-core` split checkout. |
| C03 | `.cursor/rules/prism.mdc:71-82` and `prism/README.md:58-74` — old topical inventories, paths, client counts, registries, and bundles remain usable as historical routing. |
| C04 | `.cursor/rules/prism.mdc:120-124` — several project destinations still use retired `ai_development/...` paths. |
| C05 | `staging/README.md:235-244` — frontend, whitepaper, and Bloomberg destinations were not reverified after the split. |
| C06 | `prism/codebase-tree.md:1-353` — historical tree sections coexist with a bounded current dashboard overlay. |
| C07 | `prism/code-sandbox.md:470-521` and `prism/_changelog.md:248-266` — `SESSION_PATH` is script-defined, not a namespace-injected name. |
| C08 | `prism/README.md:64`, `.cursor/rules/prism.mdc:76`, and `staging/README.md:391-412` — local client counts and migration counts describe different dates/surfaces and may be stale. |
| C09 | `prism/README.md:172-176` and `.cursor/rules/prism.mdc:153-168` — Tier 1/Tier 2 catalogs, bundles, and special cases are historical unless prompts 3 and 6 reconfirm them. |
| C10 | `.cursor/rules/viz-platforms.mdc:158-184` and `projects/echarts/README.md:48-61` — ECharts inventory is installed but parity is open because recorded and checked-out submodule identities differ. |
| C11 | `.cursor/rules/viz-platforms.mdc:272-284` and `projects/echarts/README.md:268-280` — core ECharts display uses an inlined local asset; the old `mysite` path is only a legacy code candidate. |
| C12 | prior dashboard prompt section 10.2 — XLSX/html2canvas CDN reachability and offline behavior were unresolved. |
| C13 | `.cursor/rules/viz-platforms.mdc:630-640` and `projects/echarts/README.md:10-15` — `make_echart` is an internal builder, not a public one-off-chart surface. |
| C14 | `prism/_changelog.md:12` and current dashboard/job docs — local cadence/path prose must be reconciled with actual deployment activation. |
| C15 | `prism/architecture.md:576-833`, `prism/dashboards-portal.md:219-299`, and `prism/dashboard-refresh.md:151-260` — user-list, manifest, dashboard registry, status, sharing, and S3 schema claims need current source ownership. |
| C16 | `prism/README.md:3-31`, `.cursor/rules/prism.mdc:8-31`, `.cursor/rules/prism-freshness.mdc:8-26`, and `staging/README.md:3-15` — whether `prism/` becomes maintained again is a user governance decision, not a source inference. |

Return:

| ID | Local claim and exact local location | Surface class | Reference status | Evidence verdict | Current production fact | Production path/line evidence | Recommended fold target | Governance dependency |
|---|---|---|---|---|---|---|---|---|

Requirements:

- cite at least one current production source for each `CONFIRMED` or
  `CONTRADICTS` verdict;
- for `UNKNOWN`, identify the exact missing source, permission, dependency
  reply, or current object;
- retain historical and archive references when correctly labelled;
- distinguish a stale fact from a fact that was accurate at its dated
  freshness stamp;
- `Recommended fold target` must be an existing topical or meta owner from
  section 5 or the frontmatter routing list;
- do not use the ledger to ask PRISM to modify files.

End with:

```text
CONTRADICTION_LEDGER_COMPLETE: YES/NO
ACTIVE_DEFECTS_DISTINGUISHED_FROM_HISTORY: YES/NO
EVERY_STALE_LOCAL_CLAIM_LINKED_TO_PRODUCTION_EVIDENCE: YES/NO
```

## 10. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
CURRENT_CHECKOUT_IDENTITY_COMPLETE:
PROMPTS_1_TO_6_EVIDENCE_AVAILABLE:
SOURCE_EVIDENCE_INDEX_COMPLETE:
SEARCH_ROOTS_EXHAUSTIVE:
SEARCH_PATTERNS_COMPLETE:
ALL_MATCHES_CLASSIFIED:
ARCHIVES_NOT_FLAGGED_AS_ACTIVE_DEFECTS:
ACTIVE_STALE_REFERENCE_LIST_COMPLETE:
CURRENT_CANONICAL_FILE_GRAPH_COMPLETE:
README_TOPICAL_DOCS_COVERED_17_OF_17:
TOPIC_OWNER_ROUTING_COMPLETE:
STALENESS_NOTICES_ASSESSED:
SOURCE_FACTS_SEPARATED_FROM_GOVERNANCE:
XLSX_HTML2CANVAS_BEHAVIOR_RESOLVED:
SUBMODULE_IDENTITY_RESOLVED:
ECHART_STUDIO_DELTA_CLASSIFIED:
CONTRADICTION_LEDGER_COMPLETE:
DOCUMENTATION_REFERENCE_AUDIT_COMPLETE:
```

`DOCUMENTATION_REFERENCE_AUDIT_COMPLETE` may be `YES` only if every
preceding item is `YES`. If it is `NO`, list only the unresolved
section/subsection numbers and the missing source, dependency reply, Git
object, permission, or production reachability evidence.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and what
blocked it.
