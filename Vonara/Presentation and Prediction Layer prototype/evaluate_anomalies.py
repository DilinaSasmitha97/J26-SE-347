"""
Labelled anomaly benchmark (Stage 3), reported per dimension as proposal
section 3.11 requires, and per detection rule as section 3.7 requires.

Detectors compared, all through anomaly.detect_anomalies:

  STATIC     textbook 1.5 x IQR fence or |z| > 3 on raw levels (the control)
  IQR        adaptive fence only
  ZSCORE     adaptive Z-score only
  COMBINED   adaptive fence or Z-score (the production rule)

HISTORICAL dimension
  A factorial grid of series: length {24, 36, 48} x shape {FLAT, TREND,
  SEASONAL, TREND_SEASONAL} x noise {3, 8, 15 % of level} x REPS. Each series
  carries 0-3 injected point anomalies (spike or dip) of 3, 4 or 6 sigma, at
  least two periods apart. A quarter of the series are clean, so false alarms
  are measured on data with nothing to find. Scored per point: precision,
  recall, F1, false-positive rate, plus recall per magnitude and per shape.

PREDICTIVE dimension
  Series of the same shapes with HORIZON future periods held out. Scenarios:
    NORMAL         nothing happens; the future continues the process
    SHIFT          a level shift starts 1-4 periods before the end and lasts
                   through the future
    SPIKE_LAST     a one-off spike in the last observed period; the future is
                   normal
  The forecast comes from the production selector (select_model ->
  project_series). Truth is detector-independent: a future point is anomalous
  if, and only if, an injected event covers it. A predictive warning is the
  claim "this future point will be outside the normal range"; it is scored
  against that truth per point.

Two disjoint seeds: DEV (2026) is the data any Stage 3 design choice may be
tuned on; TEST (2027) is reported once with the frozen code.

Run:  python evaluate_anomalies.py
"""

import json
import math
import os
import random
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("LLM_PROVIDER", "none")

import anomaly as anomaly_mod  # noqa: E402
import prediction  # noqa: E402
import profiler  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "data_and_reports" / "anomaly_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "anomaly_benchmark_results.json"

SEEDS = {"DEV": 2026, "TEST": 2027}
LENGTHS = (24, 36, 48)
SHAPES = ("FLAT", "TREND", "SEASONAL", "TREND_SEASONAL")
NOISES = (0.03, 0.08, 0.15)
MAGNITUDES = (3.0, 4.0, 6.0)
REPS = 4
PRED_REPS = 3
HORIZON = 3
PERIOD = 12
SEASONAL_AMPLITUDE = 0.25
TREND_PER_PERIOD = 0.015

DETECTORS = {
    "STATIC": dict(static_baseline=True),
    "IQR": dict(method="IQR"),
    "ZSCORE": dict(method="ZSCORE"),
    "COMBINED": dict(method="COMBINED"),
}


def clean_signal(shape: str, level: float, n: int, phase: int) -> list:
    out = []
    for t in range(n):
        v = level
        if "TREND" in shape:
            v += level * TREND_PER_PERIOD * t
        if "SEASONAL" in shape:
            v += level * SEASONAL_AMPLITUDE * math.sin(2 * math.pi * (t + phase) / PERIOD)
        out.append(v)
    return out


def historical_case(rng: random.Random, n: int, shape: str, noise: float) -> dict:
    level = rng.uniform(5_000, 50_000)
    sigma = level * noise
    signal = clean_signal(shape, level, n, rng.randrange(PERIOD))
    values = [s + rng.gauss(0, sigma) for s in signal]
    n_anom = rng.choice((0, 1, 2, 3))
    truth = {}
    candidates = list(range(1, n - 1))
    rng.shuffle(candidates)
    for i in candidates:
        if len(truth) == n_anom:
            break
        if any(abs(i - j) < 2 for j in truth):
            continue
        magnitude = rng.choice(MAGNITUDES)
        values[i] += rng.choice((-1, 1)) * magnitude * sigma
        truth[i] = magnitude
    return {"n": n, "shape": shape, "noise": noise, "values": values, "truth": truth}


