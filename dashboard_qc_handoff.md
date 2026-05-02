# Dashboard QC handoff -- adversarial vision + validation hardening

A multi-session methodology for hardening the echarts dashboard
engine + rendering layer + validators by deliberately building
poor, malformed, and edge-case dashboards, vision-inspecting the
output, and iterating on the engine -- with **minimal-to-zero**
edits to `dashboards.md`.

This doc is the handoff for the FIRST execution. It also encodes
the philosophy + workflow for every subsequent execution.

---

## 0. Why this exists (motivation)

The previous session shipped `build_showcase` -- one canonical
8-tab MECE dashboard covering every primitive in `dashboards.md`'s
catalog index. When opened in a real browser, the showcase
**revealed multiple aesthetic regressions** that no prior QC step
caught:

```
ISSUE OBSERVED                          WHERE                       SEVERITY
─────────────────────────────────────── ─────────────────────────── ────────
Multi-axis 40-50% horiz padding         showcase tab 1 cross-asset  HIGH
  before plot starts (4-axis tile)        overlay (mapping.axes)
Pie legend pills collide with bottom    showcase tab 3 allocation   HIGH
  edge slices                             (donut + pie)
Long single-column charts wasted px     hypothetical / rule-only    MEDIUM
Too many lines in multi_line illegible  hypothetical                MEDIUM-LOW
```

These are exactly the regressions Gemini-vision-QC was supposed
to catch in production (see `prism/vision-qc.md`). That path is
being deprecated -- vision QC is slow, can only DELETE failing
charts, and the LLM cannot recover from the deletion. The
replacement is **rich engine-side validation + good defaults +
tested aesthetic surface guaranteed by the API.**

But to GET to that state, we need a structured staging-side QC
pass that:

1. exercises the engine adversarially (adversarial synthetic data,
   adversarial manifests)
2. captures Playwright vision snapshots
3. inspects the diagnostic stream
4. documents findings
5. iterates on the engine + rendering layer (NOT the skill /
   `dashboards.md`)

Cursor + Playwright + Cursor-vision-on-PNG is the right tool for
this work. PRISM never sees any of it -- it's all staging.

---

## 1. Two tracks, one workflow

```
┌────────────────────────────────────────────────────────────────────────┐
│ TRACK A -- AESTHETIC QC (vision-driven)                                │
│                                                                        │
│  Build adversarial dashboards (extreme data shapes, layouts, mixes)    │
│      └─► render via compile_dashboard                                  │
│           └─► capture Playwright PNG (full + per-tab + per-widget)     │
│                └─► Cursor vision-inspects each PNG                     │
│                     └─► flag aesthetic regressions in findings doc     │
│                          └─► ENGINE / RENDERING fix                    │
│                               (echart_studio.py / rendering.py)        │
│                                └─► re-render, re-vision, compare delta │
└────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────┐
│ TRACK B -- VALIDATION QC (input-driven)                                │
│                                                                        │
│  Build adversarial manifests (poor / missing / malformed)              │
│      └─► run validate_manifest + chart_data_diagnostics +              │
│           compile_dashboard                                            │
│           └─► capture every diagnostic + log line + raised exception   │
│                └─► rate each diagnostic on FOUR axes:                  │
│                     - informative? (does it explain the issue)         │
│                     - actionable?  (does it tell PRISM what to fix)    │
│                     - correct?     (false-positive / false-negative)   │
│                     - comprehensive? (did it surface ALL bugs in one   │
│                                        pass, or stop at the first?)   │
│                          └─► VALIDATOR / DIAGNOSTIC-CODE fix           │
│                               (echart_dashboard.py validators,         │
│                                ALWAYS_BLOCKING_ERROR_CODES list,       │
│                                error message text)                     │
│                                └─► re-run, compare delta               │
└────────────────────────────────────────────────────────────────────────┘
```

The two tracks share the same harness + findings format and run
side by side every session.

---

## 2. Invariants (read before touching anything)

