"""Charting ``AgentTool`` for the gs_llm2 ADK agent.

Charting is an exec engine, not a parameterised call: ``make_chart`` takes live
DataFrames, so there is no JSON tool schema that can carry a chart request.
Prism therefore writes chart code the same way it always has -- what moves is
where that code runs and who reads the ~69 KB of chart guidance needed to write
it. Both now sit behind this sub-agent, off the main agent's context budget.

``AgentTool`` runs the sub-agent on a session of its own seeded with nothing but
the ``request`` string, so the request must carry the session path and the S3
CSVs the charts are built from -- the two things the sub-agent cannot look up.
DataFrames cross that boundary as files, which is the channel
``execute_analysis_script`` already writes them to.
"""

import logging

# Share gs_llm2's logger namespace so these lines interleave with the rest of the agent's.
_log = logging.getLogger("prism.gs_llm2")

# The corpus is byte-stable across calls, so it earns the long breakpoint.
CACHE_TTL = "1h"

# Hub first, then spokes. A literal list, not a registry read: none of these are
# registered any more.
_CORPUS_SOURCES = (
    "static/tools/chart_context.md",
    "static/tools/charts/chart_context_colors.md",
    "static/tools/charts/chart_context_dual_axis.md",
    "static/tools/charts/chart_context_annotations.md",
    "static/tools/charts/chart_context_composites.md",
    "static/tools/charts/chart_context_grids.md",
    "static/tools/charts/chart_context_tables.md",
)

_OPERATING_CONTRACT = """\
You render charts. You do not analyse, advise, or comment on the data.

The request names a session path, zero or more S3 CSV paths, and the charts to
build. Write Python against the chart API documented below and pass it to
`render_charts` with that session path and those CSV paths. The CSVs arrive in
your namespace as `df1`, `df2`, ... in the order you list them.

You have never seen those frames. Their column names, dtypes, category counts
and label lengths decide whether a call clears the readability gates below, so
when the request does not pin a column exactly, open with `profile_df(df1)` and
bind what it reports. Guessing a column name costs a whole attempt.

Build every chart the request asks for in ONE `render_charts` call, using
`build_charts()` when there are two or more, so a failure surfaces all of them
at once.

The tool returns two fenced blocks with different audiences. Read both.

  ===CHART_DELIVERY_START===  ...  ===CHART_DELIVERY_END===
      The caller's. When it lists at least one PNG, reply with the contents of
      this block VERBATIM: the whole block, unchanged, nothing added before or
      after, and never the sentinel lines themselves. It carries the S3 paths,
      the links and the delivery instruction the caller needs; summarising it
      destroys them.

  ===CHART_DIAGNOSTICS_START===  ...  ===CHART_DIAGNOSTICS_END===
      Yours. Warnings, stdout and tracebacks, for your retry loop. Never quote,
      paraphrase or summarise any of it, and never show a traceback to anyone.

Its `status:` line tells you what to do next:

  OK            Done. Reply with the delivery block.
  RETRYABLE     Every independent defect is named and counted. Fix them all in
                one pass and call again. Keep going while the finding count
                falls. When a pass fails to reduce it, or when the data plainly
                cannot support what was asked, stop.
  NO_ARTIFACTS  The code ran but wrote no PNG -- usually a chart function was
                never called, or its result was swallowed. Call again.
  FATAL         Do not retry. The same code fails the same way.

Five `render_charts` calls is the ceiling. Never wrap a chart call in
try/except; the traceback is the diagnostic.

If you stop without a PNG, do not paste the delivery block. Reply with one
plain sentence naming what could not be built and why, drawn from the
diagnostics but quoting none of it.
"""


def _chart_corpus() -> str:
    """Concatenate the chart hub and its spokes into one instruction block."""
    from context.loader import MODULES_DIR

    parts = []
    for source in _CORPUS_SOURCES:
        path = MODULES_DIR / source
        assert path.exists(), (
            f"chart corpus file missing: {path} -- a rename must be mirrored in "
            f"_CORPUS_SOURCES, or the sub-agent silently loses that guidance"
        )
        parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


def chart_agent_tool(worker_id: str, event_callback=None):
    """Build the ``AgentTool`` wrapping the charting agent.

    Built fresh per query to match ``local_adk_tools``' fresh-stack-per-query discipline.
    Imports are deferred so this module stays importable without google-adk.

    ``event_callback`` is the caller's structured-event sink. The sub-agent runs on a Runner of
    its own, so its tool loop reaches that sink only through the ADK callbacks attached below;
    without them the whole charting run is a single opaque ``chart_agent`` row in the lane.
    """
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm
    from google.adk.tools import AgentTool, FunctionTool
    from core.gs_llm2 import (
        APP_ID, ENV, PRISM_MAX_OUTPUT_TOKENS, PRISM_MODEL_ID, _install_cache_and_io, get_token,
    )
    from prism_mcp.tools.chart_exec import render_charts
    from core.subagent_events import subagent_callbacks

    corpus = _chart_corpus()
    llm_model = LiteLlm(
        model=f"openai/{PRISM_MODEL_ID}",
        api_base=f"https://{ENV}.gpt.site.gs.com/models-gateway/api/openai",
        api_key=get_token(),
        max_completion_tokens=PRISM_MAX_OUTPUT_TOKENS,
        extra_headers={"app_id": APP_ID, "exclude_from_history": "true"},
    )
    # LiteLLM strips cache_control on the `openai` provider; a surviving marker is
    # what makes the corpus cheap.
    _install_cache_and_io(llm_model, CACHE_TTL, worker_id)

    chart_agent = Agent(
        name="chart_agent",
        model=llm_model,
        description=(
            "Renders charts and tables to PNG. Send it the session path, the S3 paths of the "
            "CSVs holding the data, and what each chart should show; it returns the S3 paths "
            "and links of the PNGs it wrote. Paste its reply into your answer verbatim."
        ),
        # Callable provider -> ADK uses the text verbatim instead of running {var}
        # state-injection over it, which the corpus's literal braces would break.
        instruction=lambda ctx: f"{_OPERATING_CONTRACT}\n\n---\n\n{corpus}",
        tools=[FunctionTool(func=render_charts)],
        **subagent_callbacks("chart_agent", event_callback),
    )
    _log.info(
        f"[LLM] ({worker_id}) chart AgentTool attached "
        f"(model={PRISM_MODEL_ID}, corpus={len(corpus)}B)"
    )
    return AgentTool(agent=chart_agent)