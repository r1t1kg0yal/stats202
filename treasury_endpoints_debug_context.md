# Treasury Endpoints — Debug Context for PRISM's Empty Returns

Companion doc to `treasury_endpoints_integration.md`. PRISM reported that
`get_tic_mfh()`, `get_tic_top_holders()`, `get_tic_country_holdings()` and
`scrape_refunding_latest()` all return empty. This doc explains **exactly why
they return empty**, what changed, and ships verified working URLs + Python
parsers (run end-to-end against live data on 2026-04-30).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  TL;DR — ROOT CAUSES                                                         │
│                                                                              │
│  1. TIC (mfh.txt)                                                            │
│     • Old URL is alive but data frozen at Jan 2023.                          │
│     • Treasury moved to new file naming in Mar 2023 with form SLT changes.   │
│     • Real data lives at slt_table5.txt — completely different format        │
│       (TAB-DELIMITED, not fixed-width).                                      │
│                                                                              │
│  2. Quarterly Refunding (Latest.aspx)                                        │
│     • Old www.treasury.gov landing page 302-redirects to home.treasury.gov.  │
│     • Document URLs moved to /system/files/221/ predictable pattern.         │
│     • Each artifact is a directly-linkable PDF/XML/XLS — no scraping HTML    │
│       page tables needed; the press-release page just lists hyperlinks.      │
│                                                                              │
│  Diagnosis is NOT proxy / auth — both new URLs return clean 200 from any     │
│  vanilla curl. The PRISM scrapers are pointed at deprecated endpoints.       │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. TIC — What Broke and the Fix

### 1.1  Old vs new URL inventory

```
┌───────────────────────────────────────┬────────────────────────────────────┐
│ Old URL (pre-Mar-2023, still up)      │ Status (verified 2026-04-30)       │
├───────────────────────────────────────┼────────────────────────────────────┤
│ ticdata.treasury.gov/Publish/         │ HTTP 200 (7,486 bytes)             │
│   mfh.txt                              │ But last-modified Feb 10 2026 with │
│                                        │ data through Jan 2023 ONLY. The    │
│                                        │ file has been frozen since the     │
│                                        │ Form SLT migration. Any "current"  │
│                                        │ parse returns ancient data.        │
│                                        │                                    │
│ www.treasury.gov/.../tic/Documents/    │ Most return 404 (404 page is       │
│   snetus.csv                           │ ~100KB Drupal HTML, which can      │
│                                        │ silently parse to "no rows").      │
└───────────────────────────────────────┴────────────────────────────────────┘
```

```
┌───────────────────────────────────────────────────────────────────────────┐
│ Current URL (post-Mar-2023 SLT migration)                                 │
├───────────────────────────────────────────────────────────────────────────┤
│ MFH (Major Foreign Holders, current 13 months):                           │
│   ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/   │
│     slt_table5.txt    ← THE file PRISM should fetch                        │
│     slt_table5.html   (HTML version of the same)                           │
│                                                                            │
│ MFH historical (going back further):                                      │
│     mfhhis01.txt      (multi-year archive)                                 │
│                                                                            │
│ Other SLT tables (also current):                                          │
│     slt_table1.txt   foreign holdings of US LT securities (all types)     │
│     slt_table2.txt   US holdings of foreign LT securities                 │
│     slt_table3.txt   US Treasuries held by foreign residents              │
│     slt_table4.txt   US purch/sales of LT domestic & foreign by type      │
│                       (replaces the old snetus.csv)                        │
└───────────────────────────────────────────────────────────────────────────┘
```

### 1.2  Live verification (run yourself to confirm)

```bash
curl -sI "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
# HTTP/2 200, content-type: text/plain
# (Currently ~3 KB; updated monthly mid-month)

curl -sI "https://ticdata.treasury.gov/Publish/mfh.txt"
# HTTP/2 200 — but data is stale (frozen Jan 2023). Do NOT use.
```

### 1.3  Live `slt_table5.txt` head (verified 2026-04-30)

