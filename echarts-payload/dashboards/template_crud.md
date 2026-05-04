# Template CRUD patterns

Spoke fetched on demand from the dashboards hub. Concrete code patterns for CRUD on `manifest_template.json` — the one PRISM-authored JSON spec for a dashboard. **No engine API.** PRISM inlines these patterns into an ephemeral session-folder script and runs raw JSON traversal; the engine surface stays unchanged.

Pairs with `dashboards/recipes.md` (long-form worked recipes), `dashboards/widgets.md` (per-widget shape reference), `dashboards/charts.md` (per-chart-type mapping rules), `dashboards/filters.md` (filter / link / brush mechanics).

This spoke covers the three-tier edit model's middle surface — `manifest_template.json` — which is high-churn (every UX iteration touches it). For the data side see `dashboards/pipelines.md`; for cross-dataset derivation see `recipes.md` §7.

---

## 1. The skeleton

Every CRUD edit follows the same five-step shape:

1. **AUDIT** — confirm the dashboard folder is canonical (`dashboards.md` §2.5.3); raises if not, in which case realignment takes priority over the surface change
2. **READ** — load the template from S3 and `deepcopy` for mutation safety
3. **MUTATE** — copy the relevant pattern below; adapt to your case
4. **VALIDATE** — `validate_manifest(tpl)` raises on schema violations
5. **WRITE** — persist the merged template back to S3

```python
import json, copy

DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# 1. AUDIT
m = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest.json").decode("utf-8"))
_audit_dashboard_layout(DASHBOARD_PATH, m)

# 2. READ + deepcopy
tpl_raw = json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8"))
tpl = copy.deepcopy(tpl_raw)

# 3. MUTATE — pattern from §3-§8 below

# 4. VALIDATE
validate_manifest(tpl)

# 5. WRITE
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")
```

After step 5, run §9 (in-session recompile) to verify the change compiles cleanly against current data BEFORE declaring the edit complete. If the recompile fails, the manifest_template was committed but the rendered dashboard is stale — fix forward (re-edit) or revert to the prior template (`recipes.md` §5 quarantine path).

`validate_manifest(tpl)` is non-optional. It walks the same structural validator the compiler uses, so a passing validate guarantees the next `compile_dashboard` won't reject on schema grounds (it can still reject on data-shape diagnostics — those are caught by §9). Skipping validate ships a malformed template that PRISM doesn't see broken until the next refresh runner tick.

---

## 2. Layout traversal

The manifest's widgets live in one of two places depending on `tpl["layout"]["kind"]`:

| `kind` | Widgets at | Iterate via |
|---|---|---|
| `"grid"` (default) | `tpl["layout"]["rows"][i][j]` | nested for-loop over rows |
| `"tabs"` | `tpl["layout"]["tabs"][k]["rows"][i][j]` | nested for-loop over tabs → rows |

Inline this small helper at the top of any ephemeral CRUD script that needs to traverse without caring which layout kind the template uses:

```python
def _walk_rows(tpl):
    """Yield (location_dict, row_list) pairs across both layout kinds.

    location_dict carries the route back to the row for in-place mutation:
      {"tab_id": "<id>", "row_idx": i}  for tabs layout
      {"row_idx": i}                    for grid layout

    The yielded row_list is mutable — appending to it appends to the
    underlying tpl in place.
    """
    layout = tpl["layout"]
    if layout.get("kind") == "tabs":
        for tab in layout["tabs"]:
            for i, row in enumerate(tab["rows"]):
                yield {"tab_id": tab["id"], "row_idx": i}, row
    else:
        for i, row in enumerate(layout["rows"]):
            yield {"row_idx": i}, row
```

This helper is the only abstraction this spoke uses. Everything else is inline mutation. The helper exists because layout-kind variation forces it — the same widget id traversal has two different code paths, and inlining both into every CRUD pattern is noisier than a four-line helper.

---

## 3. Read patterns

Read patterns surface what's currently in the template so PRISM can plan the mutation against verified state. Always read first.

### 3.1 Find a widget by id

```python
def _find_widget(tpl, widget_id):
    for loc, row in _walk_rows(tpl):
        for j, w in enumerate(row):
            if w.get("id") == widget_id:
                return w, {**loc, "col_idx": j}
    raise KeyError(f"widget {widget_id!r} not in manifest_template")

w, loc = _find_widget(tpl, "curve_lvl")
print(f"found at {loc}; kind={w['widget']}; w={w.get('w')}")
```

