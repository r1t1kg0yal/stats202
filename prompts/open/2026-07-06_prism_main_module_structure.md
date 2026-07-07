# Context-extraction prompt — prism-main repo layout + full module/import structure

**Why this exists (staging-side note, do NOT paste this header into PRISM):**
The 2026-07-04 friction-detection scans leaked tracebacks showing PRISM now
runs from a `prism-main/` repo with a `prism-core/prism_mcp/` package tree —
not the `ai_development/mcp/` layout every staging document (viz-platforms
rule, prism.mdc mapping table, `prism/codebase-tree.md`, `prism/mcp-tools.md`,
`prism/_prompting-guide.md`, both platform READMEs) still describes. The Jul 4
housekeeping pass already flipped the altair payload's imports to
`prism_mcp.utils.*` / `prism_meta` and created partial stubs, but the staging
repo still carries the stale `ai_development/` stub tree side by side, the
`prism_meta` stub had to be reconstructed by guess, and the echarts payload
still resolves its static asset via a cwd-relative `ai_development/...` path
that may now be dead in prod. This prompt extracts the complete current
structure so every staging doc, rule, and stub mirror can be rewritten in one
pass instead of patched per-discovery. Reply lands back here; fold-in updates:
`.cursor/rules/viz-platforms.mdc`, `.cursor/rules/prism.mdc` mapping table,
`prism/_prompting-guide.md`, `projects/altair/README.md` + stub mirror,
`projects/echarts/README.md` + static-asset mirror, `staging/README.md`.
Move this file to `staging/prompts/archive/` once folded.

---

## Paste the following into PRISM

You are being asked to introspect your own codebase's file organization and
import architecture and report it verbatim. Use `list_ai_repo` /
`execute_analysis_script` / direct source reads as needed. Do not paraphrase
and do not summarize: paste exact paths, exact source lines, and exact dict
literals in fenced code blocks, and name the actual file path (+ line range
where relevant) you read each answer from. Where a question asks for a tree,
generate it programmatically (e.g. `os.walk`) rather than from memory.

### 1. Repo root and top-level map

1.1 Print the absolute path of the repository root your code runs from (the
directory historically called the "AI repo root"), and state how you
determined it (env var, `__file__` anchoring, cwd, a `REPO_ROOT` constant).

1.2 Paste a directory tree of the repo root, two levels deep, with per-file
sizes in KB for files and child counts for directories. Exclude caches,
`.git`, and virtualenvs. If the repo is split across multiple roots (e.g. a
`prism-main/` outer checkout containing a `prism-core/` inner package), show
the full outer tree and say explicitly which directory is which.

1.3 For every top-level directory in that tree, one line: what lives there
and whether it is importable Python (a package root on `sys.path`), static
content, or infrastructure.

### 2. Old-path to new-path mapping

For EACH old path below (this is the layout our external docs still assume),
state its current status: the exact new path if moved/renamed, `UNCHANGED` if
still there, or `DELETED` (with where its responsibilities went). Verify each
by listing the file, not from memory.

```
ai_development/mcp/utils/chart_functions.py
ai_development/mcp/utils/chart_functions_studio.py
ai_development/mcp/utils/download_links.py
ai_development/mcp/utils/error_handler.py
ai_development/mcp/utils/unit_helper_functions.py
ai_development/mcp/utils/vision_functions.py
ai_development/mcp/tools/script_exec_tools.py
ai_development/mcp/tools/  (list_ai_repo / RepositoryExplorer home)
ai_development/mcp/gs_app_proxy_negotiate.py
ai_development/mcp/clients/  (external API clients, ~20 modules)
ai_development/dashboards/  (echarts dashboard compiler: __init__.py,
    config.py, dashboards_time.py, echart_dashboard.py, echart_studio.py,
    refresh_runner.py, rendering.py)
ai_development/jobs/hourly/refresh_dashboards.py
ai_development/context/modules/static/chart_context.md
ai_development/context/modules/static/chart_context_grids.md
ai_development/context/modules/static/chart_context_colors.md
ai_development/context/modules/static/tools/dashboards.md
ai_development/context/modules/static/tools/dashboards_hub.md
ai_development/context/modules/static/tools/dashboards/  (spoke .md + .json)
ai_development/context/white_papers/
mysite/news/static/js/echarts.js
```

Also name any NEW top-level module or package that exists today but appears
nowhere in the list above (e.g. `param_validator`, `code_execution`,
`prism_meta`) — for each: path, one-line purpose, and who imports it.

### 3. Import architecture and sys.path mechanics

3.1 Paste verbatim the full import block at the top of
`prism_mcp/utils/chart_functions.py` (every `import` / `from ... import`
line before the first class or function definition), plus any mid-file
imports of `prism_meta` or other repo-local modules (search the file for
`^from prism` and `^import prism`).

3.2 Paste the COMPLETE contents of the `prism_meta` module (it should be
small). State its exact file path and what `REPO_ROOT` resolves to at
runtime (print it).

