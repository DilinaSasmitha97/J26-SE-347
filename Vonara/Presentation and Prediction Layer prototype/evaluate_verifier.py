"""
Summary-verifier benchmark (Stage 4).

The verifier (summarization.verify_summary) is the gate on LLM narration: a
narrated summary is shown only if every number in it traces to a computed
claim. This benchmark measures the gate by fault injection, on the claim sets
of the 12 synthetic benchmark scenarios, so the truth is known:

FAITHFUL rewrites (the verifier should PASS them - a rejection is a false alarm
that throws away a correct narration):
  AS_IS          the deterministic text itself
  NO_SEPARATORS  48,251 -> 48251
  ROUNDED_3SF    48,251 -> 48,300 (three significant figures)
  SCALE_WORDS    48,251 -> 48.3k, 1,234,567 -> 1.23 million
  HYPHEN_RANGE   "6,040 to 6,869" -> "6,040-6,869"
  DATE_FORMATS   2025-12-01 -> December 2025, Jan 2026 -> 2026-01
  NUMBER_WORDS   a small number that is in the claims written as a word

CORRUPTED narrations (the verifier should REJECT them):
  INVENTED       one number replaced by an unrelated value
  OFF_5 / OFF_10 / OFF_25 / X10   one number off by 5, 10, 25 % or 10x
  TRANSPOSED     two adjacent digits of one number swapped
  WORD_INVENTED  an added sentence with an invented number written as a word

BLIND SPOTS, reported but not counted against the verifier, because a check on
numbers alone cannot see them by design:
  OFF_1_5        one number off by 1.5 % (inside the 2 % tolerance)
  SWAPPED        two correct numbers exchanged between sentences
  DIRECTION      "increased" -> "decreased" (no number changes)

Optional live run (`--live N`): the configured LLM narrates N scenarios through
the production path (pipeline.run with use_llm_summary=True), and each rejected
number is classed as ROUNDING (within 5 % of a claim number), DATE_OR_RANGE
(a date or range fragment), WORD (a number written as a word) or INVENTED.
This sends the synthetic claim text to the LLM provider in .env.

Run:  python evaluate_verifier.py              (fault injection, current code)
      python evaluate_verifier.py --baseline   (save as the pre-change baseline)
      python evaluate_verifier.py --live 12    (also the live LLM run)
"""

import json
import os
import random
import re
import sys
from pathlib import Path

LIVE = "--live" in sys.argv
if not LIVE:
    os.environ["LLM_PROVIDER"] = "none"

import pipeline  # noqa: E402
import profiler  # noqa: E402
import summarization  # noqa: E402
import synthetic_data  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "data_and_reports" / "verifier_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "verifier_benchmark_results.json"
BASELINE_JSON = HERE / "data_and_reports" / "verifier_benchmark_baseline_stage3.json"

SEED = 2026
PER_SCENARIO = 5          # random targets per scenario for each corruption type

FAITHFUL = ("AS_IS", "NO_SEPARATORS", "ROUNDED_3SF", "SCALE_WORDS", "HYPHEN_RANGE",
            "DATE_FORMATS", "NUMBER_WORDS")
CORRUPTED = ("INVENTED", "OFF_5", "OFF_10", "OFF_25", "X10", "TRANSPOSED", "WORD_INVENTED")
BLIND = ("OFF_1_5", "SWAPPED", "DIRECTION")

_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"]
_SMALL_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven",
                8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}
_INVENTED_WORDS = {13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
                   17: "seventeen", 18: "eighteen", 19: "nineteen", 30: "thirty",
                   40: "forty", 70: "seventy", 90: "ninety"}

# A displayed number that is not part of a date: 6,351 / 85.7 / 24.
_DISPLAY_NUM = re.compile(r"(?<![\w.\-])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)(?![\w\-])")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_MON_YEAR = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{4})\b")


def _value(token: str) -> float:
    return float(token.replace(",", ""))


def _format_like(original: str, value: float) -> str:
    decimals = len(original.split(".")[1]) if "." in original else 0
    s = f"{value:,.{decimals}f}" if "," in original else f"{value:.{decimals}f}"
    return s


