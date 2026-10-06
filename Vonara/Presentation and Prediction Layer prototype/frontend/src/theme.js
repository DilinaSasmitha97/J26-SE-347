// Chart theme. Values are the validated reference palette of the data-viz
// method (categorical slots 1-3, status "critical", chart chrome), checked with
// its validator in both modes: every gate passes; light-mode aqua sits below
// 3:1 on the surface, so charts always carry a legend key with dash patterns
// and marker shapes, plus a table view (the "relief" rule).
//
// The backend's Vega-Lite specs keep their own colour constants - the API
// contract is not changed for the UI. themeSpec() maps each backend colour to
// the role it plays (history, forecast, scenario, anomaly, threshold) and
// swaps in this palette for the active mode.

import { humanize } from "./format.js";

export const PALETTE = {
  light: {
    surface: "#fcfcfb",
    ink: "#0b0b0b",
    inkSecondary: "#52514e",
    muted: "#898781",
    grid: "#e1e0d9",
    axis: "#c3c2b7",
    history: "#2a78d6",
    forecast: "#eb6834",
    scenario: "#1baf7a",
    anomaly: "#d03b3b",
    categorical: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  },
  dark: {
    surface: "#1a1a19",
    ink: "#ffffff",
    inkSecondary: "#c3c2b7",
    muted: "#898781",
    grid: "#2c2c2a",
    axis: "#383835",
    history: "#3987e5",
    forecast: "#d95926",
    scenario: "#199e70",
    anomaly: "#d03b3b",
    categorical: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  },
};

// visualization.COLORS on the backend -> the role each colour plays.
const BACKEND_ROLES = {
  "#4c78a8": "history",
  "#f58518": "forecast",
  "#d62728": "anomaly",
  "#54a24b": "scenario",
  "#b279a2": "muted",
};

export function currentMode() {
  if (typeof document !== "undefined") {
    const stamp = document.documentElement.getAttribute("data-theme");
    if (stamp === "light" || stamp === "dark") return stamp;
  }
  if (typeof window !== "undefined" && window.matchMedia) {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  return "light";
}

function recolor(node, palette) {
  if (Array.isArray(node)) return node.map((n) => recolor(n, palette));
  if (node && typeof node === "object") {
    const out = {};
    for (const [key, value] of Object.entries(node)) {
      if (key === "color" && typeof value === "string" && BACKEND_ROLES[value.toLowerCase()]) {
        out[key] = palette[BACKEND_ROLES[value.toLowerCase()]];
      } else {
        out[key] = recolor(value, palette);
      }
    }
    return out;
  }
  return node;
}

/** The backend spec with the palette for `mode`, and a Vega-Lite config. */
export function themeSpec(spec, mode = currentMode(), metaOverride = null) {
  const palette = PALETTE[mode];
  const meta = metaOverride || spec._meta || {};
  // A single series with overlays is fully described by the chart key the UI
  // draws above it; Vega's own legend would repeat part of it.
  const keyed = (meta.extension_rules_applied || []).length > 0 && !meta.color_field;
  const themed = recolor(spec, palette);
  delete themed._meta;
  // The card header names the chart (chartTitle); the backend title is the
  // question in title case, already shown above the result.
  delete themed.title;
  for (const layer of themed.layer || []) {
    // Filled markers sit on top of the line: a surface ring keeps them apart.
    if (layer.mark && layer.mark.type === "point" && layer.mark.filled) {
      layer.mark = { ...layer.mark, stroke: palette.surface, strokeWidth: 2 };
    }
  }
  if (keyed) {
    // An explicit legend on an encoding wins over config.legend.disable, so
    // switch those off too (the anomaly layer names its own legend).
    for (const layer of themed.layer || []) {
      for (const channel of Object.values(layer.encoding || {})) {
        if (channel && typeof channel === "object" && "legend" in channel) channel.legend = null;
      }
    }
  }
  themed.background = palette.surface;
  themed.width = "container";
  themed.config = {
    ...(themed.config || {}),
    font: 'system-ui, -apple-system, "Segoe UI", sans-serif',
    view: { stroke: null },
    range: { category: palette.categorical },
    title: { color: palette.ink, fontWeight: 600, fontSize: 14, anchor: "start" },
    axis: {
      labelColor: palette.muted,
      titleColor: palette.inkSecondary,
      gridColor: palette.grid,
      domainColor: palette.axis,
      tickColor: palette.axis,
      labelFontSize: 11,
      titleFontSize: 11.5,
      titleFontWeight: 500,
      labelPadding: 6,
      titlePadding: 10,
    },
    // Recessive chrome: horizontal grid only, no y domain line or ticks.
    axisX: { grid: false, tickSize: 4, labelOverlap: "greedy", labelSeparation: 10 },
    axisY: { domain: false, ticks: false },
    legend: { labelColor: palette.inkSecondary, titleColor: palette.inkSecondary, disable: keyed },
    line: { strokeWidth: 2 },
    point: { size: 64 },
    bar: { cornerRadiusEnd: 4 },
  };
  return themed;
}

/** A chart's name for its card header, from the encoding the backend chose. */
export function chartTitle(meta = {}) {
  const x = humanize(meta.x_field || "");
  const y = humanize(meta.y_field || "");
  const by = (field) => field.toLowerCase();
  switch (meta.chart_type) {
    case "histogram":
      return x ? `Distribution of ${by(x)}` : "Distribution";
    case "scatter":
      return x && y ? `${y} vs ${by(x)}` : "Relationship";
    case "pie":
    case "donut":
      return y && x ? `Share of ${by(y)} by ${by(x)}` : "Share";
    default:
      if (!y) return "Result";
      if (!x) return y;
      return meta.color_field ? `${y} by ${by(x)} and ${by(humanize(meta.color_field))}` : `${y} by ${by(x)}`;
  }
}

/**
 * The layers a chart carries, for the legend key. Identity is never colour
 * alone: each entry names its line style or marker shape too.
 */
export function chartKey(meta = {}, mode = currentMode(), spec = null) {
  const p = PALETTE[mode];
  const rules = meta.extension_rules_applied || [];
  const anomalyKinds = new Set();
  for (const layer of (spec && spec.layer) || []) {
    for (const row of (layer.data && layer.data.values) || []) {
      if (row && (row.dimension === "HISTORICAL" || row.dimension === "PREDICTIVE")) anomalyKinds.add(row.dimension);
    }
  }
  const key = [{ label: "History", color: p.history, style: "solid" }];
  if (rules.includes("R1_FORECAST_MEAN")) key.push({ label: "Forecast", color: p.forecast, style: "dashed" });
  if (rules.includes("R2_CONFIDENCE_BAND")) key.push({ label: "Forecast range", color: p.forecast, style: "band" });
  if (rules.includes("R4_SCENARIO_OVERLAY")) key.push({ label: "What-if scenario", color: p.scenario, style: "dotted" });
  if (rules.includes("R3_ANOMALY_MARKERS")) {
    if (anomalyKinds.has("HISTORICAL") || anomalyKinds.size === 0) {
      key.push({ label: "Past anomaly", color: p.anomaly, style: "triangle" });
    }
    if (anomalyKinds.has("PREDICTIVE")) key.push({ label: "Projected breach", color: p.anomaly, style: "diamond" });
  }
  if (rules.includes("R3_THRESHOLD_RULES")) key.push({ label: "Normal range", color: p.muted, style: "rule" });
  return key;
}
