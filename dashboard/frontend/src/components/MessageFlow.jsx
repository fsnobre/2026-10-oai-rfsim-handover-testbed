const ENTITIES = ["UE", "DU0", "DU1", "CU", "CN5G", "EXT-DN", "Unknown"];

function FlowRow({ step }) {
  const fromIndex = Math.max(0, ENTITIES.indexOf(step.from));
  const toIndex = Math.max(0, ENTITIES.indexOf(step.to));
  const start = Math.min(fromIndex, toIndex) + 1;
  const span = Math.abs(toIndex - fromIndex) + 1;
  return (
    <div className="relative grid grid-cols-7 gap-2 rounded-xl bg-black/20 p-3 text-sm">
      {ENTITIES.map((entity) => (
        <div key={entity} className="min-h-10 border-l border-white/10" />
      ))}
      <div
        className="absolute top-3 rounded-lg border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-cyan-50"
        style={{ left: `calc(${((start - 1) / 7) * 100}% + 0.5rem)`, width: `calc(${(span / 7) * 100}% - 1rem)` }}
      >
        <div className="font-semibold">{step.from} → {step.to}</div>
        <div className="font-mono text-xs">{step.label}</div>
        <div className="mt-1 text-xs text-slate-300">{step.source} · {step.confidence}</div>
      </div>
    </div>
  );
}

// Best-effort reconstruction from run artifacts. Unknown endpoints stay "Unknown"
// rather than being inferred from topology names.
export default function MessageFlow({ steps = [] }) {
  return (
    <div className="card p-5">
      <h3 className="text-lg font-semibold text-white">Message flow</h3>
      {steps.length ? (
        <div className="mt-4 overflow-auto">
          <div className="min-w-[760px]">
            <div className="grid grid-cols-7 gap-2 border-b border-white/10 pb-2 text-center text-xs uppercase tracking-wide text-slate-400">
              {ENTITIES.map((entity) => <div key={entity}>{entity}</div>)}
            </div>
            <div className="mt-3 space-y-3">
              {steps.map((step, index) => <FlowRow key={index} step={step} />)}
            </div>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No message-flow steps could be reconstructed from available artifacts.</p>
      )}
    </div>
  );
}
