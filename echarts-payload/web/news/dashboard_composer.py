"""Leaf-node injector: mount the FULL Prism Composer into a served standalone
dashboard HTML document.

A dashboard ``dashboard.html`` is a self-contained compiled artifact (built by
``dashboards/echart_dashboard.py`` / ``rendering.py``) served verbatim by the
dashboard-detail views in ``views.py``. It does NOT extend ``base.html``, so the
Portal Composer mount (base.html) never reaches it. This module splices the SAME
Composer markup into the dashboard doc right before ``</body>``.

SSOT contract
-------------
The Composer is defined ONCE and identically everywhere:

  * behavior -> ``/static/js/composer.js``  (the SAME file base.html loads)
  * styling  -> ``/static/css/composer.css`` (the SAME file base.html loads)

Those two files are the single source of truth for the Composer. This injector
adds NOTHING that changes Composer behavior or appearance -- it only reproduces
the base.html mount so a compiled dashboard (which cannot extend base.html) gets
the identical, fully-featured Composer: drag-and-drop context, the
"Drop materials..." hint, local upload, and inline chat, exactly as on every
other Portal page.

This is the exact shape/precedent of ``views.py::_inject_prism_globals``: a pure
string-splice leaf. ``rendering.py`` and ``echart_dashboard.py`` are untouched.

Why the two design-token declarations exist (and why they are NOT a second SSOT)
--------------------------------------------------------------------------------
``composer.css`` styles the Composer entirely in terms of ``--gs-uitk-*`` design
tokens. On the Portal those tokens are provided by ``base.html``'s ``:root``. A
compiled dashboard has no ``base.html`` ``:root``, so ``composer.css`` would fall
back to its own inline defaults. To make the dashboard Composer look pixel-
identical to the Portal, this injector re-declares the SAME token values that
``base.html`` uses, scoped to ``#prism-composer-root`` only. These are literally
the base.html token values -- if base.html's palette ever changes, update this
one ``_COMPOSER_TOKENS_STYLE`` block to match. It is a rendering shim for a
context that lacks the site ``:root``, NOT a second definition of the Composer.

Inline-chat parity
------------------
Inline chat is gated by the ``enable_inline_chat`` feature flag on the Portal.
The caller (``views.py``) passes that resolved flag into
``inject_dashboard_composer(html, enable_inline_chat=...)`` so the dashboard
Composer honors the SAME flag as the rest of the Portal -- no hardcoded value,
no drift.

There is NO Content-Security-Policy on the dashboard artifact (verified against
the compiled user-dashboard HTML head), so the same-origin ``/api/*`` fetches
composer.js makes and the injected inline flag script are both permitted.
"""

import json

# Served static URLs (STATIC_URL default is "/static/").
_COMPOSER_CSS_URL = "/static/css/composer.css"
_COMPOSER_JS_URL = "/static/js/composer.js"
# The dashboard-only boot script: binds the owner-only component-header drag once
# both composer.js and the prism:dashboard:ready event have fired (two-latch).
_COMPOSER_BOOT_URL = "/static/js/dashboard_composer.js"
# marked.js markdown-to-HTML renderer. base.html loads this same CDN script so
# composer.js's renderMarkdown() can use window.marked (which turns ![alt](url)
# into <img>). A compiled dashboard does not extend base.html, so without this
# splice window.marked is undefined and renderMarkdown() falls back to its
# hand-rolled regex, which has NO image handling -- ![alt](url) then renders as
# literal text. Inject the SAME CDN script (before composer.js; both defer, so
# document order == execution order) so the dashboard Composer renders PNGs
# identically to the Portal.
_MARKED_JS_URL = "https://cdn.jsdelivr.net/npm/marked/marked.min.js"

# PrismMenu -- the shared right-click primitive. base.html loads these same three
# files for every Portal page; a compiled dashboard does not extend base.html, so
# without this splice the Composer surfaces (tabs, turns, charts, tool crumbs,
# attachment cards) silently lose their secondary-click menus on a dashboard.
_PRISM_MENU_CSS_URL = "/static/css/prism_menu.css"
_PRISM_MENU_JS_URL = "/static/js/prism_menu.js"
_PRISM_MENU_SPECS_URL = "/static/js/prism_menu_specs.js"


