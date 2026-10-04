"""
Benchmark for the Stage 1 strategies (strategies.py), against naive answers.

Each strategy answers a different predictive question, so each is scored on
its own question, on synthetic data where the truth is known, and compared to
the answer a user would get by assuming "nothing changes":

  CATEGORY_TRAJECTORY  N_SETS sets of K categories x N_PERIODS months. The last
                       HORIZON periods are held out. Scored: is the projected
                       leader for the next period (and for the end of the
                       horizon) the actual leader? Baseline: today's leader
                       stays the leader. Reported separately for the sets
                       where the leader actually changes - there the baseline
                       is wrong by construction, and forecasting must earn it.
  SHARE_SHIFT          Same sets: mean absolute error of the projected shares
                       for the next period, in percentage points. Baseline:
                       today's shares persist.
  ANOMALY_PERSISTENCE  N_ANOMALY single series per event type, each ending in
                       an event: a one-off SPIKE (future returns to normal) or a
                       level SHIFT (future stays shifted). Truth = whether the
                       actual next HORIZON values breach the same adaptive
                       threshold in the same direction. Scored only where the
                       event was detected as a recent anomaly. Baselines:
                       "always persists" and "always recovers".

Everything runs through the production code: result_profiler builds the
profile (including layout inference), strategies.py makes the predictions,
anomaly.py supplies the thresholds.

Run:  python evaluate_strategies.py
"""

import json
import math
import os
import random
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("LLM_PROVIDER", "none")

import anomaly as anomaly_mod  # noqa: E402
import prediction  # noqa: E402
import profiler  # noqa: E402
import strategies  # noqa: E402
from result_profiler import profile_results  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
REPORT_MD = HERE / "data_and_reports" / "strategy_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "strategy_benchmark_results.json"

SEED = 2026
N_SETS = 200
K = 4
N_PERIODS = 24
HORIZON = 3
N_ANOMALY = 100
ANALYSIS = SimpleNamespace(primary_intent="COMPARISON")


def _month(t: int) -> str:
    return f"{2024 + t // 12:04d}-{t % 12 + 1:02d}-01"


def grouped_set(rng: random.Random) -> dict:
    """K category series with random level, trend and noise; trends often cross."""
    series = {}
    for k in range(K):
        level = rng.uniform(10_000, 50_000)
        trend = level * rng.uniform(-0.02, 0.03)
        noise = rng.uniform(0.02, 0.12)
        series[f"C{k + 1}"] = [max(level * 0.05, level + trend * t + rng.gauss(0, level * noise))
                               for t in range(N_PERIODS)]
    return series


