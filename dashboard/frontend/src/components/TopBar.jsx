export default function TopBar({ state, connection }) {
  const dus = state?.config?.dus || [];
  const latest = state?.latest_run;
  const ueCount = state?.live_kpis?.ue_count ?? "n/a";

  return (
    <header className="flex items-center justify-between border-b border-white/10 bg-slate-950/60 px-6 py-4">
      <div>
        <p className="text-xs uppercase tracking-[0.25em] text-cyan-300">Topology</p>
        <h2 className="text-xl font-semibold text-white">{state?.topology || "f1"} / {state?.radio_mode || "rfsim"}</h2>
      </div>
      <div className="flex gap-4 text-sm">
        <Metric label="DUs" value={dus.length || 2} />
        <Metric label="Current UEs" value={ueCount} />
        <Metric label="Latest HO" value={latest?.estimated_interruption_ms ? `${latest.estimated_interruption_ms.toFixed(1)} ms` : "n/a"} />
        <Metric label="WS" value={connection} />
      </div>
    </header>
  );
}

function Metric({ label, value }) {
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="font-mono text-cyan-100">{value}</div>
    </div>
  );
}
