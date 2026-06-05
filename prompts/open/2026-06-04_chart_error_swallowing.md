# Context-extraction prompt — how `execute_analysis_script` surfaces (or swallows) chart errors + related tickets

**Why this exists (staging-side note, do NOT paste this header into PRISM):**
We're about to change `chart_functions.py` so that chart/table failures
*bubble up as raised exceptions* instead of being swallowed inside a
returned `ChartResult(success=False)` / `CompositeResult(success=False)` /
`TableResult(success=False)`. Today every public entry point
(`make_chart`, `make_2pack_*`, `make_3pack_*`, `make_4pack_grid`,
`make_6pack_grid`, `make_table`) catches `ValidationError` (and in places a
broad `Exception`) internally and *returns* a `success=False` result, so the
LLM script runs to completion with no exception — meaning PRISM only learns
about the failure if the emitted script happens to inspect `result.success`.
We have reports of swallowed chart errors consistent with exactly this.

Before we flip the engine to raise, we need the *current, verbatim* PRISM-side
error-handling architecture so the raised exception lands on the cleanest
surfacing path, and so we don't break any PRISM-side consumer that depends on
the graceful `success=False` return. We also want any tickets already filed
about this.

This is a context-extraction prompt: pure introspection. Paste exact code,
exact mappings, exact namespace block — no paraphrase.

---

## Paste the following into PRISM

You are being asked to introspect your own code-execution + charting
internals and report them verbatim. Use `list_ai_repo` /
`execute_analysis_script` / direct source reads as needed. Do not paraphrase;
paste exact source, signatures, and dict literals in fenced code blocks, and
name the actual file path + line range you read each from.

### 1. The exec wrapper and error surfacing (`mcp/tools/script_exec_tools.py`)

1.1 Paste **verbatim** the current body of the function that runs the
LLM script under a timeout (the one historically named
`execute_with_timeout`) — the full `def ... target() ... thread.join ...
if result['exception']: raise` block. Include its current line range.

1.2 Paste **verbatim** the outer `execute_analysis_script` error-handling
chain — every `try/except` stage that can fire after the script is invoked
(session-init, data-loading, the script-execution catch, the outer
catch-all, timeout). For each `except`, show what it does: re-raise, return
an error string, call `send_error_email`, etc.

1.3 Paste **verbatim** `format_llm_friendly_error()` (signature + full body)
and any helper it calls to build the message the LLM ultimately sees (error
type, message, offending line, hint). I want to see exactly what text a
raised exception turns into in the tool result.

1.4 Paste **verbatim** the hint-key mapping table/dict that decides things
like `chart_function_error` vs `valueerror` (the structure referenced as the
"hint key" mapping). Show how a given exception is routed to a hint key —
is it by exception **type**, by **message substring**, by **module of
origin**, or something else? Paste the exact routing code.

1.5 Show the `send_error_email(...)` call site(s) inside
`script_exec_tools.py` — for each, the `stage=` value and the trigger
condition. Confirm whether a raised exception from `make_chart` results in
exactly one email at `stage='script_execution'`.

### 2. The crux — is a returned `success=False` result ever noticed?

This is the single most important question.

2.1 When `exec(code, exec_namespace)` completes with **no exception**
(i.e. the script called `make_chart(...)`, got back a
`ChartResult(success=False)`, and did NOT itself raise or print), does
**any** post-execution step inspect the local/returned result objects in the
namespace for `success == False`? If yes, paste that code. If no, state
plainly that there is no such inspection.

2.2 Walk the post-exec artifact path: paste the code where
`S3ManagerWrapper` tracked artifacts are collected and turned into presigned
download links. Does an empty artifact set (no PNG was produced because the
chart failed) surface anything to the LLM, or is "zero artifacts" silent?

2.3 Does `_check_charts_quality_injected` (the post-exec vision sweep) only
iterate over PNGs that actually exist in S3? Confirm that a failed chart
(which wrote no PNG) produces zero QC lines and zero error lines.

