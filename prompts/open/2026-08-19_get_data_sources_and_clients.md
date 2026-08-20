---
class: context-extraction
topic: get_data per-source mechanics — all nine sources, the client allowlist, and what retirement of the curated helpers actually means
expected_reply: ~28 KB
created_at: 2026-08-19
sent:
status: OPEN
trigger: >
  Follow-on to 2026-08-19_get_data_contract.md (archived). That reply gave the
  function, the Details discriminated union, persistence, and execution context
  — but almost entirely through the tsdb_eod lens. Eight of the nine sources
  were named in a table and never opened. The user has since stated that
  get_data is the single canonical retrieval path and that pull_haver_data,
  pull_fred_data, pull_nyfed_data and every other retrieval helper are done.
  If that holds, the echarts dashboards layer can collapse five pull primitives
  to one, shrink the injected namespace, make static stem inference exact, and
  reduce the provenance vocabulary to the details.source literals. Every one of
  those changes is unsafe to make while eight source shapes and the client
  allowlist are unread.
reply_folded_into:
  - prism/data-functions.md                                    # §2 per-source models, §3 persistence matrix
  - prism/api-clients.md                                       # how source="client" relates to the 17 clients
  - projects/echarts/echarts-payload/echart_dashboard.py       # namespace collapse, _PULL_PRIMITIVES, partial-series detector
  - projects/echarts/echarts-payload/dashboards.md             # pull primitives table
  - projects/echarts/echarts-payload/dashboards/pipelines.md   # stem rules, client indirection, provenance
  - projects/echarts/echarts-payload/dashboards/build.md       # canonical pull_data.py example
---

**Staging-side note — do NOT paste this header into PRISM.**

Why this prompt exists. Three concrete decisions are blocked on it.

1. **Namespace collapse.** `_build_dashboard_exec_namespace` currently injects
   `pull_haver_data`, `pull_plottool_data`, `pull_fred_data`, `pull_nyfed_data`,
   `save_artifact`, `s3_manager`, `pd`, `np`. If the curated helpers are truly
   retired the injection list shrinks to almost nothing — but injecting a name
   PRISM has deleted is a P0 `ImportError` on promotion, and *removing* one that
   the persisted corpus still calls is a P0 `NameError` on refresh. We already
   took that hit once with `pull_market_data`. Section 1 decides it.

2. **The partial-series detector we just shipped.** The engine now reads
   `<stem>_metadata.json`, shape-detects `requested`/`resolved`/`series`, and
   marks a pull stale when it came back short. That detector was written from a
   single `tsdb_eod` sidecar example. If `client`, `haver`, `lakehouse` or the
   MDAPI sources write a different sidecar shape, the detector silently stops
   covering them. Sections 4 and 5 decide it.

3. **Whether `source="client"` removes the save_artifact indirection.** Today
   the context teaches: call the client, get an object back, persist it yourself
   through `save_artifact` or an explicit CSV write. If `source="client"`
   persists a bindable CSV directly, an entire pattern leaves the skill. But
   `client` is the only `UNTRUSTED` source and routes through a quarantine
   summariser, and we do not know whether the persisted bytes are the raw data
   or the summariser's output. Section 3 decides it, and it is the single most
   important section in this prompt.

Sections 1-5 are blocking. 6-8 are what we need to teach the spokes correctly.

---

## Paste everything below into PRISM

This is read-only source introspection for external documentation. Do not build
a dashboard, do not pull any data, do not edit or create any file, and do not
report frictions. Do not answer from remembered context, from a context module,
or from the previous turn's summary where live source is available — open the
file and cite it. Where a previous answer and the current source disagree, say
so explicitly.

Give repository-relative paths from the `prism-main` root, with `path:line`
citations. Quote signatures, class definitions, field lists, docstrings and
literals **verbatim in fenced code blocks**; do not paraphrase them.

**Reply budget: keep this under roughly 28,000 characters.** Sections 1-5 are
the priority. If you run long, stop at a section boundary and name what remains
rather than compressing the early sections.

### 1. Which retrieval helpers still exist

