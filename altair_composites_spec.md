# Altair Composites & Forecast Styling — Design Spec

This file is the design artifact for the next leg of `make_chart()`: support
for layered/composite visuals (bar+dot, bar+line), forecast styling
(faded bars + dashed lines + shaded regions), per-bar/per-point highlights,
publication-grade in-plot labelling (Connector, SeriesLabel, EndCapLabel),
and two-level x-axis grouping. Six real-world equity-research exhibits are
the design targets.

It is a one-shot buildable spec: every API surface, every engine helper,
every demo cell, and the skill diff are written out in enough detail to
implement linearly without back-and-forth.

```
╔═══════════════════════════════════════════════════════════════════════════╗
║ ONE-SENTENCE GOAL                                                         ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║ Make every chart in a typical Goldman / sell-side equity-research note    ║
║ reachable as a single make_chart() call — bars-with-overlays, forecast    ║
║ styling, in-plot callouts, and per-element highlights — without giving    ║
║ the LLM raw aesthetic control. Structure stays in the API; aesthetics     ║
║ stay in the chart center.                                                 ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

## 1. The six exhibits this spec is built against

Each exhibit was extracted from a published research note. The middle
column is the patterns each exhibit needs; the right column is the
batch-1..4 features that satisfy those patterns.

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Exhibit 2  — Sentiment Indicator (bar + dots, dual-axis)                  │
│   bars (avg return, left) + dots (hit rate, right)                        │
│   in-plot series labels with axis hints                                   │
│ ► overlay (B2)  + SeriesLabel (B3)                                        │
├───────────────────────────────────────────────────────────────────────────┤
│ Exhibit 5  — EPS-beat day-after returns (line + reference line + tails)   │
│   line + dashed HLine at 101bp + "101" labelled at right edge             │
│   "20" labelled at last datum                                             │
│ ► HLine.end_label (B3) + LastValueLabel (existing)                        │
├───────────────────────────────────────────────────────────────────────────┤
│ Exhibit 7  — Q1 2026 EPS growth (the kitchen sink)                        │
│   grouped bars over (quarter, year) two-tier x-axis                       │
│   one bar (current Q) highlighted                                         │
│   value labels on each bar                                                │
│   forecast quarters faded                                                 │
│   square marker at 16 inside Q1 2026 column                               │
│   text + leader arrow → marker                                            │
│   top-area text + arrow ("Bottom-up consensus →")                         │
│   two corner labels ("Median stock", "Aggregate index")                   │
│ ► forecast_after (B1) + BarValueLabels (B1) + BarHighlight (B1) +         │
│   overlay point (B2) + Connector (B3) + SeriesLabel (B3) + x_groups (B4)  │
├───────────────────────────────────────────────────────────────────────────┤
│ Exhibit 8  — Quarter-ahead guidance (bars + ref line + 1 highlight + tail)│
│   bars + horizontal dashed line + one highlighted bar + tail label "45%"  │
│ ► BarHighlight (B1) + BarValueLabels (B1) + HLine (existing)              │
├───────────────────────────────────────────────────────────────────────────┤
│ Exhibit 13 — Net profit margin (bars + line + dashed forecast + shading)  │
│   bars (history dark / current pale-blue / forecast light grey)           │
│   line overlay (median stock) — solid through actuals, dashed forecast    │
│   in-plot text+arrow ("Bottom-up consensus")                              │
│   in-plot label ("Median stock")                                          │
│ ► forecast_after (B1) + overlay line (B2) + Connector (B3) +              │
│   SeriesLabel (B3) + x_groups (B4)                                        │
├───────────────────────────────────────────────────────────────────────────┤
│ Exhibit 29 — US real GDP growth (bars + value labels + dot annotations)   │
│   bars w/ value labels (2.9 %, 2.8 %, ..., 2.0 %)                         │
│   forecast bars (2026/27) lighter                                         │
│   dots above forecast bars (consensus comparison)                         │
│   in-plot text labels ("Consensus", "Goldman Sachs Economics forecast")   │
│ ► forecast_after (B1) + BarValueLabels (B1) + overlay point (B2) +        │
│   SeriesLabel (B3)                                                        │
└───────────────────────────────────────────────────────────────────────────┘
```

## 2. Architectural choice: hybrid extension

```
┌──────────────────────────────────────────────────────────────────────────┐
│  REJECTED:  chart-type proliferation (bar_with_dots, forecast_bar, …)    │
│             — combinatorial explosion (≥8 new types just for the 6       │
│               exhibits); new builder per cross-product                   │
│                                                                          │
│  REJECTED:  marks-as-list refactor today                                 │
│             — right end-state but a breaking change to a stable API;     │
│               loses the "chart_type tells you what you're getting"       │
│               affordance the LLM relies on; can be revisited later       │
│                                                                          │
│  CHOSEN:    hybrid — chart_type stays primary, add `overlay=[...]`       │
│             for secondary marks, add `forecast_after`/`forecast_*` for   │
│             cross-mark forecast styling, add new annotation classes      │
│             for the rest of the vocabulary                               │
│             — backward-compatible; ships in 4 isolated batches; every    │
│               batch can drag-and-drop to PRISM independently; demo       │
│               gallery never breaks                                       │
└──────────────────────────────────────────────────────────────────────────┘
```

The principle is the existing one in `dev/notes.md` and `chart_context.md`:
**the API encodes structure, the chart center encodes aesthetics.** Forecast
styling is structural (it changes which datum is which); arrow curvature is
aesthetic. Bar value labels' presence is structural; the value-label font is
aesthetic.

