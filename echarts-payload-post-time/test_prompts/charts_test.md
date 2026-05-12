Build a US 10Y yield dashboard with a line chart showing daily yields since 2010, annotated with vlines at major regime changes (2015 lift-off, 2020 COVID, 2022 hiking cycle start). Add an hline at the Fed's 2% inflation target equivalent for context. Let me know if frictions.

---

Build a Big Tech capex dashboard. Multi-line chart with capex per company (AAPL, MSFT, GOOG, META, AMZN) where solid lines are actuals and dashed lines are GS analyst estimates — use `strokeDash` to differentiate the two states. Add a sibling chart showing capex year-over-year growth on a different y-axis using `dual_axis_series`. Let me know if frictions.

---

Build a cross-asset correlation dashboard using a `correlation_matrix` chart over US 2Y / 5Y / 10Y / 30Y / S&P 500 / DXY / WTI / gold daily returns since 2018. Initial view: 63-day rolling Pearson on percent changes. Let me know if frictions.

---

Build an exploratory scatter dashboard for the S&P 500 universe with `scatter_studio`. Whitelisted x columns: pe / fwd_pe / pb / market_cap. Whitelisted y columns: 1y_return / 5y_return / dividend_yield. Color column: sector. Window slicer: 252d / 504d / 5y / all. Regression: ols + ols_per_group. Let me know if frictions.

---

Build a macro multi-axis time series chart showing S&P 500 (left, compact $), UST 10Y (right, percent, inverted), DXY (left, plain), and WTI (right, $) on the same x-axis since 2020 using the `mapping.axes` API. Let me know if frictions.

---

Build a rates RV dashboard that uses manifest-level `compute` to derive `us_2s10s_bp = (us_10y - us_2y) * 100` and `us_10y_z_60 = zscore(us_10y, 60)` from the existing `rates` dataset. Render both in a 2-up multi_line layout — 2s10s spread on the left, 10Y z-score on the right. Let me know if frictions.

---

Build a sector × month performance heatmap with cell labels showing the percent return. Use a 15-step diverging palette around zero so we can differentiate fine deltas. Let me know if frictions.
