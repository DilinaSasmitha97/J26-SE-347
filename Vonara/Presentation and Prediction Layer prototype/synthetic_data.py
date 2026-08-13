"""
Synthetic multi-tenant business data generator.

The TAF commits the project to synthetic Sales/HR/Finance environments "with
varying degrees of statistical noise and volatility". This module produces
them deterministically (fixed seed) so every number in the evaluation report is
reproducible.

Series are generated from a known ground-truth process:

    value(t) = level + trend*t + seasonal(t) + noise(t) [+ injected anomalies]

Because the generator knows where it injected anomalies and what the noise-free
signal was, it supplies the labels that `evaluate.py` needs to measure anomaly
detection precision and recall - which is otherwise unobtainable on real data.
"""

import math
import random

SCHEMA_DDL = """
CREATE TABLE expenses (
    expense_id INT,
    tenant_id VARCHAR(32),
    invoice_date DATE,
    category VARCHAR(64),
    vendor VARCHAR(128),
    amount DECIMAL(12,2),
    approved_by_email VARCHAR(128)
);

CREATE TABLE sales (
    sale_id INT,
    tenant_id VARCHAR(32),
    sale_date DATE,
    region VARCHAR(64),
    product VARCHAR(64),
    units INT,
    revenue DECIMAL(12,2)
);

CREATE TABLE employees (
    employee_id INT,
    tenant_id VARCHAR(32),
    full_name VARCHAR(128),
    email VARCHAR(128),
    department VARCHAR(64),
    hire_date DATE,
    salary DECIMAL(12,2)
);

CREATE TABLE support_tickets (
    ticket_id INT,
    tenant_id VARCHAR(32),
    opened_date DATE,
    priority VARCHAR(16),
    resolution_hours DECIMAL(8,2),
    customer_phone VARCHAR(32)
);
"""

CATEGORIES = ["Software", "Hardware", "Travel", "Marketing", "Facilities"]
REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Basic", "Pro", "Enterprise"]
DEPARTMENTS = ["Engineering", "Sales", "Finance", "HR", "Support"]


def _month_label(start_year: int, start_month: int, offset: int) -> str:
    total = start_month - 1 + offset
    year = start_year + total // 12
    month = total % 12 + 1
    return f"{year:04d}-{month:02d}-01"


def generate_timeseries(
    n_periods: int = 24,
    level: float = 3500.0,
    trend: float = 80.0,
    seasonal_amplitude: float = 0.0,
    noise_pct: float = 0.06,
    anomaly_indices: list = None,
    anomaly_magnitude: float = 3.0,
    seed: int = 42,
    start_year: int = 2024,
    start_month: int = 1,
    date_field: str = "invoice_date",
    value_field: str = "amount",
) -> tuple:
    """
    Generate a labelled monthly series.

    Returns (rows, ground_truth) where ground_truth carries the noise-free
    signal and the injected anomaly positions.

    Args:
        seasonal_amplitude: peak deviation of the 12-month seasonal component,
                            as a fraction of `level`. 0 disables seasonality.
        noise_pct:          Gaussian noise standard deviation as a fraction of
                            the current signal level.
        anomaly_indices:    period offsets at which to inject an outlier.
        anomaly_magnitude:  outlier size, in multiples of the noise sigma.
    """
    rng = random.Random(seed)
    anomaly_indices = set(anomaly_indices or [])

    rows = []
    clean_signal = []
    labels = []

    for t in range(n_periods):
        signal = level + trend * t
        if seasonal_amplitude:
            signal += level * seasonal_amplitude * math.sin(2 * math.pi * t / 12.0)
        clean_signal.append(signal)

        sigma = abs(signal) * noise_pct
        value = signal + rng.gauss(0, sigma)

        if t in anomaly_indices:
            # Sign alternates so the suite exercises both HIGH and LOW detection.
            direction = 1 if len(labels) % 2 == 0 else -1
            value += direction * anomaly_magnitude * max(sigma, abs(signal) * 0.05)
            labels.append(t)

        rows.append(
            {
                date_field: _month_label(start_year, start_month, t),
                value_field: round(value, 2),
            }
        )

    return rows, {
        "clean_signal": [round(v, 2) for v in clean_signal],
        "anomaly_indices": sorted(labels),
        "n_periods": n_periods,
        "has_trend": trend != 0,
        "has_seasonality": seasonal_amplitude > 0,
        "noise_pct": noise_pct,
    }


