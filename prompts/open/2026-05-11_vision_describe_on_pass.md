---
session: vision describe-on-pass — extend post-exec QC sweep so every passing chart returns a macro/rates analyst-eye description that lands in sandbox stdout
sent: 2026-05-11
class: implementation-directive (NOT context-extraction; NOT end-usage)
files_to_modify:
  - ai_development/mcp/utils/vision_functions.py (QUALITY_CHECK_PROMPT body + parser in check_chart_quality + per-future fail-open dict in check_charts_quality_parallel)
  - ai_development/mcp/tools/script_exec_tools.py (_check_charts_quality_injected — add stdout printing loop after the parallel call returns)
reply_folded_into:
  - confirmation back to staging (post-impl) so chart_context.md §2 + dev/notes.md Track 3 + the staging stub at projects/altair/ai_development/mcp/utils/vision_functions.py can be updated to close the loop
status: pending
---

Title: Vision describe-on-pass — fuse QC + analyst-eye chart description into the post-exec sweep

The post-exec vision sweep today calls Gemini-3 Flash Vision with the
chart PNG and a long QC prompt that returns `GOOD` or `BAD: <diagnostic>`.
The verdict gates whether the chart is "ready for delivery". When a chart
passes, the sweep records the verdict and moves on — PRISM gets nothing
visual back.

This change repurposes the sweep. Every chart still gets a QC verdict,
but on `GOOD` the same Gemini call additionally returns a 2-5 sentence
analyst-eye description (trends, turning points, divergences, outliers,
annotation implications, core dynamic). The description gets printed
to sandbox stdout under a structured prefix, so PRISM sees a visual
readback of every chart it rendered in the same turn the script ran.
Cost stays at one Gemini-Flash call per chart — the QC and description
are fused into a single prompt.

Three concrete things change:

  1. `QUALITY_CHECK_PROMPT` (the constant in `vision_functions.py`) —
     RESPONSE FORMAT section rewritten, new DESCRIPTION REQUIREMENTS
     section appended, one-token typo fix in the intro line.
  2. `check_chart_quality` parser — extract description on `GOOD`,
     return it in a new `description` field on the result dict.
     `check_charts_quality_parallel` per-future fail-open dict gains
     the same field.
  3. `_check_charts_quality_injected` in `script_exec_tools.py` —
     after the parallel call returns, loop the result list and
     print one structured line per chart to sandbox stdout. The
     print happens INSIDE the sandbox's `redirect_stdout` block so
     the LLM sees the lines in the same captured script-output
     stream.

Reply with:

  - a single `## Confirmation` block at the end listing the four
    files actually edited (with the new line ranges or function
    names you touched), so the staging side knows what shipped
    and can update its mirror.
  - a `## Frictions` section IF anything in this spec did not
    apply cleanly (an existing prompt section the spec assumes
    is gone, an existing parser branch not described here,
    an injected-name collision, etc.). No friction = no section.

This is an **implementation directive**, not a context-extraction
prompt. Do not paste signatures or docstrings back. Edit the files,
confirm what changed, surface any frictions.

---

## 1. New QUALITY_CHECK_PROMPT (verbatim — replace the entire constant body)

Replace the entire `QUALITY_CHECK_PROMPT` string constant in
`ai_development/mcp/utils/vision_functions.py` with the block below
EXACTLY. The three differences vs the previous version:

  - Intro line: `"FIVE categories"` -> `"SIX categories"` (fixes
    long-standing mismatch with the body, which has listed six
    since category 6 was added).
  - `RESPONSE FORMAT` section: both branches now carry a payload
    (`GOOD: <description>` / `BAD: <diagnostic>`).
  - New `DESCRIPTION REQUIREMENTS (for GOOD charts)` section
    inserted between `RESPONSE FORMAT` and `FAILURE DESCRIPTION
    REQUIREMENTS`.

Everything else (the six category blocks, the THINGS THAT ARE NOT
DEFECTS list, the FAILURE DESCRIPTION REQUIREMENTS structure) is
unchanged byte-for-byte.

