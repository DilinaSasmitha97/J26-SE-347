"""
Regression tests for the Stage 5 intent changes (analytical intent, response
shape, implicit LIMIT 1, and scalar forecast questions).

Runnable with plain `python test_intent.py` or under pytest.
"""

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "none")

import pipeline  # noqa: E402
import profiler  # noqa: E402
import query_analyzer  # noqa: E402
import response_intent  # noqa: E402
import synthetic_data  # noqa: E402

profiler.VERBOSE = False
_FAILURES = []


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _a(text):
    return query_analyzer.analyze(text, None, use_llm=False)


def test_not_superlatives():
    print("\n[1] Thresholds, average filters and name columns are not superlatives")
    a = _a("What are the names of the teachers who teach at least two courses?")
    check(a.response_intent != "SINGLE_ANSWER" and a.limit != 1,
          "'at least two' is a filter: many rows, no LIMIT 1")
    check(a.primary_intent != "RANKING", "'at least' does not make a ranking")
    rewritten = response_intent.neutralize(
        "stores with more products than the average and staff above the mean")
    check("average" not in rewritten and "mean" not in rewritten,
          "'than the average' and 'above the mean' are rewritten before any marker is matched")
    # Known remaining error, recorded in the Stage 5 report rather than fixed
    # after the TEST run: "names of stores whose NUMBER OF products is more than
    # the average" still reads as a count, because "number of" names a column
    # there.
    a = _a("What is the first name of the student whose permanent address is in Texas?")
    check(a.primary_intent != "RANKING", "'first name' is a column, not 'the first'")


def test_word_boundaries_and_coverage():
    print("\n[2] Whole-word markers and retrieval phrasings")
    check(_a("Show names of teachers and the courses they are arranged to teach").primary_intent
          != "COMPARISON", "'teach' does not contain the marker 'each'")
    check(_a("What are the names of all the singers from France?").primary_intent == "DETAIL_LOOKUP",
          "a 'what are the names of' question is a lookup, not UNKNOWN")
    check(_a("Return the abbreviation of the airline JetBlue").primary_intent == "DETAIL_LOOKUP",
          "a 'return the' request is a lookup")
    a = _a("How many shops are there in each location?")
    check(a.primary_intent == "COMPARISON" and a.response_intent != "SINGLE_ANSWER",
          "a count in each location is one value per group")
    a = _a("What is the code of the airport with the most flights?")
    check(a.primary_intent == "RANKING" and a.response_intent == "SINGLE_ANSWER" and a.limit == 1,
          "the top entity is a ranking, answered by one row with LIMIT 1")


def test_limit_only_with_order():
    print("\n[3] LIMIT 1 only where something orders the rows")
    a = _a("What is the name of the museum that had no visitor yet?")
    check(a.limit != 1, "a singular question with no superlative does not request LIMIT 1")
    b = response_intent.derive_bounds("which department spends the most", "SINGLE_ANSWER")
    check(b["limit"] == 1 and b["limit_source"] == "INFERRED", "a superlative still requests LIMIT 1")


def test_response_shape_cases():
    print("\n[4] Negation, two questions, yes/no questions")
    cls = response_intent.classify
    check(cls("dont give me a chart just the numbers").intent != "CHART",
          "a refused format is not chosen")
    check(cls("no tables please just explain it to me").intent == "SHORT_SUMMARY",
          "the negation stops at 'please just'")
    check(cls("what is our MRR and how is it trending").intent == "MIXED_SUMMARY",
          "two questions in one request get the mixed report")
    check(cls("who spent the most and who spent the least").intent == "TABLE_CONTENT",
          "two extremes of one question are a two-row table, not two questions")
    check(cls("is revenue up or down since Q1").intent == "SHORT_SUMMARY",
          "a yes/no question about direction is answered in a sentence")
    check(cls("what are the names of the teachers and how many courses do they teach").intent
          != "MIXED_SUMMARY", "a clause that refers back with 'they' is a column, not a question")


def test_scalar_forecast_question():
    print("\n[5] A scalar question about the future is answered by the forecast")
    sc = synthetic_data.benchmark_suite()[0]
    env = pipeline.run("How much will I spend next month?", rows=sc["rows"],
                       schema_meta=sc["schema"], use_llm=False, enable_cache=False)
    answer = env["response"].get("answer") or {}
    check(env["response"]["blocks_emitted"] == ["ANSWER"] and answer.get("is_forecast"),
          "one projected figure, not the 24-row history table")
    check(answer.get("interval") is not None, "the figure carries its forecast range")
    a = _a("How many orders will we get next week?")
    check(a.prediction_required, "'will we ... next week' is a forecast request")
    env = pipeline.run("How much did I spend in total?", rows=sc["rows"],
                       schema_meta=sc["schema"], use_llm=False, enable_cache=False)
    check(env["response"]["blocks_emitted"] == ["TABLE"],
          "a past scalar over 24 rows is still corrected to a table by G1")


def main() -> int:
    test_not_superlatives()
    test_word_boundaries_and_coverage()
    test_limit_only_with_order()
    test_response_shape_cases()
    test_scalar_forecast_question()
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
