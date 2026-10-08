// A small inline icon set (stroke icons on a 20px grid). Decorative unless a
// title is given; meaning is always also carried by text next to the icon.

const PATHS = {
  trend: "M3 14l4-4 3 3 7-7M13 6h4v4",
  bar: "M4 16V9M10 16V4M16 16v-5",
  distribution: "M3 16h14M5 16v-3M8 16V8M11 16V5M14 16v-6",
  scatter: "M5 14h.01M8 9h.01M11 12h.01M14 6h.01M16 10h.01",
  table: "M3 5h14v10H3zM3 9h14M8 5v10",
  figure: "M10 3v14M6 7h6a2 2 0 010 4H8a2 2 0 000 4h6",
  database: "M4 5c0-1.1 2.7-2 6-2s6 .9 6 2-2.7 2-6 2-6-.9-6-2zm0 0v10c0 1.1 2.7 2 6 2s6-.9 6-2V5M4 10c0 1.1 2.7 2 6 2s6-.9 6-2",
  search: "M9 15a6 6 0 100-12 6 6 0 000 12zM13.5 13.5L17 17",
  sparkle: "M10 3l1.6 4.4L16 9l-4.4 1.6L10 15l-1.6-4.4L4 9l4.4-1.6zM15.5 13.5l.6 1.4 1.4.6-1.4.6-.6 1.4-.6-1.4-1.4-.6 1.4-.6z",
  check: "M4 10l4 4 8-8",
  x: "M5 5l10 10M15 5L5 15",
  alert: "M10 4l7 12H3zM10 9v3M10 14.5h.01",
  info: "M10 17a7 7 0 100-14 7 7 0 000 14zM10 9v4M10 6.5h.01",
  lock: "M6 9V7a4 4 0 018 0v2M5 9h10v7H5z",
  sliders: "M4 6h7M15 6h1M4 14h1M9 14h7M13 4v4M7 12v4",
  layers: "M10 3l7 4-7 4-7-4zM3 11l7 4 7-4",
  clock: "M10 17a7 7 0 100-14 7 7 0 000 14zM10 6v4l3 2",
  sun: "M10 13a3 3 0 100-6 3 3 0 000 6zM10 2v2M10 16v2M2 10h2M16 10h2M4.3 4.3l1.4 1.4M14.3 14.3l1.4 1.4M4.3 15.7l1.4-1.4M14.3 5.7l1.4-1.4",
  moon: "M16 12.5A6.5 6.5 0 017.5 4a6.5 6.5 0 108.5 8.5z",
  monitor: "M3 4h14v9H3zM7 17h6M10 13v4",
  chevron: "M7 8l3 3 3-3",
  shield: "M10 3l6 2v5c0 3.5-2.6 6.2-6 7-3.4-.8-6-3.5-6-7V5z",
  arrowUp: "M10 16V4M5 9l5-5 5 5",
  arrowDown: "M10 4v12M5 11l5 5 5-5",
  arrowRight: "M4 10h12M11 5l5 5-5 5",
  grid: "M3.5 3.5h5v5h-5zM11.5 3.5h5v5h-5zM3.5 11.5h5v5h-5zM11.5 11.5h5v5h-5z",
  gear: "M10 12.5a2.5 2.5 0 100-5 2.5 2.5 0 000 5zM10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4",
  history: "M3.5 10a6.5 6.5 0 106.5-6.5c-2.4 0-4.4 1.3-5.6 3.2M3.5 3.5v3.2h3.2M10 6.5V10l2.5 1.5",
  chevronLeft: "M12 5l-5 5 5 5",
  chevronRight: "M8 5l5 5-5 5",
  refresh: "M16 10a6 6 0 11-1.8-4.3M16 3.5v3.2h-3.2",
  sparkleAsk: "M4 10h7M8 6l4 4-4 4M15 5v10",
};

export default function Icon({ name, size = 18, title, className = "" }) {
  const d = PATHS[name];
  if (!d) return null;
  return (
    <svg
      className={`icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      <path d={d} />
    </svg>
  );
}

/**
 * The component's mark: observed history as a solid line, then the forecast
 * as a dashed one, with a dot where the projection starts. Drawn in
 * currentColor so it sits on the brand tile (white) or anywhere else.
 */
export function BrandMark({ size = 20 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none"
      stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 17l4.5-5 3.5 3 4-5.5" />
      <path d="M15 9.5l5.5-5" strokeDasharray="2.2 2.6" />
      <circle cx="15" cy="9.5" r="1.6" fill="currentColor" stroke="none" />
      <path d="M3 21h18" strokeOpacity="0.45" />
    </svg>
  );
}
