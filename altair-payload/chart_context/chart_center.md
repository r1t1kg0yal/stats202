# Prism Chart Center

Spoke fetched on demand from the chart_context hub. Covers the interactive editor HTML that ships alongside every PNG — what the editor offers, the styling-delegation discipline that keeps PRISM from re-running `make_chart()` for cosmetic asks, the mandatory link-delivery contract, the session-folder layout, the non-fatal-generation contract, and the small set of currently-not-supported feature/workaround pairs.

For composite-result variants of these links (which carry the same fields) fetch `composites.md`.

---

## 1. What it provides

Every successful `make_chart()` / composite produces TWO artifacts in the
session folder: a static PNG and a self-contained interactive editor HTML
(the "Chart Center"), both on the same `ChartResult`.

- ~140 editable knobs across Dimensions, Title, Typography, Axes, Legend, Colors, Interactivity, and per-mark sections (Line / Bar / Scatter / Area / Arc / Heatmap / Box / Bullet / Waterfall). Editable title, subtitle, axis labels, legend title.
- 5 theme presets (`gs_clean`, `bridgewater`, `minimal`, `dark`, `print`); 14 color palettes -- categorical (`gs_primary`, `bridgewater`, `mono_blue`, `mono_grey`, `vivid`, `tableau`, `okabe_ito`), sequential (`viridis`, `blues`, `reds`, `greens`), diverging (`gs_diverging`, `redblue`, `spectral`).
- 12 dimension presets: 7 PRISM canonical sizes plus `report`, `dashboard`, `widescreen`, `twopack`, `fourpack`, `custom`.
- Spec sheets: named JSON bundles of styling preferences scoped to user (and optionally chart type), persisted in browser localStorage, importable / exportable as JSON.
- Export: PNG (1x / 2x / 4x), SVG, Vega-Lite JSON, Altair Python. Tabs: Chart, Data (sortable / filterable + summary stats), Code, Metadata.
- Interactivity: tooltips, crosshair, brush zoom (x / y / both), legend click toggle, per-series color overrides. Runs entirely client-side via CDN (`vega@5`, `vega-lite@5`, `vega-embed@6`); no server, no auth.

---

## 2. Styling delegation strategy (CRITICAL)

Prism should NOT iterate on chart styling. For ANY visual / aesthetic
request -- line thickness, colors, fonts, legend position, dimensions,
palette, padding, gridlines, "make it bigger" / "make the lines thicker"
-- hand the user the Chart Center link, do not regenerate. Re-run
`make_chart()` ONLY when the request changes the **data** (series / time
range / metric / filter), the **structure** (chart type, mapping,
annotations, composite layout), or the **narrative** (title, subtitle).

---

## 3. Delivering links to the end user (MANDATORY)

After EVERY successful chart, the LLM must surface BOTH links: the PNG
(renders inline) AND the Chart Center URL (for user customization).
Markdown only -- no HTML, no styling. (1) print both URLs from the script
so they reach the LLM context; (2) emit them in the narrative reply with
the actual URL strings. Composites work identically -- `CompositeResult`
carries the same `download_url` / `editor_download_url`.

```python
result = make_chart(...)
if result.success:
    print(f"PNG: {result.download_url}")
    print(f"Chart Center: {result.editor_download_url}")
```

```markdown
![Chart](<result.download_url>)

[Open in Prism Chart Center](<result.editor_download_url>) -- customize
colors, fonts, dimensions, palette, and styling. Export as PNG / SVG /
Vega-Lite JSON. Save preferences as a spec sheet.
```

The Chart Center URL is presigned (1 hour default); the underlying
`editor_html_path` is a stable S3 path inside the session folder --
re-presign via `s3_manager` if the original URL expires.

---

## 4. Session folder structure

```
sessions/{timestamp}_{slug}/
    {timestamp}_{chart_name}_{chart_type}.png
    charts/{timestamp}_{chart_name}_{chart_type}_editor.html
```

`save_as='charts/foo.png'` lands the editor companion at
`charts/foo_editor.html` (same dir, same base, no timestamp prefix).

---

## 5. Non-fatal generation

If Chart Center generation fails (vega CDN unreachable, spec hash collision,
template error), the PNG still delivers; `editor_download_url` and
`editor_html_path` are `None` and `result.warnings` carries the cause --
deliver the PNG and note Chart Center was unavailable, never silently omit.

---

## 6. Known limitations

| Feature | Status | Workaround |
|---------|--------|------------|
| Inverted right axis | Supported | `invert_right_axis: True` |
| HLine on right axis | Supported | `HLine(y=val, axis='right')` |
| Segment on right axis | Supported | `Segment(..., axis='right')` |
| `Trendline` on dual-axis multi_line | Not supported | Single-axis chart, or `make_2pack_vertical()` |
| >2 y-axes | Not supported | Composite layouts |
| Candlestick | Not supported | Plotly (`px`) -- no GS styling |
| Sankey / Treemap | Not supported | Plotly (`px`) -- no GS styling |
| Boxplot outlier markers | Not supported | Basic boxplot (Tukey 1.5*IQR whiskers) |
