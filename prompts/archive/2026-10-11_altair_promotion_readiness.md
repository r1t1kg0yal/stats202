---
class: context-extraction
topic: altair promotion go/no-go -- where production stands, the old/ copy's identity, core.py and the seven context files against production, imports across the engine boundary, CI with the payload swapped in, how a drop goes live in the sandbox image, OKF reaching chart_agent at runtime, and a gate-by-gate verdict with the drop manifest
expected_reply: ~30-50 KB (state and identity tables, context-file diffs with production-only hunks verbatim, import tables, per-test results, deploy path, verdict table)
created_at: 2026-10-11
sent: 2026-10-12
status: ANSWERED (2026-10-12, folded)
trigger: >
  The last prompt before the canonical altair payload is dropped into PRISM.
  PRISM's old/ comparison (2026-10-11) found production core.py has nothing
  old/core.py lacks, but old/core.py measured 1,720,738 bytes / 40,470 lines
  against the canonical 1,712,462 / 40,467, and the verdict covered core.py
  only. All seven production context files differ from the last promotion,
  including three staging has not edited since. Production renders in the
  prism-sandbox gateway, so a merged drop may not be live until the image is
  rebuilt. The staging harness tests against copies of four PRISM-owned files
  that need re-confirming at the HEAD the drop lands on.
reply_folds_into:
  - projects/altair/altair-payload/chart_context*.md (fold in any production-only content)
  - projects/altair/{prism_mcp,core}/ mirrors and dev/test_chart_exec.py TestOwnership pins (if §0.4 finds a DIFFER)
  - staging/README.md (altair drag-and-drop status), .cursor/rules/viz-platforms.mdc (parity paragraph), projects/altair/README.md
  - prism/subagents.md §2.1 and §7 (OKF and image promotion inside chart_agent, runtime), prism/codebase-tree.md §8 and §12 (install paths, sandbox image)
  - prism/_changelog.md
---

**Staging-side note -- do NOT paste this header into PRISM.**

Before sending:

1. Copy the whole `staging/altair-payload/` folder into the prism-main
   checkout as `old/altair-payload/`. Leave `old/core.py` where it is; §1
   compares the two. `test_prompts/` can come along; it is ignored.
2. Decide whether PRISM's staged deadline change (`core/agent_base.py`,
   `core/chart_agent_tool.py`, its test) is merged first. It is approved to
   merge as staged (2026-10-11). Either order works; §0.3 reports which, and
   §5 runs at whatever HEAD results.

Why this prompt exists.

1. **The file PRISM compared is not byte-identical to ours.** The canonical
   engine (`projects/altair/altair-payload/chart_render/core.py`, identical to
   `staging/altair-payload/`) is 1,712,462 bytes, sha256[:16] `2f55d993cd7636f9`.
   PRISM measured `old/core.py` at 1,720,738 bytes and noted git state `AM`.
   Encoding drift would explain 138 bytes, not 8,276. §1 settles which file it
   was, and §2 re-checks the verdict on the real one if they differ.
2. **The context files are unreviewed.** Production's seven files all differ
   from `dev/_before_p6/` (the last promotion). For annotations (10,944 vs our
   10,955), dual_axis (7,613 vs 7,621) and grids (5,147 vs 5,157) staging has
   not changed a byte since that promotion, so the difference is PRISM's.
   §3 finds every production-only line so it can be folded in before the drop.
3. **A drop has to pass PRISM's tests.** `.gitlab-ci.yml` runs no pytest, so
   nothing catches a break on merge. §4 checks both directions of the import
   boundary and §5 runs the chart and context tests with the payload swapped in,
   in a temporary copy, the way the deadline change was tested.
4. **The harness tested against copies.** `dev/test_chart_exec.py` (203 tests)
   drives the engine through verbatim mirrors of `chart_exec.py`,
   `chart_agent_tool.py`, `artifact_report.py` and `file_types.py`. §0.4
   confirms they are still production's bytes at the HEAD the drop lands on.
5. **Merged is not live.** Production diverts every attributed `render_charts`
   call to the `prism-sandbox` gateway, so the engine users get is the copy in
   the sandbox image. §7 asks what turns a merge into a running engine.
