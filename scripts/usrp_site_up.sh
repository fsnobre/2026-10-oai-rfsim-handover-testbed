#!/usr/bin/env bash

# Per-host launcher for a distributed USRP handover site. Starts one role
# (cu/du0/du1/gnb0/gnb1/cu0/cu1) from its per-host compose file with the host's
# .env, then waits for local readiness. Run on the host that owns that role.
#
#   ./scripts/usrp_site_up.sh <topology> <role>
#     topology: f1 | n2-monolithic | n2-cu-du
#     role:     the service to start on this host (e.g. du0, gnb1, cu0)
#
# Env:
#   ENV_FILE          override the .env path (default: <topology-dir>/.env)
#   READY_TIMEOUT     container stable-running timeout (default 120)
#   NGAP_TIMEOUT      NG-association timeout for CU/gNB roles (default 120)
#   RUN_RADIO_CHECK   if 1, run check_usrp.sh before starting (du/gnb roles)

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"
ensure_project_root

if [[ $# -ne 2 ]]; then
  echo "Usage: $0 <f1|n2-monolithic|n2-cu-du> <role>" >&2
  exit 2
fi

TOPOLOGY="$1"
ROLE="$2"

case "${TOPOLOGY}" in
  f1)                       topo_dir="f1" ;;
  n2-monolithic|n2_monolithic) topo_dir="n2_monolithic" ;;
  n2-cu-du|n2_cu_du)        topo_dir="n2_cu_du" ;;
  *) echo "Unknown topology: ${TOPOLOGY} (use f1, n2-monolithic, n2-cu-du)" >&2; exit 2 ;;
esac

TOPO_PATH="${PROJECT_ROOT}/experiments/usrp_handover/${topo_dir}"
COMPOSE_FILE="${TOPO_PATH}/compose-${ROLE}.yaml"
ENV_FILE="${ENV_FILE:-${TOPO_PATH}/.env}"
READY_TIMEOUT="${READY_TIMEOUT:-120}"
NGAP_TIMEOUT="${NGAP_TIMEOUT:-120}"

if [[ ! -f "${COMPOSE_FILE}" ]]; then
  echo "No compose file for role '${ROLE}' in ${topo_dir} (expected ${COMPOSE_FILE})." >&2
  exit 2
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy ${TOPO_PATH}/.env.example to .env and set your LAN IPs." >&2
  exit 2
fi

# Optional radio probe for radio-bearing roles.
if [[ "${RUN_RADIO_CHECK:-0}" == "1" && "${ROLE}" != cu* ]]; then
  echo "[site-up] Probing USRP before start"
  "${SCRIPT_DIR}/check_usrp.sh" || {
    echo "[site-up] USRP probe failed; aborting." >&2
    exit 1
  }
fi

echo "[site-up] Starting ${ROLE} (${TOPOLOGY}) from ${COMPOSE_FILE#"${PROJECT_ROOT}"/}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d

wait_container_stably_running "oai-${ROLE}" "${READY_TIMEOUT}"

# CU and monolithic gNB roles carry NG to the AMF; DUs are F1-only.
case "${ROLE}" in
  cu*|gnb*)
    echo "[site-up] Waiting for NG (N2) association to the AMF"
    wait_ngap_associated "oai-${ROLE}" "${NGAP_TIMEOUT}"
    ;;
  *)
    echo "[site-up] ${ROLE} is F1-only; confirm it connects to its CU (docker logs oai-${ROLE})."
    ;;
esac

echo "[site-up] ${ROLE} is up. Bring up the remaining sites, then power on the COTS UE."
