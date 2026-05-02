#!/usr/bin/env python3
"""
Substack Newsletter Client
===========================

Programmatic access to Substack's undocumented JSON API for pulling macro/rates/energy
newsletter content. Covers the curated set of finance-relevant Substacks that represent
the sell-side-to-Substack migration: the commentary layer that wraps around data.

This is not an RSS aggregator -- it uses Substack's internal JSON API which returns
structured post metadata, full HTML bodies, engagement metrics, and publication info.
RSS is available as a secondary channel but the JSON API is richer.

API Details
-----------
Base Pattern: {subdomain}.substack.com/api/v1/{endpoint}
Auth:         None required (undocumented public endpoints)
Rate Limit:   Unofficial; throttles after sustained rapid requests. 1-2s delay recommended.
Format:       JSON

Endpoints
---------
/api/v1/archive?sort=new&offset=N&limit=M
    List posts from a publication. Returns array of post objects. Max limit ~50.
    Fields: id, title, subtitle, slug, post_date, canonical_url, audience,
            comment_count, reaction_count, wordcount, description, cover_image,
            truncated_body_text

/api/v1/posts/{slug}
    Single post with full HTML body. Returns post object with body_html field.
    Paywall posts return truncated body only.

/api/v1/publication/search?query=X&page=N&limit=M
    Search publications across all of Substack. Returns list of publication objects
    with subscriber counts, categories, descriptions.

/api/v1/category/public/{category_id}/all?page=N
    Browse publications by category. Finance=153, Business=54, etc.

Dependencies
------------
pip install requests

Dual-Mode CLI
-------------
Running without arguments launches the interactive menu.
Running with a subcommand runs non-interactively for scripting and automation.
"""

import argparse
import json
import sys
import time
import os
import csv
import re
from datetime import datetime, timezone
from html.parser import HTMLParser

try:
    import requests
except ImportError:
    print("Missing dependency: pip install requests")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

REQUEST_DELAY = 1.0

# ── Auth ──────────────────────────────────────────────────────────────────────
#
# Paywalled posts return truncated_body_text only (~200 chars) without auth.
# With a valid session cookie from a browser where you have paid subscriptions,
# the API returns full body_html for those publications.
#
# IMPORTANT: Substack cookies are domain-scoped. The .substack.com cookie
# covers all *.substack.com subdomains (apricitas, fedguy, maroonmacro, etc.)
# but does NOT transmit to publications using custom domains (e.g., Michael
# Green uses yesigiveafig.com). Those pubs need their own per-domain cookie.
#
# Cookie sources, lowest -> highest priority:
#   1. _EMBEDDED_COOKIES (baked into this file, below)
#   2. .substack_cookie (legacy single-cookie file, substack.com-scoped)
#   3. .substack_cookies.json (per-domain JSON dict)
#   4. SUBSTACK_SID env var (substack.com-scoped)
#   5. SUBSTACK_COOKIE env var (substack.com-scoped)
#
# Higher-priority sources overwrite lower-priority for the same domain.

from urllib.parse import urlparse

_COOKIE_FILE = os.path.join(DATA_DIR, ".substack_cookie")
_COOKIES_FILE = os.path.join(DATA_DIR, ".substack_cookies.json")

# Embedded default cookies. These are baked into the code as a convenience
# baseline so the script authenticates out-of-the-box. They are the LOWEST
# priority source -- any value in .substack_cookies.json, the legacy
# .substack_cookie file, or env vars will override these.
#
# To add a cookie for a custom-domain pub (e.g. yesigiveafig.com for
# michaelwgreen), visit that domain in Chrome, grab the substack.sid from
# DevTools -> Application -> Cookies -> <custom-domain>, and add it here.
_EMBEDDED_COOKIES = {
    "substack.com": "s%3Av2vsnwkzsVkzgtCKVs-efFVJTC-3NGq_.cjAHIkwOX%2F15Cg00oTON4RiV2PAFS8w3xTbh4cotBus",
}


def _load_cookie_map():
    """Return dict of {domain: sid_value}. Priority (low -> high):
    embedded defaults -> legacy .substack_cookie -> .substack_cookies.json
    -> SUBSTACK_SID env -> SUBSTACK_COOKIE env.
    """
    cookies = dict(_EMBEDDED_COOKIES)

    if os.path.exists(_COOKIE_FILE):
        with open(_COOKIE_FILE) as f:
            raw = f.read().strip()
        if raw:
            if raw.startswith("substack.sid="):
                raw = raw[len("substack.sid="):]
            cookies["substack.com"] = raw

    if os.path.exists(_COOKIES_FILE):
        try:
            with open(_COOKIES_FILE) as f:
                cookies.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    env_sid = os.environ.get("SUBSTACK_SID", "").strip()
    if env_sid:
        cookies["substack.com"] = env_sid

    env_cookie = os.environ.get("SUBSTACK_COOKIE", "").strip()
    if env_cookie:
        if env_cookie.startswith("substack.sid="):
            env_cookie = env_cookie[len("substack.sid="):].split(";")[0].strip()
        cookies["substack.com"] = env_cookie

    return cookies


def _save_cookie_map(cookies):
    _ensure_dir(DATA_DIR)
    with open(_COOKIES_FILE, "w") as f:
        json.dump(cookies, f, indent=2)


def _registrable_domain(host):
    """Return the eTLD+1 for cookie scoping. Substack-aware:
    - *.substack.com -> substack.com
    - www.example.com -> example.com
    - example.com -> example.com
    """
    if not host:
        return ""
    host = host.lower().split(":")[0]
    if host.endswith(".substack.com") or host == "substack.com":
        return "substack.com"
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def _cookie_for_url(url):
    """Pick the best-matching cookie for a given URL."""
    cookies = _load_cookie_map()
    if not cookies:
        return None
    host = urlparse(url).hostname or ""
    domain = _registrable_domain(host)
    if domain in cookies:
        return cookies[domain]
    if host in cookies:
        return cookies[host]
    return None


