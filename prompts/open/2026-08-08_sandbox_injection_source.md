# Context-extraction prompt — chart_render: which module does the sandbox inject from?

**Why this exists (staging-side note, do NOT paste this header into PRISM):**

On 2026-08-08 we consolidated the `macdist-refactor-chartRender` split into
`projects/altair/`. The engine now lives in an import-closed
`prism_mcp/chart_render/` package and the old `prism_mcp/utils/chart_functions.py`
path is a 46-line trusted-side wrapper that calls
`core.register_trusted_extensions(...)` to inject presign, chart studio, table
studio, vision QC, error mail, dimension presets, chart-id, and font root.
Unregistered, every one of those degrades to a no-op.

That creates a behavioural fork we cannot resolve from staging, because it
depends on which module `script_exec_tools.py` imports when it builds the
sandbox namespace:

```
                    ┌─────────────────────────────────────────┐
                    │  script_exec_tools.py builds namespace   │
                    └────────────────┬────────────────────────┘
                                     │
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
   from prism_mcp.utils.chart_functions          from prism_mcp.chart_render
   ────────────────────────────────────          ──────────────────────────
   extensions REGISTERED                          extensions UNREGISTERED
   • result.download_url  → presigned URL         • result.download_url  → None
   • interactive editor   → companion written     • interactive editor   → absent
   • check_charts_quality → available             • check_charts_quality → no-op
   • font root            → GS Sans TTFs          • font root            → fallback
```

`chart_context.md` and its spokes currently promise the left-hand column
unconditionally. If the answer is the right-hand column, the registered router
is making a promise the runtime does not keep, and the context needs a caveat.
We have deliberately left the context unchanged pending this reply rather than
guess.

Reply lands back here; fold-in targets: `projects/altair/altair-payload/chart_context.md`
(download/editor language), `projects/altair/README.md` (drag-and-drop status),
`staging/README.md` altair row, `.cursor/rules/viz-platforms.mdc` destination
table. Move this file to `staging/prompts/archive/` once folded.

---

## Paste the following into PRISM

You are being asked to introspect your own repository's source files and report
the results verbatim. Use `execute_analysis_script` (shelling out to `git` is
fine) and direct source reads. Do not paraphrase and do not summarize: paste
exact source lines in fenced code blocks, and name the file path and line
numbers you read each answer from. Where a question asks for a computed value,
compute it programmatically rather than answering from memory. If something
does not exist, say "does not exist" explicitly rather than skipping the item.

### 1. What is currently installed

1.1 State whether branch `macdist-refactor-chartRender` has been merged into
the default branch. Print the output of:

```
git log --oneline -5
git branch -a --contains $(git rev-parse macdist-refactor-chartRender 2>/dev/null) 2>&1 | head
```

1.2 List the contents of `prism-core/prism_mcp/chart_render/` and
`prism-core/prism_mcp/utils/`, restricted to chart-related files. For each,
print filename, line count, byte count, and `git hash-object` blob SHA:

```
for f in prism-core/prism_mcp/chart_render/*.py \
         prism-core/prism_mcp/utils/chart_functions*.py; do
  printf '%-70s %10s %8s %s\n' "$f" "$(git hash-object "$f")" \
    "$(wc -l < "$f")" "$(wc -c < "$f")"
done
```

1.3 Does `prism-core/prism_mcp/utils/chart_house_style.py` still exist? Does
`prism-core/prism_mcp/utils/unit_helper_functions.py` still exist? If either
exists, print its first 15 lines — we need to know whether it is a real module
or a back-compat shim forwarding to `chart_render`.

### 2. The injection source (the load-bearing question)

2.1 Print **every** line in `prism-core/prism_mcp/tools/script_exec_tools.py`
that imports from `chart_functions`, `chart_render`, `house_style`, or
`chart_functions_studio`, with line numbers and 3 lines of surrounding context:

```
grep -n -C3 -E "chart_functions|chart_render|house_style" \
  prism-core/prism_mcp/tools/script_exec_tools.py
```

2.2 Do the same for `prism-core/prism_mcp/utils/background_execution.py`.

2.3 In one sentence: when a user's script in the code sandbox calls
`make_chart(...)`, is the function object it reaches the one produced with
trusted extensions registered, or without? Name the module the namespace entry
was sourced from.

2.4 Print the full body of `register_trusted_extensions` from
`prism-core/prism_mcp/chart_render/core.py`, and print every call site of it
across the repo:

```
grep -rn "register_trusted_extensions" prism-core/ core/ jobs/ web/
```

2.5 Is `register_trusted_extensions` invoked at import time of
`prism_mcp/utils/chart_functions.py` (module level), or lazily inside a
function? Paste the surrounding lines.

### 3. What the sandbox actually produces

3.1 Is `prism_mcp/utils/chart_functions.py` present inside the secure-execution
sandbox image, or does the image ship only `prism_mcp/chart_render/`? If there
is a manifest, requirements file, Dockerfile, or copy list that decides this,
name the file path and paste the relevant lines.

3.2 For a chart rendered by a user script in the sandbox, is
`result.download_url` populated with a presigned URL, or is it `None` / absent?
Answer from the code path, and name the file and line where the value is set.

3.3 Is the interactive chart-studio companion HTML written for sandbox-rendered
charts? Same question for the table studio. Name the guard that decides it.

3.4 Does `check_charts_quality` remain available in the foreground sandbox
namespace after the refactor? Our prior introspection (2026-07-07) found it
foreground-only, with the background preamble omitting it — state whether that
is still true.

### 4. Ownership of `chart_render/units.py`

4.1 Print the first 25 lines of `prism-core/prism_mcp/chart_render/units.py`
and the output of `git log --oneline --follow -- prism-core/prism_mcp/chart_render/units.py`.

4.2 We treat this file as PRISM-owned — a pure `git mv` of
`unit_helper_functions.py` that staging only stubs, and therefore never ships
from staging. Confirm or correct that. If staging should own it, say so
explicitly.

4.3 Print `prism-core/prism_mcp/chart_render/__init__.py` in full. We need to
confirm the exact export mechanism (star-export from `core` versus named
re-exports) and the exact `__all__` construction.

### 5. Parity mechanics

5.1 Confirm whether the `.py` files under `prism-core/prism_mcp/chart_render/`
and `prism-core/prism_mcp/utils/` end with a trailing newline:

```
for f in prism-core/prism_mcp/chart_render/*.py \
         prism-core/prism_mcp/utils/chart_functions*.py; do
  printf '%-70s %s\n' "$f" \
    "$(tail -c1 "$f" | od -c | head -1 | grep -q '\\n' && echo HAS_TRAILING_NL || echo NO_TRAILING_NL)"
done
```

5.2 Print the length of `chart_render.core.__all__` and the list itself, sorted.
We compute 44 entries locally and want to diff against yours.

5.3 Are there any files under `prism-core/prism_mcp/chart_render/` or the three
`utils/chart_functions*.py` files that are NOT in our drag-and-drop contract —
that is, anything PRISM-side we would silently clobber on the next promotion?
List them.

### 6. Anything we did not ask

6.1 Name anything about the `chart_render` split that a staging repo owning
`core.py`, `house_style.py`, and the three `utils/chart_functions*.py` files
would get wrong if it only knew what is above. Be specific about import-order
constraints, module-level side effects, or anything that must not move across
the closure boundary.
