Build any standard chart and surface BOTH the PNG download_url AND the Chart Center editor_download_url. Confirm the editor link opens to the same chart with full theming controls. Let me know if frictions.

---

Build a multi_line and apply the `dark` theme via the Chart Center editor surface. Verify the theme overrides `gs_clean` consistently across axes, fonts, and grid lines. Let me know if frictions.

---

Build a heatmap of monthly equity returns and apply the `viridis` palette via Chart Center. Compare against the default `gs_primary` to verify palette switching works for sequential color scales. Let me know if frictions.

---

Build a chart with `dimensions='presentation'` (900x500) and confirm the typography auto-scales appropriately. Then re-render with `dimensions='thumbnail'` (300x200) and confirm typography downsizes for the smaller canvas. Let me know if frictions.

---

Build a chart with `dimensions='teams'` (420x210) for the Microsoft Teams medium. Verify the typography preset is applied automatically. Let me know if frictions.

---

Build a chart and inspect `result.editor_chart_id` (the sha1 of the spec). Modify the underlying spec slightly (different title) and rebuild; confirm the new editor_chart_id differs from the first. Let me know if frictions.

---

Build a chart that fails QC (e.g. all NaN data after filtering). Confirm both the PNG and the editor_html_path companion are deleted by `s3_manager.delete()` and that PRISM does not surface the failed editor link. Let me know if frictions.
