---
class: context-extraction
topic: altair post-drop verification -- the 14 installed files against staging's bytes, nothing else touched, the PRISM-owned mirrors' bytes after the 2026-10-13 change, PRISM's chart and context tests on the dropped tree, a direct render smoke, the sandbox image's interpreter, and a merge verdict
expected_reply: ~10-20 KB (one hash table, git status, per-test counts, smoke results, interpreter versions, verdict)
created_at: 2026-10-12
sent: no
status: OPEN
trigger: >
  The go/no-go reply (staging/prompts/archive/2026-10-11_altair_promotion_readiness.md)
  cleared the drop but could not run the swapped-payload tests, because the
  staging copy was not in the checkout. The transfer path has also altered
  files before: the 2026-09-28 promotion landed with its em-dashes deleted,
  and the old/core.py PRISM compared on 2026-10-11 measured 8,276 bytes more
  than canonical. So the installed bytes are checked, not assumed. Separately,
  the staging venv moved to Python 3.10.18 on 2026-10-14 to match production,
  but the prism-sandbox gateway image -- where attributed render_charts calls
  execute -- has never had its interpreter measured (§5).
reply_folds_into:
  - .cursor/rules/prism.mdc § "The single virtualenv" and requirements.txt (sandbox interpreter, from §5)
  - prism/codebase-tree.md (sandbox observed-vs-intended, from §5)
  - projects/altair/dev/test_chart_exec.py (TestOwnership.PRISM_MIRRORS, from §2.4)
  - prism/subagents.md and prism/codebase-tree.md §8 (the 2026-10-13 mirror change, from §2.4)
  - staging/README.md and projects/altair/README.md (drag-and-drop status -> promoted)
  - .cursor/rules/viz-platforms.mdc (promotion status paragraph)
  - prism/codebase-tree.md §8 (inventory sizes, test counts)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

Send this after copying the 14 files from `staging/altair-payload/` over their
install paths in the prism-main working tree, and before committing, merging or
tagging. `test_prompts/` does not ship. The install paths:

```
staging/altair-payload/chart_render/*.py   ->  prism-core/prism_mcp/chart_render/
staging/altair-payload/utils/*.py          ->  prism-core/prism_mcp/utils/
staging/altair-payload/chart_context.md    ->  prism-core/context/modules/static/tools/
staging/altair-payload/chart_context_*.md  ->  prism-core/context/modules/static/tools/charts/
```

Six of the 14 are already byte-identical to production, so only `core.py` and
the seven context files should show up as modified. If §1 reports a DIFFER, the
transfer altered the file; re-copy it rather than editing it in PRISM.

---

## Paste everything below into PRISM

The staging copy of the chart engine has just been copied into the working
tree. This is read-only verification plus one test run, before anything is
committed. Do not edit, stage or commit any file. You may run Python in
`execute_analysis_script` and create a temporary copy of the repository for §3
and §4.

Answer from live source, not from remembered context or a previous turn's
summary. Give repository-relative paths from the `prism-main` root with
`path:line` citations, and quote code **verbatim in fenced blocks**.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### 1. The installed bytes

Read each file's raw bytes from the working tree and give its byte count and
sha256[:16] beside ours, marking each row MATCH or DIFFER:

| Install path | Bytes | sha256[:16] |
|---|---:|---|
| `prism-core/prism_mcp/chart_render/__init__.py` | 882 | `a2d6203351e2f500` |
| `prism-core/prism_mcp/chart_render/chart_functions_studio.py` | 505,482 | `5122e0eb5257f113` |
| `prism-core/prism_mcp/chart_render/chart_functions_studio_tables.py` | 243,262 | `29309f77d82d50a2` |
| `prism-core/prism_mcp/chart_render/core.py` | 1,712,421 | `99705288444f8134` |
| `prism-core/prism_mcp/chart_render/house_style.py` | 25,860 | `7a0f326a32cea63b` |
| `prism-core/prism_mcp/utils/chart_functions.py` | 1,392 | `ca611351d5c03073` |
| `prism-core/prism_mcp/utils/vega_node_check.py` | 3,899 | `1d9a5f18bf60b175` |
| `prism-core/context/modules/static/tools/chart_context.md` | 42,534 | `376442dd3feef1c1` |
| `prism-core/context/modules/static/tools/charts/chart_context_annotations.md` | 10,947 | `8ba22cf4e4f9f59e` |
| `prism-core/context/modules/static/tools/charts/chart_context_colors.md` | 10,124 | `3f614b548d74c151` |
| `prism-core/context/modules/static/tools/charts/chart_context_composites.md` | 8,979 | `c4aef463748510d1` |
| `prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md` | 7,617 | `e1ab6fb1c6affcf5` |
| `prism-core/context/modules/static/tools/charts/chart_context_grids.md` | 5,154 | `9ef35755cd392cde` |
| `prism-core/context/modules/static/tools/charts/chart_context_tables.md` | 15,257 | `f1919cb8f49ed446` |

