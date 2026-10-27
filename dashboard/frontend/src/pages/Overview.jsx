import { useEffect, useRef, useState } from "react";
import { Line, ReferenceArea, ReferenceLine } from "recharts";
import Sidebar from "../components/Sidebar";
import TopologyDiagram from "../components/TopologyDiagram";
import IdleTopology from "../components/IdleTopology";
import CellConfigPanel from "../components/CellConfigPanel";
import UeContextCard from "../components/UeContextCard";
import Pill from "../components/Pill";
import Detail from "../components/Detail";
import RttChart from "../components/RttChart";
import { actionSupportsTopology, useCapabilities } from "../hooks/useCapabilities";
import { apiGet, apiPost } from "../utils/api";
import { chartColors } from "../utils/chartTheme";
import { buildInterruptionResult, runIdFromTail } from "../utils/interruption";
import { buildLatencyWindow } from "../utils/latency";
import { deploymentState } from "../utils/deployment";

const LIFECYCLE_TOPOLOGIES = ["f1", "n2-monolithic", "n2-cu-du"];

function topologyLabel(topology) {
  if (topology === "f1") return "F1";
  if (topology === "n2-monolithic") return "N2 monolithic";
  if (topology === "n2-cu-du") return "N2 CU/DU";
  return topology || "handover";
}

function isN2(topology) {
  return typeof topology === "string" && topology.startsWith("n2");
}

export default function Overview({ state, connection }) {
  const warnings = state?.warnings || [];
  const overview = state?.overview || {};
  const uePaths = overview.ue_paths || [];
  const activeDu = uePaths.find((item) => item.serving_du)?.serving_du || null;
  const liveLatency = overview.live_latency || state?.live_latency || {};
  const topology = state?.topology || "f1";
  const radioMode = state?.radio_mode || "rfsim";
  const containers = state?.containers || [];
  const deployment = deploymentState(containers);
  return (
    <div className="flex min-h-[calc(100vh-64px)] bg-slate-950">
      <Sidebar containers={containers} deployed={deployment.deployed} />
      <main className="flex min-w-0 flex-1 flex-col">
        <div className="grid min-h-0 flex-1 gap-5 p-5 xl:grid-cols-[minmax(520px,1fr)_420px]">
          <div className="space-y-5 min-w-0">
            <HeroSummary
              warnings={warnings}
              connection={connection}
              topology={topology}
              radioMode={radioMode}
              detection={state?.topology_detection}
              deployed={deployment.deployed}
            />
            {deployment.deployed ? (
              <TopologyDiagram containers={containers} config={state?.config || {}} activeDu={activeDu} topology={topology} />
            ) : (
              <IdleTopology state={deployment} />
            )}
            {deployment.deployed ? <MobilityCard handover={state?.handover || {}} /> : null}
            {deployment.deployed ? <CellConfigPanel config={state?.config || {}} topology={topology} /> : null}
          </div>
          <div className="space-y-5 min-w-0">
            <TopologyLifecycle state={state} />
            <OverviewTrigger state={state} />
            <InterruptionMeasurement state={state} />
            {deployment.deployed ? <LiveLatencyChart liveLatency={liveLatency} /> : null}
            {deployment.deployed ? <UeContextCard liveKpis={state?.live_kpis || {}} /> : null}
          </div>
        </div>
      </main>
    </div>
  );
}

// How the monitored topology was resolved. Detection is stated, not implied: an
// undetected fallback must not look like an observation.
function DetectionPill({ detection }) {
  if (!detection) return null;
  if (detection.mode === "pinned") return <Pill tone="warn">pinned</Pill>;
  if (detection.detected) return <Pill tone="good">detected</Pill>;
  return <Pill tone="warn">not detected</Pill>;
}

function HeroSummary({ warnings, connection, topology, radioMode, detection, deployed = true }) {
  const radioPrefix = radioMode === "rfsim" ? "RFsim " : radioMode === "usrp" ? "USRP " : "";
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="text-xs uppercase tracking-[0.2em] text-slate-500">Operator overview</div>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            {deployed ? `${topologyLabel(topology)} ${radioPrefix}handover cockpit` : "Handover cockpit — idle"}
          </h2>
          <p className="mt-2 max-w-3xl text-sm text-slate-400">
            {deployed
              ? "Health is grouped in the Handover Monitor. The topology highlights the parsed serving DU when CU logs expose it."
              : "No testbed is deployed. Deploy a topology to start collecting live telemetry."}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {deployed ? <DetectionPill detection={detection} /> : <Pill tone="neutral">idle</Pill>}
          <Pill tone={connection === "connected" ? "good" : "warn"}>WS {connection}</Pill>
        </div>
      </div>
      {detection?.warning || detection?.note ? (
        <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          {detection.warning || detection.note}
        </div>
      ) : null}
      {warnings.length ? (
        <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-100">
          {warnings.length} warning(s). Open Results or Controls for details.
        </div>
      ) : null}
    </section>
  );
}

