# Stage 7 Completion Report — Component 4 (Visualization & Prediction Layer)

6 October 2026 · Wijethunge W M V (IT23256750) · Project J26-SE-347

## Summary

Stage 7 delivers the interface the TAF names: "React … to build the adaptive rendering and prediction interface", and the "Adaptive UI Dashboard (Grounded Visual Summaries)" at the end of the conceptual diagram. It also makes the what-if simulation *interactive*, as the sub-objective requires.

**What the user can do:**
- **Ask** a question about a result set, from a search-style box with example questions for each data source.
- **See the answer in its decided shape:** a single figure, table, chart, summary, or a report of all three.
- **Read the key figures** (total, change, next forecast, forecast total) as stat tiles. Each is a computed claim from the summary, not a number worked out in the browser.
- **Read the forecast notice:** shown, shown with cautions, or refused with the reason.
- **See the anomalies,** each marked as a one-off spike or a lasting shift, and described against what it was measured against (the season, the trend, or the plain spread).
- **Run what-if scenarios** with a slider (−50% to +50%, optionally phased in) or in words, and watch the chart and totals change.
- **Open "Show the working"** to trace every number to the computation behind it, grouped by history, anomaly check and forecast.
- **Open "Details"** for the question type, shape decision, guardrails, readiness, model, masking and timing.

**How it is wired:** the UI calls the component's real `/api/v4/present` and `/api/v4/simulate`, and shows the real `/api/v4/health` status in its top bar. Only the masked rows come from stand-ins (`demo_api.py`), because the other members' services are not connected yet.

**How it was checked:**
- 14 UI tests over real API responses.
- A real browser (Microsoft Edge): 12 screens in light mode, dark mode and phone width.

**What the real browser found:** looking at the rendered output exposed **eight backend defects** that no earlier test had caught. Several came from my own earlier stages. All are fixed and covered by tests.

All Stage 7 work is in the working tree of branch `vonara-nl-to-sql-prototype-stage-7`, which contains Stages 1–6. Nothing has been committed or pushed, and `main` is untouched.

## Check against the TAF (sub-objective of IT23256750)

| TAF item | Where it stands |
| --- | --- |
| Adaptive Vega-Lite engine from query semantics and result cardinality | Built (Stage 1); now **rendered** in the UI |
| Formally defined intent-to-prediction mapping (SARIMA, Linear Regression) | Built and benchmarked; the formal write-up is Stage 8 |
| Data readiness classifier: temporal validity, statistical sufficiency, signal quality | Built (Stage 2); shown in the forecast notice and the Details tab |
| Dual-dimension anomaly detection, IQR + Z-score, past and future breaches | Built (Stage 3); shown as an anomaly panel and as chart markers (▲ past, ◆ projected) |
| Unified temporal summarization, verified historical and predictive statements | Built (Stages 1, 4); "show the working" exposes every claim's derivation |
| **Interactive** what-if scenario simulation | **Stage 7**: slider, scenario box and presets, with the redrawn chart and before/after totals |
| React adaptive rendering and prediction interface | **Stage 7** |
| Intent-informed caching | **Stage 8**: the cache is keyed on the exact question text today |

## Work completed

1. **`demo_api.py`.** It wraps the production API unchanged and adds two stand-in routes:
   - `/demo/datasets`: 11 data sources in three groups (time series, breakdowns, records and figures), each with a kind for its icon and up to six example questions. The examples come from the integration fixtures, plus a few added per source; each added one was run through `/api/v4/present` first.
   - `/demo/rows`: a data source's SQL run on the SQLite test database, returned in Member 2's exact masked format.

   It also serves the built UI. The production `api.py` is unchanged.
