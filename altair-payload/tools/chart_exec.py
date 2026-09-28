"""Chart-rendering engine behind the ``chart_agent`` sub-agent.

The chart engine is NOT imported at module scope. ``script_exec_tools`` imports
``format_chart_delivery_hint`` from here, and a top-level ``chart_functions``
import would put ``register_trusted_extensions`` back into that module's import
graph -- the coupling this split exists to remove.
"""

import asyncio
import functools
import inspect
import io
import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.agent_base import Invocation, current_invocation
from core.s3_bucket_manager import s3_manager
from prism_mcp.tools.artifact_report import ReportShape, format_report as _format_report
from prism_mcp.tools.sandbox_rollout import SandboxUnavailable
from prism_mcp.utils.baggage import (
    resolve_kerberos_info_from_baggage as _resolve_kerberos_info_from_baggage,
    resolve_medium_from_baggage as _resolve_medium_from_baggage,
)
from prism_mcp.utils.chart_call_log import record_render_call
from prism_mcp.utils.code_preprocess_utils import (
    GENERATED_CODE_PREEXEC_CHECKS,
    preprocess_script_code,
)
from prism_mcp.utils.download_links import generate_download_links_for_sandbox
from prism_mcp.utils.session_registry import resolve_or_create as _resolve_or_create

logger = logging.getLogger('chart_exec')

# Rendering is CPU-bound and local; past this it is a runaway loop, not a slow chart.
CHART_EXECUTION_TIMEOUT_SECONDS = 180

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
class ChartInvocation(Invocation):
    """What belongs to one chart_agent invocation rather than one call.

    The fields exist for the same reason: the caller can dispatch two chart
    agents in one turn, they resolve to the same session path, and neither can
    see the other.

    ``attempt`` / ``findings`` are the retry ladder. Keyed on the session instead,
    they told the second agent's very first call that it was on attempt 2 and not
    converging, on the strength of the first agent's unrelated chart -- a false
    stop signal, which is worse than no signal.

    ``sequence`` splits off the inherited ``token``, and that split is the whole
    design. The token is fixed for the invocation, so a retry overwrites its own
    previous attempt instead of littering the session with near-duplicates.
    ``sequence`` counts calls within one attempt and resets at the top of every
    ``render_charts``, so two artifacts in one script never collide while call N
    of attempt 2 still lands on call N of attempt 1.

    Both halves are load-bearing and each was missing once. Without the token,
    two agents asked for ``save_as='chart.png'`` and produced one PNG that two
    delivery blocks named. Without the sequence, two same-titled artifacts in one
    ordinary script did the same thing with no concurrency involved at all --
    charts survived only because their names carry a second-resolution timestamp
    and a render usually crosses a second boundary.

    ``delivered`` is what the last ``render_charts`` call wrote to S3, and the
    caller's pictures are built from it at the AgentTool seam rather than from
    the report the sub-agent forwards -- a renderer that summarised its reply,
    or dropped a line, still hands the caller its own renders. Assigned rather
    than extended, so a retry supersedes its own earlier attempt instead of
    offering the caller both.
    """

    attempt: int = 0
    findings: int = 0
    sequence: int = 0
    delivered: List[str] = field(default_factory=list)

    def next_key_token(self) -> str:
        """The nonce for the next artifact this invocation writes."""
        self.sequence += 1
        return f"{self.token}{self.sequence}"


# See prism/subagents.md for the open question about stripping these.
_SHAPE = ReportShape(
    noun='CHART', plural='Charts', artifact='chart PNG',
    ceiling=CHART_ATTEMPT_CEILING,
    describe=lambda art, path: _describe_artifact(art, path),
    delivery_hint=lambda count, medium: format_chart_delivery_hint(count, medium),
)

DELIVERY_OPEN = _SHAPE.delivery_open
DELIVERY_CLOSE = _SHAPE.delivery_close
DIAGNOSTICS_OPEN = _SHAPE.diagnostics_open
DIAGNOSTICS_CLOSE = _SHAPE.diagnostics_close

format_report = functools.partial(_format_report, _SHAPE)

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


