---
class: change-request
topic: chart_agent deadline -- keep the renders a cancelled invocation already made, and stop advising the main agent to draw in execute_analysis_script
target: a coding session in the prism-main checkout (not PRISM's chat; PRISM's context-extraction prompts are read-only)
created_at: 2026-10-11
sent: no
status: OPEN
trigger: >
  PRISM's 2026-10-08 reply quoted core/agent_base.py:404-416 verbatim. On the
  300 s deadline the invocation is cancelled without running result_trailer,
  so every PNG chart_agent rendered before the deadline is lost to the main
  agent, and the returned line tells the main agent to do the one thing
  00-charts-system.md §3 forbids.
reply_folds_into:
  - prism/subagents.md §1.1 (deadline consequences), §7 (image transport)
  - prism/_reference/00-charts-system.md (the §2 and §3 disagreement rows)
  - projects/altair/core/chart_agent_tool.py (re-mirror verbatim if it changes; bump its TestOwnership sha)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into the coding session.**

Both files this touches are PRISM-owned since 2026-10-11 (`core/agent_base.py`
always was; `core/chart_agent_tool.py` moved out of the altair payload that
day), so staging writes the request and does not ship the code. If
`chart_agent_tool.py` changes, copy it back byte-for-byte to
`projects/altair/core/chart_agent_tool.py` and update its hash in
`dev/test_chart_exec.py` `TestOwnership`.

The evidence is `prism/subagents.md` §1.1. The parts of `_scoped`
(`agent_base.py:394-402`) this relies on were described in PRISM's reply, not
quoted: the session should read it before changing anything.

---

## Paste everything below into the prism-main coding session

### The problem

`_ScopedAgentTool.run_async` in `prism-core/core/agent_base.py:404-416` enforces
the sub-agent deadline (`SUBAGENT_TIMEOUT_SECONDS`, 300 s, `core/gs_llm2.py:496`)
like this:

```python
run = asyncio.ensure_future(self._scoped(args, tool_context))
done, _ = await asyncio.wait({run}, timeout=deadline)
if done:
    return run.result()
run.cancel()
_log.error(f"{name} cancelled at its {deadline:g}s deadline")
return (f"{name} exceeded its {deadline:g}s deadline and was cancelled. "
        "Retry with a smaller request, or build the artifact "
        "deterministically in execute_analysis_script.")
```

Three defects, all on the cancelled path:

1. **Finished renders are thrown away.** The invocation state, and with it
   `ChartInvocation.delivered`, lives inside `_scoped` under
   `invocation_scope(invocation_state)`. `run_async` cannot see it, and
   `_scoped` has no `CancelledError` handling, so `result_trailer`
   (`chart_agent_tool._image_transport_trailer`) never runs. A chart_agent
   that rendered four PNGs and was cancelled while drawing the fifth returns
   none of them: no `[[image: key]]` markers, so `ImagePromotionPlugin`
   promotes nothing and the main agent never sees them.
2. **The advice contradicts the main agent's contract.**
   `context/modules/static/core/charts_system/00-charts-system.md` §3 says
   every house-style visual comes from `chart_agent`, never the sandbox's own
   matplotlib. The deadline line says to build it in `execute_analysis_script`.
   `chart_agent_tool.py`'s own description already says the right thing: a
   further call carries a corrected or smaller request.
3. **A render can land after the cancel.** `run.cancel()` is not awaited, and a
   render inside `asyncio.to_thread` (`prism_mcp/tools/chart_exec.py:845-846`)
   keeps running on its own thread, so a PNG can reach S3 after the deadline
   line has been returned, and nothing reports it.

### The change requested

1. **Make the invocation state reachable from `run_async`.** For example,
   `_scoped` stores the state it creates in a holder `run_async` passes in
   (a one-slot dict or a small object), rather than `run_async` catching or
   swallowing `CancelledError` in the task. On the timeout branch, after
   `run.cancel()`, call `self.result_trailer(state, <deadline line>)` when a
   trailer is configured and the state exists, and return that. A finished
   run's return is unchanged.
2. **Make the advice per tool.** Add a keyword to `subagent_tool(...)`, for
   example `deadline_advice: str | None = None`, defaulting to today's
   generic sentence so `ticket_agent` and `infographic_agent` are unchanged
   unless they opt in. `chart_agent_tool.py` passes:
   *"Retry chart_agent with fewer visuals per request or smaller CSVs
   (aggregate, take the top N, split the request). Do not draw it in
   execute_analysis_script."*
3. **Say what was kept.** When the trailer carries renders, the deadline line
   names how many (*"4 render(s) made before the deadline are attached; they
   have no links, so re-request them if they must be delivered"*), because
   the links live in the sub-agent's reply, which never came. Check this
   against what the Composer rewrite needs before choosing the wording: if
   `_rewrite_answer_chart_imgs` can resolve a bare S3 key, say that instead.
4. **Late renders (lower priority).** On the timeout branch, mark the state
   closed. The chart-call recorder ignores anything a closed state records,
   and the `chart_calls` manifest notes that the call finished after its
   invocation was cancelled.

### Acceptance

- A test that drives `_ScopedAgentTool.run_async` with a fake sub-agent run
  which appends one key to the state's `delivered` and then sleeps past a
  short deadline (pass the deadline directly; `PRISM_SUBAGENT_TIMEOUT` is
  clamped to 30-3600 s). The returned string contains the deadline line and
  exactly one `[[image: <key>]]` marker that `core/gs_llm2.py:2765`
  `_IMAGE_MARKER_RE` matches.
- The same test with `result_trailer=None` returns the deadline line alone.
- `chart_agent`'s deadline line does not contain `execute_analysis_script`.
  `ticket_agent`'s and `infographic_agent`'s are byte-identical to today's.
- `test_chart_exec_gates`, `test_chart_exec_sandbox_seam` and
  `test_chart_call_log` still pass.

### Reply wanted

The merged diff for `core/agent_base.py` and `core/chart_agent_tool.py`, the
new test file, and the new sha256[:16] and byte size of `chart_agent_tool.py`.
