export default function WarningPanel({ warnings = [] }) {
  if (!warnings.length) {
    return <p className="text-sm text-emerald-300">No active dashboard warnings.</p>;
  }
  return (
    <ul className="max-h-48 space-y-1 overflow-auto text-xs text-amber-100/90">
      {warnings.map((warning, index) => (
        <li key={index}>{warning}</li>
      ))}
    </ul>
  );
}
