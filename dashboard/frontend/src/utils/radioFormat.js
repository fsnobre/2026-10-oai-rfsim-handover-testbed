function numeric(value) {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatScs(value) {
  const mu = numeric(value);
  if (mu === null) return "Unavailable";
  const khz = {
    0: 15,
    1: 30,
    2: 60,
    3: 120,
    4: 240,
  }[mu];
  return khz ? `${value} (${khz} kHz)` : `${value} (spacing unavailable)`;
}

export function nrArfcnToMhz(value) {
  const arfcn = numeric(value);
  if (arfcn === null) return null;
  if (arfcn >= 0 && arfcn <= 599999) return 0.005 * arfcn;
  if (arfcn >= 600000 && arfcn <= 2016666) return 3000 + 0.015 * (arfcn - 600000);
  if (arfcn >= 2016667 && arfcn <= 3279165) return 24250.08 + 0.06 * (arfcn - 2016667);
  return null;
}

export function formatNrArfcn(value) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const mhz = nrArfcnToMhz(value);
  if (mhz === null) return `${value} (frequency unavailable)`;
  return `${value} (${mhz.toFixed(2)} MHz)`;
}

export function formatBand(value) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  const text = String(value);
  return text.startsWith("n") ? text : `n${text}`;
}

export function formatPrbs(value) {
  if (value === null || value === undefined || value === "") return "Unavailable";
  return `${value} PRB`;
}

export function formatTddPattern(pattern) {
  if (!pattern || typeof pattern !== "object") return "Unavailable";
  const parts = [];
  const periodicity =
    pattern.periodicity ??
    pattern.periodicity_ms ??
    pattern.dl_ul_tx_periodicity ??
    pattern.dl_UL_TransmissionPeriodicity;
  const dlSlots = pattern.dl_slots ?? pattern.nrof_downlink_slots ?? pattern.nrofDownlinkSlots;
  const dlSymbols = pattern.dl_symbols ?? pattern.nrof_downlink_symbols ?? pattern.nrofDownlinkSymbols;
  const ulSlots = pattern.ul_slots ?? pattern.nrof_uplink_slots ?? pattern.nrofUplinkSlots;
  const ulSymbols = pattern.ul_symbols ?? pattern.nrof_uplink_symbols ?? pattern.nrofUplinkSymbols;

  if (periodicity !== undefined && periodicity !== null) parts.push(`periodicity ${periodicity}`);
  if (dlSlots !== undefined || dlSymbols !== undefined) parts.push(`DL ${dlSlots ?? "?"} slots / ${dlSymbols ?? "?"} symbols`);
  if (ulSlots !== undefined || ulSymbols !== undefined) parts.push(`UL ${ulSlots ?? "?"} slots / ${ulSymbols ?? "?"} symbols`);
  return parts.length ? parts.join(", ") : "Unavailable";
}