## 3. Full API reference

### 3.1 `make_chart()` — new kwargs

```python
make_chart(
    df=df,
    chart_type='bar',                   # unchanged
    mapping={...},                      # unchanged + optional 'x_groups' (B4)
    title=...,                          # unchanged
    subtitle=...,                       # unchanged

    # ── BATCH 1 ────────────────────────────────────────────────────────
    forecast_after=None,                # value | None — exclusive cutoff
    forecast_color=None,                # str | None — auto = palette 'forecast'
    forecast_label=None,                # str | None — auto-Band if set

    # ── BATCH 2 ────────────────────────────────────────────────────────
    overlay=None,                       # list[dict] | None — secondary marks

    # ── BATCH 4 ────────────────────────────────────────────────────────
    intent='explore',                   # + 'forecast' | 'regime' | 'anomaly'

    # ── unchanged ──────────────────────────────────────────────────────
    skin='gs_clean',
    dimensions=None,
    annotations=None,
    layers=None,
    save_as=None,
    auto_beautify=True,
    x_label=None, y_label=None,
    filename_prefix=None, filename_suffix=None,
)
```

#### 3.1.1 `forecast_after`

| Aspect          | Value                                                            |
|-----------------|------------------------------------------------------------------|
| Type            | `Any` — must be comparable to `df[mapping['x']]` values          |
| Semantics       | exclusive cutoff: rows with `x > forecast_after` are forecast    |
| Compatible with | `bar`, `bar_horizontal`, `multi_line`, `area`, `scatter`         |
| Incompatible    | `histogram`, `boxplot`, `heatmap`, `donut`, `bullet`, `waterfall`|
| Behaviour       | bar: forecast bars use `forecast_color`                          |
|                 | line: line dashes (4,4) past cutoff (engine emits two layers)    |
|                 | area: opacity drops to 0.4 past cutoff                           |
|                 | scatter: forecast points use ring (`filled=False`)               |
|                 | bar_horizontal: same as bar but cutoff applies to y category     |
| Validation      | raises `ValidationError` if cutoff is outside the data range     |
|                 | warns if no rows are after cutoff (no-op forecast)               |
|                 | rejects on incompatible chart types with actionable error        |
| Inheritance     | overlays inherit parent unless explicitly set per overlay        |

#### 3.1.2 `forecast_color`

| Aspect    | Value                                                                  |
|-----------|------------------------------------------------------------------------|
| Type      | `str | None`                                                           |
| Default   | mix base color toward white at 0.5                                     |
| Used by   | bar (forecast fill), area (forecast fill)                              |
| Not used  | line (dash style is the signal), scatter (ring is the signal)          |

#### 3.1.3 `forecast_label`

| Aspect    | Value                                                                  |
|-----------|------------------------------------------------------------------------|
| Type      | `str | None`                                                           |
| Default   | `None` (no auto-Band)                                                  |
| When set  | engine adds a `Band` annotation covering the forecast x-region with    |
|           | this label, default opacity 0.10, default color same as forecast_color |

#### 3.1.4 `overlay`

```python
overlay = [
    {
        'mark':        'point' | 'line',  # required
        'y':           str,                # required: column name
        'x':           str | None,         # default = mapping['x']
        'color':       str | None,         # default = palette slot 'overlay'
        'axis':        'left' | 'right',   # default 'left'
        # — point-specific —
        'shape':       str,                # 'circle' (default) | 'diamond' |
                                           # 'square' | 'triangle' | 'cross'
        'size':        int,                # default 100
        'filled':      bool,               # default True
        'stroke':      str,                # default None (no outline)
        # — line-specific —
        'stroke_width': float,             # default 2.0
        'stroke_dash':  list,              # default [] (solid)
        # — cross —
        'forecast_after':  any,            # inherits parent unless set
        'forecast_dash':   list,           # for line: dash pattern past cutoff,
                                           # default [4, 4]
        'label':           str | None,     # convenience: auto-add SeriesLabel
                                           # at 'inline-end' position
    },
    ...
]
```

Validation:

* primary `chart_type` must be `bar`, `bar_horizontal`, `multi_line`, `area`, or `scatter`.
* `mark='bar'` is reserved for a future batch — raises a clear "not yet" error.
* `axis='right'` is mutually exclusive with `mapping['dual_axis_series']` — pick one.
* `axis='right'` requires `mapping['y_title_right']` (caller must explicitly label the right axis).
* a maximum of 3 overlays is enforced (4-mark composites are unreadable).

### 3.2 New mapping keys

#### 3.2.1 `mapping['x_groups']`

| Aspect      | Value                                                              |
|-------------|--------------------------------------------------------------------|
| Type        | `str` — column name in `df`                                        |
| Effect      | renders a second tier of x-axis labels grouping consecutive primary|
|             | labels by the values in this column                                |
| Example     | `mapping={'x':'period','y':'val','x_groups':'year'}` →             |
|             | Q1/Q2/Q3/Q4 above, 2024/2025/2026 below                            |
| Compatible  | `bar`, `bar_horizontal` (vertical group line on left)              |
| Incompatible| every other chart type (warn + ignore)                             |
| Optional    | `x_groups_separator: bool` — vertical line between groups (default |
|             | True); `x_groups_position: 'below'|'above'` (default `'below'`)    |

### 3.3 New annotation classes

