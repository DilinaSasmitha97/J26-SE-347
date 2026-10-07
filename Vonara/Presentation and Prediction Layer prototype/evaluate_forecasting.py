"""
Forecasting benchmark for Prediction Stages 2-4 (rolling-origin, vs baselines).

The source of every forecasting claim. Protocol:

  Series     SYNTHETIC (development) - 66 series: a full factorial grid of
             length x noise x seasonality x trend (60) plus 6 near-constant
             series, all generated with known parameters (seeded).
             M4_DEV (development) - 100 monthly series sampled uniformly at
             random (seed 2026) from the 48,000 monthly series of the M4
             competition, truncated to their last 36 observations. It was the
             held-out test of the first Stage 2 run; once seen, it became
             development data, and design changes were checked against it.
             M4_TEST (held out) - 100 further monthly series (seed 2027) drawn
             from the 47,900 series NOT in M4_DEV, same truncation. Nothing was
             tuned on it; it is evaluated once with the frozen code.

  Origins    4 forecast origins per series, 3 periods apart, each forecasting
             3 periods ahead: the last 12 observations are each predicted once,
             and every forecast uses only data before its origin.

  Strategies 6 fixed models (NAIVE and SEASONAL_NAIVE are the benchmarks), the
             adaptive dual-signal selector, and the same selector with the
             benchmark guard. All forecasts come from prediction.project_series,
             the code path live requests use.

  Metrics    MASE (errors scaled by the in-sample one-step naive MAE of the
             training window, Hyndman & Koehler 2006) - comparable across
             series of any scale; sMAPE; relative RMSE vs NAIVE (geometric mean
             of per-series ratios); raw RMSE / MAE (scale-dependent); all of
             them also per forecast horizon; coverage of the 95% interval per
             horizon; results per data regime. Wilcoxon signed-rank tests on
             per-series MASE.

  Gate       For every (series, origin) the readiness Gate 3 is evaluated on the
             training window only. A forecast window counts as UNRELIABLE when
             its sMAPE exceeds UNRELIABLE_SMAPE. The threshold is chosen on the
             DEVELOPMENT windows (SYNTHETIC + M4_DEV): the best F1 at refusing
             unreliable windows among thresholds whose refusals are right at
             least MIN_GATE_PRECISION of the time. It is then applied unchanged
             to M4_TEST.

Run:   python evaluate_forecasting.py               (writes data_and_reports/, ~15 min)
       python evaluate_forecasting.py --skip-large  (without the 1,000-series group)
       python evaluate_forecasting.py --quick    (synthetic only, fewer series)
"""

import argparse
import csv
import json
import math
import os
import platform
import random
import statistics
import sys
import time
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("LLM_PROVIDER", "none")

import prediction  # noqa: E402
import profiler  # noqa: E402
import synthetic_data as sd  # noqa: E402
from schemas import Granularity  # noqa: E402

profiler.VERBOSE = False

HERE = Path(__file__).resolve().parent
M4_DEV = HERE / "benchmark_data" / "m4_monthly_sample.csv"
M4_TEST = HERE / "benchmark_data" / "m4_monthly_test_seed2027.csv"
M4_TEST_LARGE = HERE / "benchmark_data" / "m4_monthly_test_seed2028_n1000.csv"
REPORT_MD = HERE / "data_and_reports" / "forecast_benchmark.md"
REPORT_JSON = HERE / "data_and_reports" / "forecast_benchmark_results.json"

SEED = 2026
HORIZON = 3
ORIGINS = 4
ORIGIN_STEP = 3
CONFIDENCE = 0.95
PERIOD = 12
UNRELIABLE_SMAPE = 20.0          # % - a window this wrong should not be shown
MIN_GATE_PRECISION = 0.80        # a refusal must be right at least this often
TAU_GRID = [round(0.05 * i, 2) for i in range(1, 15)]  # 0.05 .. 0.70

FIXED = ["NAIVE", "SEASONAL_NAIVE", "WEIGHTED_MOVING_AVERAGE",
         "LINEAR_REGRESSION", "EXPONENTIAL_SMOOTHING", "SARIMA"]
# Stage 8: the standard M4 benchmarks, as comparisons only (never deployed).
# THETA: statsmodels ThetaModel (Assimakopoulos & Nikolopoulos 2000), the M3
# winner and an official M4 benchmark. AUTO_ETS: additive-error ETS with the
# trend / damping / seasonality chosen per window by AICc (Hyndman et al. 2002).
BASELINES = ["THETA", "AUTO_ETS"]
ADAPTIVE = "ADAPTIVE"
GUARDED = "ADAPTIVE_GUARDED"
STRATEGIES = FIXED + BASELINES + [ADAPTIVE, GUARDED]
DEPLOYED = GUARDED
GROUPS = ("SYNTHETIC", "M4_DEV", "M4_TEST", "M4_TEST_LARGE")


