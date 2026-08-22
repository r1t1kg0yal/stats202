---
class: context-extraction
topic: subagent_tool / agent_base factory, model catalog, and ChartInvocation
expected_reply: ~25 KB
created_at: 2026-08-21
sent:
status: OPEN
trigger: >
  Screenshots of live core/chart_agent_tool.py show the factory no longer
  builds LiteLlm / Agent / AgentTool itself. It now calls
  core.agent_base.subagent_tool with a catalog model key (currently
  gemini_flash) and invocation_state=ChartInvocation. Staging still
  documents the pre-factory shape in prism/subagents.md and still hosts
  _ScopedChartAgentTool + chart_invocation() as the invocation scope.
  We cannot update the curated docs or the local shim until the new
  factory, the catalog, and ChartInvocation are read from source.
reply_folded_into:
  - prism/subagents.md
  - prism/_changelog.md
  - projects/altair/altair-payload/core/chart_agent_tool.py
  - projects/altair/altair-payload/tools/chart_exec.py
  - projects/altair/core/ (shim: agent_base, model_catalog)
  - projects/altair/README.md
  - .cursor/rules/viz-platforms.mdc
---

**Staging-side note — do NOT paste this header into PRISM.**

Why this prompt exists. Three decisions are blocked on it.

1. **What `subagent_tool` actually is.** Screenshots show
   `chart_agent_tool` reduced to a thin caller. The LiteLlm client, the
   `Agent(...)` construction, `_install_cache_and_io`, `subagent_callbacks`,
   the attach log line, and the `_ScopedChartAgentTool.run_async` invocation
   scope all appear to have moved into `core.agent_base.subagent_tool`. We
   cannot document that move, or stub it, without the factory body.

2. **What `invocation_state=ChartInvocation` is.** Staging scoped one
   chart_agent call with a `ContextVar` set by
   `_ScopedChartAgentTool.run_async` around `chart_invocation()`. The live
   file now imports a public `ChartInvocation` from `chart_exec` and passes
   the class (not an instance) into the factory. If that class is just a
   rename of our context manager, the shim is a one-line alias. If it is a
   new protocol the factory instantiates, the shim has to implement that
   protocol or the pair will not load.

3. **Which model the chart agent actually runs.** Staging documents
   "same `PRISM_MODEL_ID` via `LiteLlm`". The live file has
   `CHART_AGENT_MODEL_KEY = "gemini_flash"` resolved through
   `core.configs.model_catalog.MODEL_KEY_TO_ID`. We need the catalog and
   the resolved id, and we need to know whether the main agent and
   `web_search_agent` went through the same catalog or only charts did.

Sections 1-4 are blocking. 5-7 are what the shim and the curated doc need
to stay honest.

---

## Paste everything below into PRISM

This is read-only source introspection so we can update external documentation
about how you work. Do not build a chart, do not run an analysis, do not edit or
create any file, and do not report frictions.

Do not answer from remembered context, from a context module, or from a previous
turn's summary where live source is available — open the file and cite it. Where
your live source disagrees with a belief stated below, say so explicitly and
correct it; the beliefs are what we currently have written down and they may
already be stale against tonight's `chart_agent_tool.py`.

Give repository-relative paths from the `prism-main` root with `path:line`
citations. Quote signatures, class definitions, dict literals, and factory
bodies **verbatim in fenced code blocks**; do not paraphrase them.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

## What we already have — do not re-derive it

From screenshots of tonight's `core/chart_agent_tool.py` we already recorded
the factory as this shape. Confirm or correct; do not retype it unless a
line differs.