All inherit from the existing `Annotation` base; all expose `label` and
`label_color`.

#### 3.3.1 `BarValueLabels`

```python
@dataclass
class BarValueLabels(Annotation):
    format:        str = '{:.1f}'         # printf-style; e.g. '{:.0f}%', '${:.1f}B'
    position:      str = 'auto'           # 'auto' | 'outside' | 'inside-top' | 'inside-bottom'
    selection:     Any = 'all'            # 'all' | 'highlight' | 'last' | 'extremes' | list
    color:         Optional[str] = None   # default '#888888'; 'inherit' → bar color
    font_size:     int = 10
    font_weight:   str = 'bold'
    dy:            int = -4               # auto-flips for negative bars
    level:         str = 'total'          # 'total' | 'segment' (stacked only)
```

| Param      | Notes                                                                  |
|------------|------------------------------------------------------------------------|
| format     | `'{value}'` placeholder is the bar's y value passed through `.format()`|
| position   | `'auto'`: above for positive bars, below for negative. `'outside'`:    |
|            | always above (positive) or below (negative). `'inside-top'`/`-bottom'`:|
|            | inside the bar at the top or bottom edge.                              |
| selection  | `'all'`: every bar. `'highlight'`: only `BarHighlight`-marked bars.    |
|            | `'last'`: rightmost bar. `'extremes'`: min and max bars.               |
|            | list of x values: explicit selection.                                  |
| color      | `'inherit'` resolves to the bar's color at render time                 |
| level      | `'total'`: top of stacked total. `'segment'`: per-segment value at     |
|            | center (only for stacked bar with `mapping['color']`).                 |
| compat.    | `bar`, `bar_horizontal`, `waterfall`. Reject elsewhere.                |
| supersedes | the hardcoded internal value-label path in `_build_bar` lines 7920-75  |
|            | (kept intact for backward compat when no BarValueLabels passed)        |

#### 3.3.2 `BarHighlight`

```python
@dataclass
class BarHighlight(Annotation):
    x:             Any                    # value | list of values
    series:        Optional[str] = None   # color value (for grouped/stacked)
    color:         str = '#62B5E5'        # required-ish (default = secondary)
    stroke:        Optional[str] = None
    stroke_width:  float = 2.0
    fill_only:     bool = False           # if True, change stroke not fill
```

| Param  | Notes                                                                      |
|--------|----------------------------------------------------------------------------|
| x      | matched by value against `df[mapping['x']]`                                |
| series | matched against `df[mapping['color']]`. Required for grouped/stacked       |
|        | bars; optional otherwise. If absent on a grouped bar, all bars at that x   |
|        | are highlighted.                                                           |
| color  | new fill (default behavior)                                                |
| stroke | optional outline; if `fill_only=True`, only stroke is changed              |
| compat | `bar`, `bar_horizontal`. Reject elsewhere with clear error.                |
| compose| auto-coordinates with `BarValueLabels(selection='highlight')`              |

#### 3.3.3 `Connector`

```python
@dataclass
class Connector(Annotation):
    text:           str
    target_x:       Any                   # required
    target_y:       Any                   # required
    text_x:         Optional[Any] = None  # auto if None
    text_y:         Optional[Any] = None  # auto if None
    text_position:  str = 'auto'          # 'auto' | corner anchors
    arrow_color:    Optional[str] = None  # default = palette 'callout'
    text_color:     Optional[str] = None  # default = arrow_color
    font_size:      int = 10
    font_weight:    str = 'normal'
    italic:         bool = False
    align:          str = 'auto'          # 'left'|'right'|'center'|'auto'
    arrow_head:     str = 'triangle'      # 'triangle' | 'none'
    background:     str = 'halo'          # 'halo' | 'box' | 'none'
    max_width_chars: Optional[int] = None # auto-wrap at chars-per-line
    axis:           str = 'left'          # for dual-axis: which axis
    dx:             int = 0               # extra text offset
    dy:             int = 0
```

| Aspect          | Notes                                                          |
|-----------------|----------------------------------------------------------------|
| Mental model    | "this text describes that target"                              |
| Auto-position   | if `text_x`/`text_y` not given, engine picks the empty quadrant|
|                 | (`PlotText` 'auto' logic) and offsets to give arrow ~10% room  |
| Arrow geometry  | straight line from text-edge to (target_x, target_y);          |
|                 | arrowhead at target end                                        |
| Align auto      | left-align if arrow exits text on the right; right-align if    |
|                 | arrow exits on the left; center otherwise                      |
| Wrap            | if `max_width_chars` not given, defaults to 30                 |
| Distinction vs  | `Callout`: text-on-target, no arrow                            |
| existing classes| `Arrow`: arrow only, no managed text block                     |
|                 | `Connector` = managed text + arrow + auto-position             |

#### 3.3.4 `SeriesLabel`

```python
@dataclass
class SeriesLabel(Annotation):
    series:        Any                    # color value | 'left_axis' |
                                          # 'right_axis' | y column name
    label:         str
    position:      str = 'auto'           # 'auto' | 'top-left' | 'top-right' |
                                          # 'bottom-left' | 'bottom-right' |
                                          # 'inline-start' | 'inline-end' |
                                          # 'above-forecast'
    color:         Optional[str] = None   # default = series color
    font_size:     int = 11
    font_weight:   str = 'bold'
    italic:        bool = False
```

