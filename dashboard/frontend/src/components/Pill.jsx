const TONES = {
  good: "bg-emerald-400/10 text-emerald-100",
  bad: "bg-rose-400/10 text-rose-100",
  warn: "bg-amber-400/10 text-amber-100",
  neutral: "bg-cyan-400/10 text-cyan-100",
};

export default function Pill({ children, tone = "neutral" }) {
  return (
    <span className={`shrink-0 rounded-full px-3 py-1 text-xs font-semibold ${TONES[tone] || TONES.neutral}`}>
      {children}
    </span>
  );
}
