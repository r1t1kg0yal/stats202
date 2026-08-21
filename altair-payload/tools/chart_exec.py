"""Chart-rendering engine behind the ``chart_agent`` sub-agent.

The chart engine is NOT imported at module scope. ``script_exec_tools`` imports
``format_chart_delivery_hint`` from here, and a top-level ``chart_functions``
import would put ``register_trusted_extensions`` back into that module's import
graph -- the coupling this split exists to remove.
"""

import asyncio
import contextlib
import functools
import inspect
import io
import logging
import re
import traceback
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.s3_bucket_manager import s3_manager
from core.swallowed_exceptions import log_swallowed_exception
from prism_mcp.utils.baggage import (
    resolve_kerberos_info_from_baggage as _resolve_kerberos_info_from_baggage,
    resolve_medium_from_baggage as _resolve_medium_from_baggage,
)
from prism_mcp.utils.code_preprocess_utils import preprocess_script_code
from prism_mcp.utils.download_links import generate_download_links_for_sandbox
from prism_mcp.utils.output_limits import SCRIPT_STDOUT_INLINE_BYTES
from prism_mcp.utils.session_registry import resolve_or_create as _resolve_or_create

logger = logging.getLogger('chart_exec')

# Rendering is CPU-bound and local; past this it is a runaway loop, not a slow chart.
CHART_EXECUTION_TIMEOUT_SECONDS = 90

# The operating contract tells the sub-agent to stop at five calls and to stop when
# the finding count stops falling. Both are prose, and a model is free to ignore
# prose -- so both are also counted here. Past the ceiling the call is refused
# before anything executes, which is what makes a runaway loop cheap instead of
# merely discouraged.
CHART_ATTEMPT_CEILING = 5

# Untruncated DataFrame repr, so a sub-agent that opens with `print(df1.head())`
# sees every column name rather than an ellipsis -- guessing a column name costs
# it a whole attempt. `profile_df` builds its own output and does not depend on
# these.
#
# Set at import rather than per render, which is where they used to live. The
# values never varied, so the two are equivalent in effect, but pandas options
# are process-global: written per render they were a mutation on the render path
# that silently reached every other user's `execute_analysis_script` repr in the
# same process. Written once at startup they are what they always were in
# practice -- a process-wide display choice this module makes on import,
# alongside the engine's other write-once globals.
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', None)


@dataclass
class _Invocation:
    """What belongs to one chart_agent invocation rather than one call.

    Both fields exist for the same reason: the caller can dispatch two chart
    agents in one turn, they resolve to the same session path, and neither can
    see the other.

    ``attempt`` / ``findings`` are the retry ladder. Keyed on the session instead,
    they told the second agent's very first call that it was on attempt 2 and not
    converging, on the strength of the first agent's unrelated chart -- a false
    stop signal, which is worse than no signal.

    ``token`` disambiguates the S3 keys this invocation writes. Two agents both
    asked for ``save_as='chart.png'`` produced one PNG and two reports naming it,
    losing a chart with no error anywhere. It is fixed for the invocation rather
    than per call, so a retry overwrites its own previous attempt instead of
    littering the session with near-duplicates.
    """

    token: str
    attempt: int = 0
    findings: int = 0


# A ContextVar rather than a dict keyed on anything: asyncio copies the context
# into each task, so agents dispatched concurrently never see each other's state,
# and the set/reset pair in `chart_invocation` keeps sequential ones from
# bleeding. Same mechanism `core.subagent_events._FRAMES` uses to keep concurrent
# sub-agent identity frames apart.
_INVOCATION: ContextVar[Optional[_Invocation]] = ContextVar('chart_invocation',
                                                            default=None)


@contextlib.contextmanager
def chart_invocation() -> Iterator[_Invocation]:
    """Scope one chart_agent invocation.

    Entered by the ``AgentTool`` wrapper in ``core/chart_agent_tool.py``, which is
    the only place that knows where an invocation starts and ends. Without it
    every invocation in the process shares whatever context it was called from.
    """
    state = _Invocation(token=uuid.uuid4().hex[:6])
    reset = _INVOCATION.set(state)
    try:
        yield state
    finally:
        _INVOCATION.reset(reset)