| Param    | Notes                                                                  |
|----------|------------------------------------------------------------------------|
| series   | resolves to the series's render color via the engine's palette resolver|
|          | `'left_axis'` and `'right_axis'` are special tokens for dual-axis      |
| position | `'inline-start'`: above the first datum of the series                  |
|          | `'inline-end'`: above the last datum (cf. LastValueLabel for series-   |
|          | aware tail labels — SeriesLabel is the multi-purpose corner version)   |
|          | `'above-forecast'`: above the forecast region (only valid if           |
|          | `forecast_after` is set)                                               |
|          | `'auto'`: pick the empty quadrant (PlotText 'auto' logic)              |
| color    | engine resolves at render time; falls back to series's render color    |

#### 3.3.5 `HLine.end_label` (existing class extension)

Extend `HLine` (do not add a new class):

```python
@dataclass
class HLine(Annotation):
    # ... existing fields ...
    end_label:        bool = False         # if True, add a label at the right edge
    end_label_format: str  = '{:.0f}'      # value format
    end_label_color:  Optional[str] = None # default = HLine color
    end_label_dx:     int  = 8             # pixels right of right edge
    end_label_side:   str  = 'right'       # 'right' | 'left'
```

Auto-staggers vertically with other end-labelled HLines (analogous to
the existing `_auto_stagger_hline_labels`).

### 3.4 `intent` presets

Three new values for the existing `intent=` kwarg, layered as additive
defaults on top of the locked skin (skin still wins on hard color choices;
intent only sets defaults for the new cross-mark concepts).

| Intent      | Default forecast_color | Default Band opacity | Default highlight |
|-------------|------------------------|----------------------|-------------------|
| `forecast`  | mix toward white 0.5   | 0.10                 | (unchanged)       |
| `regime`    | (unchanged)            | 0.20 (more visible)  | (unchanged)       |
| `anomaly`   | (unchanged)            | (unchanged)          | `#C00000` (red)   |

Pure default-overrides — every value can still be set explicitly. `explore`,
`publish`, `monitor` remain unchanged.

## 4. Engine work (per batch)

### 4.1 Batch 1 — forecast + bar value labels + bar highlight

```
BATCH 1 ENGINE WORK
═══════════════════════════════════════════════════════════════════════════
chart_functions.py edits

  1. Annotation hierarchy
       + class BarValueLabels(Annotation)        ~25 lines
       + class BarHighlight(Annotation)          ~20 lines
       + extend HLine with end_label fields      ~10 lines

  2. New helpers
       + _split_for_forecast(df, x_field, cutoff) → (actual_df, forecast_df)
                                                   ~15 lines
       + _apply_forecast_styling_bar(spec, ...)  ~80 lines
       + _apply_forecast_styling_line(spec, ...) ~60 lines
       + _apply_forecast_styling_area(spec, ...) ~40 lines
       + _apply_forecast_styling_scatter(...)    ~30 lines
       + _resolve_forecast_color(skin, intent, override) ~10 lines
       + _apply_bar_value_labels(spec, df, ann, mapping, skin) ~120 lines
                                                   (replaces internal lines
                                                    7920-7975 path; preserves
                                                    backward compat)
       + _apply_bar_highlight(spec, df, ann, mapping, skin) ~80 lines
       + _apply_hline_end_labels(spec, hlines, skin) ~50 lines
                                                   (incl. stagger)

  3. make_chart() changes
       + accept forecast_after / forecast_color / forecast_label kwargs
       + dispatch to _apply_forecast_styling_<chart_type> when set
       + dispatch annotations BarValueLabels / BarHighlight to their helpers
       + reject forecast_after on incompatible chart types with clear error
                                                  ~40 lines added at top of
                                                   make_chart pipeline

  4. Sole-consumer side
       + add BarValueLabels / BarHighlight to the namespace literal in
         script_exec_tools.py (PRISM-side; staging notes only — actual
         injection lands when staging copies the next chart_functions.py)
═══════════════════════════════════════════════════════════════════════════
```

### 4.2 Batch 2 — overlay (multi-mark composition)

```
BATCH 2 ENGINE WORK
═══════════════════════════════════════════════════════════════════════════
chart_functions.py edits

  1. New helpers
       + _validate_overlays(overlay, primary_chart_type, mapping)  ~50 lines
       + _build_overlay_layer(df, spec, axis, skin)                ~120 lines
                                                          (per overlay spec —
                                                           dispatches to
                                                           point or line
                                                           builder, applies
                                                           forecast styling
                                                           via Batch 1
                                                           helpers)
       + _resolve_overlay_dual_axis(base, overlays, mapping, skin) ~80 lines
                                                          (engages existing
                                                           dual-axis y-
                                                           resolver if any
                                                           overlay has
                                                           axis='right')

  2. make_chart() changes
       + accept overlay= kwarg
       + after primary chart built, run _validate_overlays
       + for each overlay: build sub-chart, layer on top via alt.layer(...)
       + if any overlay axis='right': run _resolve_overlay_dual_axis
                                                  ~30 lines added in the
                                                   primary-chart-build path

  3. mapping['dual_axis_series'] becomes a special case
       + _normalize_dual_axis_to_overlay(mapping) → mutates mapping to
         remove dual_axis_series and add an equivalent overlay spec.
         Internal only — preserves the dual-axis path behaviour while
         consolidating to the new code path.
                                                  ~40 lines

  4. SeriesLabel resolves overlay-bound series
       + when SeriesLabel.series matches an overlay's `label` or its
         resolved color, the engine auto-colors to the overlay's color
                                                  (lands in Batch 3 but
                                                   stub the resolver here)
═══════════════════════════════════════════════════════════════════════════
```

