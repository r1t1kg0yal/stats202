Build a multi-line chart of four regional inflation series using the named `colorblind` palette. Put `color_scheme` inside `mapping` and do not author a manual colour registry. Let me know if frictions.

---

Build a multi-line chart that pins the US series to crimson and fades EU and Japan while leaving the requested focus fully opaque. Use named `color_map` and `opacity_map` dictionaries inside `mapping`, with an entry for every highlighted or faded category. Let me know if frictions.

---

Build a categorical bar chart and change only the second rendered category to crimson using a 1-indexed positional `color_map` dictionary. Supply an explicit `color_sort` so the requested slot is deterministic. Let me know if frictions.

---

Build a heatmap of monthly S&P 500 returns using a diverging `redblue` scheme because zero is the meaningful centre. Keep `color_map` and `opacity_map` off this quantitative heatmap. Let me know if frictions.

---

Build a heatmap of unsigned cross-asset volatility levels using a sequential `viridis` or `blues` scheme. Do not use a diverging palette because there is no meaningful midpoint. Let me know if frictions.

---

Build an ordered scatter phase path whose temporal `color` field shows early-to-late progression. Use `connect=True` and a two-colour `color_range` inside `mapping`; do not use categorical `color_map`. Let me know if frictions.

---

Build a single-series chart in one requested custom hex colour with 50% uniform opacity. Put `color_map=['#...']` and `opacity=0.5` inside `mapping`, and confirm no colour or opacity kwarg is passed at `make_chart` top level. Let me know if frictions.
