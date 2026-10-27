import { describe, it, expect } from "vitest";
import { buildLatencyWindow } from "./latency";

describe("buildLatencyWindow", () => {
  it("left-pads to a fixed width when there are fewer samples than slots", () => {
    const samples = [
      { reachable: true, rtt_ms: 5 },
      { reachable: true, rtt_ms: 7 },
    ];
    const { data, visibleSamples } = buildLatencyWindow(samples, 5);
    expect(data).toHaveLength(5);
    expect(visibleSamples).toHaveLength(2);
    // First three are placeholders, last two are real.
    expect(data.slice(0, 3).every((d) => d.placeholder)).toBe(true);
    expect(data[3].placeholder).toBe(false);
    expect(data[4].rtt_plot).toBe(7);
  });

  it("keeps only the most recent slots when there are more samples than slots", () => {
    const samples = Array.from({ length: 10 }, (_, i) => ({ reachable: true, rtt_ms: i }));
    const { data, visibleSamples } = buildLatencyWindow(samples, 4);
    expect(data).toHaveLength(4);
    expect(visibleSamples).toHaveLength(4);
    expect(data.map((d) => d.rtt_ms)).toEqual([6, 7, 8, 9]);
  });

  it("marks unreachable probes with a loss marker and null rtt", () => {
    const samples = [{ reachable: false, error: "timeout" }];
    const { data } = buildLatencyWindow(samples, 1);
    expect(data[0].rtt_plot).toBeNull();
    expect(data[0].loss_marker).toBe(0);
  });

  it("has a sane y-axis floor with no samples", () => {
    const { data, yMax } = buildLatencyWindow([], 3);
    expect(data).toHaveLength(3);
    expect(data.every((d) => d.placeholder)).toBe(true);
    expect(yMax).toBe(50);
  });
});
