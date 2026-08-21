# Context extraction — the chart sub-agent's contract surface

**Status:** OPEN
**Class:** CONTEXT-EXTRACTION (pure introspection; no Frictions section)
**Raised:** 2026-08-20
**Why:** staging now owns `core/chart_agent_tool.py` and
`prism-core/prism_mcp/tools/chart_exec.py` and is about to redesign four things
— a typed input schema for the chart hand-off, harness-injected data profiles, a
split delivery/diagnostics return, and a retry policy that replaces the flat
"stop after two failed attempts". Each one depends on a mechanism we can only
read from your installed packages.

Reply verbatim: exact signatures, exact docstrings in fenced blocks, exact field
lists, and the real path of every file you read. Do not paraphrase. Where a
question has a yes/no answer, answer it explicitly **and** paste the code that
proves it. If a section cannot be resolved, add a short `## Could not resolve`
at the end.

---

## 1. ADK version and the two mechanisms we intend to use

1.1 Output of `pip show google-adk` (or the equivalent) — **name, version,
location**. If it is vendored rather than pip-installed, say so and give the
path.

1.2 From the installed `google/adk/tools/agent_tool.py`, paste **verbatim and
complete**:
- `AgentTool.__init__`
- `AgentTool._get_declaration`
- `AgentTool.run_async`

We have read ADK **2.7.1** locally. In that version `run_async` does:

```python
input_schema = _get_input_schema(self.agent)
if input_schema:
    input_value = input_schema.model_validate(args)
    content = types.Content(role='user', parts=[types.Part.from_text(
        text=input_value.model_dump_json(exclude_none=True))])
else:
    ...
```

and `_get_declaration` has feature-flag branches (`JSON_SCHEMA_FOR_FUNC_DECL`)
that your quoted snippet did not. **Your installed copy is therefore probably
older.** We need your actual bytes, not 2.7.1's.

1.3 **Does your version's `LlmAgent` permit `output_schema` and `tools`
together?** ADK 2.7.1's field docstring says:

> The ADK supports using `output_schema` and `tools` together. It works by
> exposing tools during the thought loop and enforcing structure only on the
> final output.

Older ADK forbade it outright. Paste the `output_schema` field declaration and
its docstring from your `google/adk/agents/llm_agent.py`, plus any
`model_validator` / `model_post_init` that raises or warns when both are set.
**This single answer decides whether the chart agent can return a validated
object or must keep returning a markdown string.**

1.4 In your version, do the callback fields accept a **list** of callables, or
only one? Paste the type alias for `before_agent_callback` from
`google/adk/agents/base_agent.py` (2.7.1 has
`Union[_SingleAgentCallback, list[_SingleAgentCallback]]`).

---

## 2. Whether structured output survives the transport

Even if ADK allows `output_schema`, it has to reach the model.

2.1 Does `LiteLlm` pointed at `https://{ENV}.gpt.site.gs.com/models-gateway/api/openai`
honour a response schema / `response_format` / structured outputs? Has any
agent, tool, or call site in the codebase **ever** used `output_schema`,
`response_format`, or `response_schema`? `git grep` each and paste the hits with
file:line.

2.2 What exactly does `_install_cache_and_io(llm_model, CACHE_TTL, worker_id)`
do? Paste it verbatim from `core/gs_llm2.py`. Specifically:
- **Where is the cache breakpoint placed** — on the whole system instruction, on
  its last block, or somewhere else?
- If we appended per-request text (a data profile) to the **end** of the chart
  agent's instruction string, would that invalidate the cached prefix on every
  call, or is the breakpoint positioned so a stable prefix still hits?

2.3 Paste `core/subagent_events.py::subagent_callbacks` verbatim. We need the
exact dict it returns — **which callback keys**, and whether each value is a
single callable or a list. We may need to compose a `before_agent_callback` with
whatever it already sets, and clobbering it would silently kill the event lane.

---

## 3. The two files staging just adopted — import blocks

Both were transcribed from screenshots with the import region collapsed behind
`import ...`. Everything below the imports is confirmed character-exact
(`_OPERATING_CONTRACT` = 855 chars and the cleaned `render_charts` docstring =
1,268 chars both reproduce). The imports are the only gap.

3.1 Paste the **complete import block, verbatim**, from the top of
`prism-core/prism_mcp/tools/chart_exec.py` — every line from the closing `"""`
of the module docstring down to `logger = logging.getLogger('chart_exec')`.

