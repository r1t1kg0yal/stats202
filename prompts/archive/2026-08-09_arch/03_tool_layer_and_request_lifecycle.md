---
class: context-extraction
topic: 03 — MCP tool layer and the lifecycle of a user request
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

The tool surface is what the chart and dashboard skill files are written
against, so its shape governs how those files should be authored. Wants the
lifecycle narrative, not tool docstrings dumped wholesale.

---

## Paste everything below into PRISM

You are being asked to describe your own tool layer and request handling. This is
introspection for documentation purposes: do not build anything, do not report
frictions.

**I want the architecture and the flow**, with `path:line` citations and short
excerpts. Paste full signatures where I ask for them, but not whole tool
implementations.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a section boundary and name what remains.

### 1. The tool registry

1.1 List every tool currently registered and callable, with its module path and a
one-line description of what it does. Compute the list from the registration
mechanism rather than from memory.

1.2 Explain the registration mechanism itself: what decorator or call registers a
tool, where the registry lives, how the schema presented to the model is derived
from the Python function, and what happens to type hints and defaults in that
translation.

1.3 Group the tools by purpose — retrieval, execution, data access, repository
navigation, communication, whatever the natural clusters are — and say which
cluster is the busiest in practice if you can tell.

### 2. The three tools my documentation is written against

For each of the tool that lists or reads repository files, the tool that loads
context modules, and the tool that executes analysis code:

2.1 Full signature, verbatim, with the file and line range.

2.2 Its parameters explained — what each does, its default, and which
combinations are meaningful versus which are traps.

2.3 Its constraints: call limits, size caps, timeouts, truncation behaviour.
State whether each constraint is enforced in code that raises, or is only
instructed in prose the model is expected to obey. That distinction matters more
to me than the constraint itself.

2.4 Its failure modes and what the model sees when each fires.

### 3. Lifecycle of a request

3.1 Trace one user message end to end: arrival, session resolution, context
assembly, model call, tool dispatch, result handling, response delivery. Give it
as an ordered list of steps with file citations at each hop.

3.2 What is assembled into the model's context before it ever sees the user's
text? Name each component, its rough size, and whether it is fixed or computed
per request.

3.3 Where in that flow does progressive disclosure happen — what is always
present, what is fetched on demand, what is only reachable by executing code?
Describe the tiers as the system actually implements them.

3.4 What is the session object, where does it live, what does it carry across
turns, and what is scoped to a single message?

### 4. Where charts and dashboards enter the flow

4.1 When a user asks for a chart, what is the exact sequence of tool calls the
system expects the model to make? Same question for a dashboard.

4.2 Which tool actually produces each artifact, and how does the artifact get
back to the user — inline, attachment, link, portal page?

4.3 What does the model see as the *result* of a successful chart build and of a
successful dashboard build? Describe the shape of the returned object.

4.4 Are there guardrails specific to these two flows — validation that blocks,
retries, size caps, rate limits? Name each and where it lives.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
