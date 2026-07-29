Build a `make_table` macro snapshot from a DataFrame with GDP growth, CPI, and unemployment across the US, UK, EU, and Japan. Use semantic number formats, `rwg` for signed growth changes, `bw` for unsigned levels, and source attribution; do not use a chart `mapping`. Let me know if frictions.

---

Build a curated theme-tracker table from `rows=[{...}]` with Theme, Owner, Conviction, and Catalyst columns. Colour categorical High/Medium/Low conviction cells through `cell_colors`, not numeric `column_color_modes='rag'`. Let me know if frictions.

---

Build a risk-monitor table with numeric unemployment and inflation columns using `column_color_modes={...: 'rag'}`. Supply a separate `rag_thresholds` entry for every RAG column, using higher-is-bad dictionaries. Let me know if frictions.

---

Build a sovereign-curve table whose columns are US, UK, EU, and Japan yields and whose rows are tenors. Apply one row-scoped sequential `heatmap_groups` definition across all four country columns so each tenor compares on a shared scale. Let me know if frictions.

---

Build a multi-level rates table with grouped headers for Yield and Daily Change, regional `row_groups`, and explicit subtotal and total rows already present in the data. Ensure every header span sums to the number of columns and every row-group count sums to `len(df)`. Let me know if frictions.

---

Build a watchlist table with a Trend display column backed by per-row 60-day `sparkline_columns`, a Market Cap display column backed by `minibar_columns`, and a signed daily-return column. Let me know if frictions.

---

Build a table from a deliberately wide cross-country macro DataFrame. Preserve every row and, if the portrait legibility gate rejects the first shape, transpose or split the columns and rerun rather than shrinking, truncating, or printing text. Let me know if frictions.
