Build a screener-style dashboard for ~30 corporate bonds. The main table shows ticker, rating, spread, and ytm. Clicking any row opens a popup with a 24-month price history line chart plus a small stat strip showing the bond's current vs 1Y range. Let me know if frictions.

---

Build an NFP-style dashboard with a Release Summary table on Tab 1 (5 rows: NFP / Unemployment / AHE / Private Payrolls / Avg Hours, each pulled from haver as one row) plus a row_click popup configured with `row_key: metric` and `filter_field: metric` to show 24-month historical timeseries per clicked row. Audit whether the popup chart's dataset shape supports this filtering — if not, surface what data-structure change is needed before shipping. Let me know if frictions.

---

Build an NFP-style dashboard with two tabs: Tab 1 carrying a Release Summary table with a row_click popup showing 24-month historical timeseries per clicked row; Tab 3 carrying a Birth-Death Adjustment trend chart with actual + 3M / 6M / 12M moving-average series. Implement legend click-to-toggle on each MA series for the inline chart on Tab 3, then mirror the same toggle behavior in the popup chart that opens from Tab 1's row_click. Let me know if frictions.

---

Build a curve dashboard opening with three markdown widgets in the top row: a thesis card ("the curve is bull-steepening for the third session"), a watch card ("levels to monitor: 4.10% 10Y, 50dma; 2s10s out of inversion"), and a risk card ("stop-out: a hot CPI print would invalidate"). Each renders as a tinted semantic card with the appropriate left-edge stripe. Let me know if frictions.

---

Build a corporate bond drill-down dashboard. The main table shows ~50 issuers with rating, spread, ytm, and duration. Clicking a row opens a wide drill-down popup containing: a stat strip (price / YTM / mod duration / DV01), a markdown summary template that pulls the issuer name and rating into the prose, an embedded 180-day price line chart filtered to the clicked CUSIP, and a sub-table of recent events for that issuer. Let me know if frictions.

---

Build a rates monitor with a headline strip layout: a row of 4 KPI tiles (2Y, 10Y, 2s10s in bp, MOVE index) each with sparkline + delta vs prev, then a 12-wide stat_grid below carrying 8 stats (today's range, weekly Δ, monthly Δ, YTD Δ, 1Y high, 1Y low, percentile rank for 2Y, percentile rank for 10Y). Let me know if frictions.

---

Build a quarterly earnings pivot dashboard over a long-form dataset (sector, region, quarter, eps_growth, revenue_growth, margin). Let the user repivot by row dim (sector / region / ticker), col dim (quarter), value (eps_growth / revenue_growth / margin), aggregator (mean / median / sum). Apply a diverging color scale around zero and show row + column totals. Let me know if frictions.
