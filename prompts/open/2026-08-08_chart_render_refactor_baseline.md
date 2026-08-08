# Context-extraction prompt — chart_render refactor: baseline reconciliation + characterization harness

**Why this exists (staging-side note, do NOT paste this header into PRISM):**
A PRISM-side branch (`macdist-refactor-chartRender`, 3 commits off merge-base
`4ff783f`) extracted an import-closed render core: `prism_mcp/utils/chart_functions.py`
became `prism_mcp/chart_render/core.py`, `chart_house_style.py` became
`chart_render/house_style.py`, `unit_helper_functions.py` became
`chart_render/units.py`, and `utils/chart_functions.py` was rewritten as a 42-line
trusted-side wrapper that calls `core.register_trusted_extensions(...)`. We are
absorbing that refactor into staging (new tree at `projects/altair2/`), which is
the inverted direction from the usual staging→PRISM flow, so per the housekeeping
rule in `.cursor/rules/viz-platforms.mdc` byte-parity with prod is the goal.

We only have low-resolution screenshots of the port document, so two things are
unresolved. First, local hashing proves `staging/altair-payload-aug2/` is the
merge-base for `chart_house_style.py` and `chart_functions_studio_tables.py`
(exact byte match once the trailing newline is stripped) but NOT for
`chart_functions.py`, which is off by ~5,734 bytes. Second, the port document
explicitly excluded commit `19e8cee`'s characterization harness + 22 goldens,
which is the strongest available gate for proving the port is behaviour-preserving.

Also newly discovered and worth folding in wherever parity is discussed: every
staging payload file carries a trailing newline that the corresponding PRISM blob
does not. That is a systematic 1-byte drift on every file in the contract.

Reply lands back here; fold-in updates: `projects/altair2/` scaffold (P1),
`projects/altair2/dev/` gate (P3), `.cursor/rules/viz-platforms.mdc` parity
language, `projects/altair/README.md`. Move this file to
`staging/prompts/archive/` once folded.

---

## Paste the following into PRISM

You are being asked to introspect your own repository's git history and source
files and report the results verbatim. Use `execute_analysis_script` (shelling
out to `git` is fine) and direct source reads. Do not paraphrase and do not
summarize: paste exact SHAs, exact byte counts, exact source lines in fenced
code blocks, and name the file path you read each answer from. Where a question
asks for a computed value, compute it programmatically rather than from memory.

### 1. Branch state

1.1 State whether the branch `macdist-refactor-chartRender` has been merged, and
if so into which branch and at what commit. Print the output of:

```bash
git log --oneline -5 macdist-refactor-chartRender
git branch --contains macdist-refactor-chartRender
git log --oneline -3 HEAD
git rev-parse HEAD
```

1.2 State which commit is currently checked out and running as live PRISM, and
whether `prism-core` is a plain subdirectory of `prism-main` or a submodule at
this point in history. (Our notes disagree across dates; the port document says
plain subdirectory.)

1.3 Confirm the three commits on the branch are `9c7a880`, `2827cb9`, `19e8cee`
in that order, and print their full SHAs and one-line subjects.

### 2. Blob inventory — confirm or correct

For each path/ref pair below, print the git blob SHA, byte count, and line count.
Use `git rev-parse <ref>:<path>` and `git cat-file -s <ref>:<path>`.

At merge-base `4ff783f`:
```
prism-core/prism_mcp/utils/chart_functions.py
prism-core/prism_mcp/utils/chart_house_style.py
prism-core/prism_mcp/utils/unit_helper_functions.py
prism-core/prism_mcp/utils/chart_functions_studio.py
prism-core/prism_mcp/utils/chart_functions_studio_tables.py
```

At `macdist-refactor-chartRender` (and, if it differs, at current HEAD):
```
prism-core/prism_mcp/chart_render/__init__.py
prism-core/prism_mcp/chart_render/core.py
prism-core/prism_mcp/chart_render/house_style.py
prism-core/prism_mcp/chart_render/units.py
prism-core/prism_mcp/utils/chart_functions.py
prism-core/prism_mcp/utils/chart_functions_studio.py
prism-core/prism_mcp/utils/chart_functions_studio_tables.py
```

We have already computed these locally from our snapshot, each with its trailing
newline stripped. Confirm each MATCH or MISMATCH explicitly:

