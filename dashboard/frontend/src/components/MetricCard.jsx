export default function MetricCard({ label, value, hint }) {
  const displayValue = String(value ?? "Unavailable");
  const isLong = displayValue.length > 18;
  return (
    <div className="card min-w-0 p-4">
      <div className="truncate text-xs uppercase tracking-[0.18em] text-slate-400" title={label}>{label}</div>
      <div
        className={`mt-2 min-w-0 font-mono text-cyan-100 ${isLong ? "break-all text-base leading-snug" : "truncate text-2xl"}`}
        title={displayValue}
      >
        {displayValue}
      </div>
      {hint && <div className="mt-2 min-w-0 break-words text-xs text-slate-400">{hint}</div>}
    </div>
  );
}
