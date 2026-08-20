---
class: context-extraction
topic: Composer-in-dashboards delta re-extract + drag/panel feasibility
expected_reply: ~35 KB
created_at: 2026-08-19
sent:
status: OPEN
baseline_date: 2026-07-21
baseline_source: staging/prompts/archive/2026-07-21_composer_s3_full_stack_refresh.md
trigger: >
  The 2026-07-21 extraction predates the 2026-08-07 vendoring of prism-core into
  prism-main (287311b, fec2ace), so every path in our baseline may have moved,
  and four weeks of Composer work may have landed. Separately, staging is about
  to design (a) drag-from-anywhere on every dashboard widget and (b) first-class
  left/right dashboard panels — both of which need to know what the portal page
  and the Composer drop handler actually constrain.
reply_folded_into:
  - projects/echarts/dev/specs/composer_dashboard_stack.md   # the live/target tables
  - projects/echarts/dev/notes.md                            # "Still open" Composer bullet
  - prism/dashboards-portal.md
  - prism/security.md
  - staging/README.md
  - .cursor/rules/viz-platforms.mdc                          # Echarts Composer status para
---

**Staging-side note — do NOT paste this header into PRISM.**

Two jobs in one prompt. Sections 1-10 are a **delta re-extract**: our
`composer_dashboard_stack.md` carries 15 numbered baseline claims from
2026-07-21 and we need each one classified against current source. Sections
11-13 are **forward-looking feasibility** for the two uplifts we are about to
build, and are the only sections that ask for judgement rather than citation.

Path caveat to expect: the baseline says `web/backend_django/news/*.py` and
`web/prism_site/js/*.js`. Post-vendoring those may have moved. §2 exists to
re-anchor every path before the rest of the reply relies on them.

---

## Paste everything below into PRISM

This is read-only source introspection. Do not edit, create, delete, stage,
commit, or format any file. Do not implement a fix and do not propose a
redesign except where §11-13 explicitly ask for feasibility judgement. Inspect
the current `prism-main` working tree. Do not answer from remembered context,
prior sessions, or documentation where live source is available.

The purpose is to refresh an external staging repository's model of the
Composer-in-dashboards stack after the 2026-08-07 vendoring and roughly four
weeks of possible change since a 2026-07-21 baseline.

**For every numbered baseline claim in §3-§10, classify current source as
exactly one of:**

- `CONFIRMED` — current source matches the claim
- `CHANGED` — current source differs; quote the current truth
- `PARTIAL` — only part of the claimed path or behaviour exists
- `NOT FOUND` — a named path or symbol is absent after explicit search
- `GONE` — the file, symbol, route, or behaviour no longer exists
- `NEW` — current source contains relevant behaviour the claim does not cover

### Evidence rules

1. Inspect the repository first; do not infer.
2. Give repository-relative paths from the `prism-main` root, with `path:line`.
3. Quote code, signatures, selectors, MIME strings and message text **verbatim
   in fenced blocks**. Do not paraphrase them.
4. Distinguish committed / staged / unstaged / untracked where it matters.
5. Where a claim is `CHANGED`, quote the current truth, not a description of it.

**Reply budget: keep this under roughly 35,000 characters.** If you run long,
finish the section you are in, then list the remaining section numbers.

---

### 1. Repository state

1.1 Current branch, HEAD sha, and whether `prism-core` is a plain directory
(post-vendoring) or something else. Confirm `.gitmodules` is absent.

1.2 List every commit since `2026-07-21` that touches any Composer, dashboard
portal, or dashboard-serving path. Table: sha, date, author, subject, files.

1.3 Any uncommitted work in the working tree on those paths. The baseline noted
seven unstaged parent Composer files — say whether those are still unstaged,
committed, or gone.

### 2. Re-anchor the file inventory

For each role below, give the **current** path, byte size, line count, and a
one-line responsibility. Mark `NOT FOUND` where the role no longer has a file.