// "Never probed" is not "probed and failed", so the telnet pill reports which of the two
// it is. Passive polling is disabled by default and some topologies have no telnet node;
// neither is a fault, and neither should read as a degraded stack.
const READINESS = {
  ready: { tone: "good", label: "ready" },
  degraded: { tone: "warn", label: "degraded" },
  unavailable: { tone: "bad", label: "unavailable" },
  not_observed: { tone: "neutral", label: "not observed" },
};

const TELNET = {
  reachable: { tone: "good", label: "telnet reachable" },
  unreachable: { tone: "warn", label: "telnet unreachable" },
  polling_disabled: { tone: "neutral", label: "telnet not polled" },
  no_endpoint: { tone: "neutral", label: "no telnet endpoint" },
};

// Live mobility state from bounded log reads. Past handovers are measured artifacts and
// live under Results; this is only what is happening now.
function MobilityCard({ handover }) {
  const events = handover.recent_events || [];
  const readiness = READINESS[handover.readiness] || { tone: "neutral", label: handover.readiness || "Unavailable" };
  const telnet = TELNET[handover.cu_telnet_status]
    || (handover.cu_telnet_reachable ? TELNET.reachable : TELNET.unreachable);
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">Live mobility</h3>
          <p className="mt-1 text-sm text-slate-400">
            Readiness and recent handover-related log lines from the running stack.
          </p>
        </div>
        <div className="flex gap-2">
          <Pill tone={readiness.tone}>{readiness.label}</Pill>
          <Pill tone={telnet.tone}>{telnet.label}</Pill>
        </div>
      </div>
      {handover.cu_telnet_status === "polling_disabled" ? (
        <p className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          Passive telnet polling is off by default — repeated probes have destabilised some OAI CU builds — so the
          control node is not observed rather than known to be down. Enable with{" "}
          <span className="font-mono text-cyan-100">DASHBOARD_ENABLE_TELNET_POLLING=true</span>. Explicit handover
          actions do not depend on it.
        </p>
      ) : null}
      {handover.cu_telnet_status === "no_endpoint" ? (
        <p className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          This topology exposes no telnet control endpoint, so live mobility context is not available for it.
        </p>
      ) : null}
      {events.length ? (
        <div className="mt-4 max-h-64 space-y-2 overflow-auto">
          {events.slice(-8).reverse().map((event, index) => (
            <div key={index} className="rounded-xl bg-black/20 p-3 text-sm">
              <span className="font-mono text-cyan-100">{event.node || "unknown"}</span>
              <span className="ml-3 text-slate-300">{event.category}</span>
              <p className="mt-1 break-words text-slate-400">{event.details}</p>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-400">No live handover events observed from bounded log reads.</p>
      )}
    </section>
  );
}

function LiveLatencyChart({ liveLatency }) {
  const samples = liveLatency?.samples || [];
  const visibleSlots = 90;
  const { visibleSamples, data, yMax } = buildLatencyWindow(samples, visibleSlots);
  const latest = liveLatency?.latest || {};
  const delivered = liveLatency?.delivered_count ?? samples.filter((item) => item.reachable).length;
  const lost = liveLatency?.lost_count ?? samples.filter((item) => item.reachable === false).length;
  return (
    <section className="card p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">Live UE latency</h3>
          <p className="mt-1 text-sm text-slate-400">
            One bounded ICMP probe per update from UE tunnel to EXT-DN. Gaps/red dots are missed probes during interruption.
          </p>
        </div>
        <div className="flex gap-2">
          {liveLatency?.probing === false ? (
            <Pill tone="warn">not probing</Pill>
          ) : (
            <Pill tone={latest?.reachable ? "good" : "warn"}>{latest?.reachable ? "delivering" : "not delivering"}</Pill>
          )}
          <Pill>{typeof latest?.rtt_ms === "number" ? `${latest.rtt_ms.toFixed(2)} ms` : "RTT unavailable"}</Pill>
        </div>
      </div>
      {visibleSamples.length ? (
        <RttChart
          data={data}
          xKey="slot"
          xDomain={[0, visibleSlots - 1]}
          xTickFormatter={(slot) => data.find((item) => item.slot === slot)?.label || ""}
          yMax={yMax}
          heightClass="h-72"
          dot={{ r: 3 }}
          tooltipFormatter={(value, name, item) => {
            if (item?.payload?.placeholder) return ["", ""];
            if (name === "rtt_plot") return [`${Number(value).toFixed(2)} ms`, "RTT"];
            if (name === "loss_marker") return [item?.payload?.error || "probe missed", "Loss"];
            return [value, name];
          }}
          tooltipLabelFormatter={(_label, items) => {
            const payload = items?.[0]?.payload;
            return payload?.label ? `sample ${payload.label}` : "";
          }}
        >
          <Line
            type="linear"
            dataKey="loss_marker"
            stroke="transparent"
            dot={{ r: 4, fill: chartColors.loss, stroke: chartColors.loss }}
            activeDot={{ r: 5, fill: chartColors.loss, stroke: chartColors.lossActive }}
            connectNulls={false}
            isAnimationActive={false}
          />
        </RttChart>
      ) : (
        <p className="mt-4 text-sm text-slate-400">
          {liveLatency?.skip_reason
            || "No live latency samples yet. Samples start once the dashboard backend can reach Docker and the UE container."}
        </p>
      )}
      <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-4">
        <Detail label="Delivered" value={delivered} />
        <Detail label="Missed" value={lost} />
        <Detail label="Probe" value={`${liveLatency?.interface || "oaitun_ue1"} → ${liveLatency?.target || "192.168.71.135"}`} />
        <Detail label="Source" value={liveLatency?.source || "docker_exec_ping"} />
      </div>
    </section>
  );
}

const MAX_POLLS = 200;
const POLL_INTERVAL_MS = 1500;

function InterruptionMeasurement({ state }) {
  const { capabilities } = useCapabilities();
  const [phase, setPhase] = useState("idle"); // idle | capturing | loading | done | error
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const pollRef = useRef(null);

  const actions = state?.actions || {};
  const topology = state?.topology || "f1";
  const enabled = Boolean(capabilities?.actions_enabled ?? actions.enabled);
  const supported = actionSupportsTopology(capabilities, "measure_interruption", topology);
  const running = actions.running_job;
  const busy = phase === "capturing" || phase === "loading";
  const canSubmit = enabled && supported && !running && !busy;

  useEffect(() => () => {
    if (pollRef.current) clearTimeout(pollRef.current);
  }, []);

  async function loadRun(runId) {
    setPhase("loading");
    const data = await apiGet(`/api/runs/${encodeURIComponent(runId)}`);
    if (!data.run) throw new Error(`Capture run ${runId} was not found.`);
    setResult(buildInterruptionResult(data.run));
    setPhase("done");
  }

  async function poll(jobId, attempt) {
    try {
      const { job } = await apiGet(`/api/actions/jobs/${encodeURIComponent(jobId)}`);
      const status = job?.status;
      if (status === "succeeded") {
        const runId = runIdFromTail(job.stdout_tail);
        if (!runId) throw new Error("Capture finished but did not report a run directory.");
        await loadRun(runId);
        return;
      }
      if (status === "failed" || status === "timed_out") {
        const detail =
          (job.stderr_tail || []).slice(-3).join(" ") ||
          (job.warnings || []).join(" ") ||
          status;
        throw new Error(`Capture ${status}: ${detail}`);
      }
      if (attempt >= MAX_POLLS) throw new Error("Timed out waiting for the capture to finish.");
      pollRef.current = setTimeout(() => poll(jobId, attempt + 1), POLL_INTERVAL_MS);
    } catch (exc) {
      setError(String(exc.message || exc));
      setPhase("error");
    }
  }

  async function start() {
    setError(null);
    setResult(null);
    setPhase("capturing");
    try {
      const { job } = await apiPost("/api/actions/measure-interruption", { confirm: true });
      poll(job.job_id, 0);
    } catch (exc) {
      setError(String(exc.message || exc));
      setPhase("error");
    }
  }

  const headline =
    result?.interruptionMs != null ? `${Number(result.interruptionMs).toFixed(1)} ms` : "—";

  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Handover interruption</h3>
          <p className="mt-1 text-sm text-slate-400">
            Runs a 10 ms ICMP burst around a triggered handover and plots the user-plane outage — the gap
            the ~1 Hz live probe can’t resolve.
          </p>
        </div>
        <Pill tone={result?.interruptionMs != null ? "good" : "neutral"}>{headline}</Pill>
      </div>
      <button
        type="button"
        disabled={!canSubmit}
        onClick={start}
        className="mt-4 w-full rounded-xl bg-cyan-400/20 px-4 py-3 text-sm font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {phase === "capturing"
          ? "Capturing… (triggering handover)"
          : phase === "loading"
          ? "Loading trace…"
          : "Measure handover interruption"}
      </button>
      <div className="mt-3 text-xs text-slate-400">
        {!enabled && "Actions disabled. Start backend with DASHBOARD_ENABLE_ACTIONS=true."}
        {enabled && !supported && `Interruption capture is not available for ${topologyLabel(topology)}.`}
        {enabled && supported && !busy && "Captures ~2 s baseline, fires the trigger, then ~4 s of recovery."}
      </div>
      {error && (
        <div className="mt-3 rounded-xl border border-rose-400/30 p-3 text-sm text-rose-200">{error}</div>
      )}
      {result && result.data.length ? (
        <>
          <RttChart
            data={result.data}
            xKey="seq"
            xDomain={["dataMin", "dataMax"]}
            xLabel={{ value: "icmp_seq", position: "insideBottom", offset: -2, fill: chartColors.axis }}
            yMax={result.yMax}
            heightClass="h-64"
            dot={false}
            tooltipFormatter={(value) => [`${Number(value).toFixed(2)} ms`, "RTT"]}
            tooltipLabelFormatter={(seq) => `icmp_seq ${seq}`}
          >
            {result.gapStart != null && result.gapEnd != null && (
              <ReferenceArea
                x1={result.gapStart}
                x2={result.gapEnd}
                fill={chartColors.loss}
                fillOpacity={0.18}
                stroke={chartColors.loss}
                strokeOpacity={0.35}
              />
            )}
            {result.gapEnd != null && (
              <ReferenceLine
                x={result.gapEnd}
                stroke={chartColors.annotation}
                strokeDasharray="4 4"
                label={{ value: "trigger", position: "top", fill: chartColors.annotation, fontSize: 11 }}
              />
            )}
          </RttChart>
          <div className="mt-3 grid grid-cols-2 gap-3 text-xs sm:grid-cols-3">
            <Detail label="Interruption" value={headline} />
            <Detail
              label="First reply after"
              value={result.firstAfterMs != null ? `${Number(result.firstAfterMs).toFixed(1)} ms` : "—"}
            />
            <Detail
              label="Packet loss"
              value={result.packetLoss != null ? `${result.packetLoss}%` : "—"}
            />
          </div>
          {result.seamless ? (
            <div className="mt-3 rounded-xl border border-emerald-400/30 bg-emerald-400/5 p-2 text-xs text-emerald-100">
              0% loss with the estimate within one probe interval and no missing sequence numbers — no measurable
              user-plane outage (seamless handover). The few-ms figure is the gap between adjacent probes, not an outage.
            </div>
          ) : result.packetLoss != null && result.packetLoss > 0 ? (
            <div className="mt-3 rounded-xl border border-amber-400/30 bg-amber-400/5 p-2 text-xs text-amber-100">
              Missing sequence numbers ({result.packetLoss}% loss) — this gap is a real user-plane interruption.
            </div>
          ) : null}
        </>
      ) : phase === "done" ? (
        <p className="mt-4 text-sm text-slate-400">
          Capture completed but produced no plottable samples. Check that the UE data plane was up.
        </p>
      ) : null}
    </section>
  );
}