```text
You are a chart quality inspector for a professional financial analytics platform. Your job is to determine whether this chart is GOOD (ready for delivery to a Goldman Sachs professional) or BAD (has a defect that would make it misleading, unreadable, or unprofessional).

You must evaluate the chart across SIX categories. A failure in ANY category makes the chart BAD.

### CATEGORY 1: DATA PRESENCE AND INTEGRITY
Is there actual, meaningful data displayed?

Fail if:
- The chart is completely empty -- no visible data points, lines, or bars
- The chart area is blank white with only axes/title visible
- Only a single data point is shown when a time series or distribution is expected
- All data points are at exactly the same value (flat line at zero, NaN, or any constant), suggesting missing or placeholder data rather than genuinely flat economics
- Data shows obvious corruption: sawtooth patterns oscillating between zero and real values, extreme vertical spikes at regular intervals, or random noise inconsistent with the data type
- A significant portion of the series is missing (e.g., data stops abruptly mid-chart, leaving large empty regions)

### CATEGORY 2: VISUAL READABILITY AND SCALE
Can a reader actually SEE and DISTINGUISH all the data the chart is trying to show?

Fail if:
- **Scale compression / dominated axis**: Two or more series share a y-axis but have vastly different magnitudes, causing one or more series to appear as a flat line with no visible variation. Example: one series ranges 0-500, another ranges 0-5 -- the smaller series is unreadable. The fix is dual y-axes or separate panels.
- **Outlier domination**: A small number of extreme outliers stretch the axis so far that 90%+ of the data is compressed into a narrow band with no visible variation. The chart becomes useless for understanding the typical behavior of the data.
- **Excessive whitespace**: Data is crammed into a tiny portion of the chart area (e.g., all data in the bottom 10% of the y-axis range, or clustered in one corner of a scatter plot) with the rest of the chart empty.
- **Indistinguishable series**: Multiple series are plotted but are visually impossible to tell apart -- e.g., lines that overlap completely, colors that are too similar to differentiate, or so many series that the chart becomes an unreadable tangle.
- **Invisible or nearly invisible elements**: Data elements (lines, bars, points) that are too thin, too small, or too faint to see clearly.

### CATEGORY 3: LABELS, AXES, AND TEXT
Are all textual elements legible, correctly placed, and non-overlapping?

Fail if:
- Axis labels, tick labels, or titles overlap each other to the point of illegibility
- Text is truncated, cut off by the chart boundary, or extends outside the visible area
- Axis tick labels are garbled, nonsensical, or show raw code/column names instead of formatted labels (e.g., "PCUSLEAF@USECON" instead of "Core PCE YoY (%)")
- Font sizes are so small that labels are unreadable
- Axis labels are missing entirely when they are needed to understand the data (e.g., no y-axis label on a chart where the units are ambiguous)

### CATEGORY 4: LAYOUT AND ELEMENT COLLISIONS
Do chart elements coexist without interfering with each other?

Fail if:
- The legend covers, obscures, or overlaps the actual data
- Annotations, text boxes, or labels collide with data elements or each other
- In multi-panel/composite charts (grids, side-by-side, stacked panels): titles, axes, or labels from one panel overlap into another panel's space
- Chart elements extend beyond the plot area or are clipped in a way that loses information
- Shaded regions, bands, or reference lines obscure the primary data

### CATEGORY 5: MULTI-PANEL / COMPOSITE CHART INTEGRITY
(Only applies if the image contains multiple sub-charts/panels)

Evaluate EACH panel independently against Categories 1-4 above. The composite chart is BAD if ANY individual panel fails.

Specifically check each panel for:
- Flat lines at zero or constant values suggesting missing/placeholder data
- Scale compression where one panel's data variation is invisible
- Empty panels with only axes visible
- Panels where the data looks qualitatively different from what the title/label promises

Report WHICH panel (by position: top-left, top-right, bottom-left, bottom-right, or row/column number) and WHICH series within that panel is problematic.

### CATEGORY 6: ANNOTATION PLACEMENT VALIDITY
Do vertical line annotations (VLines) and horizontal line annotations (HLines) fall within the actual data range of the chart?

Fail if:
- A vertical line annotation is placed at an x-axis position (typically a date) that is OUTSIDE or at the very edge of the data's x-axis range, making it appear crammed against the left or right border of the chart with no data context around it. Example: the time series data ends in January 2026 but a vertical line annotation marks an event in March 2026 -- the line would appear at or beyond the right edge of the chart, looking broken and providing no useful visual context.
- A horizontal line annotation is placed at a y-axis value that is far OUTSIDE the actual data range, causing it to appear crammed against the top or bottom border of the chart (or forcing the y-axis to stretch dramatically to accommodate it, compressing the real data). Example: data ranges from 2% to 5% but a horizontal reference line is drawn at 15%, pushing all the actual data into a tiny band at the bottom.
- Multiple vertical or horizontal line annotations cluster at the extreme edges of the chart where there is no corresponding data, suggesting the annotations reference values or dates not covered by the dataset.

Note: An annotation that falls slightly outside the data range (e.g., a few days beyond the last data point) but is still clearly visible and contextually useful is acceptable. The defect is when the annotation is so far outside the data range that it looks broken, is crammed against a chart border, or distorts the chart's scale.

### THINGS THAT ARE NOT DEFECTS (do not flag these)

- Two y-axes (left and right) with different scales -- this is an intentional dual-axis pattern
- Left and right y-axes showing different units or ranges -- valid dual-axis design
- An inverted y-axis (higher values at bottom) -- intentional for certain financial charts (e.g., yield charts where lower = better)
- A genuinely flat or low-volatility trend that is still clearly readable -- not every series needs dramatic variation
- Sparse data (e.g., quarterly points) as long as the points are visible and the chart is readable
- Shaded recession bars or event markers that are clearly background context, not obscuring data
- Dense x-axis labels on long time series, as long as they remain legible

### RESPONSE FORMAT

Respond with EXACTLY one of:

GOOD: <analyst-eye description, see DESCRIPTION REQUIREMENTS below>

or

BAD: <detailed diagnostic, see FAILURE DESCRIPTION REQUIREMENTS below>

### DESCRIPTION REQUIREMENTS (for GOOD charts)

You are providing the analyst who built this chart with a visual readback they can use in the same conversation. They have the underlying DataFrame but cannot see the rendered image. Translate the visual signal into the kind of read a macro / rates trader would produce after glancing at it for ten seconds.

2-5 sentences, compact prose, no headers, no bullets, no markdown. Cover whichever of these are visible and load-bearing for the chart's argument (skip what does not apply):

- **Level and trend.** Where the data sits and whether it is rising / falling / sideways. Use approximate numbers when readable from the axes.
- **Turning points and regime shifts.** Dates or x-positions where the trajectory changes character (acceleration, reversal, break of trend, return to range). Name the dates if the x-axis is visible.
- **Divergences and co-movement** (multi-series only). Where series move together, where they decouple, which leads and which lags, the approximate gap size.
- **Outliers and standouts.** Single points or short windows that depart from the broader shape (the spike in March 2020, the cluster of misses since the rate-cut cycle started, etc.).
- **Annotations.** If VLines / Bands / Callouts / HLines / LastValueLabels are present, weave their implications into the read -- the recession band, the policy-rate threshold, the labelled event date.
- **Core dynamic.** One sentence on the underlying mechanism the visual is consistent with: a tightening cycle is biting, a base effect is rolling off, real rates are catching up to nominal, etc. Speculate cautiously -- the visual is the evidence.

For multi-panel composites (small-multiples, n-pack grids, dual-axis split panels), give one sentence per panel rather than a single blob. Identify each panel by position (top-left, bottom-right, row 1 column 2) or by its title if you can read it.

Voice: macro / rates analyst. Concrete numbers when readable. No purple prose. No restating the title or subtitle. No "this chart shows..." preambles -- start with the substance.

### FAILURE DESCRIPTION REQUIREMENTS (for BAD charts)

The person reading your diagnostic CANNOT see the chart. Your description is the ONLY information they have to identify and fix the bug. You must be extremely specific and detailed. Structure every BAD response with ALL of the following:

1. **FAILED CATEGORY**: Which of the 5 categories above was violated (can be multiple)
2. **WHAT is wrong**: Precise description of the visual defect. Use concrete language: "The blue line labeled 'Core CPI YoY' appears as a flat horizontal line at approximately zero" -- not vague language like "some data looks off."
3. **WHICH element**: Identify the problematic element by color, label text, legend entry, position, or panel location. If you can read the series name from the legend or axis, use it.
4. **WHERE in the chart**: Spatial location (e.g., "the right y-axis", "the bottom-right panel", "the left half of the x-axis from 2020-2023") and temporal location if applicable (e.g., "after January 2024", "in the most recent 6 months").
5. **SCALE/MAGNITUDE context**: If relevant, state the approximate numerical ranges you can observe (e.g., "the dominant series ranges from -200 to +400, while the compressed series ranges from -2 to +5").
6. **LIKELY ROOT CAUSE**: Your best hypothesis for what went wrong in the data pipeline or charting code. Examples:
   - "Suggests quarterly data was forward-filled to monthly before computing YoY change, causing within-quarter values to be zero"
   - "Looks like NaN values were filled with 0 instead of being dropped"
   - "Two series with fundamentally different units (basis points vs percentage points) are plotted on the same y-axis without dual-axis treatment"
   - "The y-axis range appears to be set by a single outlier spike around March 2020, compressing all other variation"
   - "Axis labels appear to be raw DataFrame column names instead of formatted display titles"
7. **SUGGESTED FIX**: Brief recommendation (e.g., "Use dual y-axes", "Separate into two panels", "Clip or remove the outlier", "Check the data join for NaN fill behavior").

Be exhaustive. When in doubt about whether something looks wrong, flag it -- false positives are better than missed defects.
```

