"""
Part 3 + Prediction Stage 7 - Unified Temporal Summarization Framework.

The pipeline never asks a language model "what does this data say". It computes
every statement first as a `Claim` carrying its own value, source and derivation,
then either renders the claims deterministically or lets an LLM narrate them
under a verifier that rejects any number not present in the claim set.

Consequently a summary can be wrong only if the arithmetic is wrong - never
because the model invented a figure. Verification spans BOTH temporal
dimensions: historical claims are checked against the result set, predictive
claims against the model output.
"""

import math
import re
from dataclasses import dataclass, field, asdict

import llm
from profiler import log_step
from prompts import SUMMARY_SYSTEM_PROMPT, build_summary_prompt


@dataclass
class Claim:
    """One verified analytical statement."""

    claim_id: str
    dimension: str              # HISTORICAL | PREDICTIVE | ANOMALY | SCENARIO
    kind: str                   # TOTAL | MEAN | PEAK | TROUGH | CHANGE | FORECAST | ...
    text: str                   # deterministic natural-language rendering
    value: float = 0.0
    unit: str = ""
    source: str = ""            # what it was computed from
    derivation: str = ""        # how it was computed
    supporting_values: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SummaryResult:
    text: str = ""
    mode: str = "DETERMINISTIC"     # DETERMINISTIC | LLM_VERIFIED | LLM_REJECTED
    claims: list = field(default_factory=list)
    verification: dict = field(default_factory=dict)
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "mode": self.mode,
            "claim_count": len(self.claims),
            "claims": [c.to_dict() if isinstance(c, Claim) else c for c in self.claims],
            "verification": self.verification,
            "warnings": self.warnings,
        }


# ==========================================================================
# Formatting
# ==========================================================================


def fmt(value: float, unit: str = "") -> str:
    """
    Render a number the same way everywhere.

    Single formatter by design: the verifier matches the summary text against
    claim values, so any divergence in rounding between claim construction and
    narration would show up as an unverifiable number.
    """
    if value is None:
        return "n/a"
    av = abs(value)
    if av >= 1_000_000:
        s = f"{value / 1_000_000:,.2f}M"
    elif av >= 1000:
        s = f"{value:,.0f}"
    elif av >= 1:
        s = f"{value:,.2f}"
    else:
        s = f"{value:,.4f}".rstrip("0").rstrip(".")
    return f"{s}{unit}" if unit else s


def _pct(value: float) -> str:
    return f"{value:,.1f}%"


def _join(items: list) -> str:
    """'a', 'a and b', 'a, b and c'."""
    items = [str(i) for i in items]
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


# ==========================================================================
# Claim construction
# ==========================================================================


