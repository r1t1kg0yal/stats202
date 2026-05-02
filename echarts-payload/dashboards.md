# ECharts Dashboards

- **Module:** `dashboards`
- **Audience:** PRISM (all interfaces, all workflows), developers, Observatory agents
- **Tier:** 2 (on-demand)
- **Scope:** ALL dashboard construction in PRISM. (One-off PNG charts in chat / email / report use Altair `make_chart()`, a separate module.)

A dashboard is a JSON manifest. PRISM never writes HTML, CSS, or JS. PRISM emits structured JSON; the compiler does the rest.

One visual style only — Goldman Sachs brand: GS Navy `#002F6C`, PMS 652 Sky Blue `#7399C6`, Goldman Sans, thin grey grid on paper-white. No theme switcher.

`compile_dashboard(manifest)` is the only PRISM-facing entry point. It validates a manifest, lowers each `widget: chart` through internal builders, and emits an interactive dashboard HTML + manifest JSON.

Every primitive in this skill's Catalog index is rendered, in MECE-grouped tabs with explanatory headers, by the staging-side `build_showcase` demo (`projects/echarts/dev/demos.py`). That dashboard is the canonical proof-of-coverage artifact: if a primitive doesn't render there, the engine has a regression. Production-flavored demos in the same gallery (`rates_monitor`, `markets_wrap`, `screener_studio`, ...) sit beneath the showcase as safety / redundancy.

For refresh-pipeline operations / failure modal / runner internals see `prism/dashboard-refresh.md`. This file is purely about authoring.

This hub covers the always-needed contract, schema, persistence flow, anti-patterns, pre-flight. Per-primitive depth (chart specs, widget specs, filter mechanics, recipes) lives in spoke files fetched on demand — see §3.

---

## Catalog index

Every named primitive PRISM picks between, with a pointer to the hub section OR spoke file that carries the per-primitive spec.

| Primitive | Names | Where |
|---|---|---|
| Widgets (10) | `chart`, `kpi`, `table`, `pivot`, `stat_grid`, `tool`, `note`, `markdown`, `image`, `divider` | `dashboards/widgets.md` (most); `dashboards/widget_tool.md` (`tool`); `dashboards/charts.md` (`chart` specs) |
| Chart types (30) | `line`, `multi_line`, `bar`, `bar_horizontal`, `scatter`, `scatter_multi`, `scatter_studio`, `area`, `heatmap`, `correlation_matrix`, `pie`, `donut`, `boxplot`, `histogram`, `bullet`, `sankey`, `treemap`, `sunburst`, `graph`, `candlestick`, `radar`, `gauge`, `calendar_heatmap`, `funnel`, `parallel_coords`, `tree`, `waterfall`, `slope`, `fan_cone`, `marimekko` | `dashboards/charts.md` §2 |
| Filter types (10) | `dateRange`, `select`, `multiSelect`, `numberRange`, `toggle`, `slider`, `radio`, `text`, `number`, `rule` | `dashboards/filters.md` §1 |
| Filter ops (11) | `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, `in`, `not_in` | `dashboards/filters.md` §5 |
| Note kinds (6) | `insight`, `thesis`, `watch`, `risk`, `context`, `fact` | `dashboards/widgets.md` §8 |
| Annotation types (5) | `hline`, `vline`, `band`, `arrow`, `point` | `dashboards/charts.md` §5 |
| KPI aggregators (8) | `latest`, `first`, `sum`, `mean`, `min`, `max`, `count`, `prev` | `dashboards/widgets.md` §2 |
| Table formats (11) | `text`, `number`, `integer`, `percent`, `currency`, `bps`, `date`, `datetime`, `link`, `signed`, `delta` | `dashboards/widgets.md` §3 |
| Tool input kinds (4) | `scalar`, `sweep`, `expression`, `matrix` | `dashboards/widget_tool.md` §4.1 |
| Tool output kinds (8) | `stat`, `scalar`, `param`, `kpi`, `series`, `table`, `stat_grid`, `distribution` | `dashboards/widget_tool.md` §4.2 |
| Sync modes (4) | `axis`, `tooltip`, `legend`, `dataZoom` | `dashboards/filters.md` §6 |
| Brush types (4) | `rect`, `polygon`, `lineX`, `lineY` | `dashboards/filters.md` §6 |
| Layouts (2) | `grid`, `tabs` | §4 |
| Refresh frequencies (4) | `hourly`, `daily`, `weekly`, `manual` | §2.3 |

Catalog only — pick what you need from this table, then fetch the relevant spoke per the menu in §3.

---

## 0. Contract: eight rules

All eight absolute. A dashboard violating any of them is broken even if `dashboard.html` renders.

### Rule 1 — real data only

- Auto-saving primitives: `pull_market_data`, `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`.
- Everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, Coalition, Inquiry, scraped DataFrames) lands via `save_artifact()` (§6.2).
- Forbidden: `np.random.*`, `np.linspace` / `np.arange` as data, hand-typed numeric arrays, synthetic fill for missing values, invented dates / labels.
- If no source exists, do not build the panel — add a data source first.

### Rule 2 — no literal data inside the manifest JSON

- Pass DataFrames; the compiler converts them to canonical on-disk shape.
- Three accepted dataset entry shapes (all normalised):

| Shape | When |
|-------|------|
| `datasets["rates"] = df` | Most common. Zero ceremony. |
| `datasets["rates"] = {"source": df}` | When attaching metadata to the entry. |
| `datasets["rates"] = {"source": df_to_source(df)}` | When the manifest is saved/read before the compiler touches it. |

### Rule 3 — order is non-negotiable

- `pull_data.py` must complete with real DataFrames (printed `df.shape` / `df.head()` / `df.dtypes`) before `build.py` is authored.
- Write the manifest against verified shapes, not imagined columns.
- Inheriting a non-compliant dashboard (bypasses `compile_dashboard()`, hand-writes HTML/CSS/JS, types numbers into `datasets[*].source`, skips persistence) → bringing it back to spec takes priority over whatever surface change was originally asked for. Surface the trade transparently.

### Rule 4 — canonical layout, exclusive whitelist

- The dashboard folder at `users/{kerberos}/dashboards/{name}/` follows an **exclusive** layout: the artefact set in §2.2 is both the floor (every `[REQUIRED · 1]` row must exist) AND the ceiling (no other paths permitted). Cardinality is exact: one `pull_data.py`, one `build.py`, one `manifest.json`, one `manifest_template.json`, one `dashboard.html`. No second copies, no `_v2` / `_old` / `_backup` siblings, no timestamped scripts, no per-source data subfolders, no scratch `.md` / `.json` siblings.
- The two `.py` files under `scripts/` are exactly what the refresh runner re-executes on schedule. Missing scripts → the [Refresh] button fails immediately with `FileNotFoundError`. Stale duplicates next to them → the runner picks up whichever bytes the lexicographic scan lands on, silently.
- §2.5 codifies the audit (`_audit_dashboard_layout`) PRISM runs at Tool 2's verify step and again whenever it inherits an existing dashboard folder. Audit failures block registration; rogue files are quarantined to `archive/<UTC>/`, never silently deleted.

### Rule 5 — every CSV at `{DASHBOARD_PATH}/data/<dataset>.csv`

- Inside `pull_data.py`, every pull-function call AND every `save_artifact(...)` MUST pass `output_path=f'{SESSION_PATH}/data'`.
- The refresh runner injects `SESSION_PATH = {DASHBOARD_PATH}` so the same string resolves identically at build time and refresh time.
- Without `output_path`, CSVs land in per-source subfolders (`market_data/`, `haver/`, `plottool_data/`) — `build.py` does not look there → refresh fails.
- `pull_market_data` ALWAYS appends `_eod` / `_intraday` to the filename. Pass `name='rates'` → `data/rates_eod.csv`. Use `'rates_eod'` as the manifest dataset key. Pass `name='rates_eod'` → broken `data/rates_eod_eod.csv`.
- The dataset key in `manifest.datasets` matches the on-disk CSV stem byte-for-byte. §6.2 has the per-source pattern.

### Rule 6 — hand off the portal URL, never the HTML file

- The deliverable PRISM surfaces is the **portal URL** (`http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{dashboard_id}/`). Lead with it on the first line of the build success message.
- The S3 path of `dashboard.html` is internal plumbing. Surface it ONLY if the user explicitly asks ("give me the raw HTML", "where on S3 does this land"). Even then, surface the portal URL alongside.
- The portal URL is load-bearing because the serving Django view injects the `window.PRISM_VIEWER` / `PRISM_DASHBOARD_AUTHOR` / `PRISM_DASHBOARD_SHARED` JS globals before `</head>` (§2.3.1). Those globals drive the always-on chrome — Refresh / Share visibility, owner vs viewer state, observatory suppression. Opening the bare `dashboard.html` directly from S3 (or downloading it) skips that injection and the chrome silently degrades.
- The portal URL is also the only path that picks up the hourly refresh runner's updates, the structured failure modal, the share-toggle endpoint, and the per-user community visibility. The bare HTML is a one-shot snapshot.

### Rule 7 — build flow is atomic

- Tools 1, 2, and 3 (§6.1) are **non-divisible**. PRISM does not return to the user between Tool 1 and Tool 3. The dashboard does not exist as a deliverable until every artefact in §2.2 is on S3, the entry sits in `registry["dashboards"][]` (not as a top-level key, §6.1 Tool 3), the user-manifest pointer reflects it, AND both audits pass (`_audit_dashboard_layout` §2.5 + `_audit_registry_state` §6.1 Tool 3).
- Forbidden language in any user-facing message before Tool 3 has completed cleanly: "next steps", "would you like me to", "I can also create / register / set up", "to make this fully persistent / auto-refreshing". Each phrase implies the build has opt-in phases the user can decline. There are no phases. The post-Tool-3 portal URL (Rule 6) is the ONLY user-facing message; everything before it is internal plumbing the user does not see.
- The canonical Rule 7 violation: PRISM pulls data + compiles in-session, renders an HTML preview, then asks the user "would you like me to register and set up daily refresh?" — and ships a worthless artefact. The browser [Refresh] button is broken (no scripts/), the hourly cron skips it (no registry entry), tomorrow's data never arrives, and the user sees a rendered HTML plus a permission prompt. There is no "preview" state to ask permission on; the build IS the registration and persistence.
- Failure handling: if Tool 1 or Tool 2 raises, the response to the user is the failure (with its diagnostic), not a rendered HTML preview gated behind a registration question. Do not paper over a failed build by surfacing partial output and asking permission to "complete" it.

### Rule 8 — slice complex requests, check in between slices

A "build me a dashboard" prompt rarely lands as a single buildable specification. PRISM does NOT attempt to fulfil the entire ask in one build flow. The discipline:

- **Slice the request** into the smallest meaningful deliverable that produces a self-contained, registered, renderable dashboard. Natural slices: one tab; one tool widget; one chart-pair + headline KPI; data pull + headline table, defer charts. Pick the slice whose feedback most disambiguates the rest of the request.
- **Build the slice atomically** (Rule 7 governs WITHIN: Tools 1, 2, 3 non-divisible; the slice must end with a registered dashboard at a portal URL).
- **Hand off the URL and ASK** "first slice live at <URL>. Structure look right? Want me to add [next chunk]?"
- **Wait for confirmation** before the next slice. Iterate.

Rule 8 is NOT in tension with Rule 7. Rule 7 governs atomicity WITHIN a build; Rule 8 governs PACING across builds. Once Rule 7 is satisfied (slice registered + URL surfaced), Rule 8 says: stop, ask, wait. Don't immediately start the next build.

Forbidden after a complex prompt:

- Building all 8 tabs / 30 widgets in one mega-build before surfacing anything.
- "Continuing with the rest of the dashboard now…" without explicit user confirmation.
- Surfacing one slice and immediately stacking "let me also add X, Y, Z" without waiting for the user.
- Pre-announcing the slice plan ("I'll do tabs 1-3 first then 4-8") and proceeding through it autonomously — the plan changes after every slice based on feedback.

Required:

- First slice → portal URL → "this is slice N of M; want me to continue with [specific next chunk]?" → wait.
- Each slice's response is short. Lead with the URL (Rule 6); one sentence on what's in this slice; one sentence on the proposed next chunk; stop.

Why: complex dashboard requests are typically 60-80% under-specified by the user (and that's normal — UX shape is hard to articulate verbatim). A small slice surfaces the misalignment cheaply. A fully-built 30-widget dashboard built in one shot is a guaranteed throwaway when the user says "no, I meant a fundamentally different shape entirely". Rule 8 trades a longer total wall-clock against dramatically less wasted work.

### The build flow IS the refresh path

PRISM authors each script as a Python string, persists to S3, then execs from S3 with the refresh-runner namespace. Build-time and refresh-time run the same bytes from the same path. No drift, no double work, no separate verification step.

```python
df_rates_eod, _ = pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    start='2020-01-01', name='rates', mode='eod')
df_rates_eod.columns = ['us_2y', 'us_10y']            # plain English (Rule 1)
manifest = {
    "schema_version": 1, "id": "rates", "title": "US Rates",
    "datasets": {"rates_eod": df_rates_eod.reset_index()},
    "layout": {"rows": [[
        {"widget": "chart", "id": "curve_lvl", "w": 6,
          "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
                    "mapping": {"x": "date", "y": ["us_2y", "us_10y"],
                                "y_title": "Yield (%)"}}},
        {"widget": "chart", "id": "curve_2s10s", "w": 6,
          "spec": {"chart_type": "line", "dataset": "rates_eod_diff",
                    "mapping": {"x": "date", "y": "spread",
                                "y_title": "2s10s (bp)"}}},
    ]]}
}
compile_dashboard(manifest, session_path=SESSION_PATH)
```

---

## 1. Injected namespace

Inside `execute_analysis_script`:

```python
compile_dashboard       # manifest -> interactive HTML + manifest JSON (+ optional PNGs)
manifest_template       # strip data from a manifest -> reusable template
populate_template       # template + fresh DataFrames -> ready-to-compile manifest
validate_manifest       # dry-run validation without rendering
chart_data_diagnostics  # check data wires up (missing columns, size limits, etc.)
load_manifest           # path -> manifest dict (used by refresh)
save_manifest           # manifest -> JSON file
df_to_source            # DataFrame -> canonical row-of-lists source form
```

`compile_dashboard()` raises by default (`strict=True`) on any error-severity diagnostic. `strict=False` is an inner-loop discovery mode — it keeps going so PRISM can see every cosmetic / advisory issue in one round-trip. **`strict=False` is for in-session iteration only; the persisted `scripts/build.py` MUST use `strict=True`.** A short list of load-bearing error codes (`chart_mapping_column_missing`, `chart_dataset_empty`, `kpi_source_*`, `table_column_field_missing`, `filter_field_missing_in_target`, `chart_build_failed`, …) raise regardless of `strict` — these are the errors that would otherwise ship a chart with `(no data)`, a KPI tile with `--`, an empty table cell, or a filter that silently filters nothing. The full list lives in `echart_dashboard.ALWAYS_BLOCKING_ERROR_CODES`. One theme (`gs_clean`); three palettes (`gs_primary`, `gs_blues`, `gs_diverging`).

---

## 2. Manifest

### 2.1 Shape

```python
manifest = {
    "schema_version": 1, "id": "rates_monitor", "title": "Rates monitor",
    "description": "Curve, spread, KPIs.",   # optional subtitle
    "theme": "gs_clean", "palette": "gs_primary",   # both defaults
    "metadata":        { ... },               # see 2.3
    "header_actions":  [ ... ],               # see Section 5
    "datasets":        {"rates": df_rates, "cpi": {"source": df_cpi}},
    "filters":         [ ... ],               # see dashboards/filters.md
    "layout":          {"kind": "tabs",       # or "grid" (default); see Section 4
                         "tabs": [{"id": "overview", "label": "Overview",
                                   "description": "Headline rates + spread",
                                   "rows": [ [ widget, widget, ... ], ... ]}]},
    "links":           [ ... ],               # see dashboards/filters.md §6
}
compile_dashboard(manifest, session_path=SESSION_PATH)
```

| Top-level field | Purpose |
|-----------------|---------|
| `title` / `description` | Header title + subtitle |
| `theme` / `palette` | `gs_clean` (only theme); `gs_primary` (default) / `gs_blues` (sequential) / `gs_diverging` |
| `metadata` | Provenance + refresh block (§2.3) |
| `header_actions` | Custom header buttons (§5) |
| `datasets` | `{name: DataFrame \| {"source": ...}}` |
| `filters` / `layout` / `links` | `dashboards/filters.md` / §4 / `dashboards/filters.md` §6 |

### 2.2 Folder structure

For **conversational (session-only)** dashboards:

```
{SESSION_PATH}/dashboards/{id}.json     compiled manifest
{SESSION_PATH}/dashboards/{id}.html     compiled dashboard
```

For **persistent user dashboards** (Rule 4) — the layout below is **exclusive**. Every `[REQUIRED · 1]` path must exist exactly once; nothing else is permitted at any depth except the explicitly-allowed `data/` / `history/` / `archive/` prefixes. The audit in §2.5 enforces this both ways (presence and exclusivity).

```
users/{kerberos}/dashboards/{dashboard_name}/
  manifest_template.json    [REQUIRED · 1] LLM-editable spec, NO data
  manifest.json             [REQUIRED · 1] template + fresh data, embedded
  dashboard.html            [REQUIRED · 1] compile_dashboard output
  refresh_status.json       [optional · ≤1] runner-owned runtime state (never author-written)
  thumbnail.png             [optional · ≤1] author-owned preview image
  scripts/                  [REQUIRED · exactly these two files, no others]
    pull_data.py            [REQUIRED · 1] data acquisition (~50-150 lines)
    build.py                [REQUIRED · 1] ~12 lines: load + populate + compile
  data/                     [REQUIRED · CSVs/JSONs whose stems match manifest.datasets keys]
    rates_eod.csv           one CSV per dataset; stem matches manifest key byte-for-byte
    rates_intraday.csv      pull_market_data appends _eod / _intraday
    rates_metadata.json     pull_market_data sidecar uses the bare name
    cpi.csv                 pull_haver_data: no suffix
    cpi_metadata.json
    swap_curve.csv          pull_plottool_data: no suffix
    fdic_gs_bank.csv        save_artifact: no suffix
  history/                  [optional] snapshots when keep_history=true; runner-managed
  archive/<UTC>/            [optional] §2.5 quarantine for non-canonical files; ignored by runner + audit