```python
CACHE_TTL = "1h"
CHART_AGENT_MODEL_KEY = "gemini_flash"
# catalog KEY from core/configs/model_catalog.py
#   "opus"          -- Claude Opus (the process default)
#   "gemini_flash"  -- Gemini 3.7 Flash

_CORPUS_SOURCES = (
    "static/tools/chart_context.md",
    "static/tools/charts/chart_context_colors.md",
    "static/tools/charts/chart_context_dual_axis.md",
    "static/tools/charts/chart_context_annotations.md",
    "static/tools/charts/chart_context_composites.md",
    "static/tools/charts/chart_context_grids.md",
    "static/tools/charts/chart_context_tables.md",
)

def chart_agent_tool(worker_id: str, event_callback=None):
    from google.adk.tools import FunctionTool
    from core.agent_base import subagent_tool
    from core.configs.model_catalog import MODEL_KEY_TO_ID
    from prism_mcp.tools.chart_exec import ChartInvocation, render_charts

    assert CHART_AGENT_MODEL_KEY in MODEL_KEY_TO_ID, (
        f"CHART_AGENT_MODEL_KEY={CHART_AGENT_MODEL_KEY!r} names no catalog row; "
        f"pick one of {sorted(MODEL_KEY_TO_ID)}"
    )
    model_id = MODEL_KEY_TO_ID[CHART_AGENT_MODEL_KEY]
    corpus = _chart_corpus()
    return subagent_tool(
        name="chart_agent",
        worker_id=worker_id,
        model_id=model_id,
        description=(...),
        instruction=lambda ctx: f"{_OPERATING_CONTRACT}\n\n---\n\n{corpus}",
        tools=[FunctionTool(func=render_charts)],
        attached=f"chart AgentTool attached (model={model_id}, corpus={len(corpus)}B)",
        event_callback=event_callback,
        cache_ttl=CACHE_TTL,
        invocation_state=ChartInvocation,
    )
```

From earlier extraction (2026-08-20 / 2026-08-21) we still treat as true
unless tonight's source contradicts it. Do not re-prove these; only flag
a contradiction:

- ADK is 2.4.0. `AgentTool.run_async` is a plain coroutine returning a `str`.
- `subagent_callbacks` returns five single callables, never a list.
- `after_agent_callback` appends an event; because `AgentTool` is
  last-content-wins that append silently becomes the entire tool result.
  The supported seam for transforming the reply is subclassing `run_async`.
- The 1h cache breakpoint sits on a synthetic carrier turn *before* the
  instruction, so the whole ~70 KB corpus is inside the cached prefix.
- `instruction` must be a callable or the corpus's literal braces break
  ADK `{var}` state-injection.
- Several `chart_agent` calls in one turn all resolve to the same session
  path, and ADK dispatches them with `create_task` + `gather`. Anything
  per-invocation cannot be keyed on the session.

---

## 1. `core/agent_base.py` — the factory we do not have

This is the file the screenshots introduced. Staging has no copy.

1.1 Paste `core/agent_base.py` **in full** if it is under ~400 lines. If it
is larger, paste in full: every public name, `subagent_tool` and every
helper it calls that lives in this file (any `_Scoped*`, `run_async`
override, LiteLlm builder, cache installer, callback composer). Give
`wc -l` and `wc -c` for the file either way.

1.2 Paste the exact `subagent_tool` signature, including every parameter,
default, and type annotation. Then paste the body verbatim.

1.3 For each parameter of `subagent_tool`, one sentence stating what it
does, quoting the line that proves it. We particularly need:

| Parameter | What we are guessing | Confirm or correct |
|---|---|---|
| `name` | becomes `Agent.name` and the tool name the parent sees | ? |
| `worker_id` | forwarded into cache / logging / `_install_cache_and_io` | ? |
| `model_id` | already-resolved gateway id, not a catalog key | ? |
| `description` | `Agent.description` / the 234-char parent-facing string | ? |
| `instruction` | still accepted as a callable so braces stay literal | ? |
| `tools` | the FunctionTool list | ? |
| `attached` | the log line that used to be `_log.info(f"[LLM] ({worker_id}) ...")` | ? |
| `event_callback` | passed into `subagent_callbacks` | ? |
| `cache_ttl` | forwarded to `_install_cache_and_io` | ? |
| `invocation_state` | entered around `run_async`; class, not instance | ? |