# Armed-tile feedback for the press-and-hold grab surface.
#
# dashboard_composer.js makes the whole [data-tile-id] wrapper the drag source,
# but only after the pointer has been held still on it -- so the user needs to
# be told the moment the tile becomes draggable, otherwise the hold is
# invisible and feels broken. `.prism-composer-armed` is added at arm time and
# removed on dragend / mouseup / blur.
#
# These rules live here rather than in composer.css because the armed state is
# a dashboard-only affordance: composer.css is Portal-wide and shared with
# pages that have no tiles. They are scoped to `[data-tile-id]` so nothing else
# in a compiled dashboard can pick them up, and the whole injected block is
# already owner-only (views.py mounts the Composer on the owner route alone),
# so a shared viewer never receives them.
#
# The transition is on outline only. Anything that changes layout would reflow
# the tile mid-gesture and move the drag out from under the cursor.
_ARMED_TILE_RULES = (
    '[data-tile-id].prism-composer-armed{'
    'outline:2px solid #7297C5;'
    'outline-offset:-2px;'
    'border-radius:inherit;'
    'transition:outline-color 90ms linear;'
    '}'
    '[data-tile-id].prism-composer-armed::after{'
    'content:"Drag to Composer";'
    'position:absolute;'
    'top:6px;'
    'right:8px;'
    'z-index:5;'
    'padding:1px 6px;'
    'font-family:var(--gs-font-sans,-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif);'
    'font-size:9px;'
    'font-weight:700;'
    'letter-spacing:0.06em;'
    'text-transform:uppercase;'
    'color:#FFFFFF;'
    'background:#7297C5;'
    'border-radius:3px;'
    'pointer-events:none;'
    '}'
    # The ::after is absolutely positioned, so the wrapper needs a containing
    # block. Tiles are `position:static` by default in rendering.py; scoping
    # this to the armed state means no stacking-context change at rest.
    '[data-tile-id].prism-composer-armed{position:relative;}'
)


# The SAME --gs-uitk-* design tokens base.html declares in :root, scoped to the
# Composer mount so composer.css renders identically on a compiled dashboard
# (which has no base.html :root). This is a rendering shim, not a second SSOT --
# keep the values in lockstep with base.html's :root palette.
_COMPOSER_TOKENS_STYLE = (
    '<style id="prism-composer-tokens">'
    '#prism-composer-root{'
    '--gs-font-sans:"GS Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;'
    '--gs-uitk-color-action-brand:#7297C5;'
    '--gs-uitk-color-border-neutral-bold:rgba(0,0,0,0.95);'
    '--gs-uitk-color-border-neutral-minimal:rgba(0,0,0,0.16);'
    '--gs-uitk-color-border-neutral-subtle:rgba(0,0,0,0.34);'
    '--gs-uitk-color-interaction-hover-on-light:rgba(0,0,0,0.04);'
    '--gs-uitk-color-surface-brand-subtle:#F0EBE6;'
    '--gs-uitk-color-surface-neutral-minimal:#FFFFFF;'
    '--gs-uitk-color-surface-neutral-subtle:#F7F7FA;'
    '--gs-uitk-color-surface-neutral-regular:#DCDCE0;'
    '--gs-uitk-color-text-brand:#446EA6;'
    '--gs-uitk-color-text-neutral-bold:rgba(0,0,0,0.95);'
    '--gs-uitk-color-text-neutral-minimal:rgba(0,0,0,0.60);'
    '--gs-uitk-color-text-neutral-regular:rgba(0,0,0,0.80);'
    '--gs-uitk-color-text-neutral-subtle:rgba(0,0,0,0.70);'
    '}'
    '.composer-panel{background:var(--gs-uitk-color-surface-neutral-minimal,#FFFFFF)!important;}'
    '.composer-panel,.composer-pill{opacity:1!important;z-index:2147483000!important;}'
    + _ARMED_TILE_RULES +
    '</style>'
)

