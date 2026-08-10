---
class: context-extraction
topic: turn 2 — byte reconciliation of the 35-file contract + recovery of PRISM-side edits
sent: 2026-08-09
status: OPEN
follows: staging/prompts/open/2026-08-09_codebase_reorientation.md
reply_pointer:
fold_into:
  - projects/altair/altair-payload/chart_render/core.py (apply PRISM-side patches from 5ff6e3f + a1620b6)
  - projects/altair/altair-payload/chart_context*.md (overwrite from PRISM verbatim)
  - projects/echarts/echarts-payload/*.py + dashboards*.md (apply / overwrite per DIFFERS rows)
  - prism/codebase-tree.md, prism/architecture.md, prism/mcp-tools.md, prism/dashboards-portal.md
  - .cursor/rules/viz-platforms.mdc (runtime layout + drag-and-drop status)
---

**Staging-side note — do NOT paste this header into PRISM.**

Turn 1 established the structural picture. The load-bearing discovery is that
`prism-core` stopped being a submodule on 2026-08-07 (vendored into `prism-main`
by subtree commit `287311b`, submodule model retired by `3ec2ace`), so there is
now exactly one repo and byte parity is directly measurable for the first time.

The second discovery is a contract violation in our favour to fix: commits
`5ff6e3f` (2026-08-08, "Two new chart types under post-refactor chart system")
and `a1620b6` (2026-08-09, "Chart functions improvements") edited
`chart_render/core.py`, `chart_render/__init__.py`, `utils/chart_functions.py`
AND four `chart_context_*.md` spokes directly inside PRISM. Those files are
supposed to flow staging -> PRISM only. Our staging `core.py` is 1,233,020 bytes
/ 29,914 lines; PRISM's is 1,238,859 / 29,911. We need those bytes back here,
which per `.cursor/rules/viz-platforms.mdc` is a housekeeping intake (apply the
hunks exactly, do not re-derive).

Turn 2 therefore has two jobs: (1) mechanically classify all 35 contract files
MATCH/DIFFERS against hashes we computed locally, and (2) recover the diverged
content — as full verbatim for small files, as git patches for the multi-hundred-
KB ones. Sections 3-7 mop up what turn 1 trimmed.

---

## Paste everything below into PRISM

Second introspection pass. Same rules as last time: compute everything
programmatically, paste exact values, cite the absolute path you read each
answer from, keep my numbering, do not paraphrase, do not summarize, do not
report frictions. Long output is expected and welcome.

One global convention for this reply: **all byte counts, line counts and hashes
are computed on the file contents with any single trailing newline stripped.**
Your files mostly lack a trailing newline and mine mostly have one; stripping
first removes that systematic 1-byte difference so we compare real content. Use
this helper:

```python
import hashlib
def measure(path):
    b = open(path, "rb").read()
    if b.endswith(b"\n"):
        b = b[:-1]
    lines = b.count(b"\n") + 1 if b else 0
    return len(b), lines, hashlib.sha256(b).hexdigest()[:12]
```

### 1. Byte reconciliation of the 35-file contract

Below is my local measurement of every file in the staging→PRISM contract, as
`bytes / lines / sha256[:12]`, all newline-stripped. For each row report your
own measured triple and a verdict of exactly `MATCH` or `DIFFERS`. Produce it as
one table, same row order, so I can diff it mechanically. Add a final count of
how many MATCH and how many DIFFER.

| PRISM path | my bytes | my lines | my sha256[:12] |
|---|---|---|---|
| prism-core/prism_mcp/chart_render/__init__.py | 889 | 18 | `14b557525d20` |
| prism-core/prism_mcp/chart_render/core.py | 1,233,020 | 29,914 | `14bed9262faf` |
| prism-core/prism_mcp/chart_render/house_style.py | 24,348 | 643 | `87764b7e6031` |
| prism-core/prism_mcp/utils/chart_functions.py | 1,912 | 44 | `3e073301c31b` |
| prism-core/prism_mcp/utils/chart_functions_studio.py | 505,329 | 12,633 | `7fe095b1d04d` |
| prism-core/prism_mcp/utils/chart_functions_studio_tables.py | 232,445 | 5,657 | `73719f021e6b` |
| prism-core/context/modules/static/tools/chart_context.md | 22,223 | 385 | `bdf45ae81509` |
| prism-core/context/modules/static/tools/charts/chart_context_annotations.md | 7,791 | 157 | `1af059c6a29d` |
| prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md | 7,229 | 199 | `c745e896a912` |
| prism-core/context/modules/static/tools/charts/chart_context_composites.md | 6,647 | 167 | `c37fe279a38f` |
| prism-core/context/modules/static/tools/charts/chart_context_tables.md | 12,802 | 328 | `b416f11fe307` |
| prism-core/context/modules/static/tools/charts/chart_context_grids.md | 3,804 | 118 | `b3f03b5840d3` |
| prism-core/context/modules/static/tools/charts/chart_context_colors.md | 6,530 | 163 | `b8291188a9f1` |
| prism-core/dashboards/__init__.py | 9,835 | 269 | `970647c736f5` |
| prism-core/dashboards/config.py | 32,556 | 862 | `c24468f4d58d` |
| prism-core/dashboards/dashboards_time.py | 9,255 | 240 | `bdee435874b0` |
| prism-core/dashboards/echart_dashboard.py | 1,005,539 | 24,088 | `d7414bd6dc5a` |
| prism-core/dashboards/echart_studio.py | 311,916 | 7,539 | `f5f2240da4fc` |
| prism-core/dashboards/rendering.py | 796,826 | 20,419 | `bc98f75a441a` |
| prism-core/dashboards/refresh_runner.py | 27,272 | 659 | `3c9a71bddd5d` |
| prism-core/dashboards/dashboard_share.py | 29,348 | 808 | `05444d9a15e0` |
| prism-core/dashboards/dashboard_user_input.py | 26,465 | 847 | `c306c868656b` |
| jobs/hourly/refresh_dashboards.py | 30,902 | 781 | `887385607601` |
| prism-core/context/modules/static/tools/dashboards.md | 14,295 | 147 | `aaef1caad15a` |
| prism-core/context/modules/static/tools/dashboards_hub.md | 27,113 | 387 | `7c2039c00269` |
| prism-core/context/modules/static/tools/dashboards/build.md | 22,080 | 476 | `8361e041a996` |
| prism-core/context/modules/static/tools/dashboards/charts.md | 27,091 | 577 | `044314599b40` |
| prism-core/context/modules/static/tools/dashboards/diagnose.md | 25,607 | 348 | `9b9a079e3363` |
| prism-core/context/modules/static/tools/dashboards/filters.md | 13,313 | 364 | `e43765add13d` |
| prism-core/context/modules/static/tools/dashboards/pipelines.md | 18,291 | 389 | `2180176aa3b7` |
| prism-core/context/modules/static/tools/dashboards/productivity.md | 4,117 | 79 | `9c382918676d` |
| prism-core/context/modules/static/tools/dashboards/recipes.md | 15,258 | 411 | `d5bf6738a8ef` |
| prism-core/context/modules/static/tools/dashboards/template_crud.md | 15,866 | 385 | `13168d8c7ab7` |
| prism-core/context/modules/static/tools/dashboards/widget_tool.md | 14,919 | 348 | `f0f381c687f3` |
| prism-core/context/modules/static/tools/dashboards/widgets.md | 28,796 | 624 | `640ed37521cd` |

1.2 Turn 1 said there are **11** files under
`context/modules/static/tools/dashboards/`; my table has 10. List that directory
exhaustively (filename, bytes, lines, sha256[:12], last commit) and identify the
file I am missing. Same for `context/modules/static/tools/charts/` — confirm it
holds exactly the 6 I listed and nothing else.

1.3 List any other file anywhere in the repo whose content is authored by the
chart or dashboard staging pipeline but is NOT in my 35-row table. I want to
know what I should be owning that I currently am not.

### 2. Recover the PRISM-side edits (the important section)

Files in the contract were edited inside PRISM rather than in staging. I need
those bytes verbatim so I can fold them into the canonical copy.

2.1 For each of these paths, print the complete commit list since the subtree
vendor, newest first:

```bash
for p in prism-core/prism_mcp/chart_render/core.py \
         prism-core/prism_mcp/chart_render/__init__.py \
         prism-core/prism_mcp/chart_render/house_style.py \
         prism-core/prism_mcp/utils/chart_functions.py \
         prism-core/prism_mcp/utils/chart_functions_studio.py \
         prism-core/prism_mcp/utils/chart_functions_studio_tables.py \
         prism-core/dashboards/echart_dashboard.py \
         prism-core/dashboards/echart_studio.py \
         prism-core/dashboards/rendering.py \
         prism-core/dashboards/config.py \
         prism-core/dashboards/__init__.py \
         prism-core/dashboards/refresh_runner.py \
         prism-core/dashboards/dashboard_share.py \
         prism-core/dashboards/dashboard_user_input.py \
         jobs/hourly/refresh_dashboards.py ; do
  echo "=== $p"
  git log --oneline --format='%h %ad %an  %s' --date=short 287311b..HEAD -- "$p"
done
```

2.2 **Full patches.** For every commit that section 2.1 surfaces touching
`chart_render/core.py`, `chart_render/__init__.py`, or
`utils/chart_functions.py` — I already know about `5ff6e3f` and `a1620b6`, there
may be more — paste the complete unified diff, per commit, per file:

```bash
git show <sha> --format='%H %ad %an%n%s%n%n%b' --date=iso -- <path>
```

Paste them whole in fenced blocks. Do not abbreviate hunks, do not collapse
context lines, do not summarize what changed. These are patches I will apply
literally. If a single patch exceeds what you can return in one message, split
it across messages at hunk boundaries and say so.

2.3 Same treatment for any commit in `287311b..HEAD` touching
`prism-core/dashboards/*.py` or `jobs/hourly/refresh_dashboards.py`.

2.4 **Full verbatim files.** For every one of these that section 1 classifies
`DIFFERS`, paste the entire file contents verbatim in a fenced block, with its
byte count and line count. They are all small enough:

```
prism-core/prism_mcp/chart_render/__init__.py
prism-core/prism_mcp/utils/chart_functions.py
prism-core/context/modules/static/tools/chart_context.md
prism-core/context/modules/static/tools/charts/chart_context_annotations.md
prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md
prism-core/context/modules/static/tools/charts/chart_context_composites.md
prism-core/context/modules/static/tools/charts/chart_context_tables.md
prism-core/context/modules/static/tools/charts/chart_context_grids.md
prism-core/context/modules/static/tools/charts/chart_context_colors.md
prism-core/context/modules/static/tools/dashboards.md
prism-core/context/modules/static/tools/dashboards_hub.md
prism-core/context/modules/static/tools/dashboards/<each DIFFERS spoke>.md
prism-core/dashboards/config.py
prism-core/dashboards/__init__.py
prism-core/dashboards/dashboards_time.py
prism-core/dashboards/refresh_runner.py
prism-core/dashboards/dashboard_share.py
prism-core/dashboards/dashboard_user_input.py
jobs/hourly/refresh_dashboards.py
```

Prioritise in this order if you run out of room: the seven chart context files
first, then `chart_render/__init__.py` + `chart_functions.py`, then the
dashboards context files, then the Python. Tell me explicitly which ones you did
not get to.

2.5 For the four very large `DIFFERS` files where a patch is not available
(because the divergence predates `287311b`), emit a 1,000-line chunk hash ladder
so I can localise the deltas myself:

```python
import hashlib
for path in ["prism-core/prism_mcp/chart_render/core.py",
             "prism-core/prism_mcp/utils/chart_functions_studio.py",
             "prism-core/dashboards/echart_dashboard.py",
             "prism-core/dashboards/echart_studio.py",
             "prism-core/dashboards/rendering.py"]:
    b = open(path, "rb").read()
    if b.endswith(b"\n"):
        b = b[:-1]
    lines = b.split(b"\n")
    print(f"\n=== {path}  {len(b)} bytes  {len(lines)} lines")
    for i in range(0, len(lines), 1000):
        chunk = b"\n".join(lines[i:i+1000])
        print(f"{i+1:>6}-{min(i+1000, len(lines)):<6} "
              f"{hashlib.sha256(chunk).hexdigest()[:12]}  {len(chunk):>8}")
```

I will compute the same ladder locally, diff the two, and come back naming the
exact windows I need pasted.

2.6 State plainly, for the record: is there any process today by which files in
this contract get edited inside PRISM rather than in staging? If so, name who or
what does it and which paths are affected. I need to know whether to expect this
class of divergence again.

### 3. The context system, in full

Turn 1 trimmed `registry.py` and the loader. I need them whole.

3.1 Paste `prism-core/context/registry.py` in full, or if it is very large,
paste: (a) every entry whose `pillar` is `tools`, verbatim; (b) the full list of
all 105 `module_id`s with their `pillar`, `order`, and `source`; (c) the
complete `SPECIALIZATION_BUNDLES` dict verbatim.

3.2 Paste the loader function that turns a registry entry into text, with file
path and line numbers, and state the base directory `source` resolves against.

3.3 Recursively list `prism-core/context/modules/` with byte sizes, so I can see
the entire L2 surface and where my 13 files sit within it.

3.4 State the exact `list_ai_repo` call that successfully fetches
`chart_context_tables.md` and `dashboards/widgets.md` today. Specifically:
does the short form `charts/chart_context_tables.md` still resolve, or is a path
rooted at `context/modules/static/tools/...` now required? Show the path
resolution code in `developer_tools.py` that decides this, and if there is a
search-root list, paste it.

3.5 Paste the `list_ai_repo`, `get_context`, and `execute_analysis_script`
signatures and complete docstrings verbatim — turn 1 trimmed all three. Include
the tool schema presented to the model if it differs from the Python signature.

### 4. The sandbox namespace, in full

4.1 Paste the complete namespace-construction region of
`prism-core/prism_mcp/tools/script_exec_tools.py` — turn 1 gave me lines
2740-2800 trimmed and line 171 and 600-624 trimmed. I want every line that
assigns into the exec namespace dict, verbatim, plus every chart-related import
statement feeding it.

4.2 Produce the definitive alphabetical list of every name visible inside
`execute_analysis_script`, and for each: is it the raw object, a wrapped
callable, or a shim? Mark which come from `chart_render`, which from
`chart_functions`, and which from elsewhere.

4.3 The sandbox imports `prism_mcp.chart_render` directly per
`chart_functions.py`'s docstring, meaning trusted extensions are never
registered there. But turn 1's "Could not resolve" says the sandbox actually
runs **in-process with the MCP server, same interpreter**. Resolve this
tension explicitly: in the live deployment, when user code calls `make_chart`,
which module object does it get, and are the trusted extensions registered or
not at that moment? Show the import that decides it.

4.4 Given that, state what a `make_chart` call actually returns in production
today — presigned URL present or absent, studio companion present or absent —
and cite the code path rather than the docstring's design intent.

### 5. Download links, error mail, and the studio (the injected four)

`chart_functions.py` injects `presign`, `send_error`, `chart_studio`,
`table_studio`, `studio_dimension_presets`, `compute_chart_id`, `font_repo_root`.
Turn 1 flagged commit `8a5ccdd` "download links moving to portal shortlinks",
which lands directly on the first of those.

5.1 Paste `generate_presigned_download_url`'s current signature and full
docstring from `prism_mcp/utils/download_links.py`, plus that module's file size
and its full list of public functions.

5.2 Paste the full diff of `8a5ccdd` for `download_links.py`, and state what
changed about what a chart's download URL now is (presigned S3 URL vs portal
shortlink), what the URL looks like, and whether it expires.

5.3 Paste `send_error_email`'s signature from `prism_mcp/utils/error_handler.py`.

5.4 Confirm `chart_functions_studio.py` still exports `DIMENSION_PRESETS` and
`_compute_chart_id`, and that `chart_functions_studio_tables.py` is still
imported as `_table_studio`. Paste those symbols' definitions.

5.5 `vision_functions.py:299` still defines `check_charts_quality_parallel`
even though `72fb925` retired Gemini chart QC. Is that function still called
anywhere? Paste the diff of `72fb925` and say what remains live in
`vision_functions.py`.

### 6. The portal, which appears to have been restructured

Turn 1 reports `web/backend_django/manage.py`, `backend_django/settings.py` and
`wsgi.py` are all ABSENT, the only URLconf is `web/backend_django/news/urls.py`,
and there is a `web/prism_site/` tree (`css/composer.css`, `js/composer.js`,
`js/prism_menu.js`, `js/prism_menu_specs.js`, `templates/base.html`,
`templates/pages.html`) with uncommitted changes. My model of the portal is
badly out of date.

6.1 Recursively list `web/` to depth 4 with byte sizes.

6.2 Explain the relationship between `web/backend_django/` and
`web/prism_site/`: which serves traffic today, is one replacing the other, and
where is the Django settings module and WSGI/ASGI entry point actually defined?
Cite the code.

6.3 Paste `web/backend_django/news/urls.py` in full.

6.4 List every route that serves, refreshes, shares, or accepts input for a
dashboard: URL pattern, view function, file, and whether it is `@csrf_exempt`.

6.5 State the current status of Composer: paste `getWidgetSnapshot`'s full
definition from `rendering.py`, every call site of it, and confirm whether
`composer_dashboard_snapshot.py` exists anywhere.

6.6 Paste the diff of `2030db1` ("portal publish authz by caller identity") and
`8a5ccdd` for anything under `web/`.

### 7. Entry points and scheduling

7.1 Paste `entrypoint.py`'s registration region — every `@app.tool` / `@mcp.tool`
decorated function name with its one-line description, as a single list.

7.2 Paste the region of `entrypoint.py` around lines 570-600 that invokes
`jobs.hourly.refresh_dashboards`, and state exactly how and when it fires
(scheduler, interval, config file path).

7.3 Paste `entrypoint.sh` in full — turn 1 cites it for the `PYTHONPATH` export
and it defines the runtime path shape for every context.

7.4 State whether the refresh subprocess still shells out via `Popen`, and paste
that call site.

### 8. The 60-day change list, expanded

Turn 1's section 10 named eight structural commits from 1,011 commits. For each
of `3ec2ace`, `287311b`, `72fb925`, `50baa68`, `53c3bca`, `8a5ccdd`, `2030db1`,
give: full SHA, date, author, subject, body, and `--stat` output. Then answer:

8.1 Which of these changed a public interface that the chart engine or the
dashboard compiler calls?

8.2 `50baa68` retired `core/gs_llm.py` and `53c3bca` migrated to `agent()`. Does
either touch anything reachable from `chart_render/`, `dashboards/`, or the
sandbox namespace? Paste the new `agent()` entry point signature.

8.3 List every commit in the last 60 days that touched
`prism-core/context/modules/static/tools/**`, with its `--stat`, so I can see
every PRISM-side edit to my skill files.

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
permission denied, output too large), add a brief `## Could not resolve` section
at the end listing what you tried and what blocked it. If you must truncate for
size, truncate section 8 first and section 2 last — section 2 is the one I
cannot proceed without.