```
┌─ INVARIANT 1 ──────────────────────────────────────────────────────┐
│ Skill (`dashboards.md`) almost never changes.                      │
│                                                                    │
│ Every byte costs PRISM context budget at conversation start.       │
│ The skill-discipline rule's filter test applies to every edit:     │
│                                                                    │
│     "Does PRISM make a different decision because of this?"        │
│                                                                    │
│ Aesthetic + validation work changes the engine's behavior, not     │
│ PRISM's authoring decision. Defaults change, error messages        │
│ change, layout heuristics change -- PRISM keeps emitting the       │
│ same manifest shape.                                               │
│                                                                    │
│ The skill changes ONLY when PRISM truly needs to know something    │
│ the engine cannot enforce. Surface every proposed skill change     │
│ in findings with explicit rationale. ASK before applying.          │
│                                                                    │
│ Rule reference: .cursor/rules/skill-discipline.mdc                 │
└────────────────────────────────────────────────────────────────────┘

┌─ INVARIANT 2 ──────────────────────────────────────────────────────┐
│ Drag-and-drop boundary is one-way.                                 │
│                                                                    │
│ echarts-payload/* is byte-identical between staging and PRISM.     │
│ No environment branching, no `if PRISM:`. If a fix needs           │
│ staging-only infrastructure, it goes in dev/, not the payload.     │
│                                                                    │
│ Rule reference: .cursor/rules/viz-platforms.mdc                    │
└────────────────────────────────────────────────────────────────────┘

┌─ INVARIANT 3 ──────────────────────────────────────────────────────┐
│ Engine validation > Gemini vision QC (in production).              │
│                                                                    │
│ Per `prism/vision-qc.md`, runtime Gemini vision QC in PRISM is     │
│ being retired. The right loop is engine validation + good          │
│ defaults + tested aesthetic surface.                               │
│                                                                    │
│ Vision QC stays in STAGING (this workflow) as a Cursor +           │
│ Playwright tool. It is NOT shipped to PRISM.                       │
└────────────────────────────────────────────────────────────────────┘

┌─ INVARIANT 4 ──────────────────────────────────────────────────────┐
│ Adversarial test data stays in dev/qc/.                            │
│                                                                    │
│ The "real data only" Rule 1 in `dashboards.md` governs PRODUCTION  │
│ dashboards. Adversarial synthetic data is the whole point of QC    │
│ -- it must NEVER leak into demos.py, samples.py, or any            │
│ production-flavored example. dev/qc/* is the ONLY allowed home.    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Workflow (per session)

```
                                              ┌──────────────────────────┐
                                              │  test set catalogue §4   │
                                              │  (this doc, growing)     │
                                              └────────────┬─────────────┘
                                                           │
       ┌──────────────────────────┐                        │
       │ pick category(ies)       │ ◄──────────────────────┘
       │ (e.g. A01, A02, V01)     │
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ author or extend test    │ each .py contains 5-15 minimal
       │ set .py file under       │ manifests, deliberately stressed
       │ dev/qc/<track>/<NN>_*.py │ on ONE failure dimension
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ run harness:             │ aesthetic: render + screenshot
       │ python3 dev/qc_runner.py │ validation: validate + diag capture
       │   --aesthetic <NN>       │ output lands in dev/qc/output/<UTC>/
       │   --validation <NN>      │
       │   --all                  │
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ Cursor reads each PNG /  │ vision-inspection (PNG) + diag-stream
       │ diag stream and grades   │ rating (informative / actionable /
       │ severity                 │ correct / comprehensive)
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ write findings doc:      │ template in §5
       │ dev/qc/findings/<UTC>.md │
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ apply engine / rendering │ touch echart_studio.py /
       │ fix(es)                  │ echart_dashboard.py / rendering.py
       │                          │ AVOID dashboards.md edits
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ re-run harness, compare  │ baseline: prior findings doc
       │ delta                    │ regression  → blocker
       │                          │ improvement → captured + closed
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ verify nothing else      │ python3 dev/demos.py --all
       │ regressed                │ python3 dev/tests.py unit
       └────────────┬─────────────┘
                    │
                    ▼
       ┌──────────────────────────┐
       │ commit findings + engine │ update dev/notes.md "Open items"
       │ changes                  │ log any deferred work
       └──────────────────────────┘
