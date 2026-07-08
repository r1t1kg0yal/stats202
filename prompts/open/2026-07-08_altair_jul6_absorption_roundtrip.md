# Altair Jul-6 absorption bundle: post-promotion verification round-trip

Paste AFTER dropping the staged bundle (`chart_functions.py` +
`chart_functions_studio.py` + `chart_context.md`) into
`prism-core/prism_mcp/utils/` and `prism-core/context/modules/static/tools/`.
One introspection line + four end-usage probes. Send as a single message.

---

Before building anything: report the installed version of `vl_convert`
(`import vl_convert; vl_convert.__version__`) and the byte sizes of
`prism_mcp/utils/chart_functions.py` and
`context/modules/static/tools/chart_context.md` as installed.

Then build these four charts, one at a time:

1. Pull any small categorical series (e.g. 5 sector YTD returns) and
   build a `bar` chart with deliberately long category names (25+
   characters each), an `HLine` at zero, and a `caption=` note. This
   previously crashed PNG export with `Unrecognized signal name:
   "concat_0_height"` -- confirm it now renders as a clean horizontal
   bar with the caption below.

2. Build a `scatter_multi` of two related daily series over 2 years
   (x = date) with a `Trendline()` overlay. This previously failed at
   PNG export with a `marktype` TypeError -- confirm the dashed trend
   renders across the date axis.

3. Build a `multi_line` of US 2y/5y/10y/30y Treasury yields over the
   last year with `Trendline(series='<your 10y series name>')`.
   Confirm the trend fits ONLY that one series and the other three
   render untouched.

4. Build a donut chart with 8 categories and confirm all 8 slice
   colours read as distinct (slots 5 and 9 of the default palette were
   re-hued in this bundle).

Let me know if frictions.