| Role | Baseline path (2026-07-21) |
|---|---|
| Composer injector for dashboards | `web/backend_django/news/dashboard_composer.py` |
| Dashboard-specific drag producer (JS) | `web/prism_site/js/dashboard_composer.js` |
| Generic Composer client (JS) | `web/prism_site/js/composer.js` |
| Composer HTTP endpoints | `web/backend_django/news/composer_views.py` |
| Artifact resolver | `web/backend_django/news/composer_artifacts.py` |
| Prompt construction SSOT | `web/backend_django/news/composer_prompt.py` |
| Snapshot validator/merger | `web/backend_django/news/composer_dashboard_snapshot.py` |
| Dashboard detail view + injection site | `web/backend_django/news/views.py` |
| Dashboard detail template | (name it) |
| Composer CSS | (name it) |

Also name any Composer-related file that exists today and is **not** in this
table.

### 3. Injection and gating

Classify each:

- **B1** — `dashboard_composer.py` mounts Composer **response-only** on the
  canonical user-dashboard detail route, and sets
  `PRISM_COMPOSER_DND_MODE = "dashboard_components"`.
- **B2** — Drag binding is owner-gated by
  `PRISM_VIEWER === PRISM_DASHBOARD_OWNER`; a non-owner viewing a shared
  dashboard gets no grips.

3.1 Paste the injector's public entry point signature and the complete set of
`window.*` globals it writes into the page (`PRISM_DASHBOARD_ID`,
`PRISM_TEMPLATE_HASH`, `PRISM_VIEWER`, `PRISM_DASHBOARD_OWNER`, and anything
else), each with the server-side value it is fed from.

3.2 On which routes is Composer mounted at all? Enumerate them, and for each say
whether drag-and-drop of dashboard components is enabled there.

### 4. `dashboard_composer.js` — the drag producer

Classify each:

- **B3** — ~205 lines; two-latch startup waiting on Composer-ready **and** the
  compiled dashboard's `prism:dashboard:ready` event, then calls
  `bindComponentDrag(_dashboardObj)` exactly once.
- **B4** — `ALLOWED_KINDS` contains exactly these 12: `chart`, `kpi`, `table`,
  `data_grid`, `pivot`, `stat_grid`, `tool`, `user_input`, `markdown`, `note`,
  `image`, `divider`.
- **B5** — Header lookup is `.kpi-header` for `kpi` and `.tile-header` for every
  other kind. `.note-head` is **not** recognised. No `.prism-composer-drag-grip`
  is ever injected. Net effect on an owned dashboard: 7 of 12 kinds are
  draggable; semantic markdown, legacy `note`, plain markdown, untitled image,
  and divider have no grip.
- **B6** — `draggable = true` is set on the **header element**, never on the
  `[data-tile-id]` wrapper and never on the tile body or chart canvas.
  `dragstart` early-returns for anything matching an `INTERACTIVE_SELECTOR`, and
  `userSelect` is set to `'none'` on the grip.
- **B7** — `dragstart` sets MIME `application/x-prism-artifact` with
  `effectAllowed = 'copy'` and exactly seven scalar fields:
  `type`, `id`, `path`, `label`, `dashboard_id`, `widget_kind`,
  `template_sha256`. `label` is formatted `"<Kind>: <title>"`. A `setData`
  failure aborts the drag with no visible error.
- **B8** — `window.DASHBOARD.getWidgetSnapshot(widgetId)` exists in the compiled
  dashboard and covers all 12 kinds, but **neither** `dashboard_composer.js` nor
  `composer.js` ever calls it, and `composer.js` contains no snapshot fields.

4.1 Paste the **entire `dragstart` handler verbatim**, plus the header-lookup
function and the `INTERACTIVE_SELECTOR` value.

4.2 Paste the full grip-binding routine — how it walks widgets, what it reads
from `window.DASHBOARD`, and what it does when a widget yields no header.

4.3 Is there any `dragend`, `drag`, or drag-image (`setDragImage`) handling? Any
visual affordance beyond cursor — outline, ghost, hover state? Quote the CSS.

