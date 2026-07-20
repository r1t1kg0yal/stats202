Build a `make_2pack_horizontal` of US headline CPI YoY (left) and EU headline CPI YoY (right), both over the last 10 years. Let me know if frictions.

---

Build a `make_2pack_vertical` of US 10y yields (top) and the US 2s10s spread (bottom) over the last 5 years. Let me know if frictions.

---

Build a `make_3pack_triangle` with the US 10y yield as the wide top panel, plus US 2y (bottom-left) and US 30y (bottom-right) as the narrower lower panels. Let me know if frictions.

---

Build a `make_4pack_grid` of regional manufacturing PMIs (US, EU, China, Japan) over the last 10 years, one per panel. Let me know if frictions.

---

Build a `make_6pack_grid` (3x2) of macro indicators for the US: headline CPI, core CPI, payrolls MoM, unemployment rate, retail sales YoY, and ISM manufacturing PMI. Let me know if frictions.

---

Build a `make_4pack_grid` where one of the four sub-panels deliberately fails (e.g. an empty DataFrame). Confirm that the surviving 3 panels render and that the failed panel's error lands in `result.chart_errors`. Let me know if frictions.

---

Build a composite via `ChartSpec` objects rather than inline kwargs (positional args; metadata keyword-only). Verify that `save_as`, `dimension_preset`, and `filename_prefix` all work when threaded through the composite constructor. Let me know if frictions.
