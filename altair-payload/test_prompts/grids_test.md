Build one facet-grid `make_chart` call for headline CPI across eight economies over the last 10 years. Put `facet` and an eight-country `facet_order` inside `mapping`, while keeping `facet_cols=4` at the top level. Let me know if frictions.

---

Build a facet grid of unemployment rates across 12 economies with direct level comparison as the goal. Use `same_scale=True` at `make_chart` top level and explain why independent scales would answer a different question. Let me know if frictions.

---

Build a time-coloured inflation-growth phase grid for eight economies. Use scatter facets with temporal `color`, `connect=True`, `same_scale=True`, and `share_color=True`, keeping facet layout controls outside `mapping`. Let me know if frictions.

---

Build comparable return-distribution histograms for eight major assets as one facet grid. Let the engine enforce a shared x-domain and use one sensible bin specification across panels. Let me know if frictions.

---

Build a 4x2 facet grid of regional PMIs with an explicit business-order `facet_order`, `edge_only_ticks=True`, and `edge_only_axis_titles=True`. Confirm panel headers still identify every region. Let me know if frictions.

---

Build a facet grid for eight countries where each panel contains two inflation measures distinguished by `color`. Use `share_color=True` only if the same measure names and colours should compare across every panel. Let me know if frictions.

---

Compare six regional growth series over the same horizon and choose the correct multi-panel API at the six-panel boundary. Use a `make_6pack_grid` of `ChartSpec` objects rather than forcing `mapping['facet']`, which begins at seven panels. Let me know if frictions.
