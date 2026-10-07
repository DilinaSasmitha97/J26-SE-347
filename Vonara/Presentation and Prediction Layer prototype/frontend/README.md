# Component 4 user interface (Stage 7)

React interface for the Presentation & Prediction Layer. It renders what the
component returns: the answer, table, chart and summary blocks; the forecast
notice; key figures taken from the summary's claims; and four tabs —
anomalies, the interactive what-if (slider or words), the "show the working"
claim trace, and details of every decision.

Layout: a top bar (API status, tenant, theme), grouped data sources and what
Member 2 sent on the left, the question box and the result on the right. On
a phone the sources become a scrolling strip above the question box.

It follows the client rendering contract in
`data_and_reports/team_interface_contract.md`:
- render from `response`, in the order of `response.blocks_emitted`
- branch on key presence
- never compute a number in the browser

## Run it

From the component folder (`Presentation and Prediction Layer prototype/`):

```bash
python test_db/seed.py                 # once: builds the SQLite test database
cd frontend
npm install                            # once
npm run build                          # builds dist/
cd ..
uvicorn demo_api:app --port 8004       # API + the built UI
```

Then open http://localhost:8004.

**For UI development with hot reload**, keep `uvicorn demo_api:app --port 8004` running and run `npm run dev` in `frontend/`, then open http://localhost:5173. Vite forwards `/api` and `/demo` to port 8004.

## Where the data comes from

The other members' services are not connected yet, so `demo_api.py` provides two stand-in routes:

| Route | Returns |
|---|---|
| `/demo/datasets` | the data sources and their example questions |
| `/demo/rows` | a dataset's SQL, run on the SQLite test database, returned in Member 2's exact masked `/api/query` format |

The UI then calls the **real** `/api/v4/present` and `/api/v4/simulate` with that payload, as the team's orchestrator will. Replacing `/demo/rows` with Member 2's real result is the only change needed for live use.

## Charts

The backend's Vega-Lite specs are rendered with `vega-embed`.

- **Colours.** `src/theme.js` maps the backend's colour roles (history, forecast, scenario, anomaly, threshold) to the validated palette of the data-viz method, in light and dark.
- **Accessibility.** Light-mode aqua sits below 3:1 contrast. Every chart therefore carries a key that uses line style and marker shape as well as colour, and a Chart / Table switch.
- **Titles.** The card header names the chart from its encoding (`chartTitle` in `src/theme.js`); the backend's title is dropped.
- **Numbers.** `src/format.js` only formats values the API sent (e.g. 777K with the full value on hover). It never computes one.

## Tests

```bash
npm test                                          # 14 UI tests
python frontend/scripts/make_fixtures.py          # refresh fixtures (run from the component folder)
node scripts/screenshot.mjs <dir>                 # real-browser screenshots (Edge, needs the server)
```

- **UI tests** render real API responses captured by `make_fixtures.py`, not hand-written JSON. Re-run that script after any change to the response envelope or to `demo_api.py`'s data sources.
- **The screenshot script** needs `npm install --no-save playwright-core` and the demo server running. It drives 12 screens and reports console errors and phone-width overflow. To use a server on another port, set `UI_URL`, e.g. `UI_URL=http://localhost:8005`.