def _current_invocation() -> _Invocation:
    """This invocation's state, installing one when called outside a scope.

    Unscoped means ``render_charts`` was reached directly rather than through the
    sub-agent. Installing into the calling context keeps the ceiling counting and
    keys unique for that caller, without reaching across to any other.
    """
    state = _INVOCATION.get()
    if state is None:
        state = _Invocation(token=uuid.uuid4().hex[:6])
        _INVOCATION.set(state)
    return state

# The sub-agent forwards its reply verbatim, so the report has to say for itself
# which half is the caller's and which half is scaffolding. Sentinels rather than
# headings, because a heading has to be recognised by meaning while these can be
# recognised by an exact line match, and chart titles are free to contain anything.
#
# Nothing strips them today: the sub-agent is told not to echo the sentinel lines
# and that instruction is the only thing standing between them and a chat answer.
# Exact-matchability is what makes a mechanical strip cheap to add later; it is not
# itself that strip. See prism/subagents.md for the open question.
DELIVERY_OPEN = "===CHART_DELIVERY_START==="
DELIVERY_CLOSE = "===CHART_DELIVERY_END==="
DIAGNOSTICS_OPEN = "===CHART_DIAGNOSTICS_START==="
DIAGNOSTICS_CLOSE = "===CHART_DIAGNOSTICS_END==="

# The engine folds 2+ validation findings into one frame under this exact header
# (`chart_render/core.py::_aggregate_finding_messages`). A lone finding is re-raised
# verbatim with no header, so absence of a match means exactly one. Deliberately
# unanchored: in a formatted traceback the header trails the exception class name.
_AGGREGATE_RE = re.compile(r'(\d+) independent problems -- fix ALL, then re-run:')

# Plausible-sounding names the model reaches for instead of the documented ones.
# Remapped silently so the call lands without costing a retry.
#
# Split by destination, because the two are not interchangeable: `save_as` is a
# top-level kwarg, while the axis titles are mapping keys and the engine rejects
# them at top level by name. Rewriting an axis alias in place would swap one
# error for a worse one -- the model wrote `ylabel` and would be told about
# `y_title`, a name it never used.
_KWARG_ALIASES = {
    'save_path': 'save_as',
    'output_path': 'save_as',
    'filename': 'save_as',
    'file_name': 'save_as',
    'output_file': 'save_as',
}

_MAPPING_ALIASES = {
    'y_axis_label': 'y_title',
    'x_axis_label': 'x_title',
    'ylabel': 'y_title',
    'xlabel': 'x_title',
}


def _disambiguate(save_as: str, token: str) -> str:
    """Tag the leaf of an explicit ``save_as`` with this invocation's token.

    Only the leaf: ``save_as`` may already be rooted at a canonical S3 prefix,
    which the engine honours verbatim, and moving it would defeat that.
    """
    head, slash, leaf = save_as.rpartition('/')
    stem, dot, extension = leaf.rpartition('.')
    if not dot:
        stem, extension = leaf, ''
    return f"{head}{slash}{stem}_{token}{dot}{extension}"


