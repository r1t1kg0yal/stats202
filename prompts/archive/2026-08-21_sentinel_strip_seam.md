# Context extraction — where a chart reply can be post-processed

**Status:** OPEN
**Class:** CONTEXT-EXTRACTION (pure introspection; no Frictions section)
**Raised:** 2026-08-21
**Why:** the chart sub-agent's report is fenced with sentinel lines
(`===CHART_DELIVERY_START===` / `===CHART_DIAGNOSTICS_START===`) and the sub-agent
is instructed never to echo the sentinels themselves. A live run showed 3/3
compliance, but that is a compliance rate, not a guarantee, and the failure mode
is maximally visible: a raw `===CHART_DELIVERY_START===` printed into a user's
chat answer. We want a mechanical strip so the prompt rule becomes a belt over a
brace. This prompt asks only for the mechanism — we already know the design.

**What we already have, so please do not re-derive it.** From your 2026-08-20
reply we recorded: ADK is **2.4.0**; `subagent_callbacks` returns **five keys,
each a single callable, never a list** — `before_agent_callback`,
`after_agent_callback`, `before_tool_callback`, `after_tool_callback`,
`after_model_callback` — with `_before_agent` pushing the `agent_id` frame and
`_after_agent` popping it; ADK 2.4.0's callback fields accept lists and call them
in order until one returns non-`None`; and `AgentTool.run_async` returns the
sub-agent's reply to the parent as a plain `str`, which becomes a
`FunctionResponse` part, with `_clip_result` (`gs_llm2.py:393`) the only other
transform and display-side only.

So `after_agent_callback` is **occupied**, and any addition there has to compose
rather than replace. That much is settled. What is not settled is whether that
callback can change the returned text at all, and whether a simpler seam exists.

Reply verbatim: exact signatures, exact bodies in fenced blocks, real file paths.
Do not paraphrase. Where a question is yes/no, answer it explicitly **and** paste
the code that proves it. If a section cannot be resolved, add a short
`## Could not resolve` at the end.

---

## 1. The tail of `AgentTool.run_async` — the likeliest seam

We have the *input* half of this method (the `input_schema` branch that builds
the first user `Content`). We do not have the half that produces the return
value, and that is exactly the half that matters here.

1.1 Paste **`AgentTool.run_async` verbatim and complete**, from `async def` to
its final `return`, from your installed
`google/adk/tools/agent_tool.py`. Include the decorator line and the full
signature with type annotations and defaults.

1.2 In that body, identify precisely **where the returned string is assembled**:
which event or events it reads, whether it takes the last event's text or
concatenates, and what it returns when the sub-agent produced no text.

1.3 Is `AgentTool.run_async` a plain `async def` returning `Any`/`str`, or is it
a generator / does it yield? We need to know whether a subclass can `result =
await super().run_async(...)`, post-process the string, and return it — the
whole question is whether that one override is sufficient and safe.

1.4 Does anything on the parent side depend on the tool result being
**byte-identical** to what the sub-agent emitted — a hash, a cache key, a replay
log, an eval fixture, an SSE frame keyed on content? `git grep` for any consumer
of the chart tool's result besides the model prompt and `_clip_result`, and paste
the hits with file:line.

---

## 2. Whether the callback route works at all

If §1 shows the subclass route is clean we will take it and skip this entirely,
but we need to know the alternative's shape.

2.1 Paste `core/subagent_events.py` **in full** — we specifically need
`_after_agent` verbatim, since composing with it means calling it in the right
order and preserving whatever it returns.

2.2 From `google/adk/agents/base_agent.py` in your installed 2.4.0, paste the
code that **invokes** `after_agent_callback` — the method body that calls it, not
just the field declaration. We need to see what it does with the return value.

2.3 **The load-bearing question:** in ADK 2.4.0, if an `after_agent_callback`
returns a `types.Content`, does that content **replace** what the agent yields as
its final response, and does that replacement reach `AgentTool.run_async`'s
return value? Or does the callback fire *after* the response has already been
captured, making it observation-only? Paste the code path that decides this.

2.4 If the callback can replace the response: is the replacement visible to the
sub-agent's own session history (so a subsequent turn would see the stripped
version), or only to the caller?

---

## 3. One measurement

3.1 Run this against the live chart tool result string and report the four
integers — we want to know whether a sentinel has ever actually leaked, not just
whether it could:

```python
for s in ("===CHART_DELIVERY_START===", "===CHART_DELIVERY_END===",
          "===CHART_DIAGNOSTICS_START===", "===CHART_DIAGNOSTICS_END==="):
    ...  # count occurrences in the last chart_agent reply as the parent received it
```

If no chart reply is available in the current session, say so — do not fabricate
a run.

3.2 Is there **any** persisted log of past `chart_agent` replies (an eval set, a
transcript store, an S3 prefix) we could grep for a leaked sentinel across
historical turns? Name the path if one exists.

---

## Reply format

One numbered section per question above, same numbering. Verbatim code in fenced
blocks. Real file paths. No summarising.
