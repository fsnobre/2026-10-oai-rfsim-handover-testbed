import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import Detail from "./Detail";
import EventTimeline from "./EventTimeline";
import MessageFlow from "./MessageFlow";
import { chartColors, tooltipStyle } from "../utils/chartTheme";

function ms(value) {
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "Unavailable";
}

function pct(value) {
  return typeof value === "number" ? `${value.toFixed(3)}%` : "Unavailable";
}

function bool(value) {
  if (typeof value === "boolean") return value ? "yes" : "no";
  return value ?? "Unavailable";
}

function PingChart({ samples = [], markers = {} }) {
  const data = samples.map((sample) => ({
    label: sample.timestamp_utc?.slice(11, 19),
    rtt_ms: sample.rtt_ms,
  }));
  const trigger = markers?.handover_trigger_start?.timestamp;
  const firstAfter = markers?.first_ping_after_handover?.timestamp;

  return (
    <div className="card p-5">
      <h3 className="text-lg font-semibold text-white">Ping RTT across the run</h3>
      {data.length ? (
        <div className="mt-4 h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="label" stroke={chartColors.axis} minTickGap={28} />
              <YAxis stroke={chartColors.axis} label={{ value: "RTT ms", angle: -90, position: "insideLeft", fill: chartColors.axis }} />
              <Tooltip contentStyle={tooltipStyle} />
              {trigger && (
                <ReferenceLine
                  x={trigger.slice(11, 19)}
                  stroke={chartColors.annotation}
                  strokeDasharray="4 4"
                  label={{ value: "trigger", position: "top", fill: chartColors.annotation, fontSize: 11 }}
                />
              )}
              {firstAfter && (
                <ReferenceLine
                  x={firstAfter.slice(11, 19)}
                  stroke={chartColors.seriesPositive}
                  strokeDasharray="4 4"
                  label={{ value: "1st ping", position: "top", fill: chartColors.seriesPositive, fontSize: 11 }}
                />
              )}
              <Line type="monotone" dataKey="rtt_ms" stroke={chartColors.series} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No ping samples available for this run.</p>
      )}
    </div>
  );
}

/**
 * One run, end to end: summary metrics, the ping trace with handover markers, the
 * normalized event timeline, and the reconstructed message flow.
 *
 * Runs and Handover used to be separate pages that both listed every run and both
 * plotted its RTT. This is the single view, fed by /api/handover/runs/{id}, which
 * already returns a superset of what either page rendered.
 */
export default function RunDetail({ run, summary, loading }) {
  if (loading) {
    return (
      <div className="card p-5">
        <p className="text-sm text-slate-400">Loading run…</p>
      </div>
    );
  }
  if (!run && !summary?.run_id) {
    return (
      <div className="card p-5">
        <h3 className="text-lg font-semibold text-white">Run details</h3>
        <p className="mt-3 text-sm text-slate-400">Select a run to inspect its metrics and handover trace.</p>
      </div>
    );
  }

  const info = run?.summary || summary || {};

  return (
    <div className="space-y-5">
      <div className="card p-5">
        <h3 className="text-lg font-semibold text-white">Run details</h3>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Detail label="Run" value={info.run_id || summary?.run_id || "Unavailable"} />
          <Detail label="Topology" value={info.topology || "Unavailable"} />
          <Detail label="Status" value={info.status || "Unavailable"} />
          <Detail label="Triggered" value={bool(info.handover_triggered)} />
          <Detail label="Interruption" value={ms(info.estimated_interruption_ms)} />
          <Detail label="First ping after" value={ms(info.first_ping_after_handover_ms)} />
          <Detail label="Packet loss" value={pct(info.packet_loss_percent)} />
          <Detail label="RTT min/avg/max" value={`${ms(info.rtt_min_ms)} / ${ms(info.rtt_avg_ms)} / ${ms(info.rtt_max_ms)}`} />
          <Detail label="iperf" value={typeof info.iperf_mbps === "number" ? `${info.iperf_mbps.toFixed(3)} Mbps` : info.iperf_status || "Unavailable"} />
          <Detail label="Start" value={info.start_time || "Unavailable"} />
          <Detail label="End" value={info.end_time || "Unavailable"} />
          <Detail label="Events" value={info.event_count ?? run?.events?.length ?? "Unavailable"} />
        </div>
      </div>

      <PingChart samples={run?.ping_samples} markers={run?.ping_interruption_markers} />

      <div className="grid gap-5 xl:grid-cols-2">
        <EventTimeline events={run?.events || []} />
        <MessageFlow steps={run?.message_flow || []} />
      </div>

      {run?.warnings?.length ? (
        <div className="card p-5">
          <h3 className="text-lg font-semibold text-white">Artifact warnings</h3>
          <ul className="mt-3 space-y-2 text-sm text-amber-100">
            {run.warnings.map((warning, index) => (
              <li key={index} className="rounded-xl bg-amber-400/5 p-3">{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
