# Component 4 user interface

React interface for the Presentation & Prediction Layer. It renders what the
component returns: the answer, table, chart and summary blocks; the forecast
notice; key figures taken from the summary's claims; and four tabs —
anomalies, the interactive what-if (slider or words), the "show the working"
claim trace, and details of every decision.

The app has its own identity: an indigo brand colour (white text 6.3:1) and a
chart mark - a solid history line turning into a dashed forecast - on a
deep-slate sidebar. Charts keep the validated data-viz palette, so the
interface colour never competes with history (blue), forecast (orange),
scenario (green) or anomalies (red).

**It fills the window and the page never scrolls.** Long content scrolls
inside its own card or pane; on the Ask screen the result sits on the left
(the chart takes the free height) and the analysis tabs on the right. This is
checked at 1440 x 900 and 1366 x 768 by `scripts/screenshot.mjs`. Below
1024 x 620 (phones, small windows) the layout becomes one column and the page
scrolls normally.

There are two separate apps on one server:

- **The user app** (`#/ask`, the default): what a business user sees. Brand,
  connection status, the question box and the answers. No sidebar and no
  links to administration.
- **The admin console** (`#/admin/...`): a sidebar with the pages below, for
  whoever runs the component. It is reached by its URL only and links out to
  the user app. It has no login yet: access control is Member 3's part.

| Screen | URL | What it shows |
| --- | --- | --- |
| Ask (user app) | `#/ask`, `#/ask/<source>` | Centred question box, source picker and example questions; after asking, the result workspace |
| Dashboard | `#/admin` | Sources, records, questions asked and forecasts shown/refused; data sources and recent questions |
| Data sources | `#/admin/sources` | Every source by group: tenant, privacy, columns, records |
| Data source | `#/admin/sources/<source>` | Fields (masked ones marked), sample records exactly as Member 2 sends them, the SQL, a connection test |
| Configuration | `#/admin/configuration` | The forecasting policy in force (`forecast_config.json`), read-only |
| Activity | `#/admin/activity` | Questions asked from this browser (the API keeps no history) |

Questions-asked figures come from this browser's log (`src/activity.js`);
every other figure comes from the API.

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

Then open http://localhost:8004 for the user app, or http://localhost:8004/#/admin for the admin console.

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
npm test                                          # 22 UI tests
python frontend/scripts/make_fixtures.py          # refresh fixtures (run from the component folder)
node scripts/screenshot.mjs <dir>                 # real-browser screenshots (Edge, needs the server)
```

- **UI tests** render real API responses captured by `make_fixtures.py`, not hand-written JSON. Re-run that script after any change to the response envelope or to `demo_api.py`'s data sources.
- **The screenshot script** needs `npm install --no-save playwright-core` and the demo server running. It drives 16 screens (ask, result, what-if, dashboard, sources, source detail, configuration, activity; light, dark, 1366 x 768 and phone width) and reports console errors, whether each page scrolls, and phone-width overflow. To use a server on another port, set `UI_URL`, e.g. `UI_URL=http://localhost:8005`.
