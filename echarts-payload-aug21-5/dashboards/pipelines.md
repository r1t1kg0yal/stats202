# Data and script edits

- **Context ID:** `echarts.pipelines`
- **Owns:** `pipeline.graph`, `pipeline.reuse`, `pipeline.pull_edit`, `pipeline.transform_edit`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [dashboards_hub.md](../dashboards_hub.md#contract) and [diagnose.md](diagnose.md#structured-inspection).

This file is the sole owner of edits to persisted `scripts/pulls.json`, `scripts/build.py`, and their data-flow contract. Manifest layout edits belong to [template_crud.md](template_crud.md#manifest-operations).

## Persisted data flow

```text
scripts/pulls.json
  pulls[].name → engine calls get_data → data/<name>.csv
                         ↓
scripts/build.py
  CSV datasets → TRANSFORMS: datasets → datasets
                         ↓
manifest_template.json slots
                         ↓
build_dashboard → manifest.json + dashboard.html
```

Retrieval is declared and derivation is coded. A dashboard never calls `get_data`: it states each request in `scripts/pulls.json` and the engine validates, resolves and runs it. So the CSVs a refresh will write are readable without executing anything, and a pull cannot quietly do something other than retrieve.

Only the three persisted inputs—pull document, build script, and template—survive refresh. They are also the complete definition recipe recorded automatically after each successful changed build. CSVs, populated manifests, and HTML are current generated state, not version history.

`scripts/pulls.json` exclusively owns sources, identifiers, windows, and output names. `scripts/build.py` exclusively owns deterministic derivations and the ordered `TRANSFORMS` list; its namespace binds only `s3_manager`, `pd` and `np`, and no retrieval helper exists in it. The template owns dataset slots, field lineage, and consumers. Only flat `data/*.csv` files are loaded as datasets; JSON artifacts and metadata sidecars are ignored.

Start with:

```python
state = inspect_dashboard(FOLDER)
```

Use `state["graph"]` to see pull names, declared stems, transforms, dataset slots, widgets, filters, and edges. Read the current document and script bytes before editing; preserve unrelated entries and `TRANSFORMS`.

## Pipeline reuse decision

For each requested field or dataset:

1. **Reuse an existing dataset.** If the persisted CSV already contains the required columns, do not edit scripts.
2. **Derive from existing datasets.** If current pulls contain the inputs, add or update a `TRANSFORMS` function in `build.py`; no network pull is needed.
3. **Extend an existing pull.** If the source and cadence already exist but a field is missing, add the verified symbol/code/label to that entry while keeping its name.
4. **Add a pull.** Only when a genuinely new source/cadence/failure unit is required; add one entry.
5. **Escalate product meaning.** If data is unavailable or substitutes change the analysis, ask the user which product outcome they want. Never invent data.

Prefer the earliest valid path. Shared pipelines reduce API calls and keep one source of truth.

A pull is also the unit of refresh failure: each entry runs in its own boundary, so one dead source leaves the others current and stamps `metadata.time.stale_pulls` instead of aborting the cycle (see `dashboards_hub.md` — per-pull isolation). Two sources with independent availability therefore belong in two entries even when their columns land in one dataset slot; folding a flaky source into a healthy pull hands them a shared fate they do not have.

## Pull document

`scripts/pulls.json` is an ordered list of `get_data` requests. Each entry is a `name` and the `details` body for that source; the engine supplies `session_path`.

For most sources one entry writes one CSV, so the name is simultaneously the pull name, the CSV stem, and the manifest dataset key. The exceptions are the multi-table sources `lakehouse` and `gs_quant_reference`: they write one CSV per entry in their `tables` list, stemmed `<name>_<table label>`, so a single `ratings` entry declaring a `dbrs` table produces the stem `ratings_dbrs` and no `ratings.csv` at all. Every table needs an explicit `label` for that reason. Take stems from `declared_stems`, never by assuming they equal the names; and run pulls by iterating entry names, since one entry writes all of its tables in one call.

```json
{
  "schema_version": 1,
  "pulls": [
    {
      "name": "rates",
      "details": {
        "source": "tsdb_eod",
        "start": "2020-01-01",
        "end": "@today",
        "symbols": [
          {"symbol": "sofrswp2y", "label": "us_2y"},
          {"symbol": "sofrswp10y", "label": "us_10y"}
        ]
      }
    },
    {
      "name": "labor",
      "details": {
        "source": "client",
        "calls": [
          {"client": "fred", "function": "pull_fred_data", "label": "unrate",
           "arguments": {"codes": ["UNRATE"], "start": "2015-01-01",
                         "end": "@today"}}
        ]
      }
    }
  ]
}
```

A dashboard that retrieves nothing still persists `{"schema_version": 1, "pulls": []}`. The name must be filename-safe and unique; a repeat is refused rather than letting the later entry overwrite the earlier dataset. `session_path` is not writable.

Read the source's spoke through `market_data_infra_hub.md` before declaring the first entry for a given `source` in a session — the `details` shape is per-source and not guessable — and take identifiers from the guides it names. An exact code, expression, or client-call form supplied by the user is authoritative and is copied verbatim; never translate a human label into a vendor code. State each entry's expected output contract (stem, columns, dtypes, units, frequency) before authoring the manifest against it.

### Date tokens

A persisted literal `end` freezes, and the dashboard then goes stale while every refresh reports success. Use a token wherever the window should move:

| Token | Resolves to |
|---|---|
| `@today`, `@yesterday` | that UTC date |
| `@today-90d`, `@today-6w` | exact day/week offsets |
| `@today-18m`, `@today-6y` | calendar offsets, clamped to real month lengths |

Legal in `start`, `end`, `intraday_windows[].date`, and inside a client call's `arguments`. In the engine's own fields an unparseable `@...` raises; inside `arguments` it passes through, since that vocabulary belongs to the upstream function. Omitting `end` fills today for the sources whose model requires it.

### Stems

| Declaration | Emitted artifact and dataset key |
|---|---|
| any single-table source | `data/<name>.csv` → `<name>` |
| `source="lakehouse"` or `"gs_quant_reference"` | one `data/<name>_<label>.csv` per table; `<name>` alone is not a key |
| `save_artifact(frame or non-empty list[dict], name=...)` in `build.py` | `data/<name>.csv` → `<name>` |
| `save_artifact` with a dictionary or empty list | JSON artifact; no dataset key |

Multi-table sources require a literal `label` on every table; an unlabelled one is refused at write time, because the key would otherwise be unknowable until the pull ran.

### Behaviour worth knowing

Partial resolution never raises: a dead symbol omits its column and records the reason in the sidecar, so `run_pull` raises on the mismatch while authoring, and a scheduled refresh keeps the partial bytes and stamps the pull into `metadata.time.stale_pulls` rather than failing the cycle. The trusted series sources write the index as `timestamp` and the engine renames it to `date` on load, so author manifests, `dateRange` filters, and vintage labels against `date`. Series align on the union of their ticks, so mixing cadences in one entry leaves NaNs in the sparser column — drop per column, not across the frame.

`source="client"` is the only untrusted one: a summariser rewrites every text cell before the write, numbers and dates pass through, and a failed quarantine still writes an empty CSV with the reason only in the sidecar — assert expected columns rather than trusting that the file exists. Its `arguments` is the client function's own kwargs.

### What the document cannot express

One entry is one request, and retrieval is all it does. Three shapes therefore move rather than being encoded:

| Intent | Where it goes |
|---|---|
| Derive a frame from pulled data | a `TRANSFORMS` function in `build.py` |
| Two requests whose columns land in one slot | two entries plus a transform that joins them |
| A deterministic user-supplied fixture | `save_artifact` in `build.py`, values and nulls preserved |

A request that genuinely depends on an earlier response — screen for CUSIPs, then fetch their history — has no declarative form. Pull the screen, then make the dependent call in a transform that reloads the first entry's current-cycle CSV. Never consume a retained prior-cycle file implicitly.

When an external source is unavailable at predictable times, model that state explicitly. A dashboard may omit an intraday-only panel or show a product-level availability state, but it must not fabricate observations or silently substitute a semantically different series.

### Transform producer visibility

Transform keys are still read from code. The engine follows each registered `TRANSFORMS` function through local helper calls, propagating literal strings through assignments, helper parameters, f-strings, `datasets.update({...})`, and finite loops over literal lists, tuples, or dictionaries. Dataset keys are fixed by the template, so a data-dependent form such as `for key in runtime_names(): datasets[key] = ...` is rejected as `transform_producer_output_unresolved`, and a missing consumer reached alongside it is `dataset_<key>_producer_unresolved` rather than silent-stale. Make the fixed keys literal at the assignment, helper call, or finite literal loop; do not add dummy `datasets["key"] = datasets["key"]` assignments for the auditor. The registry is read the same way, so name every transform inside the single `TRANSFORMS = [...]` literal: one grown by `+`, `+=`, `.append`, or `.extend` still runs, but its additions are invisible to resolution.

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

## Editing the pull document

Write the whole document; there is no fragment operation, because JSON has
no hidden execution for a fragment edit to protect against. Pass the
inspection state so the engine takes the current SHA as its guard:

```python
state = inspect_dashboard(FOLDER)
document = state["scripts"]["pulls"]["document"]
document["pulls"].append({"name": "labor", "details": {...}})
result = apply_pulls_document(state, document)
```

Every entry is validated against `Details` before anything is written, so
a bad request leaves the prior document intact. `result["declared_stems"]`
is what the refresh audit will hold the dashboard to — read it back and
confirm it matches the template's dataset keys before compiling.

## Editing the build script

`apply_persisted_script_operations` edits `scripts/build.py` only, as typed fragment operations against exact source text, with rollback on failure. Pass a `describe_dashboard` or `inspect_dashboard` state: it carries the `scripts.build.sha256` guard, which a bare folder string does not.

| `op` | Keys | Effect |
|---|---|---|
| `replace` | `old`, `new` | Replace the exact fragment `old` |
| `insert_before` / `insert_after` | `anchor`, `text` | Insert `text` at `anchor` |
| `append` | `text` | Append at end of file |

`expected_count` (default 1) is how many times the anchor must occur.

Two constraints have no local symptom. The path needs the full canonical file set, so it opens only after the first publish — a first build writes `scripts/build.py` directly ([build.md](build.md#tool-2-template-transforms-compile)). And a review hold is the one failure that does not roll back: it keeps the candidate script so `review_dashboard` can reproduce that signature, so complete the publish path rather than re-applying fragments that would now miss or double-apply.

Both this and `apply_manifest_operations` take `dry_run=True`: no writes, no raise for an authoring fault, and every stage's complaints returned together in `findings`, with `would_raise` naming what the committing call would hit. Converge on `ok: True`, then repeat without it. A `would_raise` of `DashboardReviewRequired` means the edit is valid and needs the publish path, not a repair.

## Replacing a pull module with a document

A dashboard whose inspection reports `pulls_missing` while
`scripts/pull_data.py` appears in the folder listing keeps its retrieval in
that module. Nothing executes it and no converter exists — read it and
author the document yourself:

```python
src = s3_manager.get(f"{FOLDER}/scripts/pull_data.py").decode("utf-8")
print(src)
```

One entry per `get_data` call: `name` is the name that call passed, and for
every source but the two multi-table ones it is also the CSV stem that call
writes; `details` is the mapping it passed. Then commit and delete, in that
order:

```python
apply_pulls_document(FOLDER, {"schema_version": 1, "pulls": [...]})
s3_manager.delete(f"{FOLDER}/scripts/pull_data.py")
```

Four shapes need a judgment call rather than a transcription:

| In the module | In the document |
|---|---|
| A function retrieving twice | Two entries, one per request |
| A function that also derives | Entry keeps the retrieval; the derivation becomes a `TRANSFORMS` function in `scripts/build.py` |
| A window computed at runtime (`date.today()`, a module constant) | The `@today`-family token or literal date it was computing |
| A `get_data` whose `name=` differs from the key it was registered under | Entry name is the stem the call writes; repoint the template's dataset key to match |

Confirm `declared_stems` covers every dataset key the template consumes,
then build. A saved version created before the document reports
`retrieval: "scripts/pull_data.py"` and `restorable: false`;
`restore_dashboard_version` refuses it, since writing that recipe back
would leave the dashboard with no document at all. Rewrite the current
folder instead of reaching for an older definition.

After a pull-document edit, run only the affected pull first with
`run_pull(FOLDER, name)` and verify a non-empty current-cycle CSV with the
expected schema; then call `launch_clean_refresh(FOLDER)`. The wrapper owns
subprocess arguments, environment markers, S3 log streaming, status
collection, and failure propagation. Inspect again after it succeeds.

For a multi-surface data change, order the transaction:

```text
pull document edit
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

- every existing pull entry remains present unless its entire product surface is intentionally removed;
- every declared stem in `graph.pipelines[].csv_stems` has a dataset slot, and
  every transform output is resolved in `graph.transforms` with its unresolved
  list empty;
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
| Rename an entry | Consumers still point at the old stem |
| Freeze `end` on a literal date | Every refresh reports success while the data stops moving |
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
                "system": "tsdb_eod",
                "symbol": "<exact supplied symbol>",
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

Each provenance value is a dictionary. `system` is the call's `details.source` literal, and the identifier beside it is the one that call supplied — `symbol` for the TSDB and ChunkStore sources, `coordinate` for MDAPI, `haver_code` for Haver, `dataset` plus `field` for GS Quant, `service_uri` for Lakehouse. A `source="client"` field uses the closed shape `{"system":"client","client":<calls[].client>,"method":<calls[].function>}` plus optional `identifier` only when the caller supplied that field/token; do not infer one from a display label. A deterministic user fixture uses `{"system":"fixture","source":"user_supplied","source_label":"User-supplied deterministic fixture"}` and may add supplied units/frequency; it has no invented vendor identifier. `display_name`, `units`, `frequency`, and `source_label` are optional source facts. A computed field uses `system: "computed"`, exact `recipe`, `computed_from`, and `units`. Never invent identifiers. Helper metadata sidecars and `df.attrs` never populate this structure; author it explicitly in the template.

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

After any document or script edit:

```python
after = inspect_dashboard(FOLDER)
```

Require:

- no missing required files;
- the pull document parses and its declared stems match intent;
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
