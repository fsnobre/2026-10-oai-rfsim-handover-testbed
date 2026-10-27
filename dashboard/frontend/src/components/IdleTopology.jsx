import Pill from "./Pill";

const TOPOLOGIES = [
  { name: "F1", id: "f1", detail: "1 CU + 2 DUs, intra-gNB handover over RFsim" },
  { name: "N2 monolithic", id: "n2-monolithic", detail: "2 standalone gNBs, inter-gNB handover over RFsim" },
  { name: "N2 CU/DU", id: "n2-cu-du", detail: "2 CU+DU pairs, inter-gNB handover over RFsim" },
  { name: "USRP", id: "usrp-cots", detail: "single cell on an X310 with a COTS handset — needs real radio hardware" },
];

/**
 * Shown in place of a topology diagram when no RAN container exists.
 *
 * Previously the Overview fell back to drawing F1 with every node stopped, which reads as
 * "the F1 stack is deployed and broken" rather than "nothing is deployed" — and is a
 * guess besides, since nothing indicates which topology the operator intends next.
 */
export default function IdleTopology({ state }) {
  const { coreCount, coreTotal, coreOnly, dockerDown } = state;

  return (
    <div className="card h-full p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">
            {coreOnly ? "Core running, no RAN deployed" : "No topology deployed"}
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            {coreOnly
              ? "The 5GC core is up but no CU, DU, gNB or UE container exists yet, so there is no radio topology to draw."
              : "No testbed containers are running, so there is nothing to draw."}
          </p>
        </div>
        <Pill tone="neutral">idle</Pill>
      </div>

      {dockerDown ? (
        <p className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/5 p-3 text-sm text-amber-100">
          Docker is unreachable, so deployment state could not be determined.
        </p>
      ) : null}

      <div className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-slate-300">
        5GC core: <span className="font-mono text-cyan-100">{coreCount}/{coreTotal}</span> containers present.
        {coreOnly ? " Deploying a topology will reuse it." : ""}
      </div>

      <p className="mt-5 text-xs uppercase tracking-[0.18em] text-slate-400">Available topologies</p>
      <ul className="mt-3 space-y-2">
        {TOPOLOGIES.map((item) => (
          <li key={item.id} className="rounded-xl bg-black/20 p-3 text-sm">
            <span className="font-semibold text-white">{item.name}</span>
            <span className="ml-2 font-mono text-xs text-cyan-100">{item.id}</span>
            <p className="mt-1 text-slate-400">{item.detail}</p>
          </li>
        ))}
      </ul>

      <p className="mt-4 text-sm text-slate-400">
        Deploy one from the panel on the right, or run{" "}
        <span className="font-mono text-cyan-100">./scripts/up.sh &lt;topology&gt;</span> on the host. The diagram and
        live telemetry appear once the containers exist.
      </p>
    </div>
  );
}
