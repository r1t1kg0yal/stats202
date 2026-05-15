# gs_reference — stitched bundle (Markdown + HTML + CSS)

This file merges project prose, Django templates, and stylesheet sources
into **one Markdown document** for PRISM / LLM context. Canonical sources
remain under `projects/gs_reference/`; regenerate with:

`python3 dev/stitch_reference_bundle.py`

---

## Table of contents

1. [README](#1-readmemd)
2. [Design DNA spec](#2-design-dna-spec)
3. [CSS — tokens.css](#3-css--tokenscss)
4. [CSS — fonts.css](#4-css--fontscss)
5. [CSS — components.css](#5-css--componentscss)
6. [HTML templates](#6-html-templates)

---

## 1. README.md

### projects/gs_reference/

Self-contained Django mock of the goldmansachs.com visual design
language as of 2026-05-14, paired with an authoritative markdown
spec for PRISM-side reference. Lets PRISM (or Cursor on PRISM's
behalf) reason about GS-styled UI decisions against a runnable
verification surface, not against a stale screenshot or a
half-remembered description.

```
┌────────────────────────────────────────────────────────────────────┐
│  THIS PROJECT'S TWO-LAYER OUTPUT                                   │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│   1. dev/specs/gs_design_dna.md  ← the SSOT PRISM reads in chat    │
│      (~1,000 lines; tokens + typography + components +             │
│       page archetypes + PRISM-runtime substitution recipes)        │
│                                                                    │
│   2. gs_reference-payload/ai_development/mysite_gs/  ← runnable    │
│      Django mock that REALIZES every claim in the spec, with       │
│      8 pages covering every signature layout pattern               │
│                                                                    │
│   Both layers are byte-readable by PRISM. The spec answers the     │
│   "what" + "why"; the mock proves the "how" with rendered HTML.    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

#### Status

LIVE — boots end-to-end via `python dev/run_gs_reference.py`. All
8 pages render. CSS implements the full `--gs-uitk-*` token namespace
(colors + typography + spacing + radius + dataviz palette), the 20
GS Sans + GS Sans Condensed `@font-face` blocks targeting PRISM's
TTF drop, and 25+ semantic component classes covering every primitive
catalogued in the design DNA spec.

#### Quickstart

```
cd projects/gs_reference

### First-run only (one-time setup):
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
.venv/bin/pip install Django
./dev/setup_fonts.sh ~/path/to/your/prism_repo    # copy 20 GS Sans TTFs

### Every run:
.venv/bin/python dev/run_gs_reference.py            # interactive menu (default)
.venv/bin/python dev/run_gs_reference.py up         # boot Django + open browser
.venv/bin/python dev/run_gs_reference.py info       # show config without booting
.venv/bin/python dev/run_gs_reference.py check      # smoke test imports + paths
.venv/bin/python dev/run_gs_reference.py shoot      # capture playwright screenshots
```

The mock listens on `http://127.0.0.1:8002/`. Override with
`up --port=N`. Append `?runtime=live` to any URL to flip the
display tokens onto the system-serif fallback (preview the
GS-Serif-equipped direction); default is `?runtime=prism` which
uses the GS Sans Condensed substitution per the spec §3.5.

#### URL grammar

```
/                                       home
/what-we-do/                            pillar landing (3 sub-pillars)
/insights/                              insights list (featured + 3 latest + 4 in-depth)
/insights/article/                      long-form article detail
/insights/podcast/                      short insights detail (audio variant)
/careers/                               careers landing
/careers/life/                          life-at-the-firm sub-page
/our-firm/purpose-and-values/           purpose / values centered page
```

#### Layout

```
projects/gs_reference/
├── README.md                             this file
│
├── gs_reference-payload/                 ← canonical (drag-and-drop ready)
│   └── ai_development/
│       └── mysite_gs/                    Django project (alt name to
│           │                              avoid clashing with PRISM's mysite/)
│           ├── manage.py
│           ├── mysite_gs/                project package
│           │   ├── settings.py           STATICFILES_DIRS wires fonts/
│           │   ├── urls.py
│           │   └── wsgi.py
│           ├── fonts/                    20 TTFs (gitignored; setup_fonts.sh)
│           └── gsapp/                    the single Django app
│               ├── apps.py / urls.py / views.py
│               ├── templatetags/
│               │   └── gs_extras.py      gs_placeholder SVG generator
│               ├── static/css/
│               │   ├── tokens.css        --gs-uitk-* design tokens
│               │   ├── fonts.css         20 @font-face blocks
│               │   └── components.css    25+ semantic class implementations
│               └── templates/gsapp/
│                   ├── base.html         nav + footer + briefings
│                   ├── home.html
│                   ├── what_we_do.html
│                   ├── insights_list.html
│                   ├── insights_article.html
│                   ├── insights_podcast.html
│                   ├── careers.html
│                   ├── careers_life.html
│                   └── purpose.html
│
└── dev/
    ├── specs/
    │   └── gs_design_dna.md              ← THE SSOT PRISM CONSUMES
    ├── output/screenshots/               playwright captures (run shoot)
    ├── run_gs_reference.py               interactive CLI (default) +
    │                                       argparse subcommands
    └── setup_fonts.sh                    copy 20 GS Sans TTFs from
                                          PRISM repo into fonts/
```

#### How PRISM consumes this

```
┌────────────────────────────────────────────────────────────────────┐
│ TIER 1 — markdown context                                          │
│   PRISM reads dev/specs/gs_design_dna.md inline in chat. ~1,000    │
│   lines but a single context-window load gives PRISM the entire    │
│   token namespace, type scale, component primitives, page archi-   │
│   types, and PRISM-side substitution recipes.                      │
├────────────────────────────────────────────────────────────────────┤
│ TIER 2 — CSS variables                                             │
│   PRISM can grep / read the three CSS files directly to verify     │
│   any token value or class implementation. Class names are seman-  │
│   tic (.gs-hero, .gs-card) not hashed (.gs-uitk-c-16fe2u1).        │
├────────────────────────────────────────────────────────────────────┤
│ TIER 3 — rendered screenshots                                      │
│   dev/output/screenshots/ holds full-page captures of every page   │
│   in both prism-runtime and live-runtime modes. PRISM's vision     │
│   layer (gemini-vision QC) can use these as the visual ground      │
│   truth when grading PRISM-side UI work.                           │
├────────────────────────────────────────────────────────────────────┤
│ TIER 4 — runnable verification                                     │
│   When the user wants to sanity-check a PRISM-side design proposal │
│   against the GS chrome, boot the mock locally and compare side-   │
│   by-side. The mock IS the ground truth.                           │
└────────────────────────────────────────────────────────────────────┘
```

#### What's intentionally NOT here

The mock is a visual-language reference, not a clone of gs.com:

- **No real GS marketing copy.** Every page uses lorem-style
  placeholder prose with PRISM-themed names (e.g. "Acme Industries
  IPO", "Macro Daily Brief"). Fictional author names everywhere.
- **No real photography.** All imagery is inline SVG placeholder
  rectangles tinted from the dataviz palette via `gs_placeholder`
  template tag.
- **No real CDN assets.** Fonts are loaded from local TTFs at
  `/static/fonts/` (the same drop PRISM has). The live site uses
  variable-axis woff2 from `cdn.gs.com` which is unreachable
  outside GS network.
- **No interactive JS chrome.** Mega-menu drawer, search modal,
  carousel auto-scroll are all noted in the spec §13 as deferred.
  The point is the static visual-design language, not behavior.

#### See also

| Need | File |
|------|------|
| The authoritative reference | `dev/specs/gs_design_dna.md` |
| PRISM portal's own design system (PRISM-voiced, not GS-replica) | `projects/frontend/dev/specs/design_system.md` |
| Echarts dashboard render (consumes GS Sans baked at compile) | `projects/echarts/echarts-payload/rendering.py` |
| Altair PNG render (font registration plan) | `projects/altair/dev/notes.md` §A |
| Repo orientation | `staging/README.md` (projects roster) |
| Staging-to-PRISM payload contract | `staging/README.md` §"Payload flow" |

#### Drag-and-drop contract

This project is a **reference asset**, not a payload that ships to
PRISM's MCP layer. PRISM consumes the TWO output artefacts directly
from the staging repo:

```
projects/gs_reference/dev/specs/gs_design_dna.md
   →  cited inline in PRISM context-extraction prompts
   →  optionally promoted to PRISM's
      ai_development/context/modules/static/gs_design_dna.md
      as a Tier-2 LLM context module if visual decisions become
      a recurring PRISM responsibility

projects/gs_reference/gs_reference-payload/ai_development/mysite_gs/
   →  staying in staging (the runnable mock is for the user +
      Cursor + PRISM-via-vision; PRISM doesn't run Django)
   →  if PRISM's frontend ever wants the actual mock pages
      adopted into the PRISM portal, the templates/CSS port
      directly with class-rename ("gs-*" → "prism-*") + content
      swap + remove the "Goldman Sachs" labels — the design
      system carries over verbatim
```

If the design language drifts (next GS rebrand, or PRISM's TTF drop
changes), re-extract from goldmansachs.com using the live HTML pull
in `~/.cursor/projects/.../agent-tools/` and refresh both the spec
date stamp + the CSS token values. The mock's CSS variable names
are stable; only their values move.

---

## 2. Design DNA spec

Path: `dev/specs/gs_design_dna.md`

### gs_design_dna.md

**Authoritative reference for PRISM** describing the Goldman Sachs
external-site visual design language as of 2026-05-14, captured from
goldmansachs.com live HTML+CSS extraction. Every color, font, type
scale, spacing unit, and component primitive in this document is
realized in a runnable Django mock under
`projects/gs_reference/gs_reference-payload/ai_development/mysite_gs/`.

PRISM should treat this file as the single source of truth when
designing or evaluating any UI surface that needs to read as
"GS-family of products." The Django mock is the verification layer —
PRISM can introspect its templates and CSS to see the patterns
described here in their actual rendered form.

_as of 2026-05-14; sources: goldmansachs.com live HTML extraction
(homepage, what-we-do, insights, careers, our-firm/purpose-and-values,
careers/life-at-goldman-sachs, insights article detail), verbatim
inline `<style>` block (~254 KB, 1,150 CSS variables in `--gs-uitk-*`
namespace, 26 `@font-face` blocks), the GS UI Toolkit token
vocabulary as exposed at runtime_

---

#### 0. Brand expression in one paragraph

GS reads as **quiet authority**. The visual chrome is restrained:
sharp containers (radius 0), no drop shadows, hairline dividers,
alpha-on-black text tiers instead of grayscale ramps. The signature
that lifts it from "generic enterprise SaaS" into "GS family" is the
typography pairing: **GS Serif Light at huge sizes** for hero
headlines and pull quotes, against **GS Sans** for everything else,
with **GS Sans Condensed Light** reserved for stat numerals.
Alongside that, a single **brand-blue palette** anchored on
`#7297C5` (action / sky-brand surfaces — matches live homepage
[`goldmansachs.com`](https://www.goldmansachs.com/) SSR rule
`subscribe-cta-root … background-color:#7297C5`) and `#092C61` (deep navy, used for dataviz and
hero accents) — never green/red except as semantic state. The result
is a page that looks more like a printed annual report than a typical
marketing site.

```
┌────────────────────────────────────────────────────────────────┐
│ FOUR PILLARS OF THE LANGUAGE                                   │
├────────────────────────────────────────────────────────────────┤
│  HERITAGE     │  Serif headline (GS Serif Light) reads as      │
│               │  established, considered, intellectual         │
│  DISCIPLINE   │  Sharp 0-radius containers, alpha-tier text,   │
│               │  no shadows, no decorative flourish            │
│  AUTHORITY    │  Sky-blue chrome, deep-navy accents, and       │
│               │  restraint on color; every accent earns its    │
│               │  place                                         │
│  FORWARD      │  Big-stat numerals (GS Sans Condensed Light    │
│               │  at 100-200 px) signal scale and ambition      │
└────────────────────────────────────────────────────────────────┘
```

---

#### 1. Token namespace

All design tokens in the live site live under `--gs-uitk-*`. The
mock mirrors that namespace exactly so PRISM (or any agent reading
this file plus the CSS) can grep the same names across both worlds.

```
--gs-uitk-color-{role}-{tier}          colors
--gs-uitk-text-{role}-{weight}-{bp}    typography (per-breakpoint)
--gs-uitk-space-{step}                 spacing (mock-side; live site
                                         uses raw px and a margin-
                                         based grid)
--gs-uitk-border-radius-{size}         radius (almost always 0)
```

Breakpoint suffix convention:

| Suffix | Range | Notes |
|--------|-------|-------|
| `-xs-screen` | < 768 px | mobile |
| `-md-screen` | 768 – 1199 px | tablet |
| `-lg-screen` | ≥ 1200 px | desktop default |

Tokens that don't change across breakpoints have no suffix (most
labels, all colors, spacing, radius).

---

#### 2. Color tokens

##### 2.1 Surfaces

| Token | Value | Use |
|-------|-------|-----|
| `--gs-uitk-color-surface-neutral-minimal` | `#FFFFFF` | Page background, card body |
| `--gs-uitk-color-surface-neutral-subtle` | `#F7F7FA` | Alternating section band, panel inset |
| `--gs-uitk-color-surface-neutral-regular` | `#DCDCE0` | Divider plate, disabled background |
| `--gs-uitk-color-surface-neutral-bold` | `#A2A4A6` | Strong neutral block |
| `--gs-uitk-color-surface-inverse-bold` | `#000000` | Dark surface (footer, hero overlay backing) |
| `--gs-uitk-color-surface-always-dark-regular` | `#121212` | Off-black hero backing |
| `--gs-uitk-color-surface-brand-bold` | `#7297C5` | Brand-tinted surface (rare; CTA chip) |
| `--gs-uitk-color-surface-brand-subtle` | `#F0EBE6` | Cream-tinted surface (warm brand bed) |
| `--gs-uitk-color-surface-backdrop` | `rgba(18,18,18,0.8)` | Modal scrim, image overlay |

##### 2.2 Text (alpha tiers on black/white)

| Token | Value | Tier |
|-------|-------|------|
| `--gs-uitk-color-text-neutral-bold` | `rgba(0,0,0,0.95)` | Primary |
| `--gs-uitk-color-text-neutral-regular` | `rgba(0,0,0,0.80)` | High emphasis |
| `--gs-uitk-color-text-neutral-subtle` | `rgba(0,0,0,0.70)` | Secondary |
| `--gs-uitk-color-text-neutral-minimal` | `rgba(0,0,0,0.60)` | Meta / caption |
| `--gs-uitk-color-text-inverse-bold` | `rgba(255,255,255,0.95)` | Primary on dark |
| `--gs-uitk-color-text-inverse-regular` | `rgba(255,255,255,0.80)` | Secondary on dark |
| `--gs-uitk-color-text-brand` | `#446EA6` | Link default |
| `--gs-uitk-color-text-functional-positive` | `#398025` | Positive copy |
| `--gs-uitk-color-text-functional-negative` | `#C2170A` | Negative copy |
| `--gs-uitk-color-text-functional-warning` | `#B2570D` | Warning copy |

**No grayscale ramp.** The live site has zero `#333` / `#666` /
`#999`. Hierarchy is alpha-on-`#000` so text on `#F7F7FA`
automatically reads slightly softer than the same tier on `#FFFFFF`.

##### 2.3 Borders

| Token | Value | Use |
|-------|-------|-----|
| `--gs-uitk-color-border-neutral-minimal` | `rgba(0,0,0,0.16)` | Hairline divider |
| `--gs-uitk-color-border-neutral-subtle` | `rgba(0,0,0,0.34)` | Card border |
| `--gs-uitk-color-border-neutral-regular` | `rgba(0,0,0,0.44)` | Default input border |
| `--gs-uitk-color-border-neutral-bold` | `rgba(0,0,0,0.95)` | Pressed / focused border |
| `--gs-uitk-color-border-brand` | `#7297C5` | Brand-themed border accent |

##### 2.4 Action / brand

| Token | Value | Use |
|-------|-------|-----|
| `--gs-uitk-color-action-brand` | `#7297C5` | Primary action chrome (button bg, focus ring, brand chip) |
| `--gs-uitk-color-action-neutral-bold` | `#000000` | Default button / dark CTA |
| `--gs-uitk-color-action-neutral-subtle` | `#F7F7FA` | Subtle button bed |
| `--gs-uitk-color-action-inverse` | `#FFFFFF` | Inverse text/icon on dark CTA |
| `--gs-uitk-color-action-functional-positive` | `#398025` | Positive action |
| `--gs-uitk-color-action-functional-negative` | `#C2170A` | Negative action |
| `--gs-uitk-color-action-functional-warning` | `#B2570D` | Warning action |
| `--gs-uitk-color-interaction-selected-bold` | `#7297C5` | Selected nav, active tab |
| `--gs-uitk-color-interaction-selected-subtle` | `rgba(114,151,197,0.16)` | Selected bed |

##### 2.5 Dataviz palette (categorical)

GS uses 20 categorical hues at index 010-200, with a 100-step ramp
from each. The mock lists the categorical **010 anchor swatches**
here for PRISM parity; finer **hue-010 ramps** (`010_070`–`010_100`)
also live in `tokens.css` for chart / accent parity. Full ramps for
every hue remain dataviz-only (chart engines own them). Listed here so
PRISM can map its echarts/altair palettes to "looks GS."

| Token | Value | Hue |
|-------|-------|-----|
| `--gs-uitk-color-dataviz-categorical010` | `#092C61` | Deep navy (signature) |
| `--gs-uitk-color-dataviz-categorical020` | `#7297C5` | Sky blue |
| `--gs-uitk-color-dataviz-categorical030` | `#A6428C` | Mauve |
| `--gs-uitk-color-dataviz-categorical040` | `#159788` | Teal |
| `--gs-uitk-color-dataviz-categorical050` | `#E0731A` | Burnt orange |
| `--gs-uitk-color-dataviz-categorical060` | `#7537AD` | Purple |
| `--gs-uitk-color-dataviz-categorical070` | `#B03030` | Brick red |
| `--gs-uitk-color-dataviz-categorical080` | `#BD8C00` | Mustard |
| `--gs-uitk-color-dataviz-categorical090` | `#69370E` | Brown |
| `--gs-uitk-color-dataviz-categorical100` | `#617A27` | Olive |

Hue `010` also carries UITK luminance stops injected on
[goldmansachs.com](https://www.goldmansachs.com/) SSR
(`010_070:#073985` through `010_100:#0B1624`; `010_080` aligns with
the table’s `#092C61` swatch). This mock defines those four tokens in
`tokens.css` for parity, but binds the sticky masthead to the live
homepage sky-blue surface **`#7297C5`** with dark navigation type.

Plus 10 more (110-200) for extended categorical breadth.
Divergent: positive `#398025` / negative `#C2170A` for
gain/loss; contrast variants `#092C61` (positive) /
`#E0731A` (negative) for chartjunk-light heatmaps.

##### 2.6 Image overlay convention

Hero / card images get a darkening overlay so light-on-image text
reads cleanly. Two recipes:

| Recipe | gradient |
|--------|----------|
| Hero (full-bleed) | `linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.8) 100%)` (bottom 50% darkens) |
| Card (16:9 with title overlay) | `linear-gradient(180deg, rgba(0,0,0,0.0) 30%, rgba(0,0,0,0.55) 100%)` |

---

#### 3. Typography

The signature pairing: **GS Serif** for hero / quote / large
editorial display, **GS Sans** for everything else, **GS Sans
Condensed** for stats. All three are variable-axis woff2 files on
the live site (served from `cdn.gs.com/fonts/`); PRISM has 20 static
TTF cuts of GS Sans + GS Sans Condensed but **no GS Serif TTF**
(see §3.5 for the substitution recipe).

##### 3.1 Families

| Family | Live source | PRISM availability | Role |
|--------|-------------|--------------------|------|
| GS Sans | `cdn.gs.com/fonts/gs-sans/v3/gs-sans-variable.woff2` (variable) | 10 static TTF cuts (250-700) at `ai_development/mysite/fonts/` | Body, UI, headings, labels |
| GS Sans Condensed | `gs-sans-condensed-variable.woff2` (variable) | 10 static TTF cuts (300-900) at `ai_development/mysite/fonts/` | Big stat numerals, tight labels |
| GS Serif | `cdn.gs.com/fonts/gs-serif/v3/gs-serif-variable.woff2` (variable) | **NOT IN PRISM TTF DROP** | Hero headline, pull quote, editorial display |
| Roboto Mono | system stack | system stack | Code, IDs, JSON |

> **WARN — `projects/frontend/dev/specs/design_system.md` 2026-05-02
> claims "GS Serif is NOT part of the gs.com pattern in this drop"
> and reassigns the display role to GS Sans Condensed 900 Black.
> Live extraction on 2026-05-14 confirms GS Serif IS the signature
> display face on gs.com itself — PRISM's TTF drop simply lacks it.
> The gap is real; the framing in the frontend spec needs an
> additive correction. See §3.5 below for the substitution recipe.**

##### 3.2 Type roles (verbatim from `--gs-uitk-text-*` tokens)

The live site exposes 60+ type tokens. The mock implements the
ones that actually appear on rendered pages (~25 tokens). Listed
here in declining size order. All `letter-spacing: 0` unless
noted; uppercase styles get `1px` per §3.4.

**Headlines (GS Serif Light 300, hero / quote)**

| Token | xs (<768) | md (768-1199) | lg (≥1200) |
|-------|-----------|---------------|------------|
| `--gs-uitk-text-headline01` | 50 / 50 | 80 / 80 | 140 / 140 |
| `--gs-uitk-text-headline02` | 44 / 44 | 60 / 60 | 100 / 100 |
| `--gs-uitk-text-headline03` | 36 / 36 | 50 / 50 | 80 / 80 |
| `--gs-uitk-text-headline04` | 30 / 30 | 40 / 40 | 60 / 60 |

`{font-size} / {line-height}` in px. Family is always GS Serif
weight 300 ("Light"), italics available.

**Quotes (GS Serif Light 300, narrower line-height)**

| Token | xs | md | lg |
|-------|----|----|----|
| `--gs-uitk-text-quote01` | 44 / 52 | 60 / 72 | 100 / 120 |
| `--gs-uitk-text-quote02` | 36 / 44 | 40 / 48 | 60 / 72 |
| `--gs-uitk-text-quote03` | 28 / 34 | 30 / 36 | 40 / 48 |
| `--gs-uitk-text-quote04` | 22 / 26 | 26 / 32 | 30 / 36 |

**Headings (GS Sans, sub-page / section titles)**

| Token | All breakpoints | Weight options |
|-------|-----------------|----------------|
| `--gs-uitk-text-heading01` | 40 / 48 | 400 (regular) / 500 (medium) |
| `--gs-uitk-text-heading02` | 32 / 40 | 400 / 500 |
| `--gs-uitk-text-heading03` | 24 / 32 | 400 / 500 |

**Subtitles (GS Sans, intro paragraphs)**

| Token | xs | md | lg | Weight |
|-------|----|----|----|--------|
| `--gs-uitk-text-subtitle01` | 24 / 32 | 28 / 38 | 36 / 42 | 400/500/700 |
| `--gs-uitk-text-subtitle02` | 22 / 28 | 24 / 32 | 28 / 36 | 400/500/700 |

**Body (GS Sans, prose)**

| Token | xs | md | lg | Weight |
|-------|----|----|----|--------|
| `--gs-uitk-text-body01` | 22 / 32 | 22 / 32 | 28 / 42 | 300/400/500/700 |
| `--gs-uitk-text-body02` | 16 / 24 | 18 / 28 | 20 / 30 | 300/400/500/700 |
| `--gs-uitk-text-body03` | 16 / 24 | 16 / 24 | 18 / 28 | 300/400/500/700 |
| `--gs-uitk-text-body04` | 14 / 20 | 14 / 20 | 16 / 24 | 300/400/500/700 |

**Labels (GS Sans, UI chrome)**

| Token | All bp | Weight |
|-------|--------|--------|
| `--gs-uitk-text-label01` | 20 / 24 | 400/500/700 |
| `--gs-uitk-text-label02` | 18 / 22 | 400/500/700 |
| `--gs-uitk-text-label03` | 16 / 20 | 400/500/700 |
| `--gs-uitk-text-label04` | 14 / 18 | 400/500/700 |
| `--gs-uitk-text-label05` | 12 / 16 | 400/500/700 |
| `--gs-uitk-text-label06` | 10 / 12 | 400/500/700 |

**Captions (GS Sans, fine print)**

| Token | All bp | Weight |
|-------|--------|--------|
| `--gs-uitk-text-caption01` | 14 / 18 | 400/500 |
| `--gs-uitk-text-caption02` | 12 / 16 | 400/500 |

**Overlines (GS Sans 400, ALWAYS UPPERCASE, `letter-spacing: 1px`)**

| Token | xs | md | lg |
|-------|----|----|----|
| `--gs-uitk-text-overline01` | 14 / 18 | 16 / 20 | 16 / 20 |
| `--gs-uitk-text-overline02` | 12 / 16 | 14 / 18 | 14 / 18 |
| `--gs-uitk-text-overline03` | 10 / 14 | 12 / 16 | 12 / 16 |

The overline is the **signature eyebrow** above almost every
section title and card. Compact uppercase tracking is what makes a
section read as "GS-styled."

**Stats (GS Sans Condensed Light 300)**

| Token | xs | md | lg | Use |
|-------|----|----|----|-----|
| `--gs-uitk-text-stat01` | 100 / 100 | 144 / 144 | 200 / 200 | Hero numeral (e.g. "$3T+", "46K+") |
| `--gs-uitk-text-stat02` | 72 / 72 | 88 / 88 | 100 / 100 | Featured stat |
| `--gs-uitk-text-stat03` | 44 / 44 | 46 / 46 | 46 / 46 | Inline stat (GS Sans 500, NOT condensed) |

**Code (Roboto Mono via system stack)**

| Token | All bp | Weight |
|-------|--------|--------|
| `--gs-uitk-text-code01` | 14 / 20 | 400 |
| `--gs-uitk-text-code02` | 12 / 16 | 500 |

##### 3.3 Letter-spacing rules

| Context | letter-spacing |
|---------|----------------|
| Default body, UI, headings, headlines, quotes | `0` |
| Overlines (uppercase eyebrows, badges, eyebrow labels) | `1px` |
| Small-caps subheads (rare) | `0.5px` |

The live site has 267 declarations of `letter-spacing: 0` and 15 of
`letter-spacing: 1px`. The 1-px tracking is reserved for uppercase.

##### 3.4 Weight semantics

| Family + weight | Reads as |
|-----------------|----------|
| GS Serif 300 | Heritage / authority / hero |
| GS Sans 300 | Light editorial body |
| GS Sans 400 | Default body |
| GS Sans 500 | Heading / link emphasis |
| GS Sans 700 | Strong button label / bold heading |
| GS Sans Condensed 300 | Hero stat numeral (signature thinness) |
| GS Sans Condensed 500 | Compact label / chip |
| GS Sans Condensed 700 | Compact emphasis |

GS rarely uses 600 (semibold). The gap from 500 to 700 is
intentional — sits halfway between "modern web" and "print
typography" sensibilities.

##### 3.5 PRISM-side substitution recipe (no GS Serif TTF)

When the runtime is PRISM (TTFs at `ai_development/mysite/fonts/`,
GS Serif absent), the headline/quote tokens substitute as follows:

| Live token | Live family | PRISM substitute | Rationale |
|------------|-------------|------------------|-----------|
| `--gs-uitk-text-headline01` (140 px) | GS Serif 300 | **GS Sans Condensed 300 Light** at same px | Closest "thin display" feel; preserves dramatic scale |
| `--gs-uitk-text-headline02` (100 px) | GS Serif 300 | **GS Sans Condensed 300 Light** | Same |
| `--gs-uitk-text-headline03` (80 px) | GS Serif 300 | **GS Sans Condensed 300 Light** | Same |
| `--gs-uitk-text-headline04` (60 px) | GS Serif 300 | **GS Sans 300 Light** at same px | Below Condensed-makes-sense threshold |
| `--gs-uitk-text-quote01-04` | GS Serif 300 | **GS Sans 300 Light italic** | Italics carry the editorial register |

The mock implements both: a `data-runtime="live"` mode (uses
system serif fallback `Times New Roman` for GS Serif role) and a
`data-runtime="prism"` mode (the substitution recipe above). Body
default is `prism` so the mock matches PRISM's actual render. Flip
via `<html data-runtime="live">` in `base.html` to preview the
live-site direction.

The substitution loses ~40% of the editorial weight that GS Serif
provides. The PRISM-runtime mode is honest about that — it doesn't
try to fake GS Serif with system fonts.

##### 3.6 Type-role decision tree

```
Need to set type? Walk this tree.

│
├─ Is it a HUGE editorial moment (hero headline / pull quote)?
│   ├─ live runtime  → headline01-04 (GS Serif 300)
│   └─ prism runtime → headline01-03 use GS Cond 300, hl04 GS Sans 300
│
├─ Is it a SECTION TITLE (h1 / h2 of an interior page)?
│   → heading01 (40px) / heading02 (32px) / heading03 (24px)
│     GS Sans 400 default, 500 if needs more presence
│
├─ Is it a STAT NUMERAL (big number on landing or careers)?
│   → stat01 (200px) / stat02 (100px)  GS Sans Condensed 300
│   → stat03 (46px) is GS Sans 500 (smaller inline metric)
│
├─ Is it BODY PROSE?
│   ├─ Lead paragraph just under heading → body01 / body02
│   ├─ Default body → body03 (18 px desktop)
│   └─ Meta / caption → body04 (16 px desktop)
│
├─ Is it a LABEL (button text, nav item, chip)?
│   → label02 (18px) / label03 (16px) / label04 (14px)
│
├─ Is it an EYEBROW (uppercase kicker above a title)?
│   → overline02 (14px) GS Sans 400 + letter-spacing 1px + uppercase
│
└─ Is it CODE / IDS / JSON?
    → code01 (14px) Roboto Mono via system stack
```

---

#### 4. Spacing

GS uses an 8-pt-derived grid. The mock canonicalises it:

| Token | px | Common use |
|-------|----|------------|
| `--gs-uitk-space-0` | 0 | reset |
| `--gs-uitk-space-1` | 4 | tight icon-gap |
| `--gs-uitk-space-2` | 8 | inline gap, inside compact chip |
| `--gs-uitk-space-3` | 12 | inside button, between chip and label |
| `--gs-uitk-space-4` | 16 | small block gap |
| `--gs-uitk-space-5` | 24 | card padding default |
| `--gs-uitk-space-6` | 32 | section internal gap |
| `--gs-uitk-space-7` | 48 | major block gap |
| `--gs-uitk-space-8` | 64 | section margin (vertical) |
| `--gs-uitk-space-9` | 96 | hero/section breathing room |
| `--gs-uitk-space-10` | 128 | top-of-page hero anchor |

Section vertical rhythm on the live site is **96-128 px between
major content blocks** on desktop. Tight by tech-marketing standards;
trade-off for the dense, multi-block landing pages.

---

#### 5. Layout grid

| Property | Value |
|----------|-------|
| Container max-width | `1440px` (`--gs-uitk-width-container`) |
| Inner gutter (l/r padding) | `24px` xs, `48px` md, `64px` lg |
| Column system | 12-col implicit; most layouts hand-rolled flex/grid, not framework-grid-classes |
| Default content max-width (prose) | `816px` (article body) |
| Nav max-width | `1440px` matching container |

Responsive breakpoints (matching the type-token suffix):

| Bp | min-width | Layout treatment |
|----|-----------|------------------|
| xs | 0 | single column, hamburger nav, stacked cards |
| md | 768 px | 2-col grids, expanded nav with hamburger right of menu items |
| lg | 1200 px | 3-4 col grids, full nav, hero at full size |

---

#### 6. Border-radius

Always `0`. The live site uses `border-radius: 2px` only on
non-page-level interactive controls (some form inputs, toggle
switches). Cards, panels, hero blocks, image crops — all sharp.

| Token | px | Use |
|-------|----|----|
| `--gs-uitk-border-radius-none` | 0 | Cards, panels, sections, image crops, buttons |
| `--gs-uitk-border-radius-sm` | 2 | Form inputs (rare; mostly default 0) |
| `--gs-uitk-border-radius-pill` | 9999 | Toggle switches only |

The 0-radius IS the brand. Any rounded corner is a design bug.

---

#### 7. Elevation

Flat. Zero `box-shadow` on surfaces in the live extraction. One
shadow recipe for overlays only:

| Token | Value | Use |
|-------|-------|-----|
| `--gs-uitk-shadow-overlay` | `0 8px 32px rgba(0,0,0,0.16)` | Modal, dropdown menu, share-sheet |

Hierarchy comes from alpha-tier text + hairline divider + subtle
hover overlay (`rgba(0,0,0,0.04)` on light surfaces).

---

#### 8. Component primitives

The atomic pieces every page composes from. Each gets a CSS class
in `gsapp/static/css/components.css` mirroring the names below.

##### 8.1 Top navigation bar

```
┌────────────────────────────────────────────────────────────────┐
│ [Logo: Goldman Sachs] [What We Do] [Insights]  ...  [≡]  [Login]│   sticky, sky blue
├────────────────────────────────────────────────────────────────┤
│                                                                │   1px hairline (inverse) below
```

- **Position**: `sticky; top: 0; z-index: 100`
- **Background**: `--gs-uitk-color-surface-brand-bold` (`#7297C5`,
  the live homepage sky-blue top-ribbon chrome)
- **Bottom border**: `1px solid --gs-uitk-color-border-neutral-minimal`
- **Height**: `72px` desktop, `56px` mobile
- **Logo wordmark**: `--gs-uitk-color-text-neutral-bold`; **logo mark**
  keeps the inverse square treatment (solid fill + condensed GS)
- **Menu items**: `label03-medium` (GS Sans 500 16px), spaced by
  `--gs-uitk-space-5` (24px); default link color
  `--gs-uitk-color-text-neutral-regular`, hover/active bold neutral;
  selected item uses a `3px` neutral-bold underline so it stays visible
  on the sky-blue bed
- **Right cluster**: hamburger + search icons use `--gs-uitk-color-text-neutral-bold`;
  hover fills `--gs-uitk-color-interaction-hover-on-light`. \"Client Login\"
  uses `.gs-button--ghost-dark` (black hairline border on the sky-blue bed)
- **Hover**: menu item color ramps to `--gs-uitk-color-text-neutral-bold`
  (underline is optional; the CSS mock uses color only)

The "always-on hamburger" is GS-specific. Most marketing sites
collapse the hamburger at narrow widths; gs.com keeps it on
desktop because the mega-menu has 4-level nav not expressible in
a top bar.

##### 8.2 Eyebrow (`.gs-overline`)

Uppercase kicker above every section title and most cards. The
single most repeated chrome element on the site.

```html
<span class="gs-overline">What We Do</span>
```

```css
.gs-overline {
    font: var(--gs-uitk-text-overline02-lg-screen-font);
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--gs-uitk-color-text-neutral-minimal);
}
```

##### 8.3 Section heading composite (`.gs-section-heading`)

Eyebrow + headline pair that opens almost every section.

```html
<header class="gs-section-heading">
    <span class="gs-overline">Our Thinking</span>
    <h2 class="gs-headline gs-headline--03">
        Insights on Financial Markets and the Global Economy
    </h2>
</header>
```

Spacing: eyebrow gets `margin-bottom: var(--gs-uitk-space-3)` (12px);
heading composite gets `margin-bottom: var(--gs-uitk-space-7)` (48px)
to separate from the section content below.

##### 8.4 Hero (`.gs-hero`) — full-bleed image with bottom-anchored text

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│            (full-bleed image, ~70-80vh tall)                 │
│                                                              │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐    │
│  │ EYEBROW (white, uppercase)                           │    │
│  │ Huge Serif Headline                                  │    │   bottom-left text block
│  │ Light italic subtitle below                          │    │   inside max-width container
│  │                                                      │    │
│  │  [Read Article →]                                    │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

- **Aspect**: 16:9 desktop, 4:5 mobile, min-height 480px
- **Image**: `object-fit: cover; object-position: center`
- **Overlay gradient**: `linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.8) 100%)`
- **Text block**: positioned bottom-left, padded `--gs-uitk-space-9` from edges, max-width `680px`
- **Eyebrow**: `--gs-uitk-text-overline01` white
- **Headline**: `--gs-uitk-text-headline01` (140px lg) white
  - PRISM-runtime: GS Sans Condensed 300 Light at same size
- **CTA**: `.gs-button--ghost-light` (transparent, white border)

##### 8.5 Card / tile (`.gs-card`)

Generic 16:9-image-on-top card with eyebrow + title + description
+ link below.

```
┌─────────────────────────────────────┐
│                                     │
│   16:9 image (cropped, no radius)   │
│                                     │
├─────────────────────────────────────┤
│ EYEBROW                             │
│ Card Title (GS Sans 500 24px)       │
│                                     │
│ Card description body, two or       │
│ three lines of GS Sans regular.     │
│                                     │
│ Read More →                         │
└─────────────────────────────────────┘
```

- **Border**: `1px solid --gs-uitk-color-border-neutral-minimal`
- **Radius**: `0`
- **Padding**: `0` on the image side, `--gs-uitk-space-5` (24px)
  on the body
- **Title**: `--gs-uitk-text-heading03-medium` (24px GS Sans 500)
- **Description**: `--gs-uitk-text-body04` (14-16px)
- **Link**: `--gs-uitk-text-label03-medium` brand color with
  trailing `→` glyph
- **Hover**: image gets `transform: scale(1.04)` over `400ms ease`,
  card body unchanged

Variant `.gs-card--overlay`: text overlaid ON the image (used in
deal-spotlight pattern). Adds the card overlay gradient (§2.6) and
positions text block bottom-left.

##### 8.6 Stat module (`.gs-stat`)

```
   46K+
   ─────
   Goldman Sachs People Around the World
```

- **Numeral**: `--gs-uitk-text-stat02` (100 px lg) GS Sans
  Condensed Light 300
- **Caption**: `--gs-uitk-text-body04` regular, max-width `280px`
- **Top divider**: `1px solid --gs-uitk-color-border-neutral-minimal`
  spanning full width above the numeral
- **Spacing**: `space-3` between numeral and caption

Stats appear in 3-up rows in a `.gs-stat-row` container with
`display: grid; grid-template-columns: repeat(3, 1fr); gap: space-7`.

##### 8.7 Tab strip (`.gs-tabs`)

The "Stay Informed | The Firm in Action" pattern at the top of the
content body, just under the hero.

```
┌───────────────────────────────────────────────────────────┐
│ STAY INFORMED      THE FIRM IN ACTION                     │
│ ───────────                                               │   3px black underline on selected (readable on sky-blue bed)
└───────────────────────────────────────────────────────────┘
```

- **Container**: full-width `--gs-uitk-color-surface-brand-bold` (`#7297C5`),
  matching the Subscribe to Briefings ribbon; bottom border uses
  `border-inverse-minimal` for separation on the blue bed
- **Items**: GS Sans 500 18px, uppercase NOT applied (label03-medium),
  `padding: space-4 space-5`
- **Selected indicator**: `3px solid --gs-uitk-color-action-neutral-bold`
  bottom-border on the active item, drawn 1px below the text
- **Inactive**: `--gs-uitk-color-text-neutral-subtle`; hover gets
  `text-neutral-bold`

##### 8.8 Briefings subscribe module (`.gs-briefings`)

Recurs at the bottom of EVERY page (layout-level component, not
page-level).

```
┌───────────────────────────────────────────────────────────────┐
│  Subscribe to Briefings                                       │
│  Our signature newsletter for insights and analysis           │
│  from across the firm                                         │
│                                                               │
│  ┌────────────────────────────────┐ ┌──────────┐              │
│  │ Email                          │ │ Submit  →│              │
│  └────────────────────────────────┘ └──────────┘              │
│                                                               │
│  By submitting this information, you agree...                 │
└───────────────────────────────────────────────────────────────┘
```

- **Background**: `--gs-uitk-color-surface-brand-bold` (`#7297C5`,
  the GS sky blue — same hue as `--gs-uitk-color-action-brand`).
  Verified verbatim from the live `subscribe-cta-root` rule:
  `background-color:#7297C5`. Text on this background is dark
  (`rgba(0,0,0,0.95)`) — the live site keeps the same text-tier
  ramp despite the colored bed.
- **Heading**: live site uses `400 60px/60px GS Sans Condensed`
  on lg (50px md, 36px xs). Distinctive — the only place GS Sans
  Condensed Regular 400 (not 300 Light) appears at this size.
- **Body**: `--gs-uitk-text-body02-regular`
- **Input**: full-width sans-radius `1px solid border-neutral-regular`,
  height 56px, white background (kept on the sky-blue bed),
  `--gs-uitk-text-body03-regular`
- **Submit button**: black bg, white text, height 56px (matches input),
  trailing `→`
- **Vertical padding**: live uses `144px` lg, `112px` md, `80px` xs
  (a deliberately tall ribbon — `min-height: 544px` on lg)

##### 8.9 Footer (`.gs-footer`)

Multi-column link list at the very bottom.

- **Background**: `--gs-uitk-color-surface-inverse-bold` (`#000`)
- **Text**: `--gs-uitk-color-text-inverse-regular`
- **Link**: `--gs-uitk-text-label04-regular` (14px GS Sans 400)
- **Layout**: 5 columns desktop, 2-col mobile, gap `--gs-uitk-space-7`
- **Bottom bar**: copyright + legal links + locale toggle, all
  `--gs-uitk-text-caption02-regular`

##### 8.10 Buttons

Three primary variants:

```
.gs-button--primary       black bg, white text, 0 radius, GS Sans 500 14px
.gs-button--ghost-dark    transparent bg, dark border + dark text
.gs-button--ghost-light   transparent bg, white border + white text (on hero)
```

Common: `padding: space-3 space-5`, `min-height: 48px`, no
shadow, `transition: background-color 200ms ease`. Hover deepens
background (per `--button-root :hover` overlays in the live CSS:
`rgba(0,0,0,0.04)` on light variants, `rgba(245,245,245,1)` on dark
variants).

**No icon-only buttons** beyond hamburger and search. CTAs are
text-first; arrow `→` is the universal "read more" affordance.

##### 8.11 Article body (`.gs-article-body`)

The long-form prose container used in `/insights/<article>/`.

- **Max-width**: `816px` (matches GS's article width)
- **Padding**: `--gs-uitk-space-7` horizontal on lg, `space-5` xs
- **Type**: `--gs-uitk-text-body02-regular` (20-22px)
- **Heading hierarchy inside article**:
  - h1 (article title): `--gs-uitk-text-headline03` (80px lg
    GS Serif Light, OR GS Cond 300 prism-mode)
  - h2 (section heading): `--gs-uitk-text-heading01-medium` (40px GS Sans 500)
  - h3 (subsection): `--gs-uitk-text-heading03-medium` (24px GS Sans 500)
- **Paragraph spacing**: `margin-bottom: var(--gs-uitk-space-5)`
- **Pull quote** (`.gs-pull-quote`): `--gs-uitk-text-quote03`
  (40px lg GS Serif Light), italic, padded `space-7` vertical
- **Footnote / source note**: `--gs-uitk-text-caption02-regular`
  with `--gs-uitk-color-text-neutral-minimal`, separated by hairline
- **Numbered list emphasis** (signature pattern in articles):
  large GS Sans Condensed 300 numeral on left, body text on right
  ```
  1   The economic useful life of AI silicon, where small shifts
       in replacement cadence move cumulative spend by hundreds
       of billions
  ```
  Numeral is `--gs-uitk-text-stat02` (100px), text is `--gs-uitk-text-body02`.

##### 8.12 Byline / metadata strip (`.gs-byline`)

Below an article title:

```
By Author Name, Title
Author Name 2, Title 2
                                                  May 1, 2026   [Share]
```

- **Author rows**: `--gs-uitk-text-body04-medium`
- **Date + share**: right-aligned, `--gs-uitk-text-label04-regular`
- **Bottom border**: `1px solid border-neutral-minimal` separating
  from article body, `padding-bottom: space-5`

##### 8.13 Share button (`.gs-share`)

Universal pattern: text "Share" + chevron-down or share-icon glyph,
positioned top-right of every non-home page just under the hero.

##### 8.14 Footnote / source / disclosure block (`.gs-footnote`)

End-of-article block. All articles end with one. Format:

```
1 Dealogic. Cumulative announced M&A deal volume...
2 Dealogic. Cumulative...
3 Publicly disclosed Equities revenues for 2024...
```

- **Type**: `--gs-uitk-text-caption02-regular`
- **Color**: `--gs-uitk-color-text-neutral-minimal`
- **Numeral**: superscript-aligned, weight 500
- **Border-top**: `1px solid border-neutral-minimal`, `space-5`
  vertical padding

##### 8.15 Two-up image+content section (`.gs-two-up`)

The recurring "image on left, eyebrow+title+body+CTA on right"
pattern (alternates left/right between sections).

```
┌────────────────────┬────────────────────┐
│                    │ EYEBROW            │
│                    │                    │
│   image (square    │ Section Title      │
│   or 4:5 portrait) │                    │
│                    │ Body paragraph     │
│                    │ describing the     │
│                    │ thing.             │
│                    │                    │
│                    │ [Read More →]      │
└────────────────────┴────────────────────┘
```

- **Grid**: `grid-template-columns: 1fr 1fr; gap: space-7`
- **Modifier `.gs-two-up--reverse`**: image right, content left
- **Image aspect**: 1:1 default, 4:5 if portrait orientation
- **Vertical alignment**: content vertically centered

---

#### 9. Page archetypes

Each archetype is a composition of primitives. The mock implements
all 6.

##### 9.1 Home (`/`)

```
┌────────────────────────────────────────────┐
│              top nav (sky-blue chrome)         │
├────────────────────────────────────────────┤
│                                            │
│              FULL-BLEED HERO               │   §8.4
│              (featured topic)              │
│                                            │
├────────────────────────────────────────────┤
│  STAY INFORMED   THE FIRM IN ACTION        │   §8.7 tab strip
├────────────────────────────────────────────┤
│  Card  Card  Card                          │   §8.5 deal spotlights
│                                            │
├────────────────────────────────────────────┤
│  EYEBROW                                   │   §8.3 section head
│  What We Do — Delivering for Our Clients   │
│                                            │
│  4-up cards (image+title+description+link) │   §8.5 ×4
├────────────────────────────────────────────┤
│  Two-up image+text (Insights)              │   §8.15
├────────────────────────────────────────────┤
│  Two-up image+text (Careers)               │   §8.15
├────────────────────────────────────────────┤
│  STAT ROW                                  │   §8.6 ×3
│  46K+   1M+   95%+                         │
│  caption caption caption                   │
├────────────────────────────────────────────┤
│  Two-up image+text (Our Firm)              │   §8.15
├────────────────────────────────────────────┤
│  BRIEFINGS subscribe                       │   §8.8
├────────────────────────────────────────────┤
│  FOOTER                                    │   §8.9
└────────────────────────────────────────────┘
```

##### 9.2 Pillar landing (`/what-we-do/`, `/our-firm/`)

```
┌────────────────────────────────────────────┐
│  EYEBROW (page-level: WHAT WE DO)          │
│  Page Title (GS Serif headline02 100px)    │
│  Lead paragraph (subtitle01)               │
│  [Share] right-aligned                     │
├────────────────────────────────────────────┤
│  Tab strip: Sub-pillar 1 | Sub-pillar 2 |..│   §8.7 (multi-pillar)
├────────────────────────────────────────────┤
│  Sub-pillar 1                              │
│    EYEBROW + heading02                     │
│    Lead body paragraph                     │
│    Card list (link cards, no image)        │
├────────────────────────────────────────────┤
│  Sub-pillar 2                              │
│  ...                                       │
├────────────────────────────────────────────┤
│  BRIEFINGS                                 │
│  FOOTER                                    │
└────────────────────────────────────────────┘
```

##### 9.3 Insights list (`/insights/`)

```
┌────────────────────────────────────────────┐
│  EYEBROW (IN FOCUS: ARTIFICIAL INTELLIGENCE)│
│  Featured article hero (full-bleed image,  │
│  headline overlay)                         │
├────────────────────────────────────────────┤
│  EYEBROW: THE LATEST                       │
│  3-up cards (article title + meta +        │
│  format chip [Article|Podcast|Video])      │
├────────────────────────────────────────────┤
│  IN FOCUS section (carousel-feel grid)     │
├────────────────────────────────────────────┤
│  All insights (paginated grid)             │
├────────────────────────────────────────────┤
│  BRIEFINGS                                 │
│  FOOTER                                    │
└────────────────────────────────────────────┘
```

##### 9.4 Article detail (`/insights/<slug>/`)

```
┌────────────────────────────────────────────┐
│  Full-bleed hero image (varies)            │
├────────────────────────────────────────────┤
│  Eyebrow (TOPIC)                           │
│  Article Headline (GS Serif headline03 80px)│
│  Date · Read time          [Share]         │   §8.12 byline
├────────────────────────────────────────────┤
│  Author Name 1, Title                      │
│  Author Name 2, Title                      │
├────────────────────────────────────────────┤
│  Subtitle (intro one-liner)                │
├────────────────────────────────────────────┤
│  Executive Summary heading (h2)            │
│  Body prose                                │
│                                            │
│  Numbered list with big numerals           │   §8.11 special list
│  1   Body of first point...                │
│  2   Body of second...                     │
├────────────────────────────────────────────┤
│  ## Section heading                        │
│  Body prose                                │
│                                            │
│  Pull quote ("the headline within the      │   §8.11 pull quote
│   article")                                │
│                                            │
│  Body prose continued.                     │
├────────────────────────────────────────────┤
│  Source notes / footnotes                  │   §8.14
├────────────────────────────────────────────┤
│  Related articles (3-up cards)             │
├────────────────────────────────────────────┤
│  BRIEFINGS                                 │
│  FOOTER                                    │
└────────────────────────────────────────────┘
```

##### 9.5 Insights short detail (`/insights/<slug-podcast>/`)

Variant of 9.4 for podcast/video items: shorter body, no exec
summary, audio/video player block instead of body prose, host
profile card on the right rail.

##### 9.6 Careers landing (`/careers/`)

```
┌────────────────────────────────────────────┐
│  Full-bleed hero ("Choose Excellence")     │
├────────────────────────────────────────────┤
│  Tab strip: Students | Open Roles          │   §8.7
├────────────────────────────────────────────┤
│  EYEBROW: THE GS CULTURE                   │
│  Two-up image+text (Voices of the Firm)    │
├────────────────────────────────────────────┤
│  Featured roles (4-up card grid)           │
├────────────────────────────────────────────┤
│  Path tiles: Match Your Skills | Student   │
│  Programs | Professional Programs | Feel   │
│  Prepared (4-up smaller text-only cards)   │
├────────────────────────────────────────────┤
│  Quote block ("There are many chapters in  │
│  a career. There is only one Goldman       │
│  Sachs.") in GS Serif quote02              │
├────────────────────────────────────────────┤
│  Two-up: Who We Are                        │
│  Two-up: The Business of Impact            │
│  Two-up: Culture of Belonging              │
├────────────────────────────────────────────┤
│  Our Firm — link cards row (Risk, Asset    │
│  Management, Operations, Engineering)      │
├────────────────────────────────────────────┤
│  BRIEFINGS                                 │
│  FOOTER                                    │
└────────────────────────────────────────────┘
```

##### 9.7 Purpose / values page (`/our-firm/purpose-and-values/`)

```
┌────────────────────────────────────────────┐
│  EYEBROW (OUR FIRM)                        │
│  Centered headline ("Our Purpose")         │
│  Lead paragraph centered                   │
├────────────────────────────────────────────┤
│  EYEBROW: OUR VALUES                       │
│  4-up value cards (no image, just title +  │
│  description) — Partnership, Client        │
│  Service, Integrity, Excellence            │
├────────────────────────────────────────────┤
│  Two-up: Business Principles               │
├────────────────────────────────────────────┤
│  Compact link list (Code of Business       │
│  Ethics, etc.)                             │
├────────────────────────────────────────────┤
│  Cross-link cards (Discover Our History,   │
│  Meet Our People)                          │
├────────────────────────────────────────────┤
│  BRIEFINGS                                 │
│  FOOTER                                    │
└────────────────────────────────────────────┘
```

---

#### 10. Imagery rules

##### 10.1 Aspect ratios

| Use | Aspect | Notes |
|-----|--------|-------|
| Hero (full-bleed) | 16:9 desktop, 4:5 mobile | 480px min-height |
| Card image | 16:9 | The signature aspect; ALL article cards use it |
| Two-up section image | 1:1 (square) or 4:5 (portrait) | Choice depends on subject |
| Profile / author photo | 1:1 | Square, full-bleed in card; circular only in tight chrome |

##### 10.2 Crop discipline

- Photos are tight crops on subject (a face fills the frame; a
  building is shot edge-to-edge). No "interesting empty space."
- No image stylization beyond darkening overlay (§2.6). No filters,
  no duotone, no halftone. The photo's own light/composition is
  the only visual treatment.
- No rounded crops anywhere except inside specific chips/avatars
  (and even those are usually square in the live extraction).

##### 10.3 Placeholder convention (mock-only)

The Django mock uses **stock photography from Picsum** (Unsplash-
sourced, free for commercial use, no API key) in lieu of real GS
imagery. Each placeholder is requested via the `gs_placeholder`
template tag:

```django
{% gs_placeholder tint="navy" aspect="16x9" label=card.title %}
```

- `tint` — semantic color hint (kept for back-compat; folded into
  the seed but does not constrain the rendered photo)
- `aspect` — `16x9` / `21x9` / `4x5` / `1x1`; maps to a target
  pixel size and Picsum scales the photo accordingly
- `label` — content hint (usually the card / hero title); folded
  into the seed so two placements with the same tint but different
  titles get distinct photos
- `seed` — optional explicit seed override

The tag emits an `<img>` pointing at
`https://picsum.photos/seed/<sha1-of-tint-aspect-label>/<w>/<h>`.
Deterministic: the same (tint, aspect, label) triple always yields
the same photo, so screenshot diffs are stable across runs.

The mock requires internet access on first paint to fetch each
unique photo; the browser caches subsequent loads. Tints still
matter elsewhere (for the colored card top-borders, eyebrow
chips, dataviz palette) — they just no longer paint solid blocks
where photos would be.

---

#### 11. Motion / interaction

Sparse. The live site has very little motion.

| Element | Interaction |
|---------|-------------|
| Card hover | Image scales 1.04 over 400ms ease; body unchanged |
| Link hover | `text-decoration: underline` appears |
| Button hover | Background deepens (overlay rgba(0,0,0,0.04) on light) |
| Tab strip selected | 3px brand-blue underline animates in over 200ms |
| Hamburger open | Mega-menu drawer slides down 300ms ease-in-out |
| Form input focus | `border-color: --gs-uitk-color-border-neutral-bold`; no shadow |

No parallax, no scroll-triggered animations, no marquee, no
staggered reveal of cards. The restraint IS the brand.

---

#### 12. PRISM consumption notes

How a PRISM agent should use this file.

##### 12.1 Layered reading order

```
Need to design or evaluate a GS-styled UI surface? Read in this
order:

  1. §0 (Brand expression)        — calibrate the voice
  2. §3.6 (Type-role decision tree) — pick the right type token
  3. §8 (Component primitives)    — find the relevant primitive
  4. §9 (Page archetypes)          — find the matching layout
  5. §3.5 (PRISM substitution)    — apply the GS-Serif workaround
  6. The Django mock CSS / templates — verify rendered form
```

##### 12.2 What this file is NOT

- **Not a CSS dump.** Tokens are listed for vocabulary; the actual
  CSS implementation lives in the mock at
  `gs_reference-payload/ai_development/mysite_gs/gsapp/static/css/`.
- **Not a copy of gs.com.** The mock uses lorem-ipsum-style copy
  with PRISM-themed names ("Macro Daily Brief", "PRISM Insights")
  and placeholder SVG imagery. Do not lift content from the mock
  as if it were GS marketing material.
- **Not a frozen snapshot.** GS may iterate the visual language
  again (the 2024 rebrand was significant; another rebrand could
  shift the typography or color emphasis). Re-extract before
  trusting any specific token value if the date stamp at the top
  of this file is more than 6 months stale.

##### 12.3 Mapping PRISM voice over GS chrome

PRISM is internal data tooling, not external marketing. When
PRISM-side designs adopt the GS chrome described here, two
adjustments compress the marketing register into a working tool:

1. **Reduce hero scale.** PRISM landing pages should use
   `headline03` (80px) or `heading01` (40px) — never `headline01`
   (140px). The big serif moment belongs to a marketing site;
   PRISM's landing should feel like a working dashboard.
2. **Remove the briefings module.** PRISM has no newsletter; the
   bottom-of-page real estate goes to whatever PRISM-specific
   system message belongs there (refresh status, observatory
   attribution, etc.).
3. **Keep everything else.** Eyebrow + title composite, sharp
   containers, alpha-tier text, GS Sans body, dataviz palette, the
   8-pt grid — all of it ports verbatim.

##### 12.4 Cross-references

| Need | File |
|------|------|
| Existing PRISM portal design system (PRISM-voiced, not GS-replica) | `projects/frontend/dev/specs/design_system.md` |
| PRISM portal Django templates (the actual surface this informs) | `projects/frontend/frontend-payload/ai_development/mysite/news/templates/news/` |
| PRISM portal CSS | `projects/frontend/frontend-payload/ai_development/mysite/news/static/css/{tokens,fonts,base}.css` |
| Echarts dashboard render (consumes GS Sans baked at compile) | `projects/echarts/echarts-payload/rendering.py` |
| Altair PNG render (font registration plan) | `projects/altair/dev/notes.md` §A |
| Live mock for visual verification | `gs_reference-payload/ai_development/mysite_gs/` |

##### 12.5 Freshness signals to surface

If the live extraction date stamp here drifts past 6 months OR if
goldmansachs.com visibly rebrands, flag the staleness to the user
and offer to re-extract. The mock's CSS variables map 1:1 to the
named tokens above; a re-extraction is a token-value refresh, not
a structural rewrite.

---

#### 13. Gaps / deferred

Known incompleteness, in priority order.

1. **GS Serif TTF.** PRISM's font drop has 20 GS Sans + GS Sans
   Condensed cuts but no GS Serif. The substitution recipe in §3.5
   compresses 40% of the brand register. Picking up GS Serif (TTF
   from GS internal asset library, or via the variable woff2 if
   PRISM gets CDN access) would close the gap. This is a separate
   asset request, not a design decision.

2. **Mega-menu drawer.** The mock implements a static expanded
   nav for desktop and a collapsed hamburger for mobile, but does
   NOT replicate the live site's full mega-menu drawer (4-level
   nav slider). Adding it requires JS and is out of scope for a
   "lightweight visual reference."

3. **Search modal.** Live site has a full-bleed search modal
   triggered by the magnifier icon. Mock has the icon but the
   modal is not implemented.

4. **Locale toggle.** Live footer has a Worldwide / language picker.
   Mock has the static link but no actual locale switching.

5. **Carousel patterns.** Live "In Focus" sections use auto-
   scrolling carousels. Mock renders them as static 4-up grids.

6. **Real photography.** Mock uses placeholder SVG rectangles. If
   PRISM's reference need shifts to "match crop discipline of GS
   real photos," that's a follow-up that requires sourced imagery
   (Unsplash / commissioned).

7. **Dataviz palette ramps.** Mock surfaces only the 010 swatch
   per categorical hue (10 swatches). Full 100-step ramps for each
   of 20 hues = 2000+ tokens; deferred to whoever wires PRISM's
   chart engines to consume this palette.

8. **Dark-mode pair.** Live site is light-only. The mock follows.
   If a future PRISM dark mode wants the GS-styled-dark variant,
   it's a separate spec.

9. **Cross-reference into `projects/frontend/dev/specs/design_system.md`.**
   That spec is PRISM-voiced + 2026-05-02 dated; several of its
   typography claims contradict the live extraction (see WARN in
   §3.1). The corrections are additive — the existing spec stays
   correct as a description of what PRISM currently renders;
   this file describes what gs.com currently renders. Reconciling
   the two (e.g. a "PRISM-voiced GS-faithful" alignment pass) is
   a follow-up endeavor.

---

#### 14. How to use the runnable mock

The mock at `gs_reference-payload/ai_development/mysite_gs/` is
a standalone Django project. From the project root:

```
cd projects/gs_reference

### First-run only:
/opt/homebrew/opt/python@3.11/bin/python3.11 -m venv .venv
.venv/bin/pip install Django
./dev/setup_fonts.sh ~/path/to/your/prism_repo   # copies GS TTFs

### Every run:
.venv/bin/python dev/run_gs_reference.py         # interactive menu (default)
.venv/bin/python dev/run_gs_reference.py up      # boot Django + open browser
.venv/bin/python dev/run_gs_reference.py info    # config without booting
```

The mock listens on `http://127.0.0.1:8002/`. URL grammar:

```
/                                       home
/what-we-do/                            pillar landing
/insights/                              insights list
/insights/article/                      long-form article detail
/insights/podcast/                      short insights detail
/careers/                               careers landing
/careers/life/                          life-at-GS sub-page
/our-firm/purpose-and-values/           purpose / values page
```

Every page renders the components described in §8 and follows the
archetype layouts in §9. Use the mock to verify that any GS-styled
UI work matches the rendered reality before promoting to PRISM.

---

## 3. CSS — tokens.css

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/static/css/tokens.css`

```css
/* ═══════════════════════════════════════════════════════════════════════
   tokens.css — gs-reference design system tokens

   Mirrors the --gs-uitk-* namespace extracted from goldmansachs.com. The
   public homepage (https://www.goldmansachs.com/, Next.js SSR) injects the
   subscribe / Briefings ribbon as `subscribe-cta-root` with verbatim
   `background-color:#7297C5` and `color:rgba(0,0,0,.95)` alongside
   breakpoint padding keyed to those values; that hex is authoritative for
   “GS sky blue” chrome in this repo. See gs_design_dna.md for prose.

   Token names stay byte-aligned with UITK conventions so searches line up
   with live markup.
   ═══════════════════════════════════════════════════════════════════════ */

:root {
    /* ───── Colors: surfaces ──────────────────────────────────────── */
    --gs-uitk-color-surface-neutral-minimal: #FFFFFF;
    --gs-uitk-color-surface-neutral-subtle: #F7F7FA;
    --gs-uitk-color-surface-neutral-regular: #DCDCE0;
    --gs-uitk-color-surface-neutral-bold: #A2A4A6;
    --gs-uitk-color-surface-inverse-bold: #000000;
    --gs-uitk-color-surface-always-dark-regular: #121212;
    --gs-uitk-color-surface-brand-bold: #7297C5;
    --gs-uitk-color-surface-brand-subtle: #F0EBE6;
    --gs-uitk-color-surface-backdrop: rgba(18, 18, 18, 0.8);

    /* ───── Colors: text (alpha tiers on black/white) ─────────────── */
    --gs-uitk-color-text-neutral-bold: rgba(0, 0, 0, 0.95);
    --gs-uitk-color-text-neutral-regular: rgba(0, 0, 0, 0.80);
    --gs-uitk-color-text-neutral-subtle: rgba(0, 0, 0, 0.70);
    --gs-uitk-color-text-neutral-minimal: rgba(0, 0, 0, 0.60);
    --gs-uitk-color-text-inverse-bold: rgba(255, 255, 255, 0.95);
    --gs-uitk-color-text-inverse-regular: rgba(255, 255, 255, 0.80);
    --gs-uitk-color-text-inverse-subtle: rgba(255, 255, 255, 0.70);
    --gs-uitk-color-text-inverse-minimal: rgba(255, 255, 255, 0.60);
    --gs-uitk-color-text-brand: #446EA6;
    --gs-uitk-color-text-functional-positive: #398025;
    --gs-uitk-color-text-functional-negative: #C2170A;
    --gs-uitk-color-text-functional-warning: #B2570D;

    /* ───── Colors: borders ───────────────────────────────────────── */
    --gs-uitk-color-border-neutral-minimal: rgba(0, 0, 0, 0.16);
    --gs-uitk-color-border-neutral-subtle: rgba(0, 0, 0, 0.34);
    --gs-uitk-color-border-neutral-regular: rgba(0, 0, 0, 0.44);
    --gs-uitk-color-border-neutral-bold: rgba(0, 0, 0, 0.95);
    --gs-uitk-color-border-inverse-minimal: rgba(255, 255, 255, 0.22);
    --gs-uitk-color-border-inverse-subtle: rgba(255, 255, 255, 0.34);
    --gs-uitk-color-border-inverse-regular: rgba(255, 255, 255, 0.44);
    --gs-uitk-color-border-inverse-bold: rgba(255, 255, 255, 0.95);
    --gs-uitk-color-border-brand: #7297C5;
    --gs-uitk-color-border-functional-negative: #C2170A;
    --gs-uitk-color-border-functional-positive: #398025;
    --gs-uitk-color-border-functional-warning: #B2570D;

    /* ───── Colors: actions / brand ───────────────────────────────── */
    --gs-uitk-color-action-brand: #7297C5;
    --gs-uitk-color-action-neutral-bold: #000000;
    --gs-uitk-color-action-neutral-subtle: #F7F7FA;
    --gs-uitk-color-action-inverse: #FFFFFF;
    --gs-uitk-color-action-functional-positive: #398025;
    --gs-uitk-color-action-functional-negative: #C2170A;
    --gs-uitk-color-action-functional-warning: #B2570D;
    --gs-uitk-color-interaction-selected-bold: #7297C5;
    --gs-uitk-color-interaction-selected-subtle: rgba(114, 151, 197, 0.16);
    --gs-uitk-color-interaction-hover-on-light: rgba(0, 0, 0, 0.04);
    --gs-uitk-color-interaction-pressed-on-light: rgba(0, 0, 0, 0.08);
    --gs-uitk-color-interaction-hover-on-dark: rgba(255, 255, 255, 0.10);
    --gs-uitk-color-interaction-pressed-on-dark: rgba(255, 255, 255, 0.16);

    /* ───── Colors: dataviz (010 swatch per categorical hue) ──────── */
    --gs-uitk-color-dataviz-categorical010: #092C61;  /* deep navy   */
    /* Navy luminance ramp (hue 010) — verbatim from GS.com SSR UITK injection */
    --gs-uitk-color-dataviz-categorical010_070: #073985;
    --gs-uitk-color-dataviz-categorical010_080: #092C61; /* equals categorical010 */
    --gs-uitk-color-dataviz-categorical010_090: #0B2040;
    --gs-uitk-color-dataviz-categorical010_100: #0B1624;
    --gs-uitk-color-dataviz-categorical020: #7297C5;  /* sky blue    */
    --gs-uitk-color-dataviz-categorical030: #A6428C;  /* mauve       */
    --gs-uitk-color-dataviz-categorical040: #159788;  /* teal        */
    --gs-uitk-color-dataviz-categorical050: #E0731A;  /* burnt orange*/
    --gs-uitk-color-dataviz-categorical060: #7537AD;  /* purple      */
    --gs-uitk-color-dataviz-categorical070: #B03030;  /* brick red   */
    --gs-uitk-color-dataviz-categorical080: #BD8C00;  /* mustard     */
    --gs-uitk-color-dataviz-categorical090: #69370E;  /* brown       */
    --gs-uitk-color-dataviz-categorical100: #617A27;  /* olive       */
    --gs-uitk-color-dataviz-divergent-positive: #398025;
    --gs-uitk-color-dataviz-divergent-negative: #C2170A;
    --gs-uitk-color-dataviz-divergent-contrast-positive: #092C61;
    --gs-uitk-color-dataviz-divergent-contrast-negative: #E0731A;

    /* ───── Image overlay gradients ───────────────────────────────── */
    --gs-uitk-overlay-hero: linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.8) 100%);
    --gs-uitk-overlay-card: linear-gradient(180deg, rgba(0,0,0,0) 30%, rgba(0,0,0,0.55) 100%);

    /* ───── Spacing (8-pt-derived grid) ───────────────────────────── */
    --gs-uitk-space-0: 0px;
    --gs-uitk-space-1: 4px;
    --gs-uitk-space-2: 8px;
    --gs-uitk-space-3: 12px;
    --gs-uitk-space-4: 16px;
    --gs-uitk-space-5: 24px;
    --gs-uitk-space-6: 32px;
    --gs-uitk-space-7: 48px;
    --gs-uitk-space-8: 64px;
    --gs-uitk-space-9: 96px;
    --gs-uitk-space-10: 128px;

    /* ───── Layout widths ─────────────────────────────────────────── */
    --gs-uitk-width-container: 1440px;
    --gs-uitk-width-prose: 816px;
    --gs-uitk-gutter-xs: 24px;
    --gs-uitk-gutter-md: 48px;
    --gs-uitk-gutter-lg: 64px;

    /* ───── Border-radius ─────────────────────────────────────────── */
    --gs-uitk-border-radius-none: 0px;
    --gs-uitk-border-radius-sm: 2px;
    --gs-uitk-border-radius-pill: 9999px;

    /* ───── Elevation (overlay only) ──────────────────────────────── */
    --gs-uitk-shadow-overlay: 0 8px 32px rgba(0, 0, 0, 0.16);

    /* ═════════════════════════════════════════════════════════════════
       Typography tokens — verbatim names from live extraction.
       Each role exposes per-breakpoint font shorthands and letter-spacing.
       The .gs-* utility classes below pick the right one via @media queries.
       ═════════════════════════════════════════════════════════════════ */

    /* Font families. PRISM-runtime substitution for GS Serif:
       headline01-03 fall back to GS Sans Condensed Light;
       headline04 + quotes fall back to GS Sans Light italic.
       The mock body declares data-runtime="prism" by default.
       Flip to data-runtime="live" to preview the system-serif fallback. */
    --gs-font-sans: "GS Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    --gs-font-sans-condensed: "GS Sans Condensed", "Helvetica Neue Condensed", "Helvetica Neue", Helvetica, Arial, sans-serif;
    --gs-font-serif-live: "GS Serif", "Times New Roman", Times, Georgia, serif;
    --gs-font-serif-prism: var(--gs-font-sans-condensed);
    --gs-font-mono: ui-monospace, "Roboto Mono", "SF Mono", Menlo, Monaco, Consolas, monospace;

    /* Headlines — GS Serif Light 300 (live) / GS Cond Light 300 (prism) */
    --gs-uitk-text-headline01-xs-screen-font: 300 50px/50px var(--gs-font-serif-prism);
    --gs-uitk-text-headline01-md-screen-font: 300 80px/80px var(--gs-font-serif-prism);
    --gs-uitk-text-headline01-lg-screen-font: 300 140px/140px var(--gs-font-serif-prism);
    --gs-uitk-text-headline02-xs-screen-font: 300 44px/44px var(--gs-font-serif-prism);
    --gs-uitk-text-headline02-md-screen-font: 300 60px/60px var(--gs-font-serif-prism);
    --gs-uitk-text-headline02-lg-screen-font: 300 100px/100px var(--gs-font-serif-prism);
    --gs-uitk-text-headline03-xs-screen-font: 300 36px/36px var(--gs-font-serif-prism);
    --gs-uitk-text-headline03-md-screen-font: 300 50px/50px var(--gs-font-serif-prism);
    --gs-uitk-text-headline03-lg-screen-font: 300 80px/80px var(--gs-font-serif-prism);
    --gs-uitk-text-headline04-xs-screen-font: 300 30px/30px var(--gs-font-sans);
    --gs-uitk-text-headline04-md-screen-font: 300 40px/40px var(--gs-font-sans);
    --gs-uitk-text-headline04-lg-screen-font: 300 60px/60px var(--gs-font-sans);

    /* Quotes — GS Serif Light italic (live) / GS Sans Light italic (prism) */
    --gs-uitk-text-quote01-xs-screen-font: 300 italic 44px/52px var(--gs-font-serif-prism);
    --gs-uitk-text-quote01-md-screen-font: 300 italic 60px/72px var(--gs-font-serif-prism);
    --gs-uitk-text-quote01-lg-screen-font: 300 italic 100px/120px var(--gs-font-serif-prism);
    --gs-uitk-text-quote02-xs-screen-font: 300 italic 36px/44px var(--gs-font-serif-prism);
    --gs-uitk-text-quote02-md-screen-font: 300 italic 40px/48px var(--gs-font-serif-prism);
    --gs-uitk-text-quote02-lg-screen-font: 300 italic 60px/72px var(--gs-font-serif-prism);
    --gs-uitk-text-quote03-xs-screen-font: 300 italic 28px/34px var(--gs-font-serif-prism);
    --gs-uitk-text-quote03-md-screen-font: 300 italic 30px/36px var(--gs-font-serif-prism);
    --gs-uitk-text-quote03-lg-screen-font: 300 italic 40px/48px var(--gs-font-serif-prism);
    --gs-uitk-text-quote04-xs-screen-font: 300 italic 22px/26px var(--gs-font-sans);
    --gs-uitk-text-quote04-md-screen-font: 300 italic 26px/32px var(--gs-font-sans);
    --gs-uitk-text-quote04-lg-screen-font: 300 italic 30px/36px var(--gs-font-sans);

    /* Headings (GS Sans, page / section titles) */
    --gs-uitk-text-heading01-regular-font: 400 40px/48px var(--gs-font-sans);
    --gs-uitk-text-heading01-medium-font: 500 40px/48px var(--gs-font-sans);
    --gs-uitk-text-heading02-regular-font: 400 32px/40px var(--gs-font-sans);
    --gs-uitk-text-heading02-medium-font: 500 32px/40px var(--gs-font-sans);
    --gs-uitk-text-heading03-regular-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-heading03-medium-font: 500 24px/32px var(--gs-font-sans);

    /* Subtitles (GS Sans, intro paragraphs) */
    --gs-uitk-text-subtitle01-regular-xs-screen-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-regular-md-screen-font: 400 28px/38px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-regular-lg-screen-font: 400 36px/42px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-xs-screen-font: 500 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-md-screen-font: 500 28px/38px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-lg-screen-font: 500 36px/42px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-xs-screen-font: 400 22px/28px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-md-screen-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-lg-screen-font: 400 28px/36px var(--gs-font-sans);

    /* Body — GS Sans, four sizes */
    --gs-uitk-text-body01-regular-xs-screen-font: 400 22px/32px var(--gs-font-sans);
    --gs-uitk-text-body01-regular-md-screen-font: 400 22px/32px var(--gs-font-sans);
    --gs-uitk-text-body01-regular-lg-screen-font: 400 28px/42px var(--gs-font-sans);
    --gs-uitk-text-body02-regular-xs-screen-font: 400 16px/24px var(--gs-font-sans);
    --gs-uitk-text-body02-regular-md-screen-font: 400 18px/28px var(--gs-font-sans);
    --gs-uitk-text-body02-regular-lg-screen-font: 400 20px/30px var(--gs-font-sans);
    --gs-uitk-text-body03-regular-xs-screen-font: 400 16px/24px var(--gs-font-sans);
    --gs-uitk-text-body03-regular-md-screen-font: 400 16px/24px var(--gs-font-sans);
    --gs-uitk-text-body03-regular-lg-screen-font: 400 18px/28px var(--gs-font-sans);
    --gs-uitk-text-body04-regular-xs-screen-font: 400 14px/20px var(--gs-font-sans);
    --gs-uitk-text-body04-regular-md-screen-font: 400 14px/20px var(--gs-font-sans);
    --gs-uitk-text-body04-regular-lg-screen-font: 400 16px/24px var(--gs-font-sans);

    /* Labels — GS Sans, six sizes */
    --gs-uitk-text-label01-regular-font: 400 20px/24px var(--gs-font-sans);
    --gs-uitk-text-label01-medium-font: 500 20px/24px var(--gs-font-sans);
    --gs-uitk-text-label01-bold-font: 700 20px/24px var(--gs-font-sans);
    --gs-uitk-text-label02-regular-font: 400 18px/22px var(--gs-font-sans);
    --gs-uitk-text-label02-medium-font: 500 18px/22px var(--gs-font-sans);
    --gs-uitk-text-label02-bold-font: 700 18px/22px var(--gs-font-sans);
    --gs-uitk-text-label03-regular-font: 400 16px/20px var(--gs-font-sans);
    --gs-uitk-text-label03-medium-font: 500 16px/20px var(--gs-font-sans);
    --gs-uitk-text-label03-bold-font: 700 16px/20px var(--gs-font-sans);
    --gs-uitk-text-label04-regular-font: 400 14px/18px var(--gs-font-sans);
    --gs-uitk-text-label04-medium-font: 500 14px/18px var(--gs-font-sans);
    --gs-uitk-text-label04-bold-font: 700 14px/18px var(--gs-font-sans);
    --gs-uitk-text-label05-regular-font: 400 12px/16px var(--gs-font-sans);
    --gs-uitk-text-label05-medium-font: 500 12px/16px var(--gs-font-sans);
    --gs-uitk-text-label06-regular-font: 400 10px/12px var(--gs-font-sans);

    /* Captions / overlines */
    --gs-uitk-text-caption01-regular-font: 400 14px/18px var(--gs-font-sans);
    --gs-uitk-text-caption02-regular-font: 400 12px/16px var(--gs-font-sans);

    --gs-uitk-text-overline01-xs-screen-font: 400 14px/18px var(--gs-font-sans);
    --gs-uitk-text-overline01-md-screen-font: 400 16px/20px var(--gs-font-sans);
    --gs-uitk-text-overline01-lg-screen-font: 400 16px/20px var(--gs-font-sans);
    --gs-uitk-text-overline02-xs-screen-font: 400 12px/16px var(--gs-font-sans);
    --gs-uitk-text-overline02-md-screen-font: 400 14px/18px var(--gs-font-sans);
    --gs-uitk-text-overline02-lg-screen-font: 400 14px/18px var(--gs-font-sans);
    --gs-uitk-text-overline03-xs-screen-font: 400 10px/14px var(--gs-font-sans);
    --gs-uitk-text-overline03-md-screen-font: 400 12px/16px var(--gs-font-sans);
    --gs-uitk-text-overline03-lg-screen-font: 400 12px/16px var(--gs-font-sans);

    /* Stats — GS Sans Condensed Light 300 (signature) */
    --gs-uitk-text-stat01-xs-screen-font: 300 100px/100px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat01-md-screen-font: 300 144px/144px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat01-lg-screen-font: 300 200px/200px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-xs-screen-font: 300 72px/72px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-md-screen-font: 300 88px/88px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-lg-screen-font: 300 100px/100px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat03-xs-screen-font: 500 44px/44px var(--gs-font-sans);
    --gs-uitk-text-stat03-md-screen-font: 500 46px/46px var(--gs-font-sans);
    --gs-uitk-text-stat03-lg-screen-font: 500 46px/46px var(--gs-font-sans);

    /* Code — Roboto Mono via system stack */
    --gs-uitk-text-code01-font: 400 14px/20px var(--gs-font-mono);
    --gs-uitk-text-code02-font: 500 12px/16px var(--gs-font-mono);
}

/* ───── Live-mode override ─────────────────────────────────────────────
   Flip GS Serif role onto a system-serif fallback so the headline / quote
   register reads closer to gs.com (when you're previewing the live
   direction rather than PRISM's runtime constraints).

   <html data-runtime="live"> ... </html>
   ────────────────────────────────────────────────────────────────────── */
html[data-runtime="live"] {
    --gs-font-serif-prism: var(--gs-font-serif-live);
}
```

---

## 4. CSS — fonts.css

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/static/css/fonts.css`

```css
/* ═══════════════════════════════════════════════════════════════════════
   fonts.css — @font-face declarations for the 20 GS Sans + GS Sans
   Condensed TTF cuts that PRISM has at ai_development/mysite/fonts/.

   See projects/gs_reference/dev/specs/gs_design_dna.md §3 for context.

   GS Serif is NOT in PRISM's drop. The display tokens substitute to
   GS Sans Condensed Light 300 (see tokens.css :root and §3.5 of the
   spec). To preview the live-site direction, set
       <html data-runtime="live">
   which flips --gs-font-serif-prism back to a system serif fallback.
   ═══════════════════════════════════════════════════════════════════════ */

/* ─────────────────────────────────────────────────────────────────────
   GS Sans — 10 static cuts (250-700, roman + italic each)
   ───────────────────────────────────────────────────────────────────── */

@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_Th.ttf") format("truetype");
    font-weight: 250;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_ThIt.ttf") format("truetype");
    font-weight: 250;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_Lt.ttf") format("truetype");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_LIt.ttf") format("truetype");
    font-weight: 300;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_Rg.ttf") format("truetype");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_It.ttf") format("truetype");
    font-weight: 400;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_Md.ttf") format("truetype");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_MdIt.ttf") format("truetype");
    font-weight: 500;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_Bd.ttf") format("truetype");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/GSSans_BdIt.ttf") format("truetype");
    font-weight: 700;
    font-style: italic;
    font-display: swap;
}

/* ─────────────────────────────────────────────────────────────────────
   GS Sans Condensed — 10 static cuts (300-900, roman + italic each)
   ───────────────────────────────────────────────────────────────────── */

@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_Lt.ttf") format("truetype");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_LIt.ttf") format("truetype");
    font-weight: 300;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_Rg.ttf") format("truetype");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_It.ttf") format("truetype");
    font-weight: 400;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_Md.ttf") format("truetype");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_MdIt.ttf") format("truetype");
    font-weight: 500;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_Bd.ttf") format("truetype");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_BdIt.ttf") format("truetype");
    font-weight: 700;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_Blk.ttf") format("truetype");
    font-weight: 900;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("/static/fonts/GSSansCondensed_BlkIt.ttf") format("truetype");
    font-weight: 900;
    font-style: italic;
    font-display: swap;
}
```

---

## 5. CSS — components.css

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/static/css/components.css`

```css
/* ═══════════════════════════════════════════════════════════════════════
   components.css — class implementations of the GS design primitives.

   Every class corresponds to a section of gs_design_dna.md §8.
   Naming convention: .gs-<primitive>[--<variant>][__<element>].
   ═══════════════════════════════════════════════════════════════════════ */

/* ───── Reset / base ──────────────────────────────────────────────── */

*,
*::before,
*::after {
    box-sizing: border-box;
}

html {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    text-size-adjust: 100%;
}

body {
    margin: 0;
    padding: 0;
    background: var(--gs-uitk-color-surface-neutral-minimal);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: var(--gs-uitk-text-body03-regular-lg-screen-font);
    letter-spacing: 0;
}

img {
    max-width: 100%;
    display: block;
}

a {
    color: var(--gs-uitk-color-text-brand);
    text-decoration: none;
}

a:hover {
    text-decoration: underline;
}

/* ───── Container ─────────────────────────────────────────────────── */

.gs-container {
    width: 100%;
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding-left: var(--gs-uitk-gutter-xs);
    padding-right: var(--gs-uitk-gutter-xs);
}

@media (min-width: 768px) {
    .gs-container {
        padding-left: var(--gs-uitk-gutter-md);
        padding-right: var(--gs-uitk-gutter-md);
    }
}

@media (min-width: 1200px) {
    .gs-container {
        padding-left: var(--gs-uitk-gutter-lg);
        padding-right: var(--gs-uitk-gutter-lg);
    }
}

/* ───── Type utility classes (per-breakpoint role expansion) ──────── */

.gs-overline {
    font: var(--gs-uitk-text-overline02-xs-screen-font);
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0;
    display: inline-block;
}
@media (min-width: 768px) {
    .gs-overline { font: var(--gs-uitk-text-overline02-md-screen-font); letter-spacing: 1px; }
}
@media (min-width: 1200px) {
    .gs-overline { font: var(--gs-uitk-text-overline02-lg-screen-font); letter-spacing: 1px; }
}

.gs-overline--inverse { color: var(--gs-uitk-color-text-inverse-bold); }

.gs-overline--lg {
    font: var(--gs-uitk-text-overline01-xs-screen-font);
    letter-spacing: 1px;
    text-transform: uppercase;
    color: var(--gs-uitk-color-text-neutral-minimal);
}
@media (min-width: 768px)  { .gs-overline--lg { font: var(--gs-uitk-text-overline01-md-screen-font); letter-spacing: 1px; } }
@media (min-width: 1200px) { .gs-overline--lg { font: var(--gs-uitk-text-overline01-lg-screen-font); letter-spacing: 1px; } }

.gs-headline {
    margin: 0;
    color: var(--gs-uitk-color-text-neutral-bold);
}

.gs-headline--01 {
    font: var(--gs-uitk-text-headline01-xs-screen-font);
    letter-spacing: 0;
}
@media (min-width: 768px)  { .gs-headline--01 { font: var(--gs-uitk-text-headline01-md-screen-font); } }
@media (min-width: 1200px) { .gs-headline--01 { font: var(--gs-uitk-text-headline01-lg-screen-font); } }

.gs-headline--02 {
    font: var(--gs-uitk-text-headline02-xs-screen-font);
    letter-spacing: 0;
}
@media (min-width: 768px)  { .gs-headline--02 { font: var(--gs-uitk-text-headline02-md-screen-font); } }
@media (min-width: 1200px) { .gs-headline--02 { font: var(--gs-uitk-text-headline02-lg-screen-font); } }

.gs-headline--03 {
    font: var(--gs-uitk-text-headline03-xs-screen-font);
    letter-spacing: 0;
}
@media (min-width: 768px)  { .gs-headline--03 { font: var(--gs-uitk-text-headline03-md-screen-font); } }
@media (min-width: 1200px) { .gs-headline--03 { font: var(--gs-uitk-text-headline03-lg-screen-font); } }

.gs-headline--04 {
    font: var(--gs-uitk-text-headline04-xs-screen-font);
    letter-spacing: 0;
}
@media (min-width: 768px)  { .gs-headline--04 { font: var(--gs-uitk-text-headline04-md-screen-font); } }
@media (min-width: 1200px) { .gs-headline--04 { font: var(--gs-uitk-text-headline04-lg-screen-font); } }

.gs-headline--inverse { color: var(--gs-uitk-color-text-inverse-bold); }

.gs-heading {
    margin: 0;
    color: var(--gs-uitk-color-text-neutral-bold);
    letter-spacing: 0;
}
.gs-heading--01 { font: var(--gs-uitk-text-heading01-medium-font); }
.gs-heading--02 { font: var(--gs-uitk-text-heading02-medium-font); }
.gs-heading--03 { font: var(--gs-uitk-text-heading03-medium-font); }
.gs-heading--inverse { color: var(--gs-uitk-color-text-inverse-bold); }

.gs-subtitle {
    margin: 0;
    color: var(--gs-uitk-color-text-neutral-regular);
    font: var(--gs-uitk-text-subtitle02-regular-xs-screen-font);
}
@media (min-width: 768px)  { .gs-subtitle { font: var(--gs-uitk-text-subtitle02-regular-md-screen-font); } }
@media (min-width: 1200px) { .gs-subtitle { font: var(--gs-uitk-text-subtitle02-regular-lg-screen-font); } }

.gs-subtitle--lg {
    font: var(--gs-uitk-text-subtitle01-regular-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
}
@media (min-width: 768px)  { .gs-subtitle--lg { font: var(--gs-uitk-text-subtitle01-regular-md-screen-font); } }
@media (min-width: 1200px) { .gs-subtitle--lg { font: var(--gs-uitk-text-subtitle01-regular-lg-screen-font); } }

.gs-body {
    font: var(--gs-uitk-text-body03-regular-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0;
}
@media (min-width: 768px)  { .gs-body { font: var(--gs-uitk-text-body03-regular-md-screen-font); } }
@media (min-width: 1200px) { .gs-body { font: var(--gs-uitk-text-body03-regular-lg-screen-font); } }

.gs-body--lg {
    font: var(--gs-uitk-text-body02-regular-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0;
}
@media (min-width: 768px)  { .gs-body--lg { font: var(--gs-uitk-text-body02-regular-md-screen-font); } }
@media (min-width: 1200px) { .gs-body--lg { font: var(--gs-uitk-text-body02-regular-lg-screen-font); } }

.gs-body--sm {
    font: var(--gs-uitk-text-body04-regular-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0;
}
@media (min-width: 768px)  { .gs-body--sm { font: var(--gs-uitk-text-body04-regular-md-screen-font); } }
@media (min-width: 1200px) { .gs-body--sm { font: var(--gs-uitk-text-body04-regular-lg-screen-font); } }

.gs-body--inverse { color: var(--gs-uitk-color-text-inverse-regular); }

/* Section heading composite: eyebrow + headline (DNA §8.3) */
.gs-section-heading {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    margin-bottom: var(--gs-uitk-space-7);
}

/* ───── Top navigation (DNA §8.1) ─────────────────────────────────── */

.gs-nav {
    position: sticky;
    top: 0;
    z-index: 100;
    /* Masthead: live GS sky-blue chrome from the homepage top ribbon. */
    background-color: var(--gs-uitk-color-surface-brand-bold);
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}

.gs-nav__inner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 56px;
    width: 100%;
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding: 0 var(--gs-uitk-gutter-xs);
}

@media (min-width: 768px) {
    .gs-nav__inner { height: 72px; padding: 0 var(--gs-uitk-gutter-md); }
}
@media (min-width: 1200px) {
    .gs-nav__inner { padding: 0 var(--gs-uitk-gutter-lg); }
}

.gs-nav__logo {
    font: var(--gs-uitk-text-label02-medium-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    text-decoration: none;
    letter-spacing: 0;
    display: flex;
    align-items: center;
    gap: var(--gs-uitk-space-3);
}

.gs-nav__logo-mark {
    width: 32px;
    height: 32px;
    background: var(--gs-uitk-color-action-neutral-bold);
    color: var(--gs-uitk-color-action-inverse);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font: var(--gs-uitk-text-label04-bold-font);
    letter-spacing: 0;
}

.gs-nav__items {
    display: none;
    list-style: none;
    margin: 0;
    padding: 0;
    align-items: center;
    gap: var(--gs-uitk-space-5);
}

@media (min-width: 1024px) {
    .gs-nav__items { display: flex; }
}

.gs-nav__item a {
    font: var(--gs-uitk-text-label03-medium-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    text-decoration: none;
    padding: var(--gs-uitk-space-4) 0;
    display: inline-block;
    border-bottom: 3px solid transparent;
    transition: color 200ms ease, border-color 200ms ease;
}

.gs-nav__item a:hover {
    color: var(--gs-uitk-color-text-neutral-bold);
    text-decoration: none;
}

.gs-nav__item--active a {
    color: var(--gs-uitk-color-text-neutral-bold);
    border-bottom-color: var(--gs-uitk-color-border-neutral-bold);
}

.gs-nav__right {
    display: flex;
    align-items: center;
    gap: var(--gs-uitk-space-4);
}

.gs-nav__icon {
    width: 40px;
    height: 40px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--gs-uitk-color-text-neutral-bold);
}

.gs-nav__icon:hover {
    background: var(--gs-uitk-color-interaction-hover-on-light);
}

/* ───── Buttons (DNA §8.10) ──────────────────────────────────────── */

.gs-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--gs-uitk-space-2);
    padding: var(--gs-uitk-space-3) var(--gs-uitk-space-5);
    min-height: 48px;
    border-radius: var(--gs-uitk-border-radius-none);
    border: 1px solid transparent;
    font: var(--gs-uitk-text-label04-medium-font);
    letter-spacing: 0;
    text-decoration: none;
    cursor: pointer;
    transition: background-color 200ms ease, color 200ms ease, border-color 200ms ease;
}

.gs-button:hover { text-decoration: none; }

.gs-button--primary {
    background: var(--gs-uitk-color-action-neutral-bold);
    color: var(--gs-uitk-color-action-inverse);
}

.gs-button--primary:hover {
    background: #2a2a2a;
}

.gs-button--ghost-dark {
    background: transparent;
    color: var(--gs-uitk-color-text-neutral-bold);
    border-color: var(--gs-uitk-color-border-neutral-bold);
}

.gs-button--ghost-dark:hover {
    background: var(--gs-uitk-color-interaction-hover-on-light);
}

.gs-button--ghost-light {
    background: transparent;
    color: var(--gs-uitk-color-text-inverse-bold);
    border-color: var(--gs-uitk-color-border-inverse-bold);
}

.gs-button--ghost-light:hover {
    background: var(--gs-uitk-color-interaction-hover-on-dark);
}

.gs-button__arrow {
    display: inline-block;
    transition: transform 200ms ease;
}

.gs-button:hover .gs-button__arrow {
    transform: translateX(4px);
}

/* ───── Hero (DNA §8.4) ──────────────────────────────────────────── */

.gs-hero {
    position: relative;
    min-height: 480px;
    aspect-ratio: 16 / 9;
    overflow: hidden;
    display: flex;
    align-items: flex-end;
    background: var(--gs-uitk-color-surface-always-dark-regular);
}

@media (max-width: 767px) {
    .gs-hero { aspect-ratio: 4 / 5; min-height: 600px; }
}

.gs-hero__image,
.gs-hero__image > svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
    object-position: center;
}

.gs-hero__overlay {
    position: absolute;
    inset: 0;
    background: var(--gs-uitk-overlay-hero);
}

.gs-hero__content {
    position: relative;
    width: 100%;
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding: var(--gs-uitk-space-7) var(--gs-uitk-gutter-xs) var(--gs-uitk-space-9);
    color: var(--gs-uitk-color-text-inverse-bold);
}

@media (min-width: 768px) {
    .gs-hero__content {
        padding: var(--gs-uitk-space-9) var(--gs-uitk-gutter-md);
    }
}

@media (min-width: 1200px) {
    .gs-hero__content {
        padding: var(--gs-uitk-space-10) var(--gs-uitk-gutter-lg);
    }
}

.gs-hero__text {
    max-width: 720px;
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-5);
}

.gs-hero__cta {
    margin-top: var(--gs-uitk-space-3);
    align-self: flex-start;
}

/* ───── Tab strip (DNA §8.7) ─────────────────────────────────────── */

.gs-tabs {
    /* Sky-blue ribbon (matches live hero-adjacent treatment in this mock; see `.gs-briefings`). */
    border-bottom: 1px solid var(--gs-uitk-color-border-inverse-minimal);
    background-color: #7297C5;
    background-color: var(--gs-uitk-color-surface-brand-bold, #7297C5);
}

.gs-tabs__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: var(--gs-uitk-space-7);
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding: 0 var(--gs-uitk-gutter-xs);
}

@media (min-width: 768px) {
    .gs-tabs__list { padding: 0 var(--gs-uitk-gutter-md); }
}

@media (min-width: 1200px) {
    .gs-tabs__list { padding: 0 var(--gs-uitk-gutter-lg); }
}

.gs-tabs__item a {
    display: inline-block;
    font: var(--gs-uitk-text-label03-medium-font);
    color: var(--gs-uitk-color-text-neutral-subtle);
    padding: var(--gs-uitk-space-4) 0;
    text-decoration: none;
    border-bottom: 3px solid transparent;
    transition: color 200ms ease, border-color 200ms ease;
}

.gs-tabs__item a:hover {
    color: var(--gs-uitk-color-text-neutral-bold);
    text-decoration: none;
}

.gs-tabs__item--active a {
    color: var(--gs-uitk-color-text-neutral-bold);
    border-bottom-color: var(--gs-uitk-color-action-neutral-bold);
}

/* ───── Section spacing ──────────────────────────────────────────── */

.gs-section {
    padding-top: var(--gs-uitk-space-9);
    padding-bottom: var(--gs-uitk-space-9);
}

@media (min-width: 1200px) {
    .gs-section {
        padding-top: var(--gs-uitk-space-10);
        padding-bottom: var(--gs-uitk-space-10);
    }
}

.gs-section--subtle {
    background: var(--gs-uitk-color-surface-neutral-subtle);
}

.gs-section--brand-subtle {
    background: var(--gs-uitk-color-surface-brand-subtle);
}

.gs-section--inverse {
    background: var(--gs-uitk-color-surface-inverse-bold);
}

.gs-section--tight {
    padding-top: var(--gs-uitk-space-7);
    padding-bottom: var(--gs-uitk-space-7);
}

/* ───── Card (DNA §8.5) ──────────────────────────────────────────── */

.gs-card {
    background: var(--gs-uitk-color-surface-neutral-minimal);
    border: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    border-radius: var(--gs-uitk-border-radius-none);
    overflow: hidden;
    display: flex;
    flex-direction: column;
    text-decoration: none;
    color: inherit;
    transition: border-color 200ms ease;
}

.gs-card:hover {
    text-decoration: none;
    border-color: var(--gs-uitk-color-border-neutral-subtle);
}

.gs-card__image {
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-neutral-regular);
}

.gs-card__image img,
.gs-card__image svg {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transition: transform 400ms ease;
}

.gs-card:hover .gs-card__image img,
.gs-card:hover .gs-card__image svg {
    transform: scale(1.04);
}

.gs-card__body {
    padding: var(--gs-uitk-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    flex: 1;
}

.gs-card__title {
    margin: 0;
    font: var(--gs-uitk-text-heading03-medium-font);
    color: var(--gs-uitk-color-text-neutral-bold);
}

.gs-card__body p {
    margin: 0;
}

.gs-card__cta {
    margin-top: auto;
    padding-top: var(--gs-uitk-space-3);
    font: var(--gs-uitk-text-label03-medium-font);
    color: var(--gs-uitk-color-text-brand);
    display: inline-flex;
    align-items: center;
    gap: var(--gs-uitk-space-2);
}

/* Variant: text overlaid on image */
.gs-card--overlay {
    position: relative;
    color: var(--gs-uitk-color-text-inverse-bold);
    border: none;
    aspect-ratio: 16 / 9;
}

.gs-card--overlay .gs-card__image {
    aspect-ratio: auto;
    position: absolute;
    inset: 0;
}

.gs-card--overlay::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--gs-uitk-overlay-card);
    z-index: 1;
}

.gs-card--overlay .gs-card__body {
    position: relative;
    z-index: 2;
    margin-top: auto;
    color: var(--gs-uitk-color-text-inverse-bold);
}

.gs-card--overlay .gs-card__title {
    color: var(--gs-uitk-color-text-inverse-bold);
}

.gs-card--overlay .gs-overline {
    color: var(--gs-uitk-color-text-inverse-bold);
}

.gs-card--overlay .gs-card__cta {
    color: var(--gs-uitk-color-text-inverse-bold);
}

.gs-card--overlay .gs-card__body p {
    color: var(--gs-uitk-color-text-inverse-regular);
}

/* Compact text-only card (no image) — for value tiles, link cards */
.gs-card--text {
    padding: var(--gs-uitk-space-7);
}

.gs-card--text .gs-card__body {
    padding: 0;
}

/* ───── Card grid utilities ──────────────────────────────────────── */

.gs-grid {
    display: grid;
    gap: var(--gs-uitk-space-5);
}

@media (min-width: 768px) {
    .gs-grid--2 { grid-template-columns: repeat(2, 1fr); }
    .gs-grid--3 { grid-template-columns: repeat(3, 1fr); }
    .gs-grid--4 { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 1200px) {
    .gs-grid--4 { grid-template-columns: repeat(4, 1fr); }
    .gs-grid { gap: var(--gs-uitk-space-7); }
}

/* ───── Stat module (DNA §8.6) ───────────────────────────────────── */

.gs-stat-row {
    display: grid;
    gap: var(--gs-uitk-space-7);
    grid-template-columns: 1fr;
}

@media (min-width: 768px) {
    .gs-stat-row { grid-template-columns: repeat(3, 1fr); }
}

.gs-stat {
    border-top: 1px solid var(--gs-uitk-color-border-neutral-bold);
    padding-top: var(--gs-uitk-space-4);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
}

.gs-stat__numeral {
    font: var(--gs-uitk-text-stat02-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    margin: 0;
}

@media (min-width: 768px)  { .gs-stat__numeral { font: var(--gs-uitk-text-stat02-md-screen-font); } }
@media (min-width: 1200px) { .gs-stat__numeral { font: var(--gs-uitk-text-stat02-lg-screen-font); } }

.gs-stat__numeral-sup {
    font: var(--gs-uitk-text-label05-regular-font);
    vertical-align: super;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin-left: var(--gs-uitk-space-2);
}

.gs-stat__caption {
    max-width: 320px;
    font: var(--gs-uitk-text-body04-regular-lg-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
}

/* Hero stat (stat01 — even bigger) */
.gs-stat--hero .gs-stat__numeral {
    font: var(--gs-uitk-text-stat01-xs-screen-font);
}

@media (min-width: 768px)  { .gs-stat--hero .gs-stat__numeral { font: var(--gs-uitk-text-stat01-md-screen-font); } }
@media (min-width: 1200px) { .gs-stat--hero .gs-stat__numeral { font: var(--gs-uitk-text-stat01-lg-screen-font); } }

/* ───── Two-up section (DNA §8.15) ───────────────────────────────── */

.gs-two-up {
    display: grid;
    gap: var(--gs-uitk-space-7);
    grid-template-columns: 1fr;
    align-items: center;
}

@media (min-width: 768px) {
    .gs-two-up {
        grid-template-columns: 1fr 1fr;
        gap: var(--gs-uitk-space-8);
    }
}

@media (min-width: 1200px) {
    .gs-two-up { gap: var(--gs-uitk-space-9); }
}

.gs-two-up--reverse .gs-two-up__media {
    order: 2;
}

@media (max-width: 767px) {
    .gs-two-up--reverse .gs-two-up__media { order: 0; }
}

.gs-two-up__media {
    aspect-ratio: 1 / 1;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-neutral-regular);
}

.gs-two-up__media img,
.gs-two-up__media svg {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.gs-two-up__content {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-5);
}

.gs-two-up__cta { align-self: flex-start; margin-top: var(--gs-uitk-space-3); }

/* ───── Briefings subscribe module (DNA §8.8) ────────────────────── */

.gs-briefings {
    /* Explicit hex first: if tokens.css fails to load, var(...) is dropped and strip reads white. */
    background-color: #7297C5;
    background-color: var(--gs-uitk-color-surface-brand-bold, #7297C5);
    color: var(--gs-uitk-color-text-neutral-bold);
    padding: var(--gs-uitk-space-9) 0;
}

.gs-briefings .gs-heading,
.gs-briefings p,
.gs-briefings .gs-overline {
    color: var(--gs-uitk-color-text-neutral-bold);
}

.gs-briefings__inner {
    max-width: 720px;
    margin: 0 auto;
    padding: 0 var(--gs-uitk-gutter-xs);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-5);
}

.gs-briefings__form {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--gs-uitk-space-3);
}

@media (min-width: 600px) {
    .gs-briefings__form {
        grid-template-columns: 1fr auto;
        gap: 0;
    }
}

.gs-briefings__input {
    height: 56px;
    border: 1px solid var(--gs-uitk-color-border-neutral-regular);
    border-right: none;
    background: var(--gs-uitk-color-surface-neutral-minimal);
    padding: 0 var(--gs-uitk-space-4);
    font: var(--gs-uitk-text-body03-regular-lg-screen-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    border-radius: var(--gs-uitk-border-radius-none);
}

@media (max-width: 599px) {
    .gs-briefings__input { border-right: 1px solid var(--gs-uitk-color-border-neutral-regular); }
}

.gs-briefings__input:focus {
    outline: none;
    border-color: var(--gs-uitk-color-border-neutral-bold);
}

.gs-briefings__submit {
    height: 56px;
    padding: 0 var(--gs-uitk-space-7);
    background: var(--gs-uitk-color-action-neutral-bold);
    color: var(--gs-uitk-color-action-inverse);
    border: none;
    font: var(--gs-uitk-text-label03-medium-font);
    cursor: pointer;
    border-radius: var(--gs-uitk-border-radius-none);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--gs-uitk-space-2);
    min-height: 56px;
}

.gs-briefings__legal {
    font: var(--gs-uitk-text-caption02-regular-font);
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0;
}

.gs-briefings__legal a {
    color: var(--gs-uitk-color-text-brand);
}

/* ───── Footer (DNA §8.9) ─────────────────────────────────────────── */

.gs-footer {
    background: var(--gs-uitk-color-surface-inverse-bold);
    color: var(--gs-uitk-color-text-inverse-regular);
    padding: var(--gs-uitk-space-9) 0 var(--gs-uitk-space-5);
}

.gs-footer__columns {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--gs-uitk-space-7);
    margin-bottom: var(--gs-uitk-space-9);
}

@media (min-width: 768px) {
    .gs-footer__columns { grid-template-columns: repeat(5, 1fr); }
}

.gs-footer__col-title {
    font: var(--gs-uitk-text-label04-bold-font);
    color: var(--gs-uitk-color-text-inverse-bold);
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 0 0 var(--gs-uitk-space-4);
}

.gs-footer__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
}

.gs-footer__list a {
    font: var(--gs-uitk-text-label04-regular-font);
    color: var(--gs-uitk-color-text-inverse-regular);
    text-decoration: none;
}

.gs-footer__list a:hover {
    color: var(--gs-uitk-color-text-inverse-bold);
    text-decoration: underline;
}

.gs-footer__bottom {
    border-top: 1px solid var(--gs-uitk-color-border-inverse-minimal);
    padding-top: var(--gs-uitk-space-4);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    font: var(--gs-uitk-text-caption02-regular-font);
    color: var(--gs-uitk-color-text-inverse-subtle);
}

@media (min-width: 768px) {
    .gs-footer__bottom { flex-direction: row; justify-content: space-between; align-items: center; }
}

.gs-footer__bottom-links {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: var(--gs-uitk-space-5);
    flex-wrap: wrap;
}

.gs-footer__bottom-links a {
    color: var(--gs-uitk-color-text-inverse-subtle);
    text-decoration: none;
}

.gs-footer__bottom-links a:hover {
    color: var(--gs-uitk-color-text-inverse-bold);
}

/* ───── Page header (used by interior pillar / detail pages) ───── */

.gs-page-header {
    padding-top: var(--gs-uitk-space-8);
    padding-bottom: var(--gs-uitk-space-8);
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}

.gs-page-header__inner {
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding: 0 var(--gs-uitk-gutter-xs);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-4);
}

@media (min-width: 768px)  { .gs-page-header__inner { padding: 0 var(--gs-uitk-gutter-md); } }
@media (min-width: 1200px) { .gs-page-header__inner { padding: 0 var(--gs-uitk-gutter-lg); } }

.gs-page-header__share {
    align-self: flex-end;
    font: var(--gs-uitk-text-label04-regular-font);
    color: var(--gs-uitk-color-text-neutral-subtle);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: var(--gs-uitk-space-2);
}

.gs-page-header--centered .gs-page-header__inner {
    align-items: center;
    text-align: center;
    max-width: 720px;
}

/* ───── Article body (DNA §8.11) ─────────────────────────────────── */

.gs-article-body {
    max-width: var(--gs-uitk-width-prose);
    margin: 0 auto;
    padding: var(--gs-uitk-space-8) var(--gs-uitk-gutter-xs);
}

@media (min-width: 768px) {
    .gs-article-body { padding-left: var(--gs-uitk-gutter-md); padding-right: var(--gs-uitk-gutter-md); }
}

.gs-article-body p,
.gs-article-body ul,
.gs-article-body ol {
    font: var(--gs-uitk-text-body02-regular-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0 0 var(--gs-uitk-space-5);
}

@media (min-width: 768px) {
    .gs-article-body p,
    .gs-article-body ul,
    .gs-article-body ol { font: var(--gs-uitk-text-body02-regular-md-screen-font); }
}

@media (min-width: 1200px) {
    .gs-article-body p,
    .gs-article-body ul,
    .gs-article-body ol { font: var(--gs-uitk-text-body02-regular-lg-screen-font); }
}

.gs-article-body h2 {
    font: var(--gs-uitk-text-heading01-medium-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    margin: var(--gs-uitk-space-8) 0 var(--gs-uitk-space-5);
}

.gs-article-body h3 {
    font: var(--gs-uitk-text-heading03-medium-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    margin: var(--gs-uitk-space-6) 0 var(--gs-uitk-space-4);
}

/* Numbered list with big-numeral signature */
.gs-numbered-list {
    list-style: none;
    margin: var(--gs-uitk-space-5) 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-7);
}

.gs-numbered-list__item {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: var(--gs-uitk-space-5);
    align-items: start;
}

@media (min-width: 1200px) {
    .gs-numbered-list__item { grid-template-columns: 120px 1fr; gap: var(--gs-uitk-space-7); }
}

.gs-numbered-list__numeral {
    font: var(--gs-uitk-text-stat02-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    line-height: 1;
}

@media (min-width: 768px)  { .gs-numbered-list__numeral { font: var(--gs-uitk-text-stat02-md-screen-font); line-height: 1; } }
@media (min-width: 1200px) { .gs-numbered-list__numeral { font: var(--gs-uitk-text-stat02-lg-screen-font); line-height: 1; } }

.gs-numbered-list__body {
    font: var(--gs-uitk-text-body02-regular-md-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
}

/* Pull quote */
.gs-pull-quote {
    margin: var(--gs-uitk-space-7) 0;
    padding: var(--gs-uitk-space-5) 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    font: var(--gs-uitk-text-quote03-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    quotes: "\201C" "\201D";
}

@media (min-width: 768px)  { .gs-pull-quote { font: var(--gs-uitk-text-quote03-md-screen-font); } }
@media (min-width: 1200px) { .gs-pull-quote { font: var(--gs-uitk-text-quote03-lg-screen-font); } }

.gs-pull-quote::before { content: open-quote; }
.gs-pull-quote::after { content: close-quote; }

/* Footnote / source block */
.gs-footnotes {
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding-top: var(--gs-uitk-space-5);
    margin-top: var(--gs-uitk-space-8);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    font: var(--gs-uitk-text-caption02-regular-font);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

/* ───── Byline (DNA §8.12) ───────────────────────────────────────── */

.gs-byline {
    max-width: var(--gs-uitk-width-prose);
    margin: 0 auto;
    padding: var(--gs-uitk-space-5) var(--gs-uitk-gutter-xs);
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-4);
}

@media (min-width: 768px) {
    .gs-byline { padding-left: var(--gs-uitk-gutter-md); padding-right: var(--gs-uitk-gutter-md); }
}

.gs-byline__authors {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-2);
}

.gs-byline__author-name {
    font: var(--gs-uitk-text-label04-bold-font);
    color: var(--gs-uitk-color-text-neutral-bold);
}

.gs-byline__author-title {
    font: var(--gs-uitk-text-caption02-regular-font);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

.gs-byline__meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font: var(--gs-uitk-text-label04-regular-font);
    color: var(--gs-uitk-color-text-neutral-subtle);
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding-top: var(--gs-uitk-space-4);
}

/* ───── Sub-pillar list (used by what_we_do) ─────────────────────── */

.gs-pillar-section {
    padding-top: var(--gs-uitk-space-8);
    padding-bottom: var(--gs-uitk-space-8);
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}

.gs-pillar-section__inner {
    max-width: var(--gs-uitk-width-container);
    margin: 0 auto;
    padding: 0 var(--gs-uitk-gutter-xs);
    display: grid;
    gap: var(--gs-uitk-space-7);
}

@media (min-width: 768px)  { .gs-pillar-section__inner { padding: 0 var(--gs-uitk-gutter-md); grid-template-columns: 1fr 2fr; } }
@media (min-width: 1200px) { .gs-pillar-section__inner { padding: 0 var(--gs-uitk-gutter-lg); } }

.gs-pillar-section__heading {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
}

.gs-pillar-section__links {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-5);
}

.gs-pillar-link {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    padding: var(--gs-uitk-space-5) 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    text-decoration: none;
    color: inherit;
}

.gs-pillar-link:first-child {
    border-top: none;
    padding-top: 0;
}

.gs-pillar-link__title {
    font: var(--gs-uitk-text-heading03-medium-font);
    color: var(--gs-uitk-color-text-brand);
    margin: 0;
    display: inline-flex;
    align-items: center;
    gap: var(--gs-uitk-space-2);
}

.gs-pillar-link:hover .gs-pillar-link__title {
    text-decoration: underline;
}

.gs-pillar-link__body {
    font: var(--gs-uitk-text-body03-regular-lg-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0;
}

/* ───── Quote callout (used in careers tagline) ──────────────────── */

.gs-quote-callout {
    text-align: center;
    max-width: 960px;
    margin: 0 auto;
    padding: var(--gs-uitk-space-9) var(--gs-uitk-gutter-xs);
    font: var(--gs-uitk-text-quote02-xs-screen-font);
    color: var(--gs-uitk-color-text-neutral-bold);
}

@media (min-width: 768px)  { .gs-quote-callout { font: var(--gs-uitk-text-quote02-md-screen-font); padding: var(--gs-uitk-space-10) var(--gs-uitk-gutter-md); } }
@media (min-width: 1200px) { .gs-quote-callout { font: var(--gs-uitk-text-quote02-lg-screen-font); padding: var(--gs-uitk-space-10) var(--gs-uitk-gutter-lg); } }

/* ───── Link list (compact secondary nav) ────────────────────────── */

.gs-link-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
}

.gs-link-list a {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--gs-uitk-space-5) 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: var(--gs-uitk-text-label02-medium-font);
    text-decoration: none;
}

.gs-link-list li:last-child a {
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}

.gs-link-list a:hover {
    color: var(--gs-uitk-color-text-brand);
    text-decoration: none;
}

/* ───── Format chip (Article / Podcast / Video badge on cards) ──── */

.gs-format-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--gs-uitk-space-2);
    padding: var(--gs-uitk-space-1) var(--gs-uitk-space-3);
    background: var(--gs-uitk-color-action-neutral-subtle);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: var(--gs-uitk-text-label05-medium-font);
    text-transform: uppercase;
    letter-spacing: 1px;
    border-radius: var(--gs-uitk-border-radius-none);
}

/* ───── Featured insights tile (large hero card on insights list) ─ */

.gs-feature-tile {
    position: relative;
    aspect-ratio: 21 / 9;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-always-dark-regular);
    color: var(--gs-uitk-color-text-inverse-bold);
    text-decoration: none;
    display: flex;
    align-items: flex-end;
}

@media (max-width: 767px) {
    .gs-feature-tile { aspect-ratio: 4 / 5; }
}

.gs-feature-tile__image {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.gs-feature-tile::before {
    content: "";
    position: absolute;
    inset: 0;
    background: var(--gs-uitk-overlay-hero);
    z-index: 1;
}

.gs-feature-tile__body {
    position: relative;
    z-index: 2;
    padding: var(--gs-uitk-space-7);
    max-width: 720px;
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-4);
    color: var(--gs-uitk-color-text-inverse-bold);
}

.gs-feature-tile__title {
    font: var(--gs-uitk-text-headline04-xs-screen-font);
    margin: 0;
}

@media (min-width: 768px)  { .gs-feature-tile__title { font: var(--gs-uitk-text-headline04-md-screen-font); } }
@media (min-width: 1200px) { .gs-feature-tile__title { font: var(--gs-uitk-text-headline04-lg-screen-font); } }

.gs-feature-tile__meta {
    font: var(--gs-uitk-text-label04-regular-font);
    color: var(--gs-uitk-color-text-inverse-regular);
}

/* ───── Audio / video player block (podcast detail) ──────────────── */

.gs-player {
    background: var(--gs-uitk-color-surface-neutral-subtle);
    padding: var(--gs-uitk-space-5);
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-4);
    border-left: 4px solid var(--gs-uitk-color-action-brand);
}

