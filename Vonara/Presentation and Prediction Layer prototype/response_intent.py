"""
Response-intent classification: deciding the SHAPE of the reply.

The layer answers one question - given a natural-language data request, should
the user receive a single figure, a short narrative, a table of rows, a chart,
or all three at once? The taxonomy is closed (`schemas.ResponseIntent`) and
every request resolves to exactly one member.

    SINGLE_ANSWER  "what was our highest invoice last quarter"
    SHORT_SUMMARY  "briefly, how did sales go last month"
    TABLE_CONTENT  "list every overdue invoice with its customer"
    CHART          "show revenue by month as a graph"
    MIXED_SUMMARY  "give me a full report on regional performance"

Three stages, each of which can be audited independently:

  Stage A - LEXICAL.    Weighted marker evidence over five families. Purely
                        deterministic, so the same question always produces
                        the same verdict and the same rationale.

  Stage B - ANALYTIC.   When lexical evidence is weak or absent, the analytical
                        intent (`QueryIntent`) supplies a prior. A user who
                        writes "total revenue in 2024" names no output format
                        at all, but a KPI_SINGLE_VALUE question has exactly one
                        sensible shape.

  Stage C - GUARDRAIL.  After the SQL has run, the verdict is re-checked
                        against the real result set. A question that reads like
                        a scalar but returned 40 rows was misread, and shipping
                        a "single answer" over 40 rows would be a lie about the
                        data. Guardrails only ever fire on evidence from the
                        result set, never on a second guess at the language.

Stages A and B run pre-execution, so Members 1 and 3 can call
`classify()` before a single row is fetched and know what the UI will need.
"""

import re
from difflib import SequenceMatcher

from schemas import (
    DEFAULT_RESPONSE_INTENT,
    QueryIntent,
    RESPONSE_BLOCKS,
    ResponseIntent,
    ResponseIntentResult,
)

# ==========================================================================
# Stage A - lexical evidence
# ==========================================================================
#
# Weights are ordinal, mirroring the convention already used by
# `query_analyzer.INTENT_MARKERS`:
#
#   4 = decisive. The user named the output format outright ("as a chart").
#   3 = strong. Phrasing that almost always implies one shape ("list all").
#   2 = moderate. Suggestive but defeasible ("top", "overview").
#   1 = weak corroboration only; never wins a contest on its own.
#
# Markers containing regex metacharacters are matched as patterns, everything
# else as a literal substring, so multi-word phrases stay cheap to test.