def build_historical_claims(profile, rows: list, analysis, forecast=None) -> list:
    """Compute verified facts about the returned data."""
    claims = []
    measure = None
    if forecast is not None and forecast.value_column:
        measure = forecast.value_column
    elif profile.measure_columns:
        measure = profile.measure_columns[0]

    label = measure.replace("_", " ") if measure else "the measure"

    claims.append(
        Claim(
            claim_id="H0",
            dimension="HISTORICAL",
            kind="ROW_COUNT",
            text=f"The query returned {profile.row_count} rows.",
            value=float(profile.row_count),
            source="result set",
            derivation="len(rows)",
        )
    )

    if not measure:
        return claims

    layout = getattr(profile, "layout", "SINGLE")
    if layout == "GROUPED":
        return claims + build_grouped_claims(profile, rows, measure)

    values = []
    labels = []
    axis = profile.temporal_column or (
        profile.dimension_columns[0] if profile.dimension_columns else ""
    )
    from result_profiler import extract_series, parse_number

    if layout == "SINGLE":
        # Chronological, whatever ORDER BY the query used: "changed from X to Y"
        # must read from the earliest period to the latest.
        dates, values = extract_series(rows, profile.temporal_column, measure)
        labels = [str(d.date()) for d in dates]
    else:
        for row in rows:
            v = parse_number(row.get(measure))
            if v is not None:
                values.append(v)
                labels.append(str(row.get(axis, "")) if axis else "")

    if not values:
        return claims
    # What one value stands for: a period only when there is one row per period.
    if layout == "SINGLE":
        unit = "period"
    elif layout == "CROSS_SECTIONAL" and profile.dimension_columns:
        unit = profile.dimension_columns[0].replace("_", " ")
    else:
        unit = "row"

    total = sum(values)
    mean = total / len(values)
    peak = max(values)
    trough = min(values)
    peak_label = labels[values.index(peak)] if labels else ""
    trough_label = labels[values.index(trough)] if labels else ""

    claims.append(
        Claim("H1", "HISTORICAL", "TOTAL",
              f"Total {label} across the returned "
              f"{'period' if layout == 'SINGLE' else 'rows'} is {fmt(total)}.",
              total, "", f"column '{measure}'", f"sum of {len(values)} values",
              values[:50])
    )
    claims.append(
        Claim("H2", "HISTORICAL", "MEAN",
              f"The average {label} per {unit} is {fmt(mean)}.",
              mean, "", f"column '{measure}'", f"{fmt(total)} / {len(values)}")
    )

    ratio = peak / mean if mean else 0.0
    claims.append(
        Claim("H3", "HISTORICAL", "PEAK",
              f"The highest value was {fmt(peak)}"
              + (f" at {peak_label}" if peak_label else "")
              + (f", {ratio:.2f}x the average." if mean else "."),
              peak, "", f"column '{measure}'", "max of the series")
    )
    claims.append(
        Claim("H4", "HISTORICAL", "TROUGH",
              f"The lowest value was {fmt(trough)}"
              + (f" at {trough_label}." if trough_label else "."),
              trough, "", f"column '{measure}'", "min of the series")
    )

    if layout == "SINGLE" and len(values) >= 2 and values[0] != 0:
        change = values[-1] - values[0]
        change_pct = change / abs(values[0]) * 100.0
        direction = "increased" if change > 0 else ("decreased" if change < 0 else "held flat")
        claims.append(
            Claim("H5", "HISTORICAL", "CHANGE",
                  f"Over the period the value {direction} from {fmt(values[0])} to "
                  f"{fmt(values[-1])}, a change of {_pct(change_pct)}.",
                  change_pct, "%", f"column '{measure}'",
                  "(last - first) / |first| * 100")
        )

    if len(values) > 2:
        mean_v = mean
        std = math.sqrt(sum((v - mean_v) ** 2 for v in values) / (len(values) - 1))
        claims.append(
            Claim("H6", "HISTORICAL", "DISPERSION",
                  f"Values vary with a standard deviation of {fmt(std)}.",
                  std, "", f"column '{measure}'", "sample standard deviation")
        )
    return claims


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def build_grouped_claims(profile, rows: list, measure: str) -> list:
    """Facts about a GROUPED result: per-category totals and movement, never mixed."""
    from result_profiler import extract_grouped_series

    group = profile.group_column
    label = measure.replace("_", " ")
    series = extract_grouped_series(rows, profile.temporal_column, group, measure)
    if not series:
        return []
    totals = {cat: sum(vals) for cat, (_, vals) in series.items()}
    grand = sum(totals.values())
    ranked = sorted(totals, key=lambda c: -totals[c])
    claims = [
        Claim("HG0", "HISTORICAL", "GROUP_COUNT",
              f"The result holds {len(series)} {group} series over "
              f"{profile.period_count} periods.",
              float(len(series)), "", "result set", f"distinct values of '{group}'"),
        Claim("H1", "HISTORICAL", "TOTAL",
              f"Total {label} across all {group} values and periods is {fmt(grand)}.",
              grand, "", f"column '{measure}'", "sum over every row"),
    ]
    top = ranked[0]
    share = 100.0 * totals[top] / grand if grand else 0.0
    claims.append(
        Claim("HG1", "HISTORICAL", "GROUP_LEADER",
              f"{top} has the largest total {label}, {fmt(totals[top])} "
              f"({_pct(share)} of the total).",
              totals[top], "", f"column '{measure}' by '{group}'",
              f"max of per-{group} sums", [share]))
    if len(ranked) > 1:
        last = ranked[-1]
        claims.append(
            Claim("HG2", "HISTORICAL", "GROUP_TRAILER",
                  f"{last} has the smallest total {label}, {fmt(totals[last])}.",
                  totals[last], "", f"column '{measure}' by '{group}'",
                  f"min of per-{group} sums"))
    for i, cat in enumerate(ranked[:3], start=1):
        _, vals = series[cat]
        if len(vals) >= 2 and vals[0]:
            change = (vals[-1] - vals[0]) / abs(vals[0]) * 100.0
            claims.append(
                Claim(f"HG3.{i}", "HISTORICAL", "GROUP_CHANGE",
                      f"{cat} moved from {fmt(vals[0])} to {fmt(vals[-1])} over the "
                      f"period, a change of {_pct(change)}.",
                      change, "%", f"'{cat}' series", "(last - first) / |first| * 100",
                      [vals[0], vals[-1]]))
    return claims