### 4.3 Batch 3 — annotation vocabulary expansion

```
BATCH 3 ENGINE WORK
═══════════════════════════════════════════════════════════════════════════
chart_functions.py edits

  1. Annotation hierarchy
       + class Connector(Annotation)             ~25 lines
       + class SeriesLabel(Annotation)           ~20 lines

  2. New helpers
       + _resolve_connector_text_position(target_x, target_y, df,
              x_field, y_field, primary_chart_type) → (text_x, text_y)
                                                  ~80 lines (reuses
                                                   PlotText quadrant scorer)
       + _build_connector(annotation, df, mapping, skin) ~150 lines
                                                  (text mark + arrow rule
                                                   + arrowhead — built as
                                                   3-mark layered chart)
       + _resolve_serieslabel_anchor(annotation, df, mapping, ...)
                                                  ~80 lines
       + _build_serieslabel(annotation, df, mapping, skin) ~60 lines

  3. Stagger + dedup
       + Connector + Connector collision detection (auto dy stagger)
                                                  ~40 lines
       + SeriesLabel + SeriesLabel collision detection
                                                  ~30 lines
       + Connector vs Callout vs PointLabel cross-class dedup
                                                  ~30 lines

  4. Existing class extensions wired
       + HLine.end_label rendering path (engine helper from Batch 1
         already in place — only the connection wires here)
                                                  ~10 lines
═══════════════════════════════════════════════════════════════════════════
```

### 4.4 Batch 4 — two-level x-axis + intent presets

```
BATCH 4 ENGINE WORK
═══════════════════════════════════════════════════════════════════════════
chart_functions.py edits

  1. Two-level x-axis
       + _resolve_x_groups(df, x_field, x_groups_field) → list of
         (group_value, [member_values]) pairs in render order
                                                  ~40 lines
       + _apply_x_groups_layer(spec, df, mapping, skin, width, height)
         = builds an extra text-mark layer with the group labels at the
           bottom (or top), plus optional vertical separator rules
                                                  ~120 lines
       + reserve bottom padding so x_groups labels render in-bounds
                                                  ~20 lines

  2. intent presets
       + _resolve_intent_defaults(intent, skin) → dict of additive overrides
         that flow into forecast_color / Band opacity / highlight color
         resolvers when those are not explicitly set
                                                  ~40 lines
       + threading into make_chart at the top of the pipeline
                                                  ~10 lines
═══════════════════════════════════════════════════════════════════════════
```

Total engine work, all four batches: **~1,650 lines added** to
`chart_functions.py`. Net delta after batch 1 supersedes the internal
auto-bar-value-label path: **~1,400 lines** of new code.

## 5. Skill diff (`chart_context.md`)

The skill is the LLM's source of truth. Every batch lands a section in
`chart_context.md` in the same change as its engine code.

```
┌──────────────────────────────────────────────────────────────────────────┐
│ NEW SECTIONS (in render order)                                           │
│                                                                          │
│  After "Annotations" section, before "Layers":                           │
│  ┌── Composition & Forecast (NEW) ──┐                                   │
│  │   Forecast styling                │  Batch 1                          │
│  │   Per-bar highlights              │  Batch 1                          │
│  │   Bar value labels                │  Batch 1                          │
│  │   Overlay marks (point / line)    │  Batch 2                          │
│  │   Two-level x-axis                │  Batch 4                          │
│  │   Intent presets                  │  Batch 4                          │
│  └────────────────────────────────────┘                                  │
│                                                                          │
│  Inside "Annotations" → "Annotation Parameter Reference" table:          │
│   + 4 new rows: BarValueLabels, BarHighlight, Connector, SeriesLabel    │
│   + extend HLine row with end_label parameters                           │
│                                                                          │
│ EDITED SECTIONS                                                          │
│                                                                          │
│  - "make_chart() Signature" code block: + forecast_after / forecast_*   │
│    + overlay kwargs                                                      │
│  - "Mapping Structure & Keys" → "All Mapping Keys" table:                │
│    + x_groups, x_groups_position, x_groups_separator rows                │
│  - "intent" line in signature: 'explore'|'publish'|'monitor' →           │
│    'explore'|'publish'|'monitor'|'forecast'|'regime'|'anomaly'           │
│  - "Auto-Injected Namespace" table:                                      │
│    + BarValueLabels, BarHighlight, Connector, SeriesLabel               │
│  - "Annotation Chart-Type Compatibility" subsection extended             │
│  - "Bar Charts" → new sub "Forecast on Bars / Lines / Area" sub-section  │
│                                                                          │
│ COMPRESSION OFFSETS (per skill-discipline rule)                          │
│                                                                          │
│  - Compress the "Composite Rules" section by ~10 lines (already verbose) │
│  - Drop the "Failure Transparency" section's third bullet (redundant)    │
│  - Compress "Prism Chart Center" intro by ~5 lines                       │
│                                                                          │
│ TARGET FILE GROWTH                                                       │
│                                                                          │
│  Current:    862 lines                                                   │
│  After B1:   ~920 lines  (+ 58)                                          │
│  After B2:   ~970 lines  (+ 50)                                          │
│  After B3:  ~1030 lines  (+ 60)                                          │
│  After B4:  ~1075 lines  (+ 45)                                          │
│  Compression offset: ~ -25 lines                                         │
│  Net target: ~1050 lines (+ 188 from current)                            │
└──────────────────────────────────────────────────────────────────────────┘
```

