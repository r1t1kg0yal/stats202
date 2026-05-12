---
session: pull-helper sidecar `pull_completed_at` stamping
sent: 2026-05-12
class: implementation-directive (NOT context-extraction; NOT end-usage)
preconditions:
  - The dashboards live-refresh + time uplift (2026-05-11 staging-side + 2026-05-11 views.py PRISM-side) has already landed. Specifically the canonical `ai_development/dashboards/dashboards_time.py` module exists with `format_iso(utcnow())`; `build_dashboard` calls `_max_pull_time(folder, s3_manager)` to scan `<folder>/data/<stem>_metadata.json` sidecars for a `pull_completed_at` field; today every sidecar is missing that field so `_max_pull_time` returns `None` and `metadata.time.pull_completed_at` is unstamped.
files_to_modify:
  - `ai_development/mcp/utils/data_functions.py` (every pull helper that writes a sidecar JSON)
reply_folded_into:
  - Confirmation back to staging so `prism/data-functions.md` §0 can absorb the new sidecar field; staging-side `projects/echarts/dev/notes.md` "live-refresh observability" closes one row.
status: pending
---

Title: pull-helper sidecar `pull_completed_at` stamping — close the observability half of the dashboard time-handling uplift

The dashboard live-refresh + time uplift has landed end-to-end except for ONE observability field: `metadata.time.pull_completed_at`. The engine's `_max_pull_time(folder, s3_manager)` helper already walks `<folder>/data/<stem>_metadata.json` sidecars and takes `max(.pull_completed_at)`; today every sidecar is missing the field, so the helper returns `None` and the dashboard's `metadata.time.pull_completed_at` is unstamped. The chrome pill doesn't show this field (it shows `data_domain_end` + `refresh_cycle_at`), so the impact is observability-only — but it's a load-bearing facet of the four-times schema we want to start populating.

This prompt asks PRISM-side `mcp/utils/data_functions.py` to stamp `pull_completed_at` into every sidecar JSON the pull helpers write.

## What changes

Add `pull_completed_at` to the metadata sidecar JSON that every pull helper writes, set to the moment the pull function finished writing the CSV. Use the canonical `format_iso(utcnow())` from `ai_development.dashboards.dashboards_time`.

Apply to every helper that writes a sidecar:

  - `pull_haver_data`
  - `pull_market_data`
  - `pull_plottool_data`
  - `pull_fred_data` (once added — currently missing per `prism/dashboard-refresh.md` §5.7 known-gap)
  - `save_artifact` (writes a sidecar for alt-data CSVs)

The current sidecar shape is something like (verbatim shape varies by helper; pattern-match on the load site):

```json
{
  "name": "global_cpi",
  "rows": 65,
  "columns": 43,
  "data_domain_start": "2010-01-01",
  "data_domain_end":   "2026-03-31",
  "data_domain_freq":  "quarterly"
}
```

After this change every newly-written sidecar should also carry:

```json
{
  "pull_completed_at": "2026-05-12T13:25:50.123456+00:00"
}
```

## The one-line stamp pattern

Every helper has a common shape (probe + fetch + write CSV + write sidecar). Insert the stamp right before the sidecar is serialised:

```python
from ai_development.dashboards.dashboards_time import format_iso, utcnow

# ... after CSV write succeeds ...
sidecar = {
    # ... existing fields ...
    "pull_completed_at": format_iso(utcnow()),
}
s3_manager.put(json.dumps(sidecar, indent=2).encode("utf-8"),
                f"{output_path}/{stem}_metadata.json")
```

Existing sidecars on S3 keep working untouched: `_max_pull_time` gracefully returns `None` when the field is missing.

## Why bother

`metadata.time.pull_completed_at` is the third of four named times in the dashboard pipeline (per `scans/prism/2026-05-11_dashboard_live_refresh_and_time.md` §1). Today the engine has machinery to read it and the chrome would render it if we asked; the only thing missing is helpers writing it. Once that round-trip lands, the next time we want to surface "data is N hours stale at the source" (a common observability ask), the field is already there — no helper-side change needed.

## Reply with

  - a `## Confirmation` block listing the file:line ranges actually edited (and any helper-function names you added or renamed), plus a 1-line summary per change.
  - a `## Frictions` section IF a helper's existing sidecar-write site doesn't match the shape above (e.g. the sidecar is keyed differently, or a helper doesn't write a sidecar at all). No friction = no section.

This is an implementation-directive, not a context-extraction prompt. Edit the files, confirm what changed, surface any frictions.