# ==========================================================================
# Strategy claims (Prediction Stage 1 execution)
# ==========================================================================


def build_strategy_claims(strategy_result, confidence: float = 0.95) -> list:
    """Verified statements about the strategy-specific prediction."""
    if strategy_result is None or not getattr(strategy_result, "executed", False):
        return []
    d = strategy_result.details or {}
    kind = strategy_result.executed_as
    conf = int(confidence * 100)
    claims = []

    if kind == "CATEGORY_TRAJECTORY":
        group = d["group_column"]
        label = d["measure"].replace("_", " ")
        lead, now, runner = d["projected_leader"], d["current_leader"], d["runner_up"]
        text = (f"{lead['category']} is projected to be the highest {group} in {lead['label']} at "
                f"{fmt(lead['value'])}, ahead of {runner['category']} at {fmt(runner['value'])}")
        if d["leader_changes"]:
            text += f", taking over from {now['category']}, which leads in {now['label']}"
        if d["clear_lead"]:
            text += "."
        else:
            text += ", though the two are within each other's forecast range."
        claims.append(Claim("T1", "PREDICTIVE", "STRATEGY_HEADLINE", text, lead["value"], "",
                            "per-category forecasts", "max of first-period forecasts",
                            [runner["value"], now["value"]]))
        for i, c in enumerate(d["categories"], start=1):
            p = c["points"][0]
            claims.append(Claim(
                f"T2.{i}", "PREDICTIVE", "TRAJECTORY_CATEGORY",
                f"{c['category']} {label} is projected at {fmt(p['predicted'])} for "
                f"{p['label']} ({conf}% range {fmt(p['lower'])} to {fmt(p['upper'])}), "
                f"from {fmt(c['last_actual'])} in {c['last_label']}.",
                p["predicted"], "", f"{c['model']} on '{c['category']}'",
                "first-period point forecast", [p["lower"], p["upper"], c["last_actual"]]))
        if d["rank_changes"]:
            moves = ", ".join(f"{r['category']} from {_ordinal(r['rank_now'])} to "
                              f"{_ordinal(r['rank_next'])}" for r in d["rank_changes"])
            claims.append(Claim("T3", "PREDICTIVE", "RANK_CHANGE",
                                f"Projected ranking changes: {moves}.",
                                float(len(d["rank_changes"])), "", "per-category forecasts",
                                "rank by last actual vs rank by first forecast"))
        if d["low_signal_categories"]:
            claims.append(Claim("T4", "PREDICTIVE", "LOW_SIGNAL_NOTE",
                                f"Forecasts for {_join(d['low_signal_categories'])} are "
                                "dominated by noise and less reliable.",
                                0.0, "", "Gate 3 per category", "forecastability test"))

    elif kind == "SHARE_SHIFT":
        label = d["measure"].replace("_", " ")
        g, lo = d["largest_gain"], d["largest_loss"]
        claims.append(Claim(
            "D1", "PREDICTIVE", "STRATEGY_HEADLINE",
            f"Between {d['from_label']} and {d['to_label']}, {g['category']} is projected "
            f"to gain the most share of {label}, from {_pct(g['share_now_pct'])} to "
            f"{_pct(g['share_next_pct'])}, while {lo['category']} moves from "
            f"{_pct(lo['share_now_pct'])} to {_pct(lo['share_next_pct'])}.",
            g["change_pp"], "pp", "per-category forecasts", "forecast share - current share",
            [g["share_now_pct"], g["share_next_pct"], lo["share_now_pct"], lo["share_next_pct"]]))
        for i, sh in enumerate(d["shares"], start=1):
            claims.append(Claim(
                f"D2.{i}", "PREDICTIVE", "SHARE_CATEGORY",
                f"{sh['category']}: {_pct(sh['share_now_pct'])} of {label} now, "
                f"{_pct(sh['share_next_pct'])} projected.",
                sh["share_next_pct"], "%", "per-category forecasts", "forecast / total forecast",
                [sh["share_now_pct"]]))

    elif kind == "QUARTILE_SHIFT":
        label = d["measure"].replace("_", " ")
        last, proj = d["last"], d["projected"]
        if "median" in proj:
            text = (f"The median {label} per row is projected to move from "
                    f"{fmt(last['median'])} in {d['last_label']} to {fmt(proj['median'])} "
                    f"in {d['next_label']}")
            if "p25" in proj and "p75" in proj:
                text += (f", with the middle half of values spanning {fmt(proj['p25'])} to "
                         f"{fmt(proj['p75'])} (now {fmt(last['p25'])} to {fmt(last['p75'])})")
            claims.append(Claim("D1", "PREDICTIVE", "STRATEGY_HEADLINE", text + ".",
                                proj["median"], "", "per-month quartile forecasts",
                                f"{d['periods']} monthly quartile series",
                                list(last.values()) + list(proj.values())))

    elif kind == "PERCENTILE_POSITION":
        pcts = [p["percentile"] for p in d["positions"]]
        low, high = min(pcts), max(pcts)
        span = _ordinal(round(low)) if round(low) == round(high) else \
            f"{_ordinal(round(low))} to {_ordinal(round(high))}"
        claims.append(Claim(
            "D1", "PREDICTIVE", "STRATEGY_HEADLINE",
            f"The projected values sit at the {span} percentile of the historical values "
            f"(historical median {fmt(d['historical_median'])}).",
            high, "", "forecast vs historical distribution", "share of history below forecast",
            pcts + [d["historical_median"]]))

    elif kind == "ANOMALY_PERSISTENCE":
        verdict = d["verdict"]
        if verdict == "NO_RECENT_ANOMALY":
            text = f"No anomaly occurred in the last {d['recent_window']} periods"
            latest = d.get("latest_anomaly")
            if latest:
                text += f"; the most recent was at {latest['label']} ({fmt(latest['value'])})."
            else:
                text += "."
            value = 0.0
        else:
            a = d["anomaly"]
            head = (f"The {a['direction'].lower()} anomaly at {a['label']} "
                    f"({fmt(a['value'])}) is projected to")
            if verdict == "RECOVERING":
                text = f"{head} recover: no forecast period stays beyond the threshold."
            elif verdict == "WORSENING":
                text = (f"{head} worsen: all {d['horizon']} forecast periods breach the "
                        "threshold, each further beyond it than the last.")
            else:
                text = (f"{head} persist: {d['projected_breaches']} of {d['horizon']} "
                        "forecast periods stay beyond the threshold.")
            value = float(d["projected_breaches"])
        claims.append(Claim("P1", "PREDICTIVE", "STRATEGY_HEADLINE", text, value, "",
                            "anomaly engine + forecast", verdict))
    return claims