def generate_categorical(
    n_categories: int = 5,
    label_field: str = "category",
    value_field: str = "total_amount",
    seed: int = 42,
    categories: list = None,
) -> list:
    """Generate a single-dimension aggregate result set (no time axis)."""
    rng = random.Random(seed)
    cats = (categories or CATEGORIES)[:n_categories]
    if len(cats) < n_categories:
        cats = cats + [f"Category_{i}" for i in range(len(cats), n_categories)]
    return [
        {label_field: c, value_field: round(rng.uniform(5_000, 60_000), 2)}
        for c in cats
    ]


def generate_grouped_timeseries(
    n_periods: int = 18,
    groups: list = None,
    seed: int = 7,
    date_field: str = "sale_date",
    group_field: str = "region",
    value_field: str = "revenue",
) -> list:
    """Generate a multi-series result set: one series per group."""
    groups = groups or REGIONS
    rows = []
    for gi, group in enumerate(groups):
        series, _ = generate_timeseries(
            n_periods=n_periods,
            level=20_000 + gi * 6_000,
            trend=250 * (gi + 1) * (1 if gi % 2 == 0 else -1),
            noise_pct=0.09,
            seed=seed + gi,
            date_field=date_field,
            value_field=value_field,
        )
        for row in series:
            row[group_field] = group
            rows.append(row)
    return rows


def generate_detail_rows(n: int = 12, seed: int = 11) -> list:
    """Row-level records including PII-shaped columns, for masking tests."""
    rng = random.Random(seed)
    first = ["Ayesha", "Nuwan", "Dilini", "Kasun", "Tharindu", "Sanduni"]
    last = ["Perera", "Fernando", "Silva", "Jayasuriya", "Bandara", "Rathnayake"]
    rows = []
    for i in range(n):
        name = f"{rng.choice(first)} {rng.choice(last)}"
        rows.append(
            {
                "employee_id": 1000 + i,
                "full_name": name,
                "email": f"{name.split()[0].lower()}.{i}@example.com",
                "department": rng.choice(DEPARTMENTS),
                "hire_date": _month_label(2019, 1, rng.randint(0, 60)),
                "salary": round(rng.uniform(60_000, 180_000), 2),
            }
        )
    return rows


# ==========================================================================
# Named scenarios used by main.py and evaluate.py
# ==========================================================================


