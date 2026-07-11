"""dashboards_time -- canonical time helpers for the dashboard pipeline.

Single source of truth for ISO parsing, ISO emit, refresh-frequency
deltas, and stale-lock detection. Every consumer
(``echart_dashboard.build_dashboard``, ``refresh_runner``,
``refresh_dashboards``, PRISM-side ``web/backend_django/news/views.py``
legacy: ``mysite/news/views.py``) routes
through this module so the pipeline has one parser/formatter pair
instead of ad-hoc ``.replace("Z", "+00:00")`` +
``datetime.fromisoformat`` calls scattered across files.

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

User-facing pill rendering happens in the chrome (``rendering.py``
DASHBOARD_APP_JS): two pills, one with a live-ticking now-clock
(updates every 1s via setInterval), one with the refresh timestamp
(updates on every applyLiveData tick). Both formatted in ET via
``Intl.DateTimeFormat`` — JS owns the rendering because the now-clock
must tick and that can't be server-baked. ``refresh_cycle_at`` flows
into the refresh pill as a canonical aware-UTC ISO string.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union
from zoneinfo import ZoneInfo


UTC = timezone.utc
ET = ZoneInfo("America/New_York")


# refresh_frequency -> minimum elapsed time before a dashboard is "due"
# again. Legacy enum kept for back-compat: existing registry entries
# (dashboards built before 2026-05-12) still validate without migration.
# "daily" intentionally means ">=20h since last refresh", not
# "calendar-day boundary" -- matches prism/dashboard-refresh.md §5.3.
# New entries should prefer the duration-string syntax accepted by
# ``parse_freq`` ("60s", "5m", "1h", "1d", "1w") because it lets PRISM
# pick the right cadence per-dashboard instead of being boxed into 4 buckets.
REFRESH_FREQ_DELTAS: dict = {
    "hourly": timedelta(hours=1),
    "daily":  timedelta(hours=20),
    "weekly": timedelta(hours=160),
    "manual": None,
}


# Duration string parser: "60s" / "5m" / "15m" / "1h" / "6h" / "1d" / "7d" / "1w".
# Case-insensitive, whitespace tolerant. Single positive integer + single unit.
# Compound durations ("1h30m") are intentionally NOT supported; if PRISM needs
# 90 minutes, "90m" is the expressive answer.
_DURATION_RE = re.compile(r"^\s*(\d+)\s*([smhdw])\s*$", re.IGNORECASE)
_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}


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


def parse_freq(value: Union[None, int, float, str]) -> Optional[timedelta]:
    """Parse a refresh-frequency value into an elapsed-time threshold.

    Accepts:

    - **Duration string** -- ``"60s"`` / ``"5m"`` / ``"15m"`` / ``"1h"`` /
      ``"6h"`` / ``"1d"`` / ``"7d"`` / ``"1w"``. Case-insensitive,
      whitespace tolerant. Single positive integer + single unit.
      Compound durations (``"1h30m"``) are intentionally not supported;
      ``"90m"`` is the expressive equivalent.
    - **Legacy enum (back-compat)** -- ``"hourly"`` -> 1h,
      ``"daily"`` -> 20h, ``"weekly"`` -> 160h, ``"manual"`` -> None.
      Existing registry entries continue to parse without migration.
    - **Numeric** -- ``int`` or ``float`` treated as seconds.
    - **None / "manual" / unknown** -- returns ``None``. The cron's
      ``_is_due`` short-circuits "manual" explicitly upstream; ``None``
      from ``parse_freq`` typically means "fall back to default" for
      unknown strings.

    PRISM authoring guidance:
      - intraday tape (1m bars):    ``"60s"`` to ``"2m"``
      - 5m / 15m bars:              ``"5m"`` to ``"15m"``
      - end-of-day rates / curves:  ``"1h"`` to ``"6h"``
      - monthly indicators (CPI):   ``"6h"`` to ``"1d"``
      - quarterly (GDP):            ``"1d"`` to ``"1w"``
      - structural views (rarely refreshed): ``"manual"``

    Returns: ``timedelta`` for a valid cadence, ``None`` otherwise.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if value <= 0:
            return None
        return timedelta(seconds=float(value))
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    if not s:
        return None
    if s in REFRESH_FREQ_DELTAS:
        return REFRESH_FREQ_DELTAS[s]
    m = _DURATION_RE.match(s)
    if not m:
        return None
    n = int(m.group(1))
    if n <= 0:
        return None
    return timedelta(seconds=n * _UNIT_SECONDS[m.group(2).lower()])


def freq_delta(freq: Optional[str]) -> Optional[timedelta]:
    """Back-compat alias for ``parse_freq``. New code should call
    ``parse_freq`` directly -- it accepts both the legacy enum
    (``"hourly"`` / ``"daily"`` / ``"weekly"`` / ``"manual"``) and
    duration strings (``"60s"`` / ``"5m"`` / ``"1h"``)."""
    return parse_freq(freq)


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


__all__ = [
    "UTC",
    "ET",
    "REFRESH_FREQ_DELTAS",
    "utcnow",
    "parse_iso",
    "format_iso",
    "parse_freq",
    "freq_delta",
    "is_stale",
]
