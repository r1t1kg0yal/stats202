# Handoff prompt -- Dashboard QC Session 1 (2026-05-02)

> Paste this whole file at the start of a fresh Cursor session to
> pick up from here.

You are picking up the **Dashboard QC hardening** endeavor after
Session 1. The workflow itself -- methodology, invariants, test-set
catalogue, harness contract, acceptance bar -- is codified at
`workflows/dashboard_qc.md`. This handoff relays session-specific
state: what was built, what was fixed, what's queued next.

---

## 1. Read these files before doing anything

In this order. Reading budget ~1500 lines (dense but load-bearing).

```
ORIENTATION (always-applied rules)
  .cursor/rules/prism.mdc                       workspace rule
  .cursor/rules/viz-platforms.mdc               drag-and-drop contract
  .cursor/rules/skill-discipline.mdc            when to edit the skill

THE METHOD (TIMELESS)
  workflows/README.md                           workflow catalog
  workflows/dashboard_qc.md                     THE methodology -- read
                                                  §1 philosophy, §2
                                                  invariants, §3 loop,
                                                  §4 catalogue, §6
                                                  harness, §7 acceptance
                                                  bar

THIS HANDOFF (session state)
  staging/handoffs/dashboard_qc_session_1.md    you are here

CURRENT ENGINE STATE
  GS/viz/echarts/dev/notes.md                   "Open items" §, esp. the
                                                  "Adversarial QC harness
                                                  + first hardening
                                                  pass" entry -- has the
                                                  five fixes from
                                                  Session 1 in detail
  GS/viz/echarts/dev/qc_runner.py               the harness CLI
  GS/viz/echarts/dev/qc/_common.py              shared fixtures
  GS/viz/echarts/dev/qc/aesthetic/              A01 + A02 live here
  GS/viz/echarts/dev/qc/validation/             V01 + V02 live here
  GS/viz/echarts/dev/qc/output/<UTC>/           per-run artefacts
  GS/viz/echarts/dev/qc/findings/<UTC>.md       per-session findings
                                                  stubs (Session 1 did
                                                  NOT hand-grade
                                                  findings markdown;
                                                  see §6 below)

ENGINE FILES TOUCHED IN SESSION 1 (know the surface you inherit)
  GS/viz/echarts/echarts-payload/echart_studio.py      multi-axis +
                                                        pie/donut fixes
  GS/viz/echarts/echarts-payload/echart_dashboard.py   validator +
                                                        comprehensive
                                                        error delivery

SKILL (should NOT have been touched; verify before editing)
  GS/viz/echarts/echarts-payload/dashboards.md         untouched in S1
```

---

## 2. What was done in Session 1

