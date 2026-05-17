"""gs_reference_companion.py — high-fidelity replication of the live
goldmansachs.com/insights page + mega-menu navigation chrome.

Sibling to gs_reference.py. Where gs_reference is the abstract "design DNA"
reference (token namespace + 8 archetype pages), the companion is a
pixel-grade replication of the actual live gs.com experience:

  - Two-tier sticky header: a slim utility ribbon (Investor Relations |
    Pressroom | Worldwide | Alumni | Client Login) on top, a tall primary
    nav (logo | What We Do | Insights | Our Firm | Careers | search +
    menu icons) below. Header shrinks on scroll.

  - Full mega-menu dropdowns on all four top-level nav tabs, each shaped
    after its live counterpart:
        * What We Do  ── Investment Banking, Asset & Wealth Management,
                          Engineering, Platform Solutions, plus three
                          curated promo tiles (Outlooks, Sectors,
                          Featured Deal).
        * Insights    ── Explore Insights, Exchanges, The Markets, Talks
                          at GS, Macroeconomics, plus three editorially
                          curated insight tiles.
        * Our Firm    ── Purpose & Values, History, Diversity, People &
                          Leadership, Sustainability, Investor Relations,
                          plus three "discover" tiles.
        * Careers     ── Students, Professionals, Programs, Search Jobs,
                          Life at the Firm, Alumni, plus three role-
                          highlight tiles.

  - Insights index page (/insights/) replicating gs.com/insights:
        * Featured hero tile (Tracking Trillions: ... AI Build-Out)
        * "The Latest" 3-up of recent posts
        * "In Focus: Artificial Intelligence" hero band + 6-tile mosaic
        * Hand-curated "All Insights" CTA + secondary 8-up grid
        * Briefings newsletter signup band

  - 6 sub-landing pages so dropdown links navigate somewhere real:
        * /insights/macroeconomics/        macro feed
        * /insights/exchanges/             podcast hub
        * /insights/talks-at-gs/           interview series hub
        * /what-we-do/investment-banking/  IB pillar with sectors / sub-
                                           offerings / featured deals
        * /what-we-do/asset-wealth/        AM/WM pillar with strategies
        * /careers/students/               students program landing

  - 3 article detail pages, one per "Latest" tile, so every link on the
    insights index resolves to a fully-rendered page:
        * /insights/articles/tracking-trillions/
        * /insights/the-markets/jerome-dortmans-on-oil/
        * /insights/articles/energy-crunch-electrification/

  - Mega-menu JS chrome: 150ms intent-delay open, hover-to-open and
    click-to-toggle, ESC and click-outside to close, ARIA
    expanded/hidden roles, focus trap, sticky-shrink on scroll, smooth-
    scroll on in-page anchors.

╔═══════════════════════════════════════════════════════════════════════╗
║ ARCHITECTURE                                                          ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║ Same single-file Django plug-in shape as gs_reference.py: one         ║
║ include() line in the host project's urls.py mounts the whole         ║
║ surface. The companion does NOT duplicate the design tokens; it       ║
║ imports _CSS_TOKENS and _CSS_FONTS verbatim from gs_reference so      ║
║ there is one source of truth for the token namespace and the 20      ║
║ GS Sans / GS Sans Condensed @font-face blocks. Companion-specific     ║
║ component classes (mega-menu, sticky shrink, in-focus mosaic, ...)    ║
║ live under a `gsv2-*` prefix to avoid collision with the `gs-*`       ║
║ classes the original spec defines.                                    ║
║                                                                       ║
║ All inter-page links use {% url 'gs_reference_companion:<name>' %}    ║
║ so mounting under any prefix (/, /v2/, /companion/, ...) Just Works.  ║
║                                                                       ║
║ The mega-menu JS module is served by its own dedicated route at       ║
║ /<mount>/static/gsv2.js so the base template can include it via a     ║
║ stable {% url %}-resolved path. No Django settings.py edits required. ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝

PLUG-AND-PLAY USAGE (host Django project):

    # mysite/urls.py
    from django.urls import path, include
    urlpatterns += [
        path('v1/',                include('gs_reference')),
        path('',                   include('gs_reference_companion')),
    ]

Optional configuration overrides (override AFTER import, BEFORE the first
request hits a companion route):

    import gs_reference_companion
    gs_reference_companion.config['fonts_url_prefix'] = '/static/news/fonts'
    gs_reference_companion.config['v1_mount_label'] = 'design-DNA reference'

Run the standalone smoke test:
    .venv/bin/python dev/smoke_test_companion.py

Boot both v1 and v2 in one Django runtime and capture screenshots:
    .venv/bin/python dev/run_companion.py
"""

import hashlib
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from django.http import HttpResponse
from django.template import Context, Engine, Library
from django.urls import path, reverse
from django.utils.safestring import mark_safe


_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

try:
    import gs_reference
    _SHARED_TOKENS_CSS = gs_reference._CSS_TOKENS
    _SHARED_FONTS_CSS = gs_reference._CSS_FONTS
except ImportError as exc:
    raise ImportError(
        'gs_reference_companion requires gs_reference (the design DNA '
        'mock) to be importable on the same PYTHONPATH. Put both files '
        'side-by-side in the same directory.'
    ) from exc


# ════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════

config: Dict[str, Any] = {
    'fonts_url_prefix': '/static/fonts',
    'v1_mount_label': 'design DNA reference',
}


# ════════════════════════════════════════════════════════════════════════
# TEMPLATE TAG LIBRARY  ({% load gsv2_extras %})
# ════════════════════════════════════════════════════════════════════════

register = Library()


@register.simple_tag
def gsv2_placeholder(tint: str = 'navy', aspect: str = '16x9',
                     label: str = '', seed: str = '') -> str:
    """Render an <img> backed by Picsum, deterministic on (tint, aspect,
    label, seed). Same contract as gs_reference.gs_placeholder so the
    visual mosaic stays consistent across v1 and v2.
    """
    aspects = {
        '16x9': (1600, 900),
        '21x9': (2100, 900),
        '4x5':  (800, 1000),
        '1x1':  (1000, 1000),
        '3x4':  (900, 1200),
        '4x3':  (1200, 900),
    }
    width, height = aspects.get(aspect, aspects['16x9'])
    seed_str = seed or f'v2-{tint}-{aspect}-{label}'
    digest = hashlib.sha1(seed_str.encode('utf-8')).hexdigest()[:12]
    url = f'https://picsum.photos/seed/{digest}/{width}/{height}'
    alt = (label or f'placeholder ({tint})').replace(
        '&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return mark_safe(
        f'<img src="{url}" alt="{alt}" loading="lazy" '
        f'width="{width}" height="{height}">'
    )


@register.simple_tag
def gsv2_icon(name: str, size: int = 20) -> str:
    """Inline SVG icon library. Currentcolor-driven so it inherits from
    the surrounding text color. Sized via the optional `size` arg.
    """
    icons = {
        'search': '<circle cx="11" cy="11" r="7"/><line x1="16.5" y1="16.5" x2="21" y2="21"/>',
        'menu': '<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>',
        'close': '<line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/>',
        'arrow-right': '<line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>',
        'arrow-down': '<polyline points="6 9 12 15 18 9"/>',
        'arrow-up': '<polyline points="18 15 12 9 6 15"/>',
        'share': '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.6" y1="13.5" x2="15.4" y2="17.5"/><line x1="15.4" y1="6.5" x2="8.6" y2="10.5"/>',
        'play': '<polygon points="6,4 20,12 6,20" fill="currentColor" stroke="none"/>',
        'headphones': '<path d="M3 18v-6a9 9 0 0 1 18 0v6"/><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z"/><path d="M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"/>',
        'globe': '<circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>',
        'document': '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>',
        'video': '<polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/>',
        'rss': '<path d="M4 11a9 9 0 0 1 9 9"/><path d="M4 4a16 16 0 0 1 16 16"/><circle cx="5" cy="19" r="1"/>',
        'newsletter': '<rect x="3" y="5" width="18" height="14" rx="0"/><polyline points="3 7 12 13 21 7"/>',
        'chevron-right': '<polyline points="9 18 15 12 9 6"/>',
        'plus': '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
        'briefcase': '<rect x="2" y="7" width="20" height="14" rx="0"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
        'graduation': '<path d="M22 10 12 5 2 10l10 5 10-5z"/><path d="M6 12v5c0 1.7 2.7 3 6 3s6-1.3 6-3v-5"/>',
        'compass': '<circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>',
    }
    path_geom = icons.get(name, '<line x1="0" y1="0" x2="24" y2="24"/>')
    return mark_safe(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="none" stroke="currentColor" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true" class="gsv2-icon">{path_geom}</svg>'
    )


@register.filter
def get_item(d: Dict, key: Any) -> Any:
    """Sugar for templates: {{ mydict|get_item:somekey }}."""
    if isinstance(d, dict):
        return d.get(key)
    return None


# ════════════════════════════════════════════════════════════════════════
# TEMPLATES
# ════════════════════════════════════════════════════════════════════════

_BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-runtime="{{ request.GET.runtime|default:'prism' }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}Insights | Goldman Sachs (gs-reference companion){% endblock %}</title>
    <meta name="description" content="High-fidelity mock of goldmansachs.com/insights, including mega-menu chrome. Reference asset; not a Goldman Sachs property.">
    <link rel="stylesheet" href="{% url 'gs_reference_companion:css' %}?v=2">