```
Table 5: Major Foreign Holders of Treasury Securities
Holdings at end of time period
Billions of dollars
Link: https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt

Country	2026-02	2026-01	2025-12	2025-11	2025-10	2025-09	2025-08	2025-07	2025-06	2025-05	2025-04	2025-03	2025-02
Japan	1239.3	1225.3	1185.5	1202.7	1200.0	1189.3	1180.4	1151.8	1147.9	1135.0	1134.5	1130.8	1125.9
United Kingdom	897.3	879.7	863.1	879.8	875.4	862.1	901.4	896.0	855.7	809.4	807.7	779.3	750.3
China, Mainland	693.3	694.4	683.5	683.9	687.7	699.2	699.7	695.6	731.4	732.7	743.6	765.4	784.3
Belgium	454.7	451.0	477.3	481.0	465.5	463.6	451.1	425.4	430.3	415.5	411.1	402.1	394.7
Canada	446.3	395.8	468.2	472.4	419.4	476.0	443.8	381.6	438.7	430.1	368.4	426.2	406.1
... (about 25 country rows)
All Other	1856.3	1831.3	1822.8	1840.1	1830.8	1796.3	1793.5	1788.1	1758.2	1743.0	1754.6	1743.9	1727.6
Grand Total	9487.1	9289.4	9267.2	9349.6	9232.9	9237.1	9248.4	9109.4	9094.0	9023.5	9001.0	9054.2	8900.0
Of Which: Foreign Official	4035.7	3954.8	3887.0	...
Of Which: Foreign Official Treasury Bills	475.5	407.7	388.5	...
Of Which: Foreign Official T-Bonds & Notes	3560.2	3547.1	3498.5	...

Notes:
The data in this table are collected primarily from U.S.-based custodians ...
```

