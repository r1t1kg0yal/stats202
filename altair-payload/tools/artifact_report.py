"""Shared two-block report formatter for chart and infographic engines.

Charts and infographics used to each carry a copy of ``format_report``. The
shape is the same -- a delivery block the caller pastes and a diagnostics
block the sub-agent keeps -- so the body lives here and each engine supplies
a ``ReportShape``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from prism_mcp.utils.output_limits import SCRIPT_STDOUT_INLINE_BYTES


@dataclass
class ReportShape:
    """Nouns, sentinels and callbacks that make one engine's report distinct.

    ``delivery_open`` / ``delivery_close`` / ``diagnostics_open`` /
    ``diagnostics_close`` are derived from ``noun`` so a chart report and an
    infographic report cannot collide on a sentinel, and so a mechanical strip
    can key on an exact line rather than on meaning.
    """

    noun: str
    plural: str
    artifact: str
    ceiling: int
    describe: Callable[[Dict[str, Any], str], str]
    delivery_hint: Callable[[int, str], str] = field(default=lambda count, medium: "")
    delivery_open: str = ""
    delivery_close: str = ""
    diagnostics_open: str = ""
    diagnostics_close: str = ""

    def __post_init__(self) -> None:
        if not self.delivery_open:
            self.delivery_open = f"==={self.noun}_DELIVERY_START==="
        if not self.delivery_close:
            self.delivery_close = f"==={self.noun}_DELIVERY_END==="
        if not self.diagnostics_open:
            self.diagnostics_open = f"==={self.noun}_DIAGNOSTICS_START==="
        if not self.diagnostics_close:
            self.diagnostics_close = f"==={self.noun}_DIAGNOSTICS_END==="


def _truncate(text: str) -> str:
    if len(text.encode('utf-8')) <= SCRIPT_STDOUT_INLINE_BYTES:
        return text
    return text[:SCRIPT_STDOUT_INLINE_BYTES] + "\n... [stdout truncated]"


def format_report(shape: ReportShape, session_path: str, chart_paths: List[str],
                  links: List[Dict[str, Any]], stdout: str, error: str, medium: str,
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

    out = [shape.delivery_open, "\n\n", f"**Session**: `{session_path}`\n\n"]
    if chart_paths:
        out.append(f"**{shape.plural}**: {len(chart_paths)} PNG(s)\n\n")
        for i, path in enumerate(chart_paths, 1):
            out.append(f"{i}. {shape.describe(by_path.get(path, {}), path)}\n")
            short = short_by_path.get(path)
            out.append(f"   `{path}`" + (f" -> {short}\n" if short else "\n"))
        out.append(shape.delivery_hint(len(chart_paths), medium))
    else:
        out.append(f"No {shape.artifact} was written by this run.\n")
    out.append(f"\n{shape.delivery_close}\n\n")

    out.append(f"{shape.diagnostics_open}\n")
    out.append("Yours alone. Never quote, paraphrase or summarise any of it.\n\n")
    out.append(f"status: {status}")
    out.append(f" ({n_findings} finding(s))\n" if n_findings else "\n")
    out.append(f"attempt: {attempt} of {shape.ceiling}\n")
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
    out.append(shape.diagnostics_close)
    return "".join(out)