6. **OKF reaching chart_agent is a code-path finding** (2026-10-11 OKF reply
   §4.1, "not confirmed at runtime"). §6 allows one small chart_agent call to
   confirm it and to measure what it costs. It does not gate the drop. If
   confirmed, the follow-up (decided 2026-10-11) is a separate change request:
   keep the OKF block out of sub-agents while keeping `ImagePromotionPlugin`.

§8 is the answer this prompt exists for: a gate-by-gate verdict and the exact
drop manifest. Nothing in the prompt changes the live checkout.

---

## Paste everything below into PRISM

We are about to promote a staging copy of the chart engine into this
repository, and want to be sure it reverts nothing of yours, breaks nothing
that imports it, and goes live the way we expect. This is read-only
introspection plus one test run in a throwaway copy and one `chart_agent` call.
Do not edit, stage or commit any file in the live checkout, and do not perform
the drop. You may run Python in `execute_analysis_script`, create a temporary
copy of the repository for §5, and make exactly one `chart_agent` call for §6.

Answer from live source, not from remembered context or a previous turn's
summary. Give repository-relative paths from the `prism-main` root with
`path:line` citations, and quote code **verbatim in fenced blocks**.

If part of this prompt cannot be answered, add a brief `## Could not resolve`
section at the end listing what you tried and what blocked it.

---

### 0. Where you are

1. The current branch, `git rev-parse HEAD`, and
   `git log -1 --format='%h %ad %an %s' --date=short`.
2. `git status --short` restricted to `old/`, the install paths in §0.6, and
   the five files in §0.4.
3. Is the deadline change (`core/agent_base.py`, `core/chart_agent_tool.py`
   and its test) committed? Give the commit if so; otherwise say whether it is
   still staged in the working tree.
4. Byte count and sha256[:16] of each file below, beside ours, marking each
   MATCH or DIFFER. For a DIFFER, paste the unified diff against `HEAD` (up to
   100 lines) and say what changed.

   | File | Ours | sha256[:16] |
   |---|---:|---|
   | `prism-core/prism_mcp/tools/chart_exec.py` | 42,208 | `db5fc1c20c60ce78` |
   | `core/chart_agent_tool.py` | 13,218 | `dbf587159187fa08` (your staged deadline version; master was `be3d98ef4fcd2deb`) |
   | `prism-core/prism_mcp/tools/artifact_report.py` | 6,693 | `fcdbce1d1c7d3932` |
   | `core/configs/file_types.py` | 1,842 | `794a0aaee0754d4e` |
   | `core/agent_base.py` | 20,439 | `d642a952256ba835` (staged; master was 19,751 B `4c51f0d86e55bf54`) |

5. Every commit since 2026-09-28 that touched an engine install path:
   `git log --since=2026-09-28 --format='%h %ad %an %s' --date=short --
   prism-core/prism_mcp/chart_render/ prism-core/prism_mcp/utils/chart_functions.py
   prism-core/prism_mcp/utils/vega_node_check.py`. For each, the files it touched.
6. Every file, with its byte count, in `prism-core/prism_mcp/chart_render/`,
   in `prism-core/context/modules/static/tools/charts/`, every
   `prism-core/context/modules/static/tools/chart_context*.md`, and every
   `prism-core/prism_mcp/utils/chart_functions*` and `vega_node_check*`.

### 1. Which file you compared

`old/altair-payload/` holds the staging copy we intend to promote. Its files,
with the bytes and sha256[:16] we measure on our side:

| File | Bytes | sha256[:16] |
|---|---:|---|
| `chart_context.md` | 41,878 | `35cfcd6a65a10588` |
| `chart_context_annotations.md` | 10,955 | `691791e3c38c67d6` |
| `chart_context_colors.md` | 10,132 | `2b5e6e240172cc0f` |
| `chart_context_composites.md` | 8,987 | `7abdbb568a2eab99` |
| `chart_context_dual_axis.md` | 7,621 | `efb7394a4b40af14` |
| `chart_context_grids.md` | 5,157 | `a01e1553a562f3d1` |
| `chart_context_tables.md` | 15,270 | `29eb2c14f759a646` |
| `chart_render/__init__.py` | 882 | `a2d6203351e2f500` |
| `chart_render/chart_functions_studio.py` | 505,482 | `5122e0eb5257f113` |
| `chart_render/chart_functions_studio_tables.py` | 243,262 | `29309f77d82d50a2` |
| `chart_render/core.py` | 1,712,462 | `2f55d993cd7636f9` |
| `chart_render/house_style.py` | 25,860 | `7a0f326a32cea63b` |
| `utils/chart_functions.py` | 1,392 | `ca611351d5c03073` |
| `utils/vega_node_check.py` | 3,899 | `1d9a5f18bf60b175` |