### 3.2 List all widgets / tabs / filters / datasets

Inventory the template before mutating. Always part of the first edit on an inherited dashboard — surfaces shape PRISM may not remember from earlier sessions:

```python
print("WIDGETS:")
for loc, row in _walk_rows(tpl):
    for j, w in enumerate(row):
        print(f"  {w['widget']:<10} id={w.get('id'):<24} w={w.get('w'):<3} {loc}")

print("\nTABS:")
if tpl["layout"].get("kind") == "tabs":
    for tab in tpl["layout"]["tabs"]:
        print(f"  {tab['id']:<20} label={tab.get('label')}")

print("\nFILTERS:")
for f in tpl.get("filters", []):
    print(f"  {f['id']:<24} type={f['type']:<14} targets={f.get('targets')}")

print("\nDATASETS:")
for key, entry in tpl.get("datasets", {}).items():
    src = entry.get("source", []) if isinstance(entry, dict) else []
    cols = src[0] if src else []
    print(f"  {key:<24} cols={cols}")
```

### 3.3 Inspect a single tab's row structure

When the ask is "add a chart next to the existing rates chart", knowing the row layout matters more than the global widget list:

```python
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "overview")
for i, row in enumerate(tab["rows"]):
    summary = [f"{w['widget']}#{w.get('id')} (w={w.get('w')})" for w in row]
    width_sum = sum(w.get('w', 0) for w in row)
    print(f"row {i} (w_sum={width_sum}): {summary}")
```

`width_sum` matters because chart widgets must be `w=6` or `w=4` (`dashboards.md` §4.1) and a row's widths sum to ≤ `cols` (default 12). Adding a chart to a row that's already at `w_sum=12` requires a new row, not appending to the existing one.

---

## 4. Widget CRUD

### 4.1 Append a widget to a specific tab.row

```python
NEW_WIDGET = {
    "widget": "chart", "id": "curve_real", "w": 6,
    "title": "Real 10y curve",
    "spec": {"chart_type": "line", "dataset": "rates_real",
             "mapping": {"x": "date", "y": "real_10y", "y_title": "Real 10y (%)"}},
}

tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "overview")
while len(tab["rows"]) <= 2:        # ensure row index exists
    tab["rows"].append([])
tab["rows"][2].append(NEW_WIDGET)
```

### 4.2 Append a widget to a grid layout

```python
NEW_WIDGET = {"widget": "kpi", "id": "ust_10y_kpi", "w": 3,
              "label": "UST 10Y", "source": "rates.latest.us_10y"}

while len(tpl["layout"]["rows"]) <= 0:
    tpl["layout"]["rows"].append([])
tpl["layout"]["rows"][0].append(NEW_WIDGET)
```

### 4.3 Insert a widget at a specific column position

When the ask is "put the new chart NEXT TO the curve chart" (not at the end of the row):

```python
w, loc = _find_widget(tpl, "curve_lvl")
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
tab["rows"][loc["row_idx"]].insert(loc["col_idx"] + 1, NEW_WIDGET)
```

### 4.4 Replace a widget's spec by id

When the ask is "change the curve chart from line to multi_line":

```python
w, _ = _find_widget(tpl, "curve_lvl")
w["spec"]["chart_type"] = "multi_line"
w["spec"]["mapping"]["color"] = "series"
```

In-place mutation on the dict returned by `_find_widget` mutates the template — the helper returns the actual ref, not a copy.

### 4.5 Wholesale replace a widget by id

When the spec is too divergent to mutate in place — e.g. swapping `kpi` for `stat_grid`:

```python
NEW_WIDGET = {"widget": "stat_grid", "id": "rates_stats", "w": 6,
              "items": [{"label": "2Y",  "source": "rates.latest.us_2y"},
                        {"label": "10Y", "source": "rates.latest.us_10y"},
                        {"label": "30Y", "source": "rates.latest.us_30y"}]}

w, loc = _find_widget(tpl, "rates_kpi_strip")
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
tab["rows"][loc["row_idx"]][loc["col_idx"]] = NEW_WIDGET
```

