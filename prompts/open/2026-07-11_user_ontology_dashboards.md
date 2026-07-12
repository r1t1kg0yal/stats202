---
class: context-extraction
topic: user-ontology-dashboards
status: PARTIALLY_FOLDED
created: 2026-07-11
reply_received: 2026-07-11
reply_source: cursor-chat screenshots (18 images, captured 2026-07-11 22:46-22:48 ET)
folded_on: 2026-07-11
unresolved:
  - exact kerberos-passing get_context caller shapes for email, report-worker, orchestrator, Teams, and web
  - exact equality of Community-discovery and scheduled-refresh identity sets
  - dashboard-to-usage/activity telemetry writer edge
sequence: 2/7
depends_on:
  - staging/prompts/open/2026-07-11_dashboard_architecture_validation.md
  - staging/prompts/open/2026-07-11_dashboard_data_pull_contracts.md
reply_folded_into:
  - prism/architecture.md
  - prism/dashboards-portal.md
  - prism/dashboard-refresh.md
  - prism/code-sandbox.md
  - prism/README.md
---

# Context-extraction prompt — user ontology and dashboards

**Why this exists (staging-only note; do not paste this section into
PRISM):**

The current curated architecture says `user_context` exposes memories,
cabinet state, and a dashboard roster, while the user manifest carries a
dashboard registry pointer that scheduled refresh updates but on-demand
refresh does not. It does not yet establish how the live `user_ontology`
module relates to that runtime context, which identity source governs each
surface, or whether dashboard creation, viewing, sharing, and refresh are
part of PRISM's persistent user model or merely linked artifacts.

This prompt asks for schemas and writer/reader graphs, never a user's
actual values. Fold the reply only into the `prism/` paths listed above.
Do not change the ECharts authoring context unless the evidence proves a
contract that changes dashboard authoring behavior; no ECharts context file
is a default fold target.

---

## Paste the following into PRISM

# User ontology and dashboards (read-only)

Inspect the current live implementation. This is a source-first,
read-only context-extraction request. Do not answer from memory, prior
conversation, staging documentation, inferred product semantics, or sample
user records. Executable source, active context registry/configuration, and
current templates are primary. Existing S3 objects may be inspected only
for redacted schema confirmation when source alone cannot establish shape.

The prior dashboard architecture validation already established the broad
dashboard package, portal route, registry, status, and refresh topology.
Do not repeat that global audit. Focus on the user-model boundary:
`user_ontology`, runtime `user_context`, identity, pointer graphs,
personalization/memory, dashboard roster exposure, and cross-user access.

Use `list_ai_repo`, repository search, direct source reads, and narrowly
scoped read-only introspection through `execute_analysis_script` as needed.

## Non-mutation contract

Do not:

- call `edit_ai_repo` or modify any repository or context file;
- call memory, profile, cabinet, manifest, process, dashboard, sharing, or
  registry mutation helpers;
- invoke dashboard build, pull, refresh, compile, registration, or runner
  entry points;
- issue POST/PUT/PATCH/DELETE requests;
- write, copy, move, or delete local or S3 objects;
- create a session, chat, thread, memory, profile, process, dashboard,
  report, ticket, completion marker, cache entry, or log object;
- authenticate as another user, change permissions, or test access by
  fetching another user's protected content;
- enumerate, quote, summarize, or infer actual user values.

Read definitions, registry entries, templates, schemas, and existing
metadata only. If safe schema confirmation requires an existing object,
return keys, types, cardinality classes, nullability, and redacted path
grammar only. Never return names, kerberos IDs, email addresses, profile
content, memories, chat/thread text, filenames, dashboard titles, tags,
descriptions, source identifiers, or usage history.

## Reply protocol

1. Mirror every numbered section and subsection below.
2. Cite the exact current path and line range for every source-backed
   claim. Use current split-checkout paths; identify any live legacy alias
   separately.
3. Paste requested source as complete bounded verbatim blocks in fenced
   code blocks. Never use `...`, reconstructed snippets, or prose
   placeholders inside a requested block.
