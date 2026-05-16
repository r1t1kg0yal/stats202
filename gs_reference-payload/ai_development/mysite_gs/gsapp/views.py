"""View functions for the GS-reference mock.

Each view passes a small dict of placeholder content into a template.
The placeholder content uses lorem-ipsum-style prose and PRISM-themed
naming (e.g. 'Macro Daily Brief' rather than real GS deal names) per
the design DNA spec §12.2 (this mock is NOT a copy of gs.com content).
"""
from django.shortcuts import render


NAV_ITEMS = [
    {"label": "What We Do", "url": "/what-we-do/"},
    {"label": "Insights", "url": "/insights/"},
    {"label": "Our Firm", "url": "/our-firm/purpose-and-values/"},
    {"label": "Careers", "url": "/careers/"},
]


def _base_context(active_nav=None):
    return {
        "nav_items": NAV_ITEMS,
        "active_nav": active_nav,
    }


def home(request):
    ctx = _base_context()
    ctx.update({
        "hero": {
            "eyebrow": "AI in Focus",
            "title": "The Trillion-Dollar Question",
            "subtitle": (
                "Tracking how the assumptions behind AI infrastructure spend "
                "shape the next decade of capital allocation across compute, "
                "data centers, and power."
            ),
            "cta_label": "Read the Analysis",
            "cta_url": "/insights/article/",
            "image_tint": "navy",
        },
        "tabs": [
            {"label": "Stay Informed", "url": "#stay-informed", "active": True},
            {"label": "The Firm in Action", "url": "#the-firm-in-action"},
        ],
        "deal_spotlights": [
            {
                "eyebrow": "Deal Spotlight",
                "title": "Acme Industries' $1.1B IPO",
                "body": (
                    "Strategy advised on Acme Industries' initial public "
                    "offering, a leading designer of mission-critical "
                    "components engineered for performance in extreme "
                    "environments."
                ),
                "cta": "See the Deal",
                "image_tint": "amber",
            },
            {
                "eyebrow": "Deal Spotlight",
                "title": "Northstar Logistics $10.5B Acquisition",
                "body": (
                    "Lead financial advisor to Northstar Logistics on its "
                    "acquisition of a regional storage and distribution "
                    "operator with assets across 14 metro areas."
                ),
                "cta": "See the Deal",
                "image_tint": "teal",
            },
        ],
        "what_we_do_cards": [
            {
                "eyebrow": "Investment Banking",
                "title": "Mergers & Acquisitions",
                "body": (
                    "Strategic advisory across the full M&A lifecycle for "
                    "the most complex cross-border transactions."
                ),
                "image_tint": "navy",
            },
            {
                "eyebrow": "Capital Markets",
                "title": "Equity Capital Solutions",
                "body": (
                    "Underwriting, syndication, and capital structuring "
                    "expertise across IPOs, follow-ons, and converts."
                ),
                "image_tint": "purple",
            },
            {
                "eyebrow": "Trading",
                "title": "FICC and Equities",
                "body": (
                    "Market-making and risk intermediation across rates, "
                    "credit, FX, commodities, equities, and derivatives."
                ),
                "image_tint": "burnt",
            },
            {
                "eyebrow": "Asset Management",
                "title": "Multi-Asset Solutions",
                "body": (
                    "Custom portfolio construction across public and "
                    "private markets for institutional and individual clients."
                ),
                "image_tint": "olive",
            },
        ],
        "insights_two_up": {
            "eyebrow": "Our Thinking",
            "title": "Insights on Financial Markets and the Global Economy",
            "body": (
                "Analysis and perspectives from our research, strategy, and "
                "investment teams, calibrated for institutional decision-makers "
                "navigating regime shifts, policy uncertainty, and dispersion."
            ),
            "cta": "All Insights",
            "cta_url": "/insights/",
            "image_tint": "mauve",
        },
        "careers_two_up": {
            "eyebrow": "Careers",
            "title": "Practice, Mentorship, Mastery",
            "body": (
                "Sample placeholder copy describing a hypothetical career "
                "track at a hypothetical firm. Lorem ipsum dolor sit amet, "
                "consectetur adipiscing elit, sed do eiusmod tempor."
            ),
            "cta": "Explore Careers",
            "cta_url": "/careers/",
            "image_tint": "teal",
        },
        "stats": [
            {"numeral": "46K+", "caption": "People around the world", "footnote_n": 1},
            {"numeral": "1M+", "caption": "External applications received last year", "footnote_n": 1},
            {"numeral": "95%+", "caption": "Clients give the firm top ratings of expertise", "footnote_n": 2},
        ],
        "our_firm_two_up": {
            "eyebrow": "Our Firm",
            "title": "We Aspire to Be the World's Most Exceptional Financial Institution",
            "body": (
                "Built on the principles of partnership, client service, "
                "integrity, and excellence, with a 150-year heritage of "
                "advising the world's most influential institutions."
            ),
            "cta": "Discover Our Purpose",
            "cta_url": "/our-firm/purpose-and-values/",
            "image_tint": "brown",
        },
        "footnotes": [
            "1 Headcount and external applicants as of fictional reference year. Placeholder figure for layout demonstration only.",
            "2 Biennial client and stakeholder survey. Data shown is illustrative and does not reflect any actual survey result.",
        ],
    })
    return render(request, "gsapp/home.html", ctx)


