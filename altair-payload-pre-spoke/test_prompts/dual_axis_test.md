Build a dual-axis chart of US 10y nominal yields (left) and 10y breakeven inflation (right) over the last 5 years. Use the LEFT/RIGHT series-name constants, give both axes short semantic metric + unit titles, and confirm both axes auto-scale independently. Positional labels such as "Right Axis" are unacceptable. Let me know if frictions.

---

Build a dual-axis chart of EUR/USD spot (left) and the US-EU 2y rate differential (right) over the last 3 years to show the carry-FX relationship. Let me know if frictions.

---

Build a dual-axis chart of US ISM Manufacturing PMI (left, range 30-65) and US 10y yield (right, range 0-6) with the right axis inverted to align directionally. Let me know if frictions.

---

Build a dual-axis chart of equity vol (VIX, left) and credit vol (CDX IG spread, right) with annotations on BOTH the left and right axis (a VLine on the SVB date, a Band on the COVID period). Let me know if frictions.

---

Build a dual-axis chart of US headline CPI YoY (left) and the trade-weighted USD index (right) from a wide DataFrame using `y: [list]`. Verify auto-melt preserves `dual_axis_series` binding and the semantic right-axis title. Let me know if frictions.

---

Try to build a dual-axis chart with FOUR series total (two left, two right), including a short semantic `y_title_right` for the shared right-side unit. If the API blocks this, switch to a stacked composite (`make_2pack_vertical`) showing the same four series across two panels. Let me know if frictions.

---

Build a dual-axis chart of Brent crude (left) and the trade-weighted USD index (right, inverted). Confirm the inverted-right-axis flag works and that the normal color legend renders cleanly (LastValueLabel is prohibited on dual-axis -- the engine strips it and falls back to the legend). Let me know if frictions.