def _wrap_chart_func(func, s3_mgr, session_path=None, user_id=None):
    """Inject s3_manager / session_path / user_id into every chart call.

    Positional args pass through -- the composite packs take ChartSpec objects
    positionally. functools.wraps keeps inspect.signature() resolving to the real
    function, which validate_params' error enrichment reads.
    """
    if func is None:
        return None

    try:
        _accepts_suffix = 'filename_suffix' in inspect.signature(func).parameters
    except (TypeError, ValueError):
        _accepts_suffix = False

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Canonical name wins when both are set.
        for alias, canonical in _KWARG_ALIASES.items():
            if alias in kwargs and canonical not in kwargs:
                kwargs[canonical] = kwargs.pop(alias)
            elif alias in kwargs:
                kwargs.pop(alias)
        # Copied, not mutated: the caller's dict is theirs, and a composite pack
        # can hand the same mapping to more than one spec.
        if any(alias in kwargs for alias in _MAPPING_ALIASES):
            mapping = dict(kwargs.get('mapping') or {})
            for alias, canonical in _MAPPING_ALIASES.items():
                value = kwargs.pop(alias, None)
                if value is not None and canonical not in mapping:
                    mapping[canonical] = value
            kwargs['mapping'] = mapping
        kwargs.pop('s3_manager', None)
        # Two chart agents charting into one session cannot see each other, so
        # neither can avoid the other's filenames. Tagging every key this
        # invocation writes is the only point where that is knowable. Auto-named
        # charts already carry a second-resolution timestamp; the suffix closes
        # the same-second case where the engine exposes one.
        invocation = _current_invocation()
        if kwargs.get('save_as'):
            kwargs['save_as'] = _disambiguate(kwargs['save_as'], invocation.token)
        elif _accepts_suffix and not kwargs.get('filename_suffix'):
            kwargs['filename_suffix'] = invocation.token
        # session_path forces use_s3=True, so a render never attempts a local write.
        if session_path and 'session_path' not in kwargs:
            kwargs['session_path'] = session_path
        if user_id and 'user_id' not in kwargs:
            kwargs['user_id'] = user_id
        result = func(*args, **kwargs, s3_manager=s3_mgr)
        # The only point where the result object is still in our hands. Generated
        # code is free to discard it, and usually does.
        s3_mgr.record(func, kwargs, result)
        return result

    return wrapper


def format_chart_delivery_hint(chart_count: int, medium: str = "",
                               linked: bool = False) -> str:
    """One-line reminder of how to deliver charts on the active medium.

    Emitted whenever a run produced at least one chart PNG.

    Args:
        chart_count: Number of successfully-rendered chart PNGs in this run.
        medium: Raw medium_query value; normalized through the medium SSOT.
        linked: True when the report already lists a short link for every chart,
            so the hint points at those rather than asking for a mint that would
            return the same deterministic slug.

    Returns:
        Markdown footer string, or '' when chart_count == 0.
    """
    if chart_count <= 0:
        return ""
    from core.configs.mediums import COMPOSER, EMAIL, GSAI, normalize_medium
    channel = normalize_medium(medium)
    if channel == EMAIL:
        how = ("embed each chart by referencing its S3 path in the inline JSON "
               "image spec")
    elif channel in (COMPOSER, GSAI):
        how = ("render each chart as `![title](link)` using the link listed beside its "
               "path above" if linked else
               "mint a link with `generate_download_links(<s3_path>)` and render "
               "each as `![title](short_url)`")
    else:
        how = "reference each chart by its S3 path"
    return (
        "\n\n---\n"
        "**[CHART DELIVERY]** This script produced "
        f"{chart_count} chart PNG(s). {how}.\n"
    )


class _ChartPathRecorder:
    """S3 proxy recording every ``.png`` key written, plus what wrote it.

    The write is the only signal that cannot be lost -- generated code is free to
    discard the returned ChartResult. Everything but ``put`` delegates, so routing
    and the ACL gate stay with the singleton.

    ``chart_paths`` is ground truth for what reached S3. ``artifacts`` is the
    richer story ``_wrap_chart_func`` hands over on the way past: the title, the
    type, the encoding, the warnings. The caller needs the second to describe what
    it is showing; without it a report can only list opaque keys.
    """

    def __init__(self, manager):
        self._manager = manager
        self.chart_paths: List[str] = []
        self.artifacts: List[Dict[str, Any]] = []

    def put(self, data, path, *args, **kwargs):
        result = self._manager.put(data, path, *args, **kwargs)
        if path.endswith('.png') and path not in self.chart_paths:
            self.chart_paths.append(path)
        return result

    def record(self, func, kwargs, result) -> None:
        """Capture one chart call's intent and outcome, keyed by the path it wrote."""
        mapping = kwargs.get('mapping') or {}
        self.artifacts.append({
            'call': getattr(func, '__name__', 'chart'),
            'title': kwargs.get('title'),
            'chart_type': kwargs.get('chart_type'),
            'path': getattr(result, 'png_path', None),
            'encoding': ', '.join(
                f'{key}={mapping[key]}'
                for key in ('x', 'y', 'color', 'value', 'theta', 'facet')
                if isinstance(mapping.get(key), str)
            ),
            'n_rows': getattr(result, 'n_rows', None),
            'n_cols': getattr(result, 'n_cols', None),
            'n_charts': getattr(result, 'n_charts', None),
            'warnings': list(getattr(result, 'warnings', None) or []),
        })

    def __getattr__(self, name):
        return getattr(self._manager, name)


