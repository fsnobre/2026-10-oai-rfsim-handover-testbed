#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TOPOLOGY="${1:-f1}"
apply_topology "${TOPOLOGY}"
ensure_project_root

case "${TOPOLOGY}" in
  f1)            run_tag="f1_handover_smoke" ;;
  n2-monolithic) run_tag="n2_monolithic_smoke" ;;
  n2-cu-du)      run_tag="n2_cu_du_smoke" ;;
esac

run_dir="$(create_run_dir "${run_tag}")"
run_id="$(basename "${run_dir}")"
start_time="$(timestamp_utc)"
status="failed"
handover_triggered=false
ping_started=false
ping_parsed=false
ping_capture_started=false
ping_precheck_passed=false
ping_metrics_valid=false
iperf_enabled=false
iperf_required=false
iperf_started=false
iperf_completed=false
iperf_status="disabled"
iperf_error=""
iperf_pid=""
iperf_exit_status=0
IPERF_TARGET="${IPERF_TARGET:-$(config_iperf_target)}"
IPERF_TARGET="${IPERF_TARGET:-192.168.70.135}"
IPERF_MODE="${IPERF_MODE:-$(config_iperf_mode)}"
IPERF_MODE="${IPERF_MODE:-udp}"
IPERF_DURATION="${IPERF_DURATION:-$(config_iperf_duration)}"
IPERF_DURATION="${IPERF_DURATION:-10}"
IPERF_ENABLED_VALUE="${IPERF_ENABLED:-$(config_iperf_enabled)}"
IPERF_REQUIRED_VALUE="${IPERF_REQUIRED:-0}"
ue_data_ready=false
ue_data_ready_target="${PING_TARGET:-$(config_ping_target)}"
ping_interface="${PING_INTERFACE:-$(config_ping_interface)}"
ue_data_ready_timeout_seconds="${UE_DATA_READY_TIMEOUT:-120}"
ping_error=""
notes="Smoke test did not complete."

json_metric() {
  local file="$1"
  local key="$2"

  if [[ ! -f "${file}" ]]; then
    printf 'null'
    return 0
  fi

  python3 -c 'import json, sys
data = json.load(open(sys.argv[1]))
value = data.get(sys.argv[2])
print("null" if value is None else value)
' "${file}" "${key}"
}

json_shell_string_or_null() {
  local value="$1"

  if [[ -z "${value}" || "${value}" == "null" ]]; then
    printf 'null'
    return 0
  fi

  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "${value}"
}

containers_json() {
  local json="["
  local first=true
  for item in "${CRITICAL_CONTAINERS[@]}"; do
    [[ "${first}" == "true" ]] || json+=", "
    json+="\"${item}\""
    first=false
  done
  json+="]"
  printf '%s\n' "${json}"
}

finish_summary() {
  local end_time
  local ping_summary
  local iperf_summary
  end_time="$(timestamp_utc)"
  ping_summary="${run_dir}/ping_summary.json"
  iperf_summary="${run_dir}/iperf_summary.json"

  if [[ "${ping_started}" == "true" ]]; then
    stop_ping_capture "${run_dir}"
  fi
  if [[ "${iperf_started}" == "true" && "${iperf_completed}" != "true" && -n "${iperf_pid}" ]]; then
    kill -TERM "${iperf_pid}" >/dev/null 2>&1 || true
    wait "${iperf_pid}" >/dev/null 2>&1 || true
    iperf_status="failed"
    iperf_error="${iperf_error:-iperf interrupted before completion}"
  elif [[ "${iperf_enabled}" == "true" && "${iperf_status}" == "pending" ]]; then
    iperf_status="skipped"
    iperf_error="${iperf_error:-smoke test ended before iperf started}"
  fi

  cat >"${run_dir}/summary.json" <<EOF
{
  "run_id": "$(json_escape "${run_id}")",
  "topology": "$(json_escape "${TOPOLOGY}")",
  "start_time": "$(json_escape "${start_time}")",
  "end_time": "$(json_escape "${end_time}")",
  "status": "$(json_escape "${status}")",
  "containers_checked": $(containers_json),
  "handover_triggered": ${handover_triggered},
  "ping_target": "$(json_escape "${PING_TARGET:-$(config_ping_target)}")",
  "ping_interface": "$(json_escape "${ping_interface}")",
  "ue_data_ready": ${ue_data_ready},
  "ue_data_ready_target": "$(json_escape "${ue_data_ready_target}")",
  "ue_data_ready_timeout_seconds": ${ue_data_ready_timeout_seconds},
  "ping_capture_started": ${ping_capture_started},
  "ping_precheck_passed": ${ping_precheck_passed},
  "ping_parsed": ${ping_parsed},
  "ping_metrics_valid": ${ping_metrics_valid},
  "ping_error": $(json_shell_string_or_null "${ping_error}"),
  "packets_transmitted": $(json_metric "${ping_summary}" packets_transmitted),
  "packets_received": $(json_metric "${ping_summary}" packets_received),
  "packet_loss_percent": $(json_metric "${ping_summary}" packet_loss_percent),
  "rtt_min_ms": $(json_metric "${ping_summary}" rtt_min_ms),
  "rtt_avg_ms": $(json_metric "${ping_summary}" rtt_avg_ms),
  "rtt_max_ms": $(json_metric "${ping_summary}" rtt_max_ms),
  "estimated_interruption_ms": $(json_metric "${ping_summary}" estimated_interruption_ms),
  "first_ping_after_handover_ms": $(json_metric "${ping_summary}" first_ping_after_handover_ms),
  "iperf_enabled": ${iperf_enabled},
  "iperf_required": ${iperf_required},
  "iperf_status": "$(json_escape "${iperf_status}")",
  "iperf_target": "$(json_escape "${IPERF_TARGET}")",
  "iperf_mode": "$(json_escape "${IPERF_MODE}")",
  "iperf_interface": "$(json_escape "${PING_INTERFACE:-oaitun_ue1}")",
  "iperf_duration_seconds": ${IPERF_DURATION},
  "iperf_error": $(json_shell_string_or_null "${iperf_error}"),
  "iperf_protocol": $(json_shell_string_or_null "$(json_metric "${iperf_summary}" protocol)"),
  "iperf_mbps": $(json_metric "${iperf_summary}" mbps),
  "iperf_sender_mbps": $(json_metric "${iperf_summary}" sender_mbps),
  "iperf_jitter_ms": $(json_metric "${iperf_summary}" jitter_ms),
  "iperf_lost_packets": $(json_metric "${iperf_summary}" lost_packets),
  "iperf_packets": $(json_metric "${iperf_summary}" packets),
  "iperf_lost_percent": $(json_metric "${iperf_summary}" lost_percent),
  "iperf_retransmits": $(json_metric "${iperf_summary}" retransmits),
  "notes": "$(json_escape "${notes}")"
}
EOF
}