3.3 Explain concretely how `prism_mcp`, `prism_meta`, and `core` become
importable: which directories are on `sys.path` and what puts them there
(pyproject/setup editable install, PYTHONPATH, sys.path.insert in an
entrypoint, launcher script). Paste the relevant configuration or code.
Then, from inside `execute_analysis_script`, run and paste the output of:

```python
import sys, os
print(os.getcwd())
print([p for p in sys.path if 'prism' in p.lower() or p in ('', '.')])
import prism_mcp, prism_meta, core
print(prism_mcp.__file__, prism_meta.__file__, core.__file__)
```

3.4 Font resolution: confirm the directory
`<REPO_ROOT>/web/backend_django/fonts/` exists and list its exact contents
(filenames). If chart/table code resolves fonts through a different anchor,
paste that resolution code verbatim.

### 4. The sandbox wiring (script_exec_tools + new validation layers)

4.1 Paste verbatim the `from prism_mcp.utils.chart_functions import (...)`
line(s) at the top of the current `script_exec_tools.py`, with its absolute
path and current line count.

4.2 Paste verbatim the chart/table-related auto-injected namespace block
(every `"name": ...` entry in that group, in order, with the total count),
including how each is wrapped (`_wrap_chart_func`, partial application of
`s3_manager`, etc.).

4.3 `prism_mcp/utils/param_validator.py` appeared in a recent traceback and
is new to us. Paste its full contents (it looked small — a decorator with a
`wrapper` at ~line 52). State which functions it wraps and where it sits in
the call chain relative to `_wrap_chart_func`.

4.4 `core/code_execution.py` also appeared (with `_execute_sync` at ~line
114). Paste the module's public surface: its imports, every top-level
def/class signature with docstring first lines, and the body of
`_execute_sync`. Explain its division of labor vs `script_exec_tools.py`
(who owns the exec namespace, who owns timeouts, who owns error emails).

4.5 Confirm or correct: `script_exec_tools.py` is still the SOLE importer of
`chart_functions.py` symbols anywhere in the codebase. Show the search you
ran (e.g. grep for `chart_functions import` across the repo) and its output.

4.6 Background-subprocess mode: paste the code that builds the background
subprocess's namespace/preamble and state exactly which chart/QC names it
injects vs the foreground path (a recent session hit `NameError:
check_charts_quality` in background mode — show where that divergence lives).

### 5. Context-module loading paths

5.1 Where do L2 static context modules live now (absolute directory)? Paste
the directory listing for the folder(s) containing `chart_context*.md` and
`dashboards*.md`.

5.2 Paste the exact `file_paths=[...]` strings that currently resolve when
fetching `chart_context_grids.md` / `chart_context_colors.md` /
`dashboards_hub.md` mid-session via `list_ai_repo(mode="full")` — i.e. what
path prefix does the tool expect after the reorganization?

5.3 If `get_context` / bundle assembly changed its module-resolution root as
part of the move, paste the resolution code (the part that maps a module
name like `chart_context` to a file on disk).

### 6. Dashboards / echarts side

6.1 State the current absolute directory of the dashboard compiler modules
(`rendering.py`, `echart_dashboard.py`, etc.) and paste the import lines at
the top of `echart_dashboard.py` (bare-module imports like
`from rendering import ...` — do they still work, and from what sys.path
root?).

6.2 Paste verbatim the current body of `_get_echarts_js()` (or whatever now
resolves the echarts JS asset) in `rendering.py`, including the exact path
expression. State the absolute path it resolves to at runtime and confirm
the file exists there. If the old
`os.path.join(os.getcwd(), "ai_development", "mysite", ...)` expression
survived the reorganization unchanged, say whether it still resolves and why
(symlink, cwd convention, copied tree).

6.3 State the current location and invocation path of the hourly dashboard
refresh job (`refresh_dashboards.py`) and paste its import lines.

### 7. S3 / storage layer

7.1 State the file that defines the S3 bucket manager class the sandbox's
`s3_manager` is an instance of, paste the class signature +
`__init__` signature, and the `put` / `get` signatures. Note anything that
changed about session-path nesting behavior in the move.

7.2 Paste the current signature + return type of
`generate_presigned_download_url` and its module path.

### 8. Drift check (installed payload vs staging)

Report size in KB and line count for each of the following as installed in
you right now, so we can diff against staging's canonical copies:

```
prism_mcp/utils/chart_functions.py          (staging: ~1,092 KB / 27,460 lines)
prism_mcp/utils/chart_functions_studio.py   (staging:   ~205 KB /  5,320 lines)
chart_context.md                            (staging:    ~69 KB)
chart_context_grids.md                      (staging:   ~5.4 KB)
chart_context_colors.md                     (staging:   ~12.6 KB)
dashboards.md / dashboards_hub.md / dashboards/ spokes  (report what exists)
```

Flag explicitly any file whose size differs by more than ~2% from the
staging figure, and any of the five context .md files that does NOT exist at
the path you report in §5.

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
permission denied), add a brief `## Could not resolve` section at the end
listing what you tried and what blocked it.
