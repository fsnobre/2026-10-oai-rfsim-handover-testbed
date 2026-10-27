#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

PING_TARGET_VALUE="${PING_TARGET:-$(config_ping_target)}"
PING_INTERFACE_VALUE="${PING_INTERFACE:-$(config_ping_interface)}"
TIMEOUT="${UE_DATA_READY_TIMEOUT:-120}"
RUN_DIR_VALUE="${RUN_DIR:-}"

usage() {
  cat <<'EOF'
Usage: [PING_TARGET=ip] [PING_INTERFACE=iface] [UE_DATA_READY_TIMEOUT=seconds] [RUN_DIR=path] ./scripts/wait_ue_data_ready.sh

Waits until the UE data plane can reach the configured ping target by running:
  docker exec oai-nr-ue ping [-I <interface>] -c 1 -W 1 <target>
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

_log_matches() {
  local container="$1"
  local pattern="$2"
  local label="$3"

  if ! container_exists "${container}"; then
    echo "[ue-data][diag] ${container}: container not found" >&2
    return 0
  fi

  echo "[ue-data][diag] ${label} (${container}, recent relevant logs):" >&2
  local matches
  matches="$(docker logs --tail 250 "${container}" 2>&1 | grep -Ei "${pattern}" | tail -25 || true)"
  if [[ -n "${matches}" ]]; then
    printf '%s\n' "${matches}" >&2
  else
    echo "[ue-data][diag]   no matching recent log lines" >&2
  fi
}

_mysql_subscriber_diagnostics() {
  if ! container_exists mysql; then
    echo "[ue-data][diag] mysql: container not found" >&2
    return 0
  fi

  local mysql_state mysql_health
  mysql_state="$(docker inspect -f '{{.State.Status}}' mysql 2>/dev/null || echo unknown)"
  mysql_health="$(container_health_status mysql)"
  echo "[ue-data][diag] mysql: state=${mysql_state} health=${mysql_health}" >&2

  if ! container_running mysql; then
    return 0
  fi

  echo "[ue-data][diag] mysql AuthenticationSubscription rows for RFsim IMSI/SUPI:" >&2
  local subscriber_query
  subscriber_query="SELECT ueid,supi,authenticationMethod FROM AuthenticationSubscription WHERE ueid IN ('001010000000001','imsi-001010000000001') OR supi IN ('001010000000001','imsi-001010000000001');"
  if ! docker exec mysql sh -lc 'MYSQL_PWD="${MYSQL_PASSWORD:-test}" mysql -u"${MYSQL_USER:-test}" -D oai_db --table -e "$1"' sh "${subscriber_query}" >&2; then
    echo "[ue-data][diag]   unable to query mysql; check mysql health and oai_db initialization" >&2
  fi
}

_emit_timeout_diagnostics() {
  echo "[ue-data][diag] UE data-plane readiness timed out; collecting focused NAS/auth diagnostics." >&2

  if container_running oai-nr-ue; then
    if docker exec oai-nr-ue ip link show oaitun_ue1 >/dev/null 2>&1; then
      docker exec oai-nr-ue ip -4 -o addr show oaitun_ue1 >&2 || true
    else
      echo "[ue-data][diag] oaitun_ue1 is missing inside oai-nr-ue." >&2
      echo "[ue-data][diag] This usually means UE NAS registration or PDU-session setup did not complete." >&2
    fi
  fi

  _log_matches oai-nr-ue 'REGISTRATION_REJECT|Registration reject|FGS_REGISTRATION_REJECT|PDU|NAS|DNN|NSSAI|oaitun|authentication' 'UE NAS/PDU-session hints'
  _log_matches oai-amf 'CONTEXT_NOT_FOUND|Authentication|Registration Reject|Request Authentication|Could not parse|IMSI|SUPI|5GMM' 'AMF authentication/registration hints'
  _log_matches oai-ausf 'CONTEXT_NOT_FOUND|Authentication|UE Authentication|supi|imsi|error|fail' 'AUSF authentication hints'
  _log_matches oai-udm 'CONTEXT_NOT_FOUND|Authentication|subscription|supi|imsi|error|fail' 'UDM subscription/authentication hints'
  _log_matches oai-udr 'CONTEXT_NOT_FOUND|AuthenticationSubscription|subscription|supi|imsi|error|fail' 'UDR database lookup hints'
  _mysql_subscriber_diagnostics

  cat >&2 <<'EOF'
[ue-data][diag] Focused next checks:
[ue-data][diag]   - If AMF/AUSF/UDM/UDR logs show CONTEXT_NOT_FOUND, verify oai_db has both 001010000000001 and imsi-001010000000001 in AuthenticationSubscription.
[ue-data][diag]   - If mysql is unhealthy or stale, recreate the core DB container with: ./scripts/down.sh f1 --volumes && ./scripts/up.sh f1
[ue-data][diag]   - If oaitun_ue1 is missing but authentication succeeds, inspect PDU session, DNN oai, and slice SST 1 / SD FFFFFF.
EOF
}

if ! [[ "${TIMEOUT}" =~ ^[0-9]+$ ]]; then
  echo "UE_DATA_READY_TIMEOUT must be an integer number of seconds" >&2
  exit 2
fi

ping_command=(docker exec oai-nr-ue ping)
if [[ -n "${PING_INTERFACE_VALUE}" ]]; then
  ping_command+=(-I "${PING_INTERFACE_VALUE}")
fi
ping_command+=(-c 1 -W 1 "${PING_TARGET_VALUE}")

append_event "${RUN_DIR_VALUE}" "ue_data_ready_start" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};timeout=${TIMEOUT}"

deadline=$((SECONDS + TIMEOUT))
attempt=1

while [[ "${SECONDS}" -le "${deadline}" ]]; do
  if ! container_running oai-nr-ue; then
    echo "[ue-data] attempt ${attempt}: oai-nr-ue not running"
  elif "${ping_command[@]}" >/dev/null 2>&1; then
    echo "[ue-data] target ${PING_TARGET_VALUE} via ${PING_INTERFACE_VALUE:-default}: reachable"
    append_event "${RUN_DIR_VALUE}" "ue_data_ready_passed" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};attempt=${attempt}"
    exit 0
  else
    remaining=$((deadline - SECONDS))
    if [[ "${remaining}" -lt 0 ]]; then
      remaining=0
    fi
    echo "[ue-data] attempt ${attempt}: not ready (${remaining}s remaining)"
  fi

  attempt=$((attempt + 1))
  sleep 3
done

echo "[ue-data] target ${PING_TARGET_VALUE} via ${PING_INTERFACE_VALUE:-default}: not reachable after ${TIMEOUT}s" >&2
_emit_timeout_diagnostics
append_event "${RUN_DIR_VALUE}" "ue_data_ready_failed" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};timeout=${TIMEOUT}"
exit 1