def score_trajectory_and_shares(rng: random.Random) -> dict:
    records = []
    for _ in range(N_SETS):
        series = grouped_set(rng)
        train_n = N_PERIODS - HORIZON
        rows = [{"month": _month(t), "category": c, "revenue": round(v[t], 2)}
                for c, v in series.items() for t in range(train_n)]
        profile = profile_results(rows)
        assert profile.layout == "GROUPED", profile.layout
        result = strategies.category_trajectory(profile, rows, ANALYSIS, HORIZON)
        if not result.executed:
            continue
        d = result.details
        actual_next = {c: v[train_n] for c, v in series.items()}
        actual_end = {c: v[train_n + HORIZON - 1] for c, v in series.items()}
        last = {c: v[train_n - 1] for c, v in series.items()}
        true_next_leader = max(actual_next, key=actual_next.get)
        true_end_leader = max(actual_end, key=actual_end.get)
        naive_leader = max(last, key=last.get)

        # Shares for the next period.
        total_next = sum(actual_next.values())
        total_last = sum(last.values())
        pred = {c["category"]: c["points"][0]["predicted"] for c in d["categories"]}
        total_pred = sum(pred.values())
        share_err = [abs(100 * pred[c] / total_pred - 100 * actual_next[c] / total_next)
                     for c in series]
        naive_share_err = [abs(100 * last[c] / total_last - 100 * actual_next[c] / total_next)
                           for c in series]
        records.append({
            "leader_changes": true_next_leader != naive_leader,
            "next_hit": d["projected_leader"]["category"] == true_next_leader,
            "end_hit": d["projected_leader_end"]["category"] == true_end_leader,
            "naive_next_hit": naive_leader == true_next_leader,
            "naive_end_hit": naive_leader == true_end_leader,
            "clear_lead": d["clear_lead"],
            "share_mae": statistics.mean(share_err),
            "naive_share_mae": statistics.mean(naive_share_err),
        })

    def rate(rs, key):
        return sum(r[key] for r in rs) / len(rs) if rs else None

    changed = [r for r in records if r["leader_changes"]]
    clear = [r for r in records if r["clear_lead"]]
    share_wins = sum(r["share_mae"] < r["naive_share_mae"] for r in records)
    p_share = None
    try:
        from scipy.stats import wilcoxon

        p_share = float(wilcoxon([r["share_mae"] - r["naive_share_mae"] for r in records]).pvalue)
    except ImportError:  # pragma: no cover
        pass
    return {
        "sets": len(records),
        "leader_next_accuracy": rate(records, "next_hit"),
        "leader_next_naive": rate(records, "naive_next_hit"),
        "leader_end_accuracy": rate(records, "end_hit"),
        "leader_end_naive": rate(records, "naive_end_hit"),
        "sets_where_leader_changes": len(changed),
        "leader_next_accuracy_when_changes": rate(changed, "next_hit"),
        "clear_lead_sets": len(clear),
        "leader_next_accuracy_when_clear": rate(clear, "next_hit"),
        "share_mae_pp": statistics.mean(r["share_mae"] for r in records),
        "share_mae_naive_pp": statistics.mean(r["naive_share_mae"] for r in records),
        "share_better_than_naive_in": share_wins,
        "share_wilcoxon_p": p_share,
    }


def anomaly_case(rng: random.Random, kind: str) -> dict:
    """A trending series whose last observed period carries a spike or a shift."""
    n = N_PERIODS
    level, trend, noise = rng.uniform(5_000, 30_000), rng.uniform(-0.005, 0.02), 0.04
    sigma = level * noise
    clean = [level * (1 + trend * t) for t in range(n + HORIZON)]
    values = [c + rng.gauss(0, sigma) for c in clean]
    jump = rng.choice([-1, 1]) * rng.uniform(5, 8) * sigma
    if kind == "SPIKE":
        values[n - 1] += jump                       # one period only
    else:
        for t in range(n - 2, n + HORIZON):         # last 2 observed + the future
            values[t] += jump
    history, future = values[:n], values[n:]

    readiness = prediction.ReadinessReport(is_ready=True, granularity="MONTH", n_points=n)
    selection = prediction.select_model(SimpleNamespace(primary_intent="ANOMALY_DETECTION"),
                                        readiness, history)
    proj = prediction.project_series(history, selection.model, HORIZON, 0.95, 12)
    forecast = prediction.ForecastResult(
        generated=True, model=proj["model"], historical_values=history,
        points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}", predicted=p,
                                         lower_bound=lo, upper_bound=hi)
                for h, (p, lo, hi) in enumerate(zip(proj["forecasts"], proj["lower"],
                                                    proj["upper"]))])
    report = anomaly_mod.detect_anomalies(history, [f"t{i}" for i in range(n)], forecast=forecast)
    result = strategies.anomaly_persistence(forecast, report)
    verdict = result.details.get("verdict")
    if verdict in (None, "NO_RECENT_ANOMALY"):
        return {"kind": kind, "detected": False}

    direction = result.details["anomaly"]["direction"]
    # Truth: do the ACTUAL future values breach the same band, same side?
    actual = anomaly_mod.detect_anomalies(
        history, forecast=prediction.ForecastResult(
            generated=True, points=[prediction.ForecastPoint(period_index=h + 1, label=f"t+{h + 1}",
                                                             predicted=v)
                                    for h, v in enumerate(future)]))
    truth_persists = any(w.direction == direction for w in actual.predictive_warnings)
    predicted_persists = verdict in ("PERSISTING", "WORSENING")
    return {"kind": kind, "detected": True, "verdict": verdict, "model": proj["model"],
            "truth_persists": truth_persists, "hit": predicted_persists == truth_persists}


