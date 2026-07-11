Use the existing comparison materials under:
sessions/20260709_013547_goyalri_old_vs_prod_migration_docs/
I cannot transfer the full unified diff. Return a bounded reconciliation answer with these sections:
## 1. Complete counterpart inventory
For every dashboards-subsystem file represented by old/ OR present in the current production subsystem, return:
- old/ filename
- exact production path
- kind: executed Python / LLM context / JSON reference
- old SHA-256 and production SHA-256
- byte-identical / differs / production-only / old-only
Explicitly resolve why the migration package says 16 files while staging currently has:
- 8 Python files, including __init__.py
- 9 shipped context Markdown files
State whether __init__.py differs from production. Do not omit it merely because the prior mapping omitted it.
## 2. Exact executable Python delta ledger
Ignore whitespace, comments, docstrings, and prose-only cross-reference renames. For each Python file, list every remaining executable/runtime difference between old/ and production.
For each runtime difference provide:
- production file and exact production line range
- enclosing symbol/function
- complete OLD code block
- complete PRODUCTION code block
- one-sentence behavioral effect
The code blocks must be syntactically complete replacement units, not truncated excerpts. Include all executable differences, especially:
- every import re-root, including __init__.py and lazy imports
- pull_nyfed_data’s exact production module path and import shape
- VALID_TOOL_INPUT_TYPES and range min/max validation
- _normalize_tool_output and normalize_tool_def wiring
- compile_dashboard bare-S3-manifest-key handling
- the complete _get_echarts_js function
- all range-input CSS and JavaScript helpers/wiring
- stat_grid dispatch and string-stat formatting
- community-share author/API/dashboard-id fallbacks and button visibility
- any telemetry behavior change, distinguishing executable change from comment/head-order-only change
Resolve these suspected OCR errors explicitly:
- pull_plottool_data vs pull_pltotool_data vs pull_plotdata_data
- core.mcp.clients.newyorkfed_client vs the actual production import
- the missing tail of _get_echarts_js
- whether production intentionally retains any fallback import/path behavior
End with: “Executable Python ledger complete: YES/NO”. If NO, name exactly what could not be resolved.
## 3. Markdown semantic delta ledger
Apply these neutralizers mentally before reporting:
- punctuation, arrows, smart quotes, ellipses, whitespace, and wrapping
- ai_development import/path re-rooting
- context-sensitive dashboards.md → dashboards_hub.md cross-reference renames
- the broad pull_market_data → pull_plottool_data documentation migration
Then, for each of the 9 shipped Markdown files, report every surviving word-level semantic change. For each:
- file
- heading/anchor
- exact OLD text
- exact PRODUCTION text
Do not return punctuation-only or wrapping-only differences. Confirm the final count of genuine semantic changes per file and total. Correct all OCR-corrupted function names.
Also state whether the six test_prompts files need semantic updates to remain consistent with production guidance, even though they do not ship.
## 4. Local mock-runtime contract
Return exact production import names and callable signatures used by the dashboards payload for:
- prism_meta.REPO_ROOT
- core.s3_bucket_manager.s3_manager methods actually called
- core.common.UserRegistry methods actually called
- core.user_manifest.UserManifestManager methods actually called
- prism_mcp.utils.s3_log_streamer.S3LogPathBuilder and S3LogStreamer
- prism_mcp.utils.subprocess_completion.register_completion_marker
- prism_mcp.utils.data_functions names imported by refresh_runner.py and echart_dashboard.py
State the production static asset lookup order for echarts.js and the production module invocation used to launch refresh_runner and refresh_dashboards.
## 5. Verification recipe without transferring the full diff
Give commands PRISM can run after a candidate staging version is re-promoted to classify:
- Python: byte-identical vs runtime-equivalent-only vs real executable delta
- Markdown: punctuation/mechanical-only vs surviving semantic delta
- omitted/unmapped files
Do not include the full unified diff. Do not summarize away exact executable replacement blocks or exact semantic old/new text.
If part of this prompt cannot be answered, add a brief “## Could not resolve” section at the end.






















