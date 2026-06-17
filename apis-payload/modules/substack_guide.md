# Substack Newsletter Data

Script: `projects/apis/substack/substack.py`
API Pattern: `{subdomain}.substack.com/api/v1/{endpoint}`
Auth: None required for free posts; optional session cookie for paywalled content
Rate Limit: 1-2s delay between requests recommended
Data: `projects/apis/substack/data/`
Dependencies: `requests`


## Triggers

Use for: macro/rates/energy newsletter content, post-data-release commentary scans, topic deep dives across curated publications, bulk content pulls for knowledge base ingestion, publication discovery, specific author views (Politano, Peccatiello, Wang, Tooze, Scanlon), cross-category latest aggregation, markdown export for PRISM context modules.

Not for: real-time market data (use data APIs), structured economic data (use FRED/Treasury/EIA), prediction markets (use prediction_markets/), non-Substack institutional blogs (Liberty Street, Brookings, PIIE, CEPR), social media commentary.


## Data Catalog

### Publication Registry

47 curated publications across 8 categories. All subdomains verified via the archive API.

#### Macro (16)

| Subdomain | Name | Author |
|-----------|------|--------|
| apricitas | Apricitas Economics | Joseph Politano |
| themacrocompass | The Macro Compass | Alfonso Peccatiello |
| kyla | Kyla's Newsletter | Kyla Scanlon |
| adamtooze | Chartbook | Adam Tooze |
| netinterest | Net Interest | Marc Rubinstein |
| employamerica | Employ America | Employ America |
| conorsen | Conor Sen's Newsletter | Conor Sen |
| citrini | Citrini Research | Citrini |
| variantperception | Variant Perception Blog | VP Research |
| behindthebalancesheet | Behind the Balance Sheet | Stephen Clapham |
| paulomacro | PauloMacro | PauloMacro |
| michaelwgreen | Yes I Give a Fig | Michael Green |
| lordfed | Lord Fed's Gazette | Lord Fed |
| blindsquirrelmacro | Blind Squirrel Macro | The Blind Squirrel |
| globalmarkets | Global Markets | Karim Al-Mansour |
| dannydayan | Macro Musings by Danny D | Danny Dayan |

#### Rates / FX (7)

| Subdomain | Name | Author |
|-----------|------|--------|
| concoda | Concoda / Conks | Concoda |
| fedguy | FedGuy | Joseph Wang |
| fxmacro | fx:macro | FXMacroGuy |
| cubicanalytics | Cubic Analytics | Caleb Franzen |
| harkster | Harkster / Morning Hark | Harkster |
| macrotomicro | Macro-to-Micro | Samantha LaDuc |
| macromornings | Macro Mornings | Alessandro |

#### Commodities (3)

| Subdomain | Name | Author |
|-----------|------|--------|
| doomberg | Doomberg | Doomberg |
| alexanderstahel | The Commodity Compass | Alexander Stahel |
| bewater1 | Be Water | Be Water |

#### Equities (8)

| Subdomain | Name | Author |
|-----------|------|--------|
| thescienceofhitting | TSOH Investment Research | Alex Morris |
| invariant | Invariant | Devin LaSarre |
| valuesits | Value Situations | Conor Maguire |
| thebearcave | The Bear Cave | Edwin Dorsey |
| qualitycompounding | Compounding Quality | Compounding Quality |
| toffcap | ToffCap | ToffCap |
| tmtbreakout | TMT Breakout | TMT Breakout |
| guardianresearch | Guardian Research | Guardian Research |

#### Credit (4)

| Subdomain | Name | Author |
|-----------|------|--------|
| junkbondinvestor | Credit from Macro to Micro | Junk Bond Investor |
| debtserious | DEBT SERIOUS | DEBT SERIOUS |
| altgoesmainstream | Alt Goes Mainstream | Alt Goes Mainstream |
| lewisenterprises | Lewis Enterprises | Lewis Enterprises |

#### Tactical (5)

| Subdomain | Name | Author |
|-----------|------|--------|
| macrocharts | Macro Charts | Macro Charts |
| chartstorm | Weekly ChartStorm | Callum Thomas |
| ecoinometrics | Ecoinometrics | Ecoinometrics |
| thebeartrapsreport | The Bear Traps Report | Larry McDonald |
| capitalwars | Capital Wars | Capital Wars |

#### Crypto (1)

| Subdomain | Name | Author |
|-----------|------|--------|
| noelleacheson | Crypto is Macro Now | Noelle Acheson |

#### Thinkers (3)

