"""
Regression tests for the Stage 4 scenario parser and summary verifier.

Runnable with plain `python test_whatif.py` or under pytest.
"""

import os
import sys

os.environ.setdefault("LLM_PROVIDER", "none")

import profiler  # noqa: E402
import query_analyzer  # noqa: E402
import summarization  # noqa: E402
import synthetic_data  # noqa: E402
import whatif  # noqa: E402

profiler.VERBOSE = False
_FAILURES = []
_SCHEMA = synthetic_data.benchmark_suite()[0]["schema"]


def check(condition, label):
    if condition:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}")
        _FAILURES.append(label)


def _clause(text):
    return whatif.parse_scenario(text)


def _question(text):
    return whatif.scenario_from_analysis(query_analyzer.analyze(text, _SCHEMA, use_llm=False))


def test_whole_words():
    print("\n[1] Direction words are whole words")
    for text in ("what if revenue grows by 10% unless we change suppliers",
                 "what if we increase prices by 5% regardless of demand",
                 "what if our wireless revenue grows 10%",
                 "what if the downtown store's sales increase by 12%"):
        s = _clause(text)
        check(s.valid and s.direction == "INCREASE", f"'{text}' is an INCREASE")
    s = _clause("what if the supplier price changes by 10%")
    check(not s.valid and s.reason_code == "NO_DIRECTION",
          "'supplier' does not supply the direction 'up'")


def test_refusals():
    print("\n[2] Refuses rather than guesses")
    for text, code in (("what if we don't cut spending by 10%", "NEGATED"),
                       ("what if we increase prices by 10% and cut costs by 5%", "MULTIPLE_CHANGES"),
                       ("what if sales grow 10-15%", "RANGE"),
                       ("what if we cut spending by $500", "ABSOLUTE_AMOUNT"),
                       ("what if we increase spending", "NO_MAGNITUDE")):
        s = _clause(text)
        check(not s.valid and s.reason_code == code, f"'{text}' -> {code}")


def test_amounts():
    print("\n[3] Targets, multipliers, signs, ramps")
    cases = (("what if we cut spending to 80% of current", "DECREASE", 20.0, "IMMEDIATE"),
             ("what if costs rise to 110%", "INCREASE", 10.0, "IMMEDIATE"),
             ("what if we triple marketing spend", "INCREASE", 200.0, "IMMEDIATE"),
             ("what if costs are cut in half", "DECREASE", 50.0, "IMMEDIATE"),
             ("what if revenue changes by -8%", "DECREASE", 8.0, "IMMEDIATE"),
             ("what if we spend 10% less on travel", "DECREASE", 10.0, "IMMEDIATE"),
             ("what if we gradually reduce spending by 20%", "DECREASE", 20.0, "RAMPED"))
    for text, direction, magnitude, mode in cases:
        s = _clause(text)
        check(s.valid and (s.direction, s.magnitude_pct, s.apply_mode) == (direction, magnitude, mode),
              f"'{text}' -> {direction} {magnitude:g}% {mode}")
    s = _clause("what if we increase spending by 500%")
    check(s.valid and s.magnitude_pct == whatif.MAX_INCREASE_PCT and "clamped" in s.parse_note,
          "an increase beyond 300% is clamped and says so")


def test_routes_agree():
    print("\n[4] The question route and the simulate box agree")
    for text in ("assuming sales rise 5%", "what if we gradually reduce spending by 20%",
                 "what if revenue grows by 10% unless we change suppliers",
                 "what if we don't raise prices by 8%"):
        a, b = _clause(text), _question(text)
        check((a.valid, a.direction, a.magnitude_pct, a.apply_mode)
              == (b.valid, b.direction, b.magnitude_pct, b.apply_mode),
              f"same reading of '{text}'")
    s = _question("what if each group budget is adjusted by 5%")
    check(not s.valid, "a magnitude with no direction is refused, no longer simulated as a cut")


def _claims():
    return [summarization.Claim("H1", "HISTORICAL", "TOTAL", "Total is 48,251.", 48251.37),
            summarization.Claim("H2", "HISTORICAL", "PEAK",
                                "The highest value was 6,351 at 2025-12-01.", 6351.2),
            summarization.Claim("F1", "PREDICTIVE", "FORECAST",
                                "Jan 2026 is projected at 6,454, within 6,040 to 6,869.",
                                6454.33, supporting_values=[6040.1, 6868.9]),
            summarization.Claim("F2", "PREDICTIVE", "HORIZON", "It projects 3 periods ahead.", 3)]


def test_verifier():
    print("\n[5] Precision-aware verifier")
    claims = _claims()
    ok = lambda t: summarization.verify_summary(t, claims)["passed"]  # noqa: E731
    check(ok("The total was 48.3k and the peak 6,351 in December 2025."),
          "scale words and a reworded date pass")
    check(ok("January 2026 is projected at 6,454 (range 6,040-6,869)."),
          "a hyphenated range is a range, not a negative number")
    check(ok("The peak came on 2025-12-01; it projects three periods ahead."),
          "ISO dates and a number written as a word pass")
    check(not ok("January 2026 is projected at 6,777."),
          "a forecast 5% off its claim is rejected even though other claim numbers are near")
    check(not ok("The total was 48,251 over seventeen months."),
          "an invented number written as a word is rejected")
    check(ok("The total was about 48,300."), "48,300 is within 50 of 48,251 and passes")
    check(not ok("The total was about 48,400."), "48,400 is 149 away and is rejected")


def main() -> int:
    test_whole_words()
    test_refusals()
    test_amounts()
    test_routes_agree()
    test_verifier()
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
