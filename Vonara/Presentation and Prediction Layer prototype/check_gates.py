"""
Prediction-gate inspector.

Shows, for a spread of query types, WHY the layer did or did not forecast.
Three independent gates can decline prediction, and this script makes each
one visible:

  Gate A  intent -> strategy is NONE        (the question isn't predictive)
  Gate B  prediction_required is False      (nobody asked for a forecast)
  Gate C  readiness verdict is not READY    (the data cannot support one)

Run:  python check_gates.py
"""

import pipeline
import synthetic_data as sd

SCHEMA = sd.SCHEMA_DDL

# (label, query, rows, what we expect to happen and why)
CASES = [
    (
        "Row lookup",
        "List all employees in the finance department",
        sd.generate_detail_rows(10),
        "Gate A - DETAIL_LOOKUP has no series to extend",
    ),
    (
        "Scalar KPI",
        "What is the total amount spent on travel",
        [{"total_amount": 48250.0}],
        "Gate A - a single scalar has nothing to extrapolate",
    ),
    (
        "Ranking, no forecast asked",
        "Which are the top 5 categories by total amount",
        sd.generate_categorical(5),
        "Gate B - forecast would be meaningful but was not requested",
    ),
    (
        "Forecast asked, no time axis",
        "Show spend by category and predict the next 3 months",
        sd.generate_categorical(6),
        "Gate C - NOT_TEMPORAL, there is no date column",
    ),
    (
        "Forecast asked, too few points",
        "Show monthly expenses and predict the next 3 months",
        sd.generate_timeseries(n_periods=3, seed=31)[0],
        "Gate C - INSUFFICIENT_POINTS, 3 observations",
    ),
    (
        "Forecast asked, constant series",
        "Show monthly expenses and predict the next 3 months",
        [{"invoice_date": f"2024-{m:02d}-01", "amount": 500.0} for m in range(1, 13)],
        "Gate C - DEGENERATE, a flat line carries no information",
    ),
    (
        "Forecast asked, good data",
        "Show monthly expenses and predict the next 3 months",
        sd.generate_timeseries(n_periods=24, level=3500, trend=140,
                               noise_pct=0.05, seed=42)[0],
        "PASSES all gates - forecast generated",
    ),
]


def classify(envelope) -> str:
    """Name the gate that stopped prediction, or report that none did."""
    analysis = envelope["analysis"]
    pred = envelope["prediction"]
    strategy = pred["stage_1_strategy"]["strategy"]
    required = analysis["prediction_request"]["prediction_required"]
    verdict = pred["stage_2_readiness"]["verdict"]

    if pred["stage_4_forecast"]["generated"]:
        return "FORECAST GENERATED"
    if strategy == "NONE":
        return "STOPPED AT GATE A (intent implies no prediction)"
    if not required:
        return "STOPPED AT GATE B (no forecast requested)"
    return f"STOPPED AT GATE C (readiness: {verdict})"


def main() -> None:
    print("\n" + "=" * 76)
    print("PREDICTION GATE INSPECTOR")
    print("Shows why the layer did or did not forecast, per query type.")
    print("=" * 76)

    for label, query, rows, expectation in CASES:
        envelope = pipeline.run(
            query, rows=rows, schema_meta=SCHEMA,
            use_llm=False, enable_cache=False,
        )
        analysis = envelope["analysis"]
        pred = envelope["prediction"]
        readiness = pred["stage_2_readiness"]

        print(f"\n{'-' * 76}")
        print(f"  {label}")
        print(f"  query    : \"{query}\"")
        print(f"  rows     : {envelope['result_profile']['row_count']}")
        print(f"  expected : {expectation}")
        print()
        print(f"  intent           = {analysis['intent']['primary_intent']}")
        print(f"  prediction asked = {analysis['prediction_request']['prediction_required']}")
        print(f"  strategy         = {pred['stage_1_strategy']['strategy']}")
        print(f"  readiness        = {readiness['verdict']}")
        print(f"  chart            = {envelope['visualization']['_meta']['chart_type']}")
        print()
        print(f"  >>> {classify(envelope)}")
        if readiness["reason"]:
            print(f"  >>> reason shown to user: {readiness['reason']}")

    print("\n" + "=" * 76)
    print("Every declined forecast returns a specific verdict, so the user is")
    print("always told WHY there is no prediction - never a silently empty chart.")
    print("=" * 76 + "\n")


if __name__ == "__main__":
    main()
