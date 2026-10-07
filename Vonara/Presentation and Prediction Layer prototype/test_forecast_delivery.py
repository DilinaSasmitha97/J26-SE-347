"""
Regression tests for forecast delivery.

The rule under test: if the user explicitly asked for a prediction, the
response contains the forecast or the reason there is none - in EVERY response
shape. And the converse: if nobody asked, no forecast is pushed into a table,
an answer or a short summary.

Each response shape is rendered directly (rather than relying on the
classifier to pick it), so every shape x outcome combination is covered
regardless of how a particular question happens to be classified.
Runnable with plain `python test_forecast_delivery.py` or under pytest.
"""

import sys

import anomaly as anomaly_mod
import prediction as prediction_mod
import query_analyzer
import response_renderer
import summarization
import synthetic_data as sd
import visualization
from result_profiler import coerce_measures, extract_series, profile_results
from schemas import RESPONSE_BLOCKS, ResponseIntent, ResponseIntentResult

_FAILURES = []

GOOD_ROWS = sd.generate_timeseries(n_periods=24, level=3500, trend=140,
                                   noise_pct=0.05, seed=42)[0]
SHORT_ROWS = sd.generate_timeseries(n_periods=3, seed=31)[0]

ASKED = "Show monthly expenses and predict the next 3 months"
NOT_ASKED = "List my monthly expenses by category"
SINGLE_PERIOD = "What will my expenses be next month? Forecast it"


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def build(query: str, rows: list) -> dict:
    """Run stages 1-7 once and keep the objects the renderer consumes."""
    analysis = query_analyzer.analyze(query, sd.SCHEMA_DDL, {}, False)
    profile = profile_results(rows, None, analysis)
    rows = coerce_measures(rows, profile)
    readiness = prediction_mod.assess_readiness(profile, rows)
    forecast = prediction_mod.ForecastResult()
    if readiness.is_ready and analysis.prediction_required:
        values = extract_series(rows, profile.temporal_column, profile.measure_columns[0])[1]
        selection = prediction_mod.select_model(analysis, readiness, values)
        forecast = prediction_mod.generate_forecast(analysis, profile, rows, readiness, selection)
    else:
        forecast.skipped_reason = readiness.reason
    values = extract_series(rows, profile.temporal_column, profile.measure_columns[0])[1] \
        if profile.temporal_column and profile.measure_columns else []
    anomalies = anomaly_mod.detect_anomalies(values, forecast=forecast) if values \
        else anomaly_mod.AnomalyReport()
    summary = summarization.summarize(profile, rows, analysis, forecast=forecast,
                                      anomaly_report=anomalies)
    chart = visualization.extend_with_forecast(
        visualization.build_chart(analysis, profile, rows),
        forecast=forecast if forecast.generated else None)
    return dict(analysis=analysis, profile=profile, rows=rows, readiness=readiness,
                forecast=forecast, summary=summary, chart=chart)


def render(parts: dict, intent: ResponseIntent) -> dict:
    decided = ResponseIntentResult(intent=intent.value,
                                   blocks=[b.value for b in RESPONSE_BLOCKS[intent]])
    return response_renderer.render(
        decided, analysis=parts["analysis"], profile=parts["profile"], rows=parts["rows"],
        chart_spec=parts["chart"], summary=parts["summary"], forecast=parts["forecast"],
        readiness=parts["readiness"])


