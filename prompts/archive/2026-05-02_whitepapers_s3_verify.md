---
session: whitepapers SSOT migration — S3 verbatim verification, portal-wiring drift check, dual-surface and scope-extras decisions
sent: 2026-05-02
reply: projects/whitepapers/dev/scans/2026-05-02_whitepapers_s3_verify_reply.md
reply_folded_into:
  - projects/whitepapers/whitepapers-payload/whitepaper_data_integrations.md (overwrite OCR-extracted version with §2.1 verbatim if drift)
  - projects/whitepapers/whitepapers-payload/whitepaper_user_personalization.md (overwrite with §2.2; expected to resolve OCR-induced full-section duplication)
  - projects/whitepapers/whitepapers-payload/whitepaper_world_state_and_reasoning.md (overwrite with §2.3; expected to resolve title drift "FICC Reasoning" vs "World State & Reasoning")
  - projects/whitepapers/whitepapers-payload/faq.md (overwrite with §2.4)
  - projects/whitepapers/whitepapers-payload/email_usage_guide.md (overwrite with §2.5)
  - projects/whitepapers/README.md (resolve §C dual-surface axis from §6 reply; resolve §F scope-extras axis from §5 reply; bump status from "intake from OCR scan" to "intake verified")
  - projects/frontend/dev/scans/ — flag any drift in WHITEPAPER_MAP / view bodies / listing-page bodies vs `2026-05-02_portal_views_urls_templates.md` (§3, §4)
  - prism/ — likely a new curated doc covering the customer-facing static-content surface (or an extension to `prism/dashboards-portal.md`) once §5 / §6 / §7 reveal what's actually there
status: USED
---

Title: Whitepapers SSOT migration — verify OCR intake, confirm portal wiring, lock dual-surface and scope-extras decisions

I'm migrating PRISM's customer-facing static documents (white papers
+ how-to guides) off S3 (`secondary/technical_docs/`) and into the
codebase under `ai_development/context/white_papers/`. The Cursor
staging side has a sibling project `projects/whitepapers/` that
workshops the content before each PRISM drop.

State on the staging side as of this prompt: 5 inherited document
bodies have already been **extracted from an OCR scan**
(`projects/whitepapers/dev/scans/2026-05-02_whitepapers_intake.md`) and
landed verbatim in `projects/whitepapers/whitepapers-payload/`. The
design decision (locked) is to collapse those 5 inherited docs into
**3 hand-curated docs** during workshop:

```
1. "What is Prism"     (prospect → convert)   — short, capability-led
2. "Using Prism"       (active → activate)    — practical, command-led
3. "How Prism Works"   (power + skeptic →     — encyclopedic, neutral,
                        retain + defend)        cites limits honestly
```

This round-trip exists to (a) verify the OCR intake matches what S3
actually serves, (b) close inventory gaps the OCR scan can't answer,
(c) lock two design axes that need PRISM-side facts to resolve
(dual-surface consumption pattern; rich-media support), and (d)
surface any other static-document surfaces that should join this
project before workshop starts.

Use `execute_analysis_script` (with `s3_manager.get(...)`) and
`list_ai_repo` to introspect. Reply with verbatim source pasted in
fenced code blocks and exact paths. Mirror the section structure
below — each numbered section in your reply answers the
same-numbered section here. Verbatim, no paraphrase, no summary.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it (file missing, S3 permission denied, symbol
ambiguous). This is NOT a frictions report — it is a minimal
coverage note.

---

## 1. Inventory under `secondary/technical_docs/`

List every key currently under the S3 prefix
`secondary/technical_docs/` via `s3_manager.list(...)` (or
equivalent). Working inventory the OCR scan implies:

```
secondary/technical_docs/
├── whitepaper_data_integrations.md
├── whitepaper_user_personalization.md
├── whitepaper_world_state_and_reasoning.md
├── faq.md
└── email_usage_guide.md
```

1.1 Are there exactly 5 files under that prefix? If the count is
    higher, list every additional key with size and last-modified
    timestamp. If lower, list which expected file is missing.

1.2 Are any of the 5 files currently 0 bytes, or do any look
    truncated (size ≪ what the OCR scan suggests, e.g.
    Data Integrations OCR ≈ 12 KB, User Personalization ≈ 16 KB,
    World State ≈ 12 KB, FAQ ≈ 10 KB, Email Usage Guide ≈ 8 KB)?

