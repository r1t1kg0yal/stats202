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
Tool 2  compose template + author build.py → persist → build_dashboard
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

- Pull only verified identifiers. An exact expression/code/client call supplied by the user or test prompt is authoritative for that task; preserve it byte-for-byte. If no identifier is supplied or verified, stop at the data boundary and ask for it—never infer a vendor code from a label or naming pattern.
- `labels=` is the preferred place to establish plain-English persisted columns.
- Match the eventual template dataset key to the complete emitted CSV stem.
- Import each source client or helper used by the script.
- Verify that the current pull invocation succeeded, then verify non-empty rows, columns, dtypes, latest dates, units, and economically plausible values. A retained pre-existing CSV is not current-cycle success.
- Pull functions are independent named units. Group calls only when they share source, cadence, and failure semantics.
- Persist every renderer input. An in-memory rename or derived column not written or transformed in `build.py` disappears on refresh.
- Only CSV files become build datasets. NY Fed and client returns must pass through `save_artifact` or an explicit CSV write. A dictionary or empty list saved as JSON is an artifact, not a dataset.
- Metadata sidecars and `df.attrs` are not loaded and never populate `field_provenance`; author lineage in each template dataset entry.

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

Its template uses `datasets = {}` and contains only data-independent widgets such as `widget: "tool"` plus narrative/divider widgets. Call `build_dashboard` directly in Tool 2; do not call `run_pull` when `PULLS` is empty and do not create a placeholder CSV. If any tool input uses `rows_from` or any sibling widget reads a dataset, the dashboard is not tool-only and must provide that dataset through the normal pull/transform path.

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
built = build_dashboard(FOLDER)
audit_dashboard_layout(FOLDER)
```

Template rules:

- Default to tabs when the product has separable jobs or is likely to grow; stable ids make later edits surgical.
- Template dataset entries are slots, not embedded live rows.
- Every displayed dataset follows the lineage placement owned by [pipelines.md](pipelines.md#field-provenance).
- Set the same refresh-frequency token in metadata and the registry.
- Tool `compute_js` lives in the template's `tool_def`; transforms do not author or interpolate it.
- Use `TRANSFORMS = []` when no derivation is needed.
- Transforms run in list order. Use them for joins, ratios, projections, resampling, and derived datasets from existing pulls.
- A transform never performs a network pull or writes dashboard outputs.

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
    "keep_history": False,
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
- Pick cadence from source cadence and product need.
- `synchronize_refresh_frequency` is the update path after registration because it commits template and registry together.
- Stop after the registry write and verification. There is no authoring helper named `update_user_manifest`; the scheduled orchestrator owns `UserManifestManager.update_dashboard_pointer(kerberos)`, and an on-demand browser refresh does not update that pointer today.

## Tool 4: fresh-process refresh

Run the same refresh runner used by scheduled and browser-triggered refreshes. Stream output to a file, wait for completion, then require both a zero return code and persisted success.
Launch the runner by its resolved file path, not with
`python -m dashboards.refresh_runner`. Production spawners also set
`start_new_session=True` and `cwd=REPO_ROOT`; the runner itself accepts
`--folder` plus optional `--log-path`.

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
        ],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        cwd=REPO_ROOT,
        start_new_session=True,
    )
    return_code = process.wait()

if return_code != 0:
    raise RuntimeError(f"refresh failed with rc={return_code}; log={log_path}")

status = json.loads(
    s3_manager.get(f"{FOLDER}/refresh_status.json")
    .rstrip(b"\x00").decode("utf-8")
)
if status.get("status") != "success":
    raise RuntimeError(
        f"refresh status={status.get('status')}; errors={status.get('errors')}"
    )

inspection = inspect_dashboard(FOLDER)
if inspection["files"]["missing"] or inspection["attachment_gaps"]:
    raise RuntimeError(inspection)
```

There is no universal per-pull refresh timeout. Do not impose an arbitrary authoring timeout; source-specific client timeouts still apply, and the subprocess plus status record provide terminal completion evidence. Require each expected CSV to have been produced successfully and verified non-empty in the current cycle so a stale retained file cannot qualify the build.

## Portal handoff

After all four tools pass:

`http://reports.prism-ai.url.gs.com:8501/users/{kerberos}/dashboards/{dashboard_id}/`

The user message contains the live URL and a concise product description. Do not expose the four-tool transaction, internal files, or engine diagnostics unless explicitly asked.

## First-build checklist

- [ ] Product scope and destructive intent are unambiguous.
- [ ] Persisted scripts explicitly import every helper, `pd`/`np`, NY Fed function, and client module they use.
- [ ] Every pull succeeded in the current cycle and persisted the expected non-empty CSV shape; no retained stale CSV was accepted.
- [ ] Dataset keys, CSV stems, mappings, units, and provenance agree.
- [ ] JSON artifacts, metadata sidecars, and `df.attrs` are not treated as datasets or provenance.
- [ ] Template contains slots rather than live rows.
- [ ] `TRANSFORMS` exists and each transform returns the dataset dictionary.
- [ ] `build_dashboard` and `audit_dashboard_layout` pass.
- [ ] Registry contains exactly one canonical entry.
- [ ] Template and registry cadence are synchronized.
- [ ] Registry ownership is respected; no nonexistent manifest-pointer helper is called.
- [ ] Subprocess exits zero and `refresh_status.status` is `success`.
- [ ] Final inspection has no missing required files or attachment gaps.
- [ ] The exact portal URL is handed off in product language.
