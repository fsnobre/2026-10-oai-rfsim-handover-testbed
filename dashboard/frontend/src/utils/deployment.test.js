import { describe, expect, test } from "vitest";
import { deploymentState } from "./deployment";

const core = (exists) => [
  { name: "oai-amf", role: "core", exists, status: exists ? "running" : "missing" },
  { name: "oai-smf", role: "core", exists, status: exists ? "running" : "missing" },
  { name: "oai-ext-dn", role: "external", exists, status: exists ? "running" : "missing" },
];

const ran = (exists) => [
  { name: "oai-cu", role: "cu", exists, status: exists ? "running" : "missing" },
  { name: "oai-du0", role: "du", exists, status: exists ? "running" : "missing" },
  { name: "oai-nr-ue", role: "ue", exists, status: exists ? "running" : "missing" },
];

describe("deploymentState", () => {
  test("nothing running is not a deployed topology", () => {
    const state = deploymentState([...core(false), ...ran(false)]);
    expect(state.deployed).toBe(false);
    expect(state.coreOnly).toBe(false);
    expect(state.coreCount).toBe(0);
  });

  test("a running RAN counts as deployed", () => {
    const state = deploymentState([...core(true), ...ran(true)]);
    expect(state.deployed).toBe(true);
    expect(state.ranCount).toBe(3);
  });

  test("core up with no RAN is called out separately", () => {
    const state = deploymentState([...core(true), ...ran(false)]);
    expect(state.deployed).toBe(false);
    expect(state.coreOnly).toBe(true);
    expect(state.coreCount).toBe(3);
    expect(state.coreTotal).toBe(3);
  });

  test("a partially started RAN still counts as deployed", () => {
    const containers = [
      ...core(true),
      { name: "oai-cu", role: "cu", exists: true, status: "running" },
      { name: "oai-du0", role: "du", exists: false, status: "missing" },
    ];
    expect(deploymentState(containers).deployed).toBe(true);
  });

  test("an unreachable Docker is not read as 'nothing deployed'", () => {
    const containers = [
      { name: "oai-amf", role: "core", exists: false, status: "docker_unavailable" },
      { name: "oai-cu", role: "cu", exists: false, status: "docker_unavailable" },
    ];
    const state = deploymentState(containers);
    expect(state.known).toBe(false);
    expect(state.dockerDown).toBe(true);
    // Absence of evidence is not evidence of absence: keep the normal view.
    expect(state.deployed).toBe(true);
  });

  test("an empty container list is handled", () => {
    const state = deploymentState([]);
    expect(state.deployed).toBe(false);
    expect(state.coreTotal).toBe(0);
  });
});
