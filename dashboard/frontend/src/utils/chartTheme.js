// Single source of truth for chart colors so Recharts usage stays consistent
// across pages. JSX chart code should reference these instead of raw hex.

export const chartColors = {
  axis: "#94a3b8", // slate-400 — axis lines, ticks, and label text
  grid: "#1e293b", // slate-800 — grid lines
  series: "#22d3ee", // cyan — primary series (RTT)
  seriesAlt: "#f59e0b", // amber — secondary series
  seriesPositive: "#22c55e", // green — throughput / positive series
  loss: "#fb7185", // rose — packet loss / outage
  lossActive: "#fecdd3", // rose-200 — active loss marker
  annotation: "#fbbf24", // amber-400 — trigger / event annotation
  tooltipBg: "#020617", // slate-950 — tooltip background
  tooltipBorder: "rgba(34,211,238,0.25)", // cyan tooltip border
};

// Shared Recharts <Tooltip contentStyle={...}> value.
export const tooltipStyle = {
  background: chartColors.tooltipBg,
  border: `1px solid ${chartColors.tooltipBorder}`,
  borderRadius: "12px",
};
