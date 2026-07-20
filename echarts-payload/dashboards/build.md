# First-build transaction

- **Context ID:** `echarts.build`
- **Owns:** `build.tool1`, `build.tool2`, `build.tool3`, `build.tool4`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#contract).

This file is the sole owner of first-build Tools 1-4. A first build is one uninterrupted transaction; do not respond until Tool 4 reports success and the portal URL is ready.

## Four-tool transaction

```text
Tool 1  author pull_data.py → persist → run every PULLS entry → verify CSVs
   ↓
Tool 2  compose template + author build.py → persist → review receipt
        → flagged-panel drill-down → publish_dashboard(rationale=...)
   ↓
Tool 3  register exactly once → align cadence → verify registry (pointer: scheduled orchestrator only)
   ↓
Tool 4  run refresh_runner in a fresh subprocess → require green status
   ↓
Portal handoff
```

Use a first build for a new dashboard or an explicitly requested destructive rebuild. “Add”, “change”, “extend”, and “also show” target existing dashboards and belong to typed manifest or pipeline edits.

## Tool 1: pull and verify data

`pull_data.py` is standalone persisted Python. It defines the exact dashboard folder, explicitly imports every name it uses, writes every artifact under `data/`, and exposes a module-level `PULLS` dictionary. Never rely on authoring or in-process injections: import `pandas as pd`, `numpy as np`, `pull_nyfed_data` from `core.mcp.clients.newyorkfed_client`, `save_artifact` from `prism_mcp.utils.data_functions`, and each `core.mcp.clients` module when actually used.

```python
KERBEROS = "goyalri"
DASHBOARD_ID = "rates_monitor"
FOLDER = f"users/{KERBEROS}/dashboards/{DASHBOARD_ID}"

pull_data_py = '''from core.s3_bucket_manager import s3_manager
from prism_mcp.utils.data_functions import pull_plottool_data

SESSION_PATH = "{{FOLDER}}"

def pull_rates():
    pull_plottool_data(
        expressions=["sofrswp2y", "sofrswp10y"],
        labels=["us_2y", "us_10y"],
        start="2020-01-01",
        name="rates",
        output_path=f"{SESSION_PATH}/data",
        s3_manager=s3_manager,
    )

PULLS = {"rates": pull_rates}
'''.replace("{{FOLDER}}", FOLDER)

s3_manager.put(
    pull_data_py.encode("utf-8"),
    f"{FOLDER}/scripts/pull_data.py",
)

for pull_name, csv_stem in {"rates": "rates"}.items():
    run_pull(FOLDER, pull_name)
    raw = s3_manager.get(f"{FOLDER}/data/{csv_stem}.csv")
    frame = pd.read_csv(io.BytesIO(raw))
    if frame.empty:
        raise ValueError(f"{csv_stem}.csv is empty")
    print(csv_stem, frame.shape, frame.columns.tolist())
```

Tool 1 rules:

- Pull only verified identifiers. An exact expression/code/client call supplied by the user or test prompt is authoritative for that task; preserve it byte-for-byte. If no identifier is supplied or verified, stop at the external-data boundary and ask for it—never infer a vendor code from a label or naming pattern. An exact user-supplied deterministic fixture is itself the verified source and needs no vendor identifier.
- `labels=` is the preferred place to establish plain-English persisted columns.
- Match the eventual template dataset key to the complete emitted CSV stem.
- Import each source client or helper used by the script.
- Verify that the current pull invocation succeeded, then verify non-empty rows, columns, dtypes, latest dates, units, and economically plausible values. A retained pre-existing CSV is not current-cycle success.
- Pull functions are independent named units. Group calls when they share source, cadence, and failure semantics; one such function may emit several fixed terminal CSVs through a local writer helper. The attachment engine follows literal helper arguments and finite literal loops, so do not split a coherent pull merely to expose each file.
- Every output stem must be statically resolvable because template dataset keys are fixed. If the engine reports `producer_output_unresolved`, expose the fixed literal at the standard call, local helper call, assignment/update, or finite literal loop; do not add dummy assignments.
- Persist every renderer input. An in-memory rename or derived column not written or transformed in `build.py` disappears on refresh.
- Only CSV files become build datasets. NY Fed and client returns must pass through `save_artifact` or an explicit CSV write. A dictionary or empty list saved as JSON is an artifact, not a dataset.
- Metadata sidecars and `df.attrs` are not loaded and never populate `field_provenance`; author lineage in each template dataset entry.