def _get_auth_headers(url=None):
    headers = dict(HEADERS)
    if url:
        sid = _cookie_for_url(url)
        if sid:
            headers["Cookie"] = f"substack.sid={sid}"
    return headers


def has_auth(url=None):
    if url:
        return _cookie_for_url(url) is not None
    return bool(_load_cookie_map())

SUBSTACK_CATEGORIES = {
    153: "finance",
    54: "business",
    44: "politics",
    11: "technology",
    4: "science",
}

# ── Curated Publications ─────────────────────────────────────────────────────
#
# The macro/rates/energy/equity/credit commentary layer. These are the
# publications PRISM monitors for narrative context around data releases and
# market moves. All subdomains verified via the archive API.
#
# Each entry: id (subdomain), display name, author.
# Optional "base_url" overrides for publications using custom domains where
# the {subdomain}.substack.com API returns HTML redirects instead of JSON.

PUBLICATIONS = {
    "macro": [
        {"id": "apricitas", "name": "Apricitas Economics", "author": "Joseph Politano"},
        {"id": "themacrocompass", "name": "The Macro Compass", "author": "Alfonso Peccatiello"},
        {"id": "kyla", "name": "Kyla's Newsletter", "author": "Kyla Scanlon"},
        {"id": "adamtooze", "name": "Chartbook", "author": "Adam Tooze"},
        {"id": "netinterest", "name": "Net Interest", "author": "Marc Rubinstein"},
        {"id": "employamerica", "name": "Employ America", "author": "Employ America"},
        {"id": "conorsen", "name": "Conor Sen's Newsletter", "author": "Conor Sen"},
        {"id": "citrini", "name": "Citrini Research", "author": "Citrini"},
        {"id": "variantperception", "name": "Variant Perception Blog", "author": "VP Research"},
        {"id": "behindthebalancesheet", "name": "Behind the Balance Sheet", "author": "Stephen Clapham"},
        {"id": "paulomacro", "name": "PauloMacro", "author": "PauloMacro"},
        {"id": "michaelwgreen", "name": "Yes I Give a Fig", "author": "Michael Green", "base_url": "https://www.yesigiveafig.com"},
        {"id": "lordfed", "name": "Lord Fed's Gazette", "author": "Lord Fed"},
        {"id": "blindsquirrelmacro", "name": "Blind Squirrel Macro", "author": "The Blind Squirrel", "base_url": "https://www.blindsquirrelmacro.com"},
        {"id": "globalmarkets", "name": "Global Markets", "author": "Karim Al-Mansour"},
        {"id": "dannydayan", "name": "Macro Musings by Danny D", "author": "Danny Dayan"},
    ],
    "rates_fx": [
        {"id": "concoda", "name": "Concoda / Conks", "author": "Concoda"},
        {"id": "fedguy", "name": "FedGuy", "author": "Joseph Wang"},
        {"id": "fxmacro", "name": "fx:macro", "author": "FXMacroGuy"},
        {"id": "cubicanalytics", "name": "Cubic Analytics", "author": "Caleb Franzen"},
        {"id": "harkster", "name": "Harkster / Morning Hark", "author": "Harkster"},
        {"id": "macrotomicro", "name": "Macro-to-Micro", "author": "Samantha LaDuc"},
        {"id": "macromornings", "name": "Macro Mornings", "author": "Alessandro"},
    ],
    "commodities": [
        {"id": "doomberg", "name": "Doomberg", "author": "Doomberg"},
        {"id": "alexanderstahel", "name": "The Commodity Compass", "author": "Alexander Stahel"},
        {"id": "bewater1", "name": "Be Water", "author": "Be Water"},
    ],
    "equities": [
        {"id": "thescienceofhitting", "name": "TSOH Investment Research", "author": "Alex Morris"},
        {"id": "invariant", "name": "Invariant", "author": "Devin LaSarre"},
        {"id": "valuesits", "name": "Value Situations", "author": "Conor Maguire"},
        {"id": "thebearcave", "name": "The Bear Cave", "author": "Edwin Dorsey"},
        {"id": "qualitycompounding", "name": "Compounding Quality", "author": "Compounding Quality"},
        {"id": "toffcap", "name": "ToffCap", "author": "ToffCap"},
        {"id": "tmtbreakout", "name": "TMT Breakout", "author": "TMT Breakout"},
        {"id": "guardianresearch", "name": "Guardian Research", "author": "Guardian Research"},
    ],
    "credit": [
        {"id": "junkbondinvestor", "name": "Credit from Macro to Micro", "author": "Junk Bond Investor"},
        {"id": "debtserious", "name": "DEBT SERIOUS", "author": "DEBT SERIOUS"},
        {"id": "altgoesmainstream", "name": "Alt Goes Mainstream", "author": "Alt Goes Mainstream"},
        {"id": "lewisenterprises", "name": "Lewis Enterprises", "author": "Lewis Enterprises"},
    ],
    "tactical": [
        {"id": "macrocharts", "name": "Macro Charts", "author": "Macro Charts"},
        {"id": "chartstorm", "name": "Weekly ChartStorm", "author": "Callum Thomas"},
        {"id": "ecoinometrics", "name": "Ecoinometrics", "author": "Ecoinometrics"},
        {"id": "thebeartrapsreport", "name": "The Bear Traps Report", "author": "Larry McDonald"},
        {"id": "capitalwars", "name": "Capital Wars", "author": "Capital Wars"},
    ],
    "crypto": [
        {"id": "noelleacheson", "name": "Crypto is Macro Now", "author": "Noelle Acheson"},
    ],
    "thinkers": [
        {"id": "aswathdamodaran", "name": "Musings on Markets", "author": "Aswath Damodaran"},
        {"id": "blackbullresearch", "name": "BlackBull Research", "author": "BlackBull Research"},
        {"id": "ashenden", "name": "Ashenden Finance", "author": "Ashenden"},
    ],
}

