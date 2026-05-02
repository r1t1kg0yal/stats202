---
session: Portal fonts inventory + Python font-stack audit — what's in ai_development/mysite/fonts/ after the 2026-05-02 GS 2024 rebrand TTF drop, and what font-related Python packages / Django wiring / altair+echarts defaults are in place today
sent: 2026-05-02
reply: projects/frontend/dev/scans/2026-05-02_fonts_and_python_font_stack_reply.md
reply_folded_into:
  - projects/frontend/dev/specs/design_system.md §1.1 (real filenames), §1.2 (@font-face block — collapse variable vs static based on reply §1), §1.3 (font-mono token decision — system `ui-monospace` vs installed Roboto Mono if §3 shows it's loaded), §8 (gaps: matplotlib discovery, PIL freetype, weasyprint/reportlab availability)
  - projects/frontend/README.md ("Design DNA" section — confirm the font-loading approach)
  - projects/frontend/dev/notes.md (CREATE — notes on Python font-stack constraints discovered from reply §4–§7; informs future altair/echarts font-swap work)
  - staging/README.md (frontend row — bump from "v0 design system" toward "v0 design system + font stack audited" once filenames land)
  - prism/ — likely a new short curated doc `prism/portal-fonts.md` (or a §10.6 addition to `prism/dashboards-portal.md`) once §2/§3/§8 reveal the current Django staticfiles story for fonts
status: USED
---

Title: Portal fonts + Python font-stack — inventory and integration points

The Cursor staging side has `projects/frontend/` in scoping with a v0
design system (`projects/frontend/dev/specs/design_system.md` — colors,
fonts, type scale, component primitives). On 2026-05-02 the user
dropped GS 2024 rebrand TTFs (GS Sans / GS Sans Condensed / GS Serif)
into `ai_development/mysite/fonts/` in PRISM. The design-system spec's
`@font-face` block in §1.2 has `<TO_FILL>` placeholders waiting on
real filenames.

This round-trip covers three surfaces that all bear on the portal's
font story end-to-end:

- **A.** The files themselves in `ai_development/mysite/fonts/` —
  inventory, variable-axis vs static cuts, license artifacts, git
  status.
- **B.** How Django wires `/static/fonts/...` today — `settings.py`
  `STATICFILES_DIRS` / `STATIC_ROOT` / `STATIC_URL`, existing
  `@font-face` rules in portal CSS, the portal `base.html` head
  section, `collectstatic` vs direct-serve.
- **C.** Python-side font capabilities at runtime — what matplotlib,
  Pillow, fontTools, weasyprint, and reportlab can do with these
  TTFs once they're on disk, and what the altair + echarts pipelines
  do with `font-family` strings TODAY (so the staging side knows
  what it's swapping away from).

Use `list_ai_repo` (for source files) and `execute_analysis_script`
(for runtime introspection — importing matplotlib, listing
`FontManager.ttflist`, reading package versions, calling
`fontTools.ttLib.TTFont`) to introspect. Reply with verbatim source
in fenced code blocks and exact paths. Mirror the section structure
below — each numbered section in your reply answers the
same-numbered section here. No paraphrase, no summary.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it. This is NOT a frictions report — it is a
minimal coverage note.

---

## 1. `ai_development/mysite/fonts/` inventory

1.1 List every file under `ai_development/mysite/fonts/` (recursive
    if there are subdirectories). For each file, report:

```
<filename>    <bytes>    <sha256 first 8 chars>
```

Sort by filename. If the directory does not exist or is empty, say
so explicitly.

1.2 For each `.ttf` file, use `fontTools.ttLib.TTFont(<path>)` (or
    equivalent) to extract and report:

- The `name` table's **family name** (NameID 1), **subfamily name**
  (NameID 2), **typographic family** (NameID 16 if present),
  **typographic subfamily** (NameID 17 if present), **full name**
  (NameID 4), **PostScript name** (NameID 6)
- Whether it's a **variable font** — check for the `fvar` table's
  presence. If yes, list every axis tag (`wght`, `wdth`, `slnt`,
  `ital`, etc.) with its `minValue`, `defaultValue`, `maxValue`.
- **Weight class** from the `OS/2` table (`usWeightClass`)
- Whether **italic** — `OS/2.fsSelection` bit 0, plus
  `post.italicAngle` for non-zero

Format the output as one table row per TTF:

```
filename                family              subfamily    variable   axes              weightClass   italic
gs-sans-variable.ttf    "GS Sans"           "Regular"    yes        wght 100-900      400           no
...
```

The output I need: a mapping from every TTF filename to the
(family, weight-range, style) it actually covers. This drives whether
the design_system.md `@font-face` block uses variable-axis
declarations or per-cut static declarations, and whether we need
`format("truetype-variations")` or `format("truetype")`.

1.3 Are there any **non-TTF files** in that directory — README,
    LICENSE, NOTICE, OFL.txt, design-brief PDF, font-spec doc,
    `manifest.json`? If yes, paste each verbatim in a fenced code
    block.

1.4 Is `ai_development/mysite/fonts/` **tracked in git**? Check
    whether the path matches any pattern in the repo root
    `.gitignore` / `.gitattributes`. Paste the relevant lines. If
    tracked, paste `git log --oneline -n 5 -- ai_development/mysite/fonts/`
    so I can see the drop commit from 2026-05-02.

---

## 2. Django static-fonts wiring — settings.py + staticfiles + collectstatic

2.1 Paste the current `STATICFILES_DIRS`, `STATIC_ROOT`, `STATIC_URL`,
    and any relevant `STATICFILES_FINDERS` lines from
    `mysite/settings.py` (confirm the exact path — `ai_development/mysite/settings.py`
    or elsewhere).

2.2 Is `ai_development/mysite/fonts/` currently referenced in
    `STATICFILES_DIRS`? If yes, what URL prefix does it map to
    (`/static/fonts/`, `/fonts/`, something else)? If no, how
    would a template currently reference one of those TTF files
    (e.g., does Django serve them via a FileResponse in a view,
    or are they not yet reachable at all from the browser)?

2.3 Is `collectstatic` part of the PRISM deploy path, or does the
    Django dev server serve statics live from `mysite/fonts/`?
    If there's a build step / Makefile target / CI job that runs
    `collectstatic`, paste the relevant fragment.

2.4 What is `DEBUG` set to in production? (If `DEBUG=False`,
    Django refuses to serve statics and they must go through
    `collectstatic` + an upstream like nginx / WhiteNoise. This
    decides whether the staging mirror needs a `collectstatic`
    target too.) Paste the relevant `settings.py` lines.

---

## 3. Existing `@font-face` declarations and `font-family` usage in portal CSS

3.1 List every `.css` file under `ai_development/mysite/**/static/`
    (or wherever the portal CSS lives). For each file, grep for
    `@font-face`, `font-family:`, and `url\(.*\.(ttf|woff2?|otf)\)`
    — paste each matching declaration verbatim with its source
    `<filepath>:<line>`.

3.2 Paste the current
    `ai_development/mysite/news/templates/news/base.html`
    head section verbatim (from `<head>` through `</head>`) so I
    can see which CSS bundles, JS bundles, and external font URLs
    are loaded on every portal page today.

3.3 If the portal currently loads fonts from any external source
    (Google Fonts `fonts.googleapis.com`, Goldman Sachs
    `cdn.gs.com/fonts/`, or any other CDN), list every such URL
    referenced from `base.html` or its linked CSS files.

3.4 What is the portal's **default body font-family** today? Grep
    the portal CSS for `body\s*\{` (or the equivalent root
    selector) and paste the declaration verbatim. I want to see
    what GS Sans is replacing.

3.5 Are there any `dashboard.html`-embedded CSS blocks (served by
    `user_dashboard_detail` / `community_dashboard_detail` /
    `observatory_dashboard_detail`) that set their own `font-family`
    and therefore would NOT inherit from `base.html`? Paste the
    relevant snippet from `compile_dashboard`'s HTML-writing code
    in `ai_development/dashboards/*.py` if so.

---

## 4. matplotlib font discovery — Altair's static-PNG pipeline

Altair charts (`mcp/utils/chart_functions.py`) render to PNG via
matplotlib. For PRISM-generated PNGs to carry `GS Sans` text instead
of matplotlib's default DejaVu Sans, matplotlib needs to discover
the TTFs and the chart code needs to set them as the active font.

4.1 Run inside `execute_analysis_script`:

```python
import matplotlib
from matplotlib import font_manager
print("matplotlib version:", matplotlib.__version__)
print("matplotlib cachedir:", matplotlib.get_cachedir())

ttflist = font_manager.fontManager.ttflist
print(f"Total registered TTFs in fontManager: {len(ttflist)}")

gs_like = [f for f in ttflist if "GS" in f.name or "Goldman" in f.name]
print(f"\nGS-like fonts currently in fontManager: {len(gs_like)}")
for f in gs_like:
    print(f"  name={f.name!r}  style={f.style}  weight={f.weight}  stretch={f.stretch}  fname={f.fname}")
```

Paste the full stdout. This tells me whether matplotlib **already
sees the new GS TTFs** (perhaps the user registered them
explicitly) or whether they're invisible to matplotlib today.

4.2 Paste the output of:

```python
from matplotlib import font_manager
import pprint
pprint.pprint(font_manager.findSystemFonts())
```

If `ai_development/mysite/fonts/` (or any subdirectory of it) is in
this list, matplotlib will pick the GS TTFs up on the next
`_load_fontmanager()` call. If not, matplotlib won't discover them
until we explicitly call
`font_manager.fontManager.addfont(path)` somewhere. That's an
actionable outcome.

4.3 What does `mcp/utils/chart_functions.py` currently set for
    `rcParams["font.family"]`, `rcParams["font.sans-serif"]`,
    `rcParams["font.serif"]`, or matplotlib `FontProperties` /
    `fontname=...` kwargs? Grep the file and paste the first ~10
    hits with `<filepath>:<line>`:

```
rg -n 'font\.family|font\.sans-serif|font\.serif|FontProperties|fontname\s*=|rcParams\[' mcp/utils/chart_functions.py mcp/utils/chart_functions_studio.py
```

4.4 If no GS font is in matplotlib's registry today (§4.1 empty),
    what is the canonical way in this codebase to register a new
    TTF path at import time? Is there a helper like
    `register_font(path)` in `mcp/utils/`, or an `.rcfile` override,
    or a `matplotlibrc` shipped with the repo? Paste whichever
    pattern exists — or confirm explicitly that no such helper
    exists yet and a new one would need to be added.

---

## 5. Pillow / PIL freetype availability

Some chart annotations (and some report / export code paths) write
text via PIL. PIL requires libfreetype support at build time to
render TTF text.

5.1 Run inside `execute_analysis_script`:

```python
from PIL import Image, features
print("Pillow version:", Image.__version__)
print("libfreetype available:", features.check("freetype2"))
try:
    print("libfreetype version:", features.version("freetype2"))
except Exception as e:
    print("libfreetype version check raised:", e)
```

Paste stdout. If `freetype2` is `False`, Pillow cannot render
any TTF and would need a rebuild / re-install. If `True`, any path
Pillow can read (`ImageFont.truetype(path, size)`) resolves.

5.2 Grep `mcp/utils/`, `mcp/clients/`, `ai_development/dashboards/`,
    and `mysite/` for `ImageFont.truetype` usage:

```
rg -n 'ImageFont\.truetype|ImageFont\.load' mcp/ ai_development/dashboards/ mysite/
```

Paste each hit with `<filepath>:<line>`. I want to see where PIL
currently loads a font and with what path — so I can tell if the
GS TTFs need to be plumbed through there too.

---

## 6. fontTools / weasyprint / reportlab / cairo — other font-aware packages

6.1 Run inside `execute_analysis_script`:

```python
import importlib.metadata as im
packages = [
    "fonttools",
    "weasyprint",
    "xhtml2pdf",
    "reportlab",
    "cairocffi",
    "pycairo",
    "cairosvg",
    "pdfkit",
    "wkhtmltopdf-pack",
    "pyppeteer",
    "playwright",
]
for pkg in packages:
    try:
        print(f"{pkg:20s} {im.version(pkg)}")
    except im.PackageNotFoundError:
        print(f"{pkg:20s} NOT INSTALLED")
```

Paste stdout. This is the audit of what PRISM can do today for
HTML-to-PDF / SVG-to-PNG / PDF-with-custom-fonts workflows.

6.2 Does PRISM use ANY of these libraries today? Specifically:

- Is there a **PDF export path** anywhere in the codebase
  (reports, emails, whitepapers, dashboards)? If yes, paste the
  file path + the font-setup fragment.
- Is there a **server-side HTML-to-PDF** path for rendering
  dashboards as PDFs? If yes, same.
- Is there a **headless browser** path (Playwright, pyppeteer)
  that could snapshot a rendered portal page with GS fonts?

Grep:

```
rg -n 'WeasyPrint|weasyprint|HTML\(|ReportLab|reportlab|FPDF|xhtml2pdf|playwright\.sync_api|async_playwright|pyppeteer' mcp/ ai_development/
```

Paste the first 10 hits if any — I want to know the full
font-dependent output surface, not just portal HTML.

---

## 7. Altair + echarts current `font-family` strategy

7.1 **Altair side.** In `mcp/utils/chart_functions.py` and
    `chart_functions_studio.py`, grep for the font-config kwargs
    and rcParams:

```
rg -n 'font\.family|font\.sans-serif|sans-serif|fontname|FontProperties|set_fontname' mcp/utils/chart_functions.py mcp/utils/chart_functions_studio.py
```

Paste the first ~10 hits with `<filepath>:<line>`. I want to see
EXACTLY what font the altair-generated PNGs render with today, so
the staging side knows the delta when it swaps to GS Sans.

7.2 **Echarts side.** In `ai_development/dashboards/*.py` (the
    `compile_dashboard` pipeline), grep for:

```
rg -n 'fontFamily|font_family|"font-family|textStyle' ai_development/dashboards/
```

Paste the first ~10 hits with `<filepath>:<line>`. Echarts sets
its `font-family` via its JS-side `textStyle` / `title.textStyle`
config; I want to see what value is baked in today.

7.3 Echarts dashboards are self-contained HTML artefacts (per
    `dashboards.md`). Where does the `font-family` for embedded
    chart labels actually come from at render time —

    (a) baked into the echarts JS config via `textStyle`
        (independent of the surrounding portal CSS), OR
    (b) inherited from `<body>` / the dashboard template's CSS
        (meaning the dashboard IS affected by portal-wide CSS
        changes)?

    Paste the one code fragment that decides this for a generated
    dashboard — the `textStyle` block in `echart_dashboard.py` or
    `rendering.py` if option (a), or the `<body>` CSS block in
    the dashboard template if option (b).

---

## 8. License / git policy for proprietary GS fonts

The 2024 rebrand TTFs (GS Sans / GS Sans Condensed / GS Serif) are
**internal GS fonts**, not publicly licensed like the 2020 Goldman
Sans family. This matters for the staging mirror: the staging side
needs to know whether to check these fonts into
`projects/frontend/ai_development/mysite/fonts/` (the stub mirror)
or gitignore them there.

8.1 Is there a **NOTICE file, LICENSE file, or intranet link**
    describing the redistribution policy for these fonts — inside
    `ai_development/mysite/fonts/`, or at the repo root
    (`LICENSE.md`, `NOTICE.md`, `FONTS.md`, `fonts/README.md`)?
    Paste verbatim.

8.2 Are `ai_development/mysite/fonts/*.ttf` **tracked in git-lfs**,
    plain git, or gitignored? Paste the relevant `.gitattributes` /
    `.gitignore` lines. If LFS, paste the `.lfsconfig` or the
    LFS filter config.

8.3 If there is a security / compliance concern about these TTFs
    being checked in, confirm what the expected workflow is:

    - Restricted LFS bucket only reachable from GS network?
    - Gentleman's agreement (the TTFs live on every developer's
      machine but are never committed)?
    - A runtime download step (`fetch_fonts.py` that pulls from
      an internal artifact server on setup)?
    - Something else?

    This decides whether staging's `projects/frontend/ai_development/mysite/fonts/`
    stub mirror can be populated with real bytes or has to stay
    empty / gitignored.

---

## 9. Summary artifacts I need at the end of your reply

After replying to §1–§8 in order, please produce **two compact
summary artifacts** at the very end of your reply. These let the
staging side mechanically update `projects/frontend/dev/specs/design_system.md`
§1.2 and the "gaps / deferred" list without me paraphrasing.

### 9.1 Complete `@font-face` block for `fonts.css`

Use the real filenames from §1.1 and the variable-vs-static decision
from §1.2. One block per family × style. Variable-axis form if the
TTFs carry an `fvar` table; static per-cut form otherwise. Copy this
template and fill it in:

```css
/* GS Sans */
@font-face {
    font-family: "GS Sans";
    src: url("/static/fonts/<real-filename>.ttf") format("truetype-variations" | "truetype");
    font-weight: <100 900 or literal>;
    font-style: normal;
    font-display: swap;
}
/* ...one block per remaining cut... */

/* GS Sans Condensed */
/* ... */

/* GS Serif */
/* ... */
```

### 9.2 One-line JSON capability summary

Paste this exact object, filled in, so Cursor can grep-parse it:

```json
{
  "matplotlib_sees_gs_fonts": true | false,
  "matplotlib_ttflist_gs_count": <int>,
  "mysite_fonts_in_findSystemFonts": true | false,
  "pil_freetype_available": true | false,
  "fonttools_installed": "<version>" | null,
  "weasyprint_installed": "<version>" | null,
  "reportlab_installed": "<version>" | null,
  "cairosvg_installed": "<version>" | null,
  "playwright_installed": "<version>" | null,
  "django_serves_mysite_fonts_via_static": true | false,
  "mysite_fonts_url_prefix": "<e.g. /static/fonts/>" | null,
  "portal_base_html_loads_gs_fonts_today": true | false,
  "portal_body_font_family_today": "<current value>",
  "altair_font_family_today": "<current matplotlib font.family>",
  "echarts_font_family_today": "<current textStyle.fontFamily>",
  "fonts_tracked_in_git": true | false,
  "fonts_in_lfs": true | false,
  "variable_axis_ttfs": true | false,
  "ttf_count": <int>,
  "ttf_families_detected": ["GS Sans", "GS Sans Condensed", "GS Serif", ...]
}
```

---

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end listing what you tried
and what blocked it.
