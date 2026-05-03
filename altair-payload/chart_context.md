# Altair Charts (`make_chart`)

- **Module:** `chart_context`
- **Audience:** PRISM (all interfaces, all workflows), developers
- **Tier:** 2 (on-demand)
- **Scope:** All static-PNG chart authoring in PRISM (chat / email / report flows). Composites (n-pack helpers) ship in this same module. Interactive HTML dashboards use the separate `dashboards` module (echarts).

`make_chart()` and the composite/annotation/profile helpers are auto-injected
into `execute_analysis_script()`. Raw matplotlib is blocked. Do NOT import
chart functions.

This hub covers the always-needed surface — namespace, signature, return shape, mandatory QC + cleanup, the universal authoring rules, dimensions, pre-flight, and time-horizon guidance. Per-primitive depth (chart-type specs, mapping reference, annotation classes, dual-axis mechanics, composite layouts, the Chart Center editor) lives in spoke files fetched on demand — see §3.

---

## Catalog index

Every named primitive PRISM picks between, with a pointer to the hub section OR spoke file that carries the per-primitive spec.

| Primitive | Names | Where |
|---|---|---|
| Chart types (12) | `multi_line`, `scatter`, `scatter_multi`, `bar`, `bar_horizontal`, `heatmap`, `histogram`, `boxplot`, `area`, `donut`, `bullet`, `waterfall` | `chart_context/chart_types.md` |
| Mapping keys (~20) | `x`, `y`, `color`, `y_title`, `y_title_right`, `x_title`, `x_sort`, `y_sort`, `x_type`, `dual_axis_series`, `invert_right_axis`, `trendline`, `trendlines`, `stack`, `strokeDash`, `strokeDashScale`, `strokeDashLegend`, `value`, `theta`, `x_low`, `x_high`, `color_by`, `label`, `type` | `chart_context/mapping.md` |
| Annotation classes (11) | `VLine`, `HLine`, `Segment`, `Band`, `Arrow`, `PointLabel`, `PointHighlight`, `Callout`, `LastValueLabel`, `Trendline`, `PlotText` | `chart_context/annotations.md` |
| Composite functions (5) | `make_2pack_horizontal`, `make_2pack_vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid` | `chart_context/composites.md` |
| Dimension presets (7) | `wide`, `square`, `tall`, `compact`, `presentation`, `thumbnail`, `teams` | §6 |
| Skin (1, only published) | `gs_clean` | §1 (signature) |
| Intent values (3) | `'explore'`, `'publish'`, `'monitor'` | §1 (signature) |
| Layer types (3) | `regression`, `rule`, `point` | `chart_context/annotations.md` §5 |
| Chart Center themes (5) | `gs_clean`, `bridgewater`, `minimal`, `dark`, `print` | `chart_context/chart_center.md` |
| Chart Center palettes (14) | `gs_primary`, `bridgewater`, `mono_blue`, `mono_grey`, `vivid`, `tableau`, `okabe_ito`, `viridis`, `blues`, `reds`, `greens`, `gs_diverging`, `redblue`, `spectral` | `chart_context/chart_center.md` |

Catalog only — pick what you need from this table, then fetch the relevant spoke per the menu in §3.

---

## 1. Auto-injected namespace

| Function / Class | Purpose |
|------------------|---------|
| `make_chart()` | Build a single chart |
| `profile_df()` | Analyze a DataFrame pre-charting |
| `ChartResult` / `ChartSpec` | `make_chart()` return type / composite sub-chart spec |
| `check_charts_quality()` | MANDATORY post-chart QC gate |
| `make_2pack_horizontal/vertical()`, `make_3pack_triangle()`, `make_4pack_grid()`, `make_6pack_grid()` | Composite layouts (2-h, 2-v, 1+2, 2x2, 3x2) |
| `VLine`, `HLine`, `Segment`, `Band`, `Arrow` | Line/region annotations |
| `PointLabel`, `PointHighlight`, `Callout` | Point/text annotations |
| `LastValueLabel`, `Trendline`, `PlotText` | Series-aware / in-plot text annotations |

`s3_manager`, `session_path`, and `user_id` are auto-injected at call
time -- never pass them explicitly.

### `make_chart()` signature