.gs-player__bar {
    height: 4px;
    background: var(--gs-uitk-color-surface-neutral-regular);
    position: relative;
}

.gs-player__bar::before {
    content: "";
    position: absolute;
    inset: 0 70% 0 0;
    background: var(--gs-uitk-color-action-brand);
}

.gs-player__controls {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font: var(--gs-uitk-text-label04-regular-font);
    color: var(--gs-uitk-color-text-neutral-subtle);
}

.gs-player__playbutton {
    width: 48px;
    height: 48px;
    background: var(--gs-uitk-color-action-neutral-bold);
    color: var(--gs-uitk-color-action-inverse);
    border: none;
    cursor: pointer;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--gs-uitk-border-radius-none);
}

.gs-chapter-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
}

.gs-chapter-list li {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: var(--gs-uitk-space-4);
    padding: var(--gs-uitk-space-3) 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    font: var(--gs-uitk-text-body04-regular-lg-screen-font);
    color: var(--gs-uitk-color-text-neutral-regular);
}

.gs-chapter-list li:last-child {
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}

.gs-chapter-list__time {
    font: var(--gs-uitk-text-code01-font);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

/* ───── Persona card (host / guest in podcast detail) ───────────── */

.gs-persona {
    display: grid;
    grid-template-columns: 80px 1fr;
    gap: var(--gs-uitk-space-4);
    padding: var(--gs-uitk-space-5) 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    align-items: center;
}

.gs-persona__avatar {
    width: 80px;
    height: 80px;
    background: var(--gs-uitk-color-surface-neutral-regular);
    overflow: hidden;
}

.gs-persona__name {
    font: var(--gs-uitk-text-label02-medium-font);
    color: var(--gs-uitk-color-text-neutral-bold);
    margin: 0;
}

.gs-persona__title {
    font: var(--gs-uitk-text-caption01-regular-font);
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: var(--gs-uitk-space-1) 0 0;
}

/* ───── Utility classes ──────────────────────────────────────────── */

.gs-divider {
    height: 1px;
    background: var(--gs-uitk-color-border-neutral-minimal);
    margin: 0;
    border: none;
}

.gs-stack-3 { display: flex; flex-direction: column; gap: var(--gs-uitk-space-3); }
.gs-stack-4 { display: flex; flex-direction: column; gap: var(--gs-uitk-space-4); }
.gs-stack-5 { display: flex; flex-direction: column; gap: var(--gs-uitk-space-5); }
.gs-stack-7 { display: flex; flex-direction: column; gap: var(--gs-uitk-space-7); }

.gs-text-center { text-align: center; }
```

---

## 6. HTML templates

Base: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/`

### `base.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/base.html`

```html
{% load static %}{% load gs_extras %}<!DOCTYPE html>
<html lang="en" data-runtime="{{ request.GET.runtime|default:'prism' }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}gs-reference mock{% endblock %}</title>
    <meta name="description" content="Mock of the gs.com visual design language for PRISM-side reference.">
    <link rel="stylesheet" href="{% static 'css/tokens.css' %}?v=7">
    <link rel="stylesheet" href="{% static 'css/fonts.css' %}?v=7">
    <link rel="stylesheet" href="{% static 'css/components.css' %}?v=7">
</head>
<body>

    <header class="gs-nav" role="banner">
        <div class="gs-nav__inner">
            <a href="/" class="gs-nav__logo">
                <span class="gs-nav__logo-mark">GS</span>
                <span>Goldman Sachs</span>
            </a>

            <nav class="gs-nav__items" aria-label="Primary">
                {% for item in nav_items %}
                <li class="gs-nav__item {% if item.label == active_nav %}gs-nav__item--active{% endif %}">
                    <a href="{{ item.url }}">{{ item.label }}</a>
                </li>
                {% endfor %}
            </nav>

            <div class="gs-nav__right">
                <button type="button" class="gs-nav__icon" aria-label="Search">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="7"/>
                        <line x1="16.5" y1="16.5" x2="21" y2="21"/>
                    </svg>
                </button>
                <button type="button" class="gs-nav__icon" aria-label="Menu">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="3" y1="6" x2="21" y2="6"/>
                        <line x1="3" y1="12" x2="21" y2="12"/>
                        <line x1="3" y1="18" x2="21" y2="18"/>
                    </svg>
                </button>
                <a href="#" class="gs-button gs-button--ghost-dark" style="min-height: 40px; padding-top: 0; padding-bottom: 0;">
                    Client Login
                </a>
            </div>
        </div>
    </header>

    <main>
        {% block content %}{% endblock %}
    </main>

    <section class="gs-briefings" aria-labelledby="briefings-title">
        <div class="gs-briefings__inner">
            <span class="gs-overline">Newsletter</span>
            <h2 id="briefings-title" class="gs-heading gs-heading--02">Subscribe to Briefings</h2>
            <p class="gs-body--lg">
                The signature newsletter for insights and analysis from
                across the firm. Delivered to your inbox each weekday.
            </p>
            <form class="gs-briefings__form" method="post" action="#" onsubmit="return false;">
                <input type="email" class="gs-briefings__input" placeholder="Email address" aria-label="Email address">
                <button type="submit" class="gs-briefings__submit">
                    Submit <span aria-hidden="true">&rarr;</span>
                </button>
            </form>
            <p class="gs-briefings__legal">
                By submitting this information, you agree that the
                information you are providing is subject to the
                <a href="#">privacy policy</a> and <a href="#">terms of use</a>.
                You consent to receive communications via email.
            </p>
        </div>
    </section>

    <footer class="gs-footer" role="contentinfo">
        <div class="gs-container">
            <div class="gs-footer__columns">
                <div>
                    <h3 class="gs-footer__col-title">Our Firm</h3>
                    <ul class="gs-footer__list">
                        <li><a href="/our-firm/purpose-and-values/">Purpose and Values</a></li>
                        <li><a href="#">Our People</a></li>
                        <li><a href="#">History</a></li>
                        <li><a href="#">Newsroom</a></li>
                        <li><a href="#">Sustainability</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">What We Do</h3>
                    <ul class="gs-footer__list">
                        <li><a href="/what-we-do/">Investment Banking</a></li>
                        <li><a href="/what-we-do/">Asset Management</a></li>
                        <li><a href="/what-we-do/">Wealth Management</a></li>
                        <li><a href="/what-we-do/">Markets</a></li>
                        <li><a href="/what-we-do/">Platform Solutions</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">Insights</h3>
                    <ul class="gs-footer__list">
                        <li><a href="/insights/">All Insights</a></li>
                        <li><a href="/insights/">Macroeconomics</a></li>
                        <li><a href="/insights/">Markets</a></li>
                        <li><a href="/insights/">Podcasts</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">Careers</h3>
                    <ul class="gs-footer__list">
                        <li><a href="/careers/">Careers Home</a></li>
                        <li><a href="/careers/life/">Life at the Firm</a></li>
                        <li><a href="#">Programs</a></li>
                        <li><a href="#">Search Jobs</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">Investor Relations</h3>
                    <ul class="gs-footer__list">
                        <li><a href="#">Quarterly Earnings</a></li>
                        <li><a href="#">Annual Reports</a></li>
                        <li><a href="#">Stock Information</a></li>
                        <li><a href="#">Events</a></li>
                    </ul>
                </div>
            </div>

            <div class="gs-footer__bottom">
                <span>&copy; gs-reference mock. Visual reference only; not a Goldman Sachs property.</span>
                <ul class="gs-footer__bottom-links">
                    <li><a href="#">Privacy &amp; Cookies</a></li>
                    <li><a href="#">Terms of Use</a></li>
                    <li><a href="#">Accessibility</a></li>
                    <li><a href="#">Worldwide</a></li>
                </ul>
            </div>
        </div>
    </footer>
</body>
</html>
```

---
### `careers.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/careers.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Careers — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-hero">
    <div class="gs-hero__image">{% gs_placeholder tint=hero.image_tint aspect="16x9" label=hero.title %}</div>
    <div class="gs-hero__overlay"></div>
    <div class="gs-hero__content">
        <div class="gs-hero__text">
            <span class="gs-overline gs-overline--inverse">{{ hero.eyebrow }}</span>
            <h1 class="gs-headline gs-headline--01 gs-headline--inverse">{{ hero.title }}</h1>
            <p class="gs-body--lg gs-body--inverse">{{ hero.subtitle }}</p>
        </div>
        <a href="{{ hero.cta_url }}" class="gs-button gs-button--ghost-light gs-hero__cta">
            {{ hero.cta_label }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
        </a>
    </div>
</section>

<nav class="gs-tabs" aria-label="Section tabs">
    <ul class="gs-tabs__list">
        {% for tab in tabs %}
        <li class="gs-tabs__item {% if tab.active %}gs-tabs__item--active{% endif %}">
            <a href="{{ tab.url }}">{{ tab.label }}</a>
        </li>
        {% endfor %}
    </ul>
</nav>

{# Culture two-up #}
<section class="gs-section">
    <div class="gs-container">
        <div class="gs-two-up">
            <div class="gs-two-up__media">{% gs_placeholder tint=culture_two_up.image_tint aspect="1x1" label=culture_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ culture_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ culture_two_up.title }}</h2>
                <p class="gs-body--lg">{{ culture_two_up.body }}</p>
                <a href="{{ culture_two_up.cta_url }}" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ culture_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{# Featured roles 4-up #}
<section class="gs-section gs-section--subtle" id="find-your-place">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">Featured Roles</span>
            <h2 class="gs-headline gs-headline--04">Your Pursuit of Exceptional Starts Here</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for role in featured_roles %}
            <a href="#" class="gs-card">
                <div class="gs-card__image">{% gs_placeholder tint=role.image_tint aspect="16x9" label=role.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ role.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ role.title }}</h3>
                    <p class="gs-body--sm">{{ role.body }}</p>
                    <span class="gs-card__cta">View Roles <span aria-hidden="true">&rarr;</span></span>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# Path tiles (text-only cards) #}
<section class="gs-section">
    <div class="gs-container">
        <div class="gs-grid gs-grid--4">
            {% for tile in path_tiles %}
            <div class="gs-card gs-card--text">
                <div class="gs-card__body">
                    <h3 class="gs-card__title">{{ tile.title }}</h3>
                    <p class="gs-body">{{ tile.body }}</p>
                    <a href="#" class="gs-card__cta">Explore <span aria-hidden="true">&rarr;</span></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</section>

{# Tagline quote #}
<section class="gs-section--inverse">
    <p class="gs-quote-callout" style="color: var(--gs-uitk-color-text-inverse-bold);">{{ tagline_quote }}</p>
</section>

{# Three two-ups alternating #}
{% for tu in two_ups %}
<section class="gs-section {% if forloop.counter|divisibleby:2 %}gs-section--subtle{% endif %}">
    <div class="gs-container">
        <div class="gs-two-up {% if tu.reverse %}gs-two-up--reverse{% endif %}">
            <div class="gs-two-up__media">{% gs_placeholder tint=tu.image_tint aspect="1x1" label=tu.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ tu.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ tu.title }}</h2>
                <p class="gs-body--lg">{{ tu.body }}</p>
                <a href="{{ tu.cta_url }}" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ tu.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>
{% endfor %}

{# Our Firm — link cards (no image) #}
<section class="gs-section">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">Our Firm</span>
            <h2 class="gs-headline gs-headline--04">Where You Could Land</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for d in our_firm_links %}
            <div class="gs-card gs-card--text">
                <div class="gs-card__body">
                    <h3 class="gs-card__title">{{ d.title }}</h3>
                    <p class="gs-body">{{ d.body }}</p>
                    <a href="#" class="gs-card__cta">Learn More <span aria-hidden="true">&rarr;</span></a>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</section>

{% endblock %}
```

---
### `careers_life.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/careers_life.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Life at the Firm — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-page-header">
    <div class="gs-page-header__inner">
        <span class="gs-overline">{{ page_eyebrow }}</span>
        <h1 class="gs-headline gs-headline--02">{{ page_title }}</h1>
        <p class="gs-subtitle--lg" style="max-width: 720px;">{{ page_subtitle }}</p>
        <a href="#" class="gs-page-header__share" aria-label="Share">
            Share <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg>
        </a>
    </div>
</section>

{% for tu in two_ups %}
<section class="gs-section {% if forloop.counter|divisibleby:2 %}gs-section--subtle{% endif %}">
    <div class="gs-container">
        <div class="gs-two-up {% if tu.reverse %}gs-two-up--reverse{% endif %}">
            <div class="gs-two-up__media">{% gs_placeholder tint=tu.image_tint aspect="1x1" label=tu.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ tu.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ tu.title }}</h2>
                <p class="gs-body--lg">{{ tu.body }}</p>
                <a href="#" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ tu.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>
{% endfor %}

<section class="gs-section">
    <div class="gs-container">
        <div class="gs-two-up gs-two-up--reverse">
            <div class="gs-two-up__media">{% gs_placeholder tint=alumni_two_up.image_tint aspect="1x1" label=alumni_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ alumni_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ alumni_two_up.title }}</h2>
                <p class="gs-body--lg">{{ alumni_two_up.body }}</p>
                <a href="#" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ alumni_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{% endblock %}
