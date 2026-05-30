# Context-extraction prompt — recover `dashboards.md` §0 (invisibility principle) verbatim

**Why this exists (staging-side note, do NOT paste this header into PRISM):**
During the 2026-05-29/30 echarts housekeeping rebase, the OCR scan of the
PRISM-side diffs (`scans/inbox/transcribed_diffs_clean.md`) began partway
through the new §0 invisibility block of the preflight pointer
`dashboards.md` — the transcription starts mid-list at forbidden-item **#4**
(`"The ticket is filed with the dev team"`). The §0 header, the `0.0`
intro, and forbidden-list items **1–3** were never captured. Every other
section of `dashboards.md` has been reconstructed and applied locally; only
§0 is missing. This prompt recovers it verbatim so it can be dropped into
`projects/echarts/echarts-payload/dashboards.md` immediately after the intro
block (before `## 1. Folder layout`).

---

## Paste the following into PRISM

Read the installed L2 preflight pointer at
`context/modules/static/tools/dashboards.md` (the ECharts Dashboards
Pre-flight module — NOT the hub `dashboards_hub.md`).

Return, **verbatim and complete**, the entire **§0 invisibility-principle
section** of that file: from its section header (the first `##`-level
heading that appears AFTER the intro paragraph "ECharts is the ONLY
sanctioned path…" and BEFORE `## 1. Folder layout`) down to — but not
including — the `## 1. Folder layout` heading.

Reproduce it exactly as it appears in the file, preserving:

- The exact section heading text and number (e.g. `## §0 …` or `## 0. …`).
- Every sub-heading (`###` / `####`) in order, including any `0.0` and
  `0.1` subsections.
- The COMPLETE forbidden-phrases / forbidden-tokens numbered list —
  in particular items **1, 2, and 3**, which are the specific items I am
  missing. Include items 4–8 too so the full list is contiguous.
- All tables (e.g. the "What this means in practice" engineering-leak vs
  product-rewrite table), code/quote blocks, the leaked-message
  anti-example, the forbidden-phrase test, the probing exception, and the
  "mental test" closing paragraph — verbatim.
- Exact punctuation (em-dashes `—`, middots `·`, backticks, section
  references like `§2.5`).

Wrap the entire returned section in a single fenced ```markdown block so
whitespace and headings survive copy-paste. Do not summarise, paraphrase,
re-order, or add commentary — I need a byte-faithful copy to splice into a
staging file.

If part of this prompt cannot be answered, add a brief
`## Could not resolve` section at the end naming what was missing.