def _disambiguate(save_as: str, token: str, base: str) -> str:
    """Tag the leaf of an explicit ``save_as`` with this call's nonce.

    Only the leaf: ``save_as`` may already be rooted at a canonical S3 prefix,
    which the engine honours verbatim, and moving it would defeat that.

    Idempotent within an invocation, because the input is not always the model's
    own. A delivery block lists tagged paths, and a model that copies one back as
    ``save_as`` on a retry would otherwise get ``chart_a1b2c31_a1b2c32.png`` --
    growing a suffix per attempt and defeating the overwrite the fixed token
    exists to give. Stripping is keyed on ``base``, this invocation's own token,
    so only a tag this invocation wrote is removed: a stem that merely looks
    hex-ish, or one tagged by some earlier invocation, is left alone.
    """
    head, slash, leaf = save_as.rpartition('/')
    stem, dot, extension = leaf.rpartition('.')
    if not dot:
        stem, extension = leaf, ''
    if base:
        stem = re.sub(rf'_{re.escape(base)}\d+$', '', stem)
    return f"{head}{slash}{stem}_{token}{dot}{extension}"


def _wrap_chart_func(func, recorder, session_path=None, user_id=None):
    """Inject s3_manager / session_path / user_id into every chart call.

    Positional args pass through -- the composite packs take ChartSpec objects
    positionally. functools.wraps keeps inspect.signature() resolving to the real
    function, which validate_params' error enrichment reads.

    ``recorder`` must be a ``_ChartPathRecorder``, not a bare ``S3BucketManager``:
    the artifact manifest is built by calling ``.record()`` after every chart, so
    a plain manager raises ``AttributeError`` on the first call. Only
    ``_chart_namespace`` constructs these today and it passes the recorder, but
    the name says so rather than leaving the next caller to find out.
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
        # Nothing else in the stack can make two artifacts distinct. Two chart
        # agents in one session cannot see each other's filenames, and two calls
        # in one script cannot see each other's either -- the engine names from
        # title and clock alone, so same title plus same second is one file and a
        # silently lost chart. The nonce closes both: the invocation half keeps
        # concurrent agents apart, the per-call half keeps one script's own calls
        # apart, and because the per-call half restarts each render, a retry's
        # Nth artifact overwrites the previous attempt's Nth rather than
        # accumulating.
        invocation = current_invocation(ChartInvocation)
        token = invocation.next_key_token()
        if kwargs.get('save_as'):
            kwargs['save_as'] = _disambiguate(kwargs['save_as'], token,
                                              invocation.token)
        elif _accepts_suffix and not kwargs.get('filename_suffix'):
            kwargs['filename_suffix'] = token
        # session_path forces use_s3=True, so a render never attempts a local write.
        if session_path and 'session_path' not in kwargs:
            kwargs['session_path'] = session_path
        if user_id and 'user_id' not in kwargs:
            kwargs['user_id'] = user_id
        result = func(*args, **kwargs, s3_manager=recorder)
        # The only point where the result object is still in our hands. Generated
        # code is free to discard it, and usually does.
        recorder.record(func, kwargs, result)
        return result

    return wrapper


def format_chart_delivery_hint(chart_count: int, medium: str = "") -> str:
    """One-line reminder of how to deliver charts on the active medium.

    Emitted whenever a run produced at least one chart PNG.

    Args:
        chart_count: Number of successfully-rendered chart PNGs in this run.
        medium: Raw medium_query value; normalized through the medium SSOT.

    Returns:
        Markdown footer string, or '' when chart_count == 0.
    """
    if chart_count <= 0:
        return ""
    # The GS AI entrypoint is retired. "gsai" survives only as an alias the
    # medium SSOT folds into COMPOSER, so there is no second constant to branch
    # on -- importing one is an ImportError at first call, not a dead branch.
    from core.configs.mediums import COMPOSER, EMAIL, normalize_medium
    channel = normalize_medium(medium)
    if channel == EMAIL:
        how = ("embed each chart by referencing its S3 path in the inline JSON "
               "image spec")
    elif channel == COMPOSER:
        how = ("render each chart as `![title](link)` using the link listed beside "
               "its path above")
    else:
        how = "reference each chart by its S3 path"
    return (
        "\n\n---\n"
        "**[CHART DELIVERY]** This script produced "
        f"{chart_count} chart PNG(s). {how}.\n"
    )


# The key set of an artifact record, and the only place it is written down.
# `format_report` and `record_render_call` both read these dicts, so the shape is
# a contract between three functions and was previously only a convention held in
# one dict literal.
ARTIFACT_KEYS = ('call', 'title', 'chart_type', 'path', 'encoding',
                 'n_rows', 'n_cols', 'n_charts', 'warnings')


def _new_artifact(func, kwargs, result) -> Dict[str, Any]:
    """One chart call described: what was asked for, and what came back.

    Every key in ``ARTIFACT_KEYS`` is written unconditionally, missing values as
    None or empty rather than as an absent key. Readers are still tolerant, but
    they are tolerant of something that does not happen -- which is the property
    a factory can guarantee and a dict literal at a call site cannot.
    """
    mapping = kwargs.get('mapping') or {}
    return {
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
    }


class _ChartPathRecorder:
    """S3 surface recording every ``.png`` key written, plus what wrote it.

    The write is the only signal that cannot be lost -- generated code is free to
    discard the returned ChartResult. ``put`` records; the rest of the surface is
    the bucket manager's gated verbs, so routing and the ACL gate stay with the
    singleton.

    Delegation is explicit methods rather than ``__getattr__``: this object is
    bound as ``s3_manager`` in a namespace running model-authored Python, and a
    proxy would re-export the whole manager, raw boto3 client included -- one
    generated line reaching ``s3_client`` reads and overwrites the bucket with no
    ACL in the path. The delegated set is the bucket manager's gated verbs;
    ``s3_client`` and ``bucket_name`` are not among them. Adding a verb should
    cost someone a line of thought.

    The verbs are CLOSURES built in ``__init__``, so the manager lives in a cell
    rather than on the instance. Anything that hands it back by name -- an
    attribute, or a module function taking the surface -- is the same single
    generated line ``self._manager`` was, under a name
    ``code_preprocess_utils._ESCAPE_ATTRS`` does not carry, so nothing logs the
    walk either. A closure leaves ``__closure__`` as the only route, and that
    tuple does carry it. This narrows the reach; it does not contain it. Only the
    execution substrate can close that.

    ``chart_paths`` is ground truth for what reached S3. ``artifacts`` is the
    richer story ``_wrap_chart_func`` hands over on the way past: the title, the
    type, the encoding, the warnings. The caller needs the second to describe what
    it is showing; without it a report can only list opaque keys.
    """

    def __init__(self, manager):
        self.chart_paths: List[str] = []
        self.artifacts: List[Dict[str, Any]] = []

        def put(data, path, *args, **kwargs):
            result = manager.put(data, path, *args, **kwargs)
            self.adopt(path)
            return result

        def get(path):
            return manager.get(path)

        def exists(path):
            return manager.exists(path)

        def show_all(prefix=""):
            return manager.show_all(prefix)

        def list_(prefix=""):
            return manager.list(prefix)

        def delete(path):
            return manager.delete(path)

        def move(src, tgt):
            return manager.move(src, tgt)

        self.put = put
        self.get = get
        self.exists = exists
        self.show_all = show_all
        self.list = list_
        self.delete = delete
        self.move = move

    def adopt(self, path: str) -> None:
        """Record a chart key the run wrote, whichever side of the boundary wrote it.

        An ordinary method while the verbs above are closures, because the two
        hide different things. The closures exist to keep ``manager`` off the
        instance; this touches only ``chart_paths``, so exposing it by name gives
        generated code nothing. It has to be reachable by name -- the sandbox seam
        takes it as a callback (``adopt=recorder.adopt``), which is how a render
        that ran off-box still lands in ``chart_paths``.
        """
        if path.endswith('.png') and path not in self.chart_paths:
            self.chart_paths.append(path)

    def record(self, func, kwargs, result) -> None:
        """Capture one chart call's intent and outcome, keyed by the path it wrote."""
        self.artifacts.append(_new_artifact(func, kwargs, result))