Sample new section (Batch 1, draft text — for fidelity check before build):

```markdown
## Composition & Forecast

### Forecast Styling

`forecast_after` is a single cutoff value that shifts the visual
treatment of every datum past it: bars fade, lines dash, area opacity
drops, scatter points ring (filled=False). It is the highest-leverage
single concept for sell-side research charts.

```python
result = make_chart(
    df=df, chart_type='bar',
    mapping={'x': 'period', 'y': 'eps_growth'},
    forecast_after='2026-Q1',          # exclusive cutoff
    forecast_color=None,               # default = base color × 0.5 toward white
    forecast_label='Bottom-up consensus estimate',  # auto-Band over forecast
    title='S&P 500 EPS growth',
)
```

Compatible with: bar, bar_horizontal, multi_line, area, scatter.
Incompatible: histogram, boxplot, heatmap, donut, bullet, waterfall —
raises ValidationError with a clear "use chart_type=… instead" message.

### Per-bar Highlights

`BarHighlight` recolors specific bars by x value (or x + series for
grouped/stacked). Use to flag the current period, the latest report,
or a specific decision point.

[etc.]
```

## 6. Demo gallery additions

Total new demos: **9 files, ~76 cells**. Each demo is interactive (CLI
menu when run without args) and `--all` (non-interactive). All output
goes to `dev/demos/output/<demo_number>_<slug>/`.

```
27_forecast_styling.py        10 cells
28_bar_value_labels.py        12 cells
29_bar_highlight.py            8 cells
30_overlay_marks.py           10 cells
31_connectors.py               8 cells
32_endcap_serieslabel.py       8 cells
33_x_groups.py                 6 cells
34_real_world_recipes.py       6 cells   ← the 6 exhibits, byte-for-byte
35_stress_collisions.py        8 cells
─────────────────────────────────────
                              76 cells
```

### 6.1 `27_forecast_styling.py` (10 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | bar single-series + forecast_after                                        |
| A2   | bar single-series + forecast_after + forecast_label (auto-Band)           |
| A3   | bar single-series + forecast_after + custom forecast_color                |
| A4   | bar multi-series stacked + forecast_after                                 |
| A5   | bar multi-series grouped (`stack=False`) + forecast_after                 |
| A6   | bar_horizontal + forecast_after                                           |
| B1   | multi_line single-series + forecast_after                                 |
| B2   | multi_line multi-series + forecast_after (each series dashes past cutoff) |
| B3   | area single + forecast_after                                              |
| B4   | area stacked + forecast_after                                             |

### 6.2 `28_bar_value_labels.py` (12 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | BarValueLabels alone, default `'{:.1f}'`                                  |
| A2   | format `'{:.0f}%'`                                                        |
| A3   | format `'${:.1f}B'`                                                       |
| A4   | position='inside-top'                                                     |
| A5   | color='inherit' (matches bar color)                                       |
| B1   | selection='last'                                                          |
| B2   | selection='extremes' (min and max)                                        |
| B3   | selection=['2026-Q1', '2026-Q2'] (explicit list)                          |
| C1   | on bar_horizontal                                                         |
| C2   | on stacked bar (level='total', default)                                   |
| C3   | on stacked bar (level='segment')                                          |
| D1   | on grouped bar (per-facet labels)                                         |

### 6.3 `29_bar_highlight.py` (8 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | single bar (x=value)                                                      |
| A2   | multiple bars (x=list)                                                    |
| A3   | stroke-only highlight (`fill_only=True`, `stroke='#C00000'`)              |
| A4   | with attached label                                                       |
| B1   | on horizontal bar                                                         |
| B2   | on stacked bar (specific x + series)                                      |
| B3   | on grouped bar (specific x + series)                                      |
| C1   | + BarValueLabels(selection='highlight') — highlighted bar gets the label  |

### 6.4 `30_overlay_marks.py` (10 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | bar + point overlay, same axis                                            |
| A2   | bar + point overlay, dual axis (Ex 2 base pattern)                        |
| A3   | bar + point overlay, shape='diamond'                                      |
| A4   | bar + 2 point overlays (different y columns)                              |
| B1   | bar + line overlay, same axis                                             |
| B2   | bar + line overlay, dual axis (Ex 13 base)                                |
| B3   | bar + line overlay with stroke_dash                                       |
| C1   | bar + point + line (3 marks, all on left axis)                            |
| C2   | multi_line + point overlay (point overlay highlights specific points)     |
| D1   | bar + line overlay + forecast_after — both fade/dash past cutoff          |

### 6.5 `31_connectors.py` (8 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | Connector text auto-positioned, target = bar value                        |
| A2   | Connector text explicit (text_x/text_y given)                             |
| A3   | Connector with text wrapping (long text)                                  |
| A4   | Connector pointing to HLine                                               |
| B1   | two Connectors no-collision (auto stagger)                                |
| B2   | Connector + BarHighlight — Connector points to highlighted bar            |
| B3   | Connector pointing to scatter point                                       |
| C1   | Connector with halo background vs box background (2-pack comparison)     |