def _targets(text: str) -> list:
    """Number tokens that a corruption may change: not years, not tiny counts."""
    out = []
    for m in _DISPLAY_NUM.finditer(text):
        v = _value(m.group(1))
        if 1900 <= v <= 2100 and "." not in m.group(1) and "," not in m.group(1):
            continue
        if v < 10:
            continue
        out.append(m)
    return out


def _replace(text: str, m, new: str) -> str:
    return text[:m.start(1)] + new + text[m.end(1):]


def _allowed(claims) -> list:
    vals = []
    for c in claims:
        vals.append(float(c.value))
        vals += [float(v) for v in c.supporting_values if isinstance(v, (int, float))]
    return vals


def _near_allowed(v: float, allowed: list, tol: float = 0.02) -> bool:
    return any((abs(v - a) / max(abs(a), 1e-9) <= tol) if a else abs(v) < 1e-9 for a in allowed)


# ---- faithful rewrites ----------------------------------------------------

def faithful(kind: str, text: str, claims) -> str:
    if kind == "AS_IS":
        return text
    if kind == "NO_SEPARATORS":
        return re.sub(r"(\d),(?=\d{3})", r"\1", text)
    if kind == "ROUNDED_3SF":
        def r3(m):
            v = _value(m.group(1))
            if v < 100:
                return m.group(0)
            digits = len(str(int(v))) - 3
            return f"{round(v, -digits):,.0f}"
        return _DISPLAY_NUM.sub(r3, text)
    if kind == "SCALE_WORDS":
        def sc(m):
            v = _value(m.group(1))
            if v >= 1_000_000:
                return f"{v / 1_000_000:.2f} million"
            if v >= 10_000:
                return f"{v / 1000:.1f}k"
            return m.group(0)
        return _DISPLAY_NUM.sub(sc, text)
    if kind == "HYPHEN_RANGE":
        return re.sub(r"(\d[\d,.]*) to (\d[\d,.]*\d)", r"\1-\2", text)
    if kind == "DATE_FORMATS":
        text = _ISO_DATE.sub(lambda m: f"{_MONTHS[int(m.group(2)) - 1]} {m.group(1)}", text)
        return _MON_YEAR.sub(lambda m: f"{m.group(2)}-{_MONTHS.index(next(x for x in _MONTHS if x.startswith(m.group(1)))) + 1:02d}", text)
    if kind == "NUMBER_WORDS":
        allowed = {round(a, 6) for a in _allowed(claims)}
        for n, word in _SMALL_WORDS.items():
            m = re.search(rf"(?<![\w.,\-]){n}(?![\w.,\-%])", text)
            if m and n in allowed:
                return text[:m.start()] + word + text[m.end():]
        return text
    raise ValueError(kind)


# ---- corruptions ----------------------------------------------------------

def corrupt(kind: str, text: str, claims, rng: random.Random):
    """Returns (new_text, collides) or None when the corruption does not apply."""
    allowed = _allowed(claims)
    targets = _targets(text)
    if kind in ("WORD_INVENTED",):
        choices = [(n, w) for n, w in _INVENTED_WORDS.items() if not _near_allowed(n, allowed)]
        n, word = rng.choice(choices)
        return text + f" The value was above average in {word} of the periods.", False
    if kind == "DIRECTION":
        for a, b in (("increased", "decreased"), ("decreased", "increased"),
                     ("higher", "lower"), ("above", "below"), ("rise", "fall")):
            if re.search(rf"\b{a}\b", text):
                return re.sub(rf"\b{a}\b", b, text, count=1), True
        return None
    if kind == "SWAPPED":
        distinct = {}
        for m in targets:
            distinct.setdefault(round(_value(m.group(1)), 6), m)
        if len(distinct) < 2:
            return None
        m1, m2 = rng.sample(list(distinct.values()), 2)
        first, second = sorted((m1, m2), key=lambda m: m.start())
        new = (text[:first.start(1)] + second.group(1) + text[first.end(1):second.start(1)]
               + first.group(1) + text[second.end(1):])
        return new, True
    if not targets:
        return None
    m = rng.choice(targets)
    v = _value(m.group(1))
    if kind == "INVENTED":
        for _ in range(100):
            nv = v * rng.uniform(0.3, 3.0)
            if not _near_allowed(nv, allowed, 0.05):
                break
        new = _format_like(m.group(1), nv)
    elif kind == "TRANSPOSED":
        digits = [i for i, ch in enumerate(m.group(1)) if ch.isdigit()]
        pairs = [(a, b) for a, b in zip(digits, digits[1:])
                 if m.group(1)[a] != m.group(1)[b]]
        if not pairs:
            return None
        a, b = rng.choice(pairs)
        s = list(m.group(1))
        s[a], s[b] = s[b], s[a]
        new = "".join(s)
        nv = _value(new)
    else:
        factor = {"OFF_5": 0.05, "OFF_10": 0.10, "OFF_25": 0.25, "OFF_1_5": 0.015}.get(kind)
        nv = v * 10 if kind == "X10" else v * (1 + rng.choice((-1, 1)) * factor)
        new = _format_like(m.group(1), nv)
    collides = _near_allowed(_value(new), allowed)
    return _replace(text, m, new), collides