Note the `FAILURE DESCRIPTION REQUIREMENTS` block still says "the 5
categories above" in point 1. Leave that as-is — it's a minor wording
slip but changing it would require re-reading the whole prompt as a
diff against today's version. The model's category-identification
behaviour does not depend on this number.

---

## 2. New `check_chart_quality` return shape

Add a `description: Optional[str]` field to the result dict everywhere
the parser returns. The four return-statement branches inside
`check_chart_quality` should look like this:

```python
# Branch 1: GOOD with description (the common case)
if answer.upper().startswith('GOOD'):
    # answer might be "GOOD: <description>" or just "GOOD"
    description = answer[4:].strip().lstrip(':').strip() if len(answer) > 4 else None
    return {
        'passed':      True,
        'verdict':     'GOOD',
        'reason':      None,
        'description': description or None,   # collapse empty string to None
        'error':       None,
    }

# Branch 2: BAD with diagnostic
elif answer.upper().startswith('BAD'):
    reason = answer[3:].strip().lstrip(':').lstrip('.').strip() if len(answer) > 3 else 'No reason provided'
    return {
        'passed':      False,
        'verdict':     'BAD',
        'reason':      reason,
        'description': None,
        'error':       None,
    }

# Branch 3: unexpected response format -- fail open
else:
    return {
        'passed':      True,
        'verdict':     'GOOD',
        'reason':      None,
        'description': None,
        'error':       f'Unexpected response format: {answer[:100]}',
    }
```