_PUB_INDEX = {}
for _cat, _pubs in PUBLICATIONS.items():
    for _p in _pubs:
        _PUB_INDEX[_p["id"]] = {**_p, "category": _cat}


def _all_pub_ids():
    return list(_PUB_INDEX.keys())


# ── API Layer ─────────────────────────────────────────────────────────────────

def _api_url(subdomain, path):
    pub = _PUB_INDEX.get(subdomain, {})
    base = pub.get("base_url", f"https://{subdomain}.substack.com")
    return f"{base}/api/v1{path}"


def _get(url, params=None, retries=2):
    headers = _get_auth_headers(url)
    for attempt in range(retries + 1):
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(url, headers=headers, params=params, timeout=30)
            if resp.status_code == 429:
                wait = min(10, 2 ** (attempt + 1))
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.HTTPError as e:
            if attempt < retries and e.response.status_code in (429, 500, 502, 503):
                time.sleep(2 ** (attempt + 1))
                continue
            raise
        except requests.exceptions.RequestException as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            raise
    return None


def get_archive(subdomain, limit=12, offset=0, sort="new"):
    """Fetch post listing from a publication's archive."""
    url = _api_url(subdomain, "/archive")
    return _get(url, {"sort": sort, "limit": limit, "offset": offset})


def get_post(subdomain, slug):
    """Fetch a single post with full body HTML."""
    url = _api_url(subdomain, f"/posts/{slug}")
    return _get(url)


def search_publications(query, page=0, limit=10):
    """Search for Substack publications by keyword.

    Note: this endpoint requires browser-level session state and may return
    empty results from headless requests. Use browse_category() or the curated
    PUBLICATIONS registry for reliable discovery.
    """
    url = "https://substack.com/api/v1/publication/search"
    result = _get(url, {"query": query, "page": page, "limit": limit})
    if isinstance(result, dict) and not result.get("results") and not result.get("publications"):
        return {"results": [], "_note": "Search may require browser session. Use 'browse' (category browse) for discovery."}
    return result


def browse_category(category_id=153, page=0):
    """Browse publications by Substack category (153=finance)."""
    url = f"https://substack.com/api/v1/category/public/{category_id}/all"
    return _get(url, {"page": page})


# ── HTML-to-Text ──────────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    """Minimal HTML-to-text converter. Preserves paragraph breaks and list items."""

    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
        self._in_li = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True
        elif tag in ("p", "div", "br", "h1", "h2", "h3", "h4", "blockquote"):
            self._text.append("\n")
        elif tag == "li":
            self._text.append("\n  - ")
            self._in_li = True
        elif tag == "a":
            pass

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False
        elif tag in ("p", "div", "h1", "h2", "h3", "h4", "blockquote"):
            self._text.append("\n")
        elif tag == "li":
            self._in_li = False

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        raw = "".join(self._text)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def html_to_text(html):
    if not html:
        return ""
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


# ── Display Helpers ───────────────────────────────────────────────────────────

def _format_date(date_str):
    if not date_str:
        return "?"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str[:10] if len(date_str) >= 10 else date_str


def _print_posts(posts, show_pub=False):
    if not posts:
        print("  No posts found.")
        return
    for i, p in enumerate(posts, 1):
        date = _format_date(p.get("post_date"))
        title = p.get("title", "(untitled)")
        audience = p.get("audience", "everyone")
        paywall = " [PAID]" if audience == "only_paid" else ""
        words = p.get("wordcount") or 0
        reactions = p.get("reaction_count") or 0
        comments = p.get("comment_count") or 0

        pub_prefix = ""
        if show_pub:
            pub_name = p.get("_pub_name", "")
            if not pub_name:
                bylines = p.get("publishedBylines") or []
                if bylines:
                    pub_name = bylines[0].get("name", "")
            if pub_name:
                pub_prefix = f"[{pub_name}] "

        print(f"  {i:3d}. {date}  {pub_prefix}{title}{paywall}")
        subtitle = p.get("subtitle", "")
        if subtitle:
            print(f"       {subtitle[:100]}")
        print(f"       {words:,} words | {reactions} reactions | {comments} comments | slug: {p.get('slug', '?')}")
        print()


def _print_post_full(post, max_chars=5000):
    title = post.get("title", "(untitled)")
    subtitle = post.get("subtitle", "")
    date = _format_date(post.get("post_date"))
    audience = post.get("audience", "everyone")
    words = post.get("wordcount") or 0
    url = post.get("canonical_url", "")

    print(f"\n{'=' * 76}")
    print(f"  {title}")
    if subtitle:
        print(f"  {subtitle}")
    print(f"  {date} | {words:,} words | {audience}")
    if url:
        print(f"  {url}")
    print(f"{'=' * 76}\n")

    body_html = post.get("body_html", "")
    if body_html:
        text = html_to_text(body_html)
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n\n  [...truncated at {max_chars:,} chars, full post has {len(text):,}...]"
        print(text)
    else:
        trunc = post.get("truncated_body_text", "")
        if trunc:
            print(trunc)
            print("\n  [Full body not available -- post may be paywalled]")
        else:
            print("  [No body content available]")
    print()


def _print_publications(pubs):
    if not pubs:
        print("  No publications found.")
        return
    for i, p in enumerate(pubs, 1):
        name = p.get("name", "(unknown)")
        author = p.get("author_name", "") or p.get("author_bio", "")[:60]
        subs = p.get("public_user_count") or p.get("subscriber_count") or "?"
        subdomain = p.get("subdomain", "?")
        tier = p.get("tier", "")
        print(f"  {i:3d}. {name}")
        print(f"       by {author} | {subs} subscribers | tier: {tier}")
        print(f"       subdomain: {subdomain} | {subdomain}.substack.com")
        print()