The id can change (`rates_kpi_strip` → `rates_stats`), but if the new widget references a dataset the old one didn't, that dataset must already be a slot in `tpl["datasets"]` (or added per §6.1) AND `build.py` must already populate it.

### 4.6 Remove a widget by id

```python
w, loc = _find_widget(tpl, "curve_2s10s")
if "tab_id" in loc:
    tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
    rows = tab["rows"]
else:
    rows = tpl["layout"]["rows"]
del rows[loc["row_idx"]][loc["col_idx"]]
# Optional cleanup: if the row is now empty, remove it
if not rows[loc["row_idx"]]:
    del rows[loc["row_idx"]]
```

### 4.7 Move a widget across rows / tabs

```python
w, src_loc = _find_widget(tpl, "rates_kpi_strip")

# Detach from current location
if "tab_id" in src_loc:
    src_tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == src_loc["tab_id"])
    src_rows = src_tab["rows"]
else:
    src_rows = tpl["layout"]["rows"]
src_rows[src_loc["row_idx"]].pop(src_loc["col_idx"])

# Attach to new location (tab "overview", row 0)
dst_tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "overview")
while len(dst_tab["rows"]) <= 0:
    dst_tab["rows"].append([])
dst_tab["rows"][0].append(w)
```

Detach-before-attach matters because if the detach raises (widget not found), the attach side never runs and the template is unchanged. Reverse order risks duplicating the widget.

---

## 5. Tab CRUD

### 5.1 Add a new tab (after a specific existing tab)

```python
NEW_TAB = {
    "id": "credit", "label": "Credit",
    "description": "IG and HY spreads, default rates, issuance.",
    "rows": [],   # widgets get appended via §4 patterns
}

tabs = tpl["layout"]["tabs"]
after_idx = next(i for i, t in enumerate(tabs) if t["id"] == "rates")
tabs.insert(after_idx + 1, NEW_TAB)
```

### 5.2 Add a tab at the end

```python
tpl["layout"]["tabs"].append(NEW_TAB)
```

### 5.3 Remove a tab

Removing a tab also removes every widget under it. If those widgets were referenced from filter `targets`, those references become dangling — clean them up:

```python
DOOMED = "credit"
tabs = tpl["layout"]["tabs"]

# Collect widget ids about to disappear
removed_widget_ids = set()
for tab in tabs:
    if tab["id"] == DOOMED:
        for row in tab["rows"]:
            for w in row:
                if "id" in w:
                    removed_widget_ids.add(w["id"])

# Drop the tab
tpl["layout"]["tabs"] = [t for t in tabs if t["id"] != DOOMED]

# Clean filter targets that pointed at removed widgets
for f in tpl.get("filters", []):
    targets = f.get("targets", [])
    if isinstance(targets, list):
        f["targets"] = [t for t in targets if t not in removed_widget_ids]
```

`"*"` in filter targets means "all widgets" — leave it alone; it self-adjusts to the new widget set.

### 5.4 Reorder tabs

```python
ORDER = ["overview", "rates", "credit", "fx"]
tabs = tpl["layout"]["tabs"]
by_id = {t["id"]: t for t in tabs}
tpl["layout"]["tabs"] = [by_id[tid] for tid in ORDER if tid in by_id]
```

### 5.5 Update a tab's label or description

```python
tab = next(t for t in tpl["layout"]["tabs"] if t["id"] == "overview")
tab["label"] = "Snapshot"
tab["description"] = "Today's headline rates, curve, and risk pills."
```

---

## 6. Filter CRUD

### 6.1 Add a filter

```python
NEW_FILTER = {
    "id": "country",
    "type": "multiSelect",
    "label": "Country",
    "field": "country",
    "options": ["US", "DE", "JP", "UK"],
    "default": ["US", "DE"],
    "targets": ["fx_curve", "fx_carry_table"],
}
tpl.setdefault("filters", []).append(NEW_FILTER)
```

### 6.2 Update a filter's options / range / default / targets

```python
f = next(f for f in tpl["filters"] if f["id"] == "lookback")
f["default"] = "1Y"
f["options"] = ["3M", "6M", "1Y", "2Y", "5Y"]
```

### 6.3 Add or remove a target on an existing filter

```python
f = next(f for f in tpl["filters"] if f["id"] == "lookback")
if "*" not in f["targets"] and "new_chart_id" not in f["targets"]:
    f["targets"].append("new_chart_id")
```

