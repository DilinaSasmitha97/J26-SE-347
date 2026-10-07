"""
Stage 8 - candidate improvements to the forecasting layer, on DEVELOPMENT data only.

Four candidates were proposed after Stage 2 (see stage2_technical_details.md,
section 14). Each is measured here against the current behaviour, on data the
design is allowed to see, and adopted only if it meets the rule fixed below
BEFORE the run. The held-out samples (M4_TEST, M4_TEST_LARGE) are not read.

  E1 guard_sarima      SARIMA must also beat naive / seasonal naive on the
                       series' own history (it was exempt for speed)
  E2 fitted smoothing  damped Holt with estimated constants from 48 points
                       (measured on the 72-month development series, where it
                       can apply; on 36-month series it never does)
  E3 empirical bands   band half-width from the 95% quantile of the absolute
                       residuals instead of 1.96 x their standard deviation
  E4 conflict rule     also refuse when ADF/KPSS conflict and the in-history
                       error exceeds a second, lower limit

Adoption rules (fixed before running):
  E1, E2  adopt if the guarded selector's mean MASE improves on the development
          group the candidate applies to, and median MASE does not get worse.
  E3      adopt if 95% coverage moves closer to 95% on both SYNTHETIC and
          M4_DEV, without the mean scaled width growing by more than 10%.
  E4      adopt the limit with the best F1 on development windows among those
          whose refusals are right >= 80% of the time (the Stage 2 criterion),
          if that F1 beats the current gate's.

Data: SYNTHETIC (66 series), M4_DEV (100 x 36 months), M4_DEV_LONG (the same
100 series, 72 months). Protocol as evaluate_forecasting.py: 4 origins, 3
periods apart, horizon 3.

Run:   python evaluate_stage8_candidates.py
Writes data_and_reports/stage8_candidates.md and _results.json.
"""

import json
import os
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "none")

import evaluate_forecasting as ef  # noqa: E402

HERE = Path(__file__).resolve().parent
M4_DEV_LONG = HERE / "benchmark_data" / "m4_monthly_dev_long72.csv"
REPORT_MD = HERE / "data_and_reports" / "stage8_candidates.md"
REPORT_JSON = HERE / "data_and_reports" / "stage8_candidates_results.json"

BASE = {"guard_sarima": False, "fitted_min": 0, "band": "normal"}
CONFIGS = {
    "BASE": BASE,
    "E1_GUARD_SARIMA": {**BASE, "guard_sarima": True},
    "E2_FITTED_SMOOTHING": {**BASE, "fitted_min": 48},
    "E3_EMPIRICAL_BANDS": {**BASE, "band": "empirical"},
    # Added after the first run: the adopted combination, checked together on
    # development data before the held-out run. E1 is included although it
    # missed its pre-set rule by 0.001 median MASE on 36-month series, because
    # the first run showed SARIMA failing catastrophically on 72-month series
    # (MASE 57 on M36475); see stage8_completion_report.md.
    "ADOPTED_E1_E2": {**BASE, "guard_sarima": True, "fitted_min": 48},
}
CONFLICT_GRID = [round(0.02 * i, 2) for i in range(2, 10)]   # 0.04 .. 0.18
WIDTH_GROWTH_LIMIT = 1.10


def _apply(config: dict):
    import prediction

    prediction.GUARD_SARIMA = config["guard_sarima"]
    prediction.FITTED_SMOOTHING_MIN_POINTS = config["fitted_min"]
    prediction.BAND_METHOD = config["band"]
    prediction.CLIP_NON_NEGATIVE = True
    return prediction