4. Never paste an entire large file. A bounded block is one complete
   registry entry, schema/dataclass, generator, helper, decorator, view,
   or contiguous writer/reader call site. If a definition exceeds 150
   lines, return its signature and only the complete relevant branches,
   each with exact line ranges.
5. For each search, state every searched root, exact
   literal/regex/glob pattern, exclusions, and whether it completed.
   Return each relevant match as `path:line:source`.
6. Distinguish source-defined schema from a redacted observed schema,
   static context from runtime-generated context, and identity from
   authorization.
7. Redact secrets, tokens, cookies, credentials, personal data, user
   content, proprietary identifiers, and live values. Preserve field names,
   types, nullability, path grammar, import names, control flow, and access
   checks. Use `<REDACTED>` only for values, never for keys.
8. Use only these verdicts where a verdict is requested:
   `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, `NOT_PRESENT`.
9. If sources conflict, show all conflicting paths and line ranges. Do not
   silently select one, and do not infer an access rule from UI visibility.

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

Do not repeat installed dashboard inventory or parity results. If Git
metadata is unavailable, return `UNKNOWN`.

## 1. Complete source discovery

### 1.1 Search roots

Search all active executable, context, portal, and job code under:

```text
prism-main/core/
prism-main/jobs/
prism-main/web/
prism-main/email/
prism-main/report_generation/
prism-main/entrypoint.py
prism-main/prism-core/context/
prism-main/prism-core/prism_mcp/
prism-main/prism-core/dashboards/
```

Include current templates and JavaScript only where they read identity,
ownership, sharing, visibility, or dashboard-roster state.

Exclude `.git/`, caches, bytecode, generated documentation, archived
trees, test fixtures, logs, session artifacts, vendored packages, and
historical context snapshots. Report missing roots rather than substituting
retired paths.

### 1.2 Search patterns

Search definitions, registry/config entries, imports, calls, string keys,
paths, and templates with at least:

```text
\buser_ontology\b
\buser_ontology_context\b
\buser_context\b
\bUserManifestManager\b
\bUserRegistry\b
\bget_all_kerberos_ids\b
\bget_user_info\b
\bresolve_email\b
\bis_authorized\b
\bupdate_[A-Za-z0-9_]+_pointer\b
\bmanifest\.json\b
\bmemories\.json\b
\bcabinet(?:_manifest)?\b
\bscheduled_processes\b
\bdashboards_registry\.json\b
\bprofile\b
\bmemories\b
\bcabinet\b
\bsessions\b
\bchats\b
\bthreads\b
\bdashboards\b
\bshared\b
\bshared_at\b
\bvisibility\b
\bcommunity\b
\bobservatory\b
\bfranchise\b
\bkerberos\b
\brequest\.user\b
\bREMOTE_USER\b
\brequire_auth\b
\badd_memory\b
\bbatch_add_memories\b
\bedit_memory\b
\bretrieve_memories\b
\bupdate_user_manifest\b
users/\{?[A-Za-z0-9_]+\}?/
secondary/prism_observations/dashboards
```

Also search for semantic aliases, dynamic imports, module IDs, generator
names, bundle membership, trigger descriptions, and path constants that
ordinary symbol search would miss.

### 1.3 Source inventory

Return:

| Concern | Definition/config path:lines | Runtime owner | Writer(s) | Reader(s) | Identity input | Storage/context output |
|---|---|---|---|---|---|---|

Include at least:

```text
user_ontology module
user_context runtime module
context registry row(s)
assembler auto-include logic
loader runtime-generator path
user manifest
profile
memories
cabinet and cabinet manifest
sessions
chats
threads/email processes
scheduled processes
dashboard pointer
dashboard registry
Community sharing fields
Observatory dashboard registry
Franchise roster
UserRegistry
Django authentication/authorization identity
```

## 2. Context registry, bundles, triggers, and loading

### 2.1 Exact registration

Paste the complete active registry entries for `user_ontology` and
`user_context`, including any aliases or composite membership. Return:

| Module ID | Generator/file | Content type | Tier | Pillar | Bundle(s) | Required kwargs | Size hint | Description |
|---|---|---|---|---|---|---|---|---|

If either module is generated or registered under a different current ID,
show the exact mapping. Do not infer from filename.

### 2.2 Selection and trigger behavior

Paste the bounded assembler/context-tool blocks that determine:

- whether `kerberos` auto-includes `user_context`;
- whether `user_ontology` is always loaded, bundle-loaded, query-selected,
  explicitly included, or never reachable;
- specialization-specific inclusion/exclusion;
- composite expansion and deduplication;
- trigger phrases or L1 routing instructions;
- missing-kerberos behavior;
- whether email, report worker, orchestrator, developer, Teams, and web
  paths pass the same user identity into `get_context`.

Return a truth table:

| Invocation/interface | Kerberos present | Specialization/bundle | `user_context` loaded | `user_ontology` loaded | Trigger/source |
|---|---:|---|---:|---:|---|

Use only source-proven invocation shapes. Do not fabricate an interface row
when its `get_context` caller cannot be found.

### 2.3 Loader behavior

Paste the complete bounded loader branches for static and runtime modules,
including generator import, kwargs dispatch, error handling, and caching.
Resolve:

1. Is either module cached across users or requests?
2. Is runtime output generated once per message, process, session, or
   loader call?
3. What exact kwargs reach each generator?
4. What happens when a generator fails or returns empty content?
5. Can one user's generated context be reused for another user?

## 3. Live `user_ontology` contract

### 3.1 Module identity and source

Identify the exact current module implementing `user_ontology`. Paste:

- its complete public generator/entrypoint;
- its imports and path constants;
- each complete helper that materially changes the returned schema or
  content;
- its module/registry metadata.

Do not paste long static prose unrelated to dashboards. If the ontology is
a static context file, paste only its complete schema and dashboard-related
sections, with headings and exact line ranges.

### 3.2 Ontology purpose and schema

Return a source-backed schema table:

| Ontology concept/field | Type/shape | Required/null behavior | Source of value | Persistent storage | Writer | Reader/consumer | Dashboard relationship |
|---|---|---|---|---|---|---|---|

Determine whether the ontology describes:

- storage layout only;
- a machine-readable user schema;
- personalization semantics;
- identity and authorization;
- memories and preferences;
- artifact pointers;
- dashboard concepts, ownership, or sharing;
- writer/reader APIs;
- a mixture of these.

Do not answer conceptually until the source packet is complete.

### 3.3 Dashboard treatment

Paste every bounded `user_ontology` block that names dashboards, dashboard
registries, sharing, Community, Observatory, Franchise, ownership, or
manifest pointers. Then answer:

1. Is a dashboard a first-class ontology entity, a manifest pointer, a
   cabinet-like artifact, a session artifact, a process output, or only a
   path convention?
2. Does the ontology distinguish dashboard owner, viewer, author,
   publisher, and system owner?
3. Does it define lifecycle states, visibility, freshness, tags, cadence,
   provenance, or access rights?
4. Does it describe per-user dashboards only, or all portal categories?
5. Is its dashboard description executable, LLM guidance, or both?

Use the fixed verdict vocabulary for each answer, followed by source
evidence.

## 4. Runtime `user_context` contract

### 4.1 Generator and dependencies

Paste the complete current `generate(**kwargs)` or equivalent public
entrypoint and each bounded helper that loads:

```text
profile
memories
cabinet
recent sessions
chats
threads
scheduled processes
dashboards
```

If a category is not loaded, mark it `NOT_PRESENT`; do not assume it is
covered by another summary.

For every source read, return:

| Context section | S3/filesystem path grammar | Manager/bucket | Reader function | Limits/sorting | Freshness source | Failure behavior |
|---|---|---|---|---|---|---|

### 4.2 Exact rendered structure

Return a fully redacted structural rendering of `user_context`:

- preserve headings, key names, field names, type placeholders,
  conditional sections, ordering, caps, and omission rules;
- replace every actual value with typed placeholders such as
  `<string>`, `<timestamp>`, `<integer>`, or `<redacted-item>`;
- do not include actual paths containing a kerberos/dashboard/session ID;
- do not quote memory, profile, chat, cabinet, process, or dashboard text.

If rendering requires a user record, use static source analysis or a
synthetic in-memory object that performs no writes. Do not read a real
user's content merely to produce an example.

### 4.3 Dashboard roster exposure

Trace exactly how the runtime context obtains and renders dashboards:

```text
kerberos
  → user manifest dashboard pointer?
  → dashboards_registry.json?
  → dashboard entries
  → rendered L2 roster