| Subdomain | Name | Author |
|-----------|------|--------|
| aswathdamodaran | Musings on Markets | Aswath Damodaran |
| blackbullresearch | BlackBull Research | BlackBull Research |
| ashenden | Ashenden Finance | Ashenden |

### API Endpoints

#### /api/v1/archive

List posts from a publication, paginated. Returns array of post objects sorted by date.

| Parameter | Description |
|-----------|-------------|
| sort | "new" (default) or "top" |
| limit | Posts per page (max ~50) |
| offset | Pagination offset |

#### /api/v1/posts/{slug}

Single post with full HTML body. Paywall posts return truncated body only.

#### /api/v1/publication/search

Search across all Substack publications. May require browser session state -- use `browse` for reliable discovery.

| Parameter | Description |
|-----------|-------------|
| query | Search term |
| page | Page number (0-based) |
| limit | Results per page (max 100) |

#### /api/v1/category/public/{category_id}/all

Browse publications by Substack category. Finance=153, Business=54, Politics=44, Technology=11, Science=4.

### Post Fields (archive response)

| Field | Description |
|-------|-------------|
| id | Unique post ID |
| title | Post title |
| subtitle | Post subtitle/description |
| slug | URL slug (for fetching full post) |
| post_date | ISO 8601 publication date |
| canonical_url | Full URL |
| audience | "everyone", "only_paid", "only_free" |
| wordcount | Word count |
| reaction_count | Likes/hearts |
| comment_count | Comments |
| description | Short excerpt |
| truncated_body_text | First ~200 chars |
| body_html | Full HTML (single post endpoint only, free posts) |


## CLI Recipes

All commands support `--json` for structured output.

### Browse Publications

```bash
# List all 46 curated publications by category
python substack.py list-pubs
```

### Archive (Post Listings)

```bash
# Recent posts from a publication
python substack.py archive apricitas
python substack.py archive apricitas --limit 20
python substack.py archive apricitas --limit 10 --json
python substack.py archive apricitas --limit 20 --save
python substack.py archive fedguy --limit 30 --json
python substack.py archive themacrocompass --limit 15 --json
python substack.py archive concoda --limit 30 --json
python substack.py archive adamtooze --limit 20 --json
python substack.py archive doomberg --limit 10 --json
python substack.py archive kyla --limit 15 --json
python substack.py archive junkbondinvestor --limit 10 --json

# Pagination
python substack.py archive apricitas --limit 20 --offset 20 --json

# Sort by engagement
python substack.py archive apricitas --sort top --limit 10 --json
```

### Read Post (Full Content)

```bash
# Fetch single post with full body
python substack.py read-post apricitas some-post-slug
python substack.py read-post apricitas some-post-slug --json
python substack.py read-post apricitas some-post-slug --save
python substack.py read-post apricitas some-post-slug --save --json
python substack.py read-post fedguy some-post-slug --save --json
python substack.py read-post themacrocompass some-post-slug --json
python substack.py read-post adamtooze some-post-slug --max-chars 20000
python substack.py read-post concoda some-post-slug --save --json
```

### Search & Browse

```bash
# Search for publications across all of Substack
python substack.py search "macro economics"
python substack.py search "interest rates" --limit 20 --json
python substack.py search "fiscal deficit" --json
python substack.py search "energy markets" --json
python substack.py search "credit markets" --json

# Browse publications by Substack category
python substack.py browse --category 153 --json
python substack.py browse --category 54 --page 1 --json
python substack.py browse --category 44 --json
```

### Latest (Cross-Publication)

```bash
# Latest posts across all curated pubs
python substack.py latest --top 30
python substack.py latest --top 20 --json
python substack.py latest --per-pub 3 --top 30 --json

# Filter by category
python substack.py latest --categories macro --per-pub 5 --json
python substack.py latest --categories macro,rates_fx --per-pub 3 --top 30 --json
python substack.py latest --categories rates_fx --per-pub 5 --json
python substack.py latest --categories commodities --per-pub 5 --json
python substack.py latest --categories credit --per-pub 3 --json
python substack.py latest --categories equities --per-pub 3 --json
python substack.py latest --categories tactical --per-pub 3 --json
python substack.py latest --categories thinkers --per-pub 3 --json
```

### Bulk Pull

```bash
# Download archives from all curated publications
python substack.py pull --per-pub 20
python substack.py pull --per-pub 20 --json

# Category-specific pulls
python substack.py pull --categories macro --per-pub 15
python substack.py pull --categories rates_fx --per-pub 10
python substack.py pull --categories commodities --per-pub 10
python substack.py pull --categories credit --per-pub 10

# With full post bodies
python substack.py pull --categories macro --per-pub 10 --bodies
python substack.py pull --categories rates_fx --per-pub 10 --bodies
python substack.py pull --bodies --per-pub 5 --json
```