def what_we_do(request):
    ctx = _base_context(active_nav="What We Do")
    ctx.update({
        "page_eyebrow": "What We Do",
        "page_title": "Our Businesses",
        "page_subtitle": (
            "We deliver advisory, financing, market-making, and asset "
            "management services to the world's most influential institutions, "
            "corporations, governments, and individuals."
        ),
        "pillars": [
            {
                "id": "global-banking",
                "label": "Global Banking & Markets",
                "active": True,
            },
            {
                "id": "asset-wealth",
                "label": "Asset & Wealth Management",
            },
            {
                "id": "platform",
                "label": "Platform Solutions",
            },
        ],
        "pillar_sections": [
            {
                "id": "global-banking",
                "eyebrow": "Global Banking & Markets",
                "title": "Investment Banking",
                "body": (
                    "We serve the most influential corporations and institutions "
                    "with strategic advisory, financing, and capital structuring "
                    "across the full deal lifecycle."
                ),
                "links": [
                    {
                        "label": "Mergers & Acquisitions",
                        "body": (
                            "Cross-border M&A advisory anchored by sector "
                            "depth and execution rigour, partnering with "
                            "leadership through every stage of the process."
                        ),
                    },
                    {
                        "label": "Capital Solutions",
                        "body": (
                            "End-to-end underwriting across equity, debt, and "
                            "structured products, leveraging the firm's network "
                            "to source and deliver bespoke capital structures."
                        ),
                    },
                ],
            },
            {
                "id": "asset-wealth",
                "eyebrow": "Asset & Wealth Management",
                "title": "Asset Management",
                "body": (
                    "Investment management across public and private markets "
                    "for institutional, intermediary, and individual clients."
                ),
                "links": [
                    {
                        "label": "Equity",
                        "body": (
                            "Active fundamental and quantitative strategies "
                            "across emerging and developed markets."
                        ),
                    },
                    {
                        "label": "Fixed Income",
                        "body": (
                            "Single-sector, multi-sector, and regional credit "
                            "and rates strategies across the public-credit "
                            "universe."
                        ),
                    },
                    {
                        "label": "Liquidity Solutions",
                        "body": (
                            "Highly liquid short-duration strategies across "
                            "government and high-grade corporate instruments."
                        ),
                    },
                    {
                        "label": "Alternatives",
                        "body": (
                            "Private equity, growth equity, private credit, "
                            "real estate, infrastructure, and hedge funds."
                        ),
                    },
                ],
            },
            {
                "id": "platform",
                "eyebrow": "Platform Solutions",
                "title": "Transaction Banking",
                "body": (
                    "Cash management, treasury, and embedded financial "
                    "infrastructure for corporates and platform partners."
                ),
                "links": [
                    {
                        "label": "Treasury Services",
                        "body": (
                            "Multi-currency cash management with API-first "
                            "integration into corporate treasury workflows."
                        ),
                    },
                ],
            },
        ],
    })
    return render(request, "gsapp/what_we_do.html", ctx)


