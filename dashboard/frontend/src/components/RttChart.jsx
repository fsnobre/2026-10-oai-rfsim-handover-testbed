import { Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { chartColors, tooltipStyle } from "../utils/chartTheme";

// Shared RTT line chart used by the Overview live-latency and interruption cards.
// Renders the common scaffold (container, axes, tooltip, primary `rtt_plot`
// series) and accepts `children` for per-chart annotations (ReferenceArea /
// ReferenceLine) and extra series.
export default function RttChart({
  data,
  xKey,
  xDomain,
  xTickFormatter,
  xLabel,
  yMax,
  heightClass = "h-64",
  dot = { r: 2 },
  tooltipFormatter,
  tooltipLabelFormatter,
  children,
}) {
  return (
    <div className={`mt-4 ${heightClass}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <XAxis
            dataKey={xKey}
            type="number"
            domain={xDomain}
            tickFormatter={xTickFormatter}
            stroke={chartColors.axis}
            minTickGap={28}
            label={xLabel}
          />
          <YAxis
            stroke={chartColors.axis}
            domain={[0, yMax]}
            allowDataOverflow={false}
            label={{ value: "RTT ms", angle: -90, position: "insideLeft", fill: chartColors.axis }}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={tooltipFormatter}
            labelFormatter={tooltipLabelFormatter}
          />
          {children}
          <Line
            type="linear"
            dataKey="rtt_plot"
            stroke={chartColors.series}
            strokeWidth={2}
            dot={dot}
            connectNulls={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
