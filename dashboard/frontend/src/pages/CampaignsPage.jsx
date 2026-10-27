import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import MetricCard from "../components/MetricCard";
import { useCapabilities } from "../hooks/useCapabilities";
import { apiGet, apiPost } from "../utils/api";
import { chartColors } from "../utils/chartTheme";

const DEFAULT_TOPOLOGIES = ["f1", "n2-monolithic", "n2-cu-du"];

function fmt(value, digits = 2, suffix = "") {
  return typeof value === "number" ? `${value.toFixed(digits)}${suffix}` : "Unavailable";
}

function pct(value) {
  return typeof value === "number" ? `${value.toFixed(2)}%` : "Unavailable";
}

function stat(stats, field, name) {
  const value = stats?.[field]?.[name];
  return typeof value === "number" ? value : null;
}

export default function CampaignsPage({ state, embedded = false }) {
  const { campaignId } = useParams();
  const { capabilities } = useCapabilities();
  const [campaigns, setCampaigns] = useState([]);
  const [comparison, setComparison] = useState(null);
  const [selected, setSelected] = useState(campaignId || null);
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const [message, setMessage] = useState(null);
  const [confirm, setConfirm] = useState(false);
  const [topology, setTopology] = useState("f1");
  const [count, setCount] = useState(5);

  useEffect(() => {
    refresh();
    // Run once on mount; refresh is stable enough for this dashboard's usage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (campaignId) setSelected(campaignId);
  }, [campaignId]);

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    apiGet(`/api/campaigns/${selected}`)
      .then((data) => setDetail(data.campaign))
      .catch((exc) => setError(String(exc)));
  }, [selected]);

  function refresh() {
    setError(null);
    apiGet("/api/campaigns")
      .then((data) => {
        const rows = data.campaigns || [];
        setCampaigns(rows);
        if (!selected && rows[0]) setSelected(rows[0].campaign_id);
      })
      .catch((exc) => setError(String(exc)));
    apiGet("/api/campaigns/compare")
      .then((data) => setComparison(data.comparison))
      .catch((exc) => setError(String(exc)));
  }

  const repeatedAction = capabilities?.available_actions?.find((item) => item.kind === "repeated_smoke_test");
  const actionsEnabled = Boolean(capabilities?.actions_enabled && repeatedAction?.enabled);
  const minCount = repeatedAction?.min_count ?? 1;
  const maxCount = repeatedAction?.max_count ?? 20;
  const topologies = repeatedAction?.allowed_topologies || DEFAULT_TOPOLOGIES;
  const runningJob = state?.actions?.running_job;
  const canLaunch = actionsEnabled && confirm && !runningJob;
  const selectedSummary = detail?.summary || campaigns.find((item) => item.campaign_id === selected) || {};
  const latest = state?.campaigns?.latest_summary || campaigns[0] || null;

  const chartRows = useMemo(() => (detail?.runs || []).map((row) => ({
    run_id: row.run_id,
    short: row.run_id?.slice(0, 14),
    interruption: row.estimated_interruption_ms,
    packet_loss: row.packet_loss_percent,
    rtt_avg: row.rtt_avg_ms,
  })), [detail]);

  async function launchRepeated() {
    setError(null);
    setMessage(null);
    try {
      const data = await apiPost("/api/actions/repeated-smoke-test", {
        confirm,
        topology,
        count: Number(count),
      });
      setMessage(`Started repeated smoke-test campaign: ${data.job.job_id}`);
      refresh();
    } catch (exc) {
      setError(String(exc));
      refresh();
    }
  }

  return (
    <div className={embedded ? "space-y-5" : "space-y-5 p-5"}>
      {(error || message) && (
        <section className={`card p-4 text-sm ${error ? "border-rose-400/30 text-rose-200" : "border-emerald-400/30 text-emerald-200"}`}>
          {error || message}
        </section>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-5">
        <MetricCard label="Campaigns" value={state?.campaigns?.campaign_count ?? campaigns.length} />
        <MetricCard label="Latest campaign" value={latest?.campaign_id || "None"} hint={latest?.topology} />
        <MetricCard label="Latest pass rate" value={pct(latest?.pass_rate_percent)} />
        <MetricCard label="Latest interruption p95" value={fmt(stat(latest?.statistics, "estimated_interruption_ms", "p95"), 2, " ms")} />
        <MetricCard label="Warnings" value={state?.campaigns?.warning_count ?? 0} />
      </div>

      <RepeatedLauncher
        actionsEnabled={actionsEnabled}
        disabledReason={repeatedAction?.reason}
        confirm={confirm}
        setConfirm={setConfirm}
        topology={topology}
        setTopology={setTopology}
        topologies={topologies}
        count={count}
        setCount={setCount}
        minCount={minCount}
        maxCount={maxCount}
        runningJob={runningJob}
        canLaunch={canLaunch}
        launchRepeated={launchRepeated}
      />

      <section className="card p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-white">Campaigns</h3>
            <p className="mt-1 text-sm text-slate-400">Repeated smoke-test groups discovered under results/repeated.</p>
          </div>
          <button type="button" onClick={refresh} className="rounded-xl bg-white/[0.06] px-3 py-1 text-sm text-slate-200">Refresh</button>
        </div>
        {campaigns.length ? (
          <div className="mt-4 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th className="py-2">Campaign</th>
                  <th>Topology</th>
                  <th>Runs</th>
                  <th>Pass rate</th>
                  <th>Interruption mean/p95</th>
                  <th>Loss mean/p95</th>
                  <th>RTT mean/p95</th>
                  <th>iperf mean</th>
                  <th>Start</th>
                  <th>End</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => (
                  <tr
                    key={campaign.campaign_id}
                    onClick={() => setSelected(campaign.campaign_id)}
                    className={`cursor-pointer border-t border-white/10 ${selected === campaign.campaign_id ? "bg-cyan-400/10" : "hover:bg-white/[0.04]"}`}
                  >
                    <td className="max-w-xs truncate py-2 font-mono text-cyan-100">{campaign.campaign_id}</td>
                    <td>{campaign.topology || "unknown"}</td>
                    <td>{campaign.run_count}</td>
                    <td>{pct(campaign.pass_rate_percent)}</td>
                    <td>{fmt(stat(campaign.statistics, "estimated_interruption_ms", "mean"), 2, " ms")} / {fmt(stat(campaign.statistics, "estimated_interruption_ms", "p95"), 2, " ms")}</td>
                    <td>{fmt(stat(campaign.statistics, "packet_loss_percent", "mean"), 3, "%")} / {fmt(stat(campaign.statistics, "packet_loss_percent", "p95"), 3, "%")}</td>
                    <td>{fmt(stat(campaign.statistics, "rtt_avg_ms", "mean"), 2, " ms")} / {fmt(stat(campaign.statistics, "rtt_avg_ms", "p95"), 2, " ms")}</td>
                    <td>{fmt(stat(campaign.statistics, "iperf_mbps", "mean"), 3, " Mbps")}</td>
                    <td className="font-mono text-xs">{campaign.start_time || "n/a"}</td>
                    <td className="font-mono text-xs">{campaign.end_time || "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-4 text-sm text-slate-400">No campaign artifacts found. Individual runs still appear under the Runs tab.</p>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="space-y-5">
          <CampaignDetails detail={detail} summary={selectedSummary} />
          <CampaignCharts rows={chartRows} />
          <ComparisonPanel comparison={comparison} />
        </section>
        <section className="space-y-5">
          <OutlierPanel outliers={detail?.outliers} />
          <Warnings warnings={detail?.warnings || []} />
        </section>
      </div>
    </div>
  );
}

function RepeatedLauncher(props) {
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Repeated smoke-test campaign</h3>
      <p className="mt-2 text-sm text-slate-400">
        Uses the trusted repeated smoke-test script. Actions remain disabled unless explicitly enabled in the backend.
      </p>
      {!props.actionsEnabled && (
        <p className="mt-3 rounded-xl border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100">
          Repeated campaign actions are unavailable. {props.disabledReason || "Set DASHBOARD_ENABLE_ACTIONS=true to enable controlled actions."}
        </p>
      )}
      <label className="mt-4 flex items-start gap-3 text-sm text-slate-300">
        <input type="checkbox" checked={props.confirm} onChange={(event) => props.setConfirm(event.target.checked)} className="mt-1" />
        <span>I understand this will run a repeated experiment campaign on the local OAI testbed.</span>
      </label>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <label className="text-sm text-slate-300">
          <span className="block text-xs text-slate-400">Topology</span>
          <select
            value={props.topology}
            onChange={(event) => props.setTopology(event.target.value)}
            className="mt-1 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          >
            {props.topologies.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="text-sm text-slate-300">
          <span className="block text-xs text-slate-400">Count</span>
          <input
            type="number"
            min={props.minCount}
            max={props.maxCount}
            value={props.count}
            onChange={(event) => props.setCount(event.target.value)}
            className="mt-1 w-28 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          />
        </label>
        <button
          type="button"
          disabled={!props.canLaunch}
          onClick={props.launchRepeated}
          className="rounded-xl bg-cyan-400/20 px-4 py-2 text-sm text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Start campaign
        </button>
        {props.runningJob && <span className="text-sm text-slate-400">Running job: {props.runningJob.job_id}</span>}
      </div>
    </section>
  );
}

function CampaignDetails({ detail, summary }) {
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Selected campaign</h3>
      {summary?.campaign_id ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
            <Detail label="Campaign" value={summary.campaign_id} />
            <Detail label="Topology" value={summary.topology} />
            <Detail label="Runs" value={summary.run_count} />
            <Detail label="Pass rate" value={pct(summary.pass_rate_percent)} />
          </div>
          <div className="mt-5 overflow-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-slate-400">
                <tr>
                  <th className="py-2">Run</th>
                  <th>Status</th>
                  <th>Triggered</th>
                  <th>Interruption</th>
                  <th>First ping</th>
                  <th>Loss</th>
                  <th>RTT avg</th>
                  <th>iperf</th>
                  <th>Warnings</th>
                </tr>
              </thead>
              <tbody>
                {(detail?.runs || []).map((run) => (
                  <tr key={`${run.path}-${run.run_id}`} className="border-t border-white/10">
                    <td className="max-w-xs truncate py-2 font-mono text-cyan-100">{run.run_id}</td>
                    <td>{run.status || "n/a"}</td>
                    <td>{run.handover_triggered === true ? "yes" : "no"}</td>
                    <td>{fmt(run.estimated_interruption_ms, 2, " ms")}</td>
                    <td>{fmt(run.first_ping_after_handover_ms, 2, " ms")}</td>
                    <td>{fmt(run.packet_loss_percent, 3, "%")}</td>
                    <td>{fmt(run.rtt_avg_ms, 2, " ms")}</td>
                    <td>{fmt(run.iperf_mbps, 3, " Mbps")}</td>
                    <td>{run.warnings_count || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p className="mt-3 text-sm text-slate-400">Select a campaign to inspect per-run details.</p>
      )}
    </section>
  );
}

function CampaignCharts({ rows }) {
  if (!rows.length) {
    return <section className="card p-5"><h3 className="text-lg font-semibold text-white">Campaign charts</h3><p className="mt-3 text-sm text-slate-400">No run metrics available for charts.</p></section>;
  }
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Campaign charts</h3>
      <div className="mt-4 grid gap-5 xl:grid-cols-3">
        <MiniLine title="Interruption by run" data={rows} dataKey="interruption" suffix=" ms" />
        <MiniLine title="Packet loss by run" data={rows} dataKey="packet_loss" suffix="%" />
        <MiniLine title="RTT avg by run" data={rows} dataKey="rtt_avg" suffix=" ms" />
      </div>
    </section>
  );
}

function MiniLine({ title, data, dataKey }) {
  return (
    <div>
      <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
      <div className="mt-3 h-56">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data.filter((row) => typeof row[dataKey] === "number")}>
            <CartesianGrid stroke={chartColors.grid} />
            <XAxis dataKey="short" stroke={chartColors.axis} />
            <YAxis stroke={chartColors.axis} />
            <Tooltip />
            <Line type="monotone" dataKey={dataKey} stroke={chartColors.series} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function ComparisonPanel({ comparison }) {
  const rows = comparison?.topologies || [];
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Topology comparison</h3>
      {rows.length ? (
        <div className="mt-4 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows.map((row) => ({
              topology: row.topology,
              pass_rate_percent: row.pass_rate_percent,
              interruption_p95: stat(row.statistics, "estimated_interruption_ms", "p95"),
            }))}>
              <CartesianGrid stroke={chartColors.grid} />
              <XAxis dataKey="topology" stroke={chartColors.axis} />
              <YAxis stroke={chartColors.axis} />
              <Tooltip />
              <Bar dataKey="pass_rate_percent" fill={chartColors.series} name="Pass rate %" />
              <Bar dataKey="interruption_p95" fill={chartColors.seriesAlt} name="Interruption p95 ms" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No comparison groups available.</p>
      )}
    </section>
  );
}

function OutlierPanel({ outliers }) {
  const sections = [
    ["Failed runs", outliers?.failed_runs],
    ["Missing handover trigger", outliers?.missing_handover_trigger],
    ["Missing ping metrics", outliers?.missing_ping_metrics],
    ["Highest interruption", outliers?.highest_interruption],
    ["Highest packet loss", outliers?.highest_packet_loss],
    ["Highest RTT avg", outliers?.highest_rtt_avg],
    ["Lowest iperf Mbps", outliers?.lowest_iperf_mbps],
  ];
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Failures and outliers</h3>
      <div className="mt-4 space-y-4">
        {sections.map(([title, rows]) => (
          <div key={title}>
            <h4 className="text-sm font-semibold text-slate-200">{title}</h4>
            {rows?.length ? (
              <div className="mt-2 space-y-1">
                {rows.slice(0, 5).map((row, index) => (
                  <div key={`${title}-${row.run_id}-${index}`} className="rounded-lg bg-black/20 p-2 text-xs text-slate-300">
                    <span className="font-mono text-cyan-100">{row.run_id}</span>
                    <span className="ml-2 text-slate-400">{row.status}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-1 text-xs text-slate-500">None observed.</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

function Warnings({ warnings }) {
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Artifact warnings</h3>
      {warnings.length ? (
        <ul className="mt-3 space-y-2 text-sm text-amber-100">
          {warnings.map((warning, index) => <li key={index} className="rounded-xl bg-amber-400/5 p-3">{warning}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No campaign artifact warnings for the selected campaign.</p>
      )}
    </section>
  );
}

function Detail({ label, value }) {
  return (
    <div className="rounded-xl bg-black/20 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 break-words font-mono text-cyan-100">{value ?? "Unavailable"}</div>
    </div>
  );
}