4.4 Does anything re-bind after DOM changes — tab switch, filter re-render,
refresh poll, widget re-render? If binding happens once at ready, say so
explicitly and name what would silently lose its grip.

### 5. `composer.js` — the drop side

5.1 Paste the `drop` / `dragover` handlers verbatim. Which MIME types are read,
in what precedence, and what is the fallback if `application/x-prism-artifact`
is absent?

5.2 What does it do with the parsed payload — the exact normalisation
(`path` → `art_path` was in the baseline), what it stores, and where.

5.3 How is artifact state persisted across tab switch, page navigation, browser
history, and page reload? Name the storage and the key format.

5.4 Can multiple artifacts be attached to one message? Is there a maximum count,
a maximum total byte size, or de-duplication by widget id? Quote any limit
constants.

5.5 What does the user see once a component is attached — the card markup, the
label, whether a preview is fetched, and from which endpoint.

5.6 How are errors surfaced? Name every user-visible Composer error path
(`reportArtifactError` or equivalent) and quote the message strings.

### 6. Endpoints

- **B12** — There are eight `@csrf_exempt` Composer endpoints, each doing manual
  Kerberos authentication in the view body.

6.1 Table every Composer endpoint: URL pattern, view function, file:line, HTTP
methods, CSRF treatment, auth mechanism, and whether it touches S3.

6.2 For the artifact-info / preview endpoint specifically: what does it return
for a `dashboard_component`, and does it include any current-view state?

### 7. `composer_artifacts.py` — resolution

- **B10** — `read_artifact_content` has a `dashboard_component` branch guarded by
  `_ALLOWED_KINDS`; it resolves the widget dict **live from the server-side
  manifest** rather than trusting the dragged payload; there is **no**
  `purpose="preview" | "submit"` split.

7.1 Paste the `dashboard_component` branch verbatim.

7.2 Exactly which fields of the dragged payload are trusted, and which are
re-derived server-side? Give a two-column authority table.

7.3 What happens when `template_sha256` from the drag no longer matches the
current template — hard error, warning in the body, or silent?

7.4 What happens when the widget id no longer exists in the manifest, or the
kind is not in `_ALLOWED_KINDS`?

### 8. Snapshots

- **B9** — `composer_dashboard_snapshot.py` does not exist; there is no
  server-side snapshot schema, validator, or per-kind merge.

8.1 Confirm or correct. If any snapshot handling has appeared anywhere in the
parent tree since, cite it and describe its schema.

### 9. Prompt construction — the part we most need verbatim

- **B11** — `composer_prompt.py::build_composer_prompt` is the single source of
  truth for prompt framing; `dashboard_component` bodies are **inlined** as
  canonical widget JSON inside `content_summary`, never sent as a reference.

9.1 Paste `build_composer_prompt` **in full, verbatim**. This is the highest-value
answer in the prompt — we cannot reason about prompt quality from a description.

9.2 Paste a **complete, real rendered example** of the final prompt string PRISM
receives when a user drags one `chart` widget into Composer and sends the
message "why did this move today". Show the literal text including every framing
sentence, header, delimiter, and the full JSON body — exactly as the model sees
it. Redact only identifiers.

9.3 Do the same, abbreviated, for one `table` and one `user_input` component, so
we can see the per-kind differences in the body.

9.4 What is the **manifest slice** that travels? Just the one top-level widget
dict, or does it carry the dataset, the filters, the layout position, the
dashboard title, sibling widgets, or anything else? Enumerate exactly.

9.5 Does the prompt carry any of: current filter state, the visible date window,
sort order, the rendered numbers the user is actually looking at? If not, say so
plainly — a user asking "why did this move" while looking at a filtered view is
the case we care about.

9.6 Where does `build_composer_prompt` output sit relative to the user's own
typed text — before, after, in a system position, in a separate content block?

9.7 Is the same builder used for the email path and the fire-off path, or are
there divergent framings?

### 10. Reload handshake and loose ends