def _chart_namespace(session_base_path: str, user_id: Optional[str],
                     recorder: _ChartPathRecorder) -> Dict[str, Any]:
    """Build the exec namespace: the chart engine's public API plus pandas/numpy."""
    from prism_mcp.utils.chart_functions import (
        make_chart, make_table, build_charts, TableResult, ChartResult, ChartSpec,
        profile_df, make_2pack_horizontal, make_2pack_vertical, make_3pack_triangle,
        make_4pack_grid, make_6pack_grid, VLine, HLine, Band, Arrow, PointLabel,
        PointHighlight, Callout, PlotText, Segment, LastValueLabel, Trendline,
    )
    from prism_mcp.utils.param_validator import validate_params
    # Deferred: script_exec_tools imports format_chart_delivery_hint from this
    # module, so a top-level import here would close the cycle.
    from prism_mcp.tools.script_exec_tools import CANONICAL_STDLIB_NAMESPACE

    def wrap(func):
        return validate_params(_wrap_chart_func(func, recorder, session_base_path, user_id=user_id))

    return {
        'pd': pd,
        'np': np,
        's3_manager': recorder,
        'SESSION_PATH': session_base_path,
        **CANONICAL_STDLIB_NAMESPACE,
        'make_chart': wrap(make_chart),
        'make_table': wrap(make_table),
        'make_2pack_horizontal': wrap(make_2pack_horizontal),
        'make_2pack_vertical': wrap(make_2pack_vertical),
        'make_3pack_triangle': wrap(make_3pack_triangle),
        'make_4pack_grid': wrap(make_4pack_grid),
        'make_6pack_grid': wrap(make_6pack_grid),
        # Bare: each thunk closes over its own wired make_chart call.
        'build_charts': validate_params(build_charts),
        'profile_df': profile_df,
        'TableResult': TableResult,
        'ChartResult': ChartResult,
        'ChartSpec': ChartSpec,
        'VLine': VLine,
        'HLine': HLine,
        'Band': Band,
        'Arrow': Arrow,
        'PointLabel': PointLabel,
        'PointHighlight': PointHighlight,
        'Callout': Callout,
        'PlotText': PlotText,
        'Segment': Segment,
        'LastValueLabel': LastValueLabel,
        'Trendline': Trendline,
    }


def _load_data_files(namespace: Dict[str, Any], data_files: Optional[List[str]]) -> None:
    """Bind each S3 CSV in ``data_files`` as ``df1``, ``df2``, ... in index order."""
    for i, file_path in enumerate(data_files or [], 1):
        csv_bytes = s3_manager.get(file_path)
        namespace[f'df{i}'] = pd.read_csv(io.BytesIO(csv_bytes), index_col=0, parse_dates=True)


def _truncate(text: str) -> str:
    if len(text.encode('utf-8')) <= SCRIPT_STDOUT_INLINE_BYTES:
        return text
    return text[:SCRIPT_STDOUT_INLINE_BYTES] + "\n... [stdout truncated]"


