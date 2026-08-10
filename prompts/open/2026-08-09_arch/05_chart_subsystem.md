---
class: context-extraction
topic: 05 — chart subsystem architecture end to end
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

The engine code is in sync with `projects/altair/altair-payload/`, so this is not
about recovering content — it is about the surrounding architecture we do not
own: how the sandbox reaches the engine, what happens to a rendered PNG after
`make_chart` returns, and where charts are consumed. That is the part our
docstrings and `prism/` docs get wrong.

---

## Paste everything below into PRISM

You are being asked to describe your own chart subsystem's architecture. This is
introspection for documentation purposes: do not build anything, do not render a
chart, do not report frictions.

**I want the surrounding architecture, not the engine internals.** I already have
the engine source. What I need is how it is wired into everything else: call
paths, injection, artifact handling, consumers. Cite `path:line` and use short
excerpts. Do not paste large regions of the chart module.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a section boundary and name what remains.

### 1. Module split

1.1 Name every module in the chart subsystem and give each a one-sentence
responsibility. Include the render core, the trusted-side wrapper, the studio
modules, the units helper, and anything else that belongs.

1.2 Explain why the split exists — what each side is allowed to do that the other
is not, and what problem the separation solves. Cite where that rationale is
recorded if it is written down anywhere.

1.3 Which of these modules are owned and maintained on your side versus dropped
in from elsewhere? If you can tell from history or convention, say which.

### 2. The injection seam

2.1 Describe the mechanism by which the trusted side installs capabilities onto
the render core: the function, its parameters, who calls it, and at what moment.

2.2 For each injected capability, name the concrete implementation it receives
and the module that provides it.

2.3 What is the behaviour of the core when a capability was never injected? Go
capability by capability and say what degrades and how visibly.

2.4 In the live deployment right now, when user code calls the chart builder,
which module object does it actually get and are the capabilities installed at
that moment? Answer from the observed import path, and cite it.

### 3. From call to artifact

3.1 Trace a single chart request end to end: model emits code, code calls the
builder, the builder renders, the image is written somewhere, something is
returned, the user eventually sees it. Give the ordered steps with citations.

3.2 Where does the rendered image physically go — filesystem, object storage,
what bucket and key shape, what lifetime?

3.3 How does the user get a viewable link? Describe the URL that comes back, who
generates it, whether it expires, and whether it requires authentication. If this
changed recently, say what it was before and what it is now.

3.4 What does the returned result object carry, field by field?

### 4. Consumers

4.1 Enumerate every place a chart can end up: chat responses, email, reports,
dashboards, the portal, anything else. For each, name the code path that puts it
there.

4.2 Do any of those consumers call the chart engine differently — different entry
point, different parameters, different post-processing? Describe the differences.

4.3 Is the chart engine used anywhere by non-model code — a scheduled job, a
report generator, a test harness?

### 5. Supporting infrastructure

5.1 Fonts: where do they live, how does the engine find them, what happens if the
directory is missing or empty?

5.2 The interactive studio companion: what is it, when is one produced, where
does it go, and how does a user reach it?

5.3 Quality control: what validation runs automatically on a chart, and what is
blocking versus advisory? If a model-graded visual QC step used to exist and was
removed, say when and why.

5.4 Tests: where do the chart tests live, what do they assert, and is there a
characterization or golden-file harness? Describe what it pins and how it is
regenerated.

### 6. The seams that bite

From your own vantage point, name the parts of this subsystem that are most
fragile, most surprising, or most likely to break when the engine is replaced
with a newer copy from upstream. I am asking for engineering judgement here, not
a file listing.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
