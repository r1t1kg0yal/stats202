Build a dual-axis chart of US 10y nominal yields (left) and 10y breakeven inflation (right) over the last 5 years. Use the LEFT/RIGHT series-name constants and confirm both axes auto-scale independently. Let me know if frictions.

---

Build a dual-axis chart of EUR/USD spot (left) and the US-EU 2y rate differential (right) over the last 3 years to show the carry-FX relationship. Let me know if frictions.

---

Build a dual-axis chart of US ISM Manufacturing PMI (left, range 30-65) and US 10y yield (right, range 0-6) with the right axis inverted to align directionally. Let me know if frictions.

---

Build a dual-axis chart of equity vol (VIX, left) and credit vol (CDX IG spread, right) with annotations on BOTH the left and right axis (a VLine on the SVB date, a Band on the COVID period). Let me know if frictions.

---

Build a dual-axis chart of US headline CPI YoY (left) and the trade-weighted USD index (right), starting from a WIDE DataFrame: pass `y` as the two-column list (auto-melt) and name the right-axis column in `dual_axis_series`. Confirm the engine remaps the raw column name through the melt and renders both axes. Let me know if frictions.

---

Build a dual-axis chart with FOUR series total (two left, two right) using `dual_axis_bind` to make every series's axis explicit. Confirm the colour legend carries ` (LHS)` / ` (RHS)` tags and report any `DUAL-AXIS WITHIN-AXIS COMPRESSION` warning; if one fires, resolve it (rebind or z-score) or switch to `make_2pack_vertical`. Let me know if frictions.

---

Build a dual-axis chart of Brent crude (left) and the trade-weighted USD index (right, inverted). Confirm the inverted-right-axis flag works and that the normal color legend renders cleanly (LastValueLabel is prohibited on dual-axis -- the engine strips it and falls back to the legend). Let me know if frictions.