```

---

## 4. Test set catalogue

The catalogue grows over time. Each row is a test set under
`dev/qc/<track>/<NN>_<topic>.py` containing ~5-15 minimal manifests.
Initial backlog below; add new entries as new failure modes show
up.

### 4.1 Track A -- aesthetic categories

```
ID    NAME                       WHAT TO STRESS
────  ─────────────────────────  ──────────────────────────────────────
A01   Multi-axis padding         mapping.axes with 1/2/3/4 axes;
                                  left-only / right-only / mixed sides;
                                  short labels (DXY) vs long
                                  (DXY 100Y avg dev. (z));
                                  percent / bp / usd / compact / raw JS
                                  axisLabel formatters; offset 0/80/160.

A02   Pie / donut collisions     N = 2/3/5/10/25/50 slices;
                                  one dominant + many tiny;
                                  long category labels;
                                  legend at top / bottom / left / right /
                                  none; w:6 / w:4 / w:3 tile widths.

A03   Multi_line series density  1/2/5/10/25/100 series;
                                  strokeDash + N series;
                                  humanize on/off; legend overflow.

A04   Single-column dashboards   1 chart per row; 8/10/12/15 rows;
                                  chart at w:12 (rule violation; engine
                                  should warn but render usable).

A05   Tab + row density          2/4/6/8/12 tabs;
                                  1/2/3/4/6/9 widgets per row;
                                  long tab markdown headers.

A06   Table column widths        very long text values; very short;
                                  in_cell bar with negative range;
                                  sparkline column with very long /
                                  very short ticker; 30-column tables.

A07   KPI tile crowding          1/2/3/4/6 KPIs per row;
                                  big numbers (12.34M) vs tiny (0.0001);
                                  compact / comma / raw / percent
                                  formats; sparkline vs no sparkline.

A08   Empty / single-row         dataset with 1 row;
                                  chart with single data point;
                                  table with one row;
                                  pivot with one row+col combo;
                                  empty datasets gated by show_when.

A09   Heatmap density            5x5 / 12x12 / 26x26 cells;
                                  long axis labels; visualMap clearance;
                                  diverging vs sequential palette
                                  edge cases.

A10   Annotations overlap        multiple hlines + vlines + bands +
                                  arrows + points on the same chart;
                                  arrow that overlaps a series;
                                  vline at right edge; band spanning
                                  100% of x; label collisions.

A11   Long category labels       30/60/120-char category names on
                                  bar / bar_horizontal / boxplot /
                                  funnel; ellipsis behaviour vs
                                  rotation vs label-cap-px.

A12   Very wide numbers          KPI / table cells with values like
                                  12345678901.23 -- formatter behaviour;
                                  `format=raw` vs `compact` vs `comma`.

A13   Brush + sync visual        brush selection visible across all
                                  members; sync legend toggling
                                  preserves shared y-axis;
                                  dataZoom slider visual jitter.

A14   Tooltip rendering          hover behaviour at edge of chart;
                                  tooltip overflow off-screen;
                                  decimals in tooltip vs in axis;
                                  long series names in tooltip.

A15   Theme + palette edges      gs_clean default;
                                  series_colors with all hex values
                                  matching palette; gs_blues on
                                  diverging data; gs_diverging on
                                  sequential data.
```

### 4.2 Track B -- validation categories

```
ID    NAME                       ADVERSARIAL INPUTS
────  ─────────────────────────  ──────────────────────────────────────
V01   Missing required keys      manifest without metadata;
                                  no datasets;
                                  widget without id;
                                  chart without spec/option/ref;
                                  spec without chart_type / dataset /
                                  mapping; mapping without required
                                  keys (sankey without source, etc.)