RESPONSE_MARKERS = {
    ResponseIntent.SINGLE_ANSWER: {
        4: [
            r"\bwhat'?s the (?:single |one )?(?:highest|lowest|largest|smallest|maximum|minimum|biggest|best|worst)\b",
            r"\bwhat (?:is|was) the (?:single |one )?(?:highest|lowest|largest|smallest|maximum|minimum|biggest|best|worst)\b",
            r"\bwho (?:is|was|has) the (?:highest|lowest|top|best|worst|most|least)\b",
            r"\bhow many\b", r"\bhow much\b",
            r"\bjust (?:the |give me the )?(?:number|figure|total|value|answer)\b",
            r"\bone number\b", r"\bsingle (?:number|value|figure|answer)\b",
            # An explicit singular quantifier in front of a superlative: the
            # user has told us they want exactly one row back.
            r"\b(?:the )?single (?:highest|lowest|biggest|largest|best|worst|most|top)\b",
            r"\b(?:need|want|give me|tell me) the (?:number|figure|total|count|value)\b",
            # "which department spends the most", "which product had the worst
            # return rate", "who has the biggest pipeline". A singular noun
            # after which/what, plus a superlative, identifies one entity.
            # The negative lookbehind rejects the plural ("which departments
            # spend the most" is a ranking, and ranking of many is a table).
            r"\bwhich [a-z]+(?<!s)\b.{0,40}\b(?:the )?"
            r"(?:most|least|highest|lowest|largest|smallest|biggest|best|worst)\b",
            # "the department that is spending more than the others" is a
            # superlative without a superlative word (Stage 5, stress set).
            r"\bthe [a-z]+(?<!s) (?:that|which|who)\b.{0,30}\b(?:more|less) than "
            r"(?:the |all (?:the )?)?(?:others|rest)\b",
            r"\bheadline (?:number|figure)\b",
            # One future period asked for by value: "what will revenue be next
            # quarter" is answered by one projected figure.
            r"\bwhat will\b.{0,40}\bbe\b.{0,15}\bnext (?:day|week|month|quarter|year)\b",
            r"\bwho\b.{0,40}\b(?:the )?"
            r"(?:most|least|highest|lowest|largest|smallest|biggest|best|worst)\b",
            # "the id of the document with the fewest paragraphs", "where is the
            # youngest teacher from": a singular noun led by a superlative that
            # the patterns above do not list (Stage 5, Spider DEV).
            r"\bwhich [a-z]+(?<!s)\b.{0,40}\b(?:the )?"
            r"(?:fewest|greatest|youngest|oldest|earliest|latest|longest|shortest)\b",
            r"\bthe (?:fewest|greatest|youngest|oldest|earliest|latest|longest|shortest"
            r"|most common)\b",
        ],
        3: [
            r"\btop 1\b", r"\bthe (?:very )?(?:highest|lowest|largest|smallest)\b",
            r"\bwhat'?s the (?:total|sum|average|mean|median|count)\b",
            r"\bwhat (?:is|was) the (?:total|sum|average|mean|median|count)\b",
            r"\bmaximum\b", r"\bminimum\b",
            r"\bwhich (?:customer|product|region|employee|branch|department|item|category) (?:has|had|spent|bought|generated)\b",
            r"\bpeak\b", r"\ball[- ]time (?:high|low)\b",
        ],
        2: [
            r"\bhighest\b", r"\blowest\b", r"\bmost\b", r"\bleast\b",
            r"\btotal\b", r"\baverage\b", r"\bcount of\b", r"\bnumber of\b",
            r"\bexactly\b", r"\bvalue of\b",
        ],
        1: [r"\bwhat is\b", r"\btell me the\b"],
    },
    ResponseIntent.SHORT_SUMMARY: {
        4: [
            r"\bsummar(?:y|ise|ize|ised|ized)\b", r"\bin (?:a few words|short|brief)\b",
            r"\btl;?dr\b", r"\bbrief(?:ly)?\b", r"\bshort summary\b",
            r"\bexecutive summary\b", r"\bone paragraph\b",
            # Verbs that name prose as the deliverable as plainly as "chart"
            # names a picture. Grouped with the decisive tier for that reason.
            r"\bexplain\b", r"\bdescribe\b", r"\binterpret\b",
            r"\bwhat does the (?:data|report|numbers?|result) (?:tell|say|show|mean)\b",
        ],
        3: [
            r"\boverview\b", r"\bhigh[- ]level\b",
            r"\bwhat'?s the (?:story|takeaway|gist)\b",
            r"\bkey (?:takeaway|point|insight|finding)s?\b",
            # Deliberately loose on the subject: "how are sales doing", "how
            # did the northern region perform" and "how is it going" all put
            # an arbitrary noun phrase between the wh-word and the verb.
            r"\bhow\b.{0,32}\b(?:doing|going|performing|perform|performed)\b",
            # A yes/no question about direction is answered in a sentence:
            # "is revenue up or down since Q1", "are we doing better".
            r"^(?:is|are|was|were|did|do|does|has|have)\b.{0,50}\b(?:up|down|better|worse"
            r"|higher|lower|improv\w*|declin\w*|grow\w*)\b",
            r"\banything (?:i|we) (?:should|need to|ought to) (?:worry|know|look)\b",
        ],
        2: [
            r"\binsight(?:s)?\b", r"\bcomment on\b", r"\bwhat happened\b",
            r"\bin words\b", r"\bnarrative\b", r"\bwrite up\b",
            r"\banything (?:notable|interesting|worth|unusual|odd|strange|off|concerning|wrong)\b",
        ],
        1: [r"\btell me about\b", r"\bhow was\b", r"\bthoughts on\b"],
    },
    ResponseIntent.TABLE_CONTENT: {
        4: [
            r"\blist (?:all|every|out|the)\b", r"\bas a table\b", r"\bin (?:a )?table\b",
            r"\btabular\b", r"\bshow me all\b", r"\bexport\b", r"\bdownload\b",
            r"\braw data\b", r"\bfull list\b", r"\bspreadsheet\b", r"\bcsv\b",
            # Naming the tool names the format. Its absence was masked by the
            # fallback, which returns TABLE_CONTENT anyway - the right answer
            # for the wrong reason, and exactly what `evidence_grade` exposes.
            r"\bexcel\b", r"\bxlsx?\b",
            r"\btabulate\b",
        ],
        3: [
            r"\bevery (?:row|record|entry|transaction|invoice|order|customer|item)\b",
            r"\ball (?:the )?(?:rows|records|entries|details)\b",
            r"\bdataset\b", r"\brecords? (?:for|of|where)\b",
            r"\bline items?\b", r"\bwith (?:their|its) (?:name|id|date|details)\b",
            r"\bcolumns?\b", r"\bfields?\b",
            r"\ball (?:the )?(?:information|info|details|attributes)\b",
            r"\brun the numbers\b",
        ],
        2: [
            r"\blist\b", r"\brows\b", r"\brecords\b", r"\bentries\b",
            r"\bdetails of\b", r"\blook ?up\b", r"\bpull up\b", r"\bwhich ones\b",
        ],
        1: [r"\bshow me\b", r"\bgive me\b", r"\bfind\b", r"\bget\b"],
    },
    ResponseIntent.CHART: {
        4: [
            r"\bchart\b", r"\bgraph\b", r"\bplot\b", r"\bvisuali[sz]e\b",
            r"\bvisuali[sz]ation\b", r"\bdiagram\b",
            r"\b(?:bar|line|pie|donut|scatter|area|column) chart\b",
            r"\bhistogram\b", r"\bheat ?map\b",
        ],
        3: [
            r"\bdraw\b", r"\bgraphically\b", r"\bvisually\b",
            r"\btrend (?:line|over)\b", r"\bplot(?:ted)? (?:against|over|by)\b",
            r"\bpie\b", r"\bbar\b",
            # "what does the sales curve look like" names a picture without
            # using any of the words for one.
            r"\bcurve\b",
        ],
        2: [
            r"\bover time\b", r"\bmonth by month\b", r"\byear over year\b",
            r"\btrend\b", r"\bcompare\b", r"\bcomparison\b", r"\bversus\b", r"\bvs\b",
            r"\bdistribution\b", r"\bbreak(?:\s+(?:it|this|that|them))?\s*down\b", r"\bshare of\b",
            r"\bproportion\b", r"\bpercentage of total\b", r"\bcorrelation\b",
            r"\btrending\b",
            # A share of a whole is drawn (Stage 6, fixture P04).
            r"\bpercent(?:age)? of\b",
        ],
        1: [# A per-period word is a weak cue only: "list my monthly expenses"
            # names a table, and the verb outranks it (Stage 6, F09 / T09).
            r"\b(?:monthly|weekly|daily|quarterly|yearly|annually)\b",
            r"\bby (?:month|quarter|year|week|day|region|category|product|department"
            r"|status|segment|team|branch|channel|customer|unit|business unit|cohort"
            r"|country|city|location|supplier|vendor)\b",
            r"\bpattern\b", r"\bshape of\b"],
    },
    ResponseIntent.MIXED_SUMMARY: {
        4: [
            r"\bfull report\b", r"\bcomplete report\b", r"\bdetailed report\b",
            r"\bfull (?:analysis|breakdown|picture|rundown)\b",
            r"\bcomprehensive\b", r"\bdeep dive\b", r"\beverything (?:about|on|you have)\b",
            r"\bdashboard\b", r"\ball of it\b", r"\bthe works\b",
            r"\bsummary,? (?:and )?(?:table|chart|data)\b",
            r"\b(?:table|chart|data),? (?:and )?summary\b",
            # Two formats named in one breath. Decisive rather than
            # suggestive: the user has enumerated their deliverables.
            r"\bwith (?:a |the )?(?:chart|graph|table|visual|summary)\b",
            r"\bplus (?:a |the )?(?:chart|graph|table|summary|rows|data)\b",
            r"\bboth\b.{0,25}\b(?:chart|table|summary)\b",
            r"\band (?:a |the )?(?:chart|graph|table)\b",
            r"^everything\W*$",
        ],
        3: [
            r"\breport on\b", r"\bfull\b.{0,20}\breport\b",
            r"\banalysis of\b", r"\bwrite (?:me )?a report\b",
            r"\bsupporting visual(?:s)?\b",
        ],
        2: [
            r"\bdetailed\b", r"\bin depth\b", r"\bthorough\b",
            r"\breport\b", r"\breview of\b", r"\bbreak (?:it|this) down\b",
        ],
        1: [r"\bmore detail\b", r"\bexpand on\b"],
    },
}

# Explicit multi-modality request: the user named two or more different output
# formats in one sentence ("show the numbers and chart them"). This is the
# strongest possible evidence for MIXED_SUMMARY and is detected structurally
# rather than lexically, because the combinations are open-ended.
_MODALITY_PROBES = {
    ResponseIntent.SHORT_SUMMARY: r"\bsummar|\boverview\b|\bexplain\b|\binsight",
    ResponseIntent.TABLE_CONTENT: r"\btable\b|\blist\b|\brows\b|\brecords\b|\bdata\b|\bnumbers\b",
    ResponseIntent.CHART: r"\bchart\b|\bgraph\b|\bplot\b|\bvisuali[sz]|\bdiagram\b"
                          r"|\bbreak(?:\s+(?:it|this|that|them))?\s*down\b|\bvisual\b"
                          r"|\bforecast\b",
}

# "then" sequences two deliverables ("pull the numbers then chart them"); "but"
# keeps a second one ("summarise but keep the table too").
_CONJUNCTION = (r"\b(?:and|plus|along with|together with|as well as|with|also|then|but"
                r"|\+|&)\b")

