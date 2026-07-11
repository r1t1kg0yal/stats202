# Data and script edits

- **Context ID:** `echarts.pipelines`
- **Owns:** `pipeline.graph`, `pipeline.reuse`, `pipeline.pull_edit`, `pipeline.transform_edit`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#contract) and [diagnose.md](diagnose.md#structured-inspection).

This file is the sole owner of edits to persisted `scripts/pull_data.py`, `scripts/build.py`, and their data-flow contract. Manifest layout edits belong to [template_crud.md](template_crud.md#manifest-operations).

## Persisted data flow

```text
scripts/pull_data.py
  PULLS[name]() → data/<stem>.csv
                         ↓
scripts/build.py
  TRANSFORMS: datasets → datasets
                         ↓
manifest_template.json slots
                         ↓
build_dashboard → manifest.json + dashboard.html
```

Only the three persisted inputs—pull script, build script, and template—survive refresh. Do not edit generated CSV, manifest, or HTML as the durable change.

`scripts/pull_data.py` exclusively owns imports, source/client calls, output names, and `PULLS`. `scripts/build.py` exclusively owns deterministic derivations and the ordered `TRANSFORMS` list. The template owns dataset slots, field lineage, and consumers; it never owns a network call.

Start with:

```python
state = inspect_dashboard(FOLDER)
```

Use `state["graph"]` to see pull names, inferred stems, transforms, dataset slots, widgets, filters, and edges. Read the full current script bytes before editing; preserve unrelated functions, imports, `PULLS`, and `TRANSFORMS`.

## Pipeline reuse decision

For each requested field or dataset:

1. **Reuse an existing dataset.** If the persisted CSV already contains the required columns, do not edit scripts.
2. **Derive from existing datasets.** If current pulls contain the inputs, add or update a `TRANSFORMS` function in `build.py`; no network pull is needed.
3. **Extend an existing pull.** If the source and cadence already exist but a field is missing, add the verified code/expression/label to that pull while keeping its stem.
4. **Add a pull.** Only when a genuinely new source/cadence is required; create one function, one `PULLS` entry, and one deterministic output stem.
5. **Escalate product meaning.** If data is unavailable or substitutes change the analysis, ask the user which product outcome they want. Never invent data.

Prefer the earliest valid path. Shared pipelines reduce API calls and keep one source of truth.

## Pull contract

Every persisted pull script:

- defines `SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_id}"`;
- imports each helper/client it calls;
- defines named zero-argument pull functions;
- defines module-level `PULLS = {"name": function, ...}`;
- writes each artifact under `f"{SESSION_PATH}/data"`;
- uses stable `name=` values whose stems match dataset slots;
- establishes plain-English persisted labels;
- logs enough source-level progress to locate a slow or failed pull.

An exact expression, code, or client-call form supplied by the user/test is authoritative and must be copied without normalization. If the request supplies no verified identifier, do not translate a human label into a vendor code. Each pull also has an explicit expected output contract—stem, ordered column names, pandas dtypes, units, and frequency—stated by the request or verified from the response before manifest authoring. Assert required columns after the call and inspect actual dtypes; never guess returned field names.

```python
from core.s3_bucket_manager import s3_manager
from prism_mcp.utils.data_functions import (
    pull_haver_data,
    pull_plottool_data,
    pull_fred_data,
    pull_market_data,
    save_artifact,
)

SESSION_PATH = "users/goyalri/dashboards/rates_monitor"

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
```

Stem rules:

| Producer | Stem |
|---|---|
| Haver / PlotTool / FRED / `save_artifact` | `name` verbatim |
| Market data `mode="eod"` | `<name>_eod` |
| Market data `mode="iday"` or `"intraday"` | `<name>_intraday` |
| Market data `mode="both"` | both stems |
| Direct S3 write | literal `data/<stem>.csv` or `.json` path |

When an external source is unavailable at predictable times, model that state explicitly. A dashboard may omit an intraday-only panel or show a product-level availability state, but it must not fabricate observations or silently substitute a semantically different series.

## Transform contract

`build.py` contains module-level `TRANSFORMS`, even when empty. Each function receives loaded DataFrames keyed by CSV stem and returns a dataset dictionary.

```python
import pandas as pd

SESSION_PATH = "users/goyalri/dashboards/rates_monitor"

def derive_spread(datasets):
    rates = datasets["rates"]
    datasets["spread"] = pd.DataFrame({
        "date": rates["date"],
        "spread_bp": (rates["us_10y"] - rates["us_2y"]) * 100,
    })
    return datasets

TRANSFORMS = [derive_spread]
```

Transforms:

- execute in list order;
- do not perform network calls;
- do not call compile/populate/write APIs;
- preserve existing dataset keys unless destructive product intent is explicit;
- validate required input columns and fail with actionable text;
- emit tidy DataFrames with dates as columns and stable plain-English names;
- attach provenance for derived fields through the template dataset metadata.

Use transforms for joins, ratios, changes, resampling, native-frequency cleanup, projections, long/wide reshaping, and model outputs derived from existing pulls. Use manifest-level `compute` expressions for concise safe per-column formulas already supported by the chart contract.

Before a manifest-only phase references a new dataset or column, its CSV/transform output must already be provisioned and verified. If it is absent, finish the owning pull/transform edit first and only then apply typed manifest operations. `recompile=False` is not a substitute for phase data.

## Editing persisted scripts

There is no root-replacement script API. The safe edit is evidence-based byte mutation:

1. Inspect and read both scripts in full.
2. Identify the smallest unique edit anchor.
3. Build new bytes while preserving all unrelated content.
4. Require the new bytes to differ and the anchor to match exactly once.
5. Compile the new source before writing.
6. Persist the owning script.
7. Run only the affected pull first; verify its output.
8. Run `build_dashboard`.
9. Run the clean subprocess refresh.
10. Inspect again.

```python
path = f"{FOLDER}/scripts/pull_data.py"
old = s3_manager.get(path).decode("utf-8")
if old.count(OLD_BLOCK) != 1:
    raise ValueError("pull edit anchor must match exactly once")
new = old.replace(OLD_BLOCK, NEW_BLOCK, 1)
if new == old:
    raise ValueError("pull edit produced no change")
compile(new, path, "exec")
s3_manager.put(new.encode("utf-8"), path)
```

For a multi-surface data change, order the transaction:

```text
pull script edit
  → run affected pull(s)
  → verify persisted columns and values
  → build script edit if derivation changes
  → typed manifest operations for new/changed slots and widgets
  → build_dashboard
  → clean subprocess refresh
  → inspect_dashboard
```

Keep exact pre-edit bytes in the active transaction until final verification, so a failed multi-surface edit can restore known state. Do not create parallel live copies or alternate script trees.

## Active-pipeline integrity

Before writing, use the inspection graph and persisted CSV schemas to prove:

- every existing `PULLS` entry remains present unless its entire product surface is intentionally removed;
- every pre-edit CSV still exists after the edit;
- every pre-edit column consumed by a widget, filter, transform, or source path remains;
- every template dataset has a pull or transform producer;
- every pull-produced CSV intended for display has a matching slot;
- all mapping/source/filter fields exist in the refreshed data;
- source cadence, units, as-of dates, and row cardinality remain plausible.

Common breakages:

| Edit | Failure |
|---|---|
| Rename `name=` | Consumers still point at the old stem |
| Change `output_path` | Loader cannot discover the CSV |
| Drop a field | Widget mapping or transform fails |
| Ephemeral rename only | Refresh reloads raw persisted columns |
| Add slot before producer | Attachment audit reports unattached data |
| Change dtype/unit silently | Dashboard can show wrong values without a schema error |
| Remove a pull without graph review | Multiple downstream surfaces disappear |

## Field provenance

Every displayed field identifies its source. `field_provenance` is placed inside the owning dataset entry at `datasets.<dataset_name>.field_provenance`, never under top-level `metadata`:

```python
"datasets": {
    "rates": {
        "source": [],
        "field_provenance": {
            "us_10y": {
                "system": "plottool",
                "symbol": "<exact supplied expression>",
                "display_name": "US 10Y swap rate",
                "units": "percent",
                "source_label": "GS Market Data",
            },
            "issuer": {
                "system": "client",
                "client": "bond_client",
                "method": "get_screen",
                "identifier": "issuer",
            },
            "spread_bp": {
                "system": "computed",
                "recipe": "(us_10y - us_2y) * 100",
                "computed_from": ["us_10y", "us_2y"],
                "units": "bp",
            },
        },
    },
}
```

Each provenance value is a dictionary. Native-source fields use `system` plus the exact supplied identifier (`symbol`, `haver_code`, `fred_series`, or another source-native key). Client-returned fields use the closed shape `{"system":"client","client":<exact imported client name>,"method":<exact called method>}` plus optional `identifier` only when the caller supplied that field/token; do not infer one from a display label. `display_name`, `units`, `frequency`, and `source_label` are optional source facts. A computed field uses `system: "computed"`, exact `recipe`, `computed_from`, and `units`. Never invent identifiers.

## Refresh-frequency edits

Changing source cadence may require a dashboard cadence change. After data/script verification:

```python
synchronize_refresh_frequency(
    FOLDER,
    "1h",
    expected_sha256=inspect_dashboard(FOLDER)["manifest_template_sha256"],
)
```

This aligns template and registry atomically. Do not patch one side manually.

## Verification

After any script edit:

```python
after = inspect_dashboard(FOLDER)
```

Require:

- no missing required files;
- pull script parses and named pipelines/stems match intent;
- transform keys match intended derived slots;
- graph edges connect producer → CSV/transform → dataset → consumer;
- no attachment gaps;
- strict build succeeds;
- clean refresh status is success;
- pre-existing pipeline outputs and consumed columns remain;
- no new relevant telemetry errors appear after the refreshed page is exercised.

If verification fails, follow the structured evidence, restore exact transaction bytes when needed, and retry before responding.
