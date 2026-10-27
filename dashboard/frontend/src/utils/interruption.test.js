import { describe, it, expect } from "vitest";
import { runIdFromTail, buildInterruptionResult } from "./interruption";

describe("runIdFromTail", () => {
  it("returns the basename from the sentinel line", () => {
    const tail = [
      "[interruption] Capturing...",
      "INTERRUPTION_RUN_DIR=results/runs/20260703_f1_interruption",
      "results/runs/20260703_f1_interruption",
    ];
    expect(runIdFromTail(tail)).toBe("20260703_f1_interruption");
  });

  it("scans backward and ignores trailing slashes", () => {
    const tail = [
      "INTERRUPTION_RUN_DIR=results/runs/first",
      "INTERRUPTION_RUN_DIR=/abs/results/runs/second/",
    ];
    expect(runIdFromTail(tail)).toBe("second");
  });

  it("returns null when no sentinel present", () => {
    expect(runIdFromTail(["nothing here"])).toBeNull();
    expect(runIdFromTail([])).toBeNull();
    expect(runIdFromTail(null)).toBeNull();
  });
});

describe("buildInterruptionResult", () => {
  function run(overrides = {}) {
    return {
      run_id: "r1",
      ping_samples: [
        { icmp_seq: 1, rtt_ms: 0.5, timestamp_unix: "100000.000" },
        { icmp_seq: 2, rtt_ms: 0.5, timestamp_unix: "100000.010" },
        { icmp_seq: 5, rtt_ms: 0.6, timestamp_unix: "100000.100" },
      ],
      events: [{ event: "handover_trigger_start", timestamp: "1970-01-02T03:46:40.050Z" }],
      ping_summary: { estimated_interruption_ms: 90, first_ping_after_handover_ms: 50, packet_loss_percent: 40 },
      ...overrides,
    };
  }

  it("builds a dense per-seq series with nulls across missing sequences", () => {
    const result = buildInterruptionResult(run());
    // seqs 1..5 => 5 points; seq 3 and 4 are missing => null rtt_plot.
    expect(result.data.map((d) => d.seq)).toEqual([1, 2, 3, 4, 5]);
    expect(result.data[2].rtt_plot).toBeNull();
    expect(result.data[3].rtt_plot).toBeNull();
    expect(result.data[0].rtt_plot).toBe(0.5);
  });

  it("flags a lossy result as not seamless", () => {
    const result = buildInterruptionResult(run());
    expect(result.packetLoss).toBe(40);
    expect(result.seamless).toBe(false);
  });

  it("flags a 0% loss, no-gap, small-estimate result as seamless", () => {
    const seamlessRun = run({
      ping_samples: [
        { icmp_seq: 1, rtt_ms: 0.5, timestamp_unix: "100000.000" },
        { icmp_seq: 2, rtt_ms: 0.5, timestamp_unix: "100000.010" },
        { icmp_seq: 3, rtt_ms: 0.5, timestamp_unix: "100000.020" },
      ],
      ping_summary: { estimated_interruption_ms: 10, packet_loss_percent: 0 },
    });
    const result = buildInterruptionResult(seamlessRun);
    expect(result.seamless).toBe(true);
    expect(result.data.some((d) => d.rtt_plot === null)).toBe(false);
  });

  it("handles empty samples without throwing", () => {
    const result = buildInterruptionResult({ run_id: "empty", ping_samples: [], events: [] });
    expect(result.data).toEqual([]);
    expect(result.interruptionMs).toBeNull();
  });
});