1.3 Are there sibling prefixes under `secondary/` that hold
    additional customer-facing static prose I should consider for
    this project? Specifically check:
    - `secondary/guides/`
    - `secondary/help/`
    - `secondary/onboarding/`
    - `secondary/glossary/`
    - `secondary/training/`
    - `secondary/docs/`
    - any other `secondary/<x>/*.md` prefix where the contents read
      as customer-facing prose rather than data / observations

    For each prefix that exists, list its file inventory.

---

## 2. Verbatim S3 bodies — drift-check vs the OCR-extracted versions

For each file below, fetch via `s3_manager.get(<path>)` and paste
the complete decoded UTF-8 body in a fenced markdown code block.
Do not paraphrase, summarize, truncate, or "clean up" the body. I
need the bytes that PRISM is currently serving so the staging SSOT
can be diffed against the OCR extract before workshop.

After each verbatim paste, append a one-line metadata block:

```
[ size: <bytes>; last_modified: <ISO timestamp>; checksum: <md5 or etag> ]
```

If the S3 body is byte-identical to the OCR-extracted version
already in `projects/whitepapers/whitepapers-payload/<name>.md`,
just say so explicitly (`[ matches OCR extract verbatim ]`) — no
need to paste in that case.

The OCR extracts carry two known artifacts I want explicitly
confirmed or denied against the S3 bodies:

- **User Personalization** (§2.2): the OCR extract has
  `## Pillar 1: Memories` and `## Pillar 2: File Cabinet` appearing
  TWICE in the document body, with intervening
  `<details><summary>Hyper-detailed visual description</summary>`
  figure scaffolding from the paper2md pipeline. The S3 body almost
  certainly has neither the duplication nor the `<details>` blocks
  — confirm.

- **World State** (§2.3): the OCR extract has document title
  `# Prism AI -- World State & FICC Reasoning`, but the portal's
  `title_map` for the `world-state` URL key returns
  `"World State & Reasoning"`. Confirm what the S3 body's H1
  actually says.

### 2.1 `whitepaper_data_integrations.md`

Path: `secondary/technical_docs/whitepaper_data_integrations.md`

### 2.2 `whitepaper_user_personalization.md`

Path: `secondary/technical_docs/whitepaper_user_personalization.md`

### 2.3 `whitepaper_world_state_and_reasoning.md`

Path: `secondary/technical_docs/whitepaper_world_state_and_reasoning.md`

### 2.4 `faq.md`

Path: `secondary/technical_docs/faq.md`

### 2.5 `email_usage_guide.md`

Path: `secondary/technical_docs/email_usage_guide.md`

---

## 3. `WHITEPAPER_MAP` + render views — portal-wiring drift check

Cursor staging has, per
`projects/frontend/dev/scans/2026-05-02_portal_views_urls_templates.md`:

```python
WHITEPAPER_MAP = {
    'data-integrations':    'whitepaper_data_integrations.md',
    'user-personalization': 'whitepaper_user_personalization.md',
    'world-state':          'whitepaper_world_state_and_reasoning.md',
}
```

Plus view functions: `views.whitepapers`, `views.user_guides`,
`views.faq`, `views.email_guide`, `views.download_whitepaper`.

3.1 Read the current `mysite/news/views.py` (or whatever the
    canonical Django views file is — confirm path) and paste the
    verbatim current `WHITEPAPER_MAP` definition. Still 3 entries
    with those exact keys → filenames? Any additions, renames, or
    removals?

3.2 Paste the verbatim current `download_whitepaper(request, doc_name)`
    function body. Confirm whether the S3 path it reads from is
    still `secondary/technical_docs/{filename}` (the scan shows the
    string with what looks like a missing f-prefix —
    `s3_manager.get("secondary/technical_docs/{filename}")` —
    confirm whether it is in fact an f-string in the actual source).