# When lexical evidence is thin, the analytical intent decides. Each mapping is
# a claim about the question's natural shape, not a UI preference:
#   - a scalar question has one answer, so it renders as one answer;
#   - row retrieval has no aggregate to plot, so it renders as rows;
#   - every remaining analytical intent describes a *relationship* between
#     values, and a relationship is what a chart exists to show.
ANALYTIC_PRIOR = {
    QueryIntent.KPI_SINGLE_VALUE: ResponseIntent.SINGLE_ANSWER,
    QueryIntent.DETAIL_LOOKUP: ResponseIntent.TABLE_CONTENT,
    QueryIntent.RANKING: ResponseIntent.TABLE_CONTENT,
    QueryIntent.TREND_ANALYSIS: ResponseIntent.CHART,
    QueryIntent.COMPARISON: ResponseIntent.CHART,
    QueryIntent.PROPORTION: ResponseIntent.CHART,
    QueryIntent.DISTRIBUTION: ResponseIntent.CHART,
    QueryIntent.CORRELATION: ResponseIntent.CHART,
    QueryIntent.ANOMALY_DETECTION: ResponseIntent.CHART,
    QueryIntent.UNKNOWN: DEFAULT_RESPONSE_INTENT,
}

# Below this, the lexical verdict is not trusted on its own and Stage B
# arbitrates. Tuned on the development split of response_intent_dataset.csv.
LEXICAL_TRUST_THRESHOLD = 0.55

# The pre-execution chart hint implied by each response shape. The analytical
# intent proposes an encoding ("RANKING maps to bar"), but the response intent
# is the authority on presentation: if the user asked which department spends
# the most, a bar-chart hint answers a question they did not ask. Only the two
# shapes that actually render a chart defer to the analytical encoding.
CHART_HINT_BY_RESPONSE = {
    ResponseIntent.SINGLE_ANSWER: ("kpi_card", []),
    ResponseIntent.TABLE_CONTENT: ("table", []),
    ResponseIntent.SHORT_SUMMARY: ("none", []),
    ResponseIntent.CHART: None,          # keep the analytical encoding
    ResponseIntent.MIXED_SUMMARY: None,  # keep the analytical encoding
}

# A scalar reading is incompatible with a multi-row request, but the two ways
# of being multi-row point at different shapes, so they are detected apart:
#
#   ENUMERATION - "list all", "top 10", "every invoice". The user wants N
#                 rows back. N rows is a table.
#   GROUPING    - "per region", "by month", "for each team". The user wants
#                 one value *per group*, which is a series, and a series is
#                 what a chart draws.
#
# Collapsing these into one veto is what made "total revenue by month" come
# back as a scalar and "how many orders per region" come back as a count.
_ENUMERATION_VETO = re.compile(
    r"\btop\s+(?:[2-9]|\d{2,})\b"
    r"|\bbottom\s+(?:[2-9]|\d{2,})\b"
    r"|\btop\s+(?:two|three|four|five|ten|twenty)\b"
    # "all" as a scope ("the total bonus given in all evaluations") is not a
    # request for every row; only "all X" as the object of the request is.
    r"|(?<!\bin )(?<!\bof )(?<!\bfor )(?<!\bfrom )(?<!\bover )"
    r"\ball (?:the |our |these |those )?[a-z]+s\b"
    r"|\bevery\b|\blist\b"
)

_GROUPING_VETO = re.compile(
    r"\bper\b"
    r"|\bfor each\b|\beach\b|\bacross\b"
    r"|\bby (?:month|quarter|year|week|day|region|category|product|department"
    r"|status|segment|team|branch|channel|customer|store|type)\b"
)

# A per-period word as a series ("the monthly count of X" is one value per
# month), used as a grouping veto only when nothing asks for one extreme: "the
# all-time high for daily signups" and "the highest monthly revenue" are one
# figure, and so is "the average monthly spend" (Stage 6).
_PERIOD_SERIES = re.compile(
    r"(?<!average )(?<!mean )(?<!median )(?<!typical )"
    r"\b(?:monthly|weekly|daily|quarterly|yearly)\b(?! (?:average|mean|median|rate)\b)"
)
_EXTREME = re.compile(r"\ball[- ]time\b|\bpeak\b|\brecord\b")

# An explicit singular quantifier makes the scalar reading immune to both
# vetoes: "list the single highest paying customer" contains "list", but the
# user has named the row count themselves and it is one.
_SINGULAR_OVERRIDE = re.compile(
    r"\bsingle\b|\bjust one\b|\bonly one\b|\btop 1\b|\bone (?:number|value|figure|record|row)\b"
    r"|\b(?:the )?top one\b"
)

# An entity-identification question: the user named a *thing* they want back,
# not a quantity. "which department spends the most" is answered by
# "Engineering", and reporting 482,000 instead answers a question nobody asked.
# The measure still travels with it as the qualifier - it is the evidence for
# the choice, not the choice itself.
_ENTITY_QUESTION = re.compile(
    r"\bwhich [a-z]+(?<!s)\b"
    r"|\bwho (?:is|was|are|were|has|had|spends?|spent|earns?|earned|bought|buys?)\b"
    r"|\bwhat (?:is|was) the (?:name|title|id) of\b"
    r"|\bname (?:of )?the\b"
)

# The counterpart: the user asked for a quantity outright, so the number is the
# answer even when a dimension is named beside it.
_VALUE_QUESTION = re.compile(
    r"\bhow (?:many|much)\b"
    r"|\bwhat'?s the (?:total|sum|average|mean|median|count|number|value|figure)\b"
    r"|\bwhat (?:is|was) the (?:total|sum|average|mean|median|count|number|value|figure)\b"
    r"|\b(?:total|count|number|value|figure|amount) of\b"
    r"|\bjust the (?:number|figure|total|value)\b"
)

# The plural counterpart of an entity question. "which department spends the
# most" wants one name; "which departmentS spend the most" is a ranking of
# several, and a ranking of several is a table. The lookahead protects the
# singular nouns that happen to end in 's' - without it "which business spends
# the most" would be read as plural.
_SINGULAR_S_NOUNS = (
    "business|status|address|class|process|analysis|series|campus|bonus"
    "|premises|goods|news|basis|access|success|focus|census"
)
_PLURAL_ENTITY_QUESTION = re.compile(
    rf"\bwhich (?!(?:{_SINGULAR_S_NOUNS})\b)[a-z]+s\b"
)

# Phrases that look like superlatives or KPI requests but are neither (Stage 5,
# from the Spider DEV failures). "teachers who teach at least two courses" is a
# filter returning many rows, but "least" read it as a single answer - which
# asks Member 1 for LIMIT 1 and silently drops rows. "stores with more products
# than the average" returns stores, not the average. "first name" is a column,
# not "the first". Both classifiers rewrite these to neutral tokens before any
# marker is matched; the tokens contain no marker as a substring.
_NEUTRAL_PHRASES = [
    (re.compile(r"\bat (?:least|most)\b"), "thresholdfilter"),
    (re.compile(r"\b(?:no|not) (?:more|less|fewer|greater) than\b"), "thresholdfilter"),
    (re.compile(r"\b(?:more|less|fewer) than (?:a |one )?single\b"), "thresholdfilter"),
    # "more staff than the minimum staff number of all museums" compares rows
    # to an aggregate; it does not ask for the aggregate.
    (re.compile(r"\bthan\s+(?:the\s+)?(?:overall\s+)?(?:average|mean|minimum|maximum)\b"),
     "than normfilter"),
    (re.compile(r"\b(?:above|below|over|under)\s+(?:the\s+)?(?:overall\s+)?(?:average|mean)\b"),
     "normfilter"),
    (re.compile(r"\b(first|last|middle|full|given|family|maiden)\s+(names?)\b"), r"\1\2"),
    (re.compile(r"\bacross all\b"), "overall"),
]


