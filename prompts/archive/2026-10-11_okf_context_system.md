---
class: context-extraction
topic: the OKF context system -- the floor, what !1895 deleted, how get_context resolves now, and what reaches sub-agents
expected_reply: ~25-40 KB (okf.py whole, registry and bundle state, static/index.md, short verbatim excerpts)
created_at: 2026-10-11
sent: no
status: OPEN
trigger: >
  The 2026-10-08 loose-ends reply showed an OKF floor (okf.py:182-183) holding
  prism_md, end_user_abstraction, charts_system, hallucination_guard and
  market_orientation, said floor pieces are deregistered, and cited
  docs/context-index-plan.md:101 recording "Delete end_user and _base" as done
  in !1895. prism/context-system.md still describes always-on as
  MODULE_REGISTRY's _base.include and nine bundles, as of 2026-08-09.
reply_folds_into:
  - prism/context-system.md (rewrite §1-§4 around the floor; resolve the §2.2 WARN)
  - prism/mcp-tools.md (get_context tiers and include_modules behaviour)
  - prism/subagents.md §2.1, §7.2 (whether sub-agents get the floor)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

Why this prompt exists. `prism/context-system.md` was last verified on
2026-08-09, before the OKF floor and !1895. Its account of what is always on,
which bundles exist and how `include_modules` resolves is now unverified, and
the 2026-10-08 reply contradicts part of it. The chart work does not block on
this, but every staging project that ships a context module does: where a new
`.md` lands and how it is reached depend on the answer.

---

## Paste everything below into PRISM

This is read-only source introspection so we can keep external documentation
in sync with you. Do not build a chart, do not edit or create any file in the
repository, and do not report frictions. You may run read-only Python in
`execute_analysis_script` to read files.

Answer from live source, not from remembered context, a context module, or a
previous turn's summary. Open the file and cite it. Where your live source
disagrees with a belief stated below, say so and correct it.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, constants and code **verbatim in fenced code
blocks**; do not paraphrase them.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### 1. `okf.py`

Paste `prism-core/context/okf.py` **whole**, with its size in bytes and lines.

### 2. The floor and the registry

Our belief, from your 2026-10-08 reply: `_FLOOR` at `okf.py:182-183` lists
`prism_md/00`, `end_user_abstraction/00`, `charts_system/00`,
`hallucination_guard/00` and `market_orientation/00`; `with_floor`
(`:197-224`) puts them first; `OkfContextPlugin._resolve` calls it; the plugin
is appended only `if not self.toolless` (`core/gs_llm2.py:3354`); floor pieces
are deregistered (`okf.py:179-181`).

1. Does `MODULE_REGISTRY` still exist in `prism-core/context/registry.py`? If so,
   its entry count, and the list of entry keys.
2. Does `SPECIALIZATION_BUNDLES` still exist? List its keys. Is there still a
   `_base` bundle, and if so what does `_base.include` hold?
3. Is `get_always_on_modules()` still defined and called? By whom?
4. Quote `docs/context-index-plan.md` rows for steps 3a-3f (or whatever the
   numbering is around `:101`), with their status column.
5. Paste `prism-core/context/modules/static/index.md` lines 1-80.

### 3. How a main-agent turn gets its context

1. On a normal Composer turn with tools, list in order every piece of context
   the main agent receives before its first model call: the floor, anything
   else `OkfContextPlugin` adds, and anything the system prompt builder adds.
   Cite where each is added.
2. What does `get_context` do now? Paste its signature and docstring, and say
   whether `include_modules=[...]` resolves against `MODULE_REGISTRY`, against
   OKF paths, or both.
3. Is `list_ai_repo` still how a model reads an unregistered `.md`? Quote its
   signature.
4. Which front-matter keys does any code read? Our belief: `okf.py` reads only
   `computation`, `parameters` and `ttl` (`:266`, `:285`, `:299`).

### 4. What sub-agents receive

1. Does `chart_agent`, `infographic_agent` or `web_search_agent` receive the OKF
   floor or any other context module? Cite the line that decides it, or say
   that nothing gives them any.
2. Is `OkfContextPlugin` installed anywhere other than the main agent's `App`?

### 5. `dashboards.md`

Our belief: `prism-core/context/modules/static/tools/dashboards.md` is a
registered module reached by `include_modules=["dashboards"]`, and its spokes
under `tools/dashboards/` are read through `list_ai_repo`. Is that still true
under OKF? If not, how does a model reach the dashboard router and its spokes?

---

## Reply structure

Use one `##` heading per section above, numbered the same, with sub-answers in
order. Put whole-file pastes under `## Appendix: whole files`, one fenced block
per file headed by its path.