### 6.6 `32_endcap_serieslabel.py` (8 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | HLine end_label=True (Ex 5 reference line at right edge)                  |
| A2   | HLine end_label + custom format ('{:.0f}bp')                              |
| A3   | HLine end_label + LastValueLabel on series (no collision)                 |
| A4   | multiple HLines with end_labels (auto-stagger)                            |
| B1   | SeriesLabel on multi_line single-series                                   |
| B2   | SeriesLabel on multi_line multi-series                                    |
| B3   | SeriesLabel on dual-axis ('left_axis' + 'right_axis' — Ex 2 pattern)      |
| C1   | SeriesLabel position='above-forecast'                                     |

### 6.7 `33_x_groups.py` (6 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | grouped bar with x_groups (Ex 7 layout)                                   |
| A2   | stacked bar with x_groups                                                 |
| A3   | single-series bar with x_groups                                           |
| B1   | x_groups + forecast_after (Ex 7 / Ex 13 pattern)                          |
| C1   | x_groups + multi_line (date by quarter, year groups)                      |
| D1   | x_groups + separator lines (vertical rule between year groups)            |

### 6.8 `34_real_world_recipes.py` (6 cells)

The six exhibits, reproduced byte-for-byte. Each demo cell lands a PNG
that should be visually indistinguishable from the source exhibit.

| Cell | Recipe                                                                    |
|------|---------------------------------------------------------------------------|
| A    | **Ex 2** — Sentiment Indicator (bars + dots, dual-axis)                   |
| B    | **Ex 5** — EPS-beat day-after returns (line + ref + tail)                 |
| C    | **Ex 7** — Q1 2026 EPS growth (the kitchen sink)                          |
| D    | **Ex 8** — Quarter-ahead guidance (bars + ref + highlight + tail)         |
| E    | **Ex 13** — Net profit margin (bars + line + forecast)                    |
| F    | **Ex 29** — US real GDP growth (bars + dots + value labels + forecast)    |

### 6.9 `35_stress_collisions.py` (8 cells)

| Cell | Coverage                                                                  |
|------|---------------------------------------------------------------------------|
| A1   | forecast + BarValueLabels + BarHighlight + Connector + EndCapLabel +      |
|      | SeriesLabel — all six new primitives on one chart                         |
| A2   | same as A1 but on horizontal bar                                          |
| B1   | 2 overlays + forecast_after + 5 annotations                               |
| C1   | composite (2-pack horizontal) with new features on both panels            |
| D1   | Connector + Callout collision (auto-stagger)                              |
| D2   | multiple BarHighlights + multiple Connectors                              |
| E1   | forecast + intent='forecast' preset                                       |
| F1   | edge: empty forecast region (cutoff after last x) — should warn, not fail |

## 7. Synthetic data additions

New generators to land in `dev/synthetic_data/composites.py` (new module):

```python
# composites.py

def quarterly_eps_growth(...) -> pd.DataFrame
    """Q1 2024 .. Q4 2027 with columns: period, year, quarter, aggregate,
    median, ex_amzn_googl, is_forecast. Used by Ex 7, demos 27/28/33/34."""

def quarterly_profit_margin(...) -> pd.DataFrame
    """Q1 2022 .. Q4 2027 with columns: period, year, quarter,
    aggregate_margin, median_margin, is_forecast. Used by Ex 13,
    demos 27/30/33/34."""

def annual_gdp_growth(...) -> pd.DataFrame
    """2023 .. 2027 with columns: year, gdp_growth, consensus, is_forecast.
    Used by Ex 29, demos 27/30/34."""

def sentiment_indicator(...) -> pd.DataFrame
    """11 sentiment buckets (<-2.0 .. >2.0) with columns: bucket,
    avg_return, hit_rate. Used by Ex 2, demos 30/32/34."""

def quarterly_guidance(...) -> pd.DataFrame
    """2017-Q1 .. 2026-Q2 with columns: period, year, quarter, pct_above,
    is_current. Used by Ex 8, demos 29/34."""

def eps_beat_returns(...) -> pd.DataFrame
    """2006 .. 2026 quarterly with columns: date, median_excess_return_bp.
    Used by Ex 5, demos 32/34."""
```

Each generator returns a deterministic DataFrame (seed-controlled) so
re-renders are stable. Index style: integer 0..N-1, with `period` /
`year` / `quarter` columns. Datetime where natural.

## 8. Open design questions (decisions made)

| Q | Decision |
|---|----------|
| Forecast as kwarg vs annotation? | Kwarg. Cross-mark coupling (bar fill + line dash + Band) demands a single source of truth that the annotation model can't express. |
| Overlay axis: explicit vs auto? | Explicit; default `'left'`. Auto-axis introduces the existing dual-axis footgun. |
| `mapping['dual_axis_series']` vs `overlay`? | Both are kept. `dual_axis_series` is internally normalised into an `overlay` spec. Skill marks `dual_axis_series` as legacy in Batch 2; full deprecation later. |
| `bar` mark in `overlay`? | Future. `mark='bar'` raises NotImplementedError until needed. |
| `BarValueLabels` default-on or default-off? | The existing implicit auto-labels for ≤15 single-series bars stay on (back-compat). `BarValueLabels` overrides. To suppress the implicit path, pass `BarValueLabels(suppress_auto=True)`. |
| `Connector` curved arrows? | No. Straight lines only. Curvature is aesthetic, belongs in chart center. |
| `SeriesLabel` positioning vocabulary? | `'auto'` is the default; engine picks empty quadrant. Other values are hints. Document as "engine-anchored". |
| `intent` presets affect skin? | No. Intent is purely an additive default-resolver for the new cross-mark concepts. Skin still wins. |
| `x_groups` implementation? | Render as a hidden text-mark layer beneath the x-axis, with optional separator rules. Independent of facet structure. |
| `forecast_after` cutoff convention? | Exclusive: rows with `x > cutoff` are forecast. The cutoff datum itself is "actual". |
| HLine end_label vs new EndCapLabel class? | Extend HLine — the value being labelled is intrinsic to the rule. |
| Do we ship intent presets in Batch 4 or Batch 1? | Batch 4. They're cosmetic polish; nothing in batches 1-3 requires them. |

