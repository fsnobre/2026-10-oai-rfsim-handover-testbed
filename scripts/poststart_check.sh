#!/usr/bin/env bash

set -uo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

RUN_DIR_VALUE="${RUN_DIR:-}"

# If a run directory is provided, tee all output into it
if [[ -n "${RUN_DIR_VALUE}" ]]; then
  mkdir -p "${RUN_DIR_VALUE}"
  exec > >(tee "${RUN_DIR_VALUE}/poststart_check.txt") 2>&1
fi

issues=0

_pass() { printf '[PASS] %s\n' "$1"; }
_warn() { printf '[WARN] %s\n' "$1"; issues=$(( issues + 1 )); }
_fail() { printf '[FAIL] %s\n' "$1"; issues=$(( issues + 1 )); }
_info() { printf '[INFO] %s\n' "$1"; }

echo "=== OAI RFsim testbed — post-start check ==="
echo "[poststart] $(timestamp_utc)"
echo

# --- Auto-detect topology from running containers ---
topology="$(detect_topology)"
apply_topology "${topology}"
_info "Detected topology: ${topology}"
echo

# --- 5GC containers ---
echo "--- 5GC ---"
for name in oai-amf oai-smf oai-upf; do
  if container_running "${name}"; then
    health="$(container_health_status "${name}")"
    _pass "${name}: running (health=${health})"
  elif container_exists "${name}"; then
    _fail "${name}: exists but not running"
  else
    _warn "${name}: not found"
  fi
done
echo

# --- RAN containers + telnet target ---
echo "--- RAN ---"
telnet_host=""
telnet_port=""
case "${topology}" in
  f1)
    ran_containers=(oai-cu oai-du0 oai-du1 oai-nr-ue)
    telnet_host="${CU_TELNET_HOST}"
    telnet_port="${CU_TELNET_PORT}"
    ;;
  n2-monolithic)
    ran_containers=(oai-gnb0 oai-gnb1 oai-nr-ue)
    telnet_host="$(config_n2_source_gnb_ip)"
    telnet_port="$(config_n2_source_gnb_port)"
    ;;
  n2-cu-du)
    ran_containers=(oai-cu0 oai-du0 oai-cu1 oai-du1 oai-nr-ue)
    telnet_host="192.168.70.150"
    telnet_port="9090"
    ;;
  *)
    ran_containers=(oai-nr-ue)
    ;;
esac

for name in "${ran_containers[@]}"; do
  if container_running "${name}"; then
    health="$(container_health_status "${name}")"
    _pass "${name}: running (health=${health})"
  elif container_exists "${name}"; then
    _fail "${name}: exists but not running"
  else
    _warn "${name}: not found"
  fi
done
echo

# --- gNB Telnet reachability ---
if [[ -n "${telnet_host}" && -n "${telnet_port}" ]]; then
  echo "--- gNB Telnet ---"
  if port_reachable "${telnet_host}" "${telnet_port}"; then
    _pass "Telnet ${telnet_host}:${telnet_port} reachable"
  else
    _fail "Telnet ${telnet_host}:${telnet_port} not reachable — gNB may not be ready yet or Tailscale is active"
  fi
  echo
fi

# --- UE PDU session interface ---
echo "--- UE data plane ---"
if container_running oai-nr-ue; then
  ue_ip="$(docker exec oai-nr-ue ip -4 -o addr show oaitun_ue1 2>/dev/null \
    | awk '{print $4}' | cut -d/ -f1 | head -1 || true)"
  if [[ -n "${ue_ip}" ]]; then
    _pass "oaitun_ue1 present with IP: ${ue_ip}"
  else
    _warn "oaitun_ue1 not yet present — UE has not established a PDU session (this is normal if the stack just started)"
  fi

  # Quick connectivity check to data network target
  dn_target="$(config_ping_target)"
  ping_iface="$(config_ping_interface)"
  ping_args=(-c 1 -W 2)
  [[ -n "${ping_iface}" ]] && ping_args+=(-I "${ping_iface}")

  if docker exec oai-nr-ue ping "${ping_args[@]}" "${dn_target}" >/dev/null 2>&1; then
    _pass "UE can reach ${dn_target} via ${ping_iface:-default route}"
  else
    _warn "UE cannot reach ${dn_target} via ${ping_iface:-default route} — PDU session may not be ready yet"
  fi
else
  _warn "oai-nr-ue not running — skipping UE data-plane checks"
fi
echo

# --- Fatal error scan in recent container logs ---
echo "--- Log scan (last 100 lines per container) ---"
fatal_pattern='(FATAL|Segmentation fault|core dumped)'
all_containers=("${ran_containers[@]}" oai-amf)
for name in "${all_containers[@]}"; do
  if ! container_running "${name}"; then
    continue
  fi
  hits="$(docker logs --tail 100 "${name}" 2>&1 \
    | grep -iE "${fatal_pattern}" \
    | head -3 \
    || true)"
  if [[ -n "${hits}" ]]; then
    _fail "${name}: fatal error pattern found in logs:"$'\n'"${hits}"
  else
    _pass "${name}: no fatal errors in last 100 log lines"
  fi
done
echo

echo "=== Post-start check: ${issues} issue(s) ==="
if [[ "${issues}" -gt 0 ]]; then
  echo "[poststart] Issues detected — review the items above."
  [[ -n "${RUN_DIR_VALUE}" ]] && echo "[poststart] Output saved to ${RUN_DIR_VALUE}/poststart_check.txt"
else
  echo "[poststart] Testbed looks healthy."
fi

# Always exit 0 — diagnostic only, never blocks the caller
exit 0
