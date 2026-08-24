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

from __future__ import annotations

# The corpus is byte-stable across calls, so it earns the long breakpoint.
CACHE_TTL = "1h"

# Which model runs the charting sub-agent. Flip this literal to switch; it is a
# catalog KEY from core/configs/model_catalog.py, resolved to a gateway model id
# at build time so a typo fails loudly at the first chart call rather than
# silently falling back to the process default.
#   "opus"          -- Claude Opus (the process default)
#   "gemini_flash"  -- Gemini 3.7 Flash
CHART_AGENT_MODEL_KEY = "opus"

# How hard that model thinks. Same shape as the key above -- flip the literal -- and
# validated against the chosen route's vocabulary when the sub-agent is built, so a
# level the route refuses fails at attach rather than as a gateway 422.
#  None      -- name no effort, take the route's catalog default (DEFAULT_EFFORT_LEVEL,
#               env PRISM_EFFORT, currently "high"). This is the pre-existing behaviour.
#  "low" | "medium" | "high" | "xhigh" | "max" -- Claude accepts all five; the OpenAI
#               route stops at "xhigh"; gemini publishes thought text only up to "high".
# Charting is code-writing against a fixed API rather than open-ended reasoning, so this
# is the first knob to turn down if chart latency is the complaint.
CHART_AGENT_EFFORT = "low"

# Hub first, then spokes. A literal list, not a registry read; none of these are
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

===CHART_DELIVERY_START=== ... ===CHART_DELIVERY_END===
    The caller's. When it lists at least one PNG, reply with the contents of
    this block VERBATIM: the whole block, unchanged, nothing added before or
    after, and never the sentinel lines themselves. It carries the S3 paths,
    the links and the delivery instruction the caller needs; summarising it
    destroys them.

===CHART_DIAGNOSTICS_START=== ... ===CHART_DIAGNOSTICS_END===
    Yours. Warnings, stdout and tracebacks, for your retry loop. Never quote,
    paraphrase or summarise any of it, and never show a traceback to anyone.

Its `status:` line tells you what to do next:

OK             Done. Reply with the delivery block.
RETRYABLE      Every independent defect is named and counted. Fix them all in
               one pass and call again. The block says which attempt you are on
               and says so outright when the finding count has stopped falling;
               when it does, or when the data plainly cannot support what was
               asked, stop.
NO_ARTIFACTS   The code ran but wrote no PNG -- usually a chart function was
               never called, or its result was swallowed. Call again.
FATAL          Do not retry. The same code fails the same way. A CSV path that
               does not exist arrives this way too; the caller chose that path,
               so name it as missing rather than guessing at another.

Five `render_charts` calls is the ceiling and it is enforced -- a sixth is
refused without running. Never wrap a chart call in try/except; the traceback is
the diagnostic.

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

    Built fresh per query to match ``local_adk_tools`` fresh-stack-per-query discipline.
    Imports are deferred so this module stays importable without google-adk.

    ``event_callback`` is the caller's structured-event sink. The sub-agent runs on a Runner of
    its own, so its tool loop reaches that sink only through the ADK callbacks ``subagent_tool``
    attaches; without them the whole charting run is a single opaque ``chart_agent`` row.

    The invocation scope is what ``render_charts`` counts its retry ladder against: two chart
    agents in one turn resolve to the same session path and neither can see the other.
    """
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
        description=(
            "The renderer for every chart and table Prism produces. Send it the session path, "
            "the s3 paths of the CSVs holding the data, and what each chart or table should "
            "show; it returns the s3 paths and links of the PNGs it wrote. Paste its reply "
            "into your answer verbatim."
        ),
        # Callable provider -> ADK uses the text verbatim instead of running {var}
        # state-injection over it, which the corpus's literal braces would break.
        instruction=lambda ctx: f"{_OPERATING_CONTRACT}\n\n---\n\n{corpus}",
        tools=[FunctionTool(func=render_charts)],
        attached=f"chart AgentTool attached (model={model_id}, corpus={len(corpus)}B)",
        event_callback=event_callback,
        cache_ttl=CACHE_TTL,
        effort=CHART_AGENT_EFFORT,
        invocation_state=ChartInvocation,
    )
