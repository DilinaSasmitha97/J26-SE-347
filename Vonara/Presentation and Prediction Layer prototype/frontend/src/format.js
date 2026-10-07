// Display formatting only - every number shown comes from the API. These
// mirror summarization.fmt on the backend, so a tile and the claim behind it
// read the same.

export function fmt(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const v = Number(value);
  const a = Math.abs(v);
  if (a >= 1_000_000) return `${(v / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}M`;
  if (a >= 1000) return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (a >= 1) return v.toLocaleString(undefined, { maximumFractionDigits: 2, minimumFractionDigits: 2 });
  return v.toLocaleString(undefined, { maximumFractionDigits: 4 });
}

/** Stat-tile value: auto-compact (12.9K, 4.2M); the full value goes in a tooltip. */
export function compact(value) {
  if (value === null || value === undefined) return "—";
  const a = Math.abs(Number(value));
  if (a < 10_000) return fmt(value);
  return new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function pct(value) {
  if (value === null || value === undefined) return "—";
  const v = Number(value);
  // A true minus sign, so +15% and −15% line up in tiles.
  const text = Math.abs(v).toLocaleString(undefined, { maximumFractionDigits: 1 });
  return `${v > 0 ? "+" : v < 0 ? "−" : ""}${text}%`;
}

export function humanize(name = "") {
  const s = String(name).replace(/_/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// schemas.ForecastModel -> how a reader names it.
const MODEL_NAMES = {
  SARIMA: "SARIMA",
  LINEAR_REGRESSION: "Linear trend",
  EXPONENTIAL_SMOOTHING: "Damped Holt smoothing",
  WEIGHTED_MOVING_AVERAGE: "Weighted moving average",
  NAIVE: "Naive (last value)",
  SEASONAL_NAIVE: "Seasonal naive",
};

export function modelName(model) {
  if (!model) return "";
  return MODEL_NAMES[model] || humanize(String(model).toLowerCase());
}

export function lowerFirst(s = "") {
  return s.charAt(0).toLowerCase() + s.slice(1);
}