```

Return:

| Roster field exposed to LLM | Source field/path | Required/default | Filtering/sorting/cap | Staleness risk | Writer |
|---|---|---|---|---|---|

Resolve:

- whether `user_context` trusts the user-manifest pointer, follows its
  `registry_path`, reads the canonical registry directly, or combines both;
- whether it exposes count only, titles/IDs, status, cadence, tags,
  sharing, freshness, portal URL, or another shape;
- whether disabled, failed, manual, shared, or stale dashboards are
  filtered;
- whether Community, Observatory, Franchise, or system-owned dashboards
  appear in the user's runtime context;
- whether registry and manifest-pointer disagreement is visible.

## 5. Persistent user pointer graph

### 5.1 Canonical manifest schema

Paste the complete source-defined user-manifest schema/default constructor
and each dashboard-related schema block. If no formal schema exists,
return a redacted observed key/type/nullability skeleton only after source
search proves the absence of a formal schema.

Return one row per pointer family:

| Pointer | Exact schema | Canonical target grammar | Writer(s) | Reader(s) | Update trigger | Aggregate fields | Stale when |
|---|---|---|---|---|---|---|---|

Include:

```text
profile
memories
cabinet
sessions
chats
threads
scheduled_processes
dashboards
```

If sessions are not a manifest pointer in the live schema, say
`NOT_PRESENT` and show their actual discoverability path.

### 5.2 Writer graph

Paste every complete `UserManifestManager.update_*_pointer` signature and
only the bounded body branch that writes its pointer. For each method,
return all executable callers across both roots:

```text
caller → update method → pointer fields → underlying source counted/read
```

Search direct calls, aliases, dynamic dispatch, string method names,
scheduled jobs, request handlers, sandbox partials, and background workers.

### 5.3 Reader graph

For each pointer, identify all active readers and whether they:

- trust aggregate fields;
- dereference a target path;
- bypass the pointer and read a canonical path directly;
- tolerate missing/stale fields;
- repair the pointer;
- expose the result to the LLM or UI.

Return:

```text
stored object → pointer writer → manifest pointer → reader → exposed surface
```

Use one edge per line with exact path/line citations.

### 5.4 Dashboard-specific write chronology

Trace source-backed chronology for:

```text
dashboard first creation/build
registry registration
on-demand browser refresh
scheduled refresh
share/unshare
rename/edit
disable/delete/archive, if live
```

For each event, state whether it updates:

```text
dashboard registry
per-dashboard status
user manifest dashboard pointer
user_context output on next load
user_ontology storage
memory store
usage/activity store
```

Use `CONFIRMED`, `CONTRADICTS`, `UNKNOWN`, or `NOT_PRESENT` in every cell.

## 6. Identity, authentication, ownership, and authorization

### 6.1 Identity sources

Paste bounded definitions and call sites for:

- `UserRegistry` load, cache/reset, user enumeration, lookup, email
  resolution, and authorization methods;
- Django's authenticated kerberos extraction;
- `_get_prism_users` or current equivalent;
- page decorators and JSON-endpoint authorization checks;
- dashboard owner/author derivation;
- sandbox/get-context kerberos propagation;
- any system-owner identity convention.

Return:

| Identity concept | Source | Canonical key | Cache/filter | Used for | Can diverge from |
|---|---|---|---|---|---|
| registered user | | | | | |
| active/authorized web user | | | | | |
| authenticated viewer | | | | | |
| dashboard author/owner | | | | | |
| context user | | | | | |
| system/Observatory owner | | | | | |

### 6.2 `UserRegistry` versus Django auth

Resolve with exact source:

1. Whether `UserRegistry` includes inactive records.
2. Whether Django filters on `active`.
3. Cache lifetime and invalidation for each.
4. Whether a registered but inactive/system identity is refreshed by jobs.
5. Whether that identity can authenticate or receive `user_context`.
6. Whether dashboard ownership requires registration.
7. Whether Community discovery and scheduled refresh enumerate the same
   identity set.
8. Whether a Django-authenticated identity can diverge temporarily from
   `UserRegistry` due to caching.

### 6.3 Access boundaries

Return one row per read or write surface:

| Surface | Viewer identity | Owner identity | Read condition | Write condition | Sharing effect | Source enforcement |
|---|---|---|---|---|---|---|

Include own dashboard list/detail, Community list/detail, Observatory,
Franchise, refresh start/status, live data polling, share toggle, registry
read/write, user manifest, `user_context`, memories, cabinet, and scheduled
refresh.

Do not test access with live requests. Source inspection only.

## 7. Dashboard categories and persistent-model placement

### 7.1 Category matrix

Return:

| Category | Canonical storage/authority | Owner identity | Discovery path | Visibility field/check | Reader/view | Writer/refresher | Appears in user manifest | Appears in user context | Appears in user ontology |
|---|---|---|---|---|---|---|---|---|---|

Include:

```text
per-user private
Community/shared user
Observatory
Franchise/report-server
system-owned user namespace, if live
```

Do not collapse Community into a separate storage schema if source proves it
is a visibility state on a user dashboard. Do not infer a system-owned
category merely because the architecture permits an inactive registry
entry; distinguish implemented, configured, and hypothetical.

### 7.2 Sharing and visibility schemas

Paste the complete bounded schema/write/read blocks for every dashboard
sharing or visibility field. Include defaults, missing-field behavior,
timestamps, listing filters, direct-detail checks, and author-only mutation.

Search for:

```text
shared
shared_at
visibility
published
community
public
private
owner
author
viewer
```

State whether any sharing/visibility field exists in:

```text
user manifest
dashboard registry
manifest_template.json / manifest.json
user ontology
user context
Django/session identity
```

### 7.3 Conceptual and operational classification

Based only on the verified graphs, classify dashboards in two ways:

1. **Conceptual:** what persistent role do dashboards play in PRISM's model
   of a user?
2. **Operational:** which stores, pointers, contexts, registries, and access
   checks actually implement that role?

Use this fixed classification table:

| Candidate role | Verdict | Source-backed reason |
|---|---|---|
| first-class user entity | | |
| linked persistent artifact | | |
| cabinet artifact | | |
| session artifact promoted to persistence | | |
| scheduled process output | | |
| personalized context input | | |
| social/community publication | | |
| Observatory/system artifact | | |
| external Franchise product | | |

The answer may confirm multiple roles at different layers. Do not force one
label when storage and product semantics differ.

## 8. Personalization, memory, and dashboard feedback

### 8.1 Memory surface and triggers

Paste bounded source/config/context blocks that define:

- memory CRUD helpers and sandbox pre-binding;
- memory retrieval into `user_context`;
- proactive trigger instructions such as “remember”, preference,
  correction, or self-context;
- automatic memory extraction or consolidation, if present;
- memory limits, deduplication, timestamps, and user scoping;
- any profile-personalization trigger separate from memory.

Return:

| Event/trigger | Automatic or LLM-decided | Writer/API | Persistent target | Added to next user context | Dashboard relevance |
|---|---|---|---|---|---|

### 8.2 Dashboard-to-user-model writes

Search all executable writers for direct or indirect edges from:

```text
dashboard create/build/register
dashboard view/open
dashboard edit
dashboard refresh
dashboard failure
dashboard share/unshare
dashboard delete/archive
dashboard tags/sources/cadence
```

to:

```text
profile
memories
user manifest
cabinet
sessions
chats
threads
scheduled processes
usage/activity analytics
user_context cache/output
user_ontology storage/output
```

Return every found edge:

| Dashboard event | Writer/call site | User-model target | Data written | Used later by | Verdict |
|---|---|---|---|---|---|

For absent edges, report `NOT_PRESENT` only after the complete search.
Do not infer that viewing a dashboard updates memory from the existence of
usage analytics.

### 8.3 User-model-to-dashboard reads

Search the reverse direction. Determine whether dashboard authoring,
compilation, serving, refresh, or portal listing reads profile, memories,
cabinet, sessions, chats, threads, processes, or ontology content to
personalize output.

Separate:

- the LLM receiving `user_context` before deciding what to author;
- executable dashboard code directly reading user-model stores;
- portal UI using authenticated identity;
- registry metadata merely identifying ownership.

Return all source-backed edges and mark absent direct integrations
`NOT_PRESENT`.

## 9. Staleness, consistency, and repair

### 9.1 Pointer staleness scenarios

For each pointer family, identify:

| Pointer | Canonical underlying state | Update trigger | Known missed trigger | Reader behavior when stale | Repair path | User-visible/LLM-visible effect |
|---|---|---|---|---|---|---|

Analyze at minimum:

- on-demand dashboard refresh without pointer update;
- dashboard creation before the next scheduled registry walk;
- share/unshare without pointer update;
- dashboard deletion/registry removal;
- failed scheduled refresh;
- stale `UserRegistry` versus fresher Django auth cache, and the reverse;
- missing/corrupt manifest or registry;
- pointer count/path/timestamp disagreement;
- a system-owned dashboard namespace absent from user registration.

Do not invent repair mechanisms. If none exists, use `NOT_PRESENT`.

### 9.2 Dashboard pointer semantics

Resolve whether the user-manifest dashboard pointer is:

- authoritative for dashboard existence;
- an aggregate/cache over the dashboard registry;
- a discovery accelerator;
- a freshness signal;
- an LLM-context input;
- a UI input;
- a scheduled-job output only.

Use one verdict per role with source evidence.

### 9.3 Consistency checks and observability

Identify live validators, diagnostics, jobs, or readers that detect or
repair:

```text
pointer ↔ registry mismatch
registry ↔ dashboard folder mismatch
owner ↔ authenticated viewer mismatch
shared flag ↔ Community visibility mismatch
manifest metadata ↔ registry metadata mismatch
dashboard freshness ↔ pointer timestamp mismatch
```

Return exact signatures and call sites only for checks that exist. Mark the
rest `NOT_PRESENT`.

## 10. Current context and documentation alignment

Compare executable facts against active:

```text
user_ontology context
user_context runtime output
Tier-1 sandbox context
context-tool routing text
dashboard portal/context guidance
```

Return:

| Context path:lines | Claim or omission | Executable fact | Verdict | Curation target |
|---|---|---|---|---|

Check:

- registry ID, tier, bundle, trigger, and loader behavior;
- exact categories loaded into `user_context`;
- dashboard roster source and fields;
- user-manifest pointer authority versus aggregate/cache role;
- `UserRegistry` versus Django auth;
- sharing location and access boundaries;
- whether dashboard activity writes memory/profile/ontology;
- stale-pointer implications;
- system-owned, Community, Observatory, and Franchise treatment.

Do not recommend changes to ECharts authoring context unless a verified fact
changes what PRISM must author, persist, or verify while building a
dashboard. Identity, portal, ontology, and pointer plumbing belongs in the
listed `prism/` curation targets by default.

## 11. Canonical schema and graph packets

Produce these compact source-backed curation artifacts without repeating
verbatim source blocks:

1. `user_ontology` registry/loading/schema packet;
2. redacted `user_context` input/output packet;
3. complete persistent pointer writer/reader graph;
4. identity/auth/ownership/access matrix;
5. dashboard-category placement matrix;
6. personalization/memory/dashboard feedback graph;
7. pointer-staleness and repair matrix.

Every row/edge must cite the defining executable or context source.

## 12. User-ontology/dashboard contradiction ledger

Resolve each assumption:

| ID | Assumption | Verdict | Current fact | Evidence |
|---|---|---|---|---|
| UOD01 | `user_context` is auto-included whenever `kerberos` is provided. | | | |
| UOD02 | `user_ontology` is a reachable registered module with a current trigger. | | | |
| UOD03 | `user_ontology` and `user_context` describe the same user schema. | | | |
| UOD04 | Runtime `user_context` includes profile, memories, recent sessions, cabinet, and dashboards. | | | |
| UOD05 | Runtime `user_context` also includes chats, threads, and scheduled processes. | | | |
| UOD06 | The dashboard roster is read through the user-manifest dashboard pointer. | | | |
| UOD07 | The user-manifest dashboard pointer is authoritative for dashboard existence. | | | |
| UOD08 | Dashboard creation/build updates the user-manifest dashboard pointer immediately. | | | |
| UOD09 | On-demand refresh updates the user-manifest dashboard pointer. | | | |
| UOD10 | Scheduled refresh updates the pointer after at least one successful dashboard refresh. | | | |
| UOD11 | Share/unshare updates the user-manifest dashboard pointer. | | | |
| UOD12 | A stale dashboard pointer can make the next `user_context` roster stale. | | | |
| UOD13 | `UserRegistry` and Django auth enumerate the same active identities with the same cache policy. | | | |
| UOD14 | Community is a visibility state on a user-owned dashboard, not a separate storage schema. | | | |
| UOD15 | Sharing fields live in the dashboard registry, not the user manifest. | | | |
| UOD16 | Direct Community detail access rechecks `shared == true`. | | | |
| UOD17 | Observatory dashboards are represented in each user's manifest/context. | | | |
| UOD18 | Franchise dashboards are part of the persistent per-user dashboard model. | | | |
| UOD19 | A live system-owned user namespace is registered and refreshed. | | | |
| UOD20 | Dashboard creation, use, refresh, or sharing automatically writes user memory. | | | |
| UOD21 | Executable dashboard code directly reads memories/profile for personalization. | | | |
| UOD22 | Dashboard usage analytics, if present, are distinct from memory and ontology writes. | | | |
| UOD23 | `user_ontology` treats dashboards as first-class persistent user entities. | | | |
| UOD24 | Current curated documentation accurately describes dashboard placement in the persistent user model. | | | |

For every `CONTRADICTS` or `UNKNOWN` row, identify the exact local claim
that must remain untrusted until reconciled. Do not turn this ledger into a
redesign proposal.

## 13. Coverage closure

Return exactly this checklist with `YES` or `NO`:

```text
CHECKOUT_IDENTITY_COMPLETE:
SOURCE_SEARCH_COMPLETE:
CONTEXT_REGISTRATION_COMPLETE:
BUNDLE_TRIGGER_LOADING_COMPLETE:
USER_ONTOLOGY_SCHEMA_COMPLETE:
USER_CONTEXT_GENERATOR_COMPLETE:
USER_CONTEXT_RENDER_SHAPE_COMPLETE:
DASHBOARD_ROSTER_EXPOSURE_COMPLETE:
USER_MANIFEST_SCHEMA_COMPLETE:
POINTER_WRITER_GRAPH_COMPLETE:
POINTER_READER_GRAPH_COMPLETE:
IDENTITY_AUTH_GRAPH_COMPLETE:
ACCESS_BOUNDARIES_COMPLETE:
DASHBOARD_CATEGORY_MATRIX_COMPLETE:
SHARING_VISIBILITY_SCHEMA_COMPLETE:
MEMORY_PERSONALIZATION_TRIGGERS_COMPLETE:
DASHBOARD_TO_USER_MODEL_WRITES_COMPLETE:
USER_MODEL_TO_DASHBOARD_READS_COMPLETE:
STALE_POINTER_IMPLICATIONS_COMPLETE:
CONSISTENCY_REPAIR_PATHS_COMPLETE:
CONTEXT_ALIGNMENT_COMPLETE:
CONTRADICTION_LEDGER_COMPLETE:
USER_ONTOLOGY_DASHBOARD_MODEL_COMPLETE:
```

`USER_ONTOLOGY_DASHBOARD_MODEL_COMPLETE` may be `YES` only if every
preceding item is `YES`. If it is `NO`, list only the unresolved
section/subsection numbers and the missing source or permission.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried and what
blocked it.