- **B13** — Installed `composer.js` and the installed compiled-dashboard runtime
  both use `__prismComposerStreaming` / `prism:composer-streaming-change`; the
  staging candidate uses the neutral `__prismNavigationHoldCount` /
  `prism:navigation-hold-change`.
- **B14** — `enable_inline_chat=True` product intent unconfirmed; there is an
  empty `website_dev.md` registry entry.
- **B15** — Persisted user-input routes are live; conditional S3 writes use a
  raw-boto3 Django bypass that degrades to a **non-atomic plain PUT** when the
  store rejects conditional headers.

10.1 Classify each, quoting the current symbol names.

10.2 What happens to an attached-but-unsent artifact if the dashboard
auto-refreshes or the page reloads underneath it?

---

### 11. Feasibility — drag from anywhere on a widget

We want to remove the header-only restriction: a user should be able to start a
drag from anywhere on a widget — the chart canvas, a table body, the markdown
text, the whole tile. Answer as engineering judgement grounded in the code you
just read.

11.1 If `draggable = true` moved from the header element to the
`[data-tile-id]` wrapper, what would break? Enumerate concretely: chart canvas
pan / brush / data-zoom, table cell text selection and column sort, control
drawer form inputs, popup triggers, the tool widget's inputs, link clicks,
scroll inside a scrollable table body.

11.2 Does anything **server-side** depend on the drag having originated from a
header — or is the header purely a client-side affordance? Cite whatever proves
this.

11.3 What is the most robust pattern available to you here: (a) whole-tile
`draggable` plus an `INTERACTIVE_SELECTOR` denylist, (b) a press-and-hold /
drag-threshold gesture before the native drag arms, (c) a persistent visible
grip overlay on hover covering the whole tile, or (d) something else? Give a
recommendation with the reason, and name the failure mode of each.

11.4 Are there known browser constraints in the production environment — the
browser and version in use, and whether HTML5 drag-and-drop from a `<canvas>`
element behaves there.

11.5 If the compiled dashboard itself emitted the drag handlers rather than the
portal injecting them, what would break? We keep the compiled dashboard neutral
(it must render identically from `file://`, S3, and email), so we would need the
handlers to be inert outside the portal. Is there a clean signal for that?

### 12. Feasibility — dashboard-emitted left/right panels

We are adding first-class left and right panels to the compiled dashboard —
both an overlay mode (floats above the grid) and a push mode (narrows the grid).
These are emitted by the dashboard HTML itself, not by the portal.

12.1 **How is the compiled dashboard embedded in the portal page** — an
`<iframe>`, an inline `srcdoc`, server-side HTML inclusion, or a direct S3
redirect? This determines whether a dashboard-emitted panel is isolated or
shares a stacking context with portal chrome. Cite the template.

12.2 If it is not isolated: what portal chrome is `position: fixed` or
`position: sticky` on the dashboard detail page, and what are the z-index values
in play? Give the full z-index inventory for that page — header, nav, Composer,
toasts, modals.

12.3 **Where does Composer physically sit** on the dashboard detail page —
docked bottom, right rail, floating, expanding? Give its dimensions, its
positioning, and whether it overlays dashboard content or reserves space. A
right-side dashboard panel and a right-docked Composer would collide.

12.4 Does the portal ever change the width of the dashboard container at runtime
(Composer expanding, a sidebar opening)? If so, what event fires, and does
anything currently tell the embedded dashboard to re-layout?

12.5 Is there a viewport-width floor below which the dashboard detail page
already misbehaves? Any responsive breakpoints we would be fighting.

12.6 Any accessibility or focus-management convention the portal already
follows that a panel should match — focus trapping, Escape handling, ARIA roles.

### 13. Judgement

13.1 Of the Composer-in-dashboards stack, name the three parts you consider most
fragile or most likely to surprise someone maintaining the compiler from
outside. Coupling that is not obvious, state that lives in two places, a path
only one trigger exercises.

13.2 If you were told to make dragged dashboard components produce materially
better PRISM answers, and could change only one thing in this stack, what would
it be and why?

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
