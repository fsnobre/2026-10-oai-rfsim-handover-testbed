#!/usr/bin/env bash

# Measure the user-plane handover interruption time.
#
# Runs a bounded, high-rate ICMP capture from oai-nr-ue to the EXT-DN while a
# handover is triggered mid-capture, then parses the reply stream with
# tools/parse_ping.py to compute estimated_interruption_ms. Unlike the full
# smoke test this does NOT bring up the testbed or run iperf: it assumes the
# stack is already active (same precondition as the dashboard quick trigger).
#
#   ./scripts/measure_interruption.sh [f1|n2-monolithic|n2-cu-du]
#
# Env overrides:
#   INTERRUPTION_PING_INTERVAL   seconds between probes (default 0.01 = 10 ms)
#   INTERRUPTION_PRE_SECONDS     baseline capture before the trigger (default 2)
#   INTERRUPTION_POST_SECONDS    capture after the trigger (default 4)
#   UE_DATA_READY_TIMEOUT        data-plane readiness timeout (default 60)
#   PING_TARGET / PING_INTERFACE override the experiment config values
#
# The finer probe cadence resolves the tens-of-ms outage that the ~1 Hz live
# Overview probe cannot see. Sub-200 ms intervals require the ping to run as
# root, which the oai-nr-ue container already does.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

TOPOLOGY="${1:-f1}"
apply_topology "${TOPOLOGY}"
ensure_project_root

case "${TOPOLOGY}" in
  f1)            run_tag="f1_interruption" ;;
  n2-monolithic) run_tag="n2_monolithic_interruption" ;;
  n2-cu-du)      run_tag="n2_cu_du_interruption" ;;
  *) echo "Unsupported topology: ${TOPOLOGY} (use f1, n2-monolithic, n2-cu-du)" >&2; exit 2 ;;
esac

PING_TARGET="${PING_TARGET:-$(config_ping_target)}"
PING_INTERFACE="${PING_INTERFACE:-$(config_ping_interface)}"
PING_INTERVAL="${INTERRUPTION_PING_INTERVAL:-0.01}"
PRE_SECONDS="${INTERRUPTION_PRE_SECONDS:-2}"
POST_SECONDS="${INTERRUPTION_POST_SECONDS:-4}"
UE_DATA_READY_TIMEOUT="${UE_DATA_READY_TIMEOUT:-60}"

run_dir="$(create_run_dir "${run_tag}")"
ping_started=false

cleanup() {
  if [[ "${ping_started}" == "true" ]]; then
    stop_ping_capture "${run_dir}" || true
    ping_started=false
  fi
}
trap cleanup EXIT

append_event "${run_dir}" "interruption_measure_start" "topology=${TOPOLOGY};interval=${PING_INTERVAL};pre=${PRE_SECONDS};post=${POST_SECONDS}"

echo "[interruption] Waiting for UE data plane to reach ${PING_TARGET} via ${PING_INTERFACE:-default}."
if ! RUN_DIR="${run_dir}" PING_TARGET="${PING_TARGET}" PING_INTERFACE="${PING_INTERFACE}" \
  UE_DATA_READY_TIMEOUT="${UE_DATA_READY_TIMEOUT}" "${SCRIPT_DIR}/wait_ue_data_ready.sh"; then
  echo "[interruption] UE data plane not ready; aborting before capture." >&2
  exit 1
fi

echo "[interruption] Starting ${PING_INTERVAL}s ping capture from oai-nr-ue to ${PING_TARGET}."
if ! RUN_DIR="${run_dir}" PING_TARGET="${PING_TARGET}" PING_INTERFACE="${PING_INTERFACE}" \
  PING_INTERVAL="${PING_INTERVAL}" "${SCRIPT_DIR}/start_ping_capture.sh" >/dev/null; then
  echo "[interruption] Ping capture precheck failed; see ${run_dir}/ping_error.txt" >&2
  exit 1
fi
ping_started=true

echo "[interruption] Capturing ${PRE_SECONDS}s baseline before handover."
sleep "${PRE_SECONDS}"

echo "[interruption] Triggering ${TOPOLOGY} handover."
RUN_DIR="${run_dir}" "${SCRIPT_DIR}/trigger_handover.sh" "${TOPOLOGY}"

echo "[interruption] Capturing ${POST_SECONDS}s after handover."
sleep "${POST_SECONDS}"

stop_ping_capture "${run_dir}"
ping_started=false

python3 "${PROJECT_ROOT}/tools/parse_ping.py" \
  --raw "${run_dir}/ping_raw.log" \
  --csv "${run_dir}/ping.csv" \
  --events "${run_dir}/events.csv" \
  --summary-out "${run_dir}/ping_summary.json"

interruption_ms="$(python3 -c 'import json,sys
data=json.load(open(sys.argv[1]))
value=data.get("estimated_interruption_ms")
print("unknown" if value is None else value)' "${run_dir}/ping_summary.json" 2>/dev/null || echo unknown)"

append_event "${run_dir}" "interruption_measure_end" "estimated_interruption_ms=${interruption_ms}"

echo "[interruption] estimated_interruption_ms=${interruption_ms}"
# Stable sentinel so the dashboard can locate this run from the job stdout tail.
printf 'INTERRUPTION_RUN_DIR=%s\n' "${run_dir}"
printf '%s\n' "${run_dir}"
