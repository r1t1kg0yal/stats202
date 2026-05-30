Build an NFP-style dashboard with 4 KPI tiles (Headline NFP, Private Payrolls, Unemployment Rate, AHE YoY), a Release Summary table, and an "AHE by sector" horizontal bar chart showing wage levels in $/hr per sector — `pull_data.py` PULLS dict has one entry (`pull_ahe_sector`) that calls `pull_haver_data` for AHE-by-sector with a single 6-month lag column. Then redesign the AHE-by-sector chart to show wage growth (YoY) versus the corresponding PCE component for each sector, with a lag toggle for 3 / 6 / 9 / 12 months — extend the existing `pull_ahe_sector` function to add the additional lag columns + add a new `derive_ahe_pce_pairs` transform to `build.py` `TRANSFORMS`. Let me know if frictions.

---

Build a `rates_monitor` dashboard with a single `pull_rates` function in `PULLS` (us_2y, us_10y, us_30y EOD via `pull_market_data`) and 3 curve charts in a row. Then add a 5y rolling realized vol chart for each tenor below the existing curve charts — derive the vol columns via a new `derive_realized_vol` transform in `build.py` `TRANSFORMS` (no `pull_data.py` change needed; this is a build-time derivation per recipes.md §3). Let me know if frictions.

---

Build an NFP-style dashboard with a Wages & Inflation chart showing AHE by sector (one `pull_ahe_sector` function in `PULLS`). Then redesign the chart with multi-lag PCE-comparison lines (3 / 6 / 9 / 12 month toggle) — this requires editing `pull_data.py` to add a new `pull_pce_lagged` function to `PULLS` and a `derive_lag_pairs` transform to `build.py` `TRANSFORMS`. Finally, undo that redesign and revert the dashboard to its pre-redesign state via Recipe 6 (hub §G): re-edit `pull_data.py` and `build.py` back to the prior shape using the bytes from chat history, then `build_dashboard(folder)` to verify. Let me know if frictions.

---

Build a Fed Scenario Tool dashboard with two tabs: Tab 1 (Scenario Builder) carrying a `widget: tool` taking FOMC scenario inputs, Tab 2 (Visualization) showing 5 chart widgets. Then simulate a botched edit by directly overwriting `manifest_template.json` with a fresh dict containing only Tab 2 — wiping the Scenario Builder tool tab. Now restore the Scenario Builder tab via Recipe 6 (hub §G): re-author the missing tab + tool def from chat history via raw JSON CRUD per hub §C, then `build_dashboard(folder)` to verify. Let me know if frictions.

---

Build a US versus Europe rates dashboard with two `PULLS` entries (`pull_us_curve` via `pull_market_data` for US 2Y / 5Y / 10Y / 30Y, `pull_de_curve` via `pull_haver_data` for German bunds) and two side-by-side multi-line charts in long form: tab one shows US curve levels colored by tenor; tab two shows the same curve for German bunds. Add a thesis card above each tab summarising the steepening regime in each region. Let me know if frictions.

---

Build a TIPS RV screener dashboard. One `pull_tips` function in `PULLS` (via `pull_market_data` for current Z-spread) plus one `derive_tips_rv` transform in `TRANSFORMS` (computes 5y range + percentile + z-score from history). Each row is a TIPS issue rendered as a `bullet` chart per the recipes RV pattern. Add a slider filter for max maturity year that filters both the bullet chart and a sibling table. Let me know if frictions.

---

Build a curve-monitor dashboard with a thesis card and a watch card in the top row, then a 2-up multi-line chart of curve level alongside the computed 2s10s spread (in basis points). One `pull_rates` function in `PULLS` (us_2y + us_10y EOD); the 2s10s spread is derived in `build.py` via a `derive_spread` transform (recipes.md §3) — the manifest references the derived `spread` dataset by key. Let me know if frictions.