def run_series(args) -> list:
    """All windows of one series under one configuration (worker process)."""
    series, name = args
    prediction = _apply(CONFIGS[name])
    import profiler

    profiler.VERBOSE = False
    values = series["values"]
    n = len(values)
    out = []
    for k in range(ef.ORIGINS, 0, -1):
        origin = n - ef.HORIZON - ef.ORIGIN_STEP * (k - 1)
        train, test = values[:origin], values[origin:origin + ef.HORIZON]
        selection = prediction.select_model(ef._ANALYSIS, ef._ready(len(train)), train, guard=True)
        proj = prediction.project_series(train, selection.model, ef.HORIZON, ef.CONFIDENCE, ef.PERIOD)
        scale = ef.naive_scale(train)
        window = {
            "series": series["id"], "group": series["group"], "origin": origin,
            "model": proj["model"],
            "scaled_errors": [abs(a - f) / scale for a, f in zip(test, proj["forecasts"])],
            "smape": [ef.smape(a, f) for a, f in zip(test, proj["forecasts"])],
            "covered": [lo <= a <= hi for a, lo, hi in zip(test, proj["lower"], proj["upper"])],
            "scaled_width": [(hi - lo) / scale for lo, hi in zip(proj["lower"], proj["upper"])],
        }
        if name == "BASE":
            info = prediction.forecastability(train, ef.PERIOD)
            window["expected_error"] = info.get("expected_relative_error")
            window["stationarity"] = prediction.stationarity_evidence(train).get(
                "verdict", "NOT_ASSESSED")
        out.append(window)
    return out


def per_series_mase(windows: list) -> dict:
    by = {}
    for w in windows:
        by.setdefault(w["series"], []).extend(w["scaled_errors"])
    return {s: statistics.mean(v) for s, v in by.items()}


def summary(windows: list) -> dict:
    mase = per_series_mase(windows)
    return {
        "series": len(mase), "windows": len(windows),
        "mase_mean": statistics.mean(mase.values()),
        "mase_median": statistics.median(mase.values()),
        "smape_mean": statistics.mean(s for w in windows for s in w["smape"]),
        "coverage95": statistics.mean(c for w in windows for c in w["covered"]),
        "scaled_width_mean": statistics.mean(x for w in windows for x in w["scaled_width"]),
        "models": {m: sum(w["model"] == m for w in windows)
                   for m in sorted({w["model"] for w in windows})},
    }


def paired(a: list, b: list) -> dict:
    ma, mb = per_series_mase(a), per_series_mase(b)
    diffs = [ma[s] - mb[s] for s in ma if s in mb]
    out = {"a_better_in": sum(d < 0 for d in diffs), "series": len(diffs), "p_value": None}
    try:
        from scipy.stats import wilcoxon

        if any(d != 0 for d in diffs):
            out["p_value"] = float(wilcoxon(diffs).pvalue)
    except ImportError:  # pragma: no cover
        pass
    return out


def gate(windows: list, tau: float, tau_conflict=None) -> dict:
    rows = []
    for w in windows:
        err = w["expected_error"]
        refused = err is not None and (err > tau or (
            tau_conflict is not None and w["stationarity"] == "CONFLICT" and err > tau_conflict))
        s = statistics.mean(w["smape"])
        rows.append((refused, s > ef.UNRELIABLE_SMAPE, s))
    refused = [r for r in rows if r[0]]
    unreliable = [r for r in rows if r[1]]
    tp = sum(1 for r in refused if r[1])
    precision = tp / len(refused) if refused else None
    recall = tp / len(unreliable) if unreliable else None
    f1 = 2 * precision * recall / (precision + recall) if precision and recall else 0.0
    accepted = [r for r in rows if not r[0]]
    return {"tau_conflict": tau_conflict, "refusal_rate": len(refused) / len(rows),
            "refusals": len(refused), "precision": precision, "recall": recall, "f1": f1,
            "smape_accepted": statistics.mean(r[2] for r in accepted) if accepted else None}


def _f(v, spec=".3f"):
    return "-" if v is None else format(v, spec)