### Export & Metadata

```bash
# Export post(s) to markdown
python substack.py export-md apricitas --slug my-post-slug
python substack.py export-md apricitas --slug all
python substack.py export-md fedguy --slug all
python substack.py export-md themacrocompass --slug all
python substack.py export-md adamtooze --slug all

# Publication info
python substack.py pub-info apricitas
python substack.py pub-info apricitas --json
python substack.py pub-info fedguy --json
python substack.py pub-info doomberg --json

# Raw API query
python substack.py raw /archive --subdomain apricitas --params "limit=5,sort=new"
python substack.py raw /posts/my-slug --subdomain fedguy
```

### Common Flags

| Flag | Effect | Applies to |
|------|--------|------------|
| `--json` | JSON output | All commands |
| `--save` | Save to data/ directory | archive, read-post |
| `--limit N` | Posts per page | archive, search |
| `--offset N` | Pagination offset | archive |
| `--sort new\|top` | Sort order | archive |
| `--per-pub N` | Posts per publication | latest, pull |
| `--top N` | Total posts to show | latest |
| `--categories` | Comma-separated categories | latest, pull |
| `--bodies` | Fetch full post bodies | pull |
| `--max-chars N` | Max body chars to display | read-post |
| `--slug` | Post slug or "all" | export-md |
| `--category N` | Substack category ID | browse |


## Python Recipes

### Archive & Posts

```python
from substack import get_archive, get_post, html_to_text, PUBLICATIONS

# Recent posts from a publication
# Returns: list of post dicts with title, subtitle, slug, post_date,
#          wordcount, reaction_count, comment_count, audience, canonical_url
posts = get_archive("apricitas", limit=10)
posts = get_archive("fedguy", limit=20)
posts = get_archive("themacrocompass", limit=15, sort="top")
posts = get_archive("concoda", limit=30, offset=0)
posts = get_archive("adamtooze", limit=20)
posts = get_archive("doomberg", limit=10)

# Full post with body
# Returns: post dict with body_html field (free posts only)
post = get_post("apricitas", "the-employment-situation")
body = html_to_text(post["body_html"])

post = get_post("fedguy", "some-post-slug")
post = get_post("themacrocompass", "some-post-slug")
```

### Search & Browse

```python
from substack import search_publications, browse_category

# Search across all Substack
# Returns: publication objects with name, author, subscriber count, subdomain
results = search_publications("macro economics", limit=10)
results = search_publications("interest rates", limit=20)
results = search_publications("fiscal deficit", limit=10)

# Browse by category
# Returns: {"publications": [...], "more": bool}
finance = browse_category(category_id=153, page=0)
business = browse_category(category_id=54, page=0)
```

### Publication Registry

```python
from substack import PUBLICATIONS, _PUB_INDEX, _all_pub_ids

# All categories and publications
for cat, pubs in PUBLICATIONS.items():
    print(f"{cat}: {len(pubs)} pubs")

# Lookup a specific publication
info = _PUB_INDEX["apricitas"]
# -> {"id": "apricitas", "name": "Apricitas Economics",
#     "author": "Joseph Politano", "category": "macro"}

# All subdomain IDs
all_ids = _all_pub_ids()
```

### Bulk Operations

```python
from substack import get_archive, get_post, PUBLICATIONS

# Latest from all macro pubs
macro_posts = []
for pub in PUBLICATIONS["macro"]:
    posts = get_archive(pub["id"], limit=3)
    if posts:
        for p in posts:
            p["_pub"] = pub["name"]
        macro_posts.extend(posts)
macro_posts.sort(key=lambda p: p.get("post_date", ""), reverse=True)

# Latest from rates pubs
rates_posts = []
for pub in PUBLICATIONS["rates_fx"]:
    posts = get_archive(pub["id"], limit=5)
    if posts:
        rates_posts.extend(posts)

# Latest from commodities pubs
commod_posts = []
for pub in PUBLICATIONS["commodities"]:
    posts = get_archive(pub["id"], limit=5)
    if posts:
        commod_posts.extend(posts)
```

### Subprocess (via CLI)

```python
import subprocess, json

def substack_query(command, args_str=""):
    cmd = f"python projects/apis/substack/substack.py {command} {args_str} --json"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return json.loads(result.stdout) if result.stdout else None

posts = substack_query("archive", "apricitas --limit 5")
latest = substack_query("latest", "--top 20 --per-pub 3")
results = substack_query("search", '"fiscal deficit"')
macro = substack_query("latest", "--categories macro --per-pub 3")
rates = substack_query("latest", "--categories rates_fx --per-pub 3")
```


