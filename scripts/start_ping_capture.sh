#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

RUN_DIR_VALUE="${RUN_DIR:-}"
PING_TARGET_VALUE="${PING_TARGET:-}"
PING_INTERFACE_VALUE="${PING_INTERFACE:-}"
PING_INTERVAL_VALUE="${PING_INTERVAL:-}"

usage() {
  cat <<'EOF'
Usage: RUN_DIR=path [PING_TARGET=ip] [PING_INTERFACE=iface] [PING_INTERVAL=seconds] ./scripts/start_ping_capture.sh

Starts timestamped ping capture from inside the oai-nr-ue container and writes:
  RUN_DIR/ping_raw.log
  RUN_DIR/ping.pid
  RUN_DIR/ping_command.txt
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ensure_project_root

if [[ -z "${RUN_DIR_VALUE}" ]]; then
  echo "RUN_DIR is required." >&2
  exit 2
fi

mkdir -p "${RUN_DIR_VALUE}"

if [[ -z "${PING_TARGET_VALUE}" ]]; then
  PING_TARGET_VALUE="$(config_ping_target)"
fi

if [[ -z "${PING_INTERFACE_VALUE}" ]]; then
  PING_INTERFACE_VALUE="$(config_ping_interface)"
fi

if [[ -z "${PING_TARGET_VALUE}" ]]; then
  echo "PING_TARGET is required or must be set in experiments/manual_f1_handover/config.yaml." >&2
  exit 2
fi

if [[ -z "${PING_INTERVAL_VALUE}" ]]; then
  PING_INTERVAL_VALUE="$(config_ping_interval)"
fi

if ! container_running oai-nr-ue; then
  echo "oai-nr-ue is not running; cannot start ping capture." >&2
  exit 1
fi

raw_log="${RUN_DIR_VALUE}/ping_raw.log"
pid_file="${RUN_DIR_VALUE}/ping.pid"
command_file="${RUN_DIR_VALUE}/ping_command.txt"
precheck_status_file="${RUN_DIR_VALUE}/ping_precheck_status.txt"
error_file="${RUN_DIR_VALUE}/ping_error.txt"
ping_command=(docker exec oai-nr-ue ping)
precheck_command=(docker exec oai-nr-ue ping)
if [[ -n "${PING_INTERFACE_VALUE}" ]]; then
  ping_command+=(-I "${PING_INTERFACE_VALUE}")
  precheck_command+=(-I "${PING_INTERFACE_VALUE}")
fi
ping_command+=(-D -i "${PING_INTERVAL_VALUE}" "${PING_TARGET_VALUE}")
precheck_command+=(-c 2 "${PING_TARGET_VALUE}")

if [[ -f "${pid_file}" ]] && kill -0 "$(cat "${pid_file}")" >/dev/null 2>&1; then
  echo "Ping capture is already running with PID $(cat "${pid_file}")" >&2
  exit 1
fi

{
  printf '# ping_target=%s\n' "${PING_TARGET_VALUE}"
  printf '# ping_interface=%s\n' "${PING_INTERFACE_VALUE:-none}"
  printf '# ping_interval_seconds=%s\n' "${PING_INTERVAL_VALUE}"
  printf '# ping_source_container=oai-nr-ue\n'
  printf '# precheck_command=%q ' "${precheck_command[@]}"
  printf '\n'
} >"${raw_log}"

printf '%q ' "${ping_command[@]}" >"${command_file}"
printf '\n' >>"${command_file}"

append_event "${RUN_DIR_VALUE}" "ping_precheck_start" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};source=oai-nr-ue"
if "${precheck_command[@]}" >"${RUN_DIR_VALUE}/ping_precheck_raw.log" 2>&1; then
  printf 'passed\n' >"${precheck_status_file}"
  append_event "${RUN_DIR_VALUE}" "ping_precheck_passed" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none}"
else
  printf 'failed\n' >"${precheck_status_file}"
  printf 'ping precheck failed: ' >"${error_file}"
  printf '%q ' "${precheck_command[@]}" >>"${error_file}"
  printf '\n' >>"${error_file}"
  append_event "${RUN_DIR_VALUE}" "ping_precheck_failed" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};see=ping_precheck_raw.log"
  echo "Ping precheck failed; see ${RUN_DIR_VALUE}/ping_precheck_raw.log" >&2
  exit 1
fi

append_event "${RUN_DIR_VALUE}" "ping_capture_start" "target=${PING_TARGET_VALUE};interface=${PING_INTERFACE_VALUE:-none};interval=${PING_INTERVAL_VALUE};source=oai-nr-ue"

"${ping_command[@]}" >>"${raw_log}" 2>&1 &

ping_pid=$!
printf '%s\n' "${ping_pid}" >"${pid_file}"
printf '%s\n' "${PING_TARGET_VALUE}" >"${RUN_DIR_VALUE}/ping_target.txt"
printf '%s\n' "${PING_INTERFACE_VALUE}" >"${RUN_DIR_VALUE}/ping_interface.txt"

echo "${ping_pid}"
