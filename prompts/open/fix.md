Short answer: yes, you need refresh_dashboards.py (or its equivalent loop) running for the dashboard to auto-update. The 304 = "nothing changed since you last asked" is the chrome poll loop working perfectly — but if nothing on the server side is changing the data, every poll for the rest of time will be a 304.

┌───────────────────────────────────────────────────────────────────┐
│  WHY 304 EVERY MINUTE ≠ AUTO-REFRESH                              │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  304 means: "your ETag matches registry.last_refreshed; the data  │
│             on the server is identical to what you already have"  │
│                                                                   │
│  For the chrome to swap in fresh numbers, registry.last_refreshed │
│  has to ADVANCE. The only things that advance it are:             │
│                                                                   │
│  (a) refresh_dashboards.main() runs (the cron) and refreshes the  │
│      dashboard because it's "due" per refresh_frequency           │
│  (b) refresh_runner.py is invoked directly (manual or another     │
│      orchestrator) for this folder                                │
│  (c) Someone clicks [Refresh] in any browser tab on this          │
│      dashboard (POST /api/dashboard/refresh/ ─► same runner)      │
│                                                                   │
│  None of those are happening passively. Hence every poll: 304.    │
│                                                                   │
└───────────────────────────────────────────────────────────────────┘
Here's the PRISM-side diagnosis prompt:

---
class: context-extraction (read-only introspection)
topic: live-refresh poll loop returns 304 every minute but dashboard never updates
dashboard: users/goyalri/dashboards/ust_10y_intraday
---
# Diagnose why the live-refresh loop sees only 304s
Context: the chrome's `pollLiveData()` is hitting `GET /api/dashboard/data/`
every 60 seconds and getting `304` every time. The chrome is wired
correctly (manual `[Refresh]` button works and the in-place swap
fires). The hypothesis is that nothing on the server side is
advancing `registry.last_refreshed`, so the ETag stays the same
forever and every poll legitimately 304s. Diagnose end to end.
Reply in this structure:
## 1. Registry entry
Read `users/goyalri/dashboards/dashboards_registry.json` and quote the
verbatim entry whose `id == "ust_10y_intraday"`. Surface these fields
specifically:
  - `refresh_enabled`
  - `refresh_frequency`
  - `last_refreshed`
  - `last_refresh_status`
  - `created_at`
Then: given `refresh_frequency`, compute the elapsed hours since
`last_refreshed` and say whether `_is_due()` would return True right
now (thresholds: hourly = ≥1h, daily = ≥20h, weekly = ≥160h).
## 2. Refresh status
Read `users/goyalri/dashboards/ust_10y_intraday/refresh_status.json`
verbatim. If `status == "error"` or `status == "partial"`, quote
every `errors[].message` and `errors[].traceback`. If `status ==
"running"`, give `started_at` + the PID and (if possible) check
whether the PID is alive.
## 3. Cron loop liveness
Determine whether the PRISM-side cron loop that drives
`refresh_dashboards.main()` is actually running:
  - In `ai_development/entrypoint.py`, find `fifteen_minute_context_generator`
    and confirm it calls `refresh_dashboards.main()` (or whatever the
    current cron entry point is named).
  - Search recent PRISM logs / stdout for lines matching `[15MIN]
    Dashboard refresh completed` or `[refresh_dashboards] starting at`
    or `[refresh_dashboards] done`. Quote the 2-3 most recent ones
    verbatim with timestamps.
  - If no such lines exist in the last hour, the cron loop is
    not running and that is the root cause.
## 4. Last 3 cron passes (if cron IS running)
For the 3 most recent `[refresh_dashboards] done` lines from §3,
quote the summary stats (refreshed / success / fail / skipped /
disabled / not_due / manifests_refreshed). Then list which
dashboards were in each pass's "refreshed" set. Confirm whether
`ust_10y_intraday` appeared in any of them.
## 5. Build pipeline integrity for this dashboard
If `last_refresh_status == "error"` or the dashboard hasn't appeared
in any cron pass, walk these:
  - Does `users/goyalri/dashboards/ust_10y_intraday/scripts/pull_data.py`
    exist? Quote the `PULLS` dict literal (just the keys).
  - Does `users/goyalri/dashboards/ust_10y_intraday/scripts/build.py`
    exist? Quote the `TRANSFORMS = [...]` literal.
  - Does `users/goyalri/dashboards/ust_10y_intraday/manifest_template.json`
    exist? Quote `metadata.refresh_frequency` and
    `metadata.live_refresh_seconds` from it.
## 6. Force a manual rebuild + observe
Run the runner directly to confirm the rebuild path works end-to-end:
```bash
python -m ai_development.dashboards.refresh_runner \
  --folder users/goyalri/dashboards/ust_10y_intraday
Quote the full stdout/stderr. After it returns, re-read users/goyalri/dashboards/dashboards_registry.json for this dashboard's last_refreshed and confirm it advanced. Re-read users/goyalri/dashboards/ust_10y_intraday/refresh_status.json for the new completed_at + status.

7. Verdict
Synthesize §1-§6 into ONE of these explicit verdicts:

A. Cron loop is NOT running — no [15MIN] lines in the last hour. The 304s will continue forever until either (a) the cron loop is started, (b) the user clicks [Refresh], or (c) someone invokes refresh_runner.py manually. Recommend the user start the cron loop (cite the entry point) and / or set up a wrapper that invokes refresh_runner.py for this dashboard at the desired cadence.

B. Cron loop IS running but ust_10y_intraday is "not due" per refresh_frequency. Quote the current refresh_frequency and the elapsed hours since last_refreshed; recommend the user either wait for the threshold, lower refresh_frequency (e.g. "hourly" instead of "daily"), or click [Refresh] manually.

C. Cron loop IS running and ust_10y_intraday IS being attempted but the runner is failing (e.g. pull_data.py error). Quote the errors[].message and recommend the fix.

D. Cron loop IS running, ust_10y_intraday IS being refreshed successfully (last_refreshed is advancing), but the chrome is somehow not seeing it. (Unlikely — would indicate an ETag comparison bug or a stale-process Django cache.) Quote the evidence and recommend.

If part of this prompt cannot be answered, add a brief ## Could not resolve section at the end naming exactly what couldn't be resolved and why.