```python
result = make_chart(
    df=df, chart_type='multi_line', mapping={...},
    title='Title',                # Required for production charts
    subtitle='Subtitle',          # Optional (NEVER for source attribution)
    skin='gs_clean',              # Only published skin
    intent='explore',             # 'explore' | 'publish' | 'monitor'
    dimensions='wide',            # See §6 Dimensions
    annotations=[...], layers=[...],  # Optional; layers = regression / rule / point
    save_as='charts/name.png',    # Optional fixed path (overwrites, no timestamp)
    auto_beautify=True,           # Date format, label angle, y-domain (default True)
    x_label=None, y_label=None,   # Aliases for mapping['x_title' / 'y_title']
    filename_prefix=None, filename_suffix=None,  # Optional slug pre/suffix
)
```

`SESSION_PATH` and `s3_manager` are wired by the sandbox. `output_dir` is
local-mode only. `interactive=True` is reserved.

### `ChartResult` (dataclass, NOT dict)

Access via dot notation only (`result.png_path`). `result['png_path']` raises `TypeError`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `png_path` / `download_url` | str | PNG S3 path / presigned URL |
| `editor_html_path` / `editor_download_url` | str | Chart Center HTML S3 path / presigned URL |
| `editor_chart_id` | str | Chart Center chart ID (sha1 of spec) |
| `vegalite_json` | dict | Final Vega-Lite spec |
| `chart_type` / `skin` | str | Echoed chart type / skin |
| `success` / `error_message` | bool / str-None | Render succeeded? + error details |
| `warnings` | list | Non-fatal warnings (auto-melt, downsample, beautify failures, ...) |

`CompositeResult` (returned by all `make_Npack_*` helpers) carries the same
PNG/editor fields plus `layout`, `n_charts`, and `chart_errors` (per-sub-chart
failures with `df_shape`, `error_type`, `error_message`).

---

## 2. Quality gate (MANDATORY)

Every chart must pass through `check_charts_quality()`. Fail-open: if
Gemini is unavailable, all charts auto-pass. Pass composite results as
single PNGs.

```python
results = [r1, r2]  # list of ChartResults
qc_results = check_charts_quality(results)
for r, qc in zip(results, qc_results):
    if not qc['passed']:
        print(f"FAIL: {r.png_path} -- {qc['reason']}")
        s3_manager.delete(r.png_path)
        if r.editor_html_path:
            s3_manager.delete(r.editor_html_path)
    elif r.success:
        print(f"PASS PNG: {r.download_url}\n  Chart Center: {r.editor_download_url}")
```

### Failed chart cleanup

Session folders must contain only QC-passed charts (failed PNGs mislead
reports, dashboards, session reloads). On QC fail, `s3_manager.delete()`
BOTH the PNG and its `editor_html_path` companion, then fix or remove the
offending `make_chart()`. Saying Prism could not generate a chart is
acceptable; showing a failed one is not.

---

## 3. On-demand spec fetching

This hub covers the always-needed contract + the catalog index. For per-primitive depth (chart-type rules, mapping keys, annotation parameters, dual-axis mechanics, composite layouts, the Chart Center editor), fetch the relevant spoke.

**Do NOT call `get_context()` again — it is one-shot per user message.** Mid-session reads use `list_ai_repo` with `mode="full"`. Each spoke is independent; mix and match.

| Spoke | Contents | Verbatim tool call (copy-paste) |
|-------|----------|--------------------------------|
| `chart_context/chart_types.md` | 12 chart types, required mapping per type, bullet + waterfall, bar-chart family (stacked vs grouped, annotation compatibility, datetime x-axes), Haver business-daily storage + mixed-frequency merges | `list_ai_repo(file_paths=["context/modules/static/chart_context/chart_types.md"], mode="full")` |
| `chart_context/mapping.md` | Basic patterns (long, wide, profile, scatter+trendlines), full mapping-key reference, `strokeDash` per-series styles | `list_ai_repo(file_paths=["context/modules/static/chart_context/mapping.md"], mode="full")` |
| `chart_context/annotations.md` | 11 annotation classes (parameter reference), the "is this annotation worth it?" filter, anti-patterns table, chart-type compatibility, `layers=[...]` overlays | `list_ai_repo(file_paths=["context/modules/static/chart_context/annotations.md"], mode="full")` |
| `chart_context/dual_axis.md` | Declaring dual-axis (long-format requirement), series-name discipline (LEFT/RIGHT constants), inverted right axis, annotations on the right axis, when to switch to a stacked composite instead | `list_ai_repo(file_paths=["context/modules/static/chart_context/dual_axis.md"], mode="full")` |
| `chart_context/composites.md` | `ChartSpec` + 5 layout helpers (`make_2pack_horizontal/vertical`, `make_3pack_triangle`, `make_4pack_grid`, `make_6pack_grid`); composite rules; common patterns | `list_ai_repo(file_paths=["context/modules/static/chart_context/composites.md"], mode="full")` |
| `chart_context/chart_center.md` | ~140 editor knobs + 5 themes + 14 palettes + 12 dimension presets + spec sheets; styling-delegation discipline; mandatory link-delivery contract; session folder layout; non-fatal generation; known limitations | `list_ai_repo(file_paths=["context/modules/static/chart_context/chart_center.md"], mode="full")` |

