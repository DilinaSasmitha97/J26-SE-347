"""
Scenario language - the one parser for what-if clauses (Stage 4).

Both routes into the what-if engine use it: text typed into the simulate box
(whatif.parse_scenario) and a what-if asked inside the question
(query_analyzer._detect_what_if -> whatif.scenario_from_analysis). Before
Stage 4 each route had its own copy, and both matched direction words as
substrings, so "unless" read as "less" (a decrease), "supplier" and "group" as
"up", "execute" as "cut" and "address" as "add".

The parser reads one change: a direction and a percentage, plus whether the
change applies at once or is phased in. It refuses rather than guesses when the
clause cannot be read as exactly one percentage change:

  NO_MAGNITUDE      no percentage, multiplier or "by N"
  NO_DIRECTION      a percentage with no word saying which way
  NEGATED           "don't cut", "do not increase" - describes no change
  MULTIPLE_CHANGES  two percentages ("raise prices 5% and cut costs 3%")
  RANGE             "10-15%", "between 5 and 10 percent"
  ABSOLUTE_AMOUNT   "$500", "2000 dollars", "3 new staff" - not a percentage
  NO_CHANGE         a 0 % change

Pure functions, no dependencies, so the analyzer and the engine can share it.
"""

import re

MAX_DECREASE_PCT = 100.0   # a fall of more than 100 % would make values negative
MAX_INCREASE_PCT = 300.0   # up to "quadruple"; beyond it the linear model is not a scenario

_INCREASE = {
    "increase", "increases", "increased", "increasing",
    "raise", "raises", "raised", "raising",
    "rise", "rises", "rose", "risen", "rising",
    "grow", "grows", "grew", "grown", "growing", "growth",
    "boost", "boosts", "boosted", "boosting",
    "add", "adds", "added", "adding",
    "expand", "expands", "expanded", "expanding",
    "climb", "climbs", "climbed", "climbing",
    "jump", "jumps", "jumped", "jumping",
    "surge", "surges", "surged", "surging",
    "soar", "soars", "soared", "soaring",
    "improve", "improves", "improved", "improving", "improvement",
    "gain", "gains", "gained", "gaining",
    "hike", "hikes", "hiked", "hiking",
    "up", "more", "higher", "bigger", "larger", "greater",
}
_DECREASE = {
    "reduce", "reduces", "reduced", "reducing", "reduction",
    "decrease", "decreases", "decreased", "decreasing",
    "cut", "cuts", "cutting",
    "lower", "lowers", "lowered", "lowering",
    "drop", "drops", "dropped", "dropping",
    "fall", "falls", "fell", "fallen", "falling",
    "shrink", "shrinks", "shrank", "shrunk", "shrinking",
    "decline", "declines", "declined", "declining",
    "slash", "slashes", "slashed", "slashing",
    "trim", "trims", "trimmed", "trimming",
    "sink", "sinks", "sank", "sunk", "sinking",
    "plunge", "plunges", "plunged", "plunging",
    "dip", "dips", "dipped", "dipping",
    "save", "saves", "saved", "saving",
    "down", "less", "fewer", "smaller", "cheaper",
}
# word -> (direction, magnitude %)
_MULTIPLIERS = {
    "double": ("INCREASE", 100.0), "doubles": ("INCREASE", 100.0),
    "doubled": ("INCREASE", 100.0), "doubling": ("INCREASE", 100.0),
    "twice": ("INCREASE", 100.0),
    "triple": ("INCREASE", 200.0), "triples": ("INCREASE", 200.0),
    "tripled": ("INCREASE", 200.0), "tripling": ("INCREASE", 200.0),
    "thrice": ("INCREASE", 200.0),
    "quadruple": ("INCREASE", 300.0), "quadruples": ("INCREASE", 300.0),
    "quadrupled": ("INCREASE", 300.0), "quadrupling": ("INCREASE", 300.0),
    "halve": ("DECREASE", 50.0), "halves": ("DECREASE", 50.0),
    "halved": ("DECREASE", 50.0), "halving": ("DECREASE", 50.0),
    "half": ("DECREASE", 50.0),
}
_NEGATIONS = {"not", "don't", "dont", "doesn't", "doesnt", "didn't", "didnt", "never",
              "without", "no", "won't", "wont", "can't", "cant", "cannot", "isn't",
              "aren't", "wasn't", "weren't", "shouldn't", "wouldn't"}
NEGATION_WINDOW = 3          # tokens before the direction word

_RAMP = re.compile(r"\b(gradual(?:ly)?|over time|phas(?:e|ed|es|ing)\b|ramp(?:s|ed|ing)?\b|"
                   r"slowly|step by step|progressively|incrementally)")
_PCT = re.compile(r"(?<![\w.])([+-]?)(\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)")
_RANGE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent)?\s*(?:-|to)\s*\d+(?:\.\d+)?\s*(?:%|percent)"
                    r"|\bbetween\s+\d+(?:\.\d+)?\s*(?:%|percent)?\s+and\s+\d+(?:\.\d+)?")
_ABSOLUTE = re.compile(
    r"(?:[$£€]|\brs\.?|\blkr|\busd)\s*\d"
    r"|\d+(?:\.\d+)?\s*(?:dollars?|usd|rupees?|lkr|euros?|pounds?|units?|staff|people|"
    r"employees?|new|more\s+(?:staff|people|employees|units))\b")
