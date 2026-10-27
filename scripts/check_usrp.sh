#!/usr/bin/env bash

# Standalone USRP X310 probe. Confirms the device is reachable on the host
# 10GbE link and that UHD can enumerate/probe it. UHD is run inside the gNB
# image so the UHD version matches the one the gNB will use. Read-only: it does
# not start the testbed or modify configuration.

set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

ensure_project_root
apply_topology usrp-cots

GNB_IMAGE="${GNB_IMAGE:-oaisoftwarealliance/oai-gnb:develop}"
SDR_ADDR="${SDR_ADDR:-$(config_value_after_key "sdr_addr" "192.168.40.2")}"

status=0

echo "=== USRP X310 check (sdr_addr=${SDR_ADDR}) ==="
echo

# 1. IP reachability on the 10GbE link.
if ping -c 1 -W 2 "${SDR_ADDR}" >/dev/null 2>&1; then
  echo "[PASS] USRP reachable at ${SDR_ADDR}"
else
  echo "[FAIL] USRP not reachable at ${SDR_ADDR} — check 10GbE cabling and host NIC IP on ${SDR_ADDR%.*}.0/24" >&2
  status=1
fi

# 2. Socket buffers (UHD recommends large buffers for 10GbE).
rmem_max="$(cat /proc/sys/net/core/rmem_max 2>/dev/null || echo 0)"
if [[ "${rmem_max}" -ge 24000000 ]]; then
  echo "[PASS] net.core.rmem_max=${rmem_max}"
else
  echo "[WARN] net.core.rmem_max=${rmem_max} (recommend >= 33554432: sudo sysctl -w net.core.rmem_max=33554432 net.core.wmem_max=33554432)"
fi

# 3. UHD probe. Prefer host uhd_usrp_probe; otherwise run it inside the gNB image.
echo
if command_exists uhd_usrp_probe; then
  echo "[INFO] Probing with host uhd_usrp_probe"
  if uhd_usrp_probe --args "addr=${SDR_ADDR}" 2>&1 | sed 's/^/    /'; then
    echo "[PASS] uhd_usrp_probe completed"
  else
    echo "[FAIL] uhd_usrp_probe failed" >&2
    status=1
  fi
elif docker image inspect "${GNB_IMAGE}" >/dev/null 2>&1; then
  echo "[INFO] Probing with UHD inside ${GNB_IMAGE} (host networking)"
  if docker run --rm --network host "${GNB_IMAGE}" \
      uhd_usrp_probe --args "addr=${SDR_ADDR}" 2>&1 | sed 's/^/    /'; then
    echo "[PASS] uhd_usrp_probe (in container) completed"
  else
    echo "[FAIL] uhd_usrp_probe (in container) failed" >&2
    status=1
  fi
else
  echo "[WARN] No host uhd_usrp_probe and ${GNB_IMAGE} not pulled — cannot probe UHD yet" >&2
fi

echo
if [[ "${status}" -eq 0 ]]; then
  echo "=== USRP check: OK ==="
else
  echo "=== USRP check: FAILED ===" >&2
fi
exit "${status}"
