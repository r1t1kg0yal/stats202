"""gs_reference.py — Single-file Django plug-in that serves the GS website
mock at any sub-route in PRISM.

This module is the byte-identical drag-and-drop counterpart to the standalone
mysite_gs/ Django project under ai_development/. Drop this ONE file into
PRISM's ai_development/ directory and add ONE include() line to PRISM's
mysite/urls.py. No INSTALLED_APPS edit. No settings.py edit. No template-
search-path config. No static-file plumbing for the CSS or the page templates.

╔════════════════════════════════════════════════════════════════════════╗
║ PLUG-AND-PLAY INSTRUCTIONS                                              ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                         ║
║ 1. Drop this file into your PRISM repo's ai_development/ directory:     ║
║      cp gs_reference.py /path/to/prism/ai_development/                  ║
║                                                                         ║
║ 2. Add ONE line to PRISM's mysite/urls.py:                              ║
║      from django.urls import path, include                              ║
║      urlpatterns += [                                                   ║
║          path('gs-reference/', include('gs_reference')),                ║
║      ]                                                                  ║
║                                                                         ║
║ 3. (Optional) Tell us where to find GS Sans TTFs if PRISM doesn't       ║
║    serve them at /static/fonts/ (the staging frontend default):         ║
║      import gs_reference                                                ║
║      gs_reference.config['fonts_url_prefix'] = '/static/news/fonts'     ║
║                                                                         ║
║ Browse to /gs-reference/ and the GS home page renders. Eight pages      ║
║ resolve under that mount:                                               ║
║   /gs-reference/                            home                        ║
║   /gs-reference/what-we-do/                 pillar landing              ║
║   /gs-reference/insights/                   insights list               ║
║   /gs-reference/insights/article/           long-form article           ║
║   /gs-reference/insights/podcast/           podcast detail              ║
║   /gs-reference/careers/                    careers landing             ║
║   /gs-reference/careers/life/               life-at-the-firm            ║
║   /gs-reference/our-firm/purpose-and-values/   purpose / values         ║
║                                                                         ║
║ Mount under any prefix you like. Internal navigation uses Django's      ║
║ reverse() so URLs resolve correctly regardless of where you include().  ║
║                                                                         ║
╚════════════════════════════════════════════════════════════════════════╝

The mock IS the same one rendered by the standalone mysite_gs/ Django project
under projects/gs_reference/gs_reference-payload/ai_development/. The Python
+ HTML + CSS bytes are inlined here so the surface is one file.

What this file embeds:
  - 8 view functions with placeholder content dicts (lorem-style prose, no
    real GS marketing copy).
  - 9 templates (1 base + 8 pages) loaded via a private Django Engine that
    uses an in-memory loader; PRISM's TEMPLATES setting is untouched.
  - 3 CSS files (tokens + fonts + components, ~1,800 lines) concatenated
    and served by a single inline view at /<mount>/static/gs.css.
  - The gs_placeholder template tag (Picsum-backed deterministic-seed image).

What this file does NOT embed:
  - The 20 GS Sans TTF font files (binary; can't go in a Python string).
    The fonts.css URL paths default to /static/fonts/<name>.ttf — PRISM's
    existing /static/fonts/ wiring (per staging/README frontend section)
    serves them. Override via config['fonts_url_prefix'] if your PRISM
    staticfiles layout differs.
  - Any real GS marketing copy or photography. Per the design DNA spec §12.2
    every page uses placeholder prose with PRISM-themed names. Picsum/
    Unsplash stock backs every image via the gs_placeholder tag.
"""

import hashlib
from typing import Any, Callable, Dict, Optional

from django.http import HttpResponse
from django.template import Context, Engine, Library
from django.urls import path, reverse
from django.utils.safestring import mark_safe


# ════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ════════════════════════════════════════════════════════════════════════════
# Override AFTER importing this module if defaults don't match your PRISM
# layout, e.g. in PRISM's mysite/settings.py or in a startup hook.

config: Dict[str, Any] = {
    # Where the browser fetches GS Sans TTF files. PRISM's frontend project
    # mounts news/static/fonts/ at /static/fonts/ via STATICFILES_DIRS (per
    # the staging/README frontend section). If your PRISM serves fonts at a
    # different URL prefix, override here BEFORE the first /gs.css request.
    'fonts_url_prefix': '/static/fonts',
}


# ════════════════════════════════════════════════════════════════════════════
# TEMPLATE TAG LIBRARY  ({% load gs_extras %})
# ════════════════════════════════════════════════════════════════════════════
# Django's template engine resolves `{% load <name> %}` against the
# `libraries` dict on the Engine; we map 'gs_extras' to this module's name
# (see _make_engine() below). Django then imports this module and looks for
# a Library instance literally named `register`.

register = Library()


@register.simple_tag
def gs_placeholder(tint: str = 'navy', aspect: str = '16x9',
                   label: str = '', seed: str = '') -> str:
    """Render an <img> backed by Picsum (Unsplash-sourced stock photo).

    Args:
        tint:   Semantic colour hint from the dataviz palette (navy, sky,
                mauve, teal, burnt, purple, brick, amber, brown, olive).
                Folded into the deterministic seed so a given (tint, aspect,
                label) tuple yields the same photo across page loads.
        aspect: '16x9' / '21x9' / '4x5' / '1x1'.
        label:  Optional content hint folded into the seed for additional
                uniqueness; also used as alt text.
        seed:   Explicit seed override; takes precedence over (tint+label)
                so callers can force a distinct image at a given placement.
    """
    aspects = {
        '16x9': (1600, 900),
        '21x9': (2100, 900),
        '4x5':  (800, 1000),
        '1x1':  (1000, 1000),
    }
    width, height = aspects.get(aspect, aspects['16x9'])
    seed_str = seed or f'{tint}-{aspect}-{label}'
    digest = hashlib.sha1(seed_str.encode('utf-8')).hexdigest()[:12]
    url = f'https://picsum.photos/seed/{digest}/{width}/{height}'
    alt = (label or f'placeholder ({tint})').replace(
        '&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return mark_safe(
        f'<img src="{url}" alt="{alt}" loading="lazy" '
        f'width="{width}" height="{height}">'
    )