```

---
### `home.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/home.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Home — gs-reference mock{% endblock %}

{% block content %}

{# ─── Hero (DNA §8.4) ───────────────────────────────────────────── #}
<section class="gs-hero">
    <div class="gs-hero__image">{% gs_placeholder tint=hero.image_tint aspect="16x9" label=hero.title %}</div>
    <div class="gs-hero__overlay"></div>
    <div class="gs-hero__content">
        <div class="gs-hero__text">
            <span class="gs-overline gs-overline--inverse">{{ hero.eyebrow }}</span>
            <h1 class="gs-headline gs-headline--01 gs-headline--inverse">{{ hero.title }}</h1>
            <p class="gs-body--lg gs-body--inverse">{{ hero.subtitle }}</p>
        </div>
        <a href="{{ hero.cta_url }}" class="gs-button gs-button--ghost-light gs-hero__cta">
            {{ hero.cta_label }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
        </a>
    </div>
</section>

{# ─── Tab strip (DNA §8.7) ──────────────────────────────────────── #}
<nav class="gs-tabs" aria-label="Section tabs">
    <ul class="gs-tabs__list">
        {% for tab in tabs %}
        <li class="gs-tabs__item {% if tab.active %}gs-tabs__item--active{% endif %}">
            <a href="{{ tab.url }}">{{ tab.label }}</a>
        </li>
        {% endfor %}
    </ul>
</nav>

{# ─── Deal spotlights (overlay-card variant) ────────────────────── #}
<section class="gs-section" id="stay-informed">
    <div class="gs-container">
        <div class="gs-grid gs-grid--2">
            {% for deal in deal_spotlights %}
            <a href="#" class="gs-card gs-card--overlay">
                <div class="gs-card__image">{% gs_placeholder tint=deal.image_tint aspect="16x9" label=deal.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ deal.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ deal.title }}</h3>
                    <p>{{ deal.body }}</p>
                    <span class="gs-card__cta">{{ deal.cta }} <span aria-hidden="true">&rarr;</span></span>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── What We Do (4-up cards) ───────────────────────────────────── #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">What We Do</span>
            <h2 class="gs-headline gs-headline--04">Delivering for Our Clients</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for card in what_we_do_cards %}
            <a href="/what-we-do/" class="gs-card">
                <div class="gs-card__image">{% gs_placeholder tint=card.image_tint aspect="16x9" label=card.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ card.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ card.title }}</h3>
                    <p class="gs-body--sm">{{ card.body }}</p>
                    <span class="gs-card__cta">Learn More <span aria-hidden="true">&rarr;</span></span>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── Insights two-up ───────────────────────────────────────────── #}
<section class="gs-section">
    <div class="gs-container">
        <div class="gs-two-up">
            <div class="gs-two-up__media">{% gs_placeholder tint=insights_two_up.image_tint aspect="1x1" label=insights_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ insights_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ insights_two_up.title }}</h2>
                <p class="gs-body--lg">{{ insights_two_up.body }}</p>
                <a href="{{ insights_two_up.cta_url }}" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ insights_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{# ─── Careers two-up (reverse) ──────────────────────────────────── #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <div class="gs-two-up gs-two-up--reverse">
            <div class="gs-two-up__media">{% gs_placeholder tint=careers_two_up.image_tint aspect="1x1" label=careers_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ careers_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ careers_two_up.title }}</h2>
                <p class="gs-body--lg">{{ careers_two_up.body }}</p>
                <a href="{{ careers_two_up.cta_url }}" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ careers_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{# ─── Stats row (DNA §8.6) ──────────────────────────────────────── #}
<section class="gs-section">
    <div class="gs-container">
        <div class="gs-stat-row">
            {% for stat in stats %}
            <div class="gs-stat">
                <span class="gs-stat__numeral">{{ stat.numeral }}<sup class="gs-stat__numeral-sup">{{ stat.footnote_n }}</sup></span>
                <p class="gs-stat__caption">{{ stat.caption }}</p>
            </div>
            {% endfor %}
        </div>
        <div style="margin-top: var(--gs-uitk-space-7); padding-top: var(--gs-uitk-space-5); border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);">
            {% for fn in footnotes %}
            <p class="gs-body--sm" style="color: var(--gs-uitk-color-text-neutral-minimal); margin-bottom: var(--gs-uitk-space-2);">{{ fn }}</p>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── Our Firm two-up ───────────────────────────────────────────── #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <div class="gs-two-up">
            <div class="gs-two-up__media">{% gs_placeholder tint=our_firm_two_up.image_tint aspect="1x1" label=our_firm_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ our_firm_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ our_firm_two_up.title }}</h2>
                <p class="gs-body--lg">{{ our_firm_two_up.body }}</p>
                <a href="{{ our_firm_two_up.cta_url }}" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ our_firm_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{% endblock %}
