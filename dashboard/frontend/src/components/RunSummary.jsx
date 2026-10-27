export default function RunSummary({ latestRun, warnings = [], telnet, freshness = {} }) {
  return (
    <aside className="w-96 shrink-0 space-y-4 p-5">
      <section className="card p-4">
        <h3 className="text-lg font-semibold text-white">Latest run</h3>
        {latestRun ? (
          <div className="mt-3 space-y-2 text-sm">
            <Row label="Run" value={latestRun.run_id} />
            <Row label="Status" value={latestRun.status} />
            <Row label="HO interruption" value={formatMs(latestRun.estimated_interruption_ms)} />
            <Row label="Loss" value={formatPct(latestRun.packet_loss_percent)} />
            <Row label="RTT avg" value={formatMs(latestRun.rtt_avg_ms)} />
            <Row label="iperf" value={latestRun.iperf_mbps ? `${latestRun.iperf_mbps.toFixed(3)} Mbps` : latestRun.iperf_status || "n/a"} />
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-400">No run summaries found.</p>
        )}
      </section>
      <section className="card p-4">
        <h3 className="text-lg font-semibold text-white">CU telnet</h3>
        <p className="mt-2 text-sm text-slate-300">
          {telnet?.cu?.reachable ? "Reachable" : "Unavailable"} at {telnet?.cu?.host || "192.168.70.150"}:{telnet?.cu?.port || 9090}
        </p>
        {telnet?.cu?.warning && <p className="mt-2 text-xs text-amber-300">{telnet.cu.warning}</p>}
      </section>
      <section className="card p-4">
        <h3 className="text-lg font-semibold text-white">Source freshness</h3>
        <div className="mt-2 space-y-1 text-xs text-slate-400">
          {Object.entries(freshness).map(([source, timestamp]) => (
            <div key={source} className="flex justify-between gap-2">
              <span>{source}</span>
              <span className="font-mono">{timestamp ? timestamp.slice(11, 19) : "n/a"}</span>
            </div>
          ))}
        </div>
      </section>
      {warnings.length > 0 && (
        <section className="card border-amber-400/20 p-4">
          <h3 className="text-lg font-semibold text-amber-200">Warnings</h3>
          <ul className="mt-2 max-h-48 space-y-1 overflow-auto text-xs text-amber-100/80">
            {warnings.slice(0, 10).map((warning, index) => <li key={index}>{warning}</li>)}
          </ul>
        </section>
      )}
    </aside>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex justify-between gap-4 border-b border-white/5 pb-1">
      <span className="text-slate-400">{label}</span>
      <span className="max-w-52 truncate font-mono text-cyan-100">{value ?? "n/a"}</span>
    </div>
  );
}

function formatMs(value) {
  return typeof value === "number" ? `${value.toFixed(2)} ms` : "n/a";
}

function formatPct(value) {
  return typeof value === "number" ? `${value.toFixed(3)}%` : "n/a";
}