```python
f = next(f for f in tpl["filters"] if f["id"] == "lookback")
f["targets"] = [t for t in f["targets"] if t != "removed_chart_id"]
```

### 6.4 Remove a filter

```python
tpl["filters"] = [f for f in tpl.get("filters", []) if f["id"] != "doomed_filter_id"]
```

If the filter was the only producer of a state value other widgets read via `click_emit_filter` or `links`, remove those references too.

---

## 7. Dataset slot CRUD

`manifest_template.json` carries dataset SLOTS — each slot's `source` field is empty in the template, populated at build time by `populate_template(tpl, datasets)` in `build.py`. Adding / removing a slot in the template is HALF the change; the other half is editing `build.py` to populate (or not) that key.

### 7.1 Add a dataset slot

```python
tpl.setdefault("datasets", {})
tpl["datasets"]["rates_real"] = {
    "source": [],
    "schema": {"date": "datetime", "real_10y": "float", "real_5y": "float"},
}
```

Then surgically edit `build.py` per `recipes.md` §6 to load the matching `data/rates_real.csv`, rename columns to plain English, and pass it into `populate_template(tpl, datasets={..., "rates_real": df_real})`. If the underlying pull doesn't exist yet, edit `pull_data.py` first (per `dashboards/pipelines.md` §3 reuse-decision-ladder) — fully populated CSV must land before `build.py` references the key.

### 7.2 Remove a dataset slot

```python
del tpl["datasets"]["rates_real"]

# Also remove every widget that referenced it as `spec.dataset`
referencing_ids = set()
for loc, row in _walk_rows(tpl):
    for w in row:
        if w.get("spec", {}).get("dataset") == "rates_real":
            referencing_ids.add(w["id"])

for wid in referencing_ids:
    w, loc = _find_widget(tpl, wid)
    rows = (next(t["rows"] for t in tpl["layout"]["tabs"] if t["id"] == loc["tab_id"])
            if "tab_id" in loc else tpl["layout"]["rows"])
    rows[loc["row_idx"]].remove(w)
```

KPI / stat_grid / table widgets reference datasets via `source: "<dataset>.<aggregator>.<col>"` strings, not via `spec.dataset` — surface those too if the orphan check matters.

### 7.3 Update a dataset slot's schema

When `pull_data.py` will start producing a new column, declare it in the template's `datasets[<key>].schema` so the widgets that map to that column have something to validate against:

```python
tpl["datasets"]["rates"]["schema"]["real_10y"] = "float"
```

Schema is advisory — the validator doesn't reject a manifest whose schema misses a column. The reason to keep it accurate is human-readability of the template + downstream tooling that may consume schemas later.

---

## 8. Metadata + chrome CRUD

### 8.1 Patch top-level metadata fields

```python
md = tpl.setdefault("metadata", {})
md["sources"] = ["GS Market Data", "Haver", "FRED"]
md["tags"] = ["rates", "credit"]
md["refresh_frequency"] = "daily"
```

Three required fields per `dashboards.md` §2.3 — `kerberos`, `dashboard_id`, `methodology` — must be non-empty for the validator to pass. If the inherited template has any of these missing, set them BEFORE the rest of the mutation:

```python
md = tpl.setdefault("metadata", {})
md.setdefault("kerberos", KERBEROS)
md.setdefault("dashboard_id", DASHBOARD_NAME)
if not md.get("methodology"):
    md["methodology"] = (
        "## Sources\n"
        "* GS Market Data: 2Y / 10Y USD swap rates (EOD)\n"
        "## Construction\n"
        "* Daily close pulled via pull_market_data; no transforms"
    )
```

### 8.2 Update the summary banner

```python
tpl.setdefault("metadata", {})["summary"] = {
    "title": "Today's read",
    "body": ("Front-end has richened ~6bp on a softer print. Curve "
             "**bull-steepened**, 2s10s out of inversion."),
}
```

### 8.3 Add or update header_actions

`header_actions[]` injects custom buttons to the LEFT of the always-on chrome (Methodology / Refresh / Share / Download). Reserved chrome ids cannot collide; the validator hard-rejects collisions. See `dashboards.md` §5 for the full reserved list.