```

---
### `insights_article.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/insights_article.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}{{ article.title }} — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-hero" style="aspect-ratio: 21 / 9; min-height: 360px;">
    <div class="gs-hero__image">{% gs_placeholder tint=article.image_tint aspect="21x9" label=article.title %}</div>
    <div class="gs-hero__overlay"></div>
    <div class="gs-hero__content">
        <div class="gs-hero__text">
            <span class="gs-overline gs-overline--inverse">{{ article.eyebrow }}</span>
            <h1 class="gs-headline gs-headline--03 gs-headline--inverse">{{ article.title }}</h1>
        </div>
    </div>
</section>

<section style="background: var(--gs-uitk-color-surface-neutral-minimal);">
    <div class="gs-byline">
        <ul class="gs-byline__authors">
            {% for author in article.authors %}
            <li>
                <span class="gs-byline__author-name">{{ author.name }}</span>
                <span class="gs-byline__author-title"> — {{ author.title }}</span>
            </li>
            {% endfor %}
        </ul>
        <div class="gs-byline__meta">
            <span>{{ article.date }} · {{ article.read_time }}</span>
            <a href="#" class="gs-page-header__share">
                Share <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg>
            </a>
        </div>
    </div>
</section>

<article class="gs-article-body">

    <p class="gs-body--lg" style="font-style: italic; color: var(--gs-uitk-color-text-neutral-bold);">{{ article.intro }}</p>

    <h2>Executive Summary</h2>
    <p>{{ article.exec_summary_body }}</p>

    <ol class="gs-numbered-list">
        {% for point in article.numbered_points %}
        <li class="gs-numbered-list__item">
            <span class="gs-numbered-list__numeral">{{ forloop.counter }}</span>
            <p class="gs-numbered-list__body">{{ point }}</p>
        </li>
        {% endfor %}
    </ol>

    {% for sec in article.sections %}
    <h2>{{ sec.heading }}</h2>
    <p>{{ sec.body }}</p>
    {% if sec.pull_quote %}
    <blockquote class="gs-pull-quote">{{ sec.pull_quote }}</blockquote>
    {% endif %}
    {% endfor %}

    <div class="gs-footnotes">
        {% for fn in article.footnotes %}
        <p>{{ fn }}</p>
        {% endfor %}
    </div>

