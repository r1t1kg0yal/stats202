# Context extraction — can two chart agents actually run at once, and what breaks if they do

**Status:** OPEN
**Class:** CONTEXT-EXTRACTION (pure introspection; no Frictions section)
**Raised:** 2026-08-21
**Why:** we want the main agent to be able to fan out — several `chart_agent`
invocations in one turn, rendering in parallel instead of one after another. The
ADK layer looks ready for it: `AgentTool.run_async` builds a fresh `Runner`,
`InMemorySessionService` and throwaway session per call, `_FRAMES` is a
`ContextVar` so "concurrent sub-agents never see each other's frames", `_SEQ` is
process-wide so `agent_id` is unique across concurrent turns, and `_call_id`'s
docstring names "the parallel same-name calls a sub-agent makes". All of that is
from your 2026-08-20 reply and we are not asking you to re-derive it.

What we do not know is whether the *rest* of the stack agrees. Staging has fixed
three of its own concurrency defects already (a retry ladder keyed on the session
that two agents shared, a five-call ceiling that reset on its own refusal, and
identical `save_as` values silently overwriting each other's PNGs). The four
questions below are the ones we cannot answer from staging, and §1 is the one
that decides whether the other three matter yet.

Reply verbatim: exact signatures, exact bodies in fenced blocks, real file paths.
Do not paraphrase. Where a question is yes/no, answer it explicitly **and** paste
the code that proves it. If a section cannot be resolved, add a short
`## Could not resolve` at the end.

---

## 1. Does the main agent's tool loop dispatch in parallel at all?

This gates everything else. If `core/gs_llm2.py` awaits tool calls one at a time,
two chart agents never overlap today and the fan-out is a feature to build rather
than a hazard to contain.

1.1 In `core/gs_llm2.py`, find where a model turn's `function_calls` are executed.
Paste that block verbatim, with file:line. We need to see whether it is a `for`
loop with `await` inside (serial) or an `asyncio.gather` / `TaskGroup` /
`create_task` fan-out (parallel).

1.2 If it is serial: is there a cap, a flag, or a code comment explaining the
choice? Paste anything that reads like a deliberate decision rather than an
accident.

1.3 If it is parallel: what bounds it — a semaphore, a max-concurrency constant,
nothing? Paste the bound.

1.4 Empirically, has a single model turn ever emitted two `chart_agent` calls?
You have `sessions/<id>/thoughts/trail.jsonl` with `kind == "tool"` and
`tool == "chart_agent"` rows carrying an `agent_id` (unique per invocation) — the
same corpus you scanned for the sentinel measurement, 426 trails across
2026-08-16 to 2026-08-20. Count turns with two or more distinct `chart_agent`
`agent_id`s. Report the number of turns and the max fan-out seen. If the answer
is zero, say zero — do not fabricate a run.

---

## 2. Is `core/code_execution.py` safe to call from two threads at once?

**This is the highest-stakes question in this prompt.** Staging's mirror used
`contextlib.redirect_stdout`, and we measured what that does under four
concurrent renders: `redirect_stdout` saves and restores a *process-global*
`sys.stdout`, so overlapping workers interleave their save/restore pairs and one
restores the other's buffer. `sys.stdout` is then a dead `StringIO` for the life
of the process and every subsequent print anywhere in it disappears — silently,
with no error. We fixed the mirror by routing capture through a thread-local.

Our own notes disagree about which shape PRISM uses. `prism/vision-qc.md` puts
output capture "inside the sandbox's `redirect_stdout` block", which is the
unsafe shape. `prism/codebase-tree.md` describes "scoped `print` / `sys` proxies
(`code_execution.py:44-47`)", which is not. Both cannot be the whole story.

2.1 Paste `core/code_execution.py` **in full**. It is described elsewhere as
~29-53 lines of substance, so this should be short.

2.2 Answer explicitly: does capturing stdout there mutate `sys.stdout` (or
`sys.stderr`) process-wide for the duration of an exec, or is the capture scoped
to the calling thread / the exec namespace? Quote the exact lines that decide it.

2.3 If it is process-wide: run this and report the two lines. It is the same
experiment we ran locally.

```python
import sys, concurrent.futures
from core.code_execution import _execute_sync
real = sys.stdout
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    out = list(pool.map(lambda n: _execute_sync(f"print({n})\n", {}), range(4)))
print("captured:", out, file=real)
print("stdout intact:", sys.stdout is real, file=real)
```

2.4 Is `_execute_sync` reachable concurrently from anything **other** than two
chart agents — two `execute_analysis_script` calls in one turn, a dashboard
refresh overlapping a sandbox run, the hourly job? `git grep` the call sites and
paste them with file:line. If the answer is yes, this is not a charting bug.

---

## 3. What else in the chart path is process-global?

We found and fixed three pieces of shared state on our side. We want to know
whether PRISM holds any of its own.

3.1 In `prism-core/prism_mcp/tools/chart_exec.py` and
`prism-core/prism_mcp/chart_render/`, list every **module-level mutable** — dict,
list, set, counter, cache, or a `global` rebound at runtime. For each, say
whether it is written during a render. `chart_render/core.py` has injected
globals (`_compute_chart_id`, `_chart_studio`, `_FONT_REPO_ROOT`) set by
`register_trusted_extensions` — we assume those are write-once at startup; please
confirm rather than assume.

3.2 `_persist_editable_spec` writes
`{session_path}/charts/chart_manifest.json` with
`manifest.setdefault("charts", {})[png_path] = chart_id`. That is read-modify-write
on one S3 key. If two agents in one session persist a spec at the same time, does
one manifest update overwrite the other? Paste the read and the write, and say
whether anything makes it atomic.

3.3 Does `S3BucketManager` (or the wrapper `chart_exec` binds) hold any per-call
state on the instance — a last-path, a buffer, a counter — that two concurrent
renders through the same singleton would corrupt?

---

## 4. Identity and baggage under concurrency

`chart_exec` reads `resolve_kerberos_info_from_baggage()` and
`resolve_medium_from_baggage()` at the top of every `render_charts`.

4.1 Are those contextvars, thread-locals, or module globals? Paste the
declarations.

4.2 If contextvars: `asyncio.to_thread` copies the context, so a worker thread
sees the right principal. Confirm that holds for the specific path
`AgentTool.run_async` → sub-agent tool loop → `render_charts` →
`asyncio.to_thread`, and say whether anything resets or rebinds baggage between
those hops.

---

## Reply format

One numbered section per question above, same numbering. Verbatim code in fenced
blocks. Real file paths. No summarising. §1.4, §2.3 and §3.2 want measurements or
executed output, not reasoning about what would happen.