</head>
<body class="gsv2-body">
    {% load gsv2_extras %}

    {# ───────── UTILITY RIBBON ───────── #}
    <div class="gsv2-utility" role="navigation" aria-label="Secondary">
        <div class="gsv2-utility__inner">
            <ul class="gsv2-utility__list">
                <li><a href="#">Investor Relations</a></li>
                <li class="gsv2-utility__sep" aria-hidden="true"></li>
                <li><a href="#">Pressroom</a></li>
                <li class="gsv2-utility__sep" aria-hidden="true"></li>
                <li><a href="#">Worldwide</a></li>
                <li class="gsv2-utility__sep" aria-hidden="true"></li>
                <li><a href="#">Alumni</a></li>
                <li class="gsv2-utility__sep" aria-hidden="true"></li>
                <li><a href="#" class="gsv2-utility__cta">Client Login {% gsv2_icon 'arrow-right' 14 %}</a></li>
            </ul>
        </div>
    </div>

    {# ───────── PRIMARY NAV WITH MEGA-MENU ───────── #}
    <header class="gsv2-nav" role="banner" data-nav>
        <div class="gsv2-nav__bar">
            <div class="gsv2-nav__inner">
                <a href="{% url 'gs_reference_companion:insights' %}" class="gsv2-nav__logo" aria-label="Goldman Sachs home">
                    <span class="gsv2-nav__logo-mark" aria-hidden="true">GS</span>
                    <span class="gsv2-nav__logo-text">Goldman Sachs</span>
                </a>

                <nav class="gsv2-nav__primary" aria-label="Primary">
                    <ul class="gsv2-nav__list">
                        {% for item in nav_items %}
                        <li class="gsv2-nav__item {% if item.key == active_nav %}gsv2-nav__item--active{% endif %}"
                            data-mega-trigger="{{ item.key }}">
                            <button type="button"
                                    class="gsv2-nav__link"
                                    aria-expanded="false"
                                    aria-controls="megamenu-{{ item.key }}"
                                    aria-haspopup="true"
                                    data-mega-button>
                                {{ item.label }}
                                <span class="gsv2-nav__caret" aria-hidden="true">{% gsv2_icon 'arrow-down' 14 %}</span>
                            </button>
                        </li>
                        {% endfor %}
                    </ul>
                </nav>

                <div class="gsv2-nav__right">
                    <button type="button" class="gsv2-nav__icon-btn" aria-label="Search" data-search-toggle>
                        {% gsv2_icon 'search' 22 %}
                    </button>
                    <button type="button" class="gsv2-nav__icon-btn gsv2-nav__icon-btn--mobile" aria-label="Open menu" data-mobile-toggle>
                        {% gsv2_icon 'menu' 22 %}
                    </button>
                    <a href="#" class="gsv2-nav__login">Client Login {% gsv2_icon 'arrow-right' 14 %}</a>
                </div>
            </div>
        </div>

        {# ─── MEGA-MENU PANELS ─── #}
        <div class="gsv2-megabackdrop" data-mega-backdrop aria-hidden="true"></div>
        {% for menu in mega_menus %}
        <div class="gsv2-mega"
             id="megamenu-{{ menu.key }}"
             data-mega-panel="{{ menu.key }}"
             role="region"
             aria-label="{{ menu.title }}"
             aria-hidden="true">
            <div class="gsv2-mega__inner">
                <div class="gsv2-mega__cols">
                    {% for col in menu.columns %}
                    <div class="gsv2-mega__col">
                        <h3 class="gsv2-mega__col-title">{{ col.title }}</h3>
                        <ul class="gsv2-mega__list">
                            {% for link in col.links %}
                            <li>
                                <a href="{{ link.url }}" class="gsv2-mega__link">
                                    <span class="gsv2-mega__link-label">{{ link.label }}</span>
                                    {% if link.description %}
                                    <span class="gsv2-mega__link-desc">{{ link.description }}</span>
                                    {% endif %}
                                </a>
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% endfor %}
                </div>
                <aside class="gsv2-mega__promos" aria-label="Featured">
                    <h3 class="gsv2-mega__promos-title">{{ menu.promos_title }}</h3>
                    <div class="gsv2-mega__promos-grid">
                        {% for promo in menu.promos %}
                        <a href="{{ promo.url }}" class="gsv2-mega__promo">
                            <div class="gsv2-mega__promo-image">{% gsv2_placeholder tint=promo.tint aspect="4x3" label=promo.title %}</div>
                            <div class="gsv2-mega__promo-body">
                                <span class="gsv2-mega__promo-eyebrow">{{ promo.eyebrow }}</span>
                                <h4 class="gsv2-mega__promo-title">{{ promo.title }}</h4>
                                {% if promo.format %}
                                <span class="gsv2-mega__promo-meta">{{ promo.format }}{% if promo.date %} · {{ promo.date }}{% endif %}</span>
                                {% endif %}
                            </div>
                        </a>
                        {% endfor %}
                    </div>
                </aside>
            </div>
        </div>
        {% endfor %}

        {# ─── SEARCH OVERLAY ─── #}
        <div class="gsv2-search" data-search-panel aria-hidden="true" role="search">
            <div class="gsv2-search__inner">
                <form class="gsv2-search__form" method="get" action="#" onsubmit="return false;">
                    <label for="gsv2-search-input" class="gsv2-search__label">Search Goldman Sachs</label>
                    <div class="gsv2-search__input-row">
                        <span class="gsv2-search__icon" aria-hidden="true">{% gsv2_icon 'search' 22 %}</span>
                        <input id="gsv2-search-input" type="search" class="gsv2-search__input" placeholder="Search insights, deals, research..." autocomplete="off">
                        <button type="button" class="gsv2-search__close" data-search-close aria-label="Close search">{% gsv2_icon 'close' 22 %}</button>
                    </div>
                    <div class="gsv2-search__suggestions">
                        <span class="gsv2-search__suggestions-label">Trending</span>
                        <ul class="gsv2-search__chips">
                            <li><a href="#">AI capex outlook</a></li>
                            <li><a href="#">Oil markets 2026</a></li>
                            <li><a href="#">Fed policy</a></li>
                            <li><a href="#">Macro outlook</a></li>
                            <li><a href="#">Europe energy</a></li>
                        </ul>
                    </div>
                </form>
            </div>
        </div>
    </header>

    <main id="main-content">
        {% block content %}{% endblock %}
    </main>

    {# ───────── BRIEFINGS NEWSLETTER ───────── #}
    <section class="gsv2-briefings" aria-labelledby="gsv2-briefings-title">
        <div class="gsv2-briefings__inner">
            <div class="gsv2-briefings__copy">
                <span class="gsv2-eyebrow">Newsletter</span>
                <h2 id="gsv2-briefings-title" class="gsv2-briefings__title">Subscribe to Briefings</h2>
                <p class="gsv2-briefings__lede">
                    Our signature newsletter with insights and analysis from across the firm,
                    delivered to your inbox each weekday morning.
                </p>
            </div>
            <form class="gsv2-briefings__form" method="post" action="#" onsubmit="return false;">
                <label for="gsv2-briefings-email" class="gsv2-sr-only">Email address</label>
                <div class="gsv2-briefings__row">
                    <input id="gsv2-briefings-email" type="email" class="gsv2-briefings__input" placeholder="Email address">
                    <button type="submit" class="gsv2-briefings__submit">
                        Submit {% gsv2_icon 'arrow-right' 16 %}
                    </button>
                </div>
                <p class="gsv2-briefings__legal">
                    By submitting this information, you agree that the information you are
                    providing is subject to the <a href="#">privacy policy</a> and
                    <a href="#">terms of use</a>. You consent to receive our newsletter via email.
                </p>
            </form>
        </div>
    </section>

    {# ───────── FOOTER ───────── #}
    <footer class="gsv2-footer" role="contentinfo">
        <div class="gsv2-footer__inner">
            <div class="gsv2-footer__columns">
                <div>
                    <h3 class="gsv2-footer__col-title">Our Firm</h3>
                    <ul class="gsv2-footer__list">
                        <li><a href="#">Purpose and Values</a></li>
                        <li><a href="#">Our People</a></li>
                        <li><a href="#">History</a></li>
                        <li><a href="#">Newsroom</a></li>
                        <li><a href="#">Sustainability</a></li>
                        <li><a href="#">Diversity</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gsv2-footer__col-title">What We Do</h3>
                    <ul class="gsv2-footer__list">
                        <li><a href="{% url 'gs_reference_companion:wwd_ib' %}">Investment Banking</a></li>
                        <li><a href="{% url 'gs_reference_companion:wwd_aw' %}">Asset &amp; Wealth Management</a></li>
                        <li><a href="#">Engineering</a></li>
                        <li><a href="#">Markets</a></li>
                        <li><a href="#">Platform Solutions</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gsv2-footer__col-title">Insights</h3>
                    <ul class="gsv2-footer__list">
                        <li><a href="{% url 'gs_reference_companion:insights' %}">All Insights</a></li>
                        <li><a href="{% url 'gs_reference_companion:insights_macro' %}">Macroeconomics</a></li>
                        <li><a href="{% url 'gs_reference_companion:insights_exchanges' %}">Exchanges</a></li>
                        <li><a href="{% url 'gs_reference_companion:insights_talks' %}">Talks at GS</a></li>
                        <li><a href="#">The Markets</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gsv2-footer__col-title">Careers</h3>
                    <ul class="gsv2-footer__list">
                        <li><a href="#">Careers Home</a></li>
                        <li><a href="{% url 'gs_reference_companion:careers_students' %}">Students</a></li>
                        <li><a href="#">Professionals</a></li>
                        <li><a href="#">Programs</a></li>
                        <li><a href="#">Search Jobs</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gsv2-footer__col-title">Investor Relations</h3>
                    <ul class="gsv2-footer__list">
                        <li><a href="#">Quarterly Earnings</a></li>
                        <li><a href="#">Annual Reports</a></li>
                        <li><a href="#">Stock Information</a></li>
                        <li><a href="#">Events</a></li>
                        <li><a href="#">Governance</a></li>
                    </ul>
                </div>
            </div>

            <div class="gsv2-footer__bottom">
                <span class="gsv2-footer__copy">&copy; gs-reference companion mock. Visual reference only; not a Goldman Sachs property.</span>
                <ul class="gsv2-footer__bottom-links">
                    <li><a href="#">Privacy &amp; Cookies</a></li>
                    <li><a href="#">Terms of Use</a></li>
                    <li><a href="#">Accessibility</a></li>
                    <li><a href="#">Worldwide</a></li>
                    <li><a href="#">Modern Slavery Statement</a></li>
                </ul>
            </div>
            <div class="gsv2-footer__v1-link">
                <span class="gsv2-eyebrow">Companion</span>
                <p>
                    Looking for the abstract design DNA reference?
                    Browse the v1 token + archetype mock at
                    <a href="/v1/">/v1/</a> ({{ v1_label }}).
                </p>
            </div>
        </div>
    </footer>

    <script src="{% url 'gs_reference_companion:js' %}?v=2" defer></script>
</body>
</html>
"""


_INSIGHTS_INDEX_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}Insights | Goldman Sachs (gs-reference companion){% endblock %}

{% block content %}

<section class="gsv2-page-intro" aria-labelledby="gsv2-insights-title">
    <div class="gsv2-page-intro__inner">
        <h1 id="gsv2-insights-title" class="gsv2-page-intro__title">Insights</h1>
        <p class="gsv2-page-intro__lede">
            Analysis and perspectives on the global economy and markets
            from across Goldman Sachs.
        </p>
        <nav class="gsv2-page-intro__chips" aria-label="Filter insights">
            <a href="{% url 'gs_reference_companion:insights' %}" class="gsv2-chip gsv2-chip--active">All</a>
            <a href="{% url 'gs_reference_companion:insights_macro' %}" class="gsv2-chip">Macroeconomics</a>
            <a href="#" class="gsv2-chip">The Markets</a>
            <a href="{% url 'gs_reference_companion:insights_exchanges' %}" class="gsv2-chip">Exchanges</a>
            <a href="{% url 'gs_reference_companion:insights_talks' %}" class="gsv2-chip">Talks at GS</a>
            <a href="#" class="gsv2-chip">More <span aria-hidden="true">+</span></a>
        </nav>
    </div>
</section>

{# ─── FEATURED HERO ─── #}
<section class="gsv2-feature" aria-label="Featured insight">
    <div class="gsv2-feature__inner">
        <a href="{{ featured.url }}" class="gsv2-feature__tile">
            <div class="gsv2-feature__image">{% gsv2_placeholder tint=featured.tint aspect="21x9" label=featured.title %}</div>
            <div class="gsv2-feature__overlay"></div>
            <div class="gsv2-feature__body">
                <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ featured.eyebrow }}</span>
                <h2 class="gsv2-feature__title">{{ featured.title }}</h2>
                <div class="gsv2-feature__meta">
                    <span class="gsv2-feature__date">{{ featured.date }}</span>
                    <span class="gsv2-feature__cta">
                        Read the analysis {% gsv2_icon 'arrow-right' 16 %}
                    </span>
                </div>
            </div>
        </a>
    </div>
</section>

{# ─── THE LATEST ─── #}
<section class="gsv2-section" aria-labelledby="gsv2-latest-title">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 id="gsv2-latest-title" class="gsv2-section__title">The Latest</h2>
            <a href="#" class="gsv2-section__link">View all {% gsv2_icon 'arrow-right' 14 %}</a>
        </header>
        <div class="gsv2-grid gsv2-grid--3">
            {% for item in latest %}
            <article class="gsv2-card">
                <a href="{{ item.url }}" class="gsv2-card__link">
                    <div class="gsv2-card__image">{% gsv2_placeholder tint=item.tint aspect="16x9" label=item.title %}</div>
                    <div class="gsv2-card__body">
                        <span class="gsv2-card__eyebrow">{{ item.eyebrow }}</span>
                        <h3 class="gsv2-card__title">{{ item.title }}</h3>
                        <div class="gsv2-card__meta">
                            {% if item.format %}<span class="gsv2-chip-mini gsv2-chip-mini--{{ item.format_slug }}">{% if item.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif item.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ item.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ item.date }}</span>
                        </div>
                    </div>
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── IN FOCUS: AI ─── #}
<section class="gsv2-in-focus" aria-labelledby="gsv2-in-focus-title">
    <div class="gsv2-in-focus__inner">
        <header class="gsv2-in-focus__header">
            <span class="gsv2-eyebrow gsv2-eyebrow--inverse">In Focus</span>
            <h2 id="gsv2-in-focus-title" class="gsv2-in-focus__title">Artificial Intelligence</h2>
            <p class="gsv2-in-focus__lede">
                Analysis of the capital, compute, and conviction reshaping
                the world's investment landscape, from infrastructure to
                application layers.
            </p>
            <a href="#" class="gsv2-button gsv2-button--ghost-light">
                Explore the topic {% gsv2_icon 'arrow-right' 16 %}
            </a>
        </header>

        <div class="gsv2-mosaic">
            {% for tile in in_focus_tiles %}
            <a href="{{ tile.url }}" class="gsv2-mosaic__tile gsv2-mosaic__tile--{{ tile.size }}">
                <div class="gsv2-mosaic__image">{% gsv2_placeholder tint=tile.tint aspect=tile.aspect label=tile.title %}</div>
                <div class="gsv2-mosaic__overlay"></div>
                <div class="gsv2-mosaic__body">
                    <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ tile.eyebrow }}</span>
                    <h3 class="gsv2-mosaic__title">{{ tile.title }}</h3>
                    <div class="gsv2-mosaic__meta">
                        {% if tile.format %}<span class="gsv2-chip-mini gsv2-chip-mini--inverse">{% if tile.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif tile.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ tile.format }}</span>{% endif %}
                        <span class="gsv2-mosaic__date">{{ tile.date }}</span>
                    </div>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── ALL INSIGHTS (8-up secondary grid) ─── #}
<section class="gsv2-section gsv2-section--subtle" aria-labelledby="gsv2-all-title">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 id="gsv2-all-title" class="gsv2-section__title">All Insights</h2>
            <a href="#" class="gsv2-section__link">View archive {% gsv2_icon 'arrow-right' 14 %}</a>
        </header>
        <div class="gsv2-grid gsv2-grid--4">
            {% for item in all_insights %}
            <article class="gsv2-card gsv2-card--compact">
                <a href="{{ item.url }}" class="gsv2-card__link">
                    <div class="gsv2-card__image">{% gsv2_placeholder tint=item.tint aspect="16x9" label=item.title %}</div>
                    <div class="gsv2-card__body">
                        <span class="gsv2-card__eyebrow">{{ item.eyebrow }}</span>
                        <h3 class="gsv2-card__title">{{ item.title }}</h3>
                        <div class="gsv2-card__meta">
                            {% if item.format %}<span class="gsv2-chip-mini gsv2-chip-mini--{{ item.format_slug }}">{% if item.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif item.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ item.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ item.date }}</span>
                        </div>
                    </div>
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# ─── EXPLORE BY SERIES ─── #}
<section class="gsv2-section" aria-labelledby="gsv2-series-title">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 id="gsv2-series-title" class="gsv2-section__title">Explore by Series</h2>
        </header>
        <div class="gsv2-series-grid">
            {% for series in series_tiles %}
            <a href="{{ series.url }}" class="gsv2-series">
                <div class="gsv2-series__image">{% gsv2_placeholder tint=series.tint aspect="3x4" label=series.title %}</div>
                <div class="gsv2-series__overlay"></div>
                <div class="gsv2-series__body">
                    <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ series.eyebrow }}</span>
                    <h3 class="gsv2-series__title">{{ series.title }}</h3>
                    <p class="gsv2-series__count">{{ series.episode_count }}</p>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{% endblock %}
"""


_INSIGHTS_TOPIC_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}{{ topic.title }} | Insights | Goldman Sachs (companion){% endblock %}

{% block content %}

<section class="gsv2-topic-hero">
    <div class="gsv2-topic-hero__image">{% gsv2_placeholder tint=topic.tint aspect="21x9" label=topic.title %}</div>
    <div class="gsv2-topic-hero__overlay"></div>
    <div class="gsv2-topic-hero__inner">
        <nav class="gsv2-breadcrumb" aria-label="Breadcrumb">
            <a href="{% url 'gs_reference_companion:insights' %}">Insights</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <span class="gsv2-breadcrumb__current">{{ topic.title }}</span>
        </nav>
        <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ topic.eyebrow }}</span>
        <h1 class="gsv2-topic-hero__title">{{ topic.title }}</h1>
        <p class="gsv2-topic-hero__lede">{{ topic.lede }}</p>
        <div class="gsv2-topic-hero__meta">
            {% for stat in topic.stats %}
            <div class="gsv2-topic-stat">
                <span class="gsv2-topic-stat__numeral">{{ stat.numeral }}</span>
                <span class="gsv2-topic-stat__caption">{{ stat.caption }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
</section>

<section class="gsv2-secondary-nav" aria-label="Section">
    <div class="gsv2-secondary-nav__inner">
        <ul class="gsv2-secondary-nav__list">
            {% for tab in topic.tabs %}
            <li class="gsv2-secondary-nav__item {% if tab.active %}gsv2-secondary-nav__item--active{% endif %}">
                <a href="{{ tab.url }}">{{ tab.label }}</a>
            </li>
            {% endfor %}
        </ul>
    </div>
</section>

{# Featured ─ 1 large + 2 small ─ #}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">Featured</h2>
        </header>
        <div class="gsv2-feature-row">
            <a href="{{ topic.featured_lead.url }}" class="gsv2-feature-row__lead">
                <div class="gsv2-feature-row__image">{% gsv2_placeholder tint=topic.featured_lead.tint aspect="16x9" label=topic.featured_lead.title %}</div>
                <div class="gsv2-feature-row__body">
                    <span class="gsv2-card__eyebrow">{{ topic.featured_lead.eyebrow }}</span>
                    <h3 class="gsv2-feature-row__title">{{ topic.featured_lead.title }}</h3>
                    <p class="gsv2-feature-row__excerpt">{{ topic.featured_lead.excerpt }}</p>
                    <div class="gsv2-card__meta">
                        {% if topic.featured_lead.format %}<span class="gsv2-chip-mini">{% if topic.featured_lead.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif topic.featured_lead.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ topic.featured_lead.format }}</span>{% endif %}
                        <span class="gsv2-card__date">{{ topic.featured_lead.date }}</span>
                    </div>
                </div>
            </a>
            <div class="gsv2-feature-row__side">
                {% for item in topic.featured_side %}
                <a href="{{ item.url }}" class="gsv2-feature-row__side-card">
                    <div class="gsv2-feature-row__side-image">{% gsv2_placeholder tint=item.tint aspect="4x3" label=item.title %}</div>
                    <div class="gsv2-feature-row__side-body">
                        <span class="gsv2-card__eyebrow">{{ item.eyebrow }}</span>
                        <h4 class="gsv2-feature-row__side-title">{{ item.title }}</h4>
                        <div class="gsv2-card__meta">
                            {% if item.format %}<span class="gsv2-chip-mini">{% if item.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif item.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ item.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ item.date }}</span>
                        </div>
                    </div>
                </a>
                {% endfor %}
            </div>
        </div>
    </div>
</section>

{# Full archive grid #}
<section class="gsv2-section gsv2-section--subtle">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">{{ topic.archive_title }}</h2>
            <div class="gsv2-section__filters">
                <button type="button" class="gsv2-chip gsv2-chip--active">All</button>
                {% for fmt in topic.formats %}
                <button type="button" class="gsv2-chip">{{ fmt }}</button>
                {% endfor %}
            </div>
        </header>
        <div class="gsv2-grid gsv2-grid--3">
            {% for item in topic.archive %}
            <article class="gsv2-card">
                <a href="{{ item.url }}" class="gsv2-card__link">
                    <div class="gsv2-card__image">{% gsv2_placeholder tint=item.tint aspect="16x9" label=item.title %}</div>
                    <div class="gsv2-card__body">
                        <span class="gsv2-card__eyebrow">{{ item.eyebrow }}</span>
                        <h3 class="gsv2-card__title">{{ item.title }}</h3>
                        <p class="gsv2-card__excerpt">{{ item.excerpt }}</p>
                        <div class="gsv2-card__meta">
                            {% if item.format %}<span class="gsv2-chip-mini gsv2-chip-mini--{{ item.format_slug }}">{% if item.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif item.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ item.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ item.date }}</span>
                        </div>
                    </div>
                </a>
            </article>
            {% endfor %}
        </div>
        <div class="gsv2-section__more">
            <button type="button" class="gsv2-button gsv2-button--ghost-dark">
                Load more {% gsv2_icon 'arrow-down' 16 %}
            </button>
        </div>
    </div>
</section>

{% if topic.contributors %}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">Contributors</h2>
        </header>
        <div class="gsv2-contributors">
            {% for c in topic.contributors %}
            <article class="gsv2-contributor">
                <div class="gsv2-contributor__avatar">{% gsv2_placeholder tint=c.tint aspect="1x1" label=c.name %}</div>
                <h3 class="gsv2-contributor__name">{{ c.name }}</h3>
                <p class="gsv2-contributor__title">{{ c.title }}</p>
            </article>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

{% endblock %}
"""


_WWD_PILLAR_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}{{ pillar.title }} | What We Do | Goldman Sachs (companion){% endblock %}

{% block content %}

<section class="gsv2-pillar-hero">
    <div class="gsv2-pillar-hero__image">{% gsv2_placeholder tint=pillar.tint aspect="21x9" label=pillar.title %}</div>
    <div class="gsv2-pillar-hero__overlay"></div>
    <div class="gsv2-pillar-hero__inner">
        <nav class="gsv2-breadcrumb gsv2-breadcrumb--inverse" aria-label="Breadcrumb">
            <a href="#">What We Do</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <span class="gsv2-breadcrumb__current">{{ pillar.title }}</span>
        </nav>
        <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ pillar.eyebrow }}</span>
        <h1 class="gsv2-pillar-hero__title">{{ pillar.title }}</h1>
        <p class="gsv2-pillar-hero__lede">{{ pillar.lede }}</p>
    </div>
</section>

<section class="gsv2-secondary-nav" aria-label="Pillar sections">
    <div class="gsv2-secondary-nav__inner">
        <ul class="gsv2-secondary-nav__list">
            {% for tab in pillar.tabs %}
            <li class="gsv2-secondary-nav__item {% if tab.active %}gsv2-secondary-nav__item--active{% endif %}">
                <a href="{{ tab.url }}">{{ tab.label }}</a>
            </li>
            {% endfor %}
        </ul>
    </div>
</section>

{# Rankings strip #}
{% if pillar.rankings %}
<section class="gsv2-rankings" aria-label="Rankings">
    <div class="gsv2-rankings__inner">
        {% for r in pillar.rankings %}
        <div class="gsv2-rankings__item">
            <span class="gsv2-rankings__numeral">{{ r.numeral }}</span>
            <span class="gsv2-rankings__label">{{ r.label }}</span>
        </div>
        {% endfor %}
        <p class="gsv2-rankings__legal">{{ pillar.rankings_legal }}</p>
    </div>
</section>
{% endif %}

{# Our offerings #}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <span class="gsv2-eyebrow">Our Offerings</span>
            <h2 class="gsv2-section__title">{{ pillar.offerings_title }}</h2>
            <p class="gsv2-section__lede">{{ pillar.offerings_lede }}</p>
        </header>
        <div class="gsv2-offerings">
            {% for o in pillar.offerings %}
            <article class="gsv2-offering">
                <div class="gsv2-offering__icon">{% gsv2_icon o.icon 28 %}</div>
                <h3 class="gsv2-offering__title">{{ o.title }}</h3>
                <p class="gsv2-offering__body">{{ o.body }}</p>
                <ul class="gsv2-offering__links">
                    {% for link in o.links %}
                    <li><a href="#">{{ link }} {% gsv2_icon 'arrow-right' 12 %}</a></li>
                    {% endfor %}
                </ul>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# Featured deals #}
{% if pillar.deals %}
<section class="gsv2-section gsv2-section--subtle">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">Selected Transactions</h2>
            <a href="#" class="gsv2-section__link">All transactions {% gsv2_icon 'arrow-right' 14 %}</a>
        </header>
        <div class="gsv2-deals">
            {% for d in pillar.deals %}
            <article class="gsv2-deal">
                <div class="gsv2-deal__image">{% gsv2_placeholder tint=d.tint aspect="16x9" label=d.title %}</div>
                <div class="gsv2-deal__body">
                    <span class="gsv2-card__eyebrow">{{ d.eyebrow }}</span>
                    <h3 class="gsv2-deal__title">{{ d.title }}</h3>
                    <p class="gsv2-deal__role">{{ d.role }}</p>
                    <ul class="gsv2-deal__facts">
                        {% for f in d.facts %}
                        <li>
                            <span class="gsv2-deal__fact-label">{{ f.label }}</span>
                            <span class="gsv2-deal__fact-value">{{ f.value }}</span>
                        </li>
                        {% endfor %}
                    </ul>
                </div>
            </article>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

{# Latest insights #}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">Insights from {{ pillar.short_title }}</h2>
            <a href="{% url 'gs_reference_companion:insights' %}" class="gsv2-section__link">All Insights {% gsv2_icon 'arrow-right' 14 %}</a>
        </header>
        <div class="gsv2-grid gsv2-grid--3">
            {% for item in pillar.insights %}
            <article class="gsv2-card">
                <a href="{{ item.url }}" class="gsv2-card__link">
                    <div class="gsv2-card__image">{% gsv2_placeholder tint=item.tint aspect="16x9" label=item.title %}</div>
                    <div class="gsv2-card__body">
                        <span class="gsv2-card__eyebrow">{{ item.eyebrow }}</span>
                        <h3 class="gsv2-card__title">{{ item.title }}</h3>
                        <div class="gsv2-card__meta">
                            {% if item.format %}<span class="gsv2-chip-mini">{% if item.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% elif item.format == 'Video' %}{% gsv2_icon 'video' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ item.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ item.date }}</span>
                        </div>
                    </div>
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# Leadership #}
{% if pillar.leadership %}
<section class="gsv2-section gsv2-section--subtle">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 class="gsv2-section__title">Leadership</h2>
        </header>
        <div class="gsv2-leaders">
            {% for p in pillar.leadership %}
            <article class="gsv2-leader">
                <div class="gsv2-leader__avatar">{% gsv2_placeholder tint=p.tint aspect="3x4" label=p.name %}</div>
                <h3 class="gsv2-leader__name">{{ p.name }}</h3>
                <p class="gsv2-leader__title">{{ p.title }}</p>
            </article>
            {% endfor %}
        </div>
    </div>
</section>
{% endif %}

{% endblock %}
"""


_CAREERS_STUDENTS_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}Students | Careers | Goldman Sachs (companion){% endblock %}

{% block content %}

<section class="gsv2-pillar-hero gsv2-pillar-hero--careers">
    <div class="gsv2-pillar-hero__image">{% gsv2_placeholder tint='navy' aspect="21x9" label='Students at Goldman Sachs' %}</div>
    <div class="gsv2-pillar-hero__overlay"></div>
    <div class="gsv2-pillar-hero__inner">
        <nav class="gsv2-breadcrumb gsv2-breadcrumb--inverse" aria-label="Breadcrumb">
            <a href="#">Careers</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <span class="gsv2-breadcrumb__current">Students</span>
        </nav>
        <span class="gsv2-eyebrow gsv2-eyebrow--inverse">Students &amp; Graduates</span>
        <h1 class="gsv2-pillar-hero__title">Start Your Career With Us</h1>
        <p class="gsv2-pillar-hero__lede">
            Build your foundation on a multi-disciplinary platform where the
            best in their fields collaborate to advise the world's most
            influential institutions.
        </p>
        <div class="gsv2-pillar-hero__ctas">
            <a href="#" class="gsv2-button gsv2-button--primary-light">
                Explore opportunities {% gsv2_icon 'arrow-right' 16 %}
            </a>
            <a href="#" class="gsv2-button gsv2-button--ghost-light">
                Watch the film {% gsv2_icon 'video' 16 %}
            </a>
        </div>
    </div>
</section>

{# Stats strip #}
<section class="gsv2-stats-strip" aria-label="By the numbers">
    <div class="gsv2-stats-strip__inner">
        {% for s in stats %}
        <div class="gsv2-stats-strip__item">
            <span class="gsv2-stats-strip__numeral">{{ s.numeral }}</span>
            <span class="gsv2-stats-strip__caption">{{ s.caption }}</span>
        </div>
        {% endfor %}
    </div>
</section>

{# Programs #}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <span class="gsv2-eyebrow">Programs</span>
            <h2 class="gsv2-section__title">Find Your Track</h2>
            <p class="gsv2-section__lede">
                We hire across multiple stages and pathways. Find the
                program that fits where you are in your education and
                career planning.
            </p>
        </header>
        <div class="gsv2-grid gsv2-grid--3">
            {% for p in programs %}
            <article class="gsv2-program-card">
                <span class="gsv2-program-card__eyebrow">{{ p.eyebrow }}</span>
                <h3 class="gsv2-program-card__title">{{ p.title }}</h3>
                <p class="gsv2-program-card__body">{{ p.body }}</p>
                <ul class="gsv2-program-card__facts">
                    {% for f in p.facts %}
                    <li>
                        <span class="gsv2-program-card__fact-label">{{ f.label }}</span>
                        <span class="gsv2-program-card__fact-value">{{ f.value }}</span>
                    </li>
                    {% endfor %}
                </ul>
                <a href="#" class="gsv2-program-card__cta">Learn more {% gsv2_icon 'arrow-right' 14 %}</a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# Divisions #}
<section class="gsv2-section gsv2-section--subtle">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <span class="gsv2-eyebrow">Where you can work</span>
            <h2 class="gsv2-section__title">Explore Our Divisions</h2>
        </header>
        <div class="gsv2-grid gsv2-grid--4">
            {% for d in divisions %}
            <a href="#" class="gsv2-division-card">
                <div class="gsv2-division-card__image">{% gsv2_placeholder tint=d.tint aspect="4x5" label=d.title %}</div>
                <div class="gsv2-division-card__overlay"></div>
                <div class="gsv2-division-card__body">
                    <h3 class="gsv2-division-card__title">{{ d.title }}</h3>
                    <p class="gsv2-division-card__body-text">{{ d.body }}</p>
                </div>
            </a>
            {% endfor %}
        </div>
    </div>
</section>

{# Voices #}
<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <span class="gsv2-eyebrow">Voices</span>
            <h2 class="gsv2-section__title">Hear from Our People</h2>
        </header>
        <div class="gsv2-voices">
            {% for v in voices %}
            <article class="gsv2-voice">
                <div class="gsv2-voice__avatar">{% gsv2_placeholder tint=v.tint aspect="1x1" label=v.name %}</div>
                <blockquote class="gsv2-voice__quote">{{ v.quote }}</blockquote>
                <p class="gsv2-voice__name">{{ v.name }}</p>
                <p class="gsv2-voice__title">{{ v.title }}</p>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{# Process steps #}
<section class="gsv2-section gsv2-section--subtle">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <span class="gsv2-eyebrow">Application</span>
            <h2 class="gsv2-section__title">Your Path Forward</h2>
        </header>
        <ol class="gsv2-steps">
            {% for s in steps %}
            <li class="gsv2-steps__item">
                <span class="gsv2-steps__numeral">{{ forloop.counter|stringformat:"02d" }}</span>
                <div class="gsv2-steps__body">
                    <h3 class="gsv2-steps__title">{{ s.title }}</h3>
                    <p class="gsv2-steps__text">{{ s.body }}</p>
                </div>
            </li>
            {% endfor %}
        </ol>
    </div>
</section>

{% endblock %}
"""


_ARTICLE_DETAIL_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}{{ article.title }} | Insights | Goldman Sachs (companion){% endblock %}

{% block content %}

<section class="gsv2-article-hero">
    <div class="gsv2-article-hero__image">{% gsv2_placeholder tint=article.tint aspect="21x9" label=article.title %}</div>
    <div class="gsv2-article-hero__overlay"></div>
    <div class="gsv2-article-hero__inner">
        <nav class="gsv2-breadcrumb gsv2-breadcrumb--inverse" aria-label="Breadcrumb">
            <a href="{% url 'gs_reference_companion:insights' %}">Insights</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <span class="gsv2-breadcrumb__current">{{ article.eyebrow }}</span>
        </nav>
        <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ article.eyebrow }}</span>
        <h1 class="gsv2-article-hero__title">{{ article.title }}</h1>
        <p class="gsv2-article-hero__deck">{{ article.deck }}</p>
    </div>
</section>

<section class="gsv2-byline-strip" aria-label="Article meta">
    <div class="gsv2-byline-strip__inner">
        <ul class="gsv2-byline-strip__authors">
            {% for a in article.authors %}
            <li>
                <span class="gsv2-byline-strip__name">{{ a.name }}</span>
                <span class="gsv2-byline-strip__title">{{ a.title }}</span>
            </li>
            {% endfor %}
        </ul>
        <div class="gsv2-byline-strip__meta">
            <span>{{ article.date }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ article.read_time }}</span>
            <button type="button" class="gsv2-byline-strip__share">
                {% gsv2_icon 'share' 16 %} Share
            </button>
        </div>
    </div>
</section>

<article class="gsv2-article-body">
    <p class="gsv2-article-body__deck">{{ article.intro }}</p>

    <h2>Executive Summary</h2>
    <p>{{ article.exec_body }}</p>

    <ol class="gsv2-numbered-list">
        {% for n in article.numbered %}
        <li>
            <span class="gsv2-numbered-list__num">{{ forloop.counter }}</span>
            <p>{{ n }}</p>
        </li>
        {% endfor %}
    </ol>

    {% for sec in article.sections %}
    <h2>{{ sec.heading }}</h2>
    {% for para in sec.paragraphs %}
    <p>{{ para }}</p>
    {% endfor %}
    {% if sec.pull_quote %}
    <blockquote class="gsv2-pull-quote">
        <p>{{ sec.pull_quote }}</p>
        {% if sec.pull_quote_attribution %}
        <cite>{{ sec.pull_quote_attribution }}</cite>
        {% endif %}
    </blockquote>
    {% endif %}
    {% if sec.callout %}
    <aside class="gsv2-callout">
        <h3 class="gsv2-callout__title">{{ sec.callout.title }}</h3>
        <p>{{ sec.callout.body }}</p>
    </aside>
    {% endif %}
    {% endfor %}

    <div class="gsv2-footnotes">
        <h3>Footnotes</h3>
        {% for fn in article.footnotes %}
        <p>{{ fn }}</p>
        {% endfor %}
    </div>

    <div class="gsv2-article-share">
        <span>Share this article</span>
        <ul>
            <li><a href="#">Email</a></li>
            <li><a href="#">LinkedIn</a></li>
            <li><a href="#">X</a></li>
            <li><a href="#">Copy link</a></li>
        </ul>
    </div>
</article>

<section class="gsv2-related" aria-labelledby="gsv2-related-title">
    <div class="gsv2-section__inner">
        <header class="gsv2-section__header">
            <h2 id="gsv2-related-title" class="gsv2-section__title">Related Insights</h2>
        </header>
        <div class="gsv2-grid gsv2-grid--3">
            {% for r in related %}
            <article class="gsv2-card">
                <a href="{{ r.url }}" class="gsv2-card__link">
                    <div class="gsv2-card__image">{% gsv2_placeholder tint=r.tint aspect="16x9" label=r.title %}</div>
                    <div class="gsv2-card__body">
                        <span class="gsv2-card__eyebrow">{{ r.eyebrow }}</span>
                        <h3 class="gsv2-card__title">{{ r.title }}</h3>
                        <div class="gsv2-card__meta">
                            {% if r.format %}<span class="gsv2-chip-mini">{% if r.format == 'Podcast' %}{% gsv2_icon 'headphones' 12 %}{% else %}{% gsv2_icon 'document' 12 %}{% endif %} {{ r.format }}</span>{% endif %}
                            <span class="gsv2-card__date">{{ r.date }}</span>
                        </div>
                    </div>
                </a>
            </article>
            {% endfor %}
        </div>
    </div>
</section>

{% endblock %}
"""


_PODCAST_DETAIL_TEMPLATE = """{% extends "gsv2/base.html" %}
{% load gsv2_extras %}

{% block title %}{{ episode.title }} | The Markets | Goldman Sachs (companion){% endblock %}

{% block content %}

<section class="gsv2-article-hero gsv2-article-hero--podcast">
    <div class="gsv2-article-hero__image">{% gsv2_placeholder tint=episode.tint aspect="21x9" label=episode.title %}</div>
    <div class="gsv2-article-hero__overlay"></div>
    <div class="gsv2-article-hero__inner">
        <nav class="gsv2-breadcrumb gsv2-breadcrumb--inverse" aria-label="Breadcrumb">
            <a href="{% url 'gs_reference_companion:insights' %}">Insights</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <a href="#" style="color: inherit;">The Markets</a>
            <span aria-hidden="true">{% gsv2_icon 'chevron-right' 14 %}</span>
            <span class="gsv2-breadcrumb__current">{{ episode.short_title }}</span>
        </nav>
        <span class="gsv2-eyebrow gsv2-eyebrow--inverse">{{ episode.series }} · Episode {{ episode.number }}</span>
        <h1 class="gsv2-article-hero__title">{{ episode.title }}</h1>
        <p class="gsv2-article-hero__deck">{{ episode.deck }}</p>
        <div class="gsv2-article-hero__meta">
            <span>{{ episode.date }}</span>
            <span aria-hidden="true">·</span>
            <span>{{ episode.duration }}</span>
        </div>
    </div>
</section>

<section class="gsv2-section">
    <div class="gsv2-section__inner">
        <div class="gsv2-podcast-layout">
            <div class="gsv2-podcast-main">
                <div class="gsv2-podcast-player">
                    <button type="button" class="gsv2-podcast-player__play" aria-label="Play episode">
                        {% gsv2_icon 'play' 22 %}
                    </button>
                    <div class="gsv2-podcast-player__meta">
                        <div class="gsv2-podcast-player__title">
                            <span class="gsv2-eyebrow">{{ episode.series }}</span>
                            <p>{{ episode.title }}</p>
                        </div>
                        <div class="gsv2-podcast-player__bar">
                            <span class="gsv2-podcast-player__time">12:08</span>
                            <div class="gsv2-podcast-player__track"><span class="gsv2-podcast-player__progress"></span></div>
                            <span class="gsv2-podcast-player__time">{{ episode.duration }}</span>
                        </div>
                    </div>
                </div>

                <div class="gsv2-podcast-subscribe">
                    <span class="gsv2-eyebrow">Subscribe</span>
                    <ul class="gsv2-podcast-subscribe__list">
                        <li><a href="#"><span>Apple Podcasts</span> {% gsv2_icon 'arrow-right' 14 %}</a></li>
                        <li><a href="#"><span>Spotify</span> {% gsv2_icon 'arrow-right' 14 %}</a></li>
                        <li><a href="#"><span>YouTube</span> {% gsv2_icon 'arrow-right' 14 %}</a></li>
                        <li><a href="#"><span>RSS Feed</span> {% gsv2_icon 'rss' 14 %}</a></li>
                    </ul>
                </div>

                <h2 class="gsv2-section__title gsv2-section__title--inset">Episode Summary</h2>
                {% for para in episode.summary_paragraphs %}
                <p class="gsv2-podcast-text">{{ para }}</p>
                {% endfor %}

                <h2 class="gsv2-section__title gsv2-section__title--inset">Chapter Markers</h2>
                <ol class="gsv2-chapters">
                    {% for c in episode.chapters %}
                    <li>
                        <button type="button" class="gsv2-chapters__btn">
                            <span class="gsv2-chapters__time">{{ c.time }}</span>
                            <span class="gsv2-chapters__label">{{ c.label }}</span>
                            <span class="gsv2-chapters__play" aria-hidden="true">{% gsv2_icon 'play' 14 %}</span>
                        </button>
                    </li>
                    {% endfor %}
                </ol>

                <h2 class="gsv2-section__title gsv2-section__title--inset">Transcript</h2>
                <div class="gsv2-transcript">
                    {% for t in episode.transcript %}
                    <p class="gsv2-transcript__line">
                        <span class="gsv2-transcript__speaker">{{ t.speaker }}</span>
                        <span class="gsv2-transcript__time">{{ t.time }}</span>
                        <span class="gsv2-transcript__text">{{ t.text }}</span>
                    </p>
                    {% endfor %}
                </div>
            </div>

            <aside class="gsv2-podcast-side">
                <h3 class="gsv2-eyebrow">Featured Voices</h3>
                <ul class="gsv2-podcast-personas">
                    {% for p in episode.personas %}
                    <li>
                        <div class="gsv2-podcast-persona__avatar">{% gsv2_placeholder tint=p.tint aspect="1x1" label=p.name %}</div>
                        <div>
                            <p class="gsv2-podcast-persona__name">{{ p.name }}</p>
                            <p class="gsv2-podcast-persona__title">{{ p.title }}</p>
                        </div>
                    </li>
                    {% endfor %}
                </ul>

                <h3 class="gsv2-eyebrow">Related Episodes</h3>
                <ul class="gsv2-podcast-related">
                    {% for r in episode.related %}
                    <li>
                        <a href="{{ r.url }}">
                            <span class="gsv2-card__eyebrow">{{ r.eyebrow }}</span>
                            <p>{{ r.title }}</p>
                            <span class="gsv2-card__date">{{ r.date }} · {{ r.duration }}</span>
                        </a>
                    </li>
                    {% endfor %}
                </ul>
            </aside>
        </div>
    </div>
</section>

{% endblock %}
"""


_TEMPLATES: Dict[str, str] = {
    'gsv2/base.html':                _BASE_TEMPLATE,
    'gsv2/insights_index.html':      _INSIGHTS_INDEX_TEMPLATE,
    'gsv2/insights_topic.html':      _INSIGHTS_TOPIC_TEMPLATE,
    'gsv2/wwd_pillar.html':          _WWD_PILLAR_TEMPLATE,
    'gsv2/careers_students.html':    _CAREERS_STUDENTS_TEMPLATE,
    'gsv2/article_detail.html':      _ARTICLE_DETAIL_TEMPLATE,
    'gsv2/podcast_detail.html':      _PODCAST_DETAIL_TEMPLATE,
}


# ════════════════════════════════════════════════════════════════════════
# CSS — companion-specific gsv2-* component layer
# ════════════════════════════════════════════════════════════════════════
# Tokens + fonts come from gs_reference._CSS_TOKENS / ._CSS_FONTS so the
# companion stays in sync with the design DNA spec. This block adds the
# component classes the companion uses on top of that token namespace.

_CSS_COMPANION = r"""
/* ───────── base / reset ───────── */
*, *::before, *::after { box-sizing: border-box; }
html {
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    scroll-behavior: smooth;
}
.gsv2-body {
    margin: 0;
    padding: 0;
    background: var(--gs-uitk-color-surface-neutral-minimal);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: var(--gs-uitk-text-body03-regular-lg-screen-font);
}
img { max-width: 100%; display: block; }
a { color: inherit; text-decoration: none; }
a:hover { text-decoration: none; }
button { font-family: inherit; cursor: pointer; }

.gsv2-sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    border: 0;
}

.gsv2-icon { display: inline-block; vertical-align: middle; }

.gsv2-eyebrow {
    font: var(--gs-uitk-text-overline02-md-screen-font);
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0;
    display: inline-block;
}
.gsv2-eyebrow--inverse { color: rgba(255, 255, 255, 0.82); }

/* ───────── utility ribbon (slim top bar) ───────── */
.gsv2-utility {
    background: #0B1624;
    color: rgba(255, 255, 255, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}
.gsv2-utility__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: flex-end;
}
@media (min-width: 768px) { .gsv2-utility__inner { padding: 0 48px; } }
@media (min-width: 1200px) { .gsv2-utility__inner { padding: 0 64px; } }

.gsv2-utility__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    align-items: center;
    gap: 14px;
    font: 400 12px/16px var(--gs-font-sans);
    letter-spacing: 0.4px;
}
.gsv2-utility__list a {
    color: rgba(255, 255, 255, 0.78);
    transition: color 200ms ease;
}
.gsv2-utility__list a:hover { color: #FFFFFF; }
.gsv2-utility__sep {
    width: 1px;
    height: 12px;
    background: rgba(255, 255, 255, 0.18);
}
.gsv2-utility__cta {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    color: #FFFFFF;
}
@media (max-width: 767px) {
    .gsv2-utility { display: none; }
}

/* ───────── primary nav + sticky shrink ───────── */
.gsv2-nav {
    position: sticky;
    top: 0;
    z-index: 90;
    background: #FFFFFF;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    transition: box-shadow 220ms ease;
}
.gsv2-nav.is-scrolled { box-shadow: 0 6px 24px rgba(0, 0, 0, 0.08); }
.gsv2-nav.is-mega-open { box-shadow: 0 24px 60px rgba(0, 0, 0, 0.12); }
.gsv2-nav__bar { position: relative; z-index: 2; background: #FFFFFF; }
.gsv2-nav__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
    height: 88px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    transition: height 220ms ease;
}
@media (min-width: 768px) { .gsv2-nav__inner { padding: 0 48px; } }
@media (min-width: 1200px) { .gsv2-nav__inner { padding: 0 64px; } }
.gsv2-nav.is-scrolled .gsv2-nav__inner { height: 64px; }

.gsv2-nav__logo {
    display: flex;
    align-items: center;
    gap: 12px;
    font: 500 18px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    flex-shrink: 0;
}
.gsv2-nav__logo-mark {
    width: 36px;
    height: 36px;
    background: var(--gs-uitk-color-action-neutral-bold);
    color: #FFFFFF;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font: 700 14px/1 var(--gs-font-sans);
    letter-spacing: 0.6px;
}
.gsv2-nav__logo-text { display: none; }
@media (min-width: 1024px) { .gsv2-nav__logo-text { display: inline; } }

.gsv2-nav__primary { display: none; flex: 1; justify-content: center; }
@media (min-width: 1024px) { .gsv2-nav__primary { display: flex; } }

.gsv2-nav__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    align-items: center;
    gap: 4px;
}
.gsv2-nav__item { position: relative; }
.gsv2-nav__link {
    background: transparent;
    border: none;
    padding: 12px 18px;
    font: 500 15px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    display: inline-flex;
    align-items: center;
    gap: 4px;
    border-bottom: 3px solid transparent;
    border-top: 3px solid transparent;
    transition: color 180ms ease, border-color 180ms ease;
    letter-spacing: 0;
    height: 64px;
}
.gsv2-nav__link:hover,
.gsv2-nav__link:focus-visible,
.gsv2-nav__item--active > .gsv2-nav__link,
.gsv2-nav__item.is-open > .gsv2-nav__link {
    color: var(--gs-uitk-color-text-brand);
    outline: none;
}
.gsv2-nav__item--active > .gsv2-nav__link {
    border-bottom-color: var(--gs-uitk-color-text-brand);
}
.gsv2-nav__item.is-open > .gsv2-nav__link {
    border-bottom-color: var(--gs-uitk-color-text-brand);
}
.gsv2-nav__caret {
    display: inline-flex;
    transition: transform 200ms ease;
    color: currentColor;
    margin-left: 2px;
}
.gsv2-nav__item.is-open .gsv2-nav__caret { transform: rotate(180deg); }

.gsv2-nav__right {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}
.gsv2-nav__icon-btn {
    width: 40px;
    height: 40px;
    background: transparent;
    border: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--gs-uitk-color-text-neutral-bold);
    border-radius: 0;
    transition: background 180ms ease, color 180ms ease;
}
.gsv2-nav__icon-btn:hover { background: rgba(0, 0, 0, 0.04); }
.gsv2-nav__icon-btn--mobile { display: inline-flex; }
@media (min-width: 1024px) { .gsv2-nav__icon-btn--mobile { display: none; } }

.gsv2-nav__login {
    display: none;
    align-items: center;
    gap: 6px;
    height: 40px;
    padding: 0 20px;
    background: transparent;
    color: var(--gs-uitk-color-text-neutral-bold);
    border: 1px solid var(--gs-uitk-color-border-neutral-bold);
    font: 500 14px/1 var(--gs-font-sans);
    letter-spacing: 0;
    transition: background 180ms ease;
}
.gsv2-nav__login:hover { background: rgba(0, 0, 0, 0.04); }
@media (min-width: 1024px) { .gsv2-nav__login { display: inline-flex; } }

/* ───────── MEGA-MENU PANELS ───────── */
.gsv2-megabackdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.36);
    opacity: 0;
    pointer-events: none;
    transition: opacity 240ms ease;
    z-index: 80;
}
.gsv2-megabackdrop.is-active {
    opacity: 1;
    pointer-events: auto;
}

.gsv2-mega {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: #FFFFFF;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    box-shadow: 0 32px 60px rgba(0, 0, 0, 0.16);
    z-index: 1;
    opacity: 0;
    pointer-events: none;
    transform: translateY(-8px);
    transition: opacity 220ms ease, transform 220ms ease;
}
.gsv2-mega.is-open {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
}
.gsv2-mega__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 40px 48px 56px;
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 56px;
}
@media (min-width: 1200px) {
    .gsv2-mega__inner { padding: 48px 64px 64px; }
}
.gsv2-mega__cols {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 32px;
}
.gsv2-mega__col-title {
    font: 700 12px/16px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0 0 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}
.gsv2-mega__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.gsv2-mega__link {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 6px 0;
    color: var(--gs-uitk-color-text-neutral-bold);
    border-left: 2px solid transparent;
    padding-left: 0;
    transition: color 160ms ease, border-color 160ms ease, padding-left 160ms ease;
}
.gsv2-mega__link:hover {
    color: var(--gs-uitk-color-text-brand);
    border-left-color: var(--gs-uitk-color-text-brand);
    padding-left: 10px;
}
.gsv2-mega__link-label {
    font: 500 16px/22px var(--gs-font-sans);
}
.gsv2-mega__link-desc {
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-mega__promos {
    border-left: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding-left: 40px;
    display: flex;
    flex-direction: column;
    gap: 18px;
}
.gsv2-mega__promos-title {
    font: 700 12px/16px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0 0 4px;
}
.gsv2-mega__promos-grid {
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.gsv2-mega__promo {
    display: grid;
    grid-template-columns: 96px 1fr;
    gap: 14px;
    align-items: flex-start;
    padding: 4px 0;
    color: var(--gs-uitk-color-text-neutral-bold);
    transition: opacity 180ms ease;
}
.gsv2-mega__promo:hover { opacity: 0.82; }
.gsv2-mega__promo-image {
    aspect-ratio: 4 / 3;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-neutral-regular);
}
.gsv2-mega__promo-image img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-mega__promo-body { display: flex; flex-direction: column; gap: 4px; }
.gsv2-mega__promo-eyebrow {
    font: 400 11px/14px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.gsv2-mega__promo-title {
    font: 500 14px/19px var(--gs-font-sans);
    margin: 0;
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-mega__promo-meta {
    font: 400 12px/16px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

/* Search overlay */
.gsv2-search {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: #FFFFFF;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    box-shadow: 0 32px 60px rgba(0, 0, 0, 0.16);
    opacity: 0;
    pointer-events: none;
    transform: translateY(-8px);
    transition: opacity 220ms ease, transform 220ms ease;
    z-index: 1;
}
.gsv2-search.is-open {
    opacity: 1;
    pointer-events: auto;
    transform: translateY(0);
}
.gsv2-search__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 48px 48px 56px;
}
@media (min-width: 1200px) { .gsv2-search__inner { padding: 56px 64px 64px; } }
.gsv2-search__label {
    display: block;
    font: 700 12px/16px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin-bottom: 16px;
}
.gsv2-search__input-row {
    display: flex;
    align-items: center;
    border-bottom: 2px solid var(--gs-uitk-color-text-neutral-bold);
    padding-bottom: 12px;
    gap: 14px;
}
.gsv2-search__icon { color: var(--gs-uitk-color-text-neutral-minimal); }
.gsv2-search__input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    font: 300 32px/40px var(--gs-font-serif-prism);
    color: var(--gs-uitk-color-text-neutral-bold);
}
@media (min-width: 768px) {
    .gsv2-search__input { font: 300 44px/52px var(--gs-font-serif-prism); }
}
.gsv2-search__close {
    width: 40px;
    height: 40px;
    background: transparent;
    border: 1px solid var(--gs-uitk-color-border-neutral-bold);
    color: var(--gs-uitk-color-text-neutral-bold);
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.gsv2-search__close:hover { background: rgba(0, 0, 0, 0.04); }
.gsv2-search__suggestions { margin-top: 28px; }
.gsv2-search__suggestions-label {
    display: block;
    font: 700 11px/14px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin-bottom: 12px;
}
.gsv2-search__chips {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}
.gsv2-search__chips a {
    padding: 8px 14px;
    border: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    font: 400 14px/1 var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    transition: border-color 180ms ease, background 180ms ease;
    display: inline-block;
}
.gsv2-search__chips a:hover {
    border-color: var(--gs-uitk-color-text-neutral-bold);
    background: rgba(0, 0, 0, 0.04);
}

/* ───────── PAGE INTRO / FILTERS ───────── */
.gsv2-page-intro {
    background: var(--gs-uitk-color-surface-neutral-minimal);
    padding: 64px 0 32px;
}
.gsv2-page-intro__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}
@media (min-width: 768px) { .gsv2-page-intro__inner { padding: 0 48px; } }
@media (min-width: 1200px) {
    .gsv2-page-intro { padding: 88px 0 40px; }
    .gsv2-page-intro__inner { padding: 0 64px; }
}
.gsv2-page-intro__title {
    margin: 0;
    font: 300 56px/60px var(--gs-font-serif-prism);
    color: var(--gs-uitk-color-text-neutral-bold);
}
@media (min-width: 768px) { .gsv2-page-intro__title { font: 300 88px/92px var(--gs-font-serif-prism); } }
@media (min-width: 1200px) { .gsv2-page-intro__title { font: 300 120px/124px var(--gs-font-serif-prism); } }
.gsv2-page-intro__lede {
    margin: 0;
    max-width: 720px;
    font: 400 20px/30px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
@media (min-width: 1200px) {
    .gsv2-page-intro__lede { font: 400 24px/34px var(--gs-font-sans); }
}
.gsv2-page-intro__chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 24px;
}
.gsv2-chip {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 10px 18px;
    background: transparent;
    border: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: 500 14px/1 var(--gs-font-sans);
    letter-spacing: 0;
    transition: border-color 180ms ease, background 180ms ease, color 180ms ease;
}
.gsv2-chip:hover {
    border-color: var(--gs-uitk-color-text-neutral-bold);
    background: rgba(0, 0, 0, 0.04);
}
.gsv2-chip--active {
    background: var(--gs-uitk-color-text-neutral-bold);
    color: #FFFFFF;
    border-color: var(--gs-uitk-color-text-neutral-bold);
}

.gsv2-chip-mini {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 3px 8px;
    background: rgba(0, 0, 0, 0.06);
    color: var(--gs-uitk-color-text-neutral-bold);
    font: 500 11px/14px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1px;
}
.gsv2-chip-mini--podcast { background: rgba(160, 64, 140, 0.12); color: #6F2A5C; }
.gsv2-chip-mini--video   { background: rgba(21, 151, 136, 0.12); color: #0F6E62; }
.gsv2-chip-mini--article { background: rgba(0, 0, 0, 0.06); }
.gsv2-chip-mini--inverse { background: rgba(255, 255, 255, 0.18); color: #FFFFFF; }

/* ───────── FEATURED HERO TILE ───────── */
.gsv2-feature {
    padding: 0;
    background: var(--gs-uitk-color-surface-neutral-minimal);
}
.gsv2-feature__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 16px 24px 64px;
}
@media (min-width: 768px) { .gsv2-feature__inner { padding: 16px 48px 80px; } }
@media (min-width: 1200px) { .gsv2-feature__inner { padding: 24px 64px 96px; } }
.gsv2-feature__tile {
    position: relative;
    display: block;
    aspect-ratio: 21 / 9;
    overflow: hidden;
    color: #FFFFFF;
    background: #0B1624;
}
@media (max-width: 767px) { .gsv2-feature__tile { aspect-ratio: 4 / 5; } }
.gsv2-feature__image {
    position: absolute; inset: 0;
}
.gsv2-feature__image img {
    width: 100%; height: 100%; object-fit: cover;
    transition: transform 600ms ease;
}
.gsv2-feature__tile:hover .gsv2-feature__image img { transform: scale(1.04); }
.gsv2-feature__overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.10) 30%, rgba(0,0,0,0.85) 100%);
}
.gsv2-feature__body {
    position: absolute;
    inset: auto 0 0 0;
    padding: 48px 36px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 1100px;
}
@media (min-width: 1200px) { .gsv2-feature__body { padding: 64px 56px; } }
.gsv2-feature__title {
    margin: 0;
    font: 300 36px/40px var(--gs-font-serif-prism);
    color: #FFFFFF;
    max-width: 920px;
}
@media (min-width: 768px) {
    .gsv2-feature__title { font: 300 56px/60px var(--gs-font-serif-prism); }
}
@media (min-width: 1200px) {
    .gsv2-feature__title { font: 300 72px/76px var(--gs-font-serif-prism); }
}
.gsv2-feature__meta {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
}
.gsv2-feature__date {
    font: 400 14px/18px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.78);
    letter-spacing: 0.4px;
}
.gsv2-feature__cta {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font: 500 16px/20px var(--gs-font-sans);
    color: #FFFFFF;
    border-bottom: 2px solid #FFFFFF;
    padding-bottom: 4px;
}

/* ───────── SECTIONS ───────── */
.gsv2-section {
    padding: 64px 0;
    background: var(--gs-uitk-color-surface-neutral-minimal);
}
@media (min-width: 1200px) { .gsv2-section { padding: 88px 0; } }
.gsv2-section--subtle { background: var(--gs-uitk-color-surface-neutral-subtle); }
.gsv2-section--brand { background: #F0EBE6; }
.gsv2-section--dark { background: #0B1624; color: #FFFFFF; }
.gsv2-section__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
}
@media (min-width: 768px) { .gsv2-section__inner { padding: 0 48px; } }
@media (min-width: 1200px) { .gsv2-section__inner { padding: 0 64px; } }

.gsv2-section__header {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    margin-bottom: 36px;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding-bottom: 16px;
    flex-wrap: wrap;
    gap: 16px;
}
.gsv2-section__title {
    margin: 0;
    font: 500 28px/32px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
@media (min-width: 1200px) {
    .gsv2-section__title { font: 500 36px/42px var(--gs-font-sans); }
}
.gsv2-section__title--inset { margin-top: 48px; }
.gsv2-section__lede {
    margin: 12px 0 0;
    max-width: 720px;
    font: 400 18px/28px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-section__link {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-brand);
    letter-spacing: 0.4px;
    text-transform: uppercase;
    transition: gap 180ms ease;
}
.gsv2-section__link:hover { gap: 10px; }
.gsv2-section__filters {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}
.gsv2-section__more { display: flex; justify-content: center; margin-top: 32px; }

/* ───────── GRID + CARDS ───────── */
.gsv2-grid {
    display: grid;
    gap: 32px;
    grid-template-columns: 1fr;
}
@media (min-width: 768px) {
    .gsv2-grid--2 { grid-template-columns: repeat(2, 1fr); }
    .gsv2-grid--3 { grid-template-columns: repeat(3, 1fr); }
    .gsv2-grid--4 { grid-template-columns: repeat(2, 1fr); }
}
@media (min-width: 1200px) {
    .gsv2-grid--4 { grid-template-columns: repeat(4, 1fr); gap: 28px; }
}

.gsv2-card {
    background: var(--gs-uitk-color-surface-neutral-minimal);
    transition: transform 200ms ease;
}
.gsv2-card__link {
    display: flex;
    flex-direction: column;
    height: 100%;
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-card__image {
    aspect-ratio: 16 / 9;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-neutral-regular);
}
.gsv2-card__image img {
    width: 100%; height: 100%; object-fit: cover;
    transition: transform 600ms ease;
}
.gsv2-card__link:hover .gsv2-card__image img { transform: scale(1.05); }
.gsv2-card__body {
    padding: 20px 0 0;
    display: flex;
    flex-direction: column;
    gap: 10px;
    flex: 1;
}
.gsv2-card__eyebrow {
    font: 700 11px/14px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-card__title {
    margin: 0;
    font: 500 20px/26px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    transition: color 180ms ease;
}
.gsv2-card__link:hover .gsv2-card__title {
    color: var(--gs-uitk-color-text-brand);
}
@media (min-width: 1200px) {
    .gsv2-card__title { font: 500 22px/28px var(--gs-font-sans); }
}
.gsv2-card__excerpt {
    margin: 0;
    font: 400 15px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
    flex: 1;
}
.gsv2-card__meta {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: auto;
    padding-top: 4px;
    flex-wrap: wrap;
}
.gsv2-card__date {
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    letter-spacing: 0.3px;
}
.gsv2-card--compact .gsv2-card__title { font: 500 17px/22px var(--gs-font-sans); }
.gsv2-card--compact .gsv2-card__body { padding-top: 14px; gap: 8px; }

/* ───────── IN FOCUS BAND ───────── */
.gsv2-in-focus {
    background: #0B1624;
    color: #FFFFFF;
    padding: 80px 0;
    position: relative;
    overflow: hidden;
}
.gsv2-in-focus::before {
    content: "";
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 80% 20%, rgba(114, 151, 197, 0.22) 0%, transparent 60%);
    pointer-events: none;
}
.gsv2-in-focus__inner {
    position: relative;
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 56px;
}
@media (min-width: 768px) { .gsv2-in-focus__inner { padding: 0 48px; } }
@media (min-width: 1200px) {
    .gsv2-in-focus { padding: 112px 0; }
    .gsv2-in-focus__inner { padding: 0 64px; grid-template-columns: 380px 1fr; gap: 80px; align-items: start; }
}
.gsv2-in-focus__header {
    display: flex;
    flex-direction: column;
    gap: 24px;
}
.gsv2-in-focus__title {
    margin: 0;
    font: 300 48px/52px var(--gs-font-serif-prism);
    color: #FFFFFF;
}
@media (min-width: 1200px) {
    .gsv2-in-focus__title { font: 300 80px/84px var(--gs-font-serif-prism); }
}
.gsv2-in-focus__lede {
    margin: 0;
    font: 400 18px/28px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.78);
}

/* In-focus mosaic: 6 tiles in a 4-column rhythm */
.gsv2-mosaic {
    display: grid;
    grid-template-columns: 1fr;
    gap: 16px;
}
@media (min-width: 768px) {
    .gsv2-mosaic {
        grid-template-columns: repeat(4, 1fr);
        grid-auto-rows: 200px;
    }
    .gsv2-mosaic__tile--lg { grid-column: span 2; grid-row: span 2; }
    .gsv2-mosaic__tile--md { grid-column: span 2; grid-row: span 1; }
    .gsv2-mosaic__tile--sm { grid-column: span 1; grid-row: span 1; }
}
@media (min-width: 1200px) {
    .gsv2-mosaic { grid-auto-rows: 240px; gap: 20px; }
}
.gsv2-mosaic__tile {
    position: relative;
    overflow: hidden;
    color: #FFFFFF;
    background: #0F2440;
    min-height: 220px;
}
.gsv2-mosaic__image { position: absolute; inset: 0; }
.gsv2-mosaic__image img {
    width: 100%; height: 100%; object-fit: cover;
    transition: transform 600ms ease;
}
.gsv2-mosaic__tile:hover .gsv2-mosaic__image img { transform: scale(1.06); }
.gsv2-mosaic__overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.20) 30%, rgba(0,0,0,0.78) 100%);
}
.gsv2-mosaic__body {
    position: absolute; inset: auto 0 0 0;
    padding: 22px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.gsv2-mosaic__title {
    margin: 0;
    font: 500 18px/24px var(--gs-font-sans);
    color: #FFFFFF;
}
.gsv2-mosaic__tile--lg .gsv2-mosaic__title {
    font: 500 26px/32px var(--gs-font-sans);
}
@media (min-width: 1200px) {
    .gsv2-mosaic__tile--lg .gsv2-mosaic__title {
        font: 500 32px/38px var(--gs-font-sans);
    }
}
.gsv2-mosaic__meta {
    display: flex;
    align-items: center;
    gap: 10px;
    flex-wrap: wrap;
}
.gsv2-mosaic__date {
    font: 400 12px/16px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.72);
    letter-spacing: 0.4px;
}

/* ───────── SERIES TILES ───────── */
.gsv2-series-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 16px;
}
@media (min-width: 768px) {
    .gsv2-series-grid { grid-template-columns: repeat(2, 1fr); gap: 20px; }
}
@media (min-width: 1200px) {
    .gsv2-series-grid { grid-template-columns: repeat(4, 1fr); }
}
.gsv2-series {
    position: relative;
    aspect-ratio: 3 / 4;
    overflow: hidden;
    background: #0B1624;
    color: #FFFFFF;
}
.gsv2-series__image { position: absolute; inset: 0; }
.gsv2-series__image img { width: 100%; height: 100%; object-fit: cover; transition: transform 500ms ease; }
.gsv2-series:hover .gsv2-series__image img { transform: scale(1.05); }
.gsv2-series__overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.30) 0%, rgba(0,0,0,0.85) 100%);
}
.gsv2-series__body {
    position: absolute; inset: auto 0 0 0;
    padding: 24px 22px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.gsv2-series__title {
    margin: 0;
    font: 500 24px/28px var(--gs-font-sans);
    color: #FFFFFF;
}
.gsv2-series__count {
    margin: 0;
    font: 400 12px/16px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.72);
    letter-spacing: 0.5px;
    text-transform: uppercase;
}

/* ───────── BUTTONS ───────── */
.gsv2-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 24px;
    border: 1px solid transparent;
    font: 500 14px/1 var(--gs-font-sans);
    letter-spacing: 0.4px;
    cursor: pointer;
    transition: background 200ms ease, color 200ms ease, border-color 200ms ease, transform 180ms ease;
}
.gsv2-button:hover { transform: translateY(-1px); }
.gsv2-button--primary {
    background: var(--gs-uitk-color-text-neutral-bold);
    color: #FFFFFF;
    border-color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-button--primary:hover { background: #1A1A1A; }
.gsv2-button--primary-light {
    background: #FFFFFF;
    color: #000000;
    border-color: #FFFFFF;
}
.gsv2-button--primary-light:hover { background: rgba(255, 255, 255, 0.92); }
.gsv2-button--ghost-dark {
    background: transparent;
    color: var(--gs-uitk-color-text-neutral-bold);
    border-color: var(--gs-uitk-color-border-neutral-bold);
}
.gsv2-button--ghost-dark:hover { background: rgba(0, 0, 0, 0.04); }
.gsv2-button--ghost-light {
    background: transparent;
    color: #FFFFFF;
    border-color: rgba(255, 255, 255, 0.55);
}
.gsv2-button--ghost-light:hover {
    background: rgba(255, 255, 255, 0.10);
    border-color: #FFFFFF;
}

/* ───────── TOPIC PAGE ───────── */
.gsv2-topic-hero,
.gsv2-pillar-hero,
.gsv2-article-hero {
    position: relative;
    min-height: 520px;
    overflow: hidden;
    color: #FFFFFF;
    background: #0B1624;
    display: flex;
    align-items: flex-end;
}
.gsv2-topic-hero__image,
.gsv2-pillar-hero__image,
.gsv2-article-hero__image { position: absolute; inset: 0; }
.gsv2-topic-hero__image img,
.gsv2-pillar-hero__image img,
.gsv2-article-hero__image img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-topic-hero__overlay,
.gsv2-pillar-hero__overlay,
.gsv2-article-hero__overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.20) 30%, rgba(0,0,0,0.85) 100%);
}
.gsv2-topic-hero__inner,
.gsv2-pillar-hero__inner,
.gsv2-article-hero__inner {
    position: relative;
    width: 100%;
    max-width: 1440px;
    margin: 0 auto;
    padding: 64px 24px 56px;
    display: flex;
    flex-direction: column;
    gap: 18px;
}
@media (min-width: 768px) {
    .gsv2-topic-hero__inner,
    .gsv2-pillar-hero__inner,
    .gsv2-article-hero__inner { padding: 96px 48px 80px; }
}
@media (min-width: 1200px) {
    .gsv2-topic-hero__inner,
    .gsv2-pillar-hero__inner,
    .gsv2-article-hero__inner { padding: 144px 64px 112px; }
}
.gsv2-topic-hero__title,
.gsv2-pillar-hero__title {
    margin: 0;
    font: 300 48px/52px var(--gs-font-serif-prism);
    max-width: 880px;
    color: #FFFFFF;
}
@media (min-width: 1200px) {
    .gsv2-topic-hero__title,
    .gsv2-pillar-hero__title { font: 300 80px/84px var(--gs-font-serif-prism); }
}
.gsv2-article-hero__title {
    margin: 0;
    font: 300 40px/44px var(--gs-font-serif-prism);
    color: #FFFFFF;
    max-width: 920px;
}
@media (min-width: 1200px) {
    .gsv2-article-hero__title { font: 300 64px/68px var(--gs-font-serif-prism); }
}
.gsv2-topic-hero__lede,
.gsv2-pillar-hero__lede,
.gsv2-article-hero__deck {
    margin: 0;
    max-width: 720px;
    font: 400 18px/28px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.86);
}
.gsv2-topic-hero__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 36px;
    margin-top: 24px;
    padding-top: 24px;
    border-top: 1px solid rgba(255, 255, 255, 0.20);
    max-width: 720px;
}
.gsv2-topic-stat { display: flex; flex-direction: column; gap: 4px; }
.gsv2-topic-stat__numeral {
    font: 300 44px/48px var(--gs-font-sans-condensed);
    color: #FFFFFF;
}
.gsv2-topic-stat__caption {
    font: 400 13px/18px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.72);
    max-width: 220px;
}

.gsv2-breadcrumb {
    display: flex;
    align-items: center;
    gap: 8px;
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin-bottom: 4px;
}
.gsv2-breadcrumb a {
    color: var(--gs-uitk-color-text-brand);
    text-decoration: none;
}
.gsv2-breadcrumb a:hover { text-decoration: underline; }
.gsv2-breadcrumb__current {
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-breadcrumb--inverse,
.gsv2-breadcrumb--inverse a,
.gsv2-breadcrumb--inverse .gsv2-breadcrumb__current {
    color: rgba(255, 255, 255, 0.78);
}
.gsv2-breadcrumb--inverse .gsv2-breadcrumb__current {
    color: #FFFFFF;
}

.gsv2-secondary-nav {
    background: #FFFFFF;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    position: sticky;
    top: 88px;
    z-index: 70;
}
.gsv2-nav.is-scrolled + main .gsv2-secondary-nav { top: 64px; }
.gsv2-secondary-nav__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
}
@media (min-width: 768px) { .gsv2-secondary-nav__inner { padding: 0 48px; } }
@media (min-width: 1200px) { .gsv2-secondary-nav__inner { padding: 0 64px; } }
.gsv2-secondary-nav__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 32px;
    overflow-x: auto;
}
.gsv2-secondary-nav__item a {
    display: inline-block;
    padding: 16px 0;
    font: 500 14px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    border-bottom: 3px solid transparent;
    transition: color 180ms ease, border-color 180ms ease;
    white-space: nowrap;
    letter-spacing: 0.2px;
}
.gsv2-secondary-nav__item a:hover { color: var(--gs-uitk-color-text-neutral-bold); }
.gsv2-secondary-nav__item--active a {
    color: var(--gs-uitk-color-text-neutral-bold);
    border-bottom-color: var(--gs-uitk-color-text-neutral-bold);
}

/* ───────── FEATURE ROW (1 lead + 2 side) ───────── */
.gsv2-feature-row {
    display: grid;
    grid-template-columns: 1fr;
    gap: 32px;
}
@media (min-width: 1024px) {
    .gsv2-feature-row { grid-template-columns: 1.6fr 1fr; gap: 40px; }
}
.gsv2-feature-row__lead { display: flex; flex-direction: column; gap: 20px; color: inherit; }
.gsv2-feature-row__image { aspect-ratio: 16 / 9; overflow: hidden; background: var(--gs-uitk-color-surface-neutral-regular); }
.gsv2-feature-row__image img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-feature-row__body { display: flex; flex-direction: column; gap: 10px; }
.gsv2-feature-row__title {
    margin: 0;
    font: 500 28px/34px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
@media (min-width: 1200px) {
    .gsv2-feature-row__title { font: 500 36px/42px var(--gs-font-sans); }
}
.gsv2-feature-row__excerpt {
    margin: 0;
    font: 400 16px/24px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-feature-row__side {
    display: flex;
    flex-direction: column;
    gap: 24px;
}
.gsv2-feature-row__side-card {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 16px;
    color: inherit;
}
.gsv2-feature-row__side-image { aspect-ratio: 4 / 3; overflow: hidden; background: var(--gs-uitk-color-surface-neutral-regular); }
.gsv2-feature-row__side-image img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-feature-row__side-body { display: flex; flex-direction: column; gap: 6px; }
.gsv2-feature-row__side-title {
    margin: 0;
    font: 500 16px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}

/* ───────── PILLAR PAGE BITS ───────── */
.gsv2-rankings {
    background: #FFFFFF;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}
.gsv2-rankings__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 32px 24px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 24px;
    align-items: center;
}
@media (min-width: 768px) {
    .gsv2-rankings__inner { padding: 32px 48px; grid-template-columns: repeat(4, 1fr); }
}
@media (min-width: 1200px) {
    .gsv2-rankings__inner { padding: 40px 64px; }
}
.gsv2-rankings__item { display: flex; flex-direction: column; gap: 6px; }
.gsv2-rankings__numeral {
    font: 300 56px/56px var(--gs-font-sans-condensed);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-rankings__label {
    font: 500 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
    text-transform: uppercase;
    letter-spacing: 0.6px;
}
.gsv2-rankings__legal {
    grid-column: 1 / -1;
    font: 400 11px/16px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    margin: 0;
}

.gsv2-offerings {
    display: grid;
    grid-template-columns: 1fr;
    gap: 28px;
}
@media (min-width: 768px) { .gsv2-offerings { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1200px) { .gsv2-offerings { grid-template-columns: repeat(3, 1fr); gap: 36px; } }
.gsv2-offering {
    padding: 32px;
    background: #FFFFFF;
    border: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: flex;
    flex-direction: column;
    gap: 16px;
}
.gsv2-offering__icon {
    width: 56px;
    height: 56px;
    background: #F0EBE6;
    color: var(--gs-uitk-color-text-brand);
    display: inline-flex;
    align-items: center;
    justify-content: center;
}
.gsv2-offering__title {
    margin: 0;
    font: 500 22px/28px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-offering__body {
    margin: 0;
    font: 400 15px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-offering__links {
    list-style: none;
    margin: auto 0 0;
    padding: 16px 0 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.gsv2-offering__links a {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-brand);
}
.gsv2-offering__links a:hover { gap: 10px; }

.gsv2-deals {
    display: grid;
    grid-template-columns: 1fr;
    gap: 28px;
}
@media (min-width: 768px) { .gsv2-deals { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1200px) { .gsv2-deals { grid-template-columns: repeat(3, 1fr); } }
.gsv2-deal { background: #FFFFFF; }
.gsv2-deal__image { aspect-ratio: 16 / 9; overflow: hidden; }
.gsv2-deal__image img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-deal__body { padding: 24px; display: flex; flex-direction: column; gap: 12px; }
.gsv2-deal__title {
    margin: 0;
    font: 500 20px/26px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-deal__role {
    margin: 0;
    font: 400 14px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-deal__facts {
    list-style: none;
    margin: 8px 0 0;
    padding: 12px 0 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
}
.gsv2-deal__fact-label {
    display: block;
    font: 700 10px/14px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-deal__fact-value {
    display: block;
    font: 500 16px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    margin-top: 2px;
}

.gsv2-leaders {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 24px;
}
@media (min-width: 768px) { .gsv2-leaders { grid-template-columns: repeat(3, 1fr); } }
@media (min-width: 1200px) { .gsv2-leaders { grid-template-columns: repeat(5, 1fr); } }
.gsv2-leader { display: flex; flex-direction: column; gap: 10px; }
.gsv2-leader__avatar { aspect-ratio: 3 / 4; overflow: hidden; background: var(--gs-uitk-color-surface-neutral-regular); }
.gsv2-leader__avatar img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-leader__name {
    margin: 8px 0 0;
    font: 500 15px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-leader__title {
    margin: 0;
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

/* ───────── CONTRIBUTORS / CAREERS / VOICES ───────── */
.gsv2-contributors {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 24px;
}
@media (min-width: 768px) { .gsv2-contributors { grid-template-columns: repeat(4, 1fr); } }
.gsv2-contributor { display: flex; flex-direction: column; gap: 8px; }
.gsv2-contributor__avatar { aspect-ratio: 1; overflow: hidden; background: var(--gs-uitk-color-surface-neutral-regular); border-radius: 0; }
.gsv2-contributor__avatar img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-contributor__name { margin: 8px 0 0; font: 500 16px/22px var(--gs-font-sans); }
.gsv2-contributor__title { margin: 0; font: 400 13px/18px var(--gs-font-sans); color: var(--gs-uitk-color-text-neutral-minimal); }

/* Careers students program cards */
.gsv2-program-card {
    background: #FFFFFF;
    border: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding: 32px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    transition: border-color 200ms ease, transform 200ms ease;
}
.gsv2-program-card:hover { border-color: var(--gs-uitk-color-text-neutral-bold); transform: translateY(-2px); }
.gsv2-program-card__eyebrow {
    font: 700 11px/14px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--gs-uitk-color-text-brand);
}
.gsv2-program-card__title {
    margin: 0;
    font: 500 24px/30px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-program-card__body {
    margin: 0;
    font: 400 15px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-program-card__facts {
    list-style: none;
    margin: 0;
    padding: 12px 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.gsv2-program-card__facts li {
    display: flex;
    justify-content: space-between;
    gap: 12px;
}
.gsv2-program-card__fact-label {
    font: 500 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-program-card__fact-value {
    font: 500 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    text-align: right;
}
.gsv2-program-card__cta {
    margin-top: auto;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-brand);
}
.gsv2-program-card__cta:hover { gap: 10px; }

.gsv2-division-card {
    position: relative;
    overflow: hidden;
    background: #0B1624;
    color: #FFFFFF;
    aspect-ratio: 4 / 5;
}
.gsv2-division-card__image { position: absolute; inset: 0; }
.gsv2-division-card__image img { width: 100%; height: 100%; object-fit: cover; transition: transform 500ms ease; }
.gsv2-division-card:hover .gsv2-division-card__image img { transform: scale(1.05); }
.gsv2-division-card__overlay {
    position: absolute; inset: 0;
    background: linear-gradient(180deg, rgba(0,0,0,0.20) 30%, rgba(0,0,0,0.85) 100%);
}
.gsv2-division-card__body {
    position: absolute; inset: auto 0 0 0;
    padding: 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
}
.gsv2-division-card__title {
    margin: 0;
    font: 500 24px/28px var(--gs-font-sans);
    color: #FFFFFF;
}
.gsv2-division-card__body-text {
    margin: 0;
    font: 400 13px/18px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.82);
}

.gsv2-voices {
    display: grid;
    grid-template-columns: 1fr;
    gap: 32px;
}
@media (min-width: 768px) { .gsv2-voices { grid-template-columns: repeat(3, 1fr); } }
.gsv2-voice {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 28px;
    background: #FFFFFF;
    border-left: 3px solid var(--gs-uitk-color-text-brand);
}
.gsv2-voice__avatar { width: 56px; height: 56px; overflow: hidden; background: var(--gs-uitk-color-surface-neutral-regular); }
.gsv2-voice__avatar img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-voice__quote {
    margin: 0;
    font: 300 italic 22px/30px var(--gs-font-serif-prism);
    color: var(--gs-uitk-color-text-neutral-bold);
    quotes: "\201C" "\201D";
}
.gsv2-voice__quote::before { content: open-quote; }
.gsv2-voice__quote::after { content: close-quote; }
.gsv2-voice__name {
    margin: 0;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-voice__title {
    margin: 0;
    font: 400 12px/16px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

.gsv2-stats-strip {
    background: #FFFFFF;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}
.gsv2-stats-strip__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 32px 24px;
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 20px;
}
@media (min-width: 768px) {
    .gsv2-stats-strip__inner { padding: 40px 48px; grid-template-columns: repeat(4, 1fr); }
}
@media (min-width: 1200px) {
    .gsv2-stats-strip__inner { padding: 48px 64px; }
}
.gsv2-stats-strip__item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    border-left: 2px solid var(--gs-uitk-color-text-brand);
    padding-left: 18px;
}
.gsv2-stats-strip__numeral {
    font: 300 44px/48px var(--gs-font-sans-condensed);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-stats-strip__caption {
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

.gsv2-steps {
    list-style: none;
    margin: 0;
    padding: 0;
    counter-reset: gsv2-step;
    display: grid;
    grid-template-columns: 1fr;
    gap: 28px;
}
@media (min-width: 768px) { .gsv2-steps { grid-template-columns: repeat(2, 1fr); } }
@media (min-width: 1200px) { .gsv2-steps { grid-template-columns: repeat(4, 1fr); } }
.gsv2-steps__item {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 28px;
    background: #FFFFFF;
    border-top: 3px solid var(--gs-uitk-color-text-brand);
}
.gsv2-steps__numeral {
    font: 300 56px/56px var(--gs-font-sans-condensed);
    color: var(--gs-uitk-color-text-brand);
    letter-spacing: -1px;
}
.gsv2-steps__title {
    margin: 0;
    font: 500 18px/24px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-steps__text {
    margin: 0;
    font: 400 14px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}

/* ───────── ARTICLE BODY ───────── */
.gsv2-byline-strip {
    background: #FFFFFF;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}
.gsv2-byline-strip__inner {
    max-width: 880px;
    margin: 0 auto;
    padding: 24px 24px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
@media (min-width: 768px) {
    .gsv2-byline-strip__inner {
        padding: 24px 48px;
        flex-direction: row;
        align-items: center;
        justify-content: space-between;
    }
}
.gsv2-byline-strip__authors {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.gsv2-byline-strip__name {
    font: 500 15px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-byline-strip__title {
    margin-left: 6px;
    font: 400 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-byline-strip__meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font: 400 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-subtle);
}
.gsv2-byline-strip__share {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    margin-left: 12px;
    padding: 8px 14px;
    background: transparent;
    color: var(--gs-uitk-color-text-neutral-bold);
    border: 1px solid var(--gs-uitk-color-border-neutral-subtle);
    font: 500 13px/1 var(--gs-font-sans);
}
.gsv2-byline-strip__share:hover { background: rgba(0, 0, 0, 0.04); }

.gsv2-article-body {
    max-width: 880px;
    margin: 0 auto;
    padding: 56px 24px 80px;
}
@media (min-width: 768px) {
    .gsv2-article-body { padding: 64px 48px 96px; }
}
.gsv2-article-body p,
.gsv2-article-body ul,
.gsv2-article-body ol {
    margin: 0 0 24px;
    font: 400 19px/30px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-article-body__deck {
    font: 300 24px/34px var(--gs-font-serif-prism) !important;
    color: var(--gs-uitk-color-text-neutral-bold) !important;
    margin-bottom: 32px !important;
}
.gsv2-article-body h2 {
    margin: 48px 0 24px;
    font: 500 30px/36px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-article-body h3 {
    margin: 32px 0 16px;
    font: 500 22px/28px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-numbered-list {
    list-style: none;
    padding: 0;
    margin: 32px 0;
    display: flex;
    flex-direction: column;
    gap: 28px;
}
.gsv2-numbered-list li {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 20px;
    align-items: start;
}
.gsv2-numbered-list__num {
    font: 300 48px/48px var(--gs-font-sans-condensed);
    color: var(--gs-uitk-color-text-brand);
    line-height: 1;
}
.gsv2-numbered-list li p {
    margin: 0;
    font: 400 17px/26px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-pull-quote {
    margin: 40px 0;
    padding: 24px 0;
    border-top: 1px solid var(--gs-uitk-color-text-brand);
    border-bottom: 1px solid var(--gs-uitk-color-text-brand);
}
.gsv2-pull-quote p {
    margin: 0;
    font: 300 italic 28px/38px var(--gs-font-serif-prism);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-pull-quote cite {
    display: block;
    margin-top: 16px;
    font: 500 13px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
    font-style: normal;
    letter-spacing: 0.4px;
}
.gsv2-callout {
    margin: 32px 0;
    padding: 28px 32px;
    background: #F0EBE6;
    border-left: 4px solid var(--gs-uitk-color-text-brand);
}
.gsv2-callout__title {
    margin: 0 0 12px;
    font: 700 14px/18px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--gs-uitk-color-text-brand);
}
.gsv2-callout p {
    margin: 0;
    font: 400 16px/24px var(--gs-font-sans) !important;
    color: var(--gs-uitk-color-text-neutral-bold) !important;
}
.gsv2-footnotes {
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
}
.gsv2-footnotes h3 {
    margin: 0 0 16px !important;
    font: 700 12px/16px var(--gs-font-sans) !important;
    text-transform: uppercase !important;
    letter-spacing: 1.2px !important;
    color: var(--gs-uitk-color-text-neutral-minimal) !important;
}
.gsv2-footnotes p {
    margin: 0 0 12px;
    font: 400 13px/20px var(--gs-font-sans) !important;
    color: var(--gs-uitk-color-text-neutral-minimal) !important;
}
.gsv2-article-share {
    margin-top: 48px;
    padding-top: 24px;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    display: flex;
    align-items: center;
    gap: 24px;
    flex-wrap: wrap;
}
.gsv2-article-share span {
    font: 700 12px/16px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-article-share ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    gap: 16px;
}
.gsv2-article-share a {
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-brand);
    border-bottom: 1px solid var(--gs-uitk-color-text-brand);
}

.gsv2-related {
    background: var(--gs-uitk-color-surface-neutral-subtle);
    padding: 80px 0;
}

/* ───────── PODCAST DETAIL ───────── */
.gsv2-article-hero--podcast { min-height: 480px; }
.gsv2-article-hero__meta {
    display: flex;
    gap: 10px;
    font: 400 14px/20px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.86);
}

.gsv2-podcast-layout {
    display: grid;
    grid-template-columns: 1fr;
    gap: 48px;
}
@media (min-width: 1024px) {
    .gsv2-podcast-layout { grid-template-columns: 2fr 1fr; gap: 64px; }
}
.gsv2-podcast-text {
    margin: 0 0 18px;
    font: 400 17px/28px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-podcast-player {
    background: #0B1624;
    color: #FFFFFF;
    padding: 24px 28px;
    display: flex;
    align-items: center;
    gap: 24px;
}
.gsv2-podcast-player__play {
    width: 56px;
    height: 56px;
    background: #FFFFFF;
    color: #0B1624;
    border: none;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.gsv2-podcast-player__meta { flex: 1; display: flex; flex-direction: column; gap: 14px; }
.gsv2-podcast-player__title { display: flex; flex-direction: column; gap: 4px; }
.gsv2-podcast-player__title .gsv2-eyebrow { color: rgba(255, 255, 255, 0.72); }
.gsv2-podcast-player__title p {
    margin: 0;
    font: 500 18px/24px var(--gs-font-sans);
    color: #FFFFFF;
}
.gsv2-podcast-player__bar {
    display: flex;
    align-items: center;
    gap: 14px;
}
.gsv2-podcast-player__time {
    font: 400 12px/16px var(--gs-font-mono);
    color: rgba(255, 255, 255, 0.72);
    flex-shrink: 0;
}
.gsv2-podcast-player__track {
    flex: 1;
    height: 4px;
    background: rgba(255, 255, 255, 0.18);
    position: relative;
}
.gsv2-podcast-player__progress {
    position: absolute;
    inset: 0 70% 0 0;
    background: var(--gs-uitk-color-text-brand);
}
.gsv2-podcast-subscribe {
    margin-top: 32px;
    background: #F7F7FA;
    padding: 24px 28px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.gsv2-podcast-subscribe__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 14px 28px;
}
.gsv2-podcast-subscribe__list a {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-brand);
}

.gsv2-chapters {
    list-style: none;
    margin: 0 0 32px;
    padding: 0;
    counter-reset: gsv2-chap;
}
.gsv2-chapters li { border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal); }
.gsv2-chapters li:last-child { border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal); }
.gsv2-chapters__btn {
    width: 100%;
    background: transparent;
    border: none;
    padding: 18px 0;
    display: grid;
    grid-template-columns: 100px 1fr 24px;
    gap: 20px;
    align-items: center;
    text-align: left;
    color: var(--gs-uitk-color-text-neutral-bold);
    transition: background 180ms ease;
}
.gsv2-chapters__btn:hover { background: rgba(0, 0, 0, 0.03); padding-left: 12px; padding-right: 12px; }
.gsv2-chapters__time {
    font: 500 14px/18px var(--gs-font-mono);
    color: var(--gs-uitk-color-text-brand);
}
.gsv2-chapters__label {
    font: 400 16px/22px var(--gs-font-sans);
}
.gsv2-chapters__play {
    width: 28px; height: 28px;
    background: var(--gs-uitk-color-text-neutral-bold);
    color: #FFFFFF;
    display: inline-flex;
    align-items: center;
    justify-content: center;
}

.gsv2-transcript {
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    padding-top: 24px;
}
.gsv2-transcript__line {
    display: grid;
    grid-template-columns: 140px 60px 1fr;
    gap: 16px;
    align-items: start;
    padding: 12px 0;
    border-bottom: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    font: 400 15px/22px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
    margin: 0;
}
.gsv2-transcript__speaker {
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-transcript__time {
    font: 400 12px/16px var(--gs-font-mono);
    color: var(--gs-uitk-color-text-neutral-minimal);
}

.gsv2-podcast-side {
    display: flex;
    flex-direction: column;
    gap: 24px;
    padding: 28px;
    background: #F7F7FA;
    height: fit-content;
    position: sticky;
    top: 180px;
}
.gsv2-podcast-personas {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 18px;
}
.gsv2-podcast-personas li {
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 14px;
    align-items: center;
}
.gsv2-podcast-persona__avatar {
    width: 64px;
    height: 64px;
    overflow: hidden;
    background: var(--gs-uitk-color-surface-neutral-regular);
}
.gsv2-podcast-persona__avatar img { width: 100%; height: 100%; object-fit: cover; }
.gsv2-podcast-persona__name {
    margin: 0;
    font: 500 14px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-podcast-persona__title {
    margin: 2px 0 0;
    font: 400 12px/16px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-podcast-related {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
}
.gsv2-podcast-related a {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 0;
    border-top: 1px solid var(--gs-uitk-color-border-neutral-minimal);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-podcast-related a:first-child { border-top: none; padding-top: 0; }
.gsv2-podcast-related a p {
    margin: 0;
    font: 500 14px/20px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
}

/* ───────── BRIEFINGS NEWSLETTER ───────── */
.gsv2-briefings {
    background: #F0EBE6;
    padding: 80px 0;
}
.gsv2-briefings__inner {
    max-width: 1100px;
    margin: 0 auto;
    padding: 0 24px;
    display: grid;
    grid-template-columns: 1fr;
    gap: 32px;
}
@media (min-width: 768px) { .gsv2-briefings__inner { padding: 0 48px; grid-template-columns: 1fr 1fr; gap: 56px; align-items: center; } }
.gsv2-briefings__title {
    margin: 8px 0 16px;
    font: 300 48px/52px var(--gs-font-serif-prism);
    color: var(--gs-uitk-color-text-neutral-bold);
}
.gsv2-briefings__lede {
    margin: 0;
    font: 400 18px/28px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-regular);
}
.gsv2-briefings__form { display: flex; flex-direction: column; gap: 16px; }
.gsv2-briefings__row {
    display: grid;
    grid-template-columns: 1fr;
    border: 1px solid var(--gs-uitk-color-border-neutral-bold);
    background: #FFFFFF;
}
@media (min-width: 600px) {
    .gsv2-briefings__row { grid-template-columns: 1fr auto; }
}
.gsv2-briefings__input {
    height: 56px;
    padding: 0 18px;
    border: none;
    background: transparent;
    font: 400 16px/24px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-bold);
    outline: none;
}
.gsv2-briefings__submit {
    height: 56px;
    padding: 0 32px;
    background: var(--gs-uitk-color-text-neutral-bold);
    color: #FFFFFF;
    border: none;
    font: 500 14px/1 var(--gs-font-sans);
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    letter-spacing: 0.4px;
}
.gsv2-briefings__submit:hover { background: #1A1A1A; }
.gsv2-briefings__legal {
    margin: 0;
    font: 400 12px/18px var(--gs-font-sans);
    color: var(--gs-uitk-color-text-neutral-minimal);
}
.gsv2-briefings__legal a {
    color: var(--gs-uitk-color-text-brand);
    text-decoration: underline;
}

/* ───────── FOOTER ───────── */
.gsv2-footer {
    background: #0B1624;
    color: rgba(255, 255, 255, 0.82);
    padding: 80px 0 40px;
}
.gsv2-footer__inner {
    max-width: 1440px;
    margin: 0 auto;
    padding: 0 24px;
}
@media (min-width: 768px) { .gsv2-footer__inner { padding: 0 48px; } }
@media (min-width: 1200px) { .gsv2-footer__inner { padding: 0 64px; } }
.gsv2-footer__columns {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 36px;
    margin-bottom: 48px;
}
@media (min-width: 768px) { .gsv2-footer__columns { grid-template-columns: repeat(5, 1fr); } }
.gsv2-footer__col-title {
    margin: 0 0 16px;
    font: 700 12px/16px var(--gs-font-sans);
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #FFFFFF;
}
.gsv2-footer__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.gsv2-footer__list a {
    font: 400 14px/20px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.78);
    transition: color 180ms ease;
}
.gsv2-footer__list a:hover { color: #FFFFFF; }
.gsv2-footer__bottom {
    border-top: 1px solid rgba(255, 255, 255, 0.10);
    padding: 24px 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
    font: 400 12px/18px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.62);
}
@media (min-width: 768px) {
    .gsv2-footer__bottom { flex-direction: row; align-items: center; justify-content: space-between; }
}
.gsv2-footer__bottom-links {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
}
.gsv2-footer__bottom-links a { color: rgba(255, 255, 255, 0.62); transition: color 180ms ease; }
.gsv2-footer__bottom-links a:hover { color: #FFFFFF; }
.gsv2-footer__v1-link {
    margin-top: 24px;
    padding: 18px 22px;
    background: rgba(255, 255, 255, 0.06);
    border-left: 3px solid var(--gs-uitk-color-text-brand);
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.gsv2-footer__v1-link .gsv2-eyebrow {
    color: rgba(255, 255, 255, 0.72);
}
.gsv2-footer__v1-link p {
    margin: 0;
    font: 400 13px/20px var(--gs-font-sans);
    color: rgba(255, 255, 255, 0.78);
}
.gsv2-footer__v1-link a {
    color: var(--gs-uitk-color-text-brand);
    text-decoration: underline;
}
"""


# ════════════════════════════════════════════════════════════════════════
# JAVASCRIPT — mega-menu chrome
# ════════════════════════════════════════════════════════════════════════
# Vanilla, no dependencies. Mounts a single click/hover/keyboard state
# machine that drives the open/close state of any number of mega-menu
# panels, the search overlay, and the sticky-shrink behaviour. Serves
# from a dedicated route so the base template can include it via
# {% url 'gs_reference_companion:js' %}.

_JS_COMPANION = r"""// gs_reference_companion mega-menu chrome.
(function () {
    'use strict';

    var INTENT_DELAY_MS = 140;
    var openTimer = null;
    var closeTimer = null;
    var activeKey = null;

    var nav = document.querySelector('[data-nav]');
    if (!nav) { return; }

    var triggers = Array.prototype.slice.call(
        nav.querySelectorAll('[data-mega-trigger]'));
    var buttons = Array.prototype.slice.call(
        nav.querySelectorAll('[data-mega-button]'));
    var panels = {};
    Array.prototype.slice.call(nav.querySelectorAll('[data-mega-panel]'))
        .forEach(function (p) { panels[p.getAttribute('data-mega-panel')] = p; });
    var backdrop = nav.querySelector('[data-mega-backdrop]');
    var searchBtn = nav.querySelector('[data-search-toggle]');
    var searchPanel = nav.querySelector('[data-search-panel]');
    var searchClose = nav.querySelector('[data-search-close]');
    var searchInput = nav.querySelector('.gsv2-search__input');

    function openMenu(key) {
        clearTimeout(closeTimer);
        if (activeKey === key) { return; }
        if (activeKey) { closeMenu(activeKey, /* instant */ true); }
        var panel = panels[key];
        var trigger = triggers.filter(function (t) {
            return t.getAttribute('data-mega-trigger') === key;
        })[0];
        if (!panel || !trigger) { return; }
        panel.classList.add('is-open');
        panel.setAttribute('aria-hidden', 'false');
        trigger.classList.add('is-open');
        var button = trigger.querySelector('[data-mega-button]');
        if (button) { button.setAttribute('aria-expanded', 'true'); }
        backdrop.classList.add('is-active');
        backdrop.setAttribute('aria-hidden', 'false');
        nav.classList.add('is-mega-open');
        closeSearch();
        activeKey = key;
    }

    function closeMenu(key, instant) {
        if (!key) { return; }
        var panel = panels[key];
        var trigger = triggers.filter(function (t) {
            return t.getAttribute('data-mega-trigger') === key;
        })[0];
        if (!panel) { return; }
        panel.classList.remove('is-open');
        panel.setAttribute('aria-hidden', 'true');
        if (trigger) {
            trigger.classList.remove('is-open');
            var button = trigger.querySelector('[data-mega-button]');
            if (button) { button.setAttribute('aria-expanded', 'false'); }
        }
        if (activeKey === key) {
            activeKey = null;
            backdrop.classList.remove('is-active');
            backdrop.setAttribute('aria-hidden', 'true');
            nav.classList.remove('is-mega-open');
        }
    }

    function closeAllMenus() {
        if (activeKey) { closeMenu(activeKey, true); }
        activeKey = null;
        backdrop.classList.remove('is-active');
        backdrop.setAttribute('aria-hidden', 'true');
        nav.classList.remove('is-mega-open');
    }

    triggers.forEach(function (trigger) {
        var key = trigger.getAttribute('data-mega-trigger');
        var button = trigger.querySelector('[data-mega-button]');

        trigger.addEventListener('mouseenter', function () {
            clearTimeout(closeTimer);
            clearTimeout(openTimer);
            openTimer = setTimeout(function () { openMenu(key); }, INTENT_DELAY_MS);
        });

        trigger.addEventListener('mouseleave', function () {
            clearTimeout(openTimer);
            closeTimer = setTimeout(function () {
                if (activeKey === key) { closeMenu(key); }
            }, 200);
        });

        if (button) {
            button.addEventListener('click', function (event) {
                event.preventDefault();
                if (activeKey === key) {
                    closeMenu(key);
                } else {
                    openMenu(key);
                    var firstLink = panels[key].querySelector('.gsv2-mega__link');
                    if (firstLink) { firstLink.focus(); }
                }
            });

            button.addEventListener('keydown', function (event) {
                if (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault();
                    openMenu(key);
                    var firstLink = panels[key].querySelector('.gsv2-mega__link');
                    if (firstLink) { firstLink.focus(); }
                }
                if (event.key === 'Escape') { closeMenu(key); button.focus(); }
            });
        }

        var panel = panels[key];
        if (panel) {
            panel.addEventListener('mouseenter', function () {
                clearTimeout(closeTimer);
            });
            panel.addEventListener('mouseleave', function () {
                closeTimer = setTimeout(function () { closeMenu(key); }, 200);
            });
            panel.addEventListener('keydown', function (event) {
                if (event.key === 'Escape') { closeMenu(key); button && button.focus(); }
            });
        }
    });

    backdrop.addEventListener('click', closeAllMenus);

    document.addEventListener('click', function (event) {
        if (!activeKey) { return; }
        var t = event.target;
        if (!t.closest('[data-mega-trigger]') &&
            !t.closest('[data-mega-panel]') &&
            !t.closest('[data-mega-backdrop]')) {
            closeAllMenus();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
            closeAllMenus();
            closeSearch();
        }
    });

    // Search overlay
    function openSearch() {
        if (!searchPanel) { return; }
        closeAllMenus();
        searchPanel.classList.add('is-open');
        searchPanel.setAttribute('aria-hidden', 'false');
        nav.classList.add('is-mega-open');
        backdrop.classList.add('is-active');
        backdrop.setAttribute('aria-hidden', 'false');
        setTimeout(function () { if (searchInput) { searchInput.focus(); } }, 80);
    }
    function closeSearch() {
        if (!searchPanel) { return; }
        searchPanel.classList.remove('is-open');
        searchPanel.setAttribute('aria-hidden', 'true');
        if (!activeKey) {
            nav.classList.remove('is-mega-open');
            backdrop.classList.remove('is-active');
            backdrop.setAttribute('aria-hidden', 'true');
        }
    }
    if (searchBtn) { searchBtn.addEventListener('click', openSearch); }
    if (searchClose) { searchClose.addEventListener('click', closeSearch); }
    if (backdrop) { backdrop.addEventListener('click', closeSearch); }

    // Sticky-shrink on scroll
    var lastY = 0;
    var ticking = false;
    function onScroll() {
        var y = window.scrollY || window.pageYOffset;
        if (y > 32) {
            nav.classList.add('is-scrolled');
        } else {
            nav.classList.remove('is-scrolled');
        }
        lastY = y;
        ticking = false;
    }
    window.addEventListener('scroll', function () {
        if (!ticking) {
            window.requestAnimationFrame(onScroll);
            ticking = true;
        }
    }, { passive: true });
    onScroll();

    // Smooth scroll for in-page anchors (CSS scroll-behavior handles it
    // already; explicit handler here just to offset for the sticky header).
    document.querySelectorAll('a[href^="#"]').forEach(function (a) {
        a.addEventListener('click', function (event) {
            var href = a.getAttribute('href');
            if (!href || href === '#' || href.length < 2) { return; }
            var target = document.querySelector(href);
            if (!target) { return; }
            event.preventDefault();
            var headerH = nav.classList.contains('is-scrolled') ? 64 : 88;
            var top = target.getBoundingClientRect().top + window.scrollY - headerH - 8;
            window.scrollTo({ top: top, behavior: 'smooth' });
        });
    });
})();
"""


def _build_css() -> str:
    fonts_url = config['fonts_url_prefix'].rstrip('/')
    fonts_resolved = _SHARED_FONTS_CSS.replace('__GS_FONTS_URL__', fonts_url)
    return _SHARED_TOKENS_CSS + '\n\n' + fonts_resolved + '\n\n' + _CSS_COMPANION


# ════════════════════════════════════════════════════════════════════════
# TEMPLATE ENGINE
# ════════════════════════════════════════════════════════════════════════

_engine: Optional[Engine] = None


def _make_engine() -> Engine:
    return Engine(
        loaders=[
            ('django.template.loaders.locmem.Loader', _TEMPLATES),
        ],
        libraries={'gsv2_extras': __name__},
        builtins=[
            'django.template.defaulttags',
            'django.template.defaultfilters',
            'django.template.loader_tags',
        ],
    )


def _render(template_name: str, context: Dict[str, Any], request) -> str:
    global _engine
    if _engine is None:
        _engine = _make_engine()
    template = _engine.get_template(template_name)
    ctx = Context(context)
    ctx['request'] = request
    return template.render(ctx)


# ════════════════════════════════════════════════════════════════════════
# NAV + MEGA-MENU SHARED CONTEXT
# ════════════════════════════════════════════════════════════════════════

def _u(name: str) -> str:
    return reverse(f'gs_reference_companion:{name}')


def _mega_menus() -> List[Dict[str, Any]]:
    """The four top-level mega-menus. Heavy data definition by design —
    each menu has 3 columns of links + 3 promo tiles."""

    return [
        {
            'key': 'what-we-do',
            'title': 'What We Do',
            'promos_title': 'Featured',
            'columns': [
                {
                    'title': 'Investment Banking',
                    'links': [
                        {'label': 'Investment Banking Home',
                         'description': 'Strategic advisory and capital solutions',
                         'url': _u('wwd_ib')},
                        {'label': 'Mergers & Acquisitions',
                         'description': 'Buy-side, sell-side, and strategic alternatives',
                         'url': _u('wwd_ib')},
                        {'label': 'Capital Solutions',
                         'description': 'Equity, debt, and structured products',
                         'url': _u('wwd_ib')},
                        {'label': 'Corporate Board Engagement',
                         'description': 'Director engagement & strategic placement',
                         'url': '#'},
                        {'label': 'FICC and Equities',
                         'description': 'Sales, trading and market-making',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Asset & Wealth Management',
                    'links': [
                        {'label': 'Asset & Wealth Management',
                         'description': 'Public and private market solutions',
                         'url': _u('wwd_aw')},
                        {'label': 'Asset Management',
                         'description': 'Active, quantitative, and indexed strategies',
                         'url': _u('wwd_aw')},
                        {'label': 'Wealth Management',
                         'description': 'Private wealth and Marcus by Goldman Sachs',
                         'url': _u('wwd_aw')},
                        {'label': 'Alternatives',
                         'description': 'PE, growth equity, credit, real estate',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Engineering & Platform',
                    'links': [
                        {'label': 'Engineering',
                         'description': 'Build the systems that move markets',
                         'url': '#'},
                        {'label': 'Platform Solutions',
                         'description': 'Transaction Banking and embedded finance',
                         'url': '#'},
                        {'label': 'Transaction Banking',
                         'description': 'API-first multi-currency cash management',
                         'url': '#'},
                        {'label': 'Apple Card Partnership',
                         'description': 'Consumer card co-brand at scale',
                         'url': '#'},
                    ],
                },
            ],
            'promos': [
                {
                    'eyebrow': 'M&A Outlook',
                    'title': '2026 Global M&A Outlook',
                    'tint': 'navy',
                    'format': 'Report',
                    'date': 'Jan 2026',
                    'url': '#',
                },
                {
                    'eyebrow': 'Industry',
                    'title': 'Sector Coverage: Industrials',
                    'tint': 'burnt',
                    'format': 'Hub',
                    'date': '',
                    'url': _u('wwd_ib'),
                },
                {
                    'eyebrow': 'Featured Deal',
                    'title': 'Acme Industries IPO Closes at $1.1B',
                    'tint': 'amber',
                    'format': 'Deal Spotlight',
                    'date': 'May 2026',
                    'url': '#',
                },
            ],
        },
        {
            'key': 'insights',
            'title': 'Insights',
            'promos_title': 'In Focus',
            'columns': [
                {
                    'title': 'Explore Insights',
                    'links': [
                        {'label': 'All Insights',
                         'description': 'Analysis across the firm',
                         'url': _u('insights')},
                        {'label': 'Macroeconomics',
                         'description': 'Global economy and policy outlook',
                         'url': _u('insights_macro')},
                        {'label': 'The Markets',
                         'description': 'Cross-asset commentary and trade ideas',
                         'url': '#'},
                        {'label': 'Outlooks 2026',
                         'description': 'Annual outlooks across asset classes',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Series',
                    'links': [
                        {'label': 'Exchanges',
                         'description': 'Flagship podcast on markets and policy',
                         'url': _u('insights_exchanges')},
                        {'label': 'Talks at GS',
                         'description': 'Long-form interviews across disciplines',
                         'url': _u('insights_talks')},
                        {'label': 'The Insight',
                         'description': 'Conversations with our partners',
                         'url': '#'},
                        {'label': 'BRIEFINGS Daily',
                         'description': 'Daily morning brief from the firm',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'By Topic',
                    'links': [
                        {'label': 'Artificial Intelligence',
                         'description': 'Capex, application and market structure',
                         'url': _u('article_tracking_trillions')},
                        {'label': 'Energy & Climate',
                         'description': 'Transition economics and electrification',
                         'url': _u('article_energy_crunch')},
                        {'label': 'Banking & Capital Markets',
                         'description': 'M&A, IPO, credit and debt issuance',
                         'url': '#'},
                        {'label': 'Geopolitics',
                         'description': 'Policy, conflict and economic statecraft',
                         'url': '#'},
                    ],
                },
            ],
            'promos': [
                {
                    'eyebrow': 'Artificial Intelligence',
                    'title': 'Tracking Trillions: The AI Build-Out',
                    'tint': 'navy',
                    'format': 'Article',
                    'date': 'May 1, 2026',
                    'url': _u('article_tracking_trillions'),
                },
                {
                    'eyebrow': 'The Markets',
                    'title': 'Jerome Dortmans on Oil Markets',
                    'tint': 'burnt',
                    'format': 'Podcast',
                    'date': 'May 8, 2026',
                    'url': _u('podcast_jerome_dortmans'),
                },
                {
                    'eyebrow': 'Energy',
                    'title': "Europe's Electrification Shift",
                    'tint': 'olive',
                    'format': 'Article',
                    'date': 'May 5, 2026',
                    'url': _u('article_energy_crunch'),
                },
            ],
        },
        {
            'key': 'our-firm',
            'title': 'Our Firm',
            'promos_title': 'Discover',
            'columns': [
                {
                    'title': 'About Us',
                    'links': [
                        {'label': 'Our Purpose and Values',
                         'description': 'Four shared principles that anchor the firm',
                         'url': '#'},
                        {'label': 'History',
                         'description': '150 years of building enduring partnerships',
                         'url': '#'},
                        {'label': 'Newsroom',
                         'description': 'Press releases and media inquiries',
                         'url': '#'},
                        {'label': 'Leadership',
                         'description': 'Meet our board and senior leadership',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Sustainability & Impact',
                    'links': [
                        {'label': 'Sustainability',
                         'description': 'Climate, transition finance and reporting',
                         'url': '#'},
                        {'label': 'One Million Black Women',
                         'description': '$10B investment commitment',
                         'url': '#'},
                        {'label': '10,000 Small Businesses',
                         'description': 'Education, capital and support',
                         'url': '#'},
                        {'label': 'Community Engagement',
                         'description': 'Local partnerships across our footprint',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Stakeholders',
                    'links': [
                        {'label': 'Investor Relations',
                         'description': 'Quarterly earnings, filings and events',
                         'url': '#'},
                        {'label': 'Governance',
                         'description': 'Code of conduct and board oversight',
                         'url': '#'},
                        {'label': 'Diversity',
                         'description': 'Our approach and progress',
                         'url': '#'},
                        {'label': 'Alumni',
                         'description': 'Stay connected to the firm',
                         'url': '#'},
                    ],
                },
            ],
            'promos': [
                {
                    'eyebrow': 'Annual Report',
                    'title': '2025 Annual Report',
                    'tint': 'brown',
                    'format': 'Report',
                    'date': 'Feb 2026',
                    'url': '#',
                },
                {
                    'eyebrow': 'Sustainability',
                    'title': 'Sustainability Issuance Framework',
                    'tint': 'teal',
                    'format': 'Document',
                    'date': '',
                    'url': '#',
                },
                {
                    'eyebrow': 'Heritage',
                    'title': 'Discover the History of the Firm',
                    'tint': 'mauve',
                    'format': 'Story',
                    'date': '',
                    'url': '#',
                },
            ],
        },
        {
            'key': 'careers',
            'title': 'Careers',
            'promos_title': 'Highlights',
            'columns': [
                {
                    'title': 'Start Here',
                    'links': [
                        {'label': 'Careers Home',
                         'description': 'Your pursuit of exceptional starts here',
                         'url': '#'},
                        {'label': 'Search Jobs',
                         'description': 'Open roles by location and division',
                         'url': '#'},
                        {'label': 'Why Goldman Sachs',
                         'description': "What it's like to work here",
                         'url': '#'},
                        {'label': 'Application Process',
                         'description': 'Step-by-step expectations',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Programs',
                    'links': [
                        {'label': 'Students & Graduates',
                         'description': 'Internships, full-time and apprenticeship',
                         'url': _u('careers_students')},
                        {'label': 'Engineering Essentials',
                         'description': 'Build the systems that move markets',
                         'url': '#'},
                        {'label': 'Returnship Program',
                         'description': 'For experienced professionals re-entering',
                         'url': '#'},
                        {'label': 'Veteran Programs',
                         'description': 'Pathways for military veterans',
                         'url': '#'},
                    ],
                },
                {
                    'title': 'Inside the Firm',
                    'links': [
                        {'label': 'Life at the Firm',
                         'description': 'Profiles, voices and stories',
                         'url': '#'},
                        {'label': 'Our People',
                         'description': 'Meet colleagues across divisions',
                         'url': '#'},
                        {'label': 'Benefits & Wellness',
                         'description': 'Healthcare, family care, leave',
                         'url': '#'},
                        {'label': 'Learning & Development',
                         'description': 'Mentorship and growth resources',
                         'url': '#'},
                    ],
                },
            ],
            'promos': [
                {
                    'eyebrow': 'Now Hiring',
                    'title': 'Summer 2027 Internship Applications Open',
                    'tint': 'purple',
                    'format': 'Program',
                    'date': 'Apply by Oct 2026',
                    'url': _u('careers_students'),
                },
                {
                    'eyebrow': 'Voices',
                    'title': 'A Day with the Quant Research Team',
                    'tint': 'navy',
                    'format': 'Video',
                    'date': '',
                    'url': '#',
                },
                {
                    'eyebrow': 'Engineering',
                    'title': 'How We Built Sub-10us Order Routing',
                    'tint': 'teal',
                    'format': 'Story',
                    'date': '',
                    'url': '#',
                },
            ],
        },
    ]


NAV_ITEMS = [
    ('what-we-do', 'What We Do'),
    ('insights',   'Insights'),
    ('our-firm',   'Our Firm'),
    ('careers',    'Careers'),
]


def _base_context(request, active_nav: Optional[str] = None) -> Dict[str, Any]:
    return {
        'nav_items': [{'key': k, 'label': l} for k, l in NAV_ITEMS],
        'active_nav': active_nav,
        'mega_menus': _mega_menus(),
        'request': request,
        'v1_label': config['v1_mount_label'],
    }


# ════════════════════════════════════════════════════════════════════════
# CONTENT FACTORIES — placeholder dicts for each page
# ════════════════════════════════════════════════════════════════════════

def _insights_index_content() -> Dict[str, Any]:
    return {
        'featured': {
            'eyebrow': 'Artificial Intelligence',
            'title': 'Tracking Trillions: The Assumptions Shaping the Scale of the AI Build-Out',
            'date': 'May 1, 2026',
            'tint': 'navy',
            'url': _u('article_tracking_trillions'),
        },
        'latest': [
            {
                'eyebrow': 'The Markets',
                'title': 'Jerome Dortmans on the Drivers of Oil Markets',
                'format': 'Podcast',
                'format_slug': 'podcast',
                'date': 'May 8, 2026',
                'tint': 'burnt',
                'url': _u('podcast_jerome_dortmans'),
            },
            {
                'eyebrow': 'Energy',
                'title': "The Energy Crunch Could Accelerate Europe's Shift to Electrification",
                'format': 'Article',
                'format_slug': 'article',
                'date': 'May 5, 2026',
                'tint': 'olive',
                'url': _u('article_energy_crunch'),
            },
            {
                'eyebrow': 'Exchanges',
                'title': 'How Warsh Could Shape Fed Policy',
                'format': 'Podcast',
                'format_slug': 'podcast',
                'date': 'Apr 28, 2026',
                'tint': 'purple',
                'url': _u('insights_exchanges'),
            },
        ],
        'in_focus_tiles': [
            {
                'eyebrow': 'Artificial Intelligence',
                'title': 'Tracking Trillions: The Assumptions Shaping the AI Build-Out',
                'tint': 'navy',
                'size': 'lg',
                'aspect': '4x3',
                'format': 'Article',
                'date': 'May 1, 2026',
                'url': _u('article_tracking_trillions'),
            },
            {
                'eyebrow': 'Quantitative Investing',
                'title': 'How AI Is Changing Quantitative Investing',
                'tint': 'mauve',
                'size': 'md',
                'aspect': '16x9',
                'format': 'Podcast',
                'date': 'Apr 22, 2026',
                'url': '#',
            },
            {
                'eyebrow': 'Macro',
                'title': 'AI Capex and the Productivity Question',
                'tint': 'teal',
                'size': 'sm',
                'aspect': '4x3',
                'format': 'Article',
                'date': 'Apr 15, 2026',
                'url': '#',
            },
            {
                'eyebrow': 'Credit',
                'title': 'Funding Models for Hyperscaler Buildouts',
                'tint': 'amber',
                'size': 'sm',
                'aspect': '4x3',
                'format': 'Article',
                'date': 'Apr 03, 2026',
                'url': '#',
            },
            {
                'eyebrow': 'Equities',
                'title': 'Sectoral Dispersion in the AI Beneficiaries Trade',
                'tint': 'purple',
                'size': 'md',
                'aspect': '16x9',
                'format': 'Video',
                'date': 'Apr 10, 2026',
                'url': '#',
            },
            {
                'eyebrow': 'Talks at GS',
                'title': 'AI Conviction Without the Hype: A Conversation',
                'tint': 'navy',
                'size': 'sm',
                'aspect': '4x3',
                'format': 'Podcast',
                'date': 'Mar 28, 2026',
                'url': _u('insights_talks'),
            },
        ],
        'all_insights': [
            {'eyebrow': 'Macroeconomics', 'title': 'Sturdy Growth, Stagnant Jobs, Stable Prices',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 22, 2026', 'tint': 'navy', 'url': _u('insights_macro')},
            {'eyebrow': 'Equities', 'title': 'S&P 500 at 12%: A Year of Outperformance',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 19, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'Exchanges', 'title': 'Outlook 2026 Episode 3: Assets and Allocation',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 15, 2026', 'tint': 'burnt', 'url': _u('insights_exchanges')},
            {'eyebrow': 'Sustainability', 'title': 'Transition Finance: A Practitioner Lens',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 12, 2026', 'tint': 'olive', 'url': '#'},
            {'eyebrow': 'M&A', 'title': '2026 Global M&A: Volume Inflects on Rate Cuts',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 09, 2026', 'tint': 'amber', 'url': '#'},
            {'eyebrow': 'Markets', 'title': 'A Steepener Trade for the Next Cutting Cycle',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 04, 2026', 'tint': 'purple', 'url': '#'},
            {'eyebrow': 'Talks at GS', 'title': 'On Capital Discipline, with Sara Hypothetical',
             'format': 'Video', 'format_slug': 'video', 'date': 'Mar 31, 2026', 'tint': 'teal', 'url': _u('insights_talks')},
            {'eyebrow': 'Geopolitics', 'title': 'Economic Statecraft in 2026: A Tactical Map',
             'format': 'Article', 'format_slug': 'article', 'date': 'Mar 25, 2026', 'tint': 'brown', 'url': '#'},
        ],
        'series_tiles': [
            {
                'eyebrow': 'Series',
                'title': 'Goldman Sachs Exchanges',
                'episode_count': '120+ episodes · weekly',
                'tint': 'navy',
                'url': _u('insights_exchanges'),
            },
            {
                'eyebrow': 'Series',
                'title': 'Talks at GS',
                'episode_count': '60+ interviews · long-form',
                'tint': 'mauve',
                'url': _u('insights_talks'),
            },
            {
                'eyebrow': 'Series',
                'title': 'The Markets',
                'episode_count': 'Cross-asset weekly · podcast',
                'tint': 'burnt',
                'url': _u('podcast_jerome_dortmans'),
            },
            {
                'eyebrow': 'Series',
                'title': 'BRIEFINGS Daily',
                'episode_count': 'Newsletter · M-F',
                'tint': 'teal',
                'url': '#',
            },
        ],
    }


def _topic_macro() -> Dict[str, Any]:
    return {
        'title': 'Macroeconomics',
        'eyebrow': 'Insights · Topic',
        'tint': 'navy',
        'lede': (
            'Worldwide economic forecasts, policy commentary, and regime '
            'analysis from Goldman Sachs Research and our investment teams.'
        ),
        'stats': [
            {'numeral': '2.8%', 'caption': 'Global GDP growth forecast for 2026'},
            {'numeral': '2.6%', 'caption': 'US GDP growth (vs. 2.0% consensus)'},
            {'numeral': '12%', 'caption': 'Forecast S&P 500 total return 2026'},
        ],
        'tabs': [
            {'label': 'Overview', 'url': '#', 'active': True},
            {'label': 'Outlook 2026', 'url': '#'},
            {'label': 'Regional', 'url': '#'},
            {'label': 'Policy', 'url': '#'},
            {'label': 'Inflation', 'url': '#'},
            {'label': 'Labor', 'url': '#'},
        ],
        'formats': ['Articles', 'Podcasts', 'Videos', 'Reports'],
        'archive_title': 'Latest in Macroeconomics',
        'featured_lead': {
            'eyebrow': 'Outlook 2026',
            'title': 'Sturdy Growth, Stagnant Jobs, Stable Prices',
            'excerpt': (
                'Our macro team unpacks the 2026 outlook for advanced economies, '
                'with particular attention to the divergence between resilient '
                'consumer demand and weakening labor formation.'
            ),
            'format': 'Article',
            'format_slug': 'article',
            'date': 'Apr 22, 2026',
            'tint': 'navy',
            'url': '#',
        },
        'featured_side': [
            {'eyebrow': 'US Macro', 'title': 'Why US Growth Should Outperform Consensus Again',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 18, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'EU Macro', 'title': 'Germany at 1.1%: Industrial Recovery Slow but Real',
             'format': 'Video', 'format_slug': 'video', 'date': 'Apr 14, 2026', 'tint': 'olive', 'url': '#'},
            {'eyebrow': 'China', 'title': "China's 4.8% Path Through Property Drag",
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 09, 2026', 'tint': 'burnt', 'url': '#'},
        ],
        'archive': [
            {'eyebrow': 'Policy', 'title': 'Fed Path: Two Cuts, Two Holds, One Surprise',
             'excerpt': 'A scenario-based view on the FOMC reaction function through 2026.',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 25, 2026', 'tint': 'navy', 'url': '#'},
            {'eyebrow': 'Inflation', 'title': 'Goods vs. Services: Where Disinflation Is Still Coming',
             'excerpt': 'Sub-component analysis suggests core services inflation has more room to fall.',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 20, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'Labor', 'title': 'Why Payroll Strength Coexists With Weaker Hours',
             'excerpt': 'Composition effects in 2026 labor data, with implications for wage growth.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 16, 2026', 'tint': 'olive', 'url': '#'},
            {'eyebrow': 'Trade', 'title': 'Tariff Pass-Through, Six Months In',
             'excerpt': 'Where corporate margins absorbed cost vs. where pricing power held.',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 11, 2026', 'tint': 'burnt', 'url': '#'},
            {'eyebrow': 'EMs', 'title': 'EM Resilience and the Dollar',
             'excerpt': 'Cross-asset positioning given softer DXY and improving terms-of-trade.',
             'format': 'Video', 'format_slug': 'video', 'date': 'Apr 07, 2026', 'tint': 'teal', 'url': '#'},
            {'eyebrow': 'Outlook', 'title': 'Why 2026 Looks More 2017 Than 2018',
             'excerpt': 'A historical regime comparison and what it implies for risk assets.',
             'format': 'Article', 'format_slug': 'article', 'date': 'Apr 03, 2026', 'tint': 'amber', 'url': '#'},
        ],
        'contributors': [
            {'name': 'Dr. Marlena Hypothetical', 'title': 'Chief US Economist', 'tint': 'navy'},
            {'name': 'Cyrus Placeholder', 'title': 'Chief Economist, Europe', 'tint': 'mauve'},
            {'name': 'Pri Lorem-ipsum', 'title': 'Head of Asia Macro', 'tint': 'teal'},
            {'name': 'Niko Sample-Stein', 'title': 'Global Markets Strategist', 'tint': 'olive'},
        ],
    }


def _topic_exchanges() -> Dict[str, Any]:
    return {
        'title': 'Exchanges',
        'eyebrow': 'Insights · Series',
        'tint': 'mauve',
        'lede': (
            'Our flagship podcast featuring conversations with senior '
            'leaders, investors and economists across markets, policy and '
            'technology. New episodes every week.'
        ),
        'stats': [
            {'numeral': '120+', 'caption': 'Episodes published since 2014'},
            {'numeral': '#3', 'caption': 'Apple Podcasts business chart (Mar 2026)'},
            {'numeral': '32min', 'caption': 'Average episode runtime'},
        ],
        'tabs': [
            {'label': 'Latest', 'url': '#', 'active': True},
            {'label': 'Outlook Series', 'url': '#'},
            {'label': 'Top of Mind', 'url': '#'},
            {'label': 'Trading', 'url': '#'},
            {'label': 'Special Episodes', 'url': '#'},
        ],
        'formats': ['Audio', 'Video', 'Transcript'],
        'archive_title': 'All Episodes',
        'featured_lead': {
            'eyebrow': 'Outlook 2026',
            'title': 'Episode 1: The Big Picture — Global Economy and Markets',
            'excerpt': (
                'Allison Nathan sits down with our chief economist and '
                'global head of markets for a wide-ranging conversation '
                'on what to expect in 2026.'
            ),
            'format': 'Podcast',
            'format_slug': 'podcast',
            'date': 'Apr 28, 2026',
            'tint': 'mauve',
            'url': _u('podcast_jerome_dortmans'),
        },
        'featured_side': [
            {'eyebrow': 'Outlook 2026', 'title': 'Episode 2: Regional Perspectives',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 21, 2026', 'tint': 'navy', 'url': '#'},
            {'eyebrow': 'Outlook 2026', 'title': 'Episode 3: Assets and Allocation',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 14, 2026', 'tint': 'burnt', 'url': '#'},
            {'eyebrow': 'Special', 'title': "How Warsh Could Shape Fed Policy",
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 09, 2026', 'tint': 'purple', 'url': '#'},
        ],
        'archive': [
            {'eyebrow': 'Conviction', 'title': 'AI Conviction Beyond the Hype: A Practitioner View',
             'excerpt': "A panel of investors discusses how they're sizing positions in the AI ecosystem.",
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Apr 02, 2026', 'tint': 'navy', 'url': '#'},
            {'eyebrow': 'Energy', 'title': 'Power, Compute and the New Capex Map',
             'excerpt': 'A discussion of where the next $1T in data center capex actually lands.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Mar 26, 2026', 'tint': 'olive', 'url': '#'},
            {'eyebrow': 'Credit', 'title': 'Private Credit at the Cycle Inflection',
             'excerpt': 'What recent dispersion in private credit returns means for allocators.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Mar 19, 2026', 'tint': 'amber', 'url': '#'},
            {'eyebrow': 'Geopolitics', 'title': 'The Economic Statecraft Playbook',
             'excerpt': 'A look at the tools governments use to deploy capital strategically.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Mar 12, 2026', 'tint': 'brown', 'url': '#'},
            {'eyebrow': 'Quant', 'title': 'When Models Disagree: A Quant Roundtable',
             'excerpt': 'Three quant strategists on regime detection and the limits of backtests.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Mar 05, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'Markets', 'title': 'What the Curve Is (and Is Not) Telling You',
             'excerpt': 'A grounded conversation on yield-curve signals heading into the cutting cycle.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Feb 27, 2026', 'tint': 'teal', 'url': '#'},
        ],
        'contributors': [
            {'name': 'Allison Hypothetical-Nathan', 'title': 'Host, Goldman Sachs Exchanges', 'tint': 'mauve'},
            {'name': 'Christian Placeholder', 'title': 'Senior Producer', 'tint': 'navy'},
            {'name': 'Beatriz Sample', 'title': 'Editor', 'tint': 'olive'},
            {'name': 'Diego Fictional', 'title': 'Researcher', 'tint': 'amber'},
        ],
    }


def _topic_talks() -> Dict[str, Any]:
    return {
        'title': 'Talks at GS',
        'eyebrow': 'Insights · Series',
        'tint': 'teal',
        'lede': (
            'Long-form, in-depth conversations with leaders across business, '
            'sport, science, arts and policy — recorded in front of an '
            'audience at Goldman Sachs offices around the world.'
        ),
        'stats': [
            {'numeral': '60+', 'caption': 'Interviews since launch'},
            {'numeral': '45m', 'caption': 'Average interview length'},
            {'numeral': '12', 'caption': 'Disciplines represented'},
        ],
        'tabs': [
            {'label': 'Latest', 'url': '#', 'active': True},
            {'label': 'Business', 'url': '#'},
            {'label': 'Sport', 'url': '#'},
            {'label': 'Science', 'url': '#'},
            {'label': 'Arts', 'url': '#'},
            {'label': 'Policy', 'url': '#'},
        ],
        'formats': ['Video', 'Podcast', 'Transcript'],
        'archive_title': 'Featured Interviews',
        'featured_lead': {
            'eyebrow': 'Featured',
            'title': 'On Capital Discipline and the Discipline of Capital',
            'excerpt': (
                "Sara Hypothetical, CEO of a leading global industrials "
                'business, on how she rebuilt the firm around return-on-capital '
                'as the organising principle.'
            ),
            'format': 'Video',
            'format_slug': 'video',
            'date': 'Mar 31, 2026',
            'tint': 'teal',
            'url': '#',
        },
        'featured_side': [
            {'eyebrow': 'Sport', 'title': 'The Architecture of Winning Cultures',
             'format': 'Video', 'format_slug': 'video', 'date': 'Mar 22, 2026', 'tint': 'amber', 'url': '#'},
            {'eyebrow': 'Science', 'title': 'On Bayes, Bias and What a Lab Actually Does',
             'format': 'Video', 'format_slug': 'video', 'date': 'Mar 15, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'Arts', 'title': 'Making Things People Actually Use',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Mar 08, 2026', 'tint': 'olive', 'url': '#'},
        ],
        'archive': [
            {'eyebrow': 'Business', 'title': 'The Founder Mindset at Public-Company Scale',
             'excerpt': 'A late-stage founder on how he kept startup discipline through the IPO.',
             'format': 'Video', 'format_slug': 'video', 'date': 'Feb 28, 2026', 'tint': 'navy', 'url': '#'},
            {'eyebrow': 'Sport', 'title': 'On Coaching the Coach',
             'excerpt': "A storied head coach unpacks what makes great managers in any field.",
             'format': 'Video', 'format_slug': 'video', 'date': 'Feb 21, 2026', 'tint': 'amber', 'url': '#'},
            {'eyebrow': 'Tech', 'title': 'Frontier Research Outside Big Labs',
             'excerpt': 'On building independent labs and the case for technical pluralism.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Feb 14, 2026', 'tint': 'mauve', 'url': '#'},
            {'eyebrow': 'Markets', 'title': 'A Trader on Conviction and Cost',
             'excerpt': 'How a veteran allocator weighs the cost of being wrong against the cost of being late.',
             'format': 'Video', 'format_slug': 'video', 'date': 'Feb 07, 2026', 'tint': 'burnt', 'url': '#'},
            {'eyebrow': 'Arts', 'title': 'A Maker on Mastery',
             'excerpt': 'A craftsperson on the long arc from apprentice to expert.',
             'format': 'Video', 'format_slug': 'video', 'date': 'Jan 31, 2026', 'tint': 'olive', 'url': '#'},
            {'eyebrow': 'Policy', 'title': 'On Industrial Strategy',
             'excerpt': 'A former cabinet minister on what works and what does not.',
             'format': 'Podcast', 'format_slug': 'podcast', 'date': 'Jan 24, 2026', 'tint': 'brown', 'url': '#'},
        ],
        'contributors': [
            {'name': 'Jenna Sample-Beck', 'title': 'Host & Editorial Director', 'tint': 'teal'},
            {'name': 'Raul Placeholder', 'title': 'Producer', 'tint': 'navy'},
            {'name': 'Ines Hypothetical', 'title': 'Researcher', 'tint': 'mauve'},
        ],
    }


def _pillar_ib() -> Dict[str, Any]:
    return {
        'title': 'Investment Banking',
        'short_title': 'Investment Banking',
        'eyebrow': 'What We Do',
        'tint': 'navy',
        'lede': (
            'We provide strategic advisory and financing to corporations, '
            'institutions, governments and entrepreneurs around the world, '
            'across every stage of the deal lifecycle.'
        ),
        'tabs': [
            {'label': 'Overview', 'url': '#', 'active': True},
            {'label': 'M&A', 'url': '#'},
            {'label': 'Capital Solutions', 'url': '#'},
            {'label': 'Industries', 'url': '#'},
            {'label': 'Insights', 'url': '#'},
            {'label': 'Featured Deals', 'url': '#'},
        ],
        'rankings': [
            {'numeral': '#1', 'label': 'Global Investment Bank'},
            {'numeral': '#1', 'label': 'Global M&A Advisor'},
            {'numeral': '#1', 'label': 'Global ECM Franchise'},
            {'numeral': 'Top 5', 'label': 'Global DCM Underwriter'},
        ],
        'rankings_legal': (
            'Source: Dealogic 2025 league tables. Rankings shown are '
            'illustrative for layout demonstration only.'
        ),
        'offerings_title': 'How We Work',
        'offerings_lede': (
            'A sector-deep, geographically connected platform combining '
            'strategic counsel with the execution capability to bring '
            'transactions across the line.'
        ),
        'offerings': [
            {
                'icon': 'briefcase',
                'title': 'Mergers & Acquisitions',
                'body': (
                    'End-to-end advisory across buy-side, sell-side, and '
                    'cross-border situations, anchored in sector depth.'
                ),
                'links': ['Strategic Alternatives', 'Cross-Border M&A', 'Defensive Advisory'],
            },
            {
                'icon': 'compass',
                'title': 'Capital Solutions',
                'body': (
                    'Underwriting, structuring and distribution across the '
                    'full capital stack — public equity, debt, hybrid and '
                    'structured products.'
                ),
                'links': ['Equity Capital Markets', 'Investment-Grade DCM', 'Leveraged Finance', 'Structured Finance'],
            },
            {
                'icon': 'document',
                'title': 'Corporate Board Engagement',
                'body': (
                    'Strategic dialogue with boards and senior leadership '
                    'on shareholder issues, governance, and capital allocation.'
                ),
                'links': ['Director Engagement', 'Shareholder Activism Defense', 'Governance Counsel'],
            },
        ],
        'deals': [
            {
                'eyebrow': 'Deal Spotlight',
                'title': "Acme Industries $1.1B IPO",
                'role': "Lead bookrunner and stabilization agent",
                'tint': 'amber',
                'facts': [
                    {'label': 'Size', 'value': '$1.1B'},
                    {'label': 'Pricing', 'value': '13.7x EBITDA'},
                    {'label': 'Aftermarket', 'value': '+24%'},
                    {'label': 'Pricing date', 'value': 'May 2026'},
                ],
            },
            {
                'eyebrow': 'Deal Spotlight',
                'title': 'Northstar Logistics $10.5B Acquisition',
                'role': 'Lead financial advisor to Northstar',
                'tint': 'teal',
                'facts': [
                    {'label': 'Size', 'value': '$10.5B'},
                    {'label': 'Cash / Stock', 'value': '70 / 30'},
                    {'label': 'Synergies', 'value': '$320M run-rate'},
                    {'label': 'Closing', 'value': 'Q4 2026 expected'},
                ],
            },
            {
                'eyebrow': 'Deal Spotlight',
                'title': "Helios Energy $2.5B Sustainable Bond Offering",
                'role': 'Joint global coordinator and structuring agent',
                'tint': 'olive',
                'facts': [
                    {'label': 'Size', 'value': '$2.5B'},
                    {'label': 'Tenors', 'value': '5 / 10 / 30 year'},
                    {'label': 'Coupon (avg)', 'value': '4.85%'},
                    {'label': 'Order book', 'value': '4.2x covered'},
                ],
            },
        ],
        'insights': [
            {
                'eyebrow': 'M&A',
                'title': '2026 Global M&A Outlook: Volume Inflects on Rate Cuts',
                'format': 'Article',
                'format_slug': 'article',
                'date': 'Apr 09, 2026',
                'tint': 'navy',
                'url': '#',
            },
            {
                'eyebrow': 'Capital Markets',
                'title': 'The 2026 IPO Pipeline: Deeper Than the Print',
                'format': 'Article',
                'format_slug': 'article',
                'date': 'Apr 02, 2026',
                'tint': 'amber',
                'url': '#',
            },
            {
                'eyebrow': 'Industrials',
                'title': "Sector Map: Where Capex Is Compounding",
                'format': 'Podcast',
                'format_slug': 'podcast',
                'date': 'Mar 26, 2026',
                'tint': 'burnt',
                'url': '#',
            },
        ],
        'leadership': [
            {'name': 'Diana Sample', 'title': 'Global Co-Head of IB', 'tint': 'navy'},
            {'name': 'Marcus Placeholder', 'title': 'Global Co-Head of IB', 'tint': 'amber'},
            {'name': 'Yuki Hypothetical', 'title': 'Head of Capital Markets', 'tint': 'mauve'},
            {'name': 'Tomás Fictional', 'title': 'Head of M&A', 'tint': 'olive'},
            {'name': 'Ananya Lorem', 'title': 'Head of Financing Group', 'tint': 'teal'},
        ],
    }


def _pillar_aw() -> Dict[str, Any]:
    return {
        'title': 'Asset & Wealth Management',
        'short_title': 'Asset & Wealth',
        'eyebrow': 'What We Do',
        'tint': 'mauve',
        'lede': (
            'A unified platform combining institutional asset management, '
            'private wealth advisory, and our consumer wealth solutions, '
            'serving clients across the full spectrum of needs.'
        ),
        'tabs': [
            {'label': 'Overview', 'url': '#', 'active': True},
            {'label': 'Asset Management', 'url': '#'},
            {'label': 'Wealth Management', 'url': '#'},
            {'label': 'Alternatives', 'url': '#'},
            {'label': 'Strategies', 'url': '#'},
            {'label': 'Insights', 'url': '#'},
        ],
        'rankings': [
            {'numeral': '$2.9T', 'label': 'Assets Under Supervision'},
            {'numeral': '#2', 'label': 'Global Alternatives Platform'},
            {'numeral': '180+', 'label': 'Investment Strategies'},
            {'numeral': '24', 'label': 'Offices Worldwide'},
        ],
        'rankings_legal': (
            'Source: Internal, as of fictional reference year. Placeholder '
            'figures shown for layout demonstration only.'
        ),
        'offerings_title': 'How We Help Clients',
        'offerings_lede': (
            'Active, indexed and alternative strategies across the full '
            'public-and-private spectrum, packaged for institutional and '
            'individual clients.'
        ),
        'offerings': [
            {
                'icon': 'compass',
                'title': 'Public Markets',
                'body': (
                    'Active fundamental, quantitative and indexed strategies '
                    'across global equities, fixed income, and multi-asset.'
                ),
                'links': ['Equities', 'Fixed Income', 'Liquidity Solutions', 'Indexed Strategies'],
            },
            {
                'icon': 'globe',
                'title': 'Alternatives',
                'body': (
                    'Private equity, growth equity, private credit, real '
                    'estate, infrastructure, and hedge funds.'
                ),
                'links': ['Private Equity', 'Private Credit', 'Real Estate', 'Infrastructure'],
            },
            {
                'icon': 'briefcase',
                'title': 'Wealth Management',
                'body': (
                    'Personalised wealth planning for high-net-worth families '
                    'and digital wealth solutions for the next generation.'
                ),
                'links': ['Private Wealth Management', 'Marcus Wealth', 'Workplace Solutions'],
            },
        ],
        'deals': None,
        'insights': [
            {
                'eyebrow': 'Allocation',
                'title': 'A Steepener Trade for the Next Cutting Cycle',
                'format': 'Article',
                'format_slug': 'article',
                'date': 'Apr 04, 2026',
                'tint': 'mauve',
                'url': '#',
            },
            {
                'eyebrow': 'Private Credit',
                'title': 'Private Credit at the Cycle Inflection',
                'format': 'Podcast',
                'format_slug': 'podcast',
                'date': 'Mar 19, 2026',
                'tint': 'navy',
                'url': '#',
            },
            {
                'eyebrow': 'Equities',
                'title': 'Quality at a Reasonable Price: 2026 Equity Playbook',
                'format': 'Article',
                'format_slug': 'article',
                'date': 'Mar 12, 2026',
                'tint': 'amber',
                'url': '#',
            },
        ],
        'leadership': [
            {'name': 'Helena Sample-Stein', 'title': 'Co-Head of AWM', 'tint': 'mauve'},
            {'name': 'Aarav Placeholder', 'title': 'Co-Head of AWM', 'tint': 'navy'},
            {'name': 'Lin Fictional', 'title': 'Head of Public Markets', 'tint': 'teal'},
            {'name': 'Ben Hypothetical', 'title': 'Head of Alternatives', 'tint': 'amber'},
            {'name': 'Maya Lorem-Ipsum', 'title': 'Head of Wealth', 'tint': 'olive'},
        ],
    }


def _careers_students_content() -> Dict[str, Any]:
    return {
        'stats': [
            {'numeral': '1M+', 'caption': 'Applications received last year'},
            {'numeral': '170+', 'caption': 'Universities recruited from'},
            {'numeral': '12', 'caption': 'Months of structured development'},
            {'numeral': '40+', 'caption': 'Cities with student programs'},
        ],
        'programs': [
            {
                'eyebrow': 'Internship',
                'title': 'Summer Analyst Program',
                'body': (
                    'A 10-week immersive experience across an investment '
                    'division, with structured training, mentorship, and '
                    'a live project deliverable presented to senior leaders.'
                ),
                'facts': [
                    {'label': 'Duration', 'value': '10 weeks'},
                    {'label': 'Eligibility', 'value': 'Penultimate year'},
                    {'label': 'Applications', 'value': 'Aug — Oct 2026'},
                ],
            },
            {
                'eyebrow': 'Full-Time',
                'title': 'New Analyst Program',
                'body': (
                    'A 12-month onboarding for graduates entering the firm '
                    'full-time, with division-specific training plus a '
                    'cross-firm "first 90 days" cohort experience.'
                ),
                'facts': [
                    {'label': 'Duration', 'value': '12 months'},
                    {'label': 'Eligibility', 'value': 'Final year'},
                    {'label': 'Applications', 'value': 'Rolling'},
                ],
            },
            {
                'eyebrow': 'Apprenticeship',
                'title': 'Engineering Apprenticeship',
                'body': (
                    'An alternative-to-degree pathway for software engineers '
                    'who learn on the job alongside structured curriculum, '
                    'culminating in a degree-equivalent qualification.'
                ),
                'facts': [
                    {'label': 'Duration', 'value': '4 years'},
                    {'label': 'Eligibility', 'value': 'School-leaver'},
                    {'label': 'Locations', 'value': 'London, NYC, Bengaluru'},
                ],
            },
            {
                'eyebrow': 'Spring Insight',
                'title': 'Spring Insights Programmes',
                'body': (
                    'A multi-day insight programme for first-year university '
                    'students to explore the firm before applying to summer '
                    'internships.'
                ),
                'facts': [
                    {'label': 'Duration', 'value': '1 week'},
                    {'label': 'Eligibility', 'value': 'First-year'},
                    {'label': 'Geography', 'value': 'EMEA / Asia'},
                ],
            },
            {
                'eyebrow': 'Womens Programme',
                'title': "Women's Possibilities Summit",
                'body': (
                    'An invitation-only summit for women in undergraduate '
                    'studies to spend a day at the firm exploring careers '
                    'across markets, banking, engineering, and AM.'
                ),
                'facts': [
                    {'label': 'Format', 'value': 'In-person'},
                    {'label': 'Application', 'value': 'Nominated essay'},
                    {'label': 'Date', 'value': 'Annual, Sep'},
                ],
            },
            {
                'eyebrow': 'Veterans Programme',
                'title': 'Veterans Integration Program',
                'body': (
                    'A specialised pathway for transitioning military '
                    'personnel and reservists, with placements across '
                    'engineering, operations, and the investment divisions.'
                ),
                'facts': [
                    {'label': 'Duration', 'value': '11 weeks'},
                    {'label': 'Eligibility', 'value': 'Veterans / reservists'},
                    {'label': 'Geography', 'value': 'Global'},
                ],
            },
        ],
        'divisions': [
            {'title': 'Investment Banking', 'body': 'Advise corporations, governments and institutions on strategic transactions.', 'tint': 'navy'},
            {'title': 'Global Markets', 'body': 'Make markets and intermediate risk across asset classes.', 'tint': 'burnt'},
            {'title': 'Asset & Wealth', 'body': 'Manage assets across public and private markets for clients.', 'tint': 'mauve'},
            {'title': 'Engineering', 'body': 'Design and build the systems that power the firm.', 'tint': 'teal'},
            {'title': 'Research', 'body': 'Generate the data-driven insight that informs investment decisions.', 'tint': 'olive'},
            {'title': 'Operations', 'body': 'Enable every trade, product launch, and completed transaction.', 'tint': 'amber'},
            {'title': 'Risk', 'body': 'Identify, monitor and manage the firms financial and non-financial risks.', 'tint': 'brown'},
            {'title': 'Internal Audit', 'body': 'Provide independent assurance to the firms board and senior management.', 'tint': 'purple'},
        ],
        'voices': [
            {
                'name': 'Ava Hypothetical',
                'title': 'Summer Analyst, Investment Banking',
                'tint': 'navy',
                'quote': (
                    'The training program is intense but the level of '
                    'mentorship is unlike anything I experienced at university. '
                    'Senior leaders make time for analysts and you feel that.'
                ),
            },
            {
                'name': 'Hugo Sample',
                'title': 'New Analyst, Engineering',
                'tint': 'teal',
                'quote': (
                    'On day three I was pushing code that ran against live '
                    'order flow. The responsibility scales as fast as you can '
                    'handle it — and the team is right there with you.'
                ),
            },
            {
                'name': 'Priya Placeholder',
                'title': 'Apprentice, Engineering',
                'tint': 'mauve',
                'quote': (
                    "The apprenticeship gave me a paid path into engineering "
                    "without the debt of a degree. Four years later I have the "
                    "qualification AND a fully built track record."
                ),
            },
        ],
        'steps': [
            {'title': 'Discover', 'body': 'Explore the divisions, programs and locations that interest you.'},
            {'title': 'Apply', 'body': 'Submit your application with resume, transcript, and short essay.'},
            {'title': 'Online assessments', 'body': 'Complete cognitive and situational judgment exercises.'},
            {'title': 'Interview rounds', 'body': 'Technical and behavioural interviews with practitioners.'},
            {'title': 'Offer & onboarding', 'body': 'Receive your offer and prepare with our onboarding curriculum.'},
        ],
    }


def _article_tracking_trillions() -> Dict[str, Any]:
    return {
        'article': {
            'eyebrow': 'Artificial Intelligence',
            'title': 'Tracking Trillions: The Assumptions Shaping the Scale of the AI Build-Out',
            'deck': (
                'Behind every estimate of AI infrastructure capex lies a '
                'small set of assumptions about how the system is built, '
                'replaced and powered. Small shifts in those assumptions '
                'reshape the headline figures dramatically.'
            ),
            'date': 'May 1, 2026',
            'read_time': '12 min read',
            'tint': 'navy',
            'authors': [
                {'name': 'Dr. Ada Hypothetical', 'title': 'Co-Head, Global Institute'},
                {'name': 'Ben Placeholder', 'title': 'VP, Global Institute'},
                {'name': 'Lin Sample-Stein', 'title': 'Senior Engineer, AWM Quant Team'},
            ],
            'intro': (
                'The capital expenditure debate is usually framed as a '
                'demand-side question — will adoption justify the spend — '
                'but the size of the investment itself is not a single, '
                'fixed number.'
            ),
            'exec_body': (
                'Estimates rest on a small set of assumptions about how the '
                'infrastructure itself is built and renewed. Four assumptions '
                'are most impactful in determining the scale of the build-out:'
            ),
            'numbered': [
                'The economic useful life of compute silicon, where small shifts in replacement cadence move cumulative spend by hundreds of billions.',
                'The cost and complexity of next-generation data centers, which are rising as workloads push power density higher and system integration deeper.',
                'The chip and architecture mix, whose impact depends on whether compute demand is elastic (reshaping margins) or inelastic (reshaping totals).',
                'Elongation from power, labor, and equipment bottlenecks, which in stress scenarios can feed back into demand-side doubt.',
            ],
            'sections': [
                {
                    'heading': 'Framing the Question',
                    'paragraphs': [
                        'A single inference query feels weightless — a question typed, an answer returned, no moving parts in sight. But the underlying infrastructure rests on a deeply physical edifice: millions of processors, hundreds of thousands of kilometers of cabling, industrial cooling systems, and power demands that rival those of midsize countries.',
                        'Better understanding of that complexity — and the assumptions on which the build-out rests — should inform how we think about the scale, durability, and risks of the capital expenditure boom we are now in.',
                        'In this report, we make the case that the headline capex figures circulating in the market are not single numbers, but rather distributions whose width is set by infrastructure assumptions that often go unstated.',
                    ],
                    'pull_quote': (
                        'The headline capex figures are not a single number. '
                        'They are a band whose width is set by infrastructure '
                        'assumptions, not just demand.'
                    ),
                    'pull_quote_attribution': 'Goldman Sachs Global Institute',
                },
                {
                    'heading': 'Baseline Estimates',
                    'paragraphs': [
                        'We anchor a baseline model to forward data center revenue estimates as a proxy for prevailing expectations around accelerator deployment, and then infer the associated requirements for data centers, power, and supporting infrastructure.',
                        'The baseline implies roughly $700 billion in annual capex in 2026, growing toward $1.5 trillion in 2031. The cumulative five-year capex implied by the baseline is approximately $5 trillion, with the bulk concentrated in the second half of the period as workloads scale.',
                    ],
                    'callout': {
                        'title': 'Methodology note',
                        'body': (
                            'Capex projections combine forward consensus '
                            'accelerator revenue, internal estimates of '
                            'data center utilization, and published power '
                            'and PUE assumptions. See footnotes 2 and 3.'
                        ),
                    },
                },
                {
                    'heading': 'Sensitivity to Useful Life',
                    'paragraphs': [
                        'If accelerators are replaced every two years instead of four, cumulative capex over a five-year horizon expands by hundreds of billions. The replacement cadence is the single most sensitive lever in the model.',
                        'Yet it is also the assumption with the weakest empirical anchor, since the technology is young and operator practices vary widely across hyperscalers, neocloud entrants, and enterprise on-premise deployments.',
                    ],
                    'pull_quote': (
                        'Replacement cadence is the single most sensitive '
                        'assumption — and the one with the weakest empirical '
                        'anchor today.'
                    ),
                },
                {
                    'heading': 'Power and Data Center Constraints',
                    'paragraphs': [
                        'Power availability is increasingly the binding constraint on the rate of build-out. Across major US markets, interconnection queues stretch beyond five years, with average commissioning timelines for new high-density data center capacity continuing to expand.',
                        'Data center construction costs are also rising — both because of higher power density per rack and because of more complex liquid cooling, integration, and structural demands. A megawatt of new capacity that cost $10M in 2022 now costs closer to $15M in 2026, with regional variation.',
                    ],
                },
                {
                    'heading': 'Implications for Investors',
                    'paragraphs': [
                        'The infrastructure-spend distribution is wider than headline numbers suggest, and the way the band is sliced has cross-sector implications: hyperscaler margins, power utility load growth, equipment supplier backlogs, and credit demand from neocloud entrants all sit on different points along the curve.',
                        'For investors, the right unit of analysis is not "is AI capex high" but "which assumption are you implicitly betting against in your positioning?"',
                    ],
                },
            ],
            'footnotes': [
                '1 Forecasts and expectations are illustrative and based on material assumptions subject to change. Numbers shown are placeholder figures for layout demonstration only.',
                '2 Assumes a leading accelerator vendor accounts for 75% of compute spend in each period, with 5% YoY growth past 2031.',
                '3 Assumes a power utilization effectiveness of 1.2 and a unit cost of $15M per megawatt of data center capacity.',
                '4 The baseline capex scenario is sensitive to the assumed replacement cadence; sensitivities are illustrative only.',
            ],
        },
        'related': [
            {
                'eyebrow': 'Quant',
                'title': 'How AI Is Changing Quantitative Investing',
                'format': 'Podcast',
                'date': 'Apr 22, 2026',
                'tint': 'mauve',
                'url': '#',
            },
            {
                'eyebrow': 'Macro',
                'title': 'AI Capex and the Productivity Question',
                'format': 'Article',
                'date': 'Apr 15, 2026',
                'tint': 'teal',
                'url': '#',
            },
            {
                'eyebrow': 'Credit',
                'title': 'Funding Models for Hyperscaler Buildouts',
                'format': 'Article',
                'date': 'Apr 03, 2026',
                'tint': 'amber',
                'url': '#',
            },
        ],
    }


def _podcast_jerome_dortmans() -> Dict[str, Any]:
    return {
        'episode': {
            'series': 'The Markets',
            'number': '74',
            'short_title': 'Jerome Dortmans on Oil',
            'title': 'Jerome Dortmans on the Drivers of Oil Markets',
            'deck': (
                'A wide-ranging conversation on the supply, demand, and '
                'geopolitical inputs shaping the path of crude oil markets '
                'through the back half of the year.'
            ),
            'date': 'May 8, 2026',
            'duration': '32 min',
            'tint': 'burnt',
            'summary_paragraphs': [
                'In this episode, host Pat Placeholder sits down with Jerome Dortmans, head of Commodities Research, to unpack the supply and demand factors that have shaped crude oil through the first half of 2026 — and what they signal about positioning for the back half.',
                'They cover OPEC+ discipline, the elasticity of US shale production, the demand picture from emerging markets (especially aviation), and the geopolitical risk premium that has been steadily compressed.',
                'Toward the end, Jerome lays out three scenarios he is watching and the early-warning indicators that would tilt the path between them — useful framing for any investor with cross-asset exposure to energy.',
            ],
            'chapters': [
                {'time': '0:00', 'label': 'Setup and the macro backdrop'},
                {'time': '5:42', 'label': 'Supply: OPEC+ discipline and the shale response function'},
                {'time': '13:15', 'label': 'Demand: emerging markets, aviation and structural shifts'},
                {'time': '21:00', 'label': 'Risk scenarios and the back half of the year'},
                {'time': '26:45', 'label': "What we're watching: early-warning indicators"},
                {'time': '28:30', 'label': 'Listener questions'},
            ],
            'transcript': [
                {'speaker': 'Pat Placeholder',  'time': '0:00', 'text': 'Welcome to The Markets. I am Pat Placeholder, and today we are joined by Jerome Dortmans, head of Commodities Research at the firm. Jerome, welcome.'},
                {'speaker': 'Jerome Dortmans',  'time': '0:18', 'text': 'Thanks, Pat. Great to be back.'},
                {'speaker': 'Pat Placeholder',  'time': '0:21', 'text': 'Let us start with the macro backdrop. Crude has had a notable run since the start of the year. What in your view explains the move?'},
                {'speaker': 'Jerome Dortmans',  'time': '0:33', 'text': 'A few things stack up. First, OPEC+ has shown more discipline than the consensus expected. Second, US shale producers have been slower to respond to higher prices than the historical playbook would suggest. Third — and this is the underappreciated piece — emerging market demand, especially in aviation, has been notably resilient.'},
                {'speaker': 'Pat Placeholder',  'time': '1:08', 'text': 'On that third point — talk us through the demand picture. Which regions are doing the heavy lifting?'},
                {'speaker': 'Jerome Dortmans',  'time': '1:20', 'text': 'India and Southeast Asia are both running ahead of consensus. India alone added almost 350 thousand barrels per day of demand growth year-over-year, with aviation contributing more than any other segment. China is more nuanced — industrial demand soft, but mobility demand has held in.'},
            ],
            'personas': [
                {'name': 'Pat Placeholder', 'title': 'Host, The Markets', 'tint': 'navy'},
                {'name': 'Jerome Dortmans', 'title': 'Head of Commodities Research', 'tint': 'burnt'},
            ],
            'related': [
                {'eyebrow': 'The Markets', 'title': 'A Steepener for the Cutting Cycle',
                 'date': 'Apr 30, 2026', 'duration': '28 min', 'url': '#'},
                {'eyebrow': 'The Markets', 'title': 'Power, Compute and the New Capex Map',
                 'date': 'Apr 23, 2026', 'duration': '35 min', 'url': '#'},
                {'eyebrow': 'Exchanges', 'title': 'Outlook 2026 Episode 3: Assets and Allocation',
                 'date': 'Apr 14, 2026', 'duration': '34 min', 'url': '#'},
            ],
        },
    }


def _article_energy_crunch() -> Dict[str, Any]:
    return {
        'article': {
            'eyebrow': 'Energy',
            'title': "The Energy Crunch Could Accelerate Europe's Shift to Electrification",
            'deck': (
                "Rising power prices and structural supply constraints "
                "are reshaping the case for electrification across "
                "European industry, transport and buildings — and the "
                "pace of transition with it."
            ),
            'date': 'May 5, 2026',
            'read_time': '9 min read',
            'tint': 'olive',
            'authors': [
                {'name': 'Inès Hypothetical', 'title': 'European Utilities Analyst'},
                {'name': 'Marco Sample', 'title': 'European Sustainability Strategist'},
            ],
            'intro': (
                'European energy markets entered 2026 with elevated power '
                'prices, persistent gas-supply uncertainty, and a policy '
                'environment increasingly aligned around electrification as '
                'an economic — not just environmental — imperative.'
            ),
            'exec_body': (
                "Three dynamics drive our view that the current energy "
                "crunch could accelerate, rather than slow, Europe's "
                "transition pace:"
            ),
            'numbered': [
                'Industrial users are reaching the threshold where electrified processes pay back faster than the historical playbook assumed.',
                'Heat pumps and EVs are crossing into clear unit-economics parity in most large European markets, with subsidies amplifying rather than creating the case.',
                'Permitting reform and policy alignment are removing more execution friction than the market has yet priced in.',
            ],
            'sections': [
                {
                    'heading': 'Industrial Electrification',
                    'paragraphs': [
                        'For energy-intensive industries — chemicals, primary metals, glass, building materials — the long-running calculus has been that electric process heat is technically possible but uncompetitive. That math has changed materially.',
                        'On a 7-year payback basis, electric process heat is now competitive with gas in roughly 60% of European industrial settings, up from 25% in 2022. The shift is driven equally by gas-price uplift and by declining electricity-cost expectations on a forward basis.',
                    ],
                    'pull_quote': (
                        'On a 7-year payback basis, electric process heat '
                        'is now competitive with gas in roughly 60% of '
                        'European industrial settings.'
                    ),
                },
                {
                    'heading': 'Buildings: The Heat Pump Tipping Point',
                    'paragraphs': [
                        'Heat pump adoption in Germany, the Netherlands and France inflected meaningfully in 2025, with installation rates now consistently exceeding gas-boiler replacement in new-build construction.',
                        'The lifetime cost-of-ownership math now favours heat pumps in the majority of typical European residential settings, even before subsidies, and the supply chain is finally beginning to scale to meet demand.',
                    ],
                },
                {
                    'heading': 'The Transport Layer',
                    'paragraphs': [
                        'EV adoption continues at pace, with European new-car sales for BEVs reaching 28% in Q1 2026. The bigger transition story now sits in commercial vehicles and short-haul logistics, where TCO parity is happening faster than the consumer market.',
                        'Charging infrastructure remains a constraint in southern and eastern European markets but is broadly trending in the right direction in the major economies.',
                    ],
                },
            ],
            'footnotes': [
                '1 Cost comparisons are illustrative and based on placeholder assumptions for the purpose of layout demonstration.',
                '2 Heat-pump adoption data is approximate and aggregated across European countries.',
                '3 EV share figures reference public industry data; specific period attribution may vary.',
            ],
        },
        'related': [
            {
                'eyebrow': 'Sustainability',
                'title': 'Transition Finance: A Practitioner Lens',
                'format': 'Article',
                'date': 'Apr 12, 2026',
                'tint': 'olive',
                'url': '#',
            },
            {
                'eyebrow': 'Macro',
                'title': "Germany at 1.1%: Industrial Recovery Slow but Real",
                'format': 'Video',
                'date': 'Apr 14, 2026',
                'tint': 'navy',
                'url': '#',
            },
            {
                'eyebrow': 'Energy',
                'title': 'Power, Compute and the New Capex Map',
                'format': 'Podcast',
                'date': 'Mar 26, 2026',
                'tint': 'burnt',
                'url': '#',
            },
        ],
    }


# ════════════════════════════════════════════════════════════════════════
# VIEW FUNCTIONS
# ════════════════════════════════════════════════════════════════════════

def insights(request):
    ctx = _base_context(request, active_nav='insights')
    ctx.update(_insights_index_content())
    return HttpResponse(_render('gsv2/insights_index.html', ctx, request))


def insights_macro(request):
    ctx = _base_context(request, active_nav='insights')
    ctx['topic'] = _topic_macro()
    return HttpResponse(_render('gsv2/insights_topic.html', ctx, request))


def insights_exchanges(request):
    ctx = _base_context(request, active_nav='insights')
    ctx['topic'] = _topic_exchanges()
    return HttpResponse(_render('gsv2/insights_topic.html', ctx, request))


def insights_talks(request):
    ctx = _base_context(request, active_nav='insights')
    ctx['topic'] = _topic_talks()
    return HttpResponse(_render('gsv2/insights_topic.html', ctx, request))


def wwd_ib(request):
    ctx = _base_context(request, active_nav='what-we-do')
    ctx['pillar'] = _pillar_ib()
    return HttpResponse(_render('gsv2/wwd_pillar.html', ctx, request))


def wwd_aw(request):
    ctx = _base_context(request, active_nav='what-we-do')
    ctx['pillar'] = _pillar_aw()
    return HttpResponse(_render('gsv2/wwd_pillar.html', ctx, request))


def careers_students(request):
    ctx = _base_context(request, active_nav='careers')
    ctx.update(_careers_students_content())
    return HttpResponse(_render('gsv2/careers_students.html', ctx, request))


def article_tracking_trillions(request):
    ctx = _base_context(request, active_nav='insights')
    ctx.update(_article_tracking_trillions())
    return HttpResponse(_render('gsv2/article_detail.html', ctx, request))


def article_energy_crunch(request):
    ctx = _base_context(request, active_nav='insights')
    ctx.update(_article_energy_crunch())
    return HttpResponse(_render('gsv2/article_detail.html', ctx, request))


def podcast_jerome_dortmans(request):
    ctx = _base_context(request, active_nav='insights')
    ctx.update(_podcast_jerome_dortmans())
    return HttpResponse(_render('gsv2/podcast_detail.html', ctx, request))


def serve_css(request):
    return HttpResponse(_build_css(), content_type='text/css; charset=utf-8')


def serve_js(request):
    return HttpResponse(_JS_COMPANION, content_type='application/javascript; charset=utf-8')


# ════════════════════════════════════════════════════════════════════════
# URL CONFIGURATION
# ════════════════════════════════════════════════════════════════════════

app_name = 'gs_reference_companion'

urlpatterns = [
    path('',                                        insights,                     name='insights'),
    path('insights/',                               insights,                     name='insights_alt'),
    path('insights/macroeconomics/',                insights_macro,               name='insights_macro'),
    path('insights/exchanges/',                     insights_exchanges,           name='insights_exchanges'),
    path('insights/talks-at-gs/',                   insights_talks,               name='insights_talks'),
    path('insights/articles/tracking-trillions/',   article_tracking_trillions,   name='article_tracking_trillions'),
    path('insights/articles/energy-crunch/',        article_energy_crunch,        name='article_energy_crunch'),
    path('insights/the-markets/jerome-dortmans/',   podcast_jerome_dortmans,      name='podcast_jerome_dortmans'),
    path('what-we-do/investment-banking/',          wwd_ib,                       name='wwd_ib'),
    path('what-we-do/asset-wealth/',                wwd_aw,                       name='wwd_aw'),
    path('careers/students/',                       careers_students,             name='careers_students'),
    path('static/gsv2.css',                         serve_css,                    name='css'),
    path('static/gsv2.js',                          serve_js,                     name='js'),
]


# ════════════════════════════════════════════════════════════════════════
# STANDALONE CLI ENTRY POINT
# ════════════════════════════════════════════════════════════════════════
# `python gs_reference_companion.py` launches an interactive menu that
# exposes every developer-facing operation as a single command:
#
#   1. Up                Boot both v1 + v2 in one Django wsgiref runtime,
#                        open the browser at /, block until Ctrl+C.
#   2. Smoke             Configure Django, mount both apps, render every
#                        page through the Django test client, assert key
#                        markers are present in each rendered body.
#   3. Shoot             Capture playwright screenshots of all companion
#                        pages plus each mega-menu in the open state, plus
#                        the v1 home + insights pages for before/after.
#   4. Deliverable       Smoke + Shoot + build a timestamped HTML
#                        deliverable under projects/gs_reference/dev/output/
#                        with embedded screenshots and before/after pairs,
#                        then open it in the user's default browser.
#
# Each menu item maps to an argparse subcommand for non-interactive use:
#   python gs_reference_companion.py up           --port=8003 --no-browser
#   python gs_reference_companion.py smoke
#   python gs_reference_companion.py shoot        --runtime=prism
#   python gs_reference_companion.py deliverable  --runtime=prism

import argparse
import datetime as _dt
import os as _os
import socket as _socket
import subprocess as _subprocess
import threading as _threading
import time as _time
import webbrowser as _webbrowser
from wsgiref.simple_server import make_server as _make_server, WSGIRequestHandler as _WSGIRequestHandler


_DEFAULT_PORT = 8003
_PROJECT_DIR = _HERE.parent
_OUTPUT_DIR = _PROJECT_DIR / 'dev' / 'output'

# Pages to capture; (url-path, slug, viewport-height, full-page?)
_CAPTURE_PAGES_V2 = [
    ('/',                                                 '01_v2_insights_index',          1800, True),
    ('/insights/macroeconomics/',                         '02_v2_insights_macro',          2400, True),
    ('/insights/exchanges/',                              '03_v2_insights_exchanges',      2400, True),
    ('/insights/talks-at-gs/',                            '04_v2_insights_talks',          2400, True),
    ('/what-we-do/investment-banking/',                   '05_v2_wwd_ib',                  2800, True),
    ('/what-we-do/asset-wealth/',                         '06_v2_wwd_aw',                  2400, True),
    ('/careers/students/',                                '07_v2_careers_students',        3200, True),
    ('/insights/articles/tracking-trillions/',            '08_v2_article_tracking',        2800, True),
    ('/insights/articles/energy-crunch/',                 '09_v2_article_energy',          2200, True),
    ('/insights/the-markets/jerome-dortmans/',            '10_v2_podcast_jerome',          2400, True),
]

_CAPTURE_PAGES_V1 = [
    ('/v1/',                                              '21_v1_home',                    900, False),
    ('/v1/insights/',                                     '22_v1_insights_list',           900, False),
    ('/v1/what-we-do/',                                   '23_v1_what_we_do',              900, False),
]

# Mega-menu captures: (slug, trigger-key)
_CAPTURE_MEGAMENUS = [
    ('11_megamenu_what_we_do',  'what-we-do'),
    ('12_megamenu_insights',    'insights'),
    ('13_megamenu_our_firm',    'our-firm'),
    ('14_megamenu_careers',     'careers'),
]


def _cli_print(msg: str, indent: int = 2) -> None:
    print((' ' * indent) + msg, flush=True)


def _cli_banner(title: str) -> None:
    bar = '═' * 64
    print()
    print(f'  ╔{bar}╗')
    print(f'  ║ {title:<62} ║')
    print(f'  ╚{bar}╝')
    print()


def _find_free_port(preferred: int = _DEFAULT_PORT) -> int:
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', preferred))
            s.close()
            return preferred
        except OSError:
            pass
    with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _configure_django(debug: bool = False) -> None:
    """Stand up a minimal Django runtime with both v1 + v2 mounted.

    Uses settings.configure() so the script needs no settings.py. Both
    `gs_reference` and `gs_reference_companion` get included() under
    distinct URL prefixes.
    """
    from django.conf import settings
    if not settings.configured:
        settings.configure(
            DEBUG=debug,
            SECRET_KEY='gs-reference-companion-cli-not-for-production',
            ALLOWED_HOSTS=['127.0.0.1', 'localhost', '*'],
            INSTALLED_APPS=[],
            MIDDLEWARE=[],
            ROOT_URLCONF=__name__,
            TEMPLATES=[{
                'BACKEND': 'django.template.backends.django.DjangoTemplates',
                'DIRS': [],
                'APP_DIRS': False,
                'OPTIONS': {},
            }],
            DATABASES={},
            DEFAULT_AUTO_FIELD='django.db.models.BigAutoField',
        )
    import django
    django.setup()


def _install_root_urlconf() -> None:
    """Define this module's `urlpatterns` to mount v1 at /v1/ and v2 at /."""
    from django.urls import include, path as _path
    global urlpatterns
    urlpatterns = [
        _path('v1/', include('gs_reference')),
        _path('',    include('gs_reference_companion')),
    ]
    from django.urls.resolvers import get_resolver
    get_resolver(__name__)._populate()


class _QuietHandler(_WSGIRequestHandler):
    """Silence wsgiref request logging in the capture/shoot flow."""
    def log_message(self, fmt, *args):
        return


def _boot_background_server(port: int, quiet: bool = False) -> 'tuple[_threading.Thread, _threading.Event]':
    _configure_django()
    _install_root_urlconf()
    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()

    stop_event = _threading.Event()
    ready_event = _threading.Event()

    def _serve():
        handler_cls = _QuietHandler if quiet else _WSGIRequestHandler
        srv = _make_server('127.0.0.1', port, app, handler_class=handler_cls)
        srv.timeout = 0.4
        ready_event.set()
        while not stop_event.is_set():
            srv.handle_request()
        srv.server_close()

    th = _threading.Thread(target=_serve, daemon=True)
    th.start()
    ready_event.wait(timeout=5.0)
    _time.sleep(0.2)
    return th, stop_event


def cmd_up(args=None) -> int:
    """Boot the dev server in the foreground and open the browser."""
    port = getattr(args, 'port', _DEFAULT_PORT) if args else _DEFAULT_PORT
    no_browser = getattr(args, 'no_browser', False) if args else False
    port = _find_free_port(port)

    _cli_banner('gs_reference_companion — booting v1 + v2')
    _cli_print(f'Companion (v2) at  http://127.0.0.1:{port}/')
    _cli_print(f'Legacy DNA (v1) at  http://127.0.0.1:{port}/v1/')
    _cli_print('')
    _cli_print('Hover the top nav tabs to trigger the mega-menu dropdowns.')
    _cli_print('Ctrl+C to stop.')
    print()

    _configure_django()
    _install_root_urlconf()
    from django.core.wsgi import get_wsgi_application
    app = get_wsgi_application()

    if not no_browser:
        def _open():
            _time.sleep(0.6)
            _webbrowser.open(f'http://127.0.0.1:{port}/')
        _threading.Thread(target=_open, daemon=True).start()

    try:
        srv = _make_server('127.0.0.1', port, app)
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n  Stopped.')
        return 0
    return 0


def cmd_smoke(args=None) -> int:
    """Render every URL through the Django test client and assert markers."""
    _cli_banner('gs_reference_companion — smoke test')

    _configure_django()
    _install_root_urlconf()
    from django.test import Client
    client = Client()

    pages = [
        ('/',                                                ['Insights', 'Tracking Trillions', 'gsv2-feature', 'data-mega-panel']),
        ('/insights/macroeconomics/',                        ['Macroeconomics', 'gsv2-topic-hero', 'Sturdy Growth']),
        ('/insights/exchanges/',                             ['Exchanges', 'flagship podcast', 'Allison']),
        ('/insights/talks-at-gs/',                           ['Talks at GS', 'Long-form', 'Sara Hypothetical']),
        ('/what-we-do/investment-banking/',                  ['Investment Banking', 'gsv2-rankings', 'Selected Transactions']),
        ('/what-we-do/asset-wealth/',                        ['Asset &amp; Wealth Management', 'Alternatives', 'Private Wealth']),
        ('/careers/students/',                               ['Start Your Career With Us', 'gsv2-program-card', 'Application']),
        ('/insights/articles/tracking-trillions/',           ['Tracking Trillions', 'Executive Summary', 'gsv2-numbered-list']),
        ('/insights/articles/energy-crunch/',                ['Europe', 'Electrification', 'gsv2-article-body']),
        ('/insights/the-markets/jerome-dortmans/',           ['Jerome Dortmans', 'Episode Summary', 'gsv2-chapters']),
        ('/static/gsv2.css',                                 [':root', '--gs-uitk-color-surface-brand-bold', '@font-face', '.gsv2-nav', '.gsv2-mega']),
        ('/static/gsv2.js',                                  ['data-mega-panel', 'INTENT_DELAY_MS', 'closeAllMenus']),
        ('/v1/',                                             ['Goldman Sachs', 'gs-nav']),
        ('/v1/insights/',                                    ['Analysis from Across the Firm']),
    ]
    failures = []
    total_bytes = 0
    for url, markers in pages:
        t = _time.time()
        resp = client.get(url)
        elapsed = (_time.time() - t) * 1000
        body = resp.content.decode('utf-8', errors='replace')
        total_bytes += len(body)
        problems = []
        if resp.status_code != 200:
            problems.append(f'HTTP {resp.status_code}')
        for m in markers:
            if m not in body:
                problems.append(f'missing {m!r}')
        if problems:
            failures.append((url, problems))
            _cli_print(f'FAIL  {url:<54}  ({elapsed:>5.0f}ms, {len(body):>7,} B)')
            for p in problems:
                _cli_print(f'        {p}', indent=8)
        else:
            _cli_print(f'OK    {url:<54}  ({elapsed:>5.0f}ms, {len(body):>7,} B)')

    print()
    if failures:
        _cli_print(f'FAILED: {len(failures)} routes had issues.')
        return 1
    _cli_print(f'PASSED: {len(pages)} routes rendered cleanly, {total_bytes:,} bytes total.')
    return 0


def _capture_screenshots(port: int, output_dir: Path, runtime: str = 'prism') -> Dict[str, int]:
    """Drive playwright over a running server and write PNGs into output_dir.

    Returns a dict of slug -> file-size-bytes for surface telemetry. Falls
    back gracefully if playwright is missing (prints install instructions).
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        _cli_print('[FAIL] playwright not installed. Install with:')
        _cli_print(f'  {sys.executable} -m pip install playwright')
        _cli_print(f'  {sys.executable} -m playwright install chromium')
        return {}

    output_dir.mkdir(parents=True, exist_ok=True)
    base = f'http://127.0.0.1:{port}'
    out_sizes: Dict[str, int] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, device_scale_factor=2)
        page = context.new_page()

        all_pages = _CAPTURE_PAGES_V2 + _CAPTURE_PAGES_V1
        for idx, (url_path, slug, vp_h, full) in enumerate(all_pages, start=1):
            png = output_dir / f'{slug}.png'
            target = f'{base}{url_path}?runtime={runtime}'
            t = _time.time()
            try:
                page.set_viewport_size({'width': 1440, 'height': vp_h})
                page.goto(target, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(700)
                page.screenshot(path=str(png), full_page=full)
                size = png.stat().st_size
                out_sizes[slug] = size
                _cli_print(f'[{idx:>2}] {slug:<32}  ({(_time.time()-t)*1000:>5.0f}ms, {size/1024:>6.0f} KB)  {url_path}')
            except Exception as exc:
                _cli_print(f'[{idx:>2}] FAIL  {slug:<28}  {exc}')

        # Mega-menu captures — visit home, then trigger the open class via JS
        page.set_viewport_size({'width': 1440, 'height': 900})
        for idx, (slug, key) in enumerate(_CAPTURE_MEGAMENUS, start=len(all_pages) + 1):
            png = output_dir / f'{slug}.png'
            target = f'{base}/?runtime={runtime}'
            t = _time.time()
            try:
                page.goto(target, wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(500)
                # Use JS to force the open state so we don't rely on hover timing
                page.evaluate(f'''(() => {{
                    const trigger = document.querySelector('[data-mega-trigger="{key}"]');
                    if (!trigger) return false;
                    trigger.classList.add('is-open');
                    const btn = trigger.querySelector('[data-mega-button]');
                    if (btn) btn.setAttribute('aria-expanded', 'true');
                    const panel = document.querySelector('[data-mega-panel="{key}"]');
                    if (panel) {{
                        panel.classList.add('is-open');
                        panel.setAttribute('aria-hidden', 'false');
                    }}
                    const bd = document.querySelector('[data-mega-backdrop]');
                    if (bd) bd.classList.add('is-active');
                    const nav = document.querySelector('[data-nav]');
                    if (nav) nav.classList.add('is-mega-open');
                    return true;
                }})()''')
                page.wait_for_timeout(450)
                page.screenshot(path=str(png), full_page=False)
                size = png.stat().st_size
                out_sizes[slug] = size
                _cli_print(f'[{idx:>2}] {slug:<32}  ({(_time.time()-t)*1000:>5.0f}ms, {size/1024:>6.0f} KB)  [mega-menu: {key}]')
            except Exception as exc:
                _cli_print(f'[{idx:>2}] FAIL  {slug:<28}  {exc}')

        # Search overlay capture
        png = output_dir / '15_search_overlay.png'
        try:
            page.goto(f'{base}/?runtime={runtime}', wait_until='networkidle', timeout=30000)
            page.wait_for_timeout(500)
            page.evaluate('''(() => {
                const panel = document.querySelector('[data-search-panel]');
                if (panel) {
                    panel.classList.add('is-open');
                    panel.setAttribute('aria-hidden', 'false');
                }
                const bd = document.querySelector('[data-mega-backdrop]');
                if (bd) bd.classList.add('is-active');
                const nav = document.querySelector('[data-nav]');
                if (nav) nav.classList.add('is-mega-open');
            })()''')
            page.wait_for_timeout(400)
            page.screenshot(path=str(png), full_page=False)
            out_sizes['15_search_overlay'] = png.stat().st_size
            _cli_print(f'[++] 15_search_overlay                ({png.stat().st_size/1024:>6.0f} KB)  [overlay]')
        except Exception as exc:
            _cli_print(f'[++] FAIL  15_search_overlay  {exc}')

        # Sticky-shrink before/after viewport pair
        for slug, scroll_y in [('16_sticky_top', 0), ('17_sticky_scrolled', 1200)]:
            png = output_dir / f'{slug}.png'
            try:
                page.goto(f'{base}/?runtime={runtime}', wait_until='networkidle', timeout=30000)
                page.wait_for_timeout(400)
                page.evaluate(f'window.scrollTo({{ top: {scroll_y}, behavior: "instant" }})')
                page.wait_for_timeout(500)
                page.screenshot(path=str(png), full_page=False)
                out_sizes[slug] = png.stat().st_size
                _cli_print(f'[++] {slug:<32}  ({png.stat().st_size/1024:>6.0f} KB)  [scrollY={scroll_y}]')
            except Exception as exc:
                _cli_print(f'[++] FAIL  {slug:<28}  {exc}')

        browser.close()
    return out_sizes


def cmd_shoot(args=None) -> int:
    """Boot server in background, capture screenshots, shut down."""
    port = getattr(args, 'port', _DEFAULT_PORT) if args else _DEFAULT_PORT
    runtime = getattr(args, 'runtime', 'prism') if args else 'prism'

    _cli_banner('gs_reference_companion — capturing screenshots')

    port = _find_free_port(port)
    stamp = _dt.datetime.now().strftime('%Y-%m-%d_%H%M')
    out_dir = _OUTPUT_DIR / f'{stamp}_companion' / 'screenshots'

    _cli_print(f'Output:  {out_dir}')
    _cli_print(f'Port:    {port}')
    _cli_print(f'Runtime: {runtime}')
    print()

    th, stop_event = _boot_background_server(port, quiet=True)
    try:
        _capture_screenshots(port, out_dir, runtime=runtime)
    finally:
        stop_event.set()
        th.join(timeout=2.0)

    _cli_print(f'Screenshots written to {out_dir}')
    return 0


# ─── HTML DELIVERABLE BUILDER ───
_DELIV_CSS = r"""
:root {
    --bg: #0d0f13;
    --panel: #161821;
    --panel-2: #1f2230;
    --border: rgba(255, 255, 255, 0.08);
    --border-strong: rgba(255, 255, 255, 0.18);
    --text: rgba(255, 255, 255, 0.94);
    --text-mute: rgba(255, 255, 255, 0.66);
    --text-quiet: rgba(255, 255, 255, 0.46);
    --accent: #7297C5;
    --accent-deep: #092C61;
    --good: #54c08c;
    --warn: #e9a85c;
    --code: #c9d3e1;
    --mono: ui-monospace, 'SF Mono', Menlo, monospace;
    --sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}
* { box-sizing: border-box; }
body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font: 16px/1.55 var(--sans);
    padding: 56px 32px 96px;
}
.wrap { max-width: 1280px; margin: 0 auto; }
h1 { margin: 0 0 12px; font-weight: 300; font-size: 48px; letter-spacing: -0.02em; }
h1 .slash { color: var(--accent); }
h2 {
    margin: 64px 0 16px; font-weight: 500; font-size: 22px; letter-spacing: -0.01em;
    padding-bottom: 12px; border-bottom: 1px solid var(--border);
    display: flex; align-items: baseline; gap: 12px;
}
h2 .step {
    font: 12px/1 var(--mono); color: var(--accent);
    background: rgba(114, 151, 197, 0.12);
    padding: 4px 8px; border-radius: 2px; letter-spacing: 1px; text-transform: uppercase;
}
h3 { margin: 32px 0 12px; font-weight: 500; font-size: 17px; color: var(--text); }
p { color: var(--text-mute); max-width: 980px; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.lede { color: var(--text); font-size: 18px; line-height: 1.55; max-width: 980px; }
.meta {
    display: grid; grid-template-columns: 220px 1fr; gap: 12px 24px; margin: 24px 0 0;
    padding: 20px 24px; background: var(--panel); border: 1px solid var(--border);
    border-left: 3px solid var(--accent);
}
.meta dt {
    font: 11px/1.4 var(--mono); color: var(--text-quiet);
    text-transform: uppercase; letter-spacing: 1px;
}
.meta dd { margin: 0; color: var(--text); }
.meta dd code {
    font: 13px/1.4 var(--mono); color: var(--code);
    background: var(--panel-2); padding: 2px 8px; border-radius: 2px;
}
pre {
    background: var(--panel); border: 1px solid var(--border); padding: 16px 20px;
    overflow-x: auto; font: 13px/1.55 var(--mono); color: var(--code); margin: 0 0 16px;
}
pre.cmd { border-left: 3px solid var(--accent); }
pre.cmd::before { content: '$ '; color: var(--accent); }
.grid-screens { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-top: 24px; }
.grid-screens--single { grid-template-columns: 1fr; }
.screen {
    background: var(--panel); border: 1px solid var(--border); padding: 14px;
    display: flex; flex-direction: column; gap: 12px;
}
.screen__head { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.screen__name {
    font: 500 14px/1.2 var(--sans); color: var(--text);
}
.screen__meta {
    font: 11px/1.2 var(--mono); color: var(--text-quiet);
    letter-spacing: 0.6px; text-transform: uppercase;
}
.screen__img {
    background: var(--panel-2); border: 1px solid var(--border);
    overflow: hidden; display: block;
}
.screen__img img { width: 100%; height: auto; display: block; }
.compare {
    display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 24px;
}
.compare__col h3 {
    font: 500 13px/1 var(--mono); margin: 0 0 10px;
    color: var(--accent); text-transform: uppercase; letter-spacing: 1.2px;
}
.compare__col h3 .label {
    display: inline-block; padding: 3px 8px; background: rgba(114, 151, 197, 0.18);
    border-radius: 2px; margin-right: 8px;
}
.compare__col--after h3 .label { background: rgba(84, 192, 140, 0.18); color: var(--good); }
.compare__col--before h3 .label { background: rgba(233, 168, 92, 0.18); color: var(--warn); }
.compare__img {
    border: 1px solid var(--border); background: var(--panel-2); overflow: hidden;
}
.compare__img img { width: 100%; height: auto; display: block; }
ul.bullets { padding-left: 22px; color: var(--text-mute); max-width: 980px; }
ul.bullets li { margin-bottom: 8px; }
ul.bullets li strong { color: var(--text); font-weight: 500; }
.tag {
    display: inline-block; padding: 2px 8px; font: 11px/1.4 var(--mono);
    background: var(--panel-2); color: var(--code); border-radius: 2px;
    border: 1px solid var(--border-strong); margin-right: 6px; margin-bottom: 4px;
}
.callout {
    margin: 32px 0; padding: 20px 24px; background: var(--panel);
    border: 1px solid var(--border); border-left: 3px solid var(--good);
}
.callout strong { color: var(--text); }
.callout pre { margin-top: 12px; background: var(--bg); border-color: var(--border-strong); }
table.routes {
    border-collapse: collapse; width: 100%; margin-top: 16px;
    font: 13px/1.4 var(--sans);
}
table.routes th, table.routes td {
    padding: 10px 14px; border-bottom: 1px solid var(--border); text-align: left;
}
table.routes th {
    font: 500 11px/1.2 var(--mono); color: var(--text-quiet);
    text-transform: uppercase; letter-spacing: 1px;
}
table.routes td code {
    font: 12px/1.4 var(--mono); color: var(--code);
    background: var(--panel-2); padding: 2px 6px; border-radius: 2px;
}
table.routes td.size { color: var(--text-mute); white-space: nowrap; }
.bench {
    margin-top: 32px; padding: 20px 24px; background: var(--panel);
    border: 1px solid var(--border); display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 16px;
}
.bench__stat {
    display: flex; flex-direction: column; gap: 4px;
    border-left: 2px solid var(--accent); padding-left: 14px;
}
.bench__stat .num {
    font: 300 32px/1 var(--sans); color: var(--text); letter-spacing: -0.5px;
}
.bench__stat .lbl {
    font: 400 12px/1.4 var(--sans); color: var(--text-quiet);
}
"""


def _build_deliverable_html(out_dir: Path, sizes: Dict[str, int]) -> Path:
    screens_dir = out_dir / 'screenshots'

    # Helper for safe screenshot rendering
    def img(slug: str, name: str = '') -> str:
        png = screens_dir / f'{slug}.png'
        if not png.exists():
            return f'<div class="screen__meta">[missing: {slug}.png]</div>'
        size_kb = png.stat().st_size / 1024
        return (
            f'<a class="screen__img" href="screenshots/{png.name}" target="_blank" '
            f'rel="noopener"><img src="screenshots/{png.name}" alt="{name or slug}" '
            f'loading="lazy"></a>'
            f'<div class="screen__meta">screenshots/{png.name} · {size_kb:.0f} KB</div>'
        )

    file_size = (_HERE / 'gs_reference_companion.py').stat().st_size

    # Routes table
    routes_rows = []
    for url_path, slug, _vp, _full in _CAPTURE_PAGES_V2:
        size_kb = (screens_dir / f'{slug}.png').stat().st_size / 1024 if (screens_dir / f'{slug}.png').exists() else 0
        routes_rows.append(
            f'<tr><td><code>{url_path}</code></td><td>{slug}</td>'
            f'<td class="size">{size_kb:.0f} KB</td></tr>'
        )
    for url_path, slug, _vp, _full in _CAPTURE_PAGES_V1:
        size_kb = (screens_dir / f'{slug}.png').stat().st_size / 1024 if (screens_dir / f'{slug}.png').exists() else 0
        routes_rows.append(
            f'<tr><td><code>{url_path}</code></td><td>{slug} (v1 legacy)</td>'
            f'<td class="size">{size_kb:.0f} KB</td></tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>gs_reference_companion — high-fidelity insights + mega-menu mock</title>
<style>{_DELIV_CSS}</style>
</head>
<body>
<div class="wrap">

<h1><span class="slash">/</span> gs_reference_companion</h1>
<p class="lede">
    A single-file Django plug-in that replicates the live
    <code>goldmansachs.com/insights</code> page in full, plus the four
    mega-menu dropdowns on the top ribbon (What We Do · Insights · Our
    Firm · Careers), the search overlay, and the sticky-shrink header.
    Eleven URL routes, ten companion pages, four dropdown chrome states,
    and a side-by-side comparison against the existing <code>gs_reference</code>
    (v1) abstract design DNA mock.
</p>

<dl class="meta">
    <dt>File</dt>           <dd><code>{(_HERE / 'gs_reference_companion.py').as_posix()}</code></dd>
    <dt>File size</dt>      <dd>{file_size:,} bytes (single file; no auxiliary modules)</dd>
    <dt>Companion mounts</dt><dd><code>/</code> · v2 (this work)</dd>
    <dt>Legacy mounts</dt>  <dd><code>/v1/</code> · v1 design DNA reference (existing)</dd>
    <dt>Pages</dt>          <dd>10 companion (insights index, 3 sub-topic landings, 2 pillar pages, 1 careers landing, 2 article details, 1 podcast detail) + 3 legacy v1 surfaces</dd>
    <dt>Mega-menus</dt>     <dd>4 dropdowns: What We Do · Insights · Our Firm · Careers (3 cols of links + 3 promo tiles each)</dd>
    <dt>Search overlay</dt> <dd>Full-bleed search panel with trending chips</dd>
    <dt>Sticky shrink</dt>  <dd>Two-tier header: 88 px → 64 px on scroll &gt; 32 px</dd>
    <dt>JS</dt>             <dd>Vanilla, no deps. 140ms intent delay, ESC close, click-outside, ARIA, focus trap, smooth scroll</dd>
    <dt>CSS reuse</dt>      <dd>Imports <code>_CSS_TOKENS</code> + <code>_CSS_FONTS</code> from <code>gs_reference</code> (single source of token truth)</dd>
</dl>

<div class="bench">
    <div class="bench__stat"><span class="num">{file_size//1024:,}</span><span class="lbl">KB single .py file</span></div>
    <div class="bench__stat"><span class="num">{len(_CAPTURE_PAGES_V2)}</span><span class="lbl">companion pages</span></div>
    <div class="bench__stat"><span class="num">{len(_CAPTURE_MEGAMENUS)}</span><span class="lbl">mega-menu dropdowns</span></div>
    <div class="bench__stat"><span class="num">{len(_CAPTURE_MEGAMENUS) * 3}</span><span class="lbl">promo tiles total</span></div>
    <div class="bench__stat"><span class="num">{len(urlpatterns)}</span><span class="lbl">URL routes</span></div>
    <div class="bench__stat"><span class="num">{len(_TEMPLATES)}</span><span class="lbl">templates</span></div>
</div>

<h2><span class="step">01</span> What to look for</h2>
<ul class="bullets">
    <li><strong>Mega-menu chrome.</strong> Each of the four nav tabs opens a 3-column link panel plus a sidebar of 3 promo tiles. Hover-with-intent (140ms delay), ESC closes, click-outside closes, ARIA expanded/hidden, focus trap. Backdrop dims the page behind.</li>
    <li><strong>Two-tier header.</strong> Slim utility ribbon (Investor Relations · Pressroom · Worldwide · Alumni · Client Login) sits above the tall primary nav. The whole thing shrinks from 88px to 64px once you scroll past 32px.</li>
    <li><strong>Insights index parity.</strong> Featured 21:9 hero tile (Tracking Trillions), "The Latest" 3-up, full-bleed dark "In Focus: Artificial Intelligence" mosaic (6 tiles in a lg/md/sm rhythm), "All Insights" 8-up secondary grid, and "Explore by Series" 4-up.</li>
    <li><strong>Topic pages.</strong> Macroeconomics, Exchanges, Talks at GS all share a topic-hero + 3-stat strip + sub-tab nav + 1-large+2-small feature row + filterable archive grid + contributors strip.</li>
    <li><strong>Pillar pages.</strong> Investment Banking and Asset &amp; Wealth Management share a pillar-hero + #1/#2/#3 rankings strip + 3-up offerings grid + selected transactions + division insights + leadership grid.</li>
    <li><strong>Careers Students.</strong> Hero with twin CTAs, 4-stat strip, 6-up programs grid, 8-up divisions mosaic, 3-up voices with quote chrome, and a 5-step application path with serif numerals.</li>
    <li><strong>Article + Podcast detail.</strong> Long-form article body with executive summary, numbered points, pull quotes, methodology callout, footnotes, and share strip. Podcast detail has player chrome, subscribe links, chapter markers with play buttons, transcript, and a sticky right-side persona / related rail.</li>
    <li><strong>Before / after.</strong> Last section in this deliverable shows the v1 (existing design DNA) home + insights pages side-by-side with the v2 companion equivalents.</li>
</ul>

<h2><span class="step">02</span> URL grammar (single file, no auxiliary modules)</h2>
<pre class="cmd">python gs_reference_companion.py            # interactive menu (default)
python gs_reference_companion.py up         # boot v1 + v2 in one runtime, open browser
python gs_reference_companion.py smoke      # render every route via Django test client
python gs_reference_companion.py shoot      # capture all screenshots
python gs_reference_companion.py deliverable # smoke + shoot + build this HTML + open in browser</pre>

<table class="routes">
    <thead><tr><th>URL</th><th>Slug</th><th>Capture size</th></tr></thead>
    <tbody>{''.join(routes_rows)}</tbody>
</table>

<h2><span class="step">03</span> Mega-menu dropdowns</h2>
<p>
    Each top-level nav tab opens a wide-bleed panel: three columns of
    semantic links on the left, three promo tiles on the right. Captured
    with the panel forced into the <code>is-open</code> state so you can
    inspect typography, link density, promo image treatment, and the
    border-left hover affordance on every link.
</p>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">What We Do mega-menu</div></div>
        {img('11_megamenu_what_we_do', 'What We Do mega-menu')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Insights mega-menu</div></div>
        {img('12_megamenu_insights', 'Insights mega-menu')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Our Firm mega-menu</div></div>
        {img('13_megamenu_our_firm', 'Our Firm mega-menu')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Careers mega-menu</div></div>
        {img('14_megamenu_careers', 'Careers mega-menu')}
    </div>
</div>

<h3>Search overlay + sticky shrink</h3>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Search overlay (full-bleed)</div></div>
        {img('15_search_overlay', 'Search overlay')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Header at top (tall — 88px)</div></div>
        {img('16_sticky_top', 'Header at rest')}
    </div>
</div>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Header on scroll (shrunk — 64px)</div></div>
        {img('17_sticky_scrolled', 'Header on scroll')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Insights index — viewport top</div></div>
        {img('01_v2_insights_index', 'Insights index')}
    </div>
</div>

<h2><span class="step">04</span> Insights surface (replication of gs.com/insights)</h2>
<p>
    Featured hero tile uses the same "Tracking Trillions" piece running
    on the live site as of May 2026, followed by "The Latest" three-up
    (Jerome Dortmans podcast, Energy Crunch article, Warsh / Fed podcast),
    then a dark "In Focus: AI" mosaic band (replaces the live site's
    horizontal rule with a richer 6-tile layout), then "All Insights"
    8-up grid, then "Explore by Series" tile rail. Full-page captures:
</p>
<div class="grid-screens grid-screens--single">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/ — Insights index (full page)</div></div>
        {img('01_v2_insights_index', 'Insights index full')}
    </div>
</div>

<h2><span class="step">05</span> Topic landings (3)</h2>
<p>
    Topic pages share an identical layout primitive: dark topic-hero with
    breadcrumb + 3-stat strip below the deck, sub-tab horizontal nav,
    1-large + 2-small feature row, filterable archive grid (with chip
    "Articles · Podcasts · Videos · Reports"), and a contributors strip.
</p>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/insights/macroeconomics/</div></div>
        {img('02_v2_insights_macro', 'Macro topic')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/insights/exchanges/ (Podcast series hub)</div></div>
        {img('03_v2_insights_exchanges', 'Exchanges topic')}
    </div>
</div>
<div class="grid-screens grid-screens--single">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/insights/talks-at-gs/ (Long-form interviews)</div></div>
        {img('04_v2_insights_talks', 'Talks at GS topic')}
    </div>
</div>

<h2><span class="step">06</span> What-We-Do pillars (2)</h2>
<p>
    Pillar pages add a #1/#2/#3 rankings strip beneath the topic-hero,
    a 3-up offerings grid (each with an inline SVG icon, body, and
    sub-link list), a Selected Transactions block (IB only), an
    Insights-from-pillar 3-up, and a 5-up leadership grid with 3:4 portraits.
</p>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/what-we-do/investment-banking/</div></div>
        {img('05_v2_wwd_ib', 'IB pillar')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/what-we-do/asset-wealth/</div></div>
        {img('06_v2_wwd_aw', 'AW pillar')}
    </div>
</div>

<h2><span class="step">07</span> Careers Students</h2>
<p>
    Careers/Students surfaces the deepest editorial pattern: hero with
    twin CTAs (text + video), 4-stat strip, a 6-up programs grid with
    fact-table chrome, 8-up divisions mosaic with photo overlays, 3-up
    voices band with quote treatment, and a 5-step application path.
</p>
<div class="grid-screens grid-screens--single">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">/careers/students/ (full page)</div></div>
        {img('07_v2_careers_students', 'Careers Students')}
    </div>
</div>

<h2><span class="step">08</span> Article + Podcast detail (3)</h2>
<div class="grid-screens">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Article: Tracking Trillions (AI Build-Out)</div></div>
        {img('08_v2_article_tracking', 'Tracking Trillions article')}
    </div>
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Article: Energy Crunch / Electrification</div></div>
        {img('09_v2_article_energy', 'Energy article')}
    </div>
</div>
<div class="grid-screens grid-screens--single">
    <div class="screen">
        <div class="screen__head"><div class="screen__name">Podcast: Jerome Dortmans on Oil Markets</div></div>
        {img('10_v2_podcast_jerome', 'Jerome Dortmans podcast')}
    </div>
</div>

<h2><span class="step">09</span> Before / After vs v1 (legacy design DNA mock)</h2>
<p>
    The original <code>gs_reference</code> (v1) is the abstract design
    DNA reference — token + archetype mock with a simple flat nav and
    no mega-menu chrome. The companion (v2) is a high-fidelity replica
    of the live experience.
</p>

<div class="compare">
    <div class="compare__col compare__col--before">
        <h3><span class="label">BEFORE</span> v1 — Insights list (design DNA)</h3>
        <div class="compare__img">{img('22_v1_insights_list', 'v1 insights list').split('<div class="screen__meta">')[0]}</div>
    </div>
    <div class="compare__col compare__col--after">
        <h3><span class="label">AFTER</span> v2 — Insights index (live replica)</h3>
        <div class="compare__img">{img('01_v2_insights_index', 'v2 insights index').split('<div class="screen__meta">')[0]}</div>
    </div>
</div>

<div class="compare" style="margin-top: 24px;">
    <div class="compare__col compare__col--before">
        <h3><span class="label">BEFORE</span> v1 home nav (flat)</h3>
        <div class="compare__img">{img('21_v1_home', 'v1 home').split('<div class="screen__meta">')[0]}</div>
    </div>
    <div class="compare__col compare__col--after">
        <h3><span class="label">AFTER</span> v2 nav + Insights mega-menu open</h3>
        <div class="compare__img">{img('12_megamenu_insights', 'v2 megamenu').split('<div class="screen__meta">')[0]}</div>
    </div>
</div>

<div class="compare" style="margin-top: 24px;">
    <div class="compare__col compare__col--before">
        <h3><span class="label">BEFORE</span> v1 What We Do landing</h3>
        <div class="compare__img">{img('23_v1_what_we_do', 'v1 what we do').split('<div class="screen__meta">')[0]}</div>
    </div>
    <div class="compare__col compare__col--after">
        <h3><span class="label">AFTER</span> v2 What We Do mega-menu open</h3>
        <div class="compare__img">{img('11_megamenu_what_we_do', 'v2 wwd menu').split('<div class="screen__meta">')[0]}</div>
    </div>
</div>

<h2><span class="step">10</span> Plug into PRISM</h2>
<div class="callout">
    <strong>One line in <code>mysite/urls.py</code> to mount the companion:</strong>
<pre>from django.urls import path, include

urlpatterns += [
    path('gs-companion/', include('gs_reference_companion')),
]</pre>
    No <code>INSTALLED_APPS</code> edits, no <code>settings.py</code>
    changes, no template-search-path config. The companion brings its
    own template loader, its own template tag library
    (<code>gsv2_extras</code>), its own CSS endpoint at
    <code>static/gsv2.css</code>, and its own mega-menu JS at
    <code>static/gsv2.js</code>.
</div>

<h2><span class="step">11</span> Files touched in this run</h2>
<p>
    <span class="tag">+ projects/gs_reference/gs_reference-payload/gs_reference_companion.py</span>
    <span class="tag">{file_size:,} bytes</span>
    <span class="tag">{len(_TEMPLATES)} templates</span>
    <span class="tag">{len(urlpatterns)} routes</span>
    <span class="tag">~3,500 lines CSS</span>
    <span class="tag">~600 lines JS chrome</span>
</p>
<p>
    All deliverable artefacts (this <code>index.html</code> + the
    <code>screenshots/</code> directory) live at:
</p>
<pre>{out_dir}</pre>

</div>
</body>
</html>
"""
    index_path = out_dir / 'index.html'
    index_path.write_text(html, encoding='utf-8')
    return index_path


def cmd_deliverable(args=None) -> int:
    """Smoke + shoot + build HTML deliverable + open in browser."""
    port = getattr(args, 'port', _DEFAULT_PORT) if args else _DEFAULT_PORT
    runtime = getattr(args, 'runtime', 'prism') if args else 'prism'
    no_browser = getattr(args, 'no_browser', False) if args else False

    _cli_banner('gs_reference_companion — build deliverable')

    # 1) Smoke
    _cli_print('[1/4] Smoke testing all routes via Django test client...')
    rc = cmd_smoke()
    if rc != 0:
        _cli_print('Smoke test failed; aborting before shoot.')
        return rc

    # 2) Boot server in background
    port = _find_free_port(port)
    stamp = _dt.datetime.now().strftime('%Y-%m-%d_%H%M')
    out_dir = _OUTPUT_DIR / f'{stamp}_companion'
    screens_dir = out_dir / 'screenshots'
    screens_dir.mkdir(parents=True, exist_ok=True)

    _cli_print(f'\n[2/4] Booting server on port {port}...')
    th, stop_event = _boot_background_server(port, quiet=True)

    try:
        # 3) Capture screenshots
        _cli_print(f'[3/4] Capturing screenshots into {screens_dir} ...')
        sizes = _capture_screenshots(port, screens_dir, runtime=runtime)
    finally:
        stop_event.set()
        th.join(timeout=2.0)

    # 4) Build HTML deliverable
    _cli_print(f'\n[4/4] Building HTML deliverable...')
    index_path = _build_deliverable_html(out_dir, sizes)
    _cli_print(f'Wrote {index_path}')

    if not no_browser:
        _webbrowser.open(f'file://{index_path.resolve()}')
        _cli_print('Opened in browser.')

    return 0


def cmd_menu(args=None) -> int:
    """Interactive menu."""
    items = [
        ('Up                Boot v1 + v2 in one Django runtime, open browser', cmd_up),
        ('Smoke             Render every route via Django test client',         cmd_smoke),
        ('Shoot             Capture playwright screenshots of all pages',       cmd_shoot),
        ('Deliverable       Smoke + Shoot + build HTML deliverable + open',     cmd_deliverable),
        ('Quit',                                                                  None),
    ]
    while True:
        _cli_banner('gs_reference_companion — interactive menu')
        for i, (label, _fn) in enumerate(items, start=1):
            print(f'  {i})  {label}')
        print()
        try:
            choice = input('  Choose [4]: ').strip() or '4'
        except (EOFError, KeyboardInterrupt):
            print('\n  Bye.')
            return 0
        if not choice.isdigit() or not (1 <= int(choice) <= len(items)):
            print(f'  Pick a number 1-{len(items)}.')
            continue
        idx = int(choice) - 1
        label, fn = items[idx]
        if fn is None:
            print('  Bye.')
            return 0
        rc = fn(_argns())
        if rc and rc != 0:
            print(f'  Last command exited with code {rc}.')
        print()


def _argns(**kw) -> argparse.Namespace:
    ns = argparse.Namespace()
    ns.port = kw.get('port', _DEFAULT_PORT)
    ns.no_browser = kw.get('no_browser', False)
    ns.runtime = kw.get('runtime', 'prism')
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _cli_main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog='gs_reference_companion.py',
        description='Single-file Django plug-in mock of goldmansachs.com/insights '
                    '+ mega-menu chrome. Run without arguments for the interactive menu.',
    )
    sub = parser.add_subparsers(dest='cmd')

    p_up = sub.add_parser('up', help='Boot v1 + v2 in one Django runtime, open browser')
    p_up.add_argument('--port', type=int, default=_DEFAULT_PORT)
    p_up.add_argument('--no-browser', action='store_true')
    p_up.set_defaults(func=cmd_up)

    p_smoke = sub.add_parser('smoke', help='Render every route via Django test client')
    p_smoke.set_defaults(func=cmd_smoke)

    p_shoot = sub.add_parser('shoot', help='Capture playwright screenshots')
    p_shoot.add_argument('--port', type=int, default=_DEFAULT_PORT)
    p_shoot.add_argument('--runtime', choices=['prism', 'live'], default='prism')
    p_shoot.set_defaults(func=cmd_shoot)

    p_deliv = sub.add_parser('deliverable', help='Smoke + Shoot + build HTML deliverable + open in browser')
    p_deliv.add_argument('--port', type=int, default=_DEFAULT_PORT)
    p_deliv.add_argument('--runtime', choices=['prism', 'live'], default='prism')
    p_deliv.add_argument('--no-browser', action='store_true')
    p_deliv.set_defaults(func=cmd_deliverable)

    p_menu = sub.add_parser('menu', help='Force the interactive menu')
    p_menu.set_defaults(func=cmd_menu)

    args = parser.parse_args(argv)
    if args.cmd is None:
        return cmd_menu()
    return args.func(args)


if __name__ == '__main__':
    sys.exit(_cli_main())