Canonical fixture pull:

```python
from core.s3_bucket_manager import s3_manager
import pandas as pd
from prism_mcp.utils.data_functions import save_artifact

SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_id}"

def pull_fixture():
    frame = pd.DataFrame(EXACT_USER_SUPPLIED_ROWS)
    save_artifact(frame, name="fixture", output_path=f"{SESSION_PATH}/data",
                  s3_manager=s3_manager)

PULLS = {"fixture": pull_fixture}
```

Replace only `EXACT_USER_SUPPLIED_ROWS` and the stable stem; preserve supplied
values and nulls without normalization.

Pull primitives and stems:

| Call | Persisted stem |
|---|---|
| `pull_haver_data(..., name="cpi")` | `cpi` |
| `pull_plottool_data(..., name="rates")` | `rates` |
| `pull_fred_data(..., name="labor")` | `labor` |
| `result = pull_nyfed_data(...)` then `save_artifact(result, name="nyfed", output_path=...)` | `nyfed` only when `result` is a DataFrame or non-empty tabular records |
| `save_artifact(DataFrame or non-empty list[dict], name="screen")` | `screen` |

### Tool-only build

A pure calculator with no source data is a legal first build. Persist both scripts with these exact module-level declarations:

```python
# scripts/pull_data.py
SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_id}"
PULLS = {}

# scripts/build.py
SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_id}"
TRANSFORMS = []
```

Its template uses `datasets = {}` and contains only data-independent widgets
such as `widget: "tool"`, `widget: "user_input"`, and narrative/divider
widgets. Call `build_dashboard` directly in Tool 2; do not call `run_pull`
when `PULLS` is empty and do not create a placeholder CSV. Persisted
`user_input` state remains outside the manifest and does not make the build
data-bound. If any tool input uses `rows_from` or any sibling widget reads a
dataset, the dashboard is not tool-only and must provide that dataset through
the normal pull/transform path.

## Tool 2: template, transforms, compile

Compose the initial manifest from verified data, derive the data-free template with `manifest_template`, and author `build.py`.

`build.py` contains only module-level `TRANSFORMS`. Each transform accepts the CSV-loaded dataset dictionary and returns a dictionary. JSON artifacts, metadata sidecars, and `df.attrs` are not inputs. CSV discovery, population, strict compilation, attachment audit, and output writes belong to `build_dashboard`.

```python
rates = pd.read_csv(
    io.BytesIO(s3_manager.get(f"{FOLDER}/data/rates.csv"))
)

initial_manifest = {
    "schema_version": 1,
    "id": DASHBOARD_ID,
    "title": "Rates Monitor",
    "theme": "gs_clean",
    "palette": "gs_primary",
    "metadata": {
        "kerberos": KERBEROS,
        "dashboard_id": DASHBOARD_ID,
        "methodology": (
            "## Sources\n* GS Market Data\n"
            "## Construction\n* Daily closes; 2s10s is 10Y minus 2Y in bp"
        ),
        "sources": ["GS Market Data"],
        "refresh_frequency": "1d",
        "tags": ["rates"],
    },
    "datasets": {
        "rates": {"source": rates},
        "spread": {"source": []},
    },
    "layout": {
        "kind": "tabs",
        "cols": 12,
        "tabs": [{
            "id": "overview",
            "label": "Overview",
            "rows": [[
                {
                    "widget": "chart", "id": "curve", "w": 6,
                    "title": "USD swap curve",
                    "spec": {
                        "chart_type": "multi_line",
                        "dataset": "rates",
                        "mapping": {
                            "x": "date",
                            "y": ["us_2y", "us_10y"],
                            "y_title": "Rate (%)",
                        },
                    },
                },
                {
                    "widget": "chart", "id": "spread", "w": 6,
                    "title": "2s10s",
                    "spec": {
                        "chart_type": "line",
                        "dataset": "spread",
                        "mapping": {
                            "x": "date", "y": "spread_bp",
                            "y_title": "Spread (bp)",
                        },
                    },
                },
            ]],
        }],
    },
}

template = manifest_template(initial_manifest)
s3_manager.put(
    json.dumps(template, indent=2).encode("utf-8"),
    f"{FOLDER}/manifest_template.json",
)

build_py = '''import pandas as pd

SESSION_PATH = "{{FOLDER}}"

def derive_spread(datasets):
    rates = datasets["rates"]
    datasets["spread"] = pd.DataFrame({
        "date": rates["date"],
        "spread_bp": (rates["us_10y"] - rates["us_2y"]) * 100,
    })
    return datasets

TRANSFORMS = [derive_spread]
'''.replace("{{FOLDER}}", FOLDER)

s3_manager.put(build_py.encode("utf-8"), f"{FOLDER}/scripts/build.py")
review = review_dashboard(FOLDER)
print(review.to_text())
for panel in review.panels:
    if panel.status != "CLEAR":
        print(review.panel(panel.panel_id).to_text())
published = publish_dashboard(
    FOLDER,
    rationale=(
        "Reviewed the complete curve and spread panel index; accepted this "
        "CLEAR first baseline because both default-state series are populated "
        "and no Python-visible quality finding remains."
    ),
)
built = published["manifest"]
audit_dashboard_layout(FOLDER)
```

