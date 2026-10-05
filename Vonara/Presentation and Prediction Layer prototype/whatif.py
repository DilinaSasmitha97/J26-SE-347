"""
Prediction Stage 6 - Natural-Language What-If Scenario Simulation.

Turns a scenario clause ("what if I cut spending by 20%?") into a parametric
modification of an existing forecast, then regenerates every downstream output
so chart, summary and anomaly state all move together.

Security note: scenario text is untrusted user input, but it never reaches SQL
and never re-enters the database. It is parsed into a bounded numeric
perturbation (direction + magnitude, clamped) and applied to values already
returned. A scenario cannot widen data access.
"""

import re
from dataclasses import dataclass, field, asdict

import scenario_language
from anomaly import detect_anomalies
from prediction import ForecastPoint, ForecastResult
from schemas import SEASONAL_PERIOD, Granularity, WhatIfSpec


def _period(granularity) -> int:
    """Seasonal period for the anomaly screen; same mapping as the pipeline."""
    try:
        return SEASONAL_PERIOD.get(Granularity(granularity), 1)
    except ValueError:
        return 1

# Bounds on a scenario (see scenario_language): a fall beyond 100 % would make
# values negative; a rise beyond 300 % (quadrupling) is a different question and
# the multiplicative perturbation model would not hold.
MAX_MAGNITUDE_PCT = scenario_language.MAX_DECREASE_PCT
MAX_INCREASE_PCT = scenario_language.MAX_INCREASE_PCT

_APPLY_MODES = {
    "IMMEDIATE": "Full effect applied from the first forecast period.",
    "RAMPED": "Effect phases in linearly across the forecast horizon.",
}


@dataclass
class ScenarioSpec:
    valid: bool = False
    raw_clause: str = ""
    parameter: str = ""
    direction: str = ""              # INCREASE | DECREASE
    magnitude_pct: float = 0.0
    apply_mode: str = "IMMEDIATE"
    parse_note: str = ""
    reason_code: str = ""            # why an invalid spec was refused (scenario_language)

    def multiplier(self) -> float:
        sign = -1.0 if self.direction == "DECREASE" else 1.0
        return 1.0 + sign * (self.magnitude_pct / 100.0)


@dataclass
class ScenarioResult:
    simulated: bool = False
    spec: dict = field(default_factory=dict)
    baseline_points: list = field(default_factory=list)
    scenario_points: list = field(default_factory=list)
    deltas: list = field(default_factory=list)
    baseline_total: float = 0.0
    scenario_total: float = 0.0
    total_delta: float = 0.0
    total_delta_pct: float = 0.0
    anomaly_report: dict = field(default_factory=dict)
    skipped_reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_scenario(text: str, default_parameter: str = "") -> ScenarioSpec:
    """
    Parse a free-text scenario clause into a bounded parametric spec.

    Deliberately conservative: if direction or magnitude cannot be recovered
    with confidence, the spec is marked invalid and the pipeline reports that
    it could not interpret the scenario, rather than simulating a guess.
    """
    spec = ScenarioSpec(raw_clause=(text or "").strip()[:200], parameter=default_parameter)
    parsed = scenario_language.parse(text)
    spec.reason_code = parsed["reason_code"]
    if not parsed["valid"]:
        spec.parse_note = parsed["note"]
        return spec
    spec.valid = True
    spec.direction = parsed["direction"]
    spec.magnitude_pct = parsed["magnitude_pct"]
    spec.apply_mode = parsed["apply_mode"]
    spec.parse_note = parsed["note"] or (
        f"Parsed as {spec.direction} of {spec.magnitude_pct:g}% "
        f"({_APPLY_MODES[spec.apply_mode]})"
    )
    return spec


