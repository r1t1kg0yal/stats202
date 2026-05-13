Build a small rates dashboard with 3 distinct `PULLS` entries feeding 5+ widgets across 2 tabs: `pull_rates` (market_data for us_2y, us_10y EOD), `pull_cpi` (haver for core PCE JCXFE@USECON + headline CPI CUUR0000SA0@USECON), `pull_labor` (FRED for UNRATE). Once the build is live, walk me through the dashboard's data flow using the DEEP GLANCE script from hub §F.2: print pipeline → CSV stem → dataset_key → consuming widgets, plus the `PULLS` keys and `TRANSFORMS` list. Let me know if frictions.

---

Build a rates dashboard with a single `pull_rates` function in `PULLS` producing us_2y, us_5y, us_10y, us_30y EOD coordinates feeding a 4-line curve chart and per-tenor KPI tiles. Then, without touching `pull_data.py`, add a histogram of the us_10y daily yield distribution as a new chart in the bottom row — the `rates_eod` CSV already has the column, so this is Step 1 of the reuse ladder (manifest-only edit per hub §C). Let me know if frictions.

---

Build a rates dashboard with a `pull_rates` function in `PULLS` (us_2y, us_10y EOD) and a 2-up curve chart. Then add a 5Y curve chart alongside, requiring you to EXTEND the existing `pull_rates` body (Step 2 of the reuse ladder per hub §D) — surgically edit the function's `coordinates` list to add `'IR_USD_Swap_5Y_Rate'`, then `run_pull(folder, 'rates')` to verify the new column lands. Let me know if frictions.

---

Build a rates dashboard with a `pull_rates` function in `PULLS` (us_2y, us_10y EOD) and a 2-up curve chart. Then add a section showing FDIC bank-financials for GS Bank (FDIC cert 33124) — Step 3 of the reuse ladder per hub §D: add a new `pull_gs_bank` function to `PULLS` using `fdic_client.get(...)` + `save_artifact(name='gs_bank', ...)`, then `run_pull(folder, 'gs_bank')` to verify the CSV lands. Render the result as a table of the last 8 quarters with key call-report metrics (assets, deposits, net interest margin, return on assets). Let me know if frictions.

---

Build a rates dashboard with a `pull_rates` function in `PULLS` producing us_2y, us_5y, us_10y EOD coordinates feeding 5+ widgets — at minimum a 3-line curve chart, a 2s10s spread chart, a us_2y KPI tile, a us_10y KPI tile, and a curve table. Then walk through what would need to change in `pull_data.py` + `build.py` `TRANSFORMS` + the manifest to remove the us_2y series entirely (no charts, no KPIs, nothing that uses 2Y rates). Confirm via the DEEP GLANCE pipeline-graph (hub §F.2) that no other widget would silently break BEFORE applying the changes. Let me know if frictions.

---

Build a rates dashboard with a `pull_rates` function in `PULLS` (us_2y, us_10y EOD) and a 2-up curve chart. Then surgically edit `pull_data.py` to add a new `pull_macro` function pulling unemployment rate (LR@USECON) and core PCE (JCXFE@USECON) via `pull_haver_data`, plus add the `'macro'` entry to the `PULLS` dict, plus add at least one chart consuming the new dataset. Use the §D pattern (READ → MUTATE → WRITE with a unique anchor + `assert new_src != src`) — never re-emit the whole script as a fresh string. Let me know if frictions.

---

Build a rates dashboard with a single `pull_rates` function in `PULLS` (us_2y, us_10y EOD) and a 2-up curve chart, then add a new `pull_macro` function (LR@USECON, JCXFE@USECON) plus a chart consuming it. Once the edit is applied, run the §F.2 DEEP GLANCE script to verify the post-edit state: every `PULLS` entry corresponds to a CSV in `data/`, every `manifest.datasets` key has a matching CSV stem, no pre-existing pipeline's column set was silently dropped, the `TRANSFORMS` list is intact, and `build_dashboard(folder)` recompiles cleanly against current data. Let me know if frictions.