def _chart_namespace(session_base_path: str, user_id: Optional[str],
                     recorder: _ChartPathRecorder) -> Dict[str, Any]:
    """Build the exec namespace: the chart engine's public API plus pandas/numpy."""
    from prism_mcp.sandbox.chart_names import WRAPPED_CHART_FUNCS
    from prism_mcp.utils import chart_functions
    from prism_mcp.utils.chart_functions import (
        build_charts, TableResult, ChartResult, ChartSpec, profile_df,
        VLine, HLine, Band, Arrow, PointLabel, PointHighlight, Callout,
        PlotText, Segment, LastValueLabel, Trendline,
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
        **{name: wrap(getattr(chart_functions, name)) for name in WRAPPED_CHART_FUNCS},
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


# A value that names a day: ISO (2026-09-01, optionally with a time) or slashed.
_FULL_DATE_RE = re.compile(r"^\s*(\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{2,4})")


def _date_index_or_as_written(index: pd.Index) -> pd.Index:
    """The index as a DatetimeIndex when every value names a day, else as read.

    ``parse_dates=True`` also rewrote calendar years into Jan-1 stamps and
    ``2024Q1`` / ``24Q1`` into quarter starts, so the chart code saw months
    where the caller wrote quarters. Those stay as written; the engine reads
    their grain itself.
    """
    if index.dtype != object:
        return index
    values = [v for v in index if isinstance(v, str)]
    if not values or len(values) != index.notna().sum():
        return index
    if not all(_FULL_DATE_RE.match(v) for v in values):
        return index
    try:
        parsed = pd.to_datetime(index)
    except (TypeError, ValueError):
        return index
    parsed.name = index.name
    return parsed


def _read_data_file(csv_bytes: bytes) -> pd.DataFrame:
    """One CSV, first column as the index, text as the file wrote it.

    ``read_csv``'s default missing-value list turns ``n/a``, ``None``, ``NA``
    and ``null`` into NaN in every column, so a text cell that said n/a
    printed blank, and Namibia's ``NA`` vanished. Only a column that parses
    as numbers keeps that reading -- a chart needs it numeric, gaps and all;
    text columns, the index, and a column holding nothing but such words
    keep every cell as written, with only empty cells missing.
    """
    parsed = pd.read_csv(io.BytesIO(csv_bytes), index_col=0)
    frame = pd.read_csv(io.BytesIO(csv_bytes), index_col=0,
                        keep_default_na=False, na_values=[''])
    # Positional: the two reads label a row differently when its index says NA.
    for col in frame.columns:
        if pd.api.types.is_numeric_dtype(parsed[col]) and parsed[col].notna().any():
            frame[col] = parsed[col].to_numpy()
    if pd.api.types.is_numeric_dtype(parsed.index) and parsed.index.notna().any():
        frame.index = parsed.index
    frame.index = _date_index_or_as_written(frame.index)
    return frame


def _load_data_files(namespace: Dict[str, Any], data_files: Optional[List[str]]) -> None:
    """Bind each S3 CSV in ``data_files`` as ``df1``, ``df2``, ... in index order."""
    for i, file_path in enumerate(data_files or [], 1):
        namespace[f'df{i}'] = _read_data_file(s3_manager.get(file_path))


# The shared tuple, not a copy of it: the dashboard sink applies the same gates
# and a second list is how the two come to disagree.
_CHART_PREEXEC_CHECKS = GENERATED_CODE_PREEXEC_CHECKS


def _refuse_unsafe_chart_code(code: str) -> str:
    """The first gate's refusal message, or '' when every gate passes."""
    for check in _CHART_PREEXEC_CHECKS:
        refusal = check(code)
        if refusal:
            return refusal
    return ''


def _suffixable_builders() -> Tuple[str, ...]:
    """The sandbox-bound chart functions that take ``filename_suffix``.

    Read off the signatures rather than listed, the way ``_wrap_chart_func`` reads
    the one it wraps: a builder that loses the parameter would otherwise have the
    prelude below call it with an argument it no longer accepts.
    """
    from prism_mcp import chart_render
    from prism_mcp.sandbox.chart_names import WRAPPED_CHART_FUNCS

    names = []
    for name in WRAPPED_CHART_FUNCS:
        func = getattr(chart_render, name, None)
        if func is None:
            continue
        try:
            accepts = 'filename_suffix' in inspect.signature(func).parameters
        except (TypeError, ValueError):
            accepts = False
        if accepts:
            names.append(name)
    return tuple(names)


def _nonce_prelude(base: str) -> str:
    """Source that gives a diverted run the nonce it cannot mint for itself.

    ``_wrap_chart_func`` injects the nonce on the in-process path, but a diverted run
    executes in a namespace this process never builds and under no invocation it can
    read. Without it the engine names from title and clock alone, so a retry
    accumulates near-duplicates instead of overwriting and two same-titled charts in
    one script become one file.

    Sent as source because no argument on the tool can carry it. Scoped to
    ``filename_suffix`` and skipped when the caller passed ``save_as``, mirroring
    ``_wrap_chart_func``'s own ``elif``: tagging an explicit ``save_as`` needs
    ``_disambiguate``, whose idempotent stripping is keyed on the invocation token,
    and a second copy of that in generated code is worse than the gap it closes.

    ``base`` is this invocation's token, so the per-call counter restarting at each
    attempt is what makes attempt N's Nth artifact overwrite attempt N-1's.
    """
    if not base.isalnum():
        raise ValueError(
            f'invocation token {base!r} is not alphanumeric; it is embedded in '
            f'generated source and a token that is not would change its meaning'
        )
    rebinds = ''.join(
        f"{name} = _prism_suffixed({name})\n" for name in _suffixable_builders())
    return (
        f"_prism_nonce_base = '{base}'\n"
        f"_prism_nonce_n = 0\n"
        f"def _prism_nonce():\n"
        f"    global _prism_nonce_n\n"
        f"    _prism_nonce_n += 1\n"
        f"    return _prism_nonce_base + str(_prism_nonce_n)\n"
        f"def _prism_suffixed(fn):\n"
        f"    def _call(*a, **k):\n"
        f"        if not k.get('save_as') and not k.get('filename_suffix'):\n"
        f"            k['filename_suffix'] = _prism_nonce()\n"
        f"        return fn(*a, **k)\n"
        f"    return _call\n"
        f"{rebinds}"
    )


def _ladder_step() -> Tuple[ChartInvocation, int, int]:
    """Advance this invocation's ladder, returning ``(state, attempt, prev_findings)``."""
    state = current_invocation(ChartInvocation)
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
    if isinstance(exc, SandboxUnavailable):
        return 'FATAL', (
            'the sandbox substrate could not run this render; no chart code can '
            'fix it'
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
            Each is read with the first column as the index, named by its
            header: a DatetimeIndex when it holds dates, as written otherwise
            (years, quarter and month labels, names). You have not seen these frames; `profile_df(df1)` before you bind a
            column name you are not certain of.

    Returns:
        Two fenced blocks. `===CHART_DELIVERY_START===` holds what the caller
        needs -- every PNG written, a browser link where the medium supports one,
        and a line per artifact naming what it shows. `===CHART_DIAGNOSTICS_START===`
        holds a `status:` line (OK / RETRYABLE / NO_ARTIFACTS / FATAL), engine
        warnings, stdout and any traceback; it is for your retry loop and must
        not appear in your reply.
    """
    from core.configs.mediums import COMPOSER, normalize_medium
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
        detail = (f'{CHART_ATTEMPT_CEILING} render_charts calls already '
                  f'made for this session; nothing was executed')
        # Recorded even though nothing ran. The code a refused call carried is
        # precisely what an audit of a runaway ladder wants to read, and a
        # refusal is the one outcome that leaves no other trace at all.
        record_render_call(
            session_path=resolved_path, invocation_token=invocation.token,
            attempt=attempt, chart_code=chart_code, data_files=data_files,
            status='FATAL', status_detail=detail, n_findings=0,
            previous_findings=previous_findings, chart_paths=[], artifacts=[],
            stdout='', error='', elapsed_s=0.0, executed=False)
        # Nothing ran, so nothing is offered: a refusal must not re-attach the pictures
        # of the attempt before it.
        invocation.delivered = []
        return format_report(
            resolved_path, [], [], "", "", medium, artifacts=[], status='FATAL',
            status_detail=detail, attempt=attempt)

    # Restart the per-call nonce so this attempt's Nth artifact lands on the
    # previous attempt's Nth. Retries then overwrite rather than accumulate,
    # which is the property the fixed invocation token exists to give and which a
    # monotonic counter would quietly take away.
    invocation.sequence = 0

    from prism_mcp.tools import sandbox_rollout as _sandbox_rollout
    _sandbox = _sandbox_rollout.decide()
    logger.info(f"[sandbox-rollout] chart_exec divert={_sandbox.divert} "
                f"({_sandbox.reason})")
    divert = _sandbox.divert
    # Asked where the decision is read, so a refused call never gets as far as a
    # namespace: a deployment declaring an off-process engine has no in-process
    # fallback for a call the gate could not attribute.
    unisolated = None if divert else _sandbox_rollout.refuse_unisolated_exec(
        'chart_exec', _sandbox.reason)

    recorder = _ChartPathRecorder(s3_manager)
    namespace: Dict[str, Any] = {}
    if not divert and not unisolated:
        namespace = _chart_namespace(resolved_path, kerberos or None, recorder)

    stdout = ""
    error = ""
    status, status_detail, n_findings = 'OK', '', 0
    refusal = ''
    started = time.perf_counter()
    # Reading the CSVs belongs inside the guard: a path relayed from the caller is
    # the likeliest thing in this call to be wrong, and raising out of the tool
    # would skip the whole two-block protocol the sub-agent is trained on.
    stage = 'load'
    try:
        if not divert and not unisolated:
            _load_data_files(namespace, data_files)
        stage = 'exec'
        code, _preprocess_notes = preprocess_script_code(chart_code)
        # The substrate refusal wins: no rewrite of the script changes which
        # engine this deployment runs, so there is nothing for the ladder to try.
        refusal = unisolated or _refuse_unsafe_chart_code(code)
        if refusal:
            # FATAL, non-retryable: a sub-agent that keeps probing for phrasing
            # that slips the gate would otherwise spend the rest of its budget
            # searching rather than stopping.
            status, status_detail = 'FATAL', refusal
        else:
            if divert:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_sandbox_rollout.run_in_sandbox,
                                      _nonce_prelude(invocation.token) + code,
                                      resolved_path, data_files,
                                      adopt=recorder.adopt, s3_manager=s3_manager),
                    timeout=CHART_EXECUTION_TIMEOUT_SECONDS,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(_execute_sync, code, namespace),
                    timeout=CHART_EXECUTION_TIMEOUT_SECONDS,
                )
            stdout = result['stdout']
    except Exception as exc:
        stdout = getattr(exc, '_partial_stdout', '') or ''
        error = traceback.format_exc()
        status, status_detail, n_findings = _classify_failure(exc, error, stage)

    # The abandoned worker thread keeps running past a timeout; clearing the dict
    # in place drops its grip on every DataFrame and closure it holds.
    artifacts = list(recorder.artifacts)
    namespace.clear()

    if status == 'RETRYABLE' and recorder.chart_paths:
        status_detail = (f'{status_detail}; {len(recorder.chart_paths)} chart(s) already '
                         f'rendered and listed in the delivery block -- re-issue ONLY the '
                         f'failed chart, not the batch')

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

    # Every attempt, not only the ones that drew something: a retry overwrites
    # the previous attempt's specs and PNGs, so without this the failures leave
    # nothing behind but a hash in the thought trail.
    record_render_call(
        session_path=resolved_path, invocation_token=invocation.token,
        attempt=attempt, chart_code=chart_code, data_files=data_files,
        status=status, status_detail=status_detail, n_findings=n_findings,
        previous_findings=previous_findings, chart_paths=recorder.chart_paths,
        artifacts=artifacts, stdout=stdout, error=error,
        elapsed_s=time.perf_counter() - started, executed=not refusal)

    links = []
    if recorder.chart_paths and normalize_medium(medium) == COMPOSER:
        links = generate_download_links_for_sandbox(recorder.chart_paths)

    logger.info(
        f"[chart_exec] session={resolved_path} charts={len(recorder.chart_paths)} "
        f"medium={medium} status={status} findings={n_findings} "
        f"attempt={attempt}/{CHART_ATTEMPT_CEILING}"
    )
    # Ground truth for the seam: what reached S3, not what the sub-agent says
    # reached it. NO_ARTIFACTS and a failed attempt both leave it empty, which
    # is the correct offer.
    invocation.delivered = list(recorder.chart_paths)
    return format_report(resolved_path, recorder.chart_paths, links, stdout, error, medium,
                         artifacts=artifacts, status=status, status_detail=status_detail,
                         n_findings=n_findings, attempt=attempt,
                         previous_findings=previous_findings)