# ---- run ------------------------------------------------------------------

def scenario_claims():
    out = []
    for sc in synthetic_data.benchmark_suite():
        env = pipeline.run(sc["query"], rows=sc["rows"], schema_meta=sc["schema"],
                           use_llm=False, enable_cache=False)
        claims = [summarization.Claim(**c) for c in env["summary"]["claims"]]
        out.append((sc["name"], env["summary"]["text"], claims))
    return out


def run_injection() -> dict:
    rng = random.Random(SEED)
    data = scenario_claims()
    res = {}
    for kind in FAITHFUL:
        passed = total = 0
        failures = []
        for name, text, claims in data:
            t = faithful(kind, text, claims)
            if kind != "AS_IS" and t == text:
                continue
            v = summarization.verify_summary(t, claims)
            total += 1
            passed += v["passed"]
            if not v["passed"]:
                failures.append({"scenario": name, "unverified": v["unverified_values"][:5]})
        res[kind] = {"group": "FAITHFUL", "cases": total, "passed": passed,
                     "false_rejection_rate": (total - passed) / total if total else None,
                     "examples": failures[:3]}
    for kind in CORRUPTED + BLIND:
        caught = total = collisions = 0
        for name, text, claims in data:
            for _ in range(PER_SCENARIO if kind not in ("DIRECTION",) else 1):
                made = corrupt(kind, text, claims, rng)
                if made is None:
                    continue
                t, collides = made
                v = summarization.verify_summary(t, claims)
                total += 1
                caught += not v["passed"]
                collisions += collides
        res[kind] = {"group": "BLIND" if kind in BLIND else "CORRUPTED", "cases": total,
                     "rejected": caught, "detection_rate": caught / total if total else None,
                     "collides_with_a_claim_number": collisions}
    return res


def classify_unverified(value: float, text: str, claims) -> str:
    allowed = _allowed(claims) + [n for c in claims for n in summarization._numbers_in(c.text)]
    if _near_allowed(value, allowed, 0.05):
        return "ROUNDING"
    if value < 0 or re.search(rf"\d-{abs(int(value)):02d}\b", text):
        return "DATE_OR_RANGE"
    return "INVENTED"


def run_live(n: int) -> dict:
    import llm
    if not llm.is_available():
        return {"skipped": "no LLM provider configured"}
    out = {"provider": llm.PROVIDER, "model": llm.active_model(), "scenarios": []}
    for name, _, claims in scenario_claims()[:n]:
        # The production narration path: same prompt, same verifier. (The
        # pipeline only narrates when the response shape has a SUMMARY block,
        # and the benchmark questions are chart questions.)
        try:
            llm_text, mode, ver = summarization.render_with_llm(claims)
        except Exception as exc:  # noqa: BLE001 - provider errors are recorded
            out["scenarios"].append({"scenario": name, "mode": "UNAVAILABLE",
                                     "error": str(exc)[:200]})
            continue
        unverified = ver.get("unverified_values") or []
        stage3 = (summarization.verify_summary(llm_text, claims, tolerance=0.02)["passed"]
                  if llm_text else None)
        out["scenarios"].append({
            "scenario": name, "mode": mode,
            "numbers": ver.get("numbers_in_summary"), "unverified": unverified,
            "classes": [classify_unverified(u, llm_text, claims) for u in unverified],
            "stage3_rule_would_pass": stage3,
            "narration": llm_text,
        })
    modes = [x["mode"] for x in out["scenarios"]]
    out["verified"] = modes.count("LLM_VERIFIED")
    out["rejected"] = modes.count("LLM_REJECTED")
    out["unavailable"] = len(modes) - out["verified"] - out["rejected"]
    return out


