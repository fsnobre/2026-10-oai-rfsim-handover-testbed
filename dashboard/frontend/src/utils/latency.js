// Pure helper for the Overview live-latency chart. Builds a fixed-width scrolling
// window: the most recent `visibleSlots` samples, left-padded with placeholder
// slots so the x-axis stays stable before enough samples have arrived.

export function buildLatencyWindow(samples, visibleSlots = 90) {
  const source = samples || [];
  const visibleSamples = source.slice(-visibleSlots);
  const paddingCount = Math.max(0, visibleSlots - visibleSamples.length);
  const data = [
    ...Array.from({ length: paddingCount }, (_, index) => ({
      slot: index,
      label: "",
      rtt_plot: null,
      loss_marker: null,
      placeholder: true,
    })),
    ...visibleSamples.map((sample, index) => ({
      ...sample,
      slot: paddingCount + index,
      rtt_plot: sample.reachable ? sample.rtt_ms : null,
      loss_marker: sample.reachable ? null : 0,
      placeholder: false,
    })),
  ];
  const maxRtt = Math.max(
    0,
    ...visibleSamples.map((sample) => (typeof sample.rtt_ms === "number" ? sample.rtt_ms : 0)),
  );
  const yMax = Math.max(50, Math.ceil((maxRtt + 5) / 25) * 25);
  return { visibleSamples, data, yMax };
}
