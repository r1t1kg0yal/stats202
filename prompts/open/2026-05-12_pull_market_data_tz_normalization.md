---
class: code-change (PRISM-side fix)
topic: normalise tz convention across pull_market_data modes (eod / iday)
priority: low (engine now absorbs the friction; this prompt is for SOURCE-side hygiene)
generated: 2026-05-12
context: staging engine fix for ticket TKT-20260512-020107 just landed
---

# Normalise tz convention across pull_market_data modes

## What's already been fixed

`echart_dashboard._derive_domain_end` now coerces every per-dataset
max Timestamp to tz-naive UTC before the cross-dataset `max()`
comparison. So PRISM no longer has to write workarounds like

```python
df['date'] = pd.to_datetime(df['date'], utc=True).dt.tz_localize(None)
```

in `build.py` transforms when mixing intraday + EOD pulls. The engine
absorbs the friction. **You don't have to do anything for the
ust_10y_intraday case anymore.**

This prompt is about a DIFFERENT thing: making `pull_market_data`
itself emit a uniform tz convention across its modes, so the friction
never even reaches the engine. Two-sided fix is better hygiene.

## Diagnosis (verbatim from TKT-20260512-020107)

> The dashboard engine's metadata stamping (metadata.time.data_domain_end
> / pull_completed_at) does a max() across all datasets' date columns.
> `pull_market_data(mode='iday')` writes the intraday CSV with tz-aware
> timestamps in US/Eastern (e.g. '2026-05-12 00:00:00-04:00'), while
> `pull_market_data(mode='eod')` writes the EOD CSV with a tz-naive
> 'date' index. The cross-dataset max() then fails because pandas
> refuses to compare tz-aware and tz-naive Timestamps.

The engine fix unblocks compile. But the underlying friction lives in
`ai_development/mcp/utils/data_functions.py::pull_market_data`.

## The PRISM-side task

Pick ONE of two policies and apply consistently across every `mode`
emitted by `pull_market_data`:

**Option A: All tz-naive, UTC wall-clock semantics.**

Both modes emit the CSV with a tz-naive date / datetime index, where
values are stored as UTC wall-clock times. Downstream consumers can
re-localise to ET / local zones if they want. This matches the EOD
convention today.

**Option B: All tz-aware, US/Eastern.**

Both modes emit a tz-aware timestamp column in `America/New_York`.
Downstream consumers can `.dt.tz_convert(...)` if they want UTC.
This matches the intraday convention today.

Either is fine; just pick one. The point is to have ONE convention,
not two.

## Concrete changes

In `ai_development/mcp/utils/data_functions.py::pull_market_data`:

1. Identify the branches that produce CSVs per `mode` (`'eod'`,
   `'iday'`, others if any).
2. At each branch's CSV-write step, normalise the date / timestamp
   column to the chosen policy:
   - Option A: `df['date'] = df['date'].dt.tz_localize(None)` after
     converting to UTC (`.dt.tz_convert('UTC')` first if aware).
   - Option B: `df['date'] = df['date'].dt.tz_localize('America/New_York')`
     after parsing to naive ET wall-clock (or `.dt.tz_convert('America/New_York')`
     if already aware).
3. Same for the `<stem>_metadata.json` sidecar if it carries any
   timestamp field with tz baggage.
4. If the function exposes a `tz=` kwarg / config flag, decide whether
   to honour an override or strip-and-normalise unconditionally. The
   skill module's contract should say which.

## Reply structure

1. Quote the verbatim head of `pull_market_data` (signature + docstring
   + first 30 lines of body).
2. Identify every `mode == 'X'` branch that writes a CSV, with file
   line numbers.
3. Quote the existing tz-handling at each branch (or NOTE: tz-naive /
   NOTE: tz-aware US/Eastern).
4. Propose the unified policy (A or B above; one-line justification).
5. Provide the unified diff that lands it.
6. Note any downstream callers (`projects/apis/**` clients,
   `GS/skills/**` skill modules, `ai_development/dashboards/**`
   transforms) that consume the CSV and might rely on the old
   convention; flag them for follow-up.

## Acceptance

After this change, the engine-side workaround in
`_derive_domain_end` is no longer load-bearing — both modes already
emit a consistent shape and `pd.Timestamp.max()` across datasets is
trivially well-defined. The engine-side fix stays in place as
defence-in-depth (a future `pull_some_other_source` might emit a
weird tz too).

## Why this is low priority

The engine fix already eliminates the user-visible friction (build
no longer crashes on mixed-tz datasets). This prompt is about
upstream cleanliness, not blocking. Slot whenever convenient.