def neutralize(text: str) -> str:
    """Rewrite threshold, average-filter and name phrases (see _NEUTRAL_PHRASES)."""
    for pattern, replacement in _NEUTRAL_PHRASES:
        text = pattern.sub(replacement, text)
    return text


# A format named only to be refused ("don't give me a chart", "I don't need the
# full list") is evidence against that format, not for it.
_NEGATION_BEFORE = re.compile(
    r"\b(?:dont|don't|do not|not|no|without|never|instead of|rather than)\s+"
    # The negation stops at a word that starts the user's actual request:
    # "no tables please just explain it" refuses tables, not the explanation.
    r"(?:(?!just\b|only\b|but\b|please\b|instead\b|rather\b)\w+\s+){0,3}$"
)


def _negated(text: str, start: int) -> bool:
    return bool(_NEGATION_BEFORE.search(text[max(0, start - 40):start]))


# "the names of the teachers and how many courses they teach": a count per row,
# which is a column of a table, not one figure.
_PER_ROW_COUNT = re.compile(
    r"\b(?:names?|ids?)\b.{0,60}\b(?:and|with) (?:the )?(?:number of|count of|how many)\b"
    r"|\bhow many\b.{0,40}\b(?:they|them|each of them)\b"
)

# Two questions in one request ("what is our MRR and how is it trending", "how
# many departments are there and which one spends most") need an answer to
# each, which only the mixed report gives. A later clause that refers back to
# the rows ("...and how many courses do THEY teach") is a column of the first
# answer, not a second question.
_SECOND_QUESTION = re.compile(r"(?:,|\band\b)\s+(?=(?:how|what|which|who|where|when)\b)")
_BACK_REFERENCE = re.compile(r"\b(?:they|them|their|each|those|these)\b")

# Two superlatives joined together ("the highest and lowest") is a request for
# two rows, which is a small table rather than an answer.
_SUPERLATIVES = re.compile(
    r"\bhighest\b|\blowest\b|\blargest\b|\bsmallest\b|\bbiggest\b|\bmaximum\b"
    r"|\bminimum\b|\bbest\b|\bworst\b|\bmost\b|\bleast\b"
    r"|\bfewest\b|\bgreatest\b|\byoungest\b|\boldest\b|\bearliest\b|\blatest\b"
    r"|\blongest\b|\bshortest\b"
)

# --------------------------------------------------------------------------
# Lexical repair
# --------------------------------------------------------------------------
#
# Real users mistype the exact words that carry the format signal - "summery"
# for summary, "chartt" for chart, "how mnay". Losing the decisive marker to a
# transposed letter drops the request to the analytical prior, which is a
# noticeably worse answer for a fully understandable question.
#
# The repair is deliberately narrow. A token is rewritten only when it is a
# near-miss for a *format* keyword on four independent checks - same first
# letter, same last letter, near-identical length, and a high similarity
# ratio - and only when it is not on the protected list below. Every repair is
# recorded, so a wrong one is visible in the rationale rather than silent.

_FORMAT_VOCAB = (
    "many much summary summarise summarize overview brief briefly explain describe "
    "list chart graph plot table report full total highest lowest average detailed "
    "dashboard visualise visualize records export breakdown comprehensive "
    "distribution compare comparison trend every analysis number numbers count "
    "maximum minimum tabular histogram"
).split()

# Legitimate domain words that are near-misses for a format keyword. Without
# this list the repair would turn "cost" into "count", "last" into "list" and
# "cart" into "chart". The list grows with the corpus; every entry here was
# added because it collided with a real keyword.
_PROTECTED_TOKENS = {
    "cost", "costs", "last", "chat", "chats", "port", "ports", "lost", "court",
    "courts", "fall", "falls", "fill", "fills", "lift", "lifts", "pilot",
    "pilots", "cart", "carts", "card", "cards", "cash", "rate", "rates",
    "date", "dates", "late", "part", "parts", "past", "plan", "plans",
    "mean", "main", "match", "batch", "board", "brand", "grant", "count",
    "amount", "account", "month", "market", "margin", "target", "budget",
}

_SIMILARITY_THRESHOLD = 0.75
_MIN_REPAIR_LENGTH = 3


def _repair_token(token: str) -> str:
    """Rewrite one near-miss token to its format keyword, or return it as-is."""
    if len(token) < _MIN_REPAIR_LENGTH or token in _PROTECTED_TOKENS:
        return token
    if token in _FORMAT_VOCAB:
        return token

    best, best_ratio = token, 0.0
    for candidate in _FORMAT_VOCAB:
        if (
            token[0] != candidate[0]
            or token[-1] != candidate[-1]
            or abs(len(token) - len(candidate)) > 1
        ):
            continue
        ratio = SequenceMatcher(None, token, candidate).ratio()
        # A single transposition inside a four-letter word ("mnay") scores
        # exactly at the threshold, so the bound is inclusive.
        if ratio >= _SIMILARITY_THRESHOLD and ratio > best_ratio:
            best, best_ratio = candidate, ratio
    return best


def repair_typos(text: str) -> tuple:
    """
    Return (repaired_text, [(original, replacement), ...]).

    Word borders and punctuation are preserved so the marker patterns, which
    rely on \\b anchors, behave identically on repaired and clean input.
    """
    repairs = []

    def _sub(match):
        token = match.group(0)
        fixed = _repair_token(token)
        if fixed != token:
            repairs.append((token, fixed))
        return fixed

    return re.sub(r"[a-z]+", _sub, text), repairs


# ==========================================================================
# Precondition - is this a request for data at all?
# ==========================================================================
#
# "hello" has no correct response shape. Neither does "qwertyuiop". Before this
# check existed they were labelled with the fallback intent and the engine
# returned the fallback, so they scored correct by construction - a tautology
# that tested nothing and inflated the reported accuracy.
#
# This is a precondition, not a sixth intent. The taxonomy stays closed and a
# renderable shape is still produced, because the layer must always render
# something. But `is_data_request=False` tells the interface to ask what the
# user meant instead of showing them an empty table.

_PLEASANTRY = re.compile(
    r"^(?:hi|hello|hey|hiya|yo|greetings|good (?:morning|afternoon|evening|day))\b"
    r"|^(?:thanks|thank you|thx|cheers|ta)\b"
    r"|^(?:ok|okay|kk|fine|great|cool|nice|sure|perfect|awesome)\s*[!.]*$"
    r"|^(?:bye|goodbye|see you|later|good ?night)\b"
    r"|\b(?:that was helpful|appreciate it|well done|good job|no worries)\b"
)

