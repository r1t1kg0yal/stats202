# Context extraction: dashboard retrieval — is it code or a document?

Introspection only. No dashboard is being built here. Do not produce a
Frictions section; if something cannot be resolved, add a short
`## Could not resolve` at the end naming what you tried and what blocked it.

Read source and paste what is actually there. Do not paraphrase, do not
reconstruct from memory, and do not fill a gap with what you think the
design should be. Where a question asks for a verbatim block, use a fenced
code block and give the exact path plus line range you read it from.

---

## Why we are asking

Staging has changed how an ECharts dashboard declares what it fetches. In
`projects/echarts/echarts-payload/`, `scripts/pull_data.py` — a persisted
Python module carrying a module-level `PULLS = {"name": callable}` mapping,
whose bodies called `get_data` themselves — has been replaced by
`scripts/pulls.json`:

```json
{
  "schema_version": 1,
  "pulls": [
    {"name": "rates",
     "details": {"source": "tsdb_eod",
                 "start": "2015-01-01", "end": "@today",
                 "symbols": [{"symbol": "sofrswp2y", "label": "us_2y"},
                             {"symbol": "sofrswp10y", "label": "us_10y"}]}}
  ]
}
```

The engine now owns the call: it resolves `@today`-family tokens to ISO
dates, validates each `details` against the `Details` union, pins
`session_path` to the dashboard's own `data/` prefix, and awaits
`get_data`. Nothing is executed to discover what a dashboard fetches.

We believe this originated as an MR tried on your side, but we do not know
its current state in your tree, and several of our curated docs now carry
WARN sentinels because of that. These questions close that gap.

---

## 1. Which shape is installed right now

In the installed `prism-core/dashboards/echart_dashboard.py`:

1. Does the symbol `apply_pulls_document` exist? If yes, paste its full
   signature and docstring verbatim, with its line range.
2. Does `migrate_pull_script` exist? Same treatment.
3. Paste the current body of `run_pull` verbatim, whatever it is. This is
   the single most decisive answer: it either parses a JSON document or it
   executes a Python module.
4. Grep the module for the literal strings `pulls.json`, `PULLS`,
   `pull_data.py`, `pull_registry_missing`, and `pull_document_changed`.
   Report the count for each. A zero is as informative as a hit.
5. What does the module's `_AUDIT_REQUIRED_PATHS` (or whatever the audit's
   required-file collection is currently named) contain? Paste it.

## 2. The runner

In `prism-core/dashboards/refresh_runner.py`:

6. Paste `_list_pulls` verbatim, or state that no such function exists and
   paste whatever enumerates pulls in its place.
7. Does `run()` accept a `pulls_subset` parameter, and does the CLI expose
   a `--pulls` argument? Paste the `add_argument` calls.
8. What exact string does a per-pull failure write into the `script` field
   of a `refresh_status.json` error entry? We need the literal format,
   e.g. whether it is `scripts/pull_data.py::rates` or
   `scripts/pulls.json::rates`.

## 3. The persisted corpus

9. For a single dashboard folder you can read — your own is fine, name the
   kerberos you used — list `scripts/`. Which of `pull_data.py` and
   `pulls.json` is present?
10. If you can reach more than one owner's folders without an ACL refusal,
    give a count of folders carrying each file. If the cross-user walk is
    refused, say so plainly rather than estimating; a refusal is a fine
    answer and we already record that constraint.

## 4. The exec namespace

11. Paste the current `_build_dashboard_exec_namespace` (or its equivalent)
    verbatim. We specifically need the complete set of names it binds.
    Staging has reduced this to `s3_manager`, `pd`, `np` on the grounds
    that a persisted script no longer retrieves; we want to know whether
    the installed copy still binds pull helpers.
12. Does `refresh_runner` import that builder from `echart_dashboard`, or
    does it construct its own namespace?

## 5. Date tokens

13. Does the installed engine recognise any `@today`-family token? If yes,
    paste the regex or parsing function and state exactly which fields it
    is applied to — specifically whether it reaches inside a
    `source="client"` call's `arguments` dict, or only top-level
    `start` / `end`.

## 6. Multi-table sources

14. Which `Details` members write more than one CSV per call? We have
    `lakehouse` (via `tables[]`) and believe `gs_quant_reference` behaves
    the same way. For each, name the field holding the table list and the
    per-table field that supplies the filename suffix, and paste the
    member class definition verbatim.
15. `gs_quant_reference` and `gs_quant_dataset` are the two members our
    local `Details` mirror is least sure about. Paste both class
    definitions in full, including every field, default, and validator.

## 7. Version recipes

16. When a dashboard definition version is recorded, what keys does the
    recipe carry? We are looking specifically for whether it stores
    `pull_data_py` or `pulls_json`, and whether the version summary field
    is `pull_script_changed` or `pull_document_changed`. Paste the dict
    construction verbatim.

## 8. If the MR did not land

17. If the answers above show the installed engine is still on
    `pull_data.py`, tell us that in one line at the top of your reply.
    Then, if you can see it, say whether the MR exists as an open branch
    or was closed, and name the branch. We are not asking you to merge
    anything — we need to know which state to document.