If `subagent_tool` takes parameters the screenshots did not show, list
them. If a screenshot parameter is ignored, say so.

1.4 How is `invocation_state` used? Paste the exact block. We need to
know which of these is true — answer with the letter **and** the code:

```
A. with invocation_state():          # contextmanager function / class
B. with invocation_state() as state: # same, but the factory reads state
C. state = invocation_state()        # instantiated; factory holds it
D. a ContextVar set to invocation_state() for the duration of run_async
E. something else (paste it)
```

1.5 Does `subagent_tool` still subclass `AgentTool` and override
`run_async`? If yes, paste the subclass. If the override now lives under
a different name, paste that. We need to know whether the
`_ScopedChartAgentTool` idea moved into the factory or was deleted.

1.6 Where do LiteLlm construction, `_install_cache_and_io`, and
`subagent_callbacks` now live — inside `subagent_tool`, in a helper in
this file, or still in `gs_llm2`? Paste the call sites with file:line.
If `_install_cache_and_io` is no longer imported from `gs_llm2`, say
where it moved.

---

## 2. `ChartInvocation` — the other half of the pair

`chart_agent_tool` now does
`from prism_mcp.tools.chart_exec import ChartInvocation, render_charts`
and passes `invocation_state=ChartInvocation`. Staging's `chart_exec.py`
has a private `_Invocation` dataclass and a `chart_invocation()`
context manager. We do not know whether those were renamed, wrapped, or
replaced.

2.1 In `prism-core/prism_mcp/tools/chart_exec.py`, paste `ChartInvocation`
in full — class or function, every method, every field, the docstring.

2.2 Does `_Invocation` still exist? Does `chart_invocation()` still
exist? For each, yes/no, and if yes paste the current definition. If
`ChartInvocation` *is* the old `chart_invocation` renamed, say that in
one sentence.

2.3 What does one instance own? We currently believe an invocation
carries `token`, `attempt`, `findings`, `sequence`. Confirm the live
fields. If the factory, not `chart_exec`, now owns any of those, say
which.

2.4 Who else imports `ChartInvocation`? `git grep -n ChartInvocation`
from the repo root and paste every hit. Same for `chart_invocation` and
`_ScopedChartAgentTool` — we need to know whether those names are dead.

---

## 3. The model catalog

3.1 Paste `core/configs/model_catalog.py` **in full**. If that path is
wrong, find `MODEL_KEY_TO_ID` with `git grep` and paste the defining
file in full.

3.2 What does `CHART_AGENT_MODEL_KEY = "gemini_flash"` resolve to tonight?
Paste the dict row and the resolved gateway model id as a string.

3.3 List every catalog key and the id behind it, as a table:
`key | gateway id | one-line comment from the file if any`.

3.4 Does the **main agent** (`ClaudeWithMCP` / `gs_llm2.agent`) also
resolve through this catalog, or does it still use `PRISM_MODEL_ID`
directly? Paste the line that decides it. Same question for
`bing_search_agent_tool` / `web_search_agent`.

3.5 The screenshot comment says `"opus"` is "the process default" and
`"gemini_flash"` is "Gemini 3.7 Flash". Confirm both strings against
the file. If the comment and the catalog disagree, the catalog wins
and we want both quotes.

---

## 4. `chart_agent_tool.py` in full

Screenshots can drop a space. We need the file as it sits on disk.

4.1 Paste `core/chart_agent_tool.py` **in full**.

4.2 Report `wc -l`, `wc -c`, and `sha256sum` of that file.

