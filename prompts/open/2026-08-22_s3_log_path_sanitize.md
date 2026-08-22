# Context extraction: `S3LogPathBuilder._sanitize` and class constants

Small, closing prompt. The 2026-08-22 subprocess-sprawl extraction gave us
both key-building classmethods verbatim, which was enough to bring the
staging mirror to parity on structure, ordering, timestamp formats and
suffix widths. One member was referenced but not shown, so our mirror
reconstructs it from observed output — the only unverified piece left in
`projects/echarts/prism_mcp/utils/s3_log_streamer.py`.

## 1. The missing body

Paste `prism-core/prism_mcp/utils/s3_log_streamer.py` lines 52-84 verbatim
— everything from the `class S3LogPathBuilder:` line down to the start of
`build()`. That range should contain the class docstring, `ROOT`, any other
class-level constants, and `_sanitize` itself.

Specifically:

1. `_sanitize(cls, value, max_len)` in full. What is the character
   allowlist, what do disallowed characters become, does it lowercase, does
   it collapse runs of the replacement character, does it strip leading or
   trailing separators, and is the truncation a plain slice or does it cut
   on a boundary?
2. Every class attribute on `S3LogPathBuilder` besides `ROOT`, with values.
3. Is `_sanitize` called anywhere outside these two classmethods?

## 2. Two behaviours our reconstruction cannot predict

4. What does `build_session_side` produce when `kind` contains a character
   that needs sanitizing? The generic spawner at `subprocess_tools.py:993`
   takes a caller-supplied `kind`, so this is reachable in a way the four
   known literal kinds are not. A concrete example of a real
   caller-supplied `kind` value from the last month of
   `subprocess_logs/`, if one exists that is not one of
   `dashboard_refresh` / `scheduled_process` / `ticket`, would settle it.

5. What happens when `session_description` exceeds 60 characters? The
   dashboard engine passes the flattened folder path, and
   `users_<kerberos>_dashboards_<dashboard_id>` crosses 60 for a long
   dashboard id. Does the truncated slug still disambiguate, given that
   the `rand6` suffix follows it — i.e. can two different dashboards owned
   by the same user produce the same folder name modulo the random
   suffix, and is that considered acceptable?

## 3. Why this matters little but is worth closing

The keys nothing reads (`build_session_side`) and the keys only triage
reads (`build`) are both low-stakes, so a stricter-than-PRISM `_sanitize`
in staging costs nothing today. It matters for one reason: our mirror
having invented a `subprocess_logs/` segment is what produced a curated
folder contract that was wrong for months and a scoping exercise that
started from two false hypotheses. Closing the last reconstructed member
removes the last place that can happen in this file.

No code change is being requested. If the answer reveals that our
reconstruction diverges, the fix is in the staging mirror, not in PRISM.