Template rules:

- A first build requires exact acknowledgment even when its `DashboardReview.status` is `CLEAR`. Always inspect the one-line-per-panel receipt, drill into every flagged panel with `review.panel(id)`, then call `publish_dashboard` with a real rationale (or the equivalent `acknowledge_dashboard_review` + `build_dashboard`).
- `BLOCK` is unacknowledgeable (`publish_dashboard` refuses it). Repair the deterministic defect and review the new signature.
- The first successful `build_dashboard` creates the baseline definition version; later successful builds create a version only when the template or either persisted script changed.
- Default to tabs when the product has separable jobs or is likely to grow; stable ids make later edits surgical.
- Template dataset entries are slots, not embedded live rows.
- Every displayed dataset follows the lineage placement owned by [pipelines.md](pipelines.md#field-provenance).
- Set the same refresh-frequency token in metadata and the registry.
- For a deterministic user fixture, use source
  `User-supplied deterministic fixture`, state that construction in
  `metadata.methodology`, and use `refresh_frequency: "manual"` unless the
  user supplied a real refresh cadence. Do not invent an external source.
- Tool `compute_js` lives in the template's `tool_def`; transforms do not author or interpolate it.
- Use `TRANSFORMS = []` when no derivation is needed.
- Transforms run in list order. Use them for joins, ratios, projections, resampling, and derived datasets from existing pulls.
- A transform never performs a network pull or writes dashboard outputs.

Layout composition remains a flat, collision-checked `rows` list. Add named visual hierarchy without nesting widgets by declaring non-overlapping row ranges beside those rows:

```python
"groups": [
    {
        "id": "macro_regime",
        "title": "Macro regime",
        "description": "Growth, inflation, and policy",
        "start_row": 0,
        "end_row": 2,
        "collapsible": False,
    },
]
```

`groups` is valid on a grid layout or inside an individual tab. Group ids are globally unique; ranges are zero-based, inclusive, in bounds, and may not overlap. Use one `hero: true, w: 12` chart in its own row only when the chart is the page's decision-critical focal point. Standard charts remain 4/12 or 6/12. Use `data_grid` for a full-width virtualized records surface rather than overloading a chart row.

At an adaptive manifest phase, every dataset referenced by the proposed operation must already be present in the current compiled/persisted data. If it is not, route to the persisted pipeline owner and provision the producer before applying the manifest operation; `recompile=False` does not make missing phase data legal.

## Tool 3: register

The registry path is `users/{kerberos}/dashboards/dashboards_registry.json`. Preserve unrelated entries and `created_at`; write exactly one matching id inside `dashboards[]`.

```python
REGISTRY_PATH = f"users/{KERBEROS}/dashboards/dashboards_registry.json"
now_iso = datetime.now(timezone.utc).isoformat()

if s3_manager.exists(REGISTRY_PATH):
    registry = json.loads(
        s3_manager.get(REGISTRY_PATH).rstrip(b"\x00").decode("utf-8")
    )
else:
    registry = {"dashboards": [], "last_updated": now_iso}

entries = registry.get("dashboards")
if not isinstance(entries, list):
    raise ValueError("registry dashboards must be a list")

matches = [i for i, entry in enumerate(entries)
           if isinstance(entry, dict) and entry.get("id") == DASHBOARD_ID]
if len(matches) > 1:
    raise ValueError(f"duplicate registry entries for {DASHBOARD_ID}")

created_at = (
    entries[matches[0]].get("created_at", now_iso) if matches else now_iso
)
entry = {
    "id": DASHBOARD_ID,
    "name": "Rates Monitor",
    "description": "Daily monitor of the USD rates curve.",
    "created_at": created_at,
    "last_refreshed": None,
    "last_refresh_status": None,
    "refresh_enabled": True,
    "refresh_frequency": "1d",
    "folder": FOLDER,
    "html_path": f"{FOLDER}/dashboard.html",
    "data_path": f"{FOLDER}/data",
    "tags": ["rates"],
}
if matches:
    entries[matches[0]] = entry
else:
    entries.append(entry)

registry["last_updated"] = now_iso
s3_manager.put(
    json.dumps(registry, indent=2).encode("utf-8"),
    REGISTRY_PATH,
)
synchronize_refresh_frequency(FOLDER, "1d")

inspection = inspect_dashboard(FOLDER)
if inspection["registry"]["match_count"] != 1:
    raise ValueError(inspection["findings"])
```

Registration rules:

- Never store the dashboard as a top-level registry key.
- Preserve unrelated registry fields and entries.
- `folder`, `html_path`, and `data_path` use the canonical folder.
- Pick cadence from the class table below; set the same value on the
  template and registry entry.
- `synchronize_refresh_frequency` is the update path after registration because it commits template and registry together.
- Stop after the registry write and verification. There is no authoring helper named `update_user_manifest`; the scheduled orchestrator owns `UserManifestManager.update_dashboard_pointer(kerberos)`, and an on-demand browser refresh does not update that pointer today.

### Cadence

Author **one** field: `metadata.refresh_frequency` (and the matching
registry value via `synchronize_refresh_frequency`). Do not author
`live_refresh_seconds` unless you need an explicit browser-poll override;
the engine stamps it from `refresh_frequency` at build time.

| Dashboard class | Example `refresh_frequency` |
|---|---|
| Intraday market / live positioning | `30s` or `60s` |
| Email / ops monitoring | `60s` or `5m` |
| Rates/FX desk monitors | `5m` or `15m` |
| Macro / GDP / releases | `1h` or `1d` |
| Static / one-shot | `manual` |

That frequency gates both the cold 15-minute full walk and open-tab
light pulls (presence-fresh folders that are due). Browser
`[Refresh]` always pulls now. Site `--open-interval` is only how often
the open daemon *checks* due state (recommend 10s).

## Tool 4: fresh-process refresh

Run the same refresh runner used by scheduled refreshes. Tool 4 must use
`--mode full` (compile + HTML) so cold loads see fresh bytes. The browser
Refresh button uses `--mode light` (datasets only); do not close a
first-build on light mode. Prefer `launch_clean_refresh(FOLDER, mode="full")`
when the import resolves. Otherwise launch the runner by its resolved file
path, not with `python -m dashboards.refresh_runner`. Production spawners
also set `start_new_session=True` and `cwd=REPO_ROOT`; the runner accepts
`--folder`, optional `--log-path`, and `--mode full|light` (default `full`).

```python
import dashboards.refresh_runner as refresh_runner_module
from prism_meta import REPO_ROOT

log_path = (
    f"/tmp/dashboard_refresh/"
    f"{KERBEROS}_{DASHBOARD_ID}_{int(time.time())}.log"
)
os.makedirs(os.path.dirname(log_path), exist_ok=True)

with open(log_path, "wb") as log_file:
    process = subprocess.Popen(
        [
            sys.executable,
            refresh_runner_module.__file__,
            "--folder", FOLDER,
            "--log-path", log_path,
            "--mode", "full",
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=REPO_ROOT,
        start_new_session=True,
    )
    return_code = process.wait()

status = json.loads(
    s3_manager.get(f"{FOLDER}/refresh_status.json")
    .rstrip(b"\x00").decode("utf-8")
)
if status.get("status") == "review_required":
    review = review_dashboard(FOLDER)
    print(review.to_text())
    raise RuntimeError(
        "review the flagged panels, acknowledge the exact signature with "
        "a rationale, then rerun the build and clean refresh"
    )
if return_code != 0:
    raise RuntimeError(f"refresh failed with rc={return_code}; log={log_path}")
if status.get("status") != "success":
    raise RuntimeError(
        f"refresh status={status.get('status')}; errors={status.get('errors')}"
    )

inspection = inspect_dashboard(FOLDER)
if inspection["files"]["missing"] or inspection["attachment_gaps"]:
    raise RuntimeError(inspection)

dashboard_html = s3_manager.get(f"{FOLDER}/dashboard.html").decode("utf-8")
for required_id in ('id="export-chart-data"', 'id="export-print"'):
    if required_id not in dashboard_html:
        raise RuntimeError(f"missing export action: {required_id}")
```

There is no universal per-pull refresh timeout. Do not impose an arbitrary authoring timeout; source-specific client timeouts still apply, and the subprocess plus status record provide terminal completion evidence. Require each expected CSV to have been produced successfully and verified non-empty in the current cycle so a stale retained file cannot qualify the build.

`review_required` is a publish hold, not a failed refresh: the runner retains the live manifest/dashboard bytes, does not stamp registry or user-manifest pointers, and does not increment failure cooldown. Inspect the new receipt and flagged panels, acknowledge its exact signature with a rationale, then call `build_dashboard` and rerun Tool 4. Ordinary raw-value refreshes reuse an acknowledgment only while the definition and versioned quality signature remain unchanged; the quality signature uses finding codes and coarse count/fraction/ratio/span/text/shape classes rather than ordinary raw observations. When a fresh inspection reports `review.acknowledgment_match=True` and `review.publish_ready=True`, proceed without a redundant acknowledgment.

The compile gate proves both export actions are present. In the browser gate,
download chart-data CSV and trigger print once: print must use the light theme,
mount every tab, open collapsed groups, and expand each `data_grid` to its
complete filtered/sorted result up to `max_rows`.

These are sequential gates, not competing claims. Python acknowledgment occurs
before build and accepts the exact compile/default-state receipt, including any
explicit `runtime_unverified` boundary. Browser-only JavaScript can run only
after that build; exercise tool default/representative/edge inputs and exports
before delivery. A browser failure requires a definition repair, a fresh
review/acknowledgment when its signature changes, another build, and another
browser check.

## Portal handoff

After all four tools pass:

`http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/`

The user message contains the live URL and a concise product description. Prefer paraphrasing `describe_dashboard(FOLDER)["text"]` so create and edit share the same layout-sync grammar. Do not expose the four-tool transaction, internal files, or engine diagnostics unless explicitly asked.

## First-build checklist

- [ ] Product scope and destructive intent are unambiguous.
- [ ] Persisted scripts explicitly import every helper, `pd`/`np`, NY Fed function, and client module they use.
- [ ] Every pull succeeded in the current cycle and persisted the expected non-empty CSV shape; no retained stale CSV was accepted.
- [ ] Dataset keys, CSV stems, mappings, units, and provenance agree.
- [ ] JSON artifacts, metadata sidecars, and `df.attrs` are not treated as datasets or provenance.
- [ ] Template contains slots rather than live rows.
- [ ] `TRANSFORMS` exists and each transform returns the dataset dictionary.
- [ ] `review_dashboard` receipt and every flagged `review.panel(id)` were inspected.
- [ ] The exact non-`BLOCK` review signature was acknowledged with a substantive rationale.
- [ ] `build_dashboard` and `audit_dashboard_layout` pass.
- [ ] Registry contains exactly one canonical entry.
- [ ] Template and registry cadence are synchronized.
- [ ] Registry ownership is respected; no nonexistent manifest-pointer helper is called.
- [ ] Subprocess exits zero and `refresh_status.status` is `success`.
- [ ] Final inspection has no missing required files or attachment gaps.
- [ ] Chart-data CSV and PDF/print actions are present; the browser export gate passes.
- [ ] The exact portal URL is handed off in product language.
