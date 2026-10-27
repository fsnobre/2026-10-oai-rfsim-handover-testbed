import { useEffect, useState } from "react";
import MetricCard from "../components/MetricCard";
import { useCapabilities } from "../hooks/useCapabilities";
import { apiGet, apiPost, getApiToken, setApiToken } from "../utils/api";

const TOPOLOGIES = ["f1", "n2-monolithic", "n2-cu-du"];

export default function ControlsPage({ state }) {
  const { capabilities, reload: reloadCapabilities } = useCapabilities();
  const [jobs, setJobs] = useState([]);
  const [runningJob, setRunningJob] = useState(null);
  const [selectedJobId, setSelectedJobId] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);
  const [confirm, setConfirm] = useState(false);
  const [topology, setTopology] = useState("f1");
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const actions = state?.actions;
  const enabled = Boolean(capabilities?.actions_enabled);
  const wsRunningJob = actions?.running_job;
  const effectiveRunningJob = wsRunningJob || runningJob;
  const disabledReason = capabilities?.available_actions?.find((item) => !item.enabled)?.reason;

  useEffect(() => {
    refresh();
    // Run once on mount; refresh is stable enough for this dashboard's usage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedJobId) {
      setSelectedJob(null);
      return;
    }
    apiGet(`/api/actions/jobs/${selectedJobId}`)
      .then((data) => setSelectedJob(data.job))
      .catch((exc) => setError(String(exc)));
  }, [selectedJobId]);

  function refresh() {
    setError(null);
    reloadCapabilities();
    apiGet("/api/actions/jobs")
      .then((data) => {
        setJobs(data.jobs || []);
        setRunningJob(data.running_job || null);
        if (!selectedJobId && data.jobs?.[0]) setSelectedJobId(data.jobs[0].job_id);
      })
      .catch((exc) => setError(String(exc)));
  }

  async function submit(path, payload) {
    setError(null);
    setMessage(null);
    try {
      const data = await apiPost(path, payload);
      setMessage(`Started ${data.job.kind}: ${data.job.job_id}`);
      setSelectedJobId(data.job.job_id);
      refresh();
    } catch (exc) {
      setError(String(exc));
      refresh();
    }
  }

  const canSubmit = enabled && confirm && !effectiveRunningJob;

  return (
    <div className="space-y-5 p-5">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <MetricCard label="Actions" value={enabled ? "Enabled" : "Disabled"} hint={enabled ? "controlled actions available" : disabledReason} />
        <MetricCard label="Running job" value={effectiveRunningJob?.job_id || "None"} hint={effectiveRunningJob?.status} />
        <MetricCard label="Recent jobs" value={jobs.length} />
        <MetricCard label="Concurrency" value="Single job" hint="dashboard-started actions" />
      </div>

      {!enabled && (
        <section className="card border-amber-400/30 p-5">
          <h3 className="text-lg font-semibold text-amber-100">Actions are disabled</h3>
          <p className="mt-2 text-sm text-slate-300">
            Actions are disabled because the backend was started without{" "}
            <span className="font-mono text-cyan-100">DASHBOARD_ENABLE_ACTIONS=true</span>.
            Changing the shell variable after startup is not enough; restart or recreate the backend with actions enabled.
          </p>
          <div className="mt-4 space-y-3 text-sm">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Backend-only recreate</div>
              <pre className="mt-2 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-cyan-100">DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up -d --force-recreate dashboard-backend</pre>
            </div>
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-slate-400">Full dashboard restart</div>
              <pre className="mt-2 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-cyan-100">DASHBOARD_ENABLE_ACTIONS=true docker compose -f dashboard/docker-compose.dashboard.yml up --build</pre>
            </div>
          </div>
        </section>
      )}

      <RepoRootWarning environment={capabilities?.environment} />

      {(error || message) && (
        <section className={`card p-4 text-sm ${error ? "border-rose-400/30 text-rose-200" : "border-emerald-400/30 text-emerald-200"}`}>
          {error || message}
        </section>
      )}

      <section className="card p-5">
        <h3 className="text-lg font-semibold text-white">Safety controls</h3>
        <div className="mt-4 grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
          <Safety label="Arbitrary commands" value={capabilities?.safety?.arbitrary_commands === false ? "blocked" : "unknown"} />
          <Safety label="Shell execution" value={capabilities?.safety?.shell_execution === false ? "blocked" : "unknown"} />
          <Safety label="Config editing" value={capabilities?.safety?.config_editing === false ? "blocked" : "unknown"} />
          <Safety label="Arbitrary lifecycle" value={capabilities?.safety?.container_lifecycle === false ? "blocked" : "unknown"} />
          <Safety label="Concurrency" value={capabilities?.safety?.single_job_concurrency ? "single job" : "unknown"} />
          <Safety label="Output tails" value={capabilities?.safety?.bounded_output_tails ? "bounded" : "unknown"} />
        </div>
      </section>

      <RuntimeChecks checks={capabilities?.runtime_checks} />

      <ApiTokenCard onSaved={refresh} />

      <section className="card p-5">
        <h3 className="text-lg font-semibold text-white">Experiment actions</h3>
        <label className="mt-4 flex items-start gap-3 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={confirm}
            onChange={(event) => setConfirm(event.target.checked)}
            className="mt-1"
          />
          <span>I understand this will run an experiment action on the local OAI testbed.</span>
        </label>

        <p className="mt-3 text-sm text-slate-400">
          Handover triggering and interruption capture live on Overview, where they follow the
          detected topology.
        </p>

        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
            <h4 className="font-semibold text-white">Start smoke test</h4>
            <p className="mt-2 text-sm text-slate-400">Runs the trusted smoke-test script for an allowed topology.</p>
            <select
              value={topology}
              onChange={(event) => setTopology(event.target.value)}
              className="mt-4 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              {TOPOLOGIES.map((item) => <option key={item} value={item}>{item}</option>)}
            </select>
            <button
              type="button"
              disabled={!canSubmit}
              onClick={() => submit("/api/actions/smoke-test", { confirm, topology })}
              className="ml-3 mt-4 rounded-xl bg-cyan-400/20 px-4 py-2 text-sm text-cyan-100 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Start smoke test
            </button>
          </div>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <section className="card p-5">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white">Jobs</h3>
            <button type="button" onClick={refresh} className="rounded-xl bg-white/[0.06] px-3 py-1 text-sm text-slate-200">Refresh</button>
          </div>
          <div className="mt-4 max-h-[560px] space-y-2 overflow-auto">
            {jobs.length ? jobs.map((job) => (
              <button
                key={job.job_id}
                type="button"
                onClick={() => setSelectedJobId(job.job_id)}
                className={`block w-full rounded-xl p-3 text-left text-sm ${
                  selectedJobId === job.job_id ? "bg-cyan-400/20" : "bg-black/20 hover:bg-white/[0.08]"
                }`}
              >
                <div className="font-mono text-cyan-100">{job.job_id}</div>
                <div className="mt-1 text-slate-400">{job.kind} · {job.status}</div>
              </button>
            )) : <p className="text-sm text-slate-400">No dashboard action jobs yet.</p>}
          </div>
        </section>

        <JobDetails job={selectedJob || effectiveRunningJob} />
      </div>
    </div>
  );
}

