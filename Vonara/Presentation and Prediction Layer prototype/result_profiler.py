"""
Result-Set Profiler.

The analyzer describes what was *asked*; this module describes what actually
*came back* from Member 2's masked result pipeline. Both signals are needed:
intent alone cannot choose an encoding (a TREND over 400 points is a line, over
2 points it is a KPI delta), and prediction feasibility is a property of the
data, not of the question.

Produces a `ResultProfile` consumed by visualization.py and prediction.py.
"""

import math
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime

from schemas import ColumnRole, Granularity

# Date formats accepted from a SQL driver or a JSON payload, in priority order.
_DATE_FORMATS = [
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y",
    "%m/%d/%Y", "%Y/%m/%d", "%Y-%m", "%b %Y", "%B %Y", "%Y",
]

_PERIOD_RE = re.compile(r"^\s*(\d{4})[-\s]?Q([1-4])\s*$", re.IGNORECASE)
_QUARTER_ONLY_RE = re.compile(r"^\s*Q([1-4])\s*$", re.IGNORECASE)


@dataclass
class ColumnProfile:
    name: str
    role: str = ColumnRole.UNSUPPORTED.value
    inferred_type: str = "string"     # number | date | string | boolean
    non_null: int = 0
    null_count: int = 0
    distinct_count: int = 0
    is_monotonic: bool = False
    min_value: object = None
    max_value: object = None
    mean: float = None
    std: float = None
    sample_values: list = field(default_factory=list)


@dataclass
class ResultProfile:
    row_count: int = 0
    column_count: int = 0
    columns: list = field(default_factory=list)      # list[ColumnProfile]
    temporal_column: str = ""
    granularity: str = Granularity.NONE.value
    measure_columns: list = field(default_factory=list)
    dimension_columns: list = field(default_factory=list)
    is_time_series: bool = False
    is_regular_interval: bool = False
    has_gaps: bool = False
    warnings: list = field(default_factory=list)

    def column(self, name: str):
        for c in self.columns:
            if c.name == name:
                return c
        return None

    def to_dict(self) -> dict:
        return {
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [asdict(c) for c in self.columns],
            "temporal_column": self.temporal_column,
            "granularity": self.granularity,
            "measure_columns": self.measure_columns,
            "dimension_columns": self.dimension_columns,
            "is_time_series": self.is_time_series,
            "is_regular_interval": self.is_regular_interval,
            "has_gaps": self.has_gaps,
            "warnings": self.warnings,
        }


# ==========================================================================
# Value coercion
# ==========================================================================


def parse_date(value):
    """Best-effort parse to datetime. Returns None when the value is not a date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "year") and hasattr(value, "month") and not isinstance(value, str):
        try:
            return datetime(value.year, value.month, getattr(value, "day", 1))
        except (TypeError, ValueError):
            return None

    s = str(value).strip()
    if not s:
        return None

    m = _PERIOD_RE.match(s)
    if m:  # "2024-Q3"
        return datetime(int(m.group(1)), (int(m.group(2)) - 1) * 3 + 1, 1)

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_number(value):
    """Parse a numeric value, tolerating currency symbols and thousands separators."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if (isinstance(value, float) and math.isnan(value)) else float(value)
    s = str(value).strip().replace(",", "")
    s = re.sub(r"^[\$£€₹]\s*", "", s)
    if s.endswith("%"):
        s = s[:-1]
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ==========================================================================
# Column typing
# ==========================================================================

# Fraction of non-null values that must parse for a column to take that type.
_TYPE_THRESHOLD = 0.80
# A categorical column must have at most this many distinct values, and they
# must cover a reasonable share of rows - otherwise it is an identifier.
_MAX_DIMENSION_CARDINALITY = 30
_IDENTIFIER_UNIQUENESS = 0.90

# Below this many distinct values, the uniqueness ratio carries no information:
# an aggregated result is unique on its grouping column by construction. Set at
# 12 because that is roughly where a categorical axis stops being legible as
# discrete bars anyway, so a false DIMENSION here costs nothing downstream.
_LOW_CARDINALITY_FLOOR = 12