3.2 Same for `core/chart_agent_tool.py` — from the closing `"""` down to
`_log = logging.getLogger("prism.gs_llm2")`.

3.3 For each of these eight names used in `chart_exec.py`, give the **module it
is imported from** and whether the import is module-scope or deferred:

```
s3_manager                            SCRIPT_STDOUT_INLINE_BYTES
preprocess_script_code                log_swallowed_exception
generate_download_links_for_sandbox   _resolve_or_create
_resolve_kerberos_info_from_baggage   _resolve_medium_from_baggage
```

Note the constraint we inferred: `script_exec_tools` imports
`format_chart_delivery_hint` from `chart_exec`, and the deferred
`CANONICAL_STDLIB_NAMESPACE` import inside `_chart_namespace` carries a comment
saying a module-scope import there would close the cycle. So any of the eight
that really do live in `script_exec_tools` must be deferred. Confirm or correct.

---

## 4. What the harness can see, for the profile injection

We want to hand the sub-agent the schema, dtypes, ranges and a row preview of
every CSV **before its first token**, because it currently authors against
frames it has never seen while obeying a dozen data-shape gates.

4.1 `_load_data_files` reads every CSV with `index_col=0, parse_dates=True`.
What happens today when the first column is **not** a date — does
`parse_dates=True` silently leave it as-is, or coerce? Has this ever produced a
malformed frame in practice?

4.2 Paste `preprocess_script_code` verbatim (signature, docstring, body). What
does it rewrite or reject, and what is in `_preprocess_notes`? Does it strip
imports? Does it block matplotlib on this path, or is matplotlib simply absent
from the namespace? `chart_context.md` currently claims "Raw matplotlib is
blocked" and we need to know whether that is enforcement or just absence.

4.3 Paste `prism_mcp/utils/param_validator.py::validate_params` verbatim. What
does its error enrichment add, and does it run **before** the wrapped function
so a bad kwarg is caught without executing?

4.4 Does the engine's `ValidationError` carry **structured** data — a list of
findings, codes, offending field names — or only a formatted message string?
Paste the exception class definition. We want to count findings across attempts
to detect whether a retry is converging.

---

## 5. The return path and the retry budget

5.1 Paste `generate_download_links_for_sandbox` verbatim. Return shape per item,
failure mode, and whether minting is idempotent / rate-limited (the corpus says
the slug is deterministic — confirm).

5.2 `AgentTool.__init__` takes `skip_summarization: bool = False` and
`chart_agent_tool` does not set it. **Does the main agent currently run an extra
summarization pass over the `chart_agent` tool result before using it?** If so,
that pass sits between the verbatim markdown and the user. Paste whatever reads
the tool result on the parent side, and say whether setting
`skip_summarization=True` would remove a model call.

5.3 Is there **any** telemetry on the chart path — number of `render_charts`
calls per `chart_agent` invocation, attempts-to-success, timeout rate, failure
classes? If nothing exists, say so plainly; that itself is the answer.

5.4 `CHART_EXECUTION_TIMEOUT_SECONDS = 90`. When `asyncio.wait_for` trips, the
`except Exception` arm formats a `TimeoutError` traceback into `error` and the
report goes back as a normal result. **Confirm the sub-agent sees a timeout as
an ordinary retryable error string with nothing marking it as a timeout.**

5.5 Beyond the 234-char tool description, is there **anything at all** on the
main-agent side that shapes how a `chart_agent` request is phrased — a context
module, a PRISM.md line, a prompt fragment, a few-shot example? `git grep -n
chart_agent` across the whole repo and paste every hit with two lines of
context. This is the seam nobody owns and we need to know whether it is
genuinely empty.

---

## 6. Sanity check on two numbers

6.1 Re-measure and report, as integers:
- `len(_OPERATING_CONTRACT)`
- `len(chart_agent.description)` — you previously reported 274; we measure
  **234** from the literal transcribed out of your own source, whose text
  matches your quote word for word.
- `len(_chart_corpus())`
- `len(render_charts.__doc__)` raw, and after `inspect.cleandoc`

6.2 For each of the seven `_CORPUS_SOURCES` files, the exact byte size on disk.
Our staging copies are intentionally 252 chars lighter in total right now, and
we want the install-side baseline to confirm the delta is exactly what we think.

---

## Reply format

One numbered section per question above, same numbering. Verbatim code in fenced
blocks. Real file paths. No summarising.
