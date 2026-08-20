---
class: context-extraction
topic: 04 — context module system: registry, bundles, loader, on-demand fetch
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

This is the delivery mechanism for `chart_context.md` and `dashboards.md` and
their spokes. How modules are selected, budgeted, and fetched determines how the
skill files should be structured — router size, spoke granularity, fetch
triggers.

---

## Paste everything below into PRISM

You are being asked to describe your own context module system. This is
introspection for documentation purposes: do not build anything, do not report
frictions.

**I want the mechanism and the policy**, with `path:line` citations and short
excerpts. Paste the shape of a registry entry and the list of module identifiers,
but not the contents of the modules themselves.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a section boundary and name what remains.

### 1. The registry

1.1 Where does the registry live, and what is the schema of a single entry? Show
one entry verbatim as an example and explain every field.

1.2 How many entries are there? List all of their identifiers with their pillar
or category and their ordering value — identifiers only, not descriptions.

1.3 What does the ordering value control, and what is the effect of two entries
sharing one?

1.4 Are entries ever conditional — included for some users, some
specializations, some request types? Explain the selection logic and cite it.

### 2. Bundles and specializations

2.1 Enumerate the bundles or specializations that exist, and for each: which
modules it includes, which it suppresses, and when it is selected.

2.2 Is there an always-on set that every specialization inherits? Name it.

2.3 Which bundles include the chart module and which include the dashboard
module? If either is in the always-on set, say so explicitly.

### 3. The loader

3.1 Trace how a registry entry becomes text in the model's context: the function
that reads it, the base directory it resolves against, any transformation between
disk and delivery, and the order modules are concatenated in.

3.2 Is a module's content delivered byte-for-byte as it sits on disk, or is it
templated, trimmed, wrapped, or annotated on the way through? If it is
transformed, show the transformation.

3.3 What size accounting happens — per-module budgets, a total cap, truncation,
logging of what was loaded? Cite the code and give the current numbers.

### 4. On-demand retrieval

Some modules are registered and always loaded; others sit on disk and are fetched
mid-session by the repository-reading tool.

4.1 Explain both paths and what determines which one a given file uses.

4.2 For the on-demand path, give the exact call shape that resolves a file today.
Specifically: what is the path rooted at, are short relative paths supported, and
is there a search-root list? Cite the resolution code.

4.3 What happens on a miss — a path that does not resolve? What does the model
see, and is the failure loud or silent?

4.4 Is there a size limit or a warning threshold on files fetched this way?

### 5. My two module families

5.1 For the chart module and the dashboard module, give their registry entries
verbatim, and confirm which of their sibling files are registered versus fetched
on demand.

5.2 List the on-demand files that belong to each family, with byte sizes, and the
exact call that fetches one.

5.3 From what you can observe of the system's behaviour: is the router-plus-spoke
shape working as intended — do the spokes actually get fetched when they should?
Name any structural weakness you can see in how those files are organised for
retrieval.

5.4 Is there anything in the registry or loader that a person authoring these
files should know and probably does not — a constraint, a gotcha, an ordering
effect, an interaction with the always-on set?

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