def main() -> int:
    started = time.perf_counter()
    data = {
        "SYNTHETIC": ef.synthetic_series(False),
        "M4_DEV": ef.m4_series(ef.M4_DEV, "M4_DEV"),
        "M4_DEV_LONG": ef.m4_series(M4_DEV_LONG, "M4_DEV_LONG"),
    }
    jobs = [(s, name) for name in CONFIGS for group in data.values() for s in group]
    print(f"{len(jobs)} series-configurations on {os.cpu_count()} CPUs...", flush=True)
    windows = {name: {g: [] for g in data} for name in CONFIGS}
    with ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 2)) as pool:
        for (series, name), result in zip(jobs, pool.map(run_series, jobs, chunksize=4)):
            windows[name][series["group"]].extend(result)

    results = {"configs": CONFIGS, "groups": {g: len(s) for g, s in data.items()}, "summary": {},
               "paired_vs_base": {}, "decisions": {}}
    for name in CONFIGS:
        results["summary"][name] = {g: summary(ws) for g, ws in windows[name].items()}
        if name != "BASE":
            results["paired_vs_base"][name] = {
                g: paired(windows[name][g], windows["BASE"][g]) for g in data}

    s = results["summary"]
    dev36 = lambda name: windows[name]["SYNTHETIC"] + windows[name]["M4_DEV"]  # noqa: E731
    base36, e1_36 = summary(dev36("BASE")), summary(dev36("E1_GUARD_SARIMA"))
    results["decisions"]["E1_GUARD_SARIMA"] = {
        "applies_to": "SYNTHETIC + M4_DEV", "base": base36, "candidate": e1_36,
        "adopt": e1_36["mase_mean"] < base36["mase_mean"]
        and e1_36["mase_median"] <= base36["mase_median"],
    }
    b, c = s["BASE"]["M4_DEV_LONG"], s["E2_FITTED_SMOOTHING"]["M4_DEV_LONG"]
    results["decisions"]["E2_FITTED_SMOOTHING"] = {
        "applies_to": "M4_DEV_LONG", "base": b, "candidate": c,
        "adopt": c["mase_mean"] < b["mase_mean"] and c["mase_median"] <= b["mase_median"],
    }
    closer = all(abs(s["E3_EMPIRICAL_BANDS"][g]["coverage95"] - 0.95)
                 < abs(s["BASE"][g]["coverage95"] - 0.95) for g in ("SYNTHETIC", "M4_DEV"))
    narrow_enough = all(s["E3_EMPIRICAL_BANDS"][g]["scaled_width_mean"]
                        <= WIDTH_GROWTH_LIMIT * s["BASE"][g]["scaled_width_mean"]
                        for g in ("SYNTHETIC", "M4_DEV"))
    results["decisions"]["E3_EMPIRICAL_BANDS"] = {
        "applies_to": "SYNTHETIC and M4_DEV", "coverage_closer": closer,
        "width_within_limit": narrow_enough, "adopt": closer and narrow_enough,
    }
    gate_windows = dev36("BASE")
    current = gate(gate_windows, ef.prediction.MAX_EXPECTED_ERROR)
    sweep = [gate(gate_windows, ef.prediction.MAX_EXPECTED_ERROR, t) for t in CONFLICT_GRID]
    eligible = [r for r in sweep if (r["precision"] or 0) >= ef.MIN_GATE_PRECISION]
    best = max(eligible, key=lambda r: (r["f1"], -r["refusal_rate"])) if eligible else None
    results["decisions"]["E4_CONFLICT_RULE"] = {
        "applies_to": "SYNTHETIC + M4_DEV windows", "current_gate": current, "sweep": sweep,
        "best": best, "adopt": bool(best and best["f1"] > current["f1"]),
        "chosen_limit": best["tau_conflict"] if best and best["f1"] > current["f1"] else None,
    }
    results["runtime_seconds"] = round(time.perf_counter() - started, 1)

    md = ["# Stage 8 candidates: development data only", "",
          "Generated by `evaluate_stage8_candidates.py`. Do not edit by hand. Held-out "
          "samples were not read. Adoption rules were fixed before the run (see the script).", "",
          "| Config | Group | Mean MASE | Median MASE | sMAPE | 95% coverage | Scaled width | "
          "Better than BASE in (series) | Wilcoxon p |", "|---|---|---|---|---|---|---|---|---|"]
    for name in CONFIGS:
        for g in data:
            r = s[name][g]
            pv = results["paired_vs_base"].get(name, {}).get(g)
            better = f"{pv['a_better_in']}/{pv['series']}" if pv else "-"
            p_value = _f(pv["p_value"], ".4f") if pv else "-"
            md.append(f"| {name} | {g} | {_f(r['mase_mean'])} | {_f(r['mase_median'])} | "
                      f"{_f(r['smape_mean'], '.2f')} | {r['coverage95'] * 100:.1f}% | "
                      f"{_f(r['scaled_width_mean'], '.2f')} | {better} | {p_value} |")
    md += ["", "## Decisions", ""]
    d = results["decisions"]
    md.append(f"- **E1 guard SARIMA** (SYNTHETIC + M4_DEV): mean MASE "
              f"{_f(d['E1_GUARD_SARIMA']['base']['mase_mean'])} -> "
              f"{_f(d['E1_GUARD_SARIMA']['candidate']['mase_mean'])}, median "
              f"{_f(d['E1_GUARD_SARIMA']['base']['mase_median'])} -> "
              f"{_f(d['E1_GUARD_SARIMA']['candidate']['mase_median'])}: "
              f"**{'adopt' if d['E1_GUARD_SARIMA']['adopt'] else 'reject'}**")
    md.append(f"- **E2 fitted smoothing** (M4_DEV_LONG): mean MASE "
              f"{_f(d['E2_FITTED_SMOOTHING']['base']['mase_mean'])} -> "
              f"{_f(d['E2_FITTED_SMOOTHING']['candidate']['mase_mean'])}, median "
              f"{_f(d['E2_FITTED_SMOOTHING']['base']['mase_median'])} -> "
              f"{_f(d['E2_FITTED_SMOOTHING']['candidate']['mase_median'])}: "
              f"**{'adopt' if d['E2_FITTED_SMOOTHING']['adopt'] else 'reject'}**")
    md.append(f"- **E3 empirical bands**: coverage closer to 95% on both groups: "
              f"{d['E3_EMPIRICAL_BANDS']['coverage_closer']}; width within +10%: "
              f"{d['E3_EMPIRICAL_BANDS']['width_within_limit']}: "
              f"**{'adopt' if d['E3_EMPIRICAL_BANDS']['adopt'] else 'reject'}**")
    e4 = d["E4_CONFLICT_RULE"]
    md += [f"- **E4 conflict rule**: current gate F1 {_f(e4['current_gate']['f1'], '.3f')} "
           f"(precision {_f(e4['current_gate']['precision'], '.2f')}, recall "
           f"{_f(e4['current_gate']['recall'], '.2f')}); best eligible "
           f"{_f(e4['best']['f1'], '.3f') if e4['best'] else '-'}"
           f"{' at ' + str(e4['best']['tau_conflict']) if e4['best'] else ''}: "
           f"**{'adopt ' + str(e4['chosen_limit']) if e4['adopt'] else 'reject'}**", "",
           "| Conflict limit | Refusal rate | Refusals | Precision | Recall | F1 | sMAPE accepted |",
           "|---|---|---|---|---|---|---|",
           f"| none (current) | {e4['current_gate']['refusal_rate'] * 100:.1f}% | "
           f"{e4['current_gate']['refusals']} | {_f(e4['current_gate']['precision'], '.2f')} | "
           f"{_f(e4['current_gate']['recall'], '.2f')} | {_f(e4['current_gate']['f1'], '.3f')} | "
           f"{_f(e4['current_gate']['smape_accepted'], '.2f')} |"]
    for r in e4["sweep"]:
        md.append(f"| {r['tau_conflict']} | {r['refusal_rate'] * 100:.1f}% | {r['refusals']} | "
                  f"{_f(r['precision'], '.2f')} | {_f(r['recall'], '.2f')} | {_f(r['f1'], '.3f')} | "
                  f"{_f(r['smape_accepted'], '.2f')} |")
    md += ["", f"Runtime: {results['runtime_seconds']} s"]
    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