def _ladder_step() -> Tuple[_Invocation, int, int]:
    """Advance this invocation's ladder, returning ``(state, attempt, prev_findings)``."""
    state = _current_invocation()
    return state, state.attempt + 1, state.findings


def _classify_failure(exc: BaseException, error_text: str,
                      stage: str = 'exec') -> Tuple[str, str, int]:
    """Say whether re-writing the code could plausibly help.

    A flat attempt counter spends the same budget on a fix that is converging and
    on a timeout guaranteed to reproduce. That distinction only exists here, where
    the exception object still does.

    ``stage`` separates the two things that can fail. Reading the input CSVs is not
    something the sub-agent can fix by rewriting chart code -- it never chose those
    paths, the caller did -- so a load failure is FATAL however retryable the same
    exception type would be coming out of the script.
    """
    if stage == 'load':
        return 'FATAL', (
            f'{type(exc).__name__} reading the input CSVs: {exc}. The path came '
            f'from the caller; no chart code can fix it'
        ), 0
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return 'FATAL', (
            f'execution exceeded CHART_EXECUTION_TIMEOUT_SECONDS '
            f'({CHART_EXECUTION_TIMEOUT_SECONDS}s); the same code will time out again'
        ), 0
    if isinstance(exc, (MemoryError, RecursionError)):
        return 'FATAL', f'{type(exc).__name__}: the render exhausted the worker', 0
    # The count is the convergence signal across attempts: a retry that does not
    # reduce it is not making progress.
    aggregate = _AGGREGATE_RE.search(error_text)
    return 'RETRYABLE', type(exc).__name__, int(aggregate.group(1)) if aggregate else 1


def _describe_artifact(art: Dict[str, Any], path: str = '') -> str:
    """One line naming what an artifact shows, for the caller to write prose against.

    A PNG whose result object carried no ``png_path`` has no manifest entry to join
    against, so everything below is missing. The filename still says something, and
    a naked separator with nothing after it says less than no separator at all.
    """
    title = art.get('title')
    if title:
        head = f"**{title}**"
    elif path:
        head = f"**{path.rsplit('/', 1)[-1].rsplit('.', 1)[0]}**"
    else:
        head = "_(untitled)_"
    facts = [str(art.get('chart_type') or art.get('call'))]
    if art.get('n_charts'):
        facts.append(f"{art['n_charts']} panels")
    if art.get('n_rows') is not None and art.get('n_cols') is not None:
        facts.append(f"{art['n_rows']} rows x {art['n_cols']} cols")
    if art.get('encoding'):
        facts.append(art['encoding'])
    facts = [fact for fact in facts if fact and fact != 'None']
    return f"{head} -- {' | '.join(facts)}" if facts else head


