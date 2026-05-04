Build a small rates dashboard with 3 distinct pipelines feeding 5+ widgets across 2 tabs: one market_data pipeline (us_2y, us_10y EOD), one haver pipeline (core PCE JCXFE@USECON + headline CPI CUUR0000SA0@USECON named `cpi`), one FRED pipeline (UNRATE named `labor`). Once the build is live, walk me through the dashboard's data flow: print the graph as a table — pipeline → CSV stem → dataset_key → consuming widgets. Let me know if frictions.

---

Build a rates dashboard with a single market_data pipeline producing us_2y, us_5y, us_10y, us_30y EOD coordinates feeding a 4-line curve chart and per-tenor KPI tiles. Then, without touching pull_data.py, add a histogram of the us_10y daily yield distribution as a new chart in the bottom row. Let me know if frictions.

---

Build a rates dashboard with a market_data pipeline producing us_2y and us_10y EOD coordinates and a 2-up curve chart. Then add a 5Y curve chart alongside, requiring you to extend (not duplicate) the existing rates pipeline rather than spawn a new one. Let me know if frictions.

---

Build a rates dashboard with a market_data pipeline (us_2y, us_10y EOD) and a 2-up curve chart. Then add a section showing FDIC bank-financials for GS Bank (FDIC cert 33124) — a table of the last 8 quarters with key call-report metrics (assets, deposits, net interest margin, return on assets). Let me know if frictions.

---

Build a rates dashboard with a market_data pipeline producing us_2y, us_5y, us_10y EOD coordinates feeding 5+ widgets — at minimum a 3-line curve chart, a 2s10s spread chart, a us_2y KPI tile, a us_10y KPI tile, and a curve table. Then walk through what would need to change in pull_data.py + build.py + the manifest to remove the us_2y series entirely (no charts, no KPIs, nothing that uses 2Y rates), and confirm no other widget would silently break before applying the changes. Let me know if frictions.

---

Build a rates dashboard with a market_data pipeline (us_2y, us_10y EOD) and a 2-up curve chart. Then edit pull_data.py to add a new haver-data pipeline pulling unemployment rate (LR@USECON) and core PCE (JCXFE@USECON) named `macro`, plus add at least one chart consuming the new dataset. Re-author the full pull_data.py script end-to-end so all existing pipelines remain intact — don't append the new pipeline as an inline delta. Let me know if frictions.

---

Build a rates dashboard with a single market_data pipeline (us_2y, us_10y EOD) and a 2-up curve chart, then re-author pull_data.py + build.py to add a new haver-data `macro` pipeline (LR@USECON, JCXFE@USECON) plus a chart consuming it. Once the edit is applied, run the full 8-step session-folder health check: confirm both scripts parse, the pull runs end-to-end, the new + existing CSVs land at data/<stem>.csv, the build runs end-to-end, the folder audit passes, every manifest dataset_key has a matching CSV stem, no pre-existing pipeline's column set was silently dropped, AND the §2.6 version chain integrity holds — both scripts/versions/pull_data_v2.py and scripts/versions/build_v2.py exist (the post-edit coupled bump), the live scripts/<name>.py is byte-identical to its v2 snapshot, and manifest.metadata.script_version == 2. Let me know if frictions.
