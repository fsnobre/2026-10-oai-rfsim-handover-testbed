import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import TopologyDiagram from "./TopologyDiagram";

// Mirrors the backend topology registry (dashboard/backend/config.py).
const CONTAINERS = {
  f1: [
    { name: "oai-amf", role: "core", indicator: "green" },
    { name: "oai-cu", service: "cu", role: "cu", expected_ip: "192.168.70.150", telnet_port: 9090, indicator: "green" },
    { name: "oai-du0", service: "du0", role: "du", expected_ip: "192.168.70.171", indicator: "green" },
    { name: "oai-du1", service: "du1", role: "du", expected_ip: "192.168.70.172", indicator: "green" },
    { name: "oai-nr-ue", service: "nr-ue", role: "ue", expected_ip: "192.168.70.181", indicator: "green" },
  ],
  "n2-monolithic": [
    { name: "oai-amf", role: "core", indicator: "green" },
    { name: "oai-gnb0", service: "gnb0", role: "gnb", expected_ip: "192.168.70.160", telnet_port: 9090, indicator: "green" },
    { name: "oai-gnb1", service: "gnb1", role: "gnb", expected_ip: "192.168.70.161", telnet_port: 9090, indicator: "green" },
    { name: "oai-nr-ue", service: "nr-ue", role: "ue", expected_ip: "192.168.70.181", indicator: "green" },
  ],
  "n2-cu-du": [
    { name: "oai-amf", role: "core", indicator: "green" },
    { name: "oai-cu0", service: "cu0", role: "cu", expected_ip: "192.168.70.150", telnet_port: 9090, indicator: "green" },
    { name: "oai-cu1", service: "cu1", role: "cu", expected_ip: "192.168.70.155", telnet_port: 9090, indicator: "green" },
    { name: "oai-du0", service: "du0", role: "du", expected_ip: "192.168.70.171", indicator: "green" },
    { name: "oai-du1", service: "du1", role: "du", expected_ip: "192.168.70.172", indicator: "green" },
    { name: "oai-nr-ue", service: "nr-ue", role: "ue", expected_ip: "192.168.70.181", indicator: "green" },
  ],
  "usrp-cots": [
    { name: "oai-amf", role: "core", indicator: "green" },
    { name: "oai-gnb", service: "gnb", role: "gnb", indicator: "green" },
  ],
};

describe("per-topology diagrams", () => {
  test("F1 renders CU, both DUs and the RFsim UE", () => {
    render(<TopologyDiagram topology="f1" containers={CONTAINERS.f1} config={{ dus: [{ pci: 0 }, { pci: 1 }] }} />);
    expect(screen.getByText("F1 RFsim topology")).toBeTruthy();
    ["CN5G", "CU", "DU0", "DU1", "RFsim UE"].forEach((label) => expect(screen.getByText(label)).toBeTruthy());
    // Parsed cell config is used when available.
    expect(screen.getByText("PCI 0 / 192.168.70.171")).toBeTruthy();
    // CU shows its telnet endpoint.
    expect(screen.getByText("192.168.70.150:9090")).toBeTruthy();
  });

  test("N2 monolithic renders both gNBs with their own telnet endpoints", () => {
    render(<TopologyDiagram topology="n2-monolithic" containers={CONTAINERS["n2-monolithic"]} />);
    expect(screen.getByText("N2 monolithic RFsim topology")).toBeTruthy();
    ["CN5G", "gNB0", "gNB1", "RFsim UE"].forEach((label) => expect(screen.getByText(label)).toBeTruthy());
    expect(screen.getByText("192.168.70.160:9090")).toBeTruthy();
    expect(screen.getByText("192.168.70.161:9090")).toBeTruthy();
  });

  test("N2 CU/DU renders both CU+DU pairs", () => {
    render(<TopologyDiagram topology="n2-cu-du" containers={CONTAINERS["n2-cu-du"]} />);
    expect(screen.getByText("N2 CU/DU RFsim topology")).toBeTruthy();
    ["CN5G", "CU0", "CU1", "DU0", "DU1", "RFsim UE"].forEach((label) => expect(screen.getByText(label)).toBeTruthy());
    // The two CUs are distinct endpoints, which the old F1-only diagram could not show.
    expect(screen.getByText("192.168.70.150:9090")).toBeTruthy();
    expect(screen.getByText("192.168.70.155:9090")).toBeTruthy();
  });

  test("USRP marks the COTS handset as outside the monitored stack", () => {
    render(<TopologyDiagram topology="usrp-cots" containers={CONTAINERS["usrp-cots"]} />);
    expect(screen.getByText("USRP X310 single-cell topology")).toBeTruthy();
    expect(screen.getByText("COTS UE")).toBeTruthy();
    expect(screen.getByText("not monitored")).toBeTruthy();
    expect(screen.getByLabelText("not monitored")).toBeTruthy();
    // No RFsim UE container in this topology.
    expect(screen.queryByText("RFsim UE")).toBeNull();
  });

  test("an unknown topology says so instead of drawing an F1-shaped diagram", () => {
    render(<TopologyDiagram topology="something-else" containers={[]} />);
    expect(screen.getByText(/No diagram is defined for something-else/)).toBeTruthy();
  });
});

describe("honesty", () => {
  test("no serving cell is highlighted when none was observed", () => {
    render(<TopologyDiagram topology="n2-monolithic" containers={CONTAINERS["n2-monolithic"]} activeDu={null} />);
    expect(screen.getByText(/Serving cell not observed/)).toBeTruthy();
  });

  test("the note disappears once a serving cell is reported", () => {
    render(<TopologyDiagram topology="f1" containers={CONTAINERS.f1} config={{}} activeDu="DU1" />);
    expect(screen.queryByText(/Serving cell not observed/)).toBeNull();
  });

  test("non-F1 topologies state that cell config is not parsed", () => {
    render(<TopologyDiagram topology="n2-cu-du" containers={CONTAINERS["n2-cu-du"]} />);
    expect(screen.getByText(/cell configuration parsing is F1-only/i)).toBeTruthy();
  });

  test("missing containers still render, marked stopped", () => {
    render(<TopologyDiagram topology="n2-monolithic" containers={[]} />);
    expect(screen.getByText("gNB0")).toBeTruthy();
    // Registry address is unavailable without the container, so the node says so.
    expect(screen.getAllByText("address unavailable").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("stopped").length).toBeGreaterThan(0);
  });
});
