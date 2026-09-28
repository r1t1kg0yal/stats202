# Context extraction: four hidden hunks in the 2026-09-06 dashboard review diff, plus the stub seams they import

Introspection only. No dashboard is being built here. Do not produce a
Frictions section; if something cannot be resolved, add a short
`## Could not resolve` at the end naming what you tried and what blocked it.

Read source and paste what is actually there. Do not paraphrase, do not
reconstruct from memory, and do not fill a gap with what you think the
design should be. Where a question asks for a verbatim block, use a fenced
code block and give the exact path plus line range you read it from.

---

## Why we are asking

Staging folded the `prism-main/old` vs installed review diff for the
dashboard subsystem (21 hunks across `echart_dashboard.py`,
`rendering.py`, `refresh_launcher.py`, `refresh_runner.py`,
`jobs/hourly/refresh_dashboards.py` and
`web/backend_django/news/dashboard_composer.py`) into the canonical
payload on 2026-09-06. The diff arrived as a scanned review page. Four
regions sat under the review UI's sticky header and were never visible;
staging reconstructed them from the identifiers the visible hunks use.
Everything else was read. These questions replace the four
reconstructions with bytes, and confirm the signatures of the five
modules the payload now imports so the staging stubs match them.

---

## 1. The four hidden regions (verbatim, with line ranges)

1. `prism-core/dashboards/refresh_launcher.py` — the deferred import block
   inside `launch_clean_refresh` that brings in `scrub_child_credentials`.
   Paste from the `from dashboards.echart_dashboard import (` line down
   to the close of the `S3LogStreamer` import. We wrote:
   `from prism_mcp.utils.detached_subprocess import scrub_child_credentials`
   between the `dashboards` import and the `s3_log_streamer` import.

2. `prism-core/dashboards/refresh_runner.py` — the module-level imports
   from `core`. Paste every line from `import traceback` down to the
   `from dashboards import (` line. We wrote a single
   `from core import identity, service_account` directly above
   `from core.s3_bucket_manager import s3_manager`.

3. `jobs/hourly/refresh_dashboards.py` — the module-level imports from
   `core`. Paste from `from typing import List, Optional` down to the
   `from dashboards.dashboards_time import (` line. We wrote
   `from core.service_account import system_token_scope` between the
   `core.common` and `core.s3_bucket_manager` imports.

4. `web/backend_django/news/dashboard_composer.py` — everything from
   `import json` down to the `_COMPOSER_BOOT_URL` assignment. That range
   should contain the `core.configs.composer_assets` import, the
   `_STATIC_URL` constant with its comment, and the full body of
   `_asset_url`. We wrote:

   ```python
   def _asset_url(ref):
       return ref if is_absolute_url(ref) else _STATIC_URL + ref
   ```

   Report the blank-line count between `_STATIC_URL`, `_asset_url` and
   `_COMPOSER_BOOT_URL` exactly; the file is drag-and-drop promoted and a
   one-line difference breaks parity.

## 2. The five imported seams (signatures, so the stubs match)

5. `core/identity.py`: paste the signature and docstring of `acting_as`,
   and the signature of whatever `_is_system_call()` reads (`current_kerberos`
   or equivalent). Is `acting_as` a `contextlib.contextmanager` over a
   `ContextVar`? What does it bind when the argument is `None` or empty?

6. `core/service_account.py`: paste the signatures and docstrings of
   `job_scope` and `system_token_scope`. What does each one set, and what
   does the S3 layer read back to enforce it? Does `job_scope` accept one
   prefix or a collection? Is a key outside the prefix refused with an
   exception (which class?) or silently rewritten?

7. `core/configs/composer_assets.py`: paste the file. We need
   `COMPOSER_BUNDLE_ORDER`, every `ASSET_BUNDLES` entry with its
   `styles` / `globals` / `scripts`, and `is_absolute_url`. Our stub
   carries three bundles (`markdown`, `mermaid`, `composer`) against the
   mock static tree; the payload docstring names KaTeX and a drop-action
   registry that our stub omits.

8. `prism_mcp/utils/detached_subprocess.py`: paste
   `scrub_child_credentials` verbatim — the exact-name set and the suffix
   set it filters on, and whether it returns a new dict or mutates the
   argument.

9. `prism_mcp/utils/code_preprocess_utils.py`: paste the signature and
   return contract of `neutralize_and_refuse_generated_code`, and the
   tuple it iterates (`GENERATED_CODE_PREEXEC_CHECKS` or whatever it is
   named). Is the return `(neutralized_source, refusal_text)` with an
   empty string meaning "clean"? Does `check_for_local_file_writes` sit
   in the tuple this entry point runs, or is it excluded as on the chart
   path?

## 3. One behaviour we observed and want confirmed

10. Under `job_scope("users/<k>/dashboards/<id>/")`, `build_dashboard`'s
    `_audit_refresh_attachment(strict=False)` reads the sibling
    `users/<k>/dashboards/dashboards_registry.json`. In staging that read
    is refused and surfaces as one lenient `registry_entry_missing` log
    line per cycle, exactly as the runner's comment predicts. Does the
    installed hourly log show the same line on every scoped refresh? Paste
    one such line from a recent `subprocess_logs/` entry if so.