**Common combos** (one call, multiple file_paths):

| Build shape | Single call to copy |
|-------------|---------------------|
| Single chart, basic | `list_ai_repo(file_paths=["context/modules/static/chart_context/chart_types.md", "context/modules/static/chart_context/mapping.md"], mode="full")` |
| Single chart with annotations | `list_ai_repo(file_paths=["context/modules/static/chart_context/chart_types.md", "context/modules/static/chart_context/mapping.md", "context/modules/static/chart_context/annotations.md"], mode="full")` |
| Dual-axis chart | `list_ai_repo(file_paths=["context/modules/static/chart_context/dual_axis.md", "context/modules/static/chart_context/mapping.md"], mode="full")` |
| Composite (n-pack) | `list_ai_repo(file_paths=["context/modules/static/chart_context/composites.md", "context/modules/static/chart_context/chart_types.md"], mode="full")` |
| User asks about styling / "make it bigger" | `list_ai_repo(file_paths=["context/modules/static/chart_context/chart_center.md"], mode="full")` |

Each spoke is well under the 20 KB warning threshold. Fetch only the
spokes you need; avoid fetching all six preemptively — that defeats the
hub-spoke purpose. The Catalog index above is enough to PICK a primitive;
fetch a spoke when you need its mapping rules / required keys / parameter
reference / mechanics.

---

## 4. Design defaults: compose + annotate

Two LLM-default behaviours that distinguish a published chart from
a data dump. Apply both unless the user has explicitly asked otherwise.

### 4.1 Default to a composite when there's more than one story

If the data tells more than one related story (regional split,
level vs change, before/after, mixed chart types), reach for
`make_2pack_horizontal` / `make_2pack_vertical` /
`make_3pack_triangle` / `make_4pack_grid` / `make_6pack_grid`
BEFORE producing multiple standalone PNGs. Single PNG, single QC
call, per-panel scales / palettes independent. Up to N-1 sub-charts
can fail and survivors still render.

| Shape | Layout |
|---|---|
| 2-3 related angles | `make_2pack_horizontal` / `_vertical` |
| 4 panels (regional / sector grid) | `make_4pack_grid` |
| 1 headline + 2 supporting | `make_3pack_triangle` |
| 6-panel dashboard | `make_6pack_grid` |
| 9+ series | aggregate / group, or `heatmap` |

Single charts only for genuinely unrelated topics or when the user
explicitly asked for one. Composite design depth (`ChartSpec`,
per-panel mapping rules, common patterns): fetch
`chart_context/composites.md`.

### 4.2 Annotations make charts argue

A published chart almost always benefits from at least one
annotation -- a line at a threshold, a band over a regime, a callout
on the latest print, direct labels via `LastValueLabel`. Default-
include the annotation that makes the chart's point legible at-a-
glance.

| Intent | Reach for |
|---|---|
| Threshold (Fed 2%, recession 0%, PMI 50) | `HLine` |
| Regime / shaded period | `Band` |
| Point at latest / max / min / event | `Callout` |
| Direct-label series, drop the legend | `LastValueLabel` |
| Event date | `VLine` |
| Forecast / regime-change segment | `Segment` |
| Best-fit on scatter | `Trendline` (or `mapping['trendline']=True`) |
| Corner caption | `PlotText` |

Annotation specs + per-class params + the "is this annotation worth
it?" filter + chart-type compatibility: fetch
`chart_context/annotations.md`.

A chart with no annotation is appropriate when the user asked for a
clean reference plot OR the purpose is exploratory (looking for
patterns rather than arguing for one). Otherwise, annotate.

---

## 5. Authoring rules

### 5.1 Max lines per chart (soft guideline)

<= 4 lines per `multi_line` chart; 5+ lines cause clutter. For >4-series
data, use a composite (`composites.md` §1).

### 5.2 Y-axis labels: plain English, max 16 chars