# ==========================================================================
# Datasets
# ==========================================================================


def _regimes(n: int, noise: float, seasonal: float, trend: str) -> list:
    """Data regimes a synthetic series belongs to (proposal 3.11)."""
    out = ["short (24)" if n <= 24 else "long (36)"]
    if noise <= 0.01:
        out.append("near-constant")
    elif noise >= 0.30:
        out.append("volatile (noise >= 30%)")
    elif noise <= 0.08:
        out.append("low noise (<= 8%)")
    else:
        out.append("medium noise (15%)")
    if seasonal:
        out.append("seasonal")
    if trend != "flat" and noise <= 0.08:
        out.append("trend-dominant")
    return out


def synthetic_series(quick: bool = False) -> list:
    """Factorial grid (2 x 5 x 2 x 3 = 60) plus 6 near-constant series."""
    rng = random.Random(SEED)
    lengths = [24, 36]
    noises = [0.03, 0.08, 0.15, 0.30, 0.50]
    seasonals = [0.0, 0.20]
    trends = [("flat", 0.0), ("up", 0.02), ("down", -0.012)]
    if quick:
        lengths, noises = [36], [0.03, 0.15, 0.50]
    out = []

    def make(n, noise, seasonal, trend_name, trend_frac, tag):
        level = round(math.exp(rng.uniform(math.log(1_000), math.log(80_000))), 2)
        rows, _ = sd.generate_timeseries(
            n_periods=n, level=level, trend=level * trend_frac,
            seasonal_amplitude=seasonal, noise_pct=noise, seed=rng.randint(1, 10**6))
        floor = level * 0.05
        out.append({
            "id": f"syn_n{n}_e{noise * 100:g}_s{int(seasonal * 100)}_{trend_name}{tag}",
            "group": "SYNTHETIC",
            "values": [max(r["amount"], floor) for r in rows],
            "regimes": _regimes(n, noise, seasonal, trend_name),
        })

    for n in lengths:
        for noise in noises:
            for seasonal in seasonals:
                for trend_name, trend_frac in trends:
                    make(n, noise, seasonal, trend_name, trend_frac, "")
    if not quick:
        for n in (24, 36):
            for k in range(3):
                make(n, 0.005, 0.0, "flat", 0.0, f"_c{k}")
    return out


def m4_series(path: Path, group: str) -> list:
    out = []
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append({
                "id": row["series_id"], "group": group,
                "values": [float(v) for v in row["values"].split()],
                "regimes": [f"M4 {row['category'] or 'Other'}"],
            })
    return out


# ==========================================================================
# Metrics
# ==========================================================================


def naive_scale(train: list) -> float:
    """In-sample one-step naive MAE: the MASE denominator."""
    diffs = [abs(b - a) for a, b in zip(train, train[1:])]
    scale = sum(diffs) / len(diffs) if diffs else 0.0
    return scale if scale > 0 else (abs(sum(train) / len(train)) * 0.01 or 1.0)


def smape(actual: float, forecast: float) -> float:
    denom = abs(actual) + abs(forecast)
    return 200.0 * abs(actual - forecast) / denom if denom else 0.0


# ==========================================================================
# Rolling-origin run
# ==========================================================================

_ANALYSIS = SimpleNamespace(primary_intent="TREND_ANALYSIS")


def _ready(n: int):
    return prediction.ReadinessReport(is_ready=True, verdict="READY", n_points=n,
                                      granularity=Granularity.MONTH.value)


def _clip(train, forecasts, lower, upper):
    """The deployed layer's non-negative rule, applied to the baselines too."""
    if prediction.CLIP_NON_NEGATIVE and min(train) >= 0:
        forecasts = [max(0.0, f) for f in forecasts]
        lower = [max(0.0, x) for x in lower]
        upper = [max(u, f) for u, f in zip(upper, forecasts)]
    return forecasts, lower, upper