4.3 Does `_OPERATING_CONTRACT` still name the four statuses
`OK` / `RETRYABLE` / `NO_ARTIFACTS` / `FATAL`, the four sentinels
`===CHART_DELIVERY_START===` / `===CHART_DELIVERY_END===` /
`===CHART_DIAGNOSTICS_START===` / `===CHART_DIAGNOSTICS_END===`,
`profile_df`, and the five-call ceiling? Answer each yes/no. Do not
re-paste the contract if 4.1 already has it.

---

## 5. Who else went through the factory

The factory is only worth a shared shim if more than charts uses it.

5.1 `git grep -n subagent_tool` from the repo root. Paste every hit.

5.2 Paste the current `bing_search_agent_tool` factory (the function
that builds the `web_search_agent` tool). Does it call `subagent_tool`?
Does it pass `invocation_state`? If it has its own scope object, paste
that class too.

5.3 Is there a third `AgentTool` in the parent tool list besides
`chart_agent` and `web_search_agent`? Paste the `tools.append(...)`
block from `core/adk_local_tools.py` and the MCP-path mirror in
`core/adk_tool_source.py`.

---

## 6. Beliefs to mark true, stale, or dead

For each row: **TRUE** (still exactly this), **STALE** (same idea,
wrong location / name), or **DEAD** (no longer in the tree). One
short correction when it is not TRUE.

| # | Belief we currently have written down |
|---|---|
| B1 | `chart_agent` runs the same `PRISM_MODEL_ID` as the main agent, via a `LiteLlm` built inside `chart_agent_tool` |
| B2 | `chart_agent_tool` constructs `Agent(...)` itself and spreads `**subagent_callbacks(...)` into that constructor |
| B3 | Invocation scope is `_ScopedChartAgentTool.run_async` wrapping `chart_invocation()` |
| B4 | Per-invocation state is a `ContextVar` holding `_Invocation` (`token`, `attempt`, `findings`, `sequence`) |
| B5 | The attach log is `_log.info(f"[LLM] ({worker_id}) chart AgentTool attached (model={PRISM_MODEL_ID}, corpus={len(corpus)}B)")` |
| B6 | `_install_cache_and_io(llm_model, CACHE_TTL, worker_id)` is called from `chart_agent_tool` |
| B7 | `from google.adk.agents import Agent` and `from google.adk.models.lite_llm import LiteLlm` appear in `chart_agent_tool` |
| B8 | `from core.gs_llm2 import APP_ID, ENV, PRISM_MAX_OUTPUT_TOKENS, PRISM_MODEL_ID, _install_cache_and_io, get_token` appears in `chart_agent_tool` |
| B9 | Post-processing a chart reply still has to subclass `run_async`; `after_agent_callback` is still a landmine |
| B10 | `instruction=lambda ctx: ...` is still required so the corpus braces stay literal |

---

## 7. What a local shim has to implement

We will stand up `core.agent_base.subagent_tool` and
`core.configs.model_catalog.MODEL_KEY_TO_ID` in a staging mirror so
`chart_agent_tool.py` imports the same way it does in you. We will
**not** run ADK. We need the minimum surface that makes
`from core.agent_base import subagent_tool` and
`from core.configs.model_catalog import MODEL_KEY_TO_ID` resolve, and
that lets `invocation_state=ChartInvocation` be the real class from
`chart_exec`.

7.1 List every name `subagent_tool` reads from `core.gs_llm2`,
`core.subagent_events`, `google.adk.*`, and anywhere else, with the
import line. This is the import block a shim has to either provide or
explicitly not provide.

7.2 Does `subagent_tool` import `ChartInvocation`, or does it only
accept whatever object the caller passed as `invocation_state`? Quote
the line. A generic protocol is what we want; a hard-coded
`chart_exec` import inside the factory would be a layering break we
need to know about before stubbing.

7.3 Is `MODEL_KEY_TO_ID` a plain `dict[str, str]`, a mapping proxy, or
something that does I/O on lookup? Paste the type.

---

## Could not resolve

If a file is missing, a symbol is ambiguous, or a read is denied, list
it here with the path you tried. Do not invent a body.
