---
class: context-extraction
topic: subagent architecture — the agent topology, and how chart context now reaches the agent that authors charts
expected_reply: ~30 KB
created_at: 2026-08-20
sent:
status: OPEN
trigger: >
  User reports PRISM has moved to a full subagent architecture. The chart
  engine and the seven chart context files are unchanged, but if a
  chart-authoring subagent loads the whole chart surface at once, then the
  registered-router / on-demand-spoke split that shapes all seven files is
  vestigial. That split is the single largest structural decision in
  projects/altair/altair-payload/ — a 22 KB router whose §1 is a six-row
  fetch-trigger table, plus six unregistered spokes totalling 44.7 KB whose
  only discoverability is prose inside the router. Every one of those bytes
  exists to ration context. Under a subagent that gets the full surface,
  they ration nothing and cost a fetch hop, a trigger table, and six
  duplicated preambles. We cannot collapse or keep the split without
  knowing what the subagent's context assembly actually does.
reply_folded_into:
  - prism/architecture.md                                        # agent topology, replaces the single-lane model
  - prism/mcp-tools.md                                           # §3 request lifecycle, §3.2 progressive disclosure, §4 chart call sequence
  - prism/context-system.md                                      # §1.4 resolve_modules, §2 bundles/suppress, §5 chart family layout
  - prism/code-sandbox.md                                        # who calls execute_analysis_script now
  - projects/altair/altair-payload/chart_context.md              # §1 routing table — keep, shrink, or delete
  - projects/altair/altair-payload/chart_context_*.md            # six spokes — keep split or merge
  - .cursor/rules/viz-platforms.mdc                              # "Skill files are the LLM-facing source of truth" table
  - .cursor/rules/skill-discipline.mdc                           # registered-vs-spoke byte-cost framing
---

**Staging-side note — do NOT paste this header into PRISM.**

Why this prompt exists. Four decisions are blocked on it.

1. **Whether the router/spoke split survives.** `chart_context.md` §1 is a
   six-row table telling PRISM which spokes to fetch, followed by a literal
   `list_ai_repo(file_paths=[...], mode="full")` call shape. If the chart
   subagent starts with all seven files resident, that section is dead weight
   *and* actively misleading — it instructs a fetch that is already done.

2. **Whether the 22 KB router should shrink or grow.** Our current shape is a
   deliberate compromise: the router had to survive being read cold with no L2
   chart context present, because `chart_context` is suppressed by the default
   `end_user` bundle. If the subagent's assembly is a static file list rather
   than the bundle/suppress machinery, that constraint is gone and the right
   split is a different one.

3. **Whether the grounding footer is still load-bearing.** We documented the
   footer on every `execute_analysis_script` return re-asserting the spoke
   fetch. If it now fires into an agent that already holds the spokes, it is
   burning tokens on every exec return and telling the model to redo work.

4. **Whether `order`, `footer_note`, the suppress list, and the
   dashboards↔chart_context mutex still do anything.** All four shape how we
   author these files. If `resolve_modules` is no longer on the chart path,
   four constraints we design around are fiction.

Sections 1-4 are blocking. 5-7 are what we need to author correctly.

---

## Paste everything below into PRISM

This is read-only source introspection so we can update external documentation
about how you work. Do not build a chart, do not run an analysis, do not edit or
create any file, and do not report frictions.

Do not answer from remembered context, from a context module, or from a previous
turn's summary where live source is available — open the file and cite it. Where
your live source disagrees with a belief stated below, say so explicitly and
correct it; the beliefs are what we currently have written down and they may be
months stale.

Give repository-relative paths from the `prism-main` root with `path:line`
citations. Quote signatures, class definitions, dict literals, prompt strings,
and file lists **verbatim in fenced code blocks**; do not paraphrase them. Line
numbers we cite are from reads dated 2026-08-09 and 2026-08-19 and may have
moved — cite the current ones.

**Reply budget: keep this under roughly 30,000 characters.** Sections 1-4 are
the priority. If you run long, stop at a section boundary and name what remains
rather than compressing the early sections.

---

### 1. The agent topology

We have no picture of this at all. Our documentation still describes a single
Composer lane: one model, one `get_context` call, one context payload assembled
by `assembler.resolve_modules`, tools called from that one context. Replace that
picture.

1.1 **Enumerate every agent that exists.** For each: its name/identifier, the
file and line where it is defined, its role in one sentence, and the model it
runs on. Give this as a table, then paste the source of whatever registry,
enum, dict, or config declares the set.

1.2 **Paste the orchestration entry point verbatim** — the function that decides
which agent handles an incoming request and dispatches to it. Include its
signature, its full body if under ~120 lines, and its `path:line`.

1.3 **Spawn mechanics.** Are subagents separate processes, separate model calls
in the same process, threads, or something else? Are they ever run in parallel,
or strictly sequentially? Cite the dispatch code.

1.4 **Handoff contract.** What exactly does a parent pass to a subagent, and
what comes back? Paste the request and response objects (dataclass, TypedDict,
pydantic model, or plain dict construction site) verbatim. Specifically: does
the subagent inherit the parent's conversation history, a summary of it, or only
a task description?

