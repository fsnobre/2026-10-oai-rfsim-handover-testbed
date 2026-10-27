#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

TOPOLOGY="${1:-}"
if [[ -z "${TOPOLOGY}" ]]; then
  TOPOLOGY="$(detect_topology)"
fi
apply_topology "${TOPOLOGY}"

warn_tailscale

if ! command_exists nc; then
  echo "nc is required to trigger handover." >&2
  exit 1
fi

run_dir="${RUN_DIR:-}"

if [[ "${HANDOVER_TYPE}" == "f1" ]]; then
  HOST="${CU_TELNET_HOST}"
  PORT="${CU_TELNET_PORT}"
  LABEL="CU"
  CMD="ci trigger_f1_ho"
else
  HOST="${N2_SOURCE_GNB_TELNET_HOST:-$(config_n2_source_gnb_ip)}"
  PORT="${N2_SOURCE_GNB_TELNET_PORT:-$(config_n2_source_gnb_port)}"
  N2_TARGET_PCI="${N2_TARGET_PCI:-$(config_n2_target_pci)}"
  N2_UE_RRC_ID="${N2_UE_RRC_ID:-$(config_n2_ue_rrc_id)}"
  LABEL="source gNB"
  CMD="ci trigger_n2_ho ${N2_TARGET_PCI},${N2_UE_RRC_ID}"
fi

if ! port_reachable "${HOST}" "${PORT}"; then
  echo "${LABEL} Telnet ${HOST}:${PORT} is not reachable." >&2
  exit 1
fi

start_ts="$(timestamp_utc)"
echo "[trigger_handover] topology=${TOPOLOGY} start=${start_ts}"
# NOTE: tools/parse_ping.py keys the handover interruption estimate on the
# "handover_trigger_start" event name across all topologies. Keep this name
# stable; renaming it (e.g. to a topology-specific name) silently breaks the
# interruption metric. See docs/en/guide-measurement-pipeline.md.
append_event "${run_dir}" "handover_trigger_start" "${LABEL}_telnet ${HOST}:${PORT}"

response="$(echo "${CMD}" | nc -N "${HOST}" "${PORT}")"
printf '%s\n' "${response}"

if printf '%s\n' "${response}" | grep -qiE 'no single UE|could not find any UE|no UE in RRC'; then
  echo "[trigger_handover] Failed: no eligible UE is connected in RRC." >&2
  append_event "${run_dir}" "handover_trigger_failed" "command=${CMD};reason=no_ue_in_rrc"
  exit 1
fi

end_ts="$(timestamp_utc)"
echo "[trigger_handover] end=${end_ts}"
append_event "${run_dir}" "handover_trigger_end" "command=${CMD}"