| our file (trailing newline stripped)  | our blob SHA | our bytes | our lines |
|---|---|---|---|
| chart_functions.py                    | `e477346a…`  | 1,184,571 | 28,802 |
| chart_house_style.py                  | `43b4620b…`  |    24,354 |    643 |
| chart_functions_studio.py             | `b5a8cccb…`  |   493,230 | 12,367 |
| chart_functions_studio_tables.py      | `a3a9eebd…`  |   232,444 |  5,657 |

### 3. Localize the `chart_functions.py` delta

Our copy is 28,802 lines / 1,184,571 bytes; the port document reports the
merge-base blob at 28,797 lines / 1,190,305 bytes. Five fewer lines but ~5.7 KB
more content means a real edit, not drift at the file edges. Localize it.

Run this against the merge-base blob and paste the full output:

```python
import hashlib, subprocess
blob = subprocess.check_output(
    ["git", "show", "4ff783f:prism-core/prism_mcp/utils/chart_functions.py"])
lines = blob.split(b"\n")
if lines and lines[-1] == b"":
    lines = lines[:-1]
print("total lines:", len(lines), "total bytes:", len(b"\n".join(lines)))
for i in range(0, len(lines), 1000):
    chunk = b"\n".join(lines[i:i+1000])
    print(f"{i+1:>6}-{min(i+1000,len(lines)):<6} "
          f"{hashlib.md5(chunk).hexdigest()[:12]}  {len(chunk):>7}")
```

Then, for whichever chunk indices we flag back to you as mismatching, paste that
1,000-line window verbatim in a fenced block. (We will compare your ladder
against ours and come back with the specific windows; you do not need to guess
which ones they are on this pass.)

### 4. The characterization harness (commit 19e8cee)

4.1 Paste `prism-core/tests/test_chart_characterization.py` verbatim, with its
absolute path and line count.

4.2 List every file under `prism-core/tests/golden/chart_specs/` with filename
and byte size. State the total count.

4.3 State how the goldens are generated: is there a regeneration command, an
environment variable, or a `--update-golden` style flag? Paste the code path
that writes them. **This is the key question** — if the goldens are regenerable
from source we do not need you to paste 22 JSON files, we can regenerate them
locally against our own copy.

4.4 State exactly what the harness asserts: Vega-Lite spec equality, PNG bytes,
image hashes, or something else. Paste the assertion body.

4.5 State whether the harness passes on the branch tip, and paste the run output
if you can execute it.

### 5. Trailing newline

5.1 Confirm: does `prism-core/prism_mcp/utils/chart_functions.py` (at any ref)
end with a newline character? Print `git show <ref>:<path> | tail -c 1 | xxd`
for the merge-base and for current HEAD.

5.2 Same for `chart_house_style.py`, `chart_functions_studio.py`, and
`chart_functions_studio_tables.py` at merge-base.

5.3 If these files consistently lack a final newline while the rest of the
repository has one, say whether that is deliberate (an editor/lint convention,
a `.gitattributes` rule) or incidental. Paste any relevant `.gitattributes`,
`.editorconfig`, or pre-commit configuration.

### 6. Post-refactor import surface

6.1 Re-confirm the sole-consumer property after the refactor: is
`prism-core/prism_mcp/tools/script_exec_tools.py` still the only Python importer
of `chart_functions` symbols? Show the search you ran across the whole repo
(both `prism-main` and `prism-core`) and its raw output.

6.2 Paste verbatim every `from prism_mcp.utils.chart_functions import (...)` and
`from prism_mcp.chart_render...` line currently in the repo, with file path and
line number.

6.3 State whether anything imports `prism_mcp.chart_render` directly today, or
whether the wrapper is still the only entry point. If the minimal sandbox image
exists, name the module list it ships.

6.4 Paste the current `__all__` of `prism_mcp/chart_render/core.py` and of
`prism_mcp/utils/chart_functions.py`, and confirm they are identical 44-entry
lists.

### 7. Optional — verbatim source for the three new blocks

Only if cheap; we can reconstruct these functionally from the port document, but
having them verbatim is the difference between claiming byte-parity and not.

7.1 Paste `prism-core/prism_mcp/chart_render/__init__.py` in full (17 lines).

7.2 Paste `prism-core/prism_mcp/utils/chart_functions.py` in full (42 lines).

7.3 Paste the dependency-injection seam from `chart_render/core.py` — the ~79
lines inserted immediately after the module logger block, from the
`_NullDownload` class through the end of `register_trusted_extensions`.

---

If part of this prompt cannot be answered (file missing, symbol ambiguous,
permission denied), add a brief `## Could not resolve` section at the end
listing what you tried and what blocked it.