For **each** of these six names — `pull_haver_data`, `pull_fred_data`,
`pull_nyfed_data`, `pull_plottool_data`, `pull_market_data`, `save_artifact`:

1.1 Does a definition exist in the live tree right now? Give `path:line` or
state that a repo-wide search returned nothing. Say exactly what you searched.
Note that our copy imports five of these from
`prism_mcp.utils.data_functions` but `pull_nyfed_data` from
`core.mcp.clients.newyorkfed_client` — confirm or correct **both** import paths,
since a moved module is as fatal to us as a deleted one.

1.2 If it exists, is it (a) fully functional, (b) a translator/shim onto
`get_data`, (c) deprecated with a warning, or (d) defined but raising? Quote any
deprecation text or `raise` verbatim.

1.3 Is it injected into each of these three namespaces — the
`execute_analysis_script` sandbox, `prism-core/dashboards/echart_dashboard.py::_build_dashboard_exec_namespace`,
and whatever namespace `refresh_runner.py` uses? Paste the **current injected
name list for each of the three, verbatim**, so we can diff against our copy.

1.4 Summary line per name: `KEEP` (still the right thing to author),
`LEGACY` (works, do not author new), or `GONE`.

### 2. The eight unopened source models

The previous reply gave `TsdbEodDetails` and `TsdbSymbol` verbatim and listed
the other eight in a one-line-each table. Open them now.

2.1 For **each** of `chunkstore`, `tsdb_intraday`, `client`, `mdapi_eod`,
`mdapi_intraday`, `gs_quant_dataset`, `haver`, `lakehouse`: paste the
**complete model class verbatim** — every field, type annotation, default, and
validator — plus any nested model it references that was not already covered by
`TsdbSymbol`.

2.2 For each, state in one line what the caller must supply that is *not*
obvious from the field names — the thing an author gets wrong on the first try.

2.3 Which sources take a symbol/series list and which take something else
entirely (a table name, a dataset id, a coordinate, a method call)? Give the
grouping explicitly; our compiler currently assumes every source is a
symbols-onto-one-index shape and we know at least `lakehouse` is not.

### 3. `source="client"` in depth — the blocking section

3.1 Paste the `client` model verbatim, including how the target client and the
method are named.

3.2 **The allowlist.** Where is it defined? Paste it verbatim. Is it a literal
list, a registry lookup, an import check, or a decorator? Name every client
currently on it.

3.3 How does an allowlisted client's method get called — positional args, a
params dict, a serialized blob? Paste the dispatch site.

3.4 **Quarantine.** `client` is the only `UNTRUSTED` source. Trace what actually
happens to the returned payload:

- Is the **persisted CSV** the raw client response, or the summariser's output?
- Does the summariser run before or after the file is written?
- Does `summarisation_instructions` change the persisted bytes, or only the
  text returned to the model?
- Is there any path where a `client` pull writes **no** CSV at all?

Cite the write call and the quarantine call and show their order.

3.5 **The question this all serves:** can a dashboard bind a manifest dataset
key directly to a `source="client"` pull's CSV, the same way it binds a
`tsdb_eod` pull, with no `save_artifact` step and no post-processing? Yes or no,
then the evidence.

3.6 Paste a **complete, currently-correct** `get_data` call for FRED — series
`UNRATE`, 2015 to today — exactly as you would author it. Then the same for a NY
Fed call of your choosing. State the resulting CSV path and column headers for
each.

3.7 If FRED or NY Fed is *not* reachable through `get_data` at all, say so
plainly and name what the current correct path is. Do not construct a
speculative call.

### 4. Persistence matrix — one row per source

Our loader scans `<folder>/data/*.csv` and uses the filename stem as the dataset
key, so on-disk bytes matter more than return values.

4.1 Build a table with one row per source and these columns:

| source | exact object key(s) written | index/first column name | `_metadata.json` written? | `_freshness.json` written? |

Fill every cell from source, not from inference. Where a source writes multiple
objects (lakehouse), show the pattern.

4.2 Is the first column **always** named `timestamp` for the series sources? Name
every source where it is something else, and say what.