def build_forecast_claims(forecast) -> list:
    """Compute verified statements about the model's projections."""
    claims = []
    if forecast is None or not forecast.generated:
        if forecast is not None and forecast.skipped_reason:
            claims.append(
                Claim("F0", "PREDICTIVE", "SKIPPED",
                      f"No forecast was produced: {forecast.skipped_reason}",
                      0.0, "", "readiness classifier", "gate failure")
            )
        return claims

    label = forecast.value_column.replace("_", " ")
    period = forecast.granularity.lower()

    claims.append(
        Claim("F1", "PREDICTIVE", "MODEL",
              f"A {forecast.model.replace('_', ' ').lower()} model was selected and "
              f"projects {forecast.horizon} {period} periods ahead.",
              float(forecast.horizon), "", "model selection engine",
              forecast.model_reason)
    )

    for i, p in enumerate(forecast.points, start=1):
        claims.append(
            Claim(
                f"F2.{i}", "PREDICTIVE", "FORECAST",
                f"{label.title()} for {p.label} is projected at {fmt(p.predicted)}, "
                f"within a {int(forecast.confidence_level * 100)}% confidence range of "
                f"{fmt(p.lower_bound)} to {fmt(p.upper_bound)}.",
                p.predicted, "", f"{forecast.model} output",
                f"point forecast h={p.period_index} with interval half-width "
                f"{fmt(p.interval_width / 2)}",
                [p.lower_bound, p.upper_bound],
            )
        )

    if forecast.points:
        # The whole projection in one sentence. Short responses have room for
        # three sentences, so they cannot afford one per forecast period; this
        # condensed claim is what they use. It is excluded from the full
        # deterministic text, which already states every point individually.
        points = forecast.points
        if len(points) == 1:
            p = points[0]
            path_text = (
                f"{label.title()} for {p.label} is projected at {fmt(p.predicted)}, "
                f"within a {int(forecast.confidence_level * 100)}% confidence range of "
                f"{fmt(p.lower_bound)} to {fmt(p.upper_bound)}."
            )
        else:
            path_text = (
                f"{label.title()} is projected at {_join([fmt(p.predicted) for p in points])} "
                f"for {_join([p.label for p in points])} respectively."
            )
        claims.append(
            Claim("F7", "PREDICTIVE", "FORECAST_PATH", path_text,
                  points[0].predicted, "", f"{forecast.model} output",
                  f"point forecasts h=1..{len(points)}",
                  [p.predicted for p in points]
                  + [b for p in points for b in (p.lower_bound, p.upper_bound)])
        )

        projected_total = sum(p.predicted for p in forecast.points)
        claims.append(
            Claim("F3", "PREDICTIVE", "FORECAST_TOTAL",
                  f"Across the full {forecast.horizon}-period horizon the projected "
                  f"total is {fmt(projected_total)}.",
                  projected_total, "", f"{forecast.model} output",
                  "sum of point forecasts")
        )

        if forecast.historical_values:
            hist_mean = sum(forecast.historical_values) / len(forecast.historical_values)
            last_point = forecast.points[-1]
            if hist_mean:
                delta_pct = (last_point.predicted - hist_mean) / abs(hist_mean) * 100.0
                relation = "above" if delta_pct > 0 else "below"
                claims.append(
                    Claim("F4", "PREDICTIVE", "FORECAST_VS_HISTORY",
                          f"The {last_point.label} projection of "
                          f"{fmt(last_point.predicted)} sits {_pct(abs(delta_pct))} "
                          f"{relation} the historical average of {fmt(hist_mean)}.",
                          delta_pct, "%", "forecast vs result set",
                          "(forecast - historical mean) / |historical mean| * 100")
                )

        widths = [p.interval_width for p in forecast.points]
        if len(widths) > 1 and widths[0] > 0:
            growth = widths[-1] / widths[0]
            claims.append(
                Claim("F5", "PREDICTIVE", "UNCERTAINTY",
                      f"Forecast uncertainty widens with distance: the interval at the "
                      f"final period is {growth:.2f}x as wide as at the first.",
                      growth, "x", "interval construction",
                      "final interval width / first interval width")
            )

    if forecast.in_sample_mape:
        claims.append(
            Claim("F6", "PREDICTIVE", "MODEL_FIT",
                  f"On the observed data the model's mean absolute percentage error "
                  f"is {_pct(forecast.in_sample_mape)}.",
                  forecast.in_sample_mape, "%", "in-sample residuals", "MAPE")
        )
    return claims