# ════════════════════════════════════════════════════════════════════════════
# TEMPLATES (9: 1 base + 8 pages)
# ════════════════════════════════════════════════════════════════════════════
# Templates are stored as Python string constants below and loaded via
# django.template.loaders.locmem.Loader (configured in _make_engine()).
# Internal navigation uses {% url 'gs_reference:<name>' %} so the templates
# don't care where this URL conf is mounted in PRISM's main urls.py.
#
# All hardcoded /paths/ from the original mysite_gs/ templates have been
# rewritten to {% url %} for mount-prefix-agnosticism.

_BASE_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-runtime="{{ request.GET.runtime|default:'prism' }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{% block title %}gs-reference mock{% endblock %}</title>
    <meta name="description" content="Mock of the gs.com visual design language for PRISM-side reference.">
    <link rel="stylesheet" href="{% url 'gs_reference:css' %}?v=8">
</head>
<body>

    <header class="gs-nav" role="banner">
        <div class="gs-nav__inner">
            <a href="{% url 'gs_reference:home' %}" class="gs-nav__logo">
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
                        <li><a href="{% url 'gs_reference:purpose' %}">Purpose and Values</a></li>
                        <li><a href="#">Our People</a></li>
                        <li><a href="#">History</a></li>
                        <li><a href="#">Newsroom</a></li>
                        <li><a href="#">Sustainability</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">What We Do</h3>
                    <ul class="gs-footer__list">
                        <li><a href="{% url 'gs_reference:what_we_do' %}">Investment Banking</a></li>
                        <li><a href="{% url 'gs_reference:what_we_do' %}">Asset Management</a></li>
                        <li><a href="{% url 'gs_reference:what_we_do' %}">Wealth Management</a></li>
                        <li><a href="{% url 'gs_reference:what_we_do' %}">Markets</a></li>
                        <li><a href="{% url 'gs_reference:what_we_do' %}">Platform Solutions</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">Insights</h3>
                    <ul class="gs-footer__list">
                        <li><a href="{% url 'gs_reference:insights_list' %}">All Insights</a></li>
                        <li><a href="{% url 'gs_reference:insights_list' %}">Macroeconomics</a></li>
                        <li><a href="{% url 'gs_reference:insights_list' %}">Markets</a></li>
                        <li><a href="{% url 'gs_reference:insights_list' %}">Podcasts</a></li>
                    </ul>
                </div>
                <div>
                    <h3 class="gs-footer__col-title">Careers</h3>
                    <ul class="gs-footer__list">
                        <li><a href="{% url 'gs_reference:careers' %}">Careers Home</a></li>
                        <li><a href="{% url 'gs_reference:careers_life' %}">Life at the Firm</a></li>
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
"""


_HOME_TEMPLATE = """{% extends "gsapp/base.html" %}
{% load gs_extras %}

{% block title %}Home — gs-reference mock{% endblock %}

{% block content %}