## Composite Recipes

### Post-Release Commentary Scan

```bash
python substack.py latest --categories macro,rates_fx --per-pub 3 --top 30 --json
```

PRISM receives: latest 3 posts from each macro + rates publication, sorted by recency, with title, subtitle, post_date, wordcount, reaction_count, slug. Filter by date for 24-72h reaction window around a data release.

### Topic Deep Dive

```bash
python substack.py archive fedguy --limit 30 --json
python substack.py archive concoda --limit 30 --json
python substack.py archive apricitas --limit 30 --json
python substack.py read-post fedguy {relevant-slug} --save --json
python substack.py read-post concoda {relevant-slug} --save --json
```

PRISM receives: 30-post archives from targeted publications with titles/dates/slugs for topic scanning, then full post bodies for selected articles.

### Cross-Category Latest

```bash
python substack.py latest --categories macro --per-pub 5 --json
python substack.py latest --categories rates_fx --per-pub 5 --json
python substack.py latest --categories commodities --per-pub 5 --json
python substack.py latest --categories credit --per-pub 3 --json
python substack.py latest --categories equities --per-pub 3 --json
```

PRISM receives: category-level latest posts showing what each segment of the commentary ecosystem is focused on.

### Bulk Knowledge Base Refresh

```bash
python substack.py pull --categories macro --per-pub 15 --bodies
python substack.py pull --categories rates_fx --per-pub 15 --bodies
python substack.py export-md apricitas --slug all
python substack.py export-md fedguy --slug all
python substack.py export-md themacrocompass --slug all
```

PRISM receives: full post content downloaded and saved as JSON + markdown for macro and rates publications, then exported as clean markdown for context module ingestion.

### Author-Specific Deep Read

```bash
python substack.py archive apricitas --limit 20 --json
python substack.py read-post apricitas {slug-1} --save --json
python substack.py read-post apricitas {slug-2} --save --json
python substack.py read-post apricitas {slug-3} --save --json
```

PRISM receives: archive listing for title/date scanning, then full body content for 2-3 selected posts from a single author.

### Publication Discovery

```bash
python substack.py search "macro economics" --json
python substack.py browse --category 153 --json
python substack.py pub-info {new-subdomain} --json
python substack.py archive {new-subdomain} --limit 5 --json
```

PRISM receives: search results with subscriber counts, category browse for finance publications, metadata for a candidate publication, sample archive to assess relevance.


## Cross-Source Recipes

### Commentary + Data Release

```bash
python substack.py latest --categories macro --per-pub 3 --json
python projects/apis/fred/fred_client.py series PAYEMS --json
```

PRISM receives: latest macro commentary + actual employment data. Commentary interpretation vs headline numbers.

### Rates Commentary + Funding Data

```bash
python substack.py archive fedguy --limit 5 --json
python projects/apis/nyfed/nyfed.py funding-snapshot --json
```

PRISM receives: Joseph Wang's latest rates/plumbing commentary + actual overnight rates and RRP data. Narrative vs observed funding conditions.

### Commentary + Positioning

```bash
python substack.py latest --categories macro,rates_fx --per-pub 3 --json
python projects/apis/cftc/cftc.py rates --json
```

PRISM receives: what writers are saying + how speculators are positioned. Narrative direction vs actual bets.

### Commentary + Prediction Markets

```bash
python substack.py latest --categories macro --per-pub 3 --json
python projects/apis/prediction_markets/prediction_markets.py scrape --preset fed_policy --json
```

PRISM receives: macro commentary themes + market-implied probabilities. Qualitative narrative vs quantitative odds.

### Energy Commentary + Supply Data

```bash
python substack.py archive doomberg --limit 10 --json
python substack.py archive alexanderstahel --limit 10 --json
python projects/apis/eia/eia.py petroleum --json
```

PRISM receives: energy newsletter commentary + actual petroleum supply/inventory data.

### Commentary + Public Attention

```bash
python substack.py latest --categories macro --per-pub 3 --json
python projects/apis/wikipedia/wikipedia.py fear-gauge --json
```

PRISM receives: what sophisticated commentators are writing about + what the general public is searching for. Expert vs grassroots attention.

### Credit Commentary + Bank Health

```bash
python substack.py latest --categories credit --per-pub 3 --json
python projects/apis/fdic/fdic.py recipe bank-stress --json
```

PRISM receives: credit market commentary + bank-level stress indicators. Narrative on credit conditions vs observed bank health.

### Commentary + Sanctions