def insights_list(request):
    ctx = _base_context(active_nav="Insights")
    ctx.update({
        "page_eyebrow": "Insights",
        "page_title": "Analysis from Across the Firm",
        "page_subtitle": (
            "Perspectives on the global economy, markets, and policy from "
            "our research, strategy, and investment teams."
        ),
        "featured": {
            "eyebrow": "Artificial Intelligence",
            "title": "Tracking Trillions: The Assumptions Shaping the AI Build-Out",
            "date": "May 1, 2026",
            "image_tint": "navy",
            "url": "/insights/article/",
        },
        "latest": [
            {
                "eyebrow": "The Markets",
                "title": "Crude Oil Drivers and the Path Through 2026",
                "format": "Podcast",
                "date": "May 8, 2026",
                "image_tint": "burnt",
                "url": "/insights/podcast/",
            },
            {
                "eyebrow": "Energy",
                "title": "Could the Power Crunch Accelerate the Electrification Shift",
                "format": "Article",
                "date": "May 5, 2026",
                "image_tint": "olive",
                "url": "/insights/article/",
            },
            {
                "eyebrow": "Exchanges",
                "title": "How a New Fed Chair Could Reshape Policy",
                "format": "Podcast",
                "date": "Apr 28, 2026",
                "image_tint": "purple",
                "url": "/insights/podcast/",
            },
        ],
        "in_focus_eyebrow": "In Focus: Artificial Intelligence",
        "in_focus_cards": [
            {
                "eyebrow": "Markets",
                "title": "How AI Is Changing Quantitative Investing",
                "format": "Podcast",
                "date": "Apr 22, 2026",
                "image_tint": "mauve",
            },
            {
                "eyebrow": "Macro",
                "title": "AI Capex and the Productivity Question",
                "format": "Article",
                "date": "Apr 15, 2026",
                "image_tint": "teal",
            },
            {
                "eyebrow": "Equities",
                "title": "Sectoral Dispersion in the AI Beneficiaries Trade",
                "format": "Article",
                "date": "Apr 10, 2026",
                "image_tint": "navy",
            },
            {
                "eyebrow": "Credit",
                "title": "Funding Models for Hyperscaler Buildouts",
                "format": "Article",
                "date": "Apr 03, 2026",
                "image_tint": "amber",
            },
        ],
    })
    return render(request, "gsapp/insights_list.html", ctx)


