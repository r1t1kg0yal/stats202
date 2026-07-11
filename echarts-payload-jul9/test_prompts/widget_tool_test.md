Build a bond YTM solver dashboard cribbing from the bond_pricer canonical example. Scalar inputs for face value, coupon rate, payment frequency, settlement date, maturity date, and a radio toggle for solving from price → yield or yield → price. Output the headline price/yield as a stat plus a cashflow schedule table. Tool def lives ONCE in the initial manifest dict (Tool 2 of hub §B); `build.py` `TRANSFORMS` does NOT touch the tool def — the JS string literal in `tool_def.compute_js` is set at first build and edited surgically via hub §C thereafter (per the carve-out in hub §A.1.1). Let me know if frictions.

---

Build a Fed Scenario Tool dashboard with two tabs: Tab 1 (Scenario Builder) carrying a `widget: tool` taking FOMC scenario inputs and outputting implied swap rates, Tab 2 (Visualization) showing 5 chart widgets. Then add a "Spot vs Forward swap differential" bar chart as a third tab via hub §C raw JSON CRUD on `manifest_template.json` — append the new tab + chart widget surgically; the Tab 1 tool def must stay byte-identical (manifest-wipe-fragile per widget_tool.md §1). Let me know if frictions.

---

Build a Fed Scenario Analysis dashboard cribbing from the fed_scenario_swaps canonical example. Tool widget with a matrix input for FOMC meeting cumulative bp changes across 3 scenarios (paste-from-Excel enabled), plus scalar inputs for the starting EFFR and trade date. Outputs: spot swap rates (1Y–5Y) per scenario as a stat_grid plus a series chart of the Fed Funds path per scenario. The compute_js is a Python string LITERAL inside the initial manifest dict (hub §A.1.1 carve-out); the dashboard's `build.py` `TRANSFORMS` is empty — tool widgets don't need build-time derivation because compute happens client-side on every input change. Let me know if frictions.

---

Build a Fed Taylor Rule dashboard with a `widget: tool` taking 6 scalar inputs (inflation, target inflation, neutral rate, output gap, phi_pi=1.5, phi_y=0.5) and outputting an implied policy rate as a stat. Then raise the default of the inflation reaction coefficient (phi_pi) from 1.5 to 1.7 to test a more aggressive policy stance — surgical hub §C raw JSON CRUD on `manifest_template.json`'s `tool_def.inputs[].default` field; do NOT touch `compute_js` (the formula coefficients are PRISM-supplied via `inputs[].default`, never inlined into the JS body). Let me know if frictions.

---

Build a Black-Scholes call/put pricer dashboard cribbing from the option_bsm canonical example. Scalar inputs for spot, strike, vol, rate, time-to-expiry, plus a radio toggle for call vs put. Output price as a stat, the five greeks as a stat_grid, and the payoff curve as a series chart with a vline annotation tracking the current spot. Let me know if frictions.

---

Build an NFP-style dashboard with 4 tabs (Release Summary, Wages & Inflation, Birth-Death, Sector Detail), each populated with charts and KPI tiles only — no tool widgets anywhere — and corresponding `pull_<thing>` functions in `PULLS`. Then append a real-wages calculator tool widget to Tab 1 via hub §C raw JSON CRUD: insert the new `widget: tool` into Tab 1's row list with scalar inputs for AHE month-over-month, AHE year-over-year, and CPI year-over-year. Output the real-wage MoM and real-wage YoY rates as a stat_grid. The `pull_data.py` `PULLS` dict and `build.py` `TRANSFORMS` list are unchanged — this is a manifest-only edit. Let me know if frictions.

---

Build a TIPS RV dashboard with a single tab carrying a slider filter, a TIPS scatter chart (Z-spread vs Modified Duration colored by maturity), and 3 tables (TIPS bond details, carry & roll, TIPS-vs-nominal comparison). Set the title to "TIPS RV Dashboard" and the methodology to a placeholder. Then update the title to "TIPS Relative Value Monitor" and append a sentence to the methodology block mentioning the SOFR + 9bp funding assumption — hub §C.8 metadata patch on `manifest_template.json`. Verify via `build_dashboard(folder)` that the new title + methodology are stamped into the rebuilt `manifest.json` + `dashboard.html`. Let me know if frictions.