</article>

{% endblock %}
```

---
### `insights_list.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/insights_list.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Insights — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-page-header">
    <div class="gs-page-header__inner">
        <span class="gs-overline">{{ page_eyebrow }}</span>
        <h1 class="gs-headline gs-headline--02">{{ page_title }}</h1>
        <p class="gs-subtitle--lg" style="max-width: 720px;">{{ page_subtitle }}</p>
    </div>
</section>

{# Featured tile #}
<section class="gs-section gs-section--tight">
    <div class="gs-container">
        <a href="{{ featured.url }}" class="gs-feature-tile">
            <div class="gs-feature-tile__image">{% gs_placeholder tint=featured.image_tint aspect="21x9" label=featured.title %}</div>
            <div class="gs-feature-tile__body">
                <span class="gs-overline gs-overline--inverse">{{ featured.eyebrow }}</span>
                <h2 class="gs-feature-tile__title">{{ featured.title }}</h2>
                <span class="gs-feature-tile__meta">{{ featured.date }}</span>
            </div>
        </a>
    </div>
</section>

{# The Latest #}
<section class="gs-section">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">The Latest</span>
            <h2 class="gs-headline gs-headline--04">Recent Analysis</h2>
        </header>
        <div class="gs-grid gs-grid--3">
            {% for item in latest %}
            <a href="{{ item.url }}" class="gs-card">
                <div class="gs-card__image">{% gs_placeholder tint=item.image_tint aspect="16x9" label=item.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ item.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ item.title }}</h3>
                    <div style="display: flex; align-items: center; gap: var(--gs-uitk-space-3);">
                        <span class="gs-format-chip">{{ item.format }}</span>
                        <span class="gs-body--sm" style="color: var(--gs-uitk-color-text-neutral-minimal);">{{ item.date }}</span>
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# In Focus #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">{{ in_focus_eyebrow }}</span>
            <h2 class="gs-headline gs-headline--04">In Depth</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for item in in_focus_cards %}
            <a href="/insights/article/" class="gs-card">
                <div class="gs-card__image">{% gs_placeholder tint=item.image_tint aspect="16x9" label=item.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ item.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ item.title }}</h3>
                    <div style="display: flex; align-items: center; gap: var(--gs-uitk-space-3);">
                        <span class="gs-format-chip">{{ item.format }}</span>
                        <span class="gs-body--sm" style="color: var(--gs-uitk-color-text-neutral-minimal);">{{ item.date }}</span>
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{% endblock %}
```

---
### `insights_podcast.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/insights_podcast.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}{{ article.title }} — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-hero" style="aspect-ratio: 21 / 9; min-height: 360px;">
    <div class="gs-hero__image">{% gs_placeholder tint=article.image_tint aspect="21x9" label=article.title %}</div>
    <div class="gs-hero__overlay"></div>
    <div class="gs-hero__content">
        <div class="gs-hero__text">
            <span class="gs-overline gs-overline--inverse">{{ article.eyebrow }}</span>
            <h1 class="gs-headline gs-headline--03 gs-headline--inverse">{{ article.title }}</h1>
            <p class="gs-body gs-body--inverse">{{ article.date }} · {{ article.duration }}</p>
        </div>
    </div>
