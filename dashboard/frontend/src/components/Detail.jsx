export default function Detail({ label, value }) {
  return (
    <div className="rounded-xl bg-black/20 p-2">
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <div className="mt-1 min-w-0 break-words font-mono text-cyan-100">{value}</div>
    </div>
  );
}
