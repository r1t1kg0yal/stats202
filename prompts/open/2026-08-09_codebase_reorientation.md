---
class: context-extraction
topic: full codebase re-orientation (turn 1 of N) — re-anchor all staging documentation
sent: 2026-08-09
status: OPEN
reply_pointer:
fold_into:
  - staging/README.md (roster: altair + echarts rows, PRISM destination cells)
  - .cursor/rules/viz-platforms.mdc (PRISM runtime layout, drag-and-drop table, import contracts, drag-and-drop status)
  - .cursor/rules/prism.mdc (Repo-to-PRISM Mapping table)
  - projects/altair/README.md, projects/echarts/README.md
  - projects/altair/altair-payload/{chart_render,utils}/*.py module docstrings + header comments
  - projects/echarts/echarts-payload/*.py module docstrings + header comments
  - projects/altair/altair-payload/chart_context*.md, projects/echarts/echarts-payload/dashboards*.md (namespace/path claims only)
---

**Staging-side note — do NOT paste this header into PRISM.**

This is the kick-off turn of a multi-turn re-orientation. Our local picture of
PRISM's codebase organization is anchored to the 2026-07-07 `prism-main` split
scan plus the 2026-07-21 Composer extraction and the 2026-08-08 `chart_render`
refactor prompt. The user reports the organization has since changed
substantially. Goal: rebuild the map from first principles, then freshen every
staging doc, README, rule, module docstring, and header comment in
`projects/altair/` and `projects/echarts/`.

Turn 1 asks for breadth (topology, tree, destination confirmation, import
surface, registry, conventions) plus an explicit delta report against 20 named
beliefs. Turns 2+ drill into whatever section 8 flags as `DIFFERS` or `GONE`.

---

## Paste everything below into PRISM

You are being asked to introspect your own repository and report the results
verbatim. This is pure code introspection — do not build anything, do not run an
analysis, do not report frictions.

Rules for this reply:

- Compute every value programmatically (`execute_analysis_script`, shelling out
  to `git` / `os.walk` / `hashlib` is fine). Do not answer from memory.
- Paste exact paths, exact SHAs, exact byte counts, exact line counts, exact
  signatures, exact docstrings. Do not paraphrase, do not summarize, do not
  round numbers.
- Name the absolute path you read each answer from.
- Keep my section numbering (1.1, 1.2, …) so I can diff your reply against my
  questions mechanically.
- Where I state a belief and ask you to classify it, use exactly one of
  `MATCHES` / `DIFFERS` / `GONE`, then give the correction.
- Long output is fine and expected. Prefer completeness over brevity.

---

### 1. Checkout topology and git state

1.1 Print the output of, from the repository root:

```bash
pwd
git rev-parse --show-toplevel
git remote -v
git branch -a --sort=-committerdate | head -40
git log --oneline -10 HEAD
git rev-parse HEAD
git status --porcelain=v1 | head -60
git submodule status
```

1.2 State whether `prism-core` is today a git submodule, a plain subdirectory, a
separate clone, or something else. If it is a submodule, print the gitlink SHA
recorded by the parent (`git ls-tree HEAD prism-core`) alongside the actual
checked-out SHA (`git -C prism-core rev-parse HEAD`) and say explicitly whether
they agree.

1.3 If `prism-core` is its own repo, run 1.1's git block inside it too.

1.4 Name every directory that is on `sys.path` at runtime for each of these
execution contexts, and paste the code that puts it there (file path + line
numbers):

  a. the MCP server process
  b. the `execute_analysis_script` code sandbox
  c. the dashboard refresh subprocess
  d. the hourly cron job
  e. the Django web process

1.5 State the Python version each of those contexts runs, and whether the
sandbox runs in a separate image / container / venv from the MCP server. If
there is a secure-execution sandbox image, name it and list the Python modules
it ships.

1.6 List the branches that have touched `prism_mcp/chart_render/`,
`prism_mcp/utils/chart_functions*.py`, or `dashboards/` in the last 60 days,
with their last-commit date, and say which of them are merged into the branch
that is live in production.

### 2. Annotated tree

2.1 Run this and paste the complete output (adjust `ROOTS` if my assumed roots
are wrong — say so if you do):

```python
import os, hashlib

ROOTS = ["."]                      # repo root; add prism-core explicitly if separate
SKIP  = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache",
         ".pytest_cache", ".ruff_cache", "site-packages", ".idea", ".vscode"}
COUNT_LINES = {".py", ".md", ".json", ".html", ".css", ".txt", ".cfg", ".toml", ".yaml", ".yml"}

for root in ROOTS:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP and not d.startswith("."))
        rel = os.path.relpath(dirpath, root)
        depth = 0 if rel == "." else rel.count(os.sep) + 1
        if depth > 4:
            dirnames[:] = []
            continue
        print(f"\n{dirpath}/")
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            ext = os.path.splitext(fn)[1].lower()
            lines = ""
            if ext in COUNT_LINES and size < 8_000_000:
                try:
                    with open(p, "rb") as fh:
                        lines = f"{fh.read().count(bytes([10])) + 1:>7} lines"
                except OSError:
                    lines = ""
            print(f"    {fn:<52} {size:>10,} B  {lines}")
```

2.2 If that walk truncates or the output is too large to return in one message,
say so and instead paste: (a) the full walk restricted to `prism_mcp/`,
`dashboards/`, `context/`, `jobs/`, `core/`, and `prism_meta/`, and (b) a
depth-2-only listing of everything else. Tell me which mode you used.

2.3 Paste the repo-root listing of top-level directories with a one-line
description of what each contains, sourced from a README or the code itself
(not from memory). Flag any top-level directory that did not exist 60 days ago
(`git log --diff-filter=A --format=%ad -1 -- <dir>`).

### 3. Destination confirmation for the 25 files I ship you

These are the exact files I develop in staging and drop into you. For each, my
believed destination path is given. Report, in one table:

`believed path` | `EXISTS` / `MOVED` / `ABSENT` | `actual path today` | `sha256`
(first 12) | `bytes` | `lines` | `last commit SHA + date touching it`

Compute `sha256` on the raw bytes on disk. If `MOVED`, give the new path and the
commit that moved it.

Altair — believed destinations:

```
prism-core/prism_mcp/chart_render/__init__.py
prism-core/prism_mcp/chart_render/core.py
prism-core/prism_mcp/chart_render/house_style.py
prism-core/prism_mcp/chart_render/units.py                (PRISM-owned; I do not ship this)
prism-core/prism_mcp/utils/chart_functions.py
prism-core/prism_mcp/utils/chart_functions_studio.py
prism-core/prism_mcp/utils/chart_functions_studio_tables.py
prism-core/context/modules/static/tools/chart_context.md
prism-core/context/modules/static/tools/charts/chart_context_annotations.md
prism-core/context/modules/static/tools/charts/chart_context_dual_axis.md
prism-core/context/modules/static/tools/charts/chart_context_composites.md
prism-core/context/modules/static/tools/charts/chart_context_tables.md
prism-core/context/modules/static/tools/charts/chart_context_grids.md
prism-core/context/modules/static/tools/charts/chart_context_colors.md
```

Echarts — believed destinations:

```
prism-core/dashboards/__init__.py
prism-core/dashboards/config.py
prism-core/dashboards/dashboards_time.py
prism-core/dashboards/echart_dashboard.py
prism-core/dashboards/echart_studio.py
prism-core/dashboards/rendering.py
prism-core/dashboards/refresh_runner.py
prism-core/dashboards/dashboard_share.py
prism-core/dashboards/dashboard_user_input.py
jobs/hourly/refresh_dashboards.py                          (parent tree, not prism-core)
prism-core/context/modules/static/tools/dashboards.md
prism-core/context/modules/static/tools/dashboards_hub.md
prism-core/context/modules/static/tools/dashboards/build.md
prism-core/context/modules/static/tools/dashboards/charts.md
prism-core/context/modules/static/tools/dashboards/diagnose.md
prism-core/context/modules/static/tools/dashboards/filters.md
prism-core/context/modules/static/tools/dashboards/pipelines.md
prism-core/context/modules/static/tools/dashboards/productivity.md
prism-core/context/modules/static/tools/dashboards/recipes.md
prism-core/context/modules/static/tools/dashboards/template_crud.md
prism-core/context/modules/static/tools/dashboards/widget_tool.md
prism-core/context/modules/static/tools/dashboards/widgets.md
```

3.2 Separately, list EVERY file in `prism-core/dashboards/` and in
`prism-core/prism_mcp/chart_render/` — including any file I did not name above.
Anything present there that is not in my list is either something I don't know
about or something I need to start owning; call each one out explicitly.

3.3 Same for `prism-core/prism_mcp/utils/`: full file listing with sizes, so I
can see the whole helper surface `chart_functions.py` sits inside.

### 4. Altair: consumer and injection surface

4.1 Run a repo-wide search (both parent and `prism-core`) for importers and
paste the raw output plus the exact command:

```bash
grep -rn "chart_render" --include=*.py .
grep -rn "chart_functions" --include=*.py .
grep -rn "from prism_mcp" --include=*.py . | grep -i chart
```

4.2 Is `prism-core/prism_mcp/tools/script_exec_tools.py` still the only Python
importer of chart symbols? If not, name every other importer.

4.3 Paste verbatim the block in `script_exec_tools.py` that imports chart
symbols and the block that injects them into the sandbox namespace, with file
path and line numbers. Include any wrapping (`_wrap_chart_func`, validation
decorators, partials) applied on the way in.

4.4 Print the exact list of chart-related names visible inside the
`execute_analysis_script` namespace, and for each say whether it is the raw
function or a wrapped one.

4.5 Paste `prism_mcp/chart_render/__init__.py` and
`prism_mcp/utils/chart_functions.py` in full.

4.6 Paste the `register_trusted_extensions` definition from
`chart_render/core.py` verbatim, plus every call site of it in the repo.

4.7 State what happens today when `chart_render` is imported WITHOUT
`register_trusted_extensions` having been called — specifically what a chart
render returns (presigned URL? bare S3 key? interactive studio companion? error
mail?). Cite the code path.

4.8 Print `prism_mcp/chart_render/core.py`'s `__all__` and
`prism_mcp/utils/chart_functions.py`'s `__all__`, and say whether they are
identical and how many entries each has.

4.9 State whether `check_charts_quality` still exists anywhere in the repo,
where it is defined, and where it is imported.

4.10 Paste the complete top-of-file import block of `chart_render/core.py` and
of `chart_render/house_style.py`, so I can verify the import-closure claim
(stdlib + altair / numpy / pandas / PIL / vl_convert only).

4.11 Where does the font directory resolve to today, and paste the code that
resolves it. List the font files actually present.

### 5. Echarts: consumer and runtime surface

5.1 Paste the `sys.path` manipulation block(s) inside `dashboards/*.py`
verbatim, with file paths and line numbers, and explain which execution contexts
depend on them.

5.2 Run and paste raw output:

```bash
grep -rn "from dashboards" --include=*.py .
grep -rn "import dashboards" --include=*.py .
grep -rn "compile_dashboard\|refresh_runner\|refresh_dashboards" --include=*.py .
```

5.3 List every entry point that invokes the dashboard system: MCP tool, Django
view / URL route, cron job, management command, background worker. For each give
file path, function name, and one sentence on when it fires.

5.4 Paste `jobs/hourly/refresh_dashboards.py`'s module docstring and `main()`
signature, and state how it is scheduled (crontab line, systemd timer,
scheduler config) with the config file path.

5.5 Paste `_get_echarts_js()` verbatim and state which asset path actually
resolves on disk today, with the file's byte size.

5.6 List every Django route under the dashboards / composer / user-input
surface with its URL pattern, view function, and file path. Note which are
`@csrf_exempt`.

5.7 State the current status of the Composer integration: is
`getWidgetSnapshot()` called from anywhere yet, does `composer.js` carry
snapshot transport, and does `composer_dashboard_snapshot.py` exist? Cite paths.

5.8 State whether the persisted user-input routes still use a raw-boto3
conditional-write bypass, and paste that code path.

### 6. Context module system

6.1 Paste the context registry verbatim — the full `MODULE_REGISTRY` (or
whatever it is called today), with its file path. If it is large, paste it in
full anyway; I need every entry, not just the chart / dashboard ones.

6.2 Paste the loader that resolves a registry entry to a file on disk, and state
the base directory it resolves relative to.

6.3 Recursively list `context/modules/` with file sizes, so I can see the whole
L2 surface and where my files sit inside it.

6.4 State which of my 14 context markdown files are in the registry and which
are fetched on demand. For the on-demand ones, paste the exact
`list_ai_repo(...)` call shape that successfully fetches them today, including
whether short paths (`charts/chart_context_tables.md`) still resolve or whether
full paths are now required.

6.5 State whether `get_context()` is still one-shot per user message, and
whether `include_modules=[...]` can be used mid-session. Paste the enforcement
code path.

6.6 Paste the current bundle definitions (end_user / developer / report_worker /
orchestrator or whatever exists today) and say which bundle loads
`chart_context` and which loads `dashboards`.

### 7. Tool layer signatures I write skill files against

For each of `list_ai_repo`, `get_context`, and `execute_analysis_script`, paste:
the file path, the full function signature, and the complete docstring verbatim
in a fenced block. If the tool schema exposed to the model differs from the
Python signature, paste the schema too.

7.2 List every other MCP tool currently registered, with its one-line
description, so I know the full L1 surface my skill files are competing with for
attention.

### 8. Delta report against my 20 current beliefs

Classify each as `MATCHES` / `DIFFERS` / `GONE` and correct it. One line of
correction each is enough unless the delta is structural, in which case give me
the full picture.

| # | Belief I currently hold |
|---|---|
| 1 | `prism-main` is the repo root and is on `sys.path`; `prism-core` is a git submodule that is ALSO on `sys.path`, so `prism_mcp` / `context` / `dashboards` import as bare packages |
| 2 | There is no `ai_development/` tree anywhere any more |
| 3 | `prism_meta/__init__.py` defines `REPO_ROOT` as a `__file__`-based anchor and is the SSOT for repo-relative paths |
| 4 | `prism-core/dashboards/` — the directory itself — is on `sys.path`, which is what makes bare `from rendering import ...` resolve inside the package |
| 5 | `prism-core/prism_mcp/tools/script_exec_tools.py` is the ONLY Python importer of `chart_functions` symbols |
| 6 | `prism_mcp/chart_render/` is import-closed: stdlib plus altair / numpy / pandas / PIL / vl_convert only, so it can ship inside the secure-execution sandbox image |
| 7 | `prism_mcp/utils/chart_functions.py` is now a ~42-46 line trusted-side wrapper whose whole job is calling `register_trusted_extensions(...)` |
| 8 | `chart_render/units.py` is PRISM-owned (a `git mv` of `unit_helper_functions.py`) and is NOT shipped from staging |
| 9 | `chart_render/core.py` and `utils/chart_functions.py` export an identical 44-entry `__all__` |
| 10 | `script_exec_tools.py` still imports `check_charts_quality`, but the staging payload no longer defines it, so installing the payload without changing `script_exec_tools.py` would break the import |
| 11 | Only `chart_context.md` and `dashboards.md` are in the context registry; `dashboards_hub.md` and all spokes are fetched by `list_ai_repo`, never by `get_context(include_modules=[...])` |
| 12 | Altair spokes live at `context/modules/static/tools/charts/` and echarts spokes at `context/modules/static/tools/dashboards/` |
| 13 | `refresh_dashboards.py` lives in the PARENT tree at `jobs/hourly/`, not inside `prism-core` |
| 14 | `rendering._get_echarts_js()` anchors to `prism_meta.REPO_ROOT` and reads `web/backend_django/news/static/js/echarts.js`; the legacy `mysite/news/static/js/echarts.js` candidate does not exist on disk |
| 15 | `dashboard_share.py` and `dashboard_user_input.py` both exist under `prism-core/dashboards/` |
| 16 | As of 2026-07-21 the parent-recorded gitlink (`1e6d3955…`) was BEHIND the checked-out `prism-core` (`bf4bcd12…`) |
| 17 | `get_context()` is one-shot per user message and `include_modules=[...]` is not a mid-session fetch primitive |
| 18 | 20 GS Sans TTFs live at `web/backend_django/fonts/` and that is what the chart engine's font-root resolves to |
| 19 | Payload source files in your repo do NOT end with a trailing newline, while my staging copies do — a systematic 1-byte drift on every file in the contract |
| 20 | The branch `macdist-refactor-chartRender` carried the `chart_render` split (commits `9c7a880`, `2827cb9`, `19e8cee`) and its characterization harness lives at `prism-core/tests/test_chart_characterization.py` with goldens under `prism-core/tests/golden/chart_specs/` |

### 9. Code conventions I should match in the files I ship you

9.1 Do the files I own carry a house convention for module docstrings, header
comment banners, section dividers, or `Args:` / `Returns:` docstring style?
Paste two representative examples from files I do NOT own (so I can see the
convention independent of my own drift) — one from `prism_mcp/utils/` and one
from outside it.

9.2 Paste any lint / format config that applies to my files: `pyproject.toml`,
`setup.cfg`, `.flake8`, `ruff.toml`, `.pre-commit-config.yaml`,
`.editorconfig`, `.gitattributes`. State the enforced max line length and
whether anything runs in CI.

9.3 State the repo's actual convention on trailing newlines and on
`from __future__ import annotations`, measured across the repo rather than
asserted.

9.4 State whether type hints are expected on public functions in the modules
neighbouring mine, with a measured percentage rather than an impression.

### 10. What I did not know to ask

10.1 Name the structural changes to the codebase in the last 60 days that a
downstream maintainer of the chart engine and the dashboard compiler would most
need to know about, and that my nine sections above did not cover. Cite the
commits.

10.2 Name anything currently in flight — a branch, a partial migration, a
deprecation, a rename — that will invalidate the picture I just built, and give
me the expected shape after it lands.

10.3 Name any place where the chart engine or the dashboard compiler is now
coupled to a subsystem it was not coupled to before (new import, new shared
helper, new asset, new database or S3 dependency).

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
permission denied, output too large), add a brief `## Could not resolve` section
at the end listing what you tried and what blocked it. Do not silently drop a
numbered item.