function TopologyLifecycle({ state }) {
  const { capabilities } = useCapabilities();
  const [selected, setSelected] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(null); // "deploy" | "teardown" | null

  const actions = state?.actions || {};
  const activeTopology = state?.topology || "f1";
  const topology = selected ?? (LIFECYCLE_TOPOLOGIES.includes(activeTopology) ? activeTopology : "f1");
  const enabled = Boolean(capabilities?.actions_enabled ?? actions.enabled);
  const running = actions.running_job;
  const deploySupported = actionSupportsTopology(capabilities, "deploy_topology", topology);
  const canSubmit = enabled && deploySupported && !running && !pending;

  async function run(kind, path) {
    setError(null);
    setMessage(null);
    setPending(kind);
    try {
      const data = await apiPost(path, { confirm: true, topology });
      setMessage(`Started ${data.job.kind}: ${data.job.job_id}`);
    } catch (exc) {
      setError(String(exc));
    } finally {
      setPending(null);
    }
  }

  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Deploy / teardown</h3>
          <p className="mt-1 text-sm text-slate-400">
            Bring a full stack up (5GC core + RAN) or tear it down. Switch topologies without leaving Overview.
          </p>
        </div>
        <Pill tone={enabled ? "good" : "warn"}>{enabled ? "Enabled" : "Disabled"}</Pill>
      </div>
      <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-100">
        Deploy runs <span className="font-mono">up.sh</span> (starts containers, waits for the UE data plane — can take
        minutes). Teardown runs <span className="font-mono">down.sh</span>. Only one topology can run at a time — tear the
        current one down before deploying another.
      </div>
      <label className="mt-4 block text-xs uppercase tracking-[0.18em] text-slate-400">Topology</label>
      <select
        value={topology}
        onChange={(event) => setSelected(event.target.value)}
        disabled={Boolean(running) || Boolean(pending)}
        className="mt-2 w-full rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100 disabled:opacity-40"
      >
        {LIFECYCLE_TOPOLOGIES.map((item) => (
          <option key={item} value={item}>{topologyLabel(item)}</option>
        ))}
      </select>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => run("deploy", "/api/actions/deploy-topology")}
          className="rounded-xl bg-emerald-400/20 px-4 py-3 text-sm font-semibold text-emerald-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending === "deploy" ? "Deploying…" : `Deploy ${topologyLabel(topology)}`}
        </button>
        <button
          type="button"
          disabled={!canSubmit}
          onClick={() => run("teardown", "/api/actions/teardown-topology")}
          className="rounded-xl bg-rose-400/20 px-4 py-3 text-sm font-semibold text-rose-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {pending === "teardown" ? "Tearing down…" : "Teardown"}
        </button>
      </div>
      <div className="mt-3 text-xs text-slate-400">
        {!enabled && "Actions disabled. Start backend with DASHBOARD_ENABLE_ACTIONS=true."}
        {enabled && !deploySupported && `Deploy is not available for ${topologyLabel(topology)}.`}
        {enabled && running && `A job is running: ${running.job_id}. Wait for it to finish.`}
      </div>
      {(message || error) && (
        <div className={`mt-3 rounded-xl border p-3 text-sm ${error ? "border-rose-400/30 text-rose-200" : "border-emerald-400/30 text-emerald-200"}`}>
          {error || message}
        </div>
      )}
    </section>
  );
}

