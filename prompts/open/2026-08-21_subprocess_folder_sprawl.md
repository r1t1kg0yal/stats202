# Context extraction: what writes `subprocess_dashboard_refresh_*` at a dashboard folder root?

Introspection only. Nothing is being built or changed here. Do not produce a
Frictions section; if something cannot be resolved, add a short
`## Could not resolve` at the end naming what you tried and what blocked it.

Read source and object listings and paste what is actually there. Do not
paraphrase, do not reconstruct from memory, and do not describe what the
design ought to be. Every verbatim request means a fenced code block plus the
exact path and line range you read it from. Every count means a real count,
not an estimate — if a listing is truncated or refused, say so.

---

## Why we are asking

The dashboard Files browser for a live dashboard shows this at the **root** of
the dashboard folder, interleaved with the real artifacts:

```text
users/<kerberos>/dashboards/<dashboard_id>/
├── data/                                                  (6)
├── history/                                               (2)
├── scripts/                                               (2)
├── subprocess_dashboard_refresh_20260522_043715_66…/       (2)
├── subprocess_dashboard_refresh_20260522_053447_41…/       (3)
├── subprocess_dashboard_refresh_20260523_061036_60…/       (3)
├── subprocess_dashboard_refresh_20260524_064614_2a…/       (3)
│   … dozens more, one or more per refresh cycle, continuing past the
│     bottom of the scroll viewport …
```

Two things about that listing do not match what we have documented.

First, our curated dashboard folder contract says session-side child logs
live **under a single `subprocess_logs/` prefix**, not as sibling directories
at the folder root:

```text
users/<kerberos>/dashboards/<dashboard_id>/
├── manifest_template.json
├── manifest.json
├── dashboard.html
├── scripts/{pulls.json,build.py}
├── data/<dataset>.csv
├── refresh_status.json
└── subprocess_logs/          session-side streamed child logs
```

Second, the observed directory name is `subprocess_<kind>_<YYYYMMDD>_<HHMMSS>_<hash>`,
which is neither of the two shapes our staging mirror produces. Our mirror of
`S3LogPathBuilder` builds:

```python
# centralized
folder_key = f"subprocess_logs/{YYYY}/{MM}/{DD}/{kind}/{session_description}__{HHMMSS}__{rand8}"
# session-side
folder_key = f"{session_path.rstrip('/')}/subprocess_logs/{kind}__{HHMMSS}__{rand8}"
```

So either our mirror has drifted from the installed builder (a parity
violation we need to fix on our side), or these directories are legacy
artifacts from a scheme that has since been retired, or a spawner other than
`launch_clean_refresh` is constructing its own key inline. We need to know
which before we touch anything.

---

## 1. Ground truth on one real folder

Pick one dashboard folder with a long refresh history — your own is fine, name
the kerberos and dashboard id you used.

1. List the **immediate** children of the dashboard folder (top-level prefixes
   and objects only, not a recursive walk). Paste the full list. Include
   `subprocess_logs/` explicitly if it is present, and say plainly if it is
   absent.
2. Count the `subprocess_*`-prefixed top-level directories. Give the count,
   the oldest name, and the newest name.
3. Total object count and total bytes for the whole dashboard folder, and the
   same two numbers restricted to the `subprocess_*` directories. We want to
   know what share of the folder is refresh exhaust.
4. Do **both** naming shapes coexist in that folder — flat
   `subprocess_dashboard_refresh_*` directories *and* a nested
   `subprocess_logs/` prefix? If both, give the newest timestamp under each.
   This single answer discriminates "legacy leftovers" from "still being
   written today".

## 2. Who constructs these keys

5. Paste the installed `S3LogPathBuilder` **in full**, verbatim, with its path
   and line range — every classmethod, every f-string that builds a key. If
   the class lives somewhere other than `prism-core/prism_mcp/utils/s3_log_streamer.py`,
   give the real path.
6. Does a `build_session_side` (or similarly-named session-rooted) classmethod
   exist on it? If yes, paste it verbatim. If no, say so in one line — that
   would mean our payload's call to it is calling a method that does not exist
   in your tree, which is a P0 for us.
