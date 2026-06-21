# World State Question Bank

_last updated: 2026-06-21_

## Why this file exists

PRISM gets situational awareness through **world-state modules and data APIs** — calendars, market levels, news snapshots, Treasury auction schedules, earnings calendars, prediction markets, and a daily macro timeline — **not** open-ended internet browsing.

That covers most macro and markets questions well. It breaks down on a **small class of hyper-timely asks**: same-day earnings reactions, IPO first-day/pop details, auction tails posted minutes ago, or policy headlines that landed in the last scrape cycle. Those are the edge cases this list is meant to catch.

**Refresh cadence:** update every ~2 days so answers stay aligned with what a well-informed user would expect *right now*.

### Coverage tags

| Tag | Meaning |
|-----|---------|
| **WS** | Should be answerable from world-state modules (`calendars`, `market_dashboard`, `news_snapshot`, `auction_schedule`, `earnings`, `timeline`, `prediction_markets`) |
| **API** | Needs structured data pulls (Haver, GS market data, Treasury API, etc.) but not raw web search |
| **GAP** | Likely weak or stale without internet; flag for product / ingestion improvement |

---

## Earnings & corporate events

### Q: How did NVIDIA do on its latest earnings?

**Correct answer:** NVIDIA reported **Q1 FY27** (quarter ended **Apr 26, 2026**) on **May 20, 2026**: revenue **$81.6B** (+85% y/y, +20% q/q); Data Center **$75.2B** (+92% y/y); GAAP diluted EPS **$2.39**; Q2 FY27 revenue guide **~$91B ±2%**. Also announced **$80B** additional buyback authorization and dividend raised to **$0.25/share**.

**Tag:** WS (`earnings_calendar` for dates; `news_snapshot` for headline results) — **GAP** if user means "today's call" (no NVDA report on Jun 21).

---

### Q: When does NVDA report next?

**Correct answer:** **Wednesday Aug 26, 2026**, after market close (Q2 FY27).

**Tag:** WS (`earnings_calendar`)

---

### Q: Did NVDA beat or miss today?

**Correct answer:** **No earnings today.** Last report was **May 20, 2026** (Q1 FY27). Next report **Aug 26, 2026**. Do not invent an intraday print.

**Tag:** GAP — classic stale-LLM trap; world-state should disambiguate date.

---

### Q: Who reports earnings this week?

**Correct answer:** Check `earnings_calendar` for the next 7 days. As of Jun 21, the calendar is thin post-SpaceX IPO week; no mega-cap tech cluster comparable to NVDA's May print. (Re-verify against live calendar on refresh.)

**Tag:** WS

---

## IPOs & M&A

### Q: Is SpaceX public? What was the IPO price?

**Correct answer:** Yes. **Ticker SPCX** (Nasdaq). Priced **Jun 11, 2026** at **$135/share**; first trade **Jun 12** ~$150; gross proceeds **~$85.7B** after full overallotment (largest IPO ever). Closing/settlement **Jun 15, 2026**.

**Tag:** WS (`news_snapshot`, `timeline`) — **GAP** for exact intraday high/low on a given session.

---

### Q: Where is SpaceX stock trading after the IPO?

**Correct answer:** As of **Jun 16 close**, SPCX ~**$192.50** (~+43% vs $135 offer); heavy volume (~500M shares day 1, ~244M day 2). Market cap cited above **$2T** post-debut. (Re-check `market_dashboard` on refresh.)

**Tag:** WS + API — **GAP** for live tick during session.

---

### Q: Did SpaceX buy Cursor?

**Correct answer:** Yes — **Jun 16, 2026** definitive agreement to acquire **Anysphere** (Cursor) for **$60B all-stock** via subsidiary **X67 Inc.** Expected close **Q3 2026**, subject to regulatory approval. Exercised an option from Apr 2026; **$10B** termination fee / **$4B** antitrust break fee in merger docs.

**Tag:** WS (`news_snapshot`, `timeline`)

---

### Q: What's the status of the OpenAI / Anthropic IPOs?

