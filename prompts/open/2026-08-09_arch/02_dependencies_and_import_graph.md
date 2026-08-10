---
class: context-extraction
topic: 02 — dependency stack, import graph, and layering rules
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

The chart engine's import closure and the dashboard compiler's bare sibling
imports are both dependency-graph facts, so this needs to be right before either
subsystem prompt lands. Also the input for keeping the staging stub mirror
honest.

---

## Paste everything below into PRISM

You are being asked to describe your own repository's dependency structure. This
is introspection for documentation purposes: do not build anything, do not
report frictions.

**I want the graph and the rules that shape it**, with `path:line` citations and
short excerpts as evidence. Do not paste whole files. Where a rule is enforced by
convention rather than by code, say which.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a section boundary and name what remains.

### 1. The runtime environment

1.1 Python version, interpreter path, and virtualenv location for each execution
context (server, sandbox, scheduled jobs, web). Note where they differ.

1.2 Where are third-party dependencies declared — `requirements.txt`,
`pyproject.toml`, `setup.py`, a lockfile, an internal package index? Paste the
dependency list itself if it is under about 100 lines; otherwise summarise it by
category and paste the section that matters for charts and dashboards.

1.3 List the third-party packages actually imported anywhere in the repo, ranked
by how many modules import each. Truncate at the top 40.

1.4 Are there packages that are installed and available but deliberately not
used, or that are blocked at some layer? Name them and the reason.

### 2. The internal import graph

2.1 Produce a directed dependency graph between the top-level Python packages.
For each edge give the number of distinct importing modules. Compute it by
walking imports rather than describing it from memory.

2.2 Draw the layering that graph implies: which packages are foundational,
which are mid-tier, which are top-level. Note any cycles and say whether each is
deliberate.

2.3 State the layering *rules* — what is a module in each package allowed to
import, and what is it forbidden from importing? Distinguish rules enforced by a
test or lint from rules that are conventions in a docstring or a reviewer's head.

### 3. Import closure as a design constraint

One package in this repo is deliberately import-closed so it can run in a
restricted environment, importing only the standard library and the data-science
stack.

3.1 Name it, state the exact allowed-import set, and cite where that constraint
is written down.

3.2 Is the closure verified anywhere — a test, a lint rule, a CI check, an AST
walk? If yes, cite it and say what it would catch. If no, say plainly that it is
unenforced and relies on reviewer discipline.

3.3 How does that package receive the capabilities it cannot import — the
injection mechanism, who calls it, when, and what the defaults are when nobody
does. Cite the code.

3.4 What is the environment the closure exists to serve? Is it a real separate
image or process today, or a design intent being prepared for? Answer from
observed deployment, not from the docstring's aspiration, and say which you are
reporting.

### 4. Path manipulation

4.1 Find every place in the repo that mutates `sys.path` at runtime. For each:
file, line, what it inserts, and why it is needed. Include any `PYTHONPATH`
export in shell scripts or process config.

4.2 Which packages rely on being importable as bare top-level names rather than
through a parent package, and what would break if the path manipulation were
removed?

4.3 Is there a canonical anchor for resolving repo-relative paths — a
`REPO_ROOT`-style constant? Name it, cite its definition, show how it computes
its value, and list the subsystems that depend on it.

### 5. Charts and dashboards specifically

5.1 Give the complete list of imports at the top of the chart engine's core
module and of the dashboard compiler's main modules, grouped into stdlib,
third-party, and internal.

5.2 For each internal import in that list, state which layer it crosses and
whether it is consistent with the rules from section 2.3.

5.3 Do either subsystem's dependencies include anything heavyweight, optional,
lazily imported, or loaded at call time rather than module import time? Name them
and explain the reason for the deferral.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