Continue the same read-only reconciliation. Return ONLY the four bounded artifacts below, copied verbatim from production. Do not use `...`, prose placeholders, reconstructed snippets, or omitted lines.
## A. Production-only __init__.py
Return the complete current contents of:
prism-core/dashboards/__init__.py
This file is production-only relative to old/, so there is no meaningful diff. Include its full SHA-256 and line count.
## B. Complete range-slider JavaScript
From production `prism-core/dashboards/rendering.py`, return:
1. The complete enclosing event-binding function/block containing the scalar-input `row.querySelector(...)`, including every input/change listener.
2. Every complete function whose name contains `Range`, especially `_toolUpdateRangeDisplay`.
3. The complete `_toolReadScalarValue` function.
4. State explicitly whether `_toolFormatRangeDisplay` exists in production.
5. List every executable old→production range-slider delta with exact production line ranges.
All code must be verbatim and complete. The prior response’s `_toolUpdateRangeDisplay` block contained `...`, so it cannot be applied.
## C. Complete widgets.md semantic blocks
From production `prism-core/context/modules/static/tools/dashboards/widgets.md`, return verbatim:
1. The entire `Widget shape & width contract` section, from its heading through the line immediately before the next heading.
2. The complete production provenance example changed from old.
3. The complete production `symbol` field/table row changed from old.
Also return the exact old text for items 2 and 3. No truncation.
## D. Rendering logo import
Compare the executable `_get_prism_logo_b64` function in old/rendering.py and production rendering.py. Return the complete old and production function only if executable bytes differ. Otherwise state byte-identical. Explicitly confirm whether production imports `s3_manager` from `core.s3_bucket_manager`.
End with:
`All requested blocks verbatim and complete: YES/NO`
If NO, identify the specific missing block.
Can you run the bounded follow-up prompt above?































Continue the same read-only dashboards reconciliation against the current production source tree. Do not use old/ as a runtime target and do not return full file contents or unified diffs.
Resolve only these final ambiguities.
## 1. Freshness and completeness
Return the current:
- prism-main HEAD SHA
- prism-core submodule SHA
Then confirm YES/NO:
1. Is the prior executable ledger exhaustive for all eight Python payload files, including production-only __init__.py?
2. Are the only genuine Markdown semantic changes the two documented widgets.md changes?
3. Is test_prompts/ outside the current production-overlap promotion?
If any answer is NO, identify the missing file or behavior precisely.
## 2. Exact local-mock signatures
Return the exact production import path and inspect.signature output for:
- type(s3_manager).get
- type(s3_manager).put
- type(s3_manager).exists
- type(s3_manager).list
- UserRegistry.__init__
- UserRegistry.get_all_kerberos_ids
- UserManifestManager.__init__
- UserManifestManager.update_dashboard_pointer
- S3LogPathBuilder.build
- S3LogPathBuilder.build_session_side
- S3LogStreamer.__init__
- register_completion_marker
- core.mcp.clients.newyorkfed_client.pull_nyfed_data
Also state:
- whether prism_meta.REPO_ROOT is str or Path
- the actual return shapes of s3_manager.list and both S3LogPathBuilder methods
- whether any dashboard payload call uses an unlisted method
Do not abbreviate signatures with prose or ellipses.
## 3. Import-resolution edge cases
Search the current production echart_dashboard.py and return every import statement containing dashboards_time, including imports nested inside functions.
Answer explicitly:
1. Are any bare `from dashboards_time import ...` statements retained?
2. If yes, why do they resolve when echart_dashboard is imported as dashboards.echart_dashboard?
3. Should the staging mirror preserve those bare imports exactly?
4. Is pull_market_data intentionally retained in the executable refresh namespace even though authoring guidance migrated to pull_plottool_data?
## 4. No-op textual differences
Classify each as EXECUTABLE, EMITTED-ARTIFACT, or INERT:
- changing the _get_prism_logo_b64 docstring from the stale ai_development.* wording to core.*
- a final trailing-LF difference
- em-dash/hyphen substitutions in comments and Markdown
- dashboards.md to dashboards_hub.md prose-only cross-reference changes
- mysite/news to web/backend_django/news docstring changes
State whether any of these would prevent a candidate from being accepted as runtime/semantic-equivalent to production.
## 5. Candidate-versus-live verification
The prior recipe compares old/ against production. We instead need to compare a newly uploaded candidate snapshot directly against live production.
Provide:
1. The recommended session-folder layout for uploading the candidate’s eight Python and nine Markdown files.
2. A bounded command or script that compares candidate → live production and emits only:
   - BYTE_IDENTICAL
   - RUNTIME_EQUIVALENT_ONLY
   - SEMANTIC_EQUIVALENT_ONLY
   - REAL_EXECUTABLE_DELTA
   - REAL_SEMANTIC_DELTA
   - UNMAPPED
3. The exact expected file inventory.
4. Confirmation that test_prompts/ is excluded.
Do not output the underlying full diff.
End with:
FINAL AMBIGUITIES RESOLVED: YES/NO
If NO, list only the unresolved questions.
