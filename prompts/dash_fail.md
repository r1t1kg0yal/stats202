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