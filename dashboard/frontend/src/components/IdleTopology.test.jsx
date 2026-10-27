import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import IdleTopology from "./IdleTopology";
import Sidebar from "./Sidebar";
import { deploymentState } from "../utils/deployment";

describe("IdleTopology", () => {
  test("says nothing is deployed rather than drawing a guessed topology", () => {
    render(<IdleTopology state={deploymentState([])} />);
    expect(screen.getByText("No topology deployed")).toBeTruthy();
    expect(screen.getByText(/nothing to draw/i)).toBeTruthy();
    // It offers the real choices instead of implying one.
    ["f1", "n2-monolithic", "n2-cu-du", "usrp-cots"].forEach((id) => {
      expect(screen.getByText(id)).toBeTruthy();
    });
  });

  test("distinguishes a running core from a completely cold host", () => {
    const containers = [
      { name: "oai-amf", role: "core", exists: true, status: "running" },
      { name: "oai-cu", role: "cu", exists: false, status: "missing" },
    ];
    render(<IdleTopology state={deploymentState(containers)} />);
    expect(screen.getByText("Core running, no RAN deployed")).toBeTruthy();
    expect(screen.getByText(/Deploying a topology will reuse it/)).toBeTruthy();
  });

  test("reports an unreachable Docker instead of claiming an idle testbed", () => {
    const state = { ...deploymentState([]), dockerDown: true, known: false };
    render(<IdleTopology state={state} />);
    expect(screen.getByText(/Docker is unreachable/)).toBeTruthy();
  });
});

describe("Sidebar", () => {
  const containers = [
    { name: "oai-amf", role: "core", exists: false, indicator: "red", status: "missing" },
    { name: "oai-cu", role: "cu", exists: false, indicator: "red", status: "missing" },
    { name: "oai-du0", role: "du", exists: false, indicator: "red", status: "missing" },
  ];

  test("does not name fallback RAN containers when nothing is deployed", () => {
    render(<Sidebar containers={containers} deployed={false} />);
    expect(screen.queryByText("oai-cu")).toBeNull();
    expect(screen.queryByText("oai-du0")).toBeNull();
    // Core is shared by every topology, so it is a real observation and stays.
    expect(screen.getByText("oai-amf")).toBeTruthy();
    expect(screen.getByText(/Nodes appear here once a topology is deployed/)).toBeTruthy();
  });

  test("lists RAN containers once a topology is deployed", () => {
    render(<Sidebar containers={containers.map((c) => ({ ...c, exists: true }))} deployed />);
    expect(screen.getByText("oai-cu")).toBeTruthy();
    expect(screen.getByText("oai-du0")).toBeTruthy();
  });
});
