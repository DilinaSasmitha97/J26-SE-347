# AskDB — natural language interface to your databases

A working demo of the research system: users connect a database, ask questions in
plain English, and get back a **short answer**, a **description**, a **table**, a
**chart** and the **SQL that ran**. Database owners configure behaviour and
governance from an admin panel.

Built with **React + Vite** (client) and **Express** (server).

---

## Quick start

```bash
npm run install:all     # installs server + client dependencies
npm run dev             # starts the API on :4000 and the client on :5173
```

Open <http://localhost:5173>.

To run the production build from a single origin instead:

```bash
npm run build           # builds the client into client/dist
npm start               # Express serves the API and the built client on :4000
```

### Demo accounts

| Email | Role | Can do |
|---|---|---|
| `admin@askdb.io` | Owner | everything, including changing settings |
| `analyst@askdb.io` | Analyst | ask questions, export results |
| `viewer@askdb.io` | Viewer | ask questions only |

Password for all three: `demo1234`.

---

## What to show in a demo

1. **Ask a question.** On the Ask page, click a suggestion or type
   *“What was our total revenue last quarter?”*. The answer opens with the number,
   then the paragraph, then Chart / Table / SQL / *How I got this* tabs.
2. **Show the SQL.** The SQL tab holds the exact query that executed — nothing is
   canned. *How I got this* lists how each part of the sentence was resolved.
3. **Try different shapes of question.** They produce different answer forms:
   - `Show revenue by month over the last 12 months` → line chart
   - `Top 5 products by revenue this year` → ranked horizontal bars
   - `Gross profit by category` → bars with a donut alternative
   - `How many orders did we get last month?` → a single number with a
     period-over-period delta
4. **Show governance changing an answer.** In **Admin → Access control**, block the
   `products` table, then ask a product question again — it is refused, and the
   refusal names the setting responsible. Unblock it and the answer returns.
5. **Show the glossary.** In **Admin → Business glossary**, add
   `takings → revenue`, then ask *“What were our takings last month?”*. Step 1 of
   the reasoning shows the rewrite.
6. **Switch databases.** The header switcher moves between NorthWind Retail and
   PeopleOps HR; the schema, suggestions and settings all follow.
7. **Switch themes.** Light and dark are both designed, not auto-inverted.

---

## How it works

```
question
  │
  ├─ planner.js      parse the sentence against the semantic layer
  │                    metric · dimension · time grain · time range · filters
  ├─ (policy)        blocked tables, restricted measures, row caps
  ├─ executor.js     run the generated SQL (alasql, in-memory)
  ├─ narrator.js     turn rows into the short answer + description + insights
  └─ visualizer.js   choose the chart form from the shape of the result
```

**The question parser is deterministic, not an LLM.** For a demo that is
deliberate: it is instant, offline, reproducible, and every decision it makes can
be displayed as a numbered reasoning step. Production would replace
`planner.js` alone — the rest of the pipeline depends only on the plan object it
returns, not on how the plan was produced.

**The SQL really executes.** `alasql` is a SQL engine in pure JavaScript, so the
query shown in the UI is the query that ran against the in-memory tables. Pointing
this at a live Postgres means replacing `executor.js` with a `pg` pool.

**The data is generated from a fixed seed** (`server/src/data/`), so every machine
shows identical numbers: ~2,800 orders and ~5,600 line items over two years, with
seasonality (November/December peaks) and steady growth so trends look real. The
dataset is anchored to 2026-06-30, which is what “last month” resolves against.

### Layout

```
server/src/
  data/         seeded datasets (retail, HR) and the schema catalog
  engine/       semantic layer, planner, executor, narrator, visualizer, pipeline
  routes/       REST API
  middleware/   demo auth (HMAC-signed token)
  store.js      connections, settings, users, history, audit log (in memory)

client/src/
  pages/        Login, Overview, Ask, Connections, History, Admin
  components/   Shell, AnswerCard, ChartPanel, Icons
  context/      auth, active connection, theme, toasts
  lib/          API client, formatting, CSV export, SQL highlighting
```

---

## Admin panel

Every setting is per connection and takes effect on the next question.

| Section | Controls |
|---|---|
| Query behaviour | row cap, statement timeout, exclude cancelled/refunded orders, allow joins |
| Governance | PII handling (full / masked / blocked), hide sensitive measures, read-only enforcement |
| Answer format | auto charts, show SQL, show reasoning, narrative length, model |
| Business glossary | company vocabulary → schema measures |
| Access control | block individual tables from natural language access |
| Users & roles | invite users, change roles (owner / analyst / viewer) |
| Audit log | who changed what, and when |

---

## Tests

With the server running on :4000:

```bash
node server/test-engine.mjs   # 17 questions through the planner, prints each answer
node server/test-api.mjs      # 21 API assertions: roles, policy, masking, payloads
```

`test-engine.mjs` runs the pipeline directly and needs no server.

---

## Demo-build limitations

These are deliberate, and worth stating up front in a presentation:

- **Only the two seeded databases carry data.** Adding a connection through the UI
  creates it but leaves it offline; no credentials are dialled out.
- **State is in memory.** Restarting the server resets settings, history and any
  connections or users added during a session.
- **Auth is demo-grade.** Passwords are in plain text in `store.js` and the token
  is a simple HMAC. Use real password hashing and JWTs in production.
- **The parser understands this schema's vocabulary**, not arbitrary English. Ask
  something unrelated and it says so rather than guessing.

## Stack note

React + Express was the requested stack and is a good fit for the demo — one
language across the whole app, and the fastest path to a UI that looks like the
real product. For the production research system, consider a **Python (FastAPI)
service for the query engine** while keeping this React client: the NL-to-SQL
ecosystem (SQLAlchemy for dialect-correct generation and schema reflection, plus
evaluation tooling for measuring accuracy against a labelled question set) is
substantially stronger in Python, and accuracy measurement is what a research
project ultimately has to report. The API contract in `routes/index.js` transfers
unchanged.