1.5 **Which agent authors charts.** Name it. State the exact condition that
routes a chart request to it — paste the routing predicate, prompt fragment, or
tool description that makes that decision. If chart authoring is not a distinct
agent, say so plainly and name the agent that does it among its other jobs.

1.6 **Where the old specialization machinery sits now.** Our belief:
`context/assembler.py` exposes `resolve_modules(...)`, a 10-step pipeline
(seed always-on → bundle → world_state → kerberos → planner blacklist →
explicit include/exclude → bundle fixpoint → suppress veto → dashboards mutex →
composite dedup), with nine bundles in `context/registry.py` and `end_user` as
the default specialization. For each of the following, state STILL LIVE /
BYPASSED ON THE CHART PATH / DELETED, with a citation:

- `resolve_modules`
- the nine bundles and the `specialization` parameter
- `get_always_on_modules()` and the six always-on modules
- the suppress list as an absolute veto over `include_modules`
- the `dashboards` present → `chart_context` dropped mutex
- the `MODULE_REGISTRY` (we have it at 105 entries) and its `order` field
- `get_context` as a tool the model can call

1.7 **The request lifecycle, rewritten.** Give us the current end-to-end
sequence for a user asking for a chart in Composer, from HTTP request to
returned PNG, naming every model call and every agent boundary crossed. A
numbered list with `path:line` at each step is ideal. Explicitly mark where the
old single-lane picture was wrong.

---

### 2. What the chart-authoring agent actually holds at turn 0

This is the most important section in the prompt.

2.1 **Paste the complete, ordered list of everything in that agent's context
window before the user's text is appended.** Every system prompt fragment,
every context module, every file, every tool schema. Name each by the path it
was read from. If the assembly is a loop over a list, paste the list literal and
the loop.

2.2 **Is the chart context in it?** For each of these seven files, state
PRESENT AT TURN 0 / FETCHED ON DEMAND / NEVER LOADED, and give the installed
path you checked:

```
context/modules/static/tools/chart_context.md
context/modules/static/tools/charts/chart_context_annotations.md
context/modules/static/tools/charts/chart_context_dual_axis.md
context/modules/static/tools/charts/chart_context_composites.md
context/modules/static/tools/charts/chart_context_tables.md
context/modules/static/tools/charts/chart_context_grids.md
context/modules/static/tools/charts/chart_context_colors.md
```

2.3 **Static or dynamic?** Is the chart agent's context a hardcoded file list, a
glob over a directory, a registry query, or the old bundle resolution? Paste the
code that builds it. If it is a glob, paste the pattern — we need to know
whether adding a seventh spoke file would be picked up automatically or would be
invisible until someone edits a list.

2.4 **Measure it.** Total characters and, if you can compute it, total tokens
for the chart agent's turn-0 context. Break that down by source: chart context
files, other context modules, tool schemas, system prompt, user/world state.

2.5 **Does anything still suppress or veto?** Under the subagent model, is there
any code path that can prevent `chart_context.md` from reaching the chart agent?
Our old belief was that `end_user` (the default) suppressed it outright and that
charts therefore arrived only through an L3 `list_ai_repo` fetch. Confirm,
correct, or state that the question no longer applies.

2.6 **Dashboards and charts together.** If a user asks for a dashboard and a
static PNG chart in one turn, what happens now — two subagents, one, a
handoff? Does the old one-directional mutex still drop chart context in that
case?

---

### 3. What happened to the fetch layer

3.1 **Does `list_ai_repo` still exist and is it in the chart agent's toolset?**
Paste its current signature verbatim with `path:line`, and paste the tool list
the chart agent is given.

3.2 **Does the chart agent ever fetch a chart spoke at runtime?** If the spokes
are resident at turn 0, presumably never — confirm. If it does still fetch,
under what condition?

3.3 **The grounding footer.** Our belief: every `execute_analysis_script` return
appends a footer that repeats "ALWAYS pull the spokes FIRST … this is a ROUTER …
never guess one" (we last saw it near `prism_mcp/tools/script_exec_tools.py:1472`).
Paste the current footer string verbatim with its `path:line`, state whether it
still fires, and state whether the chart agent is a recipient. If it now
instructs a fetch the agent has already done, say so.

3.4 **`footer_note`.** Our belief: the registry `footer_note` field is capped at
400 chars by `validate_registry`, and renders twice — in the L2 closing
cheatsheet and in L3 tool footers. Paste the current `chart_context` registry
entry verbatim and state whether its `footer_note` is still rendered anywhere in
the subagent path.

3.5 **Telemetry.** If any usage data exists since the migration, give the count
of `list_ai_repo` calls naming a `chart_context*` path. Zero is a useful answer;
"not instrumented" is also a useful answer.

3.6 **Path resolution.** If spoke fetching survives at all, confirm the six
short paths (`charts/chart_context_tables.md` and siblings) still resolve, and
restate the current resolution algorithm — we have it as a repo-wide basename
index with path-hint scoring and alphabetical tie-break.

