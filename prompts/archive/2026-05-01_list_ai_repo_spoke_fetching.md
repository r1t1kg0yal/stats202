---
session: pre-APIs-endeavor (dashboards spoke-fetching design)
sent: 2026-05-01 (earlier in day)
reply_folded_into:
  - prism/mcp-tools.md (NEW at the time)
  - prism/architecture.md §3.6
  - prism/_changelog.md 2026-05-01 (earlier) entry — C32, C33
status: USED — open item F7 (verbatim list_ai_repo def from
  developer_tools.py) carried forward into the Session 2 prompt for
  the APIs endeavor; everything else closed.
---

Title: list_ai_repo mechanics + mid-session reference-doc fetching model

I'm designing a hub-and-spoke layout for the dashboards skill. Today
dashboards.md (~2200 lines, ~141 KB in context/modules/static/) is
loaded once as a single L2 static module via get_context(). I want to
split it into a hub (always-loaded L2) plus several per-primitive
"spoke" markdown files the LLM fetches mid-session, ON DEMAND, via a
tool call the hub spells out verbatim. The spoke fetch is an L3
operation (execution-tier), not an L2 re-include -- get_context() runs
once at session start and include_modules isn't a mid-session
primitive.

Use list_ai_repo and execute_analysis_script to introspect. Reply with
verbatim source and exact paths. Mirror the section structure below.

## 1. list_ai_repo verbatim

Paste the full function definition from mcp/tools/subprocess_tools.py
-- signature, docstring, parameter defaults. Then explicitly answer:

- What does it return? Directory listing only, file contents inline, or
  both?
- What directory does it root at? Can it traverse into
  context/modules/static/?
- Parameters for recursion depth, glob filtering, content inclusion?

## 2. Companion file-content reading

- If list_ai_repo does NOT return file bodies, paste the verbatim
  signature of whatever tool the LLM uses to read a specific file's
  contents from the ai repo (read_ai_repo, cat_ai_repo, or whatever
  exists in mcp/tools/). Full def please.
- If no dedicated read tool exists, paste a representative example of
  using execute_analysis_script with open(path) to read a file from
  the repo -- including what cwd/path the sandbox is rooted at when
  reading these paths.

## 3. L2 module loading model -- confirm one-shot

Look at mcp/tools/context_tool.py and the context assembler. Confirm:

- Once get_context() has produced its assembled context block, is
  calling get_context(include_modules=[...]) a SECOND time during the
  same session a supported flow?
- If yes, what happens -- append, replace, raise?
- If no, what enforces the one-shot -- guard in the tool, LLM
  convention, or simply not re-discoverable after first call?

Sanity check -- I want to confirm include_modules can't function as a
mid-session fetch before committing to list_ai_repo for spoke fetching.

## 4. Mid-session reference-doc fetching -- precedent

Search context/modules/static/ and ai_development/ for any existing
file that points the LLM at a SECOND markdown file via verbatim
list_ai_repo(...) (or equivalent read tool). Examples to look for:

- A SKILL.md or context module that says "for advanced patterns, also
  read X" with the exact tool call inline.
- A "see also" pattern in a static context module that translates into
  a follow-up read.
- Any existing hub/spoke decomposition where one always-loaded doc
  instructs the LLM to fetch a sibling doc on demand.

Paste 1-2 excerpts if precedent exists (source instruction + ideally
an LLM-transcript snippet of the call+response). If no precedent
exists, say so plainly.

## 5. Path conventions for spokes

If I ship 5-6 new markdown spoke files (e.g. dashboards_charts.md,
dashboards_widgets.md, dashboards_widget_tool.md, dashboards_filters.md,
dashboards_recipes.md) reachable via list_ai_repo mid-session, where
should they live? Pick from:

- Alongside dashboards.md in context/modules/static/
- In a sub-directory (context/modules/static/dashboards/)
- Elsewhere (e.g. ai_development/dashboards/specs/ adjacent to the
  engine)

Criterion: cleanest list_ai_repo call shape AND consistency with
whatever convention exists. Quote any layout norms you find.

## 6. Size + budget constraints

- Soft/hard ceiling on what list_ai_repo (or the companion read tool)
  returns per call? Per file? Per session?
- Each spoke will be ~150-300 lines (~3-7 KB); a hub-driven build
  might pull 2-3 spokes back-to-back. Any context-budget instrumentation
  (e.g. a diagnostic in context/) the LLM is meant to be aware of when
  deciding to fetch?

If part of this prompt cannot be answered, add a brief
"## Could not resolve" section at the end listing what you tried and
what blocked it.
