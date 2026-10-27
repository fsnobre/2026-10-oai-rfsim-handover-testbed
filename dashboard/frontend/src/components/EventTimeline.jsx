function Tag({ children }) {
  return <span className="rounded-full bg-white/[0.06] px-2 py-0.5 text-xs text-slate-300">{children || "n/a"}</span>;
}

// Normalized run events. Source and confidence stay visible on every row: an event
// parsed from a bounded log tail is not the same evidence as one recorded in events.csv.
export default function EventTimeline({ events = [] }) {
  return (
    <div className="card p-5">
      <h3 className="text-lg font-semibold text-white">Event timeline</h3>
      {events.length ? (
        <div className="mt-4 max-h-[520px] space-y-2 overflow-auto">
          {events.map((event, index) => (
            <div key={index} className="rounded-xl bg-black/20 p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-cyan-100">{event.timestamp || "time unavailable"}</span>
                {event.relative_ms !== null && event.relative_ms !== undefined && (
                  <span className="rounded-full bg-cyan-400/10 px-2 py-0.5 text-xs text-cyan-100">+{event.relative_ms} ms</span>
                )}
                <Tag>{event.source}</Tag>
                <Tag>{event.confidence}</Tag>
                <Tag>{event.category}</Tag>
              </div>
              <div className="mt-2 font-semibold text-white">{event.event}</div>
              {event.details && <p className="mt-1 text-slate-400">{event.details}</p>}
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-400">No normalized events available for this run.</p>
      )}
    </div>
  );
}