def _baseline(train: list, strategy: str) -> dict:
    """THETA or AUTO_ETS with their own 95% intervals; naive if the fit fails."""
    import warnings

    import numpy as np

    y = np.asarray(train, dtype=float)
    n = len(y)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if strategy == "THETA":
                from statsmodels.tsa.forecasting.theta import ThetaModel

                res = ThetaModel(y, period=PERIOD, deseasonalize=n >= 2 * PERIOD).fit()
                mean = [float(v) for v in res.forecast(HORIZON)]
                pi = res.prediction_intervals(HORIZON, alpha=1 - CONFIDENCE)
                lower, upper = [float(v) for v in pi["lower"]], [float(v) for v in pi["upper"]]
            else:
                import pandas as pd
                from statsmodels.tsa.exponential_smoothing.ets import ETSModel

                # ETS prediction intervals need an indexed (pandas) series.
                y = pd.Series(y)
                best = None
                for trend in (None, "add"):
                    for damped in ((False,) if trend is None else (False, True)):
                        for seasonal in ((None, "add") if n >= 2 * PERIOD + 2 else (None,)):
                            try:
                                fit = ETSModel(y, error="add", trend=trend, damped_trend=damped,
                                               seasonal=seasonal,
                                               seasonal_periods=PERIOD if seasonal else None
                                               ).fit(disp=False)
                            except Exception:  # noqa: BLE001
                                continue
                            if np.isfinite(fit.aicc) and (best is None or fit.aicc < best.aicc):
                                best = fit
                if best is None:
                    raise ValueError("no ETS candidate fitted")
                frame = best.get_prediction(start=n, end=n + HORIZON - 1).summary_frame(
                    alpha=1 - CONFIDENCE)
                mean = [float(v) for v in frame["mean"]]
                lower, upper = [float(v) for v in frame["pi_lower"]], [float(v) for v in frame["pi_upper"]]
        model = strategy
    except Exception:  # noqa: BLE001
        proj = prediction.project_series(train, "NAIVE", HORIZON, CONFIDENCE, PERIOD)
        mean, lower, upper, model = proj["forecasts"], proj["lower"], proj["upper"], "NAIVE"
    mean, lower, upper = _clip(train, mean, lower, upper)
    return {"model": model, "guard_override": False, "forecasts": mean,
            "lower": lower, "upper": upper}


def forecast_window(train: list, strategy: str) -> dict:
    """One forecast from one origin with one strategy."""
    if strategy in BASELINES:
        return _baseline(train, strategy)
    if strategy in (ADAPTIVE, GUARDED):
        selection = prediction.select_model(_ANALYSIS, _ready(len(train)), train,
                                            guard=(strategy == GUARDED))
        model = selection.model
        overridden = bool(selection.signals.get("guard", {}).get("overridden"))
    else:
        model, overridden = strategy, False
    projection = prediction.project_series(train, model, HORIZON, CONFIDENCE, PERIOD)
    return {"model": projection["model"], "guard_override": overridden,
            "forecasts": projection["forecasts"], "lower": projection["lower"],
            "upper": projection["upper"]}


def run_series(series: dict) -> list:
    values = series["values"]
    n = len(values)
    windows = []
    for k in range(ORIGINS, 0, -1):
        origin = n - HORIZON - ORIGIN_STEP * (k - 1)
        train, test = values[:origin], values[origin:origin + HORIZON]
        test_info = prediction.forecastability(train, PERIOD)
        window = {
            "series": series["id"], "group": series["group"], "regimes": series["regimes"],
            "origin": origin, "actual": test, "scale": naive_scale(train),
            "gate_legacy_pass": prediction.legacy_signal_adequate(train),
            "gate_expected_error": test_info.get("expected_relative_error"),
            "stationarity": prediction.stationarity_evidence(train).get("verdict", "NOT_ASSESSED"),
            "strategies": {},
        }
        for strategy in STRATEGIES:
            fc = forecast_window(train, strategy)
            errs = [a - f for a, f in zip(test, fc["forecasts"])]
            fc.update({
                "abs_errors": [abs(e) for e in errs],
                "sq_errors": [e * e for e in errs],
                "smape": [smape(a, f) for a, f in zip(test, fc["forecasts"])],
                "covered": [lo <= a <= hi for a, lo, hi in zip(test, fc["lower"], fc["upper"])],
            })
            window["strategies"][strategy] = fc
        windows.append(window)
    return windows


# ==========================================================================
# Aggregation
# ==========================================================================


def per_series(windows: list, strategy: str, horizon: int = None) -> dict:
    """Series-level metrics for one strategy, pooled over origins (and horizons)."""
    hs = range(HORIZON) if horizon is None else [horizon]
    by_series = {}
    for w in windows:
        fc = w["strategies"][strategy]
        s = by_series.setdefault(w["series"], {"scaled": [], "abs": [], "sq": [], "smape": []})
        for h in hs:
            s["scaled"].append(fc["abs_errors"][h] / w["scale"])
            s["abs"].append(fc["abs_errors"][h])
            s["sq"].append(fc["sq_errors"][h])
            s["smape"].append(fc["smape"][h])
    return {
        sid: {"mase": statistics.mean(s["scaled"]), "mae": statistics.mean(s["abs"]),
              "rmse": math.sqrt(statistics.mean(s["sq"])), "smape": statistics.mean(s["smape"])}
        for sid, s in by_series.items()
    }