function OverviewTrigger({ state }) {
  const { capabilities } = useCapabilities();
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const actions = state?.actions || {};
  const topology = state?.topology || "f1";
  const enabled = Boolean(capabilities?.actions_enabled ?? actions.enabled);
  const supported = actionSupportsTopology(capabilities, "trigger_handover", topology);
  const running = actions.running_job;
  const canSubmit = enabled && supported && !running;

  async function trigger() {
    setError(null);
    setMessage(null);
    try {
      const data = await apiPost("/api/actions/trigger-handover", { confirm: true });
      setMessage(`Started ${data.job.kind}: ${data.job.job_id}`);
    } catch (exc) {
      setError(String(exc));
    }
  }

  return (
    <section className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-white">Quick handover</h3>
          <p className="mt-1 text-sm text-slate-400">Control action only. Use smoke tests for measured interruption traces.</p>
        </div>
        <Pill tone={enabled ? "good" : "warn"}>{enabled ? "Enabled" : "Disabled"}</Pill>
      </div>
      <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/5 p-3 text-sm text-amber-100">
        This runs immediately on the local testbed. Use only while the {topologyLabel(topology)} stack is intentionally active.
      </div>
      {isN2(topology) && (
        <div className="mt-3 rounded-xl border border-white/10 bg-black/20 p-3 text-xs text-slate-300">
          N2 handover moves the UE to the target cell. Triggering again in the same direction has no effect until the
          topology is reset — use repeated smoke tests (RESET_BETWEEN_RUNS=1) on the Controls page for repeated N2 runs.
        </div>
      )}
      <button
        type="button"
        disabled={!canSubmit}
        onClick={trigger}
        className="mt-4 w-full rounded-xl bg-cyan-400/20 px-4 py-3 text-sm font-semibold text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Trigger {topologyLabel(topology)} handover
      </button>
      <div className="mt-3 text-xs text-slate-400">
        {!enabled && "Actions disabled. Start backend with DASHBOARD_ENABLE_ACTIONS=true."}
        {enabled && !supported && `Quick trigger is not available for ${topologyLabel(topology)}.`}
        {running && `Running job: ${running.job_id}`}
      </div>
      {(message || error) && (
        <div className={`mt-3 rounded-xl border p-3 text-sm ${error ? "border-rose-400/30 text-rose-200" : "border-emerald-400/30 text-emerald-200"}`}>
          {error || message}
        </div>
      )}
    </section>
  );
}