2.4 Net answer in one paragraph: **if an LLM script calls
`make_chart(...)` / `make_table(...)`, receives a `success=False` result,
and does not itself act on `.success`, what (if anything) does PRISM surface
to the user about the failure?**

### 3. The wrapping + namespace (verbatim, current state)

3.1 Paste **verbatim** the current `_wrap_chart_func` and `validate_params`
implementations (we have 2026-04/05 copies and want to confirm they're
unchanged, especially the `__wrapped__` unwrap loop in `validate_params`).

3.2 Paste **verbatim** the *entire* chart/table-related auto-injected
namespace block from `script_exec_tools.py` (every `"name": ...,` line in
that group, in order). I specifically need to see:
   - whether `make_table` and `TableResult` are now injected, and with
     exactly what wrapping;
   - whether any chart **exception** class (e.g. `ChartError`,
     `ValidationError`) is injected as a name;
   - the total count of names in that block.

3.3 Paste **verbatim** the `from ai_development.mcp.utils.chart_functions
import (...)` line(s) at the top of `script_exec_tools.py`.

### 4. What exception type should chart code raise?

4.1 Given the routing code in §1.4: if `make_chart` raises, what exception
**type** lands on the `chart_function_error` hint (the chart-specific, most
helpful surfacing)? List every exception type the mapping special-cases for
charts, verbatim.

4.2 If `chart_functions.py` were to define and raise a new
`class ChartError(Exception)` (carrying the failure message), trace what the
LLM would see: does it fall through to the generic catch-all path, or can it
reach the chart-specific hint? Would raising the **existing**
`ValidationError` (already defined in `chart_functions.py`) route better?
Recommend which type to raise for cleanest LLM-facing surfacing, with the
reason grounded in the routing code you pasted.

### 5. Other consumers of `ChartResult.success` (drag-and-drop safety)

5.1 Search the repo for every caller of `make_chart`, `make_table`,
`make_2pack_*`, `make_3pack_*`, `make_4pack_grid`, `make_6pack_grid`, and
`make_composite` **outside** `script_exec_tools.py` (e.g. `report_workflow`,
`email_processing`, `jobs/`, dashboards, any batch/report worker). For each
hit, paste the call + the surrounding lines and state whether it branches on
`result.success == False` expecting a *graceful return*. If the engine
starts raising on failure, any such caller breaks — I need the complete list.

5.2 Confirm (or correct) the claim that `mcp/tools/script_exec_tools.py` is
the **sole** importer of `chart_functions.py` symbols inside PRISM.

### 6. Dashboard analog (for parity reasoning)

6.1 Confirm verbatim that `compile_dashboard(..., strict=True)` raises
`ValueError` on an error-severity diagnostic (paste the raise site + the
`strict` default). This is the dashboard-side precedent for "fail loud at
build time," and I want to confirm charts would be matching an existing
pattern rather than inventing one.

### 7. Tickets / observations related to swallowed chart errors

7.1 Search tickets / issues / observations / reports for anything about:
silent or swallowed chart failures; `make_chart` returning `success=False`
with no user-visible error; charts that "didn't render" with no error
surfaced; missing chart artifacts with no explanation; or general
`make_chart` / `make_table` error-handling complaints.

For each match, return: ticket ID / handle, title, status (open/closed),
date, reporter if available, a 1–2 line summary, and any root-cause notes or
decisions already recorded. If a fix or direction was decided, quote it.

7.2 If there is a ticketing/submission API the LLM can query
(`submit_ticket` implies a store), say how you searched and over what corpus,
so we know the coverage of the search.

### 8. Drift check

Report the current size (KB) and line count of
`mcp/tools/script_exec_tools.py` and `mcp/utils/chart_functions.py`. If
`chart_functions.py` differs materially from ~418 KB, say so — that means
staging and your installed copy have desynchronized.

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
no ticket store reachable), add a brief `## Could not resolve` section at the
end listing what you tried and what blocked it.
