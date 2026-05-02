Compile a dashboard with a `tool` widget that takes one `scalar` input (a yield-shift in bps) and outputs a `stat` showing the resulting bond price impact for a 10y Treasury. Let me know if frictions.

---

Compile a dashboard with a `tool` widget that takes a `sweep` input (a range of dates) and outputs a `series` showing the rolling correlation between US 10y yields and the trade-weighted USD over the swept window. Let me know if frictions.

---

Compile a dashboard with a `tool` widget that takes an `expression` input (a custom formula referencing dataset columns) and outputs a `kpi` tile showing the evaluated expression with a delta vs the prior period. Let me know if frictions.

---

Compile a dashboard with a `tool` widget that takes a `matrix` input (a 4x4 currency cross-rate matrix) and outputs a `table` showing the implied cross-rates plus a `distribution` showing the percentile of each pair vs its 5y history. Let me know if frictions.

---

Compile a dashboard with a `tool` widget producing a `stat_grid` output (multiple KPIs in a single grid layout) from a single computation. Let me know if frictions.

---

Compile a dashboard with a `tool` widget that produces a `param` output, then have that param feed into a sibling chart's filter. Confirm the parameter wires through correctly when the user changes the tool input. Let me know if frictions.

---

Compile a dashboard with a `tool` widget that requires multiple input kinds at once (one scalar plus one expression) and emits multiple outputs (one scalar plus one series). Verify the I/O contract surfaces correctly to the user. Let me know if frictions.