function ApiTokenCard({ onSaved }) {
  const [token, setToken] = useState(getApiToken());
  const [saved, setSaved] = useState(false);

  function save() {
    setApiToken(token.trim());
    setSaved(true);
    onSaved?.();
  }

  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">API token</h3>
      <p className="mt-2 text-sm text-slate-400">
        Only needed when the backend is started with{" "}
        <span className="font-mono text-cyan-100">DASHBOARD_API_TOKEN</span> set. The token is stored
        in this browser and attached to action requests and the live WebSocket. Reload the page after
        changing it so the live connection re-authenticates.
      </p>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          type="password"
          value={token}
          onChange={(event) => {
            setToken(event.target.value);
            setSaved(false);
          }}
          placeholder="bearer token"
          className="min-w-[240px] flex-1 rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-sm text-slate-100"
        />
        <button
          type="button"
          onClick={save}
          className="rounded-xl bg-cyan-400/20 px-4 py-2 text-sm text-cyan-100"
        >
          Save token
        </button>
        <button
          type="button"
          onClick={() => {
            setToken("");
            setApiToken("");
            setSaved(true);
            onSaved?.();
          }}
          className="rounded-xl bg-white/[0.06] px-4 py-2 text-sm text-slate-200"
        >
          Clear
        </button>
        {saved && <span className="text-sm text-emerald-200">Saved — reload to apply to the live socket.</span>}
      </div>
    </section>
  );
}

