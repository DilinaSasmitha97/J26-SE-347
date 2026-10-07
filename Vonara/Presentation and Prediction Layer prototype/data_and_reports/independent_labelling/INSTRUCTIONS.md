# Labelling forecast readiness

Thank you for helping. You are giving an **independent** judgement, so please
do not look at the code or the reports first.

## The situation

A business user asked a question, for example "show monthly expenses and
forecast the next 3 months", and the database returned the result set below.
Before showing a forecast, the system must decide whether this data can
support one.

## What to decide, for each case in `cases.csv`

Fill in the `your_decision` column of `labels.csv` with exactly one of:

| Decision | Meaning |
| --- | --- |
| `FORECAST` | The data is fine; show the forecast. |
| `FORECAST_WITH_CAUTION` | Show the forecast, but warn the user about something specific. |
| `NO_FORECAST` | Do not forecast; any forecast from this data would mislead. |

Use your own judgement about what a careful analyst would do. Add a few words
in `your_reason` (for example "too few points", "gaps", "looks like noise").

## Reading a case

Each row of `cases.csv` is one result set:

- `columns`: the columns returned.
- `rows`: the data, one row per line inside the cell, values separated by `;`.
  Empty values are shown as `NULL`.
- `note`: anything else the system knows about the result (for example that
  the database cut it at a row limit). Empty for most cases.

Plotting a case in Excel or Google Sheets often helps.

There are 34 cases; most take under a minute. Please work alone and do not
change `case_id`. When done, send `labels.csv` back.
