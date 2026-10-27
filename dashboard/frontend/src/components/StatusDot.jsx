// Status is conveyed by shape/fill as well as color (WCAG 1.4.1): running is a
// solid dot, starting adds a ring, stopped is a hollow ring. An aria-label makes
// the state available to screen readers.
const STYLES = {
  green: { cls: "bg-status-ok shadow-status-ok/60", label: "running" },
  orange: { cls: "bg-status-warn ring-2 ring-white/50 shadow-status-warn/60", label: "starting" },
  red: { cls: "border-2 border-status-bad bg-transparent", label: "stopped" },
};

export default function StatusDot({ indicator = "red" }) {
  const style = STYLES[indicator] || STYLES.red;
  return (
    <span
      role="img"
      aria-label={style.label}
      title={style.label}
      className={`inline-block h-3 w-3 rounded-full shadow ${style.cls}`}
    />
  );
}
