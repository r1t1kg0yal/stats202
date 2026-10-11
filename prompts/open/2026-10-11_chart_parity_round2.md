---
class: context-extraction
topic: chart payload round 2 -- PRISM-side edits since the last promotion (chunk hashes), the sandbox render path, image promotion inside the sub-agent, delivery placeholders, units.py, what the NO_ARTIFACTS calls were
expected_reply: ~30-50 KB (chunk report, sandbox_rollout.py + chart_names.py + units.py whole, short verbatim excerpts)
created_at: 2026-10-11
sent: no
status: OPEN
trigger: >
  The 2026-10-08 replies showed PRISM's core.py and three context files we
  never touched (annotations, dual_axis, grids) differ from our last promotion,
  production diverts every attributed render_charts call to the prism-sandbox
  gateway, and the sub-agent pair became PRISM-owned on 2026-10-11. Staging
  cannot promote the engine until PRISM's own edits are folded in, and cannot
  test the production render path until it knows the sandbox side.
reply_folds_into:
  - projects/altair/altair-payload/chart_render/core.py and chart_context*.md (3-way merge, base dev/_before_p6)
  - projects/altair/prism_mcp/tools/sandbox_rollout.py, prism_mcp/sandbox/chart_names.py, prism_mcp/chart_render/units.py (verbatim mirrors)
  - projects/altair/dev/test_chart_exec.py (a 'sandbox' layer)
  - prism/subagents.md (§4 lifecycle, §7 image transport), prism/code-sandbox.md, prism/codebase-tree.md
  - prism/_reference/00-charts-system.md (description line)
  - prism/subagents.md §8.1 (what the NO_ARTIFACTS calls were)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

Why this prompt exists.

1. **PRISM has edits we never received.** Against `dev/_before_p6` (the last
   promotion), PRISM's `core.py` def lines drift by +4, +2, -1, -1 and -2 lines at
   five separate places beyond !1939, and PRISM's `annotations` / `dual_axis` /
   `grids` context files differ from ours although we have not edited them since
   that promotion. Promoting now would silently revert all of it. §1 sends the
   chunk hashes of the last promotion (`dev/prism_chunk_parity.py`) so PRISM names
   only the chunks it changed. `_auto_melt_for_multiline` must come back CHANGED
   (that is !1939): it is the anchor that proves the method works. Staging's own
   changes since the promotion are listed by `prism_chunk_parity.py local`; a chunk
   on both lists is a conflict to merge by hand.
2. **The production render path is untested here.** `decide()` diverts every
   attributed caller to the gateway sandbox, where `artifacts` comes back empty and
   `chart_paths` arrive through `adopt`. The harness only runs in-process. You
   chose to ask first and build the sandbox layer after: §2 is what it needs.
3. **`attach_renders` may still do nothing** if ADK's `AgentTool` does not hand
   the parent's plugins to the child Runner (§3).
4. **Engine-side save_as fix (2026-10-11)** slugs whitespace out of keys because
   PRISM's marker regex cannot match one. §4.4 checks whether the Composer
   rewrite path has the same blind spot.
5. **NO_ARTIFACTS is 28.5% of production calls** and almost never the final
   status. §8 asks what those scripts were, to decide between a contract fix
   (stop probing through `render_charts`), an engine fix, or a PRISM-side
   change to what counts against the ceiling.

Sections 1-2 are blocking.

---

## Paste everything below into PRISM

This is read-only source introspection so we can keep external documentation
and a staging copy of the chart engine in sync with you. Do not build a chart,
do not edit or create any file in the repository, and do not report frictions.
You may run read-only Python in `execute_analysis_script` to read files and
compute hashes.

Answer from live source, not from remembered context, a context module, or a
previous turn's summary. Open the file and cite it. Where your live source
disagrees with a belief stated below, say so and correct it.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, constants and code **verbatim in fenced code
blocks**; do not paraphrase them.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### 1. Chunk parity against our last promotion (blocking)

The appendix holds a small Python function, `chunk_table`, and eight tables.
Each table is what `chunk_table` returns for **our copy of the file as we last
promoted it to you**. Each row is `sha256[:10]  n_lines  label`.

For each of the eight files:

1. Read your installed file as UTF-8 text and run exactly the appendix's
   `chunk_table` on it. Do not modify the function.
2. Compare your rows with ours by `label`, and report three lists:
   - **CHANGED**: label present in both, hash differs. Give our hash, your hash,
     your `n_lines`.
   - **ADDED**: label only you have. Give the label of the row before it in
     your table, and your `n_lines`.
   - **REMOVED**: label only we have.
3. Report the total row count of your table, and the file's byte size and
   `sha256[:16]`.