def format_report(session_path: str, chart_paths: List[str], links: List[Dict[str, Any]],
                  stdout: str, error: str, medium: str,
                  artifacts: Optional[List[Dict[str, Any]]] = None,
                  status: str = 'OK', status_detail: str = '',
                  n_findings: int = 0, attempt: int = 1,
                  previous_findings: int = 0) -> str:
    """Assemble the two-block report the sub-agent reads and half-forwards.

    Everything the sub-agent returns is pasted into the caller's answer, so the
    report separates what is meant to travel from what never should. The delivery
    block holds paths, links and one line per artifact saying what it shows. The
    diagnostics block holds warnings, stdout and tracebacks -- the retry loop's
    material, and nothing a reader should ever see.

    ``links`` is the ``generate_download_links_for_sandbox`` result for
    ``chart_paths``, or empty on media where a shortlink reaches nothing.
    """
    short_by_path = {
        link['s3_path']: link['short_url']
        for link in links if link.get('success') and link.get('short_url')
    }
    artifacts = artifacts or []
    by_path = {art['path']: art for art in artifacts if art.get('path')}

    out = [DELIVERY_OPEN, "\n\n", f"**Session**: `{session_path}`\n\n"]
    if chart_paths:
        out.append(f"**Charts**: {len(chart_paths)} PNG(s)\n\n")
        for i, path in enumerate(chart_paths, 1):
            out.append(f"{i}. {_describe_artifact(by_path.get(path, {}), path)}\n")
            short = short_by_path.get(path)
            out.append(f"   `{path}`" + (f" -> {short}\n" if short else "\n"))
        out.append(format_chart_delivery_hint(
            len(chart_paths), medium,
            linked=len(short_by_path) == len(chart_paths)))
    else:
        out.append("No chart PNG was written by this run.\n")
    out.append(f"\n{DELIVERY_CLOSE}\n\n")

    out.append(f"{DIAGNOSTICS_OPEN}\n")
    out.append("Yours alone. Never quote, paraphrase or summarise any of it.\n\n")
    out.append(f"status: {status}")
    out.append(f" ({n_findings} finding(s))\n" if n_findings else "\n")
    out.append(f"attempt: {attempt} of {CHART_ATTEMPT_CEILING}\n")
    if status_detail:
        out.append(f"reason: {status_detail}\n")
    # The ceiling is a hard stop; this is the softer one the contract asks for, and
    # the model cannot compute it -- each call is all it can see.
    if status == 'RETRYABLE' and previous_findings and n_findings >= previous_findings:
        out.append(f"findings did not fall (was {previous_findings}, now {n_findings}); "
                   f"this approach is not converging -- change it or stop\n")
    flagged = [(art, w) for art in artifacts for w in art['warnings']]
    if flagged:
        out.append(f"\nwarnings ({len(flagged)}):\n")
        for art, warning in flagged:
            out.append(f"- {art.get('title') or art.get('call')}: {warning}\n")
    if stdout.strip():
        out.append(f"\nstdout:\n```\n{_truncate(stdout)}\n```\n")
    if error:
        out.append(f"\ntraceback:\n```\n{error}\n```\n")
    out.append(DIAGNOSTICS_CLOSE)
    return "".join(out)