def _geo_ratio(series: dict, naive: dict, key: str):
    ratios = [series[s][key] / naive[s][key] for s in series
              if naive[s][key] > 0 and series[s][key] > 0]
    return math.exp(statistics.mean(math.log(r) for r in ratios)) if ratios else None


def summarise(windows: list) -> dict:
    out = {}
    naive = per_series(windows, "NAIVE")
    for strategy in STRATEGIES:
        series = per_series(windows, strategy)
        covered = [c for w in windows for c in w["strategies"][strategy]["covered"]]
        by_h = []
        for h in range(HORIZON):
            sh, nh = per_series(windows, strategy, h), per_series(windows, "NAIVE", h)
            by_h.append({
                "mase": statistics.mean(v["mase"] for v in sh.values()),
                "mae": statistics.mean(v["mae"] for v in sh.values()),
                "rmse": statistics.mean(v["rmse"] for v in sh.values()),
                "rel_mae_vs_naive": _geo_ratio(sh, nh, "mae"),
                "rel_rmse_vs_naive": _geo_ratio(sh, nh, "rmse"),
                "coverage95": statistics.mean(w["strategies"][strategy]["covered"][h]
                                              for w in windows),
            })
        out[strategy] = {
            "series": len(series), "windows": len(windows),
            "mase_mean": statistics.mean(v["mase"] for v in series.values()),
            "mase_median": statistics.median(v["mase"] for v in series.values()),
            "smape_mean": statistics.mean(v["smape"] for v in series.values()),
            "rel_rmse_vs_naive": _geo_ratio(series, naive, "rmse"),
            "rmse_mean": statistics.mean(v["rmse"] for v in series.values()),
            "mae_mean": statistics.mean(v["mae"] for v in series.values()),
            "coverage95": sum(covered) / len(covered),
            "by_horizon": by_h,
        }
        if strategy in (ADAPTIVE, GUARDED) or strategy in BASELINES:
            models = [w["strategies"][strategy]["model"] for w in windows]
            out[strategy]["models_used"] = {m: models.count(m) for m in sorted(set(models))}
            out[strategy]["guard_overrides"] = sum(
                w["strategies"][strategy]["guard_override"] for w in windows)
    return out


def regime_table(windows: list) -> list:
    """Per data regime: naive vs deployed vs the best fixed model, by mean MASE."""
    regimes = sorted({r for w in windows for r in w["regimes"]})
    rows = []
    for regime in regimes:
        ws = [w for w in windows if regime in w["regimes"]]
        mase = {s: statistics.mean(v["mase"] for v in per_series(ws, s).values())
                for s in STRATEGIES}
        best_fixed = min(FIXED, key=lambda s: mase[s])
        rows.append({
            "regime": regime, "series": len({w["series"] for w in ws}),
            "naive": mase["NAIVE"], "deployed": mase[DEPLOYED],
            "best_fixed": best_fixed, "best_fixed_mase": mase[best_fixed],
            "coverage95": statistics.mean(c for w in ws for c in w["strategies"][DEPLOYED]["covered"]),
        })
    return rows


def stationarity_table(windows: list) -> list:
    """Does the ADF+KPSS verdict on the training window predict forecast trouble?"""
    rows = []
    for verdict in ("STATIONARY", "NON_STATIONARY", "CONFLICT", "INCONCLUSIVE", "NOT_ASSESSED"):
        ws = [w for w in windows if w["stationarity"] == verdict]
        if not ws:
            continue
        smapes = [statistics.mean(w["strategies"][DEPLOYED]["smape"]) for w in ws]
        rows.append({
            "verdict": verdict, "windows": len(ws), "share": len(ws) / len(windows),
            "smape_mean": statistics.mean(smapes),
            "unreliable_rate": sum(s > UNRELIABLE_SMAPE for s in smapes) / len(smapes),
            "coverage95": statistics.mean(c for w in ws for c in w["strategies"][DEPLOYED]["covered"]),
        })
    return rows