Then, under `## Appendix: chunks`, paste **verbatim** every CHANGED or ADDED
chunk of 80 lines or fewer, exactly the lines `chunk_table` assigned to it
(the comments and blank lines above a def belong to the def's chunk). For a
CHANGED or ADDED chunk longer than 80 lines, do not paste it; list it with its
line count and we will narrow it in a follow-up.

We expect `_auto_melt_for_multiline` in `core.py` to come back CHANGED. Say
explicitly if it does not.

### 2. The sandbox render path (blocking)

Our belief: `core/config/environments/prod/common.yaml:247-252` enables
`sandbox.analysis` with a `gateway` executor (`prism-sandbox/execute_analysis_script`)
and no allow or deny list, so `decide()` diverts every attributed caller. On
divert, `render_charts` reads only `stdout`; `chart_paths` come back through
`adopt=recorder.adopt`; `artifacts` is empty because `_wrap_chart_func` and
`recorder.record` exist only in the in-process namespace.

1. Paste `prism-core/prism_mcp/tools/sandbox_rollout.py` **whole**.
2. Paste `prism-core/prism_mcp/sandbox/chart_names.py` **whole**.
3. On a diverted `render_charts` call, which code builds the namespace the chart
   script runs in on the sandbox side, and where does it live (repository path,
   or a separate image)? Paste the function. Specifically: are `make_chart`,
   `make_table` and the packs wrapped there, and if so with what; how does the
   sandbox side tell `render_charts` which PNGs it wrote (a stdout protocol, a
   manifest key, a listing); and what does `adopt` receive.
4. Inside the sandbox image: does `chart_render.core.register_studio()` run, so
   the editable-spec manifest is written? Is `web/backend_django/fonts` present,
   or does `_gs_font_dir()` return None and fall to system fonts? Quote the
   pins for `altair`, `numpy`, `pandas`, `pillow` and `vl-convert-python` from
   `requirements-sandbox-arm64.txt` (path and line).
5. The chart-call records for 2026-09-10 to 2026-10-11 carried 1,654 artifact
   records over 1,746 calls, which does not fit "artifacts is empty on divert".
   Which field of the chart-call manifest records whether a call ran in the
   sandbox or in-process, and how many calls in that window ran each way?

### 3. Image promotion inside the sub-agent

`ImagePromotionPlugin` is installed on the main agent's App/Runner
(`core/gs_llm2.py:3342`). `chart_agent` runs as an ADK `AgentTool`.

1. Paste `inspect.getsource(google.adk.tools.agent_tool.AgentTool.run_async)`
   from the installed ADK, and give the ADK version.
2. Does the child Runner it builds receive the parent's plugins? Quote the line
   that decides it.
3. If it does not: does anything else turn `[[image: key]]` markers in the chart
   sub-agent's own `function_response` into image parts? Cite it, or say that
   nothing does.

### 4. Delivery placeholders

1. Paste `_defers_to_the_renderer()` and the branch of
   `generate_download_links_for_sandbox` that returns placeholder references,
   verbatim, with one example of the placeholder string it produces.
2. Paste the regexes `composer_views._sentinel_artifact_paths` and
   `_resolve_link_sentinels` use.
3. Which surfaces take the placeholder branch, and which get real `short_url`s?
4. If a chart's S3 key contains a space (`sessions/x/US 10y yield_ab12cd01.png`),
   does `_rewrite_answer_chart_imgs` still resolve `![title](<reference>)` for
   it? Answer from the regexes.

### 5. `units.py`

Paste `prism-core/prism_mcp/chart_render/units.py` **whole**.

### 6. `00-charts-system.md`

1. Quote the full `description:` value from the front matter of
   `prism-core/context/modules/static/core/charts_system/00-charts-system.md`.
2. Does anything read this file other than the OKF floor in
   `prism-core/context/okf.py`? Cite each reader.

### 7. Tests

1. Does `prism-core/tests/test_chart_characterization.py` exist? If yes, its
   test count and the number of golden files under `tests/golden/chart_specs/`.
2. List every test file that imports `prism_mcp.chart_render`,
   `prism_mcp.utils.chart_functions` or `prism_mcp.tools.chart_exec`, with its
   test count.

### 8. What the NO_ARTIFACTS calls were

In the 2026-09-10 to 2026-10-11 chart-call records, 498 of 1,746 `render_charts`
calls returned `NO_ARTIFACTS`, but only 1 of 807 invocations ended on it. So
the sub-agent spends calls against `CHART_ATTEMPT_CEILING` on scripts that
render nothing and then goes on to render.

1. Pick 10 `NO_ARTIFACTS` attempts from that window, spread across sessions,
   and for each give the `chart_calls/<agent_id>__<token>/attempt_NN.py` path,
   its attempt number, the status of the next attempt in the same invocation,
   and the script **verbatim** if it is 40 lines or fewer (first 40 lines
   otherwise).
2. Classify all 498 by what the script did, using the code itself: inspected
   the data only (`print`, `.head()`, `.describe()`, `.columns`), built a
   chart object without calling a chart function, called a chart function
   that raised before writing, wrote a PNG whose key does not end `.png`, or
   other. Give the count per class, and say how you classified (a regex over
   the scripts is fine; name it).
3. Quote the text `render_charts` returns for a `NO_ARTIFACTS` call, and the
   line that counts it toward `CHART_ATTEMPT_CEILING`.

---

## Reply structure

Use one `##` heading per section above, numbered the same, with sub-answers in
order. Put §1 in one table per file (CHANGED / ADDED / REMOVED). Put the chunk pastes under
`## Appendix: chunks`, one fenced block per chunk headed by `path :: label`,
and whole-file pastes under `## Appendix: whole files`, one fenced block per
file headed by its path.

---

## Appendix: our chunk tables (the last promotion)

<!-- CHUNK TABLES START -->

### The chunker (run exactly this)

```python
def chunk_table(text):
    """[(label, sha256[:10], n_lines)] for each chunk of a .py or .md file's text."""
    import ast
    import hashlib
    import re

    lines = text.splitlines(keepends=True)
    spans = []
    try:
        body = ast.parse(text).body
    except SyntaxError:
        body = None
    if body is not None:
        def name_of(node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                return node.name
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target] if isinstance(node, ast.AnnAssign) else [])
            names = []
            for t in targets:
                for n in (t.elts if isinstance(t, ast.Tuple) else [t]):
                    names.append(n.id if isinstance(n, ast.Name) else type(n).__name__)
            if names:
                return ",".join(names)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                return "import"
            return type(node).__name__

        start = 0
        for node in body:
            spans.append((name_of(node), start, node.end_lineno))
            start = node.end_lineno
        if start < len(lines):
            spans.append(("<tail>", start, len(lines)))
    else:
        heads, fenced = [(0, "<preamble>")], False
        for i, line in enumerate(lines):
            if line.lstrip().startswith(("```", "~~~")):
                fenced = not fenced
            elif not fenced and re.match(r"#{1,6} ", line):
                heads.append((i, line.strip()[:70]))
        heads.append((len(lines), None))
        spans = [(label, a, b) for (a, label), (b, _) in zip(heads, heads[1:]) if b > a]

    out, seen = [], {}
    for name, a, b in spans:
        seen[name] = seen.get(name, 0) + 1
        label = name if seen[name] == 1 else f"{name}#{seen[name]}"
        digest = hashlib.sha256("".join(lines[a:b]).encode("utf-8")).hexdigest()[:10]
        out.append((label, digest, b - a))
    return out
```

### `prism-core/prism_mcp/chart_render/core.py` -- 924 chunks

```
aea55a6fb7    50 Expr
82ed152553     2 import
d8e23a9193     5 import#2
3b3ea3cdc7     1 import#3
62cd3ae402     1 import#4
cf23479a6b     1 import#5
6abd451366     1 import#6
261a9112a2     1 import#7
6f32a18263     1 import#8
82847998d6     1 import#9
c03077efc8     1 import#10
085ea91d7c     1 import#11
3727adff52     1 import#12
a830333312     1 import#13
c517577851     1 import#14
bfda8797d0     1 import#15
8ae7a5d0f1     1 import#16
73e2325d4d     1 import#17
6164efa8ac     1 import#18
67ec3a3296     1 import#19
3f37b97f70     1 import#20
3cb9ffccba     1 import#21
0581831645     4 import#22
7d5a5e4a94     5 import#23
bc91635c0b     1 import#24
d34aea06c9     1 import#25
d7a11d5edc     1 import#26
12c829c0d7     1 import#27
3f91c5e707     9 import#28
3aa10a81a6     1 import#29
eef7048ff6     1 import#30
c91c0d78ab     2 _SUBSCHEMA_INDEXES
6ad25eb230    13 _share_jsonschema_subschema_index
677667553a     3 Expr#2
5fd71de0d1     5 logger
3fc39e2ea8     7 If
4c5dd01f0b    26 _NullDownload
ffbc72759c     5 generate_presigned_download_url
ba173a6dc2     3 _chart_studio
515cfa2eb8     1 _table_studio
e5342693b9     1 _STUDIO_DIMENSION_PRESETS
33c080d8e6     1 _compute_chart_id
170605e8c1     5 _FONT_REPO_ROOT
1065a332b6    14 _gs_font_dir
c131911c72    14 register_trusted_extensions
d418062fd0    22 register_studio
4dab7f5873    23 ChartType
e3f3e7630e     2 IntentType
4cc27c3fc6    21 DimensionPreset
ca177a1486     2 SkinName
f4d1badcdc    10 Expr#3
9bf4e65b57     9 MAX_COLOR_CARDINALITY
f704d5bd9c     1 MAX_ROWS_INTERACTIVE
031fad8cf0     9 MAX_LINE_SERIES
9452c1ef9e     1 MAX_ORDERED_LINE_SERIES
e4bb2dd1ea     1 MAX_STACKED_AREA_BANDS
d74d5b4140     3 MAX_ROWS_BEFORE_DOWNSAMPLE
eecfac4431     1 DOWNSAMPLE_TARGET_ROWS
40bce67d95    14 _MIN_GROUPED_BAR_PER_BAR_PX
6aacce087e     5 _GROUPED_BAR_FACET_SPACING_PX
d70d717b9c     4 _GROUPED_BAR_INNER_X_PADDING_OUTER
c331caa73c     1 _GROUPED_BAR_INNER_X_PADDING_INNER
504752fb4a     9 _GROUPED_BAR_CATEGORY_LABEL_FONT_SIZE
ad8ad2f4d7    18 _facet_header_label_font
ab51ecd84c     5 _VEGA_LITE_UNSAFE_CHARS
a7c18ebd2d     7 TENOR_ORDER
839fa5c023    16 DIMENSION_PRESETS
f18f43efc5    16 _FACET_VALID_CHART_TYPES
3a3594435d     7 _FACET_MIN_PANELS
4da566070a     4 _FACET_HARD_CAP
534203d89a     4 _FACET_SOFT_WARN_THRESHOLD
e3dcbde025     6 _FACET_DEFAULT_SPACING
a9185b3b8e    17 _SUBCHART_TITLE_FONT_SIZE
d078eee26e     1 _SUBCHART_SUBTITLE_FONT_SIZE
632d4aa584     1 _TEXT_CHAR_WIDTH_RATIO
55ffab03be    10 _TEXT_FONT_SIZE
999115bb64    13 _TEXT_LINE_CAP
0109c88843     4 _TEXT_LINE_CAP_BY_SLOT
ec2f1d1d66    20 _safe_legend_kwargs
118870acd7    24 ValidationError
f607838af1    66 _raise_on_failure
5556e1bf2a    20 _aggregate_finding_messages
b4b5215e9f    16 _raise_findings
2b1935c3b5    26 _PUBLIC_CHART_MAPPING_KEYS
103859f8a3    31 _ENGINE_ONLY_CHART_MAPPING_KEYS
926107d70d    13 _MAKE_CHART_TOP_LEVEL_KWARGS
79d2d2e459    19 _MAKE_CHART_PARAM_ALIASES
133e01f1ce     6 _MAKE_CHART_PARAM_NOUNS
37d6462830    13 _LAYER_ALLOWED_KEYS
455f4d7e4b     3 _LAYER_REGRESSION_METHODS
b4fe28004b    16 _RETIRED_KEY_CANONICAL
1b015c60c1    10 _retired_key_hint
f87235eb49    70 _collect_chart_mapping_findings
d436108816    35 _collect_make_chart_extra_findings
207e319ff9    86 _make_chart_bind_findings
fbf98f6e57    83 _collect_layer_findings
12a8af81d5    18 YAxisLabelTooLongError
f5594ac644    26 LvlSeriesNameTooLongError
764d9a6392    32 LegendLabelTooLongError
698aaec424    33 HeatmapRowLabelTooLongError
8c1f18426d    34 HeatmapColumnLabelTooLongError
b453e5902f    33 BarCategoryLabelTooLongError
8d70c50ede    33 NominalLabelTooLongError
93e3896078    28 LegendTitleTooLongError
5fbecaa237    26 SeriesMisalignmentError
39aa06a120    26 SeriesOscillationError
607a8eb7c8    40 _NO_TRUNCATE_LABEL_LIMIT
89b12a55a9    14 _NO_AXIS_EXTENT_CLAMP
eca9842534    12 _AXIS_LABEL_CHAR_WIDTH_RATIO
a6c71c80f0     3 _SKIN_AXIS_LABEL_FONT_PX
e62840c1fe     6 _AXIS_TITLE_LINE_CHARS
092582e93b     1 _Y_AXIS_LABEL_MAX_CHARS
4e8a1833b7    16 _DUAL_AXIS_RIGHT_TITLE_PLACEHOLDERS
792ea0be7d     7 _HEATMAP_ROW_GUTTER_FRAC_STANDALONE
71d202158b     1 _HEATMAP_ROW_GUTTER_FRAC_COMPOSITE
d931d5cba2     1 _HEATMAP_ROW_LABEL_VERTICAL_PAD_PX
82c9fdeb69     5 _HEATMAP_FULL_MONTH_LABEL_RE
388983ebac    10 _LVL_SERIES_NAME_MAX_CHARS
c99ab3f005    43 _NOMINAL_LABEL_MAX_CHARS
69816ba2ff    11 _NOMINAL_LABEL_MAX_LINES
262ff12256    10 _HBAR_LABEL_MAX_CHARS
a1d0ef2213     7 _HEATMAP_ROW_LABEL_MAX_CHARS
98605f526b     1 _HEATMAP_COLUMN_LABEL_MAX_CHARS
2e56697de4     9 _MIN_SCATTER_VISIBLE_DOTS
9858d93347    10 _MIN_SERIES_VERTICAL_SHARE
0385a095ee    12 _LEVEL_DISPARITY_RATIO_THRESHOLD
509b331b25    14 _SEASONAL_STRENGTH_THRESHOLD
8aa8086690     1 _SEASONAL_SWING_LEVEL_THRESHOLD
f0d38ddfd0     1 _SEASONAL_SWING_RANGE_THRESHOLD
060baf0dae     1 _SEASONAL_MIN_CYCLES
d95780516b     8 _AREA_SERIES_COVERAGE_MIN
92efba8908     8 _OSCILLATION_REVERSAL_THRESHOLD
bfd113bb71     1 _OSCILLATION_VERTICAL_RATIO_THRESHOLD
b04d849fc3     1 _OSCILLATION_LARGE_STEP_THRESHOLD
b98f845706     1 _OSCILLATION_LARGE_STEP_RATE_THRESHOLD
eb5b44ce29     1 _OSCILLATION_MIN_POINTS
7f85397f20    14 _MAX_LINE_SERIES_MISSING_FRAC
dbdd69981a    17 _MIN_SERIES_HORIZONTAL_SHARE
73c5878920     5 _axis_label_px_per_char
aa66362901     5 _axis_label_pixel_budget
a4c3b86ebc    28 _axis_text_width_px
7f6ee295f7    10 _axis_labels_max_width_px
e4cea7bca8    11 _heatmap_axis_label_font_size
52c505e228    30 _validate_y_axis_label
c4546cab97    46 _validate_dual_axis_right_title
e1114e15a6    59 _suggest_label_abbreviations
1ddbc2a7d0     6 _label_line_shape
f6d14081a3   104 _validate_nominal_labels
56a97f4cb0    18 _validate_bar_category_labels
a2cc83dc44    30 _bar_would_auto_flip
99ca001b86    73 _nominal_label_surfaces
c83ebd9937    21 _BAR_UNIT_FAMILY
6b28fb654e    15 _unit_family
d9324854dd    40 _validate_bar_unit_homogeneity
103a8a9b4e    43 _grouped_bar_cell_budget
ffcb3983a5    21 _is_grouped_bar
b36c7d4692    16 _BAND_SCALE_X_CHART_TYPES
e641792ba6    28 _x_renders_on_band_scale
2a0d980cd2    15 _get_field
f74a424972    19 _is_orderable
bc22556129    27 _extract_fields
8368acfd0c    71 _sanitize_column_names
91748b2934     6 _DEFAULT_INTRADAY_TZ
809cdb951f    13 _X_TIMEZONE_ALIASES
caae8b9701    14 _resolve_x_timezone
7bd37345ab    12 _to_et_naive_wall_clock
dffdcc1720    18 _convert_wall_clock_timezone
08e6e77d70    25 _intraday_label_expr
80e0c94660    24 _is_intraday_datetime_series
93914da759    12 HEATMAP_QUARTER_RE
70c439f036    16 _quarter_label_to_timestamp
e25660f3aa    21 _parse_bar_period_label
b509e567a6    22 _period_string_series_to_datetime
0743b6c34b     5 _FULL_DATE_TEXT_RE
4392754028    25 _stash_period_source_labels
7508146617   177 _normalize_intraday_x_column
24f249943d    87 _parse_heatmap_string_to_timestamp
c59c343b43    25 _parse_month_day_batch
c820755d65    16 _coerce_heatmap_time_only_batch
203a39e4ae    17 _coerce_calendar_year_timestamp
58ad899c2f    73 _coerce_heatmap_x_value_to_timestamp
e683018ef9    25 _infer_heatmap_period_frequency
6c2cc0aaf2     5 _heatmap_intraday_display_label
1a2b5af4ca    20 _heatmap_period_display_label
97b0d903cb    23 _heatmap_x_value_kind
cd64ed005f    34 _parse_heatmap_display_label_to_timestamp
2dfeae3eb6    39 _heatmap_nice_column_step
159bfb7150    45 _uniform_step_indices
8f58e7a28f    52 _heatmap_calendar_tick_subset
20321a410f   136 _normalize_heatmap_x_column
2cb115c64d    89 _coerce_string_x_to_datetime
2d91d5ff03   117 _materialize_ordinal_datetime_x
b93a38c0e6    61 _materialize_band_path
24ad7ccbed    38 _house_period_labels
777950c2ea    23 _materialize_period_axis
b8921c0b95    27 _annotation_on_timeline
b7ccfc6152     5 _CALENDAR_YEAR_RANGE
6567a3bbcb     1 _CALENDAR_YEAR_MAX_STEP
f919bc7f15     1 _YEAR_HEADER_RE
76391f6f31     1 _NOT_YEAR_HEADER_RE
8b3fadb754    28 _calendar_year_stamps
a1a5fc5b9f    18 _years_read_as_epoch_nanoseconds
07436b9ce4     3 _PERIOD_FREQ_BY_GRAIN
783cafe6c1    27 _annotation_stamp
bae155ac41    29 _period_index_of
7bb132a7d3    44 _move_annotation_onto_periods
bbca3f24cb    97 _materialize_bar_periods
ff65f2485b    67 _materialize_contribution_periods
0f55e02fe9    39 _relabel_annotation_x
00ee93f71e    18 _band_level_fields
6bb7aae70f     6 _BUILDER_OWNED_Y_DOMAIN
7c50e8ea55    29 _band_y_domain
fb5c568f0e    25 _contribution_net_values
826ad7a642    36 _contribution_y_domain
e17ab88039    58 _collect_band_findings
451aea3654    64 _collect_contribution_findings
674c38ee46   415 _collect_plot_ready_findings
541a3749d9    75 _collect_encoding_findings
d0037bf44c    15 _validate_encoding_data
4c45cba6ad   230 _collect_integrity_findings
63752fca47    20 _validate_chart_data_integrity
957c0aaef7   171 _collect_content_findings
1ab3b1155b    23 _collect_explicit_title_findings
f74df1a7b7   130 _validate_line_coverage
a1d16ed539    16 _ordered_axis_span
f261c1b384    32 _plotted_row_groups
272096dcb6    40 _x_axis_candidate_columns
fa5ca76e55   146 _validate_x_extent
1a25d92c33    70 _validate_temporal_x_plausibility
a66f88993b   181 _validate_y_scale_homogeneity
d87ab4c36d   142 _validate_y_level_disparity
5d6d7d37c4    27 _infer_seasonal_period
e186261627    51 _seasonal_diagnostics
4a35a34a27    86 _seasonal_jaggedness_warning
3d057cff70    37 _oscillation_series_diagnostics
0cb470316e    91 _validate_series_oscillation
e7a2b8bea4    60 _validate_series_alignment
77b7eff960    29 _group_scale_ok
ce6dd11f6b   164 _maybe_auto_recover_y_scale
257d8574a9    18 _LABEL_ABBREVIATIONS
a08dd57d67    24 _dedup_axis_title
d0ee6a3237    53 _format_label
9655300f9c    12 _LINE_STYLE_DASH
1b7347896b    11 _OBVIOUS_HLINE_THRESHOLDS
ec0483c8b1     9 _VLINE_RIGHT_EDGE_REJECT_FRAC
fc39f645a2    18 _resolve_axis_type
db05a0acf7    32 _profile_x_axis_type
2ce1f2ffeb    42 _resolve_point_family_x_encoding
a0b3500381    36 _ordinal_x_axis
92457bf23b    18 _x_axis_is_profile
8ba7ba9fca    19 _annotation_x_axis_type
8e794a4bf4    29 _annotation_y_axis_type
648620bc7a    22 _annotation_y_encoding
6cdae30d41    18 _band_scale_text_offsets
cb97ea0a0a    13 _note
1a5a91302b    12 _band_domain
8d87fd0bdb    27 _band_row_slice
288eecaf4a    15 _band_positions
79940ce1e3    18 _band_midpoint
b07c8412a4    28 _resolve_x_sort_for_annotation
17527a0851    29 _last_row_at_max_x
0b8059da24    32 _apply_nominal_axis_sort
ede5b1e12e    29 _to_numeric_x
5bab84c500    17 Annotation
08514b4bf9   126 VLine
edb2786622   152 HLine
89580294cd   225 Band
2314035fd2    96 PointLabel
b1e6f5677c   276 Arrow
a3b7aaa6b7    79 Trendline
83c1c209c5   206 Segment
32f92ecda4   121 PointHighlight
f7a786bbd1   207 Callout
52db1673c9   351 LastValueLabel
9e0c980fbc     9 _PLOTTEXT_AUTO_PRIORITY
8a0cb176cf    11 _PLOTTEXT_VALID_POSITIONS
c1a12b0b3d     6 _PLOTTEXT_LEGACY_POSITIONS
322e2c7fd2     9 PLOTTEXT_HARD_WORD_CAP
fae50824b6     1 PLOTTEXT_SOFT_WORD_CAP
ca5df80368    30 _validate_plottext_position
6c95d84c1b     7 _count_words
a9dc506cd0    28 _validate_plottext_text
418fc13088    87 PlotText
34071b7eb4    19 _squash_name
03706bf770    27 _ANNOTATION_TYPE_ALIASES
68f3b54354     8 _ANNOTATION_COORD_ALIASES
a349e18a9e    24 _ANNOTATION_KWARG_ALIASES
e8a98401e1     6 _AMBIGUOUS_ANNOTATION_TYPES
843d710e0b    26 _annotation_class_from_keys
b44ec3609d    18 _AMBIGUOUS_ANNOTATION_RESOLVERS
aafe960d52    93 _annotation_from_dict
8d2f378216    67 _normalize_annotation_specs
ae0f8eaa09    37 _split_annotation_dicts_from_layers
32fe225916    14 _PLOTTEXT_POSITION_TO_SLOT
e810905197   147 _route_plottext_to_panels
ada353d174   155 _auto_stagger_band_labels
010349be7c    94 _compute_bar_value_suppression
ed9ea622ea     5 _VALUE_CAPTION_RE
f6b5f07b61    13 _value_shaped_caption
494db97624     5 _bar_category_key
df2569ce46     8 _is_plain_number
12a5255dba    10 _caption_text_colour
b192950b90     5 _caption_is_light
de4ef3342b     7 _caption_to_default_colour
8599242761     7 _BAR_VALUE_LABEL_COLOR
47042ecc9e     1 _BAR_VALUE_LABEL_FONT_SIZE
bdc1847607    12 _caption_is_unstyled
0b44636cb2    13 _caption_in_bar_value_style
1dea92bcba   343 _arbitrate_bar_labels
a7144400d4     6 _BAR_LOG_LABEL_FIELD
9763255ad5    14 _bar_value_text
1af3200f83     5 _SEGMENT_MID_FIELD
38f7c69088     1 _SEGMENT_LABEL_FIELD
1e1cd44d20     1 _SEGMENT_LABEL_FONT_SIZE
da7c63123f     2 _SEGMENT_LABEL_PAD_PX
46a0d1537e     4 _SEGMENT_LABEL_LIGHT_FILL_LUMINANCE
7f90eab441    33 _stacked_segment_fill_by_category
eadc158360   112 _stacked_segment_label_layers
347072bbbe    48 _bar_value_label_font
c20c505a31    18 _vega_nice_max
6a223f4ba5    16 _hbar_end_text_domain
c2aa54dd8d    12 _hbar_value_extent
0b5f0b6852    34 _hbar_end_text
83f38254c3     9 _bar_labels_omitted_note
76d8a6575b    14 _single_bar_per_category
181b34ff4a     4 _STACK_END_FIELD
b7f36fe2c4    94 _stack_total_layers
94d03a4f54    95 _grouped_bar_value_layers
2fa4079f9d    65 _grouped_bar_rule_layers
2c90f35095    41 _rewrap_annotations_for_bar_axis
04f28ae194    35 _stacked_value_extent
1d03c0cc09   132 _dedup_vlines_by_x
886f4947dc     5 _FORWARD_EXTENSION_FRAC
e2170d2f28     1 _FORWARD_EXTENSION_PAD_FRAC
3690214077    52 _plan_forward_extension
6fb99f0806     5 _forward_extension_end
b5f04cd94f   112 _drop_right_edge_vlines
5c4c655297   145 _auto_stagger_vline_labels
acfcee8b11    53 _flip_hline_label_inside_band
6cba4b6414   131 _auto_stagger_pointlabels
6bd806c7fd   163 _auto_stagger_callouts
bd9dcfcbbb   114 _auto_stagger_hline_labels
0c2f4d2f7a    32 _collect_lvl_series_labels
1738135d51    37 _validate_lvl_series_names
1286d6afe5    43 _should_auto_inject_lvl
cf50f2af96     7 _same_words
1e849c68d1    17 _single_line_label_repeats_y_title
ddb51f19ca     5 _MARKER_KEY
8e127c10eb     4 _is_marker_key
b999a8b1b4     9 _label_restates_value
d20e00ee0f     6 _ORDERED_LINE_SCHEMES
2021071d4c    11 _ordered_line_scheme
f492e27f54    29 _ordered_line_colour_field
ac2a320a5b     3 _NUMBERED_LABEL
21825744fc    17 _numbered_sequence
4de63f6172    17 _strip_dual_axis_lvl_annotations
dff3cdcd01    16 _strip_lvl_annotations
91da10df1c    29 _values_match_for_endpoint
f361497330   130 _strip_endpoint_annotations_redundant_to_lvl
9c2b31a101    26 _merge_coincident_markers
37d55c4990   119 _stagger_lvl_text_y
9099f25955   137 _rewrite_y_encodings_for_dual_axis
8648607ecc    38 _LP_PRIORITY
510471f3b2     2 _LP_COLUMN_TOL_PX
0abc12c3d8     1 _LP_COLUMN_SEED_DY
11f83d5525     1 _LP_MIN_GAP_PX
6232aca493     1 _LP_EDGE_PAD_PX
aaef6c171d     1 _LP_LINE_HEIGHT
051405aeac     1 _LP_MIN_FONT_SIZE
e6cd96fc24     1 _LP_LEADER_COLOR
a347667e10     1 _LP_LEADER_WIDTH
53a82f5cc8     1 _LP_LEADER_REACH_X
00392f5d6e     1 _LP_LEADER_GAP_PX
f76706cb91    17 _lp_measure
6a14f2996a   182 _LabelCanvas
0765d2b4ae    61 _LabelBox
42949ae22f     9 _lp_align_offset
66d9638553    17 _lp_render_dx
917feed99b    13 _lp_overlaps
5fffc98ebb    13 _lp_inside
e0540d48fd    36 _lp_sanitize_seed
b7083923bc    27 _lp_ladder_compass
193c3b4d45    21 _lp_ladder_rows
098e3c78e1    45 _lp_rule_obstacles
7d194b861c    34 _lp_sweep
20ea662bbc    22 _lp_ladder_leader
9cafc51de0    24 _lp_leader
007f31f3f5   221 _lp_collect
93d7e812a0    83 _lp_seed_column_order
db5abbb5b7   124 _lp_solve
a46490043e    74 _lp_apply
4a17304760    46 _place_labels
07d182184e  1564 render_annotations
bacb6a40d8    46 AxisConfig
05a1f2968f    24 DateFormatConfig
c98cf94554    72 DATE_FORMAT_PRESETS
4bc81f9757    39 calculate_optimal_label_angle
4c529b39c6    10 _PROFILE_LABEL_CHAR_PX
320786f729     1 _PROFILE_LABEL_PAD_PX
99149623f3     1 _PROFILE_MIN_PITCH_45_PX
cc176cb18f     1 _PROFILE_MIN_HORIZONTAL_TICKS
125cebbdc6     5 _HEATMAP_MIN_LABEL_FONT_PX
dc9d0b98ae     4 _HEATMAP_CALENDAR_MAX_TICKS
d866c87d97     3 _HEATMAP_CALENDAR_YEAR_MIN
0c0a14020e     1 _HEATMAP_CALENDAR_YEAR_MAX
2c109d8dce     2 _HEATMAP_COLUMN_PITCH_MARGIN
a618966f08    22 _uniform_step_subset
072e48dc77    30 _resolve_profile_x_order
8b20b1424c    38 _profile_ordinal_axis_plan
7b7a7fabb4    14 detect_label_collision
46e836c883    23 _temporal_tick_step
51ce75c384     7 _DEFAULT_AXIS_LABEL_FONT_SIZE
705a1fb47d     4 _BAR_HORIZONTAL_Y_LABEL_FONT_MIN
39aead2297    23 _horizontal_label_min_pitch_px
7077bc80f8     9 _bar_horizontal_label_font_for_pitch
d10b9ecc80    27 _bar_horizontal_y_label_font_size
610568ffba    13 _bar_horizontal_row_capacity
e01e506f92    19 _bar_vertical_category_capacity
f032061920    72 _validate_bar_horizontal_label_pitch
a8d7a0c495    50 _BAR_CATEGORY_LABEL_GAP_PX
1e0249b93f     3 _BAR_CATEGORY_LABEL_FONT_MIN
6f3d85225f     5 _BAR_CATEGORY_LABEL_FONT_COMFORT
2e9a511479     3 _BAR_CATEGORY_DIAGONAL_PITCH_FACTOR
ffee6bee70     1 _BAR_CATEGORY_ANGLE_LADDER
150555c469    16 _bar_category_label_shape
fda62cce8e    18 _bar_category_widest_label
b6b43f3272    22 _bar_category_pitch_needed
a13bab7bd9    23 _bar_category_font_for_pitch
8f00e70515    34 _NominalAxisSurface
80625d4b03    13 _BAR_SURFACE
14178a8c0d    16 _HBAR_SURFACE
1c06a64b19     8 _BOXPLOT_SURFACE
24b5c78439     8 _CONTRIBUTION_SURFACE
b9ae1035c8     9 _WATERFALL_SURFACE
3c92af67e1     8 _PROFILE_SURFACE
a64464fb05     8 _BULLET_SURFACE
2b59ed899c    11 _DONUT_SURFACE
038a0cd5bc    10 _FACET_SURFACE
6f4c28d159   117 _nominal_axis_label_plan
0cc1e0a732    46 _bar_category_axis_plan
16d8117b4a    41 _max_ticks_for_width
f967ffefe9    26 _pick_tick_count_and_angle
5dedc12390    65 _count_calendar_ticks_in_range
8e618daaef    43 _calendar_ticks_in_range
1c02b24763    20 _TICK_STEP_LADDER
64d92ad108    10 _NICE_MONTH_STEPS
be152c3fe8     1 _NICE_YEAR_STEPS
86d9a80a3f     1 _NICE_DAY_STEPS
ecbb7bbd73    18 _unique_sorted_diffs
24d5383219    29 _coarsen_month_step_to_fit
76baf2f80b    31 _format_for_step
916f75b624    83 _ensure_min_temporal_ticks
0d061746a2    33 determine_date_format
af63ec28f8     6 _ANNUAL_OBSERVATION_STRIDES
55b6dd92a4     1 _QUARTERLY_OBSERVATION_STRIDES
1d5516aa68    42 _period_observation_ticks
813a07acf3    15 _temporal_house_strftime
0d2c1d2650    14 _format_timestamp_house
4a6e6da8ed   390 _determine_date_format_raw
b68a8f6fc7    81 calculate_y_axis_domain
1b18908b68    17 should_use_log_scale
ac5846f036    12 wrap_label
1fc8ad1b6c     7 _CATEGORY_WRAP_MAX_LINES
5ce5ab522e     7 _WRAPPED_LABEL_EXPR
1c6a23ff67    23 _balanced_word_lines
62d79efb44    43 _wrap_category_label_to_pitch
93bec2972c    26 _wrap_category_labels_to_pitch
be735a2750    27 _natural_sort_key
91d514a2e0    93 _SCHEME_ANCHORS
dd65158d0d     5 _hex_to_rgb
c9c8e4a782     4 _rgb_to_hex
b7bb47e734    11 _LIGHT_HALO_COLOR
30c481a423     1 _MIN_HALO_CONTRAST_RATIO
f8aa275f32    24 _relative_luminance
c4323b4b5c    25 _halo_color_for
f5f6315294    34 _sample_named_scheme
5fc38c4857    19 _scheme_color_at
d527a340de    23 _heatmap_scale_unit
810593b955    21 _heatmap_label_color_for_value
4d36a377aa     3 _HEATMAP_LABEL_COLOR_FIELD
592ebb3043    60 _smart_number_format
252580d6d8    34 _smart_format_value
07e1b8a967     9 _all_integral
f8c2e508b8    28 _format_log_value_label
2302bcae23    11 _smart_format_template
2517a45161    53 _wrap_text_to_width
5653c1b13c    13 _chars_per_line
2c7201e3ac    29 _wrap_text_at_width
31a896e546   101 _validate_and_wrap_text
7e214dca5b     7 _title_text_from_lines
a40ca36d5a    41 _title_params_from_lines
8d34c708c2    18 _title_dict_from_lines
7ed7d6937f    50 calculate_tick_values
303def677b    15 _QUANT_TICK_GAP_PX
77484b8b5c     1 _QUANT_TICK_MIN
59d0dc278c     1 _QUANT_TICK_MAX
0c1a2c0d8f     1 _QUANT_TICK_SLACK
86a58f9e4e     4 _QUANT_X_ENCODING_TYPES
4eaaf6eff2     3 _QUANT_ZERO_CHART_TYPES
a4fa521fca    10 _format_quant_tick_label
3d64917be3     8 _quant_tick_format
93f8ee3a2b    13 _quant_bracket_ticks
7457ca0de3    16 _quant_ticks_fit
2744600137    62 plan_quantitative_ticks
d11b7d815f    49 _quantitative_axis_extent
b0d6cdaace    15 _x_axis_is_quantitative_encoding
c74583b0ed   379 get_axis_beautification
4dde396a24   244 apply_beautification_to_spec
2d4524e97f    17 _two_line_axis_title
2830195038    17 _wrap_long_axis_titles
47ef6f5582   120 _blank_duplicate_axis_titles
419026f276    72 TYPOGRAPHY_OVERRIDES
57dcaee195   103 _apply_typography_overrides
c9987396b2    29 BASE_CONFIG
a0f76bc7f0    35 _SHARED_MARK_CONFIG
1dc9a1d70d    59 _INTERACTIVE_PARAMS
ba7bb8c92f   127 _build_skin
3664c2e8aa     9 AVAILABLE_SKINS
34d168a14c     2 GS_CLEAN
ed27a9d4e1    30 get_skin
456c3b2107     6 _get_color_scale
63a7cdd1c3    20 _CATEGORICAL_PALETTES
74577b95d6     2 _HEATMAP_GRADIENT_NAMES
6e8c8160a7    26 _collect_color_kwarg_findings
4a54c40b4d    26 _NAMED_COLOR_HEX
228cbcfb3b     7 _resolve_named_color
f2fe02fd7c    20 _normalize_named_colors_in_mapping
717fb789b5    14 _SCALE_TYPE_CHART_TYPES
89387eeef5     3 _BAR_LOG_CHART_TYPES
f3ffcc0122     9 _scale_type_value_field
905edcae41   127 _collect_scale_type_findings
20ea9f832e     7 _BAR_LOG_MIN_VISIBLE_DECADES
913d45523d     2 _BAR_LOG_HEADROOM_DECADES
0acd1eb1e4     3 _BAR_LOG_DENSE_TICKS_MAX_DECADES
a60503a225     5 _BAR_LOG_MIN_SPAN_DECADES
88f1919fe9     9 _BarLogAxisPlan
b0eceabb8b    72 _bar_log_axis_plan
7c08259720     8 _LineLogAxisPlan
bece12bf69     6 _LINE_LOG_PAD_FACTOR
8dbfd9e9d2     4 _LINE_LOG_DENSE_TICKS_MAX_DECADES
c409d49c10     3 _LOG_AXIS_TICKS_KEY
5691277e63    80 _line_log_axis_plan
5708c5d3a6    14 _publish_line_log_plan
c568b62316    25 _bar_log_zero_note
6b1a96cbb0    25 _collect_legend_kwarg_findings
5253773abd    38 _collect_segment_labels_findings
81ae41977d    21 _validate_color_kwargs
5119a23729    37 _validate_color_range_kwarg
fac4b2cb22    58 _validate_color_scheme_kwarg
994d5ba98e    43 _validate_emphasis_kwarg
801b166d1b    95 _validate_color_map_kwarg
b8e84f8205    28 _resolve_single_series_color
40ea44aaf5    98 _resolve_categorical_color_scale
97399dc12f    25 _line_to_label_color_map
3ea9512eca    59 _resolve_lvl_series_label_colors
2682e9b5d9    15 _validate_opacity_value
1736607c5f    24 _collect_opacity_kwarg_findings
dda08b5e74    16 _validate_opacity_kwargs
1f04069d8d    90 _validate_opacity_map_kwarg
c4075b4f6f    54 _resolve_categorical_opacity_encoding
1824937558    30 _prepare_categorical_opacity
6ccab1707a    11 _categorical_legend
4c8a2efd76    31 _encode_categorical_color_and_opacity
029b6a6069     3 _EMPHASIS_STROKE_WIDTH
fb68d3694b    27 _line_draw_order
2adf4caf70    19 _encode_line_emphasis
8e054b1122    33 _scatter_multi_color_opacity
6e36dd923a     8 _TENOR_PATTERN
55f81db89c     8 _TENOR_UNIT_DAYS
cd2d94eb76    15 _tenor_sort_key
ee7a886937    14 _infer_tenor_sort
a7efc6e05e     6 _RELATIVE_TIME_PATTERN
7cf68ee2d3    24 _relative_time_sort_key
4e70acc728    13 _infer_relative_time_sort
0b7b85a6ec    32 _resolve_color_sort
8834223db5     6 _STACK_ORDER_FIELD
2119cf2b84    29 _assign_stack_order
4975675998     3 _LEGEND_MAX_WIDTH_FRAC
3443bcdbc7    26 Expr#4
51d9fc7425     2 _LEGEND_CHAR_WIDTH_PX
f3464e2c8f    11 Expr#5
af9ded1af9     2 _COMPOSITE_LEGEND_CELL_WIDTH_PX
eca624169a     2 Expr#6
1f5aa5a631     3 _LEGEND_LABEL_FONT_SIZE_PX
b9b119706e     2 Expr#7
0d1ef600e7     7 _legend_budget_px
3b4f6bf02a     5 _legend_label_width_px
bcea3ae522    16 _legend_label_max_chars
5f01b6455a    47 _color_legend_will_render
19e0293ae8   117 _validate_legend_labels
17f30e346d    40 _validate_legend_title
285e9b7d8c    50 _calculate_legend_config
e65244c705     9 _safe_field
8d4fb5ba0d   120 _build_tooltip
5ed61c96de    17 _force_data_embedding
eda53b4565    18 _get_y_axis
7b24270527    45 _ensure_data_embedded
d90ce567ae    47 _ensure_data_in_layers
caa5d15836   148 _validate_spec_has_data
0f6c0179b6     6 _ENCODING_AUDIT_CHANNELS
53c20d07af     4 _SHORTHAND_TYPE_CODES
2f15d4d390    30 _encoding_audit_target
4df3cfa974    18 _encoding_audit_source
520d2793fb    13 _encoding_audit_column
a18b1d10c5    31 _iter_encoding_audit_targets
5ab584672b    81 _validate_encoding_types_render
3b54d3f0e6    22 _apply_heatmap_config
60d434f97a    10 _LINE_GAP_MAX_BRIDGED
ff9b4fc4f9     9 _LINE_MONTH_GRAINS
ab40aa9f00     3 _LINE_REGULAR_GRAINS
c2050f369b     9 _LineGrain
aa518d4e18    27 _line_grain
db3f07e5bc    16 _line_grain_periods
71c27b7ffa     7 _line_timeline
ec1515147e    21 _line_gap_breaks
b34e5549ae    28 _line_gap_note
bfcc4d7e1f   103 _break_line_gaps
3162ab7281   328 _build_timeseries
f6c1f12371    29 _build_multi_line
433426efc5    48 _build_multi_line_single_axis
b60b7cb364    10 _DUAL_AXIS_SIDE_ALIASES
fa8c6d1ada    85 _resolve_dual_axis_binding
b6e3e725c3    67 _dual_axis_flatness_warnings
e29453d53d    34 _dual_axis_legend_tags_enabled
d4e5ea15b5    14 _dual_axis_legend_suffix
0e40fa6972    16 _dual_axis_legend_label
59d997e2f9     4 _dual_axis_legend_color_field
6b1a669ed6    31 _apply_dual_axis_legend_tags
28eaa84297    30 _dual_axis_legend_sort
a20ca28823    30 _legend_labels_for_validation
b8d59dc812   341 _build_multi_line_dual_axis
e83c167177   191 _build_profile_line
c37f8960d2     3 _DEFAULT_ZERO_FILL_POSITIVE
dfecc4b285     1 _DEFAULT_ZERO_FILL_NEGATIVE
ad570bd9d5    10 _scatter_color_is_gradient
fee529dccf    13 _resolve_scatter_order_field
e40f64c26f     3 _GRADIENT_LEGEND_TICK_TARGET
b212b7d0ac     1 _GRADIENT_LEGEND_TICK_MAX
a1a3641557     7 _GRADIENT_LEGEND_FRAME
89166a6519     8 _GRADIENT_LEGEND_TIME_FREQS
48d70ce868    16 _nice_tick_step
b2747e6687    32 _nice_numeric_ticks
e62d052f34    10 _tick_decimals
ce06c60f9c    13 _nice_time_ticks
bcbfd05ce6     9 _gradient_label_expr
5cbb43d2a6    60 _scatter_gradient_legend
20fb3e0309    11 _is_gradient_color_column
48070531e0     9 _scatter_gradient_bounds
c7f3876567    33 _scatter_gradient_norm_series
5a1ad8fa69     3 _SCATTER_GRADIENT_N_STOPS
c983eefaea    17 _srgb_to_lab
809039a95c    23 _lab_to_hex
05ca2699b8     6 _lab_mix
d23cd04862    10 _ramp_color
dcd6cdd64c     7 _lab_ramp
1beaa37630    17 _scatter_gradient_zero_pivot
b7e527c0fb    24 _pivoted_ramp_stops
7f0d8c713c    35 _scatter_gradient_range_stops
90a48ea87c    18 _scatter_gradient_color_scale
cc17baf138    12 _scatter_gradient_scale_spec
cad9bab684    10 _scatter_gradient_scale_uses_norm
0bd60abeb2     5 _ORDERED_LINE_MAX_LIGHTNESS
c4bf11c2b4    25 _ordered_line_ramp
ce9d6bb6c4     7 _ordered_line_scale_spec
5a7e0662e1    14 _ordered_line_order
2846f46a9b    17 _ordered_line_position
95b0e07b70    18 _ordered_line_legend
8fc1f9982b    21 _encode_ordered_line_ramp
cb96fc7e0c    53 _build_baseline_fill_layers
2b51f3702b    47 _expand_scatter_path_segments
c51bc10b01   601 _build_scatter
8dd16435dc    98 _build_scatter_multi
eff07155a9   822 _build_bar
ef472ffc43   643 _build_bar_horizontal
dea406358d   155 _build_area
b138480dd9    13 _heatmap_axis_labels
d32bad0053    22 _heatmap_row_label_font_for_pitch
3e9d995d31    33 _heatmap_row_label_font
815b63875c    47 _heatmap_row_label_plan
4a1af67f35    68 _heatmap_row_labels_fit_horizontal
d7257f4cc9   100 _validate_heatmap_row_labels
8d718f6f9d    24 _heatmap_column_label_pitch_px
85a63ae1ad    23 _heatmap_labels_are_calendar
00efa3ba79    60 _heatmap_x_axis_plan
f950cf9a2c    23 _heatmap_column_label_plan
963593eed5    74 _validate_heatmap_column_labels
cfa30f8a32    54 _heatmap_column_crowding_error
0d0cd20aa7     5 _heatmap_row_label_angle
0f3505b38c    21 _heatmap_is_symmetric
f250d2d16a    19 _HEATMAP_AUTO_ROW_PITCH_PX
138fee6f3a     1 _HEATMAP_AUTO_MAX_W
216c28bf5e     1 _HEATMAP_AUTO_MAX_H
01db0dfc40    60 _heatmap_auto_canvas
cc8727033b    45 _heatmap_min_cell_size
57b201fc11    59 _composite_preset_for_matrix_cells
e5d802b9ac   426 _build_heatmap
11c1f38bab    38 _histogram_bin_extent
d22f3f8b99    25 _vega_bin
facbcac1d5    29 _histogram_count_domain
7d10be516a   154 _build_histogram
ac6d205656   184 _build_boxplot
1764f12168   102 _build_donut
1b13fb3a3d   241 _build_bullet
f17ccdbf7a    30 _assert_waterfall_complete
06b9f36ce4   256 _build_waterfall
a0eaa9f47c     6 _BAND_TARGET_ALPHA
14d6884f3a    18 _band_x_encoding
01ac7b9bf7   247 _build_band
57fbf800b1     5 _CONTRIB_MAX_VALUE_LABELS
4428fe97d7    18 _CONTRIB_MARK_PITCH_PX
7285b141f2    29 _contribution_density_plan
4c8b8b50c5     9 _vega_label_lookup
3271cb1919    14 _contribution_period_label_for_tick
15f711845d    89 _plan_period_axis
bf1288250a   299 _build_contribution
80e2affb85   129 _build_layer
8b6ddfcb12    75 _apply_extra_layers
e661079cf7    70 _promote_index_to_x_column
ddaa6a2bf9     5 _SERIES_KEYED_MAPS
96383a1907     5 _series_spelling
3db78ce734    19 _rekey_series_maps
1db34b86b3    52 _align_series_keys
295b312f15    32 _series_group_colours
2cba7a891f    68 _desugar_series
41d9b5c1a7    39 _attach_group_legend
30f9ebd3f1   177 _auto_melt_for_multiline
2b5ce9f60e     8 _HEATMAP_X_PLACEHOLDER_ALIASES
b3b1bfa814     1 _HEATMAP_Y_PLACEHOLDER_ALIASES
7a0af25c3d   239 _auto_reshape_heatmap
394359fb1c    23 _blank_heatmap_placeholder_titles
8d3d567637   126 _auto_downsample_timeseries
d5ac7e785d    60 ChartResult
aec5b1bddc    30 DataProfile
84d00c5fc0    81 profile_df
5aa6a92cad    11 _PNG_PALETTE_MAX_COLORS
15b8706595    41 _compress_png
95c284c638    36 _json_safe_spec_value
efd0a8a164    11 _SpecInvariantError
8efdc2b581     7 _STRFTIME_TOKEN_RE
2753600d0d     4 _PLANNED_LABEL_SURFACES
0f27e3696b     7 _MIN_RENDERED_CANVAS_PX
83eea7013e    18 _iter_spec_encodings
dc0a529858    60 _assert_temporal_plans_match_scales
eb5dbb4e64    24 _assert_canvas_not_degenerate
5665a18488    36 _render_chart_to_png
07618e0bfa    34 _generate_filename
2f8cd84d41     6 _CHART_SPEC_PREFIX
913fad621b     1 _CHART_MANIFEST_NAME
858101971b    22 _MANIFEST_LOCK
c3966471aa    12 _studio_dimension_name
1f79eeb505    93 _persist_editable_spec
2d11d3207d    36 _studio_call_kwargs
deb170d0e7    23 _annotations_as_json
73a1a96174    85 _emit_chart_studio
834b068ddb  1193 _make_chart
4bfc36c943    65 _dispatch_builder
0fc918d627    18 LayoutType
618bdcc5da     6 _COMPOSITE_LAYOUTS
86fe0bb233    62 COMPOSITE_DIMENSIONS
b21a78da9f     9 _get_expected_chart_count
74110ce440    28 _layout_grid_shape
cf6a975df5    11 _CHARTSPEC_COMPOSITE_GLOBAL_KWARGS
92765213e3   136 ChartSpec
0ba0071005    53 CompositeResult
9f5c1963af   476 _build_single_chart
864d81a1b8    21 _isolate
cb3a3e7818    30 _TEXT_PANEL_DEFAULTS
24a1a1d570     5 _SIDE_PANEL_CHART_GUTTER_PX
81add85c41    29 _coerce_panel_text
d519b1ce04    37 _normalize_text_panel
fa02b03a55   128 _build_text_panel
a274aa82ac    44 _resolve_side_width
783a754d67     3 _SIDE_PANEL_MIN_READABLE_WIDTH_PX
0a599f2be0    10 Expr#8
95adddf63e    45 _autofit_side_width
b7c7377ca6    58 _wrap_with_text_panels
471117b036     6 _BLANK_PANEL_CFG
88f10fb074    18 _estimate_caption_height
7d5b2e6c38    46 _scan_text_panel_reserves
7338f4ce45   171 _apply_text_panels_to_spec
9a1d093e14    50 _composite_consensus_x_angle
dccaecb505    30 _LAYOUT_DOWNGRADE
1d21d23e62    11 _LAYOUT_SLOT_COUNT
62a2580d61    23 _downgrade_layout_for_survivors
3ca25b405a    52 _compose_charts
346a850244    44 _resolve_facet_grid_shape
62eb910b40    39 _resolve_facet_panel_dims
487f3709cd    21 _resolve_typography_for_panel_size
0b163464f7    32 _get_facet_panel_order
5308e47662    11 _split_df_by_facet
3190d710cc    23 _compute_shared_numeric_domain
3ffd7e5d68    18 _compute_shared_temporal_domain
b65e22aec6    31 _compute_shared_color_domain
1d8baf01e5    42 _inject_scale_domain_into_spec
351c4603f4    28 _strip_axis_labels_from_spec
90b84d6ddb    24 _strip_axis_title_from_spec
8e56f5c6ec    21 _strip_legend_from_spec
589c01eabb   100 _build_facet_gradient_legend_panel
50c83ef165    23 _first_color_range
de9384d2e7    60 _build_facet_legend_panel
580330d001    73 _compose_facet_grid
da73efcab1    13 _strip_schema_and_config
55820827d6    42 _inline_named_datasets_in_spec
a02e70d307   676 _render_facet_grid
cae8ecbc24    32 _resolve_composite_aliases
7ba341363b    40 _summarize_facet_panel_errors
b2ff9d88bf    37 _summarize_chart_errors
0f437c07e8    18 _normalized_source_attribution
f8e39c29a4   125 _resolve_composite_source_attribution
a083e7be87     7 _PACK_COLOUR_CHART_TYPES
db562ba735     6 _PACK_SPEC_TOP_LEVEL_KEYS
c861f5b1df    34 _cell_colour_categories
29db804bae    87 _plan_pack_colours
48ed9775a4    28 _effective_colour_map
cbc2ce61bb    43 _unify_pack_colours
bc60bd9246    57 _pack_legend_strip
13d44e2928    11 _iter_spec_dicts
f8616c1e1d   493 _make_composite
609b6ab835    45 make_2pack_horizontal
a7755cf9ca    41 make_2pack_vertical
991c3fd1d5    54 make_3pack_triangle
d75d2dd581    43 make_4pack_grid
20a6a9039e   100 make_6pack_grid
e16e03bf4b    94 build_charts
2f689be737    26 _AUTO_DIMENSIONS
a7d7e9ce6e    10 _auto_dimensions
cb440103f7    11 _BAR_HORIZONTAL_AUTO_ROW_PX
2b91c15387     1 _BAR_HORIZONTAL_AUTO_PER_BAR_PX
5e077b54f1     1 _BAR_HORIZONTAL_AUTO_MAX_HEIGHT_PX
3846104bd4    40 _bar_horizontal_auto_height
bf04a5da8c    48 AVAILABLE_TABLE_THEMES
b67b3de0cb     2 _TABLE_THEME
bd455811f0    11 _TABLE_PALETTES
6e86982f56     8 _TBL_SIDE_PAD
8d2d084e3b     1 _TBL_TEXT_COL_MAX
0354ba9e4c     1 _TBL_TEXT_COL_FLOOR
6992bec791     1 _TBL_MAX_TABLE_W
bcc3c70231     7 _TBL_MIN_COL_W
7837fa3264    22 _TBL_MAX_TABLE_H
bfcf690d0a     1 _TBL_MAX_ASPECT_RATIO
4bbdb0242f     1 _TBL_MIN_ASPECT_RATIO
e4ee5accca     1 _TBL_TARGET_HTML_WIDTH_PX
18351ab839     1 _TBL_TARGET_TEXT_PX_AT_DISPLAY
cae1d7273d     1 _TBL_NORMALIZE_MAX_ITERATIONS
02dc63688a    21 _TBL_LEGIBILITY_USABLE_IN
64435788d7     1 _TBL_MIN_LEGIBLE_PT
73268366f6     1 _TBL_FONT_TIER_FLOOR
67762e3475     1 _TBL_FONT_TIER_CEIL
d036d1db1e     1 _TBL_CELL_PAD_X
eaa28eb142     1 _TBL_BODY_PAD_BOTTOM
a9290a70ff    26 _TBL_SYSTEM_FONT_PATHS
f52a7a31d7     3 _TBL_GS_FONT_FILES
47be5ee436     1 _TBL_FONT_CACHE
58d01ce89b    22 _tbl_load_font
8fdf574e8d    11 _tbl_blend
7d218eb498     6 _tbl_readable_text_color
c3653c1c8d     3 _TBL_MIN_TEXT_CONTRAST
b118008f4b    14 _tbl_contrast_ratio
7516bb0124    12 _tbl_palette_seq
f761043714    16 _tbl_palette_div
9733bfc47b    53 _tbl_rag_color
99213ea968    23 TableResult
c785c10044    16 _TBL_DATE_HINTS
16fd3e9074    11 _TBL_FORMAT_HINTS
644343974a     7 _TBL_FORMAT_HINT_ALIASES
73bb0a02a8    15 _TblNumberPlan
0c68a538eb    12 _tbl_number_plan
40ddfce676     6 _TBL_PLAN_CACHE
578920f259    13 _tbl_column_plan
3b8a836df9    73 _tbl_smart_format
982d63ed60    25 _tbl_cell_text
16898b18c2    46 _tbl_wrap_text
9c44328bcc     3 _TBL_BREAK_AFTER
3efcbda474     1 _TBL_DIGITS
4960316b8a    28 _tbl_token_segments
dcf769b125    29 _tbl_hard_break
bfe3126e06     5 _TBL_RAG_THRESHOLD_KEYS
bfae7d75b9     4 _TBL_VALID_MODE_VALUES
841d0402b4    63 _tbl_normalize_mode
322204d5e3    64 _tbl_width_attribution
19fc0b4c28    27 _TableLayoutGeom
8ed5fa759b    30 _tbl_measure_title
4db52835e8    14 _tbl_measure_caption
9397c19094     6 _tbl_default_align
b45fd246c3    16 _tbl_is_text_col
e22baaf633    21 _tbl_is_pivoted_matrix
637894d756    20 _tbl_header_min_width
504d0bb574    12 _tbl_widest_piece
838a3903e1     5 _TBL_MINIBAR_INSET
631b4566bd     1 _TBL_MINIBAR_BAR_W
c04c03e100     1 _TBL_MINIBAR_MIN_BAR_W
e6d8cb0253     1 _TBL_MINIBAR_GAP
a600a587a9    11 _tbl_minibar_texts
75246e1b58     6 _tbl_minibar_slot_w
330f48f723    14 _tbl_minibar_scale
def5ad2e79   117 _tbl_natural_widths
553f14aa67    72 _tbl_compress_to_fit
dcee82139a    39 _tbl_row_heights
82904c6ca3   160 _tbl_normalize_theme_for_display
27f2de86dd   157 _tbl_layout
b40f963176    49 _tbl_resolve_heatmap_group
6c118166e2    42 _tbl_resolve_column_mode
d24287cc52    22 _tbl_draw_title
e554fe9e0d    12 _tbl_draw_caption
efab3fc329    63 _tbl_draw_header
209fe8e433    26 _tbl_draw_sparkline
dcabfe44e3    18 _tbl_draw_minibar
b648dfc82a   195 _tbl_draw_body
8c8c11c1e4    28 _tbl_jsonable
f48755e770    80 _tbl_studio_kwargs
3b3e2bdf1c   232 _tbl_build_cell_model
2662c12301     6 _tbl_png_bytes
a5cfa013f5     7 _PASSTHROUGH_PREFIXES
2732c20c33    29 _tbl_resolve_path
d99cd14fbf   812 make_table
0505960048     6 _ENGINE_NAMESPACE_TABLES
1bd5517af4    13 Attribute
eca77bb91a     1 Attribute#2
0a151b5154     1 make_chart
a3f55ca4a6     2 Attribute#3
0d47e44bf6     1 Attribute#4
536ef2bf52     1 make_composite
38d08d63e1    60 __all__
d4848f346e     3 __version__
```

### `prism-core/context/modules/static/tools/chart_context.md` -- 15 chunks

```
bf8678c748    12 # Altair Charts & Tables — v1 router and core
1318d3f200    19 ## 1. Where things are
d0277dc72c    38 ## 2. Pick the artifact and shape
e981dc9c18    37 ## 3. Plot-ready data contract
24565bd593    53 ## 4. `make_chart()` and results
ca2c590e0b    38 ### Kwarg placement contract
ac14978836     4 ## 5. Hard readability gates
c8567089e3    62 ### 5.1 Character budgets — check these before you write the DataFrame
d38936c6f0    36 ### 5.2 Length is not the same as fit
6b3a0b00e5    32 ### 5.3 The full gate table
c39e296166     2 ## 6. Chart types and core mapping
3035991c96    20 ### 6.1 Type catalog
91203c0025    77 ### 6.2 Canonical mapping patterns
0cbf02c9d4    84 ### 6.3 Type-specific decisions
f9ab72d11f    22 ## 7. Titles, horizons, and failure recovery
```

### `prism-core/context/modules/static/tools/charts/chart_context_annotations.md` -- 7 chunks

```
c287eabbe4     6 # Altair annotations and layers
9e91dcc6bf    34 ## 1. Pick the smallest useful annotation
714241bd92    25 ## 2. Public parameter reference
e5733f66da    38 ### Label placement is engine-owned
3961ec65da    40 ## 3. Compatibility
fa60898138    18 ## 4. Coordinates and warnings
d2c05e0f4d    34 ## 5. `layers=[...]`
```

### `prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md` -- 7 chunks

```
1d081bae8b     7 # Altair dual-axis and lead-lag charts
2b17c955b4    25 ## 1. Choose dual axis deliberately
d71365fe73    61 ## 2. Two binding forms
8aa6004291    27 ## 3. Scale gates and automatic recovery
1e3882d92e    19 ## 4. Inverted right axis and legends
7db07cbe35    20 ## 5. Right-axis annotations
e804d09d24    46 ## 6. Lead-lag
```

### `prism-core/context/modules/static/tools/charts/chart_context_composites.md` -- 6 chunks

```
d88221a442     7 # Altair composites and batch building
ddda91b3fe    19 ## 1. Pick the layout
c41490fef4    43 ## 2. `ChartSpec`
7f034e1499    76 ## 3. Pack helpers
34ef3851b1    16 ## 4. All-or-nothing failure contract
09c6046b0c    36 ## 5. `build_charts()` for two or more chart calls
```

### `prism-core/context/modules/static/tools/charts/chart_context_tables.md` -- 12 chunks

```
0a125d3d42     9 # Altair static tables (`make_table`)
9786e8da8e    42 ## 1. Data source and minimal calls
a87f5fcaa2    79 ## 2. Public kwargs
4e46ac44c4    16 ## 3. `TableResult`
83d4456b7d    30 ### Editor companion
05adca1688    45 ## 4. Colour semantics
8f334833a6    37 ### Shared heatmap scales
1b9f418b9c    20 ## 5. Headers, groups, and totals
851b533eed    22 ## 6. Sparklines and mini-bars
c8edf462e8    32 ## 7. Number formats
9699aa8c09    12 ## 8. Common shapes
f0b1c8ff47    17 ## 9. Failure contract
```

### `prism-core/context/modules/static/tools/charts/chart_context_grids.md` -- 7 chunks

```
af2fc7a799     5 # Altair facet grids
a95d8339ad    16 ## 1. Grid versus composite
47ec93c2ae    39 ## 2. Minimal call and kwargs
d374804ec0    15 ## 3. Compatible chart types
d8954c8a4c    18 ## 4. Scale synchronization
2301f9634f    26 ## 5. Time-coloured phase grids
928ef64eac    12 ## 6. Output and failures
```

### `prism-core/context/modules/static/tools/charts/chart_context_colors.md` -- 9 chunks

```
803ee0c4e0    10 # Altair chart colours and opacity
e6f897f2fe    16 ## 1. Five mapping kwargs
c7a7bdf64d    30 ## 2. Intent recipes
b6e0db5a65    15 ## 3. Named categorical palettes
fadcfb0853    37 ## 4. Explicit `color_map` and `opacity_map`
8283db2280    15 ## 5. Heatmaps
3d39c46f06    47 ## 6. Continuous scatter and phase gradients
51e2347268    23 ### 6.1 Line sequences
86240caa42    24 ## 7. Chart-specific restrictions
```

<!-- CHUNK TABLES END -->