def predictive_case(rng: random.Random, n: int, shape: str, noise: float, scenario: str) -> dict:
    level = rng.uniform(5_000, 50_000)
    sigma = level * noise
    signal = clean_signal(shape, level, n + HORIZON, rng.randrange(PERIOD))
    values = [s + rng.gauss(0, sigma) for s in signal]
    jump = rng.choice((-1, 1)) * rng.choice((4.0, 6.0)) * sigma
    future_truth = set()
    if scenario == "SHIFT":
        start = n - rng.randint(1, 4)
        for t in range(start, n + HORIZON):
            values[t] += jump
        future_truth = set(range(1, HORIZON + 1))
    elif scenario == "SPIKE_LAST":
        values[n - 1] += jump
    return {"n": n, "shape": shape, "noise": noise, "scenario": scenario,
            "history": values[:n], "future": values[n:], "future_truth": future_truth}


def forecast_for(history: list) -> object:
    n = len(history)
    readiness = prediction.ReadinessReport(is_ready=True, granularity="MONTH", n_points=n)
    selection = prediction.select_model(SimpleNamespace(primary_intent="ANOMALY_DETECTION"),
                                        readiness, history)
    proj = prediction.project_series(history, selection.model, HORIZON, 0.95, PERIOD)
    return prediction.ForecastResult(
        generated=True, model=proj["model"], historical_values=history,
        points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}", predicted=p,
                                         lower_bound=lo, upper_bound=hi)
                for h, (p, lo, hi) in enumerate(zip(proj["forecasts"], proj["lower"],
                                                    proj["upper"]))])


def _counts() -> dict:
    return {"tp": 0, "fp": 0, "fn": 0, "tn": 0}


def _add(c: dict, flagged: set, gold: set, universe) -> None:
    for i in universe:
        if i in flagged and i in gold:
            c["tp"] += 1
        elif i in flagged:
            c["fp"] += 1
        elif i in gold:
            c["fn"] += 1
        else:
            c["tn"] += 1


def metrics(c: dict) -> dict:
    p = c["tp"] / (c["tp"] + c["fp"]) if c["tp"] + c["fp"] else None
    r = c["tp"] / (c["tp"] + c["fn"]) if c["tp"] + c["fn"] else None
    f1 = 2 * p * r / (p + r) if p and r else 0.0
    fpr = c["fp"] / (c["fp"] + c["tn"]) if c["fp"] + c["tn"] else None
    return {"precision": p, "recall": r, "f1": f1, "false_positive_rate": fpr, **c}


def run_historical(rng: random.Random) -> dict:
    cases = [historical_case(rng, n, shape, noise)
             for n in LENGTHS for shape in SHAPES for noise in NOISES for _ in range(REPS)]
    out = {}
    for name, kwargs in DETECTORS.items():
        total = _counts()
        by_shape = {s: _counts() for s in SHAPES}
        by_noise = {str(z): _counts() for z in NOISES}
        hits_by_mag = {m: [0, 0] for m in MAGNITUDES}
        clean_series = clean_alarmed = 0
        for case in cases:
            report = anomaly_mod.detect_anomalies(case["values"], **kwargs)
            flagged = {a.index for a in report.historical_anomalies}
            gold = set(case["truth"])
            universe = range(case["n"])
            _add(total, flagged, gold, universe)
            _add(by_shape[case["shape"]], flagged, gold, universe)
            _add(by_noise[str(case["noise"])], flagged, gold, universe)
            for i, m in case["truth"].items():
                hits_by_mag[m][1] += 1
                hits_by_mag[m][0] += i in flagged
            if not gold:
                clean_series += 1
                clean_alarmed += bool(flagged)
        out[name] = {
            "overall": metrics(total),
            "by_shape": {s: metrics(c) for s, c in by_shape.items()},
            "by_noise": {z: metrics(c) for z, c in by_noise.items()},
            "recall_by_magnitude": {f"{m:g}sigma": h / t if t else None
                                    for m, (h, t) in hits_by_mag.items()},
            "clean_series": clean_series,
            "clean_series_with_false_alarm": clean_alarmed,
        }
    out["_series"] = len(cases)
    out["_injected"] = sum(len(c["truth"]) for c in cases)
    return out