V02   Malformed types            chart_type as int / list / None;
                                  mapping as string / list;
                                  datasets as list / string;
                                  filter type as int;
                                  widget id as int;
                                  numbers as strings, strings as
                                  numbers; mixed-type column.

V03   Cross-references           dataset key not in datasets;
                                  mapping column not in dataset;
                                  filter target not in widgets;
                                  link member not in widgets;
                                  click_emit_filter id not in filters;
                                  computed dataset cycle;
                                  cascading depends_on cycle.

V04   Duplicate ids              duplicate widget / filter / tool input
                                  ids; duplicate annotation labels.

V05   Computed dataset whitelist unauthorized function (eval, __import__,
                                  attribute access);
                                  cyclic compute (a -> b -> a);
                                  reference to missing column;
                                  identifier with digits / spaces.

V06   show_when conditions       filter id that doesn't exist;
                                  data source path that doesn't resolve;
                                  op not in valid set;
                                  malformed compound all/any/not;
                                  empty `all` / `any` arrays.

V07   Filter rule trees          nesting > 12;
                                  all + any in same node;
                                  leaf without field/op/value;
                                  in / not_in with non-list value;
                                  invalid op for type.

V08   Tool defs                  input kind not in valid set;
                                  output kind not in valid set;
                                  compute_js syntactically broken;
                                  matrix rows_from with missing dataset;
                                  scalar show_when referencing missing
                                  input.

V09   Persistence metadata       kerberos missing;
                                  dashboard_id missing;
                                  methodology empty;
                                  refresh_frequency invalid value;
                                  header_actions id collides with chrome
                                  reserved id.

V10   Stress -- combine ≥5 bugs  manifest with one bug from V01-V09
                                  -- does the validator surface ALL of
                                  them in one pass, or stop at the
                                  first?

V11   Diagnostic taxonomy edges  cases that should be `error` but get
                                  flagged as `warning` (and vice versa);
                                  ALWAYS_BLOCKING_ERROR_CODES coverage;
                                  the strict=False vs strict=True
                                  behavioural delta.

V12   Suggestion quality         "did you mean X?" surface in error
                                  messages -- false suggestions;
                                  missing suggestions where one is
                                  obvious (case-insensitive match,
                                  Levenshtein-1 match).

V13   Persistence audit          _audit_dashboard_layout edge cases:
                                  every forbidden file pattern in
                                  dashboards.md §2.5; the manifest-orphan
                                  CSV detection; the per-source subfolder
                                  detection.

V14   Refresh-runner namespace   simulate the namespace gap in
                                  dashboards.md §6.5: pull_data.py using
                                  save_artifact / pull_nyfed / etc.
                                  Confirm the resulting NameError is
                                  surfaced cleanly in the structured
                                  error modal grammar.
```

---

## 5. Findings doc format

```markdown
# QC findings <UTC>

session: <date> · runner: <git-rev or "no-git"> · duration: <secs>
test sets run: A01, A02, V01, V02

## Track A -- aesthetic

### A01 -- Multi-axis padding

**Test set**: dev/qc/aesthetic/01_multi_axis.py · 8 manifests
**Output**: dev/qc/output/<UTC>/A01/

| #  | Manifest                | Render PNG | Vision finding                                     | Severity | Engine fix                                                                    |
|----|-------------------------|------------|----------------------------------------------------|----------|-------------------------------------------------------------------------------|
| 1  | a01_2axes_left_right.py | a01_01.png | OK                                                 | --       | --                                                                            |
| 2  | a01_4axes_compact.py    | a01_02.png | 50% horiz padding before plot starts               | high     | echart_studio.py: collapse offset stack when N axes ≤ 4 and labels share unit |
| 3  | a01_long_label_titles   | a01_03.png | axis title truncated by `category_label_max_px`    | medium   | rendering.py: bump cap for axis-title-only path (not category labels)         |
| ... |                        |            |                                                    |          |                                                                               |

### A02 -- Pie / donut collisions
[same shape]

