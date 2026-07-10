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
- dashboards/canonical_showcase.json
State whether __init__.py and canonical_showcase.json differ from production. Do not omit them merely because the prior mapping omitted them.
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