```

**Why exclusivity matters.** The refresh runner has no PRISM state and no conversation memory — it re-executes the persisted scripts on a schedule. Missing `scripts/*.py` → runner has nothing to call. Missing `manifest_template.json` → `build.py` can't load the template. Missing `data/*.csv` → `build.py` can't read what `pull_data.py` was supposed to write. **Extra files are equally load-bearing**: a `scripts/build_v2.py` next to `scripts/build.py`, a `manifest_old.json` next to `manifest.json`, or a `data/haver/cpi.csv` next to `data/cpi.csv` all create ambiguity that the runner resolves silently — usually wrong.

**Forbidden (audited at §2.5):**

| Class | Examples | Why |
|-------|----------|-----|
| Cardinality violations | `scripts/build_v2.py`, `manifest_old.json`, `pull_data.bak`, `dashboard.prev.html` | Two candidates for "the" file; the runner picks one without telling you which |
| Timestamped historicals at top level | `20260424_pull_data.py`, `manifest.20260424.json` | Use `archive/<UTC>/` (§2.5) — never sit alongside live artefacts |
| Per-source data subfolders | `data/haver/`, `data/market_data/`, `data/plottool_data/` | Everything goes flat into `data/` (Rule 5) |
| Self-suffix CSVs | `data/rates_eod_eod.csv` | The `pull_market_data` `name=` footgun (§6.2 rule 1); rename to bare `name='rates'` |
| Manifest-orphan CSVs | `data/old_dataset.csv` (no matching `manifest.datasets["old_dataset"]`) | Refresh path is "scripts write CSV → build reads CSV by manifest key"; orphan CSVs never get read and shouldn't sit there |
| Scratch siblings | `*_results.md`, `*_artifacts.json`, `notes.txt`, `README.md` | Session-scope artefacts belong under `{SESSION_PATH}/`, not at dashboard scope |
| HTML / CSS / JS in any `.py` file | inlining markup into `pull_data.py` or `build.py` | `rendering.py` owns all markup |
| Multiple data JSONs at top | `data.json`, `metrics.json` next to `manifest.json` | Only `manifest.json` is canonical; embed everything else inside it |
| Inline `<script>const DATA = {}` in HTML | hand-edited `dashboard.html` | Let `compile_dashboard` emit; never post-edit |
| Legacy helpers | `sanitize_html_booleans()` references | Removed; any caller is a stale code path |
| Empty `scripts/` on a persistent dashboard | `scripts/` directory with no `.py` files | The "persistent" promise is "refresh runner re-execs these"; nothing to re-exec → not persistent |
| Renamed canonical files | `scripts/build_dashboard.py`, `scripts/refresh.py`, `scripts/main.py` | Names are load-bearing — the runner reads `scripts/pull_data.py` and `scripts/build.py` exactly |

### 2.3 Metadata block

Drives the data-freshness badge, methodology popup, summary banner, refresh button, and share button.

Three fields are **required** for every dashboard `compile_dashboard` produces — they gate the always-on header chrome (§2.3.1) and the validator rejects manifests missing them:

| Required field | Type | Purpose |
|----------------|------|---------|
| `kerberos` | str | Owner kerberos. Gates the `Refresh` and `Share` buttons; bound to the S3 path the refresh runner writes |
| `dashboard_id` | str | Stable id under `users/{kerberos}/dashboards/`. Typically equals `manifest.id` — set both to the same value |
| `methodology` | str \| `{title, body}` | Markdown describing how the data is constructed. Drives the always-on `Methodology` popup. Must be non-empty |

The remaining fields are optional but every persistent dashboard should at least carry `data_as_of` / `generated_at` (data-freshness badge) and `sources`:

| Optional field | Type | Purpose |
|----------------|------|---------|
| `data_as_of` / `generated_at` | str (ISO) | Header badge `Data as of YYYY-MM-DD HH:MM:SS UTC`; compile-time fallback |
| `sources` | list[str] | Source names (`["GS Market Data", "Haver"]`) |
| `summary` | str \| `{title, body}` | Always-visible markdown banner above row 1 (today's read) |
| `refresh_frequency` | str | `hourly` / `daily` / `weekly` / `manual`; controls the hourly runner — manual means `Refresh` is button-driven only |
| `tags` / `version` | list[str] / str | Echoed into the registry; manifest version string |
| `api_url` / `status_url` | str | Refresh / status endpoint overrides |
| `shared` / `shared_at` | bool / str | Compile-time snapshot of community-share state. `shared: True` means this dashboard is published to the `/dashboards/` Community section. `shared_at` is the ISO timestamp it was first shared. The runtime button reads live state from `window.PRISM_DASHBOARD_SHARED` if injected by the serving view; falls back to this snapshot otherwise. Defaults: `shared: False`, `shared_at: null` |
| `share_api_url` | str | Optional override of the share toggle endpoint (default `/api/dashboard/share/`) |

`summary` and `methodology` accept the shared markdown grammar (`dashboards/widgets.md` §9). `summary` is always-visible above row 1 (today's read); `methodology` is click-to-open via the always-on header button (how the data is constructed).

```python
metadata = {
    "kerberos":     "goyalri",
    "dashboard_id": "rates_monitor",
    "methodology":  "## Sources\n* US Treasury OTR yields (FRED H.15)\n## Construction\n"
                     "* 2s10s, 5s30s = simple cash differences in bp",
    "data_as_of": "2026-04-24T15:00:00Z",
    "sources":    ["GS Market Data"],
    "summary":    {"title": "Today's read",
                    "body": "Front-end has richened ~6bp on a softer print. Curve "
                             "**bull-steepened**, 2s10s out of inversion."},
}
```

#### 2.3.1 Always-on header chrome

The header's right edge is shell-injected (Methodology / Refresh / Share / Download / theme-toggle / data-as-of pill). PRISM does not author these buttons. The validator hard-rejects any manifest missing the three required metadata fields above (`kerberos` / `dashboard_id` / `methodology`); set them and the chrome is functional. The retired `metadata.refresh_enabled` flag is silently ignored. `header_actions[]` (§5) injects custom buttons to the LEFT of this chrome bar; the validator rejects any custom `id` colliding with a reserved chrome id (full list in §5).

### 2.4 `compile_dashboard` parameters

| Parameter | Purpose |
|-----------|---------|
| `manifest` | Required dict |
| `session_path` | Where compiled HTML / JSON land. Default cwd; sandbox passes `SESSION_PATH` |
| `output_path` | Override single-file location (advanced) |
| `write_html` / `write_json` | Both default `True`; suppress for OOP-style use |
| `strict` | `True` raises on any error-severity diagnostic; `False` reports + continues |
| `make_thumbnails` | `False` default; `True` auto-emits a PNG of the first row for the listing page |

`compile_dashboard()` returns a `DashboardResult` with `success`, `html`, `manifest`, `error_message`, and `diagnostics` populated. PRISM rule: ALWAYS check `r.success` before using `r.html`. The reset hint is in `r.error_message`.

### 2.5 Folder sanctity audit

Before the §6.1 build flow can register a dashboard, the folder MUST satisfy the §2.2 exclusive whitelist. The `_audit_dashboard_layout()` helper is what enforces it. The audit runs at two points:

1. **End of Tool 2** (build flow) — confirms the build PRISM just ran produced a §2.2-compliant folder and nothing rogue snuck in.
2. **Start of any inheritance** — when PRISM picks up an existing dashboard folder to modify, the audit runs FIRST. Audit failures block the surface change PRISM was asked to make; cleanup (or quarantine to `archive/<UTC>/`) takes priority.

#### 2.5.1 The audit function

```python
def _audit_dashboard_layout(folder_path: str, manifest: dict) -> None:
    """
    Audit the dashboard folder against the §2.2 exclusive whitelist.
    Raises ValueError listing every cardinality / forbidden-path violation.
    """
    REQUIRED_TOP = {'manifest_template.json', 'manifest.json', 'dashboard.html'}
    OPTIONAL_TOP = {'refresh_status.json', 'thumbnail.png'}
    REQUIRED_SCRIPTS = {'pull_data.py', 'build.py'}

    found_top, found_scripts, data_files = set(), set(), set()
    rogue = []

    listing = s3_manager.list(folder_path)
    for entry in listing:
        rel = entry['Key'].replace(f'{folder_path}/', '', 1).lstrip('/')
        if not rel:
            continue

        # Top-level files
        if '/' not in rel:
            if rel in REQUIRED_TOP or rel in OPTIONAL_TOP:
                found_top.add(rel)
            else:
                rogue.append(rel)
            continue

        # scripts/ -- exactly two .py files allowed, no others
        if rel.startswith('scripts/'):
            sub = rel[len('scripts/'):]
            if '/' in sub:
                rogue.append(rel)
            elif sub in REQUIRED_SCRIPTS:
                found_scripts.add(sub)
            else:
                rogue.append(rel)
            continue

        # data/ -- flat .csv / .json only; stem must match a manifest dataset key
        if rel.startswith('data/'):
            sub = rel[len('data/'):]
            if '/' in sub:
                rogue.append(rel)
                continue
            data_files.add(sub)
            continue

        # history/ and archive/ are permitted; runner ignores them
        if rel.startswith('history/') or rel.startswith('archive/'):
            continue

        rogue.append(rel)

    errors = []

    # Required top-level files
    for required in REQUIRED_TOP:
        if required not in found_top:
            errors.append(f'missing required: {required}')

    # Required scripts
    for required in REQUIRED_SCRIPTS:
        if required not in found_scripts:
            errors.append(f'missing required: scripts/{required}')

    # Data exclusivity: every CSV/JSON stem must match a manifest dataset key
    # (or the metadata sidecar pattern: <bare>_metadata.json where <bare>
    # strips _eod/_intraday). Orphans are forbidden.
    dataset_keys = set(manifest.get('datasets', {}).keys())
    allowed_data = set()
    for key in dataset_keys:
        allowed_data.add(f'{key}.csv')
        allowed_data.add(f'{key}.json')
        bare = key.replace('_eod', '').replace('_intraday', '')
        allowed_data.add(f'{bare}_metadata.json')

    for f in data_files:
        if f not in allowed_data:
            errors.append(f'manifest-orphan in data/: {f}')

    if rogue:
        errors.append(f'rogue paths (must move to archive/<UTC>/ or remove): {sorted(rogue)}')

    if errors:
        raise ValueError(
            f'_audit_dashboard_layout: {folder_path} violates §2.5 whitelist:\n  '
            + '\n  '.join(errors)
        )
```

The audit covers everything that would otherwise be a silent footgun. It raises on a single concatenated message listing every violation so you fix them all in one pass, not one per re-run.

#### 2.5.2 Quarantine, never delete

Rogue files are moved to `archive/<UTC>/`, never deleted. `s3_manager.move(...)` to `{folder_path}/archive/{datetime.utcnow().isoformat()}/{relpath}`. The runner ignores `archive/` and `history/`; both stay invisible to the §2.2 audit.

#### 2.5.3 Inheritance: audit BEFORE you change anything

Run `_audit_dashboard_layout(folder_path, manifest)` FIRST when inheriting an existing dashboard folder. If it raises, surface the failure to the user as the cleanup-first protocol — the requested change does not proceed until the folder is back to spec. Cleanup, re-audit, then proceed.

---

## 3. On-demand spec fetching

This hub covers every primitive's catalog row + the always-needed contract. For per-primitive depth (chart-type mapping rules, widget specs, filter mechanics, recipes), fetch the relevant spoke.

**Do NOT call `get_context()` again — it is one-shot per user message.** Mid-session reads use `list_ai_repo` with `mode="full"`. Each spoke is independent; mix and match.

| Spoke | Contents | Verbatim tool call (copy-paste) |
|-------|----------|--------------------------------|
| `dashboards/charts.md` | 30 chart types; mapping keys; cosmetic / layout knobs; annotations; `scatter_studio`; `correlation_matrix`; computed columns | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md"], mode="full")` |
| `dashboards/widgets.md` | KPI, table (incl. `row_click`), pivot, stat_grid, image, markdown, divider; provenance; `show_when` / `initial_state` / stat strip; markdown grammar | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| `dashboards/widget_tool.md` | `widget: tool` (form-driven compute) — pricers, scenarios, calculators; tool def shape; input + output kinds; canonical examples | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widget_tool.md"], mode="full")` |
| `dashboards/filters.md` | 10 filter types + 11 ops; cascading filters; per-chart `dataZoom`; `click_emit_filter`; compound rule filters; links (sync + brush) | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/filters.md"], mode="full")` |
| `dashboards/recipes.md` | Worked recipes (long-form multi_line, dual axis, RV bullet, thesis+watch); 21 data-shape archetypes → chart types | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/recipes.md"], mode="full")` |

**Common combos** (one call, multiple file_paths):

| Build shape | Single call to copy |
|-------------|---------------------|
| Charts only | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md"], mode="full")` |
| Charts + KPI / table strip | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md", "context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| Charts + widgets + filters | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/charts.md", "context/modules/static/tools/dashboards/widgets.md", "context/modules/static/tools/dashboards/filters.md"], mode="full")` |
| Pricer / scenario tool | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/widget_tool.md", "context/modules/static/tools/dashboards/widgets.md"], mode="full")` |
| "Show me a worked pattern" | `list_ai_repo(file_paths=["context/modules/static/tools/dashboards/recipes.md"], mode="full")` |

Each spoke is well under the 20 KB warning threshold (largest is `widgets.md` at ~12 KB). Fetch only the spokes you need; avoid fetching all five preemptively — that defeats the hub-spoke purpose.

The Catalog index above is enough to PICK a chart type / widget / filter type. Fetch a spoke when you need the per-primitive mapping rules / required keys / cosmetic knobs.

---

## 4. Layouts (grid + tabs)

```python
# Grid (default, simple)
"layout": {"kind": "grid", "cols": 12, "rows": [
    [widget, widget, ...],     # rows of widgets; widths must sum to <= cols
    [widget, ...]]}

# Tabs
"layout": {"kind": "tabs", "cols": 12, "tabs": [
    {"id": "overview", "label": "Overview",
      "description": "Short summary shown under the tab title",
      "rows": [...]},
    {"id": "detail", "label": "Detail", "rows": [...]}]}
```

Tabs lazily initialise charts on first activation; last-active tab persisted in `localStorage` per dashboard id.

| Tab field | Purpose |
|-----------|---------|
| `id` (req) | Stable slug used in DOM ids and localStorage keys |
| `label` | Visible tab text |
| `description` | (1) Italic secondary text below tab bar when active, (2) hover tooltip on the tab button |
| `rows` | List-of-lists of widgets |

### 4.1 Chart widths — never full-width

A chart widget (`widget: "chart"`) must never span the full grid (`w: 12` on a 12-col layout). Full-width charts stretch the plotting area horizontally to a degree no economic series rewards: a 1500px-wide line chart of 6 months of daily data hands the eye a flat ribbon of slope-zero white space rather than a shape. They also crowd out the side-by-side comparison framing the rest of the dashboard depends on, leaving the reader with one panel where there should be two.

The canonical widths are:

| Layout | Per-chart `w` | Use |
|--------|---------------|-----|
| 2-up   | `6`           | Default for most pairs (price + carry, level + change, primary + benchmark) |
| 3-up   | `4`           | Tile rows of comparable single-metric charts (sectors, regions, tenors) |
| 4-up   | `3`           | Dense small-multiples (every G10 currency, every UST tenor) |
| 1-up unbalanced | `8` + `4` companion | Headline chart paired with a stat strip / table / note that earns the rest of the row |

The rule applies to chart widgets only. KPI rows, tables, markdown banners, image headers, `note` widgets, and dividers may span `w: 12` — they are not lossy at full width. The `_audit_dashboard_layout` audit does not enforce this today; it is an aesthetic rule the author owns.

If the row has only one chart-class widget, pair it with the natural companion: a small `stat_grid`, a `provenance_note`, a `markdown` annotation, a `note` widget, or a `kpi` strip. If you cannot find a companion, the row is signalling that the chart is doing too much by itself — split into two charts (e.g. level + change, nominal + real, US + cross-country) and run them 2-up.

---

## 5. Header actions

Optional `manifest.header_actions[]` appends custom buttons / links to the header (left of the always-on chrome — Methodology / Refresh / Share / Download — described in §2.3.1). Use for dashboard-specific escape hatches.

| Key | Purpose |
|-----|---------|
| `label` (req) | Display text |
| `href` | If set, renders `<a>` (opens in new tab by default) |
| `onclick` | Name of a global JS function. One of `href` / `onclick` is required |
| `target` | `"_self"` to open inline (defaults to `_blank`) |
| `id` | Optional DOM id. Cannot collide with a reserved chrome id (`refresh-btn`, `share-btn`, `download-btn`, `download-menu`, `methodology-btn`, `theme-toggle`, `export-all`, `export-dashboard`, `export-excel`, `data-as-of`, `data-as-of-val`, `header-actions`). The validator rejects collisions because a custom action with one of these ids would silently shadow the live chrome at runtime |
| `primary` | `True` → GS Navy primary button styling |
| `icon` | Optional leading glyph |
| `title` | Hover tooltip |

---

## 6. Persistence + refresh (the build flow)

For browser-side refresh failure modal / runner internals / registry schema see `prism/dashboard-refresh.md`. This section is purely about the PRISM-side build flow.

**Atomicity contract (Rule 7).** Tools 1, 2, and 3 below are non-divisible. PRISM runs them in a single uninterrupted sequence and surfaces nothing to the user until Tool 3 has completed cleanly. There is no in-session "preview" of a half-built dashboard — every artefact below must be on S3 and both audits must pass before any user-facing message:

| Artefact / state                                                          | Created in | Audited by                              |
|---------------------------------------------------------------------------|------------|-----------------------------------------|
| `scripts/pull_data.py` persisted                                          | Tool 1     | `_audit_dashboard_layout` (§2.5)        |
| `data/<key>.csv` (one per `manifest.datasets` key) on S3                  | Tool 1     | `_audit_dashboard_layout` (§2.5)        |
| `manifest_template.json` persisted                                        | Tool 2     | `_audit_dashboard_layout` (§2.5)        |
| `manifest.json` + `dashboard.html` on S3                                  | Tool 2     | `_audit_dashboard_layout` (§2.5)        |
| `scripts/build.py` persisted                                              | Tool 2     | `_audit_dashboard_layout` (§2.5)        |
| Entry appended into `registry["dashboards"][]` (NOT a top-level key)      | Tool 3     | `_audit_registry_state` (§6.1 Tool 3)   |
| `update_user_manifest(kerberos, artifact_type='dashboard')` ran           | Tool 3     | `_audit_registry_state` (§6.1 Tool 3)   |

**User-facing message contract.** The first line PRISM emits to the user after Tool 3 leads with the portal URL (Rule 6). The shape:

```
<dashboard_id> live at http://reports.prism-ai.url.gs.com:8501/profile/dashboards/<dashboard_id>/
- Refresh: <frequency>; first refresh: <ISO timestamp the cron will pick it up>
- Datasets: <comma-separated manifest.datasets keys>
```

A short narrative sentence about what's in the dashboard is fine after that block. **Forbidden phrases** (each implies the build has opt-in phases — there are none):

- "Next steps:" / "To make this fully persistent…" / "to auto-refresh this dashboard…"
- "Would you like me to register / set up refresh / persist the scripts?"
- "I can also create `pull_data.py` and `build.py`…"
- Any prompt that asks the user to choose between "preview" and "production" for a dashboard. The dashboard is production by Tool 3; there is no other state.

If Tool 1 or Tool 2 raises, surface the failure verbatim — not a rendered preview gated behind a registration question.

**Pacing across slices (Rule 8).** The atomicity contract above governs ONE slice. Complex requests turn into multiple slices, each its own complete pass through Tools 1 → 2 → 3. After surfacing the URL for slice N, PRISM stops and asks "want me to add [specific next chunk]?" — that question is REQUIRED post-Tool-3, not forbidden. The forbidden phrases above are specifically about "would you like me to register" mid-build (papering over a failure), not "want me to add the next tab now" between completed slices.

### 6.1 Three-tool-call build model

```
Tool 1: pull_data.py   Author pull_data.py as a string, persist to
                       {DASHBOARD_PATH}/scripts/pull_data.py, then exec FROM S3
                       with the refresh-runner namespace. The exec writes
                       raw CSVs to {DASHBOARD_PATH}/data/. Read CSVs back
                       to verify shapes/heads/dtypes for Tool 2.
Tool 2: build.py       Compose the initial manifest (with embedded data, just
                       to derive the template), persist
                       {DASHBOARD_PATH}/manifest_template.json, author
                       build.py as a string, persist to
                       {DASHBOARD_PATH}/scripts/build.py, then exec build.py
                       FROM S3. The exec writes manifest.json + dashboard.html.
Tool 3: register       Load dashboards_registry.json (seed if missing),
                       append/replace entry by id in registry['dashboards']
                       (NOT as a top-level key — runner only iterates the
                       list), save, verify by re-load, then call
                       update_user_manifest(kerberos, artifact_type='dashboard')
                       and print portal URL.
```

**The persisted script is the source of truth — write it first, then run it from S3.** PRISM authors each script as a Python string, `s3_manager.put`s it to `{DASHBOARD_PATH}/scripts/<name>.py`, then `s3_manager.get`s it back and runs it via `exec(compile(src, ...), ns)` with the same namespace shape the refresh runner uses. The pull happens once (inside Tool 1's exec); the compile happens once (inside Tool 2's exec); build-time and refresh-time are byte-identical.

If Tool 1's verify lines print and Tool 2 ends with `[Tool 2] complete`, the refresh pipeline is provably stable: build-time and refresh-time run the same bytes from the same S3 path with the same helpers. There is no separate verification step. Iterate on the script string + re-run until both succeed end-to-end.

**Anti-pattern:** PRISM pulls data in-session via `pull_market_data(...)`, composes a manifest, calls `compile_dashboard(...)` in-session, *then* writes `pull_data.py` / `build.py` strings as an afterthought. The in-session execution and the on-S3 scripts are two different things; only the in-session one has been exercised. Fix: write the script first, exec it from S3.

#### Tool 1 — author + persist + exec `pull_data.py` FROM S3

```python
DASHBOARD_PATH = f"users/{KERBEROS}/dashboards/{DASHBOARD_NAME}"

# Author pull_data.py as a string. Refresh runner re-execs these exact bytes daily.
# Every pull function call passes output_path=f'{SESSION_PATH}/data' (Rule 5).
pull_data_py = '''
"""pull_data.py -- daily refresh of rates monitor data."""
from datetime import datetime
print(f"[pull_data.py] starting at {datetime.now().isoformat()}")

# name='rates' (no _eod suffix); pull_market_data appends it.
# On-disk: {SESSION_PATH}/data/rates_eod.csv + {SESSION_PATH}/data/rates_metadata.json
pull_market_data(
    coordinates=['IR_USD_Swap_2Y_Rate', 'IR_USD_Swap_10Y_Rate'],
    start='2020-01-01', name='rates', mode='eod',
    output_path=f'{SESSION_PATH}/data',
)
print("[pull_data.py] done")
'''.lstrip()

s3_manager.put(pull_data_py.encode(), f'{DASHBOARD_PATH}/scripts/pull_data.py')

# Exec FROM S3 with the refresh-runner namespace
import io as _io
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/pull_data.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': _io, 'json': json, 'os': os, 'datetime': datetime,
    's3_manager': s3_manager,
    'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'pull_haver_data':   pull_haver_data,
    'pull_market_data':  pull_market_data,
    'pull_plottool_data': pull_plottool_data,
    'pull_fred_data':    pull_fred_data,
    'save_artifact':     save_artifact,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/pull_data.py', 'exec'), ns)

# Verify by reading the CSVs back from S3 -- same path build.py will read tomorrow
df = pd.read_csv(_io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
print(f'[verify] rates_eod: shape={df.shape}'); print(df.head()); print(df.dtypes)
```

#### Tool 2 — author + persist + exec `build.py` FROM S3

**Five non-negotiables for the persisted `build.py`** — every one of these has been observed as a real PRISM-authored bug that shipped a known-broken dashboard:

1. `compile_dashboard(..., strict=True)` — explicit, no `strict=False`. `strict=False` is a discovery-mode tool for in-session iteration; the refresh runner re-execs `build.py` every day and `strict=False` ships broken artifacts with `(no data)` placeholder cards. The compiler additionally hard-fails a load-bearing allow-list of error codes (missing column, empty dataset, KPI source unresolvable, table column missing, filter field missing, builder exception) regardless of `strict`, so a `strict=False` build script will still raise on the failure modes that matter — but the SSOT is `strict=True`.
2. **No `try/except` around `compile_dashboard()`.** A swallowed `ValueError` silently re-uploads stale HTML or, worse, no HTML at all while the refresh runner records `status="success"`. Let exceptions propagate.
3. `if not r.success: raise ValueError(...)` — never `print()` and continue, never write `r.html` past the failure check.
4. **Every CSV gets renamed to plain English (Rule 1) BEFORE handing it to `populate_template`.** Loading `next_meeting_probs.csv` whose columns are Haver codes (`PFNP@DAILY`, ...) and feeding it straight into a manifest whose chart spec maps `mapping.x="outcome"` is the canonical failure mode. The rename step is non-optional even when there are 5+ datasets in the dashboard.
5. **Use `compile_dashboard()` directly (the dict-based API), NOT `Dashboard(...)` + `.build()`.** The OOP class-builder bypasses `chart_data_diagnostics` entirely; column-mapping mistakes silently fall through to `(no data)` placeholders.

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{DASHBOARD_PATH}/data/rates_eod.csv')),
                  index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']      # plain English (Rule 1)

# Compose initial manifest (with embedded data) just to derive the template.
# Dataset key 'rates_eod' matches the on-disk CSV stem (Rule 5).
initial_manifest = {
    "schema_version": 1, "id": DASHBOARD_NAME, "title": "Rates Monitor",
    "metadata": {
        "kerberos":     KERBEROS,
        "dashboard_id": DASHBOARD_NAME,
        "methodology": (
            "## Sources\n* GS Market Data: 2Y + 10Y USD swap rates (EOD)\n"
            "## Construction\n* Daily close pulled via pull_market_data; "
            "no transforms before charting"
        ),
        "data_as_of":        str(df.index.max().date()),
        "generated_at":      datetime.now(timezone.utc).isoformat(),
        "sources":           ["GS Market Data"],
        "refresh_frequency": "daily",
        "tags":              ["rates"],
    },
    "datasets": {"rates_eod": df.reset_index()},
    "layout": {"rows": [[
        {"widget": "chart", "id": "curve_lvl", "w": 6, "title": "UST Curve — level",
          "spec": {"chart_type": "multi_line", "dataset": "rates_eod",
                    "mapping": {"x": "date", "y": ["us_2y", "us_10y"],
                                "y_title": "Yield (%)"}}},
        {"widget": "chart", "id": "curve_2s10s", "w": 6, "title": "2s10s spread",
          "spec": {"chart_type": "line", "dataset": "rates_eod_diff",
                    "mapping": {"x": "date", "y": "spread",
                                "y_title": "2s10s (bp)"}}},
    ]]}
}

tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Author build.py as a string (~12 lines: load template + load CSVs + populate + compile + upload).
# Refresh runner re-execs this daily.
build_py = '''import io, json, pandas as pd
from datetime import datetime, timezone

tpl = json.loads(s3_manager.get(f"{SESSION_PATH}/manifest_template.json"))
df = pd.read_csv(io.BytesIO(s3_manager.get(f"{SESSION_PATH}/data/rates_eod.csv")),
                  index_col=0, parse_dates=True)
df.columns = ["us_2y", "us_10y"]
m = populate_template(tpl, {"rates_eod": df.reset_index()},
                       metadata={"data_as_of": str(df.index.max().date()),
                                  "generated_at": datetime.now(timezone.utc).isoformat()},
                       require_all_slots=True)
r = compile_dashboard(m, write_html=False, write_json=False, strict=True)
if not r.success:
    raise ValueError(f"compile failed: {r.error_message}")
s3_manager.put(r.html.encode("utf-8"), f"{SESSION_PATH}/dashboard.html")
s3_manager.put(json.dumps(m, indent=2).encode("utf-8"), f"{SESSION_PATH}/manifest.json")
print("[build.py] success")
'''
s3_manager.put(build_py.encode(), f'{DASHBOARD_PATH}/scripts/build.py')

# Exec build.py FROM S3 with refresh-runner namespace
src = s3_manager.get(f'{DASHBOARD_PATH}/scripts/build.py').decode('utf-8')
ns = {
    'pd': pd, 'np': np, 'io': io, 'json': json, 'os': os,
    'datetime': datetime, 'timezone': timezone,
    's3_manager': s3_manager, 'SESSION_PATH': DASHBOARD_PATH.rstrip('/'),
    'compile_dashboard': compile_dashboard,
    'populate_template': populate_template,
    'manifest_template': manifest_template,
    'validate_manifest': validate_manifest,
}
exec(compile(src, f'{DASHBOARD_PATH}/scripts/build.py', 'exec'), ns)

# Folder sanctity audit (§2.5): raises on missing required OR rogue paths.
# Author _audit_dashboard_layout() inline as shown in §2.5.1.
m = json.loads(s3_manager.get(f'{DASHBOARD_PATH}/manifest.json').decode('utf-8'))
_audit_dashboard_layout(DASHBOARD_PATH, m)
print('[Tool 2] complete; ready for Tool 3 (register)')
```

#### Tool 3 — register

**There is no `register_dashboard()` helper.** Neither the sandbox nor the refresh runner injects a registry-writing function — Tool 3 hand-rolls a load → list-append → save → pointer-update from scratch. The hourly refresh runner iterates `registry["dashboards"]`; a top-level-keyed entry (`registry[DASHBOARD_NAME] = {...}`) is invisible to it, returns 404 on every refresh, and never produces a `refresh_status.json`. Schema reference for the field shapes lives in `prism/dashboard-refresh.md` §6; the only fields a builder owns are below — `last_refreshed` and `last_refresh_status` are runner-owned and stay `null` until the first real refresh.

```python
import json
from datetime import datetime, timezone

REGISTRY_PATH = f'users/{KERBEROS}/dashboards/dashboards_registry.json'
PORTAL_URL    = f'http://reports.prism-ai.url.gs.com:8501/profile/dashboards/{DASHBOARD_NAME}/'

now_iso = datetime.now(timezone.utc).isoformat()

try:
    registry = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b'\x00').decode('utf-8'))
except Exception:
    registry = {'dashboards': [], 'last_updated': now_iso}

if 'dashboards' not in registry or not isinstance(registry['dashboards'], list):
    registry['dashboards'] = []

new_entry = {
    'id':                  DASHBOARD_NAME,
    'name':                'Rates Monitor',
    'description':         'Daily monitor of the US rates curve.',
    'created_at':          now_iso,
    'last_refreshed':      None,
    'last_refresh_status': None,
    'refresh_enabled':     True,
    'refresh_frequency':   'daily',
    'folder':              DASHBOARD_PATH,
    'html_path':           f'{DASHBOARD_PATH}/dashboard.html',
    'data_path':           f'{DASHBOARD_PATH}/data',
    'tags':                ['rates'],
    'keep_history':        False,
}

existing_ids = [d.get('id') for d in registry['dashboards']]
if DASHBOARD_NAME in existing_ids:
    idx = existing_ids.index(DASHBOARD_NAME)
    new_entry['created_at'] = registry['dashboards'][idx].get('created_at', now_iso)
    registry['dashboards'][idx] = new_entry
else:
    registry['dashboards'].append(new_entry)

registry['last_updated'] = now_iso
s3_manager.put(json.dumps(registry, indent=2).encode('utf-8'), REGISTRY_PATH)

verify = json.loads(s3_manager.get(REGISTRY_PATH).rstrip(b'\x00').decode('utf-8'))
if DASHBOARD_NAME not in [d.get('id') for d in verify.get('dashboards', [])]:
    raise RuntimeError(f'[Tool 3] {DASHBOARD_NAME} not in registry["dashboards"] after write')

update_user_manifest(KERBEROS, artifact_type='dashboard')

# Rule 7 audit: registry state is consistent and discoverable.
# Author inline; no helper is injected. Pairs with _audit_dashboard_layout (§2.5)
# from Tool 2 — together they verify every artefact in the §6 atomicity table.
def _audit_registry_state(kerberos, dashboard_id):
    """Confirm the dashboard is registered AND visible to the runner. Raises if not."""
    reg = json.loads(s3_manager.get(
        f'users/{kerberos}/dashboards/dashboards_registry.json'
    ).rstrip(b'\x00').decode('utf-8'))
    ids_in_list = [d.get('id') for d in reg.get('dashboards', [])]
    if dashboard_id not in ids_in_list:
        raise RuntimeError(
            f'[registry] {dashboard_id} not in registry["dashboards"][]; '
            f'hourly runner cannot see it')
    if dashboard_id in reg and isinstance(reg.get(dashboard_id), dict):
        raise RuntimeError(
            f'[registry] {dashboard_id} written BOTH as top-level key AND in dashboards[]; '
            f'remove the top-level key (top-level-key footgun, §6.3 of dashboard-refresh.md)')
    man = json.loads(s3_manager.get(
        f'users/{kerberos}/manifest.json'
    ).rstrip(b'\x00').decode('utf-8'))
    pointer = man.get('pointers', {}).get('dashboards', {})
    if pointer.get('count', 0) < 1:
        raise RuntimeError(
            f'[manifest] users/{kerberos}/manifest.json pointers.dashboards.count=0; '
            f'update_user_manifest(...) was skipped or failed')
    if not pointer.get('registry_path', '').startswith(f'users/{kerberos}/'):
        raise RuntimeError(
            f'[manifest] pointers.dashboards.registry_path mis-points; '
            f'expected users/{kerberos}/...')

_audit_registry_state(KERBEROS, DASHBOARD_NAME)

# User-facing success message (§6 contract). Lead with the portal URL on line 1;
# refresh frequency + datasets on the next two lines. Do NOT add "next steps",
# "would you like me to...", or any opt-in language (Rule 7).
DATASETS = ', '.join(json.loads(
    s3_manager.get(f'{DASHBOARD_PATH}/manifest.json').decode('utf-8')
).get('datasets', {}).keys())
print(f'{DASHBOARD_NAME} live at {PORTAL_URL}')
print(f'- Refresh: daily (next cron tick picks it up; on-demand via [Refresh] button)')
print(f'- Datasets: {DATASETS}')
```

Path conventions (verified against live registries): paths have **no leading slash** (`users/...`, not `/users/...`); `folder` has **no trailing slash**; `data_path` is the **`data/` directory**, not `manifest.json`. `data_path` is optional but the portal uses it to surface the dashboard's data folder, so set it.

**Anti-pattern.** Do NOT write the new entry as a top-level key:

```python
# BROKEN — runner ignores this entry, refresh returns 404 forever
registry[DASHBOARD_NAME] = new_entry
s3_manager.put(json.dumps(registry).encode(), REGISTRY_PATH)
```

The resulting registry looks structurally fine (`{"dashboards": [], "last_updated": "...", "<id>": {...}}`) but the dashboard is invisible to `jobs/hourly/refresh_dashboards.py`, which iterates `registry["dashboards"]` only. Two real dashboards (`rates_fx_corr`, `bond_carry_roll`) hit this on 2026-04-27 and required hand-repair. The verify-by-re-load step in the canonical Tool 3 above catches this immediately.

**`update_user_manifest` is NOT a registry-write step.** It only updates `users/{kerberos}/manifest.json`'s `pointers.dashboards` block (count, active_count, last_refreshed, registry_path). It reads the registry to compute those numbers but never writes the registry. The registry must already be saved on S3 with the new entry appended into `dashboards[]` before this call — which is why the canonical Tool 3 runs the put → verify → `update_user_manifest` sequence in that order.

### 6.2 Pull primitives + `save_artifact` cheat sheet

Inside `pull_data.py` they all land their CSVs in the same flat folder by passing `output_path=f'{SESSION_PATH}/data'`. At refresh time the runner injects `SESSION_PATH = {DASHBOARD_PATH}` so the same string resolves to the same S3 folder both at build time and refresh time. There is no separate `DASHBOARD_PATH` reference inside `pull_data.py`.

| Function | Call | On-disk CSV | Metadata sidecar | Manifest key |
|---|---|---|---|---|
| `pull_haver_data` | `pull_haver_data(codes=[...], start='YYYY-MM-DD', name='cpi', output_path=f'{SESSION_PATH}/data')` | `data/cpi.csv` | `data/cpi_metadata.json` | `'cpi'` |
| `pull_market_data` (eod) | `pull_market_data(coordinates=[...], start='YYYY-MM-DD', name='rates', mode='eod', output_path=f'{SESSION_PATH}/data')` | `data/rates_eod.csv` (always `_eod` suffix) | `data/rates_metadata.json` (no suffix) | `'rates_eod'` |
| `pull_market_data` (intraday) | same but `mode='iday'` | `data/rates_intraday.csv` | `data/rates_metadata.json` | `'rates_intraday'` |
| `pull_plottool_data` | `pull_plottool_data(expressions=[...], labels=[...], start='YYYY-MM-DD', name='swap_curve', output_path=f'{SESSION_PATH}/data')` | `data/swap_curve.csv` | `data/swap_curve_metadata.json` | `'swap_curve'` |
| `pull_fred_data` | `pull_fred_data(series=[...], start='YYYY-MM-DD', name='unrate', output_path=f'{SESSION_PATH}/data')` | `data/unrate.csv` | `data/unrate_metadata.json` | `'unrate'` |
| `save_artifact` | `save_artifact(data, name='gs_bank', output_path=f'{SESSION_PATH}/data')` | `data/gs_bank.csv` (or `.json` if dict) | none | `'gs_bank'` |

Three rules from the table that are easy to get wrong:

1. **`name=` does NOT include `_eod` / `_intraday`.** `pull_market_data` appends them. Pass `name='rates'` → `data/rates_eod.csv`. Pass `name='rates_eod'` → `data/rates_eod_eod.csv` (broken).
2. **`pull_market_data` metadata sidecar uses the bare `name`,** not the suffixed CSV stem. So `name='rates'` produces `data/rates_metadata.json` (one file even when both eod and intraday CSVs exist).
3. **`mode='eod'` is the default** but pass it explicitly. The intraday CSV is only written when `mode in ('iday', 'both')`. See §6.4 for the defensive try/except wrap.

#### Reading the CSVs back in `build.py`

```python
import io
df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_eod.csv')),
                 index_col=0, parse_dates=True)
df.columns = ['us_2y', 'us_10y']        # rename to plain English (Rule 1)
```

The path `{SESSION_PATH}/data/rates_eod.csv` is byte-identical to what `pull_data.py` wrote because both scripts reference `SESSION_PATH`, which the refresh runner pins to `{DASHBOARD_PATH}` for both execs. The dataset key (`rates_eod`) matches the CSV stem; `populate_template` maps the cleaned DataFrame back into the template by that key.

#### `save_artifact()` for alternative data sources

The four pull primitives only cover Haver / GS Market Data / TSDB expressions / FRED. For everything else (FDIC, SEC EDGAR, BIS, Treasury, Treasury Direct, NY Fed, prediction markets, OpenFIGI, Substack, Wikipedia, Pure / Alloy, scraped tables, hand-built DataFrames), `save_artifact()` is the universal save helper. Same `output_path` semantics; lands a CSV (or JSON for `dict` payloads) at `{output_path}/{name}.{ext}` and is idempotent on re-run.

```python
# inside pull_data.py
fdic_records = fdic_client.get_bank_financials(cert=33124, quarters=8)
save_artifact(fdic_records, name='gs_bank', output_path=f'{SESSION_PATH}/data')
# -> {SESSION_PATH}/data/gs_bank.csv

sec_data = sec_edgar_client.cmd_company_financials('AAPL', 'default')
save_artifact(sec_data, name='aapl_financials', output_path=f'{SESSION_PATH}/data')
# dict -> {SESSION_PATH}/data/aapl_financials.json (build.py reads json.loads(...))

ny_df = pull_nyfed_data('rates')   # not auto-saving; returns a DataFrame
save_artifact(ny_df, name='nyfed_rates', output_path=f'{SESSION_PATH}/data')
```

`save_artifact()`'s output extension follows the input: DataFrame / `list[dict]` / object-with-`.to_frame()` → CSV; `dict` (or empty list) → JSON. `build.py` reads JSON via `json.loads(s3_manager.get(...).decode('utf-8'))` and converts to a DataFrame at populate time.

### 6.3 Templates: `manifest_template` + `populate_template`

Auto-injected into both the `execute_analysis_script` sandbox and the refresh-runner namespace; no import needed.

```python
# One-time: strip data rows, keep column headers + every other config
tpl = manifest_template(initial_manifest)
s3_manager.put(json.dumps(tpl, indent=2).encode(),
                f'{DASHBOARD_PATH}/manifest_template.json')

# Each refresh: fresh DataFrames wired into template slots
m = populate_template(tpl, {"rates": eod_df, "cpi": cpi_df},
                         metadata={"data_as_of": "..."},
                         require_all_slots=True)
compile_dashboard(m, output_path=f'{DASHBOARD_PATH}/dashboard.html')
```

Template is pure JSON (no pandas); safe to persist and diff. `require_all_slots=True` raises `KeyError` if a template slot has no DataFrame.

### 6.4 Intraday data robustness

Intraday data is unavailable overnight / weekends / holidays. Every `pull_data.py` that fetches intraday MUST wrap it in `try/except` with EOD fallback. Every `build.py` must handle missing intraday file defensively.

```python
# pull_data.py
pull_market_data(
    coordinates=[...], start='2020-01-01',
    name='rates', mode='eod', output_path=f'{SESSION_PATH}/data')
try:
    pull_market_data(
        coordinates=[...], mode='iday',
        start=datetime.now().strftime('%Y-%m-%d'),
        name='rates', output_path=f'{SESSION_PATH}/data')
except Exception as e:
    print(f"Intraday unavailable (normal overnight/weekends): {e}")

# build.py
eod_df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_eod.csv')),
                      index_col=0, parse_dates=True)
try:
    iday_df = pd.read_csv(io.BytesIO(s3_manager.get(f'{SESSION_PATH}/data/rates_intraday.csv')),
                          index_col=0, parse_dates=True)
except Exception:
    iday_df = None
current = (iday_df.ffill().iloc[-1] if iday_df is not None and len(iday_df) > 0
           else eod_df.iloc[-1])
```

Both `pull_market_data` calls share `name='rates'`, so the metadata sidecar (`rates_metadata.json`) is written / overwritten by whichever call wrote last — both calls describe the same coordinates, so a single sidecar is correct.

The same `multi_line` chart spec works for daily EOD and intraday minute-bar data — no special manifest configuration. Compact / sparkline-shaped intraday tiles can drop the slider via `spec.chart_zoom = {"slider": false}` to reclaim ~28px (`dashboards/filters.md` §3).

### 6.5 Refresh-runner namespace gap

The refresh runner's `_build_exec_namespace` injects `pd`, `np`, `io`, `json`, `os`, `datetime`, `s3_manager`, `SESSION_PATH`, the four pull primitives, `compile_dashboard`, `populate_template`, `manifest_template`, `validate_manifest`. As of 2026-04-27, it does NOT inject `save_artifact`, `pull_nyfed_data`, `pull_pure_data`, `pull_stacked_data`, or any of the alt-data clients (`fdic_client`, `sec_edgar_client`, `bis_client`, `treasury_client`, `treasury_direct_client`, `nyfed_client`, `prediction_markets_client`, `openfigi_client`, `substack_client`, `wikipedia_client`, Coalition / Inquiry helpers).

Consequence: a `pull_data.py` using any of those builds cleanly during the in-session Tool 1 exec (the build-time exec runs in the sandbox, where they ARE injected) but the daily refresh raises `NameError`.

Behaviour when the gap fires:

- **Single-source dashboards using only the four pull primitives** refresh cleanly with no caveat.
- **Multi-source dashboards needing alt-data** are still buildable; the always-on `Refresh` button still renders (there is no manifest opt-out), and the daily/hourly runner attempt produces a `runner_error` with the offending name. The user clicks `Refresh`, the structured error modal pops with the full `NameError`, and the "Copy markdown for PRISM" button hands the failure back for triage. Until the runner namespace expands, set `refresh_frequency: "manual"` on the registry entry to suppress the cron attempt; keep the manifest as-is so the manual refresh remains one click away.

Structural fix is PRISM-side: extend `_build_exec_namespace` to mirror the `execute_analysis_script` sandbox's data-retrieval bundle. Tracked in `prism/_changelog.md`.

---

## 7. Sandbox patterns

`compile_dashboard`, `manifest_template`, `populate_template`, `validate_manifest`, `df_to_source`, `chart_data_diagnostics`, `load_manifest`, `save_manifest` are auto-injected into both `execute_analysis_script` and the refresh-runner namespace. Never write `from echart_dashboard import ...` or `sys.path.insert(0, ...)`.

In the sandbox, `compile_dashboard` writes to local FS if `output_path` is given — which is blocked by the AST checks. For persistent user dashboards, the right pattern is `write_html=False, write_json=False` and `s3_manager.put()` manually so the artifact lands at `{DASHBOARD_PATH}/dashboard.html` rather than the compiler's default `{session_path}/dashboards/{id}.html`:

```python
r = compile_dashboard(manifest, write_html=False, write_json=False, strict=True)
if not r.success: raise ValueError(f"COMPILE FAILED: {r.error_message}")
s3_manager.put(r.html.encode('utf-8'), f'{DASHBOARD_PATH}/dashboard.html')
s3_manager.put(json.dumps(manifest, indent=2).encode('utf-8'),
                f'{DASHBOARD_PATH}/manifest.json')
```

---

## 8. Palettes

| Palette | Kind | Use |
|---------|------|-----|
| `gs_primary` | categorical | Default (navy, sky, gold, burgundy, …) |
| `gs_blues` | sequential | Heatmaps, calendar heatmaps, gradients |
| `gs_diverging` | diverging | Correlation matrices, z-score heatmaps |

Categorical → `option.color`. Sequential / diverging → `visualMap.inRange.color` (heatmaps, correlation matrices).

Brand hex anchors for `series_colors`: GS Navy `#002F6C`, GS Sky `#7399C6`, GS Gold `#B08D3F`, GS Burgundy `#8C1D40`, GS Forest `#3E7C17`, GS Positive `#2E7D32`, GS Negative `#B3261E`.

---

## 9. Anti-patterns

**Data integrity:**

| Anti-pattern | Do instead |
|--------------|-----------|
| `np.random.*` / `np.linspace` / `np.arange` / hand-typed arrays as data; `np.zeros()` fill for missing values | Pull real data first (§6.1). If no source, don't build the panel; render a note or use a small real slice |
| Authoring `build.py` before `pull_data.py` produced real DataFrames | Run pulls first, print shapes / heads / dtypes, write manifest against verified columns |
| Literal numbers in manifest JSON | Pass the DataFrame; compiler converts |
| PRISM hand-writing HTML / CSS / JS, or `build.py` >50 lines | Emit manifest; `compile_dashboard()` does the rest |
| Source attribution in title / subtitle | `metadata.sources` for dashboard-level; `field_provenance` per-column (`dashboards/widgets.md` §4) |
| Dropping provenance because vendor isn't standard | `system: "computed"` + `recipe`, or `system: "csv"` + path. Never drop |
| Annotating self-evident facts (zero on a spread) | Omit |
| Hand-tuning `y_title_gap` / `grid.left` | Just set `x_title` / `y_title`; compiler sizes from real label widths |

**Atomicity of the build flow (Rule 7):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Returning to the user with "Next steps: I can now create `pull_data.py` and `build.py`, register the dashboard, set up daily refresh — would you like me to continue?" after `compile_dashboard()` produced an in-session HTML | Rule 7 violation: there are no "next steps" — Tools 1+2+3 are atomic. The dashboard does not exist as a deliverable until scripts are persisted, the registry entry sits in `dashboards[]`, the user-manifest pointer reflects it, and both audits pass (§6 atomicity table). Run all three tools without returning to the user; only the post-Tool-3 portal URL is user-facing |
| Compiling in-session, surfacing the rendered HTML to the user, then deferring `scripts/pull_data.py` / `scripts/build.py` / registry write to a follow-up turn | The in-session compile and the on-S3 build are two different code paths. Without scripts on S3, the [Refresh] button raises `FileNotFoundError`, the hourly cron skips the unregistered dashboard, and tomorrow's data never arrives. Author the scripts FIRST (Tool 1 + Tool 2 §6.1), exec from S3, then register (Tool 3) — the in-session render is a side-effect of Tool 2, not the deliverable |
| Asking the user to choose between a "preview" / "session-only" version and a "persistent" / "production" version of a dashboard | There is no preview state. A dashboard is either fully built (Tools 1+2+3 ran, both audits passed) or it does not exist. Conversational session-only manifests (§2.2 `{SESSION_PATH}/dashboards/{id}.json`) are a separate artefact class; they are not user-visible "preview dashboards" with a registration upgrade path |
| Treating a missing `scripts/`, registry entry, or manifest pointer as a separable concern the user can opt into | All three are part of the build. The audits (`_audit_dashboard_layout` §2.5, `_audit_registry_state` §6.1 Tool 3) are the gate that defines "built"; if either raises, the build is not complete and nothing is surfaced to the user |
| Phrasing user-facing messages with "to make this fully persistent" / "would you like me to set up auto-refresh" / "I can also build pull_data and build.py" | Forbidden language (§6 user-facing message contract). Each phrase implies the build has opt-in phases. Strip the phrase; the only message after a successful Tool 3 is the portal URL block in §6 |

**Persistence + the build flow:**

| Anti-pattern | Do instead |
|--------------|-----------|
| Persisting `scripts/build.py` with `compile_dashboard(..., strict=False)` | `strict=True` is the SSOT for the persisted build script. `strict=False` is for in-session iteration only and has been observed shipping `(no data)` placeholder cards as `last_refresh_status="success"`. The compiler also hard-fails a load-bearing allow-list (`ALWAYS_BLOCKING_ERROR_CODES`) regardless of `strict`, so even the deviant case raises on the failures that matter — but the SSOT is `strict=True` |
| Wrapping `compile_dashboard()` in `try/except` so the build "succeeds" past validation failures | Let the `ValueError` propagate. The refresh runner catches it, records `last_refresh_status="error"`, and the structured error modal surfaces the diagnostic to the user |
| Loading CSV files into `populate_template` without renaming columns to plain English (Rule 1) | Every `pd.read_csv(...)` is followed by a `df.columns = [...]` rename. Vendor-native column names (Haver codes like `PFNP@DAILY`, market-data coordinate names like `IR_USD_FOMCJump_30Apr2026_Rate`) into a manifest with chart specs that map `mapping.x="outcome"` / `mapping.x="meeting"` is the canonical failure mode |
| Building a dashboard via `Dashboard(...)` constructor + `.build()` (the OOP class-builder API) | Use the dict-based `compile_dashboard()` flow. `Dashboard.build()` skips `chart_data_diagnostics` entirely; column-mapping mistakes silently fall through to placeholder cards |
| Saving a user dashboard only to `SESSION_PATH`; skipping the refresh button by editing HTML | Persist to `users/{kerberos}/dashboards/...`; set `metadata.kerberos` + `dashboard_id` |
| Pulling data and/or compiling in-session, *then* writing scripts to S3 as an afterthought — two divergent code paths | Write the script to S3 first, `s3_manager.get` it back, `exec` it |
| Inlining data pull + manifest build into one tool call so neither `pull_data.py` nor `build.py` exist as standalone files | Use the three-tool model: Tool 1 persists+execs `pull_data.py`; Tool 2 persists+execs `build.py`; Tool 3 registers |
| Saving scripts to `SESSION_PATH/scripts/` instead of `{DASHBOARD_PATH}/scripts/` | Refresh runner only looks at `{DASHBOARD_PATH}/scripts/` |
| `registry[DASHBOARD_NAME] = entry` — writing the new dashboard as a TOP-LEVEL key in `dashboards_registry.json` | `registry['dashboards'].append(entry)` (or replace-by-id). The hourly refresh runner only iterates `registry['dashboards']`; a top-level-keyed entry is invisible → 404 → no `refresh_status.json`. There is no `register_dashboard()` helper; the canonical hand-rolled upsert lives in §6.1 Tool 3 |
| Treating `update_user_manifest(kerberos, artifact_type='dashboard')` as the registry-write step | It only updates `users/{kerberos}/manifest.json`'s pointer block. Save the registry with `s3_manager.put(...)` FIRST, then call the wrapper |
| Setting `last_refreshed` / `last_refresh_status` to the build timestamp at registration time | Leave both as `null` at registration; the refresh runner owns those fields and overwrites them on the first real refresh |
| Writing `history_retention_days` into the registry entry | Field is not part of the live schema (2026-04-27); treat as planned/unimplemented, do not write it |
| S3 paths with leading slash (`/users/...`) or `folder` with trailing slash | Live registry convention: no leading slash, no trailing slash on `folder`; `data_path` points to the `data/` directory, not `manifest.json` |

**Data routing (Rule 5 + `pull_*_data` quirks):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Calling any `pull_*_data` / `save_artifact` WITHOUT `output_path=f'{SESSION_PATH}/data'` | Always pass `output_path`. Otherwise CSVs land in per-source subfolders and `build.py`'s `data/<name>.csv` read raises `FileNotFoundError` on every refresh |
| Passing `name='rates_eod'` to `pull_market_data` (function appends another `_eod` → `data/rates_eod_eod.csv`) | Pass `name='rates'`. Sidecar uses the bare name (`data/rates_metadata.json`) |
| Hand-rolling `s3_manager.put(df.to_csv().encode(), ...)` for FDIC / SEC EDGAR / BIS / Treasury / NY Fed / scraper output | Use `save_artifact(data, name='...', output_path=f'{SESSION_PATH}/data')`. Polymorphic, idempotent |
| `manifest.datasets` keys NOT matching on-disk CSV stems (key `'rates'` while CSV is `data/rates_eod.csv`) | Make the dataset key the CSV stem byte-for-byte: `'rates_eod'`, `'rates_intraday'`, `'cpi'` |
| `pull_data.py` uses names the runner doesn't inject (`save_artifact`, alt-data clients) AND the registry entry is left at the default `refresh_frequency` | Restrict to the four pull primitives, OR set the registry entry's `refresh_frequency: "manual"` so the cron skips it until the runner namespace expands (§6.5). The browser's `Refresh` button stays available either way; failed clicks surface in the structured error modal |
| Setting `metadata.refresh_enabled = False` to hide the browser `Refresh` button | The field is retired — the button is non-suppressible from the manifest. Drop the field; rely on the structured error modal to surface failures |

**Layout aesthetics (§4.1):**

| Anti-pattern | Do instead |
|--------------|-----------|
| `widget: "chart"` with `w: 12` | Chart widgets are never full-width (§4.1). Drop to `w: 6` and pair with a companion chart, or `w: 8` paired with a `w: 4` stat strip / note / table. The horizontal stretch flattens slopes and wastes pixel budget the reader pays for in scroll distance |
| A single-chart row to "give the headline chart room to breathe" | Split the chart into two complementary views (level + change, nominal + real, US + cross-country, primary + benchmark) and place both `w: 6`. The two-up framing is the dashboard idiom; one-up is the wide-PNG idiom (use Altair's `make_chart` instead) |
| Three `w: 4` charts in a row where the middle one is conceptually different | Either move the odd-one-out to its own paired row, or pick a third companion that fits the trio. Mixed semantics within a tile row read as accidental rather than deliberate |
| Padding a row with empty `markdown` widgets to satisfy "at least 2 widgets" mechanically | The rule is about visual density, not widget count. If the only honest layout is one chart, ship a 2-up split of that chart; don't garnish a stretched chart with a placeholder paragraph |

**Folder sanctity (Rule 4 + §2.5):**

| Anti-pattern | Do instead |
|--------------|-----------|
| Leaving `scripts/build_v2.py` / `scripts/pull_data.bak` next to the canonical files "for reference" | Either it's the canonical file or it doesn't belong. Move references to `archive/<UTC>/` (§2.5.2). The runner cannot tell which of two `.py` files in `scripts/` is "real" |
| Renaming the canonical scripts to anything else (`scripts/main.py`, `scripts/refresh.py`, `scripts/build_dashboard.py`) | The runner reads `scripts/pull_data.py` and `scripts/build.py` exactly. No flexibility. Audit raises FileNotFoundError on the canonical name |
| Multiple manifest copies (`manifest.json` + `manifest_old.json` / `manifest_v2.json` / `manifest.20260424.json`) | Exactly one `manifest.json`. Quarantine the others to `archive/<UTC>/` |
| Per-source data subfolders (`data/haver/cpi.csv`, `data/market_data/rates_eod.csv`) | Flat `data/cpi.csv`, `data/rates_eod.csv`. Driven by `output_path=f'{SESSION_PATH}/data'` on every pull (Rule 5). Audit flags any `data/<subdir>/` |
| Self-suffix CSVs from the `pull_market_data` `name=` footgun (`data/rates_eod_eod.csv`) | Pass `name='rates'` (bare); the function appends `_eod`. The audit flags `rates_eod_eod` because no `manifest.datasets["rates_eod_eod"]` key exists to allow it |
| Manifest-orphan CSVs in `data/` (`data/old_dataset.csv` with no `manifest.datasets["old_dataset"]`) | Either register the key in `manifest.datasets` or quarantine the CSV. The audit's allowed-data set is derived from the manifest, so orphan CSVs raise |
| Scratch siblings at dashboard scope (`dashboard_results.md`, `_artifacts.json`, `notes.txt`, `README.md`) | Session-scope artefacts belong under `{SESSION_PATH}/`, not `{DASHBOARD_PATH}/`. The audit flags any non-canonical top-level path |
| Auto-deleting rogue files when the audit raises (`s3_manager.delete()` in a loop) | `s3_manager.move(...)` to `archive/<UTC>/` instead. Rogue files sometimes turn out to be the real artefact mis-named; archive is recoverable, delete is not (§2.5.2) |
| Inheriting an existing non-compliant dashboard and proceeding directly with the surface change the user asked for | Audit first. If it raises, surface to the user: "Folder violates §2.5 whitelist; cleanup-first protocol takes priority over the requested change." Cleanup, re-audit, then proceed (§2.5.3) |
| Suppressing the audit (commenting it out, wrapping in `try/except: pass`) because "the dashboard renders fine" | The audit catches refresh-time footguns that don't surface at build time. The compiler validates the manifest; the audit validates the **folder around** the manifest. Both are load-bearing |

---

## 10. Pre-flight checklist

**Folder layout (Rule 4 + §2.5).** Run the sanctity audit; it raises on any whitelist violation (missing required OR rogue paths):

```python
m = json.loads(s3_manager.get(f'{DASHBOARD_PATH}/manifest.json').decode('utf-8'))
_audit_dashboard_layout(DASHBOARD_PATH, m)   # §2.5.1
```

The audit covers everything the old hand-rolled `s3_manager.list()` loop did, plus exclusivity. Specifically it verifies:

- `dashboard.html` / `manifest.json` / `manifest_template.json` exist exactly once
- `scripts/pull_data.py` and `scripts/build.py` exist exactly once and are the only `.py` files under `scripts/`
- `data/<key>.csv` (or `.json`) exists for every `manifest.datasets` key, byte-for-byte; `pull_market_data` auto-appends `_eod` / `_intraday`
- `data/<bare>_metadata.json` sidecars allowed (where `bare` strips `_eod` / `_intraday`)
- No rogue paths anywhere — no `_v2`, no `_old`, no per-source `data/<source>/` subfolders, no scratch `.md` / `.json` siblings, no manifest-orphan CSVs

`refresh_status.json` is NOT a build-time artefact — the refresh runner writes it on first refresh attempt. The audit allows it as optional; do not pre-create it.

**Configuration:**

- `metadata.kerberos`, `metadata.dashboard_id`, and `metadata.methodology` all set (validator hard-rejects the build without them — they gate the always-on Methodology / Refresh / Share chrome buttons)
- `metadata.data_as_of` set; `refresh_frequency` set. The browser `Refresh` button is non-suppressible from the manifest; do NOT add `metadata.refresh_enabled` (retired field, silently ignored)
- Registry entry **appended into `registry['dashboards']`** (not written as a top-level key); verify by re-loading and asserting `DASHBOARD_NAME in [d['id'] for d in registry['dashboards']]`
- `update_user_manifest(kerberos, artifact_type='dashboard')` called AFTER the registry write succeeds (the wrapper updates the user manifest pointer block, it does not write the registry itself)

**Data integrity:**

- Every dataset traces to a real pull (Rule 1)
- Every `pull_*_data(...)` and `save_artifact(...)` passes `output_path=f'{SESSION_PATH}/data'` (Rule 5)
- Every `pull_market_data` `name=` is the bare base (no `_eod` / `_intraday`)
- Every `manifest.datasets` key matches the on-disk CSV stem byte-for-byte
- `pull_data.py` printed real shapes / heads / dtypes before `build.py` was authored; intraday handled defensively
- If `pull_data.py` uses `save_artifact` or any alt-data client, set the registry entry's `refresh_frequency: "manual"` until the runner namespace expands (§6.5). The browser `Refresh` button stays on regardless
- Datasets cleaned: `df.reset_index()` for DTI-keyed frames, plain English columns, no MultiIndex
- Every dataset backing a chart / table carries `field_provenance` (per-column `system` + `symbol`)
- Time-series pulls preserve full back-history (§11); never clip to the visible window

**Build mechanics:**

- Tool 1 authored as string, persisted to S3, then `s3_manager.get`-ed and `exec`-ed
- Tool 2 same pattern; `build.py` is thin (~12 lines)
- Both ran cleanly to completion — the build IS the refresh smoke test

**Atomicity (Rule 7):**

- Tools 1+2+3 ran in a single uninterrupted sequence; PRISM did NOT return to the user between them
- `_audit_dashboard_layout(...)` ran at end of Tool 2 and passed (§2.5)
- `_audit_registry_state(...)` ran at end of Tool 3 and passed (§6.1 Tool 3)
- Both audits passing is the gate that defines "built"; if either raises, the dashboard does not exist and nothing is surfaced to the user
- The user-facing message is exactly the §6 contract: portal URL on line 1, refresh frequency + datasets next; no "next steps", no "would you like me to…", no opt-in language

**Hand-off (Rule 6):** the success message leads with the portal URL (`/profile/dashboards/{id}/`); the `dashboard.html` S3 path is mentioned only if the user explicitly asks for it.

---

## 11. Time horizons

**Pull deep history.** The defaults below are initial zoom windows, not data-layer caps. Every time-series chart ships with a per-chart `dataZoom` slider (`dashboards/filters.md` §3) carrying the full dataset, and `dateRange` filters operate in view-mode by default with intervals `1M/3M/6M/YTD/1Y/2Y/5Y/All` — but both reach back only as far as the data goes.

If `pull_data.py` clips a 30-year FRED series to 2 years before persisting (or `build.py` slices / resamples / inner-joins it post-merge), those years are gone; the slider can't scroll into history that was never pulled. Loss of back-history at the PRISM transformation layer is irreversible from the dashboard side.

| Frequency | Initial zoom (default) | Rationale |
|-----------|------------------------|-----------|
| Quarterly / monthly | 10 years | Full business cycle |
| Weekly | 5 years | Trend + cycle |
| Daily | 2 years | Regime without noise |
| Intraday | 5 trading days | Event reaction window |

Override: if narrative references "highest since X", the initial window must include X (data still extends back as far as the source allows). For pre-pandemic comparisons set initial start ≥ 2015. Don't open at 12 months of monthly (hides cycle), 30 years of daily (noise), or different ranges for charts meant to be compared.