## Track B -- validation

### V01 -- Missing required keys

**Test set**: dev/qc/validation/01_missing_required.py · 12 manifests
**Output**: dev/qc/output/<UTC>/V01/

| #  | Manifest                  | Expected diag (n codes) | Actual diag (n codes) | Rating         | Action                                                       |
|----|---------------------------|--------------------------|------------------------|----------------|--------------------------------------------------------------|
| 1  | v01_no_metadata.py        | 3 (kerberos, dashboard_id, methodology) | 1 ("metadata required") | not informative | echart_dashboard.py: per-field codes when metadata absent       |
| 2  | v01_widget_no_id.py       | 1 (widget_missing_id)    | 1 (widget_missing_id)  | OK             | --                                                           |
| ...|                           |                          |                        |                |                                                              |

### V10 -- Stress combined

| #  | Manifest                  | Expected ≥ codes | Actual codes | Comprehensive? | Notes                                                        |
|----|---------------------------|------------------|--------------|----------------|--------------------------------------------------------------|
| 1  | v10_5bugs_combined.py     | 5                | 3            | NO             | Validator stops at first chart_type error; should accumulate |

## Skill change requests (this should be empty)

- (none)

## Deferred / open

- A05 tab-density tests deferred -- dev/inspect_dashboard.py needs
  a `--per-widget` capture flag first.

## Re-QC delta vs prior findings (<prior UTC>)

| Category | Prior issues | Current issues | Δ              |
|----------|--------------|----------------|----------------|
| A01      | 3            | 0              | -3 (closed)    |
| A02      | 2            | 1              | -1 (1 closed)  |
| V01      | 5            | 5              | 0 (no-op fix)  |
```

---

## 6. The harness (`dev/qc_runner.py`)

To be authored in the first session. CLI shape (mirrors
demos.py/tests.py conventions, per the user's interactive-CLI
rule):

```
python3 dev/qc_runner.py                                # interactive menu
python3 dev/qc_runner.py --aesthetic A01                # one set
python3 dev/qc_runner.py --validation V01               # one set
python3 dev/qc_runner.py --aesthetic --all              # all aesthetic
python3 dev/qc_runner.py --validation --all             # all validation
python3 dev/qc_runner.py --all                          # both, every set
python3 dev/qc_runner.py --list                         # list all sets
```

Output structure:

```
dev/qc/
├── aesthetic/
│   ├── 01_multi_axis.py
│   ├── 02_pie_donut_collisions.py
│   ├── 03_multi_line_density.py
│   └── ...
├── validation/
│   ├── 01_missing_required.py
│   ├── 02_malformed_types.py
│   ├── 03_cross_references.py
│   └── ...
├── output/<UTC>/
│   ├── A01/
│   │   ├── manifests.json          one entry per test in the .py
│   │   ├── a01_01_full.png         Playwright full-page
│   │   ├── a01_01_widget1.png      per-widget crops
│   │   ├── a01_02_full.png
│   │   ├── ...
│   │   └── diag_stream.json        validator output (validation track)
│   ├── A02/...
│   ├── V01/...
│   └── index.html                  gallery view of every PNG + diag
└── findings/
    ├── 2026-05-02T03-15-00.md
    └── 2026-05-03T10-22-00.md
```

Each .py test set follows a uniform shape:

```python
# dev/qc/aesthetic/01_multi_axis.py
"""A01 -- Multi-axis padding stress.

Each entry returns a manifest dict. The harness compiles, renders,
and screenshots each one. Cursor vision-inspects per the workflow.
"""
from typing import Any, Dict, List

def manifests() -> List[Dict[str, Any]]:
    return [
        _two_axes_left_right(),
        _four_axes_compact(),
        _four_axes_long_labels(),
        # ... ~5-15 entries
    ]

def _two_axes_left_right() -> Dict[str, Any]:
    return {
        "id": "a01_2axes_left_right",
        "title": "A01.1 -- 2 axes, 1L + 1R, short labels",
        # ... minimal manifest exercising the failure dimension
    }