1. Read each file's raw bytes and give its byte count and sha256[:16] in a
   table beside ours, marking each row MATCH or DIFFER. A DIFFER here means the
   copy was altered in transit; say so and stop at §1.
2. Give the byte count and sha256[:16] of `old/core.py` (the file your previous
   comparison read), and of its staged blob (`git show :old/core.py`).
3. If `old/core.py` differs from `old/altair-payload/chart_render/core.py`,
   give the unified diff between them (`old/core.py` first), up to 150 lines,
   and say what the extra 8,276 bytes are.

### 2. The core.py verdict, on the right file

Only if §1.3 found a difference: repeat your previous comparison with
`old/altair-payload/chart_render/core.py` against
`prism-core/prism_mcp/chart_render/core.py`. Report the same figures (hunks,
lines only in production, lines only in old/, top-level definitions and
constants on each side only) and state again, for every line only in
production, whether it is a docstring or comment that old/ rewrote or an
earlier, narrower version of code old/ extended. Name any production line that
is neither.

### 3. The seven context files against production

Install paths: `chart_context.md` lives at
`prism-core/context/modules/static/tools/chart_context.md`; the other six at
`prism-core/context/modules/static/tools/charts/<name>.md`.

For each of the seven, diff `old/altair-payload/<name>.md` against the
production file and report:

1. Production's byte count and sha256[:16]; the number of hunks; lines only
   in production; lines only in old/.
2. For **every** line only in production, one of: (a) wording old/ rewrote
   (quote the old/ line that replaces it), or (b) content old/ lacks.
3. Paste **every hunk that contains a (b) line, verbatim**, as unified diff
   with three lines of context. For each, give the commit that introduced the
   production lines (`git log -L <start>,<end>:<path> --format='%h %ad %an %s'
   --date=short`, first entry).
4. List any commit since 2026-09-28 that touched the file
   (`git log --since=2026-09-28 --format='%h %ad %an %s' --date=short -- <path>`).

### 4. Imports across the engine boundary

1. List every module outside `prism-core/prism_mcp/chart_render/` that imports
   from `prism_mcp.chart_render`, `prism_mcp.chart_render.core`,
   `prism_mcp.chart_render.house_style` or `prism_mcp.utils.chart_functions`,
   with `path:line` and the names it imports (including names reached as
   `core.<name>` attributes).
2. For each imported name, say whether
   `old/altair-payload/chart_render/core.py` (or the matching old/ file)
   defines it. Flag any it does not.
3. The other direction. We find the old/ files importing two names from
   modules the payload does not ship:
   `guess_units_from_name` from `prism_mcp.chart_render.units`
   (`chart_render/core.py:98`) and `generate_presigned_download_url` from
   `prism_mcp.utils.download_links` (`utils/chart_functions.py:25`). Quote the
   `def` line of each in production, and list any other import in the old/
   files of a repository module outside the payload that we missed.

### 5. Tests with the payload swapped in

In a **temporary copy** of the repository at your current HEAD (delete it
afterwards; the live checkout must not change):

1. Copy the 14 files from `old/altair-payload/` over their install paths:
   `chart_render/*.py` to `prism-core/prism_mcp/chart_render/`, `utils/*.py`
   to `prism-core/prism_mcp/utils/`, and the context files as in §3.
2. Run, and report pass / fail / error counts per file with the first 30
   lines of each failure:
   - every test file that imports `prism_mcp.chart_render`,
     `prism_mcp.utils.chart_functions` or `prism_mcp.tools.chart_exec`;
   - `tests/context/test_okf_floor.py` and
     `tests/context/test_no_dangling_references.py`;
   - the import-closure test in `test_secure_exec` (cite its line);
   - `tests/test_sandbox_image_layout` and
     `web/test_composer_artifact_authz` if they exist;
   - `prism-core/tests/test_chart_characterization.py` if it exists. The
     engine has changed since the last promotion, so golden differences are
     expected: for each failing case say whether the output differs or the
     render raised, and give the command that regenerates its goldens.
