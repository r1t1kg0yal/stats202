Build a dual-axis chart of US 10y nominal yields (left) and 10y breakeven inflation (right) over the last 5 years. Use the LEFT/RIGHT series-name constants, give both axes short semantic metric + unit titles, and confirm both axes auto-scale independently. Positional labels such as "Right Axis" are unacceptable. Let me know if frictions.

---

Build a dual-axis chart of EUR/USD spot (left) and the US-EU 2y rate differential (right) over the last 3 years to show the carry-FX relationship. Let me know if frictions.

---

Build a dual-axis chart of US ISM Manufacturing PMI (left; observed values roughly 30-65) and US 10y yield (right; observed values roughly 0-6) with the right axis inverted to align directionally. Let the engine compute both domains; do not pass `dual_axis_config`. Let me know if frictions.

---

Build a dual-axis chart of equity vol (VIX, left) and credit spreads (CDX IG, right) with an `HLine(axis='left')` at a VIX threshold, an `HLine(axis='right')` at a CDX threshold, and an axis-agnostic `VLine` on the SVB date. Let me know if frictions.

---

Build a dual-axis chart of US headline CPI YoY (left) and the trade-weighted USD index (right) from a wide DataFrame using `y: [list]`. Verify auto-melt preserves `dual_axis_series` binding and the semantic right-axis title. Let me know if frictions.

---

Build a four-series dual-axis chart with an explicit `dual_axis_bind` routing two same-unit series left and two same-unit series right. Include short semantic titles for both shared units and inspect any within-axis compression warning. Let me know if frictions.

---

Build a dual-axis chart of Brent crude (left) and the trade-weighted USD index (right, inverted). Confirm the inverted-right-axis flag works and that the normal color legend renders cleanly (LastValueLabel is prohibited on dual-axis -- the engine strips it and falls back to the legend). Let me know if frictions.