# Vocabulary that marks an input as *about data*, even when it names no output
# format and no verb. Deliberately generous: the cost of wrongly calling a real
# question "not a data request" is far higher than the cost of letting an odd
# one through to the normal classifier, which will hedge it with a low
# confidence anyway.
_DOMAIN_VOCAB = set("""
revenue sales cost costs price pricing spend spending expense expenses profit
margin budget invoice invoices payment payments refund refunds transaction
transactions order orders customer customers client clients supplier suppliers
vendor vendors product products item items category categories department
departments employee employees staff headcount salary salaries region regions
branch branches store stores team teams channel channels account accounts
ticket tickets support subscription subscriptions churn retention signup
signups user users traffic conversion delivery deliveries shipment shipments
shipping logistics stock inventory warehouse quantity units sale purchase
purchases contract contracts timesheet timesheets payroll tax dso nps mrr arr
kpi metric metrics figure figures amount balance rate ratio percentage share
performance growth loss gain turnover utilisation utilization throughput
business unit units segment cohort pipeline bid bids quote quotes
month months quarter quarters year years week weeks day days date dates hour
hourly daily weekly monthly quarterly yearly annual annually today yesterday
last next previous current recent period periods time
what which who when where how why whose whom
excel spreadsheet csv file download export report data dataset row rows record
records column columns field fields table tables list chart graph plot summary
overview total totals count number numbers average sum maximum minimum highest
lowest most least top bottom best worst biggest largest smallest peak
everything anything something all every each
""".split())


def _content_tokens(text: str) -> list:
    return re.findall(r"[a-z]+", text)


def is_data_request(text: str, analysis=None, has_lexical_evidence: bool = False) -> tuple:
    """
    Decide whether the input is a data request at all.

    Args:
        text:                 the NORMALISED question (lowercased, collapsed).
        analysis:             optional `QueryAnalysis`, for schema bindings.
        has_lexical_evidence: True when at least one response marker matched.

    Returns (is_request, reason). `reason` is empty when it is a request, and
    otherwise names the check that rejected it: EMPTY, CONVERSATIONAL or
    NO_RECOGNISABLE_CONTENT.

    Four things count as evidence that this is about data, in order of
    strength. A matched response marker comes first deliberately: the marker
    lexicon already *is* a vocabulary of data-request language, and consulting
    it here rather than maintaining a second parallel list is what stops the
    two drifting apart - the first version of this check rejected "visualize"
    and "draw the histogram" purely because the standalone vocabulary had not
    been kept in step with the markers.
    """
    stripped = (text or "").strip()
    if not stripped:
        return False, "EMPTY"

    if _PLEASANTRY.search(stripped):
        return False, "CONVERSATIONAL"

    # 1. The classifier already recognised format language in this input.
    if has_lexical_evidence:
        return True, ""

    # 2. A bound table or column: the question is made of schema names, which
    #    no generic vocabulary could anticipate.
    if analysis is not None:
        if getattr(analysis, "affected_tables", None) or getattr(
            analysis, "affected_columns", None
        ):
            return True, ""

    # 3. Digits carry intent on their own ("customers > 10000", "top 10").
    if re.search(r"\d", stripped):
        return True, ""

    # 4. A business noun, for questions that name a subject but no format
    #    ("revenue", "i dunno maybe sales stuff").
    for token in _content_tokens(stripped):
        if token in _DOMAIN_VOCAB or token.rstrip("s") in _DOMAIN_VOCAB:
            return True, ""

    return False, "NO_RECOGNISABLE_CONTENT"


def _norm(text: str) -> str:
    """Lowercase and collapse whitespace; punctuation is kept for word borders."""
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _score_lexical(text: str) -> tuple:
    """Accumulate weighted marker evidence for all five response intents."""
    scores = {intent: 0.0 for intent in ResponseIntent}
    hits = {intent: [] for intent in ResponseIntent}

    for intent, tiers in RESPONSE_MARKERS.items():
        for weight, patterns in tiers.items():
            for pattern in patterns:
                if any(not _negated(text, m.start()) for m in re.finditer(pattern, text)):
                    scores[intent] += float(weight)
                    hits[intent].append(pattern)
    return scores, hits


def detect_answer_focus(text: str) -> str:
    """
    Decide whether a scalar answer should lead with the entity or the value.

    An explicit quantity request wins over an entity cue, because "how much did
    the top department spend" contains both and is unambiguously about the
    money. Everything else defaults to VALUE, which is the safe reading when
    the question names no entity at all.
    """
    if _VALUE_QUESTION.search(text):
        return "VALUE"
    if _ENTITY_QUESTION.search(text):
        return "ENTITY"
    return "VALUE"


def _named_modalities(text: str) -> list:
    """Which output formats did the user name explicitly, by name?"""
    return [i for i, probe in _MODALITY_PROBES.items()
            if any(not _negated(text, m.start()) for m in re.finditer(probe, text))]