7. Grep the whole repo (both `prism-main` and `prism-core`) for the literal
   strings below and report a **path:line count for each**. A zero is as
   informative as a hit.
   - `subprocess_dashboard_refresh`
   - `subprocess_logs`
   - `build_session_side`
   - `PRISM_SUBPROCESS_SESSION_FOLDER_KEY`
   - `PRISM_SUBPROCESS_S3_FOLDER_KEY`
8. Enumerate **every** call site that spawns `refresh_runner.py`, with path and
   line. For each, paste the block that computes the log key and the block that
   builds the argv, verbatim. We know of four candidate surfaces and want the
   real set:
   - `jobs/hourly/refresh_dashboards.py` (scheduled walk)
   - `dashboards.echart_dashboard.launch_clean_refresh`
   - `web/backend_django/news/views.py` → `refresh_dashboard_api`
   - `web/backend_django/news/views.py` → `developer_dashboard_refresh`
9. Do any of those spawners compute a key **inline** rather than calling
   `S3LogPathBuilder`? If so, paste the inline construction. That is our
   leading hypothesis for where the flat name comes from.

## 3. Is the flat shape still being produced

10. From the newest flat `subprocess_dashboard_refresh_*` directory in §1,
    read its `metadata.json` (or whatever sidecar it carries) and paste it
    verbatim. We want `pid`, `started_at`, `kind`, and every `*_key` field it
    records — those fields name their own author.
11. Compare that timestamp against `refresh_status.json.completed_at` for the
    same dashboard. Is the newest flat directory from the most recent refresh
    cycle, or is it months stale?
12. If both shapes are live, is the write **dual** (same bytes to a flat
    directory and to `subprocess_logs/`) or are they alternating by spawner?

## 4. What one run directory contains

13. For one such directory, list its contents with per-object bytes. We expect
    `run.log`, `metadata.json`, `completion.json`; confirm or correct.
14. Typical and worst-case `run.log` size for a full-mode refresh. We are
    trying to size the retention problem, and `refresh_runner`'s import-time
    diagnostic banner makes us suspect these are larger than they need to be.

## 5. Readers, and what a prefix move would break

This is the part that decides whether the sprawl is safely relocatable.

15. Which code **reads** from these directories, as opposed to writing them?
    Path and line for each. Specifically: does the status-polling endpoint, the
    in-browser failure modal, the Files browser, or any triage/log-tail helper
    resolve a path under the dashboard folder root?
16. Paste the code path that serves the Files browser listing shown above — the
    view and the S3 listing call. Does it filter or collapse prefixes at all,
    or is it a raw delimiter-less listing?
17. `refresh_status.json.log_path`: for a **Django-initiated** refresh, is the
    recorded value the centralized `subprocess_logs/YYYY/MM/DD/...` key or the
    session-side key? Paste the actual `log_path` value from a real
    `refresh_status.json`, plus the `--log-path` argument the view passes.
    Our curated doc claims the session-side key; our payload passes the
    centralized one to the runner, so one of the two is wrong and we want your
    installed behaviour, not the reconciliation.
18. Is any of these keys persisted anywhere **durable** — the dashboards
    registry entry, a version recipe under `history/`, `console_log.jsonl`, a
    user manifest, a sent email body, or a presigned URL that may still be in
    circulation? If a key is persisted outside the folder, relocating the
    prefix breaks a back-reference and we need the full list.

## 6. Retention

19. Is there **any** pruning, TTL, lifecycle rule, or GC job that deletes old
    subprocess run directories — in application code, in a scheduled job, or as
    an S3 bucket lifecycle policy on the prefix? If none exists, say so
    plainly; unbounded growth is a fine answer and it is the one we currently
    assume.
20. What happens to these directories when a dashboard is deleted via
    `/api/delete-dashboard/`? Paste the deletion code path. Does it delete the
    prefix recursively, or does it delete named objects and orphan everything
    else?

## 7. Is this dashboard-specific

21. What `kind` values are passed to `S3LogPathBuilder` anywhere in the tree?
    List each with its call site.
22. Do any of those other kinds also write **into a caller-supplied session
    path** (a chat session folder, a thread folder, a report folder), or is the
    dashboard folder the only place a subprocess folder gets rooted inside
    someone else's namespace? If chat session folders get the same treatment,
    we want to know now — it changes the scope of the fix from "dashboards" to
    "every subprocess spawn".