**Correct answer:**
- **Anthropic:** confidential IPO filing **Jun 1, 2026**; **Jun 13** U.S. restricted access to Anthropic frontier models for federal/defense-adjacent use cases (headline risk for IPO narrative).
- **OpenAI:** confidential IPO filing **Jun 8, 2026**.
- Neither has priced or listed as of Jun 21. SpaceX IPO (Jun 12) is the reference comp for AI IPO window.

**Tag:** WS (`timeline`, `news_snapshot`) — **GAP** for S-1 line-item detail not in news scrape.

---

## Fed, rates & data releases

### Q: What did the Fed do at the June FOMC?

**Correct answer:** **Jun 17–18, 2026** meeting: held **fed funds at 3.50–3.75%** (unanimous **12–0**). First meeting under Chair **Kevin Warsh** (sworn in May 22). Statement cited solid growth, elevated inflation (energy/supply shocks), Middle East uncertainty. **Jun dot plot** shifted **higher-for-longer** vs Mar (most officials see yearend 2026 funds ~3.6–4.1%).

**Tag:** WS (`calendars`, `news_snapshot`, `prediction_markets`)

---

### Q: When is the next FOMC meeting?

**Correct answer:** **Jul 28–29, 2026** (decision **Jul 29** 2:00 p.m. ET).

**Tag:** WS (`calendars`)

---

### Q: What was May CPI?

**Correct answer:** Released **Jun 10, 2026**: headline **+0.5% m/m**, **4.2% y/y**; core **+0.2% m/m**, **2.9% y/y**. Energy **+23.5% y/y** (gasoline +40.5% y/y) drove most of the headline surge — Iran / Hormuz war backdrop.

**Tag:** API (BLS) + WS (`calendars` for release date)

---

### Q: What was May PPI?

**Correct answer:** Released **Jun 11, 2026**: final demand **+1.1% m/m**, **6.5% y/y** (largest 12m since Nov 2022); goods **+2.8% m/m** (record in series history back to Dec 2009).

**Tag:** API + WS

---

### Q: When is PCE / the next big inflation print?

**Correct answer:** **May PCE: Jun 25, 2026** (8:30 a.m. ET). **Jun CPI: Jul 14, 2026**.

**Tag:** WS (`calendars`)

---

### Q: Is the Fed cutting this year?

**Correct answer:** After Jun FOMC, **cuts are not the base case** — hold at 3.50–3.75% four meetings running; dot plot moved up; prediction markets / rates pricing shifted toward **hold or hike** risk given 4.2% CPI and 6.5% PPI. Iran-deal oil relief is a partial offset but not yet in Jun CPI.

**Tag:** WS (`prediction_markets`, `news_snapshot`) + API (rates)

---

## Treasury & market structure

### Q: What Treasury auctions are this week?

**Correct answer (week of Jun 22):**
- **2-Year Note:** auctioned **Jun 23** (announced Jun 18)
- **5-Year Note:** **Jun 24**
- **2-Year FRN (reopening):** **Jun 24**
- **7-Year Note:** **Jun 25**
- **13-Week / 26-Week Bills:** **Jun 22** auction
- **6-Week Bill:** **Jun 23**
- Last **20-Year Bond** reopening was **Jun 16**; next **20-Year** is **Jul 22**

**Tag:** WS (`auction_schedule`)

---

### Q: How did today's 5-year auction go?

**Correct answer:** If asked **before ~1:00 p.m. ET on auction day**, results aren't out yet — say so. If **after** release, pull tail / bid-to-cover / high yield from Treasury results or `auction_schedule` refresh. On **Jun 21**, no 5-year auction today; next is **Jun 24**.

**Tag:** WS — **GAP** in the minutes between auction close and API/scrape update.

---

### Q: Is the market open tomorrow?

**Correct answer:** **Jun 21, 2026 is Saturday** — closed. **Jun 22 (Mon)** regular session. **Jun 19 (Fri)** was **Juneteenth** — closed. Next holiday: **Jul 3** (Independence Day observed).

**Tag:** WS (`calendars`)

---

## Geopolitics, policy & news

### Q: What's the U.S.-Iran deal?