// Compose-spawning actions are refused when the backend's repository path is not the
// path the host Docker daemon sees, because the host would silently create empty
// directories in place of the OAI config files. Show the fix rather than a bare refusal.
function RepoRootWarning({ environment }) {
  if (!environment || environment.repo_root_host_visible !== false) return null;
  return (
    <section className="card border-rose-400/30 p-5">
      <h3 className="text-lg font-semibold text-rose-100">Repository path is not visible to the host Docker daemon</h3>
      <p className="mt-2 text-sm text-slate-300">
        Deploy, teardown, and smoke-test actions are blocked. The backend runs actions from{" "}
        <span className="font-mono text-cyan-100">{environment.repo_root}</span>, but the host daemon sees that content at{" "}
        <span className="font-mono text-cyan-100">{environment.host_path}</span>. Compose stacks started from here would
        resolve their bind mounts against a path that does not exist on the host, where Docker silently creates empty
        directories in place of the OAI config files.
      </p>
      <p className="mt-3 text-sm text-slate-300">Restart the dashboard with the host-actions override:</p>
      <pre className="mt-2 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-cyan-100">{`DASHBOARD_HOST_REPO_ROOT="$(pwd)" DASHBOARD_ENABLE_ACTIONS=true \\
  docker compose -f dashboard/docker-compose.dashboard.yml \\
    -f dashboard/docker-compose.dashboard.host-actions.example.yml up --build`}</pre>
    </section>
  );
}

function Safety({ label, value }) {
  return (
    <div className="rounded-xl bg-black/20 p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="mt-1 font-mono text-cyan-100">{value}</div>
    </div>
  );
}

function RuntimeChecks({ checks }) {
  const entries = Object.entries(checks || {});
  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">Action runtime checks</h3>
      <p className="mt-2 text-sm text-slate-400">
        Actions may fail if required runtime tools are missing or the results mount is not writable.
      </p>
      {entries.length ? (
        <div className="mt-4 grid grid-cols-1 gap-3 text-sm md:grid-cols-5">
          {entries.map(([key, value]) => (
            <div key={key} className={`rounded-xl border p-3 ${
              value ? "border-emerald-400/20 bg-emerald-400/5" : "border-amber-400/30 bg-amber-400/5"
            }`}>
              <div className="text-xs text-slate-400">{key}</div>
              <div className={`mt-1 font-mono ${value ? "text-emerald-200" : "text-amber-200"}`}>
                {value ? "ok" : "unavailable"}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">Runtime checks are not available from this backend.</p>
      )}
    </section>
  );
}

function JobDetails({ job }) {
  if (!job) {
    return (
      <section className="card p-5">
        <h3 className="text-lg font-semibold text-white">Job details</h3>
        <p className="mt-3 text-sm text-slate-400">Select a job to view details.</p>
      </section>
    );
  }
  return (
    <section className="space-y-5">
      <div className="card p-5">
        <h3 className="text-lg font-semibold text-white">Job details</h3>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-3">
          <Safety label="Job ID" value={job.job_id} />
          <Safety label="Kind" value={job.kind} />
          <Safety label="Status" value={job.status} />
          <Safety label="Started" value={job.started_at || "n/a"} />
          <Safety label="Finished" value={job.finished_at || "n/a"} />
          <Safety label="Return code" value={job.returncode ?? "n/a"} />
        </div>
        {job.warnings?.length ? (
          <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100">
            {job.warnings.map((warning, index) => <div key={index}>{warning}</div>)}
          </div>
        ) : null}
      </div>
      <Tail title="stdout tail" lines={job.stdout_tail} />
      <Tail title="stderr tail" lines={job.stderr_tail} />
    </section>
  );
}

function Tail({ title, lines }) {
  return (
    <div className="card p-5">
      <h3 className="text-lg font-semibold text-white">{title}</h3>
      {lines?.length ? (
        <pre className="mt-4 max-h-80 overflow-auto rounded-xl bg-black/40 p-3 text-xs text-slate-200">{lines.join("\n")}</pre>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No {title} available.</p>
      )}
    </div>
  );
}