## 9. Out of scope

* `make_echart` / `compile_dashboard` parity — these are dashboard
  primitives; the altair side stays the single-PNG path.
* Curved leader arrows, S-shaped connectors — chart-center territory.
* Per-segment colors for waterfall (already an existing feature).
* Stacked-bar segment annotations beyond `BarValueLabels(level='segment')`.
* In-plot title relocation — already covered by chart center.
* Sankey, treemap, candlestick — separate undertaking, plotly territory.
* Animation / transitions — out of scope; PRISM is static-PNG-first.
* Regression diagnostics overlay (R², p-value, etc.) — covered by
  existing `Trendline` annotation; no expansion this round.

## 10. Sequencing for the build

The user has indicated a single one-shot build over all 4 batches. The
linear path I'll take:

```
Step 1   New annotation classes   (~5 dataclasses, top of chart_functions.py)
Step 2   Synthetic data generators (composites.py — 6 functions)
Step 3   Engine helpers — Batch 1 (forecast + bar value labels + bar highlight)
Step 4   Engine helpers — Batch 2 (overlay + dual-axis normalisation)
Step 5   Engine helpers — Batch 3 (Connector, SeriesLabel, HLine.end_label)
Step 6   Engine helpers — Batch 4 (x_groups + intent presets)
Step 7   make_chart() pipeline wiring (single change at the top of the function)
Step 8   Skill diff — chart_context.md
Step 9   Demo gallery — 27 through 35 (76 cells)
Step 10  Run dev/demos/run_all.py --all and vision-inspect
Step 11  Iterate on demo failures
Step 12  Update dev/notes.md (track 3 progress)
Step 13  cli_altair.py menu refresh (add new demos to "Demos > List")
```

Estimated incremental contributions:

| Surface                       | Lines added | Lines edited | Files touched |
|-------------------------------|-------------|--------------|---------------|
| chart_functions.py (engine)   | ~1,650      | ~50          | 1             |
| chart_context.md (skill)      | ~213        | ~25          | 1             |
| dev/synthetic_data/composites.py (new) | ~250 | 0           | 1             |
| dev/demos/27..35*.py (new)    | ~1,800      | 0            | 9             |
| dev/notes.md                  | ~30         | ~10          | 1             |
| cli_altair.py                 | ~10         | ~5           | 1             |
| **TOTAL**                     | **~3,950**  | **~90**      | **14**        |

## 11. Validation gates before staging this build

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Pre-flight                                                               │
│   1. Whole gallery passes today (.venv/bin/python dev/demos/run_all.py   │
│      --all). 26 existing demos × n cells each → confirm baseline.        │
│   2. cli_altair.py works end-to-end (menu + non-interactive).            │
│                                                                          │
│ During build (per batch)                                                 │
│   3. After each batch's engine work: run the relevant demo file alone    │
│      (e.g. .venv/bin/python dev/demos/27_forecast_styling.py).           │
│   4. Vision-inspect every PNG produced; iterate on shape gaps.           │
│                                                                          │
│ Post-build                                                               │
│   5. Run dev/demos/run_all.py --all (now 35 demos × ~76 new cells).      │
│   6. Vision-inspect any demo cell that's new. Output gallery via         │
│      dev/demos/build_gallery.py and open in browser.                     │
│   7. Compare 34_real_world_recipes/{A..F}.png against the source         │
│      exhibits side by side. Fix any structural deviation.                │
│   8. Update dev/notes.md with batch landings.                            │
│                                                                          │
│ Skill discipline (per skill-discipline.mdc)                              │
│   9. Re-audit chart_context.md against the filter test. Compress         │
│      anywhere new content overlapped with existing material.             │
│  10. Verify total line count target (~1,050). Trim if over.              │
└──────────────────────────────────────────────────────────────────────────┘
```

## 12. Drag-and-drop sequencing (PRISM)

The output of this work is a new `chart_functions.py` with byte-identical
PRISM compatibility. The drag-and-drop unit:

```
GS/viz/altair/altair-payload/chart_functions.py    →   ai_development/mcp/utils/
GS/viz/altair/altair-payload/chart_context.md      →   context/modules/static/
```

PRISM-side namespace (in `script_exec_tools.py`) needs four new symbols
in the namespace literal, mirroring how `Segment`, `PointHighlight`,
`Callout`, `LastValueLabel`, `Trendline` were added on 2026-04-26:

```python
"BarValueLabels":    BarValueLabels,
"BarHighlight":      BarHighlight,
"Connector":         Connector,
"SeriesLabel":       SeriesLabel,
```

And the import block at the top of `script_exec_tools.py` needs the same
four added. This injection is PRISM-side only (lives outside the
drag-and-drop payload) and does not regress on subsequent drag-and-drops
of `chart_functions.py` alone.

Until that PRISM-side wiring lands, end-to-end PRISM use of the new
classes will fail with `NameError`. The local stub mirror plus demo
gallery confirms behaviour ahead of the live PRISM session.

---

End of spec.
