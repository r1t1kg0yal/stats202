Compile a dashboard with a `dateRange` filter wired to multiple chart widgets across two tabs. Verify the filter narrows all charts simultaneously when the user adjusts it. Let me know if frictions.

---

Compile a dashboard with a `multiSelect` filter for region (US, EU, UK, JP) and a `select` filter for indicator type (CPI, GDP, payrolls). Wire both to a chart and a KPI grid. Let me know if frictions.

---

Compile a dashboard with `numberRange`, `slider`, and `toggle` filters all driving a single scatter chart's underlying dataset. Verify each filter type composes with the others as expected. Let me know if frictions.

---

Compile a dashboard with filter ops covering all 11 cases: `==`, `!=`, `>`, `>=`, `<`, `<=`, `contains`, `startsWith`, `endsWith`, `in`, `not_in`. Use a single dataset and confirm each op produces a distinct visible filter behavior. Let me know if frictions.

---

Compile a dashboard with two charts on the same tab synced via all four sync modes: `axis`, `tooltip`, `legend`, `dataZoom`. Verify cursor / tooltip / legend / zoom propagate between the two charts. Let me know if frictions.

---

Compile a dashboard with a brush selector (`rect` or `polygon`) on a scatter chart wired to a sibling table widget showing the in-brush rows. Test all four brush types (`rect`, `polygon`, `lineX`, `lineY`) by switching the brush kind. Let me know if frictions.

---

Compile a dashboard with `links` between widgets — clicking a row in a table should filter a chart on a different tab to that row's category. Confirm the link survives manifest serialization round-trip. Let me know if frictions.