Always set `y_title` if the column name is coded or exceeds 16 chars
(`JXCHF@USECON` -> `Core CPI (YoY %)`; `Population (Millions)` (21 chars)
-> `Pop. (Millions)`).

### 5.3 Date column requirements

X column must be named `'date'` for time series and must be a column (not
just the index): `df = df.rename(columns={'datetime': 'date'}).reset_index()`.

### 5.4 Multi-line long-format pattern (with rename discipline)

For multi-series with `color`: melt to long format AFTER renaming columns
(`reset_index()` uses the original index name; rename immediately after
reset, before any melt). Or use the auto-melt shortcut.

```python
df = df.reset_index()
df.columns = ['date', 'Series A', 'Series B']  # Rename FIRST
df_long = df.melt(id_vars='date', var_name='series', value_name='value')
mapping = {'x': 'date', 'y': 'value', 'color': 'series'}
# OR auto-melt shortcut (no `color` key):
mapping = {'x': 'date', 'y': ['Series A', 'Series B']}
```

### 5.5 No source attribution in title/subtitle

Title/subtitle make the argument; source tracking lives in Prism metadata.
Good: `title='Inflation Has Peaked'`, `subtitle='Core CPI decelerating 6
months'`. Bad: `title='US CPI Data'`, `subtitle='Source: Haver'`.

### 5.6 Data cleaning before charting

```python
df['value'] = pd.to_numeric(df['value'], errors='coerce')
df = df.dropna(subset=['date', 'value'])
assert len(df) > 0, "DataFrame is empty"
```

Max 12 color categories, 16 facet categories. Time series above 5,000 rows
auto-downsample to ~2,000 (warning in `result.warnings`).

### 5.7 Never plot placeholder/zero-fill data

If data is unavailable, skip the panel (smaller composite) or add a text
annotation. Never use `np.zeros()` as fallback -- it produces misleading
flat lines at 0.

---

## 6. profile_df: pre-charting DataFrame analysis

Use before `make_chart()` to verify columns, dtypes, missingness,
cardinality, and date coverage. Returns a `DataProfile` (dataclass) with
fields: `columns`, `dtypes`, `shape`, `temporal_columns`, `numeric_columns`,
`categorical_columns`, `cardinality`, `missing_pct`, `date_range`,
`numeric_stats`. Call `profile.to_dict()` to serialise.

```python
profile = profile_df(df)
print(profile.shape)              # (rows, cols)
print(profile.cardinality)        # {'series': 4, 'date': 252, ...}
print(profile.missing_pct)        # {'value': 0.0, 'series': 0.0}
print(profile.date_range)         # {'date': {'min': '...', 'max': '...'}}
print(profile.numeric_stats)      # {'value': {'mean':..., 'std':..., ...}}
```

---

## 7. Dimensions

| Preset | Size | Best For |
|--------|------|----------|
| `wide` | 700x350 | Time series (default) |
| `square` | 450x450 | Scatter, heatmaps |
| `tall` | 400x550 | Vertical bars, rankings |
| `compact` | 400x300 | Dashboard components |
| `presentation` | 900x500 | Slides |
| `thumbnail` | 300x200 | Previews |
| `teams` | 420x210 | Required for Teams medium |

When request is from Teams, always use `dimensions='teams'` (or
`dimension_preset='teams'` for composites). Typography auto-scales for
`teams`, `thumbnail`, and `compact` presets.

---

## 8. Chart time horizon guidelines

### Default lookback

| Frequency | Default | Horizon Class | Use Case |
|-----------|---------|---------------|----------|
| Quarterly / Monthly | 10 years | Medium | Cyclical patterns, regime comparisons -- default |
| Weekly | 5 years | -- | Trend + cycle (also YoY series, to show cycle) |
| Daily | 2-3 years | Short | Recent acceleration, event reactions -- regime without noise |
| Intraday | 5 trading days | Very Short | Event reaction window, data releases |

For structural shifts ("not seen since X"), use Long (20-50y) full history
regardless of frequency.

### Override rules

- "Highest since 2008" -> chart MUST include 2008. Pre-pandemic -> start >= 2015. Percentile claims require a full percentile window.
- Don't show 1-2y of monthly data (hides cycle); don't show 30+y of daily (noise); don't use different ranges for charts meant to be compared.

---

## 9. Failure transparency

Never silently substitute a different layout or rationalize a substitution.
If a requested chart shape isn't feasible, tell the user and offer
alternatives. Max 2 retries per chart concept; after 2 failures, deliver
the best version with a note or ask the user about alternatives.