```bash
python substack.py latest --categories macro --per-pub 3 --json
python projects/apis/ofac/ofac.py geo-focus --json
```

PRISM receives: macro commentary themes + SDN designation distribution. What writers say about geopolitical risk vs actual sanctions activity.


## Auth (Paywalled Content)

Free posts return full `body_html` without auth. Paywalled posts (`audience: "only_paid"`) return only `truncated_body_text` (~200 chars) unless an authenticated session cookie for that domain is provided.

### Cookie Domain Scoping

Substack cookies are domain-scoped. There are two types of publications:

1. **substack.com subdomain pubs** (e.g. `apricitas.substack.com`, `maroonmacro.substack.com`) -- ONE cookie on `substack.com` covers all of them.
2. **Custom-domain pubs** (e.g. Michael Green at `yesigiveafig.com`) -- each needs its OWN cookie because substack.com cookies do not transmit cross-domain.

The registry marks custom-domain pubs with a `base_url` field. Currently:
- `michaelwgreen` -> `yesigiveafig.com`
- `blindsquirrelmacro` -> `blindsquirrelmacro.com`

### Cookie Storage

Cookies come from multiple sources, merged together. Higher priority overrides lower for the same domain:

1. `_EMBEDDED_COOKIES` constant in `substack.py` (baseline, baked in)
2. `.substack_cookie` legacy single-cookie file (substack.com scope)
3. `data/.substack_cookies.json` per-domain JSON dict (what `set-cookie` writes)
4. `SUBSTACK_SID` env var (substack.com scope)
5. `SUBSTACK_COOKIE` env var (substack.com scope)

The embedded default lives directly in the code near the top of `substack.py`:

```python
_EMBEDDED_COOKIES = {
    "substack.com": "s%3A...",
}
```

Edit that dict to add/rotate cookies, or use `set-cookie` to layer runtime overrides without touching code.

### Getting Your Cookie

For substack.com pubs:
1. Log into `substack.com` in Chrome (with your paid subscriptions)
2. DevTools -> Application -> Cookies -> `substack.com`
3. Copy the `substack.sid` value

For a custom-domain pub (e.g. `yesigiveafig.com`):
1. Visit that domain in Chrome while logged in
2. DevTools -> Application -> Cookies -> `www.yesigiveafig.com`
3. Copy the `substack.sid` value from THAT domain (different value than substack.com)

### CLI Auth Commands

```bash
# Set substack.com cookie (covers all <pub>.substack.com pubs)
python substack.py set-cookie "s%3A..."

# Set cookie for a custom-domain pub
python substack.py set-cookie "s%3A..." --domain yesigiveafig.com

# Check all configured cookies
python substack.py auth-status
python substack.py auth-status --json

# Clear a specific or all cookies
python substack.py clear-cookie --domain yesigiveafig.com
python substack.py clear-cookie
```

Auth only unlocks paywalled content for publications you personally pay for -- there is no universal paywall bypass.


## Setup

1. `pip install requests`
2. Test: `python substack.py list-pubs`
3. API test: `python substack.py archive apricitas --limit 3`
4. Optional: configure auth for paywalled content (see above)


## Architecture

```
substack.py
  Constants       PUBLICATIONS (8 categories, 47 pubs), SUBSTACK_CATEGORIES,
                  _PUB_INDEX (subdomain lookup), HEADERS, REQUEST_DELAY
  Auth            _load_cookie_map, _cookie_for_url, _get_auth_headers, has_auth()
                  Per-domain cookies via .substack_cookies.json + env var overrides
  HTTP            _api_url (honors base_url override for custom-domain pubs),
                  _get() with retry/backoff on 429/5xx, auth headers per URL
  API Functions   get_archive, get_post, search_publications, browse_category
  HTML            _HTMLStripper, html_to_text()
  Data Storage    _save_archive, _save_post, _save_post_markdown
  Commands (13)   list-pubs, archive, read-post, search, browse, latest,
                  pull, export-md, pub-info, auth-status, set-cookie,
                  clear-cookie, raw
  Interactive     13-item menu -> interactive wrappers with prompts
  Argparse        13 subcommands with --json, --save, --limit, etc.
```

API endpoints:
```
{subdomain}.substack.com/api/v1/archive?sort=new&offset=N&limit=M
{subdomain}.substack.com/api/v1/posts/{slug}
substack.com/api/v1/publication/search?query=X&page=N&limit=M
substack.com/api/v1/category/public/{category_id}/all?page=N
```

Data layout:
```
projects/apis/substack/data/
  {subdomain}/
    archive.json
    posts/
      {slug}.json
      {slug}.md
```