</section>

<section class="gs-section">
    <div class="gs-container">
        <div class="gs-two-up">
            <div class="gs-two-up__content">
                <span class="gs-overline">Now Playing</span>
                <h2 class="gs-heading gs-heading--02">Episode Summary</h2>
                <p class="gs-body--lg">{{ article.summary }}</p>

                <div class="gs-player">
                    <div style="display: flex; align-items: center; gap: var(--gs-uitk-space-4);">
                        <button type="button" class="gs-player__playbutton" aria-label="Play">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><polygon points="6,4 20,12 6,20"/></svg>
                        </button>
                        <div style="flex: 1;">
                            <div class="gs-player__bar"></div>
                            <div class="gs-player__controls">
                                <span>09:30</span><span>{{ article.duration }}</span>
                            </div>
                        </div>
                    </div>
                </div>

                <h3 class="gs-heading gs-heading--03" style="margin-top: var(--gs-uitk-space-7);">Chapter Markers</h3>
                <ul class="gs-chapter-list">
                    {% for ch in article.chapter_markers %}
                    <li>
                        <span class="gs-chapter-list__time">{{ ch.time }}</span>
                        <span>{{ ch.label }}</span>
                    </li>
                    {% endfor %}
                </ul>
            </div>

            <aside class="gs-two-up__content">
                <span class="gs-overline">Featured Voices</span>

                <div class="gs-persona">
                    <div class="gs-persona__avatar">{% gs_placeholder tint="navy" aspect="1x1" label=article.host.name %}</div>
                    <div>
                        <p class="gs-persona__name">{{ article.host.name }}</p>
                        <p class="gs-persona__title">{{ article.host.title }}</p>
                    </div>
                </div>

                <div class="gs-persona">
                    <div class="gs-persona__avatar">{% gs_placeholder tint="purple" aspect="1x1" label=article.guest.name %}</div>
                    <div>
                        <p class="gs-persona__name">{{ article.guest.name }}</p>
                        <p class="gs-persona__title">{{ article.guest.title }}</p>
                    </div>
                </div>

                <div style="margin-top: var(--gs-uitk-space-5);">
                    <span class="gs-overline">Subscribe On</span>
                    <ul class="gs-link-list" style="margin-top: var(--gs-uitk-space-3);">
                        <li><a href="#">Apple Podcasts <span aria-hidden="true">&rarr;</span></a></li>
                        <li><a href="#">Spotify <span aria-hidden="true">&rarr;</span></a></li>
                        <li><a href="#">RSS Feed <span aria-hidden="true">&rarr;</span></a></li>
                    </ul>
                </div>
            </aside>
        </div>
    </div>
