#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

IPERF_TARGET="${IPERF_TARGET:-$(config_iperf_target)}"
IPERF_TARGET="${IPERF_TARGET:-192.168.70.135}"
IPERF_MODE="${IPERF_MODE:-$(config_iperf_mode)}"
IPERF_MODE="${IPERF_MODE:-udp}"
IPERF_DURATION="${IPERF_DURATION:-$(config_iperf_duration)}"
IPERF_DURATION="${IPERF_DURATION:-10}"
IPERF_INTERFACE="${IPERF_INTERFACE:-${PING_INTERFACE:-$(config_ping_interface)}}"
IPERF_INTERFACE="${IPERF_INTERFACE:-oaitun_ue1}"
RUN_DIR_VALUE="${RUN_DIR:-}"

if [[ "${IPERF_MODE}" != "tcp" && "${IPERF_MODE}" != "udp" ]]; then
  echo "IPERF_MODE must be tcp or udp" >&2
  exit 2
fi

if ! [[ "${IPERF_DURATION}" =~ ^[0-9]+$ ]] || [[ "${IPERF_DURATION}" -lt 1 ]]; then
  echo "IPERF_DURATION must be a positive integer number of seconds" >&2
  exit 2
fi

if [[ -z "${RUN_DIR_VALUE}" ]]; then
  RUN_DIR_VALUE="$(create_run_dir manual_f1_handover_iperf)"
else
  mkdir -p "${RUN_DIR_VALUE}"
fi

raw_file="${RUN_DIR_VALUE}/iperf_raw.json"
server_log="${RUN_DIR_VALUE}/iperf_server.log"
summary_file="${RUN_DIR_VALUE}/iperf_summary.json"
command_file="${RUN_DIR_VALUE}/iperf_command.txt"
error_file="${RUN_DIR_VALUE}/iperf_error.txt"
server_pid_file="${RUN_DIR_VALUE}/iperf_server.pid"

require_iperf3() {
  local container="$1"
  if ! container_running "${container}"; then
    echo "${container} is not running" | tee -a "${error_file}" >&2
    return 1
  fi
  if ! docker exec "${container}" sh -lc 'command -v iperf3' >/dev/null 2>&1; then
    echo "iperf3 tool_missing in ${container}" | tee -a "${error_file}" >&2
    return 1
  fi
}

cleanup() {
  if [[ -f "${server_pid_file}" ]]; then
    local server_pid
    server_pid="$(cat "${server_pid_file}")"
    if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" >/dev/null 2>&1; then
      kill -TERM "${server_pid}" >/dev/null 2>&1 || true
    fi
  fi
  docker exec oai-ext-dn sh -lc 'pkill -TERM iperf3 2>/dev/null || true' >/dev/null 2>&1 || true
}

trap cleanup EXIT

require_iperf3 oai-ext-dn
require_iperf3 oai-nr-ue

append_event "${RUN_DIR_VALUE}" "iperf_server_start" "target=${IPERF_TARGET};mode=${IPERF_MODE}"
docker exec oai-ext-dn iperf3 -s -1 >"${server_log}" 2>&1 &
server_pid=$!
printf '%s\n' "${server_pid}" >"${server_pid_file}"
sleep 1

UE_IP="$(docker exec oai-nr-ue ip -4 -o addr show "${IPERF_INTERFACE}" 2>/dev/null \
  | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
if [[ -z "${UE_IP}" ]]; then
  echo "No IPv4 address found on oai-nr-ue interface ${IPERF_INTERFACE}" | tee -a "${error_file}" >&2
  exit 1
fi

client_command=(docker exec oai-nr-ue iperf3 -J -c "${IPERF_TARGET}" -t "${IPERF_DURATION}" -B "${UE_IP}")
if [[ "${IPERF_MODE}" == "udp" ]]; then
  client_command+=(-u)
fi

printf '%q ' "${client_command[@]}" >"${command_file}"
printf '\n' >>"${command_file}"

append_event "${RUN_DIR_VALUE}" "iperf_client_start" "target=${IPERF_TARGET};mode=${IPERF_MODE};duration=${IPERF_DURATION};interface=${IPERF_INTERFACE}"
if "${client_command[@]}" >"${raw_file}" 2>>"${RUN_DIR_VALUE}/iperf_client.stderr"; then
  append_event "${RUN_DIR_VALUE}" "iperf_client_end" "status=pass"
else
  append_event "${RUN_DIR_VALUE}" "iperf_client_end" "status=fail"
  echo "iperf3 client failed; see ${raw_file} and iperf_client.stderr" | tee -a "${error_file}" >&2
  exit 1
fi

python3 "${PROJECT_ROOT}/tools/parse_iperf.py" --raw "${raw_file}" --summary-out "${summary_file}"

echo "${RUN_DIR_VALUE}"
