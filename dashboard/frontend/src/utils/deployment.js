const RAN_ROLES = ["cu", "du", "gnb", "ue"];
const CORE_ROLES = ["core", "external"];

/**
 * Whether a testbed is actually deployed, read from observed container existence.
 *
 * Deliberately not derived from the detected topology: when nothing is running the
 * backend falls back to a default topology name, and drawing that topology's nodes as
 * "stopped" would claim a specific stack is deployed and broken when in fact none is.
 *
 * Container existence is the direct observation, so this also works when the topology is
 * pinned rather than detected. `known` is false when Docker itself is unreachable, since
 * absence of evidence is not evidence of absence.
 */
export function deploymentState(containers = []) {
  const dockerDown = containers.some((item) => item.status === "docker_unavailable");
  const ran = containers.filter((item) => RAN_ROLES.includes(item.role));
  const core = containers.filter((item) => CORE_ROLES.includes(item.role));

  const ranRunning = ran.filter((item) => item.exists);
  const coreRunning = core.filter((item) => item.exists);

  return {
    known: !dockerDown,
    dockerDown,
    ranCount: ranRunning.length,
    coreCount: coreRunning.length,
    coreTotal: core.length,
    // Nothing to draw only when we could look and found no RAN container at all.
    deployed: dockerDown || ranRunning.length > 0,
    coreOnly: !dockerDown && ranRunning.length === 0 && coreRunning.length > 0,
  };
}