```python
NEW_ACTION = {
    "id": "open_methodology_doc",
    "label": "Methodology PDF",
    "href": "https://intranet.example/dashboards/rates_methodology.pdf",
    "target": "_blank",
    "icon": "📄",
}
tpl.setdefault("header_actions", []).append(NEW_ACTION)
```

### 8.4 Add or remove a link (sync / brush group)

```python
tpl.setdefault("links", []).append({
    "id": "rates_axis_sync",
    "kind": "sync",
    "mode": "axis",
    "members": ["curve_lvl", "curve_chg", "curve_2s10s"],
})
```

```python
tpl["links"] = [l for l in tpl.get("links", []) if l["id"] != "doomed_link_id"]
```

---

## 9. In-session quick recompile (the verify step)

After step 5 of the skeleton (template written to S3), the FAST way to verify the change compiles cleanly is to exec `build.py` from S3. This uses the CURRENT `data/*.csv` on disk (no fresh pull), runs the canonical recompile recipe, and surfaces any compile-time / shape-time errors immediately:

```python
src = s3_manager.get(f"{DASHBOARD_PATH}/scripts/build.py").decode("utf-8")

# Refresh-runner namespace shape (matches dashboard-refresh.md §5.5)
ns = {
    "pd": pd, "np": np, "io": io, "json": json, "os": os,
    "datetime": datetime, "timezone": timezone,
    "s3_manager": s3_manager,
    "SESSION_PATH": DASHBOARD_PATH.rstrip("/"),
    "compile_dashboard": compile_dashboard,
    "populate_template": populate_template,
    "manifest_template": manifest_template,
    "validate_manifest": validate_manifest,
}
exec(compile(src, f"{DASHBOARD_PATH}/scripts/build.py", "exec"), ns)
print("[recompile] in-session exec succeeded")
```

If this succeeds, `manifest.json` + `dashboard.html` on S3 reflect the new template against current data. If it fails, fix forward (re-edit the template, re-run §1 + §9) or revert (`recipes.md` §5 quarantine path for templates).

**This is the in-session loop.** PRISM iterates: CRUD → write → recompile → see error → CRUD again. Tool 4's subprocess refresh (`dashboards.md` §6.1 Tool 4) is the canonical end-of-edit verification — it runs the SAME `build.py` plus a fresh `pull_data.py` re-exec in a clean interpreter, and IS load-bearing before surfacing the portal URL to the user.

| Loop | When | What it proves |
|---|---|---|
| In-session quick recompile (this section) | After every CRUD mutation | Template change is structurally valid + compiles against current data |
| Tool 4 subprocess refresh (`dashboards.md` §6.1) | Once at end-of-edit | Tomorrow's cron will produce byte-identical output; pull pipeline still works |

Skipping the in-session quick recompile in favour of going straight to Tool 4 trades fast iteration for clean-interpreter assurance — fine for a single small edit, expensive for multi-step builds. The in-session loop pays for itself after two edits.

If `build.py` itself needs editing (a new dataset slot was added in §7.1 and the script must now populate it), the order is:

1. Edit `manifest_template.json` per §1-§8 above (add slot)
2. Edit `build.py` per `recipes.md` §6 (load + populate the new key) — this bumps `SCRIPT_VERSION` + writes to `scripts/versions/`
3. Then run §9 above

---

## 10. The contract

Five rules govern every CRUD edit. Violating any of them ships a known-broken template:

| # | Rule | Consequence of skipping |
|---|---|---|
| 1 | AUDIT before mutating (`dashboards.md` §2.5.3) | Edits land on a non-compliant folder; runner picks up wrong bytes |
| 2 | `deepcopy` the loaded template before mutation | In-session re-runs see prior mutation state; bugs are non-reproducible |
| 3 | `validate_manifest(tpl)` BEFORE writing | Schema-broken template ships; refresh runner fails on the next tick |
| 4 | Recompile (§9) BEFORE surfacing the change | Data-shape break passes validate but breaks at compile; user sees broken render |
| 5 | Surgical mutation on inherited templates; never wholesale rewrite | Mutation drops widgets / tabs / filters PRISM didn't include in this script's dict |

Rule 5 is the manifest-wipe footgun (`dashboards.md` §2.5.4). The CRUD patterns above are the operational answer — they MUTATE in place, never `tpl = {...}` from a fresh dict.

---

## 11. Anti-patterns

### 11.1 Wholesale template rewrite

