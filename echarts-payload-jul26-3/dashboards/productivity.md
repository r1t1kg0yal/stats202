# Productivity and workflow workspaces

- **Context ID:** `echarts.productivity`
- **Owns:** `productivity.scope`, `productivity.archetype`, `productivity.boundary`
- **Fetch when:** Routed by `dashboards.md`.
- **Depends on:** [widgets.md](widgets.md#persisted-user-input) and [build.md](build.md#tool-only-build).

A persistent ECharts dashboard may be an analytical monitor, a shared
productivity workspace, or both. Do not reject a request merely because it
organizes work instead of visualizing economic or financial data. If current
primitives can compose the requested surface, build it through the ordinary
dashboard transaction.

## Capability decision

| User need | Dashboard composition |
|---|---|
| Shared handoff, status, or decision log | `user_input` in `text` mode |
| Tasks, stages, approvals, or runbook steps | `user_input` in `checklist` mode |
| Email/document intake or shared knowledge | `user_input` in `files` mode |
| Fixed instructions or framing | `markdown` or semantic note |
| Refreshable structured records | Dataset-backed `table` or `data_grid` |
| In-place calculation | `tool` |
| Distinct jobs or workstreams | Stable tabs and named groups |

Charts and datasets are optional. A workspace containing only manual state and
narrative is a legal data-free build: persist `PULLS = {}`, use `datasets = {}`
and `TRANSFORMS = []`, and do not create placeholder data.

## Workspace archetypes

| Intent | Recommended surface |
|---|---|
| Chief-of-staff cockpit | Handoff text, next-actions checklist, and knowledge-file intake |
| Email organizer | Separate files widgets for stable buckets, plus a checklist for follow-ups |
| Project room | Decision log, action checklist, reference files, and fixed project framing |
| Operations runbook | Checklist, shift handoff, evidence files, and an optional dataset-backed status table |
| Research workspace | Thesis/context notes, research-file intake, and review checklist |

Use tabs when these jobs are distinct; use one grid when they form a single
scan path. Keep every widget id stable because persisted state is keyed by
dashboard id plus widget id.

## Email and file intake

For “drag emails into the dashboard,” use one or more `user_input` widgets in
`files` mode. Owners can drag operating-system files onto the drop zone or use
the file picker; a valid Outlook `.msg` file is accepted alongside supported
documents, text, data files, and images. Authorized viewers can read the file
list and download active files. Removing a file takes it out of the active
list without rewriting the manifest.

Treat this as persisted intake and knowledge organization:

- “drag in” means upload a file to the selected files widget;
- “out” means download it or remove it from that widget's active list;
- one files widget per bucket gives the user visible destinations;
- moving between buckets currently means add to the destination and remove
  from the source; do not claim direct card-style drag between widgets;
- do not claim that dashboard primitives move existing PRISM mailbox entries,
  synchronize Outlook folders, or classify messages automatically.

If the request is underspecified, default to `Inbox`, `In progress`, and
`Archive` file buckets plus `Next actions` and `Handoff notes`, rather than
treating the request as unsupported. Ask one product question only when the
user explicitly requires mailbox synchronization, automatic classification,
or a named taxonomy that cannot be chosen defensibly.

## Composition rules

1. Use `refresh_frequency="manual"` for a fully data-free workspace.
2. Keep saved text, checklist state, and uploaded-file keys outside manifest
   patches; only presentation and seed fields belong in the template.
3. Preserve widget ids and modes after the first save.
4. Do not claim that a seed, upload, move, or browser save occurred during the
   build turn unless verified persisted state proves it.
5. Add analytical charts or tables only when they answer a requested product
   need; do not add them to make a productivity workspace look like a
   conventional market dashboard.