def build_readiness_claims(readiness, forecast) -> list:
    """A forecast shown with cautions says so, in the same verified summary."""
    if readiness is None or forecast is None or not getattr(forecast, "generated", False):
        return []
    if getattr(readiness, "decision", "") != "READY_WITH_WARNING":
        return []
    messages = [w["message"] for w in readiness.warnings]
    return [Claim("F8", "PREDICTIVE", "READINESS_CAUTION",
                  "This forecast carries a caution: " + " ".join(messages),
                  float(len(messages)), "", "readiness classifier",
                  "warnings: " + ", ".join(w["code"] for w in readiness.warnings))]


def build_anomaly_claims(report) -> list:
    """Compute verified statements about detected anomalies, past and projected."""
    claims = []
    if report is None or not report.evaluated:
        return claims

    if getattr(report, "detrended", False):
        # State the space the band lives in, otherwise a reader compares a
        # residual fence against raw values and concludes the numbers are wrong.
        threshold_text = (
            f"Because the series carries a strong trend (R² = {report.trend_r2:.2f}), "
            f"anomalies were measured as deviations from that trend rather than from a "
            f"flat average, with a normal deviation range of {fmt(report.lower_threshold)} "
            f"to {fmt(report.upper_threshold)}."
        )
        derivation = (
            f"detrended residual fence: Q1 - {report.iqr_multiplier}*IQR .. "
            f"Q3 + {report.iqr_multiplier}*IQR"
        )
    else:
        threshold_text = (
            f"Anomaly thresholds were adapted to this series' "
            f"{report.volatility_regime.lower()} volatility, giving a normal range of "
            f"{fmt(report.lower_threshold)} to {fmt(report.upper_threshold)}."
        )
        derivation = (
            f"Q1 - {report.iqr_multiplier}*IQR .. Q3 + {report.iqr_multiplier}*IQR"
        )

    claims.append(
        Claim("A0", "ANOMALY", "THRESHOLD", threshold_text,
              report.upper_threshold, "", "IQR/Z-score threshold engine", derivation)
    )

    for i, a in enumerate(report.historical_anomalies, start=1):
        claims.append(
            Claim(f"A1.{i}", "ANOMALY", "HISTORICAL_ANOMALY",
                  f"{a.label or 'One observation'} is a {a.severity.lower()} "
                  f"{a.direction.lower()} outlier at {fmt(a.value)}, "
                  f"{_pct(abs(a.deviation_pct))} from the mean.",
                  a.value, "", "historical dimension",
                  f"z={a.z_score}, detected by {'+'.join(a.detected_by)}")
        )

    for i, a in enumerate(report.predictive_warnings, start=1):
        claims.append(
            Claim(f"A2.{i}", "ANOMALY", "PREDICTED_BREACH",
                  f"The projection for {a.label} at {fmt(a.value)} is expected to breach "
                  f"the {a.direction.lower()} threshold, {_pct(abs(a.deviation_pct))} "
                  f"from the historical mean.",
                  a.value, "", "predictive dimension",
                  f"forecast value vs adaptive threshold, z={a.z_score}")
        )

    if not report.historical_anomalies and not report.predictive_warnings:
        claims.append(
            Claim("A3", "ANOMALY", "CLEAR",
                  "No values, historical or projected, fall outside the adaptive "
                  "normal range.",
                  0.0, "", "both dimensions", "no threshold breaches")
        )
    return claims