3. Run `python context/build_index.py --check` and report its output.
4. Run the same set once more without the swap, at the same HEAD, so a
   failure that exists on HEAD already is not blamed on the payload.

### 6. OKF and image promotion inside chart_agent, at runtime

Your 2026-10-11 OKF reply (§4.1) found by reading the code that ADK 2.4.0's
`AgentTool` passes the parent's plugins to the sub-agent's Runner
(`include_plugins` defaults to True and `core/agent_base.py:419` does not
turn it off), so `chart_agent` would receive the parent's OKF block at
`contents[0]` and `ImagePromotionPlugin` would promote the `[[image: ...]]`
markers in `render_charts`' diagnostics block.

Make **one** `chart_agent` call: a single line chart from a three-row CSV you
write to the session. Then report:

1. Whether the sub-agent's first model request carried the OKF block at
   `contents[0]`: quote its header line and list the guide frames it holds.
2. The OKF block's size in bytes, beside the size of the sub-agent's system
   instruction.
3. Whether the sub-agent's model call after its `render_charts` call carried
   an image part for the render named in the diagnostics block.
4. How you observed each of these (log, callback, captured request).
5. Paste the line that constructs the tool in `core/ticket_agent_tool.py`
   and in `core/bing_search_agent_tool.py`, with `path:line`. An earlier
   reply said `ticket_agent` is a `FunctionTool` via `subagent_function_tool`
   and `web_search_agent` goes through `subagent_tool`; your OKF reply said
   the reverse.

### 7. How a drop goes live

1. How do the files in `prism-core/prism_mcp/chart_render/` reach the image
   the `prism-sandbox` gateway runs (a `COPY`, a package install, a mount)?
   Cite the build file and lines, and the file that names the image tag
   production uses.
2. Once the 14 files are on master, what has to happen before a diverted
   `render_charts` call runs the new engine: an image rebuild, a tag bump, a
   deploy? Is any of it automatic on merge? Until it happens, does production
   run the new trusted side (`utils/chart_functions.py`, the context files)
   against the old sandbox engine?
3. Quote what `tests/test_sandbox_image_layout.py` asserts about
   `chart_render/` (a file list, an import set, sizes).
4. When does a change to the seven context files reach `chart_agent`: on the
   next invocation, on process restart, or on deploy? Cite the read
   (`_chart_corpus` and its caller) and any cache in front of it.

### 8. Verdict and drop manifest

1. One row per gate, PASS / FAIL / N/A, with the section that shows it:

   | Gate | Passes when |
   |---|---|
   | Identity | §1.1 all MATCH |
   | core.py | no production line is outside the two allowed classes (§1.3 / §2) |
   | Context | no (b) line in §3, or every (b) hunk listed for folding |
   | Imports | every name in §4.2 and §4.3 resolves |
   | Tests | nothing fails with the swap that passes without it (§5), golden regeneration aside |
   | Mirrors | §0.4 all MATCH |
   | Go-live | §7 names the steps that make the drop live |

2. Overall: **GO**, **GO AFTER FOLDS** (name each fold), or **NO-GO** (name
   each blocker).
3. The drop manifest: each of the 14 `old/altair-payload/<file>` beside its
   install path, then every other file that must change in the same commit for
   §5 to pass (regenerated goldens, a pin, the OKF index), or "none".
4. Confirm the drop overwrites no file the payload does not own
   (`chart_render/units.py`, `tools/chart_exec.py`, `core/chart_agent_tool.py`,
   `tools/artifact_report.py`, `core/configs/file_types.py`), and name any file
   in the §0.6 listing that would be left behind with nothing importing it.

---

## Reply structure

One `##` heading per section above, numbered the same, §8 last. Put §0.4 and
§1 in one table each. Put §3's hunks under
`## Appendix: production-only context hunks`, one fenced `diff` block per hunk
headed by `path :: hunk N`.