```

```python
# dev/qc/validation/01_missing_required.py
"""V01 -- Missing required keys stress.

Each entry returns a (manifest, expected_codes) pair. The harness
runs validate_manifest + chart_data_diagnostics + (try) compile,
captures every diagnostic / exception, and rates the actual codes
vs expected.
"""
def manifests() -> List[Tuple[Dict[str, Any], List[str]]]:
    return [
        (_no_metadata(),      ["metadata_kerberos_missing",
                                "metadata_dashboard_id_missing",
                                "metadata_methodology_missing"]),
        (_widget_no_id(),     ["widget_missing_id"]),
        # ...
    ]
```

The harness has zero engine-side dependencies beyond the existing
sys.path patches in dev/demos.py and dev/inspect_dashboard.py.

---

## 7. Concrete starting backlog

The following issues were observed in the showcase walk-through on
2026-05-01 and seed the first session's findings doc.

```
ISSUE 1 -- Multi-axis padding (HIGH)
─────────────────────────────────────────────────────────────────────
where:           showcase tab 1 (TS), CROSS-ASSET OVERLAY tile
                  (mapping.axes, log scale)
visible:         ~40-50% horizontal padding between left axis labels
                  and the start of the plot area; chart is squashed
                  into the right half
hypothesis:      echart_studio.py mapping.axes builder applies
                  per-axis grid.left padding cumulatively instead
                  of MAX-across-same-side
test set:        A01 (build first)
fix lives:       echart_studio.py around the mapping.axes block
                  (look for `grid.left`, `axis_offset_step`,
                  `axes[i].offset`)

ISSUE 2 -- Pie / donut legend overlap (HIGH)
─────────────────────────────────────────────────────────────────────
where:           showcase tab 3 (HIER), ALLOCATION (PIE) tile
visible:         legend pills at bottom visually collide with
                  bottom-edge slices of the pie
hypothesis:      pie `radius` defaults to ~65%; `legend.bottom: 0`
                  doesn't reserve enough vertical clearance (~16-20px
                  gap missing)
test set:        A02 (build first)
fix lives:       echart_studio.py pie / donut builder; possibly
                  rendering.py legend layout helper

ISSUE 3 -- Single-column long charts (MEDIUM)
─────────────────────────────────────────────────────────────────────
where:           any layout with chart at w:12
visible:         the §4.1 rule "chart widgets are never w:12" is
                  authorial only; engine renders w:12 charts as
                  flat ribbons of slope-zero whitespace
hypothesis:      no diagnostic emitted for chart-w:12; rule lives
                  only in skill prose
test set:        A04
proposal:        add warning-severity diagnostic when a chart
                  widget renders at w:12; could be made a soft
                  warning behind a `strict_aesthetic=True` flag if
                  hard-fail is too aggressive

ISSUE 4 -- Multi_line series density (MEDIUM-LOW)
─────────────────────────────────────────────────────────────────────
where:           charts with > 12 series
visible:         legend wraps unreadably; series colours collide;
                  `gs_primary` palette has only 7 anchors before it
                  cycles
hypothesis:      no auto-collapse for legend; no diagnostic for
                  series-count > palette-count
test set:        A03
proposal:        engine: emit warning when n_series > palette_size;
                  add legend "+N more" overflow behaviour
