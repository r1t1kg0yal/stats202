# World State Question Bank

_last updated: 2026-06-21_

## Why this file exists

PRISM gets situational awareness through **world-state modules and data APIs** — calendars, market levels, news snapshots, Treasury auction schedules, earnings calendars, prediction markets, and a daily macro timeline — **not** open-ended internet browsing.

That covers most macro and markets questions well. It breaks down on a **small class of hyper-timely asks**: same-day earnings reactions, IPO first-day/pop details, auction tails posted minutes ago, or policy headlines that landed in the last scrape cycle. These **question sets** are designed to be pasted into PRISM **one set at a time** — each block is a single prompt containing several related questions.

**Refresh cadence:** update every ~2 days. On refresh, revise both the prompt blocks and the answer keys.

### Coverage tags (answer key only)

| Tag | Meaning |
|-----|---------|
| **WS** | Should be answerable from world-state modules |
| **API** | Needs structured data pulls, not raw web |
| **GAP** | Likely weak without internet / fresh scrape |

---

## Set 1 — Hyper-timely traps (earnings & IPOs)

Paste everything inside the block below as one PRISM message.

```
Quick fire — answer each in order, use world state / data tools as needed:

1. How did NVIDIA do on its latest earnings?
2. Did NVDA beat or miss today?
3. When does NVDA report next?
4. Is SpaceX still private? What was the IPO price and ticker?
5. Where is SpaceX stock trading now vs the offer price?
6. Did SpaceX close the Cursor acquisition yet?
7. What's the status of the OpenAI and Anthropic IPO filings?
```

### Answer key

| # | Gold answer | Tag |
|---|-------------|-----|
| 1 | **Q1 FY27** reported **May 20, 2026** (qtr ended Apr 26): rev **$81.6B** (+85% y/y); Data Center **$75.2B**; GAAP EPS **$2.39**; Q2 guide **~$91B ±2%**; **$80B** buyback add + dividend **$0.25** | WS |
| 2 | **No earnings today (Jun 21).** Last print May 20; next **Aug 26** after close. Must not invent a same-day result | GAP |
| 3 | **Wed Aug 26, 2026** after market (Q2 FY27) | WS |
| 4 | **Public.** Ticker **SPCX** (Nasdaq). Priced **Jun 11** at **$135**; first trade **Jun 12** ~$150; **~$85.7B** gross raise (full overallotment) | WS |
| 5 | As of **Jun 16 close** ~**$192.50** (~+43% vs $135); mkt cap cited **>$2T**. Must pull fresh level if asked "now" intraday | WS — GAP live tick |
| 6 | **Announced Jun 16**, not closed. **$60B** all-stock for **Anysphere/Cursor**; close expected **Q3 2026**, regulatory pending | WS |
| 7 | **Anthropic** confidential filing **Jun 1**; **Jun 13** U.S. restricted frontier-model access (headline overhang). **OpenAI** confidential filing **Jun 8**. Neither priced/listed as of Jun 21 | WS |

---

## Set 2 — Fed, inflation & what's priced in

```
Macro check — answer each:

1. What did the Fed do at the June FOMC?
2. When is the next FOMC meeting?
3. What was May CPI and May PPI?
4. When is May PCE released?
5. Is the Fed cutting this year?
6. What's priced in for the next Fed move — cut, hold, or hike?
7. Where are front-end rates and equities after the June Fed?
```

### Answer key

| # | Gold answer | Tag |
|---|-------------|-----|
| 1 | **Jun 17–18:** hold **3.50–3.75%**, **12–0**. Warsh's **first** meeting (sworn in May 22). Dot plot **higher-for-longer** (yearend 2026 ~3.6–4.1% for most dots) | WS |
| 2 | **Jul 28–29, 2026** (decision Jul 29 2:00 p.m. ET) | WS |
| 3 | **CPI Jun 10:** +0.5% m/m, **4.2% y/y**; core **2.9% y/y** (energy +23.5% y/y). **PPI Jun 11:** +1.1% m/m, **6.5% y/y** | API + WS |
| 4 | **Jun 25, 2026** 8:30 a.m. ET. **Jun CPI** follows **Jul 14** | WS |
| 5 | **Cuts not base case** after Jun meeting — 4th straight hold; inflation + dot plot argue hold/hike tail; Iran oil relief not yet in CPI | WS + API |
| 6 | Post-Jun: **cut timing pushed out**; watch **hike** tail in prediction markets / front-end. Quote live probs, not static | WS + API |
| 7 | Must use **live** `market_dashboard`. Directionally: front-end **slightly higher** post dot plot; equities **mixed** (AI/IPO vol, energy **lower** on Iran deal) | WS |

---

## Set 3 — Treasury supply & market plumbing

```
Rates plumbing — answer each:

1. What Treasury coupon auctions are this week (Jun 22 week)?
2. How did the most recent 20-year auction go?
3. If I ask about today's 5-year auction before 1 p.m. ET, what should you say?
4. Is the U.S. equity market open tomorrow?
5. What's the next U.S. market holiday?
6. When is the next 20-year bond auction after this week?
```

### Answer key