def _profile_column(name: str, values: list, declared_type: str = None) -> ColumnProfile:
    non_null_vals = [v for v in values if v is not None and str(v).strip() != ""]
    prof = ColumnProfile(
        name=name,
        non_null=len(non_null_vals),
        null_count=len(values) - len(non_null_vals),
        sample_values=[v for v in non_null_vals[:5]],
    )
    if not non_null_vals:
        prof.role = ColumnRole.UNSUPPORTED.value
        return prof

    distinct = {str(v) for v in non_null_vals}
    prof.distinct_count = len(distinct)

    lowered = {str(v).strip().lower() for v in non_null_vals}
    if lowered <= {"true", "false", "0", "1", "yes", "no"} and len(lowered) <= 2:
        prof.inferred_type = "boolean"
        prof.role = ColumnRole.BOOLEAN.value
        return prof

    dates = [parse_date(v) for v in non_null_vals]
    date_ratio = sum(d is not None for d in dates) / len(non_null_vals)

    numbers = [parse_number(v) for v in non_null_vals]
    num_ratio = sum(n is not None for n in numbers) / len(non_null_vals)

    name_l = name.lower()
    looks_temporal_by_name = any(
        h in name_l for h in ("date", "month", "year", "quarter", "week", "day",
                              "period", "time", "_at", "_on")
    )

    # A 4-digit year parses as both a date and a number; the column name breaks
    # the tie, otherwise we prefer the numeric reading.
    if date_ratio >= _TYPE_THRESHOLD and (looks_temporal_by_name or num_ratio < _TYPE_THRESHOLD):
        valid = [d for d in dates if d is not None]
        prof.inferred_type = "date"
        prof.role = ColumnRole.TEMPORAL.value
        prof.min_value = min(valid).isoformat()
        prof.max_value = max(valid).isoformat()
        prof.is_monotonic = all(
            a <= b for a, b in zip(valid, valid[1:])
        )
        return prof

    if num_ratio >= _TYPE_THRESHOLD:
        valid = [n for n in numbers if n is not None]
        prof.inferred_type = "number"
        prof.min_value = min(valid)
        prof.max_value = max(valid)
        prof.mean = sum(valid) / len(valid)
        if len(valid) > 1:
            var = sum((x - prof.mean) ** 2 for x in valid) / (len(valid) - 1)
            prof.std = math.sqrt(var)
        else:
            prof.std = 0.0
        prof.is_monotonic = all(a <= b for a, b in zip(valid, valid[1:]))

        uniqueness = prof.distinct_count / len(non_null_vals)
        is_int_like = all(float(v).is_integer() for v in valid)
        if (
            (name_l == "id" or name_l.endswith("_id") or name_l.endswith("id"))
            and is_int_like
            and uniqueness > 0.5
        ):
            prof.role = ColumnRole.IDENTIFIER.value
        else:
            prof.role = ColumnRole.MEASURE.value
        return prof

    # Textual.
    prof.inferred_type = "string"
    uniqueness = prof.distinct_count / len(non_null_vals)

    # Uniqueness alone cannot separate a category from a key on an aggregated
    # result. A GROUP BY makes its grouping column unique *by construction*, so
    # "one row per department" scores uniqueness 1.0 exactly like a primary key
    # would - and treating it as a key leaves the most common charting shape
    # with no categorical axis at all. Below the floor, only the column name is
    # evidence of a key; above it, high uniqueness means what it usually means.
    looks_like_key = (
        name_l in ("id", "key", "code", "uuid", "guid")
        or name_l.endswith(("_id", "_key", "_code", "_uuid", "_no", "_num"))
    )
    is_categorical = (
        prof.distinct_count <= _MAX_DIMENSION_CARDINALITY
        and not looks_like_key
        and (
            uniqueness < _IDENTIFIER_UNIQUENESS
            or prof.distinct_count <= _LOW_CARDINALITY_FLOOR
        )
    )
    prof.role = (
        ColumnRole.DIMENSION.value if is_categorical else ColumnRole.IDENTIFIER.value
    )
    prof.min_value = min(distinct)
    prof.max_value = max(distinct)
    return prof


# ==========================================================================
# Temporal structure
# ==========================================================================

# Median gap (days) -> granularity. Bounds are generous because real business
# data has ragged month lengths and skipped weekends.
_GRANULARITY_BANDS = [
    (0.0, 0.09, Granularity.HOUR),
    (0.09, 3.0, Granularity.DAY),
    (3.0, 12.0, Granularity.WEEK),
    (12.0, 45.0, Granularity.MONTH),
    (45.0, 135.0, Granularity.QUARTER),
    (135.0, 100000.0, Granularity.YEAR),
]