```

---

## 8. File pointers

```
GS/viz/echarts/
├── echarts-payload/
│   ├── echart_dashboard.py         <-- VALIDATOR + compile_dashboard +
│   │                                    chart_data_diagnostics +
│   │                                    ALWAYS_BLOCKING_ERROR_CODES
│   ├── echart_studio.py            <-- 30 chart builders. Most
│   │                                    aesthetic regressions live here.
│   │                                    mapping.axes block ~line 1100+
│   ├── rendering.py                <-- HTML scaffold, runtime JS,
│   │                                    Playwright PNG export
│   ├── config.py                   <-- theme + palette + dimension
│   │                                    presets (palette anchor count
│   │                                    lives here)
│   └── dashboards.md               <-- SKILL: avoid edits unless
│                                        absolutely required
│
├── dev/
│   ├── demos.py                    <-- 14 demos incl. build_showcase
│   │                                    (canonical proof-of-coverage)
│   ├── tests.py                    <-- 566 unit tests + stress
│   ├── inspect_dashboard.py        <-- Playwright runtime QC harness
│   │                                    (existing; can be reused for
│   │                                    per-widget capture)
│   ├── notes.md                    <-- engine notes + open items
│   ├── samples.py                  <-- shared sample fixtures
│   ├── archive/demos/README.md     <-- 5 archived demos pointer
│   └── qc/                         <-- NEW: this work
│       ├── aesthetic/01_*.py
│       ├── validation/01_*.py
│       ├── output/<UTC>/
│       └── findings/<UTC>.md
│
├── ai_development/mysite/news/static/js/echarts.js
│                                    <-- inlined into every dashboard;
│                                        version pin lives here
└── README.md                       <-- staging mechanics

prism/
├── vision-qc.md                    <-- the deprecation context for
│                                        production-side vision QC
├── architecture.md                 <-- L1/L2/L3/L4 context tiers
└── mcp-tools.md                    <-- list_ai_repo + on-demand spoke
                                        fetching (PRISM-side; not
                                        relevant to QC but referenced
                                        in skill discipline)

.cursor/rules/
├── viz-platforms.mdc               <-- drag-and-drop contract; the
│                                        "vision-QC retirement" framing
├── skill-discipline.mdc            <-- when to edit dashboards.md
│                                        (rarely); the filter test
└── prism.mdc                       <-- repo-to-PRISM mapping
```

---

## 9. Last session's work (context)

```
session 2026-05-01 -- "make the gallery MECE, build a canonical demo"
─────────────────────────────────────────────────────────────────────
shipped:
  build_showcase()  one canonical 8-tab MECE dashboard in
                    dev/demos.py covering every primitive in
                    dashboards.md catalog index
                    (30 chart types, 10 widgets, 10 filter types,
                    11 ops, 6 note kinds, 5 annotations, 8 KPI
                    aggregators, 11 table formats, 4 tool input
                    kinds, 8 tool output kinds, 4 sync modes, 4
                    brush types, both layouts).
                    Each tab opens with a markdown header naming
                    the primitives demonstrated; per-widget
                    subtitles call out specific primitives.

  gallery rework    replaced the 13-feature coverage matrix with a
                    13-row primitive-catalog matrix; added a
                    "canonical proof-of-coverage demo" banner above
                    the matrix linking to showcase; sorted the demo
                    cards so showcase renders first.

  archived          5 demos subsumed by showcase removed from
                    DEMO_REGISTRY (feature_studio, dev_workflow,
                    compound_screener, fomc_brief, custom_tool_demo).
                    `build_*` functions remain in demos.py with
                    `# ARCHIVED 2026-05-01` markers (one-line
                    resurrection). Tombstone at
                    dev/archive/demos/README.md.

  docs             dashboards.md §0 added a one-liner referring
                    callers to the showcase as the canonical proof
                    artifact.
                    README.md "Running the demos" section reordered
                    showcase-first.
                    dev/notes.md "Demo gallery" subsection rewritten;
                    added "Open items" entry for the `raw` chart_type
                    drift between catalog and validator.

  verified         14/14 demos pass --all (~50s), 566/566 unit tests
                    pass, Playwright inspection of all 8 showcase
                    tabs clean (9 steps captured).

context this session inherits:
  - showcase exists and renders at strict=True
  - 14 production demos all green
  - 566 unit tests green
  - skill-discipline rule exists and frames the "what to edit"
    decision
  - no git in this workspace; preservation = file-on-disk
  - the user has flagged the multi-axis padding + pie collision
    issues from the screenshot pass (issues 1, 2 above)