trap finish_summary EXIT

append_event "${run_dir}" "smoke_start" "run_id=${run_id} topology=${TOPOLOGY}"

if ! command_exists python3; then
  notes="python3 is required for ping parsing."
  echo "[smoke] python3 is required for ping parsing." >&2
  exit 1
fi

"${SCRIPT_DIR}/preflight_check.sh" "${TOPOLOGY}"
echo

if "${SCRIPT_DIR}/status.sh" "${TOPOLOGY}" >/dev/null 2>&1; then
  echo "[smoke] Testbed (${TOPOLOGY}) already appears ready."
else
  echo "[smoke] Starting testbed (topology=${TOPOLOGY})."
  "${SCRIPT_DIR}/up.sh" "${TOPOLOGY}"
fi

"${SCRIPT_DIR}/wait_ready.sh" "${TOPOLOGY}" --timeout 180

RUN_DIR="${run_dir}" "${SCRIPT_DIR}/poststart_check.sh" || true
echo

PING_TARGET="${PING_TARGET:-$(config_ping_target)}"
PING_INTERFACE="${PING_INTERFACE:-$(config_ping_interface)}"
ue_data_ready_target="${PING_TARGET}"
ping_interface="${PING_INTERFACE}"
ue_data_ready_timeout_seconds="${UE_DATA_READY_TIMEOUT:-120}"
PING_INTERVAL="${PING_INTERVAL:-$(config_ping_interval)}"
PING_POST_HANDOVER_SECONDS="${PING_POST_HANDOVER_SECONDS:-$(config_ping_post_handover_seconds)}"

case "${IPERF_ENABLED_VALUE,,}" in
  1|true|yes|on) iperf_enabled=true ;;
esac
case "${IPERF_REQUIRED_VALUE,,}" in
  1|true|yes|on)
    iperf_required=true
    iperf_enabled=true
    ;;
esac

if [[ "${iperf_enabled}" == "true" ]]; then
  iperf_status="pending"
fi

echo "[smoke] Waiting for UE data plane to reach ${PING_TARGET} via ${PING_INTERFACE:-default}."
if RUN_DIR="${run_dir}" PING_TARGET="${PING_TARGET}" PING_INTERFACE="${PING_INTERFACE}" UE_DATA_READY_TIMEOUT="${ue_data_ready_timeout_seconds}" "${SCRIPT_DIR}/wait_ue_data_ready.sh"; then
  ue_data_ready=true
else
  ue_data_ready=false
  ping_precheck_passed=false
  status="failed"
  notes="UE data plane did not become ready; handover was not triggered."
  ping_error="UE data readiness failed for target ${PING_TARGET} via ${PING_INTERFACE:-default}"
  "${SCRIPT_DIR}/collect_logs.sh" --run-dir "${run_dir}" >/dev/null
  echo "[smoke] ${notes}" >&2
  exit 1