def insights_article(request):
    ctx = _base_context(active_nav="Insights")
    ctx.update({
        "article": {
            "eyebrow": "Artificial Intelligence",
            "title": "Tracking Trillions: The Assumptions Shaping the AI Build-Out",
            "date": "May 1, 2026",
            "read_time": "12 min read",
            "image_tint": "navy",
            "authors": [
                {"name": "Ada Fictional", "title": "Co-Head, Global Institute"},
                {"name": "Ben Placeholder", "title": "Vice President, Global Institute"},
            ],
            "intro": (
                "The capital expenditure debate is usually framed as a "
                "demand-side question — will adoption justify the spend — "
                "but the size of the investment itself is not a single, "
                "fixed number."
            ),
            "exec_summary_body": (
                "Estimates rest on a small set of assumptions about how the "
                "infrastructure itself is built and renewed. Four assumptions "
                "are most impactful in determining the scale of the build-out:"
            ),
            "numbered_points": [
                "The economic useful life of compute silicon, where small shifts in replacement cadence move cumulative spend by hundreds of billions.",
                "The cost and complexity of next-generation data centers, which are rising as workloads push power density higher and system integration deeper.",
                "The chip and architecture mix, whose impact depends on whether compute demand is elastic (reshaping margins) or inelastic (reshaping totals).",
                "Elongation from power, labor, and equipment bottlenecks, which in stress scenarios can feed back into demand-side doubt.",
            ],
            "sections": [
                {
                    "heading": "Framing the Question",
                    "body": (
                        "A single inference query feels weightless — a question "
                        "typed, an answer returned, no moving parts in sight. "
                        "But the underlying infrastructure rests on a deeply "
                        "physical edifice: millions of processors, hundreds of "
                        "thousands of kilometers of cabling, industrial cooling "
                        "systems, and power demands that rival those of midsize "
                        "countries. Better understanding of that complexity — "
                        "and the assumptions on which build-out rests — should "
                        "inform how we think about the scale, durability, and "
                        "risks of the capital expenditure boom."
                    ),
                },
                {
                    "heading": "Baseline Estimates",
                    "body": (
                        "We anchor a baseline model to forward data center "
                        "revenue estimates as a proxy for prevailing "
                        "expectations around accelerator deployment, and then "
                        "infer the associated requirements for data centers, "
                        "power, and supporting infrastructure. The baseline "
                        "implies roughly $700 billion in annual capex in 2026, "
                        "growing toward $1.5 trillion in 2031."
                    ),
                    "pull_quote": (
                        "The headline capex figures are not a single number. "
                        "They are a band whose width is set by infrastructure "
                        "assumptions, not just demand."
                    ),
                },
                {
                    "heading": "Sensitivity to Useful Life",
                    "body": (
                        "If accelerators are replaced every two years instead "
                        "of four, cumulative capex over a five-year horizon "
                        "expands by hundreds of billions. The replacement "
                        "cadence is the single most sensitive lever in the "
                        "model — yet it is also the assumption with the "
                        "weakest empirical anchor, since the technology is "
                        "young and operator practices vary."
                    ),
                },
            ],
            "footnotes": [
                "1 Forecasts and expectations are illustrative and based on material assumptions subject to change. Numbers shown are placeholder figures for layout demonstration.",
                "2 Assumes a leading accelerator vendor accounts for 75% of compute spend in each period, with 5% YoY growth past 2031.",
                "3 Assumes a power utilization effectiveness of 1.2 and a unit cost of $15M per megawatt of data center capacity.",
            ],
        },
    })
    return render(request, "gsapp/insights_article.html", ctx)


def insights_podcast(request):
    ctx = _base_context(active_nav="Insights")
    ctx.update({
        "article": {
            "eyebrow": "The Markets",
            "title": "Crude Oil Drivers and the Path Through 2026",
            "date": "May 8, 2026",
            "duration": "32 min",
            "image_tint": "burnt",
            "host": {"name": "Pat Placeholder", "title": "Markets Reporter"},
            "guest": {"name": "Jordan Sample", "title": "Head of Commodities Research"},
            "summary": (
                "A wide-ranging conversation on the supply, demand, and "
                "geopolitical inputs shaping the path of crude oil markets "
                "through the back half of the year, with attention to "
                "OPEC+ behaviour, US shale economics, and demand "
                "elasticity in emerging markets."
            ),
            "chapter_markers": [
                {"time": "0:00", "label": "Setup and the macro backdrop"},
                {"time": "5:42", "label": "Supply: OPEC+ discipline and shale response"},
                {"time": "13:15", "label": "Demand: emerging markets and aviation"},
                {"time": "21:00", "label": "Risk scenarios and the back half of the year"},
                {"time": "28:30", "label": "Listener questions"},
            ],
        },
    })
    return render(request, "gsapp/insights_podcast.html", ctx)