def build_scenario_claims(scenario) -> list:
    """Compute verified statements about a what-if simulation."""
    claims = []
    if scenario is None or not scenario.simulated:
        return claims

    spec = scenario.spec
    claims.append(
        Claim("S0", "SCENARIO", "PARAMETER",
              f"Simulating a {spec['magnitude_pct']:.0f}% "
              f"{spec['direction'].lower()} applied to the forecast.",
              spec["magnitude_pct"], "%", "what-if engine", spec["parse_note"])
    )
    claims.append(
        Claim("S1", "SCENARIO", "SCENARIO_TOTAL",
              f"Under this scenario the horizon total moves from "
              f"{fmt(scenario.baseline_total)} to {fmt(scenario.scenario_total)}, "
              f"a change of {_pct(scenario.total_delta_pct)}.",
              scenario.scenario_total, "", "scenario simulation",
              "baseline forecast x scenario multiplier")
    )
    for i, d in enumerate(scenario.deltas, start=1):
        claims.append(
            Claim(f"S2.{i}", "SCENARIO", "SCENARIO_POINT",
                  f"{d['label']} moves from {fmt(d['baseline'])} to "
                  f"{fmt(d['scenario'])} ({_pct(d['delta_pct'])}).",
                  d["scenario"], "", "scenario simulation",
                  "point forecast x multiplier")
        )
    return claims


# ==========================================================================
# Verification
# ==========================================================================

_NUMBER_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _numbers_in(text: str) -> list:
    out = []
    for token in _NUMBER_RE.findall(text or ""):
        try:
            out.append(float(token.replace(",", "")))
        except ValueError:
            continue
    return out


def verify_summary(text: str, claims: list, tolerance: float = 0.02) -> dict:
    """
    Check that every number in a narrated summary traces to a claim.

    A figure passes if it matches any claim value, any supporting value, or any
    number appearing in a claim's own deterministic text (which covers derived
    figures such as multiples and interval bounds), within `tolerance` relative
    error. Anything else is unverifiable and rejects the narration.
    """
    allowed = set()
    for c in claims:
        allowed.add(round(float(c.value), 6))
        for sv in c.supporting_values:
            try:
                allowed.add(round(float(sv), 6))
            except (TypeError, ValueError):
                continue
        for n in _numbers_in(c.text):
            allowed.add(round(n, 6))

    allowed_list = sorted(allowed)
    found = _numbers_in(text)
    unverified = []

    for n in found:
        ok = False
        for a in allowed_list:
            if a == 0:
                if abs(n) < 1e-9:
                    ok = True
                    break
            elif abs(n - a) / max(abs(a), 1e-9) <= tolerance:
                ok = True
                break
        if not ok:
            unverified.append(n)

    return {
        "numbers_in_summary": len(found),
        "verified": len(found) - len(unverified),
        "unverified_values": unverified,
        "passed": not unverified,
        "tolerance": tolerance,
        "claims_available": len(claims),
    }


