#!/usr/bin/env bash

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root

TOPOLOGY="${1:-}"
if [[ -z "${TOPOLOGY}" ]]; then
  TOPOLOGY="$(detect_topology)"
fi
apply_topology "${TOPOLOGY}"

failures=0

echo "OAI RFsim handover testbed status (topology: ${TOPOLOGY})"
echo

printf '%-12s %-10s %-10s\n' "CONTAINER" "EXISTS" "RUNNING"
for container in "${CRITICAL_CONTAINERS[@]}"; do
  exists="no"
  running="no"
  if container_exists "${container}"; then
    exists="yes"
    if container_running "${container}"; then
      running="yes"
    else
      failures=$((failures + 1))
    fi
  else
    failures=$((failures + 1))
  fi
  printf '%-12s %-10s %-10s\n' "${container}" "${exists}" "${running}"
done

# The handover control endpoint (Telnet) only exists for the rfsim handover
# topologies; the USRP single-cell topology has no handover trigger.
if [[ "${HANDOVER_TYPE}" != "none" ]]; then
  echo
  if [[ "${HANDOVER_TYPE}" == "f1" ]]; then
    telnet_host="${CU_TELNET_HOST}"
    telnet_port="${CU_TELNET_PORT}"
    telnet_label="CU Telnet"
  else
    telnet_host="$(config_n2_source_gnb_ip)"
    telnet_port="$(config_n2_source_gnb_port)"
    telnet_label="Source gNB Telnet"
  fi

  if port_reachable "${telnet_host}" "${telnet_port}"; then
    echo "${telnet_label} ${telnet_host}:${telnet_port}: reachable"
  else
    echo "${telnet_label} ${telnet_host}:${telnet_port}: not reachable"
    failures=$((failures + 1))
  fi
fi

echo
if [[ "${RADIO_MODE}" == "usrp" ]]; then
  # Real radio with an external COTS UE: gate on the NG association, and report
  # UE attach as informational (the operator powers on the handset manually).
  if ngap_associated oai-gnb; then
    echo "gNB NG (N2) association to AMF: established"
  else
    echo "gNB NG (N2) association to AMF: not established"
    failures=$((failures + 1))
  fi

  ue_count="$(amf_registered_ue_count)"
  if [[ "${ue_count}" -gt 0 ]]; then
    echo "COTS UE: ${ue_count} registration event(s) seen in AMF logs"
  else
    echo "COTS UE: none attached yet (power on the handset / toggle airplane mode)"
  fi
elif container_running oai-nr-ue; then
  ue_ip="$(ue_data_interface_ip || true)"
  if [[ -n "${ue_ip}" ]]; then
    echo "UE PDU session: ready (${ue_ip})"
  else
    echo "UE PDU session: not established (oaitun_ue1 missing)"
    failures=$((failures + 1))
  fi

  dn_target="$(config_ping_target)"
  ping_iface="$(config_ping_interface)"
  if [[ -n "${ue_ip}" ]] && ue_data_plane_reachable "${dn_target}" "${ping_iface}"; then
    echo "UE data plane ${dn_target} via ${ping_iface:-default route}: reachable"
  else
    echo "UE data plane ${dn_target} via ${ping_iface:-default route}: not reachable"
    failures=$((failures + 1))
  fi
else
  echo "UE PDU session: unavailable (oai-nr-ue not running)"
fi

echo
if tailscale_may_be_active; then
  echo "Tailscale: may be active"
  echo "Warning: if nc handover triggering fails, try: sudo tailscale down"
else
  echo "Tailscale: not detected"
fi

echo
if [[ "${failures}" -eq 0 ]]; then
  echo "SUMMARY: PASS"
  exit 0
fi

echo "SUMMARY: FAIL (${failures} critical check(s) failed)"
exit 1