def _apply_precedence(text: str, scores: dict, hits: dict) -> tuple:
    """
    Resolve collisions between families using documented semantic dominance.

    Every rule here encodes a real asymmetry in what the user asked for, not an
    arbitrary tie-break, and each one appends to the audit trail so a verdict
    can always be traced back to the rule that produced it.
    """
    notes = []

    # R2 - A named format beats an inferred one. "as a chart" is the user
    # stating a requirement; "over time" is us inferring one. When the user
    # states it, the inference must not override them. Applied before the
    # vetoes so those operate on the settled explicit evidence.
    for intent in (ResponseIntent.CHART, ResponseIntent.TABLE_CONTENT,
                   ResponseIntent.SHORT_SUMMARY, ResponseIntent.SINGLE_ANSWER):
        tier4 = RESPONSE_MARKERS[intent].get(4, [])
        if any(h in tier4 for h in hits[intent]):
            scores[intent] += 1.5
            notes.append(f"R2 explicit format named: {intent.value}")

    # R3 - Row-count vetoes on the scalar reading, skipped entirely when the
    # user named the row count themselves.
    singular = _SINGULAR_OVERRIDE.search(text)
    if scores[ResponseIntent.SINGLE_ANSWER] > 0 and not singular:
        if _ENUMERATION_VETO.search(text):
            scores[ResponseIntent.SINGLE_ANSWER] *= 0.35
            scores[ResponseIntent.TABLE_CONTENT] += 2.0
            notes.append("R3a enumeration veto: an N-row request is a table, not an answer")
        period_series = (_PERIOD_SERIES.search(text)
                         and not _SUPERLATIVES.search(text) and not _EXTREME.search(text))
        if _GROUPING_VETO.search(text) or period_series:
            scores[ResponseIntent.SINGLE_ANSWER] *= 0.35
            scores[ResponseIntent.CHART] += 2.0
            notes.append("R3b grouping veto: one value per group is a series, not an answer")
    elif singular:
        # Naming the row count is as explicit as naming the format, so it is
        # rewarded on the same scale - otherwise "list the single highest
        # paying customer" ties with its own leading verb and loses.
        scores[ResponseIntent.SINGLE_ANSWER] += 2.0
        notes.append("R3 explicit singular quantifier: vetoes skipped, scalar reinforced")

    # R3d - A plural entity question is a ranking of several rows, whatever
    # superlative follows it. Decisive for the same reason as R3c: the scalar
    # reading scores on the superlative that the plural noun defeats.
    if _PLURAL_ENTITY_QUESTION.search(text) and _SUPERLATIVES.search(text):
        scores[ResponseIntent.SINGLE_ANSWER] *= 0.3
        scores[ResponseIntent.TABLE_CONTENT] = max(
            scores[ResponseIntent.TABLE_CONTENT],
            max(s for i, s in scores.items() if i is not ResponseIntent.TABLE_CONTENT) + 1.5,
        )
        notes.append("R3d plural entity question: several entities is a table")

    # R3c - Two superlatives joined together is a request for two rows. Like
    # R1 this is decisive rather than additive: the scalar reading can have
    # accumulated a large score from the very superlatives that defeat it.
    superlatives = set(_SUPERLATIVES.findall(text))
    if len(superlatives) >= 2 and re.search(r"\band\b|,", text):
        scores[ResponseIntent.SINGLE_ANSWER] *= 0.3
        scores[ResponseIntent.TABLE_CONTENT] = max(
            scores[ResponseIntent.TABLE_CONTENT],
            max(s for i, s in scores.items() if i is not ResponseIntent.TABLE_CONTENT) + 1.5,
        )
        notes.append("R3c paired superlatives: two extremes are two rows")

    # R3e - A count per row ("the names of the teachers and how many courses
    # they teach") is a column of a table, however the count is phrased.
    if _PER_ROW_COUNT.search(text):
        scores[ResponseIntent.SINGLE_ANSWER] *= 0.3
        scores[ResponseIntent.TABLE_CONTENT] = max(
            scores[ResponseIntent.TABLE_CONTENT],
            max(s for i, s in scores.items() if i is not ResponseIntent.TABLE_CONTENT) + 1.0,
        )
        notes.append("R3e per-row count: a count for each listed row is a table column")

    # R4 - "how many / how much" is a counting question and stays scalar even
    # when a dimension is mentioned, unless the dimension is distributed over
    # ("how many orders per region" is a chart; "how many orders in the north
    # region" is one number). Distribution is the stronger signal of the two,
    # because it changes the row count rather than just the filter.
    if re.search(r"\bhow (?:many|much)\b", text) and not _PER_ROW_COUNT.search(text):
        if _GROUPING_VETO.search(text) or re.search(r"\bbreak\s*down\b", text):
            scores[ResponseIntent.CHART] += 3.5
            scores[ResponseIntent.SINGLE_ANSWER] *= 0.4
            notes.append("R4 distributed count: 'how many ... per X' is a per-group series")
        else:
            scores[ResponseIntent.SINGLE_ANSWER] += 2.0
            notes.append("R4 bare count: 'how many/much' resolves to one figure")

    # R1 - Explicit multi-modality, applied last and decisively. Naming two
    # different output formats joined by a conjunction is a request for both,
    # and the only intent that can honour both is MIXED_SUMMARY. Adding points
    # is not enough here: "give me a table and a chart" scores highly for
    # CHART on its own words, so the combined request has to outrank whatever
    # its own components scored, not merely compete with them.
    named = _named_modalities(text)
    if len(named) >= 2 and re.search(_CONJUNCTION, text):
        others = max(s for i, s in scores.items() if i is not ResponseIntent.MIXED_SUMMARY)
        scores[ResponseIntent.MIXED_SUMMARY] = max(
            scores[ResponseIntent.MIXED_SUMMARY], others + 2.0
        )
        notes.append(
            "R1 multi-modality: named "
            + " + ".join(n.value for n in named)
            + " in one request"
        )

    # R1b - Two separate questions in one request, each with evidence of its
    # own, are answered together by the mixed report.
    clauses = [c for c in _SECOND_QUESTION.split(text) if c.strip()]
    two_questions = False
    paired_extremes = len(set(_SUPERLATIVES.findall(text))) >= 2
    if (len(clauses) >= 2 and not paired_extremes
            and not any(_BACK_REFERENCE.search(c) for c in clauses[1:])):
        # "who spent the most and who spent the least" is one question about
        # two extremes (R3c, a two-row table), not two questions.
        if all(any(v > 0 for v in _score_lexical(c)[0].values()) for c in clauses):
            others = max(s for i, s in scores.items() if i is not ResponseIntent.MIXED_SUMMARY)
            scores[ResponseIntent.MIXED_SUMMARY] = max(
                scores[ResponseIntent.MIXED_SUMMARY], others + 2.0)
            two_questions = True                            # decisive for R5
            notes.append(f"R1b two questions in one request ({len(clauses)} clauses)")

    # R5 - MIXED must clear a real bar. A single weak "detailed" or "report"
    # is not a request for three blocks; it needs decisive phrasing or the
    # multi-modality rule to have fired.
    mixed_tier4 = RESPONSE_MARKERS[ResponseIntent.MIXED_SUMMARY].get(4, [])
    mixed_decisive = any(h in mixed_tier4 for h in hits[ResponseIntent.MIXED_SUMMARY])
    if not mixed_decisive and len(named) < 2 and not two_questions:
        scores[ResponseIntent.MIXED_SUMMARY] *= 0.5
        notes.append("R5 mixed damping: no decisive combined-output phrasing")

    # R6 - A summary request that also names data is still a summary. "briefly
    # summarise the sales data" mentions "data" but wants prose; only an
    # explicit second *format* (R1) escalates it to MIXED.
    if (
        scores[ResponseIntent.SHORT_SUMMARY] >= 4
        and re.search(r"\b(?:brief(?:ly)?|short|quick(?:ly)?|in short|tl;?dr|one paragraph)\b", text)
    ):
        # Also below the summary itself: R1 can lift the mixed report above
        # everything ("briefly summarise ... and forecast ..."), and a brevity
        # marker means the user asked for one short block (Stage 6, F10).
        scores[ResponseIntent.MIXED_SUMMARY] = min(
            scores[ResponseIntent.MIXED_SUMMARY] * 0.4,
            scores[ResponseIntent.SHORT_SUMMARY] - 0.5)
        notes.append("R6 brevity marker: an explicitly short answer cannot be a full report")

    return scores, notes


# ==========================================================================
# Implicit result bounds
# ==========================================================================
#
# "the most" is a superlative: it names a bounded top slice, not the whole
# table. When the user states the bound ("top 10") it is EXPLICIT and nothing
# here applies. When they do not, leaving the request unbounded is wrong in
# both directions - it asks Member 1 for a full table scan, and it answers
# "which departments spend the most" with every department there is.
#
# The inferred bound is 5. It is a convention rather than a derivation, so it
# is always marked INFERRED and always disclosed through a warning; a client
# must be able to say "showing the top 5" and offer to widen it. Five sits
# below `visualization.FEW_CATEGORIES` (8), so an inferred slice stays legible
# in every encoding including a donut, and it is small enough that being wrong
# costs the user one follow-up rather than a flood of rows.
IMPLICIT_TOP_N = 5

# A scalar answer is one row by construction. Stating it lets Member 1 emit
# LIMIT 1 rather than returning the whole group and leaving guardrail G1 to
# discover, after the fact, that the "single answer" was 30 rows.
IMPLICIT_SINGLE_N = 1

# Direction is only inferable for superlatives whose meaning is fixed. "best"
# and "worst" depend on whether the metric is one you want high or low - the
# worst return rate is the highest, the worst revenue is the lowest - and that
# is a property of the column, which this layer does not know. Those are left
# to Member 1 with a warning rather than guessed.
_DESC_SUPERLATIVES = re.compile(
    r"\bmost\b|\bhighest\b|\blargest\b|\bbiggest\b|\bmaximum\b|\btop\b|\bgreatest\b"
)
_ASC_SUPERLATIVES = re.compile(
    r"\bleast\b|\blowest\b|\bsmallest\b|\bminimum\b|\bbottom\b|\bfewest\b"
)
_POLARITY_SUPERLATIVES = re.compile(r"\bbest\b|\bworst\b|\bpoorest\b|\bstrongest\b|\bweakest\b")


