┌──────────────────────────────────────────────────────────────────────┐
│ Diagnose the malformed 2s10s chart on the Rates Smoke Test dashboard │
└──────────────────────────────────────────────────────────────────────┘

Do not rebuild or modify anything. Inspect the persisted dashboard artifacts and return:

1. The exact 2s10s chart widget from manifest_template.json and manifest.json.
2. The first 5, last 5, minimum, and maximum rows of the exact dataset/column bound to that chart.
3. The resolved ECharts option for that widget immediately after Python compilation, including xAxis, yAxis, series, dataset, dataZoom, and markLine.
4. The browser URL including its full hash fragment.
5. Any spec.initial_state or widget.initial_state.
6. From the live browser, run:
   const el = document.getElementById('chart-<2s10s widget id>');
   const inst = echarts.getInstanceByDom(el);
   const o = inst.getOption();
   Return o.xAxis, o.yAxis, o.series, o.dataset, and o.dataZoom.
7. Return the exact installed rendering.py snippets defining:
   _initInitialState, _restoreUrlState, materializeOption, and
   _ccApplyTimeSeries.

Keep arrays complete for the resolved series if it has at most 20 points;
otherwise report its length plus the first/last 10 points. Do not summarize
away numeric values or code.










Do not rebuild or modify anything.
Read the persisted dashboard.html as text. Extract the JSON assigned to
`var PAYLOAD =` using json.JSONDecoder().raw_decode().
For PAYLOAD.specs.spread_ts return:
- xAxis, yAxis, series, dataset, dataZoom and markLine
- series.data length
- finite y-value count
- first and last 10 series points
- finite y minimum and maximum
For PAYLOAD.manifest.datasets.spread.source return:
- row count
- finite spread_2s10s_bp count
- first and last 10 rows
- minimum and maximum
Compare that embedded manifest with the separately persisted manifest.json:
- metadata.generated_at for both
- whether spread.source is byte/value identical
- whether the spread_ts widget is identical
Also return the installed echart_dashboard.py ENGINE_VERSION and
VALID_WIDGETS, and confirm whether rendering.py contains a data_grid renderer.
Do not inspect the current scripts as a substitute for the embedded PAYLOAD.
The purpose is to diagnose the exact last-good HTML currently being served.