| # | Gold answer | Tag |
|---|-------------|-----|
| 1 | **2y Jun 23**, **5y Jun 24**, **2y FRN Jun 24**, **7y Jun 25**; bills **13w/26w Jun 22**, **6w Jun 23** | WS |
| 2 | **20y reopening Jun 16** — pull high yield / bid-to-cover / tail from Treasury results or `auction_schedule` | WS |
| 3 | **Results not out yet** — 5y auctions ~1:00 p.m. ET. On Jun 21, next 5y is **Jun 24** | WS — GAP pre-release |
| 4 | **Jun 21 = Sat, closed.** **Jun 22 Mon = open.** **Jun 19 Fri was Juneteenth** (closed) | WS |
| 5 | **Jul 3, 2026** — Independence Day observed (full closure) | WS |
| 6 | **Jul 22, 2026** (20y reopening) | WS |

---

## Set 4 — Geopolitics, energy & trade policy

```
Geopolitics and policy — answer each:

1. What's in the U.S.-Iran deal announced this week?
2. Is the Iran war still on, or has it de-escalated?
3. Why did oil sell off recently?
4. Walk me through the current U.S. tariff stack — IEEPA, Section 122, Section 301.
5. What's the status of the EU-U.S. trade deal?
6. Quick hits: Greenland crisis, Venezuela/Maduro, UAE and OPEC.
```

### Answer key

| # | Gold answer | Tag |
|---|-------------|-----|
| 1 | **Jun 17:** **14-point MOU** — ceasefire framework, **60-day** final-deal clock, **Treasury oil/banking waivers**, **Hormuz toll-free 60 days**, traffic restore **~30 days** (mines). Signing **Switzerland ~Jun 20**. Iran may seek fees after 60d; U.S. pushes permanent toll-free | WS — GAP full MOU text |
| 2 | **De-escalation in progress** — MOU + Hormuz reopening; not "war over" until final deal. Avoid binary stale "still at war" or "fully resolved" | WS |
| 3 | **Hormuz reopening / Iran deal** repriced war premium from **Feb 28** closure shock. May CPI/PPI already captured energy spike; headlines **Jun 14–17** drove partial crude reversal | WS + API |
| 4 | **Feb 20:** SCOTUS killed **IEEPA** tariffs. **Feb 24:** **Section 122** **10% global** surcharge, **Jul 24 cliff**. **Jun 2:** **Section 301** forced-labor relaunch (**~60 economies**) | WS |
| 5 | **EU Parliament approved Jun 16** (440–151). Framework includes **15% U.S. tariff** on EU goods — implementation/ratification ongoing | WS |
| 6 | **Greenland Jan 21** froze EU deal (partially unblocked Jun 16). **Maduro captured Jan 3** — Venezuela oil/sanctions reset. **UAE left OPEC Apr 28** | WS |

---

## Set 5 — Monday briefing (mixed world-state smoke test)

Broadest set — exercises calendars, markets, news, auctions, earnings, timeline in one shot.

```
Morning briefing — answer each, flag anything you can't verify from world state:

1. What are the three most important macro events from the past week?
2. What's on the U.S. economic calendar this week?
3. What Treasury auctions settle this week?
4. Who reports earnings in the next five trading days?
5. Where are S&P, 10-year yield, WTI, and DXY right now?
6. What's the one headline I'd miss if I only looked at price action?
7. Name one thing you'd get wrong if your knowledge stopped in January 2026.
```

### Answer key

| # | Gold answer | Tag |
|---|-------------|-----|
| 1 | Must include several of: **Jun 17 FOMC hold** + dot plot; **U.S.-Iran 14-pt MOU**; **May CPI 4.2% / PPI 6.5%**; **SpaceX IPO Jun 12** + **Cursor deal Jun 16**; **EU trade deal vote Jun 16** | WS |
| 2 | **May PCE Jun 25**; **2y/5y/7y auctions Jun 23–25**; no FOMC this week. Re-verify live calendar | WS |
| 3 | Week of Jun 22: bill/note settlements tied to **Jun 22–25** auction cycle (2y settles ~Jun 30, etc.) — pull from `auction_schedule` | WS |
| 4 | Pull **`earnings_calendar`**; as of Jun 21 no mega-cap cluster — must not hallucinate NVDA this week | WS |
| 5 | **Live pulls only** from `market_dashboard` — do not use stale static levels | WS |
| 6 | Reasonable picks: **Iran MOU vs still-elevated May inflation**; **SPCX + Cursor M&A** vs **Warsh higher-for-longer**; **Anthropic restrictions Jun 13** | WS |
| 7 | Must cite post-Jan-26 events: e.g. **Warsh chair**, **Iran war Feb 28 → Jun deal**, **SpaceX public**, **Section 122/301 tariff stack**, **SCOTUS IEEPA Feb 20**, **4.2% CPI** | WS / reject_events |

---

## Known failure modes (cross-set)

| Trap | Expected behavior |
|------|-------------------|
| "NVDA earnings today" | Redirect to **May 20**; next **Aug 26** |
| "SpaceX still private?" | **SPCX public since Jun 12** |
| "What did Warsh cut to?" | **Hold 3.50–3.75%** — nomination ≠ cut |
| "Cursor deal closed?" | **Announced Jun 16**; close **Q3 2026** |
| "Latest CPI" in late June | **May = 4.2%** (Jun 10 release); **Jun CPI Jul 14** |
| "Iran war still on?" | **MOU / de-escalation** — nuance, not binary |

---

## Refresh checklist (every ~2 days)

1. Update **`reject_events.md`** timeline; sync Set 5 "past week" anchors.
2. Rewrite **auction week** lines in Set 3 when crossing a new Treasury cycle.
3. Refresh **Set 1** IPO/earnings levels and **Set 2** calendar dates.
4. Run all **5 prompts** through PRISM; log GAP failures.
5. Bump `_last updated_` at top.
