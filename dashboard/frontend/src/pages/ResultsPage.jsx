import { useEffect, useState } from "react";
import { NavLink, useNavigate, useParams } from "react-router-dom";
import CampaignsPage from "./CampaignsPage";
import RunDetail from "../components/RunDetail";
import MetricCard from "../components/MetricCard";
import { apiGet } from "../utils/api";

function fmt(value, suffix = "") {
  return typeof value === "number" ? `${value.toFixed(2)}${suffix}` : "Unavailable";
}

function pct(value) {
  return typeof value === "number" ? `${value.toFixed(3)}%` : "Unavailable";
}

const TABS = [
  { label: "Runs", to: "/results/runs" },
  { label: "Campaigns", to: "/results/campaigns" },
];

function SubTabs() {
  return (
    <div className="flex gap-2">
      {TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) =>
            `rounded-xl px-4 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
              isActive ? "bg-cyan-400/20 text-cyan-100" : "bg-white/[0.04] text-slate-300 hover:bg-white/[0.08]"
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </div>
  );
}

/**
 * Experiment results: individual runs and repeated-run campaigns.
 *
 * Runs and Handover were previously separate top-level pages that listed the same
 * artifacts and plotted the same RTT trace. They are one view here, fed by
 * /api/handover/runs/{id}, which already returns summary, normalized events, message
 * flow, interruption markers and bounded ping samples in a single response.
 */
export default function ResultsPage({ state, view = "runs" }) {
  if (view === "campaigns") {
    return (
      <div className="space-y-5 p-5">
        <SubTabs />
        <CampaignsPage state={state} embedded />
      </div>
    );
  }
  return <RunsView state={state} />;
}

function RunsView({ state }) {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [runs, setRuns] = useState([]);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiGet("/api/runs")
      .then((data) => {
        const rows = data.runs || [];
        setRuns(rows);
        if (!runId && rows[0]) navigate(`/results/runs/${rows[0].run_id}`, { replace: true });
      })
      .catch((exc) => setError(String(exc)));
    // Fetch the run list once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!runId) {
      setDetail(null);
      return;
    }
    setLoading(true);
    apiGet(`/api/handover/runs/${encodeURIComponent(runId)}`)
      .then((data) => setDetail(data.run))
      .catch((exc) => setError(String(exc)))
      .finally(() => setLoading(false));
  }, [runId]);

  const listed = runs.find((run) => run.run_id === runId) || {};
  const latest = state?.latest_run || runs[0] || {};

  return (
    <div className="space-y-5 p-5">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <SubTabs />
        <span className="text-sm text-slate-400">{runs.length} run(s)</span>
      </div>

      {error && <div className="card border-rose-400/30 p-4 text-sm text-rose-200">{error}</div>}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Latest run" value={latest.run_id || "None"} hint={latest.topology} />
        <MetricCard label="Latest interruption" value={fmt(latest.estimated_interruption_ms, " ms")} />
        <MetricCard label="Latest packet loss" value={pct(latest.packet_loss_percent)} />
        <MetricCard label="Latest RTT avg" value={fmt(latest.rtt_avg_ms, " ms")} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[380px_minmax(0,1fr)]">
        <section className="card p-5">
          <h3 className="text-lg font-semibold text-white">Experiment runs</h3>
          <div className="mt-4 max-h-[720px] space-y-2 overflow-auto">
            {runs.length ? runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                aria-current={runId === run.run_id ? "true" : undefined}
                onClick={() => navigate(`/results/runs/${run.run_id}`)}
                className={`block w-full rounded-xl p-3 text-left text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70 ${
                  runId === run.run_id ? "bg-cyan-400/20" : "bg-black/20 hover:bg-white/[0.08]"
                }`}
              >
                <div className="truncate font-mono text-cyan-100">{run.run_id}</div>
                <div className="mt-1 text-slate-400">
                  {run.topology || "unknown"} · {run.status || "missing summary"}
                </div>
              </button>
            )) : <p className="text-sm text-slate-400">No experiment runs found.</p>}
          </div>
        </section>

        <RunDetail run={detail} summary={listed} loading={loading} />
      </div>
    </div>
  );
}
