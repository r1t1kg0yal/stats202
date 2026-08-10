---
class: context-extraction
topic: 06 — dashboard subsystem architecture end to end
expected_reply: ~30 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

Dashboards reach further into PRISM than charts do — storage, refresh
scheduling, the portal, user input, sharing — so this is where our documentation
is most likely to be stale. Echarts parity has not been re-verified since the
vendoring, so §1.4 asks about that directly.

---

## Paste everything below into PRISM

You are being asked to describe your own dashboard subsystem's architecture. This
is introspection for documentation purposes: do not build a dashboard, do not
report frictions.

**I want architecture and data flow**, with `path:line` citations and short
excerpts. Do not paste large regions of the compiler.

**Reply budget: keep this reply under roughly 30,000 characters.** If you run
long, stop at a section boundary and name what remains.

### 1. Module map

1.1 List every module in the dashboards package with a one-sentence
responsibility each, plus the scheduled-job entry point that lives outside the
package.

1.2 Draw the call graph between them: which module calls which, and which is the
public entry point that everything else routes through.

1.3 These modules import each other by bare sibling name rather than through the
package. Explain the mechanism that makes that work, cite it, and name the
execution contexts that depend on it.

1.4 These files are authored elsewhere and copied in. Measure each one now —
bytes, line count, sha256 — with any single trailing newline stripped, so I can
confirm my copies are in sync. Table only, no commentary.

### 2. Compilation

2.1 Trace a dashboard build end to end: what the model supplies, what the
compiler does with it, what comes out. Ordered steps with citations.

2.2 What is the input contract — the manifest or definition object? Describe its
top-level shape and the fields that matter, without pasting a full schema.

2.3 What validation runs, what blocks a build versus warns, and where does that
logic live?

2.4 What exactly is emitted — one HTML file, a folder, assets alongside? Is the
JavaScript inlined or referenced, and why?

### 3. Storage and identity

3.1 Where does a built dashboard live? Give the storage layout: buckets,
prefixes, per-user paths, registries, manifests, and what each file is for.

3.2 How is a dashboard identified and looked up — by id, slug, owner plus name?

3.3 What does a user's manifest or registry record about their dashboards, and
which code updates it?

3.4 What is the sharing model — private, shared, public — and where is that
enforced?

### 4. Refresh

4.1 Enumerate every way a dashboard's data gets refreshed: scheduled job,
in-process runner, a user clicking something, anything else. For each, name the
trigger, the code path, and the process model.

4.2 How does the scheduler decide a dashboard is due, and where is that schedule
configured?

4.3 What happens on partial failure — one dashboard in a batch fails, or one data
pull inside a dashboard fails? Describe the isolation and the recorded state.

4.4 After a successful refresh, what gets updated and in what order? Note
anything that one trigger path updates and another does not.

### 5. The browser side

5.1 What JavaScript ships inside a compiled dashboard, and where does it come
from on disk?

5.2 What interactive behaviour is supported — filters, drill-downs, exports,
polling for fresh data? Name the mechanisms.

5.3 Are there external network dependencies at view time? Name each, what breaks
without it, and whether reachability has been verified in the production browser
environment.

5.4 How does a dashboard know its data is stale, and what does the user see?

### 6. Portal integration and user input

6.1 List the routes that serve, refresh, share, or accept input for a dashboard:
URL pattern, view function, file, and auth treatment.

6.2 Describe the persisted user-input feature: what a user can save, where it is
stored, how concurrent writes are handled, and what the failure mode is if the
store rejects a conditional write.

6.3 Describe the current state of the Composer integration in plain terms — what
works today, what is scaffolded but unused, what is absent. Be specific about
what is genuinely wired versus what merely exists as a definition.

### 7. The seams that bite

Name the parts of this subsystem you consider most fragile or most likely to
surprise someone maintaining the compiler from outside — coupling that is not
obvious, state that lives in two places, a path that only one trigger exercises.
Engineering judgement, not a file listing.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