def careers(request):
    ctx = _base_context(active_nav="Careers")
    ctx.update({
        "hero": {
            "eyebrow": "Careers",
            "title": "Pursue the Exceptional",
            "subtitle": (
                "Placeholder hero copy for a hypothetical careers landing "
                "page. Lorem ipsum dolor sit amet consectetur adipiscing "
                "elit sed do eiusmod tempor incididunt ut labore."
            ),
            "cta_label": "Find Your Place",
            "cta_url": "#find-your-place",
            "image_tint": "navy",
        },
        "tabs": [
            {"label": "Students", "url": "#students", "active": True},
            {"label": "Open Roles", "url": "#open-roles"},
        ],
        "culture_two_up": {
            "eyebrow": "Culture",
            "title": "Voices of the Firm",
            "body": (
                "Sample two-up section body. Lorem ipsum dolor sit amet, "
                "consectetur adipiscing elit. Duis aute irure dolor in "
                "reprehenderit in voluptate velit esse cillum dolore."
            ),
            "cta": "Discover Life at the Firm",
            "cta_url": "/careers/life/",
            "image_tint": "teal",
        },
        "featured_roles": [
            {
                "eyebrow": "Engineering",
                "title": "Build the systems that move global markets",
                "body": "From low-latency trading infrastructure to client platforms.",
                "image_tint": "purple",
            },
            {
                "eyebrow": "Quant Research",
                "title": "Translate market structure into model and signal",
                "body": "Cross-asset quantitative research and systematic strategy.",
                "image_tint": "navy",
            },
            {
                "eyebrow": "Investment Banking",
                "title": "Advise the world's most influential institutions",
                "body": "Sector-deep teams across M&A, ECM, DCM, and structured finance.",
                "image_tint": "amber",
            },
            {
                "eyebrow": "Asset Management",
                "title": "Manage capital across public and private markets",
                "body": "Active strategies across equities, credit, alternatives.",
                "image_tint": "olive",
            },
        ],
        "path_tiles": [
            {"title": "Match Your Skills", "body": "Find the right team for your background."},
            {"title": "Student Programs", "body": "Internship and full-time entry programs."},
            {"title": "Professional Programs", "body": "Mid-career and lateral hiring tracks."},
            {"title": "Feel Prepared", "body": "Interview prep and process expectations."},
        ],
        "tagline_quote": (
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
            "Sed do eiusmod tempor incididunt ut labore et dolore magna."
        ),
        "two_ups": [
            {
                "eyebrow": "Who We Are",
                "title": "United by Partnership, Client Service, Integrity, Excellence",
                "body": (
                    "Four shared values that anchor the firm and define how "
                    "we work together, with our clients, and in our communities."
                ),
                "cta": "Our Purpose and Values",
                "cta_url": "/our-firm/purpose-and-values/",
                "image_tint": "brown",
            },
            {
                "eyebrow": "Impact",
                "title": "The Business of Impact",
                "body": (
                    "We put people, ideas, and capital to work through "
                    "impact-oriented programs across small business growth, "
                    "community investment, and access to opportunity."
                ),
                "cta": "Review Our Initiatives",
                "cta_url": "#",
                "image_tint": "teal",
                "reverse": True,
            },
            {
                "eyebrow": "Belonging",
                "title": "Diverse Teams Drive Stronger Results",
                "body": (
                    "Our focus on building inclusive, diverse teams is "
                    "central to our commercial performance and the quality "
                    "of advice we deliver to clients."
                ),
                "cta": "Learn More",
                "cta_url": "#",
                "image_tint": "mauve",
            },
        ],
        "our_firm_links": [
            {"title": "Risk", "body": "Identifies, monitors, evaluates, and manages financial and non-financial risks across the firm."},
            {"title": "Asset Management", "body": "Provides investment management solutions across all major asset classes for institutional and individual clients."},
            {"title": "Operations", "body": "Enables every trade, product launch, market entry, and completed transaction across the global business."},
            {"title": "Engineering", "body": "Envisions, builds, and deploys industry-leading systems that drive the firm's business and extend its boundaries."},
        ],
    })
    return render(request, "gsapp/careers.html", ctx)