def inject_dashboard_composer(html, enable_inline_chat=False, dash_title=None):
    """Splice the FULL (feature-identical) Prism Composer into a dashboard doc.

    Emits (in order, before ``</body>``) the SAME markup base.html emits, adapted
    for a compiled static document that cannot extend base.html:

      1. the ``--gs-uitk-*`` token shim (so composer.css renders identically
         without base.html's ``:root``),
      2. the composer.css stylesheet link (the SAME shared file),
      3. the ``#prism-composer-root`` mount div,
      4. an inline flag script setting ``PRISM_COMPOSER_INLINE_CHAT`` to the
         SAME ``enable_inline_chat`` value the Portal uses (must land before
         composer.js reads it),
      5. the shared ``composer.js`` (deferred) -- the SAME file base.html loads,
      6. the shared PrismMenu right-click primitive (stylesheet, shell, specs).

    Drag-and-drop, the "Drop materials into Composer to add as context" hint,
    local upload, and inline chat are all ENABLED, exactly as on every other
    Portal page. There is no read-only mode: ``PRISM_COMPOSER_DISABLE_DND`` is
    never set, so composer.js's ``DND_DISABLED`` stays ``False`` (its default)
    and every drag/drop/upload code path runs.

    If the document has no ``</body>`` (defensive; the compiled artifact always
    does), the block is appended to the end instead.

    Parameters
    ----------
    html : str
        The full dashboard HTML document.
    enable_inline_chat : bool
        The Portal's ``enable_inline_chat`` feature flag, threaded through from
        the caller so the dashboard Composer honors the SAME flag as base.html.

    Returns
    -------
    str
        The document with the fully-featured Composer spliced in.
    """
    inline_flag = "true" if enable_inline_chat else "false"
    # Server-authoritative dashboard title for the ambient "you are inside dash X"
    # signal. json.dumps makes quotes/unicode/None safe for embedding in the
    # inline <script>. composer.js reads PRISM_COMPOSER_DASHBOARD_TITLE (and the
    # already-present PRISM_DASHBOARD_ID / PRISM_DASHBOARD_OWNER) at fire time.
    title_json = json.dumps(dash_title or "")
    # On a compiled dashboard the Composer runs in dashboard_components DND mode:
    # the panel is a drop target and the ONLY accepted artifact type is
    # dashboard_component (owner drags a rendered tile by its header). File
    # upload and generic Portal source-scanning are OFF. Portal pages keep the
    # default 'standard' mode (never set here). dashboard_composer.js binds the
    # header drag once both composer.js and prism:dashboard:ready have fired.
    block = (
        _COMPOSER_TOKENS_STYLE +
        '<link rel="stylesheet" href="' + _PRISM_MENU_CSS_URL + '">'
        '<link rel="stylesheet" href="' + _COMPOSER_CSS_URL + '">'
        '<div id="prism-composer-root"></div>'
        '<script>window.PRISM_COMPOSER_INLINE_CHAT = ' + inline_flag + ';'
        'window.PRISM_COMPOSER_DND_MODE = "dashboard_components";'
        'window.PRISM_COMPOSER_DASHBOARD_TITLE = ' + title_json + ';'
        'window.PRISM_COMPOSER_IN_DASHBOARD = true;</script>'
        '<script src="' + _MARKED_JS_URL + '" defer></script>'
        '<script src="' + _PRISM_MENU_JS_URL + '" defer></script>'
        '<script src="' + _PRISM_MENU_SPECS_URL + '" defer></script>'
        '<script src="' + _COMPOSER_JS_URL + '" defer></script>'
        '<script src="' + _COMPOSER_BOOT_URL + '" defer></script>'
    )
    marker = '</body>'
    if marker in html:
        head, _, tail = html.rpartition(marker)   # splice before the LAST </body>
        return head + block + marker + tail
    return html + block