def simulate(
    forecast: ForecastResult,
    scenario_text: str = "",
    spec: ScenarioSpec = None,
    historical_values: list = None,
) -> ScenarioResult:
    """
    Apply a scenario to a generated forecast and recompute every dependent output.

    Confidence bounds are scaled by the same multiplier as the central estimate:
    a 20% reduction in spend reduces the absolute uncertainty proportionally,
    since the perturbation is multiplicative rather than additive.
    """
    result = ScenarioResult()

    if forecast is None or not forecast.generated:
        result.skipped_reason = "No forecast available to simulate against."
        return result

    if spec is None:
        spec = parse_scenario(scenario_text, forecast.value_column)
    result.spec = asdict(spec)

    if not spec.valid:
        result.skipped_reason = f"Scenario could not be interpreted: {spec.parse_note}"
        return result

    multiplier = spec.multiplier()
    horizon = len(forecast.points)

    for i, point in enumerate(forecast.points):
        if spec.apply_mode == "RAMPED" and horizon > 1:
            # Phase the effect in linearly: full magnitude only at the last period.
            step_mult = 1.0 + (multiplier - 1.0) * ((i + 1) / horizon)
        else:
            step_mult = multiplier

        scenario_point = ForecastPoint(
            period_index=point.period_index,
            timestamp=point.timestamp,
            label=point.label,
            predicted=round(point.predicted * step_mult, 4),
            lower_bound=round(point.lower_bound * step_mult, 4),
            upper_bound=round(point.upper_bound * step_mult, 4),
            interval_width=round(point.interval_width * abs(step_mult), 4),
        )
        result.baseline_points.append(asdict(point))
        result.scenario_points.append(asdict(scenario_point))
        result.deltas.append(
            {
                "label": point.label,
                "baseline": point.predicted,
                "scenario": scenario_point.predicted,
                "delta": round(scenario_point.predicted - point.predicted, 4),
                "delta_pct": round(
                    ((scenario_point.predicted - point.predicted) / point.predicted * 100.0)
                    if point.predicted
                    else 0.0,
                    2,
                ),
            }
        )

    result.baseline_total = round(sum(p.predicted for p in forecast.points), 4)
    result.scenario_total = round(sum(p["predicted"] for p in result.scenario_points), 4)
    result.total_delta = round(result.scenario_total - result.baseline_total, 4)
    result.total_delta_pct = round(
        (result.total_delta / result.baseline_total * 100.0) if result.baseline_total else 0.0,
        2,
    )

    # Re-screen the simulated path against the ORIGINAL historical thresholds:
    # the question is whether the scenario brings values back into the normal
    # range, so the band must not move with the scenario.
    history = historical_values if historical_values is not None else forecast.historical_values
    if history:
        scenario_forecast = ForecastResult(
            generated=True,
            model=forecast.model,
            points=[ForecastPoint(**p) for p in result.scenario_points],
        )
        result.anomaly_report = detect_anomalies(
            history, forecast=scenario_forecast, period=_period(forecast.granularity)
        ).to_dict()

    result.simulated = True
    return result


def scenario_from_analysis(analysis) -> ScenarioSpec:
    """Build a spec from the what-if the analyzer already extracted."""
    wi: WhatIfSpec = analysis.what_if
    if not wi.present:
        return ScenarioSpec(parse_note="No what-if clause detected in the query.")
    # The clause is re-read by the same parser as the simulate box, so both
    # routes agree. Before Stage 4 a clause with a magnitude but no direction
    # word ("SET") was simulated as a DECREASE, and ramp wording was dropped.
    spec = parse_scenario(wi.raw_clause, wi.parameter)
    if (not spec.valid and spec.reason_code in ("NO_DIRECTION", "NO_MAGNITUDE")
            and wi.direction in ("INCREASE", "DECREASE") and wi.magnitude_pct > 0):
        # An LLM analysis supplied what the rules could not find. Refusals for a
        # negated, ranged, absolute or multi-change clause are never overridden.
        limit = MAX_INCREASE_PCT if wi.direction == "INCREASE" else MAX_MAGNITUDE_PCT
        spec = ScenarioSpec(
            valid=True,
            raw_clause=wi.raw_clause,
            parameter=wi.parameter,
            direction=wi.direction,
            magnitude_pct=min(wi.magnitude_pct, limit),
            parse_note="Direction and magnitude taken from the LLM query analysis.",
        )
    return spec
