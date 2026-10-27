import Detail from "./Detail";

function fmt(value) {
  return value ?? "Unavailable";
}

/**
 * Current UE context.
 *
 * Deliberately narrow: the former UE page also showed serving DU, CQI, MCS DL/UL,
 * BLER DL/UL and PHR, none of which any current telemetry path populates — they read
 * "Unavailable" permanently. Only values with a real source are shown here, and the two
 * that exist are kept distinct because they mean different things: `ue_count` is current
 * attached context, while AMF registration events are historical log matches that
 * detach/reattach cycles and failed attempts can inflate.
 */
export default function UeContextCard({ liveKpis = {} }) {
  const attached = liveKpis.attached_ues || [];

  return (
    <section className="card p-5">
      <h3 className="text-lg font-semibold text-white">UE context</h3>
      <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
        <Detail label="Current UE count" value={fmt(liveKpis.ue_count)} />
        <Detail label="AMF registrations seen" value={fmt(liveKpis.amf_registration_events_seen)} />
      </div>
      <p className="mt-3 text-xs text-slate-400">
        UE count reflects current attached context only, and is available when the topology&apos;s telnet
        source exposes it. AMF registration events come from {liveKpis.amf_registration_events_window || "recent AMF logs"} and
        are not a current attachment count.
      </p>

      {attached.length ? (
        <div className="mt-4 overflow-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-slate-400">
              <tr>
                <th className="py-2">RRC ID</th>
                <th>RNTI</th>
                <th>Serving DU</th>
              </tr>
            </thead>
            <tbody>
              {attached.map((ue, index) => (
                <tr key={index} className="border-t border-white/10">
                  <td className="py-2 font-mono">{ue.rrc_id || "Unavailable"}</td>
                  <td className="font-mono">{ue.rnti || "Unavailable"}</td>
                  <td>{ue.serving_du || "Unavailable"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-4 text-sm text-slate-400">
          No live UE context from the current telemetry source. Passive telnet polling is disabled by default.
        </p>
      )}
    </section>
  );
}
