Build an NFP-style dashboard with 4 KPI tiles (Headline NFP, Private Payrolls, Unemployment Rate, AHE YoY), a Release Summary table, and an "AHE by sector" horizontal bar chart showing wage levels in $/hr per sector — the pipeline pulls AHE-by-sector data from haver with only a single 6-month lag column. Then redesign the AHE-by-sector chart to show wage growth (YoY) versus the corresponding PCE component for each sector, with a lag toggle for 3 / 6 / 9 / 12 months. Let me know if frictions.

---

Build a rates_monitor dashboard with a market_data pipeline (us_2y, us_10y, us_30y EOD) and 3 curve charts in a row. Then add a 5y rolling realized vol chart for each tenor (us_2y, us_10y, us_30y) below the existing curve charts. Let me know if frictions.

---

Build an NFP-style dashboard with a Wages & Inflation chart showing AHE by sector. Then redesign the chart with multi-lag PCE-comparison lines (3 / 6 / 9 / 12 month toggle) — this requires editing pull_data.py to add multi-lag columns. Finally, undo that redesign and revert the dashboard to its pre-redesign state using the §2.6 versioning chain (Path 1 of recipes.md §5): list scripts/versions/, identify the pre-redesign K, copy pull_data_vK.py + build_vK.py over the live paths, persist as v(N+1), re-run Tools 1+2+3+4. The chain should stay monotonic and the audit clean. Let me know if frictions.

---

Build a Fed Scenario Tool dashboard with two tabs: Tab 1 (Scenario Builder) carrying a `widget: tool` taking FOMC scenario inputs, Tab 2 (Visualization) showing 5 chart widgets. Then simulate a botched edit by directly overwriting manifest_template.json with a fresh dict containing only Tab 2 — wiping the Scenario Builder tool tab. Now restore the Scenario Builder tab: walk through the recovery paths available, pick one, and apply it. Let me know if frictions.

---

Build a US versus Europe rates dashboard with two side-by-side multi-line charts in long form: tab one shows US 2Y / 5Y / 10Y / 30Y curve levels colored by tenor; tab two shows the same curve for German bunds. Add a thesis card above each tab summarising the steepening regime in each region. Let me know if frictions.

---

Build a TIPS RV screener dashboard. Each row is a TIPS issue showing current Z-spread, 5y range, percentile, and z-score. Render as a `bullet` chart per the recipes RV pattern. Add a slider filter for max maturity year that filters both the bullet chart and a sibling table. Let me know if frictions.

---

Build a curve-monitor dashboard with a thesis card and a watch card in the top row, then a 2-up multi-line chart of curve level alongside the computed 2s10s spread (in basis points). Use the manifest-level `compute` block to derive the 2s10s column from the `rates` dataset rather than computing it in `build.py`. Let me know if frictions.
