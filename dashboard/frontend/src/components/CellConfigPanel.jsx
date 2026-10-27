import { formatBand, formatNrArfcn, formatPrbs, formatScs, formatTddPattern } from "../utils/radioFormat";

function valueOr(value) {
  return value ?? "Unavailable";
}

/**
 * Parsed CU and DU cell configuration, collapsed by default.
 *
 * This is reference data read from the committed .conf files, not telemetry — it only
 * changes when those files change — so it lives behind a disclosure rather than taking
 * permanent space on the Overview. Parsing is F1-only; other topologies say so instead
 * of showing an F1-shaped configuration.
 */
export default function CellConfigPanel({ config = {}, topology = "f1" }) {
  const cu = config.cu || {};
  const dus = config.dus || [];

  return (
    <details className="card p-5">
      <summary className="cursor-pointer list-none">
        <span className="text-lg font-semibold text-white">Cell configuration</span>
        <span className="ml-3 text-sm text-slate-400">parsed from conf files — click to expand</span>
      </summary>

      {topology !== "f1" ? (
        <p className="mt-4 text-sm text-slate-400">
          Configuration parsing is available for F1 only. No cell details are inferred for {topology}.
        </p>
      ) : (
        <div className="mt-4 space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-slate-200">CU / core</h4>
            <div className="mt-2 grid grid-cols-2 gap-2 text-xs md:grid-cols-4">
              <Field label="PLMN" value={cu.plmn ? `${cu.plmn.mcc}/${cu.plmn.mnc}` : null} />
              <Field label="TAC" value={cu.tracking_area_code} />
              <Field label="AMF" value={cu.amf_ip_address} />
              <Field label="F1 local" value={cu.f1_local_address} />
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            {dus.map((du) => {
              const tddPattern = formatTddPattern(du.tdd_pattern);
              return (
                <div key={du.name} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <h4 className="font-semibold text-cyan-100">{du.name}</h4>
                  <dl className="mt-3 grid grid-cols-2 gap-2 text-xs">
                    <dt className="text-slate-400">PCI</dt><dd className="font-mono">{valueOr(du.pci)}</dd>
                    <dt className="text-slate-400">Band</dt><dd className="font-mono">{formatBand(du.band)}</dd>
                    <dt className="text-slate-400">SSB ARFCN</dt><dd className="font-mono">{formatNrArfcn(du.ssb_arfcn)}</dd>
                    <dt className="text-slate-400">PointA</dt><dd className="font-mono">{formatNrArfcn(du.point_a)}</dd>
                    <dt className="text-slate-400">Bandwidth</dt><dd className="font-mono">{formatPrbs(du.carrier_bandwidth)}</dd>
                    <dt className="text-slate-400">SCS</dt><dd className="font-mono">{formatScs(du.subcarrier_spacing)}</dd>
                    {tddPattern !== "Unavailable" && (
                      <>
                        <dt className="text-slate-400">TDD</dt><dd className="font-mono">{tddPattern}</dd>
                      </>
                    )}
                    <dt className="text-slate-400">F1 local</dt><dd className="font-mono">{valueOr(du.f1_local_address)}</dd>
                  </dl>
                  {Object.keys(du.overrides || {}).length > 0 && (
                    <div className="mt-3 rounded-xl bg-amber-400/10 p-3 text-xs text-amber-100">
                      <div className="mb-1 font-semibold">Compose overrides</div>
                      <pre className="whitespace-pre-wrap">{JSON.stringify(du.overrides, null, 2)}</pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </details>
  );
}

function Field({ label, value }) {
  return (
    <div className="rounded-xl bg-black/20 p-2">
      <div className="text-[11px] uppercase tracking-[0.14em] text-slate-400">{label}</div>
      <div className="mt-1 break-words font-mono text-cyan-100">{valueOr(value)}</div>
    </div>
  );
}
