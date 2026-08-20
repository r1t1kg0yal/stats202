---
class: context-extraction
topic: 01 — repository topology, module ownership, entry points
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

Opens the architecture series. Establishes the map every later prompt hangs off:
what the top-level trees are, who owns what, where execution starts. Deliberately
asks for structure and responsibility rather than file contents.

---

## Paste everything below into PRISM

You are being asked to describe your own repository's structure. This is
introspection for documentation purposes: do not build anything, do not run an
analysis, do not report frictions.

**What I want is architecture, not contents.** Explain the design — what each
piece is for, who owns it, where the boundaries are — and cite `path:line` as
evidence. Paste only short excerpts (a signature, a class list, a dict of
config keys). **Do not paste whole files.** Where you are describing intent
rather than mechanism, say so.

**Reply budget: keep this reply under roughly 30,000 characters.** The prompt is
scoped to fit. If you run long, stop at a section boundary, say where you
stopped, and name what remains.

### 1. The top-level map

1.1 List every top-level directory in the repository. For each: its purpose in
one or two sentences, its rough size (file count and total bytes, excluding
`.git`, `__pycache__`, `node_modules`, virtualenvs), and whether it is an
importable Python package, a static asset tree, config, docs, or tests.

1.2 Do the same one level deeper for the directories that carry application
logic, so I can see the shape inside them rather than just their names.

1.3 Which of these directories are on `sys.path` at runtime, and what makes them
so? Cite the code or config that puts them there.

### 2. Ownership and responsibility

2.1 For each major package, give a one-paragraph statement of responsibility —
what belongs in it and what deliberately does not. I am specifically after the
rule an engineer would apply when deciding where a new module goes.

2.2 Name the packages that are *layers* (everything above them may import them)
versus packages that are *leaves* (nothing imports them). Cite evidence rather
than asserting it.

2.3 Are there any directories that are vestigial, deprecated, or mid-migration —
present on disk but no longer the live path? Name them and say what replaced
them.

### 3. Entry points

3.1 Enumerate every way execution starts in this system: the MCP server, web
request handling, scheduled jobs, CLI utilities, test runs. For each, give the
file, the callable, and one sentence on what triggers it.

3.2 Trace the startup sequence of the main server process from process launch to
ready-to-serve, as an ordered list of steps with file citations. Note anything
that happens at import time rather than in a startup function.

3.3 What configuration does startup depend on — environment variables, config
files, secrets, service discovery? List them with where each is read.

### 4. Charts and dashboards, located

I maintain the chart engine and the dashboard compiler, so I need to know where
they sit in the structure above rather than how they work internally (later
prompts cover that).

4.1 Name every directory and file that belongs to the chart subsystem, and every
one that belongs to the dashboard subsystem. Mark which are engine code, which
are model-facing documentation, which are assets, and which are tests.

4.2 For each of those two subsystems, name the packages it depends on and the
packages that depend on it.

4.3 Is either subsystem's placement in the tree unusual — split across trees,
inconsistent with the ownership rules from section 2, or the result of a
migration? Explain why it ended up that way if the history shows it.

### 5. Scale

Give the twenty largest source files in the repository with byte counts and a
one-line statement of what each is, so I can see where the mass actually sits.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
