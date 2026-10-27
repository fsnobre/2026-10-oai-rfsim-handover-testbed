#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TOPOLOGY="${1:-f1}"
apply_topology "${TOPOLOGY}"
ensure_project_root

"${SCRIPT_DIR}/preflight_check.sh" "${TOPOLOGY}"
echo

CORE_READY_TIMEOUT="${CORE_READY_TIMEOUT:-180}"
STABILIZATION_SLEEP="${STABILIZATION_SLEEP:-2}"

require_remaining_timeout() {
  local start_seconds="$1"
  local timeout="$2"
  local label="$3"
  local remaining
  remaining="$(remaining_timeout "${start_seconds}" "${timeout}")"
  if [[ "${remaining}" -le 0 ]]; then
    echo "[up] Timeout while waiting for ${label} (${timeout}s)" >&2
    exit 1
  fi
  printf '%s\n' "${remaining}"
}

wait_for_ue_data_plane() {
  local timeout="${1:-180}"
  echo "[up] Waiting for UE registration and data plane (${timeout}s)"
  UE_DATA_READY_TIMEOUT="${timeout}" "${SCRIPT_DIR}/wait_ue_data_ready.sh"
}

echo "[up] Starting 5GC core from ${CORE_COMPOSE_DIR}"
(
  cd "${CORE_COMPOSE_DIR}"
  docker compose up -d
)

while read -r network subnet compose_network; do
  if ! docker_network_exists "${network}"; then
    echo "[up] OAI CN Compose did not create required network ${network}" >&2
    exit 1
  fi

  network_error=""
  if ! network_error="$(
    validate_core_docker_network "${network}" "${subnet}" "${compose_network}"
  )"; then
    echo "[up] Docker network ${network} has invalid configuration: ${network_error}" >&2
    exit 1
  fi
  echo "[up] Docker network ready: ${network} (${subnet})"
done < <(core_docker_network_specs)

echo "[up] Waiting for core services (${CORE_READY_TIMEOUT}s)"
phase_start="${SECONDS}"
remaining="$(require_remaining_timeout "${phase_start}" "${CORE_READY_TIMEOUT}" "core")"
wait_container_healthy_or_running oai-amf "${remaining}"
remaining="$(require_remaining_timeout "${phase_start}" "${CORE_READY_TIMEOUT}" "core")"
wait_container_healthy_or_running oai-smf "${remaining}"
remaining="$(require_remaining_timeout "${phase_start}" "${CORE_READY_TIMEOUT}" "core")"
wait_container_healthy_or_running oai-upf "${remaining}"
sleep "${STABILIZATION_SLEEP}"

if [[ "${RADIO_MODE}" == "usrp" ]]; then
  GNB_READY_TIMEOUT="${GNB_READY_TIMEOUT:-120}"
  NGAP_READY_TIMEOUT="${NGAP_READY_TIMEOUT:-120}"

  echo "[up] Starting gNB on USRP (real radio)"
  docker compose "${RAN_COMPOSE_ARGS[@]}" up -d gnb

  echo "[up] Waiting for gNB (${GNB_READY_TIMEOUT}s)"
  wait_container_stably_running oai-gnb "${GNB_READY_TIMEOUT}"

  echo "[up] Waiting for NG (N2) association to AMF (${NGAP_READY_TIMEOUT}s)"
  wait_ngap_associated oai-gnb "${NGAP_READY_TIMEOUT}"

  # No in-container UE data-plane gate: the UE is an external COTS handset.
  cat <<'EOF'
[up] gNB is up and associated with the AMF.
[up] Power on the COTS UE (or toggle airplane mode) so it attaches to the cell.
[up] Verify with: ./scripts/status.sh
EOF
elif [[ "${HANDOVER_TYPE}" == "f1" ]]; then
  CU_READY_TIMEOUT="${CU_READY_TIMEOUT:-120}"
  DU_READY_TIMEOUT="${DU_READY_TIMEOUT:-120}"
  DU1_UE_READY_TIMEOUT="${DU1_UE_READY_TIMEOUT:-180}"

  echo "[up] Starting CU"
  docker compose "${RAN_COMPOSE_ARGS[@]}" up -d cu

  echo "[up] Waiting for CU (${CU_READY_TIMEOUT}s)"
  phase_start="${SECONDS}"
  remaining="$(require_remaining_timeout "${phase_start}" "${CU_READY_TIMEOUT}" "CU")"
  wait_container_stably_running oai-cu "${remaining}"
  remaining="$(require_remaining_timeout "${phase_start}" "${CU_READY_TIMEOUT}" "CU Telnet")"
  wait_port "${CU_TELNET_HOST}" "${CU_TELNET_PORT}" "${remaining}"
  sleep "${STABILIZATION_SLEEP}"

  echo "[up] Starting DU0"
  docker compose "${RAN_COMPOSE_ARGS[@]}" up -d du0

  echo "[up] Waiting for DU0 (${DU_READY_TIMEOUT}s)"
  phase_start="${SECONDS}"
  remaining="$(require_remaining_timeout "${phase_start}" "${DU_READY_TIMEOUT}" "DU0")"
  wait_container_stably_running oai-du0 "${remaining}"
  sleep "${STABILIZATION_SLEEP}"

  UE_DATA_READY_TIMEOUT="${UE_DATA_READY_TIMEOUT:-180}"
  wait_for_ue_data_plane "${UE_DATA_READY_TIMEOUT}"

  echo "[up] Starting DU1"
  docker compose "${RAN_COMPOSE_ARGS[@]}" up -d du1

  echo "[up] Waiting for DU1 and oai-nr-ue (${DU1_UE_READY_TIMEOUT}s)"
  phase_start="${SECONDS}"
  remaining="$(require_remaining_timeout "${phase_start}" "${DU1_UE_READY_TIMEOUT}" "DU1")"
  wait_container_stably_running oai-du1 "${remaining}"
  remaining="$(require_remaining_timeout "${phase_start}" "${DU1_UE_READY_TIMEOUT}" "oai-nr-ue")"
  wait_container_stably_running oai-nr-ue "${remaining}"
  sleep 5
  wait_for_ue_data_plane "${UE_DATA_READY_TIMEOUT}"
else
  NR_UE_READY_TIMEOUT="${NR_UE_READY_TIMEOUT:-180}"

  echo "[up] Starting N2 RAN (topology=${TOPOLOGY})"
  docker compose "${RAN_COMPOSE_ARGS[@]}" up -d

  echo "[up] Waiting for nr-ue (${NR_UE_READY_TIMEOUT}s)"
  wait_container_stably_running oai-nr-ue "${NR_UE_READY_TIMEOUT}"

  UE_DATA_READY_TIMEOUT="${UE_DATA_READY_TIMEOUT:-180}"
  wait_for_ue_data_plane "${UE_DATA_READY_TIMEOUT}"
fi

echo "[up] Startup readiness gates passed."
echo
"${SCRIPT_DIR}/poststart_check.sh" || true
echo
echo "[up] Run ./scripts/status.sh to check readiness."