def careers_life(request):
    ctx = _base_context(active_nav="Careers")
    ctx.update({
        "page_eyebrow": "Careers",
        "page_title": "A Practice in Practice",
        "page_subtitle": (
            "Sample placeholder page subtitle. Lorem ipsum dolor sit amet, "
            "consectetur adipiscing elit. Sed do eiusmod tempor incididunt "
            "ut labore et dolore magna aliqua."
        ),
        "two_ups": [
            {
                "eyebrow": "Meet Our People",
                "title": "Our People",
                "body": (
                    "Colleagues share their experiences, what it is like to "
                    "be part of the firm, and how they have contributed to "
                    "and benefited from growth opportunities and mentorship."
                ),
                "cta": "Read Profiles",
                "image_tint": "navy",
            },
            {
                "eyebrow": "Inclusion",
                "title": "Diversity and Inclusion",
                "body": (
                    "Our focus on diversity and inclusion is critical to our "
                    "commercial success and the quality of our work."
                ),
                "cta": "Learn More",
                "image_tint": "purple",
                "reverse": True,
            },
            {
                "eyebrow": "Wellbeing",
                "title": "Supporting Success",
                "body": (
                    "We provide top-tier benefits, from comprehensive "
                    "healthcare options and crisis support to wellness "
                    "programs and family-care resources."
                ),
                "cta": "Explore Benefits",
                "image_tint": "teal",
            },
            {
                "eyebrow": "Growth",
                "title": "Maximizing Potential",
                "body": (
                    "We develop programs and resources to support "
                    "professional growth and unlock the potential of our "
                    "people across every stage of their careers."
                ),
                "cta": "Career Development",
                "image_tint": "amber",
                "reverse": True,
            },
        ],
        "alumni_two_up": {
            "eyebrow": "Alumni",
            "title": "A Strong and Active Alumni Network",
            "body": (
                "Our people remain a part of the firm long beyond their "
                "tenure, with a global alumni network connecting former "
                "colleagues to one another and to the firm's thought "
                "leadership."
            ),
            "cta": "Explore the Network",
            "image_tint": "brown",
        },
    })
    return render(request, "gsapp/careers_life.html", ctx)


def purpose(request):
    ctx = _base_context(active_nav="Our Firm")
    ctx.update({
        "page_eyebrow": "Our Firm",
        "page_title": "Our Purpose",
        "page_subtitle": (
            "Sample placeholder subtitle. Lorem ipsum dolor sit amet, "
            "consectetur adipiscing elit, sed do eiusmod tempor "
            "incididunt ut labore et dolore magna aliqua."
        ),
        "values": [
            {
                "title": "Partnership",
                "body": (
                    "Lorem ipsum dolor sit amet, consectetur adipiscing "
                    "elit. Ut enim ad minim veniam, quis nostrud exercitation "
                    "ullamco laboris nisi ut aliquip ex ea commodo consequat."
                ),
            },
            {
                "title": "Client Service",
                "body": (
                    "Duis aute irure dolor in reprehenderit in voluptate "
                    "velit esse cillum dolore eu fugiat nulla pariatur. "
                    "Excepteur sint occaecat cupidatat non proident."
                ),
            },
            {
                "title": "Integrity",
                "body": (
                    "Sunt in culpa qui officia deserunt mollit anim id est "
                    "laborum. Sed ut perspiciatis unde omnis iste natus "
                    "error sit voluptatem accusantium doloremque."
                ),
            },
            {
                "title": "Excellence",
                "body": (
                    "Nemo enim ipsam voluptatem quia voluptas sit aspernatur "
                    "aut odit aut fugit, sed quia consequuntur magni dolores "
                    "eos qui ratione voluptatem sequi nesciunt."
                ),
            },
        ],
        "principles_two_up": {
            "eyebrow": "Defining the Firm",
            "title": "Business Principles",
            "body": (
                "A set of foundational principles articulates what the firm "
                "stands for. Established decades ago, they remain the "
                "ground truth that shapes the firm's culture and decisions."
            ),
            "cta": "Read the Principles",
            "image_tint": "navy",
        },
        "ethics_links": [
            {"title": "Code of Business Ethics and Conduct"},
            {"title": "Report of the Business Standards Committee"},
            {"title": "Business Standards Committee Impact Report"},
            {"title": "Corporate Governance"},
        ],
        "discover_cards": [
            {
                "eyebrow": "Heritage",
                "title": "Discover Our History",
                "body": "From a single trading partnership to a global institution.",
                "image_tint": "brown",
            },
            {
                "eyebrow": "Leadership",
                "title": "Meet Our People and Leaders",
                "body": "Profiles of leadership across the firm's businesses.",
                "image_tint": "olive",
            },
        ],
    })
    return render(request, "gsapp/purpose.html", ctx)
