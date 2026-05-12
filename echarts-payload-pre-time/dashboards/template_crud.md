# Template CRUD — niche reference

The canonical CRUD recipes for `manifest_template.json` live in the **hub at §C** (`dashboards.md`). The hub carries the full READ → DEEPCOPY → MUTATE → VALIDATE → WRITE skeleton, the `_walk_rows` / `_find_widget` helpers, and the eight most common mutations (append widget, insert at column, replace spec, remove widget, add tab, add filter, add dataset slot, patch metadata).

This spoke covers the **less-common patterns** that the hub elides for size — niche operations PRISM only needs occasionally. Fetch this only when the hub patterns don't cover the case.

---

## 1. Multi-target filter rebinding

When a filter's `targets` list needs surgery beyond simple add/remove (e.g. swap one widget id for another while preserving order, scope a `*` wildcard to an explicit list, redirect targets to a renamed widget):

```python
f = next(f for f in tpl["filters"] if f["id"] == "lookback")

# Swap one widget id for another, preserving position
if "old_chart_id" in f["targets"]:
    idx = f["targets"].index("old_chart_id")
    f["targets"][idx] = "new_chart_id"

# Convert wildcard to explicit list (so future renames don't auto-include
# the new widget)
if "*" in f["targets"]:
    explicit = []
    for loc, row in _walk_rows(tpl):
        for w in row:
            if w.get("widget") in ("chart", "kpi", "table") and w.get("id"):
                explicit.append(w["id"])
    f["targets"] = explicit
```

Always re-run `validate_manifest(tpl)` after target rewrites — the validator catches dangling references before they surface as broken filter behaviour.

---

## 2. `show_when` reference cleanup

When a widget with `show_when: {<filter_id>: ...}` is removed, the filter reference is orphaned but inert (no validator failure). When the filter ITSELF is removed, every `show_when` referencing it silently keeps the widget visible. To clean both directions:

```python
removed_filter_id = "regime"
for loc, row in _walk_rows(tpl):
    for w in row:
        sw = w.get("show_when")
        if isinstance(sw, dict) and removed_filter_id in sw:
            del sw[removed_filter_id]
        if isinstance(sw, dict) and not sw:
            del w["show_when"]
```

---

## 3. Link member rewrites (sync / brush)

When two charts are part of a `kind: "sync"` link and one gets removed (or a new chart should join the group):

```python
links = tpl.get("links", [])
for link in links:
    if link.get("id") == "rates_axis_sync":
        # Add a new member
        if "new_chart_id" not in link["members"]:
            link["members"].append("new_chart_id")
        # Remove a deleted one
        link["members"] = [m for m in link["members"] if m != "doomed_chart_id"]
        # Drop the link entirely if only one member remains (sync needs >=2)
        if len(link["members"]) < 2:
            tpl["links"] = [l for l in links if l["id"] != link["id"]]
```

---

## 4. Bulk spec mutations across widgets

When the same property changes across many widgets at once (e.g. switching every chart from `gs_primary` to `gs_blues`, bumping every chart's `h_px` by 40 for a denser layout, prefixing every widget id with a tab slug for namespace hygiene):

```python
# Switch palette on every chart
for loc, row in _walk_rows(tpl):
    for w in row:
        if w.get("widget") == "chart":
            w.setdefault("spec", {})["palette"] = "gs_blues"

# Bump heights
for loc, row in _walk_rows(tpl):
    for w in row:
        if w.get("widget") == "chart" and "h_px" in w:
            w["h_px"] = int(w["h_px"]) + 40
```

These bulk patterns benefit from one final `validate_manifest(tpl)` + `build_dashboard(folder)` pass — bulk edits maximise the surface area for collateral breakage.

---

## 5. Dataset key rename (template + downstream references)

When a CSV stem gets renamed (e.g. PRISM realised `pull_market_data(name='rate')` → `data/rate_eod.csv` is the wrong stem and should be `name='rates'` → `data/rates_eod.csv`), the manifest_template needs a coordinated rewrite plus the `pull_data.py` edit (§D in the hub) plus the file rename on S3:

```python
OLD, NEW = "rate_eod", "rates_eod"

# 1. Rename the dataset slot
if OLD in tpl.get("datasets", {}):
    tpl["datasets"][NEW] = tpl["datasets"].pop(OLD)

# 2. Rewrite every widget that referenced the old key
for loc, row in _walk_rows(tpl):
    for w in row:
        spec = w.get("spec", {})
        if spec.get("dataset") == OLD:
            spec["dataset"] = NEW
        if w.get("dataset") == OLD:   # tables / pivots
            w["dataset"] = NEW
        # KPIs and stat_grid items reference via dotted source strings
        if isinstance(w.get("source"), str) and w["source"].startswith(f"{OLD}."):
            w["source"] = w["source"].replace(f"{OLD}.", f"{NEW}.", 1)
        for item in (w.get("items") or []):
            src = item.get("source")
            if isinstance(src, str) and src.startswith(f"{OLD}."):
                item["source"] = src.replace(f"{OLD}.", f"{NEW}.", 1)

# 3. Filter targets / link members are widget-id keyed, NOT dataset-keyed --
#    they need no change here.

# 4. Move the CSV on S3 (do this BEFORE the next build_dashboard call;
#    otherwise the new key has no matching CSV and compile fails).
s3_manager.put(s3_manager.get(f"{DASHBOARD_PATH}/data/{OLD}.csv"),
                f"{DASHBOARD_PATH}/data/{NEW}.csv")
s3_manager.delete(f"{DASHBOARD_PATH}/data/{OLD}.csv")

validate_manifest(tpl)
s3_manager.put(json.dumps(tpl, indent=2).encode("utf-8"),
                f"{DASHBOARD_PATH}/manifest_template.json")
build_dashboard(DASHBOARD_PATH)
```

The corresponding `pull_data.py` edit (changing `name='rate'` to `name='rates'`) is a separate §D mutation; do that BEFORE the dataset key rename so the next `run_pull` produces the new CSV.

---

## Pointer index

| Pattern | Where |
|---|---|
| READ → MUTATE → VALIDATE → WRITE skeleton | hub §C |
| `_walk_rows` + `_find_widget` helpers | hub §C.0 |
| Append / insert / replace / remove a widget | hub §C.1 / §C.2 / §C.3 / §C.4 |
| Add a tab | hub §C.5 |
| Add / update / remove a filter | hub §C.6 |
| Add / remove a dataset slot | hub §C.7 |
| Patch metadata fields | hub §C.8 |
| The CRUD contract (5 rules) | hub §C.9 |
| Multi-target filter rebinding / wildcard scoping | this spoke §1 |
| `show_when` reference cleanup | this spoke §2 |
| Link member rewrites | this spoke §3 |
| Bulk spec mutations across widgets | this spoke §4 |
| Dataset key rename (template + S3 + pull_data) | this spoke §5 |