def score_anomaly_persistence(rng: random.Random) -> dict:
    cases = [anomaly_case(rng, kind) for kind in ("SPIKE", "SHIFT") for _ in range(N_ANOMALY)]
    detected = [c for c in cases if c["detected"]]
    out = {"cases": len(cases), "detected_as_recent_anomaly": len(detected)}
    if not detected:
        return out
    persists = [c for c in detected if c["truth_persists"]]
    out.update({
        "accuracy": sum(c["hit"] for c in detected) / len(detected),
        "baseline_always_persists": len(persists) / len(detected),
        "baseline_always_recovers": 1 - len(persists) / len(detected),
        "truth_persisting_cases": len(persists),
        "by_kind": {},
        "models_used": {},
    })
    for kind in ("SPIKE", "SHIFT"):
        ks = [c for c in detected if c["kind"] == kind]
        if ks:
            out["by_kind"][kind] = {
                "detected": len(ks),
                "accuracy": sum(c["hit"] for c in ks) / len(ks),
                "verdicts": {v: sum(c["verdict"] == v for c in ks)
                             for v in ("RECOVERING", "PERSISTING", "WORSENING")},
                "truth_persists": sum(c["truth_persists"] for c in ks),
            }
    for c in detected:
        out["models_used"][c["model"]] = out["models_used"].get(c["model"], 0) + 1
    return out


def _p(v):
    return "-" if v is None else f"{100 * v:.1f}%"


def main() -> int:
    rng = random.Random(SEED)
    traj = score_trajectory_and_shares(rng)
    anom = score_anomaly_persistence(rng)
    results = {"seed": SEED, "category_trajectory_and_shares": traj, "anomaly_persistence": anom}

    md = ["# Strategy benchmark (Stage 1 execution)", "",
          "Generated by `evaluate_strategies.py`. Do not edit by hand.", "",
          f"## Category trajectory ({traj['sets']} sets of {K} categories, {N_PERIODS - HORIZON} "
          f"months of history, next {HORIZON} months held out)", "",
          "| Question | Strategy | Naive (current leader stays) |", "|---|---|---|",
          f"| Leader next period | {_p(traj['leader_next_accuracy'])} | {_p(traj['leader_next_naive'])} |",
          f"| Leader at end of horizon | {_p(traj['leader_end_accuracy'])} | {_p(traj['leader_end_naive'])} |",
          f"| Leader next period, sets where it changes ({traj['sets_where_leader_changes']}) | "
          f"{_p(traj['leader_next_accuracy_when_changes'])} | 0.0% |",
          f"| Leader next period, sets the strategy calls a clear lead ({traj['clear_lead_sets']}) | "
          f"{_p(traj['leader_next_accuracy_when_clear'])} | - |", "",
          "## Share shift (same sets, next period)", "",
          f"- Mean absolute share error: **{traj['share_mae_pp']:.2f} pp** "
          f"vs naive {traj['share_mae_naive_pp']:.2f} pp; better than naive in "
          f"{traj['share_better_than_naive_in']}/{traj['sets']} sets "
          f"(Wilcoxon p = {traj['share_wilcoxon_p'] if traj['share_wilcoxon_p'] is None else format(traj['share_wilcoxon_p'], '.4f')})",
          "", f"## Anomaly persistence ({anom['cases']} series, "
          f"{anom['detected_as_recent_anomaly']} with the event detected as a recent anomaly)", ""]
    if anom.get("accuracy") is not None:
        md += [f"- Verdict accuracy: **{_p(anom['accuracy'])}** vs always-persists "
               f"{_p(anom['baseline_always_persists'])}, always-recovers "
               f"{_p(anom['baseline_always_recovers'])}",
               f"- Models used: {anom['models_used']}", "",
               "| Event | Detected | Accuracy | Verdicts | Truth: persists |", "|---|---|---|---|---|"]
        for kind, k in anom["by_kind"].items():
            md.append(f"| {kind} | {k['detected']} | {_p(k['accuracy'])} | {k['verdicts']} | "
                      f"{k['truth_persists']} |")
    text = "\n".join(md) + "\n"
    print(text)
    REPORT_MD.write_text(text, encoding="utf-8")
    REPORT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