def run_predictive(rng: random.Random) -> dict:
    cases = [predictive_case(rng, n, shape, noise, scenario)
             for n in LENGTHS for shape in SHAPES for noise in NOISES
             for scenario in ("NORMAL", "SHIFT", "SPIKE_LAST") for _ in range(PRED_REPS)]
    for case in cases:
        case["forecast"] = forecast_for(case["history"])
    out = {}
    for name, kwargs in DETECTORS.items():
        total = _counts()
        by_scenario = {s: _counts() for s in ("NORMAL", "SHIFT", "SPIKE_LAST")}
        by_shape = {s: _counts() for s in SHAPES}
        series_alarmed = {s: 0 for s in by_scenario}
        for case in cases:
            report = anomaly_mod.detect_anomalies(case["history"], forecast=case["forecast"],
                                                  **kwargs)
            flagged = {w.index for w in report.predictive_warnings}
            universe = range(1, HORIZON + 1)
            _add(total, flagged, case["future_truth"], universe)
            _add(by_scenario[case["scenario"]], flagged, case["future_truth"], universe)
            _add(by_shape[case["shape"]], flagged, case["future_truth"], universe)
            series_alarmed[case["scenario"]] += bool(flagged)
        per = len(cases) // 3
        out[name] = {
            "overall": metrics(total),
            "by_scenario": {s: metrics(c) for s, c in by_scenario.items()},
            "by_shape": {s: metrics(c) for s, c in by_shape.items()},
            "series_with_any_warning": {s: v / per for s, v in series_alarmed.items()},
        }
    out["_series"] = len(cases)
    out["_models"] = {}
    for case in cases:
        out["_models"][case["forecast"].model] = out["_models"].get(case["forecast"].model, 0) + 1
    return out


def _f(v, pct=False):
    if v is None:
        return "-"
    return f"{100 * v:.1f}%" if pct else f"{v:.3f}"


def section(md: list, split: str, hist: dict, pred: dict) -> None:
    md += [f"## {split}", "",
           f"### Historical anomalies ({hist['_series']} series, {hist['_injected']} injected "
           "point anomalies)", "",
           "| Detector | Precision | Recall | F1 | FPR | Clean series with a false alarm |",
           "|---|---|---|---|---|---|"]
    for name in DETECTORS:
        m = hist[name]["overall"]
        md.append(f"| {name} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | "
                  f"{_f(m['false_positive_rate'], True)} | "
                  f"{hist[name]['clean_series_with_false_alarm']}/{hist[name]['clean_series']} |")
    md += ["", "Recall by injected magnitude:", "",
           "| Detector | " + " | ".join(f"{m:g} sigma" for m in MAGNITUDES) + " |",
           "|---|" + "---|" * len(MAGNITUDES)]
    for name in DETECTORS:
        r = hist[name]["recall_by_magnitude"]
        md.append(f"| {name} | " + " | ".join(_f(r[f'{m:g}sigma'], True) for m in MAGNITUDES) + " |")
    md += ["", "F1 by shape (precision / recall):", "",
           "| Detector | " + " | ".join(SHAPES) + " |", "|---|" + "---|" * len(SHAPES)]
    for name in DETECTORS:
        cells = []
        for s in SHAPES:
            m = hist[name]["by_shape"][s]
            cells.append(f"{_f(m['f1'])} ({_f(m['precision'])} / {_f(m['recall'])})")
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    md += ["", f"### Predictive warnings ({pred['_series']} series, horizon {HORIZON}; "
           f"forecast models used: {pred['_models']})", "",
           "| Detector | Precision | Recall | F1 | FPR | Series warned: NORMAL / SHIFT / SPIKE_LAST |",
           "|---|---|---|---|---|---|"]
    for name in DETECTORS:
        m = pred[name]["overall"]
        w = pred[name]["series_with_any_warning"]
        md.append(f"| {name} | {_f(m['precision'])} | {_f(m['recall'])} | {_f(m['f1'])} | "
                  f"{_f(m['false_positive_rate'], True)} | {_f(w['NORMAL'], True)} / "
                  f"{_f(w['SHIFT'], True)} / {_f(w['SPIKE_LAST'], True)} |")
    md += ["", "Predictive F1 by shape (precision / recall):", "",
           "| Detector | " + " | ".join(SHAPES) + " |", "|---|" + "---|" * len(SHAPES)]
    for name in DETECTORS:
        cells = []
        for s in SHAPES:
            m = pred[name]["by_shape"][s]
            cells.append(f"{_f(m['f1'])} ({_f(m['precision'])} / {_f(m['recall'])})")
        md.append(f"| {name} | " + " | ".join(cells) + " |")
    md.append("")


def main() -> int:
    results = {}
    md = ["# Anomaly benchmark (Stage 3)", "",
          "Generated by `evaluate_anomalies.py`. Do not edit by hand. Design choices are "
          "made on DEV; TEST is a disjoint seed reported with the frozen code.", ""]
    for split, seed in SEEDS.items():
        rng = random.Random(seed)
        hist = run_historical(rng)
        pred = run_predictive(rng)
        results[split] = {"seed": seed, "historical": hist, "predictive": pred}
        section(md, split, hist, pred)
    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