def test_forecast_shown_in_every_shape():
    print("\n[1] Forecast requested and produced -> shown in every shape")
    parts = build(ASKED, GOOD_ROWS)
    check(parts["analysis"].prediction_trigger == "EXPLICIT", "fixture question is an explicit request")
    check(parts["forecast"].generated, "fixture data supports a forecast")
    first = parts["forecast"].points[0]

    for intent in ResponseIntent:
        out = render(parts, intent)
        notice = out.get("forecast_notice") or {}
        check(notice.get("status") == "SHOWN" and notice.get("message"),
              f"{intent.value}: notice reports SHOWN with the verified forecast sentence")
        embedded = set(notice.get("shown_in", []))
        expected = {b.value for b in RESPONSE_BLOCKS[intent]}
        check(embedded == expected,
              f"{intent.value}: forecast embedded in every block it emits {sorted(expected)}")

    table = render(parts, ResponseIntent.TABLE_CONTENT)["table"]
    fc_rows = [r for r in table["rows"] if r.get("row_type") == "FORECAST"]
    check(len(fc_rows) == len(parts["forecast"].points), "table carries one FORECAST row per period")
    check(fc_rows[0]["invoice_date"] == first.timestamp[:10],
          "forecast period formatted like the result's own dates")
    check(fc_rows[0]["lower_bound"] <= fc_rows[0]["amount"] <= fc_rows[0]["upper_bound"],
          "forecast row carries its interval")
    check(table["row_count"] == len(GOOD_ROWS), "row_count still reports the real result size")

    answer = render(parts, ResponseIntent.SINGLE_ANSWER)["answer"]
    total = sum(p.predicted for p in parts["forecast"].points)
    total_claim = next(c for c in parts["summary"].claims if c.kind == "FORECAST_TOTAL")
    check(answer["is_forecast"] and answer["display_value"] == summarization.fmt(total)
          and abs(total_claim.value - total) < 1e-6,
          "'next 3 months' single answer is the projected total (claim F3)")
    check(answer["interval"] is None,
          "no interval is invented for a total (summed bounds are not an interval)")

    one = build(SINGLE_PERIOD, GOOD_ROWS)
    one_first = one["forecast"].points[0]
    answer = render(one, ResponseIntent.SINGLE_ANSWER)["answer"]
    check(answer["display_value"] == summarization.fmt(one_first.predicted)
          and answer["qualifier"] == one_first.label,
          "'next month' single answer is the first projected period")
    check(answer["interval"] and answer["interval"]["lower"] == one_first.lower_bound,
          "single-period answer carries its interval")

    summary = render(parts, ResponseIntent.SHORT_SUMMARY)["summary"]
    check(summary["sentence_selection"] == "FORECAST_PRIORITY" and summary["verified"],
          "short summary is forecast-first and still passes the verifier")
    check(summary["text"].count(". ") + 1 <= response_renderer.SHORT_SUMMARY_SENTENCES,
          "short summary stays within its sentence budget")


def test_refusal_explained_in_every_shape():
    print("\n[2] Forecast requested but refused -> reason shown in every shape")
    parts = build(ASKED, SHORT_ROWS)
    check(not parts["forecast"].generated, "3 observations are refused by the readiness gate")
    reason = parts["readiness"].reason
    for intent in ResponseIntent:
        out = render(parts, intent)
        notice = out.get("forecast_notice") or {}
        check(notice.get("status") == "REFUSED" and notice.get("reason") == reason,
              f"{intent.value}: notice reports REFUSED with the gate's reason")
    answer = render(parts, ResponseIntent.SINGLE_ANSWER)["answer"]
    check(answer["value"] is None and answer["qualifier"] == reason,
          "single answer states that no forecast exists, and why")
    summary = render(parts, ResponseIntent.SHORT_SUMMARY)["summary"]
    check(reason in summary["text"], "short summary contains the refusal reason")


def test_nothing_added_when_not_asked():
    print("\n[3] Forecast not asked for -> nothing added")
    parts = build(NOT_ASKED, GOOD_ROWS)
    check(parts["analysis"].prediction_trigger != "EXPLICIT", "fixture question does not ask")
    for intent in ResponseIntent:
        out = render(parts, intent)
        check("forecast_notice" not in out, f"{intent.value}: no forecast notice")
        if "table" in out:
            check(all("row_type" not in r for r in out["table"]["rows"]),
                  f"{intent.value}: table rows unchanged")
        if "summary" in out:
            check(out["summary"]["sentence_selection"] == "LEADING_SENTENCES",
                  f"{intent.value}: summary keeps its normal selection")


def test_condensed_claim_not_duplicated():
    print("\n[4] The condensed forecast claim never duplicates the full text")
    parts = build(ASKED, GOOD_ROWS)
    path = next(c for c in parts["summary"].claims if c.kind == "FORECAST_PATH")
    check(path.text not in parts["summary"].text, "full text omits the condensed FORECAST_PATH claim")
    check(parts["summary"].verification.get("passed"), "full text still fully verified")


def main() -> int:
    test_forecast_shown_in_every_shape()
    test_refusal_explained_in_every_shape()
    test_nothing_added_when_not_asked()
    test_condensed_claim_not_duplicated()
    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} check(s) failed:")
        for f in _FAILURES:
            print(f"  - {f}")
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