**Correct answer:** **Jun 17, 2026** — U.S. released **14-point MOU**: immediate ceasefire framework, **60-day** window to negotiate final deal, **U.S. Treasury waivers** on Iranian oil exports/banking upon signing, **Strait of Hormuz** commercial passage **toll-free 60 days**, traffic restoration target **~30 days** (mines/clearance lag). Formal signing ceremony **Switzerland ~Jun 20**. Iran negotiators flagged possible **fees after 60 days** — U.S. side insists toll-free should persist in final deal.

**Tag:** WS (`news_snapshot`, `timeline`) — **GAP** for full MOU text vs headline summary.

---

### Q: Why did oil sell off this week?

**Correct answer:** **Hormuz reopening / U.S.-Iran preliminary deal** repriced war premium embedded since **Feb 28** Iran war & closure shock. May CPI/PPI already reflected war-driven energy spike; deal headlines (Jun 14–17) triggered partial reversal in crude forwards.

**Tag:** WS + API (market_dashboard for WTI/Brent move)

---

### Q: What's going on with tariffs?

**Correct answer (layered):**
- **Feb 20:** SCOTUS rejected **IEEPA** global tariffs
- **Feb 24:** **Section 122** bridge — **10% global surcharge**, **Jul 24, 2026** cliff unless extended
- **Jun 2:** **Section 301** forced-labor relaunch targeting **~60 economies**
- **Jun 16:** **EU Parliament** approved **EU-U.S. trade deal** (440–151) — **15% U.S. tariff** on EU goods under deal framework

**Tag:** WS (`timeline`, `news_snapshot`)

---

### Q: What happened with Greenland / Venezuela / UAE OPEC?

**Correct answer:**
- **Jan 21:** Greenland crisis; NATO tariff standoff froze EU trade-deal approval (since partially resolved Jun 16)
- **Jan 3:** Maduro captured; Venezuela oil / sanctions reset narrative
- **Apr 28:** **UAE left OPEC**

**Tag:** WS (`timeline`)

---

### Q: What's the EU-U.S. trade deal status?

**Correct answer:** **European Parliament approved Jun 16, 2026** (440–151). Framework includes **15% U.S. tariff** on EU goods under the deal — follow implementation / ratification steps in `news_snapshot`.

**Tag:** WS

---

## Market levels & positioning

### Q: Where are rates and equities after the Fed?

**Correct answer:** Pull live levels from `market_dashboard`. Post-Jun-17 FOMC: **front-end rates** repriced slightly higher on dot plot; **equities** mixed — AI / IPO complex (SPCX) volatile, energy lower on Iran deal. Do not quote static levels — always use fresh dashboard.

**Tag:** WS (`market_dashboard`)

---

### Q: What's priced in for the next Fed cut?

**Correct answer:** Use `prediction_markets_snapshot` + front-end OIS/swaps from market data. After Jun meeting, **cut timing pushed out**; monitor for **hike** tail vs cut. Exact probabilities change hourly.

**Tag:** WS + API

---

## Known failure modes (regression targets)

| User ask | Failure mode | Expected behavior |
|----------|--------------|-------------------|
| "NVDA earnings today" | Stale LLM invents EPS | Correct to **May 20** print; next **Aug 26** |
| "SpaceX still private?" | Pre-IPO world model | **Public SPCX since Jun 12** |
| "What did Warsh cut to?" | Confuses nomination vs decision | **Hold 3.50–3.75%** at Jun FOMC |
| "Auction tomorrow" without date | Wrong tenor/day | Use `auction_schedule` for exact CUSIP/tenor/date |
| "Latest CPI" in late June | Misses May print timing | **May CPI = 4.2%**, released Jun 10; Jun CPI Jul 14 |
| "Iran war still on?" | Binary stale state | **Jun 17 MOU** — active de-escalation / 60-day talks, Hormuz reopening in progress |
| "Cursor acquisition closed?" | Treats announce as close | **Announced Jun 16**; close expected **Q3 2026**, pending regulators |

---

## Refresh checklist (every ~2 days)

1. Add any new `reject_events.md` timeline entries since last refresh.
2. Re-verify **earnings** names reporting in the next 7 days.
3. Update **auction week** block if crossing a new Treasury announcement cycle.
4. Spot-check **3–5 GAP rows** above against live PRISM session — did world-state close the gap?
5. Bump `_last updated_` date at top.