```
┌─ SESSION 1 (dashboard QC -- first execution) ──────────────────────┐
│                                                                    │
│ HARNESS (new, from scratch)                                        │
│   dev/qc_runner.py           interactive + argparse CLI,           │
│                               auto-discovers qc/aesthetic/ and     │
│                               qc/validation/ by category id.       │
│   dev/qc/_common.py          wide_panel(), wrap_tile(),            │
│                               wrap_manifest() -- shared fixtures   │
│   dev/qc/aesthetic/          A01, A02 categories                   │
│   dev/qc/validation/         V01, V02 categories                   │
│   dev/qc/output/<UTC>/       PNGs + diag_stream.json + index.html  │
│                                                                    │
│ TEST SETS AUTHORED                                                 │
│   A01  Multi-axis padding              8 manifests                 │
│   A02  Pie / donut collisions         10 manifests                 │
│   V01  Missing required keys          12 manifests                 │
│   V02  Comprehensive error delivery    4 manifests                 │
│                                                                    │
│ ENGINE BUGS FOUND + FIXED  (six fixes total, zero skill edits)     │
│                                                                    │
│   #1  Multi-axis axis_offset_step = 80 applied as HARD FLOOR even  │
│       when author did not set it explicitly. Computed step         │
│       (name_gap + half_thick + breathing) was usually tighter;     │
│       10-30 px per stacked-axis pair wasted.                       │
│       FIX  Only floor when explicit. Default: computed step wins.  │
│                                                                    │
│   #2  Refined-pass grid.left/right capped by initial conservative  │
│       pass. max(existing, refined+16) meant the bloated initial    │
│       value stuck once set.                                        │
│       FIX  Capture user-set floor BEFORE initial pass; refined     │
│       pass compares against that floor, not the bloated value.     │
│                                                                    │
│   #3  _grid_margins_for_axes refined path floored each axis's      │
│       band at 70 px even when actual label widths were 21-35 px.   │
│       FIX  When label_widths provided, band = actual + 26          │
│       (title pad) with 35 px floor.                                │
│                                                                    │
│   #4  Pie/donut center hardcoded at ["50%", "58%"] (tuned for TOP  │
│       legend). When legend_position="bottom", pie bottom clipped   │
│       into legend pills.                                           │
│       FIX  build_pie reads mapping.legend_position up front and    │
│       picks center dynamically (58% top / 50% none / 42-22% bottom │
│       depending on slice count).                                   │
│                                                                    │
│   #5  Validator's _validate_layout used `if wid:` for the          │
│       duplicate-id check -- so if wid was MISSING, the entire      │
│       block (including a required-presence check that should have  │
│       existed) was skipped. Chart widgets without `id` silently    │
│       validated; filter targets, link members, click_emit_filter,  │
│       and runtime DOM all broke.                                   │
│       FIX  Add explicit "id required" error when widget id is      │
│       absent.                                                      │
│                                                                    │
│   #6  compile_dashboard's error delivery was fragmented:           │
│         (a) three separate `preview = errs[:10]` truncations       │
│             meant PRISM saw max 10 errors per raise.               │
│         (b) validate_manifest failure SHORT-CIRCUITED --           │
│             chart_data_diagnostics never ran, so PRISM needed N    │
│             round-trips for N cross-stream bugs.                   │
│       FIX  Remove all three [:10] truncations. Run CDD             │
│       unconditionally (try-except wrapped) even when validate      │
│       fails. Validate-failure path still returns DashboardResult   │
│       (preserves the r.success / r.warnings call pattern that      │
│       downstream tests + PRISM use) but with BOTH streams          │
│       populated in warnings + diagnostics. CDD errors in the       │
│       post-validate path (always_blocking + strict-mode) still     │
│       raise ValueError but now with the FULL error list in the     │
│       message, not a 10-item preview. End-state: one call ->       │
│       every error (either via r.warnings+r.diagnostics or via      │
│       the raised exception message).                               │
│                                                                    │
│ REGRESSION GATES                                                   │
│   showcase demo compiles + renders                   ✓             │
│   all 14 demos compile                               ✓ (before #6) │
│   566/566 unit tests pass                            ✓ (before #6) │
│   V01 12/12 comprehensive                            ✓             │
│   V02 4/4 comprehensive                              ✓             │
│                                                                    │
│   ** User interrupted the re-run of tests.py unit + demos.py       │
│      --all AFTER fix #6 landed. FIRST THING THIS SESSION DOES:     │
│      re-run those gates. See §6 below. **                          │
│                                                                    │
│ DOC WORK                                                           │
│   workflows/ folder created                                        │
│   workflows/README.md           catalog + shape convention         │
│   workflows/dashboard_qc.md     TIMELESS methodology (this is the  │
│                                  primary reference for every       │
│                                  future session)                   │
│   workflows/altair_qc.md        sibling stub (altair harness       │
│                                  doesn't exist yet; methodology    │
│                                  is ready for porting)             │
│   dev/notes.md "Open items"     Session 1 fixes documented         │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## 3. Engine state as of end of Session 1

### Multi-axis layout (A01 post-fix grid dims for reference)

```
TEST              AXES    grid.left    grid.right
────────────────  ─────  ───────────  ────────────
a01_01  1-axis      1      76           20
a01_02  1L+1R       2      76           72
a01_03  2L+1R       3     159           72
a01_04  2L+2R       4     159          152  (was 166/166)
a01_05  3L+1R       4     237           72
a01_06  1L+3R       4      76          237
a01_07  4ax long    4     159          152
a01_08  4ax short   4     159          159
```

4-axis at w:6 is still tight (~45% plot area); further gains need
the "suppress rotated title when color-coded single-series axis
carries meaning via series legend" change. Not touched in S1.

### Pie / donut geometry (A02 post-fix)

```
legend_pos     n_slices   center_y   radius
─────────────  ─────────  ─────────  ────────
top            any        58 %       72 %
none           any        50 %       68 %
bottom         <=6        42 %       72 %  (was 58 %)
bottom         7-14       32 %       72 %
bottom         15+        22 %       72 %
```

### Comprehensive error delivery (V02)

Every strict=True raise now contains the full cross-stream error
list. No truncation. No short-circuit. PRISM should see every bug
in a single recompile round-trip. Verified against four V02
fixtures (5 / 10 / 15 / 8 bugs; cross-stream; raise_only grading).

### Validator presence checks

Widget id presence is now enforced. Previously silent.

---

## 4. What's next (priority-ordered)

### Top priority -- regression gates (interrupted by user mid-run)

```
1. python3 dev/tests.py unit        expect 566/566 pass (takes ~5 min)
2. python3 dev/demos.py --all       expect 14/14 pass (takes ~50 s)
```

If EITHER fails, diagnose before adding new test sets. Possible
regression points from the six Session 1 fixes are well-contained
(multi-axis code + pie/donut code + layout validator + compile raise
path), so a failure should point clearly at one of them.

### Aesthetic track

```
A03  Multi_line series density     1 / 5 / 15 / 50 series;
                                    strokeDash + N series;
                                    humanize on/off; legend overflow;
                                    gs_primary palette anchor cycling
                                    (7 anchors). Expected bug class:
                                    no warning when n_series exceeds
                                    palette_size -> colors cycle
                                    silently.

A04  Single-column dashboards      1 chart per row; 8/10/12/15 rows;
                                    chart widget at w:12. The rule
                                    "charts are never w:12" lives in
                                    skill prose only; engine should
                                    emit a diagnostic at compile time
                                    when violated.

