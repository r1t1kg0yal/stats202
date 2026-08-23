Pull US, EU, UK, and JP headline CPI YoY for the last 10 years and chart them as a multi_line using the long-format pattern (color = region). Let me know if frictions.

---

Pull the same four CPI series and chart them using the wide-format auto-melt shortcut (mapping y as a list, no color key). Confirm both approaches produce equivalent output. Let me know if frictions.

---

Build a horizontal bar of YTD performance across the major equity indices, sorted descending by value. Let me know if frictions.

---

Pull a DataFrame of FOMC dates and dot-plot medians, then run profile_df on it. Print the columns, dtypes, cardinality, and date_range, then chart the dot-plot evolution. Let me know if frictions.

---

Build a multi_line of 4 G10 currency-pair vol levels with strokeDash differentiating G10 majors from G10 minors. Let me know if frictions.

---

Build a scatter of MOVE vs VIX for the last 3 years with a regression trendline overlay. Let me know if frictions.

---

Pull a Haver-coded series for US payrolls (`LANAGRA@USECON` or similar) and chart it with `mapping['y_title']='Payrolls (M)'` to verify the coded column gets a semantic rendered y-axis label. Let me know if frictions.

---

Build a 2-pack horizontal composite showing US 2y and 10y Treasury yields over the last 5 years. Put `"y_title": "2Y Yield (%)"` and `"y_title": "10Y Yield (%)"` inside the respective `ChartSpec.mapping` dictionaries, not on the pack helper. Let me know if frictions.
