---
session: make_table — wire the new altair static-PNG table engine into PRISM's auto-injected namespace
sent: pending
class: implementation-directive (NOT context-extraction; NOT end-usage)
preconditions:
  - The altair payload v0.5+ drag-and-drop has landed. Specifically `ai_development/mcp/utils/chart_functions.py` exports `make_table` + `TableResult` + the namespace contract `_ENGINE_NAMESPACE_TABLES = ("make_table", "TableResult")`. PIL/Pillow 11.x is already in the PRISM environment (confirmed). The L2 spoke `context/modules/static/chart_context_tables.md` has been promoted alongside `chart_context.md` and `chart_context_grids.md`.
files_to_modify:
  - ai_development/mcp/tools/script_exec_tools.py (add 2 entries to the auto-injected namespace block in §2.3 of the curated `prism/code-sandbox.md`)
reply_folded_into:
  - prism/code-sandbox.md §2.3 (extend the verbatim namespace block + count from "19 names" → "21 names"; document the make_table wrapping pattern alongside make_chart's)
  - confirmation back to staging so projects/altair/dev/notes.md and staging/README.md can flip the make_table integration row from "PENDING-PRISM" to "LIVE"
status: pending
---

Title: make_table — add the new static-PNG table engine to PRISM's auto-injected namespace

The altair payload now ships a `make_table()` engine alongside `make_chart()`. It produces beautifully-styled static PNGs for tables (watchlists, term structures, P&L attribution, factor tilts, FX cross-rates, sector tapes, calendars, snapshot dashboards) using the same DIMENSION_PRESETS, GS_PRIMARY navy palette, and Liberation Sans font stack as the chart engine. A same-preset table drops into the same UI cell a same-preset chart would.

PRISM picks the table engine on its own (it's L2-loaded via the new `chart_context_tables.md` spoke); this prompt closes the runtime-injection half so PRISM can call `make_table(...)` without an `import` statement just like it calls `make_chart(...)` today.

Two concrete things change inside `ai_development/mcp/tools/script_exec_tools.py`:

  1. **Add `make_table` and `TableResult` to the auto-injected namespace block** — the dict literal in §2.3 of `prism/code-sandbox.md`. `make_table` should be wrapped via `_wrap_chart_func(make_table, s3_manager, session.base_path, user_id=_chart_user_id)` exactly like `make_chart` (auto-injects `s3_manager` / `session_path` / `user_id`) and then through `validate_params(...)` for kwarg-error enrichment. `TableResult` is a bare-reference injection like `ChartResult`.

  2. **Update the import line at the top of `script_exec_tools.py`** — wherever it currently does `from ai_development.mcp.utils.chart_functions import (make_chart, ChartResult, ...)`, append `make_table` and `TableResult` to that import.

Patch (drop verbatim into the existing namespace block):

```python
# Existing — DO NOT remove
"make_chart":            validate_params(_wrap_chart_func(make_chart, s3_manager, session.base_path, user_id=_chart_user_id)),
"ChartResult":           ChartResult,
"ChartSpec":             ChartSpec,
# … existing annotation classes …

# NEW — add these two entries
"make_table":            validate_params(_wrap_chart_func(make_table, s3_manager, session.base_path, user_id=_chart_user_id)),
"TableResult":           TableResult,
```

The exact location: insert the two new lines AFTER the `"check_charts_quality"` entry (so the table engine sits at the end of the chart-related block, mirroring the `_ENGINE_NAMESPACE_TABLES = ("make_table", "TableResult")` tuple in chart_functions.py). Insert order matches the staging-side namespace tuple so the `prism/code-sandbox.md` §2.3 inventory can be re-derived deterministically.

`_wrap_chart_func` already does the right thing for `make_table` because the `make_table` signature carries `s3_manager`, `session_path`, and `user_id` keyword-only kwargs in the same shape as `make_chart`. No new wrapping helper is needed; verify by inspection of the `make_table` signature in `chart_functions.py`.

After the change, please reply with:

  1. The updated namespace block in full (verbatim, including the two new lines and any surrounding context lines that changed).
  2. The updated import line at the top of `script_exec_tools.py`.
  3. A 1-line confirmation that `make_table` resolves correctly in a freshly-spawned `execute_analysis_script` namespace (the smoke check is just `print(type(make_table), type(TableResult))` — should print `<class 'functools.partial'>` (the wrapped function) and `<class 'type'>` (the dataclass)).
  4. Total namespace count (was 19 chart-related names per `prism/code-sandbox.md` §2.3; should be 21 after this change).
  5. Anything that broke or surprised you.

If part of this prompt cannot be answered, add a brief `## Could not resolve` section at the end.

---

## Background — what `make_table` is

`make_table(df, *, ...)` is the altair payload's static-PNG table renderer. It ships alongside `make_chart` in the same `chart_functions.py` module and follows the same conventions:

- **Same DIMENSION_PRESETS** as charts (`wide` 700×350, `square` 450×450, `tall`, `compact`, `presentation`, `thumbnail`, `teams`)
- **Same GS_PRIMARY navy palette** (`#003359` header background, white bold header text)
- **Same Liberation Sans font stack** as `make_chart` (Liberation Sans → Arial → Helvetica)
- **Same `s3_manager` / `session_path` / `user_id` injection contract** as `make_chart`
- **Same `success` / `png_path` / `download_url` / `warnings` result-dataclass shape** (`TableResult` mirrors `ChartResult`)

PRISM-facing color modes are exactly 3 strings: `'rwg'` (red-white-green diverging at zero), `'bw'` (white-to-navy sequential for values >= 0), `'rag'` (discrete bucketing by author thresholds). All other internal palettes are engine-controlled and do NOT appear in the L2 spoke. The full skill spec lives in `context/modules/static/chart_context_tables.md`.

Engine implementation details, validation rules, and demo gallery live in the staging repo at `projects/altair/`. PRISM-side install is the only step left.