async def render_charts(session_path: str, chart_code: str,
                        data_files: Optional[List[str]] = None) -> str:
    """Run chart-building Python and return a markdown report of what it produced.

    The code runs in a namespace that already holds `make_chart`, `make_table`,
    `build_charts`, `profile_df`, `ChartSpec`, the five composite packs
    (`make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`,
    `make_4pack_grid`, `make_6pack_grid`), every annotation class (`VLine`,
    `HLine`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`,
    `PlotText`, `Segment`, `LastValueLabel`, `Trendline`), plus `pd`, `np`,
    `SESSION_PATH` and the stdlib essentials. Write NO imports for any of these.

    `s3_manager`, `session_path` and `user_id` are injected into every chart call
    automatically -- never pass them yourself.

    Args:
        session_path: The session the charts belong to. Pass the caller's session
            path unchanged so the PNGs land beside the rest of that session's work.
        chart_code: Python that calls the chart functions. `print()` goes to the
            diagnostics block, which the caller never sees, so print freely.
        data_files: S3 paths of CSVs to load, bound in order as `df1`, `df2`, ...
            Each is read with the first column as a parsed datetime index. You
            have not seen these frames; `profile_df(df1)` before you bind a
            column name you are not certain of.

    Returns:
        Two fenced blocks. `===CHART_DELIVERY_START===` holds what the caller
        needs -- every PNG written, a browser link where the medium supports one,
        and a line per artifact naming what it shows. `===CHART_DIAGNOSTICS_START===`
        holds a `status:` line (OK / RETRYABLE / NO_ARTIFACTS / FATAL), engine
        warnings, stdout and any traceback; it is for your retry loop and must
        not appear in your reply.
    """
    from core.configs.mediums import COMPOSER, GSAI, normalize_medium
    from core.code_execution import _execute_sync

    baggage_info = _resolve_kerberos_info_from_baggage()
    kerberos = baggage_info.get('kerberos') or ''
    # Tier 3 is the server process's own identity, not the end user -- passing
    # it would stamp the wrong owner onto a newly minted session folder.
    if kerberos and baggage_info.get('winning_tier', '') != 'tier3_server_kerberos':
        resolved_path, _ = _resolve_or_create(session_path, kerberos=kerberos)
    else:
        resolved_path, _ = _resolve_or_create(session_path)

    medium = _resolve_medium_from_baggage()
    invocation, attempt, previous_findings = _ladder_step()

    if attempt > CHART_ATTEMPT_CEILING:
        # Recorded, not cleared. Clearing here made the ceiling a speed bump: the
        # refusal reset the count, so call seven ran as attempt 1 and a runaway
        # loop got five more renders for the price of one refused call. The ladder
        # is scoped to this invocation and dies with it, so holding the count past
        # the ceiling strands nothing.
        invocation.attempt = attempt
        logger.warning(f"[chart_exec] session={resolved_path} refused: attempt "
                       f"{attempt} past the ceiling of {CHART_ATTEMPT_CEILING}")
        return format_report(
            resolved_path, [], [], "", "", medium, artifacts=[], status='FATAL',
            status_detail=(f'{CHART_ATTEMPT_CEILING} render_charts calls already '
                           f'made for this session; nothing was executed'),
            attempt=attempt)

    recorder = _ChartPathRecorder(s3_manager)
    namespace = _chart_namespace(resolved_path, kerberos or None, recorder)

    stdout = ""
    error = ""
    status, status_detail, n_findings = 'OK', '', 0
    # Reading the CSVs belongs inside the guard: a path relayed from the caller is
    # the likeliest thing in this call to be wrong, and raising out of the tool
    # would skip the whole two-block protocol the sub-agent is trained on.
    stage = 'load'
    try:
        _load_data_files(namespace, data_files)
        stage = 'exec'
        code, _preprocess_notes = preprocess_script_code(chart_code)
        result = await asyncio.wait_for(
            asyncio.to_thread(_execute_sync, code, namespace),
            timeout=CHART_EXECUTION_TIMEOUT_SECONDS,
        )
        stdout = result['stdout']
    except Exception as exc:
        # why: a failing chart script is a result the sub-agent retries against,
        # not an abort of the parent's turn -- the traceback has to reach the
        # model as text. The namespace is dropped either way below.
        log_swallowed_exception(exc, where="chart_exec.render_charts")
        stdout = getattr(exc, '_partial_stdout', '') or ''
        error = traceback.format_exc()
        status, status_detail, n_findings = _classify_failure(exc, error, stage)

    # The abandoned worker thread keeps running past a timeout; clearing the dict
    # in place drops its grip on every DataFrame and closure it holds.
    artifacts = list(recorder.artifacts)
    namespace.clear()

    # Clean exit that drew nothing is its own failure: today it reports as success
    # with an empty chart list, which reads like a delivered answer.
    if status == 'OK' and not recorder.chart_paths:
        status = 'NO_ARTIFACTS'
        status_detail = 'the script completed without calling a chart function'

    # A terminal status ends the ladder: the sub-agent has no reason to call again,
    # and if it does anyway it starts clean rather than inheriting a dead retry.
    if status in ('OK', 'FATAL'):
        invocation.attempt, invocation.findings = 0, 0
    else:
        invocation.attempt, invocation.findings = attempt, n_findings

    links = []
    if recorder.chart_paths and normalize_medium(medium) in (COMPOSER, GSAI):
        links = generate_download_links_for_sandbox(recorder.chart_paths)

    logger.info(
        f"[chart_exec] session={resolved_path} charts={len(recorder.chart_paths)} "
        f"medium={medium} status={status} findings={n_findings} "
        f"attempt={attempt}/{CHART_ATTEMPT_CEILING}"
    )
    return format_report(resolved_path, recorder.chart_paths, links, stdout, error, medium,
                         artifacts=artifacts, status=status, status_detail=status_detail,
                         n_findings=n_findings, attempt=attempt,
                         previous_findings=previous_findings)