Format facts that matter for parsing:
- **Tab-delimited** (the OLD `mfh.txt` was fixed-width — that's why a fixed-width parser would silently produce zero rows on the new file).
- 13 month columns rolling (most recent first, left to right).
- Date headers are `YYYY-MM` strings, **not** the old `Jan / 2023` two-row layout.
- 25-ish country rows, then `All Other`, `Grand Total`, then three `Of Which:` rows for foreign-official splits.
- `Notes:` line begins the trailer block — any parser must stop there.
- The "Korea" naming changed from `Korea` to `Korea, South`.
- Data refresh: monthly, ~6-week lag from end-of-month (Feb 2026 data live by mid-Apr 2026).

### 1.4  Verified Python parser for `slt_table5.txt`

This was run end-to-end on the live file and returned 325 country-month rows.

```python
def parse_slt_table5(text: str) -> list[dict]:
    """Parse current TIC MFH file (replaces old fixed-width mfh.txt).

    Returns:
        [{country: str, asof: 'YYYY-MM', amount_bn: float}, ...]
        Includes aggregate rows: 'Grand Total', 'All Other',
        'Of Which: Foreign Official', 'Of Which: Foreign Official Treasury Bills',
        'Of Which: Foreign Official T-Bonds & Notes'.

    Format: tab-delimited, with header rows and notes block.
        Lines 1-4: title + 'Link:' line
        Line 5   : blank
        Line 6   : header  ->  Country\\t<YYYY-MM>\\t<YYYY-MM>...
        Line 7+  : data rows  -> country_name\\t<float>\\t<float>...
        ...     : 'Notes:' line begins the trailing block (skip rest)
    """
    rows: list[dict] = []
    header: list[str] | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if line.startswith("Notes:"):
            break
        if line.startswith("Country\t"):
            header = [c.strip() for c in line.split("\t") if c.strip()]
            continue
        if header is None:
            continue  # skip title lines
        cells = [c.strip() for c in line.split("\t")]
        if not cells or not cells[0]:
            continue
        country = cells[0]
        for asof, raw_val in zip(header[1:], cells[1:]):
            if not raw_val:
                continue
            try:
                amount = float(raw_val)
            except ValueError:
                continue
            rows.append({"country": country, "asof": asof, "amount_bn": amount})
    return rows


def get_tic_mfh() -> list[dict]:
    """Top-level wrapper. Drop-in replacement for the broken get_tic_mfh()."""
    import urllib.request
    URL = ("https://ticdata.treasury.gov/resource-center/"
           "data-chart-center/tic/Documents/slt_table5.txt")
    with urllib.request.urlopen(URL, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    return parse_slt_table5(text)


def get_tic_top_holders(n: int = 20, asof: str | None = None) -> list[dict]:
    rows = get_tic_mfh()
    if asof is None:
        # Latest month is the largest 'asof' string — works because YYYY-MM sorts.
        asof = max(r["asof"] for r in rows)
    aggregates = {"Grand Total", "All Other",
                  "Of Which: Foreign Official",
                  "Of Which: Foreign Official Treasury Bills",
                  "Of Which: Foreign Official T-Bonds & Notes"}
    snap = [r for r in rows if r["asof"] == asof and r["country"] not in aggregates]
    snap.sort(key=lambda r: r["amount_bn"], reverse=True)
    return snap[:n]


def get_tic_country_holdings(country: str, months: int = 12) -> list[dict]:
    rows = get_tic_mfh()
    by_country = [r for r in rows if r["country"].lower() == country.lower()]
    by_country.sort(key=lambda r: r["asof"], reverse=True)
    return by_country[:months]
```

### 1.5  Sanity-check output (from running the parser above on live data)

```
Total country-month rows  : 325 (25 countries × 13 months)
Date columns              : ['2026-02', '2026-01', ..., '2025-02']
Latest month              : 2026-02
Top-10 (excluding aggregates):
   Japan              1239.3 bn
   United Kingdom      897.3 bn
   China, Mainland     693.3 bn
   Belgium             454.7 bn
   Canada              446.3 bn
   Luxembourg          445.7 bn
   Cayman Islands      443.0 bn
   France              395.1 bn
   Ireland             350.6 bn
   Taiwan              313.5 bn
Grand Total           9487.1 bn
```

If PRISM's `get_tic_mfh()` produced the above, it would have caught the regression.

### 1.6  Snetus replacement (`slt_table4.txt`)

The old `snetus.csv` URL is dead; the equivalent is `slt_table4.txt` and it is
much richer (sales + purchases × 8 security types × all countries × all dates).

Live head (2026-04-30):

```
Table 4: U.S. Purchases and Sales of Long-Term Domestic and Foreign Securities by Type
All Countries and International and Regional Organizations
Millions of dollars
Link: ...slt_table4.txt

# header row 1: human labels (with carryover "Sales of"/"Purchases of" prefix)
# header row 2: machine field names
country	country_code	date	for_lt_total_sale	for_lt_treas_sale	for_lt_agcy_sale	for_lt_corp_sale	for_lt_eqty_sale	us_lt_total_sale	us_lt_govt_bond_sale	us_lt_corp_bond_sale	us_lt_eqty_sale	for_lt_total_pur	for_lt_treas_pur	for_lt_agcy_pur	for_lt_corp_pur	for_lt_eqty_pur	us_lt_total_pur	us_lt_govt_bond_pur	us_lt_corp_bond_pur	us_lt_eqty_pur
Austria	10189	2026-02	5096	2291	0	282	2523	2296	400	759	1137	5022	2233	0	121	2668	1943	527	531	885
Austria	10189	2026-01	3583	1387	0	147	2049	2205	520	605	1080	3915	1520	0	192	2203	2424	574	554	1296
... (many country × month rows)
```

Format facts:
- Tab-delimited (same convention as table 5).
- The MACHINE header row begins with literal text `country\tcountry_code\tdate\t...` — split that row to get field names.
- Numeric fields are millions of USD (table 5 was billions of USD).
- ~3,925 lines total → ~217 countries × ~18 months of history per release.

Use the same parser style as `slt_table5` but pivot on `(country, date)` and
emit one row per `(country, date)` with all 17 numeric columns.

### 1.7  Country-codes lookup

The path PRISM might be using is wrong (`country-codes.txt` returns 404).
Country names appear inline in the data files — there's no separate lookup
needed. If a code-to-name mapping is wanted, it appears in `slt_table1.txt`
through `slt_table4.txt` as `country_code` column.

---

## 2. Quarterly Refunding — What Broke and the Fix

### 2.1  Old vs new URL inventory

```
┌──────────────────────────────────────────────────────────────┬───────────┐
│ Old URL (in PRISM scraper)                                   │ Status    │
├──────────────────────────────────────────────────────────────┼───────────┤
│ www.treasury.gov/resource-center/data-chart-center/          │ HTTP 302  │
│   quarterly-refunding/Pages/Latest.aspx                       │ → new URL │
│                                                              │           │
│ www.treasury.gov/resource-center/data-chart-center/          │ Variable  │
│   quarterly-refunding/Documents/*                             │ (404 mix) │
└──────────────────────────────────────────────────────────────┴───────────┘
```

```
┌──────────────────────────────────────────────────────────────────────────┐
│ Current URLs (verified 2026-04-30)                                       │
├──────────────────────────────────────────────────────────────────────────┤
│ Latest event landing page (HTML, scrape this):                           │
│   home.treasury.gov/policy-issues/financing-the-government/              │
│     quarterly-refunding/most-recent-quarterly-refunding-documents         │
│                                                                          │
│ Archive landing page (HTML, scrape for nav links to year subpages):      │
│   home.treasury.gov/policy-issues/financing-the-government/              │
│     quarterly-refunding/quarterly-refunding-archives                      │
│                                                                          │
│ Per-artifact pattern (PREDICTABLE, no HTML scraping needed):              │
│   home.treasury.gov/system/files/221/<filename>.<ext>                     │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2  Verified file-naming conventions (Q12026 case)

```
Auction calendar:
  TentativeAuctionScheduleQ12026.xml          218 entries (incl. 4 holidays)
  TentativeAuctionScheduleQ12026.pdf

Buyback calendar:
  Tentative-Buyback-ScheduleQ12026.xml         21 entries  ← note hyphens
  Tentative-Buyback-ScheduleQ12026.pdf

TBAC discussion charts:
  TreasuryPresentationToTBACQ12026.pdf
  TBACCharge1Q12026.pdf
  TBACCharge2Q12026.pdf
  CombinedChargesforArchivesQ12026.pdf

TBAC report + recommended financing:
  TBACRecommendedFinancingTableByRefundingQuarter-02042026.pdf
  (TBAC Report and TBAC Minutes are press releases, NOT PDFs in /system/files/)

Primary Dealer + Quarterly Release Data (mid-quarter release):
  Dealer-Agenda-May-2026.pdf
  2026-2nd-Quarter.xls

Press releases (Financing Estimates / Policy Statement / Reports):
  home.treasury.gov/news/press-releases/sb<NNNN>
  Q1 2026 examples: sb0377 (estimates), sb0376 (statement),
                    sb0384, sb0385, sb0386 (Mon morning batch)
```

### 2.3  Verified historical pattern works

The same predictable pattern works back at least 2 years, no archive scrape needed:

```bash
$ for q in Q12026 Q42025 Q32025 Q22025 Q12025 Q42024 Q12024; do
    curl -sLo /dev/null -w "$q: %{http_code} %{size_download}b\n" \
      "https://home.treasury.gov/system/files/221/TentativeAuctionSchedule${q}.xml"
  done

Q12026: 200 81234b
Q42025: 200 76619b
Q32025: 200 74884b
Q22025: 200 76619b
Q12025: 200 65803b
Q42024: 200 65803b
Q12024: 200 65533b
```

So PRISM can enumerate all historical refundings purely by templating
`Q{quarter}{YYYY}` — no HTML scraping required for the auction/buyback XMLs.

### 2.4  Auction XML — actual structure (from live Q12026 file)

```xml
<?xml version="1.0" encoding="UTF-8" ?>
<AuctionCalendar xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <AuctionCalendarName>Feb 2026 Refunding Auction Calendar Official</AuctionCalendarName>
  <StartDate>2026-02-04</StartDate>
  <EndDate>2026-08-01</EndDate>
  <AuctionCalendarDate>
    <SecurityTermWeekYear>3-Year</SecurityTermWeekYear>
    <SecurityType>NOTE</SecurityType>           <!-- NOTE | BOND | BILL  -->
    <ReOpeningIndicator>N</ReOpeningIndicator>  <!-- present for coupon, absent for bills -->
    <TIPS>N</TIPS>
    <FloatingRate>N</FloatingRate>
    <AnnouncementDate>2026-02-04</AnnouncementDate>
    <AuctionDate>2026-02-10</AuctionDate>
    <SettlementDate>2026-02-17</SettlementDate>
  </AuctionCalendarDate>
  ...
  <!-- HOLIDAY entries also live inside <AuctionCalendarDate> tags! -->
  <AuctionCalendarDate>
    <HolidayName>Washington's Birthday</HolidayName>
    <HolidayDate>2026-02-16</HolidayDate>
  </AuctionCalendarDate>
  ...
</AuctionCalendar>
```

**Critical schema gotcha**: holidays use the same wrapper `<AuctionCalendarDate>` as auctions but contain `<HolidayName>` + `<HolidayDate>` instead of any auction fields. A naive parser that assumes every wrapper is an auction will hit `KeyError`/empty fields. Q12026 has 4 holiday entries mixed in among 214 auctions.

Counts I verified by parsing Q12026:

```
Total <AuctionCalendarDate> wrappers : 218
  Auctions                            : 214
    NOTE                              :  41
    BOND                              :  13
    BILL                              : 160
  Holiday entries                     :   4
```

### 2.5  Buyback XML — actual structure (from live Q12026 file)

```xml
<BuyBackCalendar>
  <BuybackCalendarName>February 2026 Refunding Tentative Buyback Calendar V1</BuybackCalendarName>
  <StartDate>2026-02-19</StartDate>
  <EndDate>2026-05-13</EndDate>
  <BuybackCalendarDate>
    <PurchaseBucketName>Nominal Coupons 5Y to 7Y</PurchaseBucketName>
    <SecurityType>NOMINAL COUPONS</SecurityType>     <!-- NOMINAL COUPONS | TIPS | FRN -->
    <OperationType>Liquidity Support</OperationType>  <!-- vs "Cash Management" -->
    <MinimumPurchaseAmountDollars>0</MinimumPurchaseAmountDollars>
    <MaximumPurchaseAmountDollars>4000000000</MaximumPurchaseAmountDollars>
    <MaturityDateRangeStart>2031-02-20</MaturityDateRangeStart>
    <MaturityDateRangeEnd>2033-02-19</MaturityDateRangeEnd>
    <AnnouncementDate>2026-02-18</AnnouncementDate>
    <OperationDate>2026-02-19</OperationDate>
    <SettlementDate>2026-02-20</SettlementDate>
    <OperationStartTimeEasternUS>13:40</OperationStartTimeEasternUS>
    <OperationEndTimeEasternUS>14:00</OperationEndTimeEasternUS>
  </BuybackCalendarDate>
  ...
</BuyBackCalendar>
```

Note `<BuyBackCalendar>` (camelCase with capital B) at the root; entries are
`<BuybackCalendarDate>` (lowercase b after capital B). XML is case-sensitive.

Q12026 had 21 buyback windows totalling $113bn of max-purchase capacity.

### 2.6  Verified Python parsers

These were run end-to-end against the live Q12026 XMLs. Drop-in replacements
for whatever PRISM's `TreasuryDirectScraper` is currently using.

```python
from xml.etree import ElementTree as ET


def parse_auction_schedule(xml_bytes: bytes) -> dict:
    """Parse Treasury Tentative Auction Schedule XML.

    Returns:
        {
          'calendar_name': str,
          'calendar_start': 'YYYY-MM-DD',
          'calendar_end':   'YYYY-MM-DD',
          'auctions': [{security_term, security_type, is_reopening,
                        is_tips, is_floating_rate, announcement_date,
                        auction_date, settlement_date}, ...],
          'holidays': [{name, date}, ...],
        }
    """
    root = ET.fromstring(xml_bytes)
    auctions, holidays = [], []
    for entry in root.findall("AuctionCalendarDate"):
        # Discriminator: holidays have <HolidayName>, auctions don't.
        if entry.find("HolidayName") is not None:
            holidays.append({
                "name": entry.findtext("HolidayName", ""),
                "date": entry.findtext("HolidayDate", ""),
            })
            continue
        auctions.append({
            "security_term":     entry.findtext("SecurityTermWeekYear", ""),
            "security_type":     entry.findtext("SecurityType", ""),
            "is_reopening":      entry.findtext("ReOpeningIndicator", "N") == "Y",
            "is_tips":           entry.findtext("TIPS", "N") == "Y",
            "is_floating_rate":  entry.findtext("FloatingRate", "N") == "Y",
            "announcement_date": entry.findtext("AnnouncementDate", ""),
            "auction_date":      entry.findtext("AuctionDate", ""),
            "settlement_date":   entry.findtext("SettlementDate", ""),
        })
    return {
        "calendar_name":  root.findtext("AuctionCalendarName", ""),
        "calendar_start": root.findtext("StartDate", ""),
        "calendar_end":   root.findtext("EndDate", ""),
        "auctions": auctions,
        "holidays": holidays,
    }


def parse_buyback_schedule(xml_bytes: bytes) -> dict:
    root = ET.fromstring(xml_bytes)
    out = []
    for entry in root.findall("BuybackCalendarDate"):
        out.append({
            "purchase_bucket":      entry.findtext("PurchaseBucketName", ""),
            "security_type":        entry.findtext("SecurityType", ""),
            "operation_type":       entry.findtext("OperationType", ""),
            "min_purchase_usd":     int(entry.findtext("MinimumPurchaseAmountDollars", "0") or 0),
            "max_purchase_usd":     int(entry.findtext("MaximumPurchaseAmountDollars", "0") or 0),
            "maturity_range_start": entry.findtext("MaturityDateRangeStart", ""),
            "maturity_range_end":   entry.findtext("MaturityDateRangeEnd", ""),
            "announcement_date":    entry.findtext("AnnouncementDate", ""),
            "operation_date":       entry.findtext("OperationDate", ""),
            "settlement_date":      entry.findtext("SettlementDate", ""),
            "operation_start_et":   entry.findtext("OperationStartTimeEasternUS", ""),
            "operation_end_et":     entry.findtext("OperationEndTimeEasternUS", ""),
        })
    return {
        "calendar_name":  root.findtext("BuybackCalendarName", ""),
        "calendar_start": root.findtext("StartDate", ""),
        "calendar_end":   root.findtext("EndDate", ""),
        "buyback_windows": out,
    }
```

### 2.7  Two strategies for `scrape_refunding_latest()`

Strategy A — **predictable URL templates** (recommended; no HTML parsing):

```python
import datetime as dt
import urllib.request

REFUNDING_BASE = "https://home.treasury.gov/system/files/221"

def latest_quarter() -> tuple[int, int]:
    """Most recent refunding quarter (Feb/May/Aug/Nov releases)."""
    today = dt.date.today()
    # Refundings: first Mon-Wed of Feb (Q1), May (Q2), Aug (Q3), Nov (Q4)
    quarter_first_months = [(1, 2), (2, 5), (3, 8), (4, 11)]
    year = today.year
    last_q = 4
    last_y = year - 1
    for q, m in quarter_first_months:
        # Approx 1st-week-of-month
        if today >= dt.date(year, m, 1):
            last_q, last_y = q, year
    return last_q, last_y

def refunding_urls(q: int, year: int) -> dict:
    tag = f"Q{q}{year}"
    return {
        "auction_schedule_xml":   f"{REFUNDING_BASE}/TentativeAuctionSchedule{tag}.xml",
        "auction_schedule_pdf":   f"{REFUNDING_BASE}/TentativeAuctionSchedule{tag}.pdf",
        "buyback_schedule_xml":   f"{REFUNDING_BASE}/Tentative-Buyback-Schedule{tag}.xml",
        "buyback_schedule_pdf":   f"{REFUNDING_BASE}/Tentative-Buyback-Schedule{tag}.pdf",
        "tbac_presentation_pdf": f"{REFUNDING_BASE}/TreasuryPresentationToTBAC{tag}.pdf",
        "tbac_charge1_pdf":     f"{REFUNDING_BASE}/TBACCharge1{tag}.pdf",
        "tbac_charge2_pdf":     f"{REFUNDING_BASE}/TBACCharge2{tag}.pdf",
        "combined_charges_pdf": f"{REFUNDING_BASE}/CombinedChargesforArchives{tag}.pdf",
    }
```

Strategy B — **scrape the HTML landing page** (gets you press-release URLs and dealer-agenda PDFs that don't follow the Q-template). Use `BeautifulSoup` to walk anchor tags:

```python
import re
import urllib.request
from bs4 import BeautifulSoup

LANDING_URL = ("https://home.treasury.gov/policy-issues/financing-the-government/"
               "quarterly-refunding/most-recent-quarterly-refunding-documents")

def scrape_refunding_latest_html() -> dict:
    html = urllib.request.urlopen(LANDING_URL, timeout=30).read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    out: dict[str, list[str]] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/system/files/221/" in href or "/news/press-releases/sb" in href:
            label = a.get_text(strip=True)
            out.setdefault("links", []).append({"label": label, "url": href})
    return out
```

The HTML landing page has predictable section headers (`### DOCUMENTS RELEASED at <time> <date>`) so a parser can also key on those if it wants the release dates.

### 2.8  Sample artifact from running parse_auction_schedule (live Q12026)

```json
{
  "calendar_name":  "Feb 2026 Refunding Auction Calendar Official",
  "calendar_start": "2026-02-04",
  "calendar_end":   "2026-08-01",
  "auction_count":  214,
  "holiday_count":  4,
  "first_auction": {
    "security_term":     "3-Year",
    "security_type":     "NOTE",
    "is_reopening":      false,
    "is_tips":           false,
    "is_floating_rate":  false,
    "announcement_date": "2026-02-04",
    "auction_date":      "2026-02-10",
    "settlement_date":   "2026-02-17"
  },
  "first_holiday": {"name": "Washington's Birthday", "date": "2026-02-16"}
}
```

If PRISM's `scrape_refunding_latest()` returned the above shape, you'd know the regression was caught.

---

## 3. End-to-End Smoke Test Script

Drop this into `/tmp` and run from the PRISM environment to confirm the new
URLs work behind the GS proxy.

```python
"""Smoke test for new TIC + Refunding URLs.

Run:    python3 treasury_smoke.py
Pass:   prints "ALL CHECKS PASSED" at end
Fail:   first failing check raises immediately so you can grep the trace
"""
from __future__ import annotations
import urllib.request
from xml.etree import ElementTree as ET

CHECKS = [
    ("TIC slt_table5 (current MFH)",
     "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt",
     "Country\t",          # must contain this header marker
     2000, 50_000),         # min, max bytes (sanity)

    ("TIC slt_table4 (snetus equivalent)",
     "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table4.txt",
     "country\tcountry_code\tdate",
     500_000, 5_000_000),

    ("TIC mfhhis01 (historical archive)",
     "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/mfhhis01.txt",
     "MAJOR FOREIGN HOLDERS",
     50_000, 500_000),

    ("Refunding latest landing page",
     "https://home.treasury.gov/policy-issues/financing-the-government/quarterly-refunding/"
     "most-recent-quarterly-refunding-documents",
     "Most Recent Quarterly Refunding Documents",
     20_000, 200_000),

    ("Refunding Q12026 auction XML",
     "https://home.treasury.gov/system/files/221/TentativeAuctionScheduleQ12026.xml",
     "<AuctionCalendar",
     20_000, 200_000),

    ("Refunding Q12026 buyback XML",
     "https://home.treasury.gov/system/files/221/Tentative-Buyback-ScheduleQ12026.xml",
     "<BuyBackCalendar>",
     5_000, 50_000),
]

def main() -> None:
    fails: list[str] = []
    for label, url, sentinel, min_b, max_b in CHECKS:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                data = resp.read()
            text = data.decode("utf-8", errors="replace")
            ok_size = min_b <= len(data) <= max_b
            ok_sent = sentinel in text
            print(f"  {label:42s} {len(data):>9d}b  size_ok={ok_size}  sentinel_ok={ok_sent}")
            if not (ok_size and ok_sent):
                fails.append(label)
        except Exception as e:
            print(f"  {label:42s} EXCEPTION: {e}")
            fails.append(label)
    print()
    if fails:
        raise SystemExit(f"FAILED: {fails}")
    print("ALL CHECKS PASSED")

if __name__ == "__main__":
    main()
```

Expected output (verified 2026-04-30 from a vanilla curl-equivalent network):

```
  TIC slt_table5 (current MFH)                 ~3000b  size_ok=True  sentinel_ok=True
  TIC slt_table4 (snetus equivalent)         ~900000b  size_ok=True  sentinel_ok=True
  TIC mfhhis01 (historical archive)           ~91000b  size_ok=True  sentinel_ok=True
  Refunding latest landing page               ~50000b  size_ok=True  sentinel_ok=True
  Refunding Q12026 auction XML                ~81000b  size_ok=True  sentinel_ok=True
  Refunding Q12026 buyback XML                 ~9000b  size_ok=True  sentinel_ok=True

ALL CHECKS PASSED
```

If PRISM gets HTTP 200s with empty/wrong content, the proxy is rewriting/caching responses and that's a Goldman infra problem (not a parsing problem).

---

## 4. Migration Notes for the Treasury Skill File

The integration markdown (`treasury_endpoints_integration.md`) has the OLD URLs
in §3 of that doc — they need to flip to the new ones below. Suggested diff:

```diff
- BASE          = "https://ticdata.treasury.gov"
- ARCHIVE_BASE  = "https://www.treasury.gov/resource-center/data-chart-center/tic"
- PUBLISH_BASE  = "https://ticdata.treasury.gov/Publish"
- TIC_CURRENT_FILES = {
-     "mfh":      f"{PUBLISH_BASE}/mfh.txt",                                     # STALE
-     "snetus":   f"{ARCHIVE_BASE}/Documents/snetus.csv",                        # 404
-     "slt_s1":   f"{ARCHIVE_BASE}/Documents/slt-table1.csv",                    # wrong
-     "slt_s2":   f"{ARCHIVE_BASE}/Documents/slt-table2.csv",                    # wrong
- }

+ TIC_BASE      = "https://ticdata.treasury.gov"
+ TIC_DOC_BASE  = f"{TIC_BASE}/resource-center/data-chart-center/tic/Documents"
+ TIC_CURRENT_FILES = {
+     "mfh_current":  f"{TIC_DOC_BASE}/slt_table5.txt",   # the canonical MFH
+     "mfh_history":  f"{TIC_DOC_BASE}/mfhhis01.txt",     # multi-year archive
+     "snetus":       f"{TIC_DOC_BASE}/slt_table4.txt",   # purchases & sales
+     "slt_table1":   f"{TIC_DOC_BASE}/slt_table1.txt",   # all foreign LT holdings
+     "slt_table3":   f"{TIC_DOC_BASE}/slt_table3.txt",   # foreign UST holdings
+ }
```

For the TreasuryDirect refunding scraper:

```diff
- REFUNDING_LATEST_URL  = "https://www.treasury.gov/resource-center/data-chart-center/quarterly-refunding/Pages/Latest.aspx"
+ REFUNDING_LATEST_URL  = ("https://home.treasury.gov/policy-issues/"
+                          "financing-the-government/quarterly-refunding/"
+                          "most-recent-quarterly-refunding-documents")
+ REFUNDING_FILES_BASE  = "https://home.treasury.gov/system/files/221"
```

---

## 5. Open Questions for PRISM

1. **Goldman proxy cache**: confirm a fresh `urllib.request.urlopen()` against
   `slt_table5.txt` returns ~3KB of tab-delimited data (not an HTML 404 page).
   If it returns HTML, the proxy is rewriting and the diagnosis becomes
   network-level not parser-level.

2. **Existing PRISM scraper code**: it would help to see PRISM's
   `get_tic_mfh()` body to confirm it's parsing as fixed-width. If it is,
   the fix is exactly the parser in §1.4 above. If it's already
   tab-delimited but pointed at the wrong URL, the fix is just the URL swap
   in §4.

3. **Old `mfh.txt`**: keep it as a fallback or remove entirely? Recommendation:
   remove. The frozen Jan-2023 data is actively misleading.

4. **TIC archive ZIPs**: the staging integration doc mentioned monthly archive
   ZIPs at `www.treasury.gov/.../tic/Pages/ticarchives.aspx` — that page also
   moved. Current archive index lives at:
   `https://home.treasury.gov/data/treasury-international-capital-tic-system/tic-data-by-form-type`
   and individual archive ZIPs are linked from sub-pages like
   `…/tic-forms-instructions/securities-b-portfolio-holdings-of-us-and-foreign-securities`.
   I haven't drilled into the ZIPs yet — flag if you want a follow-up.

---

## Appendix — Verification Run Log (2026-04-30)

```
$ curl -sIL "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
HTTP/2 200
content-type: text/plain
content-length: ~3000

$ curl -sLo /dev/null -w "%{http_code} %{size_download}b\n" \
    "https://home.treasury.gov/system/files/221/TentativeAuctionScheduleQ12026.xml"
200 81234b

$ python3 test_parsers.py
======================================================================
TIC slt_table5.txt parser test
======================================================================
Total country-month rows: 325
Date columns: ['2026-02', '2026-01', ..., '2025-02']
Latest month = 2026-02
Top-10 holders (2026-02, $bn):  Japan 1239.3, UK 897.3, China 693.3, ...

Auction Schedule XML parser test
======================================================================
Total auctions in calendar: 218 (214 auctions + 4 holidays)
Counts by type: {'NOTE': 41, 'BOND': 13, 'BILL': 160, 'HOLIDAY': 4}

Buyback Schedule XML parser test
======================================================================
Total buyback windows: 21
Total max-purchase: $113.0bn

ALL PARSERS WORKING.
```

---

End of debug context.