---

### 4. The seven files, individually

Fill this table from the live installed tree. `Registered?` means "has a
`MODULE_REGISTRY` entry" (or whatever the equivalent is now — if the registry is
gone, say what replaced the concept and answer in those terms).

| Installed path | Bytes | Registered? | At turn 0 for the chart agent? | Fetchable at runtime? |
|---|---:|---|---|---|
| `tools/chart_context.md` | | | | |
| `tools/charts/chart_context_annotations.md` | | | | |
| `tools/charts/chart_context_dual_axis.md` | | | | |
| `tools/charts/chart_context_composites.md` | | | | |
| `tools/charts/chart_context_tables.md` | | | | |
| `tools/charts/chart_context_grids.md` | | | | |
| `tools/charts/chart_context_colors.md` | | | | |

Our last measured sizes, for comparison — flag any mismatch, since a mismatch
means someone edited a file on your side and broke our drag-and-drop invariant:

```
chart_context.md               22,169
chart_context_tables.md        12,775
chart_context_annotations.md    7,788
chart_context_dual_axis.md      7,220
chart_context_composites.md     6,647
chart_context_colors.md         6,518
chart_context_grids.md          3,795
```

Also state whether the directory split (`tools/` for the router, `tools/charts/`
for the spokes) still means anything mechanically, or whether it is now just
filesystem layout.

---

### 5. The cost of loading the full surface

5.1 **Is there a per-agent context budget, cap, or truncation step?** If yes,
paste it, state the limit, and state how close the chart agent's turn-0 context
currently sits to it.

5.2 **What is the marginal cost of a larger chart surface?** Concretely: if the
seven files became one 67 KB file, does anything break, degrade, or get
truncated? Is there caching that a single file would help or hurt?

5.3 **Does `order` still control anything?** Our belief: `order` was the sole
determinant of concatenation position in the assembled payload, and
`chart_context` sat at 160. If the subagent assembly is a static list, position
is now list position — confirm which, and state whether the chart context lands
early or late relative to the system prompt and tool schemas.

5.4 **Is there any remaining mechanism that would make a smaller router
cheaper?** In other words: is there *any* path where the chart agent gets the
router but not the spokes? If yes, describe it — that path is the only remaining
justification for the split.

---

### 6. Engine-side confirmation

We expect all of this to be unchanged; it is cheap to confirm and expensive to
get wrong.

6.1 Confirm these five files exist at these paths with these roles, and give
byte counts:

```
prism-core/prism_mcp/chart_render/__init__.py
prism-core/prism_mcp/chart_render/core.py
prism-core/prism_mcp/chart_render/house_style.py
prism-core/prism_mcp/chart_render/units.py
prism-core/prism_mcp/utils/chart_functions.py
prism-core/prism_mcp/utils/chart_functions_studio.py
prism-core/prism_mcp/utils/chart_functions_studio_tables.py
```

6.2 State whether `prism_mcp/tools/script_exec_tools.py` is still the sole
importer of chart symbols. Paste the search you ran and its raw output. If a
subagent module now imports them too, that is a change to the drag-and-drop
contract and we need to know.

6.3 Paste the current `len(core.__all__)` (we have 43) and confirm
`chart_functions.py` still computes `__all__ = list(_core.__all__)` at runtime
rather than duplicating the list.

6.4 Paste the exact set of chart-related names injected into the
`execute_analysis_script` namespace. Our skill files promise these are callable
bare and must never be imported: `make_chart`, `make_table`, `build_charts`,
`profile_df`, `ChartSpec`, the five `make_*pack_*` helpers, the result classes,
and the annotation classes. Confirm each is present under that exact name.

6.5 State whether the chart-authoring subagent calls `execute_analysis_script`
itself or delegates to another agent. If it delegates, name the boundary and
state which side holds the chart context.

---

### 7. Your read

Facts above, judgment here. Answer as the system that has to use these files.

7.1 **What in the current chart context is now vestigial?** Be specific — quote
the section headings or line ranges from `chart_context.md` and the spokes that
exist only to ration context and no longer earn their place. §1 "Route before
authoring" and its six-row trigger table is the obvious candidate; tell us what
else.

7.2 **What should a subagent-native chart context look like?** One file or
seven? If seven, what is the new justification for the split? If one, what is
the right internal ordering given where it lands in your window? Give a concrete
proposed structure, not a principle.

7.3 **What is the biggest risk if we collapse the seven files into one?** Name
the failure mode you would actually hit, not a theoretical one.

7.4 **What is now *underspecified* for you?** The old design assumed you would
fetch a spoke when you needed depth. If everything is resident, the failure mode
inverts: too much undifferentiated text and no signal about what matters for the
current request. Tell us where you would want stronger signposting, and what
form it should take.

7.5 **What should we ask you next?** Name the one question about the subagent
architecture that we did not ask and that would most change how we author these
files.

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
permission denied, architecture question not applicable), add a brief
`## Could not resolve` section at the end listing what you tried and what
blocked it.