def derive_bounds(text: str, intent: str, explicit_limit: int = 0,
                  metric_column: str = "") -> dict:
    """
    Derive the row bound and ordering a superlative request implies.

    Args:
        text:           the normalised question.
        intent:         the decided `ResponseIntent` value.
        explicit_limit: a limit the user stated outright; when non-zero it is
                        returned untouched and nothing is inferred.
        metric_column:  the measure to order by, when one was bound.

    Returns:
        {limit, limit_source, ordering, warnings} - `limit_source` is
        EXPLICIT | INFERRED | NONE, mirroring `HorizonSpec.source`, so a
        consumer can always tell a stated bound from an assumed one.
    """
    out = {"limit": 0, "limit_source": "NONE", "ordering": "", "warnings": []}
    text = neutralize(text)

    # Wider than `_SUPERLATIVES`, which R3c uses to detect *paired* extremes:
    # "top" and "bottom" order a result without being extremes themselves, so
    # they belong here but would create false pairs there.
    has_superlative = bool(
        _SUPERLATIVES.search(text)
        or _DESC_SUPERLATIVES.search(text)
        or _ASC_SUPERLATIVES.search(text)
        or _POLARITY_SUPERLATIVES.search(text)
    )

    if explicit_limit:
        out["limit"] = explicit_limit
        out["limit_source"] = "EXPLICIT"
    elif intent == ResponseIntent.SINGLE_ANSWER.value and (
            has_superlative or _SINGULAR_OVERRIDE.search(text)):
        # LIMIT 1 only where something orders the rows. "the name of the
        # museum that had no visitor yet" reads as singular but may match
        # several museums; without an ORDER BY, LIMIT 1 returns an arbitrary
        # one and hides the rest, whereas no limit lets guardrail G1 see the
        # extra rows and show them as a table (Stage 5, Spider DEV).
        out["limit"] = IMPLICIT_SINGLE_N
        out["limit_source"] = "INFERRED"
        out["warnings"].append("IMPLICIT_LIMIT_APPLIED")
    elif intent == ResponseIntent.TABLE_CONTENT.value and has_superlative:
        out["limit"] = IMPLICIT_TOP_N
        out["limit_source"] = "INFERRED"
        out["warnings"].append("IMPLICIT_LIMIT_APPLIED")

    # Ordering is only meaningful once there is something to order by.
    if out["limit"] and has_superlative and metric_column:
        if _DESC_SUPERLATIVES.search(text):
            out["ordering"] = f"{metric_column} DESC"
        elif _ASC_SUPERLATIVES.search(text):
            out["ordering"] = f"{metric_column} ASC"
        elif _POLARITY_SUPERLATIVES.search(text):
            # Deliberately unresolved: see the note above.
            out["warnings"].append("ORDERING_DIRECTION_AMBIGUOUS")

    return out


# Tie-break order for equal evidence. A richer block set never hides anything
# the narrower one would have shown, so when the evidence genuinely balances,
# the more expressive shape is the safer answer.
_EXPRESSIVENESS = {
    ResponseIntent.MIXED_SUMMARY: 4,
    ResponseIntent.CHART: 3,
    ResponseIntent.TABLE_CONTENT: 2,
    ResponseIntent.SHORT_SUMMARY: 1,
    ResponseIntent.SINGLE_ANSWER: 0,
}


def _confidence(best_score: float, runner_score: float) -> tuple:
    """
    Separation-based confidence, damped by absolute evidence.

    Identical in form to the analytical engine's scoring so the two confidence
    numbers in the envelope stay comparable: a 1-vs-0 win is never as
    trustworthy as a 6-vs-1 win, even though both have a perfect margin.
    """
    if best_score <= 0:
        return 0.15, 0.0
    margin = (best_score - runner_score) / max(best_score, 1.0)
    saturation = min(best_score / 8.0, 1.0)
    confidence = min(0.30 + 0.45 * margin + 0.25 * saturation, 0.97)
    return round(confidence, 4), round(margin, 4)


def classify(user_query: str, analysis=None) -> ResponseIntentResult:
    """
    Stages A and B: decide the response shape from the question alone.

    Args:
        user_query: the raw natural-language request (untrusted data).
        analysis:   optional `QueryAnalysis`. When supplied, its analytical
                    intent arbitrates cases the lexicon cannot settle.

    Returns:
        `ResponseIntentResult` - always one of the five intents, never UNKNOWN.
    """
    text = neutralize(_norm(user_query))

    text, repairs = repair_typos(text)

    scores, hits = _score_lexical(text)

    # Precondition: is this about data at all? Evaluated after scoring so it
    # can use the markers as its vocabulary, and on the normalised text so
    # case never decides it. A greeting still gets a renderable shape - the
    # layer must always render something - but it is flagged so the interface
    # can ask what was meant rather than showing an empty table, and so the
    # benchmark stops scoring it as a success.
    data_request, not_request_reason = is_data_request(
        text, analysis, has_lexical_evidence=any(v > 0 for v in scores.values())
    )

    if not text or not data_request:
        return ResponseIntentResult(
            intent=DEFAULT_RESPONSE_INTENT.value,
            confidence=0.1,
            source="RULE",
            rationale=(
                "Not a data request "
                f"({not_request_reason or 'EMPTY'}); no response shape applies. "
                "The default is carried only so the layer has something to render."
            ),
            blocks=[b.value for b in RESPONSE_BLOCKS[DEFAULT_RESPONSE_INTENT]],
            is_data_request=False,
            not_a_request_reason=not_request_reason or "EMPTY",
            evidence_grade="FALLBACK",
            warnings=["NOT_A_DATA_REQUEST"],
        )

    scores, notes = _apply_precedence(text, scores, hits)

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], -_EXPRESSIVENESS[kv[0]]))
    best, best_score = ranked[0]
    runner, runner_score = ranked[1]
    confidence, margin = _confidence(best_score, runner_score)

    source = "RULE"
    warnings = []
    if repairs:
        notes.append(
            "Lexical repair: "
            + ", ".join(f"'{a}' -> '{b}'" for a, b in repairs)
        )
    marker_note = ", ".join(f"'{h}'" for h in hits[best][:3]) or "structural cues"
    rationale = (
        f"Lexical evidence {best_score:.1f} for {best.value} "
        f"vs {runner_score:.1f} for {runner.value} ({marker_note})."
    )

    # ---- Stage B: analytical prior --------------------------------------
    analytic_intent = None
    if analysis is not None:
        try:
            analytic_intent = QueryIntent(analysis.primary_intent)
        except (ValueError, AttributeError):
            analytic_intent = None

    # A tier-4 hit for the winner means the user named this format in their own
    # words. Low confidence there reflects a *contest* between named formats
    # ("the chart or maybe just the number"), not an absence of evidence, and
    # the analytical prior - which knows nothing about presentation - has no
    # standing to overrule it.
    explicit = any(h in RESPONSE_MARKERS[best].get(4, []) for h in hits[best])

    if not explicit and (best_score <= 0 or confidence < LEXICAL_TRUST_THRESHOLD):
        if analytic_intent is not None:
            prior = ANALYTIC_PRIOR.get(analytic_intent, DEFAULT_RESPONSE_INTENT)
            if prior is not best:
                rationale = (
                    f"Lexical evidence inconclusive ({best_score:.1f} vs "
                    f"{runner_score:.1f}); analytical intent "
                    f"{analytic_intent.value} implies {prior.value}."
                )
                best = prior
                source = "ANALYTIC_PRIOR"
                # The prior is a sound structural inference but it is not the
                # user's own words, so it is never claimed as high confidence.
                confidence = round(max(confidence, 0.55), 4)
            else:
                rationale += f" Confirmed by analytical intent {analytic_intent.value}."
                source = "HYBRID"
                confidence = round(min(confidence + 0.12, 0.95), 4)
        elif best_score <= 0:
            best = DEFAULT_RESPONSE_INTENT
            rationale = (
                "No format markers and no analytical intent available; "
                "defaulted to the rows themselves."
            )
            warnings.append("LOW_CONFIDENCE_RESPONSE_INTENT")

    if confidence < 0.45:
        warnings.append("LOW_CONFIDENCE_RESPONSE_INTENT")

    # Grade the evidence, which is a different question from how confident the
    # verdict is. A FALLBACK answer can still land on the right label - the
    # default is TABLE_CONTENT, which is also the most common label - and
    # counting that as an ordinary success overstates the engine's accuracy.
    if source == "ANALYTIC_PRIOR":
        evidence_grade = "INFERRED"
    elif hits.get(best):
        evidence_grade = "DIRECT"
    else:
        evidence_grade = "FALLBACK"
        warnings.append("NO_LEXICAL_EVIDENCE")

    return ResponseIntentResult(
        intent=best.value,
        confidence=confidence,
        source=source,
        rationale=" ".join([rationale] + notes),
        blocks=[b.value for b in RESPONSE_BLOCKS[best]],
        answer_focus=detect_answer_focus(text),
        is_data_request=True,
        evidence_grade=evidence_grade,
        scores={i.value: s for i, s in scores.items()},
        matched_markers={i.value: h for i, h in hits.items() if h},
        runner_up=runner.value,
        margin=margin,
        warnings=warnings,
    )