3.3 Paste the verbatim current `faq` and `email_guide` view bodies.
    Confirm S3 paths (`secondary/technical_docs/faq.md`,
    `secondary/technical_docs/email_usage_guide.md`) and confirm
    `title_map` contents if any (the scan shows
    `'world-state': 'World State & Reasoning'` for
    `download_whitepaper`'s title map).

3.4 Paste the verbatim current `whitepapers` and `user_guides` view
    bodies (the listing-page renders).

3.5 Paste the relevant fragment of `mysite/news/urls.py` that wires
    the 5 routes:
    - `/whitepapers/`
    - `/user-guides/`
    - `/faq/`
    - `/guide/email/`
    - `/resources/<str:doc_name>/`

    Confirm whether each route exists with the path / view-name
    pairing the scan shows, or whether anything has changed.

3.6 Are there any OTHER views in `views.py` that render Markdown
    from `secondary/technical_docs/` that I haven't captured? If
    yes, paste each verbatim with its URL route.

---

## 4. Listing-page bodies — drift check

The OCR scan has, for `whitepapers.html`:

> ## Whitepapers
>
> Explore in-depth technical papers covering Prism AI's core systems,
> data integrations, and analytical frameworks.
>
> ### Data Integrations
> Comprehensive overview of Prism's 20+ data sources including Haver,
> GS Market Data, GS Quant, and more.
>
> ### User Personalization
> How Prism learns your preferences, manages memories, and personalizes
> analysis across conversations.
>
> ### World State & Reasoning
> How Prism assembles real-time context, maintains a worldview, and
> reasons about markets.

(and a similar block for User Guides currently advertising only the
Email Usage Guide).

4.1 Paste the verbatim current bodies of
    `mysite/news/templates/news/whitepapers.html`,
    `mysite/news/templates/news/user_guides.html`, and
    `mysite/news/templates/news/doc_page.html`.

4.2 If the listing pages are now driven from a Python list / dict
    in views (rather than hardcoded HTML), paste that data
    structure verbatim.

---

## 5. Rich-media support — what `news/doc_page.html` actually renders

The inherited document bodies use mermaid diagrams heavily
(graph TD / flowchart LR / sequenceDiagram). The hand-curated
3-doc workshop pass needs to know what survives the render path.

5.1 Paste the verbatim body of `_render_markdown(...)` (wherever it
    lives — likely `mysite/news/views.py` or a util module). Which
    Python markdown library does it call? Which extensions are
    enabled? (`fenced_code`, `tables`, `sane_lists`, `pymdownx.*`?)

5.2 Does the render path handle ` ```mermaid ` fenced blocks? If
    yes, where is the mermaid-to-SVG conversion happening (server
    side, or a client-side `<script>` tag in `news/base.html` /
    `news/doc_page.html`)? If no, mermaid blocks render as inert
    fenced code on the served page.

5.3 What other rich-media is supported in the doc render path?
    - HTML `<details>` / `<summary>` (the OCR scan has these
      from paper2md figure scaffolding; do they survive render?)
    - `<img>` tags / external image URLs
    - GS-styled inline charts (e.g., embedding a live observatory
      chart by URL or shortcode)
    - Code-block syntax highlighting (which languages?)
    - LaTeX / MathJax inline math

5.4 Paste the verbatim head section of `news/base.html` (or
    whichever base template `doc_page.html` extends), so I can see
    which JS / CSS bundles are actually loaded on the doc page.

---

## 6. Scope-extras — what other customer-facing prose should join `projects/whitepapers/`?

Working assumption: `projects/whitepapers/` covers the full set of
**customer-facing static documents** rendered through the portal.
The 5 known files render through `news/doc_page.html` from
`secondary/technical_docs/`. I want to confirm there's nothing else
analogous, and surface candidate additions.

6.1 Any OTHER markdown bodies fetched from S3 by a portal view and
    rendered through `news/doc_page.html` (or a similar
    render-a-markdown-as-an-html-page template) that I haven't
    captured in §3?

6.2 Any HARDCODED long-form content baked directly into a `.html`
    template (e.g., a long About page, a Privacy page, a Terms
    page, a Methodology blurb) that conceptually belongs in this
    project too because it's customer-facing prose, not chrome?

6.3 Any prose content under `ai_development/context/` (NOT the
    L1/L2 operating-instruction modules — those are out of scope
    for `projects/whitepapers/` and live in
    `projects/docstrings/` or `projects/apis/apis-payload/modules/`
    — but **customer-facing prose** that happens to live under
    `context/` for organizational reasons)? Specifically, does
    `ai_development/context/white_papers/` already exist as a
    directory? If yes, list its contents.

6.4 Any S3 prefixes other than `secondary/technical_docs/` that
    hold customer-facing prose (training material, onboarding
    decks, admin-only docs, feature explainers, release notes,
    glossaries, methodology papers)? List each prefix with its
    inventory.

6.5 Any release-notes / changelog / "what's new" content for Prism
    that's customer-facing today, anywhere? (Where does a user go
    to find out what Prism shipped this quarter?)

For each candidate surfaced under 6.1–6.5, give a one-line
classification — I'm not asking you to make the call, just label:

```
A. Customer-facing static prose served through the portal       → join whitepapers/
B. LLM operating instructions (always-on or skill-bundled)      → stays in docstrings/ or apis/modules/
C. Internal admin / dev / ops docs                              → not in scope for this project
D. Generated artifacts (reports, dashboards, observations)      → not in scope
E. Doesn't fit cleanly — flag for follow-up                     → tell me why
```

The locked design above (3 hand-curated docs: "What is Prism" /
"Using Prism" / "How Prism Works") is the destination. If a
candidate looks like it would land cleanly into one of those three,
say which.

---

## 7. Dual-surface — PRISM's own consumption of these whitepapers

This section is the open design axis. The question: when a user
asks PRISM "what data sources do you have?" or "how does Prism
work?" or "tell me about your scheduled processes" — does PRISM
read the customer-facing whitepapers as authoritative
self-description, or is there a separate L2 self-knowledge surface?

7.1 List every L2 module under
    `ai_development/context/modules/static/` whose **role is to
    describe Prism itself** (vs. teaching Prism about an external
    data source / instrument / tool). Examples I'd guess at:
    `core.md`, `prism_overview.md`, `about_prism.md`,
    `capabilities.md`, `architecture_overview.md`, anything in a
    `prism/` or `self/` subdirectory. Paste the H1 + first
    paragraph of each.

7.2 When a user message contains "what is Prism" / "how does Prism
    work" / "tell me about your data sources" / "what can you do",
    which L2 modules currently get pulled into context (via
    `include_modules=[...]` triggers, or always-on Tier 1, or
    keyword-triggered loading)? Paste the relevant trigger /
    routing logic if it lives in code; describe the convention if
    it lives only in module frontmatter.

7.3 If `ai_development/context/white_papers/` were created today,
    would the L2 module loader sweep it as part of normal context
    assembly? I.e., does the loader walk all of
    `ai_development/context/<…>/` looking for `.md` files, or does
    it only walk a known-allowlisted set of subdirectories
    (`modules/static/`, `modules/runtime/`, etc.)? Paste the
    relevant loader path-discovery code.

7.4 Three design options I'm choosing among. Which do you think
    fits PRISM's existing conventions best, and why?

    (a) **Shared SSOT** — the customer-facing `white_papers/<x>.md`
        is also the L2 module PRISM loads when describing itself.
        One file, two readers (customer + LLM). Constrains style:
        no marketing fluff, every paragraph earns its always-on /
        on-demand cost.

    (b) **Compiled** — customer-facing whitepapers auto-generated
        downstream from existing per-source L2 modules
        (`apis-payload/modules/*.md`, etc.) and registries (the
        skill catalog, the observatory domain list, the data-
        function output contracts). Drift impossible by
        construction. The customer doc is downstream, never
        upstream.

    (c) **Parallel** — customer-facing whitepapers and LLM-facing
        skill modules are independent surfaces with independent
        workshops. Style freedom. Some drift inevitable — needs a
        review cadence to keep claims aligned.

    The hand-curated, artisanal authoring discipline is locked
    (no auto-generation tooling in this project), which leans
    away from (b). But (a) and (c) are both compatible with that.
    Your input: which is closer to how PRISM is structured today,
    and which would you recommend going forward?

---

## 8. Destination directory — `ai_development/context/white_papers/`

8.1 Does `ai_development/context/white_papers/` already exist as a
    directory? If yes:
    - List its contents (filenames + sizes).
    - Tell me when each file was last modified and (if visible
      from git or the filesystem) who last touched it.
    - Are these files referenced anywhere — by views.py
      (for portal serving), by an L2 module loader, by a skill
      registry, by a runtime context generator? Paste the
      reference if so.

8.2 If `ai_development/context/white_papers/` does NOT exist,
    are there existing `ai_development/` directories that follow a
    similar "static prose checked into the codebase" pattern that
    I should match conventions to (e.g., `ai_development/docs/`,
    `ai_development/static_pages/`, `ai_development/help/`,
    `ai_development/context/help/`)? List them so the staging side
    can mirror naming + structure.

8.3 Any restrictions / linting / CI checks that apply to
    `ai_development/context/<x>.md` files broadly that I should be
    aware of when shipping these whitepapers (size limits, header
    requirements, frontmatter requirements, mermaid linting,
    spelling, tone)?

---

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it.