```python
# WRONG — wipes everything not in this script's dict
tpl = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates",
    "datasets": {"rates_eod": {"source": []}},
    "layout": {"rows": [[
        {"widget": "chart", "id": "curve_lvl", "w": 6, "spec": {...}},
    ]]},
}
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")
```

The inherited template likely had filters, metadata, header_actions, multiple tabs, and tens of widgets that this fresh dict doesn't carry. WRITE replaces the file wholesale; everything missing is lost.

```python
# RIGHT — load existing, mutate surgically per §1-§8 above
tpl = copy.deepcopy(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8")))
# ... small mutations ...
validate_manifest(tpl)
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")
```

### 11.2 Mutating without `deepcopy`

```python
# WRONG — `tpl_raw` and `tpl` are the same object; the in-session re-run
# sees the mutation already applied
tpl_raw = json.loads(s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode())
tpl = tpl_raw   # NOT a copy
tpl["layout"]["tabs"][0]["rows"][0].append(NEW_WIDGET)
```

```python
# RIGHT — explicit deepcopy before mutation
tpl = copy.deepcopy(json.loads(
    s3_manager.get(f"{DASHBOARD_PATH}/manifest_template.json").decode("utf-8")))
```

### 11.3 Skipping validate

```python
# WRONG — schema-broken template ships; refresh runner raises on next tick
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")

# RIGHT — gate the write
validate_manifest(tpl)
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
               f"{DASHBOARD_PATH}/manifest_template.json")
```

### 11.4 Skipping the recompile (§9)

The schema validator catches structural errors but not data-shape errors. A widget mapping to a column that doesn't exist in the current dataset (`chart_mapping_column_missing`) passes `validate_manifest` and fails at `compile_dashboard`. The recompile is what catches it.

### 11.5 Mutating before the audit

```python
# WRONG — edits compound on a non-compliant folder
tpl = json.loads(...)
# ... mutate ...
_audit_dashboard_layout(...)   # raises AFTER the mutation, but the mutation isn't yet on S3

# RIGHT — audit gates the read; mutation never starts on a broken folder
_audit_dashboard_layout(DASHBOARD_PATH, current_manifest)
tpl = copy.deepcopy(...)
# ... mutate ...
```

### 11.6 List-comprehension lookups when ids may collide

```python
# WRONG — silently picks the first match if two widgets share an id
w = [w for w in row if w.get("id") == "curve_lvl"][0]
```

```python
# RIGHT — assert uniqueness as part of the lookup
matches = [w for w in row if w.get("id") == "curve_lvl"]
assert len(matches) == 1, f"expected 1 widget with id curve_lvl, got {len(matches)}"
w = matches[0]
```

The validator hard-rejects duplicate widget ids (`widget_id_duplicate`), but a half-finished CRUD that left two `curve_lvl` widgets in the template will surface here before that error. Assertions in the CRUD code catch the issue at the right scope (PRISM is doing the edit, not waiting for the runner to fail).

---

## Appendix — quick reference

| Pattern | Section |
|---|---|
| READ → MUTATE → VALIDATE → WRITE skeleton | §1 |
| Layout-aware traversal helper | §2 |
| Find widget by id | §3.1 |
| List widgets / tabs / filters / datasets | §3.2 |
| Inspect tab row structure | §3.3 |
| Append widget to tab row | §4.1 |
| Append widget to grid row | §4.2 |
| Insert widget at column position | §4.3 |
| Replace widget spec in place | §4.4 |
| Wholesale replace widget by id | §4.5 |
| Remove widget by id | §4.6 |
| Move widget across rows / tabs | §4.7 |
| Add tab (after another) | §5.1 |
| Add tab at end | §5.2 |
| Remove tab + clean filter targets | §5.3 |
| Reorder tabs | §5.4 |
| Update tab label / description | §5.5 |
| Add / update / remove filter | §6.1 / §6.2 / §6.4 |
| Add / remove filter target | §6.3 |
| Add / remove dataset slot | §7.1 / §7.2 |
| Update dataset schema | §7.3 |
| Patch metadata fields | §8.1 |
| Update summary banner | §8.2 |
| Add header_action | §8.3 |
| Add / remove link (sync / brush) | §8.4 |
| In-session quick recompile (verify step) | §9 |
| The contract (5 rules) | §10 |
| Anti-patterns (6 footguns) | §11 |