And the outer exception handler (currently `except Exception as e: return {'passed': True, ...}`):

```python
except Exception as e:
    return {
        'passed':      True,
        'verdict':     'GOOD',
        'reason':      None,
        'description': None,
        'error':       str(e),
    }
```

The parser is permissive about a bare `GOOD` with no description —
sets `description=None`, does not raise. This is deliberate so a
model that ignored the new prompt format still passes through cleanly.

---

## 3. `check_charts_quality_parallel` per-future fail-open dict

The per-future `except` block inside `check_charts_quality_parallel`
(the one that triggers when a single worker raises) should produce
a fail-open dict that includes `description=None`:

```python
except Exception as e:
    return {
        'path':        chart_items[idx].get('path', 'unknown'),
        'passed':      True,        # Fail-open
        'verdict':     'GOOD',
        'reason':      None,
        'description': None,
        'error':       str(e),
    }
```

No other change to the parallel implementation. Worker count,
order preservation, ThreadPoolExecutor semantics — all unchanged.

---

## 4. `_check_charts_quality_injected` — stdout printing loop

After the parallel call returns and BEFORE the function returns
its result list, loop the results and print one structured line per
chart to stdout. Sandbox-stdout is already captured by the existing
`redirect_stdout` block in `execute_with_timeout`, so a regular
`print()` is all that's needed.

Conceptually:

```python
results = check_charts_quality_parallel(chart_items, max_workers=max_workers, s3_manager=s3_manager)

for r in results:
    path = r.get('path', '<unknown>')
    if r.get('passed') and r.get('description'):
        print(f"[ChartDescribe:{path}] {r['description']}")
    elif not r.get('passed'):
        reason = r.get('reason') or '<no reason>'
        print(f"[ChartQC FAIL:{path}] {reason}")
    # passed=True with no description (fail-open / empty) emits nothing

return results
```

Constraints:

  - One line per chart. Long descriptions go on one logical line —
    do NOT wrap them. If a description happens to contain a literal
    newline, replace internal newlines with `" "` before printing
    so each chart still occupies exactly one stdout line. PRISM's
    own line-parsing convenience is the binding constraint.
  - Order follows the result list, which follows input order, which
    follows the order PRISM rendered the charts in.
  - Prefix grammar is exact: `[ChartDescribe:<png_path>] <text>` for
    passes, `[ChartQC FAIL:<png_path>] <text>` for fails. PRISM
    will eventually be taught to look for these prefixes in its
    own stdout; the strings are part of the user-facing contract.
  - The function's RETURN value is unchanged — same list of dicts
    as today (now with `description` populated). Callers that ignore
    stdout still get the verdict via the return value.

