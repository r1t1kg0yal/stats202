"""dashboards_time -- canonical time helpers for the dashboard pipeline.

Single source of truth for ISO parsing, ISO emit, refresh-frequency
deltas, stale-lock detection, and the user-facing "Data as of" pill
string. Every consumer (``echart_dashboard.build_dashboard``,
``refresh_runner``, ``refresh_dashboards``, PRISM-side
``mysite/news/views.py``) routes through this module so the pipeline
has one parser/formatter pair instead of ad-hoc
``.replace("Z", "+00:00")`` + ``datetime.fromisoformat`` calls scattered
across files.

The module name is ``dashboards_time`` (not ``time``) because a bare
``time.py`` inside any package shadows the stdlib ``time`` module --
subtle import-resolution foot-gun nobody needs.

Four named "time" concepts threaded through the pipeline (per the
design walkthrough at ``scans/prism/2026-05-11_dashboard_live_refresh_and_time.md`` Section 1):

    data_domain_end     last observation date in the data (e.g. last
                        CPI print = 2026-Q1). Derived from the CSV.
    pull_completed_at   when the underlying source was queried.
                        Stamped into <stem>_metadata.json sidecars by
                        the pull helpers.
    build_completed_at  when build_dashboard() compiled the HTML.
                        Stamped on every build.
    refresh_cycle_at    when the cron / [Refresh] runner finished.
                        Stamped by refresh_runner.py.

The user-facing pill collapses (data_domain_end, refresh_cycle_at OR
build_completed_at) into one human-readable string. pull_completed_at
is observability-only; no consumer in the chrome.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo


UTC = timezone.utc
ET = ZoneInfo("America/New_York")


# refresh_frequency -> minimum elapsed time before a dashboard is "due"
# again. Matches the contract in prism/dashboard-refresh.md §5.3 so
# existing registry entries don't need migration. "daily" intentionally
# means ">=20h since last refresh", not "calendar-day boundary".
REFRESH_FREQ_DELTAS: dict = {
    "hourly": timedelta(hours=1),
    "daily":  timedelta(hours=20),
    "weekly": timedelta(hours=160),
    "manual": None,
}


def utcnow() -> datetime:
    """Aware UTC ``datetime`` for "now". Single source of truth -- never
    use ``datetime.utcnow()`` directly (which returns a naive datetime
    and silently breaks aware-vs-naive arithmetic)."""
    return datetime.now(UTC)


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse any ISO-8601 dialect the pipeline emits / accepts.

    Accepts:
      - "2026-05-12T00:25:45.123456+00:00"   canonical aware
      - "2026-05-12T00:25:45.123456Z"        legacy Z-suffix (registry)
      - "2026-05-12T00:25:45"                naive (treated as UTC)
      - "2026-05-12T00:25:45+05:00"          non-UTC offset (normalised)
      - "2026-05-12"                         bare date (treated as midnight UTC)

    Always returns aware UTC ``datetime`` or ``None`` for empty / malformed
    input. The None return is what lets callers chain
    ``parse_iso(x) or fallback`` without try/except scaffolding.
    """
    if not s:
        return None
    if not isinstance(s, str):
        return None
    s = s.strip()
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def format_iso(dt: datetime) -> str:
    """Canonical ISO emit. Always ``+00:00`` (never ``Z``), always aware UTC.

    Use ``format_iso(utcnow())`` instead of
    ``datetime.utcnow().isoformat() + "Z"`` (the legacy idiom that
    silently emits a naive timestamp).
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat()


def freq_delta(freq: Optional[str]) -> Optional[timedelta]:
    """Return the elapsed-time threshold for ``freq``, or ``None`` for
    ``"manual"`` / unknown frequencies. Lookup table -- no magic-number
    branches in callers."""
    if freq is None:
        return None
    return REFRESH_FREQ_DELTAS.get(freq)


def is_stale(started_at: Optional[str],
             max_age_seconds: int = 600) -> bool:
    """Return ``True`` if ``started_at`` (an ISO string) is older than
    ``max_age_seconds``. Missing / malformed input returns ``True`` (the
    safe-default for stale-lock detection: if we can't tell when something
    started, assume it's stale).

    Used by ``views.py::refresh_status_api`` to detect orphaned ``running``
    states. Replaces the naive ``datetime.utcnow() - started_dt`` idiom
    that masked an aware-vs-naive ``TypeError`` only by accident."""
    started = parse_iso(started_at)
    if started is None:
        return True
    return (utcnow() - started).total_seconds() > max_age_seconds


def _format_domain(date_str: Optional[str], freq: Optional[str]) -> Optional[str]:
    """Format the data-domain endpoint for the pill. Cadence-aware:

        quarterly  ->  "Q1 2026"
        monthly    ->  "Mar 2026"
        annual     ->  "2026"
        weekly     ->  "31 Mar 2026"
        daily      ->  "31 Mar 2026"
        (other)    ->  "31 Mar 2026"

    Returns ``None`` for empty / unparseable input so callers can chain.
    """
    if not date_str:
        return None
    dt = parse_iso(date_str)
    if dt is None:
        return None
    if freq == "quarterly":
        return f"Q{(dt.month - 1) // 3 + 1} {dt.year}"
    if freq == "monthly":
        return dt.strftime("%b %Y")
    if freq == "annual":
        return str(dt.year)
    return dt.strftime("%d %b %Y")


def format_pill(meta_time: dict) -> str:
    """Build the user-facing "Data as of" string from a ``metadata.time``
    block. Examples:

        "Data through Q1 2026 -- refreshed 12 May 2026 09:25 ET"
        "Data through Mar 2026 -- refreshed 12 May 2026 09:25 ET"
        "Data through 31 Mar 2026"                       (no cycle yet)
        "Refreshed 12 May 2026 09:25 ET"                 (no domain)
        ""                                               (nothing populated)

    The cycle timestamp is taken from ``refresh_cycle_at`` first, falling
    back to ``build_completed_at`` for in-session PRISM builds that
    haven't gone through the cron / [Refresh] runner yet. Cycle is
    rendered in Eastern Time per the trading-floor convention; if a
    non-NY user friction surfaces later, parametrize ``display_tz`` here
    instead of baking the override into manifest metadata.
    """
    if not isinstance(meta_time, dict):
        return ""
    domain_end_str = meta_time.get("data_domain_end")
    cycle_str_raw = (
        meta_time.get("refresh_cycle_at")
        or meta_time.get("build_completed_at")
    )
    freq = meta_time.get("data_domain_freq", "daily")

    domain_str = _format_domain(domain_end_str, freq)

    cycle_dt = parse_iso(cycle_str_raw)
    cycle_str = (
        cycle_dt.astimezone(ET).strftime("%d %b %Y %H:%M ET")
        if cycle_dt else None
    )

    if domain_str and cycle_str:
        return f"Data through {domain_str} -- refreshed {cycle_str}"
    if domain_str:
        return f"Data through {domain_str}"
    if cycle_str:
        return f"Refreshed {cycle_str}"
    return ""


__all__ = [
    "UTC",
    "ET",
    "REFRESH_FREQ_DELTAS",
    "utcnow",
    "parse_iso",
    "format_iso",
    "freq_delta",
    "is_stale",
    "format_pill",
]