# ==========================================================================
# Rendering
# ==========================================================================


# Claims that restate other claims in condensed form. They exist for size-bounded
# renderings (short summaries, notices) and are left out of the full text so it
# never says the same thing twice.
CONDENSED_KINDS = {"FORECAST_PATH"}


def render_deterministic(claims: list) -> str:
    """
    Concatenate claim texts into paragraphs grouped by temporal dimension.

    This is the default output. It is unconditionally correct, since every
    sentence is a claim that was computed rather than written.
    """
    order = ["HISTORICAL", "ANOMALY", "PREDICTIVE", "SCENARIO"]
    paragraphs = []
    for dimension in order:
        sentences = [c.text for c in claims
                     if c.dimension == dimension and c.kind not in CONDENSED_KINDS]
        if sentences:
            paragraphs.append(" ".join(sentences))
    return "\n\n".join(paragraphs)


def render_with_llm(claims: list, max_sentences: int = 8, profiler=None) -> tuple:
    """
    Ask an LLM to narrate the claims, then verify. Returns (text, mode, verification).

    On any verification failure the LLM output is discarded entirely - there is
    no partial acceptance, because a summary with one invented number is not
    90% trustworthy, it is untrustworthy.
    """
    claim_block = "\n".join(
        f"[{c.claim_id}] ({c.dimension}/{c.kind}) {c.text}"
        for c in claims if c.kind not in CONDENSED_KINDS
    )
    prompt = build_summary_prompt(claim_block, max_sentences)

    payload, _ = llm.call_llm_json(
        SUMMARY_SYSTEM_PROMPT
        + '\n\nReturn JSON: {"summary": "<the prose>"}',
        prompt,
        profiler=profiler,
    )
    text = str(payload.get("summary", "")).strip()
    if not text:
        return "", "LLM_REJECTED", {"passed": False, "reason": "empty summary"}

    verification = verify_summary(text, claims)
    if verification["passed"]:
        return text, "LLM_VERIFIED", verification
    return text, "LLM_REJECTED", verification


def summarize(
    profile,
    rows: list,
    analysis,
    forecast=None,
    anomaly_report=None,
    scenario=None,
    use_llm: bool = False,
    max_sentences: int = 8,
    profiler=None,
    strategy_result=None,
    readiness=None,
) -> SummaryResult:
    """
    Build the unified temporal summary.

    Claim construction always runs. LLM narration is opt-in and always gated by
    the verifier, so enabling it can improve fluency but can never introduce an
    unverified number: a rejected narration falls back to the deterministic text.
    """
    claims = []
    claims += build_historical_claims(profile, rows, analysis, forecast)
    claims += build_anomaly_claims(anomaly_report)
    claims += build_forecast_claims(forecast)
    claims += build_readiness_claims(readiness, forecast)
    claims += build_strategy_claims(
        strategy_result, getattr(forecast, "confidence_level", 0.95) if forecast else 0.95)
    claims += build_scenario_claims(scenario)

    result = SummaryResult(claims=claims)
    deterministic = render_deterministic(claims)

    if use_llm and llm.is_available() and claims:
        try:
            text, mode, verification = render_with_llm(claims, max_sentences, profiler)
            result.verification = verification
            if mode == "LLM_VERIFIED":
                result.text = text
                result.mode = mode
            else:
                result.text = deterministic
                result.mode = "LLM_REJECTED"
                result.warnings.append(
                    "LLM summary contained unverifiable numbers "
                    f"{verification.get('unverified_values')}; fell back to "
                    "deterministic rendering."
                )
                log_step("LLM summary rejected by verifier; using claims text.", level="WARN")
        except Exception as exc:  # noqa: BLE001
            result.text = deterministic
            result.mode = "DETERMINISTIC"
            result.warnings.append(f"LLM narration unavailable ({exc}).")
    else:
        result.text = deterministic
        result.mode = "DETERMINISTIC"
        result.verification = verify_summary(deterministic, claims)

    return result
