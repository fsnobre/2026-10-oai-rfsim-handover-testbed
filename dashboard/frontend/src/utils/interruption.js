// Pure helpers for the Overview handover-interruption card. Extracted so they
// can be unit-tested without rendering React.

export const RUN_DIR_SENTINEL = "INTERRUPTION_RUN_DIR=";

// Scan a job's stdout tail (array of lines) backward for the sentinel the
// measure_interruption.sh script prints, and return the run directory basename.
export function runIdFromTail(tail) {
  const lines = tail || [];
  for (let index = lines.length - 1; index >= 0; index -= 1) {
    const position = lines[index].indexOf(RUN_DIR_SENTINEL);
    if (position !== -1) {
      const path = lines[index].slice(position + RUN_DIR_SENTINEL.length).trim();
      const parts = path.split("/").filter(Boolean);
      return parts[parts.length - 1] || null;
    }
  }
  return null;
}

// Build the interruption chart model from a run's artifacts: a dense per-seq RTT
// series (missing sequence numbers become null so the line breaks across the
// outage), the gap bounds around the trigger, and the seamless/outage verdict.
export function buildInterruptionResult(run) {
  const samples = (run.ping_samples || [])
    .map((item) => ({
      seq: item.icmp_seq,
      rtt: typeof item.rtt_ms === "number" ? item.rtt_ms : null,
      ts: item.timestamp_unix != null ? Number(item.timestamp_unix) : null,
    }))
    .filter((item) => item.seq != null && Number.isFinite(item.seq))
    .sort((a, b) => a.seq - b.seq);

  const triggerEvent = (run.events || []).find((event) => event.event === "handover_trigger_start");
  const triggerTs = triggerEvent ? Date.parse(triggerEvent.timestamp) / 1000 : null;

  let gapStart = null;
  let gapEnd = null;
  if (triggerTs != null && Number.isFinite(triggerTs)) {
    for (const item of samples) {
      if (item.ts == null) continue;
      if (item.ts < triggerTs) gapStart = item.seq;
      else if (gapEnd == null) gapEnd = item.seq;
    }
  }

  // ping.csv holds replies only, so build a dense per-seq series and leave gaps
  // as nulls; connectNulls=false then breaks the line across the outage.
  const bySeq = new Map(samples.map((item) => [item.seq, item.rtt]));
  const data = [];
  if (samples.length) {
    const minSeq = samples[0].seq;
    const maxSeq = samples[samples.length - 1].seq;
    for (let seq = minSeq; seq <= maxSeq; seq += 1) {
      data.push({ seq, rtt_plot: bySeq.has(seq) ? bySeq.get(seq) : null });
    }
  }

  const summary = run.ping_summary || {};
  const maxRtt = Math.max(0, ...samples.map((item) => (typeof item.rtt === "number" ? item.rtt : 0)));
  const interruptionMs = summary.estimated_interruption_ms ?? null;
  const packetLoss = summary.packet_loss_percent ?? null;
  const hasMissingSeq = data.some((point) => point.rtt_plot === null);
  // measure_interruption.sh default cadence; estimates are floored by the probe
  // interval, so 0% loss + no gap + estimate within ~2 intervals = seamless.
  const PROBE_INTERVAL_MS = 10;
  const seamless =
    packetLoss === 0 &&
    !hasMissingSeq &&
    interruptionMs != null &&
    interruptionMs <= 2 * PROBE_INTERVAL_MS;

  return {
    runId: run.run_id,
    data,
    gapStart,
    gapEnd,
    yMax: Math.max(50, Math.ceil((maxRtt + 5) / 25) * 25),
    interruptionMs,
    firstAfterMs: summary.first_ping_after_handover_ms ?? null,
    packetLoss,
    seamless,
  };
}