2. **React UI** (`frontend/`, React 19 + Vite + vega-embed). Following the client rendering contract, it renders `response.blocks_emitted` in order and computes no numbers.

   | Area | What it shows |
   | --- | --- |
   | Top bar | Live API status from `/api/v4/health` (version, rules only or LLM), the current tenant, and a system / light / dark switch |
   | Sidebar | Data sources grouped, with an icon for each kind; "What Member 2 sent": tenant, rows, columns, masked columns as tags, and the SQL used as the Member 1 stand-in |
   | Question box | Search-style input (press `/` to focus) and the source's example questions as chips. A welcome panel shows before the first question and a loading skeleton while one runs. |
   | Result header | The question, then pills for the answer shape, the analytical intent and its confidence, and the time taken (and whether it came from the cache) |
   | Forecast notice | ✓ shown, ! shown with cautions (listed), ✕ refused with the reason |
   | Key figures | Up to four stat tiles taken from the summary's claims: total, average, highest and change, or total, change, next forecast and forecast total. Large values are shortened (777K), with the full value on hover. Not shown for single answers or record lists. |
   | Answer card | One large figure. A forecast answer gets a badge, its range and the model. |
   | Summary | The text, its mode, and how many of its numbers were traced to a claim |
   | Table | Masked columns marked with a lock and counted; forecast rows in italics; row counts, truncation and limit notes |
   | Chart card | A title built from the encoding ("Total amount by month", "Distribution of amount"), the backend's reason for the chart as subtitle, a Chart / Table switch, and the key (line style and marker shape as well as colour) |
   | Tabs | **Anomalies** (count), **What-if** (disabled, with the reason, when there is no forecast), **Show the working** (claim count), **Details**. Keyboard arrows move between tabs, and a what-if result survives switching away. |
   | What-if | A −50% to +50% slider with "Phase in gradually", or free text and four presets. Shows baseline and scenario totals, the difference, the parsed scenario and the redrawn chart, or why the scenario was not simulated. |

   The styling is a small design system in `src/styles.css`: colour tokens selected for light and dark (not inverted), cards, pills, tabs and tooltips. The primary button blue keeps white text at 4.9:1 (light) and 6.1:1 (dark). The dark-mode accent alone gave 3.7:1, so the button uses a deeper step. On a phone, the sources become a scrolling strip and the question box comes straight after them.
3. **Chart theme** (`src/theme.js`). It uses the reference palette of the data-viz method, validated with its own script in both modes:
   - All gates pass, with a worst adjacent CVD ΔE of 9.2 (light) and 9.4 (dark).
   - Light-mode aqua is below 3:1 contrast. The method's relief rule applies, so every chart has the shape-and-line key and a table view.

   The backend's colour constants are mapped by role (history, forecast, scenario, anomaly, threshold), so the API contract did not change for the UI. The theme also:
   - drops the backend's title, since the card header names the chart;
   - rings filled anomaly markers with the surface colour so they stand off the line;
   - keeps chrome recessive (horizontal grid only, no y-axis line);
   - removes colliding x-axis labels.
4. **Tests.**
   - `src/ui.test.jsx`: 14 tests over fixtures captured from the real API by `scripts/make_fixtures.py`. New since the first version: key figures come from the claims, tabs and the disabled what-if, the slider's scenario wording, chart naming, the anomaly list, and the health status.
   - `scripts/screenshot.mjs`: drives Edge through 12 screens, checks that charts draw, logs console errors, and tests phone-width overflow.
   - `test_integration.py` section 7: 9 Python checks for the backend fixes.

## Defects found by looking at the rendered UI

| What the screen showed | Cause | Fix |
| --- | --- | --- |
| Seasonal expense chart with "normal range" lines at ±2,700 and the axis down to −5,000 | In the STL seasonal space (Stage 3) the anomaly band is a *deviation*, but it was drawn as a level. Stage 1's guard covered detrending only. | Rules drawn only when the band is in the value's own space |
| Anomaly markers drawn as circles, not the triangles in the key | The past/forecast shape encoding had no scale, so Vega's default circle overrode the mark | Explicit scale: ▲ past, ◆ projected |
| An employee list showing "2018 is a moderate high outlier at 164,300" | A list with a hire date and a salary was treated as a time series, so anomaly bands and outlier claims applied to individuals | No anomaly bands for record lists (`DETAIL_LOOKUP`) |
| A noisy spend chart with a "normal range" line at −2,000, the axis below zero | The lower IQR fence was below zero for a never-negative measure | Not drawn when it is below zero and the data isn't |
| "Total total amount across the returned period" | The summary prefixed "Total" to a measure already called "total amount" | Prefix only when the measure isn't already a total |
| Vega's own legend repeated part of the chart key | An explicit legend on the encoding overrides the global setting | The key replaces it for single-series overlay charts |
| "Show spend by vendor": a chart card with nothing Vega could draw | The question reads as a row lookup (`DETAIL_LOOKUP`) but asks for a chart. The chart is only built for a CHART block, after guardrail G2 has found the rows chartable, yet the encoder still chose a data grid with no mark. A correlation with only one measure did the same. | Bars across the category instead; a grid only when there is nothing to plot. The UI also shows a table if a spec ever has no mark. |
| The employee list's working: "average salary per period", "over the period the value increased … 39.5%" | A record list with a date column (`hire_date`) has one row per date, so the summary treated it as a time series | Record lists (`DETAIL_LOOKUP`) are described per row, with no first-to-last change and no date on the highest value |