fi

echo "[smoke] Starting ping capture from nr-ue to ${PING_TARGET} via ${PING_INTERFACE:-default}."
if RUN_DIR="${run_dir}" PING_TARGET="${PING_TARGET}" PING_INTERFACE="${PING_INTERFACE}" PING_INTERVAL="${PING_INTERVAL}" "${SCRIPT_DIR}/start_ping_capture.sh" >/dev/null; then
  ping_started=true
  ping_capture_started=true
  ping_precheck_passed=true
else
  ping_error="$(cat "${run_dir}/ping_error.txt" 2>/dev/null || printf 'ping capture precheck failed')"
  notes="Ping precheck failed; handover was not triggered because ping metrics would be invalid."
  "${SCRIPT_DIR}/collect_logs.sh" --run-dir "${run_dir}" >/dev/null
  echo "[smoke] ${notes}" >&2
  exit 1
fi

if [[ "${iperf_enabled}" == "true" ]]; then
  echo "[smoke] Starting ${IPERF_MODE} iperf test to ${IPERF_TARGET} for ${IPERF_DURATION}s."
  RUN_DIR="${run_dir}" \
    IPERF_INTERFACE="${PING_INTERFACE:-oaitun_ue1}" \
    IPERF_TARGET="${IPERF_TARGET}" \
    IPERF_MODE="${IPERF_MODE}" \
    IPERF_DURATION="${IPERF_DURATION}" \
    "${SCRIPT_DIR}/run_iperf_test.sh" >"${run_dir}/iperf_runner.log" 2>&1 &
  iperf_pid=$!
  iperf_started=true
fi
sleep 3

append_event "${run_dir}" "before_handover" "ready=true"
RUN_DIR="${run_dir}" "${SCRIPT_DIR}/trigger_handover.sh" "${TOPOLOGY}"
handover_triggered=true
append_event "${run_dir}" "after_handover" "triggered=true"

echo "[smoke] Keeping ping capture running for ${PING_POST_HANDOVER_SECONDS}s after handover."
sleep "${PING_POST_HANDOVER_SECONDS}"

stop_ping_capture "${run_dir}"
ping_started=false

if [[ "${iperf_started}" == "true" ]]; then
  set +e
  wait "${iperf_pid}"
  iperf_exit_status=$?
  set -e
  iperf_completed=true
  if [[ "${iperf_exit_status}" -eq 0 && -f "${run_dir}/iperf_summary.json" ]]; then
    iperf_status="pass"
    echo "[smoke] iperf metrics captured."
  else
    iperf_status="failed"
    iperf_error="$(cat "${run_dir}/iperf_error.txt" 2>/dev/null || printf 'iperf runner failed with status %s' "${iperf_exit_status}")"
    echo "[smoke] iperf failed: ${iperf_error}" >&2
  fi
fi

python3 "${PROJECT_ROOT}/tools/parse_ping.py" \
  --raw "${run_dir}/ping_raw.log" \
  --csv "${run_dir}/ping.csv" \
  --events "${run_dir}/events.csv" \
  --summary-out "${run_dir}/ping_summary.json"
ping_parsed=true

packets_transmitted="$(json_metric "${run_dir}/ping_summary.json" packets_transmitted)"
parser_ping_metrics_valid="$(json_metric "${run_dir}/ping_summary.json" ping_metrics_valid)"
if [[ "${packets_transmitted}" == "0" || ( "${parser_ping_metrics_valid}" != "True" && "${parser_ping_metrics_valid}" != "true" ) ]]; then
  ping_metrics_valid=false
  ping_error="$(json_metric "${run_dir}/ping_summary.json" ping_error)"
  if [[ "${ping_error}" == "null" ]]; then
    ping_error="ping parser found zero transmitted packets"
  fi
  notes="Ping capture produced no usable samples; handover command was sent but metrics are invalid."
  "${SCRIPT_DIR}/collect_logs.sh" --run-dir "${run_dir}" >/dev/null
  append_event "${run_dir}" "ping_metrics_invalid" "packets_transmitted=${packets_transmitted}"
  echo "[smoke] ${notes}" >&2
  exit 1
fi

"${SCRIPT_DIR}/collect_logs.sh" --run-dir "${run_dir}" >/dev/null

if [[ "${iperf_required}" == "true" && "${iperf_status}" != "pass" ]]; then
  notes="Ping metrics are valid, but required iperf measurement failed."
  append_event "${run_dir}" "smoke_end" "status=failed;iperf_status=${iperf_status}"
  echo "[smoke] ${notes}" >&2
  exit 1
fi

status="pass"
ping_metrics_valid=true
notes="Startup/readiness checks passed, ping capture ran across handover, and ${TOPOLOGY} handover command was sent. iperf_status=${iperf_status}."
append_event "${run_dir}" "smoke_end" "status=${status}"

echo "${run_dir}"
