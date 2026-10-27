import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import RunDetail from "./RunDetail";
import UeContextCard from "./UeContextCard";

describe("RunDetail", () => {
  test("prompts for a selection when nothing is chosen", () => {
    render(<RunDetail run={null} summary={{}} loading={false} />);
    expect(screen.getByText(/Select a run/i)).toBeTruthy();
  });

  test("shows a loading state instead of an empty shell", () => {
    render(<RunDetail run={null} summary={{}} loading />);
    expect(screen.getByText(/Loading run/i)).toBeTruthy();
  });

  test("renders metrics, events and message flow from one run payload", () => {
    const run = {
      summary: {
        run_id: "20260619_145515_f1_handover_smoke",
        topology: "f1",
        status: "pass",
        handover_triggered: true,
        estimated_interruption_ms: 202.072,
        packet_loss_percent: 0,
      },
      ping_samples: [{ timestamp_utc: "2026-06-19T14:55:20Z", rtt_ms: 8.4 }],
      ping_interruption_markers: {
        handover_trigger_start: { timestamp: "2026-06-19T14:55:21Z" },
      },
      events: [{ event: "handover_trigger_start", source: "events_csv", confidence: "observed" }],
      message_flow: [{ from: "CU", to: "DU1", label: "handover", source: "events_csv", confidence: "observed" }],
      warnings: [],
    };
    render(<RunDetail run={run} summary={{}} loading={false} />);

    expect(screen.getByText("20260619_145515_f1_handover_smoke")).toBeTruthy();
    expect(screen.getByText("202.07 ms")).toBeTruthy();
    expect(screen.getByText("Event timeline")).toBeTruthy();
    expect(screen.getByText("Message flow")).toBeTruthy();
    // Confidence stays visible on the event row.
    expect(screen.getByText("observed")).toBeTruthy();
  });

  test("missing metrics read as Unavailable rather than zero", () => {
    const run = { summary: { run_id: "run-1" }, events: [], message_flow: [], ping_samples: [] };
    render(<RunDetail run={run} summary={{}} loading={false} />);
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(screen.getByText(/No ping samples available/i)).toBeTruthy();
  });
});

describe("UeContextCard", () => {
  test("keeps current UE count separate from AMF registration events", () => {
    render(
      <UeContextCard
        liveKpis={{
          ue_count: null,
          amf_registration_events_seen: 4,
          amf_registration_events_window: "last_500_log_lines",
          attached_ues: [],
        }}
      />,
    );
    expect(screen.getByText("Unavailable")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(screen.getByText(/not a current attachment count/i)).toBeTruthy();
  });

  test("lists attached UEs when a telemetry source exposes them", () => {
    render(<UeContextCard liveKpis={{ ue_count: 1, attached_ues: [{ rrc_id: "1", rnti: "0x4601", serving_du: "DU1" }] }} />);
    expect(screen.getByText("0x4601")).toBeTruthy();
    expect(screen.getByText("DU1")).toBeTruthy();
  });
});