If the existing `_check_charts_quality_injected` does anything else
in this position — logging to a side channel, mutating a session
artifact registry, writing a structured QC summary — keep that.
The stdout printing is additive, not a replacement.

---

## 5. What NOT to change

  - Do NOT touch `describe_images` or `DEFAULT_VISION_PROMPT`. That
    pipeline serves non-chart free-form image description tasks (PDF
    page comprehension via `imagify_pdf`, ad-hoc visual analysis) and
    is intentionally independent of the chart pipeline.
  - Do NOT change the model identifier (`gemini-3-flash-vision`),
    the endpoint (`https://uat.gpt.site.gs.com/conversation-service`),
    the app id (`us-rates-ai`), or the multipart-upload mechanics.
    The change is prompt + parser + printer only.
  - Do NOT introduce a second Gemini call per chart. The QC verdict
    and the analyst-eye description come from the SAME call via the
    fused prompt above. If you find yourself adding a follow-up call
    to `describe_images` after a `GOOD` verdict, stop — that is the
    wrong shape.
  - Do NOT alter the fail-open semantics. `passed=True` on any
    exception, network error, parse error, unexpected response, etc.
    Callers that want robustness specifically must continue to check
    `error is None` rather than just `passed`. Callers that want a
    description specifically must additionally check
    `description is not None`.
  - Do NOT change the sandbox-namespace injection (the
    `functools.partial(_check_charts_quality_injected, s3_manager=...)`
    in `script_exec_tools.py`). The LLM-facing name
    `check_charts_quality` continues to point at the same callable.

---

## 6. Acceptance criteria

After the edits, the following should hold:

  1. `QUALITY_CHECK_PROMPT` contains the literal strings
     `"DESCRIPTION REQUIREMENTS"`, `"GOOD: <analyst-eye description"`,
     and `"evaluate the chart across SIX categories"`. Easy grep
     confirmation.
  2. A live run that produces at least one chart and at least one
     intentionally-bad chart prints both prefix shapes to stdout —
     `[ChartDescribe:<path>] ...` for the good one,
     `[ChartQC FAIL:<path>] ...` for the bad one — in render order,
     visible in the script's returned stdout.
  3. The result dict returned by `check_charts_quality_parallel`
     (and exposed as `check_charts_quality` in the sandbox namespace)
     includes a `description` key on every entry. Value is a non-empty
     string for GOOD entries, `None` for BAD or fail-open entries.
  4. Total Gemini calls per script = total charts rendered.
     Specifically, NOT 2x charts. The fused single-call shape is the
     point.
  5. A script that renders one chart and immediately raises an
     exception still produces the description for that one chart in
     the captured stdout — the post-exec sweep runs on whatever
     `S3ManagerWrapper` recorded before the exception, independent
     of script success.

You can sanity-check the prompt change with a one-off `make_chart`
that produces an obviously-good chart (e.g. US 2s10s monthly since
2010 with a default `multi_line`), then inspect the captured stdout
for the `[ChartDescribe:` line. A good description should mention
the recent dis-inversion or the steepening since late 2025; a
mediocre one would just describe the line's shape without any
macro framing — if you see the mediocre kind, the DESCRIPTION
REQUIREMENTS section may need re-tuning (surface as a friction in
the reply).

---

## 7. Reply format

End your reply with these two sections, in this order:

### Confirmation

Four bullets — one per file you touched — naming the function /
constant changed and the rough line range. Example shape:

```
- ai_development/mcp/utils/vision_functions.py
    - QUALITY_CHECK_PROMPT (constant, lines ~XXX-YYY): replaced body
      with new fused prompt
    - check_chart_quality (function, lines ~XXX-YYY): parser extended
      with description field across 4 branches
    - check_charts_quality_parallel (function, lines ~XXX-YYY):
      per-future fail-open dict gains description=None
- ai_development/mcp/tools/script_exec_tools.py
    - _check_charts_quality_injected (function, lines ~XXX-YYY):
      stdout printing loop appended before return
```

### Frictions (only if any)

If anything in this spec did not apply cleanly — an existing prompt
section that doesn't match the verbatim text above, a parser branch
this spec doesn't describe, an injected-name collision, a missing
constant — list each as a bullet:

  - what the spec assumed
  - what the file actually has
  - the minimal local decision you made to resolve it (or "blocked —
    need staging-side clarification")

No friction = no section. Do not add a stub Frictions section just
because the prompt mentions it.
