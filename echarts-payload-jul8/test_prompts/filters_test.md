Build a global cross-asset dashboard with a top-bar `dateRange` filter (1M / 3M / 6M / YTD / 1Y / 2Y / 5Y / All) plus a `multiSelect` filter for region (US / EU / JP / UK). Both filters apply to all data-bound widgets via `targets: ["*"]`. Let me know if frictions.

---

Build a fundamental screener dashboard with cascading filters: region narrows country options, country narrows ticker options. Selecting US shows only US tickers; switching to EU rebuilds the country options to EU members and clears ticker. Let me know if frictions.

---

Build a 4-panel rates dashboard (curve level, curve change, 2s10s spread, MOVE index). Wire all four charts so dragging the `dataZoom` slider on any one chart moves the visible window on all four together via a `sync: ["dataZoom"]` Link. Let me know if frictions.

---

Build a sector exposure dashboard. The left panel is a donut chart of market-cap weights by sector. Clicking any slice should filter the screener table on the right to that sector via `click_emit_filter`. Re-clicking the same slice clears the filter. Let me know if frictions.

---

Build a corporate bond screener with a compound `rule` filter: investment-grade rating (AAA, AA, A, BBB) AND ((rich-and-tight: ytm > 4.5% AND spread < 200bp) OR (short-financials: sector in [Financials, Banks] AND duration < 5y)). Render the rule as a chip with a summary subtitle and a popup explaining the tree. Let me know if frictions.

---

Build a 3-tab macro dashboard: Tab 1 (US rates), Tab 2 (FX), Tab 3 (Credit). Each tab carries its own tab-inline filter (US: tenor select; FX: pair multiSelect; Credit: rating multiSelect). Plus one global `dateRange` filter on the top bar that applies across all three tabs. Let me know if frictions.

---

Build an FX vol regime dashboard with conditional widgets via `show_when`: a `risk` markdown card that's only visible when VIX > 25 (compile-time data condition), and a sub-pivot that's only visible when the user selects "global" on a top-level `scope` filter (runtime filter condition). Let me know if frictions.