_BARE_BY = re.compile(r"\bby\s+([+-]?)(\d+(?:\.\d+)?)\b(?!\s*(?:%|percent|\.\d))")
_TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|[+-]?\d+(?:\.\d+)?%?")


def _tokens(text: str) -> list:
    """(token, char_start) pairs."""
    return [(m.group(0), m.start()) for m in _TOKEN.finditer(text)]


def _refuse(code: str, note: str) -> dict:
    return {"valid": False, "direction": "", "magnitude_pct": 0.0, "apply_mode": "IMMEDIATE",
            "reason_code": code, "note": note}


def parse(text: str) -> dict:
    """
    Read one percentage change from a what-if clause.

    Returns {valid, direction, magnitude_pct, apply_mode, reason_code, note}.
    reason_code is "" for a valid parse, else one of the refusal codes above.
    """
    lowered = (text or "").lower().replace("–", "-").replace("—", "-")
    if not lowered.strip():
        return _refuse("EMPTY", "Empty scenario text.")
    mode = "RAMPED" if _RAMP.search(lowered) else "IMMEDIATE"

    if _RANGE.search(lowered):
        return _refuse("RANGE", "The scenario gives a range; give one percentage to simulate.")

    tokens = _tokens(lowered)
    words = [t for t, _ in tokens]

    # --- the quantity: percentages, multipliers, or "by N" ---------------
    quantities = []          # (char_pos, magnitude, sign, is_target, multiplier_dir)
    for m in _PCT.finditer(lowered):
        before = lowered[:m.start()]
        is_target = bool(re.search(r"\bto\s*$", before))
        quantities.append((m.start(), float(m.group(2)), m.group(1), is_target, None))
    for i, (tok, pos) in enumerate(tokens):
        if tok in _MULTIPLIERS:
            if tok == "half" and i + 1 < len(words) and words[i + 1] in ("of", "the"):
                continue     # "half of the stores" names a subset, not a change
            direction, magnitude = _MULTIPLIERS[tok]
            quantities.append((pos, magnitude, "", False, direction))
    if not quantities:
        if _ABSOLUTE.search(lowered):
            return _refuse("ABSOLUTE_AMOUNT", "The change is an absolute amount; only "
                           "percentage changes can be simulated.")
        m = _BARE_BY.search(lowered)
        if m:
            quantities.append((m.start(2), float(m.group(2)), m.group(1), False, None))
    if not quantities:
        return _refuse("NO_MAGNITUDE", "No percentage found (expected e.g. '20%', "
                       "'by 15', 'double').")
    if len({round(q[1], 9) for q in quantities}) > 1 or len(quantities) > 2:
        return _refuse("MULTIPLE_CHANGES", "The scenario contains more than one change; "
                       "simulate one change at a time.")
    q_pos, magnitude, sign, is_target, mult_dir = quantities[0]

    # --- the direction ----------------------------------------------------
    note = ""
    q_index = min(range(len(tokens)), key=lambda i: abs(tokens[i][1] - q_pos))
    directional = [(i, "INCREASE" if w in _INCREASE else "DECREASE")
                   for i, w in enumerate(words) if w in _INCREASE or w in _DECREASE]
    if len({d for _, d in directional}) > 1 and len(quantities) > 1:
        return _refuse("MULTIPLE_CHANGES", "The scenario contains changes in opposite "
                       "directions; simulate one change at a time.")
    anchor = None
    if mult_dir:
        # The word carries its own direction; "falls to half" is a 50 % fall.
        direction, anchor = mult_dir, q_index
    elif sign in ("+", "-"):
        direction, anchor = ("INCREASE" if sign == "+" else "DECREASE"), q_index
    elif is_target:
        if abs(magnitude - 100.0) < 1e-9:
            return _refuse("NO_CHANGE", "A target of 100 % is no change.")
        direction = "INCREASE" if magnitude > 100.0 else "DECREASE"
        magnitude = abs(magnitude - 100.0)
        anchor = q_index
        note = f"Read as a target level: {direction.lower()} of {magnitude:g}%."
    elif directional:
        # The direction word nearest the number; ties go to the earlier word.
        anchor, direction = min(directional, key=lambda d: (abs(d[0] - q_index), d[0]))
    else:
        return _refuse("NO_DIRECTION", "No word says which way the change goes "
                       "(e.g. 'increase', 'cut', 'rise', 'fall').")

    window = words[max(0, anchor - NEGATION_WINDOW):anchor]
    if any(w in _NEGATIONS for w in window) or "do not" in " ".join(window):
        return _refuse("NEGATED", "The scenario is negated ('don't', 'not', 'never'), "
                       "so it describes no change to simulate.")

    if magnitude == 0:
        return _refuse("NO_CHANGE", "A 0% change leaves the forecast unchanged.")
    limit = MAX_INCREASE_PCT if direction == "INCREASE" else MAX_DECREASE_PCT
    if magnitude > limit:
        note = f"Magnitude clamped from {magnitude:g}% to {limit:g}%."
        magnitude = limit
    if not note and quantities[0][2] == "" and not mult_dir and not is_target \
            and not _PCT.search(lowered):
        note = f"'by {magnitude:g}' read as {magnitude:g}%."
    return {"valid": True, "direction": direction, "magnitude_pct": magnitude,
            "apply_mode": mode, "reason_code": "", "note": note}