```

---

## 10. First-session task list

```
[ ] 1. Read this entire handoff doc.
[ ] 2. Read prism/vision-qc.md for the deprecation context.
[ ] 3. Read .cursor/rules/skill-discipline.mdc and
        .cursor/rules/viz-platforms.mdc.
[ ] 4. Open the showcase in a real browser:
         cd GS/viz/echarts
         python3 dev/demos.py --demo showcase --open
[ ] 5. Cursor-vision-inspect each tab via the Read tool on PNGs at
        dev/output/<latest>/showcase/ (tabs are already there from
        the prior session) OR re-run dev/inspect_dashboard.py
        --demo showcase --visual-only and read those.
[ ] 6. Catalog every aesthetic regression spotted into a TEMP
        findings doc. Tighten / merge / split categories vs §4.1
        as needed.
[ ] 7. Author dev/qc/qc_runner.py with the CLI shape from §6.
[ ] 8. Author the first three test sets:
         dev/qc/aesthetic/01_multi_axis.py        (issue 1 above)
         dev/qc/aesthetic/02_pie_donut_collisions.py (issue 2)
         dev/qc/validation/01_missing_required.py  (V01 backlog)
[ ] 9. Run the harness; vision-inspect every PNG; read every diag
        stream; populate dev/qc/findings/<UTC>.md per the §5
        template.
[ ] 10. Apply engine + rendering fixes for issues 1 and 2. Touch
         echart_studio.py (mapping.axes builder, pie/donut builder)
         and rendering.py (legend reservation). NO dashboards.md
         edits.
[ ] 11. Re-run harness, verify the two issues close. Update
         findings doc with the delta.
[ ] 12. Run python3 dev/demos.py --all (all 14 should still pass).
         Run python3 dev/tests.py unit (all 566 should still pass).
[ ] 13. Update dev/notes.md "Open items" with anything deferred.
[ ] 14. Surface in the conversation: which engine files changed,
         the delta, any unresolved blockers, any proposed skill
         changes (with rationale -- ASK before applying).
```

---

## 11. What good looks like

```
PER QC PASS:
[x] every manifest in the run set ran through the harness
[x] every render has a vision-inspected entry in findings doc
[x] every adversarial manifest has a diagnostic-rating entry
[x] every "high" / "blocker" finding has an engine fix applied
[x] dashboards.md change list is empty OR has 1-2 entries with
    explicit "could not be enforced at the engine" rationale
    (and was confirmed with the user before the edit)
[x] re-QC pass shows zero regressions on the same test set
[x] showcase + 13 production demos all still pass --all
[x] all 566 unit tests still pass

PER SESSION OUTPUT:
[x] dev/qc/findings/<UTC>.md committed
[x] list of engine / rendering files touched (with line ranges)
[x] list of new test cases added to the catalogue (§4.1 / §4.2)
[x] dev/notes.md "Open items" updated with anything deferred
[x] no broken file paths, no orphan PNGs, no rogue artefacts
    under dev/qc/output/* without a corresponding manifest
    reference in findings
```

---

## 12. Cross-platform note (altair)

This handoff is echarts-first because the showcase work that
surfaced the regressions was echarts. The PHILOSOPHY ports
directly to altair (see `GS/viz/altair/`):

```
ALTAIR EQUIVALENT
─────────────────
test sets        ─►  dev/qc/aesthetic/A01_*.py (charts not dashboards)
harness          ─►  PNG render via altair save() instead of Playwright
vision           ─►  Cursor reads each PNG (same model)
validation       ─►  validate_chart_input + the existing diagnostic
                      pipeline in chart_functions.py
findings format  ─►  identical
file pointers    ─►  GS/viz/altair/altair-payload/chart_functions.py,
                      chart_functions_studio.py, chart_context.md
```

The first cycle of this workflow can include altair test sets if
bandwidth allows, but echarts-first is the recommended sequencing
because that's where the latest aesthetic regressions surfaced.
Once echarts has 3-4 closed cycles, port the harness shape to
altair as a sibling `GS/viz/altair/dev/qc/`.