def _pct(v):
    return "-" if v is None else f"{100 * v:.1f}%"


def main() -> int:
    baseline_mode = "--baseline" in sys.argv
    results = {"seed": SEED, "injection": run_injection()}
    if LIVE:
        n = int(sys.argv[sys.argv.index("--live") + 1])
        results["live"] = run_live(n)
    if baseline_mode:
        BASELINE_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"Baseline written: {BASELINE_JSON.name}")
    base = (json.loads(BASELINE_JSON.read_text(encoding="utf-8"))["injection"]
            if BASELINE_JSON.exists() and not baseline_mode else None)
    inj = results["injection"]

    md = ["# Summary-verifier benchmark (Stage 4)", "",
          "Generated by `evaluate_verifier.py`. Do not edit by hand. Fault injection on the "
          "claim sets of the 12 synthetic benchmark scenarios (seed "
          f"{SEED}, {PER_SCENARIO} random targets per scenario and corruption).", "",
          "## Correct narrations (should pass)", "",
          "| Rewrite | Cases | " + ("Stage 3 false rejections | " if base else "")
          + "False rejections | Example rejected numbers |",
          "|---|---|" + ("---|" if base else "") + "---|---|"]
    for k in FAITHFUL:
        r = inj[k]
        row = f"| {k} | {r['cases']} | "
        if base:
            row += f"{_pct(base[k]['false_rejection_rate'])} | "
        ex = "; ".join(str(e["unverified"]) for e in r["examples"][:2]) or "-"
        md.append(row + f"**{_pct(r['false_rejection_rate'])}** | {ex} |")
    md += ["", "## Corrupted narrations (should be rejected)", "",
           "| Corruption | Cases | " + ("Stage 3 detection | " if base else "")
           + "Detection | Corrupted value lands within 2 % of another claim number |",
           "|---|---|" + ("---|" if base else "") + "---|---|"]
    for k in CORRUPTED:
        r = inj[k]
        row = f"| {k} | {r['cases']} | "
        if base:
            row += f"{_pct(base[k]['detection_rate'])} | "
        md.append(row + f"**{_pct(r['detection_rate'])}** | {r['collides_with_a_claim_number']} |")
    md += ["", "## Blind spots of a number-only check (reported, not expected to be caught)", "",
           "| Change | Cases | Detection |", "|---|---|---|"]
    for k in BLIND:
        r = inj[k]
        md.append(f"| {k} | {r['cases']} | {_pct(r['detection_rate'])} |")
    if "live" in results:
        lv = results["live"]
        md += ["", "## Live LLM narration", ""]
        if "skipped" in lv:
            md.append(f"Skipped: {lv['skipped']}.")
        else:
            md += [f"Provider {lv['provider']}, model {lv['model']}: **{lv['verified']}** "
                   f"narrations verified and shown, **{lv['rejected']}** rejected "
                   f"(deterministic text shown instead), {lv['unavailable']} unavailable.", "",
                   "| Scenario | Mode | Numbers | Rejected numbers | Class | Stage 3 rule |",
                   "|---|---|---|---|---|---|"]
            for x in lv["scenarios"]:
                s3 = {True: "pass", False: "reject", None: "-"}[x["stage3_rule_would_pass"]]
                md.append(f"| {x['scenario']} | {x['mode']} | {x['numbers']} | "
                          f"{x['unverified'] or '-'} | {x['classes'] or '-'} | {s3} |")
    text = "\n".join(md) + "\n"
    print(text)
    if not baseline_mode:
        REPORT_MD.write_text(text, encoding="utf-8")
        REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
        print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