The UI's own layout issues were also fixed:
- At phone width, the one-column grid could not shrink below its content.
- A favicon request returned 404.
- "1 periods".
- A seasonal outlier read "unusually low" at a value above the overall average. It is now "below its seasonal norm" (or "below the trend" for a detrended series).

## Results

### Real browser (Edge, headless, 1280 px and 390 px)

| Check | Result |
| --- | --- |
| Screens rendered | 12: welcome, forecast chart (light, dark), what-if from the slider, show the working, vendor bars, PII table, forecast answer, histogram, refused forecast, report (dark), report at phone width |
| Chart marks drawn | Forecast chart 77 (light and dark); vendor bars 118; histogram 40. Fewer than in the first version because the theme no longer draws a title, y-axis line or y ticks. |
| Console errors | 0 |
| Horizontal overflow at 390 px | none |

Screenshots: `data_and_reports/stage7_screenshots/`.

### Tests

| Suite | Result |
| --- | --- |
| UI tests (Vitest, real API fixtures) | 14 / 14 |
| Python suites | All 10 pass; `test_integration` now has 38 checks |
| Integration fixtures (77 questions) | 75 / 77, unchanged (the same two intent disagreements, L02 and M01) |
| HTTP rehearsal | 0 contract problems, 0 PII values leaked (7,647 checked), denylist and tenant isolation hold |
| Summary grounding (`evaluate.py`) | 100% (415 of 415 numbers, 12 of 12 summaries) |
| Production build | Succeeds. 263 kB app (83 kB gzipped), plus an 866 kB Vega chunk loaded on demand. |

## Limitations and open issues

1. **Not usability-tested.** The UI has been checked for correctness and accessibility mechanics (keys, table views, contrast relief, keyboard focus, labelled regions), but no user study has been run. The roadmap's "adaptive vs static presentation" usability evaluation is still open.
2. **Stand-in data.** The UI asks questions about the 11 integration result sets. Free-text questions work, but the SQL is the data source's own and not generated from the question. That is Member 1's part.
3. **The JS bundle is large**, mostly Vega (866 kB). It's split out and loaded on demand.
4. **Record-list wording depends on the intent being right.** A trend question misread as a row lookup (fixture M01, "how sales did this year") is now described per row, without the change figure. It is one of the two known intent disagreements.
5. **Not run:** the forecasting, anomaly and verifier benchmarks. The forecasting code is unchanged. The anomaly engine itself is unchanged; only when it runs (record lists) and how its band is drawn changed.

## Files

| File | Change |
| --- | --- |
| `frontend/` | New: React UI (`src/App.jsx`, `src/components/*`, `src/theme.js`, `src/format.js`, `src/api.js`, `src/styles.css`), tests, fixture and screenshot scripts, README |
| `demo_api.py` | New: demo server (the real API, two stand-in routes with grouped sources and checked example questions, the built UI) |
| `visualization.py` | Anomaly shape scale; threshold rules only in the value's own space; no negative lower bound for non-negative data; a CHART block never gets a markless data grid when the rows can be plotted |
| `pipeline.py` | No anomaly bands for record lists |
| `summarization.py` | No "Total total …"; record lists described per row, without a first-to-last change |
| `test_integration.py` | Section 7: 9 checks |
| `data_and_reports/` | README, roadmap, team contract, this report, screenshots |

**To reproduce:**
- `python test_db/seed.py`
- `cd frontend && npm install && npm test && npm run build`
- `uvicorn demo_api:app --port 8004`, then open http://localhost:8004

## Next stage

Stage 8 is the final evaluation, plus the three TAF items still open:
- **Intent-informed caching:** key on the analysis, not the question text, and measure it.
- **Vega-Lite schema validation** of every spec.
- **A written formal definition** of the intent-to-prediction mapping.

Then re-run every benchmark and write the results chapter.