For each DIFFER, give the unified diff against what we expect if you can infer
it (up to 60 lines), and say what kind of change it is (characters deleted,
line endings, encoding, truncation).

### 2. Nothing else moved

1. `git status --short` for the whole tree. List every modified, added or
   deleted path. We expect exactly `core.py` and the seven context files,
   plus the two unrelated dirty files your last reply saw
   (`core/config/environments/local/common.yaml`, `core/configs/model_catalog.py`).
2. Confirm `prism-core/prism_mcp/chart_render/units.py` is still 8,004 bytes,
   and that nothing under `prism-core/prism_mcp/tools/` or `core/` changed.
3. Count the em-dash characters (U+2014) in the seven installed context files.
   We expect zero.
4. For each of these three PRISM files, give the byte count, sha256[:16], and
   `git log -1 --format='%h %ad %s' --date=short` on it. Ours come from
   applying the review diff of a change that adds `ladder_attempt` to
   `record_render_call`, tags an explicit `save_as` in `_nonce_prelude`, and
   strips `<thought>` blocks in `_image_transport_trailer`. If that change is
   not on the branch you are reading, say so rather than marking DIFFER.

   | Path | Bytes | sha256[:16] |
   |---|---:|---|
   | `prism-core/prism_mcp/tools/chart_exec.py` | 43,622 | `1dfc0b5e06a00d58` |
   | `core/chart_agent_tool.py` | 13,532 | `0fccee122bfb5fee` |
   | `prism-core/prism_mcp/utils/chart_call_log.py` | (not mirrored) | -- |

   For `chart_call_log.py`, also quote the `record_render_call` signature
   verbatim.

### 3. Tests on the dropped tree

In a temporary copy of the working tree as it now stands (delete it
afterwards), run the set your go/no-go reply ran as its baseline at
`fb1e4852f`, and report pass / fail / error counts per file beside that
baseline, with the first 30 lines of each failure:

| File | Baseline |
|---|---:|
| `prism-core/tests/test_secure_exec.py` | 104 |
| `prism-core/tests/test_chart_exec_gates.py` | 13 |
| `prism-core/tests/test_chart_exec_sandbox_seam.py` | 13 |
| `prism-core/tests/test_model_facing_s3_reader_gates.py` | 31 |
| `prism-core/tests/context/test_okf_floor.py` | 18 |
| `prism-core/tests/context/test_no_dangling_references.py` | 3 |
| `tests/core/test_subagent_deadline.py` | 4 |
| `tests/test_artifact_delivery_contract.py` | 37 |
| `tests/test_sandbox_image_layout.py` | 2 |
| `tests/web/test_composer_artifact_authz.py` | 72 |

Add any other test file that imports `prism_mcp.chart_render`,
`prism_mcp.utils.chart_functions` or `prism_mcp.tools.chart_exec`
(`test_chart_call_log.py`, `test_studio_copy_controls.py` if present). Then run
`python context/build_index.py --check` and report its output.

### 4. A direct render

In a fresh interpreter rooted at the temporary copy, import the engine the way
the sandbox does (`from prism_mcp.chart_render import make_chart, make_table`)
and render, to a temporary directory:

1. a `timeseries` of two series over 24 monthly points,
2. a `bar` of five categories,
3. a `make_table` of four rows and three numeric columns.

Each with `title=` and `source="BLS via Haver Analytics"`, plus `session_path=`
and an `s3_manager` writing to the temporary directory if the core asks for
them. For each, report
`success`, the PNG's pixel size, and every entry on `warnings`. Then confirm
that `core.register_studio()` and `_gs_font_dir()` resolve in that interpreter,
and that every name `prism_mcp/sandbox/chart_names.py` lists in
`WRAPPED_CHART_FUNCS` exists on the imported module.

### 5. Interpreters

1. Report `sys.version` for the interpreter §3 and §4 ran in.
2. Find the Dockerfile for the prism-sandbox gateway image -- the one that
   does `COPY prism-core/prism_mcp/chart_render /app/prism_mcp/chart_render`.
   Quote its `FROM` line(s) verbatim with `path:line`, plus any line that
   installs, pins or selects a Python version.
3. If `requirements-sandbox-arm64.txt` carries a header naming the interpreter
   it was compiled for, quote it.
4. State which Python version the sandbox image runs, or say it cannot be
   determined from source and what would settle it.

### 6. Verdict

**SAFE TO COMMIT** or **NOT** (name each problem). Then list the steps that
remain before a user's chart runs this engine, per your go/no-go reply §7.2.

---

## Reply structure

One `##` heading per section above, numbered the same. Put §1 in one table.
