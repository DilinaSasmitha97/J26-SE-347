"""
Tests for the response-intent layer.

Two things the CSV benchmark cannot check are covered here:

  1. Stage C guardrails, which need a real result set to fire against.
  2. The block contract - that a rendered response contains exactly the blocks
     its intent declares, and nothing else.

Run with:  python test_response_intent.py
"""

import response_intent
import response_renderer
from result_profiler import profile_results
from schemas import RESPONSE_BLOCKS, ResponseIntent, ResponseIntentResult

PASSED = []
FAILED = []


def check(name: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append((name, detail))
    mark = "ok  " if condition else "FAIL"
    print(f"  [{mark}] {name}" + (f"  -  {detail}" if detail and not condition else ""))


def _decided(intent: ResponseIntent, markers=None) -> ResponseIntentResult:
    return ResponseIntentResult(
        intent=intent.value,
        confidence=0.9,
        blocks=[b.value for b in RESPONSE_BLOCKS[intent]],
        matched_markers=markers or {},
    )


# --------------------------------------------------------------------------
print("\nStage A/B - classification")
# --------------------------------------------------------------------------

cases = [
    ("What was our highest invoice?", ResponseIntent.SINGLE_ANSWER),
    ("Briefly summarise last month", ResponseIntent.SHORT_SUMMARY),
    ("List all overdue invoices", ResponseIntent.TABLE_CONTENT),
    ("Chart revenue by month", ResponseIntent.CHART),
    ("Give me a full report on regional sales", ResponseIntent.MIXED_SUMMARY),
]
for query, expected in cases:
    result = response_intent.classify(query)
    check(f"{query!r} -> {expected.value}", result.intent == expected.value,
          f"got {result.intent}")

check(
    "every verdict is inside the closed taxonomy",
    all(
        response_intent.classify(q).intent in [i.value for i in ResponseIntent]
        for q in ["", "   ", "asdf", "hello", "!!!", "12345"]
    ),
)

check(
    "blocks always match the taxonomy contract",
    all(
        response_intent.classify(q).blocks
        == [b.value for b in RESPONSE_BLOCKS[ResponseIntent(response_intent.classify(q).intent)]]
        for q, _ in cases
    ),
)

check(
    "classification is deterministic",
    response_intent.classify("show me the top 10 customers").intent
    == response_intent.classify("show me the top 10 customers").intent,
)

check(
    "typo repair is recorded in the rationale",
    "Lexical repair" in response_intent.classify("summery of expenses").rationale,
)

check(
    "protected tokens survive the repair step",
    response_intent.repair_typos("total cost last month by cart")[1] == [],
    f"unexpected repairs: {response_intent.repair_typos('total cost last month by cart')[1]}",
)

# --------------------------------------------------------------------------
print("\nPrecondition - is this a data request at all?")
# --------------------------------------------------------------------------

for query, reason in [
    ("hello", "CONVERSATIONAL"),
    ("good morning", "CONVERSATIONAL"),
    ("thanks that was helpful", "CONVERSATIONAL"),
    ("qwertyuiop", "NO_RECOGNISABLE_CONTENT"),
    ("asdkjhasd", "NO_RECOGNISABLE_CONTENT"),
    ("", "EMPTY"),
    ("   ", "EMPTY"),
]:
    result = response_intent.classify(query)
    check(f"{query!r} is not a data request ({reason})",
          not result.is_data_request and result.not_a_request_reason == reason,
          f"got is_data_request={result.is_data_request} "
          f"reason={result.not_a_request_reason}")

check(
    "a non-request still carries a renderable shape",
    response_intent.classify("hello").intent in [i.value for i in ResponseIntent],
)
check(
    "a non-request raises NOT_A_DATA_REQUEST",
    "NOT_A_DATA_REQUEST" in response_intent.classify("hello").warnings,
)

# Real requests must never be rejected by the precheck. These six were all
# false positives in the first version, which maintained its own vocabulary
# separately from the marker lexicon.
for query in [
    "summarize in one paragraph",
    "draw the histogram of session lengths",
    "SHOW ME ALL THE INVOICES NOW",
    "build a dashboard for onboarding drop-off",
    "show me the AR aging bucket distribution",
    "visualize",
    "revenue",
    "i dunno maybe sales stuff",
    "customers > 10000",
]:
    result = response_intent.classify(query)
    check(f"{query!r} IS a data request", result.is_data_request,
          f"rejected as {result.not_a_request_reason}")

# --------------------------------------------------------------------------
print("\nEvidence grade - earned vs fallback")
# --------------------------------------------------------------------------

for query, grade in [
    ("list all invoices", "DIRECT"),
    ("chart revenue by month", "DIRECT"),
    ("i need this in excel", "DIRECT"),
    ("revenue", "FALLBACK"),
]:
    result = response_intent.classify(query)
    check(f"{query!r} graded {grade}", result.evidence_grade == grade,
          f"got {result.evidence_grade}")

check(
    "a fallback verdict is flagged as having no evidence",
    "NO_LEXICAL_EVIDENCE" in response_intent.classify("revenue").warnings,
)
check(
    "'excel' is now a real marker, not a lucky default",
    response_intent.classify("i need this in excel").scores["TABLE_CONTENT"] > 0,
)

# --------------------------------------------------------------------------
print("\nAnswer focus - entity vs value")
# --------------------------------------------------------------------------

focus_cases = [
    ("which department spends the most", "ENTITY"),
    ("who has the biggest pipeline", "ENTITY"),
    ("what is the name of our largest supplier", "ENTITY"),
    ("how much did engineering spend", "VALUE"),
    ("how much does the top department spend", "VALUE"),
    ("what is the total revenue for 2024", "VALUE"),
]
for query, expected_focus in focus_cases:
    result = response_intent.classify(query)
    check(f"{query!r} focus is {expected_focus}",
          result.answer_focus == expected_focus, f"got {result.answer_focus}")

check(
    "singular entity question is a single answer",
    response_intent.classify("which department spends the most").intent
    == ResponseIntent.SINGLE_ANSWER.value,
)
check(
    "plural entity question is a table",
    response_intent.classify("which departments spend the most").intent
    == ResponseIntent.TABLE_CONTENT.value,
    f"got {response_intent.classify('which departments spend the most').intent}",
)
check(
    "singular nouns ending in s are not read as plural",
    response_intent.classify("which business spends the most").intent
    == ResponseIntent.SINGLE_ANSWER.value,
    f"got {response_intent.classify('which business spends the most').intent}",
)

entity_rows = [{"department": "Engineering", "total_spend": 482000}]
entity_profile = profile_results(entity_rows)

entity_answer = response_renderer.render(
    ResponseIntentResult(
        intent=ResponseIntent.SINGLE_ANSWER.value,
        blocks=["ANSWER"], answer_focus="ENTITY",
    ),
    profile=entity_profile, rows=entity_rows,
)["answer"]
check("ENTITY focus leads with the name",
      entity_answer["display_value"] == "Engineering", entity_answer["display_value"])
check("ENTITY focus keeps the measure as the qualifier",
      entity_answer["qualifier"] == "482,000", entity_answer["qualifier"])
check("ENTITY focus does not prefix a name with an aggregation",
      not entity_answer["label"].lower().startswith(("sum ", "max ", "avg ")),
      entity_answer["label"])

value_answer = response_renderer.render(
    ResponseIntentResult(
        intent=ResponseIntent.SINGLE_ANSWER.value,
        blocks=["ANSWER"], answer_focus="VALUE",
    ),
    profile=entity_profile, rows=entity_rows,
)["answer"]
check("VALUE focus leads with the number",
      value_answer["display_value"] == "482,000", value_answer["display_value"])
check("VALUE focus keeps the entity as the qualifier",
      value_answer["qualifier"] == "Engineering", value_answer["qualifier"])

# --------------------------------------------------------------------------
print("\nImplicit row bounds")
# --------------------------------------------------------------------------

import query_analyzer  # noqa: E402

_SCHEMA = {"expenses": {"department": "VARCHAR", "spend": "DECIMAL"}}

bound_cases = [
    # query, limit, source, ordering
    ("which departments spend the most", 5, "INFERRED", "spend DESC"),
    ("which department spends the most", 1, "INFERRED", "spend DESC"),
    ("which departments spend the least", 5, "INFERRED", "spend ASC"),
    ("give me the top 10 departments by spend", 10, "EXPLICIT", "spend DESC"),
    ("list all departments", 0, "NONE", ""),
]
for query, limit, source, ordering in bound_cases:
    a = query_analyzer.analyze(query, schema_meta=_SCHEMA, use_llm=False)
    check(f"{query!r} -> limit {limit} [{source}]",
          a.limit == limit and a.limit_source == source,
          f"got limit={a.limit} source={a.limit_source}")
    check(f"{query!r} -> ordering {ordering!r}", a.ordering == ordering,
          f"got {a.ordering!r}")

check(
    "an inferred bound is always disclosed",
    "IMPLICIT_LIMIT_APPLIED"
    in query_analyzer.analyze("which departments spend the most",
                              schema_meta=_SCHEMA, use_llm=False).warnings,
)
check(
    "an explicit bound raises no disclosure warning",
    "IMPLICIT_LIMIT_APPLIED"
    not in query_analyzer.analyze("give me the top 10 departments by spend",
                                  schema_meta=_SCHEMA, use_llm=False).warnings,
)
check(
    "polarity superlatives refuse to guess a direction",
    "ORDERING_DIRECTION_AMBIGUOUS"
    in query_analyzer.analyze("which product had the worst return rate",
                              schema_meta={"p": {"product": "VARCHAR",
                                                 "return_rate": "DECIMAL"}},
                              use_llm=False).warnings,
)

_sorted = [{"department": f"D{i}", "spend": 100000 - i * 3000} for i in range(1, 31)]
_shuffled = [{"department": f"D{i}", "spend": (i * 7919) % 100000} for i in range(1, 31)]

sorted_table = pipeline_table = None
import pipeline  # noqa: E402

env_sorted = pipeline.run("which departments spend the most", rows=_sorted,
                          schema_meta=_SCHEMA, use_llm=False, enable_cache=False)
t_sorted = env_sorted["response"]["table"]
check("a provably sorted result is trimmed to the implied bound",
      t_sorted["rows_returned"] == 5 and t_sorted["implied_limit_applied"] is True,
      f"returned {t_sorted['rows_returned']}")
check("the true total survives the trim", t_sorted["row_count"] == 30)

env_shuffled = pipeline.run("which departments spend the most", rows=_shuffled,
                            schema_meta=_SCHEMA, use_llm=False, enable_cache=False)
t_shuffled = env_shuffled["response"]["table"]
check("an unordered result is NOT trimmed",
      t_shuffled["rows_returned"] == 30
      and t_shuffled["implied_limit_applied"] is False,
      f"returned {t_shuffled['rows_returned']}")
check("the unapplied bound is explained",
      "not applied" in t_shuffled["limit_note"], t_shuffled["limit_note"])

# --------------------------------------------------------------------------
print("\nChart suppression")
# --------------------------------------------------------------------------

import pipeline  # noqa: E402  - imported here so the tests above stay import-light

for query, wants_chart in [
    ("which department spends the most", False),
    ("list all departments and their spend", False),
    ("briefly summarise department spend", False),
    ("chart department spend", True),
    ("give me a full report on department spend", True),
]:
    envelope = pipeline.run(
        query,
        rows=[{"department": f"D{i}", "total_spend": 1000 * i} for i in range(1, 6)],
        use_llm=False, enable_cache=False,
    )
    built = envelope["visualization"]["_meta"]["chart_type"] != "none"
    hint = envelope["analysis"]["visualization_hint"]["recommended_chart"]
    check(f"{query!r} builds a chart: {wants_chart}", built == wants_chart,
          f"chart_type={envelope['visualization']['_meta']['chart_type']}")
    if not wants_chart:
        check(f"{query!r} hints no chart", hint in ("kpi_card", "table", "none"),
              f"hint={hint}")

# --------------------------------------------------------------------------
print("\nStage C - result-set guardrails")
# --------------------------------------------------------------------------

many_rows = [{"region": f"R{i}", "revenue": 100 + i} for i in range(12)]
one_row = [{"revenue": 4820.5}]
series = [{"month": f"2024-0{i}-01", "revenue": 100 * i} for i in range(1, 7)]

profile_many = profile_results(many_rows)
profile_one = profile_results(one_row)
profile_series = profile_results(series)
profile_empty = profile_results([])

g1 = response_intent.apply_guardrails(_decided(ResponseIntent.SINGLE_ANSWER),
                                      profile_many, many_rows)
check("G1 scalar over 12 rows becomes a table",
      g1.intent == ResponseIntent.TABLE_CONTENT.value, f"got {g1.intent}")
check("G1 records what it replaced", g1.original_intent == "SINGLE_ANSWER")
check("G1 leaves an audit note", bool(g1.guardrails_applied))

g2 = response_intent.apply_guardrails(_decided(ResponseIntent.CHART),
                                      profile_one, one_row)
check("G2 unplottable single row becomes an answer",
      g2.intent == ResponseIntent.SINGLE_ANSWER.value, f"got {g2.intent}")

g2b = response_intent.apply_guardrails(_decided(ResponseIntent.CHART),
                                       profile_series, series)
check("G2 leaves a genuine series alone",
      g2b.intent == ResponseIntent.CHART.value and not g2b.guardrails_applied)

g3 = response_intent.apply_guardrails(_decided(ResponseIntent.TABLE_CONTENT),
                                      profile_one, one_row)
check("G3 degenerate 1x1 table becomes an answer",
      g3.intent == ResponseIntent.SINGLE_ANSWER.value, f"got {g3.intent}")

g3b = response_intent.apply_guardrails(
    _decided(ResponseIntent.TABLE_CONTENT, markers={"TABLE_CONTENT": ["list all"]}),
    profile_one, one_row,
)
check("G3 respects an explicitly requested table",
      g3b.intent == ResponseIntent.TABLE_CONTENT.value, f"got {g3b.intent}")

g0 = response_intent.apply_guardrails(_decided(ResponseIntent.CHART),
                                      profile_empty, [])
check("G0 empty result never charts",
      g0.intent == ResponseIntent.TABLE_CONTENT.value, f"got {g0.intent}")
check("G0 warns about the empty set", "EMPTY_RESULT_SET" in g0.warnings)

g4 = response_intent.apply_guardrails(_decided(ResponseIntent.MIXED_SUMMARY),
                                      profile_one, one_row)
check("G4 mixed report drops an unplottable chart block",
      "CHART" not in g4.blocks and g4.intent == ResponseIntent.MIXED_SUMMARY.value,
      f"got {g4.intent} {g4.blocks}")

g4b = response_intent.apply_guardrails(_decided(ResponseIntent.MIXED_SUMMARY),
                                       profile_series, series)
check("G4 keeps all three blocks when the data supports them",
      g4b.blocks == ["SUMMARY", "TABLE", "CHART"], f"got {g4b.blocks}")

# --------------------------------------------------------------------------
print("\nRenderer - block contract")
# --------------------------------------------------------------------------

expected_keys = {
    ResponseIntent.SINGLE_ANSWER: {"answer"},
    ResponseIntent.SHORT_SUMMARY: {"summary"},
    ResponseIntent.TABLE_CONTENT: {"table"},
    ResponseIntent.CHART: {"chart"},
    ResponseIntent.MIXED_SUMMARY: {"summary", "table", "chart"},
}

for intent, keys in expected_keys.items():
    payload = response_renderer.render(
        _decided(intent), profile=profile_series, rows=series,
        chart_spec={"_meta": {"chart_type": "line", "rationale": "test"}},
    )
    present = {k for k in ("answer", "summary", "table", "chart") if k in payload}
    check(f"{intent.value} emits exactly {sorted(keys)}", present == keys,
          f"got {sorted(present)}")

answer_payload = response_renderer.render(
    _decided(ResponseIntent.SINGLE_ANSWER), profile=profile_one, rows=one_row
)
check("answer block carries a formatted display value",
      answer_payload["answer"]["display_value"] not in ("", "-"),
      answer_payload["answer"]["display_value"])

table_payload = response_renderer.render(
    _decided(ResponseIntent.TABLE_CONTENT), profile=profile_many, rows=many_rows
)
check("table block reports the true row count",
      table_payload["table"]["row_count"] == 12)
check("table block describes every column",
      len(table_payload["table"]["columns"]) == 2)

big = [{"i": n, "v": n * 2} for n in range(500)]
big_payload = response_renderer.render(
    _decided(ResponseIntent.TABLE_CONTENT), profile=profile_results(big), rows=big
)
check("table block bounds the row window and flags truncation",
      big_payload["table"]["rows_returned"] == response_renderer.TABLE_ROW_LIMIT
      and big_payload["table"]["truncated"] is True)

# --------------------------------------------------------------------------
print("\n" + "=" * 70)
print(f"{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    for name, detail in FAILED:
        print(f"  FAIL {name}  {detail}")
print("=" * 70)
raise SystemExit(1 if FAILED else 0)
