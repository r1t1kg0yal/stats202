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
  CSV datasets → TRANSFORMS: datasets → datasets
                         ↓
manifest_template.json slots
                         ↓
build_dashboard → manifest.json + dashboard.html
```

Only the three persisted inputs—pull script, build script, and template—survive refresh. They are also the complete definition recipe recorded automatically after each successful changed build. CSVs, populated manifests, and HTML are current generated state, not version history.

`scripts/pull_data.py` exclusively owns imports, source/client calls, output names, and `PULLS`. `scripts/build.py` exclusively owns deterministic derivations and the ordered `TRANSFORMS` list. The template owns dataset slots, field lineage, and consumers; it never owns a network call. Only flat `data/*.csv` files are loaded as datasets; JSON artifacts and metadata sidecars are ignored.

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
4. **Add a pull.** Only when a genuinely new source/cadence/failure unit is required; create one function and one `PULLS` entry. That coherent function may emit one or several fixed output stems.
5. **Escalate product meaning.** If data is unavailable or substitutes change the analysis, ask the user which product outcome they want. Never invent data.

Prefer the earliest valid path. Shared pipelines reduce API calls and keep one source of truth.

## Pull contract

Every persisted pull script:

- defines `SESSION_PATH = "users/{kerberos}/dashboards/{dashboard_id}"`;
- imports each helper/client it calls;
- defines named zero-argument pull functions;
- defines module-level `PULLS = {"name": function, ...}`;
- writes each artifact under `f"{SESSION_PATH}/data"`;
- uses statically resolvable output stems that match dataset slots;
- establishes plain-English persisted labels;
- logs enough source-level progress to locate a slow or failed pull.

An exact expression, code, or client-call form supplied by the user/test is authoritative and must be copied without normalization. If the request supplies no verified identifier, do not translate a human label into a vendor code. Each pull also has an explicit expected output contract—stem, ordered column names, pandas dtypes, units, and frequency—stated by the request or verified from the response before manifest authoring. Assert required columns after the call and inspect actual dtypes; never guess returned field names.

In-process execution and clean refresh expose the same canonical names:
`s3_manager`, the standard pull helpers, `pull_nyfed_data`,
`save_artifact`, `pd`, and `np`. Import every other used client module
explicitly from `core.mcp.clients`.
Persisted scripts still import every helper they use; namespace injection is
the parity guarantee for execution, not a reason to omit durable imports.
For example, use `from core.mcp.clients import bond_client` when the verified
call is `bond_client.get_screen(...)`.

NY Fed and client calls return objects rather than dashboard artifacts.
Persist their output through `save_artifact` or an explicit CSV write. A
dictionary or empty list is saved as JSON and is not a dataset; require a
DataFrame or non-empty tabular records for a CSV-backed dataset.
Each `PULLS` entry must re-call its source during refresh; an object left in
the authoring session namespace is not a refreshable producer.

```python
from core.s3_bucket_manager import s3_manager
from prism_mcp.utils.data_functions import (
    pull_haver_data,
    pull_plottool_data,
    pull_fred_data,
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

| Producer | Emitted artifact and dataset key |
|---|---|
| Haver / PlotTool / FRED | `data/<name>.csv` → `<name>` |
| `save_artifact` with a DataFrame or non-empty list of records | `data/<name>.csv` → `<name>` |
| `save_artifact` with a dictionary or empty list | JSON artifact; no dataset key |
| Direct S3 CSV write | literal `data/<stem>.csv` → `<stem>` |
| Direct S3 JSON write | artifact only; no dataset key |

### Producer visibility

The attachment engine follows each registered `PULLS` or `TRANSFORMS` function
through local helper calls. It propagates literal strings through local
assignments, helper parameters, f-strings, `datasets.update({...})`, and finite
loops over literal lists, tuples, or dictionaries. A coherent pull may
therefore use one local writer helper for several terminal CSVs:

```python
from core.s3_bucket_manager import s3_manager

SESSION_PATH = "users/goyalri/dashboards/factor_monitor"

def _write_csv(frame, stem):
    body = frame.to_csv(index=False).encode("utf-8")
    s3_manager.put(body, f"{SESSION_PATH}/data/{stem}.csv")

def pull_factor_model():
    outputs = {
        "factor_corr": build_factor_correlation(),
        "heat_z": build_zscore_heatmap(),
        "heat_beta": build_beta_heatmap(),
    }
    for stem, frame in outputs.items():
        _write_csv(frame, stem)

PULLS = {"factor_model": pull_factor_model}
```

Keep that single `PULLS` entry when the outputs share source, cadence, and
failure semantics. Do not split it into artificial per-file pulls and do not
add dummy `datasets["key"] = datasets["key"]` assignments for the auditor.

Dashboard dataset keys are fixed by the template, so output names must also be
statically provable. A data-dependent form such as
`for stem in runtime_names(): _write_csv(frame, stem)` is rejected as
`pull_producer_output_unresolved` or
`transform_producer_output_unresolved`. A missing consumer reached alongside
such a site is `dataset_<key>_producer_unresolved`, not silent-stale. Make the
fixed stems literal at the standard call, local helper call, assignment/update,
or finite literal loop; preserve the coherent pipeline.

For an exact user-supplied deterministic fixture, preserve values and nulls
without normalization and use the ordinary refreshable pull contract:

```python
from core.s3_bucket_manager import s3_manager
import pandas as pd
from prism_mcp.utils.data_functions import save_artifact

SESSION_PATH = "users/goyalri/dashboards/fixture_dashboard"

def pull_series():
    frame = pd.DataFrame([
        {"date": "2026-01-01", "value": 100.0},
        {"date": "2026-01-02", "value": None},
    ])
    save_artifact(
        frame,
        name="series",
        output_path=f"{SESSION_PATH}/data",
        s3_manager=s3_manager,
    )

PULLS = {"series": pull_series}
```

When a second verified client call consumes the first call's in-memory result
(for example `get_screen(...)` followed by
`get_history(cusips=bonds["cusip"].tolist(), ...)`), keep both calls and both
`save_artifact` writes inside one zero-argument pull function. `PULLS`
declaration order is not a cross-pull dependency mechanism. Split the calls
only when the dependent pull explicitly reloads and verifies the first
current-cycle CSV; never consume a retained prior-cycle file implicitly.

When an external source is unavailable at predictable times, model that state explicitly. A dashboard may omit an intraday-only panel or show a product-level availability state, but it must not fabricate observations or silently substitute a semantically different series.

## Transform contract

`build.py` contains module-level `TRANSFORMS`, even when empty. Each function receives CSV-loaded DataFrames keyed by the complete filename stem and returns a dataset dictionary. Metadata sidecars, JSON artifacts, and DataFrame `attrs` are not inputs.

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

Dataset expectations belong in `datasets.<name>.quality`, not in ad-hoc
transform-side clipping or filling. State the time field, expected
frequency/gap/freshness, duplicate policy, and per-field
missingness/domain/range/outlier thresholds when those facts are known.
Conservative profiling still runs without an explicit contract. Treat a
quality error as a failed build. For a warning, repair the producer only
when the evidence identifies an unambiguous pull/join/unit defect; if an
outlier, gap, or level break may be genuine, preserve it and surface the
structured evidence rather than altering observations.

Before a manifest-only phase references a new dataset or column, its CSV/transform output must already be provisioned and verified. If it is absent, finish the owning pull/transform edit first and only then apply typed manifest operations. `recompile=False` is not a substitute for phase data.

## Editing persisted scripts

Use the typed persisted-script transaction. Pass the complete inspection
state so the engine consumes the current script SHA and definition version
without manual guard copying:

```python
state = inspect_dashboard(FOLDER)
result = apply_persisted_script_operations(
    state,
    "pull_data",  # or "build"
    [{
        "op": "replace",
        "old": OLD_BLOCK,
        "new": NEW_BLOCK,
        "expected_count": 1,
    }],
)
```

Supported operations are `replace`, `insert_before`, `insert_after`, and
`append`. Anchored operations require an exact match count. The engine
syntax-checks and executes only module-level definitions to validate
`PULLS`/`TRANSFORMS`, atomically replaces the script object, strictly
builds current persisted data, and restores the script, manifest, and HTML
bytes on failure. Whole-script replacement is not accepted.

After a pull-script edit, run only the affected pull first and verify a
non-empty current-cycle CSV with the expected schema; then call
`launch_clean_refresh(FOLDER)`. The wrapper owns subprocess arguments,
environment markers, S3 log streaming, status collection, and failure
propagation. Inspect again after it succeeds.

For a multi-surface data change, order the transaction:

```text
pull script edit
  → run affected pull(s)
  → verify persisted columns and values
  → build script edit if derivation changes
  → typed manifest operations for new/changed slots and widgets
  → build_dashboard
  → launch_clean_refresh
  → inspect_dashboard
```

## Active-pipeline integrity

Before writing, use the inspection graph and persisted CSV schemas to prove:

- every existing `PULLS` entry remains present unless its entire product surface is intentionally removed;
- every registered producer output is resolved in
  `graph.pipelines[].csv_stems` or `graph.transforms`, with both unresolved
  lists empty;
- every pre-edit CSV still exists after the edit;
- every pre-edit column consumed by a widget, filter, transform, or source path remains;
- every template dataset has a pull or transform producer;
- every pull-produced CSV intended for display has a matching slot;
- all mapping/source/filter fields exist in the refreshed data;
- source cadence, units, as-of dates, and row cardinality remain plausible.
- each required CSV was produced successfully and verified non-empty in the current cycle; pre-existing object existence is not success.
- every data-quality error is absent and every warning is either repaired
  from conclusive evidence or reported as a potentially genuine feature;
  no script silently sorts, clips, imputes, deletes, or winsorizes it.

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
| Continue after a failed pull because its CSV exists | Build can consume the stale retained CSV |

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

Each provenance value is a dictionary. Native-source fields use `system` plus the exact supplied identifier (`symbol`, `haver_code`, `fred_series`, or another source-native key). Client-returned fields use the closed shape `{"system":"client","client":<exact imported client name>,"method":<exact called method>}` plus optional `identifier` only when the caller supplied that field/token; do not infer one from a display label. A deterministic user fixture uses `{"system":"fixture","source":"user_supplied","source_label":"User-supplied deterministic fixture"}` and may add supplied units/frequency; it has no invented vendor identifier. `display_name`, `units`, `frequency`, and `source_label` are optional source facts. A computed field uses `system: "computed"`, exact `recipe`, `computed_from`, and `units`. Never invent identifiers. Helper metadata sidecars and `df.attrs` never populate this structure; author it explicitly in the template.

## Refresh-frequency edits

Changing source cadence may require a dashboard cadence change. After data/script verification:

```python
state = inspect_dashboard(FOLDER)
synchronize_refresh_frequency(
    FOLDER,
    "1h",
    expected_sha256=state["manifest_template_sha256"],
    expected_current_version_id=state["versioning"]["current_version_id"],
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
- pull script parses and registered helper-aware pipeline stems match intent;
- transform helper call graphs materialize the intended derived slots;
- graph edges connect producer → CSV/transform → dataset → consumer;
- no attachment gaps;
- strict build succeeds;
- clean refresh status is success with no failed required pull and every expected CSV verified as non-empty current-cycle output;
- pre-existing pipeline outputs and consumed columns remain;
- no new relevant telemetry errors appear after the refreshed page is exercised.

Refresh has no universal per-pull timeout. Do not impose an arbitrary
authoring timeout; source-specific client timeouts still apply. If a pull
fails, reject any retained CSV at its stable key and stop before build.

If verification fails, follow the structured evidence, restore exact transaction bytes when needed, and retry before responding.