def infer_granularity(dates: list) -> tuple:
    """
    Infer sampling granularity from consecutive gaps.

    Returns (granularity, is_regular, has_gaps).
    """
    valid = sorted(d for d in dates if d is not None)
    if len(valid) < 2:
        return Granularity.NONE.value, False, False

    gaps = [
        (b - a).total_seconds() / 86400.0
        for a, b in zip(valid, valid[1:])
        if (b - a).total_seconds() > 0
    ]
    if not gaps:
        return Granularity.NONE.value, False, False

    gaps.sort()
    median = gaps[len(gaps) // 2]

    granularity = Granularity.NONE
    for low, high, g in _GRANULARITY_BANDS:
        if low <= median < high:
            granularity = g
            break

    # Regular when every gap sits within 35% of the median - loose enough to
    # accept 28/30/31-day months, tight enough to reject genuine irregularity.
    tolerance = max(median * 0.35, 0.5)
    is_regular = all(abs(g - median) <= tolerance for g in gaps)
    has_gaps = any(g > median * 1.8 for g in gaps)
    return granularity.value, is_regular, has_gaps


# ==========================================================================
# Public API
# ==========================================================================


def profile_results(rows: list, schema_types: dict = None, analysis=None) -> ResultProfile:
    """
    Profile a masked result set.

    Args:
        rows:         list of dicts, as delivered by Member 2's PII-masked pipeline.
        schema_types: optional {column: sql_type} hints from the source schema.
        analysis:     optional QueryAnalysis; its temporal_field is preferred
                      when several columns could serve as the time axis.
    """
    profile = ResultProfile()
    if not rows:
        profile.warnings.append("EMPTY_RESULT_SET")
        return profile

    if not isinstance(rows[0], dict):
        profile.warnings.append("UNSUPPORTED_ROW_FORMAT")
        return profile

    # Preserve first-seen column order across ragged rows.
    columns = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    profile.row_count = len(rows)
    profile.column_count = len(columns)
    schema_types = schema_types or {}

    for name in columns:
        values = [row.get(name) for row in rows]
        profile.columns.append(_profile_column(name, values, schema_types.get(name)))

    temporal_candidates = [c.name for c in profile.columns if c.role == ColumnRole.TEMPORAL.value]
    profile.measure_columns = [c.name for c in profile.columns if c.role == ColumnRole.MEASURE.value]
    profile.dimension_columns = [
        c.name for c in profile.columns
        if c.role in (ColumnRole.DIMENSION.value, ColumnRole.BOOLEAN.value)
    ]

    if temporal_candidates:
        preferred = getattr(analysis, "temporal_field", "") if analysis else ""
        profile.temporal_column = (
            preferred if preferred in temporal_candidates else temporal_candidates[0]
        )
        dates = [parse_date(row.get(profile.temporal_column)) for row in rows]
        granularity, regular, gaps = infer_granularity(dates)
        profile.granularity = granularity
        profile.is_regular_interval = regular
        profile.has_gaps = gaps
        profile.is_time_series = bool(profile.measure_columns) and profile.row_count >= 2
        if gaps:
            profile.warnings.append("IRREGULAR_TIME_AXIS")
    else:
        # A pure ordinal period label ("Q1".."Q4", "Jan".."Dec") is still a
        # usable sequence for charting, though not for date arithmetic.
        for c in profile.columns:
            if c.role == ColumnRole.DIMENSION.value and all(
                _QUARTER_ONLY_RE.match(str(v)) for v in c.sample_values
            ):
                profile.temporal_column = c.name
                profile.granularity = Granularity.QUARTER.value
                profile.is_time_series = bool(profile.measure_columns)
                profile.warnings.append("ORDINAL_PERIOD_AXIS")
                break

    if not profile.measure_columns:
        profile.warnings.append("NO_MEASURE_COLUMN")

    return profile


def extract_series(rows: list, time_column: str, value_column: str) -> tuple:
    """
    Extract a clean, chronologically sorted (dates, values) series.

    Rows with an unparseable date or value are dropped - the count of dropped
    rows is what the readiness classifier reports as data loss.
    """
    pairs = []
    for row in rows:
        d = parse_date(row.get(time_column))
        v = parse_number(row.get(value_column))
        if d is not None and v is not None:
            pairs.append((d, v))
    pairs.sort(key=lambda p: p[0])
    if not pairs:
        return [], []
    dates, values = zip(*pairs)
    return list(dates), list(values)


def extract_ordinal_series(rows: list, label_column: str, value_column: str) -> tuple:
    """Extract (labels, values) preserving row order, for non-date sequences."""
    labels, values = [], []
    for row in rows:
        v = parse_number(row.get(value_column))
        if v is not None:
            labels.append(str(row.get(label_column)))
            values.append(v)
    return labels, values