def wilcoxon(windows: list, a: str, b: str) -> dict:
    """Paired test on per-series MASE: is `a` different from `b`?"""
    sa, sb = per_series(windows, a), per_series(windows, b)
    diffs = [sa[s]["mase"] - sb[s]["mase"] for s in sa]
    result = {"a": a, "b": b, "series": len(diffs), "a_better_in": sum(d < 0 for d in diffs),
              "median_diff": statistics.median(diffs) if diffs else None, "p_value": None}
    try:
        from scipy.stats import wilcoxon as _w

        if any(d != 0 for d in diffs):
            result["p_value"] = float(_w(diffs).pvalue)
    except ImportError:  # pragma: no cover
        pass
    return result


def wilson(successes: int, n: int, z: float = 1.96):
    """95% Wilson score interval for a proportion (None if n is 0)."""
    if not n:
        return None
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(centre - half, 4), round(centre + half, 4)]


def gate_table(windows: list, tau: float = None, legacy: bool = False,
               tau_conflict: float = None) -> dict:
    """
    How a readiness rule splits windows, scored by the deployed forecast's sMAPE.
    `tau=None` (and no legacy) means no gate at all - the ablation baseline.
    `tau_conflict` adds the Stage 8 rule: also refuse a window whose training
    data shows an ADF/KPSS conflict and whose in-history error exceeds it.
    """
    rows = []
    for w in windows:
        if legacy:
            refused = not w["gate_legacy_pass"]
        elif tau is None:
            refused = False
        else:
            err = w["gate_expected_error"]
            refused = err is not None and (err > tau or (
                tau_conflict is not None and w["stationarity"] == "CONFLICT"
                and err > tau_conflict))
        window_smape = statistics.mean(w["strategies"][DEPLOYED]["smape"])
        rows.append((refused, window_smape, window_smape > UNRELIABLE_SMAPE))
    refused = [r for r in rows if r[0]]
    accepted = [r for r in rows if not r[0]]
    unreliable = [r for r in rows if r[2]]
    tp = sum(1 for r in refused if r[2])
    precision = tp / len(refused) if refused else None
    recall = tp / len(unreliable) if unreliable else None
    f1 = (2 * precision * recall / (precision + recall)) if precision and recall else 0.0
    shown_unreliable = sum(1 for r in accepted if r[2])
    return {
        "tau": tau, "tau_conflict": tau_conflict, "legacy": legacy, "windows": len(rows),
        "refusals": len(refused), "true_refusals": tp,
        "precision_ci95": wilson(tp, len(refused)),
        "unreliable_shown_rate": shown_unreliable / len(accepted) if accepted else None,
        "refusal_rate": len(refused) / len(rows) if rows else 0.0,
        "smape_accepted": statistics.mean(r[1] for r in accepted) if accepted else None,
        "smape_refused": statistics.mean(r[1] for r in refused) if refused else None,
        "unreliable_windows": len(unreliable),
        "precision": precision, "recall": recall, "f1": f1,
    }


def environment() -> dict:
    import numpy
    import scipy
    import statsmodels

    return {"python": platform.python_version(), "numpy": numpy.__version__,
            "scipy": scipy.__version__, "statsmodels": statsmodels.__version__,
            "platform": platform.platform()}


# ==========================================================================
# Reporting
# ==========================================================================


def _f(v, spec=".3f"):
    return "-" if v is None else format(v, spec)


def accuracy_table(summary: dict) -> list:
    lines = ["| Strategy | MASE mean | MASE median | sMAPE % | rel. RMSE vs naive | "
             "RMSE | MAE | 95% coverage (h=1/2/3) |",
             "|---|---|---|---|---|---|---|---|"]
    for strategy in STRATEGIES:
        s = summary[strategy]
        cov = "/".join(f"{h['coverage95'] * 100:.0f}%" for h in s["by_horizon"])
        lines.append(
            f"| {strategy} | {_f(s['mase_mean'])} | {_f(s['mase_median'])} | "
            f"{_f(s['smape_mean'], '.1f')} | {_f(s['rel_rmse_vs_naive'])} | "
            f"{_f(s['rmse_mean'], ',.0f')} | {_f(s['mae_mean'], ',.0f')} | "
            f"{s['coverage95'] * 100:.1f}% ({cov}) |")
    return lines


def horizon_table(summary: dict) -> list:
    lines = ["| Strategy | h | MASE | MAE | RMSE | MAE vs naive | RMSE vs naive | 95% coverage |",
             "|---|---|---|---|---|---|---|---|"]
    for strategy in ("NAIVE", "SARIMA", "LINEAR_REGRESSION", DEPLOYED):
        for h, row in enumerate(summary[strategy]["by_horizon"], start=1):
            lines.append(
                f"| {strategy} | {h} | {_f(row['mase'])} | {_f(row['mae'], ',.0f')} | "
                f"{_f(row['rmse'], ',.0f')} | {_f(row['rel_mae_vs_naive'])} | "
                f"{_f(row['rel_rmse_vs_naive'])} | {row['coverage95'] * 100:.1f}% |")
    return lines