def benchmark_suite() -> list:
    """
    Twelve labelled scenarios spanning the volatility and shape space.

    Each entry carries `expected_model`, the model the Stage 3 rules SHOULD
    choose given the generating process. evaluate.py reports how often the
    selector agrees, which is how the dual-signal algorithm is validated.
    """
    return [
        {
            "name": "finance_linear_growth",
            "description": "Clean linear expense growth, low noise, 24 months",
            "query": "Show my total software expenses by month and predict the next 3 months",
            "expected_model": "LINEAR_REGRESSION",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 3500, 120, 0.0, 0.04, [], 101),
        },
        {
            "name": "finance_seasonal",
            "description": "Strong 12-month seasonality over 36 months",
            "query": "Show monthly marketing spend over time and forecast the next quarter",
            "expected_model": "SARIMA",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(36, 20000, 90, 0.28, 0.05, [], 102),
        },
        {
            "name": "sales_volatile_trend",
            "description": "Upward trend buried in heavy noise",
            "query": "What is the monthly revenue trend and what will it be next month",
            "expected_model": "LINEAR_REGRESSION",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 45000, 1500, 0.0, 0.18, [], 103),
        },
        {
            "name": "sales_flat_noisy",
            "description": "No trend, no season, moderate noise",
            "query": "Show revenue per month over the last two years and predict ahead",
            "expected_model": "EXPONENTIAL_SMOOTHING",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 30000, 0, 0.0, 0.12, [], 104),
        },
        {
            "name": "short_series_five",
            "description": "Only 5 periods - below the trend-identifiability threshold",
            "query": "Show my expenses by month and forecast next month",
            "expected_model": "WEIGHTED_MOVING_AVERAGE",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(5, 8000, 200, 0.0, 0.05, [], 105),
        },
        {
            "name": "anomaly_spikes",
            "description": "Trending series with three injected outliers",
            "query": "Are there any unusual spikes in my monthly cloud spend",
            "expected_model": "LINEAR_REGRESSION",
            "expected_intent": "ANOMALY_DETECTION",
            **_ts(30, 12000, 300, 0.0, 0.05, [8, 17, 25], 106),
        },
        {
            "name": "anomaly_seasonal_spikes",
            "description": "Seasonal series with two outliers, higher noise",
            "query": "Detect anomalies in monthly support ticket resolution hours",
            "expected_model": "SARIMA",
            "expected_intent": "ANOMALY_DETECTION",
            **_ts(36, 900, 5, 0.25, 0.07, [11, 29], 107),
        },
        {
            "name": "whatif_reduction",
            "description": "Trending expenses with an explicit what-if clause",
            "query": "Show monthly expenses and predict next 3 months. What if I reduce spending by 20%?",
            "expected_model": "LINEAR_REGRESSION",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 5000, 180, 0.0, 0.05, [], 108),
        },
        {
            "name": "high_volatility",
            "description": "Extreme volatility, weak trend - tests the LOW_SIGNAL gate",
            "query": "Show monthly travel costs over time and forecast",
            "expected_model": "EXPONENTIAL_SMOOTHING",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 4000, 20, 0.0, 0.55, [], 109),
        },
        {
            "name": "quarterly_seasonal",
            "description": "Longer horizon monthly series with mild seasonality",
            "query": "Show total revenue month by month and project the next six months",
            "expected_model": "SARIMA",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(48, 75000, 400, 0.20, 0.06, [], 110),
        },
        {
            "name": "declining_linear",
            "description": "Clean downward trend",
            "query": "Show the monthly decline in active users and predict next quarter",
            "expected_model": "LINEAR_REGRESSION",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(24, 50000, -900, 0.0, 0.04, [], 111),
        },
        {
            "name": "tiny_series_four",
            "description": "Four periods - the absolute minimum",
            "query": "Show quarterly expenses and forecast the next quarter",
            "expected_model": "WEIGHTED_MOVING_AVERAGE",
            "expected_intent": "TREND_ANALYSIS",
            **_ts(4, 15000, 500, 0.0, 0.03, [], 112),
        },
    ]


def _ts(n, level, trend, seasonal, noise, anomalies, seed) -> dict:
    rows, truth = generate_timeseries(
        n_periods=n,
        level=level,
        trend=trend,
        seasonal_amplitude=seasonal,
        noise_pct=noise,
        anomaly_indices=anomalies,
        seed=seed,
    )
    return {"rows": rows, "ground_truth": truth, "schema": SCHEMA_DDL}


if __name__ == "__main__":
    import json

    suite = benchmark_suite()
    print(f"Generated {len(suite)} benchmark scenarios:")
    for s in suite:
        print(
            f"  {s['name']:<26} n={s['ground_truth']['n_periods']:<3} "
            f"anomalies={len(s['ground_truth']['anomaly_indices'])} "
            f"expect={s['expected_model']}"
        )
    print("\nSample rows from the first scenario:")
    print(json.dumps(suite[0]["rows"][:3], indent=2))
