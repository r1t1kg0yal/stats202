---
class: context-extraction
topic: 07 — dashboards.md verbatim + the unidentified 11th spoke
expected_reply: ~19 KB
sent:
status: OPEN
---

**Staging-side note — do NOT paste this header into PRISM.**

`dashboards.md` measured identical on size (14,295 B / 147 lines, sha
`aaef1caad15a`) so this may come back MATCH — but the reported 11-file spoke
directory against our 10 is unresolved and matters more. Send this even if
prompt 01 classifies `dashboards.md` as MATCH; §2 is the real payload.

---

## Paste everything below into PRISM

You are being asked to print a file and enumerate a directory from your own
repository. Pure introspection: do not build anything, do not report frictions.

**Reply budget: keep this reply under roughly 30,000 characters.** The file is
about 14 KB, so it fits with room to spare.

### 1. The registered router

Paste `prism-core/context/modules/static/tools/dashboards.md` in full, in one
fenced block, exactly as it exists on disk — every blank line, every trailing
space, every code fence. Do not reflow or normalise anything. Head it with byte
count, line count and `sha256[:12]`, measured with any single trailing newline
stripped.

### 2. The spoke directory (the part I actually need)

2.1 List `prism-core/context/modules/static/tools/dashboards/` exhaustively:
filename, bytes, lines, `sha256[:12]`, and the last commit that touched each.

I believe that directory holds exactly these ten:

```
build.md  charts.md  diagnose.md  filters.md  pipelines.md
productivity.md  recipes.md  template_crud.md  widget_tool.md  widgets.md
```

2.2 If there are more than ten, name each extra file, paste it in full if it is
under 8 KB, and say when and by which commit it was added. If it is over 8 KB,
paste only its first 40 lines and its heading outline.

2.3 State which files in that directory, if any, are registry entries rather
than on-demand fetches. For the on-demand ones, give the exact `list_ai_repo`
call shape that resolves them today — specifically whether the short form
`dashboards/widgets.md` still works or a fully-rooted path is now required.

2.4 Paste the registry entry for `dashboards` verbatim — `module_id`, `pillar`,
`order`, `source`, `description`, and any `footer_note`.

---

If something cannot be answered, add a short `## Could not resolve` section at
the end naming what you tried and what blocked it.