def _gate_md_row(group: str, label: str, r: dict) -> str:
    ci = r.get("precision_ci95")
    ci_text = f" ({ci[0]:.2f}-{ci[1]:.2f})" if ci else ""
    rate = r.get("unreliable_shown_rate")
    shown = "-" if rate is None else f"{rate * 100:.1f}%"
    return (f"| {group} | {label} | {r['refusal_rate'] * 100:.1f}% ({r['refusals']}) | "
            f"{_f(r['smape_accepted'], '.1f')} | {_f(r['smape_refused'], '.1f')} | "
            f"{shown} | "
            f"{_f(r['precision'], '.2f')}{ci_text} | {_f(r['recall'], '.2f')} | {_f(r['f1'], '.3f')} |")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rolling-origin forecasting benchmark")
    parser.add_argument("--quick", action="store_true", help="small synthetic run only")
    parser.add_argument("--skip-large", action="store_true",
                        help="leave out the 1,000-series held-out group (faster)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    args = parser.parse_args()
    started = time.perf_counter()

    data = {"SYNTHETIC": synthetic_series(args.quick)}
    if not args.quick:
        groups = [("M4_DEV", M4_DEV), ("M4_TEST", M4_TEST)]
        if not args.skip_large:
            groups.append(("M4_TEST_LARGE", M4_TEST_LARGE))
        for name, path in groups:
            if not path.exists():
                print(f"Missing {path.name}: run benchmark_data/prepare_m4_sample.py")
                return 2
            data[name] = m4_series(path, name)

    windows = {name: [] for name in data}
    jobs = [s for series in data.values() for s in series]
    print(f"Running {len(jobs)} series x {ORIGINS} origins x {len(STRATEGIES)} strategies "
          f"on {args.workers} workers...", flush=True)
    from concurrent.futures import ProcessPoolExecutor

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for series, result in zip(jobs, pool.map(run_series, jobs, chunksize=4)):
            windows[series["group"]].extend(result)
    development = windows["SYNTHETIC"] + windows.get("M4_DEV", [])
    held_out = [g for g in ("M4_TEST", "M4_TEST_LARGE") if g in windows]

    results = {"protocol": {
        "seed_synthetic": SEED, "horizon": HORIZON, "origins": ORIGINS,
        "origin_step": ORIGIN_STEP, "confidence": CONFIDENCE, "seasonal_period": PERIOD,
        "unreliable_smape": UNRELIABLE_SMAPE, "min_gate_precision": MIN_GATE_PRECISION,
        "series": {name: len(s) for name, s in data.items()},
        "m4_dev": "100 monthly series sampled uniformly at random (seed 2026) from the 48,000 "
                  "monthly series of the M4 competition dataset (100,000 series in total), "
                  "each truncated to its last 36 observations; development data",
        "m4_test": "100 further monthly series (seed 2027) drawn from the 47,900 M4 monthly "
                   "series not in M4_DEV, same truncation; held out in Stage 2 and evaluated "
                   "then; re-run here with the Stage 8 code, so it is no longer unseen",
        "m4_test_large": "1,000 further monthly series (seed 2028) drawn from the 47,800 M4 "
                         "monthly series in neither earlier sample, same truncation; drawn "
                         "after the Stage 8 design was frozen and evaluated once",
        "sarima_order": f"{prediction.SARIMA_ORDER}x{prediction.SARIMA_SEASONAL_ORDER}_{PERIOD}",
        "policy_version": prediction.CONFIG["version"],
        "deployed_settings": {"guard_sarima": prediction.GUARD_SARIMA,
                              "fitted_smoothing_min_points": prediction.FITTED_SMOOTHING_MIN_POINTS,
                              "band_method": prediction.BAND_METHOD,
                              "clip_non_negative": prediction.CLIP_NON_NEGATIVE,
                              "noise_limit": prediction.MAX_EXPECTED_ERROR,
                              "conflict_noise_limit": prediction.CONFLICT_NOISE_LIMIT},
        "environment": environment(),
    }}

    for name, ws in windows.items():
        results[name] = {
            "accuracy": summarise(ws),
            "regimes": regime_table(ws),
            "stationarity": stationarity_table(ws),
            "tests": [wilcoxon(ws, ADAPTIVE, "NAIVE"), wilcoxon(ws, GUARDED, "NAIVE"),
                      wilcoxon(ws, GUARDED, ADAPTIVE), wilcoxon(ws, GUARDED, "SARIMA"),
                      wilcoxon(ws, GUARDED, "THETA"), wilcoxon(ws, GUARDED, "AUTO_ETS")],
        }

    # Gate: tau chosen on DEVELOPMENT windows (as in Stage 2), then applied
    # unchanged to the held-out groups together with the Stage 8 conflict rule.
    sweep = [gate_table(development, tau) for tau in TAU_GRID]
    eligible = [r for r in sweep if (r["precision"] or 0) >= MIN_GATE_PRECISION] or sweep
    best = max(eligible, key=lambda r: (r["f1"], -r["refusal_rate"]))
    tau = best["tau"]
    conflict = prediction.CONFLICT_NOISE_LIMIT
    results["gate"] = {
        "tau_chosen_on_development": tau,
        "tau_in_code": prediction.MAX_EXPECTED_ERROR,
        "conflict_limit_in_code": conflict,
        "tau_sweep_development": sweep,
        # Ablation: each readiness rule added in turn. "deployed" is what
        # users get with forecast_config.json as shipped.
        "ablation": {name: {
            "no_gate": gate_table(ws, None),
            "stage1_cv_rule": gate_table(ws, legacy=True),
            "noise_gate_stage2": gate_table(ws, tau),
            "deployed_noise_plus_conflict": gate_table(ws, tau, tau_conflict=conflict),
        } for name, ws in windows.items()},
        # Sensitivity, reported after the fact: how the held-out result would
        # change had a different limit been chosen. Nothing here was used to
        # choose anything.
        "sensitivity_held_out": {name: {
            "noise_limit": [gate_table(windows[name], t, tau_conflict=conflict) for t in TAU_GRID],
            "conflict_limit": [gate_table(windows[name], tau, tau_conflict=c)
                               for c in (None, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16)],
        } for name in held_out},
    }
    results["runtime_seconds"] = round(time.perf_counter() - started, 1)

    # ---- markdown --------------------------------------------------------
    p = results["protocol"]
    md = ["# Forecasting benchmark (rolling origin)", "",
          "Generated by `evaluate_forecasting.py`. Do not edit by hand.", "",
          "## Protocol", "",
          "- Series: " + ", ".join(f"{n} {g}" for g, n in p["series"].items()),
          f"- M4_DEV: {p['m4_dev']}" if not args.quick else "- M4: skipped (--quick)",
          f"- M4_TEST: {p['m4_test']}" if not args.quick else "",
          f"- M4_TEST_LARGE: {p['m4_test_large']}" if "M4_TEST_LARGE" in windows else None,
          f"- {ORIGINS} origins per series, {ORIGIN_STEP} periods apart, horizon {HORIZON}; "
          "every forecast uses only data before its origin",
          "- MASE is scaled by the in-sample one-step naive MAE of each training window",
          f"- SARIMA order: {p['sarima_order']}",
          f"- Deployed settings (forecast_config.json {p['policy_version']}): "
          + ", ".join(f"{k} {v}" for k, v in p["deployed_settings"].items()),
          "- THETA and AUTO_ETS are statsmodels comparison baselines with their own 95% "
          "intervals, clipped at zero like the deployed layer; they fall back to naive when "
          "a fit fails",
          f"- An UNRELIABLE window has sMAPE > {UNRELIABLE_SMAPE:.0f}%",
          "- Environment: " + ", ".join(f"{k} {v}" for k, v in p["environment"].items()), ""]
    for name in windows:
        acc = results[name]["accuracy"]
        md += [f"## {name} ({acc['NAIVE']['series']} series, {acc['NAIVE']['windows']} windows)",
               "", "### Accuracy", ""] + accuracy_table(acc) + [""]
        for strategy in (ADAPTIVE, GUARDED):
            md.append(f"- {strategy} models used: {acc[strategy]['models_used']}; "
                      f"guard overrides: {acc[strategy]['guard_overrides']}")
        for strategy in BASELINES:
            md.append(f"- {strategy} fits (NAIVE = fit failed, naive used): "
                      f"{acc[strategy]['models_used']}")
        md += ["", "| Paired test (per-series MASE) | A better in | median diff | Wilcoxon p |",
               "|---|---|---|---|"]
        for t in results[name]["tests"]:
            md.append(f"| {t['a']} vs {t['b']} | {t['a_better_in']}/{t['series']} | "
                      f"{_f(t['median_diff'])} | {_f(t['p_value'], '.4f')} |")
        md += ["", "### Per forecast horizon", ""] + horizon_table(acc)
        md += ["", "### Per data regime (mean MASE)", "",
               f"| Regime | Series | Naive | {DEPLOYED} | Best fixed model | "
               "95% coverage (deployed) |", "|---|---|---|---|---|---|"]
        for r in results[name]["regimes"]:
            md.append(f"| {r['regime']} | {r['series']} | {_f(r['naive'])} | {_f(r['deployed'])} | "
                      f"{r['best_fixed']} ({_f(r['best_fixed_mase'])}) | "
                      f"{r['coverage95'] * 100:.1f}% |")
        md += ["", "### ADF + KPSS verdict on the training window vs forecast outcome", "",
               "| Verdict | Windows | Share | sMAPE % (deployed) | Unreliable rate | "
               "95% coverage |", "|---|---|---|---|---|---|"]
        for r in results[name]["stationarity"]:
            md.append(f"| {r['verdict']} | {r['windows']} | {r['share'] * 100:.1f}% | "
                      f"{_f(r['smape_mean'], '.1f')} | {r['unreliable_rate'] * 100:.1f}% | "
                      f"{r['coverage95'] * 100:.1f}% |")
        md.append("")

    g = results["gate"]
    header = ["| Group | Rule | Refused | sMAPE accepted | sMAPE refused | Unreliable among shown | "
              "Precision (95% CI) | Recall | F1 |", "|---|---|---|---|---|---|---|---|---|"]
    md += ["## Readiness gate: ablation", "",
           f"Deployed strategy scored: {DEPLOYED}. Noise limit chosen on DEVELOPMENT windows "
           f"(best F1 with precision >= {MIN_GATE_PRECISION}): tau = {g['tau_chosen_on_development']} "
           f"(value in code: {g['tau_in_code']}); Stage 8 conflict limit: {conflict}.", ""] + header
    labels = {"no_gate": "no gate", "stage1_cv_rule": "Stage 1 CV/R² rule",
              "noise_gate_stage2": "noise gate (Stage 2)",
              "deployed_noise_plus_conflict": "noise + conflict (deployed)"}
    for name, rules in g["ablation"].items():
        for key, label in labels.items():
            md.append(_gate_md_row(name, label, rules[key]))
    md += ["", "Noise-limit sweep (DEVELOPMENT), used to choose tau:", "",
           "| tau | Refusal rate | sMAPE accepted | Precision | Recall | F1 |",
           "|---|---|---|---|---|---|"]
    for r in sweep:
        md.append(f"| {r['tau']} | {r['refusal_rate'] * 100:.1f}% | "
                  f"{_f(r['smape_accepted'], '.1f')} | {_f(r['precision'], '.2f')} | "
                  f"{_f(r['recall'], '.2f')} | {_f(r['f1'], '.2f')} |")
    for name, sens in g["sensitivity_held_out"].items():
        md += ["", f"Sensitivity on {name} (after the fact; not used to choose anything):", "",
               "| Noise limit | Refused | Precision | Recall | F1 | sMAPE accepted |",
               "|---|---|---|---|---|---|"]
        for r in sens["noise_limit"]:
            md.append(f"| {r['tau']} | {r['refusal_rate'] * 100:.1f}% | {_f(r['precision'], '.2f')} | "
                      f"{_f(r['recall'], '.2f')} | {_f(r['f1'], '.3f')} | "
                      f"{_f(r['smape_accepted'], '.1f')} |")
        md += ["", "| Conflict limit (noise limit fixed) | Refused | Precision | Recall | F1 |",
               "|---|---|---|---|---|"]
        for r in sens["conflict_limit"]:
            md.append(f"| {r['tau_conflict'] if r['tau_conflict'] is not None else 'off'} | "
                      f"{r['refusal_rate'] * 100:.1f}% | {_f(r['precision'], '.2f')} | "
                      f"{_f(r['recall'], '.2f')} | {_f(r['f1'], '.3f')} |")
    md += ["", f"Runtime: {results['runtime_seconds']} s"]

    text = "\n".join(line for line in md if line is not None) + "\n"
    print("\n" + text)
    if g["tau_chosen_on_development"] != g["tau_in_code"]:
        print(f"NOTE: tau chosen on development ({tau}) differs from prediction.MAX_EXPECTED_ERROR "
              f"({prediction.MAX_EXPECTED_ERROR}); set the constant and re-run.")
    if not args.quick:
        REPORT_MD.write_text(text, encoding="utf-8")
        REPORT_JSON.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"Written: {REPORT_MD.name}, {REPORT_JSON.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