# ── Data Persistence ──────────────────────────────────────────────────────────

def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


def _save_json(data, path):
    _ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    return path


def _save_archive(subdomain, posts):
    path = os.path.join(DATA_DIR, subdomain, "archive.json")
    return _save_json(posts, path)


def _save_post(subdomain, slug, post):
    path = os.path.join(DATA_DIR, subdomain, "posts", f"{slug}.json")
    return _save_json(post, path)


def _save_post_markdown(subdomain, slug, post):
    title = post.get("title", "(untitled)")
    subtitle = post.get("subtitle", "")
    date = _format_date(post.get("post_date"))
    url = post.get("canonical_url", "")
    body_html = post.get("body_html", "")
    body_text = html_to_text(body_html) if body_html else post.get("truncated_body_text", "")

    md = f"# {title}\n\n"
    if subtitle:
        md += f"*{subtitle}*\n\n"
    md += f"**Date:** {date}  \n"
    if url:
        md += f"**URL:** {url}  \n"
    md += f"**Words:** {post.get('wordcount', '?')}  \n"
    md += f"**Audience:** {post.get('audience', '?')}  \n\n"
    md += "---\n\n"
    md += body_text + "\n"

    path = os.path.join(DATA_DIR, subdomain, "posts", f"{slug}.md")
    _ensure_dir(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(md)
    return path


# ── Interactive Commands ──────────────────────────────────────────────────────

def _cmd_list_pubs():
    print()
    for cat, pubs in PUBLICATIONS.items():
        print(f"  {cat.upper()}")
        print(f"  {'─' * 70}")
        for p in pubs:
            print(f"    {p['id']:25s} {p['name']:35s} {p['author']}")
        print()
    print(f"  Total: {len(_PUB_INDEX)} curated publications")


def _cmd_archive():
    print("\n  Enter publication subdomain (or number from curated list):")
    _cmd_list_pubs()
    sub = input("\n  Subdomain: ").strip()
    if not sub:
        return
    if sub in _PUB_INDEX:
        print(f"  -> {_PUB_INDEX[sub]['name']}")

    limit = input("  Posts to fetch [12]: ").strip()
    limit = int(limit) if limit.isdigit() else 12

    print(f"  Fetching archive from {sub}.substack.com...")
    try:
        posts = get_archive(sub, limit=limit)
        if posts:
            _print_posts(posts)
            save = input("  Save archive? (y/n) [n]: ").strip().lower()
            if save == "y":
                path = _save_archive(sub, posts)
                print(f"  Saved to {path}")
        else:
            print("  No posts returned.")
    except Exception as e:
        print(f"  Error: {e}")


def _cmd_read_post():
    sub = input("\n  Subdomain: ").strip()
    if not sub:
        return
    slug = input("  Post slug: ").strip()
    if not slug:
        return

    print(f"  Fetching {sub}.substack.com/p/{slug}...")
    try:
        post = get_post(sub, slug)
        if post:
            _print_post_full(post)
            save = input("  Save post? (j=JSON, m=markdown, b=both, n=no) [n]: ").strip().lower()
            if save in ("j", "b"):
                path = _save_post(sub, slug, post)
                print(f"  Saved JSON: {path}")
            if save in ("m", "b"):
                path = _save_post_markdown(sub, slug, post)
                print(f"  Saved markdown: {path}")
        else:
            print("  No post returned.")
    except Exception as e:
        print(f"  Error: {e}")


def _cmd_search():
    query = input("\n  Search query: ").strip()
    if not query:
        return
    print(f"  Searching Substack for '{query}'...")
    try:
        results = search_publications(query, limit=15)
        if isinstance(results, list):
            _print_publications(results)
        elif isinstance(results, dict):
            pubs = results.get("publications", results.get("results", []))
            if not pubs and results.get("_note"):
                print(f"  {results['_note']}")
                print("  Try option 5 (Browse by category) instead.")
            else:
                _print_publications(pubs)
        else:
            print(f"  Unexpected response type: {type(results)}")
    except Exception as e:
        print(f"  Error: {e}")


def _cmd_latest():
    cats = input("\n  Categories (comma-sep, or 'all') [all]: ").strip().lower() or "all"
    limit_per_pub = input("  Posts per publication [5]: ").strip()
    limit_per_pub = int(limit_per_pub) if limit_per_pub.isdigit() else 5
    top_n = input("  Show top N overall [30]: ").strip()
    top_n = int(top_n) if top_n.isdigit() else 30

    if cats == "all":
        pub_ids = _all_pub_ids()
    else:
        pub_ids = []
        for c in cats.split(","):
            c = c.strip()
            if c in PUBLICATIONS:
                pub_ids.extend(p["id"] for p in PUBLICATIONS[c])

    if not pub_ids:
        print("  No publications matched.")
        return

    all_posts = []
    total = len(pub_ids)
    print(f"\n  Fetching archives from {total} publications...")
    for i, pid in enumerate(pub_ids, 1):
        name = _PUB_INDEX.get(pid, {}).get("name", pid)
        print(f"  [{i}/{total}] {name}...", end="", flush=True)
        try:
            posts = get_archive(pid, limit=limit_per_pub)
            if posts:
                for p in posts:
                    p["_pub_name"] = name
                    p["_pub_id"] = pid
                all_posts.extend(posts)
                print(f" {len(posts)} posts")
            else:
                print(" 0 posts")
        except Exception as e:
            print(f" error: {e}")

    all_posts.sort(key=lambda p: p.get("post_date", ""), reverse=True)
    all_posts = all_posts[:top_n]

    print(f"\n  Latest {len(all_posts)} posts across {total} publications:\n")
    _print_posts(all_posts, show_pub=True)


def _cmd_pull_all():
    cats = input("\n  Categories (comma-sep, or 'all') [all]: ").strip().lower() or "all"
    limit_per_pub = input("  Posts per publication [20]: ").strip()
    limit_per_pub = int(limit_per_pub) if limit_per_pub.isdigit() else 20
    fetch_bodies = input("  Fetch full post bodies? (y/n) [n]: ").strip().lower() == "y"

    if cats == "all":
        pub_ids = _all_pub_ids()
    else:
        pub_ids = []
        for c in cats.split(","):
            c = c.strip()
            if c in PUBLICATIONS:
                pub_ids.extend(p["id"] for p in PUBLICATIONS[c])

    if not pub_ids:
        print("  No publications matched.")
        return

    total = len(pub_ids)
    print(f"\n  Pulling from {total} publications, {limit_per_pub} posts each...")
    total_posts = 0

    for i, pid in enumerate(pub_ids, 1):
        name = _PUB_INDEX.get(pid, {}).get("name", pid)
        print(f"\n  [{i}/{total}] {name} ({pid}.substack.com)")

        try:
            posts = get_archive(pid, limit=limit_per_pub)
            if not posts:
                print(f"    0 posts found")
                continue

            _save_archive(pid, posts)
            print(f"    {len(posts)} posts archived")

            if fetch_bodies:
                for j, p in enumerate(posts, 1):
                    slug = p.get("slug")
                    if not slug:
                        continue
                    print(f"    [{j}/{len(posts)}] {slug}...", end="", flush=True)
                    try:
                        full = get_post(pid, slug)
                        if full:
                            _save_post(pid, slug, full)
                            _save_post_markdown(pid, slug, full)
                            print(" saved")
                        else:
                            print(" empty")
                    except Exception as e:
                        print(f" error: {e}")
                    total_posts += 1
            else:
                total_posts += len(posts)

        except Exception as e:
            print(f"    Error: {e}")

    print(f"\n  Done. {total_posts} posts across {total} publications.")
    print(f"  Data saved to: {DATA_DIR}")


def _cmd_export_markdown():
    sub = input("\n  Subdomain: ").strip()
    if not sub:
        return
    slug = input("  Post slug (or 'all' for saved archive): ").strip()
    if not slug:
        return

    if slug == "all":
        archive_path = os.path.join(DATA_DIR, sub, "archive.json")
        if not os.path.exists(archive_path):
            print(f"  No saved archive for {sub}. Run 'pull' first.")
            return
        with open(archive_path) as f:
            posts = json.load(f)
        print(f"  Exporting {len(posts)} posts from saved archive...")
        for i, p in enumerate(posts, 1):
            s = p.get("slug")
            if not s:
                continue
            post_json = os.path.join(DATA_DIR, sub, "posts", f"{s}.json")
            if os.path.exists(post_json):
                with open(post_json) as f:
                    full = json.load(f)
                path = _save_post_markdown(sub, s, full)
                print(f"  [{i}/{len(posts)}] {path}")
            else:
                path = _save_post_markdown(sub, s, p)
                print(f"  [{i}/{len(posts)}] {path} (archive metadata only)")
        print("  Done.")
    else:
        post_json = os.path.join(DATA_DIR, sub, "posts", f"{slug}.json")
        if os.path.exists(post_json):
            with open(post_json) as f:
                post = json.load(f)
        else:
            print(f"  No saved post. Fetching from API...")
            post = get_post(sub, slug)
        if post:
            path = _save_post_markdown(sub, slug, post)
            print(f"  Saved: {path}")
        else:
            print("  No post data.")


def _cmd_browse_category():
    print("\n  Substack categories:")
    for cid, cname in SUBSTACK_CATEGORIES.items():
        print(f"    {cid}: {cname}")
    cat = input("\n  Category ID [153]: ").strip()
    cat = int(cat) if cat.isdigit() else 153
    page = input("  Page [0]: ").strip()
    page = int(page) if page.isdigit() else 0

    print(f"  Browsing category {cat} page {page}...")
    try:
        result = browse_category(cat, page)
        if isinstance(result, dict):
            pubs = result.get("publications", [])
            _print_publications(pubs)
            has_more = result.get("more", False)
            if has_more:
                print(f"  More available. Next page: {page + 1}")
        elif isinstance(result, list):
            _print_publications(result)
    except Exception as e:
        print(f"  Error: {e}")


def _cmd_pub_info():
    sub = input("\n  Subdomain: ").strip()
    if not sub:
        return
    print(f"  Fetching info for {sub}.substack.com...")
    try:
        posts = get_archive(sub, limit=1)
        if posts and len(posts) > 0:
            p = posts[0]
            bylines = p.get("publishedBylines", [])
            pub = bylines[0].get("publicationUsers", [{}])[0].get("publication", {}) if bylines else {}
            print(f"\n  Publication: {pub.get('name', sub)}")
            print(f"  Author:      {pub.get('author_name', '?')}")
            print(f"  Subscribers: {pub.get('public_user_count', '?')}")
            print(f"  Created:     {pub.get('created_at', '?')[:10] if pub.get('created_at') else '?'}")
            print(f"  Language:    {pub.get('language', '?')}")
            print(f"  Paid:        {pub.get('payments_state', '?')}")
            print(f"  Subdomain:   {pub.get('subdomain', sub)}")
            base = pub.get("base_url") or pub.get("custom_domain") or f"https://{sub}.substack.com"
            print(f"  Base URL:    {base}")
            print(f"  Latest post: {p.get('title', '?')} ({_format_date(p.get('post_date'))})")
        else:
            print("  Could not retrieve publication info.")
    except Exception as e:
        print(f"  Error: {e}")


def _cmd_auth_status():
    cookies = _load_cookie_map()
    print(f"\n  Auth cookies configured: {len(cookies)}")
    if cookies:
        for domain, sid in cookies.items():
            masked = sid[:15] + "..." if len(sid) > 15 else sid
            print(f"    {domain:30s} {masked}")
        print()
        print("  Paywalled posts return full body for paid subscriptions on these domains.")
        print("  Note: *.substack.com subdomains are covered by the 'substack.com' cookie.")
        print("        Pubs with custom domains (e.g. yesigiveafig.com) need separate cookies.")
    else:
        print("  Paywalled posts return truncated_body_text only (~200 chars).")
        print()
        print("  To enable:")
        print("    python substack.py set-cookie <sid>                # covers all substack.com pubs")
        print("    python substack.py set-cookie <sid> --domain X.com # per custom domain")
        print()
        print("  To get your SID:")
        print("    1. Log into substack.com (or the custom domain) in Chrome")
        print("    2. DevTools -> Application -> Cookies -> <domain>")
        print("    3. Copy the 'substack.sid' value")


def _cmd_set_cookie():
    print("\n  Domain for this cookie:")
    print("    - 'substack.com' (default) covers all <pub>.substack.com pubs")
    print("    - for custom domains, use the eTLD+1 (e.g. 'yesigiveafig.com')")
    domain = input("\n  Domain [substack.com]: ").strip() or "substack.com"
    print(f"\n  Paste the substack.sid cookie value for {domain} (from browser DevTools):")
    sid = input("  SID: ").strip()
    if not sid:
        print("  Cancelled.")
        return
    cookies = _load_cookie_map()
    cookies[domain] = sid
    _save_cookie_map(cookies)
    print(f"  Saved cookie for {domain} -> {_COOKIES_FILE}")


def _cmd_clear_cookies():
    print("\n  Clear which cookie?")
    cookies = _load_cookie_map()
    if not cookies:
        print("  No cookies configured.")
        return
    for i, domain in enumerate(cookies.keys(), 1):
        print(f"    {i}. {domain}")
    print(f"    {len(cookies) + 1}. ALL")
    choice = input("\n  Choice: ").strip()
    if not choice.isdigit():
        return
    choice = int(choice)
    keys = list(cookies.keys())
    if choice == len(cookies) + 1:
        cookies = {}
    elif 1 <= choice <= len(keys):
        del cookies[keys[choice - 1]]
    else:
        print("  Invalid.")
        return
    _save_cookie_map(cookies)
    print("  Updated.")


def _cmd_raw_query():
    sub = input("\n  Subdomain (leave empty for substack.com): ").strip()
    path = input("  API path (e.g. /archive, /posts/my-slug): ").strip()
    if not path:
        return
    if not path.startswith("/"):
        path = "/" + path

    params_str = input("  Query params as key=val,key=val (or empty): ").strip()
    params = {}
    if params_str:
        for kv in params_str.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                params[k.strip()] = v.strip()

    if sub:
        url = _api_url(sub, path)
    else:
        url = f"https://substack.com/api/v1{path}"

    print(f"  GET {url}")
    if params:
        print(f"  Params: {params}")
    try:
        result = _get(url, params)
        print(json.dumps(result, indent=2, default=str)[:5000])
    except Exception as e:
        print(f"  Error: {e}")


COMMAND_MAP = {
    "1":  _cmd_list_pubs,
    "2":  _cmd_archive,
    "3":  _cmd_read_post,
    "4":  _cmd_search,
    "5":  _cmd_browse_category,
    "10": _cmd_latest,
    "11": _cmd_pull_all,
    "20": _cmd_export_markdown,
    "30": _cmd_pub_info,
    "40": _cmd_auth_status,
    "41": _cmd_set_cookie,
    "42": _cmd_clear_cookies,
    "90": _cmd_raw_query,
}


def interactive_loop():
    while True:
        print("\n" + "=" * 76)
        print("  Substack Newsletter Client")
        print("=" * 76)
        print("\n  BROWSE:")
        print("    1.  List curated publications")
        print("    2.  Archive -- recent posts from a publication")
        print("    3.  Read post -- full content by slug")
        print("    4.  Search -- find Substack publications")
        print("    5.  Browse -- browse by Substack category")
        print()
        print("  AGGREGATE:")
        print("    10. Latest -- recent posts across all curated pubs")
        print("    11. Pull all -- bulk download from curated pubs")
        print()
        print("  EXPORT:")
        print("    20. Export post(s) to markdown")
        print()
        print("  TOOLS:")
        print("    30. Publication info")
        print("    40. Auth status")
        print("    41. Set cookie (for paywalled content)")
        print("    42. Clear cookie(s)")
        print("    90. Raw API query")
        print()
        print("    q.  Quit")

        choice = input("\n  Choice: ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("  Bye.")
            break
        if choice in COMMAND_MAP:
            try:
                COMMAND_MAP[choice]()
            except KeyboardInterrupt:
                print("\n  (interrupted)")
            except Exception as e:
                print(f"  [!] Error: {e}")
        else:
            print("  Invalid choice.")


# ── Non-interactive CLI ───────────────────────────────────────────────────────

def build_argparse():
    parser = argparse.ArgumentParser(
        description="Substack Newsletter Client -- pull macro/rates/energy commentary",
        epilog="Run without args for interactive menu. Use subcommands for scripting.",
    )
    sub = parser.add_subparsers(dest="command", help="Subcommand")

    sub.add_parser("list-pubs", help="List curated publications")

    p = sub.add_parser("archive", help="Fetch post archive from a publication")
    p.add_argument("subdomain", help="Publication subdomain (e.g. apricitas)")
    p.add_argument("--limit", type=int, default=12, help="Number of posts")
    p.add_argument("--offset", type=int, default=0, help="Offset for pagination")
    p.add_argument("--sort", default="new", choices=["new", "top"], help="Sort order")
    p.add_argument("--save", action="store_true", help="Save archive to data/")
    p.add_argument("--json", action="store_true", help="Output raw JSON")

    p = sub.add_parser("read-post", help="Fetch a single post with full body")
    p.add_argument("subdomain", help="Publication subdomain")
    p.add_argument("slug", help="Post slug")
    p.add_argument("--save", action="store_true", help="Save post JSON + markdown")
    p.add_argument("--json", action="store_true", help="Output raw JSON")
    p.add_argument("--max-chars", type=int, default=10000, help="Max body chars to display")

    p = sub.add_parser("search", help="Search for Substack publications")
    p.add_argument("query", help="Search query")
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--limit", type=int, default=15)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("browse", help="Browse publications by Substack category")
    p.add_argument("--category", type=int, default=153, help="Category ID (153=finance)")
    p.add_argument("--page", type=int, default=0)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("latest", help="Latest posts across curated publications")
    p.add_argument("--categories", default="all", help="Comma-separated categories or 'all'")
    p.add_argument("--per-pub", type=int, default=5, help="Posts per publication")
    p.add_argument("--top", type=int, default=30, help="Total posts to show")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("pull", help="Bulk download from curated publications")
    p.add_argument("--categories", default="all", help="Comma-separated categories or 'all'")
    p.add_argument("--per-pub", type=int, default=20, help="Posts per publication")
    p.add_argument("--bodies", action="store_true", help="Also fetch full post bodies")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("export-md", help="Export post(s) to markdown")
    p.add_argument("subdomain", help="Publication subdomain")
    p.add_argument("--slug", default="all", help="Post slug or 'all' for saved archive")

    p = sub.add_parser("pub-info", help="Get publication metadata")
    p.add_argument("subdomain", help="Publication subdomain")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("auth-status", help="Show all configured auth cookies")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("set-cookie", help="Save a substack.sid cookie for paywalled content")
    p.add_argument("sid", help="The substack.sid cookie value from browser DevTools")
    p.add_argument("--domain", default="substack.com",
                   help="Cookie domain (default: substack.com, covers all *.substack.com pubs). "
                        "Use custom domain (e.g. 'yesigiveafig.com') for pubs that redirect off substack.com.")

    p = sub.add_parser("clear-cookie", help="Remove a stored cookie")
    p.add_argument("--domain", help="Cookie domain to clear (omit for all)")

    p = sub.add_parser("raw", help="Raw API query")
    p.add_argument("path", help="API path (e.g. /archive)")
    p.add_argument("--subdomain", default="", help="Publication subdomain (empty = substack.com)")
    p.add_argument("--params", default="", help="Query params as key=val,key=val")

    return parser


def _ni_output_json(data):
    print(json.dumps(data, indent=2, default=str))


def _resolve_pub_ids(categories_str):
    if categories_str == "all":
        return _all_pub_ids()
    pub_ids = []
    for c in categories_str.split(","):
        c = c.strip()
        if c in PUBLICATIONS:
            pub_ids.extend(p["id"] for p in PUBLICATIONS[c])
    return pub_ids


def run_noninteractive(args):
    cmd = args.command

    if cmd == "list-pubs":
        _cmd_list_pubs()

    elif cmd == "archive":
        posts = get_archive(args.subdomain, limit=args.limit, offset=args.offset, sort=args.sort)
        if args.json:
            _ni_output_json(posts)
        else:
            _print_posts(posts or [])
        if args.save and posts:
            path = _save_archive(args.subdomain, posts)
            print(f"  Saved: {path}")

    elif cmd == "read-post":
        post = get_post(args.subdomain, args.slug)
        if args.json:
            _ni_output_json(post)
        elif post:
            _print_post_full(post, max_chars=args.max_chars)
        else:
            print("  No post returned.")
        if args.save and post:
            p1 = _save_post(args.subdomain, args.slug, post)
            p2 = _save_post_markdown(args.subdomain, args.slug, post)
            print(f"  Saved: {p1}")
            print(f"  Saved: {p2}")

    elif cmd == "search":
        results = search_publications(args.query, page=args.page, limit=args.limit)
        if args.json:
            _ni_output_json(results)
        else:
            if isinstance(results, list):
                _print_publications(results)
            elif isinstance(results, dict):
                pubs = results.get("publications", results.get("results", []))
                _print_publications(pubs)

    elif cmd == "browse":
        result = browse_category(args.category, page=args.page)
        if args.json:
            _ni_output_json(result)
        else:
            if isinstance(result, dict):
                _print_publications(result.get("publications", []))
            elif isinstance(result, list):
                _print_publications(result)

    elif cmd == "latest":
        pub_ids = _resolve_pub_ids(args.categories)
        if not pub_ids:
            print("  No publications matched.")
            return

        all_posts = []
        total = len(pub_ids)
        for i, pid in enumerate(pub_ids, 1):
            name = _PUB_INDEX.get(pid, {}).get("name", pid)
            print(f"  [{i}/{total}] {name}...", end="", flush=True)
            try:
                posts = get_archive(pid, limit=args.per_pub)
                if posts:
                    for p in posts:
                        p["_pub_name"] = name
                        p["_pub_id"] = pid
                    all_posts.extend(posts)
                    print(f" {len(posts)} posts")
                else:
                    print(" 0 posts")
            except Exception as e:
                print(f" error: {e}")

        all_posts.sort(key=lambda p: p.get("post_date", ""), reverse=True)
        all_posts = all_posts[:args.top]

        if args.json:
            _ni_output_json(all_posts)
        else:
            print(f"\n  Latest {len(all_posts)} posts:\n")
            _print_posts(all_posts, show_pub=True)

    elif cmd == "pull":
        pub_ids = _resolve_pub_ids(args.categories)
        if not pub_ids:
            print("  No publications matched.")
            return

        total = len(pub_ids)
        total_posts = 0
        print(f"  Pulling from {total} publications, {args.per_pub} posts each...")

        for i, pid in enumerate(pub_ids, 1):
            name = _PUB_INDEX.get(pid, {}).get("name", pid)
            print(f"\n  [{i}/{total}] {name} ({pid}.substack.com)")

            try:
                posts = get_archive(pid, limit=args.per_pub)
                if not posts:
                    print(f"    0 posts found")
                    continue

                _save_archive(pid, posts)
                print(f"    {len(posts)} posts archived")

                if args.bodies:
                    for j, p in enumerate(posts, 1):
                        slug = p.get("slug")
                        if not slug:
                            continue
                        print(f"    [{j}/{len(posts)}] {slug}...", end="", flush=True)
                        try:
                            full = get_post(pid, slug)
                            if full:
                                _save_post(pid, slug, full)
                                _save_post_markdown(pid, slug, full)
                                print(" saved")
                            else:
                                print(" empty")
                        except Exception as e:
                            print(f" error: {e}")
                        total_posts += 1
                else:
                    total_posts += len(posts)
            except Exception as e:
                print(f"    Error: {e}")

        print(f"\n  Done. {total_posts} posts across {total} publications.")
        print(f"  Data: {DATA_DIR}")

    elif cmd == "export-md":
        if args.slug == "all":
            archive_path = os.path.join(DATA_DIR, args.subdomain, "archive.json")
            if not os.path.exists(archive_path):
                print(f"  No saved archive for {args.subdomain}. Run 'pull' first.")
                return
            with open(archive_path) as f:
                posts = json.load(f)
            for i, p in enumerate(posts, 1):
                s = p.get("slug")
                if not s:
                    continue
                post_json = os.path.join(DATA_DIR, args.subdomain, "posts", f"{s}.json")
                if os.path.exists(post_json):
                    with open(post_json) as f:
                        full = json.load(f)
                    path = _save_post_markdown(args.subdomain, s, full)
                else:
                    path = _save_post_markdown(args.subdomain, s, p)
                print(f"  [{i}/{len(posts)}] {path}")
        else:
            post_json = os.path.join(DATA_DIR, args.subdomain, "posts", f"{args.slug}.json")
            if os.path.exists(post_json):
                with open(post_json) as f:
                    post = json.load(f)
            else:
                post = get_post(args.subdomain, args.slug)
            if post:
                path = _save_post_markdown(args.subdomain, args.slug, post)
                print(f"  Saved: {path}")

    elif cmd == "pub-info":
        posts = get_archive(args.subdomain, limit=1)
        if args.json:
            _ni_output_json(posts)
            return
        if posts and len(posts) > 0:
            p = posts[0]
            bylines = p.get("publishedBylines", [])
            pub = bylines[0].get("publicationUsers", [{}])[0].get("publication", {}) if bylines else {}
            print(f"\n  Publication: {pub.get('name', args.subdomain)}")
            print(f"  Author:      {pub.get('author_name', '?')}")
            print(f"  Subscribers: {pub.get('public_user_count', '?')}")
            base = pub.get("base_url") or f"https://{args.subdomain}.substack.com"
            print(f"  Base URL:    {base}")
            print(f"  Latest:      {p.get('title', '?')} ({_format_date(p.get('post_date'))})")
        else:
            print("  Could not retrieve publication info.")

    elif cmd == "auth-status":
        cookies = _load_cookie_map()
        if getattr(args, 'json', False):
            masked = {d: (s[:10] + "...") for d, s in cookies.items()}
            _ni_output_json({
                "configured_domains": list(cookies.keys()),
                "cookies": masked,
                "cookies_file": _COOKIES_FILE,
            })
        else:
            print(f"  Configured cookies: {len(cookies)}")
            for domain, sid in cookies.items():
                print(f"    {domain:30s} {sid[:15]}...")
            if not cookies:
                print("  Set via: set-cookie <sid> [--domain <domain>]")

    elif cmd == "set-cookie":
        cookies = _load_cookie_map()
        cookies[args.domain] = args.sid
        _save_cookie_map(cookies)
        print(f"  Saved cookie for '{args.domain}' -> {_COOKIES_FILE}")

    elif cmd == "clear-cookie":
        cookies = _load_cookie_map()
        if args.domain:
            if args.domain in cookies:
                del cookies[args.domain]
                _save_cookie_map(cookies)
                print(f"  Cleared cookie for '{args.domain}'")
            else:
                print(f"  No cookie for '{args.domain}'")
        else:
            _save_cookie_map({})
            print("  Cleared all cookies")

    elif cmd == "raw":
        params = {}
        if args.params:
            for kv in args.params.split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    params[k.strip()] = v.strip()
        if args.subdomain:
            url = _api_url(args.subdomain, args.path if args.path.startswith("/") else "/" + args.path)
        else:
            url = f"https://substack.com/api/v1{args.path if args.path.startswith('/') else '/' + args.path}"
        result = _get(url, params)
        _ni_output_json(result)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = build_argparse()
    args = parser.parse_args()
    if args.command:
        run_noninteractive(args)
    else:
        print("\n  Substack Newsletter Client")
        print("  ==========================")
        print(f"  API Pattern: {{subdomain}}.substack.com/api/v1/...")
        print(f"  Curated publications: {len(_PUB_INDEX)} across {len(PUBLICATIONS)} categories.")
        print(f"  Data directory: {DATA_DIR}")
        auth_status = "YES (paywalled content available)" if has_auth() else "NO (free posts only)"
        print(f"  Auth: {auth_status}")
        interactive_loop()


if __name__ == "__main__":
    main()