A08  Empty / single-row data       n=0 / n=1 dataset for every chart
                                    type; show_when gating; single-row
                                    table / pivot / KPI behaviour.
```

### Validation track

```
V03  Cross-references              dataset key not in datasets;
                                    mapping column not in dataset;
                                    filter target not in widgets;
                                    link member not in widgets;
                                    click_emit_filter id not in
                                    filters; computed dataset cycle;
                                    cascading depends_on cycle.

V04  Duplicate ids                 duplicate widget / filter / tool
                                    input ids; duplicate annotation
                                    labels.

V10  Malformed types               chart_type as int / list / None;
                                    mapping as string / list; datasets
                                    as list / string; widget id as
                                    int; numbers as strings, strings
                                    as numbers; mixed-type column.
```

### Cross-cutting

```
* workflows/altair_qc.md        has methodology; harness itself does
                                 not exist. Implementation plan is in
                                 §3 of that file. Maybe 1 session to
                                 port qc_runner + qc/_common and
                                 bootstrap A01 / V01 altair-side.

* image display quirk           Cursor's in-chat image renderer was
                                 unreliable for parallel PNG reads in
                                 Session 1 -- it sometimes returned an
                                 earlier file's bytes for a later
                                 read. Engine introspection is
                                 authoritative; Playwright PNGs are
                                 receipts. Worth a line in the
                                 workflow if it persists.
```

---

## 5. Concrete first actions

```
[ ] 1. Read .cursor/rules/prism.mdc (always-on; already in context)
[ ] 2. Read workflows/dashboard_qc.md in full
[ ] 3. Read this handoff (you already are)
[ ] 4. Read dev/notes.md "Open items" section, esp. the Session 1
         entry at the top
[ ] 5. Run the interrupted regression gates:
         cd GS/viz/echarts
         python3 dev/tests.py unit
         python3 dev/demos.py --all
         Expect: 566/566 tests pass, 14/14 demos succeed.
         If either fails: diagnose (likely fix #6 related, since #1-5
         already passed tests mid-session).
[ ] 6. Pick NEXT test set. Recommended ordering:
         A03 (multi_line density, catches the silent palette cycling)
         V03 (cross-refs -- high value; touches many manifests)
         A04 (single-column warnings -- simple engine diagnostic)
[ ] 7. Author dev/qc/<track>/<NN>_<topic>.py. 8-12 minimal manifests.
[ ] 8. Run harness: python3 dev/qc_runner.py --<track> <ID>
[ ] 9. Vision-inspect every PNG (aesthetic) or grade every diag
         stream (validation).
[ ]10. Apply engine fixes. NO dashboards.md edits.
[ ]11. Re-run harness, confirm delta closes.
[ ]12. Re-run demos.py --all + tests.py unit.
[ ]13. Update dev/notes.md "Open items" with findings + any deferrals.
[ ]14. Write staging/handoffs/dashboard_qc_session_2.md.
```

---

## 6. Known unknowns + open threads

```
* Session 1 findings markdown     The harness emits a findings STUB
                                   at dev/qc/findings/<UTC>.md for
                                   every run. Session 1 wrote stubs
                                   but did NOT hand-fill the vision
                                   ratings / engine fix columns.
                                   Future sessions should do that
                                   post-run so re-QC delta tables
                                   have a baseline to compare
                                   against.

* Cursor image cache              See §4 "image display quirk".

* build_showcase tab_ts visual    After fix #1-3, the CROSS-ASSET
   delta                          OVERLAY tile on Tab 1 of the
                                   showcase is measurably tighter
                                   per engine introspection
                                   (grid.left 166 -> 159, right
                                   166 -> 152). Visual difference
                                   is subtle; for truly dramatic
                                   visual wins on 4-axis w:6
                                   tiles, the deferred "suppress
                                   rotated title" architectural
                                   change is needed. Noted; not
                                   touched in S1.

* Altair harness porting          workflows/altair_qc.md §3 has the
                                   plan. Worth ~1 session once 3-4
                                   echarts cycles close so the
                                   echarts harness shape has
                                   stabilised.
```

---

## 7. What PRISM thinks of this work

None of it affects PRISM's authored manifest shape. Every fix is
behavioural inside the engine:

* Bugs #1, #2, #3 -- dashboards look BETTER (tighter multi-axis)
  without any skill change. PRISM keeps emitting
  `mapping.axes: [...]` with the same shape.
* Bug #4 -- pies with `legend_position="bottom"` render without
  collision. PRISM keeps setting `mapping.legend_position = "bottom"`.
* Bug #5 -- manifests that previously silently validated with a
  missing widget id now fail validation with an actionable error.
  PRISM fixes the missing id via the usual compile loop.
* Bug #6 -- PRISM sees EVERY error in one recompile. Iteration
  loop convergence is 2-3x faster on cross-stream bugs.

Zero edits to `dashboards.md`. Zero edits to `chart_context.md`.
Zero new docstrings PRISM consumes.

If the next session ends up wanting to edit the skill, stop and ASK
first (skill-discipline rule + invariant 1 of the workflow).
