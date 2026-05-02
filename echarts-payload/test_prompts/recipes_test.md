Build a "rates monitor" dashboard with the canonical layout: 2y/5y/10y/30y curve chart plus 2s10s spread plus the latest-level KPI row. Use `manifest_template` and `populate_template` to demonstrate the template-fill flow. Let me know if frictions.

---

Build a "macro release calendar" dashboard pulling from Haver and showing today's releases at the top, this week's below, and a stat_grid of last-print surprises by region. Let me know if frictions.

---

Build a "cross-asset wrap" dashboard with a 4-tab layout (rates / FX / equity / commodities), each tab showing 2 charts plus a KPI row plus a markdown commentary widget. Let me know if frictions.

---

Build an "FDIC bank screener" dashboard wiring `pull_fdic_data` results to a filter-driven table plus a peer-comparison chart. Use `save_artifact()` per Rule 1 since FDIC data does not auto-save. Let me know if frictions.

---

Build a dashboard with a `correlation_matrix` driving a click-through drawer that reveals the underlying scatter and rolling-correlation series for each cell. Use it to explore SPX vs cross-asset correlations over the last 3 years. Let me know if frictions.

---

Build a "FOMC scoreboard" dashboard combining the SEP dot plot (custom chart), market-implied terminal rate (gauge widget), Fed-funds futures path (multi_line), and a methodology note explaining the construction. Let me know if frictions.

---

Build the smallest viable single-tab persistent dashboard slice (per Rule 8) with one chart plus one KPI plus a methodology note, fully Tool 1-2-3 atomic. After confirming the slice rendering at the portal URL, propose the next slice. Let me know if frictions.
