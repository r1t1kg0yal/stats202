---
class: context-extraction
topic: 01 — byte reconciliation of the 35-file contract + commit inventory
expected_reply: ~20 KB
sent: 2026-08-09
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

First of a bite-sized series. Establishes which of the 35 contract files
diverge, what the real directory contents are, and which commits caused the
divergence. Every later prompt in the series keys off this reply.

---

## Paste everything below into PRISM

You are being asked to introspect your own repository and report measurements
verbatim. This is pure code introspection: do not build anything, do not run an
analysis, do not report frictions.

**Reply budget: keep this reply under roughly 30,000 characters.** The prompt is
scoped to fit comfortably. If you find yourself running long, stop at a clean
item boundary, say exactly where you stopped, and name what remains — I will ask
for the rest separately. Never silently truncate mid-item.

Rules: compute every value programmatically rather than from memory; paste exact
paths, counts and hashes; keep my numbering; do not paraphrase or summarize.

**Measurement convention.** Measure file contents with any single trailing
newline stripped. Your copies mostly lack a final newline and mine mostly have
one; stripping first removes that systematic 1-byte offset so we compare real
content. Use exactly this:

```python
import hashlib
def measure(path):
    b = open(path, "rb").read()
    if b.endswith(b"\n"):
        b = b[:-1]
    lines = b.count(b"\n") + 1 if b else 0
    return len(b), lines, hashlib.sha256(b).hexdigest()[:12]
```

### 1. Classify the contract files

These 35 files are developed in a separate staging repo and copied into you
unchanged. Below is my local measurement of each. Report one table, same row
order, with your measured `bytes / lines / sha256[:12]` and a verdict of exactly
`MATCH` or `DIFFERS`. End with a count of each.

Keep the table terse — path, your three values, verdict. No commentary per row.

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

### 2. Directory truth

2.1 List `prism-core/context/modules/static/tools/dashboards/` exhaustively
(filename, bytes, lines). I believe it holds the 10 files named above; I have
been told it holds 11. Name the extra file if there is one.

2.2 List `prism-core/context/modules/static/tools/charts/` exhaustively. Confirm
it holds exactly the 6 I named and nothing else.

2.3 List `prism-core/prism_mcp/chart_render/` and `prism-core/dashboards/`
exhaustively (filename, bytes, lines), excluding `__pycache__`. Call out
anything present that is not in my 35-row table.

### 3. What caused the divergence

3.1 For each path below, list every commit that touched it since `287311b`,
newest first, as `sha date author subject` on one line each. No diffs, no stats —
just the list.

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
         prism-core/dashboards/dashboards_time.py \
         prism-core/dashboards/refresh_runner.py \
         prism-core/dashboards/dashboard_share.py \
         prism-core/dashboards/dashboard_user_input.py \
         jobs/hourly/refresh_dashboards.py ; do
  echo "=== $p"
  git log --format='%h %ad %an  %s' --date=short 287311b..HEAD -- "$p"
done
```

3.2 Same for the whole context tree, one list, no diffs:

```bash
git log --format='%h %ad %an  %s' --date=short 287311b..HEAD \
  --name-only -- prism-core/context/modules/static/tools/
```

3.3 State plainly whether there is any process today by which these files get
edited inside this repo rather than in the staging repo they come from. If so,
name what does it and which paths it touches. I need to know whether to expect
this class of divergence to recur.

### 4. Two small files, verbatim

Paste these two in full — they are tiny and they anchor the whole engine
contract. Give byte count and line count with each.

```
prism-core/prism_mcp/chart_render/__init__.py
prism-core/prism_mcp/utils/chart_functions.py
```

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