4.3 Is `name` reaching the filename verbatim for every source, or does any
source transform it? We know `lakehouse` treats it as a directory. Any others?

4.4 Can two different sources in the same session write the same `name` and
silently overwrite each other? Is there any collision detection?

### 5. Sidecar shape and failure semantics per source

Our engine now shape-detects the sidecar by looking for integer `requested` and
`resolved` keys plus a `series` list, and treats `resolved < requested` as a
partial pull.

5.1 Paste a **real example `_metadata.json` for each source family** — one
symbols-based source, `client`, `gs_quant_dataset`, and `lakehouse` at minimum.
We have the `tsdb_eod` one already.

5.2 Are `requested` and `resolved` present for **every** source, or only the
symbols-based ones? If a source omits them, what is the equivalent coverage
signal in its sidecar?

5.3 Is per-series failure isolation — one series fails, the others still land,
the call returns normally — universal across sources? Name any source where a
single failure aborts the whole call, and any where the call **raises** instead
of recording the error.

5.4 Paste the exact keys a **failed** series record carries. The previous reply
mentioned `error` and `error_class`; confirm the full set and whether they
appear in the same `series` list as successful records.

5.5 For `lakehouse` specifically: the previous reply said records carry
`rows`/`cols`/`connect_s`/`stream_s`/`elapsed_s`/`truncated`/`budget_enforced`
under a `files` key. Confirm, and say what a *failed table* looks like.

### 6. Discovery per source

6.1 For each source, name the context module or helper that turns a human
request into a valid identifier — the equivalent of `explore_haver()` for Haver.
Give the exact module filename so we can cite it in a routing table.

6.2 Confirm the spoke filenames. These come from an earlier reply of yours and
have never been verified against the tree:

```
market_data_infra_hub.md
market_data_infra_spoke_chunkstore.md
market_data_infra_spoke_tsdb.md
market_data_infra_spoke_gs_quant_mdapi.md
market_data_infra_spoke_gs_quant_datasets.md
market_data_infra_spoke_internal_clients.md
market_data_infra_spoke_haver.md
market_data_infra_spoke_lakehouse.md
lakehouse_hub.md
```

For each: does the file exist at that exact path? Give the real path if it
differs, and name any that do not exist at all. Is `market_data_infra_hub.md`
registered, and at what `order`?

6.3 Does `source="haver"` still require the `explore_haver()` discovery step
before a pull, or does the spoke replace it?

### 7. Can the engine call `get_data` itself

We are considering letting `scripts/pull_data.py` declare pulls as **data**
rather than code — `PULLS = {"rates": {"source": "tsdb_eod", ...}}` — and having
the dashboard engine construct and await the `get_data` call. That would remove
the asyncio/pydantic boilerplate from every authored script and make our static
stem inference exact instead of AST-parsed.

7.1 Is there anything in `get_data` that requires it be called **from the
authored script's frame** rather than from engine code — implicit session state,
a caller-derived identity, an auth context, a contextvar, a tool-invocation
record, telemetry that keys off the call site?

7.2 Is `session_path` the only thing tying a call to a session, or is there
hidden session coupling?

7.3 Would calling it from the clean refresh subprocess (a plain CPU process, no
MCP registry, no chat session) behave identically to calling it from the
in-process dashboard exec? Any difference in auth, proxy, timeout, or
concurrency?

7.4 Is there a supported way to validate a `details` dict **without executing
the pull** — so we could pre-flight an authored dashboard at build time and
reject a malformed `details` before the first refresh?

### 8. What still needs `save_artifact`

8.1 Assuming `get_data` covers all retrieval, what categories of dashboard
dataset still require `save_artifact` or an explicit CSV write? Computed frames
from `build.py` transforms, user-supplied fixtures, anything else?

8.2 Is `save_artifact` itself staying, or is it also being folded into something?

8.3 Does `get_data` emit anything per column that identifies the upstream system
— in the sidecar, in `df.attrs`, or in the return value — that a dashboard build
could **read** rather than having the author hand-write a `field_provenance`
block? The previous reply said there is no canonical `system` string; confirm
whether there is now, given we have minted the `details.source` literals on our
side.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