</section>

{% endblock %}
```

---
### `purpose.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/purpose.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Our Purpose — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-page-header gs-page-header--centered">
    <div class="gs-page-header__inner">
        <span class="gs-overline">{{ page_eyebrow }}</span>
        <h1 class="gs-headline gs-headline--02">{{ page_title }}</h1>
        <p class="gs-subtitle--lg" style="max-width: 720px;">{{ page_subtitle }}</p>
    </div>
</section>

{# Values 4-up text-only cards #}
<section class="gs-section">
    <div class="gs-container">
        <header class="gs-section-heading gs-text-center" style="align-items: center;">
            <span class="gs-overline">Our Values</span>
            <h2 class="gs-headline gs-headline--04">Four Principles That Define Us</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for v in values %}
            <div class="gs-card gs-card--text">
                <div class="gs-card__body">
                    <h3 class="gs-card__title">{{ v.title }}</h3>
                    <p class="gs-body">{{ v.body }}</p>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>
</section>

{# Principles two-up #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <div class="gs-two-up">
            <div class="gs-two-up__media">{% gs_placeholder tint=principles_two_up.image_tint aspect="1x1" label=principles_two_up.title %}</div>
            <div class="gs-two-up__content">
                <span class="gs-overline">{{ principles_two_up.eyebrow }}</span>
                <h2 class="gs-headline gs-headline--04">{{ principles_two_up.title }}</h2>
                <p class="gs-body--lg">{{ principles_two_up.body }}</p>
                <a href="#" class="gs-button gs-button--ghost-dark gs-two-up__cta">
                    {{ principles_two_up.cta }} <span class="gs-button__arrow" aria-hidden="true">&rarr;</span>
                </a>
            </div>
        </div>
    </div>
</section>

{# Ethics link list #}
<section class="gs-section">
    <div class="gs-container" style="max-width: 960px;">
        <header class="gs-section-heading">
            <span class="gs-overline">Business Standards</span>
            <h2 class="gs-headline gs-headline--04">Conduct &amp; Governance</h2>
            <p class="gs-body--lg">
                The standards and frameworks that govern how we operate
                and the public commitments we make as an institution.
            </p>
        </header>
        <ul class="gs-link-list">
            {% for link in ethics_links %}
            <li><a href="#">{{ link.title }} <span aria-hidden="true">&rarr;</span></a></li>
            {% endfor %}
        </ul>
    </div>
</section>

{# Discover cards #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">Discover</span>
            <h2 class="gs-headline gs-headline--04">Explore More</h2>
        </header>
        <div class="gs-grid gs-grid--2">
            {% for card in discover_cards %}
            <a href="#" class="gs-card">
                <div class="gs-card__image">{% gs_placeholder tint=card.image_tint aspect="16x9" label=card.title %}</div>
                <div class="gs-card__body">
                    <span class="gs-overline">{{ card.eyebrow }}</span>
                    <h3 class="gs-card__title">{{ card.title }}</h3>
                    <p class="gs-body">{{ card.body }}</p>
                    <span class="gs-card__cta">Read More <span aria-hidden="true">&rarr;</span></span>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{% endblock %}
```

---
### `what_we_do.html`

Path: `gs_reference-payload/ai_development/mysite_gs/gsapp/templates/gsapp/what_we_do.html`

```html
{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}What We Do — gs-reference mock{% endblock %}

{% block content %}

<section class="gs-page-header">
    <div class="gs-page-header__inner">
        <span class="gs-overline">{{ page_eyebrow }}</span>
        <h1 class="gs-headline gs-headline--02">{{ page_title }}</h1>
        <p class="gs-subtitle--lg" style="max-width: 720px;">{{ page_subtitle }}</p>
        <a href="#" class="gs-page-header__share" aria-label="Share">
            Share <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/></svg>
        </a>
    </div>
</section>

<nav class="gs-tabs" aria-label="Sub-pillar tabs">
    <ul class="gs-tabs__list">
        {% for pillar in pillars %}
        <li class="gs-tabs__item {% if pillar.active %}gs-tabs__item--active{% endif %}">
            <a href="#{{ pillar.id }}">{{ pillar.label }}</a>
        </li>
        {% endfor %}
    </ul>
</nav>

{% for sec in pillar_sections %}
<section class="gs-pillar-section" id="{{ sec.id }}">
    <div class="gs-pillar-section__inner">
        <header class="gs-pillar-section__heading">
            <span class="gs-overline">{{ sec.eyebrow }}</span>
            <h2 class="gs-heading gs-heading--01">{{ sec.title }}</h2>
            <p class="gs-body--lg">{{ sec.body }}</p>
        </header>

        <div class="gs-pillar-section__links">
            {% for link in sec.links %}
            <a href="#" class="gs-pillar-link">
                <h3 class="gs-pillar-link__title">{{ link.label }} <span aria-hidden="true">&rarr;</span></h3>
                <p class="gs-pillar-link__body">{{ link.body }}</p>
            </a>
            {% endfor %}
        </div>
    </div>
</section>
{% endfor %}

{% endblock %}
```

---