# ==========================================================================
# Stage C - result-set guardrails
# ==========================================================================


def apply_guardrails(result: ResponseIntentResult, profile=None, rows=None,
                     forecast_requested: bool = False, analytic_intent: str = ""):
    """
    Re-check the pre-execution verdict against the data that actually came back.

    A guardrail fires only on a contradiction the result set proves - never on
    a re-reading of the question - so each repair is defensible and is recorded
    in `guardrails_applied` alongside the intent it replaced.

    `forecast_requested` is True when the user explicitly asked about the
    future. The rows are then the history the forecast is built from, not the
    answer, so their count cannot contradict a single-answer reading.
    """
    rows = rows or []
    row_count = len(rows)
    col_count = len(rows[0]) if rows and isinstance(rows[0], dict) else 0

    measures = list(getattr(profile, "measure_columns", []) or [])
    temporal = getattr(profile, "temporal_column", "") or ""
    dimensions = list(getattr(profile, "dimension_columns", []) or [])

    original = ResponseIntent(result.intent)
    current = original
    applied = list(result.guardrails_applied)

    # G0 - Nothing came back. No shape can be rendered over zero rows, and a
    # chart or a scalar over an empty set would fabricate an answer.
    if row_count == 0:
        if current is not ResponseIntent.SHORT_SUMMARY:
            applied.append(
                f"G0 empty result: {current.value} -> TABLE_CONTENT "
                "(no rows to answer, chart or plot)"
            )
            current = ResponseIntent.TABLE_CONTENT
        result.intent = current.value
        result.original_intent = original.value
        result.guardrails_applied = applied
        result.blocks = [b.value for b in RESPONSE_BLOCKS[current]]
        if applied:
            result.source = "GUARDRAIL"
            result.warnings.append("EMPTY_RESULT_SET")
        return result

    # G1 - A single answer must be a single value. More than one row, or more
    # than two columns, means the question was not scalar after all - unless
    # the question is about the future: "how much will I spend next month" is
    # answered by one projected figure computed FROM the 24 monthly rows. Before
    # Stage 5 this fired on every such question and the user got the history
    # table instead of the forecast.
    if current is ResponseIntent.SINGLE_ANSWER and forecast_requested:
        result.rationale = (f"{result.rationale} G1 not applied: a scalar question about "
                            "the future is answered by the forecast, not by a history row.")
    elif current is ResponseIntent.SINGLE_ANSWER and (row_count > 1 or col_count > 2):
        applied.append(
            f"G1 scalar contradicted: result is {row_count}x{col_count}, "
            "not one value -> TABLE_CONTENT"
        )
        current = ResponseIntent.TABLE_CONTENT

    # G2 - A chart needs something to encode: at least one measure and either a
    # time axis or a categorical axis, over at least two points.
    chartable = bool(measures) and (bool(temporal) or bool(dimensions)) and row_count >= 2
    # A histogram needs one measure and no axis; a scatter plot needs two
    # measures. Before Stage 6 every distribution and correlation question was
    # turned into a table here, although visualization.py draws both (fixtures
    # D01-D03, K01).
    if analytic_intent == "DISTRIBUTION" and measures and row_count >= 5:
        chartable = True
    if analytic_intent == "CORRELATION" and len(measures) >= 2 and row_count >= 3:
        chartable = True
    if current is ResponseIntent.CHART and not chartable:
        reason = (
            "no numeric measure" if not measures
            else "no temporal or categorical axis" if not (temporal or dimensions)
            else f"only {row_count} data point(s)"
        )
        target = (
            ResponseIntent.SINGLE_ANSWER
            if row_count == 1 and col_count <= 2
            else ResponseIntent.TABLE_CONTENT
        )
        applied.append(f"G2 not chartable ({reason}) -> {target.value}")
        current = target

    # G3 - One row, one value, requested as a table: the table is a degenerate
    # 1x1 grid and the scalar reads better. Only fires when the user did not
    # explicitly ask for a table.
    explicit_table = "TABLE_CONTENT" in (result.matched_markers or {})
    if (
        current is ResponseIntent.TABLE_CONTENT
        and row_count == 1
        and col_count == 1
        and not explicit_table
    ):
        applied.append("G3 degenerate 1x1 table -> SINGLE_ANSWER")
        current = ResponseIntent.SINGLE_ANSWER

    # G4 - A mixed report still needs a plottable chart block. When the data
    # cannot be charted the report is emitted without it, rather than shipping
    # an empty frame; the block list, not the intent, is what changes.
    blocks = [b.value for b in RESPONSE_BLOCKS[current]]
    if current is ResponseIntent.MIXED_SUMMARY and not chartable:
        blocks = [b for b in blocks if b != "CHART"]
        applied.append("G4 mixed report: chart block dropped, data is not plottable")

    if applied != result.guardrails_applied:
        result.source = "GUARDRAIL"
        result.rationale = (
            f"{result.rationale} Result set adjusted the verdict: "
            + "; ".join(applied[len(result.guardrails_applied):])
            + "."
        )

    result.original_intent = original.value
    result.intent = current.value
    result.blocks = blocks
    result.guardrails_applied = applied
    return result