{# Hero (DNA §8.4) #}
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

{# Tab strip (DNA §8.7) #}
<nav class="gs-tabs" aria-label="Section tabs">
    <ul class="gs-tabs__list">
        {% for tab in tabs %}
        <li class="gs-tabs__item {% if tab.active %}gs-tabs__item--active{% endif %}">
            <a href="{{ tab.url }}">{{ tab.label }}</a>
        </li>
        {% endfor %}
    </ul>
</nav>

{# Deal spotlights (overlay-card variant) #}
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

{# What We Do (4-up cards) #}
<section class="gs-section gs-section--subtle">
    <div class="gs-container">
        <header class="gs-section-heading">
            <span class="gs-overline">What We Do</span>
            <h2 class="gs-headline gs-headline--04">Delivering for Our Clients</h2>
        </header>
        <div class="gs-grid gs-grid--4">
            {% for card in what_we_do_cards %}
            <a href="{% url 'gs_reference:what_we_do' %}" class="gs-card">
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

{# Insights two-up #}
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

{# Careers two-up (reverse) #}
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

{# Stats row (DNA §8.6) #}
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

{# Our Firm two-up #}
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
"""


_WHAT_WE_DO_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_INSIGHTS_LIST_TEMPLATE = """{% extends "gsapp/base.html" %}
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
            <a href="{% url 'gs_reference:insights_article' %}" class="gs-card">
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
"""


_INSIGHTS_ARTICLE_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_INSIGHTS_PODCAST_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_CAREERS_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_CAREERS_LIFE_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_PURPOSE_TEMPLATE = """{% extends "gsapp/base.html" %}
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
"""


_TEMPLATES: Dict[str, str] = {
    'gsapp/base.html':              _BASE_TEMPLATE,
    'gsapp/home.html':              _HOME_TEMPLATE,
    'gsapp/what_we_do.html':        _WHAT_WE_DO_TEMPLATE,
    'gsapp/insights_list.html':     _INSIGHTS_LIST_TEMPLATE,
    'gsapp/insights_article.html':  _INSIGHTS_ARTICLE_TEMPLATE,
    'gsapp/insights_podcast.html':  _INSIGHTS_PODCAST_TEMPLATE,
    'gsapp/careers.html':           _CAREERS_TEMPLATE,
    'gsapp/careers_life.html':      _CAREERS_LIFE_TEMPLATE,
    'gsapp/purpose.html':           _PURPOSE_TEMPLATE,
}


# ════════════════════════════════════════════════════════════════════════════
# CSS  (tokens + fonts + components, ~1,800 lines combined)
# ════════════════════════════════════════════════════════════════════════════
# Served by serve_css() below at /<mount>/static/gs.css. The fonts.css block
# is parameterised on config['fonts_url_prefix'] so the user can route TTF
# requests at whatever path PRISM exposes the GS Sans drop on (default
# /static/fonts/, the staging frontend convention). Raw strings preserve the
# CSS \\201C / \\201D quote escapes verbatim.

_CSS_TOKENS = r""":root {
    --gs-uitk-color-surface-neutral-minimal: #FFFFFF;
    --gs-uitk-color-surface-neutral-subtle: #F7F7FA;
    --gs-uitk-color-surface-neutral-regular: #DCDCE0;
    --gs-uitk-color-surface-neutral-bold: #A2A4A6;
    --gs-uitk-color-surface-inverse-bold: #000000;
    --gs-uitk-color-surface-always-dark-regular: #121212;
    --gs-uitk-color-surface-brand-bold: #7297C5;
    --gs-uitk-color-surface-brand-subtle: #F0EBE6;
    --gs-uitk-color-surface-backdrop: rgba(18, 18, 18, 0.8);

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

    --gs-uitk-color-dataviz-categorical010: #092C61;
    --gs-uitk-color-dataviz-categorical010_070: #073985;
    --gs-uitk-color-dataviz-categorical010_080: #092C61;
    --gs-uitk-color-dataviz-categorical010_090: #0B2040;
    --gs-uitk-color-dataviz-categorical010_100: #0B1624;
    --gs-uitk-color-dataviz-categorical020: #7297C5;
    --gs-uitk-color-dataviz-categorical030: #A6428C;
    --gs-uitk-color-dataviz-categorical040: #159788;
    --gs-uitk-color-dataviz-categorical050: #E0731A;
    --gs-uitk-color-dataviz-categorical060: #7537AD;
    --gs-uitk-color-dataviz-categorical070: #B03030;
    --gs-uitk-color-dataviz-categorical080: #BD8C00;
    --gs-uitk-color-dataviz-categorical090: #69370E;
    --gs-uitk-color-dataviz-categorical100: #617A27;
    --gs-uitk-color-dataviz-divergent-positive: #398025;
    --gs-uitk-color-dataviz-divergent-negative: #C2170A;
    --gs-uitk-color-dataviz-divergent-contrast-positive: #092C61;
    --gs-uitk-color-dataviz-divergent-contrast-negative: #E0731A;

    --gs-uitk-overlay-hero: linear-gradient(180deg, rgba(0,0,0,0) 50%, rgba(0,0,0,0.8) 100%);
    --gs-uitk-overlay-card: linear-gradient(180deg, rgba(0,0,0,0) 30%, rgba(0,0,0,0.55) 100%);

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

    --gs-uitk-width-container: 1440px;
    --gs-uitk-width-prose: 816px;
    --gs-uitk-gutter-xs: 24px;
    --gs-uitk-gutter-md: 48px;
    --gs-uitk-gutter-lg: 64px;

    --gs-uitk-border-radius-none: 0px;
    --gs-uitk-border-radius-sm: 2px;
    --gs-uitk-border-radius-pill: 9999px;

    --gs-uitk-shadow-overlay: 0 8px 32px rgba(0, 0, 0, 0.16);

    --gs-font-sans: "GS Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    --gs-font-sans-condensed: "GS Sans Condensed", "Helvetica Neue Condensed", "Helvetica Neue", Helvetica, Arial, sans-serif;
    --gs-font-serif-live: "GS Serif", "Times New Roman", Times, Georgia, serif;
    --gs-font-serif-prism: var(--gs-font-sans-condensed);
    --gs-font-mono: ui-monospace, "Roboto Mono", "SF Mono", Menlo, Monaco, Consolas, monospace;

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

    --gs-uitk-text-heading01-regular-font: 400 40px/48px var(--gs-font-sans);
    --gs-uitk-text-heading01-medium-font: 500 40px/48px var(--gs-font-sans);
    --gs-uitk-text-heading02-regular-font: 400 32px/40px var(--gs-font-sans);
    --gs-uitk-text-heading02-medium-font: 500 32px/40px var(--gs-font-sans);
    --gs-uitk-text-heading03-regular-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-heading03-medium-font: 500 24px/32px var(--gs-font-sans);

    --gs-uitk-text-subtitle01-regular-xs-screen-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-regular-md-screen-font: 400 28px/38px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-regular-lg-screen-font: 400 36px/42px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-xs-screen-font: 500 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-md-screen-font: 500 28px/38px var(--gs-font-sans);
    --gs-uitk-text-subtitle01-medium-lg-screen-font: 500 36px/42px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-xs-screen-font: 400 22px/28px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-md-screen-font: 400 24px/32px var(--gs-font-sans);
    --gs-uitk-text-subtitle02-regular-lg-screen-font: 400 28px/36px var(--gs-font-sans);

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

    --gs-uitk-text-stat01-xs-screen-font: 300 100px/100px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat01-md-screen-font: 300 144px/144px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat01-lg-screen-font: 300 200px/200px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-xs-screen-font: 300 72px/72px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-md-screen-font: 300 88px/88px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat02-lg-screen-font: 300 100px/100px var(--gs-font-sans-condensed);
    --gs-uitk-text-stat03-xs-screen-font: 500 44px/44px var(--gs-font-sans);
    --gs-uitk-text-stat03-md-screen-font: 500 46px/46px var(--gs-font-sans);
    --gs-uitk-text-stat03-lg-screen-font: 500 46px/46px var(--gs-font-sans);

    --gs-uitk-text-code01-font: 400 14px/20px var(--gs-font-mono);
    --gs-uitk-text-code02-font: 500 12px/16px var(--gs-font-mono);
}

html[data-runtime="live"] {
    --gs-font-serif-prism: var(--gs-font-serif-live);
}
"""


# fonts.css uses the literal token __GS_FONTS_URL__ as a placeholder for the
# user's configured fonts URL prefix. _build_css() substitutes it at request
# time so the runtime CSS string reflects the live config.

_CSS_FONTS = r"""@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_Th.ttf") format("truetype");
    font-weight: 250;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_ThIt.ttf") format("truetype");
    font-weight: 250;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_Lt.ttf") format("truetype");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_LIt.ttf") format("truetype");
    font-weight: 300;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_Rg.ttf") format("truetype");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_It.ttf") format("truetype");
    font-weight: 400;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_Md.ttf") format("truetype");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_MdIt.ttf") format("truetype");
    font-weight: 500;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_Bd.ttf") format("truetype");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans";
    src: url("__GS_FONTS_URL__/GSSans_BdIt.ttf") format("truetype");
    font-weight: 700;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_Lt.ttf") format("truetype");
    font-weight: 300;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_LIt.ttf") format("truetype");
    font-weight: 300;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_Rg.ttf") format("truetype");
    font-weight: 400;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_It.ttf") format("truetype");
    font-weight: 400;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_Md.ttf") format("truetype");
    font-weight: 500;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_MdIt.ttf") format("truetype");
    font-weight: 500;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_Bd.ttf") format("truetype");
    font-weight: 700;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_BdIt.ttf") format("truetype");
    font-weight: 700;
    font-style: italic;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_Blk.ttf") format("truetype");
    font-weight: 900;
    font-style: normal;
    font-display: swap;
}
@font-face {
    font-family: "GS Sans Condensed";
    src: url("__GS_FONTS_URL__/GSSansCondensed_BlkIt.ttf") format("truetype");
    font-weight: 900;
    font-style: italic;
    font-display: swap;
}
"""


_CSS_COMPONENTS = r"""*,
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

.gs-section-heading {
    display: flex;
    flex-direction: column;
    gap: var(--gs-uitk-space-3);
    margin-bottom: var(--gs-uitk-space-7);
}

.gs-nav {
    position: sticky;
    top: 0;
    z-index: 100;
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

.gs-tabs {
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

.gs-card--text {
    padding: var(--gs-uitk-space-7);
}

.gs-card--text .gs-card__body {
    padding: 0;
}

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

.gs-stat--hero .gs-stat__numeral {
    font: var(--gs-uitk-text-stat01-xs-screen-font);
}

@media (min-width: 768px)  { .gs-stat--hero .gs-stat__numeral { font: var(--gs-uitk-text-stat01-md-screen-font); } }
@media (min-width: 1200px) { .gs-stat--hero .gs-stat__numeral { font: var(--gs-uitk-text-stat01-lg-screen-font); } }

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

.gs-briefings {
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
"""


def _build_css() -> str:
    """Build the combined CSS body, substituting the configured fonts URL prefix."""
    fonts_url = config['fonts_url_prefix'].rstrip('/')
    fonts_resolved = _CSS_FONTS.replace('__GS_FONTS_URL__', fonts_url)
    return _CSS_TOKENS + '\n\n' + fonts_resolved + '\n\n' + _CSS_COMPONENTS


# ════════════════════════════════════════════════════════════════════════════
# CUSTOM TEMPLATE ENGINE
# ════════════════════════════════════════════════════════════════════════════
# We instantiate our own Engine rather than borrowing PRISM's so the user
# doesn't have to touch settings.py to register our locmem templates or our
# template-tag library.
#
# Engine.__init__ accepts a `libraries` dict mapping the name used by
# `{% load <name> %}` in templates to the module path Django should import.
# Django then imports that module and looks up `register` (a Library instance)
# by name. We pass __name__ (this module's import path) so when templates say
# `{% load gs_extras %}` Django finds our `register` defined above.

_engine: Optional[Engine] = None


def _make_engine() -> Engine:
    return Engine(
        loaders=[
            ('django.template.loaders.locmem.Loader', _TEMPLATES),
        ],
        libraries={'gs_extras': __name__},
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


# ════════════════════════════════════════════════════════════════════════════
# NAV / SHARED CONTEXT
# ════════════════════════════════════════════════════════════════════════════
# NAV_LINKS is a tuple of (url-name, display-label). _base_context() resolves
# each url-name to its actual URL via reverse() at request time, so the nav
# is mount-prefix-agnostic — drop us at /gs-reference/, /gs/, or /, the nav
# always points at the right URLs.

NAV_LINKS = (
    ('what_we_do',      'What We Do'),
    ('insights_list',   'Insights'),
    ('purpose',         'Our Firm'),
    ('careers',         'Careers'),
)


def _u(name: str) -> str:
    """Reverse a URL name within our app namespace."""
    return reverse(f'gs_reference:{name}')


def _base_context(request, active_nav: Optional[str] = None) -> Dict[str, Any]:
    nav_items = [
        {'label': label, 'url': _u(name)}
        for name, label in NAV_LINKS
    ]
    return {
        'nav_items': nav_items,
        'active_nav': active_nav,
        'request': request,
    }


# ════════════════════════════════════════════════════════════════════════════
# VIEWS
# ════════════════════════════════════════════════════════════════════════════
# Each view assembles its placeholder content dict (lorem-style copy + PRISM-
# themed names per design DNA spec §12.2) and renders the corresponding
# template. Internal CTAs use _u(name) so URLs resolve relative to the URL
# conf mount, not to an absolute path.

def home(request):
    ctx = _base_context(request)
    ctx.update({
        'hero': {
            'eyebrow': 'AI in Focus',
            'title': 'The Trillion-Dollar Question',
            'subtitle': (
                'Tracking how the assumptions behind AI infrastructure spend '
                'shape the next decade of capital allocation across compute, '
                'data centers, and power.'
            ),
            'cta_label': 'Read the Analysis',
            'cta_url': _u('insights_article'),
            'image_tint': 'navy',
        },
        'tabs': [
            {'label': 'Stay Informed', 'url': '#stay-informed', 'active': True},
            {'label': 'The Firm in Action', 'url': '#the-firm-in-action'},
        ],
        'deal_spotlights': [
            {
                'eyebrow': 'Deal Spotlight',
                'title': "Acme Industries' $1.1B IPO",
                'body': (
                    "Strategy advised on Acme Industries' initial public "
                    'offering, a leading designer of mission-critical '
                    'components engineered for performance in extreme '
                    'environments.'
                ),
                'cta': 'See the Deal',
                'image_tint': 'amber',
            },
            {
                'eyebrow': 'Deal Spotlight',
                'title': 'Northstar Logistics $10.5B Acquisition',
                'body': (
                    'Lead financial advisor to Northstar Logistics on its '
                    'acquisition of a regional storage and distribution '
                    'operator with assets across 14 metro areas.'
                ),
                'cta': 'See the Deal',
                'image_tint': 'teal',
            },
        ],
        'what_we_do_cards': [
            {
                'eyebrow': 'Investment Banking',
                'title': 'Mergers & Acquisitions',
                'body': (
                    'Strategic advisory across the full M&A lifecycle for '
                    'the most complex cross-border transactions.'
                ),
                'image_tint': 'navy',
            },
            {
                'eyebrow': 'Capital Markets',
                'title': 'Equity Capital Solutions',
                'body': (
                    'Underwriting, syndication, and capital structuring '
                    'expertise across IPOs, follow-ons, and converts.'
                ),
                'image_tint': 'purple',
            },
            {
                'eyebrow': 'Trading',
                'title': 'FICC and Equities',
                'body': (
                    'Market-making and risk intermediation across rates, '
                    'credit, FX, commodities, equities, and derivatives.'
                ),
                'image_tint': 'burnt',
            },
            {
                'eyebrow': 'Asset Management',
                'title': 'Multi-Asset Solutions',
                'body': (
                    'Custom portfolio construction across public and '
                    'private markets for institutional and individual clients.'
                ),
                'image_tint': 'olive',
            },
        ],
        'insights_two_up': {
            'eyebrow': 'Our Thinking',
            'title': 'Insights on Financial Markets and the Global Economy',
            'body': (
                'Analysis and perspectives from our research, strategy, and '
                'investment teams, calibrated for institutional decision-makers '
                'navigating regime shifts, policy uncertainty, and dispersion.'
            ),
            'cta': 'All Insights',
            'cta_url': _u('insights_list'),
            'image_tint': 'mauve',
        },
        'careers_two_up': {
            'eyebrow': 'Careers',
            'title': 'Practice, Mentorship, Mastery',
            'body': (
                'Sample placeholder copy describing a hypothetical career '
                'track at a hypothetical firm. Lorem ipsum dolor sit amet, '
                'consectetur adipiscing elit, sed do eiusmod tempor.'
            ),
            'cta': 'Explore Careers',
            'cta_url': _u('careers'),
            'image_tint': 'teal',
        },
        'stats': [
            {'numeral': '46K+', 'caption': 'People around the world', 'footnote_n': 1},
            {'numeral': '1M+', 'caption': 'External applications received last year', 'footnote_n': 1},
            {'numeral': '95%+', 'caption': 'Clients give the firm top ratings of expertise', 'footnote_n': 2},
        ],
        'our_firm_two_up': {
            'eyebrow': 'Our Firm',
            'title': "We Aspire to Be the World's Most Exceptional Financial Institution",
            'body': (
                'Built on the principles of partnership, client service, '
                'integrity, and excellence, with a 150-year heritage of '
                "advising the world's most influential institutions."
            ),
            'cta': 'Discover Our Purpose',
            'cta_url': _u('purpose'),
            'image_tint': 'brown',
        },
        'footnotes': [
            '1 Headcount and external applicants as of fictional reference year. Placeholder figure for layout demonstration only.',
            '2 Biennial client and stakeholder survey. Data shown is illustrative and does not reflect any actual survey result.',
        ],
    })
    return HttpResponse(_render('gsapp/home.html', ctx, request))


def what_we_do(request):
    ctx = _base_context(request, active_nav='What We Do')
    ctx.update({
        'page_eyebrow': 'What We Do',
        'page_title': 'Our Businesses',
        'page_subtitle': (
            "We deliver advisory, financing, market-making, and asset "
            "management services to the world's most influential institutions, "
            'corporations, governments, and individuals.'
        ),
        'pillars': [
            {'id': 'global-banking', 'label': 'Global Banking & Markets', 'active': True},
            {'id': 'asset-wealth',   'label': 'Asset & Wealth Management'},
            {'id': 'platform',       'label': 'Platform Solutions'},
        ],
        'pillar_sections': [
            {
                'id': 'global-banking',
                'eyebrow': 'Global Banking & Markets',
                'title': 'Investment Banking',
                'body': (
                    'We serve the most influential corporations and institutions '
                    'with strategic advisory, financing, and capital structuring '
                    'across the full deal lifecycle.'
                ),
                'links': [
                    {'label': 'Mergers & Acquisitions',
                     'body': 'Cross-border M&A advisory anchored by sector depth and execution rigour, partnering with leadership through every stage of the process.'},
                    {'label': 'Capital Solutions',
                     'body': "End-to-end underwriting across equity, debt, and structured products, leveraging the firm's network to source and deliver bespoke capital structures."},
                ],
            },
            {
                'id': 'asset-wealth',
                'eyebrow': 'Asset & Wealth Management',
                'title': 'Asset Management',
                'body': (
                    'Investment management across public and private markets '
                    'for institutional, intermediary, and individual clients.'
                ),
                'links': [
                    {'label': 'Equity',
                     'body': 'Active fundamental and quantitative strategies across emerging and developed markets.'},
                    {'label': 'Fixed Income',
                     'body': 'Single-sector, multi-sector, and regional credit and rates strategies across the public-credit universe.'},
                    {'label': 'Liquidity Solutions',
                     'body': 'Highly liquid short-duration strategies across government and high-grade corporate instruments.'},
                    {'label': 'Alternatives',
                     'body': 'Private equity, growth equity, private credit, real estate, infrastructure, and hedge funds.'},
                ],
            },
            {
                'id': 'platform',
                'eyebrow': 'Platform Solutions',
                'title': 'Transaction Banking',
                'body': (
                    'Cash management, treasury, and embedded financial '
                    'infrastructure for corporates and platform partners.'
                ),
                'links': [
                    {'label': 'Treasury Services',
                     'body': 'Multi-currency cash management with API-first integration into corporate treasury workflows.'},
                ],
            },
        ],
    })
    return HttpResponse(_render('gsapp/what_we_do.html', ctx, request))


def insights_list(request):
    ctx = _base_context(request, active_nav='Insights')
    ctx.update({
        'page_eyebrow': 'Insights',
        'page_title': 'Analysis from Across the Firm',
        'page_subtitle': (
            'Perspectives on the global economy, markets, and policy from '
            'our research, strategy, and investment teams.'
        ),
        'featured': {
            'eyebrow': 'Artificial Intelligence',
            'title': 'Tracking Trillions: The Assumptions Shaping the AI Build-Out',
            'date': 'May 1, 2026',
            'image_tint': 'navy',
            'url': _u('insights_article'),
        },
        'latest': [
            {'eyebrow': 'The Markets', 'title': 'Crude Oil Drivers and the Path Through 2026',
             'format': 'Podcast', 'date': 'May 8, 2026', 'image_tint': 'burnt',
             'url': _u('insights_podcast')},
            {'eyebrow': 'Energy', 'title': 'Could the Power Crunch Accelerate the Electrification Shift',
             'format': 'Article', 'date': 'May 5, 2026', 'image_tint': 'olive',
             'url': _u('insights_article')},
            {'eyebrow': 'Exchanges', 'title': 'How a New Fed Chair Could Reshape Policy',
             'format': 'Podcast', 'date': 'Apr 28, 2026', 'image_tint': 'purple',
             'url': _u('insights_podcast')},
        ],
        'in_focus_eyebrow': 'In Focus: Artificial Intelligence',
        'in_focus_cards': [
            {'eyebrow': 'Markets', 'title': 'How AI Is Changing Quantitative Investing',
             'format': 'Podcast', 'date': 'Apr 22, 2026', 'image_tint': 'mauve'},
            {'eyebrow': 'Macro', 'title': 'AI Capex and the Productivity Question',
             'format': 'Article', 'date': 'Apr 15, 2026', 'image_tint': 'teal'},
            {'eyebrow': 'Equities', 'title': 'Sectoral Dispersion in the AI Beneficiaries Trade',
             'format': 'Article', 'date': 'Apr 10, 2026', 'image_tint': 'navy'},
            {'eyebrow': 'Credit', 'title': 'Funding Models for Hyperscaler Buildouts',
             'format': 'Article', 'date': 'Apr 03, 2026', 'image_tint': 'amber'},
        ],
    })
    return HttpResponse(_render('gsapp/insights_list.html', ctx, request))


def insights_article(request):
    ctx = _base_context(request, active_nav='Insights')
    ctx.update({
        'article': {
            'eyebrow': 'Artificial Intelligence',
            'title': 'Tracking Trillions: The Assumptions Shaping the AI Build-Out',
            'date': 'May 1, 2026',
            'read_time': '12 min read',
            'image_tint': 'navy',
            'authors': [
                {'name': 'Ada Fictional', 'title': 'Co-Head, Global Institute'},
                {'name': 'Ben Placeholder', 'title': 'Vice President, Global Institute'},
            ],
            'intro': (
                'The capital expenditure debate is usually framed as a '
                'demand-side question — will adoption justify the spend — '
                'but the size of the investment itself is not a single, '
                'fixed number.'
            ),
            'exec_summary_body': (
                'Estimates rest on a small set of assumptions about how the '
                'infrastructure itself is built and renewed. Four assumptions '
                'are most impactful in determining the scale of the build-out:'
            ),
            'numbered_points': [
                'The economic useful life of compute silicon, where small shifts in replacement cadence move cumulative spend by hundreds of billions.',
                'The cost and complexity of next-generation data centers, which are rising as workloads push power density higher and system integration deeper.',
                'The chip and architecture mix, whose impact depends on whether compute demand is elastic (reshaping margins) or inelastic (reshaping totals).',
                'Elongation from power, labor, and equipment bottlenecks, which in stress scenarios can feed back into demand-side doubt.',
            ],
            'sections': [
                {
                    'heading': 'Framing the Question',
                    'body': (
                        'A single inference query feels weightless — a question '
                        'typed, an answer returned, no moving parts in sight. '
                        'But the underlying infrastructure rests on a deeply '
                        'physical edifice: millions of processors, hundreds of '
                        'thousands of kilometers of cabling, industrial cooling '
                        'systems, and power demands that rival those of midsize '
                        'countries. Better understanding of that complexity — '
                        'and the assumptions on which build-out rests — should '
                        'inform how we think about the scale, durability, and '
                        'risks of the capital expenditure boom.'
                    ),
                },
                {
                    'heading': 'Baseline Estimates',
                    'body': (
                        'We anchor a baseline model to forward data center '
                        'revenue estimates as a proxy for prevailing '
                        'expectations around accelerator deployment, and then '
                        'infer the associated requirements for data centers, '
                        'power, and supporting infrastructure. The baseline '
                        'implies roughly $700 billion in annual capex in 2026, '
                        'growing toward $1.5 trillion in 2031.'
                    ),
                    'pull_quote': (
                        'The headline capex figures are not a single number. '
                        'They are a band whose width is set by infrastructure '
                        'assumptions, not just demand.'
                    ),
                },
                {
                    'heading': 'Sensitivity to Useful Life',
                    'body': (
                        'If accelerators are replaced every two years instead '
                        'of four, cumulative capex over a five-year horizon '
                        'expands by hundreds of billions. The replacement '
                        'cadence is the single most sensitive lever in the '
                        'model — yet it is also the assumption with the '
                        'weakest empirical anchor, since the technology is '
                        'young and operator practices vary.'
                    ),
                },
            ],
            'footnotes': [
                '1 Forecasts and expectations are illustrative and based on material assumptions subject to change. Numbers shown are placeholder figures for layout demonstration.',
                '2 Assumes a leading accelerator vendor accounts for 75% of compute spend in each period, with 5% YoY growth past 2031.',
                '3 Assumes a power utilization effectiveness of 1.2 and a unit cost of $15M per megawatt of data center capacity.',
            ],
        },
    })
    return HttpResponse(_render('gsapp/insights_article.html', ctx, request))


def insights_podcast(request):
    ctx = _base_context(request, active_nav='Insights')
    ctx.update({
        'article': {
            'eyebrow': 'The Markets',
            'title': 'Crude Oil Drivers and the Path Through 2026',
            'date': 'May 8, 2026',
            'duration': '32 min',
            'image_tint': 'burnt',
            'host': {'name': 'Pat Placeholder', 'title': 'Markets Reporter'},
            'guest': {'name': 'Jordan Sample', 'title': 'Head of Commodities Research'},
            'summary': (
                'A wide-ranging conversation on the supply, demand, and '
                'geopolitical inputs shaping the path of crude oil markets '
                'through the back half of the year, with attention to '
                'OPEC+ behaviour, US shale economics, and demand '
                'elasticity in emerging markets.'
            ),
            'chapter_markers': [
                {'time': '0:00', 'label': 'Setup and the macro backdrop'},
                {'time': '5:42', 'label': 'Supply: OPEC+ discipline and shale response'},
                {'time': '13:15', 'label': 'Demand: emerging markets and aviation'},
                {'time': '21:00', 'label': 'Risk scenarios and the back half of the year'},
                {'time': '28:30', 'label': 'Listener questions'},
            ],
        },
    })
    return HttpResponse(_render('gsapp/insights_podcast.html', ctx, request))


def careers(request):
    ctx = _base_context(request, active_nav='Careers')
    ctx.update({
        'hero': {
            'eyebrow': 'Careers',
            'title': 'Pursue the Exceptional',
            'subtitle': (
                'Placeholder hero copy for a hypothetical careers landing '
                'page. Lorem ipsum dolor sit amet consectetur adipiscing '
                'elit sed do eiusmod tempor incididunt ut labore.'
            ),
            'cta_label': 'Find Your Place',
            'cta_url': '#find-your-place',
            'image_tint': 'navy',
        },
        'tabs': [
            {'label': 'Students', 'url': '#students', 'active': True},
            {'label': 'Open Roles', 'url': '#open-roles'},
        ],
        'culture_two_up': {
            'eyebrow': 'Culture',
            'title': 'Voices of the Firm',
            'body': (
                'Sample two-up section body. Lorem ipsum dolor sit amet, '
                'consectetur adipiscing elit. Duis aute irure dolor in '
                'reprehenderit in voluptate velit esse cillum dolore.'
            ),
            'cta': 'Discover Life at the Firm',
            'cta_url': _u('careers_life'),
            'image_tint': 'teal',
        },
        'featured_roles': [
            {'eyebrow': 'Engineering', 'title': 'Build the systems that move global markets',
             'body': 'From low-latency trading infrastructure to client platforms.', 'image_tint': 'purple'},
            {'eyebrow': 'Quant Research', 'title': 'Translate market structure into model and signal',
             'body': 'Cross-asset quantitative research and systematic strategy.', 'image_tint': 'navy'},
            {'eyebrow': 'Investment Banking', 'title': "Advise the world's most influential institutions",
             'body': 'Sector-deep teams across M&A, ECM, DCM, and structured finance.', 'image_tint': 'amber'},
            {'eyebrow': 'Asset Management', 'title': 'Manage capital across public and private markets',
             'body': 'Active strategies across equities, credit, alternatives.', 'image_tint': 'olive'},
        ],
        'path_tiles': [
            {'title': 'Match Your Skills', 'body': 'Find the right team for your background.'},
            {'title': 'Student Programs', 'body': 'Internship and full-time entry programs.'},
            {'title': 'Professional Programs', 'body': 'Mid-career and lateral hiring tracks.'},
            {'title': 'Feel Prepared', 'body': 'Interview prep and process expectations.'},
        ],
        'tagline_quote': (
            'Lorem ipsum dolor sit amet, consectetur adipiscing elit. '
            'Sed do eiusmod tempor incididunt ut labore et dolore magna.'
        ),
        'two_ups': [
            {
                'eyebrow': 'Who We Are',
                'title': 'United by Partnership, Client Service, Integrity, Excellence',
                'body': 'Four shared values that anchor the firm and define how we work together, with our clients, and in our communities.',
                'cta': 'Our Purpose and Values',
                'cta_url': _u('purpose'),
                'image_tint': 'brown',
            },
            {
                'eyebrow': 'Impact',
                'title': 'The Business of Impact',
                'body': 'We put people, ideas, and capital to work through impact-oriented programs across small business growth, community investment, and access to opportunity.',
                'cta': 'Review Our Initiatives',
                'cta_url': '#',
                'image_tint': 'teal',
                'reverse': True,
            },
            {
                'eyebrow': 'Belonging',
                'title': 'Diverse Teams Drive Stronger Results',
                'body': 'Our focus on building inclusive, diverse teams is central to our commercial performance and the quality of advice we deliver to clients.',
                'cta': 'Learn More',
                'cta_url': '#',
                'image_tint': 'mauve',
            },
        ],
        'our_firm_links': [
            {'title': 'Risk', 'body': 'Identifies, monitors, evaluates, and manages financial and non-financial risks across the firm.'},
            {'title': 'Asset Management', 'body': 'Provides investment management solutions across all major asset classes for institutional and individual clients.'},
            {'title': 'Operations', 'body': 'Enables every trade, product launch, market entry, and completed transaction across the global business.'},
            {'title': 'Engineering', 'body': "Envisions, builds, and deploys industry-leading systems that drive the firm's business and extend its boundaries."},
        ],
    })
    return HttpResponse(_render('gsapp/careers.html', ctx, request))


def careers_life(request):
    ctx = _base_context(request, active_nav='Careers')
    ctx.update({
        'page_eyebrow': 'Careers',
        'page_title': 'A Practice in Practice',
        'page_subtitle': (
            'Sample placeholder page subtitle. Lorem ipsum dolor sit amet, '
            'consectetur adipiscing elit. Sed do eiusmod tempor incididunt '
            'ut labore et dolore magna aliqua.'
        ),
        'two_ups': [
            {
                'eyebrow': 'Meet Our People',
                'title': 'Our People',
                'body': 'Colleagues share their experiences, what it is like to be part of the firm, and how they have contributed to and benefited from growth opportunities and mentorship.',
                'cta': 'Read Profiles',
                'image_tint': 'navy',
            },
            {
                'eyebrow': 'Inclusion',
                'title': 'Diversity and Inclusion',
                'body': 'Our focus on diversity and inclusion is critical to our commercial success and the quality of our work.',
                'cta': 'Learn More',
                'image_tint': 'purple',
                'reverse': True,
            },
            {
                'eyebrow': 'Wellbeing',
                'title': 'Supporting Success',
                'body': 'We provide top-tier benefits, from comprehensive healthcare options and crisis support to wellness programs and family-care resources.',
                'cta': 'Explore Benefits',
                'image_tint': 'teal',
            },
            {
                'eyebrow': 'Growth',
                'title': 'Maximizing Potential',
                'body': 'We develop programs and resources to support professional growth and unlock the potential of our people across every stage of their careers.',
                'cta': 'Career Development',
                'image_tint': 'amber',
                'reverse': True,
            },
        ],
        'alumni_two_up': {
            'eyebrow': 'Alumni',
            'title': 'A Strong and Active Alumni Network',
            'body': (
                'Our people remain a part of the firm long beyond their '
                'tenure, with a global alumni network connecting former '
                "colleagues to one another and to the firm's thought leadership."
            ),
            'cta': 'Explore the Network',
            'image_tint': 'brown',
        },
    })
    return HttpResponse(_render('gsapp/careers_life.html', ctx, request))


def purpose(request):
    ctx = _base_context(request, active_nav='Our Firm')
    ctx.update({
        'page_eyebrow': 'Our Firm',
        'page_title': 'Our Purpose',
        'page_subtitle': (
            'Sample placeholder subtitle. Lorem ipsum dolor sit amet, '
            'consectetur adipiscing elit, sed do eiusmod tempor '
            'incididunt ut labore et dolore magna aliqua.'
        ),
        'values': [
            {'title': 'Partnership',
             'body': 'Lorem ipsum dolor sit amet, consectetur adipiscing elit. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.'},
            {'title': 'Client Service',
             'body': 'Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident.'},
            {'title': 'Integrity',
             'body': 'Sunt in culpa qui officia deserunt mollit anim id est laborum. Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque.'},
            {'title': 'Excellence',
             'body': 'Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt.'},
        ],
        'principles_two_up': {
            'eyebrow': 'Defining the Firm',
            'title': 'Business Principles',
            'body': (
                'A set of foundational principles articulates what the firm '
                'stands for. Established decades ago, they remain the '
                "ground truth that shapes the firm's culture and decisions."
            ),
            'cta': 'Read the Principles',
            'image_tint': 'navy',
        },
        'ethics_links': [
            {'title': 'Code of Business Ethics and Conduct'},
            {'title': 'Report of the Business Standards Committee'},
            {'title': 'Business Standards Committee Impact Report'},
            {'title': 'Corporate Governance'},
        ],
        'discover_cards': [
            {'eyebrow': 'Heritage', 'title': 'Discover Our History',
             'body': 'From a single trading partnership to a global institution.', 'image_tint': 'brown'},
            {'eyebrow': 'Leadership', 'title': 'Meet Our People and Leaders',
             'body': "Profiles of leadership across the firm's businesses.", 'image_tint': 'olive'},
        ],
    })
    return HttpResponse(_render('gsapp/purpose.html', ctx, request))


def serve_css(request):
    """Serve the combined CSS body (tokens + fonts + components) inline."""
    return HttpResponse(_build_css(), content_type='text/css; charset=utf-8')


# ════════════════════════════════════════════════════════════════════════════
# URL CONF  (consumed by Django's include('gs_reference'))
# ════════════════════════════════════════════════════════════════════════════
# `app_name` enables `{% url 'gs_reference:home' %}` and `reverse('gs_reference:home')`
# to resolve regardless of the prefix the user mounts us at in PRISM's main urls.py.

app_name = 'gs_reference'

urlpatterns = [
    path('',                                home,             name='home'),
    path('what-we-do/',                     what_we_do,       name='what_we_do'),
    path('insights/',                       insights_list,    name='insights_list'),
    path('insights/article/',               insights_article, name='insights_article'),
    path('insights/podcast/',               insights_podcast, name='insights_podcast'),
    path('careers/',                        careers,          name='careers'),
    path('careers/life/',                   careers_life,     name='careers_life'),
    path('our-firm/purpose-and-values/',    purpose,          name='purpose'),
    path('static/gs.css',                   serve_css,        name='css'),
]
